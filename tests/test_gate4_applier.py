"""Tests for scripts/gate4_applier.py — Gate 4 Phase 3."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.gate4_applier import (  # noqa: E402
    DEFAULT_HUMAN_OWNED_SECTIONS, DEFAULT_MANAGED_SECTIONS,
    _append_new_section, _append_to_section, _excerpt_matches, _replace_section,
    apply_proposals_to_body, apply_to_page, classify_section, filter_proposals,
    serialize_frontmatter, update_frontmatter, write_product_page,
)
from scripts.gate4_proposer import Proposal, ProposalSet  # noqa: E402


def P(section, action, current=None, new="updated", reason="r"):
    return Proposal(section=section, action=action, current_excerpt=current,
                    new_content=new, reason=reason)


# ─────────────────────────────────────────────────────────────────────
# classify_section
# ─────────────────────────────────────────────────────────────────────
class TestClassify(unittest.TestCase):
    def test_default_managed(self):
        k = classify_section("一句話定位",
                             frontmatter_managed=[], frontmatter_human=[],
                             existing_sections={"一句話定位"})
        self.assertEqual(k, "managed")

    def test_default_human_owned(self):
        k = classify_section("五大賣點",
                             frontmatter_managed=[], frontmatter_human=[],
                             existing_sections={"五大賣點"})
        self.assertEqual(k, "human")

    def test_frontmatter_overrides(self):
        # section marked human in frontmatter wins even if not in defaults
        k = classify_section("Custom",
                             frontmatter_managed=[], frontmatter_human=["Custom"],
                             existing_sections={"Custom"})
        self.assertEqual(k, "human")

    def test_new_section(self):
        k = classify_section("Brand New",
                             frontmatter_managed=[], frontmatter_human=[],
                             existing_sections=set())
        self.assertEqual(k, "new")


# ─────────────────────────────────────────────────────────────────────
# filter_proposals
# ─────────────────────────────────────────────────────────────────────
class TestFilterProposals(unittest.TestCase):
    def test_human_owned_goes_to_review(self):
        fm = {"human_owned_sections": ["五大賣點（Selling Points）"]}
        proposals = [P("五大賣點（Selling Points）", "append")]
        result = filter_proposals(proposals, frontmatter=fm,
                                  existing_sections={"五大賣點（Selling Points）": "X"})
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.review), 1)
        self.assertIn("human-owned", result.review[0][1])

    def test_managed_update_applied_when_excerpt_matches(self):
        fm = {"ingest_managed_sections": ["核心規格"]}
        # v0.6: new_content must preserve >=60% of old's length (safety check)
        proposals = [P("核心規格", "update", current="A18 Pro chip",
                       new="A19 Pro chip with 12GB RAM and improved NPU")]
        sections = {"核心規格": "Current: A18 Pro chip with 8GB RAM"}
        result = filter_proposals(proposals, frontmatter=fm, existing_sections=sections)
        self.assertEqual(len(result.apply), 1)
        self.assertEqual(result.review, [])

    def test_managed_update_rejected_on_hallucination(self):
        fm = {"ingest_managed_sections": ["核心規格"]}
        proposals = [P("核心規格", "update", current="A20 Max Pro chip")]  # doesn't exist
        sections = {"核心規格": "Current: A18 Pro chip"}
        result = filter_proposals(proposals, frontmatter=fm, existing_sections=sections)
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("hallucination guard", result.rejected[0][1])

    def test_new_section_goes_to_review(self):
        proposals = [P("AI 功能", "append")]
        result = filter_proposals(proposals, frontmatter={}, existing_sections={})
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.review), 1)
        self.assertIn("new section", result.review[0][1])

    def test_suggest_action_always_review(self):
        proposals = [P("一句話定位", "suggest", new="...")]
        result = filter_proposals(proposals, frontmatter={},
                                  existing_sections={"一句話定位": "old"})
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.review), 1)

    def test_invalid_proposal_rejected(self):
        proposals = [P("一句話定位", "delete", new="x")]  # bad action
        result = filter_proposals(proposals, frontmatter={},
                                  existing_sections={"一句話定位": "x"})
        self.assertEqual(result.apply, [])
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("validation", result.rejected[0][1])

    def test_append_on_managed_applied(self):
        proposals = [P("相關頁面", "append", new="- link\n")]
        result = filter_proposals(proposals, frontmatter={},
                                  existing_sections={"相關頁面": "existing"})
        self.assertEqual(len(result.apply), 1)


# ─────────────────────────────────────────────────────────────────────
# _excerpt_matches
# ─────────────────────────────────────────────────────────────────────
class TestExcerptMatch(unittest.TestCase):
    def test_substring(self):
        self.assertTrue(_excerpt_matches("A19 chip", "The A19 chip is fast"))

    def test_whitespace_normalized(self):
        self.assertTrue(_excerpt_matches("A19    chip", "The A19 chip is fast"))

    def test_mismatch(self):
        self.assertFalse(_excerpt_matches("A20 chip", "The A19 chip is fast"))

    def test_none_excerpt(self):
        self.assertFalse(_excerpt_matches(None, "content"))
        self.assertFalse(_excerpt_matches("", "content"))


# ─────────────────────────────────────────────────────────────────────
# Page rewriting primitives
# ─────────────────────────────────────────────────────────────────────
class TestPageRewrite(unittest.TestCase):
    def test_replace_section_keeps_header(self):
        body = "## Intro\nfoo\n\n## Specs\nA18 Pro\nthermal: water\n\n## Next\nbar\n"
        new = _replace_section(body, "Specs", "A19 Pro chip")
        self.assertIn("## Specs", new)
        self.assertIn("A19 Pro chip", new)
        self.assertNotIn("A18 Pro", new)
        self.assertNotIn("thermal", new)
        self.assertIn("## Next", new)  # other section preserved
        self.assertIn("bar", new)

    def test_replace_nonexistent_appends(self):
        body = "## Intro\nfoo\n"
        new = _replace_section(body, "Specs", "A19")
        self.assertIn("## Specs", new)
        self.assertIn("A19", new)

    def test_append_to_section_preserves_existing(self):
        body = "## Refs\nold-link\n\n## Next\nbar\n"
        new = _append_to_section(body, "Refs", "- new-link")
        self.assertIn("old-link", new)
        self.assertIn("new-link", new)
        self.assertIn("## Next", new)
        self.assertIn("bar", new)

    def test_apply_proposals_multiple(self):
        body = "## A\nold\n\n## B\nfixed\n"
        proposals = [
            P("A", "update", current="old", new="new-a"),
            P("B", "append", new="added-b"),
        ]
        new_body, applied = apply_proposals_to_body(body, proposals)
        self.assertIn("new-a", new_body)
        self.assertIn("fixed", new_body)
        self.assertIn("added-b", new_body)
        self.assertEqual(set(applied), {"A", "B"})


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────
class TestFrontmatter(unittest.TestCase):
    def test_update_increments_source_count(self):
        fm = {"source_count": 3, "title": "Foo"}
        new_fm = update_frontmatter(
            fm,
            article_meta_path=Path("/tmp/fake.meta.json"),
            applied_sections=["A"],
        )
        self.assertEqual(new_fm["source_count"], 4)
        self.assertIn("last_updated", new_fm)
        self.assertEqual(len(new_fm["ingest_history"]), 1)
        self.assertEqual(new_fm["ingest_history"][0]["sections"], ["A"])

    def test_serialize_roundtrip_like(self):
        fm = {
            "title": "iPhone 17 Pro",
            "source_count": 2,
            "tags": ["iphone", "a19-pro"],
            "ingest_managed_sections": ["一句話定位"],
            "human_owned_sections": [],
        }
        s = serialize_frontmatter(fm)
        self.assertIn("title: iPhone 17 Pro", s)
        self.assertIn("source_count: 2", s)
        self.assertIn("[iphone, a19-pro]", s)
        self.assertIn("human_owned_sections: []", s)


# ─────────────────────────────────────────────────────────────────────
# End-to-end apply_to_page
# ─────────────────────────────────────────────────────────────────────
class TestApplyEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.product = self.dir / "iphone-17-pro.md"
        self.product.write_text("""---
