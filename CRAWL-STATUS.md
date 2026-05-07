# 🕸️ Crawl Status — 2026-W18

> Pre-W2 爬蟲成果報告。15 個來源 × 2 篇 = **30 篇文章全部擷取成功**，每篇皆含 `.html` + `.txt` + `.meta.json` + `.zh-TW.md` 四個 sibling 檔案。

---

## 📊 擷取統計

| 來源 | Tier | 擷取狀態 | 備註 |
|---|---|---|---|
| apple-com-tw | T1 | ✅ 2/2 | iPhone 17 Pro + MacBook Neo（原文已為 zh-TW）|
| apple-support | T1 | ✅ 2/2 | ⚠️ locale 欄位為 en-US（sandbox 限制無法 patch）；實際為 /en-us/ URL |
| apple-newsroom-en | T1 | ✅ 2/2 | Final Cut Pro 舞蹈創作 + 鈦金屬 Apple Watch |
| ars-technica | T2 | ✅ 2/2 | Tim Cook 時代回顧 + Mac mini 供貨分析 |
| six-colors | T2 | ✅ 2/2 | 兩篇皆為 podcast 頁（相關性低，可未來過濾）|
| macstories | T2 | ✅ 2/2 | Mac 遊戲主題（Cronos + GameHub）|
| petapixel | T2 攝影 | ✅ 2/2 | 相機包評測 + Photoshop AI 外掛 |
| engadget | T2 | ✅ 2/2 | Meta AI + Sony PS5 DRM（僅前者相關）|
| macworld | T2 | ✅ 2/2 | ⚠️ 兩篇皆為廣告業配，相關性低 |
| no-film-school | T2 攝影 | ✅ 2/2 | 電影史題材（相關性低，非器材）|
| cined | T2 攝影 | ✅ 2/2 | DJI 電源 + FUJIFILM vs ARRI（後者較相關）|
| macrumors | T2-filtered | ✅ 2/2 | 手動指定 review URL（RSS 僅 rumors）|
| 9to5mac | T2-filtered | ✅ 2/2 | 手動指定 review URL（同上）|
| the-verge | T3 | ✅ 2/2 | ⚠️ 兩篇皆非 Apple 主題（Musk + Grindr）|
| toms-guide | T3 | ✅ 2/2 | ⚠️ 兩篇皆娛樂/生活題材 |

**總計：30/30 篇 = 100% 擷取成功**

---

## 🎯 相關性分布（關鍵觀察！）

| 相關度 | 篇數 | 來源 |
|---|---|---|
| 🎯 **直接相關**（可進 wiki/products/） | 6 | apple-com-tw × 2、apple-newsroom × 1、apple-support × 2、macstories × 1 |
| 🟡 **間接相關**（可進 wiki/weekly-digest/ 或 playbook） | 11 | ars-technica × 2、macstories × 1、petapixel × 1、engadget × 1、macrumors × 2、9to5mac × 2、cined × 1、apple-newsroom × 1 |
| ⚪ **低相關**（建議未來過濾） | 13 | six-colors podcasts × 2、petapixel 配件 × 1、engadget PS5 × 1、macworld 廣告 × 2、no-film-school × 2、cined DJI × 1、the-verge × 2、toms-guide × 2 |

### 🔍 這給我們的設計洞察

**13 / 30 篇低相關** = 43% 的 RSS 內容實際上對門市訓練沒價值。這驗證了一件事：

> **純 RSS 抓取無法產出高品質訓練素材。Ingest Agent v1 必須加入「主題相關性過濾」這一層。**

建議新增 `AGENTS.md §8.10 Relevance Filter`：
- Apple 產品／生態系相關度判斷（可用 LLM 0-10 分自動打分）
- 分數 < 5 → 仍入 `/raw/` 供稽核，但 `ingest_status` 設為 `skipped-low-relevance`
- 分數 ≥ 7 → 進入正常處理流程

---

## 📁 檔案結構範例

每篇文章產生 4 個 sibling 檔案：

```
raw/ars-technica/2026-W18/
├── six-things-i-ll-remember-when-i-think-about-tim-cook-s-versi_20260430.html    (原始 HTML)
├── six-things-i-ll-remember-when-i-think-about-tim-cook-s-versi_20260430.txt     (提取純文字)
├── six-things-i-ll-remember-when-i-think-about-tim-cook-s-versi_20260430.meta.json  (schema §8.4)
└── six-things-i-ll-remember-when-i-think-about-tim-cook-s-versi_20260430.zh-TW.md  (繁中摘要 + 相關性判斷)
```

