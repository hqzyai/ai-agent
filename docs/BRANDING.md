# 可移植品牌配置

品牌适配使用环境配置，而不是在合并脚本中硬编码租户。默认模板位于 `config/brand.env.example`：

```bash
python3 scripts/validate_brand_profile.py config/brand.env.example
```

| 领域 | 变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 品牌 | `BRAND_NAME` | `AgentOS` | 用户可见产品品牌。 |
| 品牌 | `BRAND_WORDMARK` | `AGENT OS` | 仅用于视觉字标。 |
| 品牌 | `BRAND_SLUG` | `agentos` | 机器短名。 |
| 品牌 | `BRAND_ASSETS_DIR` | `branding/agentos` | 仓库相对品牌素材目录。 |
| 组织 | `ORG_NAME` | `hqzyai` | 组织标识，同时作为 profile 数据目录名。 |
| 应用 | `APP_NAME` | `AgentOS` | OS 和安装器显示的应用名。 |
| 应用 | `APP_ID` | `com.hqzyai.agentos` | 稳定应用 ID。 |
| 应用 | `APP_DATA_DIR` | `~/.agentos` | 用户数据根目录；加载器展开 `~`。 |
| 应用 | `APP_DEFAULT_LOCALE` | `zh-CN` | 默认语言。 |
| Skill Hub | `SKILL_HUB_NAME` | `华清严选` | 用户可见名称。 |
| Skill Hub | `SKILL_HUB_SOURCE` | `nacos` | 内部 source ID。 |

`BRAND_*` 只用于真正的品牌身份，禁止新增 `BRAND_APP_NAME`、`BRAND_COMPANY_NAME` 或 `BRAND_SKILL_HUB_NAME` 这类跨领域名称；旧 `COMPANY_NAME` 也不再接受。

应用实际数据目录固定由两个变量组合：`{APP_DATA_DIR}/profiles/{ORG_NAME}`。默认 profile 因此解析为 `~/.agentos/profiles/hqzyai`。`ORG_NAME` 必须是小写且可安全作为单个路径段，不能包含 `/`、`..` 或空格。

`APP_ID`、`APP_DATA_DIR` 与 `ORG_NAME` 是持久化身份。更换任一值都必须新增 N-1 升级、数据迁移、失败回滚和保留源数据的验收。`HERMES_HOME`、`hermes:*` 等底层兼容协议不属于用户可见品牌，不应因换肤直接重命名。

`BRAND_ASSETS_DIR` 至少包含 logo、wordmark、通用 icon，以及 macOS `icns`、Windows `ico` 和 Linux icon。CI 应验证素材存在且可解析，并在安装后的 About、Dock/任务栏、窗口、favicon 和安装器上做视觉抽检。
