# 01 品牌、中文与产品能力策略

## Requirements

- **BRAND-001** 使用默认 AgentOS profile 时，用户可见产品名、助手身份、窗口标题、安装包、图标、TUI/WebUI 均为 `AgentOS` 或 `AGENT OS`；不得显示 Hermes Agent、Hermes Cloud 或 Nous Research。使用其他 profile 时对应位置必须完全来自配置。
- **BRAND-002** `hermes` 模块名、CLI 兼容入口、`HERMES_HOME`、RPC/IPC 标识可保留，品牌替换不得破坏兼容协议。
- **BRAND-003** 默认 SOUL、系统提示和身份护栏要求助手自称 AgentOS；旧默认 Hermes persona 自动迁移，自定义 persona 不被覆盖。
- **BRAND-004** 可移植配置按领域使用 `BRAND_*`、`ORG_*`、`APP_*` 和 `SKILL_HUB_*`；`BRAND_*` 只描述真实品牌身份。应用实际数据根固定为 `{APP_DATA_DIR}/profiles/{ORG_NAME}`。`APP_ID`、`APP_DATA_DIR` 或 `ORG_NAME` 的变化必须走显式迁移，底层 `HERMES_*` 兼容协议不得因换肤直接重命名。
- **I18N-001** 默认用户可见回复、进度、错误、设置、消息平台字段和帮助均使用简体中文；用户明确要求其他语言时才切换。
- **POLICY-001** Provider、模型、Toolset、Skill 的产品可见性由一个服务端策略模块统一决定，并同时用于 runtime、server API、dashboard 和 desktop。
- **POLICY-002** 允许国内 Provider 和真实自定义 endpoint；明确屏蔽 Nous、OpenAI、Anthropic、Gemini、xAI、Copilot、HuggingFace、Bedrock 等产品面条目。
- **POLICY-003** `image_gen`、`video_gen`、`x_search` 作为完整 toolset 隐藏；`claude-code`、`claude-design`、`codex`、`opencode` 不进入产品技能列表。
- **POLICY-004** 产品面过滤不删除旧配置、磁盘插件或内部兼容实现，升级不得造成用户数据损失。

## Automated acceptance

- 行为测试从 runtime inventory、server API、dashboard payload 和 desktop selector 四个入口输入同一 catalog，断言结果一致。
- 身份测试创建全新 home 和旧默认 persona home，分别验证 AgentOS 身份与安全迁移；另测自定义 persona 原样保留。
- i18n 测试覆盖登录、连接、更新、消息平台字段、定时任务、Skill Hub 和常见错误，不允许通过切换默认 locale 规避中文契约。
- 安装包资源检查 macOS、Windows、Linux 的产品名、图标、可执行文件描述和 bundle/app ID。
- 使用默认 AgentOS profile 和一个无 AgentOS/hqzyai 字样的合成 profile 分别生成配置，断言 UI、安装元数据、`{APP_DATA_DIR}/profiles/{ORG_NAME}` 数据目录、Skill Hub 名称和素材路径均来自 profile；拒绝 `COMPANY_NAME`、`BRAND_APP_NAME`、`BRAND_COMPANY_NAME` 等旧变量。

## Manual acceptance

1. 全新安装后询问“你是谁”，回答只使用 AgentOS 身份。
2. 浏览登录、设置、模型、技能、消息平台、定时任务、关于和更新页面，无上游品牌泄漏。
3. 导入旧配置后验证被隐藏能力不再显示，但配置文件和兼容入口仍存在且未被破坏。
4. 使用非默认品牌 profile 构建至少一个桌面候选，抽检应用名、图标、About、数据目录与 Skill Hub；切回 AgentOS profile 后不得残留上一品牌字符串或素材。
