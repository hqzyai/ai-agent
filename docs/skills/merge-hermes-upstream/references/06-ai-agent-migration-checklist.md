# AI Coding 智能体迁移执行清单

本文面向后续 Codex、Cursor 等 AI coding 智能体。目标是把初始 `main` 基线和后续产品分支已经验证的 AgentOS desktop 改造迁移到新的 desktop 实现时，按正确顺序做，不漏关键契约。

## 1. 开工前先确认范围

必须确认：

- 目标分支是什么。
- 是否只迁移 `apps/desktop`。
- 是否需要同步 `tui_gateway` API。
- 是否需要同步 `web` dashboard API。
- BFF 生产地址如何注入。
- 是否保留 local gateway 模式。
- 是否保留 legacy token mode。
- 是否继续使用 Electron。

如果用户没有额外说明，默认迁移 `00-README.md` 标注的当前审计基线行为：

- AgentOS 品牌。
- BFF 账号密码登录。
- hosted gateway cookie + ws-ticket。
- locked remote gateway settings。
- remote file/media/artifacts。
- cron 时间选择 UI，自定义只用时间选择，不暴露 cron 语法。
- AgentOS 消息平台筛选和汉化。
- 精简桌面壳 chrome：隐藏截图标注的开发者/快捷入口和版本噪声。
- offline bundled agent installer。
- bundled installer + native deps resources。
- CI 三平台构建。

## 2. 建议迁移顺序

### 阶段 1：建立配置和品牌基础

迁移：

- `apps/desktop/config/defaults.json`
- `apps/desktop/src/config/defaults.ts`
- AgentOS icon assets：不要只换 `assets/icon.png`，要同时更新 `assets/icon.icns`、`assets/icon.ico`、`public/apple-touch-icon.png`；如果临时验证已打包 release，还要覆盖 `.app/Contents/Resources/icon.icns`、`.app/Contents/Resources/icon.ico` 和 unpacked dist 里的图标副本。
- `BrandMark` 使用：登录页、安装页、更新页、关于页统一引用 `apple-touch-icon.png`；兼容保留的 `nous-girl.jpg` 文件内容也必须替换成 AgentOS icon，不能继续保留旧头像。
- `index.html` title/favicon。
- i18n `types.ts` 中新增 section/key。
- `zh.ts`、`en.ts` 文案。
- agent/system prompt 身份：`agent/prompt_builder.py`、`hermes_cli/default_soul.py`、TUI/WebUI branding 也要迁移，不能只改 desktop renderer。

验收：

- app 打开后，空会话欢迎区的大字 wordmark 显示 `AGENT OS`；安装包名、可执行文件名、协议名和内部兼容标识仍使用 `AgentOS`。
- “技能与工具”完整页面把“专家技能”放在“技能”之前并作为默认页签，按 `差旅报销`、`项目研判`、`投资合同审核`、`文书起草` 的固定顺序显示可搜索专家卡片；空会话欢迎区不再重复显示四个入口。点击卡片必须新建主会话，再用 `replace/main` 生成可编辑的 `/<skill> <实例提示词>` 草稿，不自动发送、不请求 backend；Bot Mode 等嵌入式能力配置面不显示专家页签。
- 专业技能斜杠模板中的 `【...】` 在主 composer 内显示为可编辑的待填写字段；纯文本序列化和发送内容保持中文方括号原文，普通 JSON/代码大括号不误高亮。差旅报销模板含且仅含四个中文方括号字段，项目研判模板含且仅含两个中文方括号字段，不得回退为半角大括号 `{}`。
- 主空会话 composer 的输入引导必须固定为 `今天帮你做些什么? /调用技能与指令`，不得随机轮换旧文案；历史会话继续使用 follow-up 文案。
- 登录页显示中文 AgentOS。
- 登录页头像、Dock 图标、窗口图标、favicon、打包后的 macOS/Windows app icon 都使用 `BRAND_ASSETS_DIR` 中同一源图派生的素材。
- 新建会话问 `你好 你是谁`，模型回答必须自称 AgentOS，不得自称 `Hermes Agent` 或 `Nous Research`。
- 系统提示默认要求所有用户可见内容使用简体中文；若展示思考/推理摘要、进度说明或工具说明，也必须使用简体中文，正文回复同样如此。用户本轮明确指定其他语言时按本轮要求。
- 默认 `SOUL.md` 必须是 AgentOS 身份；旧默认 `You are Hermes Agent...` 必须被 `is_legacy_template_soul()` 识别并升级，自定义 persona 不得被覆盖。
- 身份提示必须在 `SOUL.md`/默认身份之后追加 AgentOS 身份护栏：用户问身份或产品名时只回答 AgentOS，不提底层运行时、组织、供应商或上游项目。旧默认 persona 的迁移和身份护栏都属于 Hermes server/backend 逻辑，不能只在 desktop renderer 替换回答文本。
- dashboard/WebUI sidebar、TUI 启动画面、TUI response label、默认主题名必须显示 AgentOS；`Hermes Teal` 必须改为 `AgentOS Teal`。
- `rg -n "nous-girl" apps/desktop/src apps/desktop/electron apps/desktop/index.html apps/desktop/DESIGN.md` 无代码/设计说明引用；`public/dist/release` 中如果仍有同名兼容文件，hash/视觉内容必须是新 AgentOS icon。
- 设置页和 sidebar 不出现用户可见 Hermes 内部词。
- titlebar 不显示 `flip-panes`、快捷键面板、设置齿轮、右侧栏按钮。
- 文件浏览面板标题栏保留独立隐藏按钮，点击必须立即折叠当前文件栏；不得继续绑定“折叠所有文件夹”。
- `IN_APP_TERMINAL_ENABLED` 保持 `false`；右下角不显示内置终端、终端 tab 或旧布局残留的空轨道。
- terminal pane、PersistentTerminal、statusbar、命令面板、快捷键设置、终端字体设置和 provider 解绑入口都不得绕过产品开关重新暴露终端。
- 升级时从 layout tree 移除旧 `terminal` pane，但不写 dismissal marker；后端 terminal toolset、`terminal.backend` 和打包依赖继续保留。
- `New session` 行不显示 `⌘ N` 快捷键 chip。
- statusbar 不显示 client/backend version pill。
- gateway status popover 不显示 recent logs tail。
- Command Center 系统页不展示最近日志、日志类型 tab、日志级别 tab、日志搜索框或 `LogTail`。
- 中文 statusbar 显示 `网关` + `已就绪`，不注册 `agents` / `cron`，因此底部不显示 `子智能体`、`定时任务`、`Agents`、`Cron`、`代理` 或 `排程`；左侧导航中的“子智能体”“定时任务”仍保留。
- 检查 `store/statusbar-prefs.ts`：状态栏默认可见；偏好迁移只修复整条状态栏的错误默认值并保留 item 选择，不再把已移除的 `agents` / `cron` 当作必显项。
- 检查内置看板插件 `plugins/kanban/plugin.tsx`：`defaultEnabled: true`；首次启动默认显示看板，用户在设置中明确关闭后的显式决定仍应保留。

### 阶段 1.1：重新应用 bundled plugins

迁移：

- 从显式 `ai-agent` checkout 校验 `config/bundled-plugins.lock.json`。
- 语义合并 `apps/desktop/src/plugins/channels`，保持插件 id 为 `channels`、route 为 `/channels`。
- 语义合并 `plugins/image_gen/qwenai`、`plugins/video_gen/qwenai`、`plugins/web/openserp`。
- 对 `patches/bundled-plugins/channels/hermes-channels-integration.patch` 运行 `git apply --check`；不兼容时按新上游结构重实现，禁止强制应用或跳过。

