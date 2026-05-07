"""Tests for scripts/backfill_gate3.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import backfill_gate3 as bg  # noqa: E402


class TestStatusForScore(unittest.TestCase):
    def test_t1_always_approved(self):
        for s in (0, 3, 6, 10):
            self.assertEqual(bg.status_for_score(s, "T1"), "approved")

    def test_non_t1_thresholds(self):
        self.assertEqual(bg.status_for_score(0, "T3"), "skipped-low-relevance")
        self.assertEqual(bg.status_for_score(4, "T2"), "skipped-low-relevance")
        self.assertEqual(bg.status_for_score(5, "T3"), "pending-review")
        self.assertEqual(bg.status_for_score(6, "T3"), "pending-review")
        self.assertEqual(bg.status_for_score(7, "T3"), "approved")
        self.assertEqual(bg.status_for_score(10, "T3"), "approved")


class TestPatchMeta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".meta.json", delete=False, encoding="utf-8"
        )
        json.dump(
            {
                "source_url": "https://example.com/a",
                "source_tier": "T3",
                "ingest_status": "pending",
            },
            self.tmp,
        )
        self.tmp.close()
        self.path = Path(self.tmp.name)
        self.entry = {
            "score": 7,
            "reasoning": "good",
            "breakdown": {"d1_product_mention": 3},
            "entities": ["iPhone"],
            "tier": "T3",
        }

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_patches_fields(self):
        result = bg.patch_meta(self.path, self.entry, dry_run=False)
        self.assertEqual(result, "patched")
        meta = json.loads(self.path.read_text())
        self.assertEqual(meta["relevance_score"], 7)
        self.assertEqual(meta["relevance_reasoning"], "good")
        self.assertEqual(meta["key_entities"], ["iPhone"])
        self.assertEqual(meta["ingest_status"], "approved")

    def test_idempotent(self):
        bg.patch_meta(self.path, self.entry, dry_run=False)
        result = bg.patch_meta(self.path, self.entry, dry_run=False)
        self.assertEqual(result, "unchanged")

    def test_dry_run_does_not_write(self):
        before = self.path.read_text()
        result = bg.patch_meta(self.path, self.entry, dry_run=True)
        self.assertEqual(result, "would-patch")
        self.assertEqual(self.path.read_text(), before)

    def test_missing_file(self):
        result = bg.patch_meta(Path("/nonexistent.meta.json"), self.entry, dry_run=False)
        self.assertEqual(result, "missing")

    def test_t1_low_score_still_approved(self):
        # T1 rubric=6 → 仍 approved（§8.10.4 豁免）
        t1_path = Path(self.tmp.name + ".t1")
        t1_path.write_text(json.dumps({"source_tier": "T1"}))
        try:
            entry = {**self.entry, "score": 6, "tier": "T1"}
            bg.patch_meta(t1_path, entry, dry_run=False)
            meta = json.loads(t1_path.read_text())
            self.assertEqual(meta["ingest_status"], "approved")
            self.assertEqual(meta["relevance_score"], 6)  # 保留原分數
        finally:
            t1_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
