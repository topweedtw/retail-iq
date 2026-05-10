"""
scripts/llm_client.py — OpenAI-compatible 客戶端（stdlib urllib，零依賴）

支援任何 OpenAI-compatible endpoint：
  - api.openai.com（預設）
  - 本地 Ollama（http://localhost:11434/v1）
  - 本地 LM Studio（http://localhost:1234/v1）
  - 其他 proxy

環境變數（全 optional，有合理預設）：
  OPENAI_API_KEY          API key（打 api.openai.com 時必填）
  OPENAI_ENDPOINT         default: https://api.openai.com/v1
  OPENAI_CHAT_MODEL       default: gpt-4o-mini
  OPENAI_EMBEDDING_MODEL  default: text-embedding-3-small
  OPENAI_TIMEOUT          default: 30（秒）
  OPENAI_MOCK             若 =1 → 用 MockLLMClient 不打網路（CI/unit test 用）

向後相容：舊的 APPLE_GENAI_* 環境變數仍可用，優先序低於 OPENAI_*。

本檔零 pip 依賴，純 stdlib。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TIMEOUT = 30


class LLMError(RuntimeError):
    """LLM API 呼叫失敗（HTTP 錯、解析錯、或業務錯）。"""


class LLMClient:
    """
    最小 OpenAI-compatible 客戶端。

    使用：
        client = LLMClient()                          # 讀環境變數
        client = LLMClient(api_key="sk-...")          # 明確傳入
        client = LLMClient(endpoint="http://localhost:11434/v1", api_key="")  # Ollama

        content = client.chat([{"role": "user", "content": "回 OK"}])
        embeddings = client.embed(["some text"])      # → list[list[float]]

    測試用：
        from scripts.llm_client import MockLLMClient
        client = MockLLMClient()                      # 固定 stub 回應
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        # Endpoint：OPENAI_ENDPOINT > APPLE_GENAI_ENDPOINT（向後相容）> default
        self.endpoint = (
            endpoint
            or os.environ.get("OPENAI_ENDPOINT")
            or os.environ.get("APPLE_GENAI_ENDPOINT")
            or DEFAULT_ENDPOINT
        ).rstrip("/")

        # API key：明確傳入 > OPENAI_API_KEY > 空字串（本地 endpoint 不需要）
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")

        # Models：OPENAI_* > APPLE_GENAI_*（向後相容）> default
        self.chat_model = (
            chat_model
            or os.environ.get("OPENAI_CHAT_MODEL")
            or os.environ.get("APPLE_GENAI_CHAT_MODEL")
            or DEFAULT_CHAT_MODEL
        )
        self.embedding_model = (
            embedding_model
            or os.environ.get("OPENAI_EMBEDDING_MODEL")
            or os.environ.get("APPLE_GENAI_EMBEDDING_MODEL")
            or DEFAULT_EMBEDDING_MODEL
        )
        self.timeout = timeout or int(
            os.environ.get("OPENAI_TIMEOUT")
            or os.environ.get("APPLE_GENAI_TIMEOUT")
            or DEFAULT_TIMEOUT
        )

    # ═════════════════════════════════════════════════════════════
    # Chat
    # ═════════════════════════════════════════════════════════════

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> str:
        """送 chat completion，回傳 content 字串。"""
        body = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post_json("/chat/completions", body)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected chat response shape: {data}") from e

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """送 chat 並解析 JSON 結果。

        策略：很多模型會包 markdown fence（如 ```json ... ```），
        先找第一個 { ... } 區塊，不行才 raise。
        """
        content = self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        return self._extract_json(content)

    # ═════════════════════════════════════════════════════════════
    # Embedding
    # ═════════════════════════════════════════════════════════════

    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """取 embedding。單筆或批次皆可。"""
        body = {
            "model": model or self.embedding_model,
            "input": texts,
        }
        data = self._post_json("/embeddings", body)
        try:
            return [item["embedding"] for item in data["data"]]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected embedding response shape: {data}") from e

    # ═════════════════════════════════════════════════════════════
    # Internal
    # ═════════════════════════════════════════════════════════════

    def _post_json(self, path: str, body: dict) -> dict:
        url = self.endpoint + path
        data = json.dumps(body).encode("utf-8")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise LLMError(f"HTTP {e.code} from {url}: {err_body[:500]}") from e
        except urllib.error.URLError as e:
            raise LLMError(
                f"Network error to {url}: {e.reason}. "
                f"Is the endpoint reachable? ({self.endpoint})"
            ) from e

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """從 LLM 輸出裡抽第一個合法 JSON 物件。

        使用 JSONDecoder.raw_decode() 逐字元掃描，找到第一個可合法解析的
        '{' 起始位置即停止，避免貪婪 regex 在多 JSON 物件時抓到整段導致
        json.loads 失敗。
        """
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        decoder = json.JSONDecoder()
        for i, ch in enumerate(content):
            if ch == "{":
                try:
                    obj, _ = decoder.raw_decode(content, i)
                    return obj
                except json.JSONDecodeError:
                    continue
        raise LLMError(f"No JSON object found in LLM output: {content[:300]!r}")


# ═════════════════════════════════════════════════════════════════
# MockLLMClient — 測試 / CI 用
# ═════════════════════════════════════════════════════════════════

