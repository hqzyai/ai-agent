# 定时任务、消息平台、汉化和桌面 UI 规范

本文记录 AgentOS desktop 的用户可见产品层改造，包括定时任务、消息平台、汉化、登录页、设置页、状态栏和提示弹窗。后续 AI 迁移新 desktop 时，不应只迁移底层连接，用户看到的 AgentOS 产品体验也要完整迁移。

## 1. 产品 UI 总原则

### AgentOS 语境

所有用户可见位置都应使用 AgentOS，而不是原始 Hermes 内部名。包括：

- app icon。
- window title。
- 登录页。
- boot/progress 页面。
- settings。
- gateway status。
- messaging gateway。
- notification。
- toast。
- error message。
- skills。
- artifacts。
- cron。
- dashboard / WebUI sidebar brand。
- TUI 启动画面、横幅、主题名称。
- 模型自我介绍和系统 prompt 身份。

内部代码路径仍可保留 `hermes` 命名，因为底层 agent core 仍是 Hermes。但 UI 文案必须转换。

首页空会话欢迎区的大字品牌是独立 wordmark，固定显示为全大写且带空格的 `AGENT OS`。它由 `apps/desktop/src/components/chat/intro.tsx` 的 `WORDMARK` 控制，视觉文本和 `aria-label` 必须保持一致。不要把这条展示规则扩散到安装包名、可执行文件名、协议名、配置目录或内部 API 标识；这些兼容标识继续使用无空格的 `AgentOS`，避免破坏打包、升级和已有数据。

### 专家技能入口

全尺寸桌面端在“技能与工具”页增加独立的“专家技能”页签，并把它放在“技能”之前作为该页面的默认页签。四个业务入口从“新建会话”欢迎区迁入此页，欢迎区不得再重复展示按钮：

- 固定按 `差旅报销`、`项目研判`、`投资合同审核`、`文书起草` 的顺序显示四张专家卡片。每张卡片包含独立 Tabler 图标、业务名称、专家角色、简短职责说明和三个能力标签；整张卡片可点击并具有键盘 focus-visible 状态。
- 卡片使用现有桌面设计 token，圆角不得超过 8px；宽屏两列、窄屏一列，固定最小高度，标签换行不能撑破或挤压相邻卡片。不得引入营销 Hero、人物图库或嵌套卡片。
- 顶部搜索同时匹配本地化业务名称、专家角色、职责说明、能力标签和真实 skill id；无结果时显示本地化空状态。
- 完整“技能与工具”页面默认打开“专家技能”；Bot Mode 等嵌入式 `SkillsView` 是 Agent 能力配置面，不展示该页签，仍默认打开“技能”，也不得因为专家页触发 profile、skills 或 toolsets 网络读取。
- 专家卡片只负责启动业务会话，不修改当前 profile 的技能开关。点击后必须先通过现有会话控制器进入全新的主会话，再把普通 slash command 草稿写入主 composer；从历史会话、空会话或其他功能页进入时行为一致。
- 跨页面请求使用 `requestNewSessionDraft()`；会话控制器消费请求后依次执行 `startFreshSessionDraft()` 和 `requestComposerInsert(..., { mode: 'replace', target: 'main' })`。这个时序不可倒置，否则路由切换可能把草稿写回旧会话或丢失。
- 点击只生成草稿，不自动发送、不直接调用 backend、不安装技能，也不创建 synthetic system/user message。用户必须能够补充材料、修改模板字段后再主动发送。
- 草稿格式固定为 `/<skill-name> <实例提示词>`。多行提示词保留换行，第一段 slash token 必须保持可被现有 `parseSlashCommand` / `slash.exec` 链路识别。
- 重新进入专家页并点击另一张卡片时，必须再创建一个全新的主会话草稿；使用 `replace/main` 完整写入所选模板，不追加、不混合旧模板，也不得写入 session tile 或消息编辑框。
- 斜杠技能模板中 `【...】` 表示需要用户检查或替换的字段。主 composer 必须把完整中文方括号字段渲染为可辨识的行内高亮，但字段仍继承 `contenteditable`，不得变成 `contenteditable=false` 的 slash/ref chip。编辑、复制、草稿恢复和发送时必须保留用户看到的原始文本，不得注入 HTML、隐藏前缀或其他协议标记；半角大括号 `{...}` 不再表示待填写字段，普通 JSON/代码不得被误高亮。
- 主空会话 composer 的输入引导固定为 `今天帮你做些什么? /调用技能与指令`。该文案是一个完整字符串，其中问号为半角 `?`，斜杠前有一个空格；不得随机轮换旧文案。已有会话继续使用 follow-up placeholder，不受此规则影响。
- 技能缺失、禁用或后端拒绝时沿用普通 slash command 的现有错误路径；renderer 不伪造“已安装”状态。

固定业务模板：

| 展示名 | skill | 实例提示词契约 |
| --- | --- | --- |
| 差旅报销 | `oa-travel-expense` | 固定文本为：`帮我处理这次差旅报销，并创建保存为草稿。`，随后依次是 `出差事由：【简要说明】`、`相关材料：【请上传出行发票、住宿发票等发票，及行程单等其他附件】`、`出发/到达时间：【往返出差地的具体出发到达时间，若材料里有可不填】`、`特殊情况（没有可不填）：【如多人同行、工作餐、公司供车、自驾、部分报销、退改签、个人绕行等】`，结尾为 `请优先从材料、OA 信息和已有业务记忆中自动整理；执行完汇报给我。`。每段独占一行，四个待填写字段只能使用中文方括号 `【】`。 |
| 项目研判 | `project-assessment` | 请基于我上传的【项目BP、立项说明书、项目简报、访谈纪要或财务材料】，对【项目名称/公司名称】开展投前项目研判。请核验主体及核心人员的工商、股权、司法与合规风险，进一步评估业务真实性、产品技术、客户商业化、行业空间和竞争格局；输出红线结论、关键证据、待核实问题、需补充材料和是否建议继续推进的意见。 |
| 投资合同审核 | `investment-contract-review` | 请将全部附件视为同一交易文件包进行联合审查，核对各文件之间的主体、金额、估值、持股比例、权利义务和效力顺序。结合知识库核验法律问题，在相关问题原句或最小必要短语上添加批注，不修改合同正文。完成后交付每份合同对应的批注版docx。 |
| 文书起草 | `document-drafting` | 请基于我上传的企业及项目材料，按项目立项材料征集模板生成一份 Word 文档。请提取已有信息并保留缺失项待补充，识别公司名称，重点涵盖项目基本情况、团队、主营业务、市场与技术、融资及财务客户信息；严格按照真实Word模板填充，统一金额、比例、日期和年度口径，并检查字段完整性及数据一致性。材料没有支持的信息请明确留空，不要编造未经材料支持的事实或财务数据。 |

关键文件和验证：

- `apps/desktop/src/app/skills/experts-tab.tsx`：“专家技能”卡片、搜索、顺序和点击行为。
- `apps/desktop/src/app/skills/index.tsx`：首位/默认页签、完整页面与嵌入模式差异、专家页禁止能力配置请求。
- `apps/desktop/src/components/chat/professional-skill-guides.ts`：唯一的技能名和模板数据源。
- `apps/desktop/src/store/composer.ts`、`apps/desktop/src/app/contrib/wiring.tsx`：跨页面“新会话并预填草稿”请求和消费时序。
- `apps/desktop/src/components/chat/intro.tsx`：只保留欢迎品牌与简介，不再渲染专业工作流入口。
- `apps/desktop/src/app/chat/composer/focus.ts`、`hooks/use-composer-draft.ts`：外部 `replace` 草稿语义。
- `apps/desktop/src/app/chat/composer/rich-editor.ts`、`apps/desktop/src/styles.css`：`【...】` 行内待填写字段的无损渲染和视觉样式。
- `apps/desktop/src/app/chat/composer/rich-editor.test.ts`：待填写字段可编辑、纯文本往返不变且普通 JSON 不误高亮。
- `apps/desktop/src/components/chat/professional-skill-guides.test.ts`：四个模板精确值和多行保真。
- `apps/desktop/src/app/skills/experts-tab.test.tsx`：卡片顺序、搜索字段和精确草稿请求。
- `apps/desktop/src/app/skills/index.test.tsx`：默认专家页签、嵌入模式和专家页零能力配置请求。
- `apps/desktop/src/components/chat/intro.test.tsx`：空会话欢迎区不再重复渲染四个入口。
- `apps/desktop/src/app/chat/composer/hooks/use-composer-draft.test.tsx`：已有草稿被替换而不是拼接。
- `apps/desktop/e2e/professional-skill-guides.spec.ts`：完整 Electron 链路、专家卡片紧凑窗口无溢出、跨页面新会话、输入框精确填充、四个差旅字段实际渲染和后端零请求验证。

