"""OpenSERP 结果过滤规则 — 与 provider 解耦，便于单独调优。

维护两份黑名单：
- ``BAIDU_REDIRECT_HOSTS``：百度/知乎/CSDN 反爬跳转域名，结果不可直接使用
- ``DEFAULT_BLOCK_HOST_SUBSTRINGS``：默认屏蔽的内容农场/搬运站特征子串
  （仅当用户通过 ``OPENSERP_BLOCK_DOMAINS`` 显式扩展时启用增强列表）
"""

BAIDU_REDIRECT_HOSTS = {
    "nourl.ubs.baidu.com",
    "www.baidu.com",
    "baidu.com",
    "link.zhihu.com",
    "link.csdn.net",
    "link.juejin.cn",
}

# 默认仅屏蔽极低价值的站点；激进列表 (内容农场/搬运站) 由用户通过
# OPENSERP_BLOCK_DOMAINS 显式启用，避免误伤知乎/CSDN 等常有干货的站。
DEFAULT_BLOCK_HOST_SUBSTRINGS = (
    "baijiahao",
    "360doc.com",
)

# 仅在 OPENSERP_BLOCK_DOMAINS 非空时追加：逗号分隔的完整域名，
# 例如 OPENSERP_BLOCK_DOMAINS=zhihu.com,csdn.net,sohu.com
ENHANCED_BLOCK_HOST_SUBSTRINGS = (
    "zhihu.com",
    "csdn.net",
    "cnblogs.com",
    "jianshu.com",
    "sohu.com",
    "sina.com.cn",
    "163.com",
    "toutiao.com",
    "infoq.cn",
)


def is_junk_url(
    url: str,
    redirect_hosts: set,
    host_substrings: tuple,
    block_domains: tuple = (),
) -> bool:
    """Return True when *url* should be filtered out of search results."""
    from urllib.parse import parse_qs, urlparse

    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return True

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return True

    host = (parsed.hostname or "").lower()
    if host in redirect_hosts:
        return True

    # Baidu redirect links: www.baidu.com/link?url=... / baidu.com/s?wd=...
    if host in ("www.baidu.com", "baidu.com") and (
        parsed.path.startswith("/link") or parsed.path.startswith("/s")
    ):
        return True

    # .../link?url=https%3A... — 中转跳转，原始目标在 query 里
    if parsed.path.endswith("/link") and parse_qs(parsed.query).get("url"):
        return True

    if any(s in host for s in host_substrings):
        return True

    for domain in block_domains:
        d = domain.strip().lower()
        if d and host == d or d and host.endswith("." + d):
            return True

    return False


# ---------------------------------------------------------------------------
# 查询相关性过滤
# ---------------------------------------------------------------------------
#
# 背景：bing/baidu 的抓取页在反爬/缓存异常时会返回与查询完全无关的 SEO
# 垃圾结果（如搜「雄安新区」返回「娜美妖姬旗袍」）。这类结果域名正常、
# 类型是 organic，域名黑名单抓不到，只能靠「标题+摘要与查询词是否有
# 重叠」来过滤。
#
# 规则：
# - 中文/日文/韩文连续段取字符 bigram（子串匹配）
# - ASCII token 取长度 >= 2 的字母数字词，词边界匹配；纯 4 位年份
#   不参与（摘要里常带日期文本，年份匹配噪音大）
# - 查询没有任何有效信号（如纯年份查询）时不过滤，全部放行

import re

_CJK_RUN = re.compile(r"[一-鿿㐀-䶿豈-﫿぀-ヿ가-힯]+")
_ASCII_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-.]*")
_YEAR = re.compile(r"^\d{4}$")


def query_signals(query: str) -> tuple:
    """Extract (cjk_bigrams, ascii_tokens) relevance signals from *query*."""
    q = (query or "").lower()
    bigrams: set = set()
    for run in _CJK_RUN.findall(q):
        if len(run) == 1:
            bigrams.add(run)
            continue
        for i in range(len(run) - 1):
            bigrams.add(run[i : i + 2])
    tokens: set = set()
    for tok in _ASCII_TOKEN.findall(q):
        if len(tok) < 2 or _YEAR.match(tok):
            continue
        tokens.add(tok)
    return bigrams, tokens


def relevance_score(title: str, snippet: str, bigrams: set, tokens: set) -> int:
    """Weighted overlap of query signals against title + snippet.

    CJK bigram hit = 2, ascii token hit = 1. Zero means no overlap at all.
    """
    text = (title + "\n" + snippet).lower()
    score = 0
    for b in bigrams:
        if b in text:
            score += 2
    for t in tokens:
        if re.search(r"\b" + re.escape(t) + r"\b", text):
            score += 1
    return score
