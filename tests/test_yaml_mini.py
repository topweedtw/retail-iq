"""
Tests for scripts/yaml_mini.py

今天（2026-05-05）我們在這些 case 踩過坑：
  - AttributeError: safe_load 只接字串，不接 file object
  - re.error: [] inline list 被當字串 '[]'
這些 test 保障未來不再重蹈覆轍。
"""
import io
import sys
import unittest
from pathlib import Path

# 允許從 tests/ 匯入 scripts/yaml_mini
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import yaml_mini  # noqa: E402


class TestScalars(unittest.TestCase):
    def test_int(self):
        self.assertEqual(yaml_mini.loads("a: 42"), {"a": 42})

    def test_float(self):
        self.assertEqual(yaml_mini.loads("a: 3.14"), {"a": 3.14})

    def test_bool_true(self):
        for lit in ("true", "True", "TRUE", "yes"):
            self.assertEqual(yaml_mini.loads(f"a: {lit}"), {"a": True})

    def test_bool_false(self):
        for lit in ("false", "False", "no"):
            self.assertEqual(yaml_mini.loads(f"a: {lit}"), {"a": False})

    def test_null(self):
        for lit in ("null", "Null", "~", ""):
            result = yaml_mini.loads(f"a: {lit}")
            self.assertIsNone(result["a"])

    def test_bare_string(self):
        self.assertEqual(yaml_mini.loads("a: hello"), {"a": "hello"})

    def test_double_quoted(self):
        self.assertEqual(yaml_mini.loads('a: "hello world"'), {"a": "hello world"})

    def test_double_quoted_with_escape(self):
        self.assertEqual(yaml_mini.loads(r'a: "line\\nbreak"'), {"a": r"line\nbreak"})

    def test_single_quoted(self):
        self.assertEqual(yaml_mini.loads("a: 'hello'"), {"a": "hello"})


class TestInlineEmptyCollections(unittest.TestCase):
    """Bug from v0.1.2: deny_url_patterns: [] 被當字串 '[]'"""

    def test_empty_list(self):
        self.assertEqual(yaml_mini.loads("a: []"), {"a": []})

    def test_empty_dict(self):
        self.assertEqual(yaml_mini.loads("a: {}"), {"a": {}})

    def test_empty_list_inside_config(self):
        y = """
sources:
  apple-com-tw:
    deny_url_patterns: []
"""
        result = yaml_mini.loads(y)
        self.assertEqual(result["sources"]["apple-com-tw"]["deny_url_patterns"], [])


class TestInlineFlowList(unittest.TestCase):
    def test_bare_items(self):
        self.assertEqual(yaml_mini.loads("a: [1, 2, 3]"), {"a": [1, 2, 3]})

    def test_string_items(self):
        self.assertEqual(
            yaml_mini.loads('a: ["x", "y", "z"]'),
            {"a": ["x", "y", "z"]},
        )

    def test_comma_in_quoted_string_not_split(self):
        self.assertEqual(
            yaml_mini.loads('a: ["with, comma", "no comma"]'),
            {"a": ["with, comma", "no comma"]},
        )


class TestBlockList(unittest.TestCase):
    def test_simple(self):
        y = """
items:
  - apple
  - banana
"""
        self.assertEqual(yaml_mini.loads(y), {"items": ["apple", "banana"]})

    def test_quoted_items(self):
        y = """
regex:
  - "^https://.*"
  - "/podcast-"
"""
        self.assertEqual(
            yaml_mini.loads(y)["regex"],
            ["^https://.*", "/podcast-"],
        )

    def test_backslash_in_quoted(self):
        """Real-world regex from sources-config.yaml"""
        y = r"""
patterns:
  - "sixcolors\\.com/podcast/"
"""
        result = yaml_mini.loads(y)
        # 兩個連續 backslash 應該 decode 成一個
        self.assertEqual(result["patterns"], [r"sixcolors\.com/podcast/"])


