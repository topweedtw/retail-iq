"""Tests for v0.6 diff-merge behavior in gate4_applier.

These tests specifically cover the new merge_section_update + is_safe_update
logic that prevents LLM 'update' actions from flattening markdown tables or
dropping content.
"""
import sys
import unittest
from pathlib import Path

from scripts.gate4_applier import (  # noqa: E402
    MIN_PRESERVATION_RATIO,
    _extract_tables, _merge_tables, _strip_tables, _table_to_markdown,
    filter_proposals, is_safe_update, merge_section_update,
)
from scripts.gate4_proposer import Proposal  # noqa: E402


class TestExtractTables(unittest.TestCase):
    def test_no_table(self):
        self.assertEqual(_extract_tables("just text\nmore text"), [])

    def test_single_table(self):
        md = """| col1 | col2 |
|---|---|
| a | b |
| c | d |"""
        tables = _extract_tables(md)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0], [["col1", "col2"], ["a", "b"], ["c", "d"]])

    def test_two_tables_with_prose(self):
        md = """First table:

| k | v |
|---|---|
| a | 1 |

Some prose.

| x | y |
|---|---|
| p | q |
"""
        tables = _extract_tables(md)
        self.assertEqual(len(tables), 2)

    def test_single_row_not_a_table(self):
        # Only header, no data rows → not treated as table
        self.assertEqual(_extract_tables("| col1 | col2 |\n|---|---|"), [])


class TestMergeTables(unittest.TestCase):
    def test_preserves_old_rows_not_in_new(self):
        old = [["item", "value"], ["cpu", "A18"], ["ram", "8GB"], ["gpu", "5-core"]]
        new = [["item", "value"], ["cpu", "A19"]]
        merged = _merge_tables(old, new)
        self.assertEqual(merged[0], ["item", "value"])
        # All 3 old rows preserved
        self.assertEqual(len(merged), 4)
        keys = [r[0] for r in merged[1:]]
        self.assertIn("cpu", keys)
        self.assertIn("ram", keys)
        self.assertIn("gpu", keys)

    def test_new_row_values_override(self):
        old = [["item", "value"], ["cpu", "A18"]]
        new = [["item", "value"], ["cpu", "A19 Pro"]]
        merged = _merge_tables(old, new)
        cpu_row = next(r for r in merged[1:] if r[0] == "cpu")
        self.assertEqual(cpu_row[1], "A19 Pro")

    def test_new_rows_appended(self):
        old = [["k", "v"], ["a", "1"]]
        new = [["k", "v"], ["a", "2"], ["b", "new"]]
        merged = _merge_tables(old, new)
        self.assertEqual(len(merged), 3)  # header + a + b
        keys = [r[0] for r in merged[1:]]
        self.assertEqual(keys, ["a", "b"])  # a stays first, b appended

    def test_empty_old_returns_new(self):
        self.assertEqual(_merge_tables([], [["h"], ["a"]]), [["h"], ["a"]])