验收：

- `python3 "$AI_AGENT_ROOT/scripts/validate_bundled_plugins.py" "$AI_AGENT_ROOT/config/bundled-plugins.lock.json"` 通过。
- Desktop lint/typecheck/build 通过，插件只注册一次 `/channels`，三种 QR onboarding 的 start/status/apply/cancel、过期和失败路径都有行为测试。
- Backend plugin manifests、缺失 env、安全日志、Qwen 图片/视频与 OpenSERP provider tests 通过。
- 三端 Desktop 包和两种架构镜像均包含锁定插件；新装、N-1 升级、显式启停、回滚和 `{APP_DATA_DIR}/profiles/{ORG_NAME}` 数据保持通过。

### 阶段 2：接入 BFF 登录

迁移：

- `login-screen.tsx`
- preload `auth` bridge。
- 重启认证恢复必须先用持久化 OAuth cookie 调 BFF 轻量
  `/desktop/hosted-gateway/api/auth/session`；该接口只验证/轮换 AT、RT，禁止调用
  `get_dashboard_endpoint_async()` 或等待运行实例。只有明确 401/403 或 cookie 缺失才
  使用安全存储中的账号密码，timeout/DNS/连接拒绝/5xx 必须保留 session 并交给连接层。
- 自动认证的瞬时失败不能持久化 `manualLoginRequired:true`；明确退出登录和未完成的手动登录仍必须设置该标记，防止退出后被自动登录回来。
- 有效 AT/RT 重启用例必须验证：不出现登录页、不调用密码登录、恢复后可发送消息、配置和日志无明文 Access Token、Refresh Token 或密码。
- main process auth IPC。
- `auth-errors.cjs`。
- `safeStorage` 加密密码。
- `auth.json` 读写。
- BFF `/auth/login` 调用。
- hosted gateway cookie 安装。
- `verifyDesktopHostedGatewaySession` + BFF 轻量 session endpoint。
- 运行时就绪移到连接阶段：BFF `ws-ticket` 可以等待 runtime ready；Desktop 初次 ticket
  请求使用一个覆盖服务端冷启动/修复预算的长超时，禁止 8 秒超时循环重试。
- `getDesktopAuthState` 必须 single-flight；窗口预启动与 renderer 的 auth IPC 并发时
  只允许一次 session 验证/密码登录。
- 登录页默认选中账号密码；飞书扫码只在用户显式切换后调用
  `auth.login({ method:'feishu' })`。扫码窗口必须复用持久化 OAuth partition，只允许已绑定
  AgentOS 的飞书账号，成功后清空旧保存密码并复用同一 hosted gateway/ws-ticket 链路。
- 登录页必须读取 BFF `GET /auth/login-options`：只有 `oidc_enabled:true` 且
  `default_tenant_configured:true` 才展示飞书扫码；BFF 未启用 OIDC、未配置默认租户、接口失败或
  响应不合法时隐藏飞书并保留账号密码。main process 必须在扫码 IPC 中重复校验，不能只靠 UI。
- 手动密码提交失败不得覆盖上一次已验证的安全存储密码；新密码只在 BFF 登录成功后落盘。

验收：

- 正确账号登录后进入 chat。
- 错误账号显示 `用户名或密码错误。`
- `invalid refresh token`、`session expired` 和非密码接口的普通 401 显示
  `登录已过期，请重新登录。`，不得按状态码误报为密码错误；普通 403 显示服务端拒绝。
- 飞书扫码成功可进入 chat；关闭扫码窗口、OIDC 失败或账号未绑定时在原登录页显示中文
  错误，不启动 backend、不暴露 token，也不自动回退旧账号密码。
- BFF 返回 HTML 不直接显示 HTML。
- BFF 登录成功后立即进入已认证状态；ticket/WS 失败按连接故障展示并重试，不得清除
  有效 cookie 或重复密码登录。只有明确 401/403 才回登录页。
- BFF 从 `/proxy/8642` 派生 dashboard `/proxy/9119` 时，必须从 OpenSandbox endpoint detail 继承 `OpenSandbox-Secure-Access` 等 headers；不能只改路径并丢掉安全访问头。
- `instance.status=ready`、runtime lazy-start 200、公开 `/api/status` 200 都不能替代 hosted gateway `/api/sessions` 与 `/api/ws` 的真实代理验收。
- 重启 app 后可自动登录；轻量认证不能被实例冷启动时间拖住。
- `createWindow`/`did-finish-load` 不得无条件启动 backend；Electron 预启动和 renderer
  必须共享同一个 auth single-flight，认证成功后才可连接。
- 退出登录后回登录页。
- 账号切换必须隔离旧 backend 生命周期：退出、登录、profile 切换和重试都推进
  primary backend generation；旧 child 的晚到 `exit/error` 事件和旧启动 Promise
  不得清空新账号的 `connectionPromise`、覆盖 `backendStartFailure`、发送错误弹窗
  或把连接切回 local backend。
- `startHermes()` 的关键异步阶段必须检查 generation；child 回调必须同时检查
  generation 和 child identity。不能用固定 sleep、二次点击“重试”或整页 reload
  作为竞态修复。
- 自动化覆盖“账号 A 退出 -> 账号 B 首次登录”以及延迟旧 child 退出事件的场景；
  首次连接就成功，不能出现“先远程 ready、随后启动旧本地 Python、点击重试才恢复”。

### 阶段 3：接入 remote gateway REST/WS

迁移：

- OAuth session partition。
- `fetchJsonViaOauthSession`。
- `mintGatewayWsTicket`。
- `freshGatewayWsUrl(profile)`。
- preload `getGatewayWsUrl`。
- renderer gateway connect 前 fresh 获取 wsUrl。
- `revalidateConnection`。
- `isGatewayReauthRequired` 同时识别 error class、自定义标记和 Electron IPC 序列化后的明确过期消息。
- 首次连接或重连遇到真实会话过期时，gateway hook 停止重连并请求顶层认证刷新；使用保存凭据自动换新 token，失败则停在登录页。
- 禁止从 gateway hook 直接调用 `window.location.reload()`；否则未变化的认证状态会制造失败页与白屏之间的无限循环。
- `fetchJsonViaOauthSession` 同时监听 Electron request 和 response 的 `error`；response body 读取不得只监听 `data/end`。

验收：

- 第一次连接成功。
- 断线重连成功。
- 第二次连接不复用旧 ticket。
- refresh token 仍有效时不强制登录。
- refresh token 无效或服务端会话丢失时，不停留在普通启动失败页，也不无限重试旧 cookie；同一登录生命周期最多自动重新认证一次。
- auth refresh 期间卸载连接 UI 并显示稳定 loader；自动认证失败时切换登录页。自动认证即使返回成功，只要重新挂载后的 gateway 仍报告认证过期，第二次 auth refresh 必须直接停在登录页，不能再次调用自动认证。用户手动登录成功后才重置自动恢复额度，renderer 全程不整页 reload。
- timeout、DNS、连接拒绝、5xx 不得误判为 token 过期。
- BFF session endpoint 单测必须断言不会调用 runtime endpoint resolver；Desktop 并发
  auth status 单测必须断言只执行一次底层恢复流程。
- 截断响应或错误 `Content-Length` 触发 `ERR_CONTENT_LENGTH_MISMATCH` 时，只让当前请求失败并进入重试，不弹主进程 JavaScript 错误框。
- `/api/status` 通过但 WS 失败时，connection test 能给出 WS 失败原因。

