"""OpenSERP 网页搜索 + 网页提取 — 用户级扩展插件。

继承 :class:`agent.web_search_provider.WebSearchProvider`。通过本地
openserp (https://github.com/karust/openserp) 的 megasearch 端点搜索，
固定只使用 ``baidu`` 和 ``bing`` 两个引擎，并行查询、合并去重；
``web_extract`` 走 openserp 的 ``/extract/batch`` 批量提取接口
(``mode=fast``，返回清理后的页面 markdown)。

配置示例 (``~/.hermes/.env``)::

    OPENSERP_URL=http://127.0.0.1:7000   # 本地 openserp serve 地址
    OPENSERP_ENGINES=baidu,bing          # 可选，默认 baidu,bing

config.yaml::

    web:
      search_backend: "openserp"
      extract_backend: "openserp"
    plugins:
      enabled:
        - web/openserp
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider, get_provider_env

logger = logging.getLogger(__name__)

DEFAULT_ENGINES = "baidu,bing"


def _opt(name: str) -> str:
    """Return an optional OpenSERP tuning env var (stripped) or empty string."""
    return get_provider_env(name)


class OpenSERPWebSearchProvider(WebSearchProvider):
    """Search + extract via a user-hosted OpenSERP instance (Baidu + Bing)."""

    @property
    def name(self) -> str:
        return "openserp"

    @property
    def display_name(self) -> str:
        return "OpenSERP (Baidu + Bing)"

    def is_available(self) -> bool:
        return bool(get_provider_env("OPENSERP_URL"))

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def _client(self) -> Any:
        import httpx

        base_url = get_provider_env("OPENSERP_URL").rstrip("/")
        if not base_url:
            return None, None
        return httpx, base_url

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        httpx, base_url = self._client()
        if base_url is None:
            return {"success": False, "error": "OPENSERP_URL is not set"}

        engines = _opt("OPENSERP_ENGINES") or DEFAULT_ENGINES

        params: Dict[str, Any] = {
            "text": query,
            "engines": engines,
            "mode": "balanced",
            "limit": limit,
        }

        try:
            resp = httpx.get(
                f"{base_url}/mega/search",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenSERP HTTP error for %r: %s", query, exc)
            return {
                "success": False,
                "error": f"OpenSERP returned HTTP {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("OpenSERP request error for %r: %s", query, exc)
            return {
                "success": False,
                "error": f"Could not reach OpenSERP at {base_url}: {exc}",
            }

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenSERP response parse error for %r: %s", query, exc)
            return {
                "success": False,
                "error": "Could not parse OpenSERP response as JSON",
            }

        raw_results = data.get("results", [])

        web_results = self._filter_results(raw_results, query)[:limit]

        meta = data.get("meta", {})
        logger.info(
            "OpenSERP search %r (engines=%s): %d results (raw %d, dropped %d) "
            "(responded=%s failed=%s took=%sms)",
            query,
            engines,
            len(web_results),
            len(raw_results),
            len(raw_results) - len(web_results),
            meta.get("engines_responded", "-"),
            meta.get("engines_failed", "-"),
            meta.get("took_ms", "-"),
        )

        return {"success": True, "data": {"web": web_results}}

    def _filter_results(
        self, raw_results: List[Dict[str, Any]], query: str = ""
    ) -> List[Dict[str, Any]]:
        """Drop low-quality / irrelevant OpenSERP results before returning.

        Removes:
        - non-``organic`` types (ads, promoted, image/video widgets…)
        - entries with an empty title, URL, or snippet
        - Baidu redirect junk (``nourl.ubs.baidu.com`` / ``/link?url=``)
        - per-engine duplicates of the same normalized URL
        - hosts matching ``OPENSERP_BLOCK_DOMAINS`` (comma-separated)
        - results with zero query-term overlap (SEO spam / wrong-SERP junk),
          unless nothing overlaps at all (then all pass through)
        """
        from urllib.parse import urlparse

        from ._filters import (
            BAIDU_REDIRECT_HOSTS,
            DEFAULT_BLOCK_HOST_SUBSTRINGS,
            ENHANCED_BLOCK_HOST_SUBSTRINGS,
            is_junk_url,
            query_signals,
            relevance_score,
        )

        block_env = _opt("OPENSERP_BLOCK_DOMAINS")
        block_domains = tuple(d.strip() for d in block_env.split(",") if d.strip())
        host_substrings = DEFAULT_BLOCK_HOST_SUBSTRINGS
        if block_domains:
            host_substrings = host_substrings + ENHANCED_BLOCK_HOST_SUBSTRINGS

        relevance_enabled = _opt("OPENSERP_RELEVANCE_FILTER").lower() not in (
            "0",
            "false",
            "off",
        )
        bigrams, tokens = query_signals(query)

        seen: set = set()
        kept: List[Dict[str, Any]] = []
        for r in raw_results:
            if not isinstance(r, dict):
                continue
            if r.get("type") not in (None, "", "organic"):
                continue
            title = str(r.get("title", "")).strip()
            url = str(r.get("url", "")).strip()
            snippet = str(r.get("snippet", "")).strip()
            if not title or not url or not snippet:
                continue
            if is_junk_url(url, BAIDU_REDIRECT_HOSTS, host_substrings, block_domains):
                continue
            try:
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower()
                normalized = f"{host}{parsed.path.rstrip('/')}"
            except Exception:  # noqa: BLE001
                normalized = url
            if normalized in seen:
                continue
            seen.add(normalized)
            kept.append(
                {
                    "title": title,
                    "url": url,
                    "description": snippet,
                    "position": r.get("rank") or (len(kept) + 1),
                }
            )

        # 相关性过滤：有查询信号时，丢掉零重叠结果；如果一个都不重叠
        # （可能是抓取整体失败/纯英文查询），放行原始结果避免空响应。
        if relevance_enabled and (bigrams or tokens) and kept:
            relevant = [
                item
                for item in kept
                if relevance_score(item["title"], item["description"], bigrams, tokens) > 0
            ]
            if relevant:
                dropped = len(kept) - len(relevant)
                if dropped:
                    logger.info(
                        "OpenSERP relevance filter %r: dropped %d/%d zero-overlap results",
                        query,
                        dropped,
                        len(kept),
                    )
                return relevant
            logger.warning(
                "OpenSERP relevance filter %r: no results overlap query; "
                "returning %d unfiltered results",
                query,
                len(kept),
            )
        return kept

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract clean page content from one or more URLs via /extract/batch.

        OpenSERP batch response is a bare array::

            [
                {"page_content": "...", "metadata": {...}},
                {"page_content": "", "metadata": {"error": "...", "source": url}},
            ]

        Failed URLs carry ``metadata.error``. Results preserve input order,
        which the ``web_extract`` dispatcher relies on.
        """
        httpx, base_url = self._client()
        if base_url is None:
            return [{"url": u, "error": "OPENSERP_URL is not set"} for u in urls]

        if not urls:
            return []

        mode = kwargs.get("mode") or "fast"
        payload: Dict[str, Any] = {"urls": list(urls), "mode": mode}
        fmt = kwargs.get("format")
        if fmt:
            payload["format"] = fmt

        try:
            resp = httpx.post(
                f"{base_url}/extract/batch",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenSERP extract HTTP error: %s", exc)
            return [{"url": u, "error": f"OpenSERP returned HTTP {exc.response.status_code}"} for u in urls]
        except httpx.RequestError as exc:
            logger.warning("OpenSERP extract request error: %s", exc)
            return [{"url": u, "error": f"Could not reach OpenSERP at {base_url}: {exc}"} for u in urls]

        try:
            items = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenSERP extract response parse error: %s", exc)
            return [{"url": u, "error": "Could not parse OpenSERP extract response as JSON"} for u in urls]

        if not isinstance(items, list):
            return [{"url": u, "error": "Unexpected OpenSERP extract response shape"} for u in urls]

        results: List[Dict[str, Any]] = []
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata") or {}
            url = str(meta.get("source") or (urls[position] if position < len(urls) else ""))
            entry: Dict[str, Any] = {
                "url": url,
                "title": str(meta.get("title", "")),
                "content": str(item.get("page_content", "")),
                "raw_content": str(item.get("page_content", "")),
                "metadata": dict(meta),
            }
            if meta.get("error"):
                entry["error"] = str(meta["error"])
                entry["content"] = ""
                entry["raw_content"] = ""
            results.append(entry)

        logger.info(
            "OpenSERP extract %d URL(s): %d ok, %d failed",
            len(urls),
            sum(1 for r in results if not r.get("error")),
            sum(1 for r in results if r.get("error")),
        )
        return results

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "OpenSERP (Baidu + Bing)",
            "badge": "free · self-hosted",
            "tag": (
                "自托管的 SERP API（karust/openserp），搜索固定使用百度与必应两个引擎，"
                "网页正文提取走 openserp /extract/batch。"
                "设置 OPENSERP_URL 指向本地服务；可选 OPENSERP_ENGINES 覆盖引擎列表。"
            ),
            "env_vars": [
                {
                    "key": "OPENSERP_URL",
                    "prompt": "OpenSERP instance URL (e.g. http://127.0.0.1:7000)",
                    "url": "https://github.com/karust/openserp",
                },
                {
                    "key": "OPENSERP_ENGINES",
                    "prompt": "搜索引擎 (可选，默认 baidu,bing)",
                },
            ],
        }
