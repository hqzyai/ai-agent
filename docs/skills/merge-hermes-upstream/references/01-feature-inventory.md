# AgentOS Desktop 改造特性总览

本文是 AgentOS 改造的功能地图，覆盖初始 `main` 基线和后续产品分支已验证的生产硬化。后续 AI coding 智能体迁移新 desktop 时，先读本文确认要迁移哪些能力，再进入对应专题文档。

## 1. 提交范围和归类

### 主要作者提交

`jiawenyao401/jiawy` 的初始改造集中在 2026-06-16 到 2026-07-06，后续生产硬化持续到 2026-07-30：

- 远程 gateway 默认地址和设置页改造。
- AgentOS 桌面品牌化、图标替换、中文文案。
- 消息平台页汉化和平台筛选。
- 技能页和平台图标本地化。
- “技能与工具”首个“专家技能”页签：按差旅报销、项目研判、投资合同审核、文书起草的固定顺序展示可搜索专家卡片，点击后进入全新主会话并生成含中文方括号待填写字段的技能 slash command 草稿；空会话欢迎区不再重复展示四个入口，主输入框空态固定提示“今天帮你做些什么? /调用技能与指令”。
- 远程 gateway 自动重连。
- 视频渲染、终端/代码执行信息展示优化。
- gateway 弹窗和 status bar 优化。
- cron 任务名称自动生成。
- 桌面账号密码登录。
- 定时任务 UI 从手写 cron 改为时间选择。
- 频道增量汉化。
- 图片/视频产物加载慢和有效期短问题处理。
- Windows 打包修复。
- 离线客户端打包、bundled agent payload、bundled installer staging。
- native dependency staging，尤其是 `simple-git` 这类 Electron main process 启动路径上的纯 JS 依赖。
- 本地登录错误处理，避免服务端 HTML 直接显示给用户。
- token 过期后的自动恢复、持久化登录态恢复和 renderer 闪烁循环治理。
- 退出账号后切换用户的 backend generation 隔离，避免旧进程回调污染新账号。
- 历史会话 `SQLITE_READONLY` 自愈、恢复时延迟构建智能体和模型目录阻塞治理。
- AgentOS server 统一模型、技能、工具集产品面策略。
- 飞书等消息平台配对回复的中文 AgentOS 品牌化。
- 多租户 Windows 客户端对象存储更新、系统代理网络栈、覆盖安装和自动重启。
- 客户端发行身份改为 `com.hqzyai.agentos`，Windows/macOS 新装进入 `hqzy` 应用目录；默认 Electron 状态、缓存、日志、crash dump 和 Agent 数据统一进入 `{APP_DATA_DIR}/profiles/{ORG_NAME}`，并安全迁移旧目录。
- Windows 保留历史 NSIS/MSI 安装产品 GUID 以继续原位升级；macOS 使用一次性旧 appId 桥接版本再切换最终新身份，避免旧客户端拒绝新 DMG。
- 基于已验证 runtime 的 server 源码覆盖派生镜像与隔离部署流程。

`邢磊` 相关提交集中在 `.github/workflows/sync-hermes-agent.yml`：

- 建立桌面三平台构建 workflow。
- 添加 workflow 写权限。
- 从早期同步 upstream 的流程收敛为 main push 构建。
- 修复 workspace `file:` 依赖安装，使用 `npm install`。
- 每平台构建对应格式。
- 构建前注入 gateway/BFF 配置。
- release upload 流程。

`g642579705-glitch` 相关提交集中在 2026-07-03 和 2026-07-06：

- 同步上游后恢复/维护 `zh.ts`。
- 添加 `summarize-command`，让工具命令展示更清爽。
- 修复 stale sudo dialog。
- 集中 BFF 默认配置。
- 增加远程文件下载和会话文件弹窗。

### 中间提交如何理解

一些提交标题如 `打包`、`打包1`、`test package 1/2/3/4` 是迭代过程，不应在规范里逐条照搬。应把最终效果归纳为：

- offline bundled agent payload 必须默认开启。
- stage 脚本必须生成可验证 manifest。
- symlink 必须物化。
- `bundled-installer` 和 `native-deps` 必须作为 `extraResources` 进入 packaged app。
- Electron main process 启动路径上的依赖必须能在 dev、build、packaged 三种环境解析；缺依赖不能让整个桌面启动崩溃。
- Windows/macOS/Linux artifacts 必须可构建和可验证。
- workflow 必须在构建后验证 payload。

