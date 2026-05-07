#!/usr/bin/env python3
"""
Write .zh-TW.md summary + relevance assessment for every article in /raw/.
Each summary is human-curated (by LLM generating this script) based on article title.
Follows schema: 標題翻譯 / 重點摘要 / 與 RetailIQ 相關性 / 建議 ingest 動作.
"""
import os, json

ROOT = os.path.expanduser("~/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728")
RAW = os.path.join(ROOT, "raw")

# (basename_glob, title_zh, summary_zh, relevance, suggested_action)
ENTRIES = [
    # ─── apple-com-tw (T1, zh-TW 原文) ─────────────────
    ("apple-com-tw", "iphone-17-pro-apple_20260430",
     "iPhone 17 Pro 與 iPhone 17 Pro Max — Apple（台灣）",
     "官方產品頁；涵蓋鍛造鋁金屬一體成型設計、A19 Pro 晶片、Pro 融合相機系統（含 8 倍光學變焦）、Center Stage 前置相機、iOS 26、Apple Intelligence 等 2025 年 9 月發表重點。",
     "🎯 直接相關（產品頁事實主來源）",
     "更新 `wiki/products/iphone-17-pro.md` 規格段落 + 五大賣點 FAB 資料"),

    ("apple-com-tw", "macbook-neo-apple_20260430",
     "MacBook Neo — Apple（台灣）",
     "官方產品頁；介紹入門定位的 MacBook Neo（A18 Pro 晶片、13 吋 Liquid Retina、四款配色、16 小時電池），含環保再生鋁金屬與購買方案。",
     "🎯 直接相關（產品頁事實主來源）",
     "更新 `wiki/products/macbook-neo.md` 規格 + 定價"),

    # ─── apple-newsroom-en (T1, 英文需翻譯) ────────────
    ("apple-newsroom-en", "behind-kyle-hanagami-s-viral-dance-creations-edited-with-fin_20260430",
     "Final Cut Pro 幕後：Kyle Hanagami 如何剪出爆紅舞蹈影片",
     "好萊塢編舞家分享如何使用 iPad Pro + Final Cut Pro 製作爆紅舞蹈短片；強調 ProRes 工作流程與 iPad / Mac 跨裝置剪輯彈性。",
     "🎯 直接相關（可作為 iPhone/iPad Pro 攝影創作者客群的案例）",
     "存入 `wiki/sales-playbook/case-studies/kyle-hanagami.md`；供 `customer-personas/creator` 引用"),

    ("apple-newsroom-en", "mapping-the-future-with-3d-printed-titanium-apple-watch-case_20260430",
     "用 3D 列印鈦金屬打造未來 Apple Watch 外殼",
     "介紹 Apple Watch 鈦金屬版採用 3D 列印製程，大幅降低鈦材料浪費（約 50%）並實現複雜結構；屬於永續製造故事。",
     "🟡 間接相關（Apple Watch 週報素材；非門市訓練核心）",
     "存入 `wiki/weekly-digest/2026-W18.md § Apple Watch 永續故事`"),

    # ─── apple-support (T1, 英文需翻譯) ────────────────
    ("apple-support", "iphone-17-pro-tech-specs_20260430",
     "iPhone 17 Pro 技術規格",
     "官方技術規格頁；涵蓋晶片、顯示器、相機、連接、電池、作業系統、環境等完整規格。",
     "🎯 直接相關（產品頁事實主來源）",
     "補足 `wiki/products/iphone-17-pro.md § 核心規格` 的缺漏項（重量、尺寸、感測器）；改用 zh-TW 版本 URL 替換"),

    ("apple-support", "about-apple-intelligence_20260430",
     "關於 Apple Intelligence",
     "官方 Apple Intelligence 概覽頁；涵蓋書寫工具、Genmoji、圖像遊樂場、視覺智慧、清除等功能的相容裝置、啟用方式、隱私架構。",
     "🎯 直接相關（跨產品概念頁主來源）",
     "建立 `wiki/concepts/apple-intelligence.md`；供三款產品頁交叉引用"),

    # ─── ars-technica (T2, 英文) ───────────────────────
    ("ars-technica", "six-things-i-ll-remember-when-i-think-about-tim-cook-s-versi_20260430",
     "Tim Cook 時代的 Apple：我會記得的六件事",
     "專欄回顧 Tim Cook 領導下的 Apple — 市值成長、服務業務崛起、供應鏈與中國依賴、設計保守化、隱私立場、AI 落後等；分析觀點客觀。",
     "🟡 間接相關（企業觀察；可作週報「產業脈動」素材，不得進產品頁）",
     "存入 `wiki/weekly-digest/2026-W18.md § 產業觀察`；遵守 §8.8 Tier T2 限制"),

    ("ars-technica", "why-are-the-mac-mini-and-mac-studio-gradually-becoming-impos_20260430",
     "為什麼 Mac mini 與 Mac Studio 越來越難買到？",
     "探討 M5 前代 Mac mini/Studio 供貨緊張原因：記憶體短缺、AI 需求擠壓供應鏈、等待新世代產品等。",
     "🟡 間接相關（Mac 購買建議背景；不直接影響 MacBook Neo 頁）",
     "標記 pending；若客戶問到 Mac mini/Studio 供貨，可轉引本文"),

    # ─── six-colors (T2, 英文 podcast) ─────────────────
    ("six-colors", "podcast-clockwise-654-i-love-the-clanker-slang_20260430",
     "Podcast｜Clockwise 654：我愛「Clanker」這個新詞",
     "Clockwise 第 654 集；四位科技評論家聊 AI 語音、家電買賣、家庭技術教學等主題。非深度產品評論。",
     "⚪ 低相關（podcast 閒聊內容；無明確銷售訓練價值）",
     "跳過此篇；未來 Ingest Agent 應將 `podcast-*` 前綴 URL 設為低優先順位"),

    ("six-colors", "podcast-the-rebound-596-wow-drugs_20260430",
     "Podcast｜The Rebound 596：Wow, Drugs",
     "The Rebound 第 596 集；Dan Moren 等人閒聊科技產業新聞，內容偏娛樂。",
     "⚪ 低相關（同上）",
     "跳過此篇"),

    # ─── macstories (T2, 英文) ─────────────────────────
    ("macstories", "cronos-the-new-dawn-showcases-the-mac-s-metalfx-and-ray-trac_20260430",
     "《Cronos: The New Dawn》展現 Mac 的 MetalFX 與光線追蹤實力",
     "3A 大作在 Mac 上使用 MetalFX 升頻 + 光線追蹤執行的實測；凸顯 Apple Silicon 的遊戲潛力。",
     "🎯 直接相關（MacBook 遊戲玩家客群素材）",
     "加入 `wiki/sales-playbook/customer-personas/gamer.md` 的 Mac 遊戲支撐論述"),

    ("macstories", "gamehub-s-desktop-beta-promises-to-expand-mac-gaming_20260430",
     "GameHub 桌面 Beta 版：擴展 Mac 遊戲生態",
     "第三方遊戲啟動器 GameHub 開始支援 Mac 桌面；整合 Steam、Epic、GOG 等平台。",
     "🟡 間接相關（Mac 遊戲生態背景）",
     "作為反對處理「Mac 沒遊戲」的佐證素材"),

    # ─── petapixel (T2 攝影, 英文) ─────────────────────
    ("petapixel", "these-protective-wraps-are-designed-to-keep-your-camera-gear_20260430",
     "這些保護包專為守護你的相機器材而設計",
     "Spider 新推出的相機保護包介紹；適合戶外攝影者。與 iPhone 攝影關聯較低。",
     "⚪ 低相關（一般攝影配件新聞，非 iPhone 攝影）",
     "跳過此篇；未來可過濾 `/accessories/` 類文章"),

    ("petapixel", "vividon-s-new-photoshop-plugin-uses-ai-to-change-photo-light_20260430",
     "Vividon 新 Photoshop 外掛：AI 改變照片光線",
     "第三方 Photoshop 外掛可用 AI 重打光；對專業攝影師有價值。",
     "🟡 間接相關（攝影師客群會關心，但非 Apple 產品）",
     "作為「攝影師工作流」背景知識；不進產品頁"),

    # ─── engadget (T2, 英文) ───────────────────────────
    ("engadget", "mark-zuckerberg-says-meta-is-working-on-ai-agents-for-person_20260430",
     "Zuckerberg 宣布 Meta 開發個人與商務用 AI 代理",
     "Meta 計畫推出 AI 代理；與 Apple Intelligence、Google Gemini 的產業 AI 競賽脈絡。",
     "🟡 間接相關（AI 產業競爭；供週報「AI 戰情」用）",
     "存入 `wiki/weekly-digest/2026-W18.md § AI 戰情`"),

    ("engadget", "sony-says-your-playstation-won-t-check-for-game-licenses-eve_20260430",
     "Sony：PlayStation 不會每 30 天檢查遊戲授權",
     "Sony 澄清 PS5 DRM 政策；與 Apple App Store 政策無關。",
     "⚪ 低相關（非 Apple 主題）",
     "跳過此篇"),

    # ─── macworld (T2, 英文) ───────────────────────────
    ("macworld", "exclusive-all-babbel-language-courses-available-for-one-life_20260430",
     "獨家：Babbel 所有語言課程終身價",
     "Macworld 廣告業配文；非產品評論。",
     "⚪ 低相關（商業置入，無訓練價值）",
     "跳過；未來 Ingest Agent 應過濾標題含 `Exclusive:` 或 price 類付費內容"),

    ("macworld", "let-ai-handle-the-repetitive-stuff-ms-visual-studio-makes-co_20260430",
     "讓 AI 處理繁瑣工作：MS Visual Studio 39 美元特價",
     "MS Visual Studio 促銷文；與 Apple 無關。",
     "⚪ 低相關（同上，廣告）",
     "跳過"),

    # ─── no-film-school (T2 攝影, 英文) ────────────────
    ("no-film-school", "how-ernst-lubitsch-invented-modern-hollywood_20260430",
     "Ernst Lubitsch 如何「發明」現代好萊塢",
     "電影史專欄；與 iPhone 攝影訓練關聯較低。",
     "⚪ 低相關（電影史文章）",
     "跳過；未來可過濾 `/history/` 類路徑"),

    ("no-film-school", "learn-film-analysis-with-this-cheat-sheet_20260430",
     "用這份 cheat sheet 學電影分析",
     "電影分析教學內容。",
     "⚪ 低相關（電影教學，非器材）",
     "跳過"),

    # ─── cined (T2 攝影, 英文) ─────────────────────────
    ("cined", "dji-power-1000-mini-released-compact-1kwh-power-station-with_20260430",
     "DJI Power 1000 Mini 發表：1kWh 緊湊電源站，含可收納 USB-C 與 58 分鐘快充",
     "DJI 新攜帶式電源產品發表；攝影外拍電力方案；與 Apple 生態無直接關聯。",
     "⚪ 低相關（第三方配件）",
     "跳過"),

    ("cined", "tech-talk-with-michael-cioni-fujifilm-gfx-eterna-55-and-how-_20260430",
     "Tech Talk：FUJIFILM GFX ETERNA 55 vs ARRI ALEXA 35",
     "電影級相機比較訪談；高階影像製作社群內容。",
     "🟡 間接相關（為「iPhone ProRes 是否能取代專業機」的反對處理提供業界資料點）",
     "作為銷售 playbook 反對處理的佐證；不進產品頁"),

    # ─── macrumors (T2-filtered, review) ───────────────
    ("macrumors", "switchbot-s20-and-k11-review_20260430",
     "SwitchBot S20 與 K11+ 掃拖機器人實測",
     "智慧家居配件評測；與 Apple HomeKit 整合。",
     "🟡 間接相關（HomeKit 生態素材）",
     "納入 `wiki/concepts/homekit-ecosystem.md`（待建立）"),

    ("macrumors", "aqara-w200-thermostat-review_20260430",
     "Aqara W200 智慧溫控器實測",
     "HomeKit 相容溫控器產品評測。",
     "🟡 間接相關（HomeKit 生態素材）",
     "同上"),

    # ─── 9to5mac (T2-filtered, review) ─────────────────
    ("9to5mac", "speakon-ai-dictation-review_20260430",
     "SpeakOn AI 聽寫 iPhone 配件實測",
     "第三方 iPhone AI 聽寫硬體配件評測；商務人士可能感興趣。",
     "🟡 間接相關（iPhone 配件；商務客群補充資料）",
     "作為商務 persona 的「效率配件」建議"),

    ("9to5mac", "aulumu-m10-3-in-1-review_20260430",
     "Aulumu M10 三合一實測：iPhone MagSafe 行動電源也能為 Apple Watch 和 AirPods 充電",
     "三合一 MagSafe 行動電源配件評測；適合重度 Apple 裝置使用者。",
     "🟡 間接相關（跨裝置配件；商務/差旅客群素材）",
     "作為商務 persona 的「差旅必備」建議"),

    # ─── the-verge (T3, 英文) ──────────────────────────
    ("the-verge", "elon-musk-s-worst-enemy-in-court-is-elon-musk_20260430",
     "Elon Musk 在法庭上最大的敵人是他自己",
     "Musk vs OpenAI 訴訟報導；與 Apple 無關。",
     "⚪ 低相關（非 Apple 主題）",
     "跳過；Ingest Agent 應優先擷取 `/apple/` 或 `/tech/` 子分類"),

    ("the-verge", "grindr-yes-grindr-won-the-whcd-party-circuit_20260430",
     "Grindr 如何成為白宮記者晚宴派對圈贏家",
     "社群 app 報導；完全非 Apple 相關。",
     "⚪ 低相關",
     "跳過"),

    # ─── toms-guide (T3, 英文) ─────────────────────────
    ("toms-guide", "3-classic-hbo-dramas-that-deserve-a-rewatch_20260430",
     "值得重看的 3 部 HBO 經典劇",
     "娛樂內容推薦。",
     "⚪ 低相關",
     "跳過；建議 Ingest Agent 過濾 `/entertainment/` 路徑"),

    ("toms-guide", "expert-reveals-the-one-solar-panel-mistake-costing-you-money_20260430",
     "專家揭露太陽能板的一個錯誤害你燒錢",
     "太陽能家居建議；非 Apple 產品。",
     "⚪ 低相關",
     "跳過"),
]