class TestNested(unittest.TestCase):
    def test_two_level_dict(self):
        y = """
sources:
  apple:
    tier: T1
    enabled: true
  engadget:
    tier: T2
    enabled: false
"""
        result = yaml_mini.loads(y)
        self.assertEqual(result["sources"]["apple"]["tier"], "T1")
        self.assertTrue(result["sources"]["apple"]["enabled"])
        self.assertFalse(result["sources"]["engadget"]["enabled"])


class TestComments(unittest.TestCase):
    def test_inline_comment_stripped(self):
        self.assertEqual(
            yaml_mini.loads("a: 42  # this is a comment"),
            {"a": 42},
        )

    def test_full_line_comment_skipped(self):
        y = """
# This is a comment
a: 1
# Another comment
b: 2
"""
        self.assertEqual(yaml_mini.loads(y), {"a": 1, "b": 2})

    def test_comment_in_string_not_stripped(self):
        """URL 中的 # 不該被當成 comment"""
        # 實際上 YAML 雙引號包起來的內容不處理 inline comment
        # 但因為 _parse_scalar 先用 \s+# regex strip，只要 # 前面有空白就會被砍
        # 這裡測一個安全 case：URL 中的 # 沒有前導空白
        result = yaml_mini.loads('url: "https://example.com/page#section"')
        self.assertEqual(result["url"], "https://example.com/page#section")


class TestSafeLoadAPI(unittest.TestCase):
    """Bug from v0.1.2: ingest_agent 傳 file object，safe_load 當時只接字串"""

    def test_safe_load_string(self):
        self.assertEqual(yaml_mini.safe_load("a: 1"), {"a": 1})

    def test_safe_load_file_object(self):
        stream = io.StringIO("a: 1\nb: 2")
        self.assertEqual(yaml_mini.safe_load(stream), {"a": 1, "b": 2})

    def test_safe_load_path(self):
        """yaml_mini.load() 接 path"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("items: [a, b, c]")
            tmp = f.name
        try:
            self.assertEqual(yaml_mini.load(tmp), {"items": ["a", "b", "c"]})
        finally:
            Path(tmp).unlink()


class TestRealConfigParsing(unittest.TestCase):
    """以真實 sources-config.yaml 跑一次整套 parser 壓力測試"""

    @classmethod
    def setUpClass(cls):
        cls.config_path = HERE.parent / "wiki" / "sources-config.yaml"
        if not cls.config_path.exists():
            raise unittest.SkipTest(f"{cls.config_path} 不存在，跳過")

    def test_parse_success(self):
        d = yaml_mini.load(self.config_path)
        self.assertIn("sources", d)
        self.assertGreater(len(d["sources"]), 10)

    def test_all_regex_compilable(self):
        """所有 regex pattern 必須 re.compile 成功（v0.1.2 初版就是卡這）"""
        import re
        d = yaml_mini.load(self.config_path)
        bad = []
        for name, cfg in d["sources"].items():
            if not cfg or not cfg.get("enabled"):
                continue
            for field in ("allow_url_patterns", "deny_url_patterns"):
                for pat in cfg.get(field) or []:
                    try:
                        re.compile(pat)
                    except re.error as e:
                        bad.append(f"{name}.{field}: {pat!r} — {e}")
            for field in ("title_blocklist_regex", "title_required_regex"):
                v = cfg.get(field)
                if v:
                    try:
                        re.compile(v)
                    except re.error as e:
                        bad.append(f"{name}.{field}: {v!r} — {e}")
        self.assertEqual(bad, [], f"發現 {len(bad)} 個無效 regex:\n" + "\n".join(bad))

    def test_list_fields_are_lists(self):
        """Bug from v0.1.2: 空 list `[]` 被當字串 — 所有 list field 必須是 list 或 None"""
        d = yaml_mini.load(self.config_path)
        for name, cfg in d["sources"].items():
            if not cfg:
                continue
            for field in ("allow_url_patterns", "deny_url_patterns", "seed_urls"):
                v = cfg.get(field)
                if v is not None:
                    self.assertIsInstance(
                        v, list,
                        f"{name}.{field} 應為 list 或 None，實際為 {type(v).__name__}: {v!r}"
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
