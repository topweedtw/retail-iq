# LICENSE — Apple Internal Use Only

Copyright © 2026 Apple Inc. All rights reserved.

本專案（**RetailIQ**）為 Apple 內部訓練系統，含：
1. 原創 schema、程式碼、文件（`wiki/AGENTS.md`、`scripts/*.py`、`wiki/products/*.md` 等）
2. 從 Apple 官方來源擷取的產品資訊（`raw/apple-com-tw/`、`raw/apple-newsroom-en/`、`raw/apple-support/`、`raw/sales-coach/`）
3. 從第三方媒體擷取的文本內容（`raw/ars-technica/`、`raw/petapixel/` 等）

---

## 使用限制

### ✅ 允許
- Apple 員工於公司業務中使用本系統產出
- 門市人員依本系統產生的訓練腳本進行客戶展示
- Apple 內部以本專案為範例衍生其他 LLM Wiki 專案

### ❌ 禁止
- 將 repo 內容（含 `raw/`、`wiki/`、`scripts/`、`generated-scripts/`）外流至非 Apple 員工
- 將本專案發布至公開 GitHub 或任何公開程式碼平台
- 將第三方媒體內容商業發布或再散布
- 未經法務核可將本系統商業化（包括授權、販售、訂閱制）

---

## 第三方內容（`raw/` 目錄）

`raw/` 目錄下從第三方媒體擷取的文本內容遵循以下原則：

1. **Fair use for internal training**：僅作為內部訓練與知識合成用途，符合美國著作權法 Fair Use 第 107 條（transformative research / education）與台灣著作權法第 52 條（教育研究目的合理使用）
2. **Not for redistribution**：不得以任何形式對第三方發布、轉授權、或商業利用
3. **HTML originals excluded from git**：為降低著作權風險，原始 HTML 檔案**不納入版本控制**（見 `.gitignore`）；僅保留 LLM 提取後的 `.txt`、`.meta.json`、`.zh-TW.md`
4. **Attribution preserved**：每篇第三方內容的 `.meta.json` 保留 `source_url`、`source_title` 欄位，確保稽核時可追溯原始出處

---

## 未發表產品資訊

依 `wiki/AGENTS.md § 7 紅線規則`：
- 不得撰寫 Apple 未公開發表之產品／功能／時程
- 不得於訓練腳本中引用 rumor、leak、analyst prediction
- Ingest Agent 內建 URL pattern + 標題黑名單兩層防護

---

## 資料安全

- 本 repo 僅限於 Apple 內部 GitHub（github.apple.com）
- Access 透過 Apple Directory SSO 控管
- 存取日誌納入公司資安稽核
- PR 流程確保每次變更皆有審核紀錄

---

## 有疑問？

- **授權範圍**：請聯繫 Apple Legal
- **技術使用**：見 `CONTRIBUTING.md` 或聯繫 @willer
- **合規疑慮**：於 PR 標題加上 `[compliance]` 觸發法務 reviewer

---

**本宣告為本 repo 所有檔案的預設授權條款。**
