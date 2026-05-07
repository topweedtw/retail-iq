# Comparisons

**產品比較頁面**（X vs Y）。

## 何時建立 comparison 頁？

1. 同類別內兩款產品客戶會直接比價（如 iphone-17-pro vs iphone-17）
2. 跨世代升級決策（如 macbook-neo vs 舊款 MacBook Air M3）
3. 友商對照（Apple 產品 vs 競品；但此類屬 human-owned 創作）

## Frontmatter 模板

```yaml
---
type: comparison
title: iPhone 17 Pro vs iPhone 17
slug: iphone-17-pro-vs-iphone-17
status: active
last_updated: YYYY-MM-DD
compared_products: [iphone-17-pro, iphone-17]
tags: [iphone, comparison]
ingest_managed_sections: [規格對照表, 價格對照, 來源]
human_owned_sections: [客戶決策樹, 銷售話術, 常見反對處理]
---
```

## 內容結構建議

1. **一句話結論**（誰適合誰）
2. **規格對照表**（ingest-managed，可自動更新）
3. **價格對照**（ingest-managed）
4. **客戶決策樹**（human-owned）
5. **銷售話術**（human-owned）

## 狀態

🟡 目前無 comparison 頁。建議待 `products/` 累積 5+ 個產品後建立首批。