## 2. 产品定位改造

### 从 Hermes 桌面壳到 AgentOS 桌面壳

当前 desktop 仍继承 Hermes agent core，但产品壳已经按 AgentOS 改造：

- app name 和图标显示为 AgentOS。
- 登录页标题是 `登录 AgentOS`。
- 错误提示替换 `Hermes`、`BFF hosted-gateway` 等内部词为用户可理解的 `AgentOS 服务` 或 `服务`。
- 消息平台描述把 `Hermes Agent` 替换为 `AgentOS`。
- 设置、技能、定时任务、产物、消息平台页都有中文文案。
- 模型自我身份、默认 `SOUL.md`、TUI/WebUI branding 也必须迁移到 AgentOS；用户问“你是谁”时不能回答 `Hermes Agent` 或 `Nous Research`。

新 desktop 迁移时不要只改 logo。要把用户可见文案、错误提示、通知、状态栏、平台名、空状态、按钮、toast 都纳入 AgentOS 语境。

### 独立 desktop chat surface

AgentOS desktop 是 Electron + React + nanostores + assistant-ui 的独立聊天面，不嵌入 dashboard 的 `hermes --tui`。这一点非常重要：

- dashboard chat 页面可以嵌入 TUI。
- desktop app 不嵌入 TUI，它有自己的 composer、thread、slash command pipeline、renderer 状态。
- desktop 和 TUI 共用后端 `tui_gateway` JSON-RPC 能力，但 UI 不共用。

迁移新 desktop 时，不要把 dashboard 的 PTY/TUI 规则误套到 desktop renderer。

## 3. 登录和远程 gateway 改造

### 默认 BFF 配置集中

关键文件：

- `apps/desktop/config/defaults.json`
- `apps/desktop/src/config/defaults.ts`
- `apps/desktop/electron/main.ts`
- `apps/desktop/src/app/settings/gateway-settings.tsx`

上游本地开发默认值：

```json
{
  "bffBaseUrl": "http://127.0.0.1:5001"
}
```

当前 `agentos-20260817` 源码默认值是 `http://192.168.2.10:5001`，它只是当前联调租户地址；生产出包必须由发行配置注入该租户实际的完整 BFF URL。规范上不要把任一 IP 当成永久协议；正确要求是：

- 源码默认值适合本地开发。
- CI/发行版通过 `AGENTOS_DESKTOP_BFF_BASE_URL` 注入完整生产 BFF URL，必须包含实际协议和端口，不能依赖默认 80 端口。
- `write-release-config.cjs` 把租户 BFF 写入 `build/desktop-release.json`；打包后的 main process 优先读取该文件，开发模式和旧包才回退到 defaults。
- 发行构建不得为了切换租户而改写 `config/defaults.json`，否则会污染本地联调地址并造成工作区漂移。

### 账号密码登录主路径

关键文件：

- `apps/desktop/src/components/login-screen.tsx`
- `apps/desktop/electron/main.ts`
- `apps/desktop/electron/auth-errors.cjs`
- `apps/desktop/electron/preload.ts`
- `apps/desktop/src/global.d.ts`

用户登录流程：

1. renderer 展示账号密码表单。
2. renderer 调用 `window.hermesDesktop.auth.login({ username, password })`。
3. preload 映射到 IPC `hermes:auth:login`。
4. main process 调用 BFF `/auth/login`。
5. main process 将 BFF 返回的 access token 和 refresh token 写成 hosted gateway 域下的 HttpOnly cookie。
6. main process 使用 cookie 调 `/api/auth/ws-ticket`，随后用单次 ticket 建立真实 WebSocket，验证 hosted gateway 及其上游运行实例完整可用。
7. 成功后保存 connection config 为 remote OAuth mode。
8. 重置本地 backend，让 renderer 重新连接远程 backend。

第 6 步的探测 ticket 已被消费，renderer 正式连接前必须重新申请。`/api/status` 成功或 ticket 签发成功都不能单独作为 authenticated 的依据；真实 WS 握手失败时应留在登录页，提示用户智能体正在头脑风暴中，不能先进入主界面再显示通用启动失败页。

