"""Ingest Pipeline API — 狀態查詢、手動觸發、來源管理、檔案上傳。"""
from __future__ import annotations

import json
import re
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "raw"
CONFIG_PATH = REPO_ROOT / "wiki" / "sources-config.yaml"
TZ = timezone(timedelta(hours=8))


@router.get("/status")
def ingest_status():
    """回傳 raw/ 目錄的 ingest 狀態摘要。"""
    stats = {
        "total_articles": 0,
        "by_status": {},
        "by_source": {},
        "by_week": {},
    }

    for meta_path in RAW_DIR.glob("*/*/*.meta.json"):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        stats["total_articles"] += 1
        status = m.get("ingest_status", "unknown")
        source = meta_path.parent.parent.name
        week = meta_path.parent.name

        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        stats["by_week"][week] = stats["by_week"].get(week, 0) + 1

    return stats


@router.get("/sources")
def list_sources():
    """回傳 sources-config.yaml 的來源清單。"""
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.yaml_mini import load

    config = load(REPO_ROOT / "wiki" / "sources-config.yaml")
    sources = []
    for name, cfg in (config.get("sources") or {}).items():
        if not cfg:
            continue
        sources.append({
            "name": name,
            "tier": cfg.get("tier", "?"),
            "enabled": cfg.get("enabled", False),
            "display_name": cfg.get("display_name", name),
            "fetch_method": cfg.get("fetch_method", "?"),
        })
    return {"sources": sources, "total": len(sources)}


# ═══════════════════════════════════════════════════════════════
# 新增來源
# ═══════════════════════════════════════════════════════════════

