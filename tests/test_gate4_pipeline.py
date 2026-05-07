"""Tests for scripts/gate4_pipeline.py — full orchestration.

Covers:
- Happy path: route → propose → apply produces expected ApplyResult
- Fan-out: N candidates run N independent LLM calls
- MAX_FANOUT cap: too many candidates → all go to review queue
- Eligibility filtering: status / ingest_log_ref checks
- run_gate4_pass aggregate stats
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import gate4_pipeline as gp  # noqa: E402
from gate4_router import Product  # noqa: E402
from gate4_proposer import Proposal, ProposalSet  # noqa: E402


def make_meta(status="approved", entities=None, log_ref=None, tier="T2"):
    return {
        "source_title": "Test Article",
        "source_type": "test-src",
        "source_tier": tier,
        "ingest_status": status,
        "relevance_score": 8,
        "key_entities": entities or ["iPhone 17", "Apple Intelligence"],
        **({"ingest_log_ref": log_ref} if log_ref else {}),
    }


def make_product(slug, tags=None):
    return Product(
        slug=slug,
        path=Path(f"/fake/{slug}.md"),
        tags=tags or ["iphone", "a19-pro"],
        title=slug,
    )


class TestGate4PipelineOrchestration(unittest.TestCase):
    """End-to-end tests using mocked LLM + filesystem."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # Set up a realistic fake products dir
        self.products_dir = self.dir / "wiki" / "products"
        self.products_dir.mkdir(parents=True)
        self.iphone_page = self.products_dir / "iphone-17-pro.md"
        self.iphone_page.write_text("""---
title: iPhone 17 Pro
slug: iphone-17-pro
status: active
source_count: 1
tags: [iphone, a19-pro]
ingest_managed_sections: [一句話定位]
human_owned_sections: []
---

## 一句話定位

Old positioning text.
""")

        # Fake article
        self.article_dir = self.dir / "raw" / "test-src" / "2026-W19"
        self.article_dir.mkdir(parents=True)
        self.meta_path = self.article_dir / "article_20260507.meta.json"
        self.meta_path.write_text(json.dumps(make_meta()))
        (self.article_dir / "article_20260507.txt").write_text("iPhone 17 has A19 Pro")

        # Patch module-level paths in BOTH gate4_applier AND gate4_pipeline
        # (gate4_pipeline imported PRODUCTS_DIR at load time)
        import gate4_applier, gate4_pipeline
        self._orig_applier_products = gate4_applier.PRODUCTS_DIR
        self._orig_pipeline_products = gate4_pipeline.PRODUCTS_DIR
        gate4_applier.PRODUCTS_DIR = self.products_dir
        gate4_pipeline.PRODUCTS_DIR = self.products_dir

    def tearDown(self):
        import gate4_applier, gate4_pipeline
        gate4_applier.PRODUCTS_DIR = self._orig_applier_products
        gate4_pipeline.PRODUCTS_DIR = self._orig_pipeline_products
        self.tmp.cleanup()

    def _mock_llm_proposals(self, proposals_json):
        llm = MagicMock()
        llm.chat.return_value = json.dumps(proposals_json)
        return llm

    def test_happy_path_single_target(self):
        """1 article → 1 matching product → propose returns valid → applied."""
        llm = self._mock_llm_proposals({
            "target_valid": True,
            "target_valid_reason": "match",
            "proposals": [{
                "section": "一句話定位",
                "action": "update",
                "current_excerpt": "Old positioning",
                "new_content": "New A19-powered positioning",
                "reason": "article confirms A19",
            }],
        })
        products = [make_product("iphone-17-pro"), make_product("decoy1", tags=["unrelated1"]), make_product("decoy2", tags=["unrelated2"])]

        # Point gate4_queue's QUEUE_DIR into tmpdir too
        import gate4_queue, gate4_pipeline
        orig_queue = gate4_queue.QUEUE_DIR
        gate4_queue.QUEUE_DIR = self.dir / "queue"
        try:
            result, queues = gp.run_gate4_for_article(
                self.meta_path, llm=llm, products=products, dry_run=False,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.applied_sections, ["一句話定位"])
            # Page updated
            self.assertIn("New A19-powered positioning",
                          self.iphone_page.read_text())
            # meta.json got ingest_log_ref
            meta_after = json.loads(self.meta_path.read_text())
            self.assertIsNotNone(meta_after.get("ingest_log_ref"))
        finally:
            gate4_queue.QUEUE_DIR = orig_queue

    def test_orphan_when_no_matching_product(self):
        llm = MagicMock()
        import gate4_queue
        orig_queue = gate4_queue.QUEUE_DIR
        gate4_queue.QUEUE_DIR = self.dir / "queue"
        try:
            result, queues = gp.run_gate4_for_article(
                self.meta_path, llm=llm, products=[], dry_run=True,
            )
            self.assertIsNone(result)
            self.assertEqual(len(queues), 1)
            self.assertIn("_orphans", str(queues[0]))
            llm.chat.assert_not_called()  # no routing match → no LLM
        finally:
            gate4_queue.QUEUE_DIR = orig_queue

    def test_idempotent_skip_when_log_ref_set(self):
        meta = make_meta(log_ref="existing")
        self.meta_path.write_text(json.dumps(meta))
        llm = MagicMock()
        result, queues = gp.run_gate4_for_article(
            self.meta_path, llm=llm,
            products=[make_product("iphone-17-pro")],
        )
        self.assertIsNone(result)
        self.assertEqual(queues, [])
        llm.chat.assert_not_called()

    def test_ineligible_status_skipped(self):
        meta = make_meta(status="skipped-low-relevance")
        self.meta_path.write_text(json.dumps(meta))
        llm = MagicMock()
        result, queues = gp.run_gate4_for_article(
            self.meta_path, llm=llm,
            products=[make_product("iphone-17-pro")],
        )
        self.assertIsNone(result)
        self.assertEqual(queues, [])
        llm.chat.assert_not_called()

    def test_fanout_cap_skips_llm(self):
        """> MAX_FANOUT candidates → all go to review queue, no LLM call."""
        llm = MagicMock()
        # Create MAX_FANOUT + 1 candidate products that all match
        # Each product has a distinct tag that matches some entity in the article,
        # so IDF > 0 for each. (If all shared one tag, IDF=0 → no matches.)
        # We add iPhone N to entities and give products unique tags iphone-1..N+2
        # Simpler: give each a generic tag and use >2 products so IDF > 0
        products = [
            make_product(f"prod{i}", tags=[f"iphone-{i}", f"unique{i}"])
            for i in range(gp.MAX_FANOUT + 1)
        ]
        # Entities need to match the per-product tags
        meta = json.loads(self.meta_path.read_text())
        meta["key_entities"] = [f"iPhone {i}" for i in range(gp.MAX_FANOUT + 1)]
        self.meta_path.write_text(json.dumps(meta))
        import gate4_queue
        orig_queue = gate4_queue.QUEUE_DIR
        gate4_queue.QUEUE_DIR = self.dir / "queue"
        try:
            result, queues = gp.run_gate4_for_article(
                self.meta_path, llm=llm, products=products, dry_run=True,
            )
            self.assertIsNone(result)  # no apply
            self.assertEqual(len(queues), gp.MAX_FANOUT + 1)
            llm.chat.assert_not_called()
        finally:
            gate4_queue.QUEUE_DIR = orig_queue

    def test_target_invalid_rejected_no_apply(self):
        """LLM returns target_valid=false → apply_to_page skips."""
        llm = self._mock_llm_proposals({
            "target_valid": False,
            "target_valid_reason": "off-topic",
            "proposals": [],
        })
        before = self.iphone_page.read_text()
        products = [make_product("iphone-17-pro"), make_product("decoy1", tags=["unrelated1"]), make_product("decoy2", tags=["unrelated2"])]
        import gate4_queue
        orig_queue = gate4_queue.QUEUE_DIR
        gate4_queue.QUEUE_DIR = self.dir / "queue"
        try:
            result, queues = gp.run_gate4_for_article(
                self.meta_path, llm=llm, products=products, dry_run=True,
            )
            # ApplyResult returned but empty
            self.assertIsNotNone(result)
            self.assertEqual(result.applied_sections, [])
            # Page not modified
            self.assertEqual(self.iphone_page.read_text(), before)
        finally:
            gate4_queue.QUEUE_DIR = orig_queue