### 阶段 4：迁移 profile/session 远程路由

迁移：

- connection config `profiles` schema。
- `sanitizeConnectionProfiles`。
- `profileRemoteOverride` 相关逻辑。
- `interceptSessionRequestForRemote`。
- `globalRemoteSessionList`。
- `remoteSessionList`。
- `mergeRemoteProfileSessions`。
- `pathWithGlobalRemoteProfile`。
- `SessionDB._execute_write()` 的 `SQLITE_READONLY` 可写连接单次重建。
- `session.resume` 只恢复会话和注册 runtime，不预构建完整 AIAgent；首次真正 agent 操作再按需构建。
- `/api/config`、`/api/model/options` 使用 config-only profile scope，不能在 DNS/HTTP 模型发现期间持有进程级 skills 锁。
- `models_dev.auto_refresh` 配置和模型目录短时 single-flight/cache。

验收：

- global remote mode sidebar 有 session。
- `/api/profiles/sessions` 空时 fallback `/api/sessions`。
- session row 有 profile。
- 打开历史 session 读远端 messages。
- rename/archive/delete 作用于远端。
- per-profile remote 不污染 primary profile。
- 左下角 Gateway 状态弹窗包含“已归档对话”，点击后先关闭弹窗再进入 `tab=sessions`；设置左侧导航不重复展示该入口，右下角省略号仍进入配置档案管理。
- 状态栏最左侧固定为“设置”并进入 `/settings`，任何连接模式都不展示远程 IP/host；全栏只允许核心 `gateway-health` 一个网关状态项，禁止打包 `plugins/gateway-pill` 演示插件。
- 浮动聊天输入框使用共享的 `POPOUT_WIDTH_REM = 56` 作为宽屏目标，并由 `composerPopoutWidthPx()` 按所属聊天区域自动收缩；渲染、首次拖出、恢复和边界计算必须一致，分屏、小窗口和侧栏场景不得越出所属聊天区域。
- 归档列表使用 `archived=only` 查询全部 profile；取消归档复用原 session ID 和 profile，不创建新会话。
- 恢复后同一会话重新进入普通列表，标题、消息数量、消息正文和消息顺序均不改变。
- 打开历史会话后 `/api/status`、WebSocket 心跳和 hosted gateway 健康检查保持响应；不得因后台 AIAgent 预热阻塞数分钟。
- 可写 `SessionDB` 的失效只读连接可以重建一次；真正的 `read_only=True` 实例仍拒绝写入，不能被升级成写连接。
- 受限网络 profile 设置 `models_dev.auto_refresh: false` 后直接使用磁盘快照，不发公共 DNS/HTTP；同一 profile 的并发 `/api/model/options?refresh=false` 合并为一次构建，显式 `refresh=true` 不复用结果。

### 阶段 5：迁移聊天展示和工具行

迁移：

- `chat-messages.ts`
- `chat-runtime.ts`
- `tool-fallback-model.ts`
- `tool-fallback.tsx`
- `summarize-command.ts`
- `markdown-text.tsx` 中 media link 处理。

### 阶段 5.1：模型请求关联当前会话

迁移：

- 所有可添加 HTTP header 的模型请求，在真正调用 provider SDK 前合并精确键名
  `HERMES_SESSION_ID`，值为当前持久会话的 `AIAgent.session_id`。同时发送值完全相同的
  `X-LiteLLM-Session-ID` 兼容头，使 AI Gateway 将会话写入 LiteLLM
  `metadata.session_id`、用量回调 `runtime_session_id` 和链路追踪；不能只发送裸
  `HERMES_SESSION_ID`，因为 LiteLLM 不会把它识别为会话元数据。
- 主回复的流式/非流式请求、provider 重试和 fallback、达到最大迭代后的总结请求，
  都必须走同一注入逻辑；不能只覆盖 OpenAI Chat Completions 首次调用。
- 标题生成、上下文压缩、评审等辅助模型请求没有直接持有 `AIAgent` 时，从
  `gateway.session_context` 的 task-local `HERMES_SESSION_ID` 读取；禁止从共享全局变量
  推断，否则并发会话会串号。
- 合并时保留鉴权、Copilot、Codex、Grok、Anthropic beta 和自定义路由 header；已有任意
  大小写的 `hermes_session_id`、旧 `session_id` 或 `x-litellm-session-id` 必须由当前运行时
  值覆盖，最终只发送精确键名 `HERMES_SESSION_ID` 和 `X-LiteLLM-Session-ID`，且两者值
  必须一致。旧 `SESSION_ID` 只允许作为升级兼容输入读取，进入 provider transport 前必须
  删除，禁止同时发送新旧两个主键。
- Gemini native REST 适配器必须把 SDK 风格的 `extra_headers` 同时传给普通请求和 SSE
  流式请求。
- Relay 等请求中间层可能追加或改写 provider headers；必须在 provider callback 的最后边界
  再次以进入中间层前的当前会话值规范化 `HERMES_SESSION_ID`。Codex Responses 与 Anthropic 的辅助
  适配器也必须继续向各自原生 SDK 转发 `extra_headers`，不能只在 chat 风格入口接收后丢弃。
- `bedrock_converse` 使用 AWS SDK/SigV4，`codex_app_server` 使用本地子进程协议；两者不
  接受 OpenAI 风格的 `extra_headers`，不得强行注入。若未来需要关联，必须使用各自协议
  原生支持的元数据通道。
- `HERMES_SESSION_ID` 是链路关联标识而非认证凭据，不得替代 token/cookie；仍需拒绝 CR/LF，
  防止 header 注入，也不得在普通用户界面展示。
- LiteLLM 返回 `Rate limit exceeded for api_key` 或 `budget has been exceeded` 时必须先脱敏：
  不回显 key，不按单密钥 rate limit 轮换 credential/fallback。可解析的 UTC reset 时间转为
  `Asia/Shanghai` 中文时间；解析失败显示通用中文超预算提示。

模型请求关联验收：

- 同一会话的主调用、重试、迭代总结和辅助调用抓包均包含同一个 `HERMES_SESSION_ID`，以及
  与它值完全相同的 `X-LiteLLM-Session-ID`；AI Gateway 内部解析结果必须等于该会话 ID。
- 两个并发会话分别触发压缩或标题生成时，各自 header 始终等于所属会话 ID。
- 自定义 `extra_headers` 和 provider 专用 header 保留，所有会话 header 变体均被规范化，
  抓包中不得出现旧 `SESSION_ID`。
- Bedrock 与 Codex app-server 调用不出现不支持参数错误。
- 执行 `pytest -q tests/agent/test_model_request_headers.py tests/agent/test_gemini_native_adapter.py`
  以及最大迭代总结和 auxiliary relay 相关测试。

聊天展示验收：

- attached context 不作为用户正文。
- cron delivery hint 不显示。
- image optimistic preview 不闪 fallback。
- `MEDIA:` 标签变附件。
- terminal success row 不刷屏。
- terminal error row 可见。
- stderr 和 stdout 分开。
- 非零 exit code 有输出时不误红。
- command summary 清爽但完整命令可复制。

### 阶段 6：迁移 remote media/files/artifacts

迁移：

- `media.ts`
- `files.ts`
- preload download/media IPC。
- main process：
  - `fetchRemoteManagedFile`
  - `resolveLocalMediaCache`
  - `persistGeneratedMediaOnGateway`
  - `downloadRemoteManagedFile`
  - `downloadRemoteManagedFilesBatch`
  - managed downloads index。
