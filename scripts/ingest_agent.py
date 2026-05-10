#!/usr/bin/env python3
"""
RetailIQ Ingest Agent v0.1
════════════════════════════════════════════════════════════════════

實作 AGENTS.md §8.5 的 Gate 1a + Gate 2：
  - Gate 1a: exact hash dedup                → skipped-duplicate
  - Gate 1b: embedding similarity ≥ 0.98     → skipped-trivial-change
  - Gate 2:  URL + title 過濾                 → skipped-filtered
  - Gate 3:  LLM relevance scoring (rubric)   → approved/pending-review/skipped-low-relevance
  - Gate 4:  LLM ingest to wiki               → wiki/products/* + wiki/ingest-queue/*

讀取：  wiki/sources-config.yaml (v1.1)
輸出：  raw/<source>/<YYYY-Www>/
         ├── <slug>_YYYYMMDD.html (原始 HTML)
         ├── <slug>_YYYYMMDD.txt  (提取純文字)
         └── <slug>_YYYYMMDD.meta.json

使用方式：
  python3 scripts/ingest_agent.py                    # 跑所有 enabled sources
  python3 scripts/ingest_agent.py --source six-colors  # 只跑一個
  python3 scripts/ingest_agent.py --dry-run           # 不寫檔，只報告
  python3 scripts/ingest_agent.py --limit 3           # 每個 source 最多 3 篇
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

# Embedded YAML parser（無 pip 依賴；詳見 scripts/yaml_mini.py）
# Support both `python3 -m scripts.ingest_agent` (package) and
# `python3 scripts/ingest_agent.py` (direct execution).
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT_DIR = _SCRIPTS_DIR.parent
if __package__:
    from . import yaml_mini as yaml
else:
    # Direct execution: add repo root to sys.path so `scripts` is importable
    # as a package (enables `from scripts.xxx import` in sibling modules).
    if str(_REPO_ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT_DIR))
    from scripts import yaml_mini as yaml  # type: ignore[no-redef]

# ════════════════════════════════════════════════════════════════════
# 常數
# ════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "wiki" / "sources-config.yaml"
RAW_DIR = REPO_ROOT / "raw"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15 "
      "RetailIQ-IngestBot/0.1")
TZ = timezone(timedelta(hours=8))  # Asia/Taipei


# ════════════════════════════════════════════════════════════════════
# 資料結構
# ════════════════════════════════════════════════════════════════════

@dataclass
class SourceConfig:
    name: str
    tier: str
    enabled: bool
    display_name: str
    base_url: str
    fetch_method: str  # rss | http | json_api | manual
    locale: str = "en-US"
    rss_url: str = ""
    seed_urls: list[str] = field(default_factory=list)
    allow_url_patterns: list[str] = field(default_factory=list)
    deny_url_patterns: list[str] = field(default_factory=list)
    title_blocklist_regex: str = ""
    title_required_regex: str = ""
    require_apple_newsroom_cross_ref: bool = False
    notes: str = ""


@dataclass
class Article:
    title: str
    url: str
    pub_date: str = ""
    description: str = ""


@dataclass
class IngestResult:
    source: str
    url: str
    title: str
    status: str  # pending | approved | pending-review | skipped-duplicate | skipped-trivial-change | skipped-filtered | skipped-low-relevance | failed
    reason: str = ""
    basename: str = ""


# ════════════════════════════════════════════════════════════════════
# 1. Config 載入
# ════════════════════════════════════════════════════════════════════

def load_sources(config_path: Path) -> list[SourceConfig]:
    with config_path.open() as f:
        cfg = yaml.safe_load(f)
    sources = []
    for name, s in (cfg.get("sources") or {}).items():
        sources.append(SourceConfig(
            name=name,
            tier=s.get("tier", "T2"),
            enabled=s.get("enabled", True),
            display_name=s.get("display_name", name),
            base_url=s.get("base_url", ""),
            fetch_method=s.get("fetch_method", "rss"),
            locale=s.get("locale", "en-US"),
            rss_url=s.get("rss_url", ""),
            seed_urls=s.get("seed_urls", []) or [],
            allow_url_patterns=s.get("allow_url_patterns", []) or [],
            deny_url_patterns=s.get("deny_url_patterns", []) or [],
            title_blocklist_regex=s.get("title_blocklist_regex", "") or "",
            title_required_regex=s.get("title_required_regex", "") or "",
            require_apple_newsroom_cross_ref=s.get("require_apple_newsroom_cross_ref", False),
            notes=s.get("notes", "") or "",
        ))
    return sources


# ════════════════════════════════════════════════════════════════════
# 2. Fetcher
# ════════════════════════════════════════════════════════════════════

def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


class TextExtractor(HTMLParser):
    """簡化 HTML→text；取 <p>, <h1-3>, <li> 內容。未來換 trafilatura。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._capture = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("p", "h1", "h2", "h3", "li"):
            self._capture = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("p", "h1", "h2", "h3", "li") and self._capture:
            text = "".join(self._buf).strip()
            if text:
                self.parts.append(text)
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)


