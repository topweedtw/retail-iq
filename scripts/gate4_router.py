#!/usr/bin/env python3
"""
scripts/gate4_router.py — Gate 4 Phase 1 routing (entity-match only, no LLM)

Given an article's meta.json (with key_entities from Gate 3), find candidate
wiki/products/*.md pages whose frontmatter tags overlap.

Design: per gate4-ingest.md §3.1
    - Step 1: candidates by entity overlap (this module)
    - Step 2: if >1 candidate, LLM picks (Phase 2+, not implemented here)

Usage:
    python3 scripts/gate4_router.py raw/apple-com-tw/2026-W19/iphone-17_20260505.meta.json
    python3 scripts/gate4_router.py --all-w 2026-W19     # route every approved/pending-review
    python3 scripts/gate4_router.py --threshold 2 <...>  # min entity hits to qualify
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import math
from pathlib import Path
from typing import NamedTuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from yaml_mini import loads as yloads  # noqa: E402

REPO_ROOT = SCRIPTS.parent
PRODUCTS_DIR = REPO_ROOT / "wiki" / "products"
RAW_DIR = REPO_ROOT / "raw"

DEFAULT_THRESHOLD = 1.0  # IDF-weighted sum threshold. With 3 products, a single unique-tag hit ≈ 1.1

ROUTABLE_STATUSES = {"approved", "pending-review"}


# ─────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────

_STOP_SUFFIXES = ["晶片", "技術", "chip", "series"]


def normalize_token(s: str) -> str:
    """lowercase, strip punctuation to '-', remove trivial suffixes."""
    s = s.strip().lower()
    for suf in _STOP_SUFFIXES:
        if s.endswith(" " + suf) or s.endswith("-" + suf):
            s = s[: -(len(suf) + 1)].strip()
    # non alnum → '-'
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s).strip("-")
    return s


def entity_matches_tag(entity_norm: str, tag_norm: str) -> bool:
    """Match if tag is contained in entity (word boundary), or vice versa,
    or they share a sufficiently long prefix."""
    if not entity_norm or not tag_norm:
        return False
    if entity_norm == tag_norm:
        return True
    # tag is a token/prefix inside entity (e.g. tag="iphone" matches entity="iphone-17")
    if tag_norm in entity_norm.split("-"):
        return True
    # entity is a token inside tag (rare)
    if entity_norm in tag_norm.split("-"):
        return True
    # tag is a hyphenated prefix (e.g. tag="apple-intelligence" matches entity "apple-intelligence")
    if entity_norm.startswith(tag_norm + "-") or tag_norm.startswith(entity_norm + "-"):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────
# Product index
# ─────────────────────────────────────────────────────────────────────

class Product(NamedTuple):
    slug: str
    path: Path
    tags: list[str]  # normalized
    title: str


def compute_idf(products: list[Product]) -> dict[str, float]:
    """Inverse-document-frequency per tag across the product corpus.
    Tag appearing in all N products → idf 0 (noise).
    Tag unique to one product       → idf = log(N) (strong signal).
    """
    if not products:
        return {}
    total = len(products)
    df: dict[str, int] = {}
    for p in products:
        for t in set(p.tags):
            df[t] = df.get(t, 0) + 1
    return {t: math.log(total / cnt) for t, cnt in df.items()}


def load_products(products_dir: Path = PRODUCTS_DIR) -> list[Product]:
    out = []
    for p in sorted(products_dir.glob("*.md")):
        s = p.read_text(encoding="utf-8")
        if not s.startswith("---"):
            continue
        fm_raw = s.split("---", 2)[1]
        fm = yloads(fm_raw) or {}
        if fm.get("status") == "archived":
            continue
        tags_raw = fm.get("tags") or []
        tags_norm = [normalize_token(t) for t in tags_raw]
        out.append(Product(
            slug=p.stem,
            path=p,
            tags=tags_norm,
            title=fm.get("title", p.stem),
        ))
    return out


# ─────────────────────────────────────────────────────────────────────
# Routing
# ─────────────────────────────────────────────────────────────────────

class RouteMatch(NamedTuple):
    product: Product
    score: float                         # IDF-weighted sum
    hits: int                            # raw count of entity-tag hits
    matched_pairs: list[tuple[str, str, float]]  # (entity, tag, idf)


def route(
    entities: list[str],
    products: list[Product],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    idf: dict[str, float] | None = None,
) -> list[RouteMatch]:
    """Return products with IDF-weighted score >= threshold, sorted desc."""
    if idf is None:
        idf = compute_idf(products)
    entities_norm = [normalize_token(e) for e in entities]
    matches = []
    for prod in products:
        pairs: list[tuple[str, str, float]] = []
        seen_tags: set[str] = set()
        for e_norm, e_raw in zip(entities_norm, entities):
            for t in prod.tags:
                if t in seen_tags:
                    continue
                if entity_matches_tag(e_norm, t):
                    pairs.append((e_raw, t, idf.get(t, 0.0)))
                    seen_tags.add(t)
                    break
        score = sum(w for _, _, w in pairs)
        if score >= threshold:
            matches.append(RouteMatch(prod, score, len(pairs), pairs))
    matches.sort(key=lambda m: -m.score)
    return matches


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def print_route(meta_path: Path, matches: list[RouteMatch], threshold: int) -> None:
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    status = m.get("ingest_status", "?")
    src = meta_path.parent.parent.name
    basename = meta_path.name.replace(".meta.json", "")
    ents = m.get("key_entities", [])
    print(f"\n📄 [{status:15s}] {src}/{basename}")
    print(f"   entities: {ents}")
    if not matches:
        print(f"   ⚠️  ORPHAN — no product with ≥{threshold} entity hits")
        return
    if len(matches) > 1:
        print(f"   🔀 FAN-OUT candidates ({len(matches)}):")
    else:
        print(f"   🎯 TARGET:")
    for m_ in matches:
        pairs = ", ".join(f"{e}→{t}({w:.2f})" for e, t, w in m_.matched_pairs)
        print(f"      • {m_.product.slug} (score={m_.score:.2f}, hits={m_.hits}): {pairs}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 4 Phase 1 routing")
    ap.add_argument("meta_path", nargs="?", type=Path, help="meta.json path (omit with --all-w)")
    ap.add_argument("--all-w", metavar="YYYY-Www", help="route all approved/pending-review in a week")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()

    products = load_products()
    print(f"Loaded {len(products)} active products: {[p.slug for p in products]}")

    paths: list[Path] = []
    if args.all_w:
        for p in sorted(RAW_DIR.glob(f"*/{args.all_w}/*.meta.json")):
            m = json.loads(p.read_text())
            if m.get("ingest_status") in ROUTABLE_STATUSES:
                paths.append(p)
    elif args.meta_path:
        paths = [args.meta_path]
    else:
        ap.error("provide meta_path or --all-w")

    # summary stats
    stats = {"routed": 0, "fanout": 0, "orphan": 0}
    for p in paths:
        m = json.loads(p.read_text())
        matches = route(m.get("key_entities", []), products, threshold=args.threshold)
        print_route(p, matches, args.threshold)
        if not matches:
            stats["orphan"] += 1
        elif len(matches) > 1:
            stats["fanout"] += 1
            stats["routed"] += 1
        else:
            stats["routed"] += 1

    print(f"\n{'═' * 60}")
    print(f" ROUTING SUMMARY ({len(paths)} articles, threshold={args.threshold})")
    print(f"{'═' * 60}")
    print(f"   routed (≥1 target):  {stats['routed']}")
    print(f"     fan-out (>1):      {stats['fanout']}")
    print(f"   orphan (no target):  {stats['orphan']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
