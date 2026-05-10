"""Tests for scripts/gate4_queue.py + gate4_pipeline.py."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.gate4_proposer import Proposal, ProposalSet  # noqa: E402
from scripts.gate4_queue import (  # noqa: E402
    format_orphan_file, format_queue_file, iso_week, orphan_file_path,
    queue_file_path, write_orphan, write_review,
)


class TestPaths(unittest.TestCase):
    def test_queue_path_structure(self):
        p = queue_file_path(
            target_slug="iphone-17-pro", article_basename="iphone-17_20260505",
            week="2026-W19", queue_dir=Path("/q"),
        )
        self.assertEqual(p, Path("/q/2026-W19/iphone-17-pro--iphone-17_20260505.md"))

    def test_orphan_path_structure(self):
        p = orphan_file_path(
            article_basename="foo_20260507", week="2026-W19",
            queue_dir=Path("/q"),
        )
        self.assertEqual(p, Path("/q/2026-W19/_orphans/foo_20260507.md"))

    def test_iso_week_format(self):
        fixed = dt.datetime(2026, 5, 7, 14, 0, tzinfo=dt.timezone.utc)
        w = iso_week(fixed)
        self.assertRegex(w, r"^\d{4}-W\d{2}$")


class TestFormatQueueFile(unittest.TestCase):
    def _p(self, section="S", action="append", current=None, new="x", reason="r"):
        return Proposal(section=section, action=action, current_excerpt=current,
                        new_content=new, reason=reason)

    def test_includes_key_fields(self):
        meta = {"source_title": "T", "source_tier": "T1",
                "ingest_status": "approved", "relevance_score": 10}
        body = format_queue_file(
            target_slug="iphone-17-pro", article_meta=meta,
            article_ref="raw/x/2026-W19/foo",
            reviewed_proposals=[(self._p("五大賣點", "append"), "human-owned")],
            now=dt.datetime(2026, 5, 7, 14, tzinfo=dt.timezone(dt.timedelta(hours=8))),
        )
        self.assertIn("iphone-17-pro", body)
        self.assertIn("五大賣點", body)
        self.assertIn("human-owned", body)
        self.assertIn("Decision", body)
        self.assertIn("T1", body)

    def test_includes_current_excerpt_when_present(self):
        body = format_queue_file(
            target_slug="x", article_meta={},
            article_ref="r",
            reviewed_proposals=[(self._p(current="A19 Pro chip spec"), "note")],
        )
        self.assertIn("A19 Pro chip spec", body)
        self.assertIn("Current excerpt", body)

    def test_empty_proposals_still_has_header(self):
        body = format_queue_file(
            target_slug="x", article_meta={},
            article_ref="r", reviewed_proposals=[],
        )
        self.assertIn("# Ingest review", body)

    def test_rejected_proposals_listed(self):
        body = format_queue_file(
            target_slug="x", article_meta={}, article_ref="r",
            reviewed_proposals=[],
            rejected_proposals=[(self._p("S", "update"), "hallucination")],
        )
        self.assertIn("Rejected proposals", body)
        self.assertIn("hallucination", body)


class TestFormatOrphanFile(unittest.TestCase):
    def test_includes_options(self):
        meta = {"source_title": "T", "key_entities": ["e1"],
                "ingest_status": "approved", "relevance_score": 8}
        body = format_orphan_file(article_meta=meta, article_ref="r")
        self.assertIn("Orphan article", body)
        self.assertIn("create-page", body)
        self.assertIn("tag-existing", body)


class TestWriteReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_file(self):
        p = write_review(
            target_slug="iphone-17-pro",
            article_meta={"source_title": "T"},
            article_ref="raw/x/2026-W19/foo",
            article_basename="foo",
            reviewed_proposals=[(Proposal("S", "append", None, "new", "r"), "reason")],
            week="2026-W19", queue_dir=self.dir,
        )
        self.assertTrue(p.exists())
        self.assertIn("iphone-17-pro", p.read_text())

    def test_dry_run_does_not_write(self):
        p = write_review(
            target_slug="x", article_meta={},
            article_ref="r", article_basename="b",
            reviewed_proposals=[],
            week="2026-W19", queue_dir=self.dir, dry_run=True,
        )
        self.assertFalse(p.exists())

    def test_write_orphan(self):
        p = write_orphan(
            article_meta={"source_title": "T"},
            article_ref="r", article_basename="foo_20260507",
            week="2026-W19", queue_dir=self.dir,
        )
        self.assertTrue(p.exists())
        self.assertIn("_orphans", str(p))


class TestPipelineRouting(unittest.TestCase):
    """Integration: gate4_pipeline.run_gate4_for_article orchestration."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # Fake product page
        self.products_dir = self.dir / "wiki" / "products"
        self.products_dir.mkdir(parents=True)
        (self.products_dir / "iphone-17-pro.md").write_text("""---
title: iPhone 17 Pro
slug: iphone-17-pro
status: active
tags: [iphone, a19-pro]
ingest_managed_sections: [一句話定位]
human_owned_sections: []
---

## 一句話定位

Old positioning.
""")
        # Fake article meta + text
        self.meta_path = self.dir / "article.meta.json"
        self.meta_path.write_text(json.dumps({
            "source_title": "iPhone 17 review",
            "source_type": "apple-com-tw",
            "source_tier": "T1",
            "ingest_status": "approved",
            "relevance_score": 10,
            "key_entities": ["iPhone 17"],
        }))
        (self.dir / "article.txt").write_text("Content about iPhone 17")

    def tearDown(self):
        self.tmp.cleanup()

    def test_orphan_when_no_products(self):
        from scripts.gate4_pipeline import run_gate4_for_article
        llm = MagicMock()
        result, queues = run_gate4_for_article(
            self.meta_path, llm=llm, products=[], dry_run=True,
        )
        self.assertIsNone(result)
        self.assertEqual(len(queues), 1)
        self.assertIn("_orphans", str(queues[0]))

    def test_skips_if_already_applied(self):
        from scripts.gate4_pipeline import run_gate4_for_article
        from scripts.gate4_router import Product
        meta = json.loads(self.meta_path.read_text())
        meta["ingest_log_ref"] = "already"
        self.meta_path.write_text(json.dumps(meta))

        llm = MagicMock()
        products = [Product("iphone-17-pro", self.products_dir / "iphone-17-pro.md",
                            ["iphone", "a19-pro"], "iPhone 17 Pro")]
        result, queues = run_gate4_for_article(
            self.meta_path, llm=llm, products=products, dry_run=True,
        )
        self.assertIsNone(result)
        self.assertEqual(queues, [])
        llm.chat.assert_not_called()  # LLM never invoked


if __name__ == "__main__":
    unittest.main()
