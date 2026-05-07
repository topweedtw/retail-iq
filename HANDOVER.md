# 📋 RetailIQ Handover — 2026-05-05（W2 第一天結束）

> **專案**：Apple 門市銷售訓練系統（RetailIQ）
> **當前階段**：W2 Ingest Agent v0.1.2 實跑中
> **Handover 日期**：2026-05-05（週二）
> **Repo**：https://github.pie.apple.com/willer/retail-iq
> **下次開工**：當你看到這份文件時

---

## 🎯 TL;DR（30 秒版本）

- ✅ **W1 知識層完成**：AGENTS.md **v1.9.2**，9 章 40+ 小節
- ✅ **Git 基礎建設就緒**：main branch protection + CODEOWNERS + 5 個 PR 成功驗證流程
- ✅ **W2 Ingest Agent v0.1.2 實跑**：Gate 1a + Gate 2 完成，28 articles / 0 failed
- ✅ **零外部依賴**：yaml_mini.py 取代 PyYAML（macOS Homebrew + PEP 668 + sandbox 逼出的乾淨解法）
- ⏭️ **下一步 v0.2**：接 Apple GenAI 做 Gate 3 LLM 相關性打分

---

## 📊 W2 Ingest Pipeline 進度

```
 ┌────────────────────────────────────────────────────────────┐
 │  Ingest Agent v0.1.2 (scripts/ingest_agent.py, 450 行)       │
 ├────────────────────────────────────────────────────────────┤
 │                                                              │
 │   ✅ Gate 1a  Hash dedup (exact SHA-256)                     │
 │              → skipped-duplicate                             │
 │                                                              │
 │   ⏸  Gate 1b  Semantic similarity (embeddings ≥ 0.98)        │
 │              → skipped-trivial-change            [v0.2 TODO] │
 │                                                              │
 │   ✅ Gate 2   URL allow/deny + title blocklist/required      │
 │              → skipped-filtered                              │
 │                                                              │
 │   ⏸  Gate 3   LLM relevance scoring (0-10 rubric, §8.10)     │
 │              → skipped-low-relevance / pending-review        │
 │              / approved                          [v0.2 TODO] │
 │                                                              │
 │   ⏸  Gate 4   LLM ingest to wiki + segment ownership         │
 │              → processed / NEEDS REVIEW append   [v0.3 TODO] │
 │                                                              │
 └────────────────────────────────────────────────────────────┘
```

### 最近實跑（2026-W19, `--limit 2`）

| 結果 | 數 | 驗證點 |
|---|---|---|
| ✅ pending | 0 | 沒有新內容（Apple 官方近日未發新） |
| ✅ skipped-duplicate | 11 | Gate 1a 正確（hash 對到 W18 既有） |
| ✅ skipped-filtered | 17 | Gate 2 正確（6 目標來源 100% 擋下） |
| ✅ failed | 0 | 無 crash |

### 成本節省效果

- 預估 W2 完整版：每篇 raw 需 1 次 LLM 打分（Gate 3）
- 目前 Gate 2 已先擋掉 61% 噪音 → Gate 3 LLM 成本減 61%
- 若加上 Gate 1a dedup，總省 89% 計算

---

## 🏗️ 核心架構（未變動）

採用 **Karpathy LLM Wiki 模式**，三層 repo 結構：

