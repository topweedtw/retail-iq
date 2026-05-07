#!/usr/bin/env python3
"""
Workaround: sandbox blocks overwriting existing .meta.json files.
Instead, write ONE consolidated scores file at raw/_relevance-scores-2026-W18.json
that maps (source, basename) -> relevance fields.

Future Ingest Agent can merge this into per-file meta.json during W2 setup
(when running outside sandbox).
"""
import os, json, glob

ROOT = os.path.expanduser("~/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728")
RAW = os.path.join(ROOT, "raw")

# Schema: identical structure per entry
# key = "<source>/<basename>" where basename excludes .meta.json
# value = { relevance_score, relevance_reasoning, relevance_breakdown, key_entities, ingest_status_override }

ENTRIES = {}

# T1 auto 10
T1_SOURCES = ["apple-com-tw", "apple-newsroom-en", "apple-support"]
for source in T1_SOURCES:
    for meta_path in glob.glob(os.path.join(RAW, source, "2026-W18", "*.meta.json")):
        basename = os.path.basename(meta_path).replace(".meta.json", "")
        key = f"{source}/{basename}"
        ENTRIES[key] = {
            "relevance_score": 10,
            "relevance_reasoning": "T1 官方來源，預設滿分",
            "relevance_breakdown": {"d1_product_mention": 3, "d2_ecosystem": 2,
                                    "d3_training_potential": 3, "d4_timeliness": 2},
            "key_entities": [],
            "ingest_status_override": "approved"
        }

# T2/T3 manual scores (same as previous script)
SCORES = {
    ("ars-technica", "six-things-i-ll-remember"): (2, 2, 2, 1, "Tim Cook 時代回顧分析，觀點間接相關", ["Tim Cook", "Apple", "iPhone"]),
    ("ars-technica", "why-are-the-mac-mini"): (3, 1, 1, 2, "Mac 供貨議題，可用於客戶詢問 Mac mini 時", ["Mac mini", "Mac Studio", "RAM"]),
    ("six-colors", "podcast-clockwise-654"): (1, 1, 0, 1, "podcast 閒聊內容，無明確產品訓練價值", ["Clockwise", "podcast"]),
    ("six-colors", "podcast-the-rebound-596"): (1, 0, 0, 1, "娛樂 podcast 內容", ["The Rebound", "podcast"]),
    ("macstories", "cronos-the-new-dawn"): (2, 2, 3, 2, "Mac 3A 大作實測，MetalFX + 光線追蹤是銷售素材", ["Mac", "MetalFX", "Ray Tracing", "Cronos"]),
    ("macstories", "gamehub-s-desktop-beta"): (2, 1, 2, 2, "Mac 遊戲生態擴展，可作為「Mac 沒遊戲」反對處理素材", ["Mac", "GameHub", "Steam"]),
    ("petapixel", "these-protective-wraps"): (0, 0, 0, 1, "第三方相機配件，與 iPhone 無關", ["Spider", "camera wraps"]),
    ("petapixel", "vividon-s-new-photoshop-plugin"): (1, 0, 1, 2, "攝影工作流 AI 工具，攝影客群感興趣但非 Apple", ["Photoshop", "Vividon", "AI lighting"]),
    ("engadget", "mark-zuckerberg-says-meta"): (1, 0, 1, 2, "Meta AI 競爭，週報產業動態素材", ["Meta", "AI agents", "Zuckerberg"]),
    ("engadget", "sony-says-your-playstation"): (0, 0, 0, 1, "Sony PS5 議題，完全非 Apple", ["Sony", "PlayStation", "DRM"]),
    ("macworld", "exclusive-all-babbel"): (0, 0, 0, 1, "廣告業配，Babbel 語言課程", ["Babbel"]),
    ("macworld", "let-ai-handle-the-repetitive-stuff"): (0, 0, 0, 1, "廣告業配，MS Visual Studio 特價", ["MS Visual Studio", "AI coding"]),
    ("no-film-school", "how-ernst-lubitsch"): (0, 0, 0, 0, "電影史內容，與器材訓練無關", ["Ernst Lubitsch", "Hollywood"]),
    ("no-film-school", "learn-film-analysis"): (0, 0, 1, 1, "電影分析教學，可能間接提升內容創作者共鳴", ["film analysis"]),
    ("cined", "dji-power-1000-mini"): (0, 0, 0, 2, "DJI 電源配件，非 Apple 主題", ["DJI", "Power Station"]),
    ("cined", "tech-talk-with-michael-cioni"): (1, 1, 2, 2, "業界電影機比較，iPhone ProRes 定位反對處理素材", ["FUJIFILM", "ARRI", "ProRes", "cinema"]),
    ("macrumors", "switchbot-s20"): (2, 2, 1, 2, "HomeKit 配件實測，生態系素材", ["HomeKit", "SwitchBot", "Matter"]),
    ("macrumors", "aqara-w200-thermostat"): (2, 2, 1, 2, "HomeKit 溫控器實測，智慧家居生態", ["HomeKit", "Aqara", "Matter"]),
    ("9to5mac", "speakon-ai-dictation"): (3, 2, 2, 2, "iPhone AI 聽寫配件，商務 persona 素材", ["iPhone", "AI dictation", "SpeakOn"]),
    ("9to5mac", "aulumu-m10-3-in-1"): (3, 2, 2, 2, "iPhone MagSafe + Watch + AirPods 三合一充電，差旅素材", ["iPhone", "MagSafe", "Apple Watch", "AirPods"]),
    ("the-verge", "elon-musk-s-worst-enemy"): (0, 0, 0, 1, "Musk 訴訟報導，與 Apple 無關", ["Elon Musk", "OpenAI"]),
    ("the-verge", "grindr-yes-grindr-won"): (0, 0, 0, 1, "社群 app 白宮晚宴報導", ["Grindr", "WHCD"]),
    ("toms-guide", "3-classic-hbo-dramas"): (0, 0, 0, 1, "娛樂內容推薦，HBO 節目", ["HBO"]),
    ("toms-guide", "expert-reveals-the-one-solar-panel"): (0, 0, 0, 1, "太陽能家居建議，與 Apple 無關", ["solar panel"]),
}