class MockLLMClient(LLMClient):
    """不打網路的 mock 實作，供 unit test 和 CI 使用。

    使用方式：
        # 1. 固定 stub（預設行為，與舊 APPLE_GENAI_MOCK=1 相同）
        client = MockLLMClient()

        # 2. 自訂 chat 回應（per-test 注入）
        client = MockLLMClient(chat_response='{"total": 5, ...}')

        # 3. 用 callable 動態決定回應
        client = MockLLMClient(chat_fn=lambda messages: '{"total": 9}')

        # 4. 模擬 API 失敗
        client = MockLLMClient(raise_on_chat=LLMError("timeout"))
    """

    def __init__(
        self,
        *,
        chat_response: str | None = None,
        chat_fn: Any = None,
        embed_fn: Any = None,
        raise_on_chat: Exception | None = None,
        raise_on_embed: Exception | None = None,
        # 保留 LLMClient 的 signature 相容性，但忽略網路相關參數
        endpoint: str | None = None,
        api_key: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        # 不呼叫 super().__init__() 的網路邏輯，直接設屬性
        self.endpoint = endpoint or "mock://localhost"
        self.api_key = ""
        self.chat_model = chat_model or DEFAULT_CHAT_MODEL
        self.embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL
        self.timeout = timeout or DEFAULT_TIMEOUT

        self._chat_response = chat_response
        self._chat_fn = chat_fn
        self._embed_fn = embed_fn
        self._raise_on_chat = raise_on_chat
        self._raise_on_embed = raise_on_embed

        # 呼叫記錄（方便 test 驗證）
        self.chat_calls: list[list[dict]] = []
        self.embed_calls: list[list[str]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> str:
        self.chat_calls.append(messages)
        if self._raise_on_chat:
            raise self._raise_on_chat
        if self._chat_fn:
            return self._chat_fn(messages)
        if self._chat_response is not None:
            return self._chat_response
        return _default_mock_chat(messages)

    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        self.embed_calls.append(texts)
        if self._raise_on_embed:
            raise self._raise_on_embed
        if self._embed_fn:
            return self._embed_fn(texts)
        return [_default_mock_embed(t) for t in texts]


# ═════════════════════════════════════════════════════════════════
# 預設 mock 實作（MockLLMClient 的 fallback）
# ═════════════════════════════════════════════════════════════════

def _default_mock_chat(messages: list[dict[str, str]]) -> str:
    """固定 stub：rubric prompt → 9 分 JSON；其他 → '[mock] ok'。"""
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if "rubric" in last_user.lower() or "total" in last_user.lower():
        return json.dumps({
            "d1_product_mention": 3,
            "d2_ecosystem": 2,
            "d3_training_potential": 2,
            "d4_timeliness": 2,
            "total": 9,
            "reasoning": "[mock] Apple 產品直接相關、時效性高",
            "key_entities": ["iPhone", "Apple Intelligence"],
        })
    return "[mock] ok"


def _default_mock_embed(text: str) -> list[float]:
    """確定性 1536-dim 假 embedding（hash-based）。相同文字 → 相同 vector。

    維度改為 1536 以符合 text-embedding-3-small 的實際輸出維度。
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    dim = 1536
    out = []
    for i in range(dim):
        b = h[i % len(h)]
        out.append((b - 128) / 128.0)
    return out


# ═════════════════════════════════════════════════════════════════
# 向後相容：OPENAI_MOCK=1 或 APPLE_GENAI_MOCK=1 → 回傳 MockLLMClient
# ═════════════════════════════════════════════════════════════════

def make_client(**kwargs: Any) -> LLMClient:
    """工廠函式：依環境變數決定回傳 LLMClient 或 MockLLMClient。

    建議在 pipeline 程式碼裡用這個取代直接 LLMClient()，
    這樣 CI 只要設 OPENAI_MOCK=1 就自動走 mock。

    使用：
        from scripts.llm_client import make_client
        llm = make_client()
    """
    mock_env = os.environ.get("OPENAI_MOCK") or os.environ.get("APPLE_GENAI_MOCK")
    if mock_env == "1":
        return MockLLMClient(**{k: v for k, v in kwargs.items()
                                if k in ("chat_model", "embedding_model", "timeout")})
    return LLMClient(**kwargs)


# ═════════════════════════════════════════════════════════════════
# CLI 測試用
# ═════════════════════════════════════════════════════════════════

def _main() -> None:
    """執行 `python3 scripts/llm_client.py` 直接測 endpoint 活著沒。"""
    import sys
    client = LLMClient()
    print(f"Endpoint:        {client.endpoint}")
    print(f"Chat model:      {client.chat_model}")
    print(f"Embedding model: {client.embedding_model}")
    print(f"API key:         {'set' if client.api_key else 'NOT SET'}")
    print()

    if not client.api_key and "openai.com" in client.endpoint:
        print("⚠️  OPENAI_API_KEY 未設定，打 api.openai.com 會 401")
        print("   請先執行：export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    print("── Chat test ──")
    try:
        reply = client.chat([{"role": "user", "content": "回「OK」即可"}], max_tokens=10)
        print(f"  ✅ {reply!r}")
    except LLMError as e:
        print(f"  ❌ {e}")
        return

    print("── Chat JSON test ──")
    try:
        data = client.chat_json([
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": 'Output: {"status": "ok", "n": 42}'},
        ], max_tokens=50)
        print(f"  ✅ {data}")
    except LLMError as e:
        print(f"  ❌ {e}")

    print("── Embedding test ──")
    try:
        vecs = client.embed(["iPhone 17 Pro", "MacBook Neo"])
        print(f"  ✅ {len(vecs)} vectors, dim={len(vecs[0])}")
    except LLMError as e:
        print(f"  ❌ {e}")


if __name__ == "__main__":
    _main()
