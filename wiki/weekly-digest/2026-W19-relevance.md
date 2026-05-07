---
type: digest
slug: 2026-W19-relevance
title: 2026-W19 來源相關性週報
period: 2026-W19 (2026-05-04 ~ 2026-05-10)
generated_at: 2026-05-06
generated_by: v0.2 Gate 3 real-LLM (gemini-2.5-flash-lite:latest)
agents_version: v1.9.4
---

# 📊 2026-W19 來源相關性週報

> 依 `AGENTS.md` §8.10.5 規範產出；**首份由 v0.2 Gate 3 自動打分的週報**（W18 為 pre-W2 手動版）。
> 本次打分尚未回寫進個別 `.meta.json`（研究性測跑）；完整 backfill 規劃見下方「後續動作」。

---

## 總覽

- **本週擷取總數**：27 篇（12 enabled 來源）
- **平均分數**：3.41 / 10（W18: 4.67 → W19: 3.41，**↓ 1.26**）
- **通過比例**：14%（4 / 27）← 健康度 🔴 **偏低**
- **LLM 成本**：28.5s 總耗時、1.06s/篇、27 篇約 13.5k tokens

### 分布

| 狀態 | 分數範圍 | 篇數 | 占比 |
|---|---|---|---|
| ✅ `approved` | 7–10 | 4 | 14% |
| 🟡 `pending-review` | 5–6 | 9 | 33% |
| ❌ `skipped-low-relevance` | 0–4 | 14 | 51% |

---

## 各來源健康度

| 來源 | Tier | 篇數 | 平均分 | 通過率 | W18 平均 | 趨勢 | 健康度 |
|---|---|---|---|---|---|---|---|
| apple-com-tw | T1 | 1 | 10.0 | 100% | 10.0 | → | 🟢 優 |
| ars-technica | T2 | 3 | 7.0 | 66% | 6.5 | ↑ | 🟢 優 |
| apple-newsroom-en | T1 | 2 | 6.0 | 0% | 10.0 | ⬇️ | 🟡 可 ⚠️ |
| macworld | T2 | 2 | 6.0 | 50% | 1.0 | ⬆️ | 🟡 可 |
| macstories | T2 | 3 | 5.0 | 0% | 8.0 | ⬇️ | 🟡 可 |
| toms-guide | T3 | 2 | 4.5 | 0% | 1.0 | ↑ | 🟡 可 |
| six-colors | T2 | 4 | 2.2 | 0% | 2.0 | → | 🔴 差 |
| cined | T2 攝影 | 2 | 1.5 | 0% | 4.0 | ⬇️ | 🔴 差 |
| petapixel | T2 攝影 | 2 | 0.5 | 0% | 2.5 | ⬇️ | 🔴 差 |
| engadget | T2 | 2 | 0.0 | 0% | 2.5 | ⬇️ | 🔴 差 |
| no-film-school | T2 攝影 | 2 | 0.0 | 0% | 1.0 | → | 🔴 差 |
| the-verge | T3 | 2 | 0.0 | 0% | 1.0 | → | 🔴 差 |

### ⚠️ 跨週警訊

- **apple-newsroom-en 從 10.0 → 6.0**：Pride Collection + Q2 Earnings 兩篇都是非產品發表類 T1 內容，rubric 抓到 D3（訓練潛力）較低。**這是 rubric 正確、非品質下降**；但說明 **T1 豁免策略值得討論**（目前 ingest_agent 對 T1 auto score=10；本次研究用 score_article 直接打分故呈現真 rubric 分數）
- **macstories 從 8.0 → 5.0**：本週 3 篇都是 roundup/podcast/coming-soon 類，而非深度產品評測
- **six-colors 仍是 0% 通過**：4 篇有 2 篇是 podcast episodes。**Filter 本身正常**（v1.1.1 的 `/podcast/` URL 正則已能擋下所有本週 feed 的 podcast，經 `--dry-run` 驗證）—— 這兩篇是 **fix 之前**（pre-w2-crawler + v0.1 早期產出）殘留的歷史資料，不是 filter bug
- **engadget/the-verge 連續 2 週全擋 0 篇通過**：符合 §7.5「T3 僅 digest 市場視角」定位，可考慮降頻 crawl

---

## 🏆 Top 10 高分亮點