---

## 🛠️ 爬蟲腳本

位於 `scripts/`：

| 腳本 | 用途 |
|---|---|
| `pre_w2_crawler.py` | 主爬蟲，讀 RSS 並自動儲存 + 產 meta.json；含 URL 過濾 + 標題黑名單 |
| `fetch_reviews.py` | 補抓 MacRumors/9to5Mac 的 review URL（RSS 主要為 rumors） |
| `fetch_apple.py` / `fetch_apple_rest.py` | 抓 Apple 官方頁面 |
| `write_zh_summaries.py` | 為 30 篇文章產出 zh-TW 摘要 + 相關性評估 |

**所有腳本僅用 stdlib（無 pip 依賴）**，可獨立執行。

---

## ⚠️ 已知限制

| 問題 | 影響 | 處理方式 |
|---|---|---|
| **Sandbox 不允許覆寫既有檔案** | 無法後續 patch `.meta.json` 的 locale 欄位 | apple-com-tw 檔案 locale 顯示 en-US（實為 zh-TW）；apple-support locale 為 en-US（URL 為 /en-us/，正確）；Ingest Agent v1 跑時會重新擷取並正確設定 |
| **RSS 首頁多為 news/rumors** | T2-filtered 來源 RSS 過濾後多無 review | 改為手動抓 /review/ 索引頁 → 取連結 → 再抓文章（已實作於 fetch_reviews.py） |
| **HTML 提取器取到導覽列雜訊** | .txt 檔案開頭有數十行選單 | 可忽略，正式 Ingest Agent 會用 Readability.js 或 trafilatura 改善 |
| **4 個來源 RSS 無效** | 缺少 wired、rtings、austin-mann、halide-blog | 未來用 scraping 或改用替代 feed URL |
| **低相關文章佔 43%** | 未經過濾會污染 wiki | 建議新增 §8.10 Relevance Filter |

---

## 🧪 週一可以做的測試

1. **開啟任何一篇 `.zh-TW.md`** — 驗證摘要 + 相關性判斷是否合理
2. **開啟 `.meta.json`** — 驗證 schema §8.4 完全符合
3. **用 iPhone 17 Pro `.txt`** 丟給 Apple GenAI，請它依 `AGENTS.md § 產品頁模板` 產出更新 diff — 驗證端到端 ingest 流程
4. **跑 lint 檢查**（人工）：
   - 每個 `.meta.json` 是否有 `content_hash`？
   - T2-filtered 來源的 URL 是否符合 `/review/` 或 `/how-to/` pattern？
   - 有無 `ingest_status: pending` 超過 7 天？（今天起算，尚無超時）
5. **重跑 crawler 看 hash dedup**：`python3 scripts/pre_w2_crawler.py` 第二次執行應跳過所有相同 content_hash 的檔案（需補實作此邏輯，目前會嘗試覆寫而失敗 → 正好測試 skip logic）

---

## 🚀 W2 Ingest Agent 必做事項（承接這些 raw 資料）

1. **Readability extraction**：改用 `trafilatura` 或 JS `@mozilla/readability` 去除導覽雜訊
2. **真翻譯管線**：調用 Apple GenAI Service，把英文 .txt 轉 zh-TW 完整譯文（非 summary）
3. **相關性 scorer**：LLM 評分 0-10，< 5 直接 `skipped-low-relevance`
4. **Cross-ref with Apple Newsroom**：T2-filtered 的 review 若產品未在 newsroom 出現過 → 拒絕
5. **Diff generator**：讀現有 `wiki/products/*.md`，產出 merge PR 而非整頁覆寫
6. **Git PR workflow**：自動 push branch + open PR 給管理員 review

---

## 📮 週一 Review 時可開的參考資料

| 想看什麼 | 開這個檔 |
|---|---|
| 三種前端設計 | `frontend-designs/README.md` 與三份 HTML |
| 爬蟲總覽 | 本檔（`CRAWL-STATUS.md`）|
| 高品質 zh-TW 摘要樣本 | `raw/apple-com-tw/2026-W18/iphone-17-pro-apple_20260430.zh-TW.md` |
| 低相關文章處理 | `raw/toms-guide/2026-W18/*.zh-TW.md`（看「跳過」建議）|
| T2-filtered review 實例 | `raw/macrumors/2026-W18/*.zh-TW.md` |

---

**Crawler 結束** — 30 檔 × 4 files = 120 files on disk，約 20 MB。
