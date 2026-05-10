"""腳本生成器 API — 依產品 + persona + 時長生成銷售腳本。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class ScriptRequest(BaseModel):
    product_slug: str = Field(..., description="產品 slug，如 iphone-17-pro")
    persona: str = Field("general", description="客群 persona：business / creative / student / general")
    duration_min: int = Field(3, description="腳本時長（分鐘）：1 / 3 / 5")
    focus: str = Field("", description="重點賣點（可選，如 '相機' 或 'AI'）")
    language: str = Field("zh-TW", description="輸出語言")


class ScriptResponse(BaseModel):
    product_slug: str
    persona: str
    duration_min: int
    script_markdown: str
    fab_sections: list[dict]
    word_count: int


@router.post("/generate", response_model=ScriptResponse)
def generate_script(req: ScriptRequest):
    """生成銷售腳本（FAB+P 結構）。

    TODO: 接入 LLM 生成。目前回傳 placeholder。
    """
    # Placeholder — 正式版會讀 wiki/products/{slug}.md 的 FAB 結構，
    # 結合 persona 和 duration 呼叫 LLM 生成腳本。
    placeholder = f"""# {req.product_slug} — {req.persona} 客群 {req.duration_min} 分鐘腳本

> ⚠️ 此為 placeholder，正式版將由 LLM 依 FAB+P 結構生成。

## 開場（30 秒）

您好！今天想了解什麼產品呢？

## 主體（{req.duration_min - 1} 分鐘）

[依 {req.persona} 客群的 Benefits 展開...]

## 收尾（30 秒）

有什麼問題都可以問我！
"""
    return ScriptResponse(
        product_slug=req.product_slug,
        persona=req.persona,
        duration_min=req.duration_min,
        script_markdown=placeholder,
        fab_sections=[],
        word_count=len(placeholder),
    )
