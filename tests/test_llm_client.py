"""
Tests for scripts/llm_client.py

單元測試不打網路：
  - LLMClient 的設定、env var 優先序、JSON 解析
  - MockLLMClient 的各種注入模式
  - make_client() 工廠函式
"""
import json
import os
import unittest
from pathlib import Path

from scripts.llm_client import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ENDPOINT,
    LLMClient,
    LLMError,
    MockLLMClient,
    make_client,
)


class TestLLMClientDefaults(unittest.TestCase):
    """預設值與環境變數優先序。"""

    def setUp(self):
        # 確保測試前清掉可能殘留的 env var
        for key in ("OPENAI_API_KEY", "OPENAI_ENDPOINT", "OPENAI_CHAT_MODEL",
                    "OPENAI_EMBEDDING_MODEL", "APPLE_GENAI_ENDPOINT",
                    "APPLE_GENAI_CHAT_MODEL"):
            os.environ.pop(key, None)

    def test_default_endpoint(self):
        c = LLMClient()
        self.assertEqual(c.endpoint, "https://api.openai.com/v1")

    def test_default_chat_model(self):
        c = LLMClient()
        self.assertEqual(c.chat_model, DEFAULT_CHAT_MODEL)

    def test_default_embedding_model(self):
        c = LLMClient()
        self.assertEqual(c.embedding_model, DEFAULT_EMBEDDING_MODEL)

    def test_default_api_key_empty(self):
        c = LLMClient()
        self.assertEqual(c.api_key, "")

    def test_openai_env_vars(self):
        os.environ["OPENAI_ENDPOINT"] = "https://custom.openai.com/v1"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_CHAT_MODEL"] = "gpt-4o"
        try:
            c = LLMClient()
            self.assertEqual(c.endpoint, "https://custom.openai.com/v1")
            self.assertEqual(c.api_key, "sk-test")
            self.assertEqual(c.chat_model, "gpt-4o")
        finally:
            for k in ("OPENAI_ENDPOINT", "OPENAI_API_KEY", "OPENAI_CHAT_MODEL"):
                os.environ.pop(k, None)

    def test_explicit_arg_beats_env(self):
        os.environ["OPENAI_ENDPOINT"] = "https://env.openai.com/v1"
        try:
            c = LLMClient(endpoint="https://arg.openai.com/v1")
            self.assertEqual(c.endpoint, "https://arg.openai.com/v1")
        finally:
            os.environ.pop("OPENAI_ENDPOINT", None)

    def test_backward_compat_apple_genai_env(self):
        """舊的 APPLE_GENAI_* 環境變數仍可用（向後相容）。"""
        os.environ["APPLE_GENAI_ENDPOINT"] = "http://localhost:11211/api/openai/v1"
        os.environ["APPLE_GENAI_CHAT_MODEL"] = "gemini-2.5-flash-lite:latest"
        try:
            c = LLMClient()
            self.assertEqual(c.endpoint, "http://localhost:11211/api/openai/v1")
            self.assertEqual(c.chat_model, "gemini-2.5-flash-lite:latest")
        finally:
            os.environ.pop("APPLE_GENAI_ENDPOINT", None)
            os.environ.pop("APPLE_GENAI_CHAT_MODEL", None)

    def test_openai_env_beats_apple_genai_env(self):
        """OPENAI_* 優先於 APPLE_GENAI_*。"""
        os.environ["OPENAI_ENDPOINT"] = "https://api.openai.com/v1"
        os.environ["APPLE_GENAI_ENDPOINT"] = "http://localhost:11211/api/openai/v1"
        try:
            c = LLMClient()
            self.assertEqual(c.endpoint, "https://api.openai.com/v1")
        finally:
            os.environ.pop("OPENAI_ENDPOINT", None)
            os.environ.pop("APPLE_GENAI_ENDPOINT", None)

    def test_trailing_slash_stripped(self):
        c = LLMClient(endpoint="https://api.openai.com/v1/")
        self.assertEqual(c.endpoint, "https://api.openai.com/v1")


class TestMockLLMClientDefault(unittest.TestCase):
    """MockLLMClient 預設 stub 行為（與舊 APPLE_GENAI_MOCK=1 相同）。"""

    def test_generic_chat_returns_ok(self):
        c = MockLLMClient()
        out = c.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "[mock] ok")

    def test_rubric_prompt_returns_json(self):
        c = MockLLMClient()
        out = c.chat([{"role": "user", "content": "依 rubric 打分，回 JSON 含 total"}])
        parsed = json.loads(out)
        self.assertIn("total", parsed)
        self.assertEqual(
            parsed["total"],
            sum(parsed[k] for k in (
                "d1_product_mention", "d2_ecosystem",
                "d3_training_potential", "d4_timeliness"
            ))
        )

    def test_embed_returns_1536_dim(self):
        """text-embedding-3-small 輸出 1536 維。"""
        c = MockLLMClient()
        vecs = c.embed(["hello"])
        self.assertEqual(len(vecs), 1)
        self.assertEqual(len(vecs[0]), 1536)

    def test_embed_deterministic(self):
        c = MockLLMClient()
        a = c.embed(["apple"])[0]
        b = c.embed(["apple"])[0]
        self.assertEqual(a, b)

    def test_embed_different_text_different_vec(self):
        c = MockLLMClient()
        a = c.embed(["apple"])[0]
        b = c.embed(["banana"])[0]
        self.assertNotEqual(a, b)

    def test_embed_batch(self):
        c = MockLLMClient()
        vecs = c.embed(["a", "b", "c"])
        self.assertEqual(len(vecs), 3)


