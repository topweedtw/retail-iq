"""
scripts/llm_client.py — OpenAI-compatible 客戶端（stdlib urllib，零依賴）

Apple GenAI 透過本地 proxy (http://localhost:11211/api/openai/v1) 提供：
  - Chat completion：gemini-2.5-flash-lite:latest（輕量，適合 Gate 3 rubric 打分）
  - Embedding:        text-multilingual-embedding-002:latest（繁中+英文，適合 Gate 1b）

環境變數（全 optional，有合理預設）：
  APPLE_GENAI_ENDPOINT        default: http://localhost:11211/api/openai/v1
  APPLE_GENAI_CHAT_MODEL      default: gemini-2.5-flash-lite:latest
  APPLE_GENAI_EMBEDDING_MODEL default: text-multilingual-embedding-002:latest
  APPLE_GENAI_TIMEOUT         default: 30（秒）
  APPLE_GENAI_MOCK            若 =1 → 用內建 mock 不打網路（CI/unit test 用）

本檔零 pip 依賴，純 stdlib。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_ENDPOINT = "http://localhost:11211/api/openai/v1"
DEFAULT_CHAT_MODEL = "gemini-2.5-flash-lite:latest"
DEFAULT_EMBEDDING_MODEL = "text-multilingual-embedding-002:latest"
DEFAULT_TIMEOUT = 30


class LLMError(RuntimeError):
    """LLM API 呼叫失敗（HTTP 錯、解析錯、或業務錯）。"""


class LLMClient:
    """
    最小 OpenAI-compatible 客戶端。

    使用：
        client = LLMClient()
        content = client.chat([
            {"role": "user", "content": "回 OK"}
        ])

        embeddings = client.embed(["some text"])
        # → list[list[float]]
    """

    def __init__(
        self,
        endpoint: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout: int | None = None,
        mock: bool | None = None,
    ) -> None:
        self.endpoint = (endpoint or os.environ.get("APPLE_GENAI_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
        self.chat_model = chat_model or os.environ.get("APPLE_GENAI_CHAT_MODEL") or DEFAULT_CHAT_MODEL
        self.embedding_model = embedding_model or os.environ.get("APPLE_GENAI_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
        self.timeout = timeout or int(os.environ.get("APPLE_GENAI_TIMEOUT", DEFAULT_TIMEOUT))
        if mock is None:
            mock = os.environ.get("APPLE_GENAI_MOCK") == "1"
        self.mock = mock

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
        if self.mock:
            return _mock_chat(messages)

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
        """
        送 chat 並解析 JSON 結果。

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
        if self.mock:
            return [_mock_embed(t) for t in texts]

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
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
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
                f"Check Apple GenAI proxy is running on {self.endpoint}."
            ) from e

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """從 LLM 輸出裡抽第一個合法 JSON 物件。

        使用 JSONDecoder.raw_decode() 逐字元掃描，找到第一個可合法解析的
        '{' 起始位置即停止，避免貪婪 regex 在多 JSON 物件時抓到整段導致
        json.loads 失敗（#6）。
        """
        content = content.strip()
        # 去掉 markdown code fence
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        # 用 raw_decode 找第一個合法 JSON 物件
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
# Mock implementations (for APPLE_GENAI_MOCK=1)
# ═════════════════════════════════════════════════════════════════

def _mock_chat(messages: list[dict[str, str]]) -> str:
    """給 CI / unit test 用。回傳符合 §8.10.3 rubric 的假 JSON。"""
    # 看 prompt 是否要求 JSON（rubric），否則回文字
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


def _mock_embed(text: str) -> list[float]:
    """回一個確定性的 768-dim 假 embedding（hash-based）。相同文字 → 相同 vector。"""
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # 把 hash bytes 展開成 768 維（每 byte → [-1, 1] 浮點）
    dim = 768
    out = []
    for i in range(dim):
        b = h[i % len(h)]
        out.append((b - 128) / 128.0)
    return out


# ═════════════════════════════════════════════════════════════════
# CLI 測試用
# ═════════════════════════════════════════════════════════════════

def _main() -> None:
    """執行 `python3 scripts/llm_client.py` 直接測 endpoint 活著沒。"""
    client = LLMClient()
    print(f"Endpoint: {client.endpoint}")
    print(f"Chat model:      {client.chat_model}")
    print(f"Embedding model: {client.embedding_model}")
    print(f"Mock mode:       {client.mock}")
    print()

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
            {"role": "user", "content": "Output: {\"status\": \"ok\", \"n\": 42}"},
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