class AddSourceRequest(BaseModel):
    name: str = Field(..., description="來源 ID（英文 slug，如 my-blog）", pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = Field(..., description="顯示名稱")
    tier: str = Field("T2", description="T1 / T2 / T2-filtered / T3")
    base_url: str = Field(..., description="來源網站 URL")
    fetch_method: str = Field("rss", description="rss / http / manual")
    rss_url: Optional[str] = Field(None, description="RSS feed URL（fetch_method=rss 時必填）")
    locale: str = Field("en-US", description="語言")
    enabled: bool = Field(True, description="是否啟用")
    allow_url_patterns: list[str] = Field(default_factory=list)
    deny_url_patterns: list[str] = Field(default_factory=list)
    title_required_regex: Optional[str] = Field(None)
    title_blocklist_regex: Optional[str] = Field(None)


@router.post("/sources")
def add_source(req: AddSourceRequest):
    """新增一個 ingest 來源到 sources-config.yaml。"""
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.yaml_mini import load

    # 驗證 name 不重複
    config = load(CONFIG_PATH)
    existing = config.get("sources") or {}
    if req.name in existing:
        raise HTTPException(status_code=409, detail=f"Source '{req.name}' already exists")

    # 驗證 tier
    valid_tiers = {"T1", "T2", "T2-filtered", "T3"}
    if req.tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {valid_tiers}")

    # 驗證 regex patterns 可 compile
    for pat in req.allow_url_patterns + req.deny_url_patterns:
        try:
            re.compile(pat)
        except re.error as e:
            raise HTTPException(status_code=400, detail=f"Invalid regex pattern '{pat}': {e}")
    for pat in [req.title_required_regex, req.title_blocklist_regex]:
        if pat:
            try:
                re.compile(pat)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex '{pat}': {e}")

    # 組裝 YAML block（手動 append 到檔案末尾，在 global: 之前）
    lines = [
        f"  {req.name}:",
        f"    tier: {req.tier}",
        f"    enabled: {'true' if req.enabled else 'false'}",
        f'    display_name: "{req.display_name}"',
        f'    base_url: "{req.base_url}"',
        f"    fetch_method: {req.fetch_method}",
        f"    locale: {req.locale}",
    ]
    if req.rss_url:
        lines.append(f'    rss_url: "{req.rss_url}"')
    if req.allow_url_patterns:
        lines.append("    allow_url_patterns:")
        for pat in req.allow_url_patterns:
            lines.append(f'      - "{pat}"')
    if req.deny_url_patterns:
        lines.append("    deny_url_patterns:")
        for pat in req.deny_url_patterns:
            lines.append(f'      - "{pat}"')
    if req.title_required_regex:
        lines.append(f'    title_required_regex: "{req.title_required_regex}"')
    if req.title_blocklist_regex:
        lines.append(f'    title_blocklist_regex: "{req.title_blocklist_regex}"')

    new_block = "\n".join(lines) + "\n"

    # 插入到 `global:` 之前
    content = CONFIG_PATH.read_text(encoding="utf-8")
    insert_marker = "\nglobal:\n"
    if insert_marker in content:
        idx = content.index(insert_marker)
        # 加一個分隔註解
        separator = f"\n  # ── 由管理後台新增 ({datetime.now(TZ).strftime('%Y-%m-%d')}) ──\n\n"
        content = content[:idx] + separator + new_block + content[idx:]
    else:
        # fallback: append at end
        content += "\n" + new_block

    CONFIG_PATH.write_text(content, encoding="utf-8")

    return {
        "status": "created",
        "source": req.name,
        "message": f"Source '{req.name}' added to sources-config.yaml",
    }


# ═══════════════════════════════════════════════════════════════
# 手動上傳 markdown 檔案
# ═══════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_markdown(
    file: UploadFile = File(..., description="Markdown 檔案（.md 或 .txt）"),
    title: str = Form(..., description="文章標題"),
    related_products: str = Form("", description="相關產品 slug（逗號分隔，如 iphone-17-pro,mac-mini）"),
    notes: str = Form("", description="備註"),
):
    """管理者手動上傳 markdown/txt 檔案，作為 admin-upload T1 來源進入 pipeline。

    檔案會存入 raw/admin-upload/<current-week>/ 並自動建立 meta.json。
    ingest_status 設為 approved（T1 免打分）。
    """
    # 驗證檔案類型
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".md", ".txt", ".markdown"):
        raise HTTPException(
            status_code=400,
            detail=f"Only .md / .txt files accepted, got '{ext}'",
        )

    # 讀取內容
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    if len(content.strip()) < 50:
        raise HTTPException(status_code=400, detail="File content too short (< 50 chars)")

    # 計算 week + slug
    now = datetime.now(TZ)
    y, w, _ = now.isocalendar()
    week = f"{y}-W{w:02d}"
    date_str = now.strftime("%Y%m%d")

    # Slugify title
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:60] or "upload"
    basename = f"{slug}_{date_str}"

    # 寫入 raw/admin-upload/<week>/
    folder = RAW_DIR / "admin-upload" / week
    folder.mkdir(parents=True, exist_ok=True)

    txt_path = folder / f"{basename}.txt"
    meta_path = folder / f"{basename}.meta.json"

    # 避免覆蓋
    counter = 1
    while txt_path.exists() or meta_path.exists():
        basename = f"{slug}_{date_str}_{counter}"
        txt_path = folder / f"{basename}.txt"
        meta_path = folder / f"{basename}.meta.json"
        counter += 1

    # 寫 .txt
    txt_path.write_text(content, encoding="utf-8")

    # 寫 meta.json
    content_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    related = [s.strip() for s in related_products.split(",") if s.strip()]

    meta = {
        "source_url": f"upload://{file.filename}",
        "source_type": "admin-upload",
        "source_tier": "T1",
        "source_title": title,
        "fetched_at": now.isoformat(timespec="seconds"),
        "fetched_by": "admin-upload-api",
        "content_hash": content_hash,
        "content_type": "text/markdown",
        "content_size_bytes": len(content_bytes),
        "http_status": 200,
        "locale": "zh-TW",
        "related_wiki_pages": related,
        "ingest_status": "approved",
        "ingest_log_ref": None,
        "relevance_score": 10,
        "relevance_reasoning": "管理者手動上傳，T1 免打分",
        "relevance_breakdown": {"d1_product_mention": 3, "d2_ecosystem": 2, "d3_training_potential": 3, "d4_timeliness": 2},
        "key_entities": related,
        "notes": notes or None,
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "uploaded",
        "path": str(txt_path.relative_to(REPO_ROOT)),
        "meta_path": str(meta_path.relative_to(REPO_ROOT)),
        "basename": basename,
        "week": week,
        "content_hash": content_hash,
        "message": f"File uploaded as T1 admin-upload. Run Gate 4 to ingest into wiki.",
    }
