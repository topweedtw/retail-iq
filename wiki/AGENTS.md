# AGENTS.md — RetailIQ Wiki Schema

> **這份文件是 LLM Agent 在維護本 Wiki 時必須遵守的規則。**
> 所有 ingest、update、lint 操作都以此為依據。

---

## 1. 整體 Repo 結構

本專案採 **Karpathy LLM Wiki** 模式，分三層：raw（不可變原始資料）／ wiki（LLM 維護的結構化知識）／ schema（本檔）。

```
retail-iq/                    ← Git repo root
├── raw/                      ← §8 原始資料層（immutable，只追加）
│   ├── apple-com-tw/
│   ├── apple-support/
│   ├── sales-coach/
│   ├── admin-uploads/
│   └── assets/
│
└── wiki/                     ← LLM 維護的結構化知識層
    ├── AGENTS.md             ← 本檔案（不可由 Agent 修改）
    ├── index.md              ← 全站頁面目錄（Agent 維護）
    ├── log.md                ← 時間軸日誌（Agent 僅能 append）
    ├── sources-config.yaml   ← Ingest 來源設定（§8.8 / §8.9）
    ├── products/             ← 產品頁（每款在售產品一頁）
    ├── concepts/             ← 跨產品概念（晶片、Apple Intelligence、隱私…）
    ├── comparisons/          ← 產品比較頁（X vs Y）
    ├── sales-playbook/       ← 銷售技巧（反對處理、破冰話術、客群畫像）
    ├── weekly-digest/        ← 每週摘要（YYYY-Www.md）
    ├── archive/              ← 停產產品歸檔（不刪除，僅移動）
    ├── design/               ← 架構設計文件（v2.0+ 新增；如 gate4-ingest.md）
    ├── handover/             ← Session handover 歷史（v2.0+ 新增）
    └── ingest-queue/         ← Gate 4 人工審核佇列（v2.0+ 新增；含 _archive/）
```

**三層職責分工**：
- **raw/**：Fetcher / Crawler / Admin 上傳的**原始檔**，LLM **只讀不寫**。詳見 §8。
- **wiki/**：LLM 主要工作區，所有產品頁、概念頁、比較頁、摘要皆在此。
- **AGENTS.md**（本檔）：規則與 schema，唯一的「人寫、Agent 讀」檔案。

---

## 2. Ingest Workflow（每週一 03:00 執行）

1. 掃描 `/raw/**/*.meta.json`（格式與欄位見 §8）
2. 依各檔的 `content_hash` 對比 `log.md` 最後紀錄 → 判斷是否為新／變更檔案（hash 相同則跳過）
3. 對每個待處理來源：
   a. 判斷主題 → 決定應更新哪些 wiki 頁面
   b. 讀取現有頁面 → 產生 diff
   c. 若偵測到**矛盾**（新舊資訊衝突）→ 在頁面頂部加 `> ⚠️ CONFLICT` 區塊，保留兩版並標註來源日期
   d. 更新 `index.md`、append `log.md`（需包含 `.meta.json` 路徑供追溯）
   e. 更新該 `.meta.json` 的 `ingest_status` → `processed`
4. 產生 `weekly-digest/YYYY-Www.md`
5. 送出 Git PR → 等管理員審核 → merge 後生效

---

## 3. 頁面通用規則

### 3.1 YAML Frontmatter（**每頁必備**）

```yaml
---
type: product | concept | comparison | playbook | digest
title: 人類可讀標題
slug: kebab-case-id
status: active | draft | archived
product_category: iphone | ipad | mac | watch | airpods | vision | accessory
last_updated: 2026-04-30
source_count: 7
tags: [camera, a19-pro, titanium]

# 段落所有權宣告（詳見 §3.6；為選填但強烈建議 product 頁提供）
ingest_managed_sections: [核心規格, 起售價, 來源]
human_owned_sections: [五大賣點, 三大獨家 Demo, 常見客戶問題與回應, 常見反對意見處理]
---
```

### 3.2 內容規則

- **來源引用**：每個事實陳述結尾加 `[^1]`，文末列出來源清單
- **交叉連結**：提到其他產品／概念時一律用 `[[page-slug]]` 格式
- **語氣**：客觀、專業，**不可出現行銷情緒詞**（如「革命性」「無與倫比」）
- **未公開資訊**：若 raw 中偵測到未發表產品的資料 → 丟棄，不寫入 wiki
- **價格**：僅記錄官方公告價，**不可**記錄促銷／折扣

### 3.3 官方術語一致性（**必須遵守**）

Agent 在撰寫與翻譯時，**必須使用 Apple 台灣官網的正式中文名稱**，不得混用英文或自行翻譯。常見對應表（持續擴充）：

| Apple 官方英文 | ✅ 官網正式中文 | ❌ 勿用 |
|---|---|---|
| Writing Tools | 書寫工具 | Writing Tools（保留英文）、寫作工具 |
| Visual Intelligence | 視覺智慧 | Visual Intelligence、視覺識別 |
| Clean Up | 清除 | Clean Up、移除、去背 |
| Live Translation | 即時翻譯 | Live Translation |
| Center Stage | Center Stage（此為品牌名保留） | 置中舞台、人物居中（僅指功能時） |
| Genmoji | Genmoji | — |
| Image Playground | Image Playground | — |
| ProMotion | ProMotion（品牌名保留） | — |
| Dynamic Island | 動態島 | Dynamic Island |
| Face ID / Touch ID | Face ID / Touch ID（保留） | — |
| Ceramic Shield | 超瓷晶盾 | — |
| Vapor Chamber | 均溫板 | 蒸汽室 |
| Pro Fusion Camera System | Pro 融合相機系統 | — |
| ProMotion display | ProMotion 技術 | — |
| Apple Intelligence | Apple Intelligence（保留） | — |

**Ingest Agent 責任**：遇到新功能／新術語時，先查 apple.com/tw 對應頁面確認官方中文，若官網尚無中文則保留英文並標記 `🟡 NEEDS REVIEW：待官方中文確認`。

### 3.4 定價區塊（產品頁 §「起售價」必備）

- 每個 `status: active` 的產品頁必須包含「起售價」段落
- 格式：`NT$XXXXX 元起（儲存容量／機型）`
- 若從來源尚未取得具體台灣售價 → 以 `NT$XXXXX` 占位符 + 標 `🟡 NEEDS REVIEW`
- **不可**寫入：促銷折扣、教育優惠折後價、Trade In 折抵後價（這些屬於活動價，變動頻繁，由前端 runtime 從活動 API 取）

### 3.5 矛盾標記格式

```markdown
> ⚠️ **CONFLICT** (flagged 2026-04-28)
> - 來源 A (2026-03-15)：電池續航 22 小時
> - 來源 B (2026-04-20)：電池續航 24 小時
> → 採用來源 B（較新）；待管理員確認
```

### 3.6 段落所有權（Segment Ownership）

**問題背景**：2026-W18 端到端測試揭露 — **人工精煉的 wiki 段落品質高於 raw 能自動生成的內容**（例如 FAB 的 B 層、Signature Demo、反對處理話術）。若 Ingest Agent 盲目覆寫，會摧毀已經做好的創作內容。

**解決方案**：每個產品頁以 YAML frontmatter 的兩個欄位宣告段落所有權：

| 欄位 | 意義 | Ingest Agent 行為 |
|---|---|---|
| `ingest_managed_sections` | 列表：段落標題（不含 `##`）。Ingest Agent **可覆寫**此類段落 | 每次 ingest 時**安全更新**（事實資料） |
| `human_owned_sections` | 列表：段落標題。Ingest Agent **不可覆寫**（即使 raw 有新資訊） | 僅能在 log.md 記錄「建議人工更新」，本體不動 |

