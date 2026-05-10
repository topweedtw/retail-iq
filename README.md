# RetailIQ — 門市銷售訓練系統

> 銷售訓練用 LLM-maintained 知識平台
> **Status**: 🎯 **v0.5beta** — Full 5-gate pipeline + Gate 4 structural diff-merge（Schema v2.0）

一套以 Karpathy LLM Wiki 模式建構的內部訓練系統，讓門市人員學習產品知識、玩測驗遊戲、生成展示腳本。知識層由 LLM 從官方與精選第三方來源自動維護；管理層由人類透過 PR 審核把關。

---

## 📂 Repo 結構

```
retail-iq/
├── wiki/                        ← LLM 維護的結構化知識層
│   ├── AGENTS.md                ← 核心 schema（v2.0，9 章 + §8.11 Gate 4 impl）
│   ├── index.md                 ← 全站目錄
│   ├── log.md                   ← 時間軸日誌（append-only）
│   ├── sources-config.yaml      ← 15 個來源的 URL/tier/過濾設定
│   ├── products/                ← 產品頁（FAB+P 結構，7 款）
│   ├── concepts/                ← 跨產品概念（stub）
│   ├── comparisons/             ← 產品比較（stub）
│   ├── sales-playbook/          ← 銷售話術（human-owned，stub）
│   ├── weekly-digest/           ← 週報（W18 + W19）
│   ├── archive/                 ← 停產歸檔（stub）
│   ├── design/                  ← 架構設計文件（v2.0+）
│   ├── handover/                ← Session handover 歷史（v2.0+）
│   └── ingest-queue/            ← Gate 4 人工審核佇列（含 _archive/）
│
├── raw/                         ← 不可變原始資料層（LLM 只讀）
│   └── <source>/YYYY-Www/       ← 每週擷取
│       ├── *.txt                ← 提取純文字（可 diff）
│       ├── *.meta.json          ← schema §8.4 元資料
│       └── *.zh-TW.md           ← 繁中摘要 + 相關性判斷
│   ⚠️  *.html 不 commit（版權考量，見 CONTRIBUTING.md）
│
├── scripts/                     ← Ingest Agent + 工具（stdlib only，sandbox-safe）
│   ├── ingest_agent.py          ← 主 pipeline（full 5-gate，含 --skip-* flags）
│   ├── yaml_mini.py             ← 零依賴 YAML parser（支援 dict-in-list）
│   ├── llm_client.py            ← Apple GenAI client（chat + embedding）
│   ├── embedding_index.py       ← Gate 1b 嵌入相似度
│   ├── relevance_scorer.py      ← Gate 3 rubric 打分
│   ├── gate4_router.py          ← Phase 1：entity × IDF routing
│   ├── gate4_proposer.py        ← Phase 2：LLM 結構化提案
│   ├── gate4_applier.py         ← Phase 3：apply + diff-merge + safety check
│   ├── gate4_queue.py           ← Phase 4：review queue
│   ├── gate4_pipeline.py        ← Phase 4：pipeline 整合 orchestration
│   ├── review_queue.py          ← Phase 5：human review CLI
│   ├── weekly_digest.py         ← 自動化週報產生器
│   ├── gate4_lint.py            ← Gate 4 hygiene lint（5 rules）
│   └── lint.py                  ← §6 內容 lint
│
├── tests/                       ← 254 tests, ~0.25s, stdlib unittest
├── frontend-designs/            ← 3 種風格 HTML mockup
├── generated-scripts/           ← 腳本生成器 demo 產出
│
├── README.md                    ← 本檔
├── CONTRIBUTING.md              ← PR 流程
├── CODEOWNERS                   ← PR 審核指派
└── LICENSE.md                   ← 內部使用宣告
```

---

## 🎯 核心概念 — 3 分鐘理解本專案

### 1. 知識庫不是 RAG

本系統採 **Karpathy LLM Wiki 模式**：LLM **持續維護** 一個結構化 markdown wiki（不是每次檢索 chunks）。知識 compounding；使用者讀 wiki，LLM 寫 wiki。

### 2. 三層資料分離

