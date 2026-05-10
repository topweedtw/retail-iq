# RetailIQ — 門市銷售訓練系統

> 一個由 LLM 自動維護的 Wiki 知識平台，人類的角色是確保內容正確合規，同時確保使用者體驗。
> **Status**: 🚀 **v0.6** — Full 5-gate pipeline + FastAPI 後端 + Admin 管理後台

一套以 Karpathy LLM Wiki 模式建構的內部訓練系統，讓門市人員學習產品知識、玩測驗遊戲、生成展示腳本。知識層由 LLM 從官方與精選第三方來源自動維護；管理層由人類透過後台與 PR 審核把關。

---

## 📂 Repo 結構

```
retail-iq/
├── api/                         ← FastAPI 後端
│   ├── main.py                  ← 應用程式入口（CORS、路由掛載）
│   ├── requirements.txt         ← fastapi + uvicorn + python-multipart
│   └── routers/
│       ├── products.py          ← GET /api/products, /api/products/:slug
│       ├── scripts_gen.py       ← POST /api/scripts/generate
│       ├── ingest.py            ← GET /status, /sources + POST /sources, /upload
│       └── review.py            ← GET /api/review-queue, /stats
│
├── admin/                       ← 管理後台（Next.js + Tailwind，Pro Dashboard 暗色風格）
│   └── src/app/
│       ├── page.tsx             ← 儀表板（KPI + 狀態分布 + bar chart）
│       ├── products/            ← 產品列表 + [slug] 詳情
│       ├── ingest/              ← Pipeline 狀態 + 上傳文件
│       ├── sources/             ← 來源列表 + 新增來源
│       └── review/              ← Review Queue UI
│
├── web/                         ← 門市 iPad UI（Next.js，Gamified 風格，開發中）
│
├── wiki/                        ← LLM 維護的結構化知識層
│   ├── AGENTS.md                ← 核心 schema（v2.0，9 章 + §8.11 Gate 4 impl）
│   ├── index.md                 ← 全站目錄
│   ├── log.md                   ← 時間軸日誌（append-only）
│   ├── sources-config.yaml      ← 21 個來源的 URL/tier/過濾設定（15 enabled）
│   ├── products/                ← 產品頁（FAB+P 結構，7 款）
│   ├── weekly-digest/           ← 週報（W18 + W19）
│   ├── design/                  ← 架構設計文件
│   ├── handover/                ← Session handover 歷史
│   └── ingest-queue/            ← Gate 4 人工審核佇列（含 _archive/）
│
├── raw/                         ← 不可變原始資料層（LLM 只讀）
│   └── <source>/YYYY-Www/
│       ├── *.txt                ← 提取純文字
│       └── *.meta.json          ← schema §8.4 元資料
│   ⚠️  *.html 不 commit（版權考量，見 CONTRIBUTING.md）
│
├── scripts/                     ← Ingest Pipeline（Python package，stdlib only）
│   ├── __init__.py              ← package 入口（from scripts.xxx import 可用）
│   ├── ingest_agent.py          ← 主 pipeline（full 5-gate）
│   ├── llm_client.py            ← OpenAI-compatible 客戶端 + MockLLMClient
│   ├── yaml_mini.py             ← 零依賴 YAML parser
│   ├── embedding_index.py       ← Gate 1b 嵌入相似度
│   ├── relevance_scorer.py      ← Gate 3 rubric 打分
│   ├── gate4_router.py          ← Phase 1：entity × IDF routing
│   ├── gate4_proposer.py        ← Phase 2：LLM 結構化提案
│   ├── gate4_applier.py         ← Phase 3：apply + diff-merge + safety check
│   ├── gate4_queue.py           ← Phase 4：review queue
│   ├── gate4_pipeline.py        ← Phase 4：pipeline 整合 orchestration
│   ├── review_queue.py          ← Phase 5：human review CLI
│   ├── generate_weekly_digest.py← 自動化週報產生器
│   ├── gate4_lint.py            ← Gate 4 hygiene lint（6 rules）
│   └── lint.py                  ← §6 內容 lint
│
├── tests/                       ← 302 tests, ~0.25s, stdlib unittest
├── pyproject.toml               ← pip install -e . 支援
├── .env.example                 ← 環境變數範本
├── README.md
├── CONTRIBUTING.md
└── LICENSE.md
```

---

## 🎯 核心概念 — 3 分鐘理解本專案

### 1. 知識庫不是 RAG

本系統採 **Karpathy LLM Wiki 模式**：LLM **持續維護** 一個結構化 markdown wiki（不是每次檢索 chunks）。知識 compounding；使用者讀 wiki，LLM 寫 wiki。

### 2. 三層資料分離

