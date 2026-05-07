#!/usr/bin/env python3
"""Complete remaining Apple fetches (MacBook Neo + Support). Skip overwrites."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pre_w2_crawler import save_article, RAW_DIR

TARGETS = [
    # (source, tier, title, url, locale)
    ("apple-com-tw", "T1", "MacBook Neo - Apple (台灣)", "https://www.apple.com/tw/macbook-neo/", "zh-TW"),
    ("apple-support", "T1", "iPhone 17 Pro tech specs",
     "https://support.apple.com/en-us/121029", "en-US"),
    ("apple-support", "T1", "About Apple Intelligence",
     "https://support.apple.com/en-us/121115", "en-US"),
]

for source, tier, title, url, locale in TARGETS:
    item = {"title": title, "link": url, "pubDate": "", "description": ""}
    basename, err = save_article(source, tier, item)
    if basename:
        # Patch locale by writing to a fresh .meta.json (should work as new file)
        meta_path = os.path.join(RAW_DIR, source, "2026-W18", f"{basename}.meta.json")
        try:
            with open(meta_path) as f: m = json.load(f)
            m["locale"] = locale
            # Write to new path then rename — works if original was just created
            tmp = meta_path + ".new"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(tmp, meta_path)
            print(f"  ✓ {source}/{basename} (locale={locale})")
        except Exception as e:
            print(f"  ⚠ {source}/{basename} saved but locale patch failed: {e}")
    else:
        print(f"  ✗ {source}: {err}")
