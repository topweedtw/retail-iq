"""Tests for scripts/generate_weekly_digest.py."""
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import scripts.generate_weekly_digest as g  # noqa: E402


class TestSourceStats(unittest.TestCase):
    def test_avg_and_pass_rate(self):
        s = g.SourceStats(name="x", count=4, approved=2, scores=[10, 8, 3, 2])
        self.assertEqual(s.avg_score, 23 / 4)
        self.assertEqual(s.pass_rate, 0.5)

    def test_empty_stats_safe(self):
        s = g.SourceStats(name="x")
        self.assertEqual(s.avg_score, 0.0)
        self.assertEqual(s.pass_rate, 0.0)


class TestCollectArticleStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"
        (self.raw / "apple-com-tw" / "2026-W20").mkdir(parents=True)
        (self.raw / "ars-technica" / "2026-W20").mkdir(parents=True)
        # Article 1: T1 approved
        (self.raw / "apple-com-tw" / "2026-W20" / "a1_20260514.meta.json").write_text(json.dumps({
            "source_tier": "T1", "ingest_status": "approved", "relevance_score": 10,
        }))
        # Article 2: T2 pending-review
        (self.raw / "ars-technica" / "2026-W20" / "a2_20260514.meta.json").write_text(json.dumps({
            "source_tier": "T2", "ingest_status": "pending-review", "relevance_score": 6,
        }))
        # Article 3: T2 low-relevance (+Gate 4 applied)
        (self.raw / "ars-technica" / "2026-W20" / "a3_20260515.meta.json").write_text(json.dumps({
            "source_tier": "T2", "ingest_status": "approved", "relevance_score": 8,
            "ingest_log_ref": "2026-05-14T10:00+08:00|iphone",
            "ingest_targets": ["iphone-17-pro"],
        }))
        self._orig_raw = g.RAW_DIR
        g.RAW_DIR = self.raw

    def tearDown(self):
        g.RAW_DIR = self._orig_raw
        self.tmp.cleanup()

    def test_aggregates_by_source(self):
        sources, metas = g.collect_article_stats("2026-W20")
        self.assertEqual(len(sources), 2)
        self.assertEqual(len(metas), 3)
        by_name = {s.name: s for s in sources}
        self.assertEqual(by_name["apple-com-tw"].count, 1)
        self.assertEqual(by_name["apple-com-tw"].approved, 1)
        self.assertEqual(by_name["ars-technica"].count, 2)
        self.assertEqual(by_name["ars-technica"].pending_review, 1)

    def test_sorted_by_avg_desc(self):
        sources, _ = g.collect_article_stats("2026-W20")
        self.assertEqual(sources[0].name, "apple-com-tw")  # 10.0
        self.assertEqual(sources[1].name, "ars-technica")  # avg 7.0


class TestCollectGate4Stats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.queue = base / "wiki" / "ingest-queue"
        (self.queue / "2026-W20").mkdir(parents=True)
        (self.queue / "2026-W20" / "_orphans").mkdir()
        (self.queue / "_archive" / "2026-W20").mkdir(parents=True)
        # 1 open review
        (self.queue / "2026-W20" / "iphone-17-pro--a1_20260514.md").write_text("x")
        # 1 orphan
        (self.queue / "2026-W20" / "_orphans" / "a4.md").write_text("x")
        # 1 archived
        (self.queue / "_archive" / "2026-W20" / "macbook--a5.md").write_text("x")
        self._orig_queue = g.QUEUE_DIR
        g.QUEUE_DIR = self.queue

    def tearDown(self):
        g.QUEUE_DIR = self._orig_queue
        self.tmp.cleanup()

    def test_counts_queue_states(self):
        metas = [
            {"ingest_log_ref": "x", "ingest_targets": ["iphone-17-pro"]},
            {"ingest_log_ref": "y", "ingest_targets": ["iphone-17-pro", "macbook-neo"]},
            {"ingest_status": "pending-review"},  # no apply
        ]
        g4 = g.collect_gate4_stats("2026-W20", metas)
        self.assertEqual(g4.applied_articles, 2)
        self.assertEqual(g4.per_target["iphone-17-pro"], 2)
        self.assertEqual(g4.per_target["macbook-neo"], 1)
        self.assertEqual(g4.queue_open, 1)
        self.assertEqual(g4.orphans, 1)
        self.assertEqual(g4.queue_archived, 1)


class TestWeekRange(unittest.TestCase):
    def test_known_week(self):
        r = g._week_range("2026-W19")
        self.assertIn("2026-05-", r)
        self.assertIn("~", r)

    def test_invalid_returns_empty(self):
        self.assertEqual(g._week_range("not-a-week"), "")


class TestRender(unittest.TestCase):
    def test_render_includes_key_sections(self):
        sources = [g.SourceStats(name="apple-com-tw", tier="T1", count=2,
                                 approved=2, scores=[10, 10])]
        metas = [{"source_title": "T", "source_type": "apple-com-tw",
                  "relevance_score": 10}]
        g4 = g.Gate4Stats(applied_articles=1,
                         per_target=Counter({"iphone-17-pro": 1}))
        out = g.render_digest("2026-W19", sources, metas, g4)
        self.assertIn("總覽", out)
        self.assertIn("各來源健康度", out)
        self.assertIn("Gate 4 運作", out)
        self.assertIn("Top 5 高分文章", out)
        self.assertIn("iphone-17-pro", out)


class TestEmptyWeekDigest(unittest.TestCase):
    """v0.6+: empty-week placeholder support (PR #40)."""

    def test_empty_digest_has_required_frontmatter(self):
        out = g.render_empty_digest("2026-W20")
        self.assertIn("type: digest", out)
        self.assertIn("slug: 2026-W20-digest", out)
        self.assertIn("empty_week: true", out)
        self.assertIn("agents_version: v2.0", out)

    def test_empty_digest_has_week_title_and_warning(self):
        out = g.render_empty_digest("2026-W20")
        self.assertIn("2026-W20 RetailIQ 週報", out)
        self.assertIn("空白週", out)
        self.assertIn("尚無 ingest 活動", out)

    def test_empty_digest_has_next_step_guidance(self):
        """Ops runbook: empty-week file must tell reviewer what to do next."""
        out = g.render_empty_digest("2026-W20")
        self.assertIn("crawler", out)
        self.assertIn("ingest_agent", out)
        self.assertIn("generate_weekly_digest.py 2026-W20", out)

    def test_empty_digest_references_correct_week(self):
        """Week token must propagate through the whole template."""
        out = g.render_empty_digest("2026-W42")
        # Frontmatter, heading, and runbook all consistently reference the week
        self.assertEqual(out.count("2026-W42"), 5)
        self.assertNotIn("2026-W20", out)  # no leaked default


if __name__ == "__main__":
    unittest.main()
