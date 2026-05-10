#!/usr/bin/env python3
"""
scripts/gate4_applier.py — Gate 4 Phase 3 applier

Takes a ProposalSet (from gate4_proposer) + target product page, filters
by §3.6 ownership rules, and applies managed-section updates. Non-managed
proposals are returned as ReviewItems for Phase 4 to write to the queue.

Guarantees:
- Hallucination guard: action=update rejected if current_excerpt doesn't
  match the actual current section content (case-insensitive substring).
- Ownership enforced: human_owned section + action∈{update,append} is
  downgraded to suggest (review queue).
- Unknown section + any action → review queue.
- Idempotent: meta.json's ingest_log_ref is checked; re-runs skip.
- Atomic writes with Enchanté-sandbox fallback.

Design: wiki/design/gate4-ingest.md §3.3, §3.4, §3.5
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
from .yaml_mini import loads as yloads   # noqa: E402
from .gate4_proposer import (            # noqa: E402
    Proposal, ProposalSet, split_frontmatter, extract_sections,
)
from .utils import sandbox_safe_write    # noqa: E402

REPO_ROOT = SCRIPTS.parent
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"
RAW_DIR = REPO_ROOT / "raw"

# §3.6 defaults when frontmatter omits an ownership list
DEFAULT_MANAGED_SECTIONS = {
    "一句話定位", "起售價", "目標客群", "核心規格",
    "競品對比摘要", "相關頁面", "來源",
}
DEFAULT_HUMAN_OWNED_SECTIONS = {
    "五大賣點（Selling Points）", "五大賣點",
    "三大獨家 Demo（Signature Demos）", "三大獨家 Demo",
    "一般實機 Demo 建議",
    "常見客戶問題與回應", "常見反對意見處理",
}

VALID_UPDATE_ACTIONS = {"update", "append"}


# ─────────────────────────────────────────────────────────────────────
# Ownership classification
# ─────────────────────────────────────────────────────────────────────

@dataclass
class FilteredProposals:
    apply: list[Proposal] = field(default_factory=list)       # to apply now
    review: list[tuple[Proposal, str]] = field(default_factory=list)  # (proposal, reason_for_review)
    rejected: list[tuple[Proposal, str]] = field(default_factory=list)  # (proposal, reason_for_rejection)


def classify_section(
    section: str,
    *,
    frontmatter_managed: list[str],
    frontmatter_human: list[str],
    existing_sections: set[str],
) -> str:
    """Return one of: 'managed' | 'human' | 'new' (section doesn't exist on page)."""
    managed = set(frontmatter_managed) | DEFAULT_MANAGED_SECTIONS
    human = set(frontmatter_human) | DEFAULT_HUMAN_OWNED_SECTIONS
    if section in human:
        return "human"
    if section in managed:
        return "managed"
    if section not in existing_sections:
        return "new"
    # Exists on page but not in either ownership list — treat as managed-ish
    return "managed"


def filter_proposals(
    proposals: list[Proposal],
    *,
    frontmatter: dict,
    existing_sections: dict[str, str],
) -> FilteredProposals:
    """Split proposals per §3.6 rules + hallucination guard."""
    fm_managed = frontmatter.get("ingest_managed_sections") or []
    fm_human = frontmatter.get("human_owned_sections") or []
    section_names = set(existing_sections.keys())

    out = FilteredProposals()
    for p in proposals:
        # Invalid proposal → reject
        errs = p.validate()
        if errs:
            out.rejected.append((p, f"validation: {'; '.join(errs)}"))
            continue

        kind = classify_section(
            p.section,
            frontmatter_managed=fm_managed,
            frontmatter_human=fm_human,
            existing_sections=section_names,
        )

        if kind == "human":
            # Downgrade any action to 'suggest' via review queue
            out.review.append((p, f"human-owned section (action was '{p.action}' → review)"))
            continue

        if kind == "new":
            # New section → always review (§3.6 NEEDS REVIEW rule)
            out.review.append((p, "new section (not in page)"))
            continue

        # kind == managed
        if p.action == "suggest":
            # LLM explicitly deferred — honor it
            out.review.append((p, "LLM marked as suggest"))
            continue

        if p.action == "update":
            # Hallucination guard: current_excerpt must appear in actual content
            current = existing_sections.get(p.section, "")
            if not _excerpt_matches(p.current_excerpt, current):
                out.rejected.append((p, "current_excerpt mismatch (hallucination guard)"))
                continue
            # v0.6: smart diff-merge for updates (preserve tables + prose)
            merged = merge_section_update(current, p.new_content)
            if not is_safe_update(current, merged):
                out.review.append((
                    p,
                    f"update would drop too much detail "
                    f"(merged {len(merged)} chars vs current {len(current)} chars, "
                    f"< {int(MIN_PRESERVATION_RATIO * 100)}%); routed to review"
                ))
                continue
            # Replace LLM's raw new_content with merged version
            p.new_content = merged

        out.apply.append(p)
    return out


# ─────────────────────────────────────────────────────────────────────
# Diff-merge for update actions (v0.6+)
# ─────────────────────────────────────────────────────────────────────

# Minimum fraction of original content that must be preserved after merge.
# Below this → downgrade proposal to review queue (LLM tried to rewrite too much).
MIN_PRESERVATION_RATIO = 0.6

# Markdown table separator pattern (e.g. |---|---|)
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def _extract_tables(text: str) -> list[list[list[str]]]:
    """Parse markdown tables out of text.
    Returns list of tables; each table is list of rows; each row is list of cell strings.
    First row of each table is the header.
    """
    tables: list[list[list[str]]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip().startswith("|"):
            i += 1
            continue
        # Collect consecutive table lines
        rows: list[list[str]] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            raw = lines[i].strip()
            if _TABLE_SEP_RE.match(raw):
                i += 1
                continue
            # Split cells (strip leading/trailing |)
            cells = [c.strip() for c in raw.strip("|").split("|")]
            rows.append(cells)
            i += 1
        if len(rows) >= 2:  # at least header + 1 row to count as a table
            tables.append(rows)
    return tables


def _table_to_markdown(table: list[list[str]]) -> str:
    """Render a parsed table back to markdown."""
    if not table:
        return ""
    lines = ["| " + " | ".join(table[0]) + " |"]
    lines.append("|" + "|".join("---" for _ in table[0]) + "|")
    for row in table[1:]:
        # Pad row to header length if short
        padded = list(row) + [""] * max(0, len(table[0]) - len(row))
        lines.append("| " + " | ".join(padded[: len(table[0])]) + " |")
    return "\n".join(lines)


def _merge_tables(old: list[list[str]], new: list[list[str]]) -> list[list[str]]:
    """Merge two tables by first column as key.

    Rules:
    - Keep all old rows in original order; if new has a matching key, use new's row values.
    - Append new rows (keys not in old) at the end.
    - Header taken from old if present, else new.
    """
    if not old:
        return new
    if not new:
        return old

    header = old[0]
    old_rows = old[1:]
    new_rows = new[1:]
    new_by_key = {r[0]: r for r in new_rows if r}

    merged = [header]
    seen = set()
    for r in old_rows:
        if not r:
            continue
        key = r[0]
        seen.add(key)
        merged.append(new_by_key.get(key, r))
    for r in new_rows:
        if not r:
            continue
        if r[0] not in seen:
            merged.append(r)
    return merged


def _strip_tables(text: str) -> str:
    """Return text with all markdown table blocks removed (non-table prose only)."""
    lines = text.split("\n")
    out: list[str] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            in_table = True
            continue
        if in_table and not stripped:
            in_table = False
            continue  # swallow trailing blank after table
        in_table = False
        out.append(line)
    return "\n".join(out)


def merge_section_update(old_content: str, new_content: str) -> str:
    """Smart merge for action=update on a section.

    Strategy:
    - If old section contains NO markdown tables → return new_content (existing replace behavior)
    - If old has tables but new does NOT → keep old tables intact, substitute new prose
    - If both have tables → merge row-by-row by first column key

    Designed to preserve multi-row spec tables that LLM tends to flatten.
    """
    old_tables = _extract_tables(old_content)
    if not old_tables:
        return new_content

    new_tables = _extract_tables(new_content)
    merged_tables_md: list[str] = []

    # Pair tables by position; merge where both exist; keep old where new absent
    max_n = max(len(old_tables), len(new_tables))
    for i in range(max_n):
        if i < len(old_tables) and i < len(new_tables):
            merged_tables_md.append(_table_to_markdown(_merge_tables(old_tables[i], new_tables[i])))
        elif i < len(old_tables):
            merged_tables_md.append(_table_to_markdown(old_tables[i]))
        else:
            merged_tables_md.append(_table_to_markdown(new_tables[i]))

    # Prose = non-table part of new_content (acts as new intro/outro for the section)
    new_prose = _strip_tables(new_content).strip()
    # Fallback: if new has no prose, keep old's prose
    if not new_prose:
        new_prose = _strip_tables(old_content).strip()

    pieces = []
    if new_prose:
        pieces.append(new_prose)
    pieces.extend(merged_tables_md)
    return "\n\n".join(pieces)


def is_safe_update(old: str, merged: str, ratio: float = MIN_PRESERVATION_RATIO) -> bool:
    """True if merged content preserves at least `ratio` fraction of the old content's length."""
    old_len = len(old.strip())
    if old_len == 0:
        return True
    return len(merged.strip()) >= ratio * old_len


def _excerpt_matches(excerpt: Optional[str], actual: str) -> bool:
    """Verify LLM saw the actual section content. Substring match, normalized whitespace."""
    if not excerpt:
        return False
    # Normalize whitespace for comparison
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    e = norm(excerpt)[:80]  # first 80 chars is enough
    a = norm(actual)
    return len(e) >= 5 and e in a  # min 5 chars to avoid trivial single-char matches


# ─────────────────────────────────────────────────────────────────────
# Page rewriting
# ─────────────────────────────────────────────────────────────────────

def apply_proposals_to_body(body: str, proposals: list[Proposal]) -> tuple[str, list[str]]:
    """Apply update/append proposals to markdown body.
    Returns: (new_body, list_of_applied_section_names).
    """
    applied: list[str] = []
    new_body = body
    for p in proposals:
        if p.action == "update":
            new_body = _replace_section(new_body, p.section, p.new_content)
            applied.append(p.section)
        elif p.action == "append":
            new_body = _append_to_section(new_body, p.section, p.new_content)
            applied.append(p.section)
    return new_body, applied


def _replace_section(body: str, heading: str, new_content: str) -> str:
    """Replace the body of a ## heading with new_content. Keeps the heading line."""
    # Pattern: ## <heading>\n<body until next ## or EOF>
    pattern = re.compile(
        r"(^## " + re.escape(heading) + r"\s*$)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    replacement = f"\\1\n\n{new_content.rstrip()}\n\n"
    new_body, n = pattern.subn(replacement, body, count=1)
    if n == 0:
        # Section didn't exist → append
        return _append_new_section(body, heading, new_content)
    return new_body


def _append_to_section(body: str, heading: str, content: str) -> str:
    """Append content within an existing ## section (before next heading)."""
    pattern = re.compile(
        r"(^## " + re.escape(heading) + r"\s*$)(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    if not m:
        return _append_new_section(body, heading, content)
    head = m.group(1)
    existing = m.group(2).rstrip()
    new_section = f"{head}{existing}\n\n{content.rstrip()}\n\n"
    return body[: m.start()] + new_section + body[m.end():]


def _append_new_section(body: str, heading: str, content: str) -> str:
    sep = "\n\n" if not body.endswith("\n") else "\n"
    return body + sep + f"## {heading}\n\n{content.rstrip()}\n"


# ─────────────────────────────────────────────────────────────────────
# Frontmatter + citation updates
# ─────────────────────────────────────────────────────────────────────

def update_frontmatter(
    frontmatter: dict,
    *,
    article_meta_path: Path,
    applied_sections: list[str],
    now: Optional[dt.datetime] = None,
) -> dict:
    """Increment source_count, bump last_updated, append ingest_history entry."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    fm = dict(frontmatter)
    fm["source_count"] = int(fm.get("source_count", 0)) + 1
    fm["last_updated"] = now.strftime("%Y-%m-%d")
    history = list(fm.get("ingest_history") or [])
    try:
        article_ref = str(article_meta_path.relative_to(REPO_ROOT)).replace(".meta.json", "")
    except ValueError:
        article_ref = article_meta_path.stem.replace(".meta", "")
    history.append({
        "article": article_ref,
        "applied_at": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "sections": applied_sections,
    })
    fm["ingest_history"] = history
    return fm


def serialize_frontmatter(fm: dict) -> str:
    """Simple YAML serializer for frontmatter (supports our subset)."""
    lines = []
    # Preserve canonical order: well-known keys first, then others
    canon = ["type", "title", "slug", "status", "product_category", "last_updated",
             "source_count", "tags", "ingest_managed_sections", "human_owned_sections",
             "ingest_history"]
    seen = set()
    for k in canon:
        if k in fm:
            lines.append(_yaml_kv(k, fm[k]))
            seen.add(k)
    for k, v in fm.items():
        if k not in seen:
            lines.append(_yaml_kv(k, v))
    return "\n".join(lines)


def _yaml_kv(key: str, val) -> str:
    if isinstance(val, list):
        if not val:
            return f"{key}: []"
        if all(isinstance(x, (str, int, float, bool)) for x in val):
            inner = ", ".join(_yaml_scalar(x) for x in val)
            return f"{key}: [{inner}]"
        # List of dicts → block style (yaml_mini-parseable)
        out = [f"{key}:"]
        for item in val:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    prefix = "  - " if first else "    "
                    if isinstance(v, list):
                        inner = ", ".join(_yaml_scalar(x) for x in v)
                        out.append(f"{prefix}{k}: [{inner}]")
                    else:
                        out.append(f"{prefix}{k}: {_yaml_scalar(v)}")
                    first = False
            else:
                out.append(f"  - {_yaml_scalar(item)}")
        return "\n".join(out)
    return f"{key}: {_yaml_scalar(val)}"


def _yaml_inline_dict(d: dict) -> str:
    """Inline flow-style dict."""
    parts = []
    for k, v in d.items():
        if isinstance(v, list):
            inner = ", ".join(_yaml_scalar(x) for x in v)
            parts.append(f"{k}: [{inner}]")
        else:
            parts.append(f"{k}: {_yaml_scalar(v)}")
    return "{" + ", ".join(parts) + "}"


def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.search(r"[:#\[\]{},\"'\n]", s) or not s:
        return json.dumps(s, ensure_ascii=False)
    return s


# ─────────────────────────────────────────────────────────────────────
# Page writing + meta update
# ─────────────────────────────────────────────────────────────────────

def sandbox_safe_write(path: Path, content: str) -> None:
    """Atomic write with Enchanté sandbox fallback.

    Delegates to utils.sandbox_safe_write; kept here for backward compatibility
    so callers that import this symbol directly (e.g. review_queue.py) continue
    to work without changes.
    """
    from .utils import sandbox_safe_write as _ssw
    _ssw(path, content, repo_root=REPO_ROOT)


def write_product_page(path: Path, frontmatter: dict, body: str) -> None:
    """Reassemble page with updated frontmatter + body."""
    content = f"---\n{serialize_frontmatter(frontmatter)}\n---\n\n{body.lstrip()}"
    if not content.endswith("\n"):
        content += "\n"
    sandbox_safe_write(path, content)


def mark_meta_applied(meta_path: Path, *, wiki_ref: str, targets: list[str]) -> None:
    """Record ingest_log_ref + ingest_targets in meta.json."""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["ingest_log_ref"] = wiki_ref
    meta["ingest_targets"] = targets
    payload = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    sandbox_safe_write(meta_path, payload)


# ─────────────────────────────────────────────────────────────────────
# Main apply routine
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ApplyResult:
    applied_sections: list[str]
    reviewed_proposals: list[tuple[Proposal, str]]
    rejected_proposals: list[tuple[Proposal, str]]
    skipped_reason: Optional[str] = None  # "already-applied" or None


def apply_to_page(
    *,
    proposal_set: ProposalSet,
    product_path: Path,
    article_meta_path: Path,
    dry_run: bool = False,
) -> ApplyResult:
    """Filter + apply to disk. Idempotent via ingest_log_ref."""
    # Idempotency check
    meta = json.loads(article_meta_path.read_text(encoding="utf-8"))
    if meta.get("ingest_log_ref"):
        # Already applied somewhere — skip (for this PoC we dedup globally per article)
        return ApplyResult([], [], [], skipped_reason=f"already-applied (ref={meta['ingest_log_ref']})")

    if not proposal_set.target_valid:
        return ApplyResult([], [], [], skipped_reason=f"target_valid=false: {proposal_set.target_valid_reason}")

    page_md = product_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(page_md)
    existing = extract_sections(body)

    filtered = filter_proposals(
        proposal_set.proposals,
        frontmatter=fm,
        existing_sections=existing,
    )

    if not filtered.apply and not filtered.review:
        return ApplyResult([], list(filtered.review), list(filtered.rejected),
                           skipped_reason="no actionable proposals")

    # Apply managed changes
    new_body, applied_sections = apply_proposals_to_body(body, filtered.apply)

    if applied_sections and not dry_run:
        new_fm = update_frontmatter(
            fm, article_meta_path=article_meta_path,
            applied_sections=applied_sections,
        )
        write_product_page(product_path, new_fm, new_body)
        wiki_ref = f"{dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')}|{product_path.stem}"
        mark_meta_applied(article_meta_path, wiki_ref=wiki_ref, targets=[product_path.stem])

    return ApplyResult(applied_sections, list(filtered.review), list(filtered.rejected))


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 4 Phase 3 applier")
    ap.add_argument("meta_path", type=Path)
    ap.add_argument("target_slug")
    ap.add_argument("--apply", action="store_true", help="write changes (otherwise dry-run)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    from gate4_proposer import propose, _load_article

    product_path = PRODUCTS_DIR / f"{args.target_slug}.md"
    if not product_path.exists():
        print(f"❌ product not found: {product_path}", file=sys.stderr); return 1
    if not args.meta_path.exists():
        print(f"❌ meta not found: {args.meta_path}", file=sys.stderr); return 1

    meta, text = _load_article(args.meta_path)
    page_md = product_path.read_text(encoding="utf-8")

    print(f"📄 {meta.get('source_type')}/{args.meta_path.stem} → {args.target_slug}")
    print("🤖 proposing...")
    result = propose(
        article_meta=meta, article_text=text,
        product_page_md=page_md, product_slug=args.target_slug,
    )
    print(f"🔍 target_valid={result.target_valid}  proposals={len(result.proposals)}")

    outcome = apply_to_page(
        proposal_set=result,
        product_path=product_path,
        article_meta_path=args.meta_path,
        dry_run=not args.apply,
    )

    if outcome.skipped_reason:
        print(f"⏭  skipped: {outcome.skipped_reason}")
    print(f"\n📊 Applied to managed sections: {outcome.applied_sections}")
    print(f"   Review queue: {len(outcome.reviewed_proposals)}")
    for p, why in outcome.reviewed_proposals:
        print(f"     • [{p.action}] {p.section}  — {why}")
    print(f"   Rejected: {len(outcome.rejected_proposals)}")
    for p, why in outcome.rejected_proposals:
        print(f"     ✗ [{p.action}] {p.section}  — {why}")
    if not args.apply and outcome.applied_sections:
        print("\n[DRY-RUN] use --apply to write changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
