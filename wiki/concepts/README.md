# Concepts

**跨產品概念頁面**（晶片、軟體、功能技術、隱私）。

## 何時建立 concept 頁？

依 Karpathy Wiki 原則 — **內容由真實素材驅動**，不提前建殼。典型觸發：

1. 兩個以上 `products/*.md` 的 `tags` 引用同一概念（例如 `a19-pro`）→ 抽出成 concept
2. Gate 4 產出的 proposal 多次出現「新段落建議」命中同一主題（如「AI 功能」）
3. 人工判斷：競品對比、反對處理需引用此概念

## 待建清單（從 wiki/index.md 同步）

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

## Frontmatter 模板

```yaml
---
type: concept
title: A19 Pro 晶片
slug: a19-pro-chip
status: active
last_updated: YYYY-MM-DD
source_count: 0
tags: [chip, apple-silicon, iphone-17-pro]
ingest_managed_sections: [技術規格, 歷史脈絡, 相關產品, 來源]
human_owned_sections: [銷售切入點, 常見客戶問題]
---
```

## 建立流程

1. 在 `wiki/index.md` 的 concepts checkbox 勾選
2. 建 `concepts/<slug>.md`，附上述 frontmatter
3. 在 `products/` 相關頁面改 `[[concepts/<slug>]]` 連結
4. 下一輪 Gate 4 會自動偵測到新 page → 可作為 target