**預設值（若 frontmatter 未宣告）**：

| 段落類型 | 預設所有權 | 理由 |
|---|---|---|
| 一句話定位 | ingest-managed | 可從 raw 擷取 |
| 起售價 | ingest-managed | 需自動從 shop 頁同步 |
| 目標客群 | ingest-managed | 首次建立；後續可人工調整 |
| 核心規格 | ingest-managed | 純事實欄位 |
| 五大賣點（FAB） | **human-owned** | B 層 persona 句需人工覆核 |
| 三大獨家 Demo | **human-owned** | Demo 話術需現場經驗 |
| 一般實機 Demo 建議 | **human-owned** | 同上 |
| 常見客戶問題與回應 | **human-owned** | 話術創作 |
| 常見反對意見處理 | **human-owned** | 話術創作 |
| 競品對比摘要 | ingest-managed | 自動交叉引用 |
| 相關頁面 | ingest-managed | 自動交叉引用 |
| 來源 | ingest-managed | 自動追加 `[^N]` |

> 📌 **原則**：當 frontmatter 未列 `human_owned_sections` 時，Ingest Agent **必須**使用上表預設值，而非假設全部可覆寫。這是避免資料遺失的紅線。

**Ingest Agent 執行規則**：

1. 讀取目標 wiki 頁面的 frontmatter
2. 收集 `ingest_managed_sections` + 預設 managed 段落 = 可寫清單
3. 收集 `human_owned_sections` + 預設 human 段落 = 禁寫清單
4. 對 raw 產出的 diff 逐段落判斷：
   - 若段落在禁寫清單 → **略過**，在 log.md 記錄「suggested update for human review」
   - 若段落在可寫清單 → **寫入**
   - 若段落不在任何清單（新段落）→ **append 並標記 🟡 NEEDS REVIEW**
5. 最後更新 `last_updated` + `source_count`（這兩個欄位永遠由 Agent 管理）

**Lint 檢查（§6 將補充）**：
- 每個 active 產品頁必須兩個欄位都有值，或明確寫 `[]` 表示接受預設
- 兩個欄位的段落集合不可重疊

---

## 4. 產品頁模板（`products/*.md`）

**所有產品頁必須包含以下段落，依此順序：**

1. `## 一句話定位` — 50 字內的產品核心價值
2. `## 起售價` — 依 §3.4 格式列出；無台灣售價時用 `NT$XXXXX 元起` + `🟡 NEEDS REVIEW`
3. `## 目標客群` — 3-5 個主要客群 + 連結到 `[[sales-playbook/customer-personas]]`
4. `## 核心規格` — 表格（晶片 / 顯示器 / 相機 / 電池 / 儲存 / 連接埠 / 重量 / 尺寸）
5. `## 五大賣點（Selling Points）` — 編號清單，**每個賣點必須有 FAB 結構**（依 §4.5）：
   - **Headline**：一句話標題
   - **F (Feature)**：可被 T1 來源驗證的規格事實
   - **A (Advantage)**：業界優勢／差異化
   - **B (Benefits)**：對至少 3 個客群的 persona-adaptive 好處句（學生／商務／攝影／家庭…擇三）
6. `## 三大獨家 Demo（Signature Demos）` — 本產品**最能讓客戶「哇！」的 3 個獨特功能**，每個功能必須包含：
   - **6a. 功能名稱 + 為何獨特** — 一句話說明為何這是本產品的殺手鐧（最好能對比「其他產品做不到 / 做不好」）
   - **6b. 前置準備** — 現場需要什麼（demo 機設定、素材、配件、網路、另一台 Apple 裝置…）
   - **6c. 分步腳本** — 編號的動作清單，依 §4.2 節奏規範（邊做邊說 + 優先用預載素材），每步含：
     - 👉 **動作**：你的手指／裝置操作
     - 🗣️ **口白**：對客戶說什麼（一到兩句，每句 ≤ 15 字）
     - 👀 **客戶看到什麼**：畫面／結果描述
   - **6d. 客戶親手做（Hands-on）** — 讓客戶自己操作什麼，加深體驗記憶
   - **6e. 常見卡點與應變** — 若網路不穩／功能沒反應／預載素材失效時的 Plan B
   - **6f. 收尾金句** — 一句把客戶拉回產品價值的話術
7. `## 一般實機 Demo 建議` — 3-5 個較常規的 Demo 步驟
8. `## 常見客戶問題與回應` — Q&A 格式，至少 5 組
9. `## 常見反對意見處理` — 「客戶說 X → 你可以回應 Y」至少 3 組
10. `## 競品對比摘要` — 連結到 `[[comparisons/xxx]]`
11. `## 相關頁面` — 交叉引用清單
12. `## 來源` — Footnote 列表

### 4.1 Signature Demo 選擇原則

Agent 在 ingest 時**不得**隨意挑 3 個 demo。必須依以下優先順序：

1. **獨家性**：該功能是否為本產品（或同代系列）獨有？競品沒有或體驗明顯較差？
2. **可視覺化**：30 秒內能讓客戶「看見差異」的功能優先（如相機、顯示器、AI 動畫）
3. **觸覺／情感衝擊**：能讓客戶伸手去摸、去試的功能優先（如觸覺回饋、材質、重量）
4. **與目標客群相關**：功能必須對應到該產品的 Top 客群的核心需求
5. **店內可執行性**：需要 5G / 戶外光線 / 特殊配件才能展示的功能 → 降低優先級，或在 `前置準備` 明確標註限制

### 4.2 Demo 展示節奏規範（**必須遵守**）

1. **優先使用展示機預載素材** — 相機／AI／顯示器類 demo，**優先**從展示機內建的官方示範相簿／樣片／影片開始，避免現場等待拍攝、上傳或下載的尷尬時間
2. **邊做邊說（show-and-tell）** — 每一步都要有「動作 + 口白」同步進行，避免「先說一堆，再動手操作」的講解型 demo
3. **口白必須簡短** — 每句 ≤ 15 字，每個 demo 步驟 ≤ 2 句口白
4. **先看效果、再解釋原理** — 讓客戶先「看到／感覺到」功能好用，再補充技術原理（如「這就是四重反射稜鏡做到的」）
5. **備援方案寫在「常見卡點與應變」** — 預載素材若因展示機狀態變動失效，必須有 Plan B（如：現場即時拍一張）

**若產品在某個維度實在找不到「獨家」功能**（例如入門機型），應選「此價位段最突出」的功能，並在「為何獨特」段落誠實標註定位（不得誇大）。

### 4.3 展示腳本長度變體（Script Length Variants）

腳本生成器支援三種長度，每種有不同的結構與適用情境：

| 長度 | 名稱 | 適用情境 | 包含 Signature Demo | 客戶親手做 |
|---|---|---|---|---|
| **1 分鐘** | 快閃展示（Flash Showcase） | 客戶經過、路過、短暫停留；無操作時間 | ❌ 不含（僅外觀／設計／實體展示） | ❌ 不含 |
| **3 分鐘** | 精華展示（Core Demo） | 客戶駐足、願意停留；店員單人操作 | ✅ 1 個 Demo（最高優先級 feature） | ⚠️ 簡短（15 秒內） |
| **5 分鐘** | 完整展示（Full Demo） | 客戶有明確意願、深入了解 | ✅ 2 個 Demo（主 + 次） | ✅ 完整（每 demo 皆有） |

#### 4.3.1 各長度的段落分配矩陣

| 段落 | 1 分鐘（60s） | 3 分鐘（180s） | 5 分鐘（300s） |
|---|---|---|---|
| 開場破冰 | 10s | 20s | 30s |
| 三大核心賣點（電梯版） | 25s | 30s | 45s |
| 外觀／材質／設計導覽 | **25s**（本段為 1min 版主角） | 15s | 略（融入賣點） |
| Signature Demo（主） | — | 90s | 90s |
| Signature Demo（次） | — | — | 75s |
| 生態系論述 | — | 15s | 30s |
| 反對預判 + 封閉 CTA | — | 10s | 30s |