- `session-artifacts-dialog.tsx`
- artifacts page remote open/download。

验收：

- remote image 可显示。
- remote video 可播放和 seek。
- remote audio 可播放。
- remote file 可下载。
- remote file 可 openAfter。
- batch download 可选择目录。
- 下载历史/cache 生效。
- session files dialog 合并 hosted artifacts。
- 产物页不显示“全部 / All”tab，默认进入“文件”tab；文件 tab 同时覆盖普通文件和视频。
- 检查产物筛选的路由白名单不含 `all`，页签由该白名单生成；手工访问 `?tab=all` 时应回落到“文件”，不能展示或加载聚合视图。合并上游代码后必须重复此项，防止“全部”页签被重新引入。
- 产物搜索提示、产物表格会话列、左侧会话标题等历史 session title 展示层不能露出 `Hermes` / `Hermes Agent` / `hermes-agent`，统一显示为 `AgentOS`，且不得改写底层会话数据。
- 产物页文件打开必须走 `openManagedFile(artifact.value)` -> Electron `resolveLocalMediaCache(fetchIfMissing:true)` -> Hermes gateway `/api/files/download`/`/api/files/read` -> 本地 cache `file://` 预览；cache 拉不到时直接提示打开失败，不得回退系统“保存为”窗口。不得把 remote absolute path、`file://` 派生 URL 或 OAuth 空 URL 直接丢给 `openExternal`。
- 产物页和本会话文件弹窗不得展示远端绝对路径，文件类产物直接隐藏路径列和路径副文本。展示层如需内部检索标签，必须把 `/opt/hermes/...` 映射为 `AgentOS/...`，把 Hermes home 映射为 `AgentOS data/...`，未知绝对路径只保留脱敏尾部；原始 path 只能作为内部下载 key。
- artifact 收集阶段要过滤目录型路径，不能因为 `/Users/.../.hermes/...` 里包含 `.hermes` 就把 `web_dist` 这类目录收进“文件”列表；同时要去掉工具输出里的包裹引号和字面 `\n` / `\r`。

### 阶段 7：迁移定时任务 UI

迁移：

- `cron/index.tsx`
- `cron/job-title.ts`
- `cron/job-state.ts`
- cron i18n。
- sidebar cron section 如目标 app 有。
- 左侧导航的“定时任务”入口；statusbar 不再重复注册 Cron 入口。

验收：

- 创建任务不需要手写 cron。
- 自定义任务只显示时间选择控件，提示词 placeholder 是 `总结我未读的晨报，并把前5条发给我`。
- 投递至只显示并提交 `此桌面` / `local`。
- daily/weekdays/weekly/monthly/hourly/every-15-minutes/custom 都生成正确 expr。
- 编辑旧 cron 能回填控件。
- 空名称根据中文 prompt 生成。
- run history 能打开 session。
- pause/resume/trigger/delete toast 正确。
- 中文界面不显示 `Cron` / `排程` 作为用户可见名称；统一使用 `定时任务`、`定时表达式`、`定时规则`。

### 阶段 8：迁移消息平台和技能 UX

迁移：

- `messaging/index.tsx`
- `messaging/platform-icon.tsx`
- 本地图标资源。
- messaging i18n。
- skill page i18n。
- `hermes_cli/agentos_policy.py` 及其模型、认证 provider、工具集、技能扫描调用点。
- desktop slash command curation。

验收：

- 只展示飞书、微信、QQ、企业微信、钉钉。
- `getMessagingPlatforms()` 返回后必须调用 `filterAgentOSMessagingPlatforms()` 再写入页面 state；检查 import 存在但没有调用不算迁移完成。
- 固定顺序为钉钉、飞书、企业微信、微信、QQ，不沿用后端 catalog 顺序。
- 企业微信选择 `wecom_callback` 优先。
- 平台名称由白名单转换函数写入中文；顶部描述通过 `t.messaging.platformDescription` 汉化，不直接展示后端英文 `name` / `description`。
- 字段 label/help/placeholder 通过 `t.messaging.fieldCopy` 汉化，覆盖五个中国消息平台的必填字段、允许列表、默认投递频道字段和机器人 webhook 字段。
- placeholder 回退顺序为 `localized.placeholder -> localized.label -> field.prompt`；这条兜底不能替代维护完整中文 placeholder，但可防止合并遗漏时立即泄漏英文。
- 文本框 placeholder 不允许回退后端英文，例如 `Allowed users (comma-separated)`、`Home channel ID`、`Home channel display name`、`DingTalk robot webhook URL (optional)` 都必须显示中文。
- 搜索、列表、详情页、开关 aria-label、保存/启用 toast 都使用汉化后的平台名称。
- 保存后提示重启 gateway。
- 陌生用户私聊触发的配对回复属于 server/gateway 契约，不是 desktop 设置页契约。`gateway/run.py` 必须调用 `gateway/pairing.py` 的统一模板，回复使用中文 AgentOS 品牌，展示 `agentos pairing approve <platform> <code>`，不得出现 `Hermes`、`Nous Research` 或英文配对提示。
- `pyproject.toml` 必须保留 `agentos = "hermes_cli.main:main"` console script；展示命令必须真实可执行。内部 `hermes` console script、模块名、容器路径、Linux 用户和配对存储格式继续保留，禁止为展示品牌破坏兼容层。
- 至少使用飞书未授权私聊做一次端到端验收：收到配对码 -> 执行 `agentos pairing approve feishu <code>` -> 下一条飞书消息通过授权。配对请求限流提示也必须是中文。
- 产品能力过滤必须由 `hermes_cli/agentos_policy.py` 集中控制，并同时作用于 server API、dashboard、desktop 和 runtime discovery，不能只改 `ToolsetConfigPanel`：
  - 模型 provider 只允许 `alibaba`、`alibaba-coding-plan`、`deepseek`、`kimi-coding-cn`、`lmstudio`、`minimax-cn`、`qwen-oauth`、`stepfun`、`tencent-tokenhub`、`xiaomi`、`zai`，并保留 `custom` / `custom:<name>` 和真实自定义 API endpoint。
  - `nous`、`openrouter`、`anthropic`、OpenAI、Gemini、xAI、Copilot、HuggingFace、Bedrock、Azure Foundry 等显式屏蔽；旧配置标记为 `is_user_defined` 也不能绕过已知屏蔽 slug。
  - `image_gen`、`video_gen`、`x_search` 当前整体隐藏，不显示工具集、provider 或 model。这取代“保留少量国产名字模型”的旧方案，因为底层仍会经过不可用的国外供应商。
  - `claude-code`、`claude-design`、`codex`、`opencode` 不出现在技能列表、同步结果和 runtime 可用技能中。
  - 过滤不得删除磁盘上的旧配置、插件目录或内部兼容模块；产品面隐藏与运行时数据迁移是两个问题。
- 上游合并后至少运行 AgentOS policy、inventory、tools config、skills profile 和 web server API 测试，防止新增 catalog 接口绕过策略。
- messaging/toolset 测试夹具不得使用 Telegram、Discord、Slack、OpenAI、Nous、FAL.ai、Krea 等产品面已屏蔽项来证明 AgentOS 行为；应使用五个允许的消息平台、本地 provider、自托管 provider 或与品牌无关的通用夹具。
- 纯通用组件测试如果需要稳定断言上游英文，可显式包裹指定 locale 的 `I18nProvider`；消息平台、品牌、供应商过滤等产品契约测试必须按默认中文断言，不能为让测试通过而把产品界面切回英文。
- skill/quick slash command 出现在 palette。
- Dashboard `/config` 必须提供独立“技能”分类，并以逐行路径列表编辑
  `skills.external_dirs`；支持新增、删除、排序和服务端/容器路径说明。保存后同一进程的技能页、
  prompt、slash index 与 `skill_view()` 必须立即读取全部有效目录，不要求重启 gateway。
