#!/usr/bin/env python3
"""
scripts/gate4_proposer.py — Gate 4 Phase 2 LLM proposer (dry-run)

Given an article + target wiki/product page, call LLM to produce structured
proposals for section updates. Does NOT write anything — purely produces JSON
for Phase 3 to act on.

Design: gate4-ingest.md §3.2 + §5
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from yaml_mini import loads as yloads           # noqa: E402
from llm_client import LLMClient, LLMError      # noqa: E402

REPO_ROOT = SCRIPTS.parent
RAW_DIR = REPO_ROOT / "raw"
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"

VALID_ACTIONS = {"update", "append", "suggest"}


@dataclass
class Proposal:
    section: str
    action: str            # update | append | suggest
    current_excerpt: Optional[str]
    new_content: str
    reason: str

    def validate(self) -> list[str]:
        errors = []
        if self.action not in VALID_ACTIONS:
            errors.append(f"invalid action: {self.action}")
        if not self.section.strip():
            errors.append("empty section")
        if not self.new_content.strip():
            errors.append("empty new_content")
        if len(self.reason) > 120:
            errors.append(f"reason too long: {len(self.reason)} > 120")
        return errors


@dataclass
class ProposalSet:
    target_valid: bool
    target_valid_reason: str
    proposals: list[Proposal]
    raw_response: str = ""     # kept for debug, not serialized to callers by default

    def to_dict(self) -> dict:
        return {
            "target_valid": self.target_valid,
            "target_valid_reason": self.target_valid_reason,
            "proposals": [asdict(p) for p in self.proposals],
        }


# ─────────────────────────────────────────────────────────────────────
# Page parsing
# ─────────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def split_frontmatter(md: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(md)
    if not m:
        return {}, md
    fm = yloads(m.group(1)) or {}
    body = md[m.end():]
    return fm, body


def extract_sections(body: str) -> dict[str, str]:
    """Return {heading (no ##): section content text} for ## level 2 headings."""
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        else:
            if current is not None:
                buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


# ─────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """你是 RetailIQ wiki 的 ingest 助手，負責從來源文章產生 wiki 頁面的段落更新建議。

[核心規則 — 請逐項在心中對照每個 proposal]

規則 1（段落所有權）：**決定 action 前，先看段落在哪個清單。**
- 若段落 ∈ ingest_managed_sections（可自動寫入）→ 用 "update" 或 "append"
- 若段落 ∈ human_owned_sections（人工創作區）→ **只能用 "suggest"**（不要用 update / append）
  ↳ human_owned 包含：賣點話術、Demo 腳本、Q&A、反對處理 — 這些需人類經驗，LLM 只提建議
- 若段落在 page 不存在 → 用 "append"（會走 review queue，由人決定要不要加）

規則 2（不編造）：每個 proposal 的 new_content 必須可從 ARTICLE 直接推得；找不到依據就不要產這個 proposal。

規則 3（preserve existing detail）：用 action=update 時，如果原段落已包含事實（如散熱設計、機身材質），而文章只補充新資訊，請**合併**而非整段替換。current_excerpt 幫你看到原內容。

規則 4（無關就說無關）：若文章主題與此 wiki 頁面不符（例如 Apple Watch 文章 vs iPhone 頁面），target_valid=false、proposals=[]。

[示範]
- 文章提到 A19 晶片規格 + 目標頁「核心規格」在 ingest_managed_sections → `{{"section":"核心規格","action":"update",...}}` ✅
- 文章提到一個新賣點 + 目標頁「五大賣點」在 human_owned_sections → `{{"section":"五大賣點","action":"suggest",...}}` ✅（**不是** update / append）
- 文章提到 AI 功能、目標頁沒有「AI 功能」段落 → `{{"section":"AI 功能","action":"append",...}}` ✅（會走 review）

[輸出格式 — 嚴格 JSON，不要 markdown fence]
{{
  "target_valid": <bool>,
  "target_valid_reason": "<≤40 字>",
  "proposals": [
    {{
      "section": "<段落標題（不含 ##）>",
      "action": "update" | "append" | "suggest",
      "current_excerpt": "<action=update 時填當前段落前 200 字以驗證 LLM 有讀到，否則 null>",
      "new_content": "<完整替換內容或新段落內容>",
      "reason": "<≤60 字>"
    }}
  ]
}}

=== ARTICLE ===
Title: {article_title}
Source: {article_source} (tier {tier})
Relevance score: {score}
Key entities: {entities}

{article_text}

=== TARGET PAGE: wiki/products/{slug}.md ===
Frontmatter:
  ingest_managed_sections: {ingest_managed}
  human_owned_sections: {human_owned}

Existing sections on this page (title : first 200 chars):
{sections_summary}
"""


def build_prompt(
    *,
    article_title: str,
    article_source: str,
    tier: str,
    score: int | None,
    entities: list[str],
    article_text: str,
    slug: str,
    frontmatter: dict,
    sections: dict[str, str],
    max_article_chars: int = 3000,
) -> str:
    text = article_text[:max_article_chars]
    if len(article_text) > max_article_chars:
        text += "\n\n[...TRUNCATED...]"
    sections_summary = "\n".join(
        f"  - {title}: {body[:200].replace(chr(10), ' ')}"
        for title, body in sections.items()
    ) or "  (no sections found)"
    return PROMPT_TEMPLATE.format(
        article_title=article_title,
        article_source=article_source,
        tier=tier,
        score=score if score is not None else "-",
        entities=entities,
        article_text=text,
        slug=slug,
        ingest_managed=frontmatter.get("ingest_managed_sections", []),
        human_owned=frontmatter.get("human_owned_sections", []),
        sections_summary=sections_summary,
    )


# ─────────────────────────────────────────────────────────────────────
# LLM call + parse
# ─────────────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> ProposalSet:
    """Robust JSON extraction (strips code fences if present)."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON: {e}\nraw: {raw[:300]!r}")

    proposals_raw = data.get("proposals") or []
    proposals: list[Proposal] = []
    for pr in proposals_raw:
        proposals.append(Proposal(
            section=pr.get("section", ""),
            action=pr.get("action", ""),
            current_excerpt=pr.get("current_excerpt"),
            new_content=pr.get("new_content", ""),
            reason=pr.get("reason", ""),
        ))
    return ProposalSet(
        target_valid=bool(data.get("target_valid", False)),
        target_valid_reason=str(data.get("target_valid_reason", "")),
        proposals=proposals,
        raw_response=raw,
    )


def propose(
    *,
    article_meta: dict,
    article_text: str,
    product_page_md: str,
    product_slug: str,
    client: LLMClient | None = None,
    max_article_chars: int = 3000,
) -> ProposalSet:
    """Main entry: article + target page → structured proposals."""
    client = client or LLMClient()
    fm, body = split_frontmatter(product_page_md)
    sections = extract_sections(body)
    prompt = build_prompt(
        article_title=article_meta.get("source_title", "") or article_meta.get("title", ""),
        article_source=article_meta.get("source_type", ""),
        tier=article_meta.get("source_tier", "?"),
        score=article_meta.get("relevance_score"),
        entities=article_meta.get("key_entities", []),
        article_text=article_text,
        slug=product_slug,
        frontmatter=fm,
        sections=sections,
        max_article_chars=max_article_chars,
    )
    raw = client.chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.2,
    )
    return _parse_response(raw)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def _load_article(meta_path: Path) -> tuple[dict, str]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    basename = meta_path.name.replace(".meta.json", "")
    txt = meta_path.parent / f"{basename}.txt"
    text = txt.read_text(encoding="utf-8", errors="replace") if txt.exists() else ""
    return meta, text


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 4 Phase 2 LLM proposer (dry-run)")
    ap.add_argument("meta_path", type=Path, help=".meta.json path of source article")
    ap.add_argument("target_slug", help="product slug (e.g. iphone-17-pro)")
    ap.add_argument("--max-chars", type=int, default=3000)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    product_path = PRODUCTS_DIR / f"{args.target_slug}.md"
    if not product_path.exists():
        print(f"❌ product not found: {product_path}", file=sys.stderr)
        return 1
    if not args.meta_path.exists():
        print(f"❌ meta not found: {args.meta_path}", file=sys.stderr)
        return 1

    meta, text = _load_article(args.meta_path)
    page_md = product_path.read_text(encoding="utf-8")
    print(f"📄 article: {meta.get('source_type')}/{args.meta_path.stem} (score={meta.get('relevance_score')})")
    print(f"🎯 target:  wiki/products/{args.target_slug}.md")
    print(f"🤖 calling LLM...\n")

    try:
        result = propose(
            article_meta=meta,
            article_text=text,
            product_page_md=page_md,
            product_slug=args.target_slug,
            max_article_chars=args.max_chars,
        )
    except LLMError as e:
        print(f"❌ LLM error: {e}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    if not result.target_valid:
        print(f"\n⚠️  target_valid=false: {result.target_valid_reason}", file=sys.stderr)
        return 0

    print(f"\n📊 {len(result.proposals)} proposal(s)", file=sys.stderr)
    for i, p in enumerate(result.proposals, 1):
        errs = p.validate()
        marker = "✅" if not errs else "❌"
        print(f"   {marker} [{p.action:8s}] {p.section}  — {p.reason}", file=sys.stderr)
        if errs:
            for e in errs:
                print(f"        • {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