def extract_text(html: bytes, max_chars: int = 8000) -> str:
    try:
        html_str = html.decode("utf-8", errors="replace")
    except Exception:
        html_str = html.decode("latin-1", errors="replace")
    parser = TextExtractor()
    try:
        parser.feed(html_str)
    except Exception:
        pass
    return "\n\n".join(parser.parts)[:max_chars]


def parse_rss(xml_bytes: bytes, max_items: int = 30) -> list[Article]:
    """RSS 2.0 + Atom 都支援。"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logging.warning(f"XML parse error: {e}")
        return []

    items: list[Article] = []

    # RSS 2.0
    for item in root.iter("item"):
        items.append(Article(
            title=(item.findtext("title") or "").strip(),
            url=(item.findtext("link") or "").strip(),
            pub_date=(item.findtext("pubDate") or "").strip(),
            description=(item.findtext("description") or "").strip(),
        ))
        if len(items) >= max_items:
            return items

    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.iter(f"{ns}entry"):
        link_el = entry.find(f"{ns}link")
        link = link_el.get("href") if link_el is not None else ""
        items.append(Article(
            title=(entry.findtext(f"{ns}title") or "").strip(),
            url=link,
            pub_date=(entry.findtext(f"{ns}updated") or "").strip(),
            description=(entry.findtext(f"{ns}summary") or "").strip(),
        ))
        if len(items) >= max_items:
            return items

    return items


# ════════════════════════════════════════════════════════════════════
# 3. Filters（§8.9 實作）
# ════════════════════════════════════════════════════════════════════

def check_url(url: str, src: SourceConfig) -> tuple[bool, str]:
    """Return (passes, reason_if_failed)."""
    for pat in src.deny_url_patterns:
        if re.search(pat, url):
            return False, f"URL matches deny: {pat}"
    if src.allow_url_patterns:
        if not any(re.search(pat, url) for pat in src.allow_url_patterns):
            return False, "URL not in allow list"
    return True, ""


def check_title(title: str, src: SourceConfig) -> tuple[bool, str]:
    if src.title_blocklist_regex:
        if re.search(src.title_blocklist_regex, title, re.I):
            return False, f"title hit blocklist"
    if src.title_required_regex:
        if not re.search(src.title_required_regex, title, re.I):
            return False, "title did not match required_regex"
    return True, ""


# ════════════════════════════════════════════════════════════════════
# 4. Storage + Hash Dedup (Gate 1a)
# ════════════════════════════════════════════════════════════════════

def sha256_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def iso_week(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(TZ)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def slugify(s: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen] or "item"


def load_all_existing_hashes() -> dict[str, Path]:
    """掃全部 /raw/ 既有 meta.json，回傳 hash → file_path，用於 Gate 1a。"""
    result = {}
    if not RAW_DIR.exists():
        return result
    for meta_path in RAW_DIR.glob("*/*/*.meta.json"):
        try:
            m = json.loads(meta_path.read_text())
            h = m.get("content_hash", "")
            if h:
                result[h] = meta_path
        except Exception:
            continue
    return result


def write_raw(
    src: SourceConfig,
    article: Article,
    html_bytes: bytes,
    text: str,
    extra_meta: dict | None = None,
    dry_run: bool = False,
) -> tuple[str, Path]:
    week = iso_week()
    date_str = datetime.now(TZ).strftime("%Y%m%d")
    slug = slugify(article.title)
    basename = f"{slug}_{date_str}"
    folder = RAW_DIR / src.name / week
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{basename}.html").write_bytes(html_bytes)
        (folder / f"{basename}.txt").write_text(text, encoding="utf-8")

    meta = {
        "source_url": article.url,
        "source_type": src.name,
        "source_tier": src.tier,
        "source_title": article.title,
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "fetched_by": "ingest-agent-v0.1",
        "content_hash": sha256_of(text),
        "content_type": "text/html",
        "content_size_bytes": len(html_bytes),
        "http_status": 200,
        "locale": src.locale,
        "related_wiki_pages": [],
        "ingest_status": "pending",  # 等 Gate 3 LLM 打分（v0.2）
        "ingest_log_ref": None,
        "notes": f"pubDate: {article.pub_date}" if article.pub_date else None,
    }
    if extra_meta:
        meta.update(extra_meta)

    meta_path = folder / f"{basename}.meta.json"
    if not dry_run:
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return basename, meta_path


# ════════════════════════════════════════════════════════════════════
# 5. Pipeline
# ════════════════════════════════════════════════════════════════════

class IngestPipeline:
    def __init__(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        skip_scoring: bool = False,
        skip_gate1b: bool = False,
    ):
        self.dry_run = dry_run
        self.limit = limit
        self.skip_scoring = skip_scoring
        self.skip_gate1b = skip_gate1b
        self.existing_hashes = load_all_existing_hashes()
        logging.info(f"Loaded {len(self.existing_hashes)} existing hashes for dedup")
        # LLM client (shared by Gate 1b + Gate 3)
        self._llm = None
        if not (skip_scoring and skip_gate1b):
            try:
                from .llm_client import LLMClient
            except ImportError:
                from scripts.llm_client import LLMClient  # type: ignore[no-redef]
                self._llm = LLMClient()
                logging.info(
                    f"LLM client ready: chat={self._llm.chat_model} embed={self._llm.embedding_model} @ {self._llm.endpoint}"
                )
            except Exception as e:
                logging.warning(f"LLM client init failed: {e}; skipping Gate 1b + Gate 3")
                self.skip_scoring = True
                self.skip_gate1b = True
        # Gate 1b embedding index
        self._embed_index = None
        if not self.skip_gate1b and self._llm is not None:
            try:
                from .embedding_index import EmbeddingIndex
            except ImportError:
                from scripts.embedding_index import EmbeddingIndex  # type: ignore[no-redef]
                self._embed_index = EmbeddingIndex(
                    path=RAW_DIR / "_embeddings-index.json",
                    client=self._llm,
                )
                logging.info(f"Gate 1b index loaded: {len(self._embed_index)} cached embeddings")
            except Exception as e:
                logging.warning(f"Gate 1b index init failed: {e}; skipping Gate 1b")
                self.skip_gate1b = True

    def fetch_articles(self, src: SourceConfig) -> list[Article]:
        if src.fetch_method == "rss":
            if not src.rss_url:
                logging.warning(f"{src.name}: fetch_method=rss but no rss_url")
                return []
            try:
                xml = http_get(src.rss_url)
            except Exception as e:
                logging.error(f"{src.name}: RSS fetch failed: {e}")
                return []
            return parse_rss(xml)

        if src.fetch_method == "http" and src.seed_urls:
            return [Article(title=url.split("/")[-2] or url, url=url) for url in src.seed_urls]

        if src.fetch_method == "manual":
            return []  # admin-upload 另走流程

        logging.warning(f"{src.name}: unsupported fetch_method '{src.fetch_method}'")
        return []

    def process_article(self, src: SourceConfig, article: Article) -> IngestResult:
        if not article.url:
            return IngestResult(src.name, "", article.title, "failed", "no URL")

        # Gate 2: URL filter
        ok, reason = check_url(article.url, src)
        if not ok:
            return IngestResult(src.name, article.url, article.title, "skipped-filtered", reason)

        # Gate 2: Title filter
        ok, reason = check_title(article.title, src)
        if not ok:
            return IngestResult(src.name, article.url, article.title, "skipped-filtered", reason)

        # Fetch article
        try:
            html = http_get(article.url)
        except Exception as e:
            return IngestResult(src.name, article.url, article.title, "failed", f"fetch: {e}")

        text = extract_text(html)
        if len(text) < 200:
            return IngestResult(src.name, article.url, article.title, "failed", "text too short")

        # Gate 1a: Hash dedup
        h = sha256_of(text)
        if h in self.existing_hashes:
            return IngestResult(
                src.name, article.url, article.title,
                "skipped-duplicate",
                f"hash matches {self.existing_hashes[h].relative_to(REPO_ROOT)}",
            )

        # Gate 1b: Embedding similarity dedup (§8.5b)
        gate1b_vec = None
        if not self.skip_gate1b and self._embed_index is not None:
            vec, dup = self._embed_index.check_and_stage(h, src.name, "", text)
            if dup is not None:
                dup_basename, sim = dup
                return IngestResult(
                    src.name, article.url, article.title,
                    "skipped-trivial-change",
                    f"embed sim={sim:.4f} ≥ {self._embed_index.threshold} vs {dup_basename}",
                )
            gate1b_vec = vec

        # Pass → write to raw/
        basename, meta_path = write_raw(src, article, html, text, dry_run=self.dry_run)
        # 即刻加到 existing hashes 避免同一批重複
        self.existing_hashes[h] = Path("<just-written>")

        # Gate 1b: cache embedding for future dedup
        if gate1b_vec is not None and self._embed_index is not None:
            self._embed_index.add(h, src.name, basename, gate1b_vec)

        # Gate 3: LLM relevance scoring (§8.10)
        # T1 + admin-upload 依 §8.10.4 跳過打分（預設滿分 10）
        if src.tier == "T1" or src.name == "admin-upload":
            score_total, status, reason = 10, "approved", "T1/admin exempt (§8.10.4)"
        elif self.skip_scoring:
            score_total, status, reason = None, "pending", "Gate 3 skipped (--skip-scoring)"
        else:
            try:
                try:
                    from .relevance_scorer import score_article, status_for_score
                except ImportError:
                    from scripts.relevance_scorer import score_article, status_for_score  # type: ignore[no-redef]
                score = score_article(article.title, text, client=self._llm)
                score_total = score.total
                status = status_for_score(score_total)
                reason = f"score={score_total} {score.reasoning[:40]}"
                # 更新 meta.json 加 relevance 欄位
                if not self.dry_run:
                    self._patch_meta_with_score(meta_path, score)
            except Exception as e:
                logging.warning(f"Gate 3 score failed for {article.url}: {e}")
                score_total, status, reason = None, "pending", f"scoring failed: {e}"

        return IngestResult(
            src.name, article.url, article.title,
            status, reason, basename=basename,
        )

    @staticmethod
    def _patch_meta_with_score(meta_path: Path, score) -> None:
        """把 Gate 3 打分結果寫入 meta.json（atomic replace）。"""
        import json as _json
        if not meta_path.exists():
            return
        meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        meta["relevance_score"] = score.total
        meta["relevance_reasoning"] = score.reasoning
        meta["relevance_breakdown"] = score.breakdown
        meta["key_entities"] = score.key_entities
        meta["ingest_status"] = (
            "skipped-low-relevance" if score.total < 5 else
            "pending-review" if score.total < 7 else
            "approved"
        )
        tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        tmp.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(meta_path)

    def process_source(self, src: SourceConfig) -> list[IngestResult]:
        if not src.enabled:
            logging.info(f"SKIP {src.name} (enabled=false)")
            return []

        logging.info(f"▶ {src.name} (Tier {src.tier})")
        articles = self.fetch_articles(src)
        if self.limit:
            articles = articles[: self.limit]
        results = []
        for a in articles:
            r = self.process_article(src, a)
            results.append(r)
            icon = {
                "pending": "✓",
                "skipped-filtered": "⊘",
                "skipped-duplicate": "=",
                "skipped-trivial-change": "≈",
                "failed": "✗",
            }.get(r.status, "?")
            logging.info(f"  {icon} [{r.status:20s}] {r.title[:55]}")
        return results


# ════════════════════════════════════════════════════════════════════
# 6. CLI + 報告
# ════════════════════════════════════════════════════════════════════

def print_report(all_results: list[IngestResult]) -> None:
    from collections import Counter, defaultdict
    by_status: Counter[str] = Counter()
    by_source_status: dict[str, Counter[str]] = defaultdict(Counter)
    for r in all_results:
        by_status[r.status] += 1
        by_source_status[r.source][r.status] += 1

    print()
    print("═" * 70)
    print(" INGEST RESULTS")
    print("═" * 70)
    print(f"  Total articles processed: {len(all_results)}")
    for status in [
        "approved", "pending", "pending-review",
        "skipped-duplicate", "skipped-trivial-change",
        "skipped-filtered", "skipped-low-relevance",
        "failed",
    ]:
        n = by_status.get(status, 0)
        if n or status in ("pending", "failed"):  # always show pending/failed
            print(f"  {status:25s} {n:3d}")
    print()
    print(" Per-source breakdown:")
    print(f"  {'source':25s} {'ok':>4} {'dup':>4} {'triv':>4} {'filt':>4} {'low':>4} {'fail':>4}")
    for src in sorted(by_source_status.keys()):
        c = by_source_status[src]
        ok = c.get("approved", 0) + c.get("pending", 0) + c.get("pending-review", 0)
        print(
            f"  {src:25s} "
            f"{ok:4d} "
            f"{c.get('skipped-duplicate', 0):4d} "
            f"{c.get('skipped-trivial-change', 0):4d} "
            f"{c.get('skipped-filtered', 0):4d} "
            f"{c.get('skipped-low-relevance', 0):4d} "
            f"{c.get('failed', 0):4d}"
        )
    print("═" * 70)


def main() -> int:
    ap = argparse.ArgumentParser(description="RetailIQ Ingest Agent v0.1")
    ap.add_argument("--source", help="只跑單一 source")
    ap.add_argument("--dry-run", action="store_true", help="不寫檔，只報告")
    ap.add_argument("--skip-scoring", action="store_true",
                    help="跳過 Gate 3 LLM 打分（走舊 v0.1 行為，pending 全部）")
    ap.add_argument("--skip-gate1b", action="store_true", help="跳過 Gate 1b embedding 近重偵測")
    ap.add_argument("--skip-gate4", action="store_true", help="跳過 Gate 4 wiki ingest (post-pass)")
    ap.add_argument("--gate4-only", action="store_true",
                    help="跳過 RSS fetch + Gates 1-3，只跑 Gate 4 於 raw/ 既有 approved/pending-review 文章")
    ap.add_argument("--week", help="--gate4-only 時限制單一週；預設全部")
    ap.add_argument("--limit", type=int, help="每個 source 最多 N 篇")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    if not CONFIG_PATH.exists():
        print(f"❌ Config not found: {CONFIG_PATH}", file=sys.stderr)
        return 1

    sources = load_sources(CONFIG_PATH)
    if args.source:
        sources = [s for s in sources if s.name == args.source]
        if not sources:
            print(f"❌ Source '{args.source}' not found", file=sys.stderr)
            return 1

    enabled = [s for s in sources if s.enabled]
    logging.info(f"Loaded {len(sources)} sources, {len(enabled)} enabled")
    if args.dry_run:
        logging.info("DRY RUN — no files written")

    # ═══ Gate 4-only mode: skip the RSS fetch + ingest pipeline ═══
    if args.gate4_only:
        if args.skip_gate4:
            logging.error("--gate4-only + --skip-gate4 is contradictory")
            return 1
        try:
            from .llm_client import LLMClient
            from .gate4_pipeline import run_gate4_pass, GATE4_ELIGIBLE_STATUSES
        except ImportError:
            from scripts.llm_client import LLMClient  # type: ignore[no-redef]
            from scripts.gate4_pipeline import run_gate4_pass, GATE4_ELIGIBLE_STATUSES  # type: ignore[no-redef]
        try:
            llm = LLMClient()
        except Exception as e:
            logging.error(f"LLM client init failed: {e}")
            return 1
        glob_pat = f"*/{args.week}/*.meta.json" if args.week else "*/*/*.meta.json"
        meta_paths: list[Path] = []
        for p in sorted(RAW_DIR.glob(glob_pat)):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if m.get("ingest_status") in GATE4_ELIGIBLE_STATUSES and not m.get("ingest_log_ref"):
                meta_paths.append(p)
        logging.info(f"Gate 4-only mode: {len(meta_paths)} eligible article(s) "
                     f"(status ∈ {sorted(GATE4_ELIGIBLE_STATUSES)}, no ingest_log_ref)")
        if not meta_paths:
            logging.info("nothing to do; exiting.")
            return 0
        report = run_gate4_pass(meta_paths, llm=llm, dry_run=args.dry_run)
        logging.info(
            f"Gate 4-only summary: processed={report.processed} "
            f"applied={report.applied_articles} sections={report.total_applied_sections} "
            f"review={report.review_items} orphans={report.orphans} errors={len(report.errors)}"
        )
        for e in report.errors[:5]:
            logging.warning(f"  Gate 4 error: {e}")
        return 0

    pipeline = IngestPipeline(
        dry_run=args.dry_run,
        limit=args.limit,
        skip_scoring=args.skip_scoring,
        skip_gate1b=args.skip_gate1b,
    )
    all_results: list[IngestResult] = []
    for src in enabled:
        all_results.extend(pipeline.process_source(src))

    # Persist Gate 1b embedding index
    if pipeline._embed_index is not None and not args.dry_run:
        pipeline._embed_index.save()

    print_report(all_results)

    # ═══ Gate 4: wiki ingest post-pass ═══
    # Only eligible on articles that passed Gates 1a+1b+2+3 this run
    # (status='pending' means Gate 3 was skipped; Gate 4 still works on
    # existing approved/pending-review articles in raw/)
    if not args.skip_gate4 and pipeline._llm is not None:
        try:
            from .gate4_pipeline import run_gate4_pass
        except ImportError:
            from scripts.gate4_pipeline import run_gate4_pass  # type: ignore[no-redef]
        # Collect meta paths for this run's successful writes
        meta_paths: list[Path] = []
        for r in all_results:
            if r.status in ("pending", "approved", "pending-review") and r.basename:
                # Find the meta file
                for candidate in RAW_DIR.glob(f"{r.source}/*/{r.basename}.meta.json"):
                    meta_paths.append(candidate)
                    break
        if meta_paths:
            logging.info("")
            logging.info(f"═══ Gate 4 post-pass: {len(meta_paths)} article(s) eligible ═══")
            report = run_gate4_pass(meta_paths, llm=pipeline._llm, dry_run=args.dry_run)
            logging.info(
                f"Gate 4 summary: processed={report.processed} "
                f"applied={report.applied_articles} sections={report.total_applied_sections} "
                f"review={report.review_items} orphans={report.orphans} errors={len(report.errors)}"
            )
            for e in report.errors[:5]:
                logging.warning(f"  Gate 4 error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