### 模型身份也属于品牌化

品牌化不能只改 React/Electron UI。用户在聊天里问“你是谁”“你是什么产品”时，模型也必须回答 `AgentOS`，不能回答 `Hermes Agent`、`Nous Research` 或 `由 Nous Research 创造`。

需要同时检查以下入口：

- `agent/prompt_builder.py` 的 `DEFAULT_AGENT_IDENTITY`：必须明确写 `You are AgentOS`，并说明被问身份时回答 AgentOS。
- `agent/prompt_builder.py` 的平台 hint：`tui`、`webui`、desktop runtime surface 不能使用 `Hermes terminal UI`、`Hermes WebUI`、`Hermes desktop GUI app` 作为用户可见身份。
- `hermes_cli/default_soul.py` 的 `DEFAULT_SOUL_MD`：默认 persona 必须与 `DEFAULT_AGENT_IDENTITY` 一致。这里会写入用户 Hermes home，如果没改，系统 prompt 改了也会被旧 SOUL 覆盖。
- `hermes_cli/default_soul.py` 的 `_LEGACY_TEMPLATE_SOULS`：旧的默认 `You are Hermes Agent...` 必须作为可安全升级模板，否则已有默认用户目录不会自动迁移到 AgentOS。只允许迁移完全匹配旧默认模板的文件，用户自己写过的 persona 不能覆盖。
- `agent/system_prompt.py` 必须在加载 `SOUL.md` 或回退默认身份之后追加 AgentOS 身份护栏：身份问题只回答 AgentOS，不归因于底层运行时、组织、供应商或上游项目。身份护栏要放在已加载 persona 之后，覆盖旧版本默认 `SOUL.md` 的优先级；不要在 renderer 中对模型回答做字符串替换。
- `hermes_cli/skin_engine.py`、`ui-tui/src/theme.ts`、`ui-tui/src/components/branding.tsx`、`ui-tui/src/banner.ts`：TUI 的品牌名、欢迎语、response label、横幅、ASCII logo 都必须是 AgentOS。
- `web/src/i18n/*.ts`、`web/src/themes/presets.ts`、`hermes_cli/web_server.py`：dashboard/WebUI 的 sidebar brand、brandShort、footer org、theme label、FastAPI title、默认 bot name 都必须是 AgentOS。

验收方式：

- 新建会话问 `你好 你是谁`，回答应为 `我是 AgentOS` 或同义中文，不得出现 `我是 Hermes Agent`。
- 使用旧版默认 `SOUL.md` 做回归测试时，系统提示仍必须包含身份护栏，模型不得回答“由 Nous Research 创建”或同义归因；用户自定义的 persona 内容必须保留。
- 切换中文/英文 UI 后，左侧顶部品牌仍显示 AgentOS。
- dashboard/TUI 底部主题名不得出现 `Hermes Teal`，默认主题显示 `AgentOS Teal`。
- `rg -n "Hermes Agent|HERMES AGENT|Hermes Teal|Nous Research" agent/prompt_builder.py hermes_cli/default_soul.py hermes_cli/skin_engine.py ui-tui/src web/src/i18n web/src/themes/presets.ts hermes_cli/web_server.py` 只允许命中内部兼容注释、旧模板常量或底层 runtime/计费语境，不能命中用户可见默认身份；当前生效的 `DEFAULT_AGENT_IDENTITY`、`DEFAULT_SOUL_MD` 和身份护栏不得包含这些品牌名。

### 思考摘要和正文默认使用中文

语言要求属于后端系统提示词契约，不能只在 Electron renderer 中替换回复文本。AgentOS 的公共系统提示词必须在 `SOUL.md`/默认身份和品牌身份护栏之后追加稳定的语言约束，覆盖桌面端、CLI、TUI 和消息网关：

- 默认使用简体中文输出所有用户可见内容。
- 如果界面展示思考/推理摘要、进度说明或工具调用说明，这些可见内容也必须使用简体中文；隐藏的内部推理不属于 UI 契约，不要求也不应通过客户端强制暴露。
- 正文最终回复必须使用简体中文。
- 代码、命令、文件路径、API 名称、标识符、原始错误信息和引用内容在必要时保持原文，避免破坏可复制性和诊断能力。
- 用户在本轮明确指定其他语言时，以本轮明确要求为准。
- 不能通过对模型输出做字符串替换实现，否则会破坏代码、路径、错误信息和流式消息；语言规则必须在后端公共 system prompt 中生效并保持会话稳定，不能每轮重建。

实现和测试：

- `agent/prompt_builder.py`：维护 `CHINESE_OUTPUT_GUIDANCE` 公共提示词常量。
- `agent/system_prompt.py`：在身份护栏之后加入该常量，保证自定义或旧版 `SOUL.md` 也受中文输出规则约束。
- `tests/agent/test_prompt_builder.py`：校验规则包含可见思考摘要和正文要求。
- `tests/agent/test_system_prompt.py`：校验规则进入 stable prompt，避免后续改造只改常量却没有实际注入。

验收方式：

- 新建会话提问，若展示思考摘要，摘要和最终正文均为简体中文。
- 要求模型输出代码、命令或错误信息时，中文解释与原始代码/路径/错误文本边界清晰，原文没有被翻译或损坏。
- 明确要求“请用英文回答”时，本轮正文按用户要求使用英文；下一轮未指定语言时恢复简体中文。

### 中文优先但保留多语言结构

当前中文文案大量落在：

- `apps/desktop/src/i18n/zh.ts`
- `apps/desktop/src/i18n/types.ts`
- `apps/desktop/src/i18n/en.ts`
- `apps/desktop/src/i18n/ja.ts`
- `apps/desktop/src/i18n/zh-hant.ts`

新增 UI 时必须：

- 先在 `types.ts` 增加 key。
- 至少补 `zh.ts` 和 `en.ts`。
- 如果当前文件已有 `ja.ts`、`zh-hant.ts` 对应 section，也要补 fallback 文案。
- 不要直接在组件里散落大段文案，除非是当前 AgentOS 锁定版临时文案，并且后续要迁移到 i18n。
- 后端接口返回的 `name`、`description`、env `prompt` / `description` 可能仍是英文；renderer 必须用 `filterAgentOSMessagingPlatforms()`、`t.messaging.platformDescription` 和 `t.messaging.fieldCopy` 做中文覆盖，不能把后端英文直接露到消息平台业务面板。

### 状态变化要有 toast 和恢复动作

例如消息平台 enable/save 后：

- toast 标题说明变更成功。
- message 提示需要重启 gateway。
- action 提供重启 gateway。

设置或连接失败：

- 使用 `notifyError`。
- 不能只 console.error。

## 2. 技能、模型与工具集：AgentOS 产品面策略

关键文件：

- `hermes_cli/agentos_policy.py`
- `hermes_cli/inventory.py`
- `hermes_cli/model_switch.py`
- `hermes_cli/skills_config.py`
- `hermes_cli/tools_config.py`
- `hermes_cli/web_server.py`
- `agent/skill_utils.py`
- `tools/skills_sync.py`
- `tools/skills_tool.py`
- `docs/agentos-product-surface-policy.md`

### 基本原则

当前最终实现不是只在 desktop React 页面隐藏供应商，而是在 Hermes server 的发现、配置和 API 输出入口统一执行 AgentOS 产品策略。原因是 dashboard、desktop、CLI 配置页和 skill/tool API 都可能重新暴露同一条目；只修改 `ToolsetConfigPanel` 会让其他入口漏出，下一次上游合并也容易恢复。

`hermes_cli/agentos_policy.py` 是唯一策略事实源，应保持 data-only，避免导入模型发现、工具配置或 skill 扫描时产生副作用。调用方负责在各自的边界过滤：

- `inventory.py`、`model_switch.py` 和 `/api/model/options` 各自在公共返回边界过滤模型供应商；
  `inventory.build_models_payload()` 不能假设底层 `list_authenticated_providers()` 已过滤，否则替代
  数据源、测试注入或后续重构会重新暴露屏蔽项。
- `/api/auth/providers`、账户配置接口和 provider 列表过滤认证入口。
- `tools_config.py` 和 toolset API 过滤工具集及其 provider。
- `skills_config.py`、`skill_utils.py`、`skills_sync.py`、`skills_tool.py` 过滤自带技能。

这是产品面隐藏，不是破坏性删除：旧配置、模块、插件目录和内部 provider id 可以保留，以兼容已有数据和上游运行时；但 AgentOS 的产品 API、desktop 和 dashboard 不得再次显示、启用或解析被屏蔽条目。禁止只靠 CSS、中文改名或 renderer 字符串过滤假装完成产品化。

### 模型供应商白名单

