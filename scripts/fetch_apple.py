#!/usr/bin/env python3
"""Fetch real Apple Newsroom + apple-com-tw pages."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pre_w2_crawler import save_article, fetch, RAW_DIR

TARGETS_NEWSROOM = [
    ("Behind Kyle Hanagami's viral dance creations edited with Final Cut Pro",
     "https://www.apple.com/newsroom/2026/01/behind-kyle-hanagamis-viral-dance-creations-edited-with-final-cut-pro/"),
    ("Mapping the future with 3D-printed titanium Apple Watch cases",
     "https://www.apple.com/newsroom/2025/11/mapping-the-future-with-3d-printed-titanium-apple-watch-cases/"),
]

TARGETS_APPLE_COM_TW = [
    ("iPhone 17 Pro - Apple (台灣)", "https://www.apple.com/tw/iphone-17-pro/", "zh-TW"),
    ("MacBook Neo - Apple (台灣)", "https://www.apple.com/tw/macbook-neo/", "zh-TW"),
]

TARGETS_APPLE_SUPPORT = [
    ("iPhone 17 Pro 規格", "https://support.apple.com/zh-tw/121029", "zh-TW"),
    ("關於 Apple Intelligence", "https://support.apple.com/zh-tw/121115", "zh-TW"),
]

print("=== apple-newsroom-en (T1) ===")
for title, url in TARGETS_NEWSROOM:
    item = {"title": title, "link": url, "pubDate": "", "description": ""}
    basename, err = save_article("apple-newsroom-en", "T1", item)
    print(f"  {'✓' if not err else '✗'} {basename or err}")

print("\n=== apple-com-tw (T1) ===")
for title, url, locale in TARGETS_APPLE_COM_TW:
    item = {"title": title, "link": url, "pubDate": "", "description": ""}
    basename, err = save_article("apple-com-tw", "T1", item)
    if basename:
        # Patch locale to zh-TW (the script defaults to en-US)
        meta_path = os.path.join(RAW_DIR, "apple-com-tw", "2026-W18", f"{basename}.meta.json")
        try:
            with open(meta_path) as f: m = json.load(f)
            m["locale"] = locale
            with open(meta_path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(meta_path + ".tmp", meta_path)
        except Exception as e:
            print(f"    locale patch failed: {e}")
    print(f"  {'✓' if not err else '✗'} {basename or err}")

print("\n=== apple-support (T1) ===")
for title, url, locale in TARGETS_APPLE_SUPPORT:
    item = {"title": title, "link": url, "pubDate": "", "description": ""}
    basename, err = save_article("apple-support", "T1", item)
    if basename:
        meta_path = os.path.join(RAW_DIR, "apple-support", "2026-W18", f"{basename}.meta.json")
        try:
            with open(meta_path) as f: m = json.load(f)
            m["locale"] = locale
            with open(meta_path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            os.replace(meta_path + ".tmp", meta_path)
        except Exception as e:
            print(f"    locale patch failed: {e}")
    print(f"  {'✓' if not err else '✗'} {basename or err}")