- 专家技能生成的四条 slash command 必须走与手工输入 `/` 相同的 `parseSlashCommand`、`slash.exec` 和 skill invocation 链路；跨页面点击按 `requestNewSessionDraft` → `startFreshSessionDraft` → `requestComposerInsert(replace/main)` 的顺序执行，多行差旅模板换行保留，任何入口都不得直接请求 backend 或模拟提交。
- Hub 子进程安装、更新或卸载技能后，当前 profile 的 `skills/.hub/lock.json` 变化必须让
  长期运行的 server/desktop 在下一次读取时立即刷新 `skills_list`、新会话技能提示词和
  slash command index；不得要求重启 gateway、手动 `/reload-skills` 或等待缓存 TTL。
- `<available_skills>` 必须声明分类标题不是技能名；`skill_view` 接受精确短名称和冲突时的
  `category/skill-name`，并兼容模型误传的多级 `category/subcategory:skill-name`。插件
  `namespace:skill` 优先级、非法 namespace 和路径 traversal 拒绝规则必须保持。
- 运行跨进程索引回归时，在同一个已有多级分类中新增 Hub 技能并改写 lock file，随后不
  sleep 直接验证三类索引；同时断言 `bad.namespace:foo` 仍返回非法 namespace。
- 运行真实 Hub E2E：用可控 source 完成 fetch、隔离、安全扫描、嵌套分类安装和 lock 登记；
  在安装前预热 slash index，安装后不重启进程，依次验证 `commands.catalog` 的裸 `/` 菜单、
  `complete.slash` 的 `/skill-prefix` 补全，以及 `command.dispatch` 的直接调用；最终必须确认
  `/skill-name <instruction>` 返回 `type=skill`，并把完整 `SKILL.md` 和用户指令装入 message。
- 验证 Desktop Hub 动作成功后会使 slash completion cache 失效并递增 epoch；预热安装前 catalog，
  完成安装后用同一 cache key 必须重新请求，不能等一小时 TTL、重启客户端或手工 reload。
- 默认 Nacos Hub 另跑一条 source-specific E2E，使用真实 `NacosSkillSource`/`do_install`，只
  mock HTTP 响应；同时模拟 `tools.skills_tool` 在 home A 导入、运行时切换 home B，验证发现、
  路径归一化、`skill_view` 和 slash payload 全部跟随 `_skills_dir()`，不得引用冻结的
  `SKILLS_DIR`。URL Hub 用例通过不能替代此项。
- Hub 只允许内部 source ID `nacos`，UI 唯一显示名为“华清严选”。landing、搜索和旧 server
  响应都必须过滤公网 source/result；Nacos 无结果或超时直接显示空态/错误，不能用官方 index
  teaser 或任何公网 fallback 补位。旧 profile 的 `skills_hub.enabled_sources` 不能重开公网来源。
- `source=all` 只作为旧客户端别名映射到 `nacos`；显式非 Nacos source 和非 `nacos/...` 的
  install/preview/scan 返回 400。测试必须断言 public source 的 search/inspect/fetch 调用数为零。
  CLI uninstall 的 `--yes/-y` 必须真实传到 `skip_confirm`，避免
  dashboard 子进程卡确认；动作完成后刷新 installed、featured、skills list 和 slash cache。
- Desktop 与 Bot Mode 不得嵌入 Nous Skills Hub iframe；扫描
  `EmbeddedHubPicker`、`HUB_PICKER_URL`、`hermes-agent.nousresearch.com/docs/skills` 必须零命中。
- 页面右上只保留允许的基础状态按钮，不恢复快捷键/设置/右侧栏 titlebar 入口。

### 阶段 9：迁移 prompt overlays

迁移：

- `prompt-overlays.tsx`
- prompt stores。
- gateway request methods：
  - `sudo.respond`
  - `secret.respond`
  - approval respond。

验收：

- sudo close 发送空 password。
- cancel 不阻塞 backend。
- `no pending` 清理 stale dialog。
- gateway disconnected 有错误提示。
- 不出现双 respond。

### 阶段 10：迁移离线打包和 CI

迁移：

- package scripts。
- `stage-installer-script.cjs`。
- `stage-agent-payload.cjs`。
- `stage-native-deps.mjs`。
- `bundled-agent.cjs`。
- `bundle-electron-main.mjs` 的纯 JS bundle 与 native external 边界；`git-review-ops.ts` 的
  `simple-git` 必须进入 main bundle。
- `electron-net-request.cjs` 的 Electron session 网络请求器。
- builder config，特别是 `electron-builder-win.cjs`。
- CI workflow。
- server `Dockerfile` 源码覆盖镜像和 `Dockerfile.source-build` 完整构建镜像的职责区分。

验收：

- `npm run dist:mac` 默认生成 bundled payload。
- `npm run dist:win` 默认生成 bundled payload。
- `npm run dist:linux` 默认生成 bundled payload。
- skip marker 让 release build fail。
- manifest 必须是 schema 2，包含 commit，且 `sanitized`、`relocatable`、
  `pythonRuntimeBundled` 都严格为 true；platform/arch 与运行客户端一致。
- payload 有 `hermes_cli/main.py`、自包含 agent venv、Hermes console entrypoint、
  `HERMES_HOME/bin/browser-use` 和自包含 `uv-tools/browser-use` Python。
- payload 不得包含 `pyvenv.cfg`、构建机 Python/work-root 绝对路径、绝对 console shebang、
  editable-install 路径、`.env`/云凭据/SSH key/token cache/private key 或真实字面 secret。
- 成功 manifest 最后写入；任一安全、自包含或可迁移检查失败都必须 fail closed。
- 当前 Windows standalone Python/distlib launcher 尚未验证，代码会拒绝 schema 2 bundle；
  不得关闭校验出假离线包。恢复 Windows 出包前必须在重定位目录执行三个 Windows entrypoint。
- packaged app 首次启动可离线 seed。
- packaged resources 下存在 `bundled-installer`、`bundled-agent`；原生 external 位于
  `app.asar.unpacked/dist/node_modules`，不能依赖旧 `resources/native-deps/vendor`。
- packaged resources 下存在 schema 3 `desktop-release.json`，其中租户 ID、Windows EXE 和 macOS DMG 对象存储地址都与当前发行租户一致。
- packaged `electron-main.mjs` 自包含 `simple-git`；原生 `node-pty`/`get-windows` 位于
  `app.asar.unpacked/dist/node_modules`。不得恢复旧 `native-deps/vendor/simple-git` fallback。
