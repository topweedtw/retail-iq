#!/usr/bin/env python3
"""
scripts/embedding_index.py — Gate 1b 近似重複偵測（§8.5b）

維護 raw/_embeddings-index.json（content_hash → embedding vector）供 Gate 1b
在 hash dedup 通過後，對同 source 既有文章做 cosine similarity 檢查。

設計：
    - Persisted cache：避免重複呼叫 embedding API（成本 ~1k tokens/篇）
    - 同 source 比對：減少跨來源誤判（apple.com 與轉載新聞可能重疊）
    - Threshold 0.98：§8.5b 預設值
    - Graceful：embedding call 失敗時 return (None, None) 讓 caller 照舊處理

Schema:
    {
      "version": 1,
      "model": "text-multilingual-embedding-002:latest",
      "embeddings": {
        "sha256:<hex>": {
          "source": "apple-com-tw",
          "basename": "iphone-17_20260505",
          "vec": [0.01, -0.02, ...]   # 768 floats
        }
      }
    }
"""
from __future__ import annotations
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Optional

INDEX_VERSION = 1
DEFAULT_THRESHOLD = 0.98


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot / (|a| * |b|)。兩邊為 0 vector 時回 0.0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class EmbeddingIndex:
    """管 raw/_embeddings-index.json 的讀寫 + 近重檢查。"""

    def __init__(self, path: Path, client=None, threshold: float = DEFAULT_THRESHOLD):
        self.path = path
        self.client = client
        self.threshold = threshold
        self._data: dict = self._load()
        self._dirty = False

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "version": INDEX_VERSION,
            "model": (self.client.embedding_model if self.client else "unknown"),
            "embeddings": {},
        }

    def save(self) -> None:
        """Atomic save with Enchanté-sandbox fallback (same pattern as backfill_gate3)."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self._data, ensure_ascii=False, indent=2) + "\n"
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.replace(tmp, self.path)
            self._dirty = False
            return
        except PermissionError:
            pass
        # Sandbox fallback
        repo_root = self.path.parent.parent if self.path.parent.name == "raw" else self.path.parent
        try:
            if self.path.exists():
                subprocess.run(
                    ["git", "rm", "-f", "--quiet", str(self.path)],
                    cwd=repo_root, check=False, capture_output=True,
                )
            self.path.write_text(payload, encoding="utf-8")
            self._dirty = False
        finally:
            if tmp.exists():
                subprocess.run(
                    ["git", "clean", "-f", "--quiet", str(tmp)],
                    cwd=repo_root, capture_output=True,
                )

    # ────────────────────────────────────────────────────────────────
    # Core ops
    # ────────────────────────────────────────────────────────────────

    def has(self, content_hash: str) -> bool:
        return content_hash in self._data["embeddings"]

    def get(self, content_hash: str) -> Optional[list[float]]:
        entry = self._data["embeddings"].get(content_hash)
        return entry["vec"] if entry else None

    def add(self, content_hash: str, source: str, basename: str, vec: list[float]) -> None:
        self._data["embeddings"][content_hash] = {
            "source": source,
            "basename": basename,
            "vec": vec,
        }
        self._dirty = True

    def embed_text(self, text: str) -> Optional[list[float]]:
        """呼叫 LLM client 取 embedding。失敗 return None。"""
        if self.client is None:
            return None
        try:
            vecs = self.client.embed([text])
            return vecs[0] if vecs else None
        except Exception:
            return None

    def find_near_duplicate(
        self, vec: list[float], source: str,
    ) -> Optional[tuple[str, float]]:
        """在同 source 既有 entries 中找 cosine similarity ≥ threshold 的第一筆。

        Returns:
            (basename, similarity) 若找到，否則 None。
        """
        best: Optional[tuple[str, float]] = None
        for entry in self._data["embeddings"].values():
            if entry["source"] != source:
                continue
            sim = cosine_similarity(vec, entry["vec"])
            if sim >= self.threshold:
                if best is None or sim > best[1]:
                    best = (entry["basename"], sim)
        return best

    def check_and_stage(
        self, content_hash: str, source: str, basename: str, text: str,
    ) -> tuple[Optional[list[float]], Optional[tuple[str, float]]]:
        """一站式：算 embedding + 找近重。

        Returns:
            (vec, dup_info) 其中 dup_info = (basename, similarity) 或 None。
            Caller 決定是否要 add() 進 index（skipped 的不加）。
            若 embed 失敗，vec = None, dup_info = None。
        """
        vec = self.embed_text(text)
        if vec is None:
            return None, None
        dup = self.find_near_duplicate(vec, source)
        return vec, dup

    # ────────────────────────────────────────────────────────────────
    # Debug
    # ────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._data["embeddings"])

    def stats(self) -> dict:
        by_source: dict[str, int] = {}
        for e in self._data["embeddings"].values():
            by_source[e["source"]] = by_source.get(e["source"], 0) + 1
        return {
            "total": len(self),
            "by_source": by_source,
            "model": self._data.get("model", "unknown"),
        }
