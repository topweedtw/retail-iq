"""Tests for scripts/review_queue.py — Gate 4 Phase 5."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from gate4_proposer import Proposal  # noqa: E402
from gate4_queue import format_queue_file  # noqa: E402
from review_queue import (  # noqa: E402
    QueueItem, QueueProposal, apply_queue_item, archive_queue_file,
    cmd_apply_decided, parse_queue_file, walk_queue,
)


def _make_queue_md(proposals: list[tuple], *, decisions: list[str] | None = None) -> str:
    """Helper: build a queue markdown with optional ticked decisions.

    proposals: list of (Proposal, reason) tuples
    decisions: parallel list of 'apply'|'reject'|'edit-then-apply'|None
    """
    body = format_queue_file(
        target_slug="iphone-17-pro",
        article_meta={"source_title": "T", "source_tier": "T1",
                      "ingest_status": "approved", "relevance_score": 10},
        article_ref="raw/apple-com-tw/2026-W19/iphone-17_20260505",
        reviewed_proposals=proposals,
    )
    if decisions:
        # Replace i-th empty `[ ] apply` with tick based on decision
        lines = body.split("\n")
        dec_iter = iter(decisions)
        new = []
        for line in lines:
            if line.startswith("**Decision**:"):
                d = next(dec_iter, None)
                if d == "apply":
                    line = line.replace("[ ] apply", "[x] apply", 1)
                elif d == "reject":
                    line = line.replace("[ ] reject", "[x] reject", 1)
                elif d == "edit-then-apply":
                    line = line.replace("[ ] edit-then-apply", "[x] edit-then-apply", 1)
            new.append(line)
        body = "\n".join(new)
    return body


class TestParseQueueFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "q.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_parses_target_and_article(self):
        p = Proposal("S1", "update", "old excerpt", "new content", "reason")
        self.path.write_text(_make_queue_md([(p, "r")]))
        item = parse_queue_file(self.path)
        self.assertEqual(item.target_slug, "iphone-17-pro")
        self.assertIn("raw/apple-com-tw/2026-W19/iphone-17_20260505", item.article_ref)

    def test_parses_multiple_proposals(self):
        ps = [
            (Proposal("A", "update", "cur", "newA", "rA"), "r1"),
            (Proposal("B", "append", None, "newB", "rB"), "r2"),
        ]
        self.path.write_text(_make_queue_md(ps))
        item = parse_queue_file(self.path)
        self.assertEqual(len(item.proposals), 2)
        self.assertEqual(item.proposals[0].section, "A")
        self.assertEqual(item.proposals[1].section, "B")
        self.assertEqual(item.proposals[1].action, "append")

    def test_parses_decisions(self):
        ps = [
            (Proposal("A", "update", "c", "na", "r"), "r"),
            (Proposal("B", "append", None, "nb", "r"), "r"),
            (Proposal("C", "suggest", None, "nc", "r"), "r"),
        ]
        self.path.write_text(_make_queue_md(ps, decisions=["apply", "reject", "edit-then-apply"]))
        item = parse_queue_file(self.path)
        self.assertEqual(item.proposals[0].decision, "apply")
        self.assertEqual(item.proposals[1].decision, "reject")
        self.assertEqual(item.proposals[2].decision, "edit-then-apply")

    def test_undecided_by_default(self):
        ps = [(Proposal("A", "update", "c", "na", "r"), "r")]
        self.path.write_text(_make_queue_md(ps))
        item = parse_queue_file(self.path)
        self.assertEqual(item.proposals[0].decision, "undecided")
        self.assertFalse(item.has_decided)
        self.assertFalse(item.has_applyable)

    def test_has_applyable(self):
        ps = [(Proposal("A", "append", None, "x", "r"), "r")]
        self.path.write_text(_make_queue_md(ps, decisions=["apply"]))
        item = parse_queue_file(self.path)
        self.assertTrue(item.has_applyable)


class TestApplyQueueItem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.products = self.dir / "wiki" / "products"
        self.products.mkdir(parents=True)
        self.product = self.products / "test-product.md"
        self.product.write_text("""---
title: Test
slug: test-product
status: active
source_count: 1
---

