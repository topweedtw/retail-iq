"""Tests for scripts/cost_report.py."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import scripts.cost_report as cr  # noqa: E402


# v2.0 digest template stub — just enough to exercise the parse regexes
V20_DIGEST_TEMPLATE = """---
type: digest
slug: {week}-digest
title: {week} RetailIQ 週報
generated_by: v2.0 Full 5-gate pipeline + Gate 4 stats
agents_version: v2.0
---

# 📊 {week} RetailIQ 週報

## LLM 成本估算（v2.1 新增）

> calibration note

- **Gate 3 LLM 呼叫**：{g3} 次
- **Gate 4 LLM 呼叫**：{g4} 次
- **估算 token 總量**：{tokens:,}
- **估算 LLM 時間**：{latency}s ({latency_min} min)

---
"""

EMPTY_WEEK_DIGEST = """---
type: digest
slug: 2026-W20-digest
title: 2026-W20 RetailIQ 週報（空白週）
empty_week: true
---

# 📊 2026-W20 RetailIQ 週報

⚠️ 空白週
"""


def make_digest(dir_: Path, week: str, g3: int, g4: int, tokens: int,
                latency: float) -> Path:
    content = V20_DIGEST_TEMPLATE.format(
        week=week, g3=g3, g4=g4, tokens=tokens,
        latency=int(latency), latency_min=f"{latency/60:.1f}")
    p = dir_ / f"{week}-digest.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestParseDigest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parses_v20_digest(self):
        p = make_digest(self.d, "2026-W19", 27, 4, 82100, 56)
        wc = cr.parse_digest(p)
        self.assertIsNotNone(wc)
        self.assertEqual(wc.week, "2026-W19")
        self.assertEqual(wc.gate3_calls, 27)
        self.assertEqual(wc.gate4_calls, 4)
        self.assertEqual(wc.tokens, 82100)
        self.assertEqual(wc.latency_sec, 56.0)

    def test_empty_week_returns_none(self):
        p = self.d / "2026-W20-digest.md"
        p.write_text(EMPTY_WEEK_DIGEST, encoding="utf-8")
        self.assertIsNone(cr.parse_digest(p))

    def test_wrong_filename_returns_none(self):
        p = self.d / "2026-W18-relevance.md"  # old naming
        p.write_text(V20_DIGEST_TEMPLATE.format(
            week="2026-W18", g3=10, g4=0, tokens=23000, latency=15, latency_min="0.3"),
            encoding="utf-8")
        self.assertIsNone(cr.parse_digest(p))

    def test_missing_cost_section_returns_none(self):
        p = self.d / "2026-W21-digest.md"
        p.write_text("# not a real digest\nno cost here", encoding="utf-8")
        self.assertIsNone(cr.parse_digest(p))

    def test_comma_in_token_count_parsed(self):
        p = make_digest(self.d, "2026-W22", 100, 50, 1_234_567, 500)
        wc = cr.parse_digest(p)
        self.assertEqual(wc.tokens, 1_234_567)


class TestCollectWeeks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_sorted_by_filename(self):
        make_digest(self.d, "2026-W20", 10, 1, 28000, 18)
        make_digest(self.d, "2026-W18", 5, 0, 11500, 8)
        make_digest(self.d, "2026-W19", 27, 4, 82100, 56)
        weeks = cr.collect_weeks(self.d)
        self.assertEqual([w.week for w in weeks], ["2026-W18", "2026-W19", "2026-W20"])

    def test_skips_empty_weeks(self):
        make_digest(self.d, "2026-W19", 27, 4, 82100, 56)
        (self.d / "2026-W20-digest.md").write_text(EMPTY_WEEK_DIGEST, encoding="utf-8")
        weeks = cr.collect_weeks(self.d)
        self.assertEqual(len(weeks), 1)
        self.assertEqual(weeks[0].week, "2026-W19")

    def test_skips_legacy_relevance_files(self):
        (self.d / "2026-W18-relevance.md").write_text(
            V20_DIGEST_TEMPLATE.format(week="2026-W18", g3=0, g4=0,
                                       tokens=0, latency=0, latency_min="0.0"),
            encoding="utf-8")
        make_digest(self.d, "2026-W19", 5, 0, 11500, 8)
        weeks = cr.collect_weeks(self.d)
        self.assertEqual([w.week for w in weeks], ["2026-W19"])


class TestDelta(unittest.TestCase):
    def test_normal_delta(self):
        self.assertAlmostEqual(cr.compute_delta_pct(120, 100), 20.0)
        self.assertAlmostEqual(cr.compute_delta_pct(80, 100), -20.0)

    def test_zero_previous_returns_none(self):
        self.assertIsNone(cr.compute_delta_pct(500, 0))


class TestRenderTrend(unittest.TestCase):
    def _weeks(self):
        return [
            cr.WeekCost("2026-W18", 10, 0, 23000, 15.0, "x"),
            cr.WeekCost("2026-W19", 27, 4, 82100, 56.0, "x"),
        ]

    def test_empty_weeks_returns_placeholder(self):
        out = cr.render_trend([])
        self.assertIn("No v2.0+ digest files", out)

    def test_table_has_all_weeks(self):
        out = cr.render_trend(self._weeks())
        self.assertIn("2026-W18", out)
        self.assertIn("2026-W19", out)
        self.assertIn("82,100", out)

    def test_first_week_has_dash_delta(self):
        out = cr.render_trend(self._weeks())
        # W18 row should show "—" in delta column since no prior week
        line = [l for l in out.splitlines() if "2026-W18" in l][0]
        self.assertIn("—", line)

    def test_wow_delta_computed(self):
        out = cr.render_trend(self._weeks())
        # (82100 - 23000) / 23000 = +257.0%
        self.assertIn("+257.0%", out)
        # Week-over-week highlight block
        self.assertIn("up", out)  # direction word
        self.assertIn("257.0%", out)

    def test_gate4_started_highlight(self):
        weeks = [
            cr.WeekCost("2026-W18", 10, 0, 23000, 15.0, "x"),
            cr.WeekCost("2026-W19", 27, 4, 82100, 56.0, "x"),
        ]
        out = cr.render_trend(weeks)
        self.assertIn("Gate 4 started contributing", out)

    def test_gate4_dropped_highlight(self):
        weeks = [
            cr.WeekCost("2026-W18", 10, 5, 48000, 35.0, "x"),
            cr.WeekCost("2026-W19", 27, 0, 62100, 40.0, "x"),
        ]
        out = cr.render_trend(weeks)
        self.assertIn("Gate 4 activity dropped to 0", out)

    def test_budget_alert_flags_over_limit(self):
        out = cr.render_trend(self._weeks(), budget=50_000)
        self.assertIn("Budget alerts", out)
        self.assertIn("2026-W19", out)
        self.assertIn("🚨", out)

    def test_budget_ok_when_all_under(self):
        out = cr.render_trend(self._weeks(), budget=100_000)
        self.assertIn("Budget status", out)
        self.assertIn("under", out)


if __name__ == "__main__":
    unittest.main()
