"""
scripts/utils.py — 共用工具函式

目前包含：
  - sandbox_safe_write: atomic 寫檔 + Enchanté sandbox fallback
    （原本在 gate4_applier.py 與 gate4_queue.py 各自重複定義，統一於此）
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def sandbox_safe_write(path: Path, content: str, *, repo_root: Path = REPO_ROOT) -> None:
    """Atomic write with Enchanté sandbox fallback.

    Strategy:
      1. Write to a .tmp sibling file.
      2. os.replace() for atomic rename (works on same filesystem).
      3. If PermissionError (sandbox), fall back to:
         a. git rm -f the existing file (check=True — failure is surfaced, not silenced).
         b. write_text() directly.
      4. Always clean up the .tmp file in a finally block.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    try:
        os.replace(tmp, path)
        return
    except PermissionError:
        pass
    # Sandbox fallback
    try:
        if path.exists():
            result = subprocess.run(
                ["git", "rm", "-f", "--quiet", str(path)],
                cwd=repo_root, capture_output=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"git rm failed for {path} (exit {result.returncode}): {stderr}"
                )
        path.write_text(content, encoding="utf-8")
    finally:
        if tmp.exists():
            subprocess.run(
                ["git", "clean", "-f", "--quiet", str(tmp)],
                cwd=repo_root, capture_output=True,
            )
