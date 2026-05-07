#!/bin/bash
# 啟用 .githooks/ 作為這個 repo 的 git hooks 目錄
# 跑一次即可：bash scripts/install-hooks.sh
git config core.hooksPath .githooks
echo "✅ Git hooks 已啟用（core.hooksPath = .githooks）"
echo "   下次 git push 會自動跑 pre-push（unit tests + smoke tests）"
