"""產品頁 API — 讀取 wiki/products/ markdown 並轉為 JSON。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"


def _parse_product(path: Path) -> dict[str, Any]:
    """Parse a product markdown file into structured JSON."""
    text = path.read_text(encoding="utf-8")

    # Frontmatter
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_raw = parts[1]
            body = parts[2]
            # Simple key: value parsing (good enough for our frontmatter)
            for line in fm_raw.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^([^:]+):\s*(.*)$", line)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    # Inline list [a, b, c]
                    if val.startswith("[") and val.endswith("]"):
                        fm[key] = [v.strip().strip('"').strip("'")
                                   for v in val[1:-1].split(",") if v.strip()]
                    elif val.lower() in ("true", "false"):
                        fm[key] = val.lower() == "true"
                    elif val.isdigit():
                        fm[key] = int(val)
                    else:
                        fm[key] = val

    # Sections
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        else:
            if current is not None:
                buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()

    return {
        "slug": path.stem,
        "frontmatter": fm,
        "sections": sections,
        "raw_markdown": text,
    }


@router.get("")
def list_products():
    """列出所有產品頁（slug + title + status）。"""
    products = []
    for p in sorted(PRODUCTS_DIR.glob("*.md")):
        data = _parse_product(p)
        fm = data["frontmatter"]
        products.append({
            "slug": data["slug"],
            "title": fm.get("title", data["slug"]),
            "status": fm.get("status", "active"),
            "product_category": fm.get("product_category", ""),
            "last_updated": fm.get("last_updated", ""),
            "source_count": fm.get("source_count", 0),
        })
    return {"products": products, "total": len(products)}


@router.get("/{slug}")
def get_product(slug: str):
    """取得單一產品頁完整內容。"""
    path = PRODUCTS_DIR / f"{slug}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")
    return _parse_product(path)
