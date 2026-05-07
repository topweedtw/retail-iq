# 📋 RetailIQ Handover Archive

歷史 session handover 紀錄。每份代表一個工作 session 結束時的狀態快照。

> **Source of truth**：`wiki/log.md`（時序事件日誌）+ `wiki/AGENTS.md`（schema）
> Handover 是給「下一個 session（或下一個人）能 30 秒上手」的補充摘要。

---

## 索引

| Handover | 階段 | 主要產出 |
|---|---|---|
| [2026-04-30](HANDOVER-2026-04-30.md) | W1 結案 | Schema 設計驗證、腳本生成器 PoC |
| [2026-05-05](HANDOVER-2026-05-05.md) | W2 Day 1 | v0.1 Ingest Agent (Gate 1a + 2)、yaml_mini |
| [2026-05-06](HANDOVER-2026-05-06.md) | W2 Day 2 | v0.2 Gate 3 (LLM scoring)、首份自動化週報 W19 |
| [2026-05-07](HANDOVER-2026-05-07.md) | W2 Day 3–4 EOD | **v0.5 Full 5-gate pipeline shipped**：Gate 1b、Gate 4（全 5 phases）、review CLI、live validated、Schema v2.0 |

---

## Handover 格式慣例

每份應包含：

1. **TL;DR** — 30 秒摘要（5-7 條 bullet）
2. **今日 Main Branch 進度** — merged PRs + 重要 commits
3. **關鍵發現** — 3-5 個「下次該知道」的事
4. **檔案變動** — 新增 / 修改清單
5. **待辦清單** — 下次優先序
6. **技術債 / 未解** — 嚴重度 + 計畫
7. **關鍵檔案速查** — 常用 bash 指令
8. **KPI 更新** — 數字進度
9. **備忘** — 雜項

---

## Workflow

新 handover **不要直接編輯 main 上的舊檔**。流程：

1. 在 conversation working folder 寫 `HANDOVER-YYYY-MM-DD.md`
2. Session 結束時走 PR 加進 `wiki/handover/`
3. 更新本 README 的索引表
4. PR 描述應引用對應的工作 PR / Issue

詳見 §8（log + handover policy in `wiki/AGENTS.md`，待加）。
