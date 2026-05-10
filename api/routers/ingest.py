"""Ingest Pipeline API — 狀態查詢與手動觸發。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "raw"


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
