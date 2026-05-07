#!/usr/bin/env python3
"""
scripts/generate_weekly_digest.py — automated weekly digest (§8.10.5 + Gate 4 stats)

Aggregates stats from raw/<source>/<week>/*.meta.json + wiki/ingest-queue/<week>/
and writes wiki/weekly-digest/YYYY-Www-digest.md.

Usage:
    python3 scripts/generate_weekly_digest.py 2026-W19
    python3 scripts/generate_weekly_digest.py 2026-W19 --dry-run   # print to stdout
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
RAW_DIR = REPO_ROOT / "raw"
QUEUE_DIR = REPO_ROOT / "wiki" / "ingest-queue"
DIGEST_DIR = REPO_ROOT / "wiki" / "weekly-digest"


@dataclass
class SourceStats:
    name: str
    tier: str = "?"
    count: int = 0
    approved: int = 0
    pending_review: int = 0
    skipped_low: int = 0
    scores: list[int] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def pass_rate(self) -> float:
        return self.approved / self.count if self.count else 0.0


@dataclass
class Gate4Stats:
    applied_articles: int = 0          # articles with ingest_log_ref set
    applied_sections_total: int = 0
    per_target: Counter = field(default_factory=Counter)
    queue_open: int = 0
    queue_open_by_target: Counter = field(default_factory=Counter)
    queue_archived: int = 0
    orphans: int = 0


# Rough token / latency model calibrated from live W19 runs
# Gate 3 (rubric scoring):  input ~2k + output ~0.3k per article = ~2.3k tokens, ~1.5s
# Gate 4 (propose):         input ~3k + output ~2k per (article × target) = ~5k tokens, ~4s
GATE3_TOKENS_PER_CALL = 2300
GATE3_LATENCY_SEC = 1.5
GATE4_TOKENS_PER_CALL = 5000
GATE4_LATENCY_SEC = 4.0


@dataclass
class CostEstimate:
    gate3_calls: int = 0
    gate4_calls: int = 0            # 1 per (article × target) Gate 4 LLM invocation

    @property
    def total_tokens(self) -> int:
        return (self.gate3_calls * GATE3_TOKENS_PER_CALL
                + self.gate4_calls * GATE4_TOKENS_PER_CALL)

    @property
    def total_latency_sec(self) -> float:
        return (self.gate3_calls * GATE3_LATENCY_SEC
                + self.gate4_calls * GATE4_LATENCY_SEC)


# ─────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────

def collect_article_stats(week: str) -> tuple[list[SourceStats], list[dict]]:
    """Return (per-source stats, flat list of all meta dicts)."""
    by_src: dict[str, SourceStats] = {}
    all_metas: list[dict] = []
    for meta_path in sorted(RAW_DIR.glob(f"*/{week}/*.meta.json")):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        m["_path"] = str(meta_path)
        m["_basename"] = meta_path.name.replace(".meta.json", "")
        all_metas.append(m)
        src = meta_path.parent.parent.name
        st = by_src.setdefault(src, SourceStats(name=src, tier=m.get("source_tier", "?")))
        st.count += 1
        status = m.get("ingest_status", "unknown")
        if status == "approved":
            st.approved += 1
        elif status == "pending-review":
            st.pending_review += 1
        elif status == "skipped-low-relevance":
            st.skipped_low += 1
        if m.get("relevance_score") is not None:
            st.scores.append(m["relevance_score"])
    return sorted(by_src.values(), key=lambda s: -s.avg_score), all_metas


def collect_gate4_stats(week: str, metas: list[dict]) -> Gate4Stats:
    g = Gate4Stats()
    for m in metas:
        if m.get("ingest_log_ref"):
            g.applied_articles += 1
            for target in m.get("ingest_targets") or []:
                g.per_target[target] += 1
    # Count applied sections by scanning ingest_history across product pages
    # (approximation: count targets × avg sections — skipped, we just report
    # targets distribution)
    g.applied_sections_total = g.per_target.total() if hasattr(g.per_target, "total") else sum(g.per_target.values())

    # Queue files
    week_queue = QUEUE_DIR / week
    if week_queue.exists():
        for p in week_queue.rglob("*.md"):
            if p.name == "README.md":
                continue
            if "_orphans" in p.parts:
                g.orphans += 1
            else:
                g.queue_open += 1
                # parse target slug from filename: <slug>--<article>.md
                name = p.stem
                if "--" in name:
                    slug = name.split("--", 1)[0]
                    g.queue_open_by_target[slug] += 1
    archive_week = QUEUE_DIR / "_archive" / week
    if archive_week.exists():
        g.queue_archived = sum(1 for p in archive_week.rglob("*.md"))
    return g


def collect_cost_estimate(metas: list[dict], g4: Gate4Stats) -> CostEstimate:
    """Approximate LLM cost from article counts.
    Gate 3: 1 call per article that received a relevance_score (T1 exempt = no call).
    Gate 4: 1 call per (article × target) attempted — use applied + review count.
    """
    c = CostEstimate()
    for m in metas:
        # Gate 3 was called iff article has relevance_score AND wasn't T1-exempt.
        # T1-exempt articles get score=10 without LLM; we can't easily distinguish,
        # so count all articles with relevance_score (overcounts slightly for T1).
        if m.get("relevance_score") is not None:
            c.gate3_calls += 1
    # Gate 4: applied_sections + open queue + archived = rough call count
    # (each target per article = 1 call; counting targets distribution + queue items)
    c.gate4_calls = (sum(g4.per_target.values()) + g4.queue_open
                     + g4.queue_archived + g4.orphans)
    return c


# ─────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────

def _week_range(week: str) -> str:
    """Return human-readable date range for an ISO week (YYYY-Www)."""
    try:
        y, w = week.split("-W")
        y, w = int(y), int(w)
        mon = dt.date.fromisocalendar(y, w, 1)
        sun = mon + dt.timedelta(days=6)
        return f"{mon.isoformat()} ~ {sun.isoformat()}"
    except Exception:
        return ""


def render_digest(week: str, sources: list[SourceStats], metas: list[dict],
                  g4: Gate4Stats, cost: CostEstimate | None = None) -> str:
    total = sum(s.count for s in sources)
    approved = sum(s.approved for s in sources)
    pending = sum(s.pending_review for s in sources)
    skipped = sum(s.skipped_low for s in sources)
    all_scores = [sc for s in sources for sc in s.scores]
    avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
    pass_rate = approved / total if total else 0.0
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))

    lines = [
        "---",
        "type: digest",
        f"slug: {week}-digest",
        f"title: {week} RetailIQ 週報",
        f"period: {week} ({_week_range(week)})",
        f"generated_at: {now.strftime('%Y-%m-%d')}",
        "generated_by: v2.0 Full 5-gate pipeline + Gate 4 stats",
        "agents_version: v2.0",
        "---",
        "",
        f"# 📊 {week} RetailIQ 週報",
        "",
        "> 依 `AGENTS.md` §8.10.5 + §8.11 規範產出；**首份整合 Gate 4 流程的週報**。",
        "",
        "---",
        "",
        "## 總覽",
        "",
        f"- **擷取總數**：{total} 篇（{len(sources)} 個來源）",
        f"- **平均分數**：{avg:.2f} / 10",
        f"- **通過比例**：{pass_rate:.0%}（{approved} / {total}）",
        "",
        "### 狀態分布",
        "",
        "| 狀態 | 篇數 | 占比 |",
        "|---|---|---|",
        f"| ✅ approved | {approved} | {approved/total:.0%}" + " |" if total else "| ✅ approved | 0 | — |",
        f"| 🟡 pending-review | {pending} | {pending/total:.0%}" + " |" if total else "| 🟡 pending-review | 0 | — |",
        f"| ❌ skipped-low-relevance | {skipped} | {skipped/total:.0%}" + " |" if total else "| ❌ skipped-low-relevance | 0 | — |",
        "",
        "---",
        "",
        "## 各來源健康度",
        "",
        "| 來源 | Tier | 篇數 | 平均分 | 通過率 |",
        "|---|---|---|---|---|",
    ]
    for s in sources:
        health = "🟢 優" if s.avg_score >= 6 else "🟡 可" if s.avg_score >= 3 else "🔴 差"
        lines.append(
            f"| {s.name} | {s.tier} | {s.count} | {s.avg_score:.2f} | {s.pass_rate:.0%} | {health} |"
        )
    # Fix header to include the health column
    lines[-len(sources) - 2] = "| 來源 | Tier | 篇數 | 平均分 | 通過率 | 健康度 |"
    lines[-len(sources) - 1] = "|---|---|---|---|---|---|"

    lines += [
        "",
        "---",
        "",
        "## Gate 4 運作（v2.0 新增）",
        "",
        f"- **自動套用至 wiki/products/**：{g4.applied_articles} 篇文章，共 {g4.applied_sections_total} 個 target × article",
        f"- **Review queue 開放中**：{g4.queue_open} 檔（+ {g4.orphans} orphans）",
        f"- **Review queue 已決策歸檔**：{g4.queue_archived} 檔",
        "",
    ]

    # Top wiki page receivers
    if g4.per_target:
        lines += ["### 本週被 Gate 4 更新的 wiki 頁面", "", "| 產品頁 | 更新次數 |", "|---|---|"]
        for slug, n in g4.per_target.most_common():
            lines.append(f"| {slug} | {n} |")
        lines.append("")

    # Queue backlog warning
    if g4.queue_open > 20:
        lines += [f"> ⚠️ **Review queue 累積 {g4.queue_open} 檔（> 20 警戒線）— 請優先清理**", ""]
    elif g4.queue_open > 0:
        lines += [f"> 📋 Review queue 目前 {g4.queue_open}/20 檔。", ""]

    # Cost estimate (E)
    if cost is not None:
        lines += [
            "---",
            "",
            "## LLM 成本估算（v2.1 新增）",
            "",
            "> 依校準後的平均值估算（Gate 3: 2.3k tokens/call、1.5s；Gate 4: 5k tokens/call、4s）。實際值依文章長度浮動 ±30%。",
            "",
            f"- **Gate 3 LLM 呼叫**：{cost.gate3_calls} 次",
            f"- **Gate 4 LLM 呼叫**：{cost.gate4_calls} 次",
            f"- **估算 token 總量**：{cost.total_tokens:,}",
            f"- **估算 LLM 時間**：{cost.total_latency_sec:.0f}s ({cost.total_latency_sec/60:.1f} min)",
            "",
        ]

    # Top / bottom articles
    ranked = sorted(
        [m for m in metas if m.get("relevance_score") is not None],
        key=lambda m: -m["relevance_score"],
    )
    if ranked:
        lines += [
            "---",
            "",
            "## Top 5 高分文章",
            "",
            "| 分數 | 來源 | 標題 |",
            "|---|---|---|",
        ]
        for m in ranked[:5]:
            title = (m.get("source_title") or "").replace("|", "\\|")[:60]
            lines.append(f"| {m['relevance_score']} | {m.get('source_type', '?')} | {title} |")
        lines += [
            "",
            "## Bottom 5 低分文章",
            "",
            "| 分數 | 來源 | 標題 |",
            "|---|---|---|",
        ]
        for m in ranked[-5:]:
            title = (m.get("source_title") or "").replace("|", "\\|")[:60]
            lines.append(f"| {m['relevance_score']} | {m.get('source_type', '?')} | {title} |")

    lines += [
        "",
        "---",
        "",
        f"> Generated by `scripts/generate_weekly_digest.py` at {now.strftime('%Y-%m-%dT%H:%M:%S+08:00')}",
        "",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Sandbox-safe write
# ─────────────────────────────────────────────────────────────────────

def render_empty_digest(week: str) -> str:
    """Minimal digest for weeks with no ingested articles.

    Used for scheduled runs at the start of a week before the crawler has
    gathered content, or for weeks that were genuinely skipped. Preserves
    the digest file as a placeholder so downstream tooling (lint, index)
    has a consistent artefact to reference.
    """
    return f"""---
