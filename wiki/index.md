# Wiki Index

> LLM Agent 於每次 ingest 後自動更新此檔案。
> 使用者與其他 Agent 先讀此檔案定位所需頁面。

_Last updated: 2026-05-07 (W2 Day 4 EOD, Schema v2.0)_

---

## 📱 產品頁（`products/`）

| 頁面 | 類別 | 狀態 | 最後更新 | 備註 |
|---|---|---|---|---|
| [[products/iphone-17-pro]] | iPhone | active | 2026-05-07 | Gate 4 自動更新 3 sections + 1 human-reviewed |
| [[products/ipad-air]] | iPad | active | 2026-05-07 | **M3 → M4 更新 + 12GB + N1/C1X + iPadOS 26** |
| [[products/macbook-neo]] | Mac | active | 2026-05-07 | **清掉 Mac mini 污染（v2.5）** |
| [[products/mac-mini]] | Mac | active | 2026-05-07 | **NEW** — M4/M4 Pro、12.7cm 迷你桌機、硬體光線追蹤、最多 8 埠 |
| [[products/apple-watch-series-11]] | Watch | active | 2026-05-07 | **NEW** — S10 晶片、24h 電池、睡眠分數、生命徵象 |
| [[products/apple-watch-ultra-3]] | Watch | active | 2026-05-07 | **NEW** — 49mm 鈦金屬、100m 防水、42h 電池、雙頻 GPS |
| [[products/airpods-pro-3]] | AirPods | active | 2026-05-07 | **NEW** — 世上最強入耳 ANC、心率感測、IP57、即時翻譯 |

---

## 💡 概念頁（`concepts/`）

**狀態**：🟡 stub dir，等 Gate 4 累積多週素材後再批次建立（Karpathy Wiki 原則：內容先由真實素材驅動）。

計畫中的概念頁（由 [[products/*]] 交叉引用自動捕獲）：

- [ ] `a18-pro-chip`
- [ ] `a19-pro-chip`
- [ ] `m3-chip`
- [ ] `apple-intelligence`
- [ ] `apple-silicon`
- [ ] `apple-pencil-pro`
- [ ] `pro-camera-system`
- [ ] `privacy`
- [ ] `titanium-design`
- [ ] `macos`
- [ ] `continuity-features`
- [ ] `ios-26`
- [ ] `promotion-technology`

---

## 🆚 比較頁（`comparisons/`）

**狀態**：🟡 stub dir，待產品線擴充後建立。典型頁面：`iphone-17-pro-vs-iphone-17.md`、`ipad-air-vs-ipad-pro.md`。

---

## 📖 銷售劇本（`sales-playbook/`）

**狀態**：🟡 stub dir。此目錄全為 **human-owned** 內容（話術、反對處理、客群畫像），Gate 4 不自動寫入。

---

## 📊 每週週報（`weekly-digest/`）

| 週 | 檔案 | 來源 |
|---|---|---|
| 2026-W18 | [[weekly-digest/2026-W18-relevance]] | pre-W2 手動版（baseline）|
| 2026-W19 | [[weekly-digest/2026-W19-relevance]] | v0.2 Gate 3 首份自動打分 |
| 2026-W19 | [[weekly-digest/2026-W19-digest]] | **v2.0 首份整合 Gate 4 stats + cost** |

以後每週由 `scripts/generate_weekly_digest.py YYYY-Www` 自動產出。

---

## 🗃️ Archive（`archive/`）

**狀態**：🟢 空（目前無停產產品）。

---

## 🏗️ 基礎建設

| 目錄 | 用途 |
|---|---|
| [`design/`](design/) | 架構設計文件（如 [gate4-ingest.md](design/gate4-ingest.md)）|
| [`handover/`](handover/) | Session handover 歷史（[README](handover/README.md)）|
| [`ingest-queue/`](ingest-queue/) | Gate 4 人工審核佇列（[README](ingest-queue/README.md)）|
| `sources-config.yaml` | Ingest 來源設定（21 個 sources / 15 enabled）|

---

## 📘 Schema

- [AGENTS.md](AGENTS.md) — v2.0 canonical
- [log.md](log.md) — 事件時間軸（v1.0 → v2.0 全紀錄）

---

## 🚦 Pipeline 狀態（v2.0 full 5-gate）

```
Gate 1a (hash) → Gate 1b (embedding) → Gate 2 (URL/title) → Gate 3 (LLM relevance) → Gate 4 (LLM ingest)
```

- **Scripts**：16 支在 `scripts/`
- **Tests**：233 全綠
- **Last full-pipeline run**：2026-05-07 via `--gate4-only --week 2026-W19`