token 生命周期与启动顺序：

- `hermes_session_at` 过期而 `hermes_session_rt` 有效时，下一次 ws-ticket/REST 请求由服务端刷新；Electron persistent session 自动保存响应中的新 cookie。恢复 authenticated 前仍需用新 ticket 完成真实 WS 握手。
- Electron 窗口 `did-finish-load` 不得直接抢跑 `startHermes()`。renderer 必须先执行 `auth.getStatus()`，用安全存储中的凭据更新 cookie，认证成功后再挂载 `ContribController` 并连接网关。
- refresh token 无效或服务端返回明确 401/403 时，首次连接和断线重连都要重载认证入口。保存凭据可用则自动重新登录；失败则设置/保留 `manualLoginRequired` 并回账号密码登录页。
- Electron IPC 可能丢失 Error 自定义字段，过期判断要兼容序列化后的明确错误文本，但不能把 timeout/DNS/5xx 当成登录过期。

### 错误转换

登录错误不能泄漏内部 HTML 或英文栈：

- 401/403 或 invalid credentials -> `用户名或密码错误。`
- 404 -> `AgentOS 服务登录接口不可用，请检查客户端服务地址配置。`
- HTML 响应 -> `AgentOS 服务返回了网页错误，请检查客户端服务地址配置 (...)。`
- network/timeout -> 中文网络错误。
- Electron remote method wrapper 要剥离。

新 desktop 如果重新写登录页，必须复制这个错误归一逻辑，或者把它抽成共享 helper。

## 4. 远程 profile/session 改造

关键文件：

- `apps/desktop/electron/main.ts`
- `apps/desktop/src/store/session.ts`
- `apps/desktop/src/app/chat/sidebar/*`

核心问题：

远程 profile 的 session 不在本地 desktop 的 state.db。它在远端 gateway 的 state.db。桌面侧如果按本地 session API 读取，就会出现：

- sidebar 空。
- session id 404。
- rename/archive/delete 无效。
- 切 profile 后写入错误 profile。

因此 main process 拦截 `hermes:api` 中的 session 请求：

- `GET /api/profiles/sessions`
- `GET /api/sessions/{id}`
- `GET /api/sessions/{id}/messages`
- `DELETE /api/sessions/{id}`
- `PATCH /api/sessions/{id}`

根据 profile 和 connection config 转发到正确 backend。

全局 remote 模式：

- 一个远程 backend 服务所有 profile。
- 请求要保留 `?profile=<name>`。
- session list 可先试 `/api/profiles/sessions`，为空或失败时回退 `/api/sessions`。

per-profile override 模式：

- 某个 profile 指向自己的 remote host。
- 请求转发到这个 remote host 后不保留桌面本地 profile 参数，因为 remote host 自己的 state.db 是源头。

## 5. 聊天消息和工具展示改造

关键文件：

- `apps/desktop/src/lib/chat-messages.ts`
- `apps/desktop/src/lib/chat-runtime.ts`
- `apps/desktop/src/components/assistant-ui/tool-fallback-model.ts`
- `apps/desktop/src/components/assistant-ui/tool-fallback.tsx`
- `apps/desktop/src/lib/summarize-command.ts`
- `apps/desktop/src/components/assistant-ui/markdown-text.tsx`

最终规则：

- 用户消息显示时剥离 `--- Attached Context ---` 后的大段上下文，只展示真实 prompt 和 ref。
- cron delivery hint 不应显示成用户输入。
- `@file`、`@folder`、`@url`、`@image`、`@tool`、`@terminal` 作为 ref 展示。
- `MEDIA:` 标签和裸音视频路径转换为可点击/可播放 media attachment。
- `terminal` 和 `execute_code` 成功结果默认隐藏普通工具 row，避免对话里充满命令输出。
- 失败、运行中、审批、stderr/stdout 仍要可见。
- stdout/stderr 分离，stderr 不自动等于错误。
- ANSI 输出用 `AnsiText` 渲染。
- 命令摘要用 `summarizeShellCommand`，但完整命令仍保留在详情和复制中。

## 6. 远程媒体和会话产物

关键文件：

- `apps/desktop/src/lib/media.ts`
- `apps/desktop/src/lib/files.ts`
- `apps/desktop/electron/main.ts`
- `apps/desktop/electron/preload.ts`
- `apps/desktop/src/app/chat/session-artifacts-dialog.tsx`
- `apps/desktop/src/app/artifacts/index.tsx`