| 層 | 內容 | 可寫者 |
|---|---|---|
| **raw/** | 原始擷取（HTML、JSON、PDF） | Crawler / Admin upload（immutable） |
| **wiki/** | 結構化 markdown | LLM Ingest Agent（PR 審核後）|
| **AGENTS.md** | Schema 規則 | 人類（唯一） |

### 3. Ingest Pipeline 有 5 個 Gate

Raw 到 Wiki 不是直通車。每篇內容必須通過：

- **Gate 1a** Hash dedup（exact SHA-256 match）
- **Gate 1b** Embedding similarity（cosine ≥ 0.98 視為 trivial change）
- **Gate 2** URL allow/deny + 標題黑名單（T2-filtered 來源擋 rumor 路徑）
- **Gate 3** LLM 相關性打分（0-10 分 rubric；< 5 拒絕；5-6 pending review；≥7 approved）
- **Gate 4** LLM ingest to wiki — 5 phases：routing → propose → apply → queue → review
  - **v0.6 升級**：`update` action 改為 structural diff-merge，row-level 保留舊 table + safety check（≥ 60% 舊長度才直接寫入，否則降級 review queue）

### 4. FAB + P 話術結構

所有客戶導向腳本必須遵循：

- **F** Feature（規格事實，T1 來源）
- **A** Advantage（業界差異化）
- **B** Benefit（依客群變化的好處；每賣點至少 3 個 persona）
- **P** Personal Twist（店員個人故事；留空讓店員自填）

---

## 🚀 快速開始

### 瀏覽專案

開這幾個檔最快進入狀況：

1. **`wiki/handover/HANDOVER-2026-05-07.md`** — 最新 session 狀態（§1-§12 EOD + §13 After-EOD）
2. **`wiki/AGENTS.md`** — 完整 schema（v2.0，9 章 + §8.11 Gate 4 實作對照）
3. **`wiki/log.md`** — 版本時間軸（v1.0 → v2.0 全紀錄）
4. **`wiki/design/gate4-ingest.md`** — Gate 4 設計文件（389 行）
5. **`frontend-designs/README.md`** — 前端 UI 設計三種風格

### 跑完整 pipeline（all 5 gates）

```bash
python3 scripts/ingest_agent.py --limit 3
```

可選 skip flag：`--skip-gate1b`、`--skip-scoring`、`--skip-gate4`、`--gate4-only`（不抓新文，只跑 Gate 4）。

### Gate 4 獨立工具

```bash
python3 scripts/gate4_router.py --all-w 2026-W19
python3 scripts/gate4_proposer.py <meta.json> <slug>
python3 scripts/gate4_applier.py <meta.json> <slug> --apply
python3 scripts/review_queue.py --list
python3 scripts/review_queue.py --stats
python3 scripts/review_queue.py --apply-decided [--dry-run]
```

### 週報產生

```bash
python3 scripts/weekly_digest.py 2026-W19
```

### 測試

```bash
python3 -m unittest discover tests/   # 254 tests, ~0.25s, 全綠
```

### Lint

```bash
python3 scripts/lint.py        # 內容 lint
python3 scripts/gate4_lint.py  # Gate 4 hygiene（queue backlog、格式、成本）
```

---

## 📅 專案時程

| 階段 | 期間 | 交付 | 狀態 |
|---|---|---|---|
| **W1** Schema + Wiki 骨架 | 2026-04-23 ~ 04-30 | AGENTS.md v1.0 → v1.8（9 章 + 40+ 小節）；`sources-config.yaml` 15 來源 tier 分級；3 款 bootstrap 產品頁（iphone-17-pro、ipad-air、macbook-neo）含 FAB+P 完整範例；pre-W2 crawler 產 30 篇 raw 測試資料；lint + hash dedup 雛型 | ✅ 結案 |
| **W2** Ingest Agent | 2026-05-04 ~ 05-07 | Full 5-gate pipeline（1a hash + 1b embedding + 2 URL filter + 3 LLM rubric + 4 LLM ingest-to-wiki 五 phases）；Apple GenAI 整合；review queue CLI；W19 live-validated 端到端跑過真實資料 | ✅ 結案 |
| **v0.6** 強化層 | 2026-05-07 | Gate 4 structural diff-merge + safety check；cost tracking（per-week + cross-week trend + budget alert）；6-rule hygiene lint（含 review file format）；+4 產品頁至 7 款、NT$ 價格全人工核實 | ✅ 結案 |
| **W2+** 前端骨架 | — | Next.js 腳本生成器 UI + 管理後台 + Review queue UI | ⏭️ Next |
| **W3** Pilot | — | 10 人內測 → 100 人信義店試營運 → end-to-end 門市 review cycle 驗證 | ⏭️ |

---

## 📊 當前 KPI（2026-05-07）

| 指標 | 值 |
|---|---|
| Pipeline gates | 5/5 完成（1a + 1b + 2 + 3 + 4，含 v0.6 diff-merge + safety check）|
| 產品頁 | 7 款（NT$ 價格全部人工核實 from apple.com/tw）|
| Wiki 結構完整度 | 100%（11 個目錄齊備）|
| Tests | **285** 全綠（~0.3s）|
| PRs merged | **42**（全走 branch protection）|
| Git tag | `v0.5beta`（首個 release tag，2026-05-07）|
| External deps | 0（Python stdlib only）|
| Embedding cache | 29 篇 |
| Gate 4 lint rules | 6（L1 backlog、L2 parseable、L3 log_ref integrity、L4 orphan age、L5 dupe、L6 format）|
| Cost tracking | per-week（digest 內建）+ cross-week trend（`_cost-trend.md`）+ budget alert |

---

## 🔗 相關資源

- **Skill**: `~/.claude/skills/llm-wiki-builder/` — 本專案方法論萃取，可復用於其他 LLM Wiki 專案
- **Karpathy 原 gist**: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## 👥 聯絡

- Schema / Architecture: @topweedtw
- Content review: `CODEOWNERS` 定義
- Compliance: 依照 `LICENSE.md` 與 `CONTRIBUTING.md § 法務與合規`

---