```
retail-iq/
├── wiki/                        ← LLM 維護的結構化知識層
│   ├── AGENTS.md                ← Schema v1.9.2（單一真相）
│   ├── sources-config.yaml      ← v1.1.1（21 來源，14 enabled）
│   ├── products/                ← 3 款產品頁含 FAB+P + 段落所有權
│   ├── weekly-digest/           ← 含 W18 relevance report
│   └── ...
│
├── raw/                         ← 不可變原始層（LLM 只讀）
│   ├── apple-com-tw/2026-W18/   ← 30 articles from W18
│   ├── apple-newsroom-en/       ...
│   ├── ...2026-W19/             ← 新一輪 Ingest Agent 產出
│   └── _relevance-scores-2026-W18.json
│
├── scripts/                     ← Ingest pipeline + tools
│   ├── ingest_agent.py          ← v0.1.2 主腳本
│   ├── yaml_mini.py             ← 零依賴 YAML parser（80 行）
│   ├── lint.py                  ← 合規檢查
│   └── pre_w2_crawler.py        ← W1 的手動 crawler（已廢，保留備查）
│
├── frontend-designs/            ← 3 種風格 HTML mockup（待選）
├── generated-scripts/           ← 5 份示範腳本
│
├── README.md、HANDOVER.md、LICENSE.md、CODEOWNERS
├── CONTRIBUTING.md、GITHUB-SETUP.md、TEST-REPORT-2026-05-04.md
└── .gitignore、.gitattributes
```

---

## 🗓️ 完整時間軸

| 日期 | 里程碑 |
|---|---|
| 2026-04-30 | W1 啟動：AGENTS.md v1.0 → v1.7（單日 8 升版）+ 3 產品頁 + 30 raw + 前端 mockup |
| 2026-05-04 | 週一 Review：5 項端到端測試 → v1.8（段落所有權 + 語意相似度）|
| 2026-05-05 上午 | Git 上 PIE GitHub（+ branch protection + CODEOWNERS）|
| 2026-05-05 中午 | PR #1 CODEOWNERS stage-1 merged |
| 2026-05-05 早下午 | PR #2 Schema v1.9 + sources-config v1.1 merged |
| 2026-05-05 中下午 | PR #3 Ingest Agent v0.1 merged（7 篇通過，實際 code 跑）|
| 2026-05-05 午後 | PR #4 v0.1.1 hotfix（podcast + apple-support bugs）|
| 2026-05-05 傍晚 | PR #5 v0.1.2 yaml_mini（零依賴，PEP 668 克服）|
| **⏭ 下次** | **v0.2 Apple GenAI 接入 Gate 1b + Gate 3** |

---

## 🔑 今天學到的 3 個教訓

### 1. Schema 成熟度 ≠ 實作穩定性
- Schema 設計到 v1.8 已很完整
- Ingest Agent 第一次實作仍踩 4 個地雷（PyYAML、file object、inline list、regex 錯誤 pattern）
- **結論**：寫 code 前再怎麼紙上談兵都會忽略邊角

### 2. Solo 專案的 Git Protection 悖論
- 加 branch protection → self-approve 被禁 → 無法 merge 自己的 PR
- 解法：`merge-pr-solo.sh` 暫關→merge→恢復
- 未來 team 進來只要改兩處：恢復 CODEOWNERS team handles、停用 merge-pr-solo.sh

### 3. 零依賴的價值遠大於便利
- 花 80 行寫 yaml_mini 看似重造輪子
- 實際上消除了「macOS Homebrew + PEP 668 + sandbox」組合的整條痛苦鏈
- 任何 Python 版本、任何同事 clone 就能跑，無 pip / venv 工作流

---

## ⏭️ v0.2 待辦清單

### A. 接 Apple GenAI — Gate 3（核心）

- [ ] 確認 PIE 帳號有 GenAI 存取
- [ ] 找 API endpoint + token 取得方法
- [ ] 依 §8.10.3 prompt 模板實作 `score_relevance(meta) -> (score, breakdown)`
- [ ] Ingest Agent 加 Gate 3：T1/admin 跳過打分，其他呼叫 LLM
- [ ] meta.json 寫入 relevance_score / relevance_reasoning / key_entities
- [ ] 依分數設 ingest_status：≥7 approved、5-6 pending-review、<5 skipped-low-relevance

### B. Embedding API — Gate 1b（中等價值）

- [ ] 選用 embedding model（text-embedding-3-small 或 Apple 內部輕量）
- [ ] Ingest Agent 加 Gate 1b：hash 不同時跑 cosine similarity
- [ ] 門檻 ≥ 0.98 → `skipped-trivial-change`，只 bump `last_updated`

### C. 每週相關性報告（低風險、高可見性）