class TestMockLLMClientInjection(unittest.TestCase):
    """MockLLMClient 的各種注入模式。"""

    def test_custom_chat_response(self):
        c = MockLLMClient(chat_response='{"status": "ok"}')
        out = c.chat([{"role": "user", "content": "anything"}])
        self.assertEqual(out, '{"status": "ok"}')

    def test_chat_fn_callable(self):
        def my_fn(messages):
            return f"got {len(messages)} messages"
        c = MockLLMClient(chat_fn=my_fn)
        out = c.chat([{"role": "user", "content": "x"}, {"role": "user", "content": "y"}])
        self.assertEqual(out, "got 2 messages")

    def test_embed_fn_callable(self):
        c = MockLLMClient(embed_fn=lambda texts: [[0.1] * 3 for _ in texts])
        vecs = c.embed(["a", "b"])
        self.assertEqual(len(vecs), 2)
        self.assertEqual(vecs[0], [0.1, 0.1, 0.1])

    def test_raise_on_chat(self):
        c = MockLLMClient(raise_on_chat=LLMError("simulated timeout"))
        with self.assertRaises(LLMError) as ctx:
            c.chat([{"role": "user", "content": "x"}])
        self.assertIn("simulated timeout", str(ctx.exception))

    def test_raise_on_embed(self):
        c = MockLLMClient(raise_on_embed=LLMError("embed failed"))
        with self.assertRaises(LLMError):
            c.embed(["text"])

    def test_call_recording(self):
        """chat_calls / embed_calls 記錄每次呼叫的參數。"""
        c = MockLLMClient()
        c.chat([{"role": "user", "content": "first"}])
        c.chat([{"role": "user", "content": "second"}])
        c.embed(["a", "b"])
        self.assertEqual(len(c.chat_calls), 2)
        self.assertEqual(c.chat_calls[0][0]["content"], "first")
        self.assertEqual(len(c.embed_calls), 1)
        self.assertEqual(c.embed_calls[0], ["a", "b"])

    def test_chat_fn_beats_chat_response(self):
        """chat_fn 優先於 chat_response。"""
        c = MockLLMClient(
            chat_response="from response",
            chat_fn=lambda _: "from fn",
        )
        self.assertEqual(c.chat([{"role": "user", "content": "x"}]), "from fn")


class TestMakeClient(unittest.TestCase):
    """make_client() 工廠函式。"""

    def setUp(self):
        os.environ.pop("OPENAI_MOCK", None)
        os.environ.pop("APPLE_GENAI_MOCK", None)

    def tearDown(self):
        os.environ.pop("OPENAI_MOCK", None)
        os.environ.pop("APPLE_GENAI_MOCK", None)

    def test_returns_llm_client_by_default(self):
        c = make_client()
        self.assertIsInstance(c, LLMClient)
        self.assertNotIsInstance(c, MockLLMClient)

    def test_openai_mock_env_returns_mock(self):
        os.environ["OPENAI_MOCK"] = "1"
        c = make_client()
        self.assertIsInstance(c, MockLLMClient)

    def test_apple_genai_mock_env_returns_mock(self):
        """向後相容：APPLE_GENAI_MOCK=1 也走 mock。"""
        os.environ["APPLE_GENAI_MOCK"] = "1"
        c = make_client()
        self.assertIsInstance(c, MockLLMClient)

    def test_mock_env_zero_returns_real(self):
        os.environ["OPENAI_MOCK"] = "0"
        c = make_client()
        self.assertNotIsInstance(c, MockLLMClient)


class TestJsonExtraction(unittest.TestCase):
    """_extract_json 靜態方法。"""

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
    """chat_json 透過 MockLLMClient 測試。"""

    def test_rubric_parsing(self):
        c = MockLLMClient()
        d = c.chat_json([{"role": "user", "content": "給 rubric 打 total 分數"}])
        self.assertIn("total", d)
        self.assertIsInstance(d["total"], int)

    def test_custom_json_response(self):
        c = MockLLMClient(chat_response='{"key": "value", "n": 42}')
        d = c.chat_json([{"role": "user", "content": "x"}])
        self.assertEqual(d["key"], "value")
        self.assertEqual(d["n"], 42)

    def test_invalid_json_raises(self):
        c = MockLLMClient(chat_response="not json at all")
        with self.assertRaises(LLMError):
            c.chat_json([{"role": "user", "content": "x"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
