# Contributing to RetailIQ

本文件說明如何安全地向 RetailIQ 貢獻變更，以及每種變更類型對應的審核流程。

---

## 🎯 核心原則

1. **沒有直接 push 到 `main`** — 所有變更走 PR
2. **AGENTS.md 是 single source of truth** — schema 先行，內容跟隨
3. **LLM 生成的內容必須可稽核** — 每個事實都有 footnote `[^N]` 對應 T1 來源
4. **紅線不可協商** — 見 `wiki/AGENTS.md § 7`

---

## 🌿 Branch 策略

| Branch 類型 | 用途 | 範例 |
|---|---|---|
| `main` | Protected；只能透過 PR merge | — |
| `ingest/YYYY-Www` | Ingest Agent 每週自動開 | `ingest/2026-W18` |
| `feat/*` | 新功能 | `feat/relevance-scorer` |
| `fix/*` | 錯誤修正 | `fix/lint-false-positive` |
| `schema/*` | AGENTS.md 升版 | `schema/v1.9-section-ownership` |
| `content/*` | 產品頁、客群頁、概念頁新增或更新 | `content/iphone-17-pro-q2-pricing` |
| `docs/*` | 純文件變更 | `docs/handover-2026-W19` |

---

## 📝 PR 檢查清單

所有 PR 作者需自我確認：

- [ ] 已跑 `python3 scripts/lint.py` 且 0 blocking errors
- [ ] AGENTS.md 有動到 → 已加 `schema vX.Y` 條目
- [ ] 產品頁有動到 human-owned 段落 → 已於 PR 說明理由
- [ ] 引入新 raw 來源 → 已更新 `wiki/sources-config.yaml` + `.meta.json` 格式正確
- [ ] 不含 `.env`、憑證、未發表產品資訊
- [ ] `wiki/log.md` 已 append 對應條目（append-only）
- [ ] PR 標題遵循 Conventional Commits 格式

---

## 🏷️ PR 標題格式