**總時長必須 ≤ 目標時長 × 1.1**（例：5 分鐘版本不得超過 330 秒），否則腳本生成器必須重新壓縮。

#### 4.3.2 1 分鐘快閃展示的特殊規則

**本長度不含任何 hands-on 操作**。生成器必須：

1. **聚焦實體可感知元素**：顏色、材質、重量、按鈕、質感、鏡頭模組、顯示器亮度
2. **使用展示機本身為「活素材」**：客戶看的是機器本身，不是 app 畫面
3. **每個賣點配一個「視覺錨點」**：店員手勢指向、翻轉、擺角度讓客戶看
4. **收尾 CTA 必須輕量**：邀請客戶「下次再來做 3 分鐘詳細 demo」，不做硬性結案
5. **絕不打開 app**：若客戶追問功能 → 順勢升級到 3/5 分鐘版本（店員自行判斷）

**1 分鐘版適用的賣點類型**（從產品頁 §五大賣點 挑選）：
- ✅ 外觀／材質／顏色
- ✅ 體感重量／觸感
- ✅ 實體按鈕位置與功能（如相機控制、動作按鈕）
- ✅ 顯示器亮度／對比（可即場看）
- ❌ AI 功能（需要操作）
- ❌ 相機變焦（需要進 app）
- ❌ 生態系連動（需要第二台裝置）

### 4.4 草稿迭代流程（Draft-then-Refine Workflow）

**避免「一次產出即定案」的弱點**。腳本生成器應支援兩段式流程：

#### 4.4.1 兩段式流程

```
使用者填寫參數（產品／客群／時長／重點）
       ↓
【第一段】生成敘事草稿（Narrative Draft）
  - 純文字散文格式
  - 無時間標記、無段落時長
  - 只描述「怎麼說這個故事」
  - 約 200-400 字
  - 末尾附詢問：「這個敘事結構 OK 嗎？」
       ↓
   使用者審閱
   ├─ ✅ 接受 → 進入第二段
   └─ ❌ 拒絕 → 說明想改的地方 → 回到第一段重新生成
       ↓
【第二段】生成完整分段腳本（Timed Script）
  - 依 §4.3 時長變體的段落分配矩陣
  - 含時間標記、口白、動作、客戶反應
  - 依 §4.2 節奏規範（邊做邊說、口白 ≤15 字）
```

#### 4.4.2 敘事草稿格式規範

第一段草稿**必須**：

1. 以第一人稱店員視角撰寫（「我會先問客戶……」「然後我切到……」）
2. 不含時間標記（no `0:00–0:30` 之類）
3. 不含動作／口白符號（no 👉🗣️👀）
4. 不含段落標題（全段連續散文）
5. 長度 200-400 字
6. 必須**點名引用**哪些 wiki 素材（以便使用者驗證）
7. 結尾附制式問句：
   > 「請確認這個敘事結構 OK 嗎？OK 我出分段版本；不 OK 請告訴我要換哪個角度、哪個 Demo、或哪段話。」

#### 4.4.3 使用者拒絕時的回饋格式

前端 UI 應提供三種快速回饋選項，讓使用者不用完整重寫：

- **換一個 Demo**：「Demo 1 改用 XXX」（列出產品頁其他 signature demos）
- **換一個論述角度**：「改強調 XXX」（如：從「效能」改為「設計」）
- **換一個開場**：「開場不要問話，直接秀產品」
- **自由文字**：讓使用者寫自己的調整指示

每次拒絕 → 記錄使用者的調整指示，作為未來 prompt optimization 的資料集。

### 4.5 FAB + P 話術原則（**腳本生成必須遵守**）

所有腳本中「提到產品功能」的段落，**必須依 F → A → B → P 四層結構撰寫**，避免只講規格（客戶疲勞）或只講好處（客戶不信）。

#### 4.5.1 四層定義

| 層級 | 名稱 | 內容 | 典型長度 | 範例（8 倍光學變焦） |
|---|---|---|---|---|
| **F** | **Feature（規格事實）** | 可被 T1 來源驗證的客觀規格／數字／官方名稱 | ≤ 10 字 | 「最高 8 倍光學品質變焦」 |
| **A** | **Advantage（業界優勢）** | 此規格在**同品類中的相對優勢**或差異化 | ≤ 15 字 | 「iPhone 歷來最長，業界罕見」 |
| **B** | **Benefit（客戶好處）** | 對**這位客戶的具體生活／工作場景**有何影響；**必須依客群調整** | ≤ 20 字 | 「下次出差會議簡報，後排也拍得清楚」 |
| **P** | **Personal Twist（店員個人印記）** | 店員自己的故事／觀察／比喻；**可選但強烈建議** | ≤ 25 字 | 「我上週幫一個客戶拍女兒畢業典禮，他哭了」 |

#### 4.5.2 句式模板

標準 FAB+P 句群（店員一次說完 2-4 句）：

```
(F) 這顆是 <規格>。
(A) <業界優勢句>。
(B) 對您來說，<客戶情境句>。
(P) <店員個人印記，可選>。
```

**範例（iPhone 17 Pro × 商務人士）**：

> (F) 這是最高 8 倍光學品質變焦。
> (A) iPhone 歷來最長。
> (B) 您出差開會，會議室最後排也拍得清楚白板。
> (P) 我自己上週去東京出差，全靠它拍到整排 slide，沒跑到前面。

#### 4.5.3 Benefit 必須 persona-adaptive

**同一個 F+A，不同客群的 B 必須不同**。LLM 生成時依 `目標客群` 參數自動挑選：

| 功能 (F+A) | B（學生） | B（商務） | B（攝影師） | B（家庭） |
|---|---|---|---|---|
| 8 倍光學變焦 | 上課拍黑板看得清楚 | 會議白板、展場看板拍清楚 | 演唱會、運動會無壓力構圖 | 孩子畢業典禮後排拍到臉 |
| 均溫板散熱 | 整天課堂錄影不當機 | 連開 Zoom 全天不降頻 | 錄 ProRes 4K 長時間穩定 | 帶出去玩全天拍不中斷 |
| 鍛造鋁金屬 + 超瓷晶盾 2 | 書包裡放不怕刮 | 公事包天天丟，心裡踏實 | 外拍碰撞頻繁，保護相機等級 | 給孩子拿也安心 |

產品頁 `§ 五大賣點` 必須**為每個賣點提供至少 3 個 persona-adaptive 的 B 句**（學生 / 商務 / 攝影 / 其中三選，依產品目標客群挑選）。

#### 4.5.4 Personal Twist（P 層）規則

「P」是讓客戶**記得「是誰跟我講的」**的關鍵。規則：

1. **必須是第一人稱真實經驗**：「我自己…」「我上週幫一位客戶…」「我阿姨也在用…」
2. **禁止虛構**：若店員尚未累積個人故事 → 留空而非編造
3. **可選不強制**：但建議每場展示至少 1-2 處 P 層，增加記憶點
4. **前端設計**：腳本生成器輸出的 P 層可留 `<您的真實故事>` 空位，讓店員在訓練時自己填入並保存為「個人腳本版本」
5. **與 §7 紅線無衝突**：P 是個人感受，非產品規格，不需 T1 來源

#### 4.5.5 反模式（Anti-patterns）

