#!/usr/bin/env python3
"""
RetailIQ Lint Agent v0 — validates /raw/ against AGENTS.md §6 + §8.4 + §8.9.
Run: python3 scripts/lint.py
"""
import os, json, glob, re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = str(ROOT / "raw")

REQUIRED_META_FIELDS = {
    "source_url", "source_type", "source_tier", "source_title",
    "fetched_at", "fetched_by", "content_hash", "content_type",
    "content_size_bytes", "locale", "ingest_status",
}
OPTIONAL_SINCE_V17 = {
    "relevance_score", "relevance_reasoning", "relevance_breakdown", "key_entities"
}
VALID_TIERS = {"T1", "T2", "T2-filtered", "T3"}
VALID_STATUS = {
    "pending", "scoring", "approved", "pending-review",
    "processed", "skipped-duplicate", "skipped-filtered",
    "skipped-low-relevance", "failed"
}

# §8.9 URL filters
URL_FILTERS = {
    "macrumors": {
        "allow": re.compile(r"^https://www\.macrumors\.com/(review|roundup|how-to)/"),
        "deny":  re.compile(r"^https://www\.macrumors\.com/(rumors|news)/"),
    },
    "9to5mac": {
        "allow": re.compile(r"^https://9to5mac\.com/"),  # 9to5Mac 路徑是日期/slug 形式
        "deny":  re.compile(r"^https://9to5mac\.com/category/rumors/"),
    },
}

errors = []
warnings = []
info = []

# ───────────────────────────────────────────
# Pass 1: Meta 檔案完整性（§8.4）
# ───────────────────────────────────────────
meta_files = glob.glob(os.path.join(RAW, "*/2026-W18/*.meta.json"))
raw_companions = glob.glob(os.path.join(RAW, "*/2026-W18/*.html"))

meta_count = len(meta_files)
print(f"🔍 PASS 1 · Meta Schema Check（§8.4）")
print(f"   Found {meta_count} meta files")

status_dist = defaultdict(int)
tier_dist = defaultdict(int)
source_scores = defaultdict(list)

for mf in sorted(meta_files):
    rel = os.path.relpath(mf, ROOT)
    try:
        with open(mf) as f:
            meta = json.load(f)
    except Exception as e:
        errors.append(f"[PARSE] {rel}: cannot parse JSON ({e})")
        continue

    # 必要欄位
    missing = REQUIRED_META_FIELDS - set(meta.keys())
    if missing:
        errors.append(f"[SCHEMA] {rel}: missing fields {missing}")

    # Tier 驗證
    tier = meta.get("source_tier")
    if tier not in VALID_TIERS:
        errors.append(f"[TIER] {rel}: invalid source_tier={tier!r}")
    else:
        tier_dist[tier] += 1

    # Status 驗證
    status = meta.get("ingest_status")
    if status not in VALID_STATUS:
        errors.append(f"[STATUS] {rel}: invalid ingest_status={status!r}")
    else:
        status_dist[status] += 1

    # Content hash 格式
    h = meta.get("content_hash", "")
    if not re.match(r"^sha256:[0-9a-f]{64}$", h):
        errors.append(f"[HASH] {rel}: malformed content_hash={h[:30]}...")

    # v1.7 relevance fields（T1/admin 可缺；其他必須有）
    if tier != "T1" and meta.get("source_type") != "admin-upload":
        if "relevance_score" not in meta:
            warnings.append(
                f"[RELEVANCE] {rel}: missing relevance_score "
                f"(T2/T3 should have it; see _relevance-scores-2026-W18.json companion)"
            )

    # 對應原始檔案存在性
    basename = os.path.basename(mf).replace(".meta.json", "")
    folder = os.path.dirname(mf)
    has_html = os.path.exists(os.path.join(folder, f"{basename}.html"))
    has_txt = os.path.exists(os.path.join(folder, f"{basename}.txt"))
    if not has_html and not has_txt:
        warnings.append(f"[ORPHAN META] {rel}: no sibling .html/.txt found")

    # fetched_at 合理性
    try:
        fetched = datetime.fromisoformat(meta["fetched_at"])
        age_days = (datetime.now(timezone(timedelta(hours=8))) - fetched).days
        if age_days > 7 and status == "pending":
            warnings.append(f"[STALE] {rel}: pending > 7 days ({age_days}d)")
    except Exception:
        warnings.append(f"[FETCHED_AT] {rel}: unparseable fetched_at")

