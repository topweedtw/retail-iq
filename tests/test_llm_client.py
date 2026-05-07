"""
Tests for scripts/llm_client.py

在 CI 會以 APPLE_GENAI_MOCK=1 跑純 mock 測試（無網路）。
有真實 endpoint 時可跑 integration tests（目前 skip）。
"""
import io
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

# 強制開 mock 模式（防止 test 意外打真實 API）
os.environ["APPLE_GENAI_MOCK"] = "1"

from llm_client import LLMClient, LLMError  # noqa: E402


class TestLLMClientDefaults(unittest.TestCase):

    def test_default_endpoint(self):
        c = LLMClient()
        self.assertEqual(c.endpoint, "http://localhost:11211/api/openai/v1")

    def test_default_chat_model(self):
        c = LLMClient()
        self.assertEqual(c.chat_model, "gemini-2.5-flash-lite:latest")

    def test_default_embedding_model(self):
        c = LLMClient()
        self.assertEqual(c.embedding_model, "text-multilingual-embedding-002:latest")

    def test_env_override(self):
        os.environ["APPLE_GENAI_ENDPOINT"] = "http://test.local/v1"
        try:
            c = LLMClient()
            self.assertEqual(c.endpoint, "http://test.local/v1")
        finally:
            del os.environ["APPLE_GENAI_ENDPOINT"]

    def test_explicit_override_beats_env(self):
        os.environ["APPLE_GENAI_ENDPOINT"] = "http://env.local/v1"
        try:
            c = LLMClient(endpoint="http://arg.local/v1")
            self.assertEqual(c.endpoint, "http://arg.local/v1")
        finally:
            del os.environ["APPLE_GENAI_ENDPOINT"]


class TestMockChat(unittest.TestCase):
    """Mock mode 應該不打網路，回合理 stub。"""

    def test_generic_chat(self):
        c = LLMClient(mock=True)
        out = c.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "[mock] ok")

    def test_rubric_chat_returns_json(self):
        c = LLMClient(mock=True)
        out = c.chat([
            {"role": "user", "content": "依 rubric 打分，回 JSON 含 total"}
        ])
        parsed = json.loads(out)
        self.assertIn("total", parsed)
        self.assertIn("d1_product_mention", parsed)
        self.assertEqual(parsed["total"],
                         sum(parsed[k] for k in
                             ("d1_product_mention", "d2_ecosystem",
                              "d3_training_potential", "d4_timeliness")))


class TestMockEmbed(unittest.TestCase):

    def test_dim(self):
        c = LLMClient(mock=True)
        vecs = c.embed(["hello"])
        self.assertEqual(len(vecs), 1)
        self.assertEqual(len(vecs[0]), 768)

    def test_determinism(self):
        """相同文字 → 相同 vector（hash-based mock）"""
        c = LLMClient(mock=True)
        a = c.embed(["apple"])[0]
        b = c.embed(["apple"])[0]
        self.assertEqual(a, b)

    def test_different_text_different_vec(self):
        c = LLMClient(mock=True)
        a = c.embed(["apple"])[0]
        b = c.embed(["banana"])[0]
        self.assertNotEqual(a, b)

    def test_batch(self):
        c = LLMClient(mock=True)
        vecs = c.embed(["a", "b", "c"])
        self.assertEqual(len(vecs), 3)


class TestJsonExtraction(unittest.TestCase):

    def test_plain_json(self):
        d = LLMClient._extract_json('{"a": 1}')
        self.assertEqual(d, {"a": 1})

    def test_markdown_fence(self):
        d = LLMClient._extract_json('```json\n{"a": 1}\n```')
        self.assertEqual(d, {"a": 1})

    def test_plain_markdown_fence_no_language(self):
        d = LLMClient._extract_json('```\n{"a": 1}\n```')
        self.assertEqual(d, {"a": 1})

    def test_with_surrounding_text(self):
        d = LLMClient._extract_json('Here is the result:\n{"a": 1}\nDone.')
        self.assertEqual(d, {"a": 1})

    def test_no_json_raises(self):
        with self.assertRaises(LLMError):
            LLMClient._extract_json("just plain text")


class TestChatJson(unittest.TestCase):

    def test_rubric_parsing(self):
        """Mock 的 rubric prompt → chat_json 能解析"""
        c = LLMClient(mock=True)
        d = c.chat_json([
            {"role": "user", "content": "給 rubric 打 total 分數"}
        ])
        self.assertIn("total", d)
        self.assertIsInstance(d["total"], int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