核心契约：

远程模式下，agent 生成的文件在 gateway 机器上，不在 desktop 本机。不能把远端路径当成本机 `file://` 打开。

处理策略：

- 图片：优先通过 `/api/media?path=...` 或 `/api/files/read?path=...` 拉 data URL。
- 音视频：使用 `hermes-media://remote/...` 流式播放，避免大 data URL 损坏或无法 seek。
- HTTP 生成媒体：先下载到本地 cache，同时尽量上传到远端 Hermes cache，记录 remote/local mapping。
- 下载单文件：renderer 调 `downloadManagedFile`，Electron main 决定本地 copy 还是 remote fetch。
- 批量下载：选择本地目标目录，逐个下载远端文件。
- 会话文件弹窗：合并消息里解析的 artifacts 和 hosted gateway `/api/sessions/{id}/artifacts` 返回的 artifacts。

## 7. 定时任务 UX 改造

关键文件：

- `apps/desktop/src/app/cron/index.tsx`
- `apps/desktop/src/app/cron/job-title.ts`
- `apps/desktop/src/app/cron/job-state.ts`
- `apps/desktop/src/i18n/*.ts`

用户不再直接写 cron 表达式。UI 提供：

- 每天。
- 工作日。
- 每周。
- 每月。
- 每小时。
- 每 15 分钟。
- 自定义模式。

UI 控件生成 5 段 cron expression，提交给后端仍是 cron。也就是说：

```text
用户看到：每天 09:00
提交后端：0 9 * * *
```

任务名称可空。保存时用 `resolveCronJobName(name, prompt, schedule)`：

- 用户填了 name 就清理并截断。
- 中文 prompt 走中文启发式。
- 英文 prompt 去停用词后 title case。
- 最大长度 32。
- fallback 是 `定时任务`。

## 8. 消息平台改造

关键文件：

- `apps/desktop/src/lib/messaging-platforms.ts`
- `apps/desktop/src/app/messaging/index.tsx`
- `apps/desktop/src/app/messaging/platform-icon.tsx`
- `apps/desktop/public/messaging-icons/*`
- `apps/desktop/src/i18n/zh.ts`

AgentOS 产品只展示这些平台，并按下列顺序排列：

- `dingtalk` -> 钉钉。
- `feishu` -> 飞书 / Lark。
- `wecom_callback` -> 企业微信（应用）；无应用模式时才回退 `wecom` -> 企业微信（群机器人）。
- `weixin` -> 微信 / WeChat（个人号）。
- `qqbot` -> QQ 机器人。

`MessagingView` 获取后端 catalog 后必须立即调用 `filterAgentOSMessagingPlatforms(result.platforms)`；只维护 helper 而页面不调用，等同于改造未完成。该函数负责过滤海外平台、企业微信去重、中文名称和固定顺序。`wecom_callback` 优先于 `wecom`。描述中 `Hermes Agent`/`Hermes` 替换为 `AgentOS`。

UI 仍复用后端返回的 env var schema，但顶部短描述必须经过 `t.messaging.platformDescription`，字段 label/help/placeholder 必须经过 `t.messaging.fieldCopy`。placeholder 的回退顺序为“中文 placeholder -> 中文 label -> 后端 prompt”，防止只配置 label 时仍显示英文。保存或开关平台后 toast 要提示重启 gateway 生效，并提供重启 action。

## 9. sudo/secret/approval 弹窗

关键文件：

- `apps/desktop/src/components/prompt-overlays.tsx`
- `apps/desktop/src/store/prompts.ts`

规则：

- sudo、secret、approval 都是后端阻塞等待的 prompt。
- 关闭 sudo 弹窗等价于拒绝，发送空 password。
- backend 返回 `no pending` 时，说明请求已经超时或释放，必须关闭 stale dialog。
- 不要让过期 sudo 弹窗留在 UI 中，否则用户会无限 cancel/send 失败。
- 不要额外加 Escape/outside handlers 造成双 respond。Radix `onOpenChange(false)` 是统一关闭入口。

## 10. 离线客户端打包和 CI

关键文件：