採用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>
```

**types**：
- `feat` — 新功能
- `fix` — 錯誤修正
- `docs` — 僅文件
- `schema` — AGENTS.md 升版
- `content` — wiki/ 內容更新
- `chore` — 雜務（依賴更新、build 設定）
- `test` — 測試相關

**範例**：
- `schema: v1.9 — add semantic similarity threshold per source`
- `content(iphone-17-pro): refresh pricing after Q2 promo ends`
- `feat(ingest): implement Gate 1b embedding comparison`
- `fix(lint): correct URL pattern for MacRumors review path`

**特殊 tag**：
- PR 標題含 `[compliance]` → 自動指派 @retailiq-legal
- PR 標題含 `[breaking]` → 需 2 位 reviewer

---

## 🔍 不同變更類型的審核流程

### Schema 變更（動 `wiki/AGENTS.md`）

最嚴謹的審核流程：

1. 先在 `HANDOVER.md` 或 issue 討論動機
2. 開 `schema/vX.Y-<描述>` branch
3. 同時更新 `wiki/log.md` append 條目
4. 若影響 meta.json → 需檢查 `scripts/lint.py` 同步更新
5. CODEOWNERS 會自動指派 `@retailiq-schema-reviewers`
6. 需 2 位 reviewer 同意

### 產品頁更新

**Ingest-managed 段落**（規格、定價等）：
- Ingest Agent 自動產出 `ingest/YYYY-Www` PR
- 1 位 content reviewer 同意即可 merge

**Human-owned 段落**（五大賣點、Signature Demo、Q&A、反對處理）：
- 人類手動編輯
- 需 `@retailiq-sales-reviewers` 同意
- 改 FAB 結構需附新版 persona B 句

### 新增 raw 來源

1. 更新 `wiki/sources-config.yaml`，新增 entry
2. 測試跑 `python3 scripts/pre_w2_crawler.py` 至少一次
3. PR 附上首週擷取的相關性分數快照
4. 若平均分 < 5 → PR 需討論是否值得保留

### 腳本生成範例

`/generated-scripts/*.md` 為 PM 與 sales reviewer 驗證用素材。PR 需：
- 附上參數（產品、persona、長度、重點）
- 說明是否對應 P 層填空策略

---

## ⚖️ 法務與合規

### Raw HTML 不入 git（`.gitignore` 已設）

為何：
- 第三方媒體 HTML 含原站著作權
- 減少 DMCA 風險
- 只保留 `.txt`（LLM 提取的純文字，已非原始表達形式）、`.meta.json`、`.zh-TW.md`

若你需要原始 HTML，請透過 **重跑爬蟲**（`scripts/pre_w2_crawler.py`）於本地重建，不要 commit。

### 未發表產品資訊

違反 `AGENTS.md § 7 紅線規則` 第 1 條。偵測方式：
- Ingest Agent 的 URL allow/deny pattern（見 `sources-config.yaml`）
- 標題關鍵字黑名單（leak、rumor、expected 等）
- PR reviewer 人工把關

若意外 commit 未發表資訊：
1. 立刻回覆 PR `/block` 防 merge
2. 通報 @willer + @retailiq-legal
3. 從 git history 移除（`git filter-repo`）

### GenAI 產出的內容

Ingest Agent 產出的每段 wiki 內容需：
- `.meta.json` 可追溯來源（Tier + URL）
- 產品頁規格段落必須有 T1 footnote `[^1]`
- T2/T3 內容只能進 weekly-digest 或「業界觀點」段落

---

## 🧪 本地開發流程

```bash
# 1. Clone
git clone https://github.apple.com/YOUR-ORG/retail-iq.git
cd retail-iq

# 2. Python 環境（stdlib only，不用 venv）
python3 --version  # 確認 >= 3.10

# 3. 開新 branch
git checkout -b feat/your-feature

# 4. 跑 lint
python3 scripts/lint.py

# 5. （若修改 raw）重跑 crawler
python3 scripts/pre_w2_crawler.py

# 6. Commit + push
git add .
git commit -m "feat(...): ..."
git push origin feat/your-feature

# 7. 在 GitHub 開 PR
```

---


## 🧪 Tests（v0.1.3+）

```bash
# 跑全部 tests
python3 -m unittest discover tests/ -v

# 只跑一個 module
python3 -m unittest tests.test_yaml_mini
python3 -m unittest tests.test_ingest_filters
```

### Dev sandbox 快速迭代（推薦）

對話 agent 使用 \`dev-sandbox/\`（對話目錄內）進行 TDD 迭代後，再 sync 回 repo：

```bash
# 從 repo 同步到 sandbox
bash dev-sandbox/sync-from-repo.sh

# 在 sandbox 改 + 測
cd dev-sandbox
python3 -m unittest discover tests/ -v

# 測通了搬回 repo
bash dev-sandbox/sync-to-repo.sh
```

## 🤖 GitHub Actions CI

每個 PR 與 push 到 main 會自動跑：
1. Unit tests（\`tests/\` 下所有 test_*.py）
2. Lint (\`scripts/lint.py\`)
3. Smoke test: load config, import ingest_agent, compile regexes

CI failed → PR 會擋 merge。


## 🪝 Pre-push Hook（PIE Actions 替代）

PIE 個人 repo 不支援 GitHub Actions，但我們有本地 git hook 當 CI 替身。

### 首次安裝（每個 clone）

```bash
bash scripts/install-hooks.sh
```

這會設 `core.hooksPath = .githooks`，啟用 `.githooks/pre-push`。

### 每次 push 會自動跑

1. `python3 -m unittest discover tests/`
2. 載入 `wiki/sources-config.yaml`
3. Import `ingest_agent` 檢查無語法錯誤
4. 驗證所有 regex patterns compile 成功

**若某項失敗 → push 被擋**。可用 `git push --no-verify` 強制（不建議）。

### 不想用？

```bash
git config --unset core.hooksPath
```

## 💬 問題聯絡

- **技術 / Schema** — @willer
- **產品頁內容** — @retailiq-sales-reviewers
- **合規 / 法務** — `[compliance]` PR tag
- **緊急** — Slack `#retailiq`（待建立）

---

感謝貢獻！📚