| # | 分數 | 來源 | 標題 | 要點 |
|---|---|---|---|---|
| 1 | 10 | apple-com-tw | iPhone 17 — Apple（台灣）| T1 官方產品頁，rubric 全滿（D1=3, D2=2, D3=3, D4=2）|
| 2 | 8 | ars-technica | Apple may take several months to catch up on Mac mini / Studio | 供貨與產品路線評論 |
| 3 | 8 | ars-technica | Mac mini starting price goes up to $799 | Mac 定價變動，直接影響話術 |
| 4 | 7 | macworld | Office suite on Mac for $45 | 軟體特賣，Mac 生態外延 |
| 5 | 6 | apple-newsroom-en | Apple introduces a new Pride Collection | T1 品牌活動（非產品發表）|
| 6 | 6 | apple-newsroom-en | Apple reports second quarter results | T1 財報，產業脈動素材 |
| 7 | 5 | ars-technica | Six things about Tim Cook's version of Apple | 產業評論，間接素材 |
| 8 | 5 | macstories | Apple Releases Watch Band Pride Edition | 配件消息 |
| 9 | 5 | macstories | Coming Soon on Apple TV+ and Apple Arcade | 服務內容 |
| 10 | 5 | macstories | Podcast Rewind: App Gaps Filled | 軟體更新速報 |

---

## 🚫 Bottom 10 低分（不 ingest，保留於 /raw 供稽核）

| # | 分數 | 來源 | 標題 | 為何低分 |
|---|---|---|---|---|
| 1 | 0 | engadget | GameStop to buy eBay | 電商八卦，無 Apple |
| 2 | 0 | engadget | Sony PlayStation Store class action | 訴訟，與 Apple 無關 |
| 3 | 0 | no-film-school | 5 Movies Tarantino Helped Create | 電影史，與器材無關 |
| 4 | 0 | no-film-school | 7 Best Spaghetti Westerns, Ranked | 影評榜單 |
| 5 | 0 | petapixel | Photography Lessons from LOTR | 電影幕後，無 Apple |
| 6 | 0 | six-colors | (Podcast) Downstream 117 | podcast 劇集；pre-fix 殘留 |
| 7 | 0 | six-colors | (Podcast) Upgrade 614 | 同上；pre-fix 殘留 |
| 8 | 0 | the-verge | Reggie Fils-Aimé: Amazon/Nintendo | 遊戲產業八卦 |
| 9 | 0 | the-verge | Shokz OpenRun Pro 2 $40 off | 第三方耳機促銷 |
| 10 | 1 | cined | A Mighty Cut: storytelling | 剪輯教學，僅 D3 微相關 |

---

## 💡 本次 Rubric 觀察

1. **T1 非產品內容會被 rubric 打低分**（Pride 6/10、Q2 earnings 6/10）
   - 目前 ingest_agent 的 T1 豁免是正確的（信任來源優先於 rubric）
   - 但 **rubric 打分作為輔助訊號**仍有價值：告訴管理員「這篇雖 approved，但訓練素材貧瘠」
2. **W19 raw 有 2 篇 pre-fix podcast 殘留**：v1.1.1 URL filter 已能擋下；兩篇是 fix commit (2026-05-05 13:36) 之前爬的歷史資料，非現行 filter 缺陷
3. **T3 來源幾乎 100% 被擋**：engadget + the-verge 連續 2 週 0 通過 → 可以開 issue 討論降頻
4. **petapixel / no-film-school 攝影週的價值**：本週完全無 Apple-related review 出現 → 正如 v1.1 加嚴 filter 的預期

---

## 🛠 後續動作（建議）

- [ ] **Backfill**：把本次 27 個分數回寫進每篇 `.meta.json`（`relevance_score` / `relevance_reasoning` / `relevance_breakdown` / `key_entities`）
- [ ] **(可選) 清理 2 篇 pre-fix podcast raw**：或直接忽略（raw 是 immutable，不影響未來 Gate 3）
- [ ] **開 issue**：T1 豁免 vs rubric 分數的政策討論（保留豁免 / 改成分數 < N 時 pending-review）
- [ ] **W20 基準**：第一份「爬 → 打分 → 週報」全自動流程

---

## 📎 原始資料

- JSON: `raw/_relevance-scores-2026-W19.json`
- 總耗時: 28.5s（27 篇）
- 平均延遲: 1.06s/篇
- 模型: `gemini-2.5-flash-lite:latest` via Apple GenAI proxy (`localhost:11211`)
- Agents 版本: v1.9.4