- `apps/desktop/package.json`
- `apps/desktop/scripts/stage-installer-script.cjs`
- `apps/desktop/scripts/stage-agent-payload.cjs`
- `apps/desktop/scripts/stage-native-deps.mjs`
- `apps/desktop/scripts/electron-builder-win.cjs`
- `apps/desktop/electron/bundled-agent.cjs`
- `apps/desktop/electron/git-review-ops.ts`
- `.github/workflows/sync-hermes-agent.yml`

最终目标：

- macOS、Windows、Linux installer 都默认带完整 agent runtime。
- 首次启动可以从 app resources seed runtime，不依赖用户现场联网安装。
- 构建阶段可以联网安装依赖。
- 发行包必须验证 payload，不允许 skip marker。

构建 manifest 必须满足：

- `schemaVersion === 2`。
- 没有 `skipped:true`。
- 没有 `bundled:false`。
- `sanitized`、`relocatable`、`pythonRuntimeBundled` 都为 `true`。
- `commit` 是有效字符串。
- `platform`、`arch` 与运行客户端严格一致。
- `build/bundled-agent/hermes-home/hermes-agent/hermes_cli/main.py` 存在。
- agent venv 的 Python 和 `hermes` console entrypoint 存在且不依赖构建机绝对路径。
- `hermes-home/bin/browser-use` 与 `hermes-home/uv-tools/browser-use` 的独立 Python 环境完整。
- payload 不包含 `.env`、云凭据、SSH key、token cache、private key block、构建机 Python 路径或 `pyvenv.cfg`。

### 应用身份、安装目录和持久化布局

- 普通发行包、Windows AUMID 和 macOS 最终 bundle id 固定为 `com.hqzyai.agentos`。旧 `com.nousresearch.hermes` 只允许出现在历史安装识别和一次性 macOS appId 桥接包中。
- Windows per-user 新装目录是 `%LOCALAPPDATA%\\Programs\\hqzy\\AgentOS`；macOS PKG/DMG 安装目录是 `/Applications/hqzy/AgentOS.app`。旧客户端自动更新优先原位覆盖，避免运行中移动自身；需要迁移应用本体时使用当前正式安装器人工覆盖。
- Windows NSIS `guid` 与 MSI `upgradeCode` 必须保留历史安装产品值，防止 appId 变化生成第二个卸载项；运行时 appId/AUMID 仍使用新值。
- macOS 旧客户端先接收版本 N 的专用旧 ID 桥接 DMG，桥接代码随后只接受 `com.hqzyai.agentos`；最终包必须使用更高版本 N+1。普通 `dist:mac` 绝不能继续生成旧 ID。
- 默认持久化根目录统一为 `{APP_DATA_DIR}/profiles/{ORG_NAME}`：`desktop/` 保存 userData、sessionData、Cookie 和登录态，`agent-data/` 是 Desktop 管理的 `HERMES_HOME`，`cache/` 保存 Electron/更新/字体缓存，`logs/electron/` 保存桌面日志，`crash-dumps/` 保存崩溃文件，`migration-backups/` 保存冲突恢复副本。
- 迁移必须发生在读取认证和连接配置之前。目标为空时原子移动；跨文件系统时先 staging 完整复制再切换；目标已有数据时目标优先、旧树整体备份后只补缺失项。失败不得删除源目录，且不得把 token、密码或完整对象存储 URL写入日志。
- 显式非默认 `HERMES_HOME` 继续生效；远程实例 `~/.hermes`、`hermes:*` IPC、更新标记和底层 `hermes` 命令属于兼容协议，不随本地发行目录改名。
- WSL fontconfig 文件和缓存进入 `cache/fontconfig`；本地 SSH ControlMaster socket 使用短期且权限受控的 `/tmp/hqzy-agentos-ssh-<uid>`，因为 macOS Unix socket 路径长度不适合放进深层持久化目录。

详细发布与恢复流程见 `05-offline-packaging-and-ci.md`，可执行验收见 `06-ai-agent-migration-checklist.md`。

## 11. 2026-07-13 至 2026-07-30 生产硬化补充

这一阶段不是独立的新产品，而是把前述功能从“开发机能运行”推进到长期运行、账号切换、
受限网络和 Windows 覆盖升级场景可用。后续智能体同步上游时，必须把以下内容视为现行
契约，不能按早期截图或旧实现回退。