| 反模式 | 錯誤範例 | 為何錯 |
|---|---|---|
| 🚫 **純 F 堆砌** | 「A19 Pro 6 核心 CPU、6 核心 GPU、神經網路加速器、均溫板蒸發冷卻、超瓷晶盾 2…」 | 規格疲勞；客戶大腦關機 |
| 🚫 **跳過 A 直接 F→B** | 「有 8 倍變焦，您出差拍簡報很方便。」 | 客戶不知道這規格「好不好」；無差異化說服力 |
| 🚫 **假 Benefit 浮誇** | 「用了之後您工作效率直接翻倍！」 | 無根據；損害銷售人員信用 |
| 🚫 **錯配 Persona 的 B** | 對學生說「會議白板拍得清楚」 | 客戶感受不到 relevance |
| 🚫 **P 層虛構故事** | 店員捏造從未發生的客戶案例 | 違反誠信；若被拆穿後果嚴重 |

#### 4.5.6 腳本生成器對 FAB+P 的執行邏輯

```
for each 核心賣點段落 in 生成腳本:
    F = 產品頁[賣點].feature_spec       # 從 §五大賣點 取規格
    A = 產品頁[賣點].advantage_vs_peers  # 從 §五大賣點 取優勢
    B = 產品頁[賣點].benefits_by_persona[選定客群]  # 依 persona 挑 B
    P = 可留 <placeholder>，讓店員訓練時自填
    
    output = f"(F) {F}。\n(A) {A}。\n(B) 對您來說，{B}。\n(P) {P or '<您的真實故事>'}"
```

如果產品頁 `§ 五大賣點` 缺少 F/A/B 結構資料 → 腳本生成器必須拒絕為該賣點生成，並在 `log.md` 標記「FAB 資料缺失，請補齊」。

---

## 5. 客群畫像模板（`sales-playbook/customer-personas/*`）

標準客群（至少覆蓋這些）：
- `student` — 學生
- `business` — 商務人士
- `photographer` — 攝影愛好者
- `creator` — 內容創作者
- `senior` — 長輩族群
- `gamer` — 遊戲玩家
- `family` — 家庭用戶

每個客群頁需包含：需求痛點、預算敏感度、關鍵決策因素、推薦產品組合。

---

## 6. Lint 檢查清單（每月執行）

- [ ] 所有產品頁 `last_updated` 是否 < 60 天？
- [ ] 所有 active 產品頁是否都有完整「三大獨家 Demo」段落（含 6a–6f 子項）？
- [ ] 所有 active 產品頁是否有「起售價」區塊？
- [ ] 所有 active 產品頁的「五大賣點」是否有完整 F / A / B(persona-adaptive) 結構（依 §4.5.3 至少 3 個 persona）？
- [ ] 官方術語是否遵循 §3.3 術語表（書寫工具／視覺智慧／清除／即時翻譯…）？
- [ ] Signature Demo 是否遵循 §4.1 選擇原則 + §4.2 節奏規範（預載素材優先、邊做邊說、口白 ≤15 字）？
- [ ] `index.md` 是否涵蓋所有實際檔案？
- [ ] 是否有 orphan 頁面（無任何 inbound `[[link]]`）？
- [ ] 是否有 `CONFLICT` 標記超過 14 天未解決？
- [ ] 是否有 `NEEDS REVIEW` 標記超過 30 天未處理？
- [ ] 停產產品是否已移到 `archive/`？
- [ ] 每款在售產品是否都有 `comparisons/` 對比頁？
- [ ] `/raw/` 中是否有 `ingest_status: pending` 超過 7 天未處理的 meta？
- [ ] `/raw/` 中是否有 `ingest_status: failed` 需人工介入的 meta？
- [ ] `/raw/` 中是否有孤立檔案（缺少對應 `.meta.json`）？
- [ ] 每個 active wiki 產品頁是否至少對應到 1 個 raw 來源（透過 `related_wiki_pages` 反查）？
- [ ] `pending-review` 檔案（relevance 5–6）累積是否 ≥ 20 篇需批次處理？
- [ ] 是否有單一來源過去 2 週平均 relevance < 5？（建議調整該來源設定或下線）
- [ ] 非 T1 / 非 admin-upload 的檔案是否都有 `relevance_score` 欄位？
- [ ] 所有 active 產品頁是否同時宣告 `ingest_managed_sections` 與 `human_owned_sections`（或明確寫 `[]` 接受預設）？
- [ ] 兩個段落所有權欄位的內容是否**無重疊**（§3.6 紅線）？
- [ ] 來源若設 `title_required_regex`，regex 本身是否合法（無語法錯誤）？
- [ ] `sources-config.yaml` 中 `enabled: false` 的來源是否有 `notes` 欄位說明原因？

---

## 7. 紅線規則（不可違反）

1. ❌ 不得撰寫未發表產品的資訊
2. ❌ 不得提供具體折扣、促銷話術
3. ❌ 不得貶低競品（可客觀比較規格，不可人身／品牌攻擊）
4. ❌ 不得承諾未公開的軟體更新時程
5. ❌ 不得引用 **T4 來源**（爆料／rumor／分析師預測）；**T2/T3 來源僅允許用於 §8.8 表中列出的用途**，不可作為產品頁規格／定價的事實依據（事實依據必須為 T1 官方來源）
6. ✅ 有疑問 → 標記 `> 🟡 NEEDS REVIEW` 交管理員裁決

---

## 8. Raw 資料層規範（`/raw/`）

### 8.1 設計原則

| 原則 | 說明 |
|---|---|
| **Immutable** | `/raw/` 內的檔案**只追加、不修改、不刪除**；稽核需保留原始快照 |
| **LLM 只讀** | Ingest Agent、Lint Agent 等所有 LLM 只能**讀取** `/raw/`，不可寫入 |
| **每檔配 meta** | 每個來源檔必須有同名的 `.meta.json` 描述檔 |
| **Hash 判變更** | Ingest 是否處理由 `content_hash` 決定，而非檔名或時間戳 |
| **不存 LLM 產物** | 摘要、翻譯、向量、提取結果**一律不得**寫入 `/raw/`，產物應放 `/wiki/` |

### 8.2 資料夾結構

```
raw/
├── apple-com-tw/                ← T1 Apple 台灣官網
├── apple-support/               ← T1 support.apple.com
├── apple-newsroom-en/           ← T1 Apple 官方新聞稿英文版
├── sales-coach/                 ← T1 Apple Sales Coach 內部 JSON
│
├── ars-technica/                ← T2 技術深度評測
├── six-colors/                  ← T2 Apple 生態系分析（Jason Snell）
├── macstories/                  ← T2 iPad/iOS 深度教學（Federico Viticci）
├── engadget/                    ← T2 消費電子評測主流
├── wired/                       ← T2 科技文化 + 評測
├── macworld/                    ← T2 Apple 長期評測
├── rtings/                      ← T2 標準化實驗室量化數據
│
├── petapixel/                   ← T2 攝影新聞 + 商業應用案例
├── no-film-school/              ← T2 獨立製片 / 商業影像工作流
├── austin-mann/                 ← T2 旅行攝影師田野實測 blog
├── halide-blog/                 ← T2 iPhone 相機技術深度剖析
├── cined/                       ← T2 專業電影／廣告攝影機評測
│
├── macrumors/                   ← T2-filtered 僅 /review/ + /roundup/ + /how-to/
├── 9to5mac/                     ← T2-filtered 僅 /category/review/ + /category/guides/
│
├── the-verge/                   ← T3 主流消費者視角
├── toms-guide/                  ← T3 購買決策導向評測
│
├── admin-uploads/               ← 管理員上傳（PDF/DOCX/PPTX）
└── assets/                      ← 共用二進位資產
    ├── images/
    └── videos/
```

**每個來源資料夾內部仍按 §8.3 週次／月份規則存放**（例：`ars-technica/2026-W18/iphone-17-pro-review_20260430.html`）。

**完整來源清單與 URL pattern 過濾規則請見 `sources-config.yaml`**（位於 repo 根）。

