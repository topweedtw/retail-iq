"""
scripts/relevance_scorer.py — Gate 3 相關性打分（§8.10）

用 LLM（預設 gemini-2.5-flash-lite）依 §8.10.1 的 4 維度 rubric 打 0-10 分：

  D1 Apple 產品直接提及     (0-3)
  D2 Apple 生態/技術        (0-2)
  D3 訓練素材潛力          (0-3)
  D4 時效性                (0-2)

T1 來源與 admin-upload 跳過（預設滿分 10，依 §8.10.4）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .llm_client import LLMClient, LLMError


@dataclass
class RelevanceScore:
    total: int                  # 0-10
    reasoning: str
    breakdown: dict[str, int]   # d1_product_mention, d2_ecosystem, d3_training_potential, d4_timeliness
    key_entities: list[str]


# §8.10.3 的 prompt template
PROMPT_TEMPLATE = """你是 RetailIQ 訓練系統的內容相關性評估員。

[你的任務]
讀下方文章，依 4 個維度打分（D1–D4），並輸出嚴格 JSON。

[評分維度]
D1 (0–3): Apple 產品直接提及（iPhone / Mac / iPad / Watch / AirPods / Vision / Apple TV+ / iCloud 等）
D2 (0–2): Apple 生態／軟體／技術（Apple Intelligence / iOS / macOS / Swift / Final Cut Pro / HomeKit / MagSafe / ProRes）
D3 (0–3): 對門市訓練（產品話術、反對處理、demo）的素材潛力
D4 (0–2): 時效性（當代在售產品 > 舊機回顧 > 歷史文章）

[文章]
標題：{title}
內文（前 3000 字）：
{content_excerpt}

[輸出格式 — 嚴格 JSON，不要 markdown fence，不要任何其他文字]
{{
  "d1_product_mention": <0-3>,
  "d2_ecosystem": <0-2>,
  "d3_training_potential": <0-3>,
  "d4_timeliness": <0-2>,
  "total": <sum>,
  "reasoning": "<一句話，≤40 字，解釋為何這個總分>",
  "key_entities": [<最多 5 個，例: "iPhone 17 Pro", "Apple Intelligence">]
}}"""


def score_article(
    title: str,
    content: str,
    *,
    client: LLMClient | None = None,
    max_content_chars: int = 3000,
) -> RelevanceScore:
    """
    對一篇文章打相關性分數。

    Args:
        title: 文章標題
        content: 文章純文字內容（會截 max_content_chars 前段）
        client: LLMClient 實例（預設用全域預設）
        max_content_chars: 丟給 LLM 的內文最大長度

    Returns:
        RelevanceScore dataclass

    Raises:
        LLMError: API 呼叫失敗或 JSON 解析失敗
    """
    client = client or LLMClient()
    content_excerpt = (content or "")[:max_content_chars]
    prompt = PROMPT_TEMPLATE.format(
        title=title or "(無標題)",
        content_excerpt=content_excerpt or "(無內文)",
    )
    raw = client.chat_json(
        messages=[
            {"role": "system", "content": "You output JSON only, no markdown fence."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
    )
    return _parse_score(raw)


def _parse_score(raw: dict) -> RelevanceScore:
    """
    從 LLM JSON 解析成 RelevanceScore，並做一致性檢查。

    - total 必須等於 d1+d2+d3+d4（若不符，以實際 sum 為準）
    - total clamp 到 [0, 10]
    - 各維度 clamp 到各自上限
    """
    def clamp(v, lo, hi):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return lo

    d1 = clamp(raw.get("d1_product_mention", 0), 0, 3)
    d2 = clamp(raw.get("d2_ecosystem", 0), 0, 2)
    d3 = clamp(raw.get("d3_training_potential", 0), 0, 3)
    d4 = clamp(raw.get("d4_timeliness", 0), 0, 2)
    computed_total = d1 + d2 + d3 + d4
    reported_total = raw.get("total", computed_total)

    # 以實際 sum 為準（LLM 偶爾自相矛盾）
    total = computed_total
    if reported_total != computed_total:
        logging.debug(
            f"Score consistency: reported={reported_total} vs sum={computed_total}; using sum"
        )

    reasoning = (raw.get("reasoning") or "").strip()[:100]

    entities = raw.get("key_entities") or []
    if not isinstance(entities, list):
        entities = []
    entities = [str(e).strip() for e in entities[:5] if str(e).strip()]

    return RelevanceScore(
        total=total,
        reasoning=reasoning,
        breakdown={
            "d1_product_mention": d1,
            "d2_ecosystem": d2,
            "d3_training_potential": d3,
            "d4_timeliness": d4,
        },
        key_entities=entities,
    )


def status_for_score(score: int) -> str:
    """§8.10.2：分數 → ingest_status"""
    if score < 5:
        return "skipped-low-relevance"
    if score < 7:
        return "pending-review"
    return "approved"


# ═════════════════════════════════════════════════════════════════
# CLI 測試用
# ═════════════════════════════════════════════════════════════════

def _main():
    """跑 `python3 scripts/relevance_scorer.py <path.txt>` 測一篇文章。"""
    import sys
    if len(sys.argv) < 2:
        # 跑個內建範例
        sample_title = "iPhone 17 Pro 與 iPhone 17 Pro Max — Apple 台灣"
        sample_text = "熱鍛造鋁金屬一體成型設計，搭載 A19 Pro 晶片，最高 8 倍光學變焦。Apple Intelligence、Center Stage 前置相機、ProRes RAW。"
        print(f"Demo scoring:\n  Title: {sample_title}")
        score = score_article(sample_title, sample_text)
    else:
        from pathlib import Path
        txt = Path(sys.argv[1])
        content = txt.read_text(encoding="utf-8")
        # 抓第一行當 title
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        title = lines[0] if lines else txt.stem
        body = "\n".join(lines[1:])
        print(f"Scoring: {txt.name}")
        print(f"  Title guess: {title[:60]}")
        score = score_article(title, body)

    status = status_for_score(score.total)
    print()
    print(f"  Total:      {score.total}/10  →  {status}")
    print(f"  Breakdown:  D1={score.breakdown['d1_product_mention']}/3, "
          f"D2={score.breakdown['d2_ecosystem']}/2, "
          f"D3={score.breakdown['d3_training_potential']}/3, "
          f"D4={score.breakdown['d4_timeliness']}/2")
    print(f"  Reasoning:  {score.reasoning}")
    print(f"  Entities:   {score.key_entities}")


if __name__ == "__main__":
    _main()