class TestTableRoundtrip(unittest.TestCase):
    def test_roundtrip_preserves_structure(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        tables = _extract_tables(md)
        rendered = _table_to_markdown(tables[0])
        tables2 = _extract_tables(rendered)
        self.assertEqual(tables, tables2)

    def test_pads_short_rows(self):
        table = [["a", "b", "c"], ["1"]]
        rendered = _table_to_markdown(table)
        # Short row "1" should be padded to 3 cells
        self.assertIn("| 1 |  |  |", rendered)


class TestStripTables(unittest.TestCase):
    def test_removes_tables_keeps_prose(self):
        md = """Before.

| a | b |
|---|---|
| 1 | 2 |

After."""
        stripped = _strip_tables(md)
        self.assertNotIn("|", stripped)
        self.assertIn("Before", stripped)
        self.assertIn("After", stripped)


class TestMergeSectionUpdate(unittest.TestCase):
    def test_no_table_in_old_uses_new(self):
        old = "Plain prose here."
        new = "New prose."
        self.assertEqual(merge_section_update(old, new), new)

    def test_old_table_preserved_when_new_has_no_table(self):
        old = """| spec | val |
|---|---|
| cpu | A18 |
| ram | 8GB |"""
        new = "Updated description without a table."
        merged = merge_section_update(old, new)
        self.assertIn("cpu", merged)
        self.assertIn("ram", merged)  # old rows preserved
        self.assertIn("Updated description", merged)

    def test_merge_preserves_all_old_rows_plus_new_ones(self):
        old = """| spec | val |
|---|---|
| cpu | A18 Pro |
| ram | 8GB |
| gpu | 5-core |
| storage | 256GB |"""
        new = """| spec | val |
|---|---|
| cpu | A19 Pro |
| npu | 16-core |"""
        merged = merge_section_update(old, new)
        # All 4 old rows + 1 new row (npu) = 5 data rows
        self.assertIn("ram", merged)     # old preserved
        self.assertIn("gpu", merged)     # old preserved
        self.assertIn("storage", merged)  # old preserved
        self.assertIn("A19 Pro", merged)  # new value wins
        self.assertIn("npu", merged)     # new row added

    def test_flattening_regression_is_prevented(self):
        """The exact scenario that broke mac-mini.md — LLM flattens table."""
        old = """| 項目 | M4 | M4 Pro |
|---|---|---|
| CPU | 10 核心 | 最多 14 核心 |
| GPU | 10 核心 | 最多 20 核心 |
| 記憶體 | 24GB | 48GB |

| 項目（共通） | 規格 |
|---|---|
| 重量 | 0.67kg |
| 連接埠 | 8 個 |"""
        # LLM returns only first table, shortened
        new = """| 項目 | M4 | M4 Pro |
|---|---|---|
| CPU | 10 核心 | 最多 14 核心 |"""
        merged = merge_section_update(old, new)
        # Common-specs table (second one) must be preserved even though LLM didn't provide it
        self.assertIn("0.67kg", merged, "weight row lost — table 2 was dropped!")
        self.assertIn("連接埠", merged, "ports row lost!")
        self.assertIn("GPU", merged)
        self.assertIn("記憶體", merged)


class TestIsSafeUpdate(unittest.TestCase):
    def test_trivially_short_new_rejected(self):
        self.assertFalse(is_safe_update("a" * 100, "a" * 10))  # 10% of original

    def test_sufficiently_long_new_accepted(self):
        self.assertTrue(is_safe_update("a" * 100, "a" * 80))  # 80%

    def test_empty_old_always_safe(self):
        self.assertTrue(is_safe_update("", "new content"))

    def test_boundary_at_ratio(self):
        old = "a" * 100
        # exactly at threshold
        threshold_len = int(MIN_PRESERVATION_RATIO * 100)
        self.assertTrue(is_safe_update(old, "a" * threshold_len))


class TestFilterProposalsWithMerge(unittest.TestCase):
    """Integration: filter_proposals now uses merge + safety."""

    def _proposal(self, new_content, current="More details here", section="核心規格"):
        return Proposal(section=section, action="update",
                        current_excerpt=current, new_content=new_content,
                        reason="r")

    def test_update_preserves_table_via_merge(self):
        section_content = """| item | value |
|---|---|
| cpu | A18 Pro |
| ram | 8GB |
| fact | kept |

More details here."""
        # LLM returns just 1 row update
        llm_new = """| item | value |
|---|---|
| cpu | A19 Pro |"""
        proposals = [self._proposal(new_content=llm_new, current="A18 Pro")]
        result = filter_proposals(
            proposals, frontmatter={}, existing_sections={"核心規格": section_content}
        )
        self.assertEqual(len(result.apply), 1)
        merged_content = result.apply[0].new_content
        # All original rows should be preserved
        self.assertIn("ram", merged_content)
        self.assertIn("fact", merged_content)
        self.assertIn("A19 Pro", merged_content)
        self.assertIn("8GB", merged_content)

    def test_update_too_destructive_goes_to_review(self):
        """Long old section + tiny new → safety check routes to review."""
        old = "Lots of detailed content. " * 20  # ~500 chars
        proposals = [self._proposal(new_content="Short update.",
                                     current="Lots of detailed content")]
        result = filter_proposals(
            proposals, frontmatter={}, existing_sections={"核心規格": old}
        )
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.review), 1)
        self.assertIn("drop too much detail", result.review[0][1])


if __name__ == "__main__":
    unittest.main()