当前可见供应商由 `AGENTOS_MODEL_PROVIDER_ALLOWLIST` 维护：

- `alibaba`
- `alibaba-coding-plan`
- `deepseek`
- `kimi-coding-cn`
- `lmstudio`
- `minimax-cn`
- `qwen-oauth`
- `stepfun`
- `tencent-tokenhub`
- `xiaomi`
- `zai`

另外保留 `custom`、`custom:<name>`，以及具有 API URL 的真正用户自定义 provider，支持私有网关和本地模型。`minimax-oauth` 通过别名归一为 `minimax-cn`。历史配置不能仅凭 `is_user_defined` 绕过屏蔽名单；如 slug 是已知国外 provider，即使旧 picker 把它标记成 user-defined 也必须隐藏。

显式屏蔽名单至少包含：`nous`、`openrouter`、`anthropic`、`openai-api`、`openai-codex`、`novita`、`xai-oauth`、`nvidia`、`copilot`、`copilot-acp`、`huggingface`、`gemini`、`vertex`、`xai`、`kimi-coding`、`minimax`、`ollama-cloud`、`arcee`、`gmi`、`kilocode`、`opencode-zen`、`opencode-go`、`bedrock`、`azure-foundry`。

### 自带技能屏蔽

以下属于国外编码智能体集成或当前产品不提供的非通用技能，不出现在 AgentOS skill 列表、同步结果和 agent 可用技能中：

- `claude-code`
- `claude-design`
- `codex`
- `opencode`

过滤必须同时覆盖展示和 runtime skill discovery。只从页面移除卡片但仍让模型加载对应 skill，会继续产生不可用命令和品牌泄漏。

### 整体隐藏的工具集

当前仓库内没有可达的国产 provider，因此以下工具集整体不向 AgentOS 暴露：

- `image_gen`
- `video_gen`
- `x_search`

这取代了早期“图像生成保留 Qwen/Z-Image、视频生成保留 Seedance/Kling”的中间方案。现在不得显示 `AgentOS 图像生成`、`AgentOS 视频生成` 或任何 provider/model 配置行，也不得让旧 enabled 配置在升级后重新解析到工具列表。以后只有在真正接入并端到端验证可用的国产 backend 后，才能修改集中策略重新开放；不能因为模型名字看起来国产，就继续通过 FAL、Nous Portal 或其他被屏蔽的国外链路暴露。

### 保留的本地和自托管能力

未列入 `AGENTOS_HIDDEN_TOOLSETS` 的工具集仍可使用，但其 provider 也要遵循可达性原则。例如浏览器、网页抓取、TTS、Home Assistant、computer use 优先保留本地或自托管入口；不得从旧组件级白名单恢复 Browserbase、Firecrawl、Exa、Tavily、OpenAI、ElevenLabs 等国外云配置。

### 测试要求

必须覆盖所有入口，而不只是 React 组件：

- 模型 inventory、model picker、认证 provider API 都不返回屏蔽供应商。
- `custom`、`custom:<name>`、LM Studio 和白名单国产 provider 仍可见。
- 伪装成 `is_user_defined` 的屏蔽 slug 仍不可见。
- `image_gen`、`video_gen`、`x_search` 不出现在 toolset 列表、配置 API 或运行时 enabled toolsets。
- `claude-code`、`claude-design`、`codex`、`opencode` 不出现在 skill list、同步和 runtime 发现结果。
- 旧配置内容仍留在磁盘，策略过滤不得擅自删除用户配置或插件文件。
- 上游合并后执行 `tests/hermes_cli/test_agentos_policy.py`、inventory、tools config、skills profile 和 web server 相关测试，防止新增入口绕开统一策略。

## 3. 登录页 UI

文件：

- `apps/desktop/src/components/login-screen.tsx`

### 布局

登录页是全屏居中：

- 背景 `bg-background`。
- 中央最大宽度约 380px。
- 顶部显示 `BrandMark`。
- 标题：`登录 AgentOS`。
- 字段：
  - `用户名`
  - `密码`
- 主按钮：
  - loading 时 `Loader2`。
  - idle 时 `LogIn`。
  - 文案 `登录`。

窗口拖动：

- 页面背景有 `[-webkit-app-region:drag]`。
- 表单区 `[-webkit-app-region:no-drag]`。
- 顶部 titlebar 高度用 `TITLEBAR_HEIGHT`。

### 登录错误归一

函数：

- `loginErrorMessage(err)`

规则：

- 去掉 Electron remote method wrapper。
- 去掉 `Error:` 前缀。
- 去掉尾部括号堆栈。
- `AgentOS BFF` 替换成 `AgentOS 服务`。
- `BFF hosted-gateway` 替换成 `服务`。
- `invalid username or password`、401、403、中文用户名密码 -> `用户名或密码错误。`
- HTML 或超长 message -> `登录失败，请检查账号密码或服务配置。`
- timeout -> `登录超时，请检查网络或服务地址配置。`
- network/ECONNREFUSED/ENOTFOUND/EHOSTUNREACH/ECONNRESET -> `无法连接服务，请检查客户端服务地址配置。`
- Desktop auth session unavailable -> `桌面登录会话不可用，请重新启动客户端。`
- 如果是中文 message，保留。
- 否则 fallback `登录失败，请检查账号密码或服务配置。`

迁移新 UI 时，错误提示不要直接显示服务端 HTML 或英文栈。

## 4. Gateway 设置 UI

文件：

- `apps/desktop/src/app/settings/gateway-settings.tsx`

当前 AgentOS 锁定版：

```ts
const LOCKED_GATEWAY_SETTINGS = true
```

含义：

- 固定远程账号密码登录。
- local gateway card 禁用。
- remote gateway card 固定 active。
- token 输入不作为主路径。
- 设置项展示 BFF base URL，而不是 hosted gateway full URL。

### BFF URL 输入

label：

```text
BFF 调用地址
```

placeholder：

```text
DEFAULT_BFF_URL
```

description：

```text
AgentOS BFF 服务基础 URL；客户端会自动使用 /desktop/hosted-gateway 连接远程网关。
```

保存 payload 时：

```ts
remoteUrl: hostedGatewayUrlFromBffBase(trimmedUrl)
remoteAuthMode: 'oauth'
mode: 'remote'
```

展示 state 时：

```ts
remoteUrl: bffBaseFromRemoteUrl(config.remoteUrl || DEFAULT_BFF_URL)
```

### Scope

旧逻辑支持 all profiles 与 named profile：

- `scope === null` 表示全局。
- `scope === profile.name` 表示 per-profile override。

但 locked mode 下不展示 profile scope。后续如果新 desktop 要恢复 per-profile UI，必须保留：

- global save 不清空 profiles。
- per-profile save 不重启 primary backend。
- per-profile remote 只影响该 profile pooled backend。

## 5. 定时任务 UX

文件：

- `apps/desktop/src/app/cron/index.tsx`
- `apps/desktop/src/app/cron/job-title.ts`
- `apps/desktop/src/app/cron/job-state.ts`

### 设计目标

用户不直接写 cron 表达式。用户通过常见时间选择生成 cron。提交给后端仍然是 5 段 cron expression。中文界面中，用户可见标题、按钮、状态栏入口和弹窗说明统一叫 `定时任务` / `定时表达式`，不要显示 `Cron`、`排程` 这类英文或机翻词。

这个设计要完整保留，因为产品要求是：

```text
让用户直接选择对应的时间点设置定时任务，而不是配置 cron。
```

### 数据流

创建：

```text
CronEditorDialog
  -> user selects preset, or chooses custom time with <input type="time">
  -> scheduleForTime(...) only when preset is custom
  -> handleEditorSave(...)
  -> resolveCronJobName(name, prompt, schedule)
  -> createCronJob({ prompt, schedule, name, deliver: 'local' })
  -> update $cronJobs atom
```

编辑：

```text
existing job
  -> scheduleOptionForExpr(job.schedule.expr)
  -> cronTimeInputValue(expr) for custom time prefill
  -> user edits preset or custom time
  -> scheduleForTime(...) for custom daily schedule
  -> updateCronJob({ ..., deliver: 'local' })
```

投递目标：

- AgentOS 锁定版只投递到此桌面，编辑器中不再展示 Telegram、Discord、Slack、Email 等可选项。
- UI 用 disabled input 显示 `此桌面`，提交 payload 固定 `deliver: 'local'`。
- 如果迁移新 desktop 时后端仍支持其他投递方式，也不要在当前 AgentOS 桌面入口暴露，除非产品重新要求。

### 支持的 preset

`SCHEDULE_OPTIONS`：

```ts
[
  { expr: '0 9 * * *', value: 'daily' },
  { expr: '0 9 * * 1-5', value: 'weekdays' },
  { expr: '0 9 * * 1', value: 'weekly' },
  { expr: '0 9 1 * *', value: 'monthly' },
  { expr: '0 * * * *', value: 'hourly' },
  { expr: '*/15 * * * *', value: 'every-15-minutes' },
  { value: 'custom' }
]
```