- `npm run dev` 不因旧 simple-git vendor 路径崩溃；如果失败是 5174 端口占用，要按端口问题处理。
- `npm run dev` 不因 `mermaid -> es-toolkit` 依赖预构建失败崩溃；根 `package.json` 必须保留 `overrides.es-toolkit = "1.48.0"`，并用 `npm ls es-toolkit --all` 验证没有浮到缺文件的 `1.49.0`。
- `scripts/assert-root-install.mjs` 在 Vite 前校验 assistant-ui 声明版本、实际安装版本和必需导出；Windows runner 必须从根目录安装 workspace。`fromThreadMessageLike`、`generateId` 直接从 `@assistant-ui/core` 导入，不能依赖 `@assistant-ui/react` 转导出。出现 `MISSING_EXPORT` 时先清理根 `node_modules` 并按锁文件重装，禁止删除 markdown 修复或数学预处理功能来绕过。
- 根 `package.json` 保留 `dist:win` 单命令入口并转发 desktop workspace；desktop 的 `dist:win`、`dist:win:nsis`、`dist:win:msi` 都必须先执行 `sync:root-deps`，通过根 prefix 同步 workspace 依赖且不改锁文件。根目录和 `apps/desktop` 两种调用路径都必须验收。根清单固定 `packageManager: npm@11.17.0`；`sync-root-deps.mjs` 必须真实探测 `npm_execpath`，在 npm 11.10 至 11.16 下从临时目录调用固定 npm 完成安装，不得全局升级 npm、关闭 `engine-strict` 或继承会阻断自举的项目 npmrc 环境变量。
- CI 三平台验证 payload。
- release tag 是 `desktop-v<version>`。
- Windows 客户端内更新成功后自动打开新版本，不能停在“旧版本退出、安装器完成、客户端不再启动”的状态。
- Windows 安装交接把当前真实 `process.execPath` 传给 PowerShell；新客户端启动位于安装器 `WaitForExit()` 之后，且临时安装包只在启动命令成功后删除。自定义安装目录下也必须成立。
- Windows/macOS 客户端检查与下载更新直接访问 `desktop-release.json` 指向的对象存储，不向 BFF 查询安装源。
- Desktop 只允许租户 AgentOS 安装包更新；本地/远程模式、启动、定时和 focus 检查都不得调用 `/api/hermes/update*`、`hermes update`、Nous release feed 或 Git 源码更新。
- 未配置当前平台包源时显式返回 `agentos-package-source-unavailable`，不得回退到 Hermes 后端更新或向用户提示上游安装命令。
- 首次安装/修复只使用 `bundled-agent` 和 `bundled-installer`；测试必须证明 packaged 资源缺失时 fail closed，不下载 `raw.githubusercontent.com/NousResearch/hermes-agent` 且不读取旧 checkout 的安装脚本。
- 系统页、关于页、命令面板和后台推送只显示 AgentOS 包版本；Windows EXE 的四个版本资源字段都是 AgentOS，不得显示 Hermes/Nous Research。
- 普通新产物 appId/AUMID 必须是 `com.hqzyai.agentos`；Windows/macOS 新装进入 `hqzy` 安装目录，默认 userData、sessionData、更新缓存、日志、crash dump 和 Agent 数据全部位于 `{APP_DATA_DIR}/profiles/{ORG_NAME}`。旧 `com.nousresearch.hermes`、旧 userData 与 `%LOCALAPPDATA%\hermes` / `~/.hermes` 只能作为迁移源；唯一允许旧 bundle id 的产物是 appId 首次迁移专用的单版本 macOS 桥接 DMG。冲突备份必须保留，迁移失败不得删除源数据。
- Windows NSIS `guid` 与 MSI `upgradeCode` 必须固定为旧安装产品值，运行时 appId/AUMID 仍为新值；macOS 旧客户端必须先升级到桥接版本 N，再升级到版本号更高的最终新身份版本 N+1。普通打包、后续发布或上游合并不得删除这条升级兼容链；普通对象存储上传必须拒绝 `appid-bridge` DMG，专用桥接上传也必须拒绝普通 DMG。
- `hermes:*` IPC、`HERMES_HOME` 环境变量名、更新标记和底层可执行文件名继续作后端兼容协议保留；显式非默认 `HERMES_HOME` 和远程实例 `~/.hermes` 不得被本地目录迁移重写。
- Windows 版本检查和下载都通过 Electron `session.fetch` / `net.fetch`，继承系统代理、PAC 和证书；HEAD 不支持时用 `Range: bytes=0-0`，正式下载复用 `.part` 和 Range 续传。
- 更新网络层最多跟随 5 次重定向，HTTPS 禁止降级为 HTTP；连接与流式读取 15 秒无活动超时，连接失败最多 3 次并做短退避。最终错误在 UI 中归一为中文，原始错误只写安全日志。
- 每个租户构建必须设置 `AGENTOS_DESKTOP_TENANT_ID`、`AGENTOS_DESKTOP_UPDATE_URL_WINDOWS` 和 `AGENTOS_DESKTOP_UPDATE_URL_MAC`；更新后的 EXE/DMG 必须继续携带同一租户的两平台更新源。
- 对象存储必须提供 `x-tos-meta-version`，或使用带 `x.y.z` 的安装包文件名；更新弹窗验收必须看到当前版本和目标版本。macOS DMG 还必须提供 `x-tos-meta-sha256`，缺失时自动安装必须在下载前拒绝。
- Windows 覆盖更新使用 `/S --updated /D=<原安装目录>`，禁止 `--force-run` 触发 electron-builder 自带且不可观测的启动分支。新安装包必须在 `customInstall` 中提供静默安装后的自启动兜底；PowerShell 交接脚本在安装器退出后优先按完整 EXE 路径接管该进程，未找到时才补充启动，并确认最终进程至少持续存活 5 秒后才记录成功和删除临时安装包。
- macOS 覆盖更新必须从持久 `.app` 路径启动，校验 DMG UDIF、SHA-256、bundle ID 与适用时的 TeamIdentifier，通过 staging/backup 原位替换；新客户端按原 app 路径重启并持续存活至少 5 秒后才提交成功，任何失败自动恢复 backup 并重新打开旧版。
- server 快速验证优先用 `Dockerfile` 在固定基础镜像 digest/tag 上做源码覆盖并重新构建 `web`、`ui-tui`、当前 Python 包；基础镜像不存在或依赖发生变化时才用 `Dockerfile.source-build` 全量构建。新镜像必须使用新 tag，不能覆盖、删除或 prune 现有基础镜像和其他派生镜像。
- 源码覆盖镜像复用旧 venv 时，NumPy 必须对齐当前源码锁；被动 voice/wake/status probe
  不触发 STT lazy install，只有真实转写允许有界 single-flight 安装。
- gateway/dashboard 使用同一新镜像，数据继续挂载 `/opt/data`；本地并行验证加入现有 `agentos-network`，使用独立容器名、端口和 volume，禁止 `docker compose down -v` 影响已有实例。

## 3. 禁止破坏的契约

### 不要把 BFF base 和 hosted gateway URL 混为一谈

UI 输入：

```text
BFF base
```

connection config 保存：

```text
BFF base + /desktop/hosted-gateway
```

BFF login 调：

```text
BFF base + /auth/login
```

WS/REST 调：

```text
hosted gateway URL + /api/...
```

### 不要把 access token 暴露给 renderer

renderer 只知道 authenticated state。cookie 和 ticket 都在 main process。

### 不要缓存 OAuth WebSocket URL

每次 connect 前调用 main process fresh mint。

### 不要把 remote path 当本机 file path

remote path 要走：

- `/api/media`
- `/api/files/read`
- `/api/files/download`
- `/api/files/upload`
- `hermes-media://remote`
- Electron download IPC

### 不要让 session 请求落回本地

remote profile 的 session read/mutation 必须转发远端。

### 不要让 terminal output 刷屏

terminal/execute_code 成功 row 默认隐藏。错误、审批、运行中仍展示。