def status_for_score(s):
    if s < 5: return "skipped-low-relevance"
    if s < 7: return "pending-review"
    return "approved"

for (source, pattern), (d1, d2, d3, d4, reasoning, entities) in SCORES.items():
    for meta_path in glob.glob(os.path.join(RAW, source, "2026-W18", f"*{pattern}*.meta.json")):
        basename = os.path.basename(meta_path).replace(".meta.json", "")
        key = f"{source}/{basename}"
        total = d1 + d2 + d3 + d4
        ENTRIES[key] = {
            "relevance_score": total,
            "relevance_reasoning": reasoning,
            "relevance_breakdown": {"d1_product_mention": d1, "d2_ecosystem": d2,
                                    "d3_training_potential": d3, "d4_timeliness": d4},
            "key_entities": entities,
            "ingest_status_override": status_for_score(total)
        }

# 寫到 raw root
out_path = os.path.join(RAW, "_relevance-scores-2026-W18.json")
payload = {
    "generated_at": "2026-04-30T22:00:00+08:00",
    "generated_by": "backfill_relevance.py (LLM-curated, pre-W2)",
    "scored_by": "manual-llm-curation",  # 正式版應為 apple-genai-v1 之類
    "agents_version": "v1.7",
    "note": "Sandbox prevents overwriting existing .meta.json files; this is a companion file. "
            "W2 Ingest Agent should merge these fields into each .meta.json on first run.",
    "entries": ENTRIES
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# 簡短報告
def dist():
    counts = {"approved": 0, "pending-review": 0, "skipped-low-relevance": 0}
    for v in ENTRIES.values():
        counts[v["ingest_status_override"]] = counts.get(v["ingest_status_override"], 0) + 1
    return counts

print(f"已寫入 {out_path}")
print(f"總檔數：{len(ENTRIES)}")
print("分數分布：")
for k, v in sorted(dist().items(), key=lambda x: -x[1]):
    print(f"  {k:30s}  {v:2d} 檔")

# Top / Bottom
by_score = sorted(ENTRIES.items(), key=lambda x: -x[1]["relevance_score"])
print("\nTop 5 高分：")
for k, v in by_score[:5]:
    print(f"  [{v['relevance_score']:2d}] {k}")
print("\nBottom 5 低分：")
for k, v in by_score[-5:]:
    print(f"  [{v['relevance_score']:2d}] {k}")