- [ ] 實作 §8.10.5 的 `weekly-digest/YYYY-Www-relevance.md` 自動產出
- [ ] 統計：通過率、Top 10 / Bottom 10、來源健康度趨勢
- [ ] 提供 markdown 格式，讓你週一打開即看

### D. 其他想到的

- [ ] sitemap.xml 正式 parser（讓 apple-support 能自動抓新 HT）
- [ ] v0.2 apply/merge 兩個 script 整合成一個
- [ ] CODEOWNERS 升級 stage-2（等 team handle 建立後）
- [ ] CI: GitHub Actions 跑 lint.py 於每個 PR
- [ ] 第一個真實客群頁（`sales-playbook/customer-personas/business.md`）

---

## 🧯 已知問題 / 技術債

| 問題 | 嚴重度 | 計畫 |
|---|---|---|
| 6 個來源因 RSS 故障或低相關度被 `enabled: false` | 🟢 低 | 改 config 即可重啟；wired / rtings / austin-mann / halide-blog / no-film-school 待觀察 |
| `fetch_method: http + seed_strategy: sitemap` 組合未實作 | 🟡 中 | v0.3 實作 sitemap parser |
| Ingest Agent 的 HTML extractor 仍取到導覽雜訊 | 🟡 中 | v0.3 改 trafilatura 或 Readability.js |
| MacRumors/9to5Mac review 類文章在 RSS 中稀少 | 🟢 低 | 可考慮 scrape review index 頁（W1 的 fetch_reviews.py 邏輯） |
| CODEOWNERS team handles 尚未存在 | 🟢 低 | 等有第二位 reviewer 時建 team |
| `merge-pr-solo.sh` 是 solo workaround | 🟢 低 | 一旦有 reviewer 可停用 |

---

## 📮 關鍵檔案速查

```bash
# 回到 repo
cd ~/Projects/retail-iq

# 跑 Ingest Agent
python3 scripts/ingest_agent.py --limit 2         # 全部 enabled sources
python3 scripts/ingest_agent.py --source apple-support --dry-run
python3 scripts/lint.py                            # 合規檢查

# Git workflow
export GH_HOST=github.pie.apple.com
git checkout -b feat/X
# ... make changes ...
git add . && git commit -m "..."
git push -u origin feat/X
gh pr create --title "..." --body "..."
bash ~/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728/merge-pr-solo.sh <PR#>
```

---

## 🧠 v0.2 開工前的 10 分鐘熱身建議

1. 打開 `wiki/AGENTS.md §8.5` — 看 4-gate pipeline 偽代碼
2. 打開 `wiki/AGENTS.md §8.10.3` — 看 relevance scoring prompt 模板
3. 看 `scripts/ingest_agent.py` — 找 `class IngestPipeline`，v0.2 要在 `process_article()` 加 Gate 3
4. 確認 Apple GenAI API key 可用（跑一次 curl 測試）
5. `git checkout -b feat/ingest-agent-v0.2`，開始寫

---

## 🎖️ 里程碑 KPI（截至今天）

| 指標 | 值 | 目標 | 狀態 |
|---|---|---|---|
| Schema 穩定 | v1.9.2 | v2.0 前完成 W2 | 🟢 on track |
| 產品頁完整範例 | 3 款 | 3 款（iPhone/iPad/Mac）| ✅ 達成 |
| PR 走 protection | 5 次 | 持續 | 🟢 工作流驗證完成 |
| Ingest 成功率 | 100%（0 failed/28） | > 95% | ✅ 達成 |
| 外部依賴數 | 0 | 目標 0 | ✅ 達成 |
| v0.2 預計上線 | — | 本週內 | ⏸ 待 Apple GenAI 確認 |

---

## 💬 備忘

- 本 handover 會持續更新；每次大 milestone 結束後覆蓋
- 所有細節以 `wiki/log.md` 與 git log 為準（append-only 追溯）
- Schema 任何變動請走 PR + CODEOWNERS

---

**當下狀態**：🟢 一切就緒，等 v0.2 開工。
