#!/usr/bin/env python3
"""
scripts/gate4_queue.py — Gate 4 Phase 4 review queue writer

Writes human-review items to wiki/ingest-queue/YYYY-Www/<product>--<article>.md
for proposals that can't be auto-applied (human_owned sections, new sections,
or orphan articles without a clear target).

One file per (article, target) pair. Contains all review proposals from that
pair, with decision checkboxes for the reviewer.

Design: wiki/design/gate4-ingest.md §3.3
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
QUEUE_DIR = REPO_ROOT / "wiki" / "ingest-queue"

from .utils import sandbox_safe_write    # noqa: E402


def iso_week(when: Optional[dt.datetime] = None) -> str:
    when = when or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    y, w, _ = when.isocalendar()
    return f"{y}-W{w:02d}"


def queue_file_path(
    *,
    target_slug: str,
    article_basename: str,
    week: Optional[str] = None,
    queue_dir: Path = QUEUE_DIR,
) -> Path:
    """Path for a (target × article) review file."""
    w = week or iso_week()
    return queue_dir / w / f"{target_slug}--{article_basename}.md"


def orphan_file_path(
    *,
    article_basename: str,
    week: Optional[str] = None,
    queue_dir: Path = QUEUE_DIR,
) -> Path:
    """Path for articles with no routing target."""
    w = week or iso_week()
    return queue_dir / w / "_orphans" / f"{article_basename}.md"


def format_queue_file(
    *,
    target_slug: str,
    article_meta: dict,
    article_ref: str,
    reviewed_proposals: list[tuple],  # [(Proposal, reason), ...]
    rejected_proposals: list[tuple] | None = None,
    now: Optional[dt.datetime] = None,
) -> str:
    """Render markdown body for queue file."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    created = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    score = article_meta.get("relevance_score")
    status = article_meta.get("ingest_status", "unknown")
    tier = article_meta.get("source_tier", "?")
    title = article_meta.get("source_title", "") or article_meta.get("title", "")

    lines = [
        f"# Ingest review: {target_slug} ← {article_ref}",
        "",
        f"- **Article**: `{article_ref}`",
        f"- **Title**: {title}",
        f"- **Source tier / status / score**: {tier} / {status} / {score if score is not None else '—'}",
        f"- **Target page**: `wiki/products/{target_slug}.md`",
        f"- **Created**: {created}",
        f"- **Reviewed proposals**: {len(reviewed_proposals)}",
        "",
        "---",
        "",
    ]

    for i, (proposal, reason) in enumerate(reviewed_proposals, 1):
        lines += [
            f"## Proposal {i}: `{proposal.section}` ({proposal.action} → review)",
            "",
            f"**Why review**: {reason}",
            "",
            f"**LLM reason**: {proposal.reason}",
            "",
        ]
        if proposal.current_excerpt:
            lines += [
                "**Current excerpt (LLM saw)**:",
                "",
                "```",
                proposal.current_excerpt[:400],
                "```",
                "",
            ]
        lines += [
            "**Proposed content**:",
            "",
            "```markdown",
            proposal.new_content.rstrip(),
            "```",
            "",
            "**Decision**: [ ] apply  [ ] reject  [ ] edit-then-apply",
            "",
            "**Decided by**: @___",
            "",
            "**Decided at**: ___",
            "",
            "---",
            "",
        ]

    if rejected_proposals:
        lines += ["## Rejected proposals (for the record)", ""]
        for proposal, reason in rejected_proposals:
            lines += [f"- `{proposal.section}` ({proposal.action}): {reason}"]
        lines.append("")

    return "\n".join(lines)


def format_orphan_file(
    *,
    article_meta: dict,
    article_ref: str,
    now: Optional[dt.datetime] = None,
) -> str:
    """Orphan articles: no routing target, but still approved/pending-review."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    created = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    title = article_meta.get("source_title", "") or article_meta.get("title", "")
    entities = article_meta.get("key_entities", [])
    status = article_meta.get("ingest_status", "unknown")
    score = article_meta.get("relevance_score")

    return "\n".join([
        f"# Orphan article (no routing target): {article_ref}",
        "",
        f"- **Title**: {title}",
        f"- **Status**: {status}",
        f"- **Relevance score**: {score if score is not None else '—'}",
        f"- **Key entities**: {entities}",
        f"- **Created**: {created}",
        "",
        "## Options for reviewer",
        "",
        "1. **Create a new product page** if this article introduces a product not yet in `wiki/products/`.",
        "2. **Tag an existing page** by adding missing entity tags to its frontmatter, then re-run Gate 4.",
        "3. **Reject**: this article is genuinely off-topic despite passing Gate 3 → set `ingest_status: skipped-low-relevance` manually and delete this queue file.",
        "",
        "**Decision**: [ ] create-page  [ ] tag-existing  [ ] reject",
        "",
        "**Decided by**: @___",
        "",
    ])


# ─────────────────────────────────────────────────────────────────────
# Sandbox-safe write
# ─────────────────────────────────────────────────────────────────────
# sandbox_safe_write is imported from utils.py (shared with gate4_applier.py)


def write_review(
    *,
    target_slug: str,
    article_meta: dict,
    article_ref: str,
    reviewed_proposals: list[tuple],
    rejected_proposals: list[tuple] | None = None,
    week: Optional[str] = None,
    queue_dir: Path = QUEUE_DIR,
    dry_run: bool = False,
    article_basename: Optional[str] = None,
) -> Path:
    basename = article_basename or article_ref.split("/")[-1]
    path = queue_file_path(
        target_slug=target_slug, article_basename=basename,
        week=week, queue_dir=queue_dir,
    )
    content = format_queue_file(
        target_slug=target_slug,
        article_meta=article_meta,
        article_ref=article_ref,
        reviewed_proposals=reviewed_proposals,
        rejected_proposals=rejected_proposals or [],
    )
    if not dry_run:
        sandbox_safe_write(path, content)
    return path


def write_orphan(
    *,
    article_meta: dict,
    article_ref: str,
    article_basename: str,
    week: Optional[str] = None,
    queue_dir: Path = QUEUE_DIR,
    dry_run: bool = False,
) -> Path:
    path = orphan_file_path(
        article_basename=article_basename, week=week, queue_dir=queue_dir,
    )
    content = format_orphan_file(article_meta=article_meta, article_ref=article_ref)
    if not dry_run:
        sandbox_safe_write(path, content)
    return path
