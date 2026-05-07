#!/usr/bin/env python3
"""
Precise hash dedup test: take an existing .meta.json and try to re-process
the same URL. Should detect identical content_hash and mark as
skipped-duplicate per AGENTS.md §8.5 Gate 1.
"""
import os, sys, json, hashlib, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pre_w2_crawler import fetch, sha256_of, extract_text_from_html, RAW_DIR

ROOT = os.path.expanduser("~/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728")
RAW = os.path.join(ROOT, "raw")

# Simulate Gate 1 logic from §8.5
def would_skip_as_duplicate(new_hash: str, source_url: str) -> bool:
    """Walk all existing meta files; return True if matching URL+hash found."""
    for mf in glob.glob(os.path.join(RAW, "*/2026-W??/*.meta.json")):
        try:
            with open(mf) as f:
                m = json.load(f)
            if m["source_url"] == source_url and m["content_hash"] == new_hash:
                return True, mf
        except Exception:
            continue
    return False, None

# Pick the iPhone 17 Pro meta to re-test
target_meta = os.path.join(RAW, "apple-com-tw/2026-W18/iphone-17-pro-apple_20260430.meta.json")
if not os.path.exists(target_meta):
    print(f"❌ Target not found: {target_meta}")
    sys.exit(1)

with open(target_meta) as f:
    meta = json.load(f)

print(f"🔬 Hash Dedup Test")
print(f"  Target URL: {meta['source_url']}")
print(f"  Stored hash: {meta['content_hash'][:30]}...")

# Re-fetch same URL
print(f"  Re-fetching...")
try:
    html = fetch(meta['source_url'])
except Exception as e:
    print(f"  ❌ Fetch failed: {e}")
    sys.exit(1)

# Compute hash of extracted text (same method as original)
text = extract_text_from_html(html)
new_hash = sha256_of(text)
print(f"  New hash:    {new_hash[:30]}...")

# Compare
if new_hash == meta['content_hash']:
    print(f"\n  ✅ HASHES MATCH → Gate 1 would mark as 'skipped-duplicate'")
    print(f"     (原本 content 未變更，不觸發 ingest)")
else:
    print(f"\n  ⚠️  HASHES DIFFER → new content detected")
    print(f"     This would be processed as an update")
    # 嘗試找差異
    old_txt_path = target_meta.replace(".meta.json", ".txt")
    if os.path.exists(old_txt_path):
        with open(old_txt_path, encoding="utf-8") as f:
            old_text = f.read()
        print(f"\n     Old text length: {len(old_text)}")
        print(f"     New text length: {len(text)}")
        # Find first diff
        for i, (a, b) in enumerate(zip(old_text, text)):
            if a != b:
                print(f"     First diff @ char {i}: old={old_text[i:i+40]!r} vs new={text[i:i+40]!r}")
                break

# Test simulated duplicate (feed same hash back)
dup, match_file = would_skip_as_duplicate(meta['content_hash'], meta['source_url'])
print(f"\n🔬 Simulated duplicate detection (§8.5 Gate 1 logic):")
if dup:
    print(f"  ✅ Duplicate detected: {os.path.relpath(match_file, ROOT)}")
    print(f"  → Ingest Agent would set ingest_status='skipped-duplicate'")
else:
    print(f"  ❌ Not detected (something wrong with logic)")