### 不要要求用户写 cron

UI 要以时间选择为主，cron expression 是后端协议。

### 不要把 skill/quick commands 从 desktop palette 过滤掉

curation 是隐藏内置噪声，不是隐藏用户扩展。

### 不要恢复截图标注的桌面壳噪声

AgentOS 桌面默认不展示：

- titlebar `flip-panes` / `arrow-swap`。
- titlebar 快捷键面板、设置齿轮、右侧栏按钮。
- `New session` 的 `⌘ N` shortcut chip。
- Gateway popover 的 `Recent activity` 日志区域。
- statusbar client/backend version pill。
- statusbar `agents` / `cron` 重复入口。
- desktop 内置终端及其 statusbar、命令面板、快捷键、设置入口；模型使用的后端 terminal tool 不在隐藏范围内。

除 desktop 内置终端外，这些能力可以在设置页、命令中心或底层快捷键里保留，但不要作为截图标注位置的常驻入口；内置终端当前要求所有客户端入口同时关闭。

### 不要把 skip manifest 当成功

offline release build 中 `skipped:true` 必须 fail。

## 4. 常见问题定位路径

### 登录失败

先看：

- `auth-errors.cjs`
- `login-screen.tsx loginErrorMessage`
- main process `postBffPasswordLogin`
- BFF `/auth/login` URL 是否正确。
- 是否误把 hosted gateway URL 当 BFF base。
- 服务端是否返回 HTML。

### 登录成功但聊天连不上

先看：

- `installHostedGatewayAuthCookies`
- cookie path 是否匹配 hosted gateway。
- `verifyDesktopHostedGatewaySession` 是否只调用 BFF 轻量认证接口，不触发实例启动。
- `mintGatewayWsTicket` 是否只在连接阶段调用，并为首次冷启动保留完整超时预算。
- renderer 是否每次连接调用 `getGatewayWsUrl`。
- ticket 是否复用。
- 是否发生账号切换竞态：检查 `primaryBackendGeneration`、旧 child 的 `exit/error`
  回调是否校验 child identity，以及旧 Promise 的 catch 是否仍会写当前
  `backendStartFailure`。
- 已启动客户端的远程网关短暂断连是否只进入后台退避重连：检查
  `primaryBackendRecoveryGeneration`；不得因为 `/api/status` 空响应、连接重置或
  超时直接出现“AgentOS 无法启动”，也不得要求用户点击“重试”。
- 首次启动失败与已启动后的远程重连失败是否保持不同语义：前者可以显示恢复页，
  后者不得写入 `backendStartFailure` 或重置已完成的 boot 状态。
- post-boot 持续断线是否只显示持久重连警告并保留主界面；警告中的“重试”应触发
  立即重连，自动恢复后警告应消失，任何阶段都不得制造 `boot.error`。
- runtime `hermes` 与 VS Code `vscode` 是否都使用 `10000:10000`；两个镜像的
  Dockerfile 必须共享同一 UID/GID 构建参数，runtime 构建必须断言上游身份未漂移。
- 同一 profile volume 的 `config.yaml`、`gateway.lock`、`state.db` 和 gateway
  日志是否保持 `10000:10000`；同时启动 runtime/VS Code 后持续十分钟，属主和
  gateway PID 不得变化，`/api/status` 必须持续返回 `200`。
- 若出现 dashboard 慢、gateway 重启或客户端约十分钟后断线，是否先查共享卷数字
  属主和 `PermissionError`，而不是先归因于历史会话大小或增加重试次数。
- 打开历史会话时，REST 消息读取与 WebSocket `session.resume` 是两个独立请求；
  若消息已显示后出现 `resume failed: attempt to write a readonly database`，必须
  检查 dashboard 的长期 `SessionDB` 写连接和伴生容器是否递归修改共享卷。
- REST transcript 返回且 `session_id` 与目标匹配后是否立即绘制，不等待
  `session.resume`、AIAgent、工具或技能初始化；用 pending 的 resume Promise 验证
  历史仍可先显示。runtime 后续无 live projection 时不得再次重建同一长消息数组。
- 从 Bots/群聊页以 `intent: main` 打开 Agent canonical chat 时是否同时导航并主动
  front `workspace` pane；连续点击同一 Agent、hash 不变化时也必须离开插件页。
- 可写 `SessionDB` 遇到一次 `SQLITE_READONLY` 时是否在锁内重建连接并重试；
  `SessionDB(read_only=True)` 是否仍严格拒绝写入，不能被自动升级。
- 普通历史会话 `session.resume` 是否只注册 lazy runtime session，不再调度
  AIAgent 后台预热；第一次发送消息时是否仍通过 `_sess()` 正确构建 agent 并
  恢复原 model/provider/reasoning/service-tier。
- VS Code entrypoint 是否只递归处理 `.code-server` 和自身 home，明确禁止
  `chown -R "${HERMES_HOME}"` 与 `find "${HERMES_HOME}" ... chmod`。
- 打开历史会话后连续探测 `/api/status` 至少一分钟；不得因 agent 构建出现连续
  2 秒超时、WebSocket 断开或客户端启动失败页。
- 日志若出现“远程 backend ready”后又启动旧本地 Python，优先按 primary backend
  lifecycle race 排查，不要先加重试延时。

### sidebar 空

先看：

- global remote 是否 active。
- `interceptSessionRequestForRemote` 是否拦截 `/api/profiles/sessions`。
- fallback `/api/sessions` 是否执行。
- rows 是否补 profile。
- profile filter 是否过严。

### 远程图片/视频打不开

先看：

- `$connection.mode` 是否 remote。
- `resolveMediaSrc` 是否走 remote 分支。
- image 是否先 `/api/media` 后 `/api/files/read`。
- audio/video 是否走 `hermes-media://remote`。
- main process custom protocol 是否支持 remote。
- profile 参数是否丢失。

### 下载失败

先看：

- preload 是否暴露 `downloadRemoteFile`。
- renderer payload 是否带 profile。
- main process `shouldFetchManagedFileRemotely` 判断。
- `/api/files/download` 是否存在。
- fallback `/api/files/read` 是否成功。
- OAuth mode 是否用 Electron session cookie，而不是 token URL。

### 定时任务保存失败

先看：

- prompt 是否为空。
- schedule 是否生成 5 段。
- `scheduleFromControls` clamp。
- `deliver` 是否只支持 local。
- name 是否通过 `resolveCronJobName`。

### dev/build 报 simple-git 找不到

先看：

- 是否运行了旧 `git-review-ops.cjs` 或未重建的 `electron-main.mjs`；当前
  `git-review-ops.ts` 静态 import 应由 esbuild 打入 main bundle。
- repo root 是否跑过 `npm install`。
- `node -p "require.resolve('simple-git')"` 在 `apps/desktop` 下是否能解析。
- `dist/electron-main.mjs` 是否已重新生成且没有 vendor simple-git fallback。
- `npm run builder -- --dir` 后 `app.asar.unpacked/dist/node_modules/node-pty` 与适用平台的
  `get-windows` 是否完整。
- `package-lock.json` 是否还保留旧 workspace link 名。

### 打包后首次启动还要联网

先看：

