#!/usr/bin/env python3
"""
scripts/gate4_lint.py — Gate 4 hygiene checks

Validates Gate 4 state across repo. Non-zero exit on WARN+, informational
output on INFO-only runs.

Checks:
  L1 queue-backlog       open queue items > 20 → WARN
  L2 queue-parseable     every queue file has Decision + Proposal blocks
  L3 log-ref-integrity   ingest_log_ref ↔ ingest_targets consistency;
                         targets must exist in wiki/products/
  L4 orphan-age          items in _orphans/ older than 2 weeks → WARN
  L5 duplicate-queue     no two queue files with same article for
                         same target (would double-apply)

Usage:
  python3 scripts/gate4_lint.py              # info
  python3 scripts/gate4_lint.py --strict     # warn → error exit
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from review_queue import walk_queue  # noqa: E402

REPO_ROOT = SCRIPTS.parent
RAW_DIR = REPO_ROOT / "raw"
QUEUE_DIR = REPO_ROOT / "wiki" / "ingest-queue"
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"

QUEUE_BACKLOG_THRESHOLD = 20
ORPHAN_MAX_AGE_DAYS = 14


@dataclass
class LintIssue:
    level: str       # INFO | WARN | ERROR
    rule: str        # L1 .. L5
    message: str


def check_queue_backlog(queue_items: list) -> list[LintIssue]:
    n = len(queue_items)
    if n > QUEUE_BACKLOG_THRESHOLD:
        return [LintIssue("WARN", "L1",
                          f"{n} open queue items (> {QUEUE_BACKLOG_THRESHOLD} threshold) — clear backlog")]
    if n > 0:
        return [LintIssue("INFO", "L1",
                          f"{n}/{QUEUE_BACKLOG_THRESHOLD} open queue items")]
    return [LintIssue("INFO", "L1", "queue empty")]


def check_queue_parseable(queue_items: list) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for it in queue_items:
        if not it.target_slug:
            issues.append(LintIssue("WARN", "L2",
                                    f"{it.path.name}: missing target_slug"))
        if not it.proposals:
            issues.append(LintIssue("WARN", "L2",
                                    f"{it.path.name}: no parseable proposals"))
    if not issues:
        issues.append(LintIssue("INFO", "L2",
                                f"all {len(queue_items)} queue file(s) parseable"))
    return issues


def check_log_ref_integrity(raw_dir: Path = RAW_DIR,
                            products_dir: Path = PRODUCTS_DIR) -> list[LintIssue]:
    issues: list[LintIssue] = []
    valid_slugs = {p.stem for p in products_dir.glob("*.md")}
    n_checked = 0
    for meta_path in raw_dir.glob("*/*/*.meta.json"):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ref = m.get("ingest_log_ref")
        targets = m.get("ingest_targets") or []
        if ref and not targets:
            issues.append(LintIssue("WARN", "L3",
                                    f"{meta_path.name}: ingest_log_ref set but ingest_targets empty"))
        if not ref and targets:
            issues.append(LintIssue("WARN", "L3",
                                    f"{meta_path.name}: ingest_targets set but no ingest_log_ref"))
        for t in targets:
            if t not in valid_slugs:
                issues.append(LintIssue("ERROR", "L3",
                                        f"{meta_path.name}: target '{t}' not in wiki/products/"))
        n_checked += 1
    if not issues:
        issues.append(LintIssue("INFO", "L3",
                                f"{n_checked} meta.json checked, all log_ref ↔ targets consistent"))
    return issues


def check_orphan_age(queue_dir: Path = QUEUE_DIR) -> list[LintIssue]:
    issues: list[LintIssue] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=ORPHAN_MAX_AGE_DAYS)
    n_orphans = 0
    for p in queue_dir.rglob("*.md"):
        if "_orphans" not in p.parts:
            continue
        if "_archive" in p.parts:
            continue
        n_orphans += 1
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=dt.timezone.utc)
        age_days = (dt.datetime.now(dt.timezone.utc) - mtime).days
        if mtime < cutoff:
            issues.append(LintIssue("WARN", "L4",
                                    f"{p.name}: orphan {age_days}d old (> {ORPHAN_MAX_AGE_DAYS}d)"))
    if not issues:
        issues.append(LintIssue("INFO", "L4",
                                f"{n_orphans} orphan(s), none over {ORPHAN_MAX_AGE_DAYS}d"))
    return issues


def check_duplicate_queue(queue_items: list) -> list[LintIssue]:
    seen: dict[tuple[str, str], list[Path]] = {}
    for it in queue_items:
        key = (it.target_slug, it.article_ref)
        seen.setdefault(key, []).append(it.path)
    issues = []
    for (slug, art), paths in seen.items():
        if len(paths) > 1:
            names = [p.name for p in paths]
            issues.append(LintIssue("ERROR", "L5",
                                    f"duplicate queue for {slug} × {art}: {names}"))
    if not issues:
        issues.append(LintIssue("INFO", "L5",
                                f"no duplicate (target × article) queue files"))
    return issues


def check_review_file_format(queue_dir: Path = QUEUE_DIR) -> list[LintIssue]:
    """L6 — each review file must follow the template so the reviewer
    workflow (`scripts/review_queue.py --apply-decided`) can parse decisions.

    Required structural elements per file:
      - `# Ingest review: <target> ← <article>` H1 header
      - Metadata bullets: Article, Title, Target page
      - At least one `## Proposal N: ...` section
      - Each proposal has a `**Decision**: [ ] apply  [ ] reject  [ ] edit-then-apply` line
      - Each proposal has `**Decided by**:` and `**Decided at**:` lines (may be unfilled)

    Scans open queue files only (archive excluded — those are immutable history).
    """
    import re
    issues: list[LintIssue] = []
    n_checked = 0
    # Open queue files = top-level + YYYY-Www dirs; exclude _archive and README.md
    for p in queue_dir.rglob("*.md"):
        if "_archive" in p.parts or p.name == "README.md":
            continue
        n_checked += 1
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            issues.append(LintIssue("ERROR", "L6", f"{p.name}: unreadable"))
            continue

        # H1 header
        if not re.search(r"^#\s+Ingest review:\s+\S+\s*←\s*\S+", text, re.MULTILINE):
            issues.append(LintIssue("WARN", "L6",
                                    f"{p.name}: missing `# Ingest review: <target> ← <article>` header"))

        # Metadata bullets
        for label in ("Article", "Title", "Target page"):
            if not re.search(rf"^-\s+\*\*{label}\*\*", text, re.MULTILINE):
                issues.append(LintIssue("WARN", "L6",
                                        f"{p.name}: missing metadata bullet `**{label}**`"))

        # At least one proposal
        proposals = re.findall(r"^##\s+Proposal\s+\d+", text, re.MULTILINE)
        if not proposals:
            issues.append(LintIssue("WARN", "L6",
                                    f"{p.name}: no `## Proposal N` sections found"))
            continue

        # Each proposal: Decision checkboxes + Decided by/at
        n_decision = len(re.findall(
            r"\*\*Decision\*\*:\s*\[\s?\]\s*apply\s+\[\s?\]\s*reject\s+\[\s?\]\s*edit-then-apply",
            text))
        n_decided_by = len(re.findall(r"\*\*Decided by\*\*:", text))
        n_decided_at = len(re.findall(r"\*\*Decided at\*\*:", text))
        expected = len(proposals)
        if n_decision < expected:
            issues.append(LintIssue("WARN", "L6",
                                    f"{p.name}: {n_decision}/{expected} proposals have `Decision` checkbox line"))
        if n_decided_by < expected:
            issues.append(LintIssue("WARN", "L6",
                                    f"{p.name}: {n_decided_by}/{expected} proposals have `Decided by` line"))
        if n_decided_at < expected:
            issues.append(LintIssue("WARN", "L6",
                                    f"{p.name}: {n_decided_at}/{expected} proposals have `Decided at` line"))

    if n_checked == 0:
        issues.append(LintIssue("INFO", "L6", "no open review files to validate"))
    elif not issues:
        issues.append(LintIssue("INFO", "L6",
                                f"all {n_checked} review file(s) conform to template"))
    return issues


def run_all() -> list[LintIssue]:
    queue_items = walk_queue()
    issues: list[LintIssue] = []
    issues += check_queue_backlog(queue_items)
    issues += check_queue_parseable(queue_items)
    issues += check_log_ref_integrity()
    issues += check_orphan_age()
    issues += check_duplicate_queue(queue_items)
    issues += check_review_file_format()
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 4 hygiene lint")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on WARN (default: only ERROR)")
    ap.add_argument("--quiet", action="store_true", help="suppress INFO lines")
    args = ap.parse_args()

    issues = run_all()
    by_level = {"INFO": 0, "WARN": 0, "ERROR": 0}
    for i in issues:
        by_level[i.level] += 1
        if args.quiet and i.level == "INFO":
            continue
        icon = {"INFO": "·", "WARN": "⚠️ ", "ERROR": "❌"}[i.level]
        print(f"  {icon} [{i.rule}] {i.message}")

    print()
    print(f"Summary: INFO={by_level['INFO']} WARN={by_level['WARN']} ERROR={by_level['ERROR']}")

    if by_level["ERROR"]:
        return 2
    if args.strict and by_level["WARN"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
