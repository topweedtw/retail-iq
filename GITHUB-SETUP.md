# 🚀 Apple GitHub 設定指引（一次性）

> 接續 W1 結案，將本專案推上 **github.apple.com**，為 W2 做好版控基礎。
> 預估時間：**15-20 分鐘**（含 repo 申請核准等待）。

---

## ⚠️ 預檢查（開始前請確認）

- [ ] 已有 `github.apple.com` 帳號
- [ ] 已 `gh auth login --hostname github.apple.com`（或等效 git credential 設定）
- [ ] 已安裝 `git-lfs`（可先裝但本次不啟用）：`brew install git-lfs`
- [ ] 確認所屬 org 允許建 internal repo（若否 → 先申請 org 權限）

---

## 📍 Step 1：另開一個乾淨的工作目錄

**⚠️ 目前 repo 檔案在 Enchanté 對話目錄下**：
```
/Users/willer/Documents/Enchanté/Conversations/0F7F1213-...
```

這個路徑不適合作為 git repo 根（會把對話 metadata 也版控）。先複製到乾淨路徑：

```bash
# 建立乾淨工作目錄
mkdir -p ~/Projects
cp -R /Users/willer/Documents/Enchanté/Conversations/0F7F1213-2778-428F-8DB5-5B9CA9BC0728 ~/Projects/retail-iq
cd ~/Projects/retail-iq

# 驗證檔案齊全
ls -la
# 應看到：README.md, HANDOVER.md, AGENTS.md 不在此，wiki/AGENTS.md 才對
# 確認看到：.gitignore, .gitattributes, LICENSE.md, CODEOWNERS, CONTRIBUTING.md
```

---

## 📍 Step 2：本地 Git 初始化

```bash
cd ~/Projects/retail-iq

# 初始化
git init -b main

# 驗證 .gitignore 生效（應看到 raw/**/*.html 等被排除）
git status | head -30

# 若 .gitignore 沒生效 → 檢查檔案是否在 root（ls -la .gitignore）
```

---

## 📍 Step 3：配置 Git LFS（為未來預備，不立即啟用）

目前沒有需要 LFS 的檔案（HTML 已被 .gitignore）。但先跑一次 install，未來開啟影片時省步驟：

```bash
git lfs install

# 驗證
git lfs --version
```

---

## 📍 Step 4：檢查沒有敏感資訊誤入

```bash
# 搜尋潛在洩漏
grep -r "password\|secret\|api_key\|private_key" . --include="*.md" --include="*.json" --include="*.py" \
  | grep -v ".git/" | grep -v "node_modules/"

# 應該無輸出，或只出現在 .env.example 這類 placeholder
```

---

## 📍 Step 5：在 Apple GitHub 建立 repo

### 方法 A：用 gh CLI（推薦）

```bash
# 登入 Apple GitHub（若尚未）
gh auth login --hostname github.apple.com
# 選 HTTPS，選 yes 給 git credential

# 建 repo（private / internal 視 org 政策）
gh repo create YOUR-ORG/retail-iq \
  --internal \
  --description "Apple 門市銷售訓練系統 — LLM-maintained knowledge wiki" \
  --hostname github.apple.com
```

### 方法 B：用網頁

1. 開 `https://github.apple.com/new`
2. Repository name: `retail-iq`
3. Visibility: **Internal**（除非你的 org 有其他慣例）
4. **不要** 勾初始化 README / .gitignore / LICENSE（我們自己有）
5. Create

---

## 📍 Step 6：關聯 remote + push

```bash
# 設 remote（把 YOUR-ORG 換成你所屬 org）
git remote add origin git@github.apple.com:YOUR-ORG/retail-iq.git

# 3 個分散 commit 讓 history 清晰
git add .gitignore .gitattributes README.md LICENSE.md CODEOWNERS CONTRIBUTING.md
git commit -m "chore: initial repo scaffolding (gitignore, license, codeowners)"

git add wiki/
git commit -m "feat: W1 milestone — AGENTS.md v1.8 + 3 product pages + sources-config"

git add raw/ scripts/ frontend-designs/ generated-scripts/
git commit -m "feat: W1 deliverables — 30 raw test articles + scripts + frontend mockups"

git add HANDOVER.md CRAWL-STATUS.md TEST-REPORT-2026-05-04.md
git commit -m "docs: management handover + crawl status + Monday test report"

# Push
git push -u origin main
```