### 8.3 命名慣例

| 項目 | 格式 | 範例 |
|---|---|---|
| 來源資料夾 | `<source-kebab>/` | `apple-com-tw/`、`sales-coach/` |
| 週次子資料夾 | `YYYY-Www/`（ISO 8601 週次） | `2026-W18/` |
| 上傳月份資料夾 | `YYYY-MM/` | `2026-04/` |
| 原始檔 | `<slug>_YYYYMMDD.<ext>` | `iphone-17-pro_20260430.html` |
| Meta 檔 | 同名 + `.meta.json` | `iphone-17-pro_20260430.meta.json` |
| Admin 上傳檔 | `<slug>_<uploadId>.<ext>` | `spring-promo-briefing_abc123.pdf`（uploadId 為前 6 碼 hash） |

**檔名 slug 規則**：全小寫、kebab-case、ASCII only；中文來源需翻成英文 slug（避免跨平台檔案系統問題）。

### 8.4 `.meta.json` Schema（**必要欄位**）

```json
{
  "source_url": "https://www.apple.com/tw/iphone-17-pro/",
  "source_type": "apple-com-tw",
  "source_tier": "T1",
  "source_title": "iPhone 17 Pro 與 iPhone 17 Pro Max - Apple (台灣)",
  "fetched_at": "2026-04-30T03:15:22+08:00",
  "fetched_by": "weekly-cron-v1",
  "content_hash": "sha256:a3f8e7b2c9d4e1f5...",
  "content_type": "text/html",
  "content_size_bytes": 182934,
  "http_status": 200,
  "locale": "zh-TW",
  "relevance_score": 10,
  "relevance_reasoning": "Apple 官方 T1 來源預設滿分",
  "relevance_breakdown": {"d1_product_mention": 3, "d2_ecosystem": 2, "d3_training_potential": 3, "d4_timeliness": 2},
  "key_entities": ["iPhone 17 Pro", "A19 Pro", "Apple Intelligence"],
  "related_wiki_pages": ["products/iphone-17-pro"],
  "ingest_status": "pending",
  "ingest_log_ref": null,
  "notes": null
}
```

**欄位說明**：

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `source_url` | string | ✅ | 原始 URL（Admin 上傳可為 `upload://<file>`） |
| `source_type` | enum | ✅ | kebab-case 來源識別碼，需對應 `sources-config.yaml` 中的 key |
| `source_tier` | enum | ✅ | `T1` / `T2` / `T2-filtered` / `T3`（詳見 §8.8）；**Ingest Agent 依此決定可寫入哪些 wiki 段落** |
| `source_title` | string | ✅ | 來源頁面標題（HTML `<title>` 或文件標題） |
| `fetched_at` | ISO 8601 | ✅ | 擷取時間（含時區） |
| `fetched_by` | string | ✅ | 擷取者：`weekly-cron-v1` / `admin-upload` / `manual-trigger` |
| `content_hash` | string | ✅ | `sha256:` 前綴 + 64 位十六進位 |
| `content_type` | MIME | ✅ | `text/html` / `application/json` / `application/pdf` 等 |
| `content_size_bytes` | int | ✅ | 檔案大小（bytes） |
| `http_status` | int | （URL 來源必填） | HTTP 狀態碼 |
| `locale` | string | ✅ | `zh-TW` / `en-US` 等 BCP-47 |
| `relevance_score` | int 0–10 | ✅ | 相關性分數（詳見 §8.10）；T1 與 admin 預設 10 |
| `relevance_reasoning` | string | ⬜ | 一句話（≤ 40 字）說明為何此分數 |
| `relevance_breakdown` | object | ⬜ | D1–D4 四維度分項（供稽核） |
| `key_entities` | string[] | ⬜ | 打分 LLM 抽取的主要實體（產品名、技術名） |
| `related_wiki_pages` | string[] | ⬜ | 首次 ingest 後由 Agent 填入，供追溯 |
| `ingest_status` | enum | ✅ | `pending` / `scoring` / `approved` / `pending-review` / `processed` / `skipped-duplicate` / `skipped-trivial-change` / `skipped-filtered` / `skipped-low-relevance` / `failed` |
| `ingest_log_ref` | string \| null | ⬜ | 對應 `log.md` 的時間戳（處理後填入） |
| `notes` | string \| null | ⬜ | 補充說明，如「部分頁面 JS 動態渲染未擷取完整」 |

### 8.5 Ingest Agent 判斷流程

```
for meta in glob("/raw/**/*.meta.json"):
    if meta.ingest_status in ("processed", "skipped-low-relevance",
                               "skipped-filtered", "skipped-duplicate",
                               "skipped-trivial-change"):
        continue                          # 已處理過或已拒絕

    # Gate 1a: hash 精確比對（exact dedup）
    prior = log.lookup(meta.source_url)
    if prior and prior.content_hash == meta.content_hash:
        meta.ingest_status = "skipped-duplicate"
        continue

    # Gate 1b: 語意相似度（near-duplicate detection）
    # 當 hash 不同但文本實質上幾乎相同（僅格式微調、標點改動、時間戳更新），
    # 不應全頁重 ingest 以避免觸動 human-owned 段落
    if prior and prior.content_hash != meta.content_hash:
        similarity = cosine_similarity(
            embed(read(meta.sibling_txt)),
            embed(read(prior.sibling_txt))
        )
        if similarity >= 0.98:
            meta.ingest_status = "skipped-trivial-change"
            meta.notes = f"semantic similarity {similarity:.3f} ≥ 0.98; only last_updated bumped"
            wiki_page.frontmatter.last_updated = today()
            continue

    # Gate 2: URL / 標題過濾（§8.9；T2-filtered 才檢查）
    if not passes_url_and_title_filter(meta):
        meta.ingest_status = "skipped-filtered"
        continue

    # Gate 3: 相關性打分（§8.10）
    if meta.source_tier == "T1" or meta.source_type == "admin-upload":
        meta.relevance_score = 10         # T1/admin 預設滿分
    else:
        meta.ingest_status = "scoring"
        score, breakdown = llm_relevance_score(meta)
        meta.relevance_score = score
        meta.relevance_breakdown = breakdown

    if meta.relevance_score < 5:
        meta.ingest_status = "skipped-low-relevance"
        continue
    if meta.relevance_score < 7:
        meta.ingest_status = "pending-review"   # 管理員手動裁決
        continue
    # score ≥ 7 → 正常處理
    meta.ingest_status = "approved"

    # Gate 4: LLM 摘要寫入 wiki（依 §3.6 段落所有權規則）
    source_file = meta.sibling_file()
    target_pages = decide_target_wiki_pages(source_file, existing_wiki_pages)
    for page in target_pages:
        managed = page.frontmatter.ingest_managed_sections + DEFAULT_MANAGED
        locked  = page.frontmatter.human_owned_sections + DEFAULT_LOCKED
        diff    = llm_generate_section_diff(source_file, page)

        for section, new_content in diff.items():
            if section in locked:
                log.record_suggested_update(page, section, new_content)  # 不寫入本體
            elif section in managed:
                page.apply(section, new_content)                         # 寫入
            else:
                page.append(section, new_content, needs_review=True)     # 新段落

        page.frontmatter.last_updated = today()
        page.frontmatter.source_count += 1

    log.append_ingest(meta, target_pages)
    meta.ingest_status   = "processed"
    meta.ingest_log_ref  = log.last_timestamp
```

**說明**：

- **Gate 1a vs 1b**：一個是精確 hash 比對（快、無成本），一個是語意相似度（需 embedding，有成本但能處理「只改了版權年份」之類的微小變動）
- **0.98 門檻**：實務值；可在 `sources-config.yaml` 針對不同來源調整（官方站門檻可設更嚴，例如 0.99）
- **新增 `skipped-trivial-change` 狀態**：讓審計可區分「完全未變」vs「幾乎未變」
- **Gate 4 新邏輯**：依 §3.6 段落所有權，**逐段落**判斷是寫入、略過、或追加 NEEDS REVIEW

