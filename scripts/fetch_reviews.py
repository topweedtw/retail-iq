#!/usr/bin/env python3
"""Fetch specific URLs for T2-filtered sources where RSS was mostly news/rumors."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pre_w2_crawler import save_article, fetch, extract_text_from_html

# Manually-picked review/guide URLs
TARGETS = [
    ("macrumors", "T2-filtered", [
        ("SwitchBot S20 and K11+ review", "https://www.macrumors.com/review/switchbot-s20-and-k11-plus/"),
        ("Aqara W200 Thermostat review", "https://www.macrumors.com/review/aqara-w200-thermostat/"),
    ]),
    ("9to5mac", "T2-filtered", [
        ("SpeakOn AI dictation review", "https://9to5mac.com/2026/04/27/key-takeaways-after-testing-out-speakon-an-ai-powered-dictation-iphone-accessory/"),
        ("Aulumu M10 3-in-1 review", "https://9to5mac.com/2026/04/27/aulumu-m10-3-in-1-iphone-magsafe-battery-also-recharges-apple-watch-and-airpods/"),
    ]),
]

for source_name, tier, targets in TARGETS:
    print(f"\n=== {source_name} (Tier {tier}) ===")
    for title, url in targets:
        item = {"title": title, "link": url, "pubDate": "", "description": ""}
        basename, err = save_article(source_name, tier, item)
        if err:
            print(f"  ✗ {title}: {err}")
        else:
            print(f"  ✓ {basename}")
