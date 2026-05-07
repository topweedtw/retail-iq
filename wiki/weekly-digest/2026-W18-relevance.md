---
type: digest
slug: 2026-W18-relevance
title: 2026-W18 來源相關性週報
period: 2026-W18 (2026-04-27 ~ 2026-05-03)
generated_at: 2026-04-30
generated_by: pre-w2-scoring (manual LLM curation)
agents_version: v1.7
---

# 📊 2026-W18 來源相關性週報

> 依 `AGENTS.md` §8.10.5 規範產出；本期為 pre-W2 手動版本，W2 Ingest Agent 上線後改為每週自動產生。

---

## 總覽

- **本週擷取總數**：30 篇（15 來源 × 2）
- **平均分數**：4.67 / 10
- **通過比例**：50%（15 / 30）← 健康度 🟡 **偏低**

### 分布

| 狀態 | 分數範圍 | 篇數 | 占比 |
|---|---|---|---|
| ✅ `approved` | 7–10 | 15 | 50% |
| 🟡 `pending-review` | 5–6 | 1 | 3% |
| ❌ `skipped-low-relevance` | 0–4 | 14 | 47% |

---

## 各來源健康度

| 來源 | Tier | 篇數 | 平均分 | 通過率 | 健康度 |
|---|---|---|---|---|---|
| apple-com-tw | T1 | 2 | 10.0 | 100% | 🟢 優 |
| apple-newsroom-en | T1 | 2 | 10.0 | 100% | 🟢 優 |
| apple-support | T1 | 2 | 10.0 | 100% | 🟢 優 |
| 9to5mac | T2-filtered | 2 | 9.0 | 100% | 🟢 優 |
| macstories | T2 | 2 | 8.0 | 100% | 🟢 優 |
| macrumors | T2-filtered | 2 | 7.0 | 100% | 🟢 優 |
| ars-technica | T2 | 2 | 6.5 | 50% | 🟡 可 |
| cined | T2 攝影 | 2 | 4.0 | 50% | 🟡 可 |
| petapixel | T2 攝影 | 2 | 2.5 | 0% | 🔴 差 |
| engadget | T2 | 2 | 2.5 | 0% | 🔴 差 |
| six-colors | T2 | 2 | 2.0 | 0% | 🔴 差 |
| no-film-school | T2 攝影 | 2 | 1.0 | 0% | 🔴 差 |
| the-verge | T3 | 2 | 1.0 | 0% | 🔴 差 |
| toms-guide | T3 | 2 | 1.0 | 0% | 🔴 差 |
| macworld | T2 | 2 | 1.0 | 0% | 🔴 差 |

---

## 🏆 Top 10 高分亮點（建議優先 ingest）

| # | 分數 | 來源 | 標題 |
|---|---|---|---|
| 1 | 10 | apple-com-tw | iPhone 17 Pro 與 iPhone 17 Pro Max — Apple（台灣）|
| 2 | 10 | apple-com-tw | MacBook Neo — Apple（台灣）|
| 3 | 10 | apple-newsroom-en | Behind Kyle Hanagami's viral dance creations edited with Final Cut Pro |
| 4 | 10 | apple-newsroom-en | Mapping the future with 3D-printed titanium Apple Watch cases |
| 5 | 10 | apple-support | About Apple Intelligence |
| 6 | 10 | apple-support | iPhone 17 Pro tech specs |
| 7 | 9 | 9to5mac | SpeakOn AI dictation review |
| 8 | 9 | 9to5mac | Aulumu M10 3-in-1 review |
| 9 | 9 | macstories | Cronos: The New Dawn Showcases the Mac's MetalFX and Ray Tracing |
| 10 | 7 | ars-technica | Tim Cook 時代回顧（間接相關但可作產業脈動素材）|

---

## 🚫 Bottom 10 低分（建議不 ingest，但保留於 /raw 供稽核）

| # | 分數 | 來源 | 標題 | 為何低分 |
|---|---|---|---|---|
| 1 | 0 | no-film-school | How Ernst Lubitsch "Invented Modern Hollywood" | 電影史，與器材無關 |
| 2 | 1 | the-verge | Elon Musk's worst enemy in court is Elon Musk | 訴訟報導 |
| 3 | 1 | the-verge | Grindr won the WHCD party circuit | 社群 app 八卦 |
| 4 | 1 | toms-guide | 3 classic HBO dramas | 娛樂內容 |
| 5 | 1 | toms-guide | Solar panel mistake | 太陽能建議 |
| 6 | 1 | macworld | All Babbel courses lifetime price | 廣告業配 |
| 7 | 1 | macworld | MS Visual Studio coding deal | 廣告業配 |
| 8 | 1 | sony-playstation | PlayStation license check | 非 Apple 主題 |
| 9 | 1 | petapixel | Camera wraps | 第三方配件 |
| 10 | 2 | six-colors | Podcast Clockwise 654 | podcast 閒聊 |

---

## ⚠️ 來源健康警報

以下 7 個來源平均分 < 5，**若下週仍維持低分 → 觸發 §8.10.4 的「連續 5 篇 < 5 分」規則**，建議：

- **petapixel**：過濾掉非 Apple 攝影的第三方配件文章；建議加 URL pattern 限制
- **engadget**：新增標題關鍵字過濾（需含 "Apple" / "iPhone" / "Mac" / "iPad"）
- **six-colors**：建議過濾 `/podcasts/` 路徑，僅留部落格文章
- **no-film-school**：疑似不適合 RetailIQ 訓練；建議**下線**或改為僅追蹤特定 tag
- **the-verge**：限定僅擷取 `/apple/` 或 `/tech/` 子分類
- **toms-guide**：限定僅擷取 `/reviews/` 或 `/buying-guide/` 且 title 含 Apple
- **macworld**：過濾標題含 "Exclusive:" 的業配文

---

## 💡 洞察

本週 47% 低相關率符合 pre-W2 預期（先前 `CRAWL-STATUS.md` 已估算 43%）。驗證了：

1. **純 RSS 抓取不可行**，必須加相關性過濾
2. **T2 攝影三站（petapixel、no-film-school、cined）需精挑路徑**，不能全站 RSS
3. **T3 來源預期大部分低分**，設計預期即是「偶爾命中」

---

## 🎯 建議 sources-config.yaml 調整

```yaml
# petapixel
allow_url_patterns:
  - "^https://petapixel\\.com/\\d{4}/\\d{2}/.*(iphone|ipad|mac|apple)"
# 只抓 URL slug 含 Apple 關鍵字的文章

# engadget
title_required_keywords: ["Apple", "iPhone", "Mac", "iPad", "Vision", "AirPods"]
# 新欄位，尚未實作，提議納入 §8.10 後續版本

# six-colors
deny_url_patterns:
  - "^https://sixcolors\\.com/.*/podcast-"

# the-verge
allow_url_patterns:
  - "^https://www\\.theverge\\.com/apple/"
  - "^https://www\\.theverge\\.com/tech/"
```

---

**報告結束** — 下週同期 (2026-W19) 將產出對比版本，可觀察來源健康度趨勢。