### 登录、token 与连接生命周期

- 客户端启动先恢复 Electron 持久化 OAuth cookie 并完成真实 WS 握手；只有 cookie
  会话无效时才回退到 safeStorage 中的保存凭据。
- access token 过期但 refresh token 有效时，服务端刷新后的 cookie 继续由 Electron
  session 保存，用户无需重新输入密码。
- 同一登录生命周期自动恢复最多一次。再次收到明确认证过期时稳定返回登录页，不在
  登录页、白屏、通用启动失败页之间循环 reload。
- timeout、DNS、5xx、短暂空响应属于 transport failure，主界面保持可用并后台退避
  重连；401/403 才进入认证恢复。
- 账号 A 退出后登录账号 B 时推进 backend generation。账号 A 的旧 child exit/error、
  旧启动 Promise 和旧 connectionPromise 不能清理或覆盖账号 B 的状态。
- Electron response body 必须同时监听 request/response error；错误 Content-Length
  只让当前请求失败，不能形成 main process 未捕获异常弹窗。

详见 `02-auth-and-remote-gateway.md`。

### 历史会话和 server 响应性

- `session.resume` 的写失败与 messages REST 读取成功是两条请求；出现历史已显示后
  `attempt to write a readonly database` 时，应修复可写 SessionDB 的失效连接，不能
  加超时或隐藏 toast。
- 可写 SessionDB 仅在 `SQLITE_READONLY` 时在锁内重建一次失败连接；真正只读实例
  仍严格拒绝写入。
- 打开历史会话只恢复 runtime 元数据，不预热完整 AIAgent。首次发送消息再按保存的
  model/provider/reasoning/service-tier 构建，避免工具、插件、MCP 发现持有 GIL 导致
  WebSocket 和 `/api/status` 同时超时。
- Desktop 并发请求 REST transcript 与 `session.resume`；REST 身份校验通过后立即绘制，
  不等待 runtime 恢复。Bots/群聊打开 canonical Agent chat 时还要强制 front 主
  workspace，覆盖“路由已经相同、hash 不触发 effect”的重复点击场景。
- 模型目录网络发现使用 config-only profile scope；受限网络可按 profile 关闭
  `models_dev.auto_refresh` 并读取磁盘快照，相同非刷新请求使用 5 秒 single-flight。

### 产品面与品牌边界

- 模型 provider、认证入口、工具集、技能列表和 runtime discovery 都使用
  `hermes_cli/agentos_policy.py`，不能只在 desktop 页面过滤。
- 当前整体隐藏 `image_gen`、`video_gen`、`x_search`；同时隐藏 `claude-code`、
  `claude-design`、`codex`、`opencode`。这是对早期“保留少量图片/视频模型”方案的替代。
- 国内 provider 和 `custom`/私有 endpoint 保留；已知国外 slug 不能利用旧
  `is_user_defined` 标志重新出现。
- 用户可见身份、思考摘要、正文、配对回复、命令示例和系统动作统一为中文 AgentOS；
  不显示 Hermes 或 Nous Research。内部模块名、`HERMES_HOME`、兼容 API 路径可保留。
- server 更新 action 是 `agentos-update`，日志为 `agentos-update.log`；兼容路由仍可叫
  `/api/hermes/update`，但只供服务端管理面使用。Desktop 的“更新 AgentOS”始终指当前租户的客户端安装包，不得调用该兼容路由或上游 Hermes 更新源。
- Hub 技能动作运行在独立 CLI 子进程；`skills/.hub/lock.json` 的 stat signature 是
  desktop/server 跨进程技能清单 generation，负责立即刷新技能发现、下一次提示词构建和
  slash command index，不能依赖进程内 clear 或 TTL。
- 技能索引中的分类只用于组织。`skill_view` 首选精确技能名，冲突时使用斜杠分类路径，并
  对模型误拼的多级 `category/subcategory:skill` 做安全兼容；插件 namespace 与路径安全
  校验不可弱化。

详见 `04-cron-messaging-i18n-ui.md`。

### Windows 更新与 server 镜像

- 每租户构建把 HTTPS EXE 地址写入 `resources/desktop-release.json`。客户端直接访问
  对象存储，不通过 BFF 动态选择安装源。