type: product
title: iPhone 17 Pro
slug: iphone-17-pro
status: active
last_updated: 2026-04-30
source_count: 1
tags: [iphone, a19-pro]
ingest_managed_sections: [一句話定位, 核心規格]
human_owned_sections: [五大賣點（Selling Points）]
---

## 一句話定位

Old positioning text.

## 核心規格

A18 Pro chip with 8GB RAM.

## 五大賣點（Selling Points）

Human-written selling points here.
""")
        self.meta_path = self.dir / "article.meta.json"
        self.meta_path.write_text(json.dumps({
            "source_title": "iPhone 17",
            "source_type": "apple-com-tw",
            "source_tier": "T1",
            "relevance_score": 10,
            "key_entities": ["iPhone 17"],
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def test_happy_path_writes_file(self):
        ps = ProposalSet(
            target_valid=True, target_valid_reason="match",
            proposals=[P("一句話定位", "update", current="Old positioning",
                         new="New positioning for A19")],
        )
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path, dry_run=False)
        self.assertEqual(result.applied_sections, ["一句話定位"])
        content = self.product.read_text()
        self.assertIn("New positioning for A19", content)
        self.assertNotIn("Old positioning text", content)
        # frontmatter updated
        self.assertIn("source_count: 2", content)
        # meta.json updated
        meta = json.loads(self.meta_path.read_text())
        self.assertIsNotNone(meta.get("ingest_log_ref"))
        self.assertEqual(meta["ingest_targets"], ["iphone-17-pro"])

    def test_dry_run_does_not_write(self):
        ps = ProposalSet(
            target_valid=True, target_valid_reason="m",
            proposals=[P("一句話定位", "update", current="Old positioning",
                         new="A new positioning statement for the updated product.")],
        )
        before = self.product.read_text()
        before_meta = self.meta_path.read_text()
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path, dry_run=True)
        self.assertEqual(result.applied_sections, ["一句話定位"])  # would apply
        self.assertEqual(self.product.read_text(), before)
        self.assertEqual(self.meta_path.read_text(), before_meta)

    def test_idempotent_skips_if_already_applied(self):
        meta = json.loads(self.meta_path.read_text())
        meta["ingest_log_ref"] = "2026-05-07T11:30:00+08:00|iphone-17-pro"
        self.meta_path.write_text(json.dumps(meta))
        ps = ProposalSet(target_valid=True, target_valid_reason="m",
                         proposals=[P("一句話定位", "update", current="x", new="y")])
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path)
        self.assertIsNotNone(result.skipped_reason)
        self.assertIn("already-applied", result.skipped_reason)

    def test_target_invalid_skips(self):
        ps = ProposalSet(target_valid=False, target_valid_reason="wrong",
                         proposals=[])
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path)
        self.assertIn("target_valid=false", result.skipped_reason)

    def test_human_owned_goes_to_review_not_file(self):
        ps = ProposalSet(
            target_valid=True, target_valid_reason="m",
            proposals=[P("五大賣點（Selling Points）", "append", new="new selling point")],
        )
        before = self.product.read_text()
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path, dry_run=False)
        self.assertEqual(result.applied_sections, [])
        self.assertEqual(len(result.reviewed_proposals), 1)
        # file NOT modified
        self.assertEqual(self.product.read_text(), before)
        # meta NOT flagged as applied (nothing was)
        meta = json.loads(self.meta_path.read_text())
        self.assertIsNone(meta.get("ingest_log_ref"))

    def test_hallucinated_update_rejected_not_written(self):
        ps = ProposalSet(
            target_valid=True, target_valid_reason="m",
            proposals=[P("核心規格", "update", current="A20 Pro (wrong!)",
                                     new="A longer replacement that would normally pass length check")],
        )
        before = self.product.read_text()
        result = apply_to_page(proposal_set=ps, product_path=self.product,
                               article_meta_path=self.meta_path, dry_run=False)
        self.assertEqual(result.applied_sections, [])
        self.assertEqual(len(result.rejected_proposals), 1)
        self.assertEqual(self.product.read_text(), before)


if __name__ == "__main__":
    unittest.main()
