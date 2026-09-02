from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


FILTERS_PATH = Path(__file__).parents[1] / "_filters.py"


def load_filters():
    spec = importlib.util.spec_from_file_location("openserp_filters_test", FILTERS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenSerpFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.filters = load_filters()

    def test_malformed_or_non_http_urls_are_junk(self) -> None:
        for url in ("not a url", "javascript:alert(1)", "file:///etc/passwd", "https:///missing-host"):
            with self.subTest(url=url):
                self.assertTrue(
                    self.filters.is_junk_url(
                        url,
                        self.filters.BAIDU_REDIRECT_HOSTS,
                        self.filters.DEFAULT_BLOCK_HOST_SUBSTRINGS,
                    )
                )

    def test_redirects_blocks_and_normal_https_urls(self) -> None:
        self.assertTrue(
            self.filters.is_junk_url(
                "https://www.baidu.com/link?url=target",
                self.filters.BAIDU_REDIRECT_HOSTS,
                self.filters.DEFAULT_BLOCK_HOST_SUBSTRINGS,
            )
        )
        self.assertTrue(
            self.filters.is_junk_url(
                "https://news.example.test/story",
                set(),
                (),
                ("example.test",),
            )
        )
        self.assertFalse(
            self.filters.is_junk_url(
                "https://docs.python.org/3/",
                self.filters.BAIDU_REDIRECT_HOSTS,
                self.filters.DEFAULT_BLOCK_HOST_SUBSTRINGS,
            )
        )

    def test_relevance_signals_match_cjk_and_ascii_queries(self) -> None:
        bigrams, tokens = self.filters.query_signals("雄安新区 AgentOS 2026")
        self.assertEqual(bigrams, {"雄安", "安新", "新区"})
        self.assertEqual(tokens, {"agentos"})
        self.assertGreater(
            self.filters.relevance_score("AgentOS 发布", "雄安新区试点", bigrams, tokens),
            0,
        )
        self.assertEqual(self.filters.relevance_score("无关标题", "没有匹配", bigrams, tokens), 0)


if __name__ == "__main__":
    unittest.main()
