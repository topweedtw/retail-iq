"""
Tests for scripts/relevance_scorer.py (Gate 3)

使用 APPLE_GENAI_MOCK=1 讓 LLMClient 回 deterministic mock score。
"""
import os
import sys
import unittest
from pathlib import Path

os.environ["APPLE_GENAI_MOCK"] = "1"

from scripts.relevance_scorer import (  # noqa: E402
    score_article,
    status_for_score,
    _parse_score,
    RelevanceScore,
)


class TestStatusForScore(unittest.TestCase):
    """§8.10.2 分數對應 ingest_status"""

    def test_low(self):
        for s in range(0, 5):
            self.assertEqual(status_for_score(s), "skipped-low-relevance")

    def test_middle(self):
        for s in (5, 6):
            self.assertEqual(status_for_score(s), "pending-review")

    def test_high(self):
        for s in range(7, 11):
            self.assertEqual(status_for_score(s), "approved")


class TestParseScore(unittest.TestCase):

    def test_wellformed(self):
        raw = {
            "d1_product_mention": 3,
            "d2_ecosystem": 2,
            "d3_training_potential": 3,
            "d4_timeliness": 2,
            "total": 10,
            "reasoning": "全數 Apple 相關",
            "key_entities": ["iPhone", "Mac"],
        }
        score = _parse_score(raw)
        self.assertEqual(score.total, 10)
        self.assertEqual(score.breakdown["d1_product_mention"], 3)
        self.assertEqual(score.key_entities, ["iPhone", "Mac"])

    def test_total_mismatch_prefers_sum(self):
        """LLM 自相矛盾時以實際 sum 為準"""
        raw = {
            "d1_product_mention": 3,
            "d2_ecosystem": 2,
            "d3_training_potential": 3,
            "d4_timeliness": 2,
            "total": 5,  # wrong
            "reasoning": "LLM 算錯",
        }
        score = _parse_score(raw)
        self.assertEqual(score.total, 10)  # sum wins

    def test_clamps_out_of_range(self):
        raw = {
            "d1_product_mention": 99,  # max 3
            "d2_ecosystem": -5,
            "d3_training_potential": 2,
            "d4_timeliness": 100,
        }
        score = _parse_score(raw)
        self.assertEqual(score.breakdown["d1_product_mention"], 3)
        self.assertEqual(score.breakdown["d2_ecosystem"], 0)
        self.assertEqual(score.breakdown["d3_training_potential"], 2)
        self.assertEqual(score.breakdown["d4_timeliness"], 2)

    def test_missing_fields_default_zero(self):
        score = _parse_score({})
        self.assertEqual(score.total, 0)
        self.assertEqual(score.reasoning, "")
        self.assertEqual(score.key_entities, [])

    def test_non_list_entities_safe(self):
        score = _parse_score({"key_entities": "not a list"})
        self.assertEqual(score.key_entities, [])

    def test_entities_capped_at_5(self):
        score = _parse_score({"key_entities": ["a", "b", "c", "d", "e", "f", "g"]})
        self.assertEqual(len(score.key_entities), 5)

    def test_reasoning_truncated(self):
        long_text = "很長" * 100
        score = _parse_score({"reasoning": long_text})
        self.assertLessEqual(len(score.reasoning), 100)


class TestScoreArticleE2E(unittest.TestCase):
    """Mock LLM 回固定分數 → scorer 正確解析出 RelevanceScore"""

    def test_apple_content_high_score(self):
        """Mock chat 看到 'rubric' 會回 Apple 相關 9 分"""
        score = score_article(
            title="iPhone 17 Pro 規格",
            content="熱鍛造鋁金屬一體成型，A19 Pro 晶片，Apple Intelligence 全面支援。",
        )
        self.assertEqual(score.total, 9)  # mock stub 固定 9
        self.assertEqual(status_for_score(score.total), "approved")

    def test_content_truncation(self):
        """超長內文應被截斷（mock 不會因此出錯）"""
        score = score_article(
            title="Test",
            content="x" * 50000,
            max_content_chars=100,
        )
        # mock 還是回 9，但重點是沒 crash
        self.assertIsInstance(score, RelevanceScore)

    def test_empty_content(self):
        score = score_article(title="empty", content="")
        self.assertIsInstance(score, RelevanceScore)


class TestSchemaCompliance(unittest.TestCase):
    """確保 breakdown 欄位名符合 AGENTS.md §8.4 規範"""

    REQUIRED_BREAKDOWN_KEYS = {
        "d1_product_mention",
        "d2_ecosystem",
        "d3_training_potential",
        "d4_timeliness",
    }

    def test_breakdown_keys(self):
        score = score_article(title="t", content="c")
        self.assertEqual(
            set(score.breakdown.keys()),
            self.REQUIRED_BREAKDOWN_KEYS,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
