#!/usr/bin/env python3
"""
scripts/review_queue.py — Gate 4 Phase 5 review queue CLI

Workflow: reviewer opens wiki/ingest-queue/YYYY-Www/*.md in an editor,
ticks `[x] apply` (or `[x] reject` / `[x] edit-then-apply`), saves,
then runs:

    python3 scripts/review_queue.py --apply-decided
    python3 scripts/review_queue.py --apply-decided --dry-run
    python3 scripts/review_queue.py --list
    python3 scripts/review_queue.py --stats

Items with `[x] apply` get their proposed content written to the target
wiki/products/ page. Decided files are moved to wiki/ingest-queue/_archive/.

Design: wiki/design/gate4-ingest.md §10 Phase 5 (originally optional)
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from .gate4_applier import (  # noqa: E402
    _append_to_section, _replace_section, _excerpt_matches, sandbox_safe_write,
    split_frontmatter, serialize_frontmatter, update_frontmatter, extract_sections,
)

REPO_ROOT = SCRIPTS.parent
QUEUE_DIR = REPO_ROOT / "wiki" / "ingest-queue"
ARCHIVE_DIR = QUEUE_DIR / "_archive"
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"


# ─────────────────────────────────────────────────────────────────────
# Queue file parsing
# ─────────────────────────────────────────────────────────────────────

@dataclass
class QueueProposal:
    section: str
    action: str              # original action (update/append/suggest)
    new_content: str
    decision: str            # apply | reject | edit-then-apply | undecided
    current_excerpt: str = ""  # LLM saw this when proposing; used for hallucination guard on update


@dataclass
class QueueItem:
    path: Path
    target_slug: str
    article_ref: str
    proposals: list[QueueProposal]

    @property
    def has_decided(self) -> bool:
        return any(p.decision != "undecided" for p in self.proposals)

    @property
    def has_applyable(self) -> bool:
        return any(p.decision == "apply" for p in self.proposals)


_TARGET_RE = re.compile(
    r"\*\*Target page\*\*:\s*`wiki/products/([^`]+)\.md`"
)
_ARTICLE_RE = re.compile(
    r"\*\*Article\*\*:\s*`([^`]+)`"
)
_PROPOSAL_HEADING_RE = re.compile(
    r"^## Proposal \d+:\s*`([^`]+)`\s*\(([^)]+?)\s*→\s*review\)\s*$",
    re.MULTILINE,
)
_DECISION_RE = re.compile(
    r"\*\*Decision\*\*:\s*\[([ x])\]\s*apply\s+\[([ x])\]\s*reject\s+\[([ x])\]\s*edit-then-apply"
)
_CONTENT_BLOCK_RE = re.compile(
    r"\*\*Proposed content\*\*:\s*\n\s*\n```(?:markdown)?\s*\n(.*?)\n```",
    re.DOTALL,
)
_EXCERPT_BLOCK_RE = re.compile(
    r"\*\*Current excerpt \(LLM saw\)\*\*:\s*\n\s*\n```\s*\n(.*?)\n```",
    re.DOTALL,
)


def parse_queue_file(path: Path) -> QueueItem:
    text = path.read_text(encoding="utf-8")
    target_m = _TARGET_RE.search(text)
    article_m = _ARTICLE_RE.search(text)
    target = target_m.group(1) if target_m else ""
    article_ref = article_m.group(1) if article_m else ""

    # Split into proposal blocks by "## Proposal N:" heading
    proposals: list[QueueProposal] = []
    headings = list(_PROPOSAL_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[start:end]
        section = m.group(1)
        action = m.group(2).strip()

        content_m = _CONTENT_BLOCK_RE.search(block)
        new_content = content_m.group(1) if content_m else ""

        excerpt_m = _EXCERPT_BLOCK_RE.search(block)
        current_excerpt = excerpt_m.group(1) if excerpt_m else ""

        decision = "undecided"
        dec_m = _DECISION_RE.search(block)
        if dec_m:
            apply_x, reject_x, edit_x = (s == "x" for s in dec_m.groups())
            if apply_x:
                decision = "apply"
            elif reject_x:
                decision = "reject"
            elif edit_x:
                decision = "edit-then-apply"

        proposals.append(QueueProposal(section, action, new_content, decision, current_excerpt))

    return QueueItem(path, target, article_ref, proposals)


# ─────────────────────────────────────────────────────────────────────
# Apply + archive
# ─────────────────────────────────────────────────────────────────────

def apply_queue_item(
    item: QueueItem,
    *,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    """Apply `[x] apply`-marked proposals to the target product page.

    Returns (applied_sections, errors).
    """
    applyable = [p for p in item.proposals if p.decision == "apply"]
    if not applyable:
        return [], []
    if not item.target_slug:
        return [], ["no target_slug in queue file (orphan?)"]
    product_path = PRODUCTS_DIR / f"{item.target_slug}.md"
    if not product_path.exists():
        return [], [f"target page not found: {product_path}"]

    page_md = product_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(page_md)
    new_body = body
    applied: list[str] = []
    for p in applyable:
        # For review-queue proposals, all actions are treated as the human
        # explicitly approving that content — write it.
        if p.action == "append" or p.action == "suggest":
            # suggest in queue means "human agreed to add it"
            new_body = _append_to_section(new_body, p.section, p.new_content)
        else:  # update
            # #17: Re-validate current_excerpt against the live page content.
            # Another apply may have modified this section since the queue file
            # was written; silently overwriting would cause data loss.
            current_sections = extract_sections(new_body)
            current_content = current_sections.get(p.section, "")
            if p.current_excerpt and not _excerpt_matches(p.current_excerpt, current_content):
                errors.append(
                    f"section '{p.section}': current_excerpt no longer matches page content "
                    f"(page may have been modified since queue was written); "
                    f"manual review required"
                )
                continue
            new_body = _replace_section(new_body, p.section, p.new_content)
        applied.append(p.section)

    if applied and not dry_run:
        new_fm = update_frontmatter(
            fm,
            article_meta_path=Path(item.article_ref + ".meta.json"),
            applied_sections=applied,
        )
        content = f"---\n{serialize_frontmatter(new_fm)}\n---\n\n{new_body.lstrip()}"
        if not content.endswith("\n"):
            content += "\n"
        sandbox_safe_write(product_path, content)
    return applied, []


def archive_queue_file(path: Path, *, dry_run: bool = False) -> Path:
    """Move a decided queue file to _archive/ preserving its week dir."""
    # wiki/ingest-queue/YYYY-Www/file.md → wiki/ingest-queue/_archive/YYYY-Www/file.md
    rel = path.relative_to(QUEUE_DIR)
    archive_path = ARCHIVE_DIR / rel
    if dry_run:
        return archive_path
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    content = path.read_text(encoding="utf-8")
    sandbox_safe_write(archive_path, content)
    # remove original
    import subprocess
    try:
        path.unlink()
    except PermissionError:
        subprocess.run(["git", "rm", "-f", "--quiet", str(path)],
                       cwd=REPO_ROOT, capture_output=True)
    return archive_path


# ─────────────────────────────────────────────────────────────────────
# Queue walking
# ─────────────────────────────────────────────────────────────────────

def walk_queue(queue_dir: Path = QUEUE_DIR) -> list[QueueItem]:
    """Return all open queue items (excluding _archive)."""
    items: list[QueueItem] = []
    if not queue_dir.exists():
        return items
    for p in sorted(queue_dir.rglob("*.md")):
        # Skip README.md, archive, orphans (orphans have different structure)
        if p.name == "README.md":
            continue
        if "_archive" in p.parts:
            continue
        if "_orphans" in p.parts:
            # orphans don't have proposals to apply; skip in this tool
            continue
        try:
            items.append(parse_queue_file(p))
        except Exception as e:
            logging.warning(f"failed to parse {p}: {e}")
    return items


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def cmd_list(items: list[QueueItem]) -> None:
    if not items:
        print("No open queue items.")
        return
    print(f"Found {len(items)} queue item(s):")
    for it in items:
        decisions = {"apply": 0, "reject": 0, "edit-then-apply": 0, "undecided": 0}
        for p in it.proposals:
            decisions[p.decision] += 1
        dec_str = ", ".join(f"{k}={v}" for k, v in decisions.items() if v)
        rel = it.path.relative_to(REPO_ROOT) if str(it.path).startswith(str(REPO_ROOT)) else it.path
        print(f"  • {rel}")
        print(f"    → {it.target_slug}  proposals={len(it.proposals)}  [{dec_str}]")


def cmd_stats(items: list[QueueItem]) -> None:
    total_proposals = sum(len(it.proposals) for it in items)
    by_decision = {"apply": 0, "reject": 0, "edit-then-apply": 0, "undecided": 0}
    for it in items:
        for p in it.proposals:
            by_decision[p.decision] += 1
    print(f"Queue items:          {len(items)}")
    print(f"Total proposals:      {total_proposals}")
    for k, v in by_decision.items():
        print(f"  {k:18s} {v:3d}")
    decided_files = sum(1 for it in items if it.has_decided)
    print(f"Files with decisions: {decided_files}")
    warning = ""
    if len(items) > 20:
        warning = "  ⚠️  > 20 open items — review backlog hygiene"
    elif len(items) > 0:
        warning = f"  ({len(items)}/20 queue threshold)"
    print(warning)


def cmd_apply_decided(items: list[QueueItem], *, dry_run: bool) -> int:
    applied_count = 0
    for it in items:
        if not it.has_applyable:
            continue
        applied, errors = apply_queue_item(it, dry_run=dry_run)
        if applied:
            rel = it.path.relative_to(REPO_ROOT) if str(it.path).startswith(str(REPO_ROOT)) else it.path
            mark = "○" if dry_run else "✅"
            print(f"  {mark} {rel} → {it.target_slug}: {applied}")
            applied_count += 1
            if not dry_run:
                archive_queue_file(it.path, dry_run=False)
        for e in errors:
            print(f"  ✗ {it.path.name}: {e}")
    # Also archive files where all proposals are rejected (no apply needed but decided)
    if not dry_run:
        for it in items:
            if it.has_applyable:
                continue  # already archived above
            if it.has_decided and all(p.decision in ("reject", "edit-then-apply") for p in it.proposals):
                archive_queue_file(it.path, dry_run=False)
                print(f"  📦 archived (all rejected): {it.path.name}")
    if dry_run and applied_count:
        print(f"\n[DRY-RUN] {applied_count} file(s) would be applied + archived")
    return applied_count


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 4 review queue CLI")
    ap.add_argument("--list", action="store_true", help="list open queue items")
    ap.add_argument("--stats", action="store_true", help="summary stats")
    ap.add_argument("--apply-decided", action="store_true",
                    help="apply all proposals marked [x] apply, archive decided files")
    ap.add_argument("--dry-run", action="store_true", help="don't write anything")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    items = walk_queue()

    if args.stats:
        cmd_stats(items)
        return 0
    if args.list:
        cmd_list(items)
        return 0
    if args.apply_decided:
        cmd_apply_decided(items, dry_run=args.dry_run)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
