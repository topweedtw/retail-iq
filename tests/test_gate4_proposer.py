"""Tests for scripts/gate4_proposer.py — Gate 4 Phase 2.

LLM call itself is not unit-tested (live integration goes in Phase 3);
these tests cover parsing, page splitting, validation, prompt building.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from scripts.gate4_proposer import (  # noqa: E402
    Proposal, ProposalSet, _parse_response, build_prompt, extract_sections,
    propose, split_frontmatter,
)
from scripts.llm_client import LLMError  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# Page parsing
# ─────────────────────────────────────────────────────────────────────

class TestSplitFrontmatter(unittest.TestCase):
    def test_with_frontmatter(self):
        md = "---\ntitle: Foo\ntags: [a, b]\n---\n\n# Body\n"
        fm, body = split_frontmatter(md)
        self.assertEqual(fm["title"], "Foo")
        self.assertEqual(fm["tags"], ["a", "b"])
        self.assertIn("# Body", body)

    def test_without_frontmatter(self):
        md = "# Just body\nContent\n"
        fm, body = split_frontmatter(md)
        self.assertEqual(fm, {})
        self.assertEqual(body, md)


class TestExtractSections(unittest.TestCase):
    def test_single_section(self):
        body = "## 規格\n- 晶片: A19\n- RAM: 8GB\n"
        s = extract_sections(body)
        self.assertIn("規格", s)
        self.assertIn("A19", s["規格"])

    def test_multiple_sections(self):
        body = "## A\nfoo\n\n## B\nbar\n"
        s = extract_sections(body)
        self.assertEqual(set(s.keys()), {"A", "B"})
        self.assertEqual(s["A"], "foo")
        self.assertEqual(s["B"], "bar")

    def test_no_sections(self):
        self.assertEqual(extract_sections("just text no headings"), {})


# ─────────────────────────────────────────────────────────────────────
# Proposal + validation
# ─────────────────────────────────────────────────────────────────────

class TestProposal(unittest.TestCase):
    def _p(self, **kwargs):
        defaults = dict(
            section="X", action="update", current_excerpt="old",
            new_content="new", reason="because",
        )
        defaults.update(kwargs)
        return Proposal(**defaults)

    def test_valid(self):
        self.assertEqual(self._p().validate(), [])

    def test_invalid_action(self):
        errs = self._p(action="delete").validate()
        self.assertTrue(any("invalid action" in e for e in errs))

    def test_empty_section(self):
        self.assertTrue(self._p(section="").validate())

    def test_empty_content(self):
        self.assertTrue(self._p(new_content="").validate())

    def test_reason_too_long(self):
        errs = self._p(reason="x" * 200).validate()
        self.assertTrue(any("too long" in e for e in errs))


# ─────────────────────────────────────────────────────────────────────
# Response parsing
# ─────────────────────────────────────────────────────────────────────

class TestParseResponse(unittest.TestCase):
    def test_valid_json(self):
        raw = json.dumps({
            "target_valid": True,
            "target_valid_reason": "match",
            "proposals": [{
                "section": "Specs", "action": "update",
                "current_excerpt": "old", "new_content": "new", "reason": "fact",
            }],
        })
        ps = _parse_response(raw)
        self.assertTrue(ps.target_valid)
        self.assertEqual(len(ps.proposals), 1)
        self.assertEqual(ps.proposals[0].action, "update")

    def test_strips_markdown_fence(self):
        inner = json.dumps({"target_valid": False, "target_valid_reason": "no", "proposals": []})
        raw = f"```json\n{inner}\n```"
        ps = _parse_response(raw)
        self.assertFalse(ps.target_valid)

    def test_invalid_json_raises(self):
        with self.assertRaises(LLMError):
            _parse_response("not json at all")

    def test_missing_fields_tolerated(self):
        raw = json.dumps({"target_valid": True})  # no proposals, no reason
        ps = _parse_response(raw)
        self.assertEqual(ps.proposals, [])
        self.assertEqual(ps.target_valid_reason, "")


# ─────────────────────────────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────────────────────────────

class TestBuildPrompt(unittest.TestCase):
    def test_includes_all_key_fields(self):
        p = build_prompt(
            article_title="T",
            article_source="s",
            tier="T1",
            score=10,
            entities=["e1"],
            article_text="body",
            slug="iphone-17-pro",
            frontmatter={"ingest_managed_sections": ["A"], "human_owned_sections": ["B"]},
            sections={"A": "aaa", "B": "bbb"},
        )
        self.assertIn("T", p)
        self.assertIn("iphone-17-pro", p)
        self.assertIn("['A']", p)
        self.assertIn("['B']", p)
        self.assertIn("aaa", p)

    def test_truncates_long_text(self):
        long = "x" * 5000
        p = build_prompt(
            article_title="T", article_source="s", tier="T1", score=10,
            entities=[], article_text=long, slug="x",
            frontmatter={}, sections={}, max_article_chars=100,
        )
        self.assertIn("[...TRUNCATED...]", p)
        # first 100 chars only
        x_count = p.count("x")
        self.assertLess(x_count, 200)


# ─────────────────────────────────────────────────────────────────────
# propose() with mocked LLM
# ─────────────────────────────────────────────────────────────────────

class TestProposeWithMock(unittest.TestCase):
    def test_reject_path(self):
        client = MagicMock()
        client.chat.return_value = json.dumps({
            "target_valid": False,
            "target_valid_reason": "irrelevant",
            "proposals": [],
        })
        result = propose(
            article_meta={"source_title": "Pride", "source_type": "apple-newsroom-en",
                          "source_tier": "T2", "relevance_score": 6, "key_entities": ["Apple Watch"]},
            article_text="text",
            product_page_md="---\ntitle: X\n---\n## S\n",
            product_slug="iphone-17-pro",
            client=client,
        )
        self.assertFalse(result.target_valid)
        self.assertEqual(result.proposals, [])

    def test_happy_path(self):
        client = MagicMock()
        client.chat.return_value = json.dumps({
            "target_valid": True,
            "target_valid_reason": "match",
            "proposals": [
                {"section": "Specs", "action": "update",
                 "current_excerpt": "A18", "new_content": "A19", "reason": "fact"},
            ],
        })
        result = propose(
            article_meta={"source_title": "T", "source_type": "apple-com-tw",
                          "source_tier": "T1", "relevance_score": 10, "key_entities": ["iPhone"]},
            article_text="text",
            product_page_md="---\ntitle: X\n---\n## Specs\nA18\n",
            product_slug="iphone-17-pro",
            client=client,
        )
        self.assertTrue(result.target_valid)
        self.assertEqual(len(result.proposals), 1)
        self.assertEqual(result.proposals[0].section, "Specs")


class TestProposalSetSerialization(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        ps = ProposalSet(
            target_valid=True, target_valid_reason="ok",
            proposals=[Proposal("S", "update", "old", "new", "r")],
        )
        d = ps.to_dict()
        self.assertEqual(d["target_valid"], True)
        self.assertEqual(d["proposals"][0]["section"], "S")
        # ensure it's JSON-serializable
        json.dumps(d, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