### 8.6 特殊情況處理

| 情境 | 處理方式 |
|---|---|
| **重複 URL 同週再擷取** | 新檔名加 `_v2` / `_v3` 後綴；若 hash 相同則拒絕寫入 |
| **HTTP 4xx / 5xx** | 仍寫入 meta（status 記錄失敗），但不產生內容檔；Lint 時提示人工處理 |
| **二進位檔（PDF / image）** | 放 `admin-uploads/` 或 `assets/`；`.meta.json` 的 `content_hash` 以檔案原始位元組計算 |
| **PDF / DOCX 需預處理** | 不得在 `/raw/` 存放「轉出的 txt／markdown」；轉換產物應視為 LLM 中介結果，僅存在記憶體或 `/wiki/` |
| **圖片重用** | Ingest Agent 提取網頁圖片時，若已在 `assets/images/` 存在相同 hash → 重用；否則下載並以 `<slug>_<hash前6碼>.<ext>` 命名 |
| **過期內容** | 不從 `/raw/` 刪除；Lint 標記 `source_url` 404 或已下架的檔案，由管理員決定是否 archive |

### 8.7 保留與備份

- `/raw/` 納入 Git 版控（文字檔），二進位資產透過 Git LFS 或 S3 後端儲存
- 建議保留週期：**最少 24 個月**（一年 + 一年比對基準）
- 超過 24 個月的 `.html` 來源可移動到 `raw/_archive/`，保留 `.meta.json` 供稽核

### 8.8 來源可信度分級（Source Tier）

| Tier | 定義 | 可寫入的 wiki 段落 | 範例來源 |
|---|---|---|---|
| **T1** | Apple 官方來源；事實與定價的唯一依據 | ✅ 全部段落（含 `products/*` 規格、定價、官方 Demo）<br>✅ 可作為 `[^1]` 主來源 | apple.com/tw, apple.com/newsroom, support.apple.com, Sales Coach |
| **T2** | 高信度第三方深度評測與分析，編輯標準明確 | ✅ `weekly-digest/*`（產業脈動、評測摘要）<br>✅ `concepts/*` 的「業界評價」或「使用案例」段落<br>✅ 產品頁的「常見客戶問題與回應」可引用評測觀點（但必須標明 T2 來源）<br>❌ **不可**作為 `products/*` 核心規格、定價的事實依據<br>✅ 可作為 `[^2]+` 輔助來源（主來源仍需 T1） | Ars Technica, Six Colors, MacStories, Engadget, Wired, Macworld, Rtings, PetaPixel, No Film School, Austin Mann, Halide Blog, CineD |
| **T2-filtered** | 內容混合 rumor 與 review 的站點；**僅允許 review / how-to / guides 路徑** | 同 T2；但 Ingest Agent 必須**先通過 §8.9 URL 過濾**才能寫入 | MacRumors `/review/*`, 9to5Mac `/category/review/*` |
| **T3** | 主流消費者視角媒體；觀點多、深度較淺 | ✅ 僅 `weekly-digest/*` 中的「市場視角 / 消費者印象」段落<br>❌ 不得進入 `products/*`、`concepts/*` | The Verge, Tom's Guide |
| **T4** | 爆料、leak、rumor、分析師預測 | ❌ **禁用**（即使來源網域在 T2/T3 列表中，只要內容屬 rumor 類，Ingest Agent 必須拒絕寫入） | MacRumors `/rumors/*`, 9to5Mac `/category/rumors/*`, 分析師爆料文 |

**Ingest Agent 必須遵守的 Tier 邏輯**：

1. 讀入 `.meta.json.source_tier`
2. 依上表判斷此來源可寫入哪些 wiki 路徑
3. 若 LLM 嘗試將 T2/T3 來源內容寫入不允許的段落 → **拒絕並在 log.md 記錄違規嘗試**
4. 每筆事實陳述的 footnote `[^N]`，若來源為 T2 → 必須在同段落有至少一個 T1 來源作為主來源
5. T4 內容即使意外進入 `/raw/`（例如 URL 過濾失誤），Ingest 階段必須**完全略過**，並將 `ingest_status` 設為 `skipped-filtered`

### 8.9 URL 過濾規則（T2-filtered 來源）

對於內容混合的站點（MacRumors、9to5Mac 等），必須同時滿足以下條件才可納入 ingest：

#### 8.9.1 允許／禁止 URL Pattern

| 站點 | ✅ Allow Pattern | ❌ Deny Pattern |
|---|---|---|
| **MacRumors** | `^https://www\.macrumors\.com/review/`<br>`^https://www\.macrumors\.com/roundup/`<br>`^https://www\.macrumors\.com/how-to/` | `^https://www\.macrumors\.com/rumors/`<br>`^https://www\.macrumors\.com/news/` |
| **9to5Mac** | `^https://9to5mac\.com/category/review/`<br>`^https://9to5mac\.com/category/guides/` | `^https://9to5mac\.com/category/rumors/` |

#### 8.9.2 標題關鍵字黑名單（T2-filtered 必過濾）

若文章標題（不分大小寫）含有下列任一詞 → 立即判定為 T4 並拒絕寫入：

```
leak, leaked, rumor, rumour, expected, reportedly, allegedly,
may launch, might launch, coming soon, unveiled ahead,
analyst predicts, supply chain says, tipster
```

#### 8.9.3 Cross-reference 規則

T2-filtered 來源**只能處理已在 Apple Newsroom 發表過的產品**。Ingest Agent 的檢查流程：

1. 從文章標題／內文抽取產品型號（如 `iPhone 17 Pro`）
2. 在 `raw/apple-newsroom-en/` 與 `raw/apple-com-tw/` 中搜尋該產品是否有 T1 來源
3. 若無 T1 來源 → **拒絕寫入**，`ingest_status = skipped-filtered`，note 標註「尚無 Apple 官方來源，待產品正式發表後重試」

#### 8.9.4 詳細設定檔

完整的來源設定（URL pattern、RSS、更新頻率、抓取深度等）請見 repo 根的 `sources-config.yaml`，此檔為 Ingest Agent 唯一的機器可讀設定來源。


#### 8.9.5 標題關鍵字白名單（title_required_regex）

**與 §8.9.2 黑名單互補**。適用於**任何 tier 的來源**（不只 T2-filtered）。

當來源網域同時發布多種主題（Apple 與非 Apple），URL pattern 無法區分時，用此欄位要求**標題必須匹配**某個 regex 才進入 ingest pipeline。

**語意**：
- 未提供 `title_required_regex` → 不檢查（相容舊行為）
- 提供 → 標題未匹配則 `ingest_status = skipped-filtered`，note 標註 "title did not match required_regex"

**範例**（已套用於 engadget、the-verge、toms-guide）：

```yaml
engadget:
  title_required_regex: "(?i)\\b(apple|iphone|ipad|mac|macbook|airpods|vision|watchos|ios|macos|apple intelligence)\\b"
```

**檢查順序**（§8.9 整體流程）：

1. `allow_url_patterns` — URL 必須匹配至少一項
2. `deny_url_patterns` — URL 不可匹配任一項
3. `title_blocklist_regex` — 標題**不可**匹配（黑名單）
4. `title_required_regex` — 標題**必須**匹配（白名單，**新**）
5. `require_apple_newsroom_cross_ref` — 產品需於 Newsroom 已出現

任一關卡失敗 → `skipped-filtered`。

### 8.10 相關性過濾器（Relevance Filter）

