"""Review Queue API — 查詢與決策。"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from scripts.review_queue import walk_queue, parse_queue_file, apply_queue_item, archive_queue_file


QUEUE_DIR = REPO_ROOT / "wiki" / "ingest-queue"


@router.get("")
def list_queue():
    """列出所有開放的 review queue items。"""
    items = walk_queue(QUEUE_DIR)
    result = []
    for it in items:
        proposals = []
        for p in it.proposals:
            proposals.append({
                "section": p.section,
                "action": p.action,
                "new_content": p.new_content,
                "decision": p.decision,
            })
        result.append({
            "path": str(it.path.relative_to(REPO_ROOT)),
            "target_slug": it.target_slug,
            "article_ref": it.article_ref,
            "proposals": proposals,
            "has_decided": it.has_decided,
            "has_applyable": it.has_applyable,
        })
    return {"items": result, "total": len(result)}


@router.get("/stats")
def queue_stats():
    """Review queue 統計摘要。"""
    items = walk_queue(QUEUE_DIR)
    by_decision = {"apply": 0, "reject": 0, "edit-then-apply": 0, "undecided": 0}
    for it in items:
        for p in it.proposals:
            by_decision[p.decision] += 1
    return {
        "total_items": len(items),
        "total_proposals": sum(len(it.proposals) for it in items),
        "by_decision": by_decision,
        "decided_files": sum(1 for it in items if it.has_decided),
    }