自定义模式：

- 不显示 cron 语法输入框。
- 不显示 `0 9 * * *`、`weekdays at 9am` 之类表达式示例。
- 只显示一个原生 `<input type="time">`，让用户选择每天执行时间。
- 选择自定义时，从当前 schedule 读取 hour/minute：`cronTimeInputValue(expr)`。
- 用户修改时间时，用 `scheduleForTime(value)` 生成提交给后端的 5 段 cron expression。

### 自定义时间生成规则

当前实现是最小可用模型：自定义 = 每天固定时间运行。

```ts
function cronTimeInputValue(expr: string): string {
  // 可解析 5 段 cron 且 minute/hour 是整数时返回 HH:mm，否则返回 09:00。
}

function scheduleForTime(value: string): string {
  // HH:mm -> `${minute} ${hour} * * *`
  // 非法值 fallback 为 `0 9 * * *`。
}
```

示例：

- `09:00` -> `0 9 * * *`
- `18:30` -> `30 18 * * *`

如果后续要支持“每周某天几点”“每月某日几点”等复杂自定义，不要恢复裸 cron 输入框；应增加 weekday/month-day 等原生控件，再继续由前端生成 cron。

### cron 生成规则

当前 preset 仍直接使用 `SCHEDULE_OPTIONS` 中的固定表达式：

- daily -> `0 9 * * *`
- weekdays -> `0 9 * * 1-5`
- weekly -> `0 9 * * 1`
- monthly -> `0 9 1 * *`
- hourly -> `0 * * * *`
- every-15-minutes -> `*/15 * * * *`
- custom -> `scheduleForTime(customTime)`，即每天固定时间。

### cron 识别规则

`scheduleOptionForExpr(expr)` 用于编辑已有任务：

- exact match 优先。
- `dayOfMonth='*' month='*' dayOfWeek='*'` 且 hour/minute 是整数 -> daily。
- dayOfWeek `1-5` -> weekdays。
- dayOfWeek 单整数 -> weekly。
- dayOfMonth 单整数 -> monthly。
- hour `*` 且 minute 整数 -> hourly。
- `*/N * * * *` -> every-15-minutes 或 interval。
- 其他 -> custom。

### summary 文案

`scheduleSummary(option, expr, c)` 输出用户可读说明：

- 每天某时间。
- 工作日某时间。
- 每周某天某时间。
- 每月某日某时间。
- 每小时整点或每小时第 N 分钟。
- 每 N 分钟。
- fallback 使用 scheduleHints。

### 任务名称生成

文件：

- `apps/desktop/src/app/cron/job-title.ts`

目标：

用户不填名称时，根据 prompt 自动生成名称。

公开函数：

- `summarizeCronPromptTitle(prompt, schedule?)`
- `resolveCronJobName(name, prompt, schedule?)`

规则：

- 默认标题 `定时任务`。
- 最大 32 字。
- 去掉代码块、引号、URL。
- 压缩空白。
- 清理开头/结尾标点。

中文逻辑：

- briefing-like 且 daily/早晨类 -> `晨间简报`。
- briefing-like -> `消息简报`。
- 匹配 `日报|周报|月报|简报` 直接取片段。
- 匹配 `检查|监控|查询|统计|汇总|总结 + 主题` -> `主题动作`。
- 匹配 `主题 + 检查|监控|查询|统计|汇总|总结` -> 原片段。
- 匹配 `提醒 + 主题` -> `主题提醒`。
- fallback 去掉 `请|帮我|帮忙|定时|每天|每日|每周|每月|每小时|自动|把|将|给我|我|需要` 等噪声，取首句前 12 字。

英文逻辑：

- 去掉非字母数字和标点噪声。
- 分词。
- 去停用词：
  - a/about/all/an/and/at/by/for/from/in/me/my/of/on/please/send/show/summarize/summary/tell/the/to/with
- 取前 4 个重要词。
- title case。

### 任务状态

文件：

- `apps/desktop/src/app/cron/job-state.ts`

状态点颜色：

- completed/disabled -> quaternary text。
- enabled/scheduled/running -> primary。
- error -> destructive。
- paused -> amber。

`jobState(job)`：

- explicit `job.state` 优先。
- 否则 `enabled === false` -> disabled。
- 否则 scheduled。

`jobTitle(job)`：

- name。
- prompt 前 60。
- script 前 60。
- id。
- fallback `Cron job`。

这个函数是 sidebar 和 Cron page 共用源，不要复制出第二套。

### Run history

`CronJobRuns`：

- 打开 detail 后调用 `getCronJobRuns(jobId)`。
- 每 8 秒 poll 一次。
- tab visible 时刷新。
- run row 点击打开 session。

## 6. 消息平台 UX

文件：

- `apps/desktop/src/app/messaging/index.tsx`
- `apps/desktop/src/app/messaging/platform-icon.tsx`
- `apps/desktop/public/messaging-icons/`
- `apps/desktop/src/i18n/zh.ts`
- `apps/desktop/src/i18n/types.ts`

### AgentOS 平台筛选

当前只展示：

```ts
['dingtalk', 'feishu', 'wecom_callback', 'wecom', 'weixin', 'qqbot']
```

别名：

- `wecom_callback` -> 企业微信（应用）。
- `wecom` -> 企业微信（群机器人）。
- `dingtalk` -> 钉钉。
- `feishu` -> 飞书 / Lark。
- `qqbot` -> QQ 机器人。
- `weixin` -> 微信 / WeChat（个人号）。

中文 label：

- dingtalk -> 钉钉。
- feishu -> 飞书 / Lark。
- qqbot -> QQ 机器人。
- wecom -> 企业微信（群机器人）。
- wecom_callback -> 企业微信（应用）。
- weixin -> 微信 / WeChat（个人号）。

排序：

```text
DingTalk -> Feishu / Lark -> WeCom (app/group bot) -> Weixin / WeChat -> QQ Bot
```

renderer 不得保持后端 catalog 顺序；必须通过 `filterAgentOSMessagingPlatforms()` 固定为钉钉、飞书、企业微信、微信、QQ。该函数必须在 `getMessagingPlatforms()` 成功返回后、写入 React state 前执行。如果 `wecom_callback` 存在，隐藏 send-only 的 `wecom`，优先展示企业微信应用。

### 平台文案

`MessagingView` 中的平台文案规则：

- 平台名称由 `filterAgentOSMessagingPlatforms()` 写入固定中文名称。
- 顶部短描述优先取 `t.messaging.platformDescription[platform.id]`，没有映射时才回退后端 `platform.description`。
- list row、detail header、detail description、search hints、search filter、enable/save toast、switch aria-label 都要走本地化后的名称/说明。
- `platformIntro` 只控制 `获取你的凭据` 段落，不负责顶部短描述。

### 平台图标

本地图片：

- `messaging-icons/dingtalk.png`
- `messaging-icons/feishu.png`
- `messaging-icons/wecom.png`

Simple Icons：

- telegram、discord、mattermost、matrix、signal、whatsapp、bluebubbles、homeassistant、email、weixin、qqbot、yuanbao。

fallback：

- Slack 因品牌方要求移除 Simple Icons，使用字母 S。
- 未知平台使用首字母 monogram。

图标 UI：

- size 6。
- brand color 16% tint 背景。
- 本地 image 用 rounded-md object-cover。

### 消息平台页面行为

`MessagingView`：

- 加载 `getMessagingPlatforms()`。
- 通过 `filterAgentOSMessagingPlatforms(result.platforms)` 筛选；禁止把未筛选的 `result.platforms` 直接传给 `setPlatforms`。
- route query `platform` 控制选中项。
- 支持搜索平台 id/name/description/state。
- 每 6 秒静默刷新状态，tab hidden 暂停。
- enable/disable 调 `updateMessagingPlatform(platform.id, { enabled })`。
- save env 调 `updateMessagingPlatform(platform.id, { env })`。
- clear env 调 `updateMessagingPlatform(platform.id, { clear_env: [key] })`。

toast：

- enable/disable 后提示 gateway restart 生效。
- save credentials 后提示 restart reconnect。
- toast action 是 `runGatewayRestart()`。

字段：