class TestRunGate4Pass(unittest.TestCase):
    """Aggregate behavior of run_gate4_pass over multiple articles."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.article_dir = self.dir / "raw" / "src" / "2026-W19"
        self.article_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_meta(self, name, **overrides):
        p = self.article_dir / f"{name}.meta.json"
        p.write_text(json.dumps(make_meta(**overrides)))
        (self.article_dir / f"{name}.txt").write_text("body")
        return p

    def test_filters_ineligible(self):
        self._write_meta("a1", status="approved")
        self._write_meta("a2", status="skipped-low-relevance")
        self._write_meta("a3", status="approved", log_ref="done")

        # Mock load_products with a dummy (non-empty) + run_gate4_for_article
        # (empty products would trigger early-exit)
        with patch.object(gp, "load_products", return_value=[MagicMock()]), \
             patch.object(gp, "run_gate4_for_article",
                          return_value=(None, [])) as mock_run:
            report = gp.run_gate4_pass(
                [self.article_dir / "a1.meta.json",
                 self.article_dir / "a2.meta.json",
                 self.article_dir / "a3.meta.json"],
                llm=MagicMock(), dry_run=True,
            )
        self.assertEqual(report.processed, 1)             # only a1
        self.assertEqual(report.skipped_not_eligible, 1)  # a2
        self.assertEqual(report.skipped_already_applied, 1)  # a3

    def test_counts_applied_and_review(self):
        from gate4_applier import ApplyResult
        self._write_meta("a1")
        self._write_meta("a2")
        fake_apply = ApplyResult(applied_sections=["S1", "S2"],
                                  reviewed_proposals=[],
                                  rejected_proposals=[])
        fake_review_path = self.dir / "queue" / "f.md"
        with patch.object(gp, "load_products", return_value=[MagicMock()]), \
             patch.object(gp, "run_gate4_for_article",
                          return_value=(fake_apply, [fake_review_path])):
            report = gp.run_gate4_pass(
                [self.article_dir / "a1.meta.json",
                 self.article_dir / "a2.meta.json"],
                llm=MagicMock(), dry_run=True,
            )
        self.assertEqual(report.processed, 2)
        self.assertEqual(report.applied_articles, 2)
        self.assertEqual(report.total_applied_sections, 4)  # 2 articles × 2 sections
        self.assertEqual(report.review_items, 2)

    def test_empty_products_early_exit(self):
        self._write_meta("a1")
        with patch.object(gp, "load_products", return_value=[]):
            report = gp.run_gate4_pass(
                [self.article_dir / "a1.meta.json"],
                llm=MagicMock(),
            )
        self.assertEqual(report.processed, 0)

    def test_catches_exceptions_without_crashing(self):
        self._write_meta("a1")
        with patch.object(gp, "load_products", return_value=[MagicMock()]), \
             patch.object(gp, "run_gate4_for_article",
                          side_effect=RuntimeError("boom")):
            report = gp.run_gate4_pass(
                [self.article_dir / "a1.meta.json"],
                llm=MagicMock(),
            )
        self.assertEqual(report.processed, 1)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("boom", report.errors[0])


if __name__ == "__main__":
    unittest.main()