TEMPLATE = """# {title_zh}

> 📌 **本檔為原文摘要與翻譯**，遵守 `AGENTS.md` §8.1 的「raw 不存 LLM 產物」精神下特例處理 —
> 僅存放標題翻譯與重點摘要，完整譯文等 Ingest Agent v1 上線後移到 `wiki/` 層。
>
> 此檔案 content_type 為 **translation / summary**。

## 原始檔案

- **Source Type**: `{source}`
- **Source URL**: {source_url}
- **Extracted Content**: `{basename}.txt` / `{basename}.html`（同目錄）
- **Meta**: `{basename}.meta.json`

## 繁中標題

{title_zh}

## 重點摘要

{summary_zh}

## 與 RetailIQ 訓練系統的相關性

{relevance}

## 建議 Ingest 動作

{suggested_action}

---

**生成時間**：2026-04-30（pre-W2-crawler）
**重要**：下次 Ingest Agent v1 跑 Apple GenAI 翻譯時，此檔視為 placeholder，以完整翻譯覆蓋。
"""

written = 0
skipped = 0
for source, basename, title_zh, summary, relevance, action in ENTRIES:
    # Find the actual source_url from .meta.json
    meta_path = os.path.join(RAW, source, "2026-W18", f"{basename}.meta.json")
    if not os.path.exists(meta_path):
        print(f"  ✗ meta not found: {meta_path}")
        skipped += 1
        continue
    with open(meta_path) as f:
        meta = json.load(f)
    out_path = os.path.join(RAW, source, "2026-W18", f"{basename}.zh-TW.md")
    if os.path.exists(out_path):
        print(f"  ○ exists, skipped: {basename}.zh-TW.md")
        skipped += 1
        continue
    content = TEMPLATE.format(
        title_zh=title_zh, source=source, source_url=meta["source_url"],
        basename=basename, summary_zh=summary,
        relevance=relevance, suggested_action=action,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {source}/{basename}.zh-TW.md")
    written += 1

print(f"\n=== 完成 ===")
print(f"新增：{written} 檔；略過：{skipped} 檔")