---

## 📍 Step 7：設定 Branch Protection（必做）

### 網頁操作

1. 開 `https://github.apple.com/YOUR-ORG/retail-iq/settings/branches`
2. "Add branch ruleset" / "Add rule"
3. Branch name pattern: `main`
4. 勾選：
   - [x] **Require a pull request before merging**
     - Required approvals: **1**（若有團隊設 2）
     - [x] Dismiss stale approvals when new commits pushed
     - [x] Require review from Code Owners
   - [x] **Require status checks to pass before merging**
     - 稍後加 CI check（例如 `lint`）
   - [x] **Require conversation resolution before merging**
   - [x] **Do not allow bypassing the above settings**
   - [ ] Allow force pushes — **不勾**
   - [ ] Allow deletions — **不勾**
5. Save

### 或 gh CLI

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/YOUR-ORG/retail-iq/branches/main/protection \
  -F required_status_checks=null \
  -F enforce_admins=true \
  -F required_pull_request_reviews[required_approving_review_count]=1 \
  -F required_pull_request_reviews[require_code_owner_reviews]=true \
  -F restrictions=null \
  --hostname github.apple.com
```

---

## 📍 Step 8：驗收檢查

```bash
# 1. remote 正確
git remote -v
# origin  git@github.apple.com:YOUR-ORG/retail-iq.git (fetch)
# origin  git@github.apple.com:YOUR-ORG/retail-iq.git (push)

# 2. main 保護啟用
gh api /repos/YOUR-ORG/retail-iq/branches/main/protection --hostname github.apple.com
# 應回傳 JSON 含 required_pull_request_reviews

# 3. 試開一個 PR 驗證流程
git checkout -b docs/test-pr-workflow
echo "# Test" >> README.md
git add README.md
git commit -m "docs: test PR workflow"
git push origin docs/test-pr-workflow
gh pr create --title "docs: test PR workflow" --body "驗收 branch protection"
# 應自動指派 @willer （CODEOWNERS 設的）
# 應 block 直接 merge，需 1 位 reviewer
```

---

## 📍 Step 9：環境清理 + 回報

回到對話：

```
Git 化完成，repo 路徑：
- 本地：~/Projects/retail-iq
- 遠端：https://github.apple.com/YOUR-ORG/retail-iq
- Main protection: 已啟用
```

然後就可以進 **B（調 sources-config）** 並以第一個正式 PR 走流程！

---

## ❓ 疑難排解

| 問題 | 解法 |
|---|---|
| `gh auth login` 失敗 | 確認 Apple Directory 密碼；嘗試 `--web` flag |
| `git push` 被拒 | 檢查 SSH key 是否已上傳到 github.apple.com |
| Branch protection 設定無效 | 確認你有 admin 權限，或請 repo owner 代設 |
| LFS 沒生效 | `git lfs install` 後需 `git lfs track` 才會套用 |
| PR 沒有自動指派 reviewer | 確認 CODEOWNERS 中的 team handle（如 `@retailiq-schema-reviewers`）真實存在；否則先改成個人 @handle |

---

## 📌 完成後，下週（或更晚）可以補的事

- 設 CI workflow：PR 時自動跑 `python3 scripts/lint.py`（見 `.github/workflows/lint.yml` — 本 PR 還沒建）
- 建立 issue template（bug report / feature request / schema proposal）
- 設 Dependabot 或 Apple 內部同等機制
- 設 labels（`schema`、`content`、`ingest`、`compliance` 等）
- 加入 `SECURITY.md`（若 org 要求）

---

**一步一步來即可，完成後立刻可進 B。**
