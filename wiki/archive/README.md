# Archive

**停產 / 已下架產品歸檔**。

## 原則

- **永不刪除**，只從 `products/` 移動至此處
- 保留原 frontmatter + 最後狀態，用於歷史比較與舊款客戶支援
- Gate 4 **不對 archive 頁作用**（不會自動 route/apply）

## 遷移流程

當產品 status 從 `active` → `discontinued`：

1. `git mv wiki/products/<slug>.md wiki/archive/<slug>.md`
2. 編輯 frontmatter：`status: active` → `status: archived`
3. 加 `discontinued_date: YYYY-MM-DD`
4. 更新 `wiki/index.md` 的產品表
5. 加 `wiki/log.md` 條目
6. Lint 後續：Gate 4 router 自動跳過 archived 頁面（`gate4_router.load_products` 已排除 `status == archived`）

## 狀態

🟢 目前無歸檔產品。