- `HERMES_DESKTOP_BUNDLE_AGENT=1` 是否在 dist env。
- `build/bundled-agent/manifest.json` 是否 skip。
- payload 是否打入 `extraResources`。
- packaged resources 下有没有 `bundled-agent`。
- `hasBundledAgentPayload` 是否 true。
- `seedBundledAgent` 是否执行。
- `build/bundled-agent` 和 packaged resources 内不得包含 `AgentOS-*.dmg`、`AgentOS-*.zip`、`AgentOS-*.exe`、`AgentOS-*.AppImage`。
- macOS 离线 DMG 体积异常时，必须检查 `bundled-agent/hermes-home/hermes-agent/apps`，避免把历史安装包递归打进新安装包。

## 5. 最小回归命令

### 官方 Hermes 上游合并

以后不再通过本仓库 `main` 中转。使用仓库内 skill：

```bash
cd /path/to/agentos-desktop
docs/skills/merge-hermes-upstream/scripts/start-merge.sh 0.21.0 v2026.8.31 2026.09.02 main
```

该脚本只接受官方 `https://github.com/NousResearch/hermes-agent.git` 的精确 release tag，并基于明确的 base branch 创建 `ai-agent/hermes-v<semver>-YYYY.MM.DD`。发生冲突时退出码为 `2`，由智能体按本规范逐块完成语义合并。

冲突解决后先运行：

```bash
docs/skills/merge-hermes-upstream/scripts/audit-agentos-contracts.sh
```

完成合并提交后运行：

```bash
docs/skills/merge-hermes-upstream/scripts/validate-merge.sh
```

验收必须包括：清单锁定的官方 tag peeled commit 已成为当前分支祖先、无未解决冲突、无 diff whitespace 错误、产物筛选/消息平台/状态栏/归档入口/供应商过滤/品牌配置契约仍成立。

根据仓库当前 package scripts，可优先跑：

```bash
cd /path/to/agentos-desktop/apps/desktop
npm run test:desktop:platforms
npm run test:ui
npm run typecheck
npm run build
```

如果只改某个模块，可跑对应测试：

```bash
node --test electron/auth-errors.test.cjs
node --test electron/client-package-update.test.cjs electron/installer-config.test.cjs electron/update-marker.test.cjs electron/release-config.test.cjs
node --test scripts/write-release-config.test.cjs
node --test scripts/release-script-boundaries.test.cjs
npm --prefix apps/desktop run test:desktop:platforms -- electron/dashboard-token.test.ts
node --test electron/bundled-agent.test.cjs
node --test scripts/stage-agent-payload.test.cjs
node --test scripts/run-electron-builder.test.cjs
rg -n "native-deps/vendor/node_modules/simple-git" dist/electron-main.mjs
# 期望无输出；再用 packaged desktop 平台测试验证 Review/Git IPC
hdiutil verify release/AgentOS-0.20.5-mac-arm64.dmg
unzip -tqq release/AgentOS-0.20.5-mac-arm64.zip
```

React/vitest 相关：

```bash
npm run test:ui -- --run src/app/profiles/create-profile-dialog.test.tsx
node --test src/plugins/hermes-bots/tests/create-agent-clone-default.test.mjs
npm run test:ui -- --run src/lib/files.test.ts
npm run test:ui -- --run src/lib/media.remote.test.ts
npm run test:ui -- --run src/app/cron/job-title.test.ts
npm run test:ui -- src/lib/gateway-ws-url.test.ts
npm run test:ui -- src/app/gateway/hooks/use-gateway-boot.test.tsx
npx vitest run --environment jsdom src/app/shell/gateway-menu-panel.test.tsx
```

Python 定向回归：

```bash
pytest -q tests/agent/test_model_request_headers.py tests/agent/test_error_classifier.py
pytest -q tests/run_agent/test_summarize_api_error.py
pytest -q tests/hermes_cli/test_dashboard_admin_endpoints.py tests/hermes_cli/test_skills_hub_source_routing.py
pytest -q tests/hermes_cli/test_web_server_files.py
pytest -q tests/tools/test_lazy_deps.py tests/tools/test_transcription_lazy_install.py tests/tools/test_transcription_tools.py tests/tools/test_voice_mode.py tests/tools/test_wake_word.py
pytest -q tests/tui_gateway/test_protocol.py
```

注意：具体 vitest 参数取决于 workspace 脚本，若失败先检查当前 package runner。

### Windows 覆盖更新与自动重启验收

- `package.json` 和 `scripts/electron-builder-win.cjs` 的最终配置都必须包含 `nsis.include: electron/installer.nsh`；自动化测试直接加载 Windows 构建配置验证，不能以旧的 `builder-effective-config.yaml` 作为本次出包证据。安装包必须包含该文件的静默安装自启动兜底，并直接启动 `$INSTDIR\${APP_EXECUTABLE_FILENAME}`，不能依赖快捷方式或只依赖当前桌面版本的 PowerShell 交接代码。
- PowerShell 在安装器成功退出后，必须删除并验证 `.hermes-update-in-progress` 已消失，再接管安装器已经启动的进程或按原 `process.execPath` 启动新进程。
- 新进程必须按完整 EXE 路径轮询确认；最多启动 3 次，每次等待出现最多 15 秒，出现后稳定运行至少 5 秒才能写成功结果。目标不存在、标记删除失败、三次启动超时或进程提前退出都必须记为失败。
- 现场日志固定查 `HERMES_HOME/logs/client-update-handoff.log`；Windows 默认是 `%LOCALAPPDATA%\hqzy\AgentOS\agent-data\logs\client-update-handoff.log`。日志应能看到 `installer-exited`、`update-marker-cleared`、逐次 `application-start-requested`/`application-start-timeout`、`application-started`/`application-adopted`、`handoff-complete`。
- 验证安装器兜底时，可从未含新桌面交接逻辑的旧包升级；验证新桌面交接逻辑时，N-1 客户端本身必须已经包含该逻辑，再升级到指纹或版本不同的 N 包。不能用“新包里已经修了”推断执行升级的旧客户端也拥有修复。
- 完整 Windows 发行包必须在 Windows runner 使用 `HERMES_DESKTOP_BUNDLE_AGENT=1` 构建；macOS 只能用 `HERMES_DESKTOP_BUNDLE_AGENT=0` 做 bootstrap-only NSIS 编译验证，不得把该验证包发布为生产安装包。
- 检查 `scripts/run-electron-builder.mjs` 没有残留 CommonJS 的 `require.main`、`module` 或 `module.exports`；测试必须加载实际 `.mjs` 入口，不能继续引用已删除的 `.cjs` 文件。该问题会在前端构建全部完成后才让 Windows 打包失败，必须列为每次上游合并后的固定检查项。

## 6. 文档完成后的人工确认问题

如果继续细化本文档，请向业务 owner 确认：

1. 生产 BFF base URL 是否继续由 CI 写 `defaults.json` 落盘，还是要改成 main/renderer 都能读取的统一发行参数。
2. 新 desktop 是否仍锁定 `LOCKED_GATEWAY_SETTINGS = true`，还是恢复 local/remote 切换。
3. legacy token mode 是否保留在 UI，还是只保留代码兼容。
4. 消息平台是否只展示中国五平台，还是需要重新开放 Telegram/Discord/Slack。
5. 离线包是否必须支持三平台完全离线首次启动，还是只要求 macOS/Windows。
6. generated media 上传远端失败后，是否接受只保留本地 cache。
7. session artifacts API `/api/sessions/{id}/artifacts` 是否在所有 hosted gateway 版本可用。
8. `auth-errors.cjs` 是否要真正接入 `electron/main.ts` 登录链路，删除重复的本地 `bffLoginErrorMessage`。
9. 是否需要重新实现一键三端 `build-clients.cjs`；如果不实现，继续不要保留 `dist:clients` 断入口。