**問題背景**：2026-W18 pre-W2 爬蟲實測 30 篇顯示 **43% 的 RSS 內容與 Apple 門市訓練低相關**（娛樂、無關科技新聞、廣告業配等）。純 Tier 分級 + URL 過濾不足以防止噪音進入 ingest pipeline。

**設計原則**：
- 所有擷取內容仍寫入 `/raw/`（不可變、可稽核）
- 由 LLM 以 **0-10 分 rubric** 判斷與 RetailIQ 訓練主題相關性
- 分數決定 ingest_status 的路徑；低分**不刪除**、只**不處理**

#### 8.10.1 打分 Rubric（總分 0-10）

| 維度 | 評分標準 | 滿分 |
|---|---|---|
| **D1 Apple 產品直接提及** | 有具體 Apple 產品/服務名稱（iPhone / Mac / iPad / Apple Watch / AirPods / Apple Vision / Apple TV+ / Apple Music / iCloud 等） | 3 |
| **D2 Apple 生態／軟體／技術** | 涉及 Apple Intelligence / iOS / macOS / Swift / Final Cut Pro / Logic Pro / HomeKit / MagSafe / ProRes 等 | 2 |
| **D3 轉為訓練素材的潛力** | 能變成產品頁 B 層、反對處理、Demo 建議、客群畫像補充的內容 | 3 |
| **D4 時效性** | 與當代在售產品相關（新品發表/評測 > 舊機回顧 > 歷史文章） | 2 |

**打分步驟**：
1. 讀取 `<basename>.txt`（去除導覽雜訊後的內文）
2. 依 4 個維度各自評分
3. 加總為 0-10 分
4. 填入 `.meta.json.relevance_score` 與 `relevance_reasoning`（一句話說明為什麼）
5. 依分數對應 ingest_status：

#### 8.10.2 分數對應 ingest_status

| 分數 | ingest_status | 說明 | 後續處理 |
|---|---|---|---|
| **0–4** | `skipped-low-relevance` | 相關性不足 | 保留於 /raw/ 供稽核；不進 wiki；Lint 報告中可見 |
| **5–6** | `pending-review` | 邊界案例 | 每週 digest 中列出；由管理員手動裁決 |
| **7–10** | `approved` → `processed` | 相關性足夠 | 正常進入 LLM ingest 流程 |

#### 8.10.3 Prompt 範本（給打分 LLM 使用）

```
你是 RetailIQ 訓練系統的內容相關性評估員。

[你的任務]
讀下方文章，依 4 個維度打分（D1–D4），並輸出 JSON。

[評分維度]
D1 (0–3): Apple 產品直接提及
D2 (0–2): Apple 生態／軟體／技術
D3 (0–3): 對門市訓練（產品話術、反對處理、demo）的素材潛力
D4 (0–2): 時效性（當代在售產品 > 舊機回顧）

[文章]
標題：{source_title}
內文（前 3000 字）：{content_excerpt}

[輸出格式 — 嚴格 JSON，不加任何其他文字]
{
  "d1_product_mention": <0-3>,
  "d2_ecosystem": <0-2>,
  "d3_training_potential": <0-3>,
  "d4_timeliness": <0-2>,
  "total": <sum>,
  "reasoning": "<一句話，≤40 字，解釋為何這個總分>",
  "key_entities": [<最多 5 個，例: "iPhone 17 Pro", "Apple Intelligence">]
}
```

#### 8.10.4 特殊情況

| 情境 | 處理 |
|---|---|
| **T1 來源** | 略過打分，直接 `approved`（官方內容預設相關；節省 LLM 呼叫）<br>**注意**：Tier 分級以「內容特性」為準，非「官方/非官方」。`apple-newsroom-en` 因內容混雜 CSR / 財務公告等非訓練材料，已於 Issue #14（2026-05-07）re-tier 為 T2，由 Gate 3 打分決定。T1 僅保留純產品/支援頁面（apple-com-tw、apple-support）。|
| **Admin 上傳** | 略過打分，直接 `approved`（管理員已人工判斷） |
| **分數 5–6 的 pending-review 累積 ≥ 20 篇** | Lint 報警，提醒管理員批次處理 |
| **特定來源連續 5 篇 < 5 分** | 建議調整 `sources-config.yaml` 中該來源的 allow_url_patterns；Lint 提醒 |

#### 8.10.5 每週相關性報告

Ingest Agent 每週 cron 結束後，產出 `wiki/weekly-digest/YYYY-Www-relevance.md`，包含：

- 各來源擷取數 / 通過 / 拒絕 比例
- 低分 Top 10 文章列表（供管理員判斷是否調整來源）
- 高分 Top 10 亮點（方便管理員掌握本週重點）
- 來源健康度警報（若某來源平均分 < 5 持續 2 週 → 建議移除）

---

### 8.11 Gate 4 實作（LLM Ingest to Wiki）

v2.0 落地：Gate 4 的概念在 §8.5 已寫出，以下是**實作細節**對照（scripts + files）。

**5 個子 phase**（設計詳見 `wiki/design/gate4-ingest.md`）：

| Phase | 腳本 | 職責 |
|---|---|---|
| 1 Routing | `scripts/gate4_router.py` | `key_entities` × product tags → 候選 wiki 頁面，IDF 權重降低通用 tag 噪音 |
| 2 Propose | `scripts/gate4_proposer.py` | LLM 讀文章 + 目標頁，產結構化 JSON `{target_valid, proposals[]}` |
| 3 Apply | `scripts/gate4_applier.py` | Ownership filter（§3.6）+ hallucination guard + atomic write |
| 4 Queue | `scripts/gate4_queue.py` + `gate4_pipeline.py` | 寫 `wiki/ingest-queue/YYYY-Www/*.md` 給人類審核 |
| 5 Review CLI | `scripts/review_queue.py` | Reviewer 在 editor 勾 checkbox → `--apply-decided` 自動套用 + 歸檔 |

**Ownership 雙層防護**（v1.9 → v2.0 強化）：

1. **Prompt 層**：§5 prompt 明確要求 human-owned 段落只能用 `action: suggest`
2. **Filter 層**：無論 LLM 用什麼 action，`classify_section` 把 human-owned 段落上的所有 proposal 強制路由到 review queue（`gate4_applier.filter_proposals`）

**Hallucination guard**：`action: update` 必須附 `current_excerpt`（當前段落前 80 字），與實際段落 substring 比對；不匹配即拒絕寫入（`_excerpt_matches`）。

**Fan-out cap**：單篇文章最多寫入 3 個 wiki 頁（`MAX_FANOUT=3`，design D1）。超過視為 routing 不明確 → 全部送 review queue。

**Idempotency**：`meta.ingest_log_ref` 紀錄 apply 時間戳 + target，Gate 4 重跑時跳過已套用的文章。

**Review queue 生命週期**：

```
wiki/ingest-queue/
├── README.md                              ← workflow 說明
├── YYYY-Www/                              ← 本週待審（open）
│   ├── <slug>--<article-basename>.md      ← 一 (target × article) 一檔
│   └── _orphans/<article-basename>.md     ← 找不到目標頁的文章
└── _archive/YYYY-Www/                     ← 已 human-decided 的歷史檔
```

**Lint 建議**（待 v2.1 實作）：

- `wiki/ingest-queue/<current-week>/` 累積 > 20 檔 → 警告 reviewer backlog 過高
- 每個 queue file 必須有 `Decision:` 區塊才算 parseable

## 9. 版本

