"""Tests for scripts/gate4_router.py — Gate 4 Phase 1 routing."""
import math
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.gate4_router import (  # noqa: E402
    Product, compute_idf, entity_matches_tag, load_products,
    normalize_token, route,
)


# ─────────────────────────────────────────────────────────────────────
# normalize_token
# ─────────────────────────────────────────────────────────────────────
class TestNormalize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(normalize_token("iPhone 17"), "iphone-17")
        self.assertEqual(normalize_token("Apple Intelligence"), "apple-intelligence")
        self.assertEqual(normalize_token("iOS 26"), "ios-26")

    def test_strips_stop_suffix(self):
        self.assertEqual(normalize_token("A19 晶片"), "a19")
        self.assertEqual(normalize_token("ProMotion 技術"), "promotion")

    def test_preserves_cjk(self):
        self.assertEqual(normalize_token("蘋果"), "蘋果")

    def test_empty(self):
        self.assertEqual(normalize_token(""), "")
        self.assertEqual(normalize_token("   "), "")


# ─────────────────────────────────────────────────────────────────────
# entity_matches_tag
# ─────────────────────────────────────────────────────────────────────
class TestMatching(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(entity_matches_tag("iphone", "iphone"))

    def test_tag_is_entity_token(self):
        # "iPhone 17" normalized = "iphone-17"; tag "iphone" is a token in it
        self.assertTrue(entity_matches_tag("iphone-17", "iphone"))

    def test_entity_is_tag_token(self):
        # "iOS" → "ios"; tag "ios-26" has token "ios"
        self.assertTrue(entity_matches_tag("ios", "ios-26"))

    def test_no_cross_pollution(self):
        self.assertFalse(entity_matches_tag("iphone", "ipad"))
        self.assertFalse(entity_matches_tag("mac", "ios-26"))

    def test_empty_safe(self):
        self.assertFalse(entity_matches_tag("", "iphone"))
        self.assertFalse(entity_matches_tag("iphone", ""))


# ─────────────────────────────────────────────────────────────────────
# IDF
# ─────────────────────────────────────────────────────────────────────
class TestIDF(unittest.TestCase):
    def test_universal_tag_zero(self):
        products = [
            Product("a", Path("/a"), ["x", "shared"], "A"),
            Product("b", Path("/b"), ["y", "shared"], "B"),
            Product("c", Path("/c"), ["z", "shared"], "C"),
        ]
        idf = compute_idf(products)
        self.assertAlmostEqual(idf["shared"], 0.0)

    def test_unique_tag_log_n(self):
        products = [
            Product("a", Path("/a"), ["x"], "A"),
            Product("b", Path("/b"), ["y"], "B"),
            Product("c", Path("/c"), ["z"], "C"),
        ]
        idf = compute_idf(products)
        for t in "xyz":
            self.assertAlmostEqual(idf[t], math.log(3))

    def test_empty_corpus(self):
        self.assertEqual(compute_idf([]), {})


# ─────────────────────────────────────────────────────────────────────
# Routing
# ─────────────────────────────────────────────────────────────────────
class TestRoute(unittest.TestCase):
    def setUp(self):
        self.products = [
            Product("iphone-17-pro", Path("/p1"),
                    ["iphone", "a19-pro", "apple-intelligence", "ios-26"], "iPhone 17 Pro"),
            Product("ipad-air", Path("/p2"),
                    ["ipad", "m3", "apple-intelligence"], "iPad Air"),
            Product("macbook-neo", Path("/p3"),
                    ["mac", "macbook-neo", "a18-pro", "apple-intelligence"], "MacBook Neo"),
        ]

    def test_strong_match(self):
        matches = route(["iPhone 17", "A19", "iOS 26"], self.products, threshold=1.0)
        self.assertEqual(matches[0].product.slug, "iphone-17-pro")
        self.assertGreater(matches[0].score, 2.0)

    def test_generic_tag_suppressed(self):
        # Only Apple Intelligence — appears in all 3 → idf=0 → no match above threshold
        matches = route(["Apple Intelligence"], self.products, threshold=0.5)
        self.assertEqual(matches, [])

    def test_multi_product_fanout(self):
        matches = route(["iPhone", "iPad", "Mac"], self.products, threshold=1.0)
        self.assertEqual(len(matches), 3)  # all three hit

    def test_orphan_returns_empty(self):
        matches = route(["AirPods", "HomeKit"], self.products, threshold=1.0)
        self.assertEqual(matches, [])

    def test_threshold_filters(self):
        # Only generic Apple Intelligence → score=0, not returned even at threshold=0.5
        matches = route(["Apple Intelligence"], self.products, threshold=0.5)
        self.assertEqual(matches, [])

    def test_ordering_by_score(self):
        # iphone+ios-26 hits iphone-17-pro (2 unique); iphone alone hits iphone-17-pro (1)
        matches = route(["iPhone", "iOS 26", "iPad"], self.products, threshold=1.0)
        self.assertEqual(matches[0].product.slug, "iphone-17-pro")
        self.assertEqual(matches[1].product.slug, "ipad-air")

    def test_one_entity_counted_once_per_product(self):
        # "iPhone 17" should count once against iphone-17-pro, not twice (iphone + apple-intelligence)
        matches = route(["iPhone 17"], self.products, threshold=0.5)
        self.assertEqual(matches[0].hits, 1)

    def test_zero_idf_matches_recorded_but_not_scored(self):
        matches = route(["iPhone", "Apple Intelligence"], self.products, threshold=1.0)
        # Match on iphone (idf≈1.1) + apple-intelligence (idf=0) → score ≈ 1.1
        iphone_match = next(m for m in matches if m.product.slug == "iphone-17-pro")
        self.assertAlmostEqual(iphone_match.score, math.log(3), places=2)
        # Both pairs appear in matched_pairs
        self.assertEqual(len(iphone_match.matched_pairs), 2)


# ─────────────────────────────────────────────────────────────────────
# load_products
# ─────────────────────────────────────────────────────────────────────
class TestLoadProducts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, frontmatter: str, body: str = "# Body"):
        (self.dir / name).write_text(f"---\n{frontmatter}\n---\n\n{body}\n")

    def test_loads_active(self):
        self._write("iphone.md", "slug: iphone\ntitle: iPhone\nstatus: active\ntags: [iphone, a19]")
        products = load_products(self.dir)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].slug, "iphone")
        self.assertEqual(products[0].tags, ["iphone", "a19"])

    def test_skips_archived(self):
        self._write("old.md", "slug: old\ntitle: Old\nstatus: archived\ntags: [x]")
        self._write("new.md", "slug: new\ntitle: New\nstatus: active\ntags: [y]")
        products = load_products(self.dir)
        self.assertEqual([p.slug for p in products], ["new"])

    def test_skips_no_frontmatter(self):
        (self.dir / "bare.md").write_text("# Just markdown\n")
        products = load_products(self.dir)
        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