## Intro

Old intro content.

## Specs

Old specs.
""")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_writes_changes(self):
        # Patch PRODUCTS_DIR to our tmpdir
        import review_queue as rq
        original = rq.PRODUCTS_DIR
        rq.PRODUCTS_DIR = self.products
        try:
            item = QueueItem(
                path=self.dir / "queue.md",
                target_slug="test-product",
                article_ref="raw/x/2026-W19/foo",
                proposals=[
                    QueueProposal("Intro", "update", "New intro content", "apply"),
                    QueueProposal("Specs", "append", "- Added line", "reject"),
                ],
            )
            applied, errors = apply_queue_item(item, dry_run=False)
            self.assertEqual(applied, ["Intro"])
            self.assertEqual(errors, [])
            content = self.product.read_text()
            self.assertIn("New intro content", content)
            self.assertNotIn("Old intro content", content)
            # Specs rejected → unchanged
            self.assertIn("Old specs", content)
            self.assertNotIn("Added line", content)
        finally:
            rq.PRODUCTS_DIR = original

    def test_dry_run_does_not_write(self):
        import review_queue as rq
        original = rq.PRODUCTS_DIR
        rq.PRODUCTS_DIR = self.products
        try:
            before = self.product.read_text()
            item = QueueItem(
                path=self.dir / "q.md", target_slug="test-product",
                article_ref="x",
                proposals=[QueueProposal("Intro", "update", "x", "apply")],
            )
            applied, _ = apply_queue_item(item, dry_run=True)
            self.assertEqual(applied, ["Intro"])
            self.assertEqual(self.product.read_text(), before)
        finally:
            rq.PRODUCTS_DIR = original

    def test_missing_target_errors(self):
        item = QueueItem(
            path=self.dir / "q.md", target_slug="nonexistent",
            article_ref="x",
            proposals=[QueueProposal("A", "update", "x", "apply")],
        )
        import review_queue as rq
        original = rq.PRODUCTS_DIR
        rq.PRODUCTS_DIR = self.products
        try:
            applied, errors = apply_queue_item(item, dry_run=False)
            self.assertEqual(applied, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("not found", errors[0])
        finally:
            rq.PRODUCTS_DIR = original

    def test_no_applyable_returns_empty(self):
        item = QueueItem(
            path=self.dir / "q.md", target_slug="test-product",
            article_ref="x",
            proposals=[QueueProposal("A", "update", "x", "reject")],
        )
        applied, errors = apply_queue_item(item, dry_run=True)
        self.assertEqual(applied, [])
        self.assertEqual(errors, [])


class TestWalkQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_skips_readme_archive_orphans(self):
        (self.queue / "README.md").write_text("readme")
        (self.queue / "_archive").mkdir()
        (self.queue / "_archive" / "old.md").write_text("archived")
        (self.queue / "2026-W19").mkdir()
        (self.queue / "2026-W19" / "_orphans").mkdir()
        (self.queue / "2026-W19" / "_orphans" / "orph.md").write_text("orphan")
        # Real item
        (self.queue / "2026-W19" / "real.md").write_text(_make_queue_md(
            [(Proposal("S", "append", None, "x", "r"), "r")]
        ))
        items = walk_queue(self.queue)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].path.name, "real.md")


class TestArchive(unittest.TestCase):
    def test_archive_path_preserves_week(self):
        import review_queue as rq
        tmp = tempfile.TemporaryDirectory()
        try:
            queue = Path(tmp.name) / "ingest-queue"
            (queue / "2026-W19").mkdir(parents=True)
            orig_queue = rq.QUEUE_DIR; orig_arch = rq.ARCHIVE_DIR
            rq.QUEUE_DIR = queue; rq.ARCHIVE_DIR = queue / "_archive"
            try:
                src = queue / "2026-W19" / "foo.md"
                src.write_text("body")
                archived = archive_queue_file(src, dry_run=False)
                self.assertTrue(archived.exists())
                self.assertIn("_archive/2026-W19", str(archived))
                self.assertFalse(src.exists())
            finally:
                rq.QUEUE_DIR = orig_queue; rq.ARCHIVE_DIR = orig_arch
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