- Schema v1.0 — 2026-04-30 — 初版
- Schema v1.1 — 2026-04-30 — 新增 §4 「三大獨家 Demo（Signature Demos）」段落與 §4.1 選擇原則；同步更新 §6 Lint 檢查清單
- Schema v1.2 — 2026-04-30 — 新增 §3.3 官方術語一致性表（書寫工具／視覺智慧／清除等）、§3.4 定價區塊規則、§4.2 Demo 節奏規範（邊做邊說 + 預載素材優先 + 口白 ≤15 字）；產品頁模板新增「起售價」段落；子項編號由 5a-5f 改為 6a-6f；擴充 Lint 檢查項目
- Schema v1.3 — 2026-04-30 — §1 擴充為完整 repo 結構（raw + wiki 雙層）；新增 §8 「Raw 資料層規範」（資料夾結構、命名慣例、.meta.json schema、ingest 判斷流程、特殊情況處理、保留策略）；§2 Ingest Workflow 改以 `.meta.json` + content_hash 為驅動；版本章節改為 §9
- Schema v1.4 — 2026-04-30 — §7.5 紅線改為 Tier 分級制；§8.2 資料夾結構擴充為 15 個英文來源（apple-newsroom-en + 7 通用 T2 + 5 攝影 T2 + 2 T2-filtered + 2 T3）；§8.4 `.meta.json` 新增 `source_tier` 欄位；新增 §8.8 來源可信度分級表（T1/T2/T2-filtered/T3/T4）；新增 §8.9 URL 過濾規則（allow/deny patterns、標題黑名單、Newsroom cross-ref）；建立 `sources-config.yaml` 作為機器可讀設定
- Schema v1.5 — 2026-04-30 — 新增 §4.3 腳本長度變體（1 / 3 / 5 分鐘三種模式 + 段落分配矩陣 + 1 分鐘快閃展示特殊規則）；新增 §4.4 草稿迭代流程（兩段式：先純文字敘事草稿 → 使用者審核 → 再分段時間腳本；附敘事草稿格式規範與回饋選項）
- Schema v1.6 — 2026-04-30 — 新增 §4.5 FAB+P 話術原則（Feature / Advantage / Benefit-by-persona / Personal twist 四層結構，含句式模板、persona B 對照表、P 層規則、5 大反模式、生成器執行邏輯）；§4 產品頁模板的「五大賣點」格式改為強制 F/A/B 結構（每賣點至少 3 個 persona-adaptive B 句）；Lint 新增 FAB 結構完整性檢查；iPhone 17 Pro 五大賣點重寫為 FAB 範本示範
- Schema v1.7 — 2026-04-30 — 新增 §8.10 相關性過濾器（Relevance Filter：0-10 分 rubric 四維度 D1-D4、分數對應 ingest_status、LLM prompt 模板、T1/admin 豁免、每週相關性報告規範）；§8.4 `.meta.json` schema 擴充 relevance_score / relevance_reasoning / relevance_breakdown / key_entities 四個新欄位；ingest_status enum 新增 `scoring`、`approved`、`pending-review`、`skipped-low-relevance` 四個狀態；§8.5 ingest 流程圖更新為「4-gate」架構（hash / URL / relevance / LLM）；§6 Lint 新增 3 項 relevance 檢查；pre-W2 backfill 30 篇 meta（通過 50% / 拒絕 47% / 待審 3%），產出首份週報 `weekly-digest/2026-W18-relevance.md`
- Schema v1.8 — 2026-05-04 — 依週一 Test 3 + Test 5 發現補強：新增 §3.6「段落所有權（Segment Ownership）」完整規則（`ingest_managed_sections` / `human_owned_sections` frontmatter 雙欄位 + 12 段落預設值表 + Agent 執行邏輯）；§3.1 frontmatter schema 納入兩個新欄位；§8.5 ingest 流程 Gate 1 精細化為 1a (exact hash) + 1b (semantic similarity ≥ 0.98)；ingest_status 新增 `skipped-trivial-change` 狀態；Gate 4 改為**逐段落**判斷（依所有權清單決定寫入 / 略過 / NEEDS REVIEW append）；§6 Lint 新增 2 項段落所有權檢查；三款產品頁 frontmatter 回填兩個新欄位
- Schema v1.9 — 2026-05-05 — 新增 §8.9.5 `title_required_regex` 欄位（標題關鍵字白名單，與現有 blocklist 互補，適用任何 tier）；sources-config.yaml 升為 v1.1 套用新欄位並加嚴 7 個低分來源（engadget / macworld / no-film-school / petapixel / six-colors / the-verge / toms-guide）；新增 `enabled: false` 機制可暫時下線來源；預期下週平均分從 4.67 提升（待測）
- Schema v1.9.1 — 2026-05-05 — hotfix：sources-config v1.1.1 修正 two bug（six-colors 新式 /podcast/ URL 未擋、apple-support 因 fetch_method=http + 無 seed_urls 被 skip），相容性改動，無 schema semantic 變更
- Schema v1.9.2 — 2026-05-05 — hotfix 延續：Ingest Agent 移除 PyYAML 依賴，改用內建 `scripts/yaml_mini.py`（80 行最小 YAML 子集 parser）；動機：Homebrew Python 3.14 + PEP 668 + macOS sandbox 三重組合讓 pip install 不穩；效果：零 pip 依賴，安裝體驗完美
- Schema v1.9.3 — 2026-05-06 — infra: 建立 `dev-sandbox/` 離線實驗環境（107 unit tests + GitHub Actions CI），讓大型變更可在不污染 main 的前提下先跑完整測試；另加本地 `.git/hooks/pre-push` 跑 `python3 -m unittest discover tests/` 作為 PIE 環境無 GitHub Actions runner 的替代（PR #7 + #8）；相容性改動，無 schema semantic 變更
- Schema v1.9.4 — 2026-05-06 — v0.2 Gate 3（LLM 相關性打分）首次接入 Apple GenAI，實現 §8.10 完整閉環：`scripts/llm_client.py`（zero-dep urllib client，endpoint `http://localhost:11211/api/openai/v1`，chat=`gemini-2.5-flash-lite:latest`，embedding=`text-multilingual-embedding-002:latest`，env `APPLE_GENAI_MOCK=1` 可切 mock）；`scripts/relevance_scorer.py` 實作 §8.10.3 rubric prompt + `_parse_score` clamp/容錯；`scripts/ingest_agent.py` 加 Gate 3（T1/admin 豁免 → score=10，其他呼叫 LLM 打分並 atomic patch meta.json，失敗 graceful fallback 為 pending）；`--skip-scoring` CLI flag 保留 v0.1 行為；+31 mock tests（76→107 all green）；實戰對 W18 6 篇打分 5/6 與手動 baseline 同向，LLM 偏保守抓到「看似相關其實不相關」；首份自動化週報 `weekly-digest/2026-W19-relevance.md` 產出（PR #10 + #11）
- Schema v1.9.5 — 2026-05-07 — Issue #14 Option D：`apple-newsroom-en` re-tier T1 → T2（sources-config.yaml）；§8.10.4 更新：Tier 分級以「內容特性」為準（T1 = 純產品/支援頁，apple-com-tw + apple-support），apple-newsroom 雖為官方但內容混 CSR/財務 → T2 由 Gate 3 打分決定；W19 backfill 重跑後 2 篇 apple-newsroom `ingest_status` 由 approved 變為 pending-review（score=6 在 T2 規則下）
- Schema v2.0 — 2026-05-07 — **Full 5-gate pipeline milestone**：Gate 4（LLM ingest to wiki）完整落地（Phase 1 routing→Phase 2 propose→Phase 3 apply→Phase 4 queue→Phase 5 review CLI），端到端 live validated 於真實 Apple GenAI + W19 資料；新增 §8.11 實作文件對照 scripts/gate4_*.py；`wiki/ingest-queue/` 目錄正式啟用（含 _archive audit trail）；`yaml_mini._parse_list` 擴充支援 dict-in-list 以支援 `ingest_history` frontmatter round-trip（PR #13-#26，+113 tests 達 200 綠）