type: digest
slug: {week}-digest
title: {week} RetailIQ 週報（空白週）
period: {week} ({_week_range(week)})
generated_at: {_now_iso()}
generated_by: v2.0 Full 5-gate pipeline + Gate 4 stats (empty-week placeholder)
agents_version: v2.0
empty_week: true
---

# 📊 {week} RetailIQ 週報

> ⚠️ **空白週**：本週尚無 ingest 活動（`raw/*/<week>/` 目錄不存在或無 meta.json 檔）。

## 可能原因

1. 週初自動排程先產報告，crawler 尚未執行
2. 連假/節日無內容更新
3. 所有來源本週都被 Gate 1a/1b/2 擋下（極不可能，但理論上可能）

## 下一步

- 等 crawler 完成後重跑：`python3 scripts/generate_weekly_digest.py {week}`
- 若確認是 crawler 未跑，手動觸發：`python3 scripts/ingest_agent.py --limit 10`
- 若確認全週跳過（例如全部 dedup），此檔可歸檔標註 skipped

---

> Generated by `scripts/generate_weekly_digest.py` at {_now_iso()}
> This is an empty-week placeholder; re-run the generator once raw data arrives.
"""


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sandbox_safe_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    try:
        os.replace(tmp, path)
        return
    except PermissionError:
        pass
    try:
        if path.exists():
            subprocess.run(["git", "rm", "-f", "--quiet", str(path)],
                           cwd=REPO_ROOT, capture_output=True, check=False)
        path.write_text(content, encoding="utf-8")
    finally:
        if tmp.exists():
            subprocess.run(["git", "clean", "-f", "--quiet", str(tmp)],
                           cwd=REPO_ROOT, capture_output=True)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate weekly RetailIQ digest")
    ap.add_argument("week", help="ISO week, e.g. 2026-W19")
    ap.add_argument("--dry-run", action="store_true", help="print to stdout only")
    ap.add_argument("--out", help="override output path")
    ap.add_argument("--allow-empty", action="store_true",
                    help="emit empty-week placeholder digest instead of erroring "
                         "when no articles are found (for scheduled runs early in week)")
    args = ap.parse_args()

    sources, metas = collect_article_stats(args.week)
    g4 = collect_gate4_stats(args.week, metas)
    cost = collect_cost_estimate(metas, g4)

    if not metas:
        if not args.allow_empty:
            print(f"❌ no articles found for {args.week}", file=sys.stderr)
            print(f"   (pass --allow-empty to emit a placeholder digest)",
                  file=sys.stderr)
            return 1
        content = render_empty_digest(args.week)
    else:
        content = render_digest(args.week, sources, metas, g4, cost=cost)

    if args.dry_run:
        print(content)
        return 0

    out = Path(args.out) if args.out else DIGEST_DIR / f"{args.week}-digest.md"
    sandbox_safe_write(out, content)
    rel = out.relative_to(REPO_ROOT) if str(out).startswith(str(REPO_ROOT)) else out
    if not metas:
        print(f"✅ wrote {rel} (empty-week placeholder)")
    else:
        print(f"✅ wrote {rel}")
        print(f"   {len(metas)} articles, {g4.applied_articles} Gate 4-applied, "
              f"{g4.queue_open} queue open, {g4.orphans} orphans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
