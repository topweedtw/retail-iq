"""Tests for scripts/embedding_index.py + Gate 1b integration in ingest_agent."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from embedding_index import EmbeddingIndex, cosine_similarity, INDEX_VERSION  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# cosine_similarity
# ─────────────────────────────────────────────────────────────────────
class TestCosineSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [-1, -2, -3]), -1.0)

    def test_near_duplicate(self):
        sim = cosine_similarity([1.0, 2.0, 3.0], [1.01, 2.01, 3.01])
        self.assertGreater(sim, 0.99)

    def test_empty_returns_zero(self):
        self.assertEqual(cosine_similarity([], [1, 2]), 0.0)
        self.assertEqual(cosine_similarity([1, 2], []), 0.0)

    def test_zero_vector_returns_zero(self):
        self.assertEqual(cosine_similarity([0, 0, 0], [1, 2, 3]), 0.0)

    def test_mismatched_length(self):
        self.assertEqual(cosine_similarity([1, 2], [1, 2, 3]), 0.0)


# ─────────────────────────────────────────────────────────────────────
# EmbeddingIndex
# ─────────────────────────────────────────────────────────────────────
class TestEmbeddingIndex(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "index.json"
        self.client = MagicMock()
        self.client.embedding_model = "test-model:latest"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_empty_index(self):
        idx = EmbeddingIndex(self.path, client=self.client)
        self.assertEqual(len(idx), 0)
        self.assertFalse(idx.has("sha256:abc"))
        self.assertIsNone(idx.get("sha256:abc"))

    def test_add_and_persist(self):
        idx = EmbeddingIndex(self.path, client=self.client)
        idx.add("sha256:abc", "src1", "name_20260101", [0.1, 0.2, 0.3])
        idx.save()
        self.assertTrue(self.path.exists())

        # Reload from disk
        idx2 = EmbeddingIndex(self.path, client=self.client)
        self.assertEqual(len(idx2), 1)
        self.assertTrue(idx2.has("sha256:abc"))
        self.assertEqual(idx2.get("sha256:abc"), [0.1, 0.2, 0.3])

    def test_save_noop_when_clean(self):
        idx = EmbeddingIndex(self.path, client=self.client)
        idx.save()  # nothing dirty → file should not be created
        self.assertFalse(self.path.exists())

    def test_find_near_duplicate_same_source(self):
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:a", "src1", "article_a", [1.0, 2.0, 3.0])
        idx.add("sha256:b", "src2", "article_b", [1.0, 2.0, 3.0])  # diff source

        # Near-identical to "a" but different hash
        dup = idx.find_near_duplicate([1.01, 2.02, 3.01], "src1")
        self.assertIsNotNone(dup)
        self.assertEqual(dup[0], "article_a")
        self.assertGreater(dup[1], 0.999)

    def test_find_near_duplicate_no_cross_source(self):
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:a", "src1", "article_a", [1.0, 2.0, 3.0])
        # Identical vector but different source → should NOT match
        dup = idx.find_near_duplicate([1.0, 2.0, 3.0], "src2")
        self.assertIsNone(dup)

    def test_find_near_duplicate_below_threshold(self):
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:a", "src1", "article_a", [1.0, 0.0, 0.0])
        # Orthogonal — sim = 0
        self.assertIsNone(idx.find_near_duplicate([0.0, 1.0, 0.0], "src1"))

    def test_find_near_duplicate_returns_best(self):
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:a", "src1", "moderate", [1.0, 0.5, 0.0])
        idx.add("sha256:b", "src1", "best_match", [1.0, 0.01, 0.0])
        # Query close to "best_match"
        dup = idx.find_near_duplicate([1.0, 0.0, 0.0], "src1")
        self.assertEqual(dup[0], "best_match")

    def test_check_and_stage_with_dup(self):
        self.client.embed.return_value = [[1.0, 0.0, 0.0]]
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:existing", "src1", "existing_article", [1.0, 0.0, 0.0])

        vec, dup = idx.check_and_stage("sha256:new", "src1", "new_basename", "some text")
        self.assertEqual(vec, [1.0, 0.0, 0.0])
        self.assertIsNotNone(dup)
        self.assertEqual(dup[0], "existing_article")

    def test_check_and_stage_no_dup(self):
        self.client.embed.return_value = [[0.0, 1.0, 0.0]]
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        idx.add("sha256:existing", "src1", "existing", [1.0, 0.0, 0.0])

        vec, dup = idx.check_and_stage("sha256:new", "src1", "new", "different text")
        self.assertEqual(vec, [0.0, 1.0, 0.0])
        self.assertIsNone(dup)

    def test_check_and_stage_handles_embed_failure(self):
        self.client.embed.side_effect = RuntimeError("API down")
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        vec, dup = idx.check_and_stage("sha256:x", "src1", "n", "text")
        self.assertIsNone(vec)
        self.assertIsNone(dup)

    def test_stats(self):
        idx = EmbeddingIndex(self.path, client=self.client)
        idx.add("sha256:1", "srcA", "a1", [0.1])
        idx.add("sha256:2", "srcA", "a2", [0.2])
        idx.add("sha256:3", "srcB", "b1", [0.3])
        stats = idx.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_source"]["srcA"], 2)
        self.assertEqual(stats["by_source"]["srcB"], 1)
        self.assertEqual(stats["model"], "test-model:latest")

    def test_corrupted_file_recovers(self):
        self.path.write_text("not json{{")
        idx = EmbeddingIndex(self.path, client=self.client)
        # Should not raise; starts fresh
        self.assertEqual(len(idx), 0)


# ─────────────────────────────────────────────────────────────────────
# Real LLM client (mock=True) integration
# ─────────────────────────────────────────────────────────────────────
class TestWithRealClientMock(unittest.TestCase):
    """Verify EmbeddingIndex works with the actual LLMClient in mock mode."""

    def setUp(self):
        from llm_client import LLMClient
        self.client = LLMClient(mock=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "idx.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_identical_text_detected_as_duplicate(self):
        """Mock embed is hash-based: identical text → cosine sim = 1.0."""
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        text = "This is some article content about iPhone 17."
        # First article
        vec1 = idx.embed_text(text)
        self.assertIsNotNone(vec1)
        self.assertEqual(len(vec1), 768)
        idx.add("sha256:a", "apple-com-tw", "first", vec1)

        # Same text → mock returns same vector → sim = 1.0
        vec2, dup = idx.check_and_stage("sha256:b", "apple-com-tw", "second", text)
        self.assertIsNotNone(dup)
        self.assertEqual(dup[0], "first")
        self.assertAlmostEqual(dup[1], 1.0)

    def test_different_text_no_duplicate(self):
        idx = EmbeddingIndex(self.path, client=self.client, threshold=0.98)
        vec1 = idx.embed_text("Article about iPhone 17 launch in Taiwan.")
        idx.add("sha256:a", "apple-com-tw", "first", vec1)
        # Totally different text
        _, dup = idx.check_and_stage("sha256:b", "apple-com-tw", "second",
                                     "Mac mini pricing changes detailed here.")
        # Mock embed for different text → very different vec → low sim
        self.assertIsNone(dup)


if __name__ == "__main__":
    unittest.main()