- env var schema 来自后端。
- label/help/placeholder 优先取 `t.messaging.fieldCopy[key]`。
- `MessagingField` 的 placeholder 回退顺序必须是 `localized.placeholder -> localized.label -> field.prompt`。中文表应显式提供 placeholder；即使漏掉 placeholder，也先使用中文 label，不能直接泄漏后端英文 prompt。
- `fieldCopy` 必须覆盖 AgentOS 五个平台的必填字段：`DINGTALK_CLIENT_ID`、`DINGTALK_CLIENT_SECRET`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ENCRYPT_KEY`、`FEISHU_VERIFICATION_TOKEN`、`WECOM_BOT_ID`、`WECOM_SECRET`、`WECOM_CALLBACK_*`、`WEIXIN_ACCOUNT_ID`、`WEIXIN_TOKEN`、`WEIXIN_BASE_URL`、`QQ_APP_ID`、`QQ_CLIENT_SECRET`、`QQ_ALLOWED_USERS`。
- 常见 allowlist、home channel 和 webhook 字段也要提前维护中文：`*_ALLOWED_USERS`、`*_ALLOW_ALL_USERS`、`*_HOME_CHANNEL`、`*_HOME_CHANNEL_NAME`、`QQ_GROUP_ALLOWED_USERS`、`DINGTALK_WEBHOOK_URL`。
- 截图中已确认需要覆盖的 placeholder 示例：`Allowed users (comma-separated)` -> `填写允许的钉钉用户 ID（多个用英文逗号分隔）`，`Home channel ID` -> `填写钉钉主页会话 ID`，`Home channel display name` -> `填写钉钉主页会话名称`，`DingTalk robot webhook URL (optional)` -> `填写钉钉机器人 Webhook URL（可选）`。
- FIELD_COPY 中标为 advanced 的字段要隐藏在高级区域或样式上弱化。

### 消息平台运行时配对提示

消息平台设置页汉化完成不代表消息平台品牌化完成。飞书、钉钉、企业微信、微信、QQ 等平台收到陌生用户私聊时，配对回复由 Hermes server 的 gateway 授权链路生成，不经过 desktop renderer。关键文件：

- `gateway/run.py`：未授权私聊进入 `pair` 策略时生成并发送配对回复。
- `gateway/pairing.py`：配对码、授权记录和 AgentOS 用户可见配对模板。
- `pyproject.toml` 的 `[project.scripts]`：同时注册 `hermes` 和 `agentos`，两者都指向 `hermes_cli.main:main`。
- `hermes_cli/pairing.py`、`hermes_cli/gateway.py`、`plugins/platforms/*/adapter.py`：管理员控制台中的配对命令示例。

用户可见配对回复固定使用中文和 AgentOS 品牌：

```text
你好，我还没有识别到你的身份。

你的 AgentOS 配对码是：<code>

请让 AgentOS 管理员运行：
agentos pairing approve <platform> <code>
```

约束：

- 回复中不得出现 `Hermes`、`Hermes Agent`、`Nous Research` 或 `hermes pairing approve`。
- 配对请求过多时显示 `当前配对请求过多，请稍后再试。`，不得回退英文。
- 展示的命令必须真实可执行，不能只把字符串从 `hermes` 替换为 `agentos`。`agentos` console script 是兼容入口，继续调用同一个 `hermes_cli.main:main`。
- 底层协议、Python 模块、配置目录、容器路径、`hermes` Linux 用户、配对文件格式和授权逻辑继续保留 Hermes 兼容命名；不要为品牌化迁移或重写这些内部标识。
- 配对模板必须放在 gateway/pairing 公共链路中，不要只在飞书 adapter 中硬编码。这样所有启用 DM pairing 的平台共享同一品牌和汉化规则。
- 配对码不得写入日志；测试只使用固定假码。

验收：

1. 使用未在 allowlist/approved store 中的飞书用户给机器人发送私聊。
2. 飞书收到中文 AgentOS 配对回复，命令为 `agentos pairing approve feishu <code>`。
3. 在运行 AgentOS server 的同一环境执行该命令，批准后用户下一条消息可正常进入 agent。
4. `agentos pairing --help` 与 `hermes pairing --help` 都可执行，底层行为一致。
5. `rg -n "hermes pairing approve" gateway/run.py hermes_cli/pairing.py hermes_cli/gateway.py plugins/platforms/feishu plugins/platforms/wecom` 不得命中用户可见文案；内部注释和历史兼容测试可保留。

## 7. 技能页和快捷导航

相关 i18n：

- `skills`
- `commandCenter.nav.skills`
- `artifacts.nav.skills`

规范：

- 技能页标题、搜索、刷新、空状态、启用/禁用 toast 都要汉化。
- 技能数量显示本地化。
- 如果后端提供 skill-derived slash command，desktop slash palette 不应隐藏用户扩展命令。
- desktop 的 slash curation 是为了隐藏 terminal-only/messaging-only 噪声，不是隐藏用户激活的 skills/quick commands。

关键文件：

- `apps/desktop/src/lib/desktop-slash-commands.ts`
- `apps/desktop/src/app/chat/composer/hooks/use-slash-completions.ts`
- `apps/desktop/src/app/session/hooks/use-prompt-actions.ts`

迁移时要保留：

- `isDesktopSlashCommand(name)` 执行 gate。
- `isDesktopSlashSuggestion(name)` suggestion gate。
- `isDesktopSlashExtensionCommand(name)` 让 skill/quick commands 透出。

### Hub 安装后的技能索引一致性

#### “华清严选”Nacos 单一来源的搜索与安装路由

AgentOS 只允许使用 Nacos 承载租户技能目录。内部协议、identifier 和 lock 文件中的 source
ID 固定保留为 `nacos`，用户界面统一显示“华清严选”，不能展示 `Nacos`、`nacos` 或任何
上游 Hub 品牌。该来源边界不是优先级，而是产品级 allowlist：

- Desktop 技能中心只能渲染 AgentOS 自有 Hub 页面并通过当前连接的
  `skills.hub.*` / `skills.manage` 后端能力搜索、预览、安装和卸载。不得恢复上游
  `EmbeddedHubPicker`、`HUB_PICKER_URL`，不得 iframe 打开
  `hermes-agent.nousresearch.com/docs/skills`，Bot Mode 的技能选择器也必须遵守同一来源边界。
  当前租户目录不可用时应展示可诊断的空态或错误，不能静默回退到 Nous 公网页面。
- `tools.skills_hub.create_source_router()` 无条件只返回 `source_id()=="nacos"` 的 source。
  `skills_hub.enabled_sources` 即使来自旧 profile 并列出 official、GitHub 或 Hermes Index，
  也不能重新打开公网来源。
- `GET /api/skills/hub/sources` 只返回一个 `{id:"nacos", label:"华清严选"}` source；landing
  `featured` 只从 Nacos 按完整 `_HUB_CATALOG_LIMIT` 获取。Nacos 无结果或不可用时显示空态或错误，
  不得使用官方 index teaser 补位。
- Desktop renderer 必须再次过滤 sources、featured 和 search results；只接受 source 为 `nacos`
  且 identifier 以 `nacos/` 开头的结果，并强制覆盖 label 为“华清严选”。这是连接旧 server 时的
  兼容防线，不能只依赖新版后端。
- `GET /api/skills/hub/search?source=all` 为旧客户端保留，但 `all` 只能映射到 `nacos`；显式
  `source=nacos` 使用相同路径。其他 source 返回 400。Nacos 搜索总预算为 8 秒，timeout 明确返回
  `timed_out:["nacos"]`，零结果直接返回空数组，任何情况都不能 fallback 到公网。
- install、preview 和 scan 只接受 `nacos/...` identifier；其他 source identifier 返回 400。
  `_resolve_source_meta_and_bundle()` 只接收过滤后的 Nacos router，禁止 inspect/fetch GitHub、
  ClawHub、Official 或 Hermes Index。

对应测试必须覆盖：旧 router 的公网 source 被剔除、旧 profile 配置不能重开公网、sources 只返回
“华清严选”、`all` 仅调用一次 Nacos、Nacos miss/timeout 均不查公网、非 Nacos source/identifier
返回 400，以及 desktop 对旧 server 返回的公网 chip、featured 和 result 做二次过滤。

#### 无交互动作和页面刷新

- CLI 的 `skills uninstall` 必须支持 `--yes`/`-y`，并把该值传给
  `do_uninstall(..., skip_confirm=True)`；dashboard 子进程不能卡在不可见确认提示。
- Hub install/update/uninstall 轮询进入完成态后，页面必须重新拉取 sources/installed、
  featured 和完整 skills list。仅更新 badge 不够，否则技能已经落盘但“已安装”页和快捷入口仍旧。
- 普通 `budget has been exceeded` 不得把 provider 原文展示在 Skill 页面关联的任务状态中，
  统一显示中文超预算提示；包含 key 的限额错误还必须遵守模型错误脱敏规范。

Hub 安装、更新和卸载由 dashboard 启动独立 CLI 子进程执行。子进程内调用
`clear_skills_system_prompt_cache()` 不能清理已经运行的 desktop/server 进程内存，因此
成功动作写入的当前 profile `skills/.hub/lock.json` 是跨进程技能清单 generation：

- `agent/prompt_builder.py` 的技能提示词 L1 cache key 必须包含 lock file 的
  `mtime_ns`、`ctime_ns` 和 `size`；只影响下一次 system prompt 构建，不得改写活动会话
  已经缓存的 prompt prefix。
- `tools/skills_tool.py` 的发现缓存 signature 必须包含同一 generation，使 dashboard
  技能列表和 `skills_list` 在安装完成后的下一次请求立即看到新技能，不能依赖 30 秒 TTL。
- `agent/skill_commands.py` 必须在每次读取命令表时比较 generation；发生变化立即重扫，
  使 desktop slash palette 和直接 `/skill-name` 调用同时注册新技能。
- profile 切换也必须改变 signature。路径必须在调用时通过 `_skills_dir()` 解析，不能使用
  进程 import 时冻结的 `SKILLS_DIR`。
- 磁盘 prompt snapshot 继续使用递归 `SKILL.md` / `DESCRIPTION.md` manifest 校验；lock
  generation 负责跨进程唤醒，manifest 负责确认实际文件内容。

### `skill_view` 分类名称契约

- `<available_skills>` 的分类标题（例如 `enterprise/investment:`）只是组织标签。
  模型应把 `-` 后展示的精确技能名传给 `skill_view`，不得拼成
  `enterprise/investment:investment-contract-review`。
- 只有名称冲突时才使用 `category/skill-name` 路径。提示词必须明确写出这条规则，不能只
  依赖缩进让模型猜测。
- 工具端保留防御性兼容：若模型仍传入 `category/subcategory:skill-name`，将其转换成
  本地 `category/subcategory/skill-name` 查询；合法单段 `plugin:skill` 仍优先走插件注册表。
- 兼容解析不得放宽安全边界。绝对路径、Windows drive、`..` traversal 和非法插件
  namespace 仍必须拒绝；不得简单按冒号或斜杠截断后只取最后一段，因为那会绕过冲突检测。
- 回归测试除了缓存单测，还必须至少有一条真实 Hub 安装链路：从 source fetch、quarantine、
  security scan、`install_from_quarantine`、lock 登记一直执行到 `resolve_skill_command_key` 和
  `build_skill_invocation_message`。技能应安装到已有多级分类，预先热过空 slash index，安装后
  立即验证 desktop/TUI 的完整 slash 链路：`commands.catalog` 必须让裸 `/` 菜单出现该技能，
  `complete.slash` 必须让 `/skill-prefix` 补全到该技能，`command.dispatch` 必须让用户直接输入
  `/skill-name <instruction>` 后返回 `type=skill` 并加载完整 `SKILL.md`；禁止用 sleep 等待 TTL。
- Desktop 的 Hub 安装/更新/卸载是异步子进程动作。动作结束后必须调用
  `invalidateSlashCompletions()`，同时清理 catalog 与 typed-completion 缓存并递增 completion epoch；
  安装成功后用户再次打开 `/` 必须重新请求目录，不得继续使用最长一小时的安装前缓存，也不得
  要求重启客户端或手动执行 `/reload-skills`。该行为需要 store 层回归测试直接断言。
- Desktop 回归测试和合并审计必须扫描并拒绝 `EmbeddedHubPicker`、`HUB_PICKER_URL` 和
  `hermes-agent.nousresearch.com/docs/skills`，避免上游自动合并重新接入公网技能选择器。
- AgentOS 默认启用 Nacos Hub，因此 URL source 的通用用例不能替代 Nacos source 用例。Nacos
  用例必须使用真实 `NacosSkillSource`、真实 `do_install` 与真实隔离/扫描/落盘逻辑；允许仅在
  HTTP 边界注入确定性的列表和 ZIP 响应，避免测试依赖外部服务可用性和测试账号。
- Desktop 是长驻进程，登录切换、profile 切换或远程实例切换后，`HERMES_HOME` 可能与模块
  首次导入时不同。技能发现、`normalize_skill_lookup_name`、`skill_view`、slash invocation
  payload 构建和支持文件提示必须共同使用 `tools.skills_tool._skills_dir()` 的运行时结果，不能
  混用导入时冻结的 `SKILLS_DIR`；否则命令索引虽然存在，加载阶段仍会把新账号的技能绝对路径
  判为目录外路径。回归测试必须先模拟 home A 导入，再切换 home B 安装并直接 `/skill-name`。

### Dashboard 多技能目录配置

安装器、共享卷和租户目录可能把技能落在不同位置。所有技能入口必须复用服务端现有的
`skills.external_dirs` 列表，禁止为 dashboard、desktop 或 `skill_view` 再增加一套目录配置：

- Dashboard `/config` 必须提供独立“技能”分类，不能把技能目录藏在包含大量字段的“代理”分类。
- `skills.external_dirs` 在表单中使用逐行多路径控件，支持添加、删除和上下移动；不得退化为一个
  逗号分隔文本框。列表顺序必须原样写入 `config.yaml`，因为发现列表使用该顺序决定展示优先级。
- 路径属于 AgentOS 服务端或容器文件系统，不是打开浏览器的客户端电脑。界面必须明确说明这一点。
- 每项支持 `~`、`${VAR}` 和相对路径；相对路径以当前 profile 的 `HERMES_HOME` 为基准解析。
  解析后只加载实际存在的目录，去重，并排除当前 profile 自带的 `skills/` 目录。
- 每个 profile 保存自己的 `skills.external_dirs`。profile、远程实例或登录账号切换后必须读取目标
  profile 的配置，不能沿用进程首次启动时的目录。
- 保存后不得要求重启网关。`get_external_skills_dirs()` 以 config path + `mtime_ns` 为缓存键，
  `_find_all_skills()`、prompt builder 和 slash command 的扫描签名必须纳入目录列表，使下一次请求
  同时更新技能页、`skills_list`、系统提示、slash palette 和 `skill_view()`。
- 完整扫描顺序为：受信任项目技能目录、当前 profile 自带技能目录、`external_dirs` 配置顺序。
  `skill_view()` 遇到同名候选必须返回歧义错误和全部路径，不得静默加载错误目录；用户可传
  `category/skill-name` 消除歧义。
- 外部目录仍遵守技能排除目录、平台/环境 gate、路径穿越、支持文件和安全扫描边界；配置更多
  目录不能放宽 `..`、绝对 skill name、非法 namespace 或 supporting-file 的限制。

关键文件：

- `hermes_cli/config_defaults.py`
- `hermes_cli/web_server.py`
- `web/src/pages/ConfigPage.tsx`
- `web/src/components/AutoField.tsx`
- `agent/skill_utils.py`
- `tools/skills_tool.py`

回归测试至少覆盖：schema 中该字段为 `type=list`、`format=paths` 且属于 `skills` 分类；表单可
增删和调整顺序；dashboard PUT 后同一进程立即读到两个目录；两个目录中的不同技能都能被
`skill_view()` 加载。

## 8. Gateway/status bar 和弹窗

### 看板插件默认启用

AgentOS 将看板作为内置业务能力，而不是首次安装后还要手动发现并开启的实验插件：

- `apps/desktop/src/plugins/kanban/plugin.tsx` 的 `defaultEnabled` 必须为 `true`。
- 新安装、清空桌面偏好以及从未操作过插件开关的客户端，启动后应立即注册 `/kanban` 页面和 sidebar 的看板入口。
- 设置中的插件开关继续保留；用户明确关闭看板后，`hermes.desktop.pluginDecisions.v2` 中的显式 `false` 优先于默认值，后续升级不得强制改回开启。
- 不需要为历史默认值做全量迁移：插件存储只记录用户主动选择，缺少决定时会自动采用新的 `defaultEnabled: true`。若未来存储实现改变，必须重新验证这一前提。
- 回归测试必须直接断言内置看板插件的 `id` 为 `kanban` 且 `defaultEnabled` 为 `true`，避免上游合并恢复为 opt-in。

### 桌面壳辅助控件隐藏

AgentOS 桌面壳要更像业务客户端，少暴露原始开发者 chrome。以下截图标注类控件默认不展示：

- 左上 titlebar 的 `flip-panes` / `arrow-swap`，即交换 sidebar 两侧按钮。
- 右上 titlebar 的快捷键面板按钮、设置齿轮、右侧栏按钮。
- `New session` 行尾的 `⌘ N` 快捷键提示 chip。
- Gateway 状态弹层里的 `Recent activity` 日志尾巴和 `View all logs`。
- 底部 statusbar 的 client/backend version pill，例如 `client v0.20.5 (+51)`、`backend ...`。

仍保留：

- 左上 sidebar 显隐按钮。
- 右上静音/触觉反馈按钮。
- 文件浏览面板标题栏自身的隐藏按钮；该按钮使用 `layout-sidebar-*-off` 图标并调用统一的
  `hideFileBrowserPane()`。默认布局中必须折叠右侧文件栏；文件栏被拖到其他区域后只关闭该面板，
  不能误折叠无关区域。原 `collapse-all` 图标不得占用这个位置冒充面板隐藏。
- 底部设置、网关和工作区等必要状态入口。
- 左侧导航中的子智能体、定时任务入口及其完整功能页面；这里只移除底部 statusbar 的重复入口。
- 设置页、命令中心、日志页面本身；只是不要从截图标注的 titlebar/statusbar 位置暴露。

关键文件：

- `apps/desktop/src/app/shell/titlebar-controls.tsx`
- `apps/desktop/src/app/right-sidebar/index.tsx`
- `apps/desktop/src/store/layout.ts`
- `apps/desktop/src/app/shell/app-shell.tsx`
- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`
- `apps/desktop/src/store/statusbar-prefs.ts`
- `apps/desktop/src/app/shell/statusbar-visibility.test.tsx`
- `apps/desktop/src/app/shell/gateway-menu-panel.tsx`
- `apps/desktop/src/app/chat/sidebar/index.tsx`

迁移规则：

- 不要新增一堆 feature flag；当前 AgentOS 目标就是默认隐藏这些控件。
- 删除渲染入口比 CSS 隐藏更好，避免保留可点击但不可见的区域。
- 如果隐藏右上系统工具，要同步调整 `AppShell` 里 titlebar tool cluster 的宽度估算，避免拖拽区域空出过宽。
- 快捷键本身可以继续生效，但不要在 sidebar row 里展示快捷键 chip。
- 上游新版可能把 `$statusbarVisible` 默认值设为 `false`。合并时必须覆盖这一行为，AgentOS 状态栏默认展示。
- statusbar item 注册表不得包含 `id: 'agents'` 或 `id: 'cron'`，不要通过 CSS 或默认隐藏偏好伪装删除；这样上下文菜单中也不会出现这两个重复入口，也不会继续订阅子智能体计数。
- `persistentAtom` 在模块初始化时会立即把 fallback 写入 `localStorage`。如果“整条状态栏默认隐藏”的错误值已经随安装包发布，必须通过一次性偏好版本迁移恢复为显示；迁移应保留用户对各状态项的显隐选择，不能在每次启动时反复覆盖用户后续操作。
- `STATUSBAR_HIDDEN_BY_DEFAULT` 无需加入已经不注册的 `agents`、`cron`，偏好迁移也不得再把这两个不存在的 item 当作必显项特殊处理。
- 回归测试至少断言：首次启动状态栏可见；设置、网关和工作区项正常渲染；`agents`、`cron` 不注册；终端、审批模式等次要控件仍按产品默认隐藏。

### 内置终端暂时关闭

AgentOS 当前不向最终用户提供 desktop 内置终端。这里关闭的是 Electron 右下角的交互式
xterm/PTY 面板，不是智能体执行任务所需的后端 `terminal` 工具；不能为了隐藏客户端面板而删除
Python terminal tool、执行后端配置或原生依赖打包。

统一产品开关为：

```ts
// apps/desktop/src/lib/product-features.ts
export const IN_APP_TERMINAL_ENABLED = false
```

所有可见入口和隐式恢复路径都必须服从该开关：

- `panes` contribution 不注册 `terminal`，默认/Focus 布局不包含终端轨道；`Terminal deck`、
  `Quad` 等依赖终端的布局预设不注册。
- 启动时通过 `removeTreePane('terminal')` 清理旧安装保存在 layout tree 中的终端轨道，避免升级后
  右下角残留空白区域。这里不能写 dismissal marker；未来重新开启开关后，默认布局应能重新 adopt。
- 不挂载 `PersistentTerminal`，不创建 xterm host，也不让已保存的 `$terminalTakeover=true`
  触发可见面板。
- statusbar 不注册 terminal item；不能只放进 `STATUSBAR_HIDDEN_BY_DEFAULT`，否则右键自定义菜单里
  仍能找到并重新显示它。
- 命令面板不注册 `view.showTerminal`，快捷键目录不暴露 show/new/next/previous/close terminal；旧版本
  保存的终端快捷键由 keybind action catalog 自动丢弃。
- `view.toggleRightSidebar` 只控制文件栏，不得在不存在右侧区域时 fallback 到 terminal。
- backend `focus_pane("terminal")` 返回不支持，不能绕过界面策略把终端唤起。
- 外观设置不展示“终端字体”；外部 provider 也不展示“在内置终端执行解绑命令”的入口。
- 底层 terminal toolset、`terminal.backend` 等智能体执行配置、`node-pty` 打包代码暂时保留。它们与
  desktop 交互面板不是同一产品能力。

关键文件：

- `apps/desktop/src/lib/product-features.ts`
- `apps/desktop/src/app/contrib/controller.tsx`
- `apps/desktop/src/app/contrib/wiring.tsx`
- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`
- `apps/desktop/src/lib/keybinds/actions.ts`
- `apps/desktop/src/app/hooks/use-keybinds.ts`
- `apps/desktop/src/store/pane-focus.ts`
- `apps/desktop/src/app/settings/appearance-settings.tsx`
- `apps/desktop/src/app/settings/providers-settings.tsx`

回归验收：全新启动和从曾经打开终端的旧版本升级后，右下区域均不得出现 `TERMINAL`、终端 tab、
新建终端按钮或空白轨道；状态栏菜单、命令面板、快捷键设置中搜索“终端/terminal”也不得出现
内置终端动作。模型仍应能正常调用后端 `terminal` 工具执行任务。

### 状态栏入口唯一性和聊天输入框宽度

相关文件：

- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`
- `apps/desktop/src/plugins/`
- `apps/desktop/src/store/composer-popout.ts`
- `apps/desktop/src/styles.css`

规范：

- 状态栏最左侧固定显示 `设置`，使用设置图标，点击进入 `/settings`。该入口在本地、SSH、Cloud 和远程 BFF 模式下都必须存在且不可被隐藏。
- 状态栏不得显示 `远程: IP:端口`、SSH host 或 Cloud host。连接地址属于敏感部署信息，只能在设置页的网关配置中查看和修改。
- 网关状态只保留核心 `gateway-health` 一处；禁止再在右侧注册第二个网关状态项。
- 底部状态栏不注册 `agents` 和 `cron`，避免与左侧“子智能体”“定时任务”导航重复；不得影响对应页面、路由、侧栏入口或底层能力。
- `apps/desktop/src/plugins/gateway-pill/plugin.tsx` 是上游演示插件，不得进入 AgentOS 源码或安装包。必须删除插件注册源，不能仅用 CSS 隐藏，否则它仍会轮询状态、出现在插件清单并占用运行资源。
- 主聊天输入框默认保持 docked；用户主动拖出后的浮动输入框目标宽度为 `56rem`，在宽屏中接近所属聊天内容区宽度，不得退回上游过窄的 `19.5rem` 或旧 AgentOS 的 `26rem`。
- 浮动宽度必须由 `composerPopoutWidthPx()` 按所属聊天区域计算：目标使用共享的 `POPOUT_WIDTH_REM`，区域不足时预留两侧各 `8px` 后自动收缩。渲染、首次拖出、恢复和 `clampPopoutPosition()` 必须复用该结果，避免小窗口、分屏或侧栏打开时越界。

验收：

1. 远程连接后，最左侧只显示 `设置`，不出现远程 IP；点击后打开设置弹层。
2. 整条状态栏只出现一个 `网关` 文案，且右侧不存在 `gateway-pill`。
3. 检查插件管理页，不存在随安装包内置的 Gateway Pill。
4. 将输入框拖到浮动模式，确认宽屏目标宽度为 `56rem`；窗口缩小或拆分聊天区后，宽度自动收缩且仍完整位于所属聊天区域内。

### Command Center 系统页

Command Center 的系统页只保留状态和操作：

- 显示网关运行状态。
- 显示 active session 数。
- 保留 `重启网关` 和 `更新 AgentOS` 按钮。Desktop 按钮只能启动租户 AgentOS 安装包更新，不得调用、轮询或向用户暴露服务端兼容路由 `/api/hermes/update*`，也不得显示 Hermes/Nous 品牌。
- statusbar 网关弹窗里必须有 `退出登录` 按钮，复用 desktop auth IPC，不要只把退出入口藏在设置页。
- 如果系统操作失败，显示一行错误文本。
- 不展示最近日志区域。
- 不展示 `agent/errors/gateway/desktop` tab。
- 不展示 `all/info/warning/error` tab。
- 不展示日志搜索框。
- 不渲染 `LogTail`。
- `refreshSystem` 只调用 `getStatus()`，不要再调用 `getLogs()`。

### Gateway menu

相关文件：

- `apps/desktop/src/app/shell/gateway-menu-panel.tsx`
- `apps/desktop/src/app/shell/hooks/use-status-snapshot.ts`
- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`
- `apps/desktop/src/i18n/zh.ts`

规范：

- 状态栏显示 AgentOS gateway 状态。
- gateway stopped/running/restarting/checking/connecting/offline 等状态要中文。
- 中文 statusbar 中 `Gateway ready` 显示为 `网关` + `已就绪`；statusbar 不显示 `Agents` / `子智能体` 或 `Cron` / `定时任务`。左侧导航和对应功能页继续使用“子智能体”“定时任务”，不得机翻为“代理”“排程”。
- gateway restart failed 需要 toast。
- 消息平台可以从 gateway status/menu 打开；定时任务通过左侧导航进入，不在 statusbar 重复提供入口。
- Gateway 状态弹层只显示连接状态、推理状态和消息平台状态；不要内嵌最近日志 tail。

### 已归档对话入口和恢复

已归档对话属于高频会话管理能力，不应只藏在设置左侧导航中。入口统一放在窗口最底部左侧的 Gateway 状态弹窗：

- 点击左下角 statusbar 的 `网关` / Gateway 状态项，打开 `GatewayMenuPanel`。
- 弹窗操作区至少包含 `已归档对话` 和 `退出登录`；连接、推理及消息平台状态继续保留。
- `已归档对话` 使用归档图标。点击时先关闭 Gateway 弹窗，再进入 `/settings?tab=sessions` 对应的归档会话视图。
- sidebar 右下角省略号保持原职责：直接进入“管理配置档案”，不要在这里放归档入口。
- 设置左侧导航不再重复展示“已归档对话”；但 `tab=sessions` 继续保留，兼容旧书签、Command Center 深链和历史版本入口。
- 归档视图通过 `listAllProfileSessions(limit, offset, 'only')` 查询，必须覆盖所有 profile，不能只查当前 profile。
- 归档动作只把原会话的 `archived` 更新为 `true`，普通会话列表立即隐藏该行；不得删除消息或新建替代会话。
- 恢复动作必须对同一个 `session.id` 调用 `setSessionArchived(id, false, profile)`，并解除对应 `id`、`_lineage_root_id` 的 optimistic tombstone。
- 恢复后把同一会话对象重新放回 `$sessions`，归档列表移除该行，普通 sidebar 可立即找到该会话，不必等待完整刷新。
- 恢复过程不得改写标题、消息正文、消息数量、消息顺序、profile、cwd 或 lineage；重新打开时仍由原 session ID 向后端读取历史消息。
- 取消归档失败时保留归档列表行并显示错误提示，不能出现“两边都没有”的状态。

关键文件：

- `apps/desktop/src/app/shell/gateway-menu-panel.tsx`
- `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`
- `apps/desktop/src/app/settings/index.tsx`
- `apps/desktop/src/app/settings/sessions-settings.tsx`
- `apps/desktop/src/app/session/hooks/use-session-actions/index.ts`
- `apps/desktop/src/hermes.ts`

自动化验收：

1. 创建或选取一个含多轮消息的会话，记录 session ID、标题、消息数量和最后一条消息。
2. 归档后确认普通 sidebar 不再显示，后端仍能以 `archived=only` 查询到同一 ID。
3. 点击左下角 `网关` 状态项，在弹窗中确认存在“已归档对话”，点击后弹窗关闭并进入 `tab=sessions`。
4. 对该行执行取消归档，确认调用参数为原 ID、`false` 和原 profile。
5. 确认归档列表移除、普通 sidebar 恢复同一会话；重新打开后消息数量、内容和顺序与归档前一致。

### Prompt overlays

文件：

- `apps/desktop/src/components/prompt-overlays.tsx`

包含：

- sudo password dialog。
- secret capture dialog。
- dangerous command / execute_code approval fallback。

重要规则：

- 关闭 sudo 弹窗等价于拒绝，发送空 password。
- submit 成功后 clear request。
- submit 失败且错误包含 `no pending`，也 clear request。
- cancel 时先 dismiss UI，再 best-effort respond 空 password。
- 不要加额外 Escape/outside handlers，避免双 respond。

## 9. 产物和导航文案

相关 i18n：

- `artifacts`
- `commandCenter.nav.artifacts`

新增文案：

- `download`
- `downloadAll`
- `downloadStarted`
- `downloadFailed`
- `sessionFilesTitle`
- `sessionFilesDesc`

语义：

- `sessionFilesTitle` 中文为 `本会话文件`。
- 描述说明从远程工作区下载本次会话生成文件。

## 10. 回归测试点

定时任务：

- `scheduleFromControls` 各 preset。
- `scheduleOptionForExpr` 识别已有 cron。
- 输入越界 clamp。
- 中文 prompt 标题生成。
- 英文 prompt 标题生成。
- 空 prompt fallback。
- 编辑任务回填控件。
- run history poll。

消息平台：

- 平台筛选只保留五类。
- 后端同时返回 Telegram/Discord 等海外平台时，DOM 中不得出现这些平台。
- 显示顺序固定为钉钉、飞书、企业微信、微信、QQ，不依赖后端 catalog 顺序。
- `wecom_callback` 优先。
- `wecom_callback` 和 `wecom` 同时返回时只显示“企业微信（应用）”。
- 顶部 description 取 `platformDescription` 中文映射，不显示后端英文。
- 任取一个后端英文 env schema，label/help/placeholder 都必须显示中文。
- 本地图标路径 base URL 正确。
- enable/save/clear 调 update API 正确。
- toast 包含 restart action。

登录页：

- 空用户名/密码禁用提交。
- busy 防重复。
- error wrapper 剥离。
- HTML 错误归一。
- network/timeout 中文提示。

prompt overlays：

- close -> empty sudo respond。
- `no pending` 清理 stale request。
- gateway disconnected 提示。
- 不双 respond。

slash commands：

- built-in curated。
- skill/quick command 仍能 suggestion。
- skill command dispatch 后作为普通 prompt 提交。

desktop chrome：

- 不显示 titlebar `flip-panes`、快捷键、设置、右侧栏按钮。
- 不显示 `New session` 的 `⌘ N` 提示。
- Gateway 状态弹层不显示 `Recent activity` 日志区域。
- statusbar 不显示 client/backend version pill。
- statusbar 不显示 `子智能体`、`定时任务` 两个重复入口；左侧导航中的对应入口仍保留。
- 左下角 Gateway 状态弹窗可直接进入“已归档对话”；右下角省略号仍只负责管理配置档案。
- 归档后普通列表隐藏，取消归档后恢复同一 session ID，历史消息内容和顺序不变。

## 11. 创建智能体与配置档案的名称契约

服务端的 profile 名称既是用户可见标识，也是目录名和运行时路由键。客户端不能只校验字符格式后把必然失败的名称交给服务端。

固定规则：

- 内部名称只允许小写英文字母、数字、连字符和下划线，长度为 1 至 64，首字符必须是字母或数字。
- `default`、`hermes`、`test`、`tmp`、`root`、`sudo` 是服务端保留名；核心“新建配置档案”和 BOTS `New Agent` 两个入口都必须在发起 `profiles.create` 前拦截。
- 保留名提示必须显示当前输入和可直接使用的替代名称，例如 `test-agent`；创建按钮必须保持禁用，不能先请求服务端再显示异常。
- BOTS 的中文展示名称填写在 `Title`，内部 `Name` 仍使用 ASCII slug；纯中文 Name 要明确提示用户使用 Title，不能静默生成空名称。
- 服务端校验是最终防线。若以后服务端新增保留名，客户端捕获到 `reserved` 类异常时仍要转成产品提示，并剥离 Electron IPC 包装和 `Hermes` 旧品牌字样。
- 修改任一创建入口时，必须同步另一入口、`apps/desktop/src/i18n/types.ts` 与五个 locale，不能让两套创建界面再次漂移。

关键文件：

- `apps/desktop/src/app/profiles/create-profile-dialog.tsx`
- `apps/desktop/src/plugins/hermes-bots/plugin.js`
- `apps/desktop/src/app/profiles/create-profile-dialog.test.tsx`
- `apps/desktop/src/plugins/hermes-bots/tests/create-agent-clone-default.test.mjs`

自动化验收：

1. 逐一输入六个保留名，确认创建按钮禁用且 `profiles.create` 未调用。
2. 输入 `work-agent`，确认仍可创建，避免把合法名称误判为保留名。
3. 输入纯中文 Name，确认提示将中文名称填写到 Title。
4. 模拟服务端返回带 IPC 包装的保留名异常，确认界面不出现 `Error invoking remote method`、`Hermes` 或原始英文堆栈。
