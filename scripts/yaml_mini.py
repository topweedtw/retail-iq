"""
scripts/yaml_mini.py — 最小 YAML 子集解析器（零依賴）

為什麼自寫：
  - Homebrew Python 3.14 + PEP 668 + macOS sandbox 三重組合讓 `pip install pyyaml`
    非常不穩（本機開發實測會部分安裝失敗）
  - 我們的 sources-config.yaml 只用到 YAML 的子集
  - 零 pip 依賴 = 安裝體驗完美 = 維運負擔低

支援：
  - 鍵值：`key: value`（value 可為 quoted 或 unquoted 字串、true/false、int、null）
  - 嵌套 dict：用縮排（2 空格）
  - List：`- item`（item 可為 quoted 字串）
  - 行尾或全行註解：`#`
  - 多行字串：**不支援**（目前 config 未用到）

測試覆蓋見 sources-config.yaml 實際解析。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_BOOL_TRUE = {"true", "True", "TRUE", "yes", "Yes", "YES"}
_BOOL_FALSE = {"false", "False", "FALSE", "no", "No", "NO"}
_NULL = {"null", "Null", "NULL", "~", ""}


def _parse_scalar(s: str) -> Any:
    """把一個 YAML 標量字串轉為 Python 物件。"""
    s = s.strip()
    if not s:
        return None
    # 去掉行內註解（# 前需有 space 或在行首）
    m = re.search(r"\s+#.*$", s)
    if m:
        s = s[: m.start()].rstrip()
    # Empty inline collections
    if s == "[]":
        return []
    if s == "{}":
        return {}
    # Inline flow list：[a, b, c] — 每個元素遞迴呼叫 _parse_scalar
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        items = _split_flow_items(s[1:-1])
        return [_parse_scalar(item) for item in items]
    if s in _NULL:
        return None
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    # 雙引號字串：處理 \\ 與 \"
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1]
        return inner.replace('\\\\', '\\').replace('\\"', '"')
    # 單引號字串
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    # 整數
    try:
        return int(s)
    except ValueError:
        pass
    # 浮點
    try:
        return float(s)
    except ValueError:
        pass
    # 裸字串
    return s


def _split_flow_items(s: str) -> list[str]:
    """Split inline flow list items，尊重引號內的逗號。"""
    items: list[str] = []
    cur: list[str] = []
    in_dq = in_sq = False
    for ch in s:
        if ch == '"' and not in_sq:
            in_dq = not in_dq
            cur.append(ch)
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
            cur.append(ch)
        elif ch == "," and not in_dq and not in_sq:
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    last = "".join(cur).strip()
    if last:
        items.append(last)
    return items


def _indent(line: str) -> int:
    """回傳行首空白數；tab 視為 4 格。"""
    i = 0
    for ch in line:
        if ch == " ":
            i += 1
        elif ch == "\t":
            i += 4
        else:
            break
    return i


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def _tokenize(lines: list[str]) -> list[tuple[int, str]]:
    """(indent, stripped_content) 忽略空行與純註解行。"""
    out = []
    for raw in lines:
        # 去尾部 \r\n
        line = raw.rstrip("\r\n")
        if _is_comment_or_blank(line):
            continue
        out.append((_indent(line), line.lstrip()))
    return out


def _parse_block(
    tokens: list[tuple[int, str]], pos: int, base_indent: int
) -> tuple[Any, int]:
    """
    解析一個 block，回傳 (parsed_value, new_pos)。
    block 可能是 dict（key: value 行）或 list（- item 行）。
    """
    if pos >= len(tokens):
        return None, pos

    ind, content = tokens[pos]
    if ind < base_indent:
        return None, pos

    # List
    if content.startswith("- "):
        return _parse_list(tokens, pos, base_indent)

    # Dict
    return _parse_dict(tokens, pos, base_indent)


def _parse_dict(
    tokens: list[tuple[int, str]], pos: int, base_indent: int
) -> tuple[dict, int]:
    result: dict = {}
    while pos < len(tokens):
        ind, content = tokens[pos]
        if ind < base_indent:
            break
        if ind > base_indent:
            # 不該發生：下一層 block 應由遞迴處理過
            pos += 1
            continue
        if content.startswith("- "):
            # 到這裡說明上層已結束，由呼叫者處理
            break
        # key: value 行
        # 找第一個 `:`，但要小心 URL 裡的 `:`
        m = re.match(r"^([^:\s][^:]*?):\s*(.*)$", content)
        if not m:
            raise ValueError(f"Invalid line at pos {pos}: {content!r}")
        key = m.group(1).strip()
        rest = m.group(2)

        # 去行內註解（# 前必須有空白）
        rest_clean = re.sub(r"\s+#.*$", "", rest).rstrip()

        if rest_clean:
            # 單行值
            result[key] = _parse_scalar(rest_clean)
            pos += 1
        else:
            # 下一行開始為 nested dict 或 list
            pos += 1
            if pos >= len(tokens):
                result[key] = None
                break
            next_ind, _next_content = tokens[pos]
            if next_ind <= base_indent:
                # 空值
                result[key] = None
            else:
                value, pos = _parse_block(tokens, pos, next_ind)
                result[key] = value
    return result, pos


def _parse_list(
    tokens: list[tuple[int, str]], pos: int, base_indent: int
) -> tuple[list, int]:
    result: list = []
    while pos < len(tokens):
        ind, content = tokens[pos]
        if ind < base_indent or not content.startswith("- "):
            break
        if ind > base_indent:
            pos += 1
            continue
        item_raw = content[2:].lstrip()
        # Dict item: "- key: value" starts a dict that continues on
        # subsequent lines indented by (base_indent + 2).
        # Skip quoted scalars like '- "^https://.*"' which also contain ':'.
        _is_quoted = item_raw[:1] in ('"', "'")
        m = None if _is_quoted else re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", item_raw)
        if m:
            item_dict: dict = {}
            key = m.group(1).strip()
            rest_clean = re.sub(r"\s+#.*$", "", m.group(2)).rstrip()
            item_dict[key] = _parse_scalar(rest_clean) if rest_clean else None
            pos += 1
            continuation_indent = base_indent + 2
            while pos < len(tokens):
                next_ind, next_content = tokens[pos]
                if next_ind < continuation_indent:
                    break
                if next_content.startswith("- "):
                    break  # next list item
                m2 = re.match(r"^([^:\s][^:]*?):\s*(.*)$", next_content)
                if not m2:
                    break
                k = m2.group(1).strip()
                v = re.sub(r"\s+#.*$", "", m2.group(2)).rstrip()
                item_dict[k] = _parse_scalar(v) if v else None
                pos += 1
            result.append(item_dict)
        else:
            result.append(_parse_scalar(item_raw))
            pos += 1
    return result, pos


def loads(source: str) -> Any:
    """Parse a YAML string（僅限我們用到的子集）。"""
    lines = source.split("\n")
    tokens = _tokenize(lines)
    if not tokens:
        return {}
    base = tokens[0][0]
    value, _ = _parse_block(tokens, 0, base)
    return value


def load(path: str | Path) -> Any:
    return loads(Path(path).read_text(encoding="utf-8"))


def safe_load(stream):
    """與 PyYAML API 相容：接受字串或檔案物件。"""
    if hasattr(stream, "read"):
        return loads(stream.read())
    return loads(stream)