- 元数据与下载共用 Electron session 网络栈，继承系统代理/PAC/证书；支持 HEAD
  fallback、Range 续传、有限重试/重定向/超时和完整性校验。
- 已是最新版本属于成功终态，只显示“已是最新版本”；不得同时显示红叉、更新未完成
  或重试按钮。
- Windows 原目录覆盖安装由独立 PowerShell 等待旧进程退出，NSIS 新包提供静默安装
  后自启动兜底；清除更新标记后按真实完整 EXE 路径接管或启动，并确认进程稳定至少
  5 秒后才提交成功。
- `Dockerfile` 是基于固定可用 runtime 的源码覆盖派生镜像，`Dockerfile.source-build`
  是完整依赖构建。新 tag 不修改基础镜像或其他派生镜像；测试使用独立容器、端口、
  volume 并加入现有 `agentos-network`。

详见 `05-offline-packaging-and-ci.md`。

## 12. 2026-08-17 至 2026-08-19 提交审计补充

本节记录 `agentos-20260817` 在官方同步前后新增的 AgentOS 契约。它们不是临时修补；下次
合并 release manifest 锁定的官方 tag 时，冲突和自动合并区域都必须逐项复核。

### 提交账本

| 提交 | 归属契约 | 必须保留的结果 |
| --- | --- | --- |
| `45fdcd03e` | Skill Hub 与模型错误文案 | `skills uninstall --yes/-y` 可无交互卸载；Hub 动作完成后刷新 installed、featured 和技能列表；普通超预算错误显示中文 |
| `12af38702` | 会话追踪与启动认证 | 模型请求主键为 `HERMES_SESSION_ID`，兼容头为同值 `X-LiteLLM-Session-ID`，旧 `SESSION_ID` 只读不发；认证恢复 single-flight，认证成功后才启动 backend |
| `12db7352a` | LiteLLM 限额安全 | `Rate limit exceeded for api_key` 不泄漏 key，不按普通可轮换密钥限流处理，也不进入 fallback/凭据轮换 |
| `935f3a970` | 限额时间本地化 | `Budget resets at ... UTC` 转为 `Asia/Shanghai` 后以北京时间展示 |
| `e2c4646e9` / `46059b954` | 登录与租户出包 | 账号密码仍为默认入口；显式提供飞书扫码登录给已绑定用户；BFF/下载地址由租户发行配置固化，Mac PKG/DMG 与 TOS 上传链路保留 |
| `e3dd2dfb1` | bundled runtime、远程会话、文件与语音 | manifest schema 2、自包含 Python/browser-use、凭据与构建机路径清理；多请求会话读取固定 connectionId；产物目录过滤、文件列表断链容错；被动语音探测不触发安装 |
| `e15f9c9f7` + 当前加固 | 私有 Skill Hub | 唯一 source ID 为 `nacos`、用户显示“华清严选”；server 与 renderer 双重过滤，`source=all` 仅为 Nacos 兼容别名，禁止公网 fallback |

### 模型限额错误的安全边界

- `agent/error_classifier.py` 必须把包含 `for api_key` 或 `budget has been exceeded` 的
  LiteLLM 429 识别为 provider/account 级上游限额，不能按凭据池中某一把 key 的普通
  rate limit 轮换。轮换不仅无效，还可能让所有会话重复撞同一预算限制。
- `AIAgent._summarize_api_error()` 对外只返回中文产品文案，任何 `api_key:` 后的值都不得
  出现在回复、toast 或日志摘要中。
- 能解析 `Budget resets at <UTC>` 时用 `zoneinfo.ZoneInfo("Asia/Shanghai")` 转换；不能
  解析时返回通用“模型超预算，请提高预算或更换模型后再试”，不得回显原始 provider body。

### 登录、Skill Hub 与远程会话的新增边界

- 飞书扫码只在用户选择“飞书扫码”后打开 OAuth 窗口；关闭窗口、OIDC 失败和账号未绑定
  都回到原登录页显示中文错误。成功 cookie 仍进入持久化 OAuth partition，renderer 不接触 token。
- Hub 首页、搜索、安装、预览和扫描只允许 `NacosSkillSource`；source ID 保留 `nacos`，所有
  用户可见位置显示“华清严选”。官方 index teaser 和公网结果均不得作为空目录 fallback。
