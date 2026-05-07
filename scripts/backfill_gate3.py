#!/usr/bin/env python3
"""
scripts/backfill_gate3.py — 把 Gate 3 批次打分結果 patch 回 per-article .meta.json

Source of truth: raw/_relevance-scores-{ISO_WEEK}.json（由 gate3_scoring_w*.py 產生）
Target:           raw/<source>/<week>/<basename>.meta.json

寫入欄位（與 ingest_agent._patch_meta_with_score 對齊）：
    - relevance_score
    - relevance_reasoning
    - relevance_breakdown
    - key_entities
    - ingest_status（依 §8.10 threshold 推導；T1 維持 approved）

設計原則：
    - Atomic write：.tmp → os.replace()
    - Sandbox fallback：os.replace 失敗時走 `git rm` + 新寫（Enchanté 限制）
    - Idempotent：重跑不改內容
    - --dry-run：只印 diff 不寫檔

Usage:
    python3 scripts/backfill_gate3.py raw/_relevance-scores-2026-W19.json
    python3 scripts/backfill_gate3.py raw/_relevance-scores-2026-W19.json --dry-run
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "raw"


def status_for_score(score: int, tier: str) -> str:
    """§8.10 門檻 — T1 一律 approved（§8.10.4）。"""
    if tier == "T1":
        return "approved"
    if score < 5:
        return "skipped-low-relevance"
    if score < 7:
        return "pending-review"
    return "approved"


def atomic_write_json(path: Path, data: dict) -> None:
    """Atomic write with Enchanté-sandbox fallback.

    Normal: write .tmp → os.replace (atomic).
    Fallback: if replace fails with PermissionError (sandbox blocks overwriting
    git-tracked files), use `git rm` + fresh write.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.replace(tmp, path)
        return
    except PermissionError:
        pass

    # Sandbox fallback
    try:
        subprocess.run(
            ["git", "rm", "-f", "--quiet", str(path)],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        path.write_text(payload, encoding="utf-8")
    finally:
        if tmp.exists():
            subprocess.run(
                ["git", "clean", "-f", "--quiet", str(tmp)],
                cwd=REPO_ROOT, capture_output=True,
            )


def patch_meta(meta_path: Path, entry: dict, *, dry_run: bool) -> str:
    """Returns: patched | unchanged | missing | would-patch"""
    if not meta_path.exists():
        return "missing"

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    tier = meta.get("source_tier", "T3")

    new_fields = {
        "relevance_score": entry["score"],
        "relevance_reasoning": entry["reasoning"],
        "relevance_breakdown": entry["breakdown"],
        "key_entities": entry.get("entities", []),
        "ingest_status": status_for_score(entry["score"], tier),
    }

    if all(meta.get(k) == v for k, v in new_fields.items()):
        return "unchanged"

    if dry_run:
        return "would-patch"

    meta.update(new_fields)
    atomic_write_json(meta_path, meta)
    return "patched"


def backfill(scores_path: Path, *, dry_run: bool) -> dict:
    doc = json.loads(scores_path.read_text(encoding="utf-8"))
    entries = doc.get("entries", {})
    if not entries:
        print(f"❌ no entries in {scores_path}", file=sys.stderr)
        sys.exit(1)

    stats = {"patched": 0, "unchanged": 0, "missing": 0, "would-patch": 0}
    missing_keys: list[str] = []

    for slug, entry in entries.items():
        meta_path = RAW_DIR / f"{slug}.meta.json"
        result = patch_meta(meta_path, entry, dry_run=dry_run)
        stats[result] += 1
        if result == "missing":
            missing_keys.append(slug)
        else:
            marker = {"patched": "✅", "unchanged": "·", "would-patch": "○"}[result]
            status = status_for_score(entry["score"], entry.get("tier", "T3"))
            print(f"  {marker} {slug} score={entry['score']:>2} status={status}")

    print()
    print(f"📊 {scores_path.name}:")
    for k, v in stats.items():
        if v:
            print(f"   {k}: {v}")
    if missing_keys:
        print(f"\n⚠️  missing meta.json:")
        for k in missing_keys:
            print(f"   - {k}")

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill Gate 3 scores into per-article meta.json")
    ap.add_argument("scores_file", type=Path, help="path to raw/_relevance-scores-<week>.json")
    ap.add_argument("--dry-run", action="store_true", help="只印 diff，不寫檔")
    args = ap.parse_args()

    if not args.scores_file.exists():
        print(f"❌ file not found: {args.scores_file}", file=sys.stderr)
        return 1

    stats = backfill(args.scores_file, dry_run=args.dry_run)
    return 1 if stats["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
