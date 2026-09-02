"""OpenSERP 网页搜索插件 — 用户级扩展。

在用户 ``~/.hermes/plugins/web/openserp/`` 下注册一个 OpenSERP 搜索后端。
固定只使用 Baidu 和 Bing 两个引擎（通过 megasearch 并行查询合并去重）。

Search-only — OpenSERP 不负责抓取/提取任意 URL，``supports_extract()``
返回 False。需要 ``web_extract`` 时请与 firecrawl / tavily / exa 等
提取提供商搭配使用。

配置示例 (``~/.hermes/.env``)::

    OPENSERP_URL=http://127.0.0.1:7000

config.yaml::

    web:
      search_backend: "openserp"
    plugins:
      enabled:
        - web/openserp
"""

from __future__ import annotations

from .provider import OpenSERPWebSearchProvider


def register(ctx) -> None:
    """Register the OpenSERP provider with the plugin context."""
    ctx.register_web_search_provider(OpenSERPWebSearchProvider())