| 層 | 內容 | 可寫者 |
|---|---|---|
| **raw/** | 原始擷取（txt、meta.json） | Crawler / Admin upload（immutable） |
| **wiki/** | 結構化 markdown | LLM Ingest Agent（PR 審核後）|
| **AGENTS.md** | Schema 規則 | 人類（唯一） |

### 3. Ingest Pipeline 有 5 個 Gate

Raw 到 Wiki 不是直通車。每篇內容必須通過：

- **Gate 1a** Hash dedup（exact SHA-256 match）
- **Gate 1b** Embedding similarity（cosine ≥ 0.98 視為 trivial change）
- **Gate 2** URL allow/deny + 標題黑名單
- **Gate 3** LLM 相關性打分（0-10 分 rubric；< 5 拒絕；5-6 pending review；≥7 approved）
- **Gate 4** LLM ingest to wiki — 5 phases：routing → propose → apply → queue → review

### 4. FAB + P 話術結構

- **F** Feature（規格事實，T1 來源）
- **A** Advantage（業界差異化）
- **B** Benefit（依客群變化的好處）
- **P** Personal Twist（店員個人故事；留空讓店員自填）

---

## 🚀 快速開始

### 環境設定

```bash
# 1. Clone
git clone https://github.com/topweedtw/retail-iq.git
cd retail-iq

# 2. Python 環境（pipeline）
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt   # FastAPI 依賴
pip install -e .                      # scripts/ package 安裝（可選）

# 3. 環境變數
cp .env.example .env
# 編輯 .env，填入 OPENAI_API_KEY=sk-...
source .env
```

### 啟動服務

```bash
# API 後端（port 8000）
uvicorn api.main:app --reload --port 8000

# 管理後台（port 3001）
cd admin && npm run dev -- --port 3001
# 開啟 http://localhost:3001
```

### 跑 Pipeline

```bash
# 完整 pipeline（爬蟲 + Gates 1-5）
python3 -m scripts.ingest_agent --limit 3

# 只跑 Gate 4（不抓新文，只 ingest 現有 approved 文章）
python3 -m scripts.ingest_agent --gate4-only --week 2026-W19

# Review queue
python3 -m scripts.review_queue --list
python3 -m scripts.review_queue --stats
python3 -m scripts.review_queue --apply-decided [--dry-run]
```

### 測試 & Lint

```bash
python3 -m unittest discover tests/   # 302 tests, ~0.25s
python3 scripts/lint.py               # 內容 lint
python3 scripts/gate4_lint.py         # Gate 4 hygiene
```

---

## 📅 專案時程

| 階段 | 期間 | 交付 | 狀態 |
|---|---|---|---|
| **W1** Schema + Wiki 骨架 | 2026-04-23 ~ 04-30 | AGENTS.md v1.0 → v1.8；sources-config.yaml；3 款產品頁；30 篇 raw 測試資料 | ✅ 結案 |
| **W2** Ingest Agent | 2026-05-04 ~ 05-07 | Full 5-gate pipeline；review queue CLI；W19 端到端驗證 | ✅ 結案 |
| **v0.6** 強化層 | 2026-05-07 | Gate 4 diff-merge + safety check；cost tracking；6-rule lint；7 款產品頁 | ✅ 結案 |
| **v0.7** 前後端骨架 | 2026-05-10 | scripts/ package 化；OpenAI API；FastAPI 後端；Admin 管理後台（8 頁）；新增來源 + 上傳文件 | ✅ 結案 |
| **W3** 門市 UI | — | 門市 iPad Gamified UI（腳本生成器）；腳本生成 LLM 接入 | ⏭️ Next |
| **W4** Pilot | — | 10 人內測 → 100 人信義店試營運 | ⏭️ |

---

## 📊 當前 KPI（2026-05-10）

| 指標 | 值 |
|---|---|
| Pipeline gates | 5/5 完成 |
| 產品頁 | 7 款（NT$ 價格人工核實）|
| Tests | **302** 全綠（~0.25s）|
| PRs merged | **48** |
| LLM provider | OpenAI API（gpt-4o-mini + text-embedding-3-small）|
| API endpoints | **8**（products / scripts / ingest / review-queue）|
| Admin 頁面 | **8**（儀表板 / 產品 / Ingest / 上傳 / 來源 / 新增來源 / Review Queue）|
| External deps (pipeline) | 0（Python stdlib only）|
| External deps (API) | 3（fastapi + uvicorn + python-multipart）|
| Lint warnings | 8（LOW-RELEVANCE SOURCE，正常管理提醒）|

---

## 🔗 相關資源

- **最新 Handover**：`wiki/handover/HANDOVER-2026-05-10.md`
- **Schema**：`wiki/AGENTS.md`（v2.0）
- **API 文件**：http://localhost:8000/docs（Swagger UI，需先啟動 API）
- **Karpathy 原 gist**：https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## 👥 聯絡

- Schema / Architecture: @topweedtw
- Content review: `CODEOWNERS` 定義
- Compliance: 依照 `LICENSE.md` 與 `CONTRIBUTING.md § 法務與合規`