- `source=all` 只映射到 Nacos；非 Nacos source/identifier 返回 400。旧 profile 配置不能重开
  公网 source，Desktop 还要过滤旧 server 返回的公网 chip、featured 和 result。
- 从一次列表查询到后续逐条 transcript hydration 必须捕获同一个 connectionId 快照。
  用户在读取期间切换网关时，旧批次继续访问原连接，不能把列表来自 A、消息来自 B。

### 离线运行时与语音探测

- schema 2 的有效 manifest 必须最后写入；任何凭据扫描、自包含 Python、entrypoint
  重写、browser-use 验证或平台/架构校验失败，都只能留下失败或 skip 状态，不能留下可被启动器误认的成功 manifest。
- `HERMES_HOME/bin/browser-use` 和 `uv-tools/browser-use` 必须随包迁移；uv 的全局工具目录
  不能进入构建结果。agent venv 与 browser-use venv 都要包含自己的解释器、标准库和依赖。
- 被动状态调用（dashboard readiness、`voice.status`、`wake.status`、requirements probe）
  只检测能力，绝不能执行 pip/uv。只有用户真正提交音频转写后才允许 lazy install；并发
  首次转写共享 single-flight，安装有明确超时，失败后允许下一次真实转写重试。
- 源码覆盖 Docker 镜像复用基础 venv 时，必须把 NumPy 对齐当前源码锁定版本后再解析
  voice/wake 可选包，避免 ABI 或依赖解析漂移。

## 13. 不应遗漏的测试点

后续迁移要至少覆盖：

- 登录错误：401/403、404、HTML、timeout、network。
- BFF -> hosted gateway cookie 安装。
- WS ticket 每次连接 fresh mint。
- refresh token 存在但 access token 过期时，不要求重新登录。
- refresh token 无效时自动走保存凭据重新认证，失败回登录页；不得停在普通 boot failure 无限重试。
- backend 首次连接发生在 `auth.getStatus()` 成功之后，不与 cookie 安装并发。
- global remote mode session list fallback。
- per-profile remote override session read/delete/rename。
- remote media image/video/audio rendering。
- remote file download single/batch。
- cron preset -> cron expression。
- empty cron name -> generated title。
- sudo `no pending` 自动关闭。
- `stage-agent-payload` skip marker fail。
- offline payload schema 2 任一安全字段缺失、平台/架构不匹配、缺 main.py/自包含 agent
  Python/Hermes entrypoint/browser-use，或残留凭据与构建机路径时 fail closed。
- 持久化 cookie 会话重启恢复，且配置与日志无明文 token/password。
- 账号切换时旧 backend 晚到事件不会让新账号首次连接失败。
- transport 断线后台恢复，不进入启动失败页；认证失效最多自动恢复一次后回登录页。
- 历史会话恢复不预构建 AIAgent；SQLite 可写连接只自愈一次，真实只读连接不升级。
- 模型目录禁用自动刷新时不访问公网；慢模型发现不阻塞 `/api/config`、`/api/status` 和 WS。
- AgentOS 产品策略同时覆盖 server API、desktop/dashboard 和 runtime discovery。
- Windows 更新使用 Electron 系统代理网络栈，已是最新为成功，安装后能自动重启并稳定存活。
- server 源码覆盖镜像使用新 tag 和隔离数据卷，不影响基础镜像、其他派生镜像或现有容器。
- 飞书扫码仅由显式选择触发，成功复用 OAuth cookie 链路，未绑定/取消回到登录页。
- `HERMES_SESSION_ID` 与 LiteLLM 兼容头同值，旧 `SESSION_ID` 不出站，并发会话不串号。
- LiteLLM 超预算错误不泄漏 api_key、不轮换凭据，UTC reset 时间转为北京时间。
- 技能 Hub 只显示“华清严选”，内部仅访问 Nacos；旧配置/旧 server、公网 miss fallback 和非 Nacos identifier 均不能绕过。
- bundled-agent schema 2 的凭据、自包含 Python、browser-use、平台/架构与 relocatable 校验全部 fail closed。
- 会话列表与 transcript hydration 固定同一 connectionId；文件列表遇到单个断链 symlink 时跳过该项且不吞权限错误。
- 被动 voice/wake/status probe 不安装 STT；并发真实转写只启动一次有界 lazy install。
