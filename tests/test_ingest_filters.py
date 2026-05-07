"""
Tests for scripts/ingest_agent.py filter functions (Gate 2).

涵蓋今天遇到的實際 bug：
  - six-colors deny `/podcast-` 擋不到新式 `/podcast/`
  - URL filter 的 allow/deny 優先順序
  - title blocklist / required regex 的邊界
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from ingest_agent import SourceConfig, check_url, check_title, sha256_of, slugify  # noqa: E402


def mk(name="test", **kwargs) -> SourceConfig:
    """建立最小可用的 SourceConfig 給測試用。"""
    defaults = dict(
        name=name, tier="T2", enabled=True,
        display_name=name, base_url="https://example.com/",
        fetch_method="rss", locale="en-US",
    )
    defaults.update(kwargs)
    return SourceConfig(**defaults)


class TestUrlFilter(unittest.TestCase):

    def test_empty_patterns_always_passes(self):
        src = mk()
        ok, reason = check_url("https://anywhere.com/anything", src)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_allow_pattern_matches(self):
        src = mk(allow_url_patterns=[r"^https://apple\.com/"])
        ok, _ = check_url("https://apple.com/iphone", src)
        self.assertTrue(ok)

    def test_allow_pattern_rejects_non_matching(self):
        src = mk(allow_url_patterns=[r"^https://apple\.com/"])
        ok, reason = check_url("https://microsoft.com/", src)
        self.assertFalse(ok)
        self.assertIn("allow list", reason)

    def test_deny_pattern_rejects(self):
        src = mk(deny_url_patterns=[r"/rumors/"])
        ok, reason = check_url("https://x.com/rumors/foo", src)
        self.assertFalse(ok)
        self.assertIn("deny", reason)

    def test_deny_takes_precedence_over_allow(self):
        """deny 應比 allow 先檢查（符合我們 check_url 實作）"""
        src = mk(
            allow_url_patterns=[r"^https://"],
            deny_url_patterns=[r"/rumors/"],
        )
        ok, reason = check_url("https://x.com/rumors/", src)
        self.assertFalse(ok)
        self.assertIn("deny", reason)

    def test_six_colors_podcast_bug_regression(self):
        """
        Regression test: W19 第一次跑時 podcast-upgrade-614 通過了，
        原因是 deny pattern 只有 /podcast- 沒包含 /podcast/ 路徑。
        v0.1.1 hotfix 補上雙 pattern。
        """
        src = mk(
            name="six-colors",
            deny_url_patterns=[
                r"sixcolors\.com/podcast/",
                r"sixcolors\.com/post/.*/podcast-",
            ],
        )

        # 新式路徑應被擋
        ok, _ = check_url("https://sixcolors.com/podcast/upgrade-614/", src)
        self.assertFalse(ok, "新式 /podcast/ 路徑應被擋")

        # 舊式 slug 也應被擋
        ok, _ = check_url(
            "https://sixcolors.com/post/2025/03/podcast-clockwise-654/",
            src,
        )
        self.assertFalse(ok, "舊式 /podcast-* 路徑應被擋")

        # 非 podcast 文章應通過
        ok, _ = check_url("https://sixcolors.com/post/2026/05/mac-storage/", src)
        self.assertTrue(ok, "非 podcast 文章不應被擋")

    def test_multiple_allow_patterns_any_match(self):
        src = mk(allow_url_patterns=[r"^https://a\.com/", r"^https://b\.com/"])
        self.assertTrue(check_url("https://a.com/", src)[0])
        self.assertTrue(check_url("https://b.com/", src)[0])
        self.assertFalse(check_url("https://c.com/", src)[0])


class TestTitleFilter(unittest.TestCase):

    def test_no_filters_passes(self):
        src = mk()
        ok, _ = check_title("Any Title", src)
        self.assertTrue(ok)

    def test_blocklist_case_insensitive(self):
        src = mk(title_blocklist_regex=r"(?i)rumor|leak")
        self.assertFalse(check_title("Apple rumor leaked", src)[0])
        self.assertFalse(check_title("Apple RUMOR leaked", src)[0])
        self.assertTrue(check_title("Apple announces iPhone", src)[0])

    def test_required_regex_must_match(self):
        src = mk(title_required_regex=r"(?i)\b(apple|iphone|ipad)\b")
        self.assertTrue(check_title("New iPhone 17 Pro review", src)[0])
        self.assertTrue(check_title("APPLE launches event", src)[0])
        ok, reason = check_title("Sony PS5 DRM news", src)
        self.assertFalse(ok)
        self.assertIn("required_regex", reason)

    def test_blocklist_and_required_combined(self):
        """同時有 blocklist 和 required：必須通過兩關"""
        src = mk(
            title_blocklist_regex=r"(?i)rumor",
            title_required_regex=r"(?i)apple",
        )
        # Apple + rumor → blocklist 先被擋
        self.assertFalse(check_title("Apple iPhone rumor", src)[0])
        # 只有 apple → 通過
        self.assertTrue(check_title("Apple event recap", src)[0])
        # 只有 rumor（非 Apple）→ blocklist 擋（實際上也 required 失敗）
        self.assertFalse(check_title("Samsung rumor", src)[0])


class TestHashing(unittest.TestCase):

    def test_identical_text_same_hash(self):
        a = "Hello, world!\nThis is content."
        b = "Hello, world!\nThis is content."
        self.assertEqual(sha256_of(a), sha256_of(b))

    def test_different_text_different_hash(self):
        self.assertNotEqual(sha256_of("A"), sha256_of("B"))

    def test_hash_prefix(self):
        h = sha256_of("anything")
        self.assertTrue(h.startswith("sha256:"))
        self.assertEqual(len(h), len("sha256:") + 64)

    def test_unicode_stable(self):
        """中文內容 hash 應穩定（不同編碼方式不應產生不同 hash）"""
        h1 = sha256_of("iPhone 17 Pro 宇宙橙色")
        h2 = sha256_of("iPhone 17 Pro 宇宙橙色")
        self.assertEqual(h1, h2)


class TestSlugify(unittest.TestCase):

    def test_basic_ascii(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_trims_to_maxlen(self):
        long = "a" * 100
        self.assertEqual(len(slugify(long, maxlen=60)), 60)

    def test_collapses_special_chars(self):
        self.assertEqual(slugify("A.B/C:D!"), "a-b-c-d")

    def test_empty_returns_item(self):
        self.assertEqual(slugify(""), "item")
        self.assertEqual(slugify("!!!"), "item")

    def test_unicode_title(self):
        """中文標題轉 slug 應去掉中文（因 regex [a-zA-Z0-9] 不匹配），fallback 'item'"""
        self.assertEqual(slugify("iPhone 17 Pro 產品規格"), "iphone-17-pro")


if __name__ == "__main__":
    unittest.main(verbosity=2)