# ───────────────────────────────────────────
# Pass 2: §8.9 URL 過濾器驗證
# ───────────────────────────────────────────
print(f"\n🔍 PASS 2 · URL Filter Check（§8.9）")

for mf in meta_files:
    with open(mf) as f: meta = json.load(f)
    src = meta.get("source_type")
    url = meta.get("source_url", "")
    rel = os.path.relpath(mf, ROOT)
    if src in URL_FILTERS:
        rules = URL_FILTERS[src]
        if rules["deny"].match(url):
            errors.append(f"[URL DENY] {rel}: URL matches deny pattern ({url[:80]})")
        if src == "macrumors" and not rules["allow"].match(url):
            # MacRumors 要求 URL 符合 allow (review/roundup/how-to)
            errors.append(f"[URL ALLOW] {rel}: MacRumors URL does not match allow pattern")

# ───────────────────────────────────────────
# Pass 3: 相關性分數（§8.10）— 讀 companion file
# ───────────────────────────────────────────
print(f"\n🔍 PASS 3 · Relevance Scores（§8.10）")

rel_file = os.path.join(RAW, "_relevance-scores-2026-W18.json")
if os.path.exists(rel_file):
    with open(rel_file) as f: rel_data = json.load(f)
    entries = rel_data.get("entries", {})
    print(f"   Companion scores: {len(entries)} entries")

    for key, e in entries.items():
        source = key.split("/")[0]
        source_scores[source].append(e["relevance_score"])

    # Per-source health
    print(f"   Per-source average (§8.10.4 warning if < 5):")
    for src, scores in sorted(source_scores.items()):
        avg = sum(scores) / len(scores) if scores else 0
        flag = "🔴" if avg < 5 else ("🟡" if avg < 7 else "🟢")
        print(f"     {flag} {src:25s}  avg={avg:4.1f}  n={len(scores)}")
        if avg < 5:
            warnings.append(f"[LOW-RELEVANCE SOURCE] {src}: avg={avg:.1f} (< 5), see §8.10.4")
else:
    warnings.append(f"[COMPANION] _relevance-scores-2026-W18.json not found")
    rel_data = {"entries": {}}  # #19: 防止 Pass 4 NameError

# ───────────────────────────────────────────
# Pass 4: Pending review backlog
# ───────────────────────────────────────────
pending_review_count = sum(1 for e in rel_data.get("entries", {}).values()
                           if e.get("ingest_status_override") == "pending-review")
if pending_review_count >= 20:
    warnings.append(f"[PENDING-REVIEW BACKLOG] {pending_review_count} files await human review (≥20 threshold)")

# ───────────────────────────────────────────
# Summary
# ───────────────────────────────────────────
print(f"\n{'='*60}")
print(f"📊 Status distribution: {dict(status_dist)}")
print(f"📊 Tier distribution: {dict(tier_dist)}")
print(f"{'='*60}")
print(f"\n❌ ERRORS ({len(errors)}):")
for e in errors: print(f"  {e}")
print(f"\n⚠️  WARNINGS ({len(warnings)}):")
for w in warnings[:30]: print(f"  {w}")
if len(warnings) > 30:
    print(f"  ... +{len(warnings)-30} more")

print(f"\n{'='*60}")
if not errors:
    print(f"✅ LINT PASSED (no blocking errors; {len(warnings)} warnings)")
else:
    print(f"❌ LINT FAILED: {len(errors)} error(s) must be fixed")
