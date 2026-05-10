"""Tests for scripts/gate4_lint.py."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import scripts.gate4_lint as gl  # noqa: E402
from scripts.review_queue import QueueItem, QueueProposal  # noqa: E402


def mock_item(slug="iphone", article="a1", proposals=None):
    return QueueItem(
        path=Path(f"/q/{slug}--{article}.md"),
        target_slug=slug,
        article_ref=f"raw/x/2026-W19/{article}",
        proposals=proposals if proposals is not None else [QueueProposal("S", "update", None, "undecided")],
    )


class TestBacklog(unittest.TestCase):
    def test_empty_info(self):
        issues = gl.check_queue_backlog([])
        self.assertEqual(issues[0].level, "INFO")

    def test_under_threshold_info(self):
        items = [mock_item(article=f"a{i}") for i in range(10)]
        issues = gl.check_queue_backlog(items)
        self.assertEqual(issues[0].level, "INFO")

    def test_over_threshold_warn(self):
        items = [mock_item(article=f"a{i}") for i in range(25)]
        issues = gl.check_queue_backlog(items)
        self.assertEqual(issues[0].level, "WARN")
        self.assertIn("25", issues[0].message)


class TestParseable(unittest.TestCase):
    def test_valid_items_info(self):
        issues = gl.check_queue_parseable([mock_item()])
        self.assertEqual(issues[0].level, "INFO")

    def test_missing_target_warn(self):
        it = mock_item()
        it = QueueItem(path=it.path, target_slug="", article_ref=it.article_ref,
                       proposals=it.proposals)
        issues = gl.check_queue_parseable([it])
        self.assertTrue(any(i.level == "WARN" for i in issues))

    def test_no_proposals_warn(self):
        issues = gl.check_queue_parseable([mock_item(proposals=[])])
        self.assertTrue(any(i.level == "WARN" for i in issues))


class TestLogRefIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.raw = base / "raw" / "src" / "2026-W20"
        self.raw.mkdir(parents=True)
        self.products = base / "products"
        self.products.mkdir()
        (self.products / "iphone-17-pro.md").write_text("# OK")

    def tearDown(self):
        self.tmp.cleanup()

    def test_consistent_info(self):
        (self.raw / "a.meta.json").write_text(json.dumps({
            "ingest_log_ref": "x", "ingest_targets": ["iphone-17-pro"],
        }))
        issues = gl.check_log_ref_integrity(
            raw_dir=self.raw.parent.parent, products_dir=self.products,
        )
        self.assertEqual(issues[0].level, "INFO")

    def test_missing_target_error(self):
        (self.raw / "b.meta.json").write_text(json.dumps({
            "ingest_log_ref": "x", "ingest_targets": ["nonexistent"],
        }))
        issues = gl.check_log_ref_integrity(
            raw_dir=self.raw.parent.parent, products_dir=self.products,
        )
        self.assertTrue(any(i.level == "ERROR" for i in issues))

    def test_ref_without_targets_warn(self):
        (self.raw / "c.meta.json").write_text(json.dumps({
            "ingest_log_ref": "x", "ingest_targets": [],
        }))
        issues = gl.check_log_ref_integrity(
            raw_dir=self.raw.parent.parent, products_dir=self.products,
        )
        self.assertTrue(any(i.level == "WARN" for i in issues))


class TestDuplicateQueue(unittest.TestCase):
    def test_no_dup_info(self):
        items = [mock_item("iphone", "a1"), mock_item("macbook", "a2")]
        issues = gl.check_duplicate_queue(items)
        self.assertEqual(issues[0].level, "INFO")

    def test_duplicate_error(self):
        items = [mock_item("iphone", "a1"), mock_item("iphone", "a1")]
        issues = gl.check_duplicate_queue(items)
        self.assertTrue(any(i.level == "ERROR" for i in issues))


class TestReviewFileFormat(unittest.TestCase):
    """L6 — review file format conformance (PR #41)."""

    # Canonical valid template — must match render in review_queue.py
    VALID = """# Ingest review: iphone-17-pro ← iphone-17-pro-review_20260505

- **Article**: `iphone-17-pro-review_20260505`
- **Title**: iPhone 17 Pro Review
- **Source tier / status / score**: T2 / approved / 8
- **Target page**: `wiki/products/iphone-17-pro.md`
- **Created**: 2026-05-07T15:00:00+08:00
- **Reviewed proposals**: 1

---

## Proposal 1: `AI` (append → review)

**Why review**: new section (not in page)

**LLM reason**: test reason

**Proposed content**:

```markdown
test content
```

**Decision**: [ ] apply  [ ] reject  [ ] edit-then-apply

**Decided by**: @___

**Decided at**: ___

---
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qdir = Path(self.tmp.name) / "ingest-queue"
        (self.qdir / "2026-W19").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, body: str):
        (self.qdir / "2026-W19" / name).write_text(body, encoding="utf-8")

    def test_empty_dir_info(self):
        issues = gl.check_review_file_format(self.qdir)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].level, "INFO")
        self.assertIn("no open review files", issues[0].message)

    def test_valid_file_passes(self):
        self._write("ok.md", self.VALID)
        issues = gl.check_review_file_format(self.qdir)
        self.assertEqual([i.level for i in issues], ["INFO"])
        self.assertIn("conform to template", issues[0].message)

    def test_archive_files_skipped(self):
        """_archive/ files are immutable history, must not be linted."""
        (self.qdir / "_archive" / "2026-W19").mkdir(parents=True)
        (self.qdir / "_archive" / "2026-W19" / "old.md").write_text(
            "totally invalid content", encoding="utf-8")
        issues = gl.check_review_file_format(self.qdir)
        # Only the INFO "nothing to validate" — archive was skipped
        self.assertEqual([i.level for i in issues], ["INFO"])

    def test_readme_skipped(self):
        """README.md is documentation, not a review file."""
        (self.qdir / "README.md").write_text("# README", encoding="utf-8")
        issues = gl.check_review_file_format(self.qdir)
        self.assertEqual([i.level for i in issues], ["INFO"])

    def test_missing_header_warns(self):
        body = self.VALID.replace(
            "# Ingest review: iphone-17-pro ← iphone-17-pro-review_20260505",
            "# Something else")
        self._write("bad.md", body)
        issues = gl.check_review_file_format(self.qdir)
        self.assertTrue(any("missing" in i.message and "header" in i.message
                            for i in issues if i.level == "WARN"))

    def test_missing_metadata_bullet_warns(self):
        body = self.VALID.replace("- **Title**: iPhone 17 Pro Review\n", "")
        self._write("bad.md", body)
        issues = gl.check_review_file_format(self.qdir)
        self.assertTrue(any("**Title**" in i.message
                            for i in issues if i.level == "WARN"))

    def test_no_proposals_warns(self):
        # Keep metadata but strip proposals block
        body = self.VALID.split("## Proposal 1:")[0]
        self._write("bad.md", body)
        issues = gl.check_review_file_format(self.qdir)
        self.assertTrue(any("no `## Proposal N`" in i.message
                            for i in issues if i.level == "WARN"))

    def test_missing_decision_line_warns(self):
        body = self.VALID.replace(
            "**Decision**: [ ] apply  [ ] reject  [ ] edit-then-apply",
            "**Decision**: apply")  # wrong format, no checkboxes
        self._write("bad.md", body)
        issues = gl.check_review_file_format(self.qdir)
        self.assertTrue(any("Decision" in i.message and "0/1" in i.message
                            for i in issues if i.level == "WARN"))

    def test_multi_proposal_counts_all(self):
        """File with 2 proposals but only 1 decision line → 1/2 warning."""
        body = self.VALID.replace(
            "## Proposal 1: `AI` (append → review)",
            "## Proposal 1: `AI` (append → review)\n\n(first block)\n\n## Proposal 2: `BI` (update → review)")
        # Single Decision/Decided line intentionally left
        self._write("bad.md", body)
        issues = gl.check_review_file_format(self.qdir)
        warns = [i for i in issues if i.level == "WARN"]
        self.assertTrue(any("1/2" in i.message for i in warns))


class TestCostEstimate(unittest.TestCase):
    def test_estimate_math(self):
        from scripts.generate_weekly_digest import CostEstimate, collect_cost_estimate, Gate4Stats
        from collections import Counter
        metas = [{"relevance_score": 10} for _ in range(10)]
        metas += [{"relevance_score": None}]  # no Gate 3 call
        g4 = Gate4Stats(per_target=Counter({"x": 3}), queue_open=2,
                        queue_archived=1, orphans=1)
        c = collect_cost_estimate(metas, g4)
        self.assertEqual(c.gate3_calls, 10)
        self.assertEqual(c.gate4_calls, 7)   # 3 + 2 + 1 + 1
        self.assertEqual(c.total_tokens, 10 * 2300 + 7 * 5000)
        self.assertAlmostEqual(c.total_latency_sec, 10 * 1.5 + 7 * 4.0)


if __name__ == "__main__":
    unittest.main()
