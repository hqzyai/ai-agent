# BFF 登录、Hosted Gateway 与远程会话契约

本文详细记录 AgentOS desktop 的登录和远程 gateway 契约。这是所有改造里最容易被新智能体误解的一块。必须先理解这个链路，再修改 login、settings、gateway boot、session sidebar、WebSocket、remote file 等功能。

## 1. 名词解释

### Desktop renderer

Electron 的 React 页面。它负责展示登录页、设置页、聊天页、sidebar、弹窗等。它不能直接访问 Node API，只通过 preload 暴露的 `window.hermesDesktop` 调 Electron main process。

关键文件：

- `apps/desktop/src/app/index.tsx`
- `apps/desktop/src/components/login-screen.tsx`
- `apps/desktop/electron/preload.ts`

### Electron main process

桌面壳的 Node 侧。它负责：

- 读写本地桌面配置。
- 启动或连接 backend。
- 维护 OAuth session partition。
- 安装 hosted gateway cookie。
- mint WebSocket ticket。
- 转发 renderer 的 REST 请求。
- 处理 remote file download 和本地文件 API。

关键文件：

- `apps/desktop/electron/main.ts`
- `apps/desktop/electron/auth-errors.cjs`
- `apps/desktop/electron/dashboard-token.ts`
- `apps/desktop/electron/connection-config.ts`
- `apps/desktop/electron/preload.ts`

### BFF

AgentOS 业务服务。桌面登录页只知道 BFF base URL 和账号密码。BFF 负责校验用户并返回可以安装到 hosted gateway 的 token 信息。

默认配置来源：

- `apps/desktop/config/defaults.json`
- `apps/desktop/src/config/defaults.ts`

本地默认：

```json
{
  "bffBaseUrl": "http://127.0.0.1:5001"
}
```

当前源码联调默认是 `http://192.168.2.10:5001`；裸发行构建默认写入当前正式云机 `http://115.190.254.114:5001`。两者都只是部署配置，不是协议常量。租户发行必须通过 `AGENTOS_DESKTOP_BFF_BASE_URL` 注入包含实际端口的完整 URL，由 `desktop-release.json` 随安装包交付；不得改写本地 defaults，也不要在迁移新 desktop 时复制某个历史 IP。

### Hosted gateway

BFF 下的桌面 gateway 路径。由 BFF base 派生：

```text
<BFF base>/desktop/hosted-gateway
```

如果输入已经以 `/desktop/hosted-gateway` 结尾，则不要重复追加。

相关 helper：

- `hostedGatewayUrlFromBffBase(rawUrl)`
- `bffBaseFromHostedGatewayUrl(rawUrl)`
- renderer 侧同名逻辑在 `gateway-settings.tsx`

### OAuth mode

这里的 `oauth` 不只指第三方 OAuth provider。对 desktop 来说，只要 hosted gateway 用 HttpOnly cookie + ws-ticket 认证，就归为 `authMode: "oauth"`。BFF 账号密码登录也是这个模式。

### Token mode

legacy static session token 模式。适用于一些 self-hosted 或旧 dashboard。AgentOS 产品主路径不是 token mode。

## 2. 配置文件和状态位置

### defaults.json

文件：

- `apps/desktop/config/defaults.json`

作用：

- 源码默认 BFF base URL。
- Electron main process 直接 `require("../config/defaults.json")` 读取默认 BFF base。
- renderer 通过 `apps/desktop/src/config/defaults.ts` 读取同一份 JSON。
- 当前运行时代码以 `defaults.json` 为准；不要只改 renderer 的 Vite env，因为 Electron main process 不读取 `import.meta.env`。
- CI 会直接改这个文件注入发行地址。

约束：

- renderer 和 main process 必须共用同一份配置源。
- 不要在多个 TS/JS 文件里散落硬编码 BFF 地址。
- 不要把 `/desktop/hosted-gateway` 存进 `defaults.json`，这里存 BFF base。
- 如果新 desktop 想改成纯 env 注入，必须同步改 main process 和 renderer；只设置 `VITE_AGENTOS_DESKTOP_BFF_BASE_URL` 不会改变 Electron main 的默认 BFF。
- 如果迁移过程中删掉或尚未实现 `build-clients.cjs`，不要在 `package.json` 留 `dist:clients` 断入口；优先使用 CI matrix 或明确实现后的脚本。

### auth.json

文件位置：

```text
app.getPath("userData")/auth.json
```

main process 常量：

- `DESKTOP_AUTH_CONFIG_PATH`

内容语义：

- `username`：最近登录用户名。
- `password`：通过 Electron `safeStorage` 加密后的密码。
- `bffUrl`：历史兼容字段。
- `manualLoginRequired`：是否要求用户手动登录。

注意：

- 登录成功后 `manualLoginRequired` 写为 `false`。
- 退出登录后保留账号/加密密码，但写 `manualLoginRequired: true`。
- 自动登录失败会返回 unauthenticated state，并附错误。

### connection.json

文件位置由 main process 的 desktop connection config 管理。内容大致：

```json
{
  "mode": "remote",
  "remote": {
    "authMode": "oauth",
    "token": null,
    "url": "http://.../desktop/hosted-gateway"
  },
  "profiles": {}
}
```

约束：

- AgentOS 登录成功后保存的是 hosted gateway URL，不是 BFF base。
- `remote.authMode` 是 `oauth`。
- token mode 保存 token 时要加密。
- `profiles` 保存 per-profile remote override。
- 保存 global connection 时不能清空 `profiles`。

### Electron OAuth session partition

常量：

```js
const OAUTH_SESSION_PARTITION = 'persist:hermes-remote-oauth'
```

用途：

- 登录窗口使用这个 partition。
- REST 请求通过 Electron `net` 绑定这个 session。
- cookie 是 HttpOnly，renderer 和普通 JS 不能读。
- access/refresh token 都存在 cookie jar 里。

关键 cookie：

- `hermes_session_at`：access token，短期。
- `hermes_session_rt`：refresh token，较长。

重要规则：

- access token 过期但 refresh token 还在时，不能判定为掉线。
- gateway middleware 会在下一次 authenticated request 时刷新 access token。
- `fetchJsonViaOauthSession` 必须使用同一个 persistent Electron session，并启用 `useSessionCookies:true`。服务端刷新成功后返回的新 AT/RT 由 Chromium Cookie Store 自动覆盖旧 cookie；不要把 token 读到 renderer 后自行更新。
- 认证有效性与运行时可用性必须分开判断。启动恢复先调用 BFF 的轻量
  `GET /desktop/hosted-gateway/api/auth/session`；它只验证/轮换 AT、RT，不得启动或探测运行实例。
- refresh token 也失效、被服务端重启清理或被轮换作废时，轻量认证接口或后续
  ticket 请求会返回 401/403。只有这两类明确认证拒绝才进入账号密码认证链路；
  timeout、DNS、连接拒绝和 5xx 属于连接故障，不能清 cookie 或重复提交密码。
- 运行时 liveness 由连接阶段的 ws-ticket + WebSocket 握手负责，不属于登录表单成功条件。

## 3. 登录请求链路

### Renderer 入口

文件：

- `apps/desktop/src/components/login-screen.tsx`

登录方式：

- 默认选中 `password`，展示 `username` 和 `password`。
- main process 必须先读取 BFF 的公开 `GET /auth/login-options`，再把可用方式通过
  `DesktopAuthState.loginMethods` 交给 renderer；renderer 不得根据是否存在飞书代码静态展示入口。
- `password_login_enabled !== false` 时展示账号密码；旧 BFF、接口超时、404 或响应格式错误时
  fail closed 为“仅账号密码”，保证登录页可用且不会展示未经服务端确认的 SSO 能力。
- 只有 `oidc_enabled:true` 且 `default_tenant_configured:true` 时才展示飞书扫码。Desktop 没有
  tenant slug 输入框，缺少默认租户时即使 OIDC 服务存在也不能展示一个必然失败的入口。
- 用户显式切换到 `feishu` 后才允许打开扫码 OAuth 窗口；main process 在清 cookie、打开窗口前
  必须再次校验能力，防止旧 renderer 或伪造 IPC 绕过 UI 门禁。仅已绑定 AgentOS 的飞书账号可登录。

调用：

```ts
const next = await window.hermesDesktop.auth.login({
  username: username.trim(),
  password
})

// 用户点击飞书扫码登录时
const next = await window.hermesDesktop.auth.login({ method: 'feishu' })
```

当前 IPC 以 `method === 'feishu'` 进入扫码流程；未传 `method` 等价于密码流程，保持旧 renderer 兼容。

submit 规则：

- username trim 后不能为空。
- password 不能为空。
- busy 时禁止重复提交。
- preload auth bridge 不存在时，提示 `桌面登录桥接不可用。请重新启动客户端。`
- 飞书扫码窗口被关闭时提示 `已取消飞书登录。`；OIDC 失败或未绑定时提示
  `飞书账号未绑定 AgentOS，无法登录客户端。`，错误必须留在当前登录页。
- 过期 OAuth/飞书会话返回的 `invalid refresh token`、`session expired` 或普通认证 401 必须提示
  `登录已过期，请重新登录。`；不得因为错误字符串中带 401 就误报为用户名或密码错误。
- 只有 BFF 密码接口明确返回 `invalid credentials`、`invalid username or password` 或已经归一化的
  `用户名或密码错误。`，才显示密码错误。普通 403 显示服务端拒绝，不得掩盖账号禁用或策略错误。

### Preload IPC

文件：

- `apps/desktop/electron/preload.ts`

暴露：

```js
auth: {
  getStatus: () => ipcRenderer.invoke('hermes:auth:status'),
  login: payload => ipcRenderer.invoke('hermes:auth:login', payload),
  logout: () => ipcRenderer.invoke('hermes:auth:logout')
}
```

迁移新 desktop 时，renderer 不应直接调用 BFF。账号密码和 cookie 安装必须在 main process 中完成，因为 cookie 是 Electron session 级能力。

### Main process 登录

文件：

- `apps/desktop/electron/main.ts`

主函数：

- `signInWithDesktopPassword(payload, options)`
- `signInWithDesktopFeishu()`
- `postBffPasswordLogin(bffUrl, username, password)`
- `installHostedGatewayAuthCookies(hostedGatewayUrl, authResponse)`
- `verifyDesktopHostedGatewaySession(hostedGatewayUrl)`
- `saveHostedGatewayConnectionConfig(hostedGatewayUrl)`

链路：

```text
signInWithDesktopPassword
  -> configuredDesktopBffBaseUrl()
  -> hostedGatewayUrlFromBffBase(bffUrl)
  -> writeDesktopAuthConfig(manualLoginRequired: true, 保留上一次已验证的加密密码)
  -> clearOauthSession(hostedGatewayUrl)
  -> postBffPasswordLogin(bffUrl, username, password)
  -> installHostedGatewayAuthCookies(hostedGatewayUrl, authResponse)
  -> saveHostedGatewayConnectionConfig(hostedGatewayUrl)
  -> writeDesktopAuthConfig(manualLoginRequired: false)
  -> teardownPrimaryBackendAndWait()
  -> desktopAuthPublicState({ authenticated: true })
```

用户手动提交的新密码只能在 BFF 登录成功后写入 `auth.json`。提交前把
`manualLoginRequired` 标为 true 是为了防止失败后重启继续自动认证，但不得提前用尚未验证的密码
覆盖安全存储中的旧凭据；否则一次输错会永久破坏原本可恢复的有效凭据。

飞书扫码链路：

```text
LoginScreen method=feishu
  -> hermes:auth:login({ method: 'feishu' })
  -> signInWithDesktopFeishu()
  -> clearOauthSession(hostedGatewayUrl)
  -> openOauthLoginWindow(hostedGatewayUrl)
  -> BFF/飞书 OIDC 在 persist:hermes-remote-oauth 中写入 HttpOnly AT/RT cookie
  -> hasLiveOauthSession(hostedGatewayUrl)
  -> saveHostedGatewayConnectionConfig(hostedGatewayUrl)
  -> writeDesktopAuthConfig(manualLoginRequired:false, password:null)
  -> teardownPrimaryBackendAndWait()
  -> desktopAuthPublicState({ authenticated:true })
```

扫码登录不能复用密码提交 API，也不能把飞书 token、BFF token 或 OAuth callback 参数传给
renderer。它与密码登录只在“如何建立持久化 cookie”这一步不同，后续 hosted gateway、
ws-ticket、WebSocket 和退出登录链路完全一致。扫码成功后清空保存密码，防止下一次明确
认证失效时错误地用上一个账号的旧密码自动登录。

### 登录错误文案当前状态

文件：

- `apps/desktop/electron/auth-errors.cjs`
- `apps/desktop/electron/main.ts`

注意：

- `auth-errors.cjs` 定义了更完整的 `bffLoginErrorMessage` 和 `looksLikeHtml`。
- `auth-errors.test.cjs` 覆盖 JSON detail、401/403、404、HTML、长错误等情况。
- 但当前 `main.ts` 里仍有一份本地 `bffLoginErrorMessage` 实现，`postBffPasswordLogin` 调的是本地函数，不是直接复用 `auth-errors.cjs`。
- 因此迁移时不能误以为登录链路已经统一引用了 `auth-errors.cjs`。

推荐迁移规则：

- 新 desktop 应只保留一个登录错误归一化入口。
- main process 登录链路、测试和 renderer 展示应共享同一套错误语义。
- HTML 错误页、404 登录接口不可用、超长非 JSON 响应都不能原样透给登录页。
- renderer 的二次归一化不得用 `/401|403/` 判断“密码错误”。refresh token 失效发生在密码提交
  之前，也会携带 401；把它归到密码错误会造成“飞书登录把密码弄坏了”的假象。

### BFF login endpoint

main process 拼接：

```text
<BFF base>/auth/login
```

请求：

```http
POST /auth/login
Accept: application/json
Content-Type: application/json

{
  "username": "...",
  "password": "..."
}
```

期望响应至少包含：

- `access_token`
- `refresh_token`
- `expires_in_seconds` 可选，默认 900 秒。
- `refresh_expires_in_seconds` 可选，默认 86400 秒。

### Hosted gateway cookie 安装

`installHostedGatewayAuthCookies` 设置：

- `httpOnly: true`
- `sameSite: "lax"`
- `secure` 取决于 hosted gateway URL 是否是 https。
- `url` 是 hosted gateway URL。
- `path` 使用 `hostedGatewayCookiePath(hostedGatewayUrl)`，确保 cookie path 与 `/desktop/hosted-gateway` 匹配。

不要把 token 交给 renderer，也不要用 localStorage 存。

### 认证检查与运行时就绪分层

登录 BFF 成功不代表用户的运行实例已经就绪，但不能因此让登录请求等待实例冷启动。
完整链路分三层：

```text
认证恢复：GET  <hosted gateway>/api/auth/session
连接准备：POST <hosted gateway>/api/auth/ws-ticket
真实连接：WS   <hosted gateway>/api/ws?ticket=<single-use ticket>
```

`/api/auth/session` 的唯一职责是校验 hosted-gateway cookie，并在 RT 有效时轮换
AT/RT。BFF 实现不得调用 `get_dashboard_endpoint_async()`，否则每次客户端启动和每次
`auth.getStatus()` 都会被实例冷启动、修复锁或 OpenSandbox 探测阻塞。

`/api/auth/ws-ticket` 属于连接阶段。BFF 可以在这里调用
`get_dashboard_endpoint_async()`，确保上游 dashboard 已就绪后再签发一次性 ticket。
Desktop 首次连接只发起一个具有完整恢复预算的 ticket 请求：当前初始超时为 120 秒，
普通重连/刷新 ticket 为 30 秒。不能恢复成 8 秒超时再重试 3 次；服务端冷启动允许约
29 秒、修复流程最长可达约 90 秒，短超时只会取消客户端等待并制造重复唤醒请求。

WebSocket upgrade 和 `gateway.ready` 仍是最终可用性依据，但失败由连接状态机处理，
不是把已成功的账号密码登录改判为失败。只有 session/ticket 明确返回 401/403 时才
进入登录页；网络故障、5xx 或运行时尚未就绪应显示连接/恢复状态并允许重试。

### BFF 到 OpenSandbox dashboard 的完整代理约束

hosted gateway 的 HTTP 与 WebSocket 最终都要经过 BFF 访问用户默认运行实例的 dashboard。生产 OpenSandbox endpoint 常见形态为：

```text
<host>:<dynamic-port>/proxy/8642
```

BFF 可以把 runtime endpoint 派生为 `<host>:<dynamic-port>/proxy/9119`，但不能只替换端口路径。必须同时调用 OpenSandbox `get_sandbox_endpoint_detail(sandbox_id, 9119)`，保留响应中的 `OpenSandbox-Secure-Access` 等安全访问 headers，再补充 `Host: 127.0.0.1:9119` 和 `X-Forwarded-Prefix`。丢失安全 header 时，运行实例即使显示 `ready`、lazy-start API 也返回 200，dashboard HTTP 与 WS 仍会在 BFF 侧报 500。

兼容旧 OpenSandbox 时，endpoint detail 不可用可以回退到无安全 header 的派生地址；但生产验收必须实际访问 dashboard 根路径、`/api/sessions` 和 `/api/ws`，不能用数据库中的 `instance.status=ready` 或 BFF 的公开 `/api/status` 代替链路验证。

## 4. WebSocket 认证

### OAuth/password 模式

WebSocket 不使用 `?token=`。它使用单次 ticket：

```text
POST /api/auth/ws-ticket
  -> { ticket: "..." }

WS /api/ws?ticket=<ticket>
```

ticket 特性：

- 单次使用。
- TTL 短。
- 每次 reconnect 前必须 fresh mint。
- BFF 签发前可以等待目标 runtime ready，因此客户端初次请求的超时必须覆盖服务端
  冷启动和一次修复预算，且不能用多个短请求并发/循环轰击同一个实例。

关键函数：

- `mintGatewayWsTicket(baseUrl)`
- `freshGatewayWsUrl(profile)`
- `buildGatewayWsUrlWithTicket(baseUrl, ticket)`

renderer 每次连接前调用：

```ts
window.hermesDesktop.getGatewayWsUrl(profile)
```

不要缓存 OAuth mode 下的 `wsUrl` 长时间复用。第二次连接可能因为 ticket 已使用或过期失败。

### Token 模式

legacy token mode 用：

```text
WS /api/ws?token=<session_token>
```

token mode 下还会尝试刷新远端 gateway token：

- 读取 gateway index HTML。
- 提取 `window.__AGENTOS_DASHBOARD_SESSION_TOKEN__`。
- 兼容旧变量 `window.__HERMES_SESSION_TOKEN__`。
- 两个变量同时存在时必须优先采用 `__AGENTOS_DASHBOARD_SESSION_TOKEN__`；旧变量只能作为兼容回退，不能覆盖 BFF 注入的新 token。
- 如果 served token 和当前 token 不同，可保存刷新后的 token。

关键文件：

- `apps/desktop/electron/dashboard-token.ts`

### Foreign backend 防护

本地 dashboard token discovery 有一个重要安全/正确性规则：

如果 child process 已死，但 `baseUrl /` 上仍有另一个进程返回不同 token，这可能是 orphan 或 port squatter。此时不能采用它的 token，应报错：

```text
<label> exited and <url>/ is served by a process we did not spawn; refusing its session token.
```

这避免 desktop 连接到不是自己启动的 backend。

## 5. REST 请求认证

renderer 对 gateway REST 的统一入口：

```ts
window.hermesDesktop.api({ path, method, body, profile, timeoutMs })
```

preload：

```js
api: request => ipcRenderer.invoke('hermes:api', request)
```

main process：

```js
ipcMain.handle('hermes:api', async (_event, request) => { ... })
```

### OAuth mode REST

走：

```js
fetchJsonViaOauthSession(url, opts)
```

特点：

- 使用 Electron `net.request`。
- 绑定 `session: getOauthSession()`。
- `useSessionCookies: true`。
- cookie 自动附加。
- 响应必须是 JSON。
- HTML 响应视为错误。
- Electron `net.request` 的 request 和 response 是两个独立的错误事件源，必须同时监听。
- response 读取必须监听 `data`、`end` 和 `error`。代理截断响应、服务端声明的 `Content-Length` 与实际字节数不一致时，Electron 会从 response 抛出 `net::ERR_CONTENT_LENGTH_MISMATCH`；缺少监听器会直接触发主进程 `uncaughtException` 和系统 JavaScript 错误弹窗。
- response 流错误应 reject 当前 REST/WS-ticket 请求，交由已有连接重试逻辑处理，不能让主进程退出，也不能误判为 OAuth 登录过期。

### Token/local mode REST

走：

```js
fetchJson(url, connection.token, opts)
```

通常通过 header 传 session token。这个模式不要扩展为 AgentOS 主路径。

## 6. Settings gateway 页面

文件：

- `apps/desktop/src/app/settings/gateway-settings.tsx`

当前常量：

```ts
const LOCKED_GATEWAY_SETTINGS = true
```

含义：

- 当前 AgentOS 版本固定使用远程账号密码登录。
- 设置页展示的是 BFF 调用地址。
- 本地 gateway 选项禁用。
- remote token 输入禁用或不展示。
- 保存 payload 时把 BFF base 转成 hosted gateway URL。

UI 文案：

- 标题显示 gateway 设置，但带 `账号密码登录` pill。
- URL label 是 `BFF 调用地址`。
- 描述说明客户端会自动使用 `/desktop/hosted-gateway` 连接远程网关。

### URL 转换

renderer 侧有两个 helper：

- `bffBaseFromRemoteUrl(rawUrl)`
- `hostedGatewayUrlFromBffBase(rawUrl)`

必须和 main process 侧语义一致。

Settings 显示时：

- 如果保存的是 hosted gateway URL，展示 BFF base。

保存/测试时：

- 把 BFF base 转成 hosted gateway URL。

## 7. Auth mode probe

虽然当前 `LOCKED_GATEWAY_SETTINGS = true` 时 probe 不运行，但通用逻辑仍保留。

函数：

- main process `probeRemoteAuthMode(rawUrl)`
- renderer `probeConnectionConfig(trimmedUrl)`

探测：

- `GET /api/status`
- 如果 `auth_required` 表示 OAuth gate 开启，则 `authMode: "oauth"`。
- 如果 public status 表示无需 OAuth，则 `authMode: "token"`。
- gated gateway 可额外读取 `/api/auth/providers` 获取 provider display name 和 `supports_password`。

约束：

- 网络失败返回 `reachable:false`，不要抛给 UI 崩溃。
- provider list 是可选 metadata，失败不影响 authMode。

## 8. 自动登录和退出登录

### getDesktopAuthState

启动时调用：

```text
hermes:auth:status -> getDesktopAuthState()
```

行为：

- 如果 `manualLoginRequired`，返回 unauthenticated；这是用户明确退出登录或手动登录尚未成功的硬阻断，不得自动恢复。
- 普通重启先检查持久化 OAuth partition 中是否仍有 AT 或 RT cookie；有 cookie 时调用
  轻量 `/api/auth/session`，由 BFF 验证并按需轮换 token，不等待运行实例。
- 轻量接口明确返回 401/403，或本地根本没有 AT/RT cookie 时，才使用安全存储中的
  username/password 自动登录。
- 轻量接口 timeout、DNS、连接拒绝、409 或 5xx 时保留本地 session，先返回
  authenticated，让连接状态机负责报告和重试服务故障；不得清 cookie 后再做一次慢密码登录。
- main process 的 `getDesktopAuthState` 必须使用 single-flight；窗口预启动和 renderer
  的 `auth.getStatus()` 并发到达时共享同一个 Promise，不能同时清/装 cookie 或重复提交密码。
- 没有保存凭据时返回 unauthenticated。
- 自动登录失败返回 unauthenticated 并记录脱敏 error，但不能把 `manualLoginRequired` 永久改成 true；否则一次启动瞬时网络故障会让以后每次启动都要求重新输入密码。当前 renderer 生命周期会停在登录页，下一次完整启动可以重新尝试。
- 手动登录流程仍在开始时写 `manualLoginRequired:true`，完整安装新 AT/RT 并保存 remote
  配置后写回 false；登录成功不等待 runtime 冷启动。密码登录或自动换新 token 后必须
  teardown/reset 旧 primary backend failure，避免新凭据继续复用旧账号锁存的连接失败。
- 登录表单只有收到 `authenticated:true` 才能挂载主界面。IPC 抛出认证错误或返回带 `error` 的 `authenticated:false` 状态时，都必须把规范化错误显示在登录表单内；不得继续连接 gateway，也不得落入“AgentOS 无法启动”通用恢复页。

### 启动顺序与 token 过期恢复

启动顺序是认证正确性的组成部分：

1. renderer 的 `hermes:auth:status` 与 Electron 窗口的后台预启动都调用同一个
   single-flight `getDesktopAuthState()`。
2. `getDesktopAuthState()` 先用轻量 session API 验证 Electron 持久化 OAuth 会话；
   只有明确失效时才用安全存储中的账号密码换取并安装最新 AT/RT。
3. 只有共享认证结果为 `authenticated:true`，Electron 才允许调用 `startHermes()`；
   renderer 也只有此时才挂载 `ContribController`。
4. Electron 可以在 renderer 加载期间提前开始已认证 backend 连接，但绝不能在认证
   Promise 完成前启动。renderer 后续的 `getConnection()` 必须复用同一个 backend Promise。

禁止在 `createWindow()` 或 `did-finish-load` 中无条件调用 `startHermes()`。无认证门禁的
预启动会与 cookie 恢复竞争，并可能先把旧 token 的 `backendStartFailure` 锁死。

连接期间的恢复分两级：

- AT 过期、RT 有效：`POST /api/auth/ws-ticket` 触发服务端刷新，Electron session 自动接收 `Set-Cookie`，当前连接继续。
- RT 无效或服务端返回 401/403：`useGatewayBoot` 只触发共享的 desktop auth refresh，不得直接调用 `window.location.reload()`。顶层 `App` 临时卸载 `ContribController`、展示稳定的登录检查页并重新执行一次 `auth.getStatus()`。保存凭据仍有效时自动换取新 token 并重新挂载客户端；自动登录失败时 `manualLoginRequired:true` 保持生效，客户端停在登录页，由用户稍后重新登录。如果 `auth.getStatus()` 返回 `authenticated:true`，但重新挂载后的 gateway 仍立即报告认证过期，说明自动恢复没有真正建立可用连接：同一登录生命周期不得再次调用 `auth.getStatus()`，必须直接稳定停在登录页。只有用户手动登录成功后，才重置这次自动恢复额度。

Electron IPC 会把 main process Error 包装为 `Error invoking remote method ...`，并可能丢失 `needsOauthLogin` 自定义字段。因此 `isGatewayReauthRequired` 必须同时支持：

- `GatewayReauthRequiredError`。
- `{ needsOauthLogin:true }`。
- 明确的序列化消息 `remote gateway session has expired / needs to be refreshed / uses OAuth, but you are not signed in`。

消息匹配必须保持窄范围。timeout、DNS、连接拒绝和 5xx 是传输/服务故障，不能误判成 token 过期并强制回登录页。

禁止在 gateway boot/reconnect 的认证过期分支直接 `window.location.reload()`。如果认证状态没有在 reload 前落盘改变，每次启动都会再次得到同一过期错误，形成“失败页闪现 -> renderer 白屏 -> 再次失败”的无限循环。认证恢复必须由顶层状态切换完成：

1. gateway hook 将自身标记为 cancelled，停止重连定时器。
2. 递增共享 auth refresh atom。
3. 顶层 `App` 卸载 `ContribController`，显示 `PageLoader`。
4. `auth.getStatus()` 在同一登录生命周期只允许自动重新认证一次，顶层用持久于 `ContribController` 重挂载的状态记录是否已尝试。
5. 自动认证返回失败时直接渲染 `LoginScreen`；即使自动认证返回成功，只要新挂载的 gateway 再次报告认证过期，也直接渲染 `LoginScreen`，不得开始第二轮自动认证。
6. 用户在 `LoginScreen` 手动登录成功后才清除“已自动尝试”状态；整个过程不 reload renderer。

### logoutDesktopPasswordAuth

退出登录：

1. 清 hosted gateway OAuth session cookies。
2. 写 `manualLoginRequired: true`，保留账号和加密密码。
3. connection config 改回 local，保留 per-profile overrides。
4. teardown primary backend。
5. 返回 unauthenticated state，并带 BFF base。

UI 入口：

- 设置页“网关连接”必须保留退出登录。
- 底部 statusbar 的“网关”弹窗也必须提供退出登录按钮，直接调用 `window.hermesDesktop.auth.logout()`；成功后主进程会 reload 并回到账号密码登录页，renderer 不要另写一套清登录态逻辑。

### 账号切换时的 backend 生命周期隔离

退出账号再登录另一个账号是一次完整的 primary backend re-home，不是普通的
WebSocket reconnect。旧账号的 backend、启动 Promise 和退出事件可能在新账号登录
后才完成，所以不能只把 `connectionPromise` 和 `hermesProcess` 设为 `null` 就认为
旧生命周期已经消失。

必须满足以下实现约束：

- main process 维护一个递增的 primary backend generation；退出登录、登录成功后的
  backend 重置、profile 切换和手动重试都必须推进 generation。
- 每次 `startHermes()` 捕获自己的 generation。所有跨 `await` 的关键阶段（解析
  backend、等待远程就绪、解析本地 runtime、等待本地端口、等待服务 ready、采用
  served token）返回前都要确认仍是当前 generation。
- 本地子进程的 `error`、`exit` 和 `childAlive` 回调必须同时校验 generation 和
  子进程对象身份。旧 child 的晚到事件不得清空新 child、清空新
  `connectionPromise`、发送新账号的 `backend-exit`，或覆盖当前 boot error。
- 旧启动 Promise 的 catch 只能向它原来的调用方结束；如果 generation 已变化，
  不得写入当前 `backendStartFailure`、boot progress 或 `connectionPromise`。
- teardown 必须先使旧 generation 失效，再停止旧 child，并等待 child 退出；等待
  超时也不能允许旧回调污染后续登录。
- 登录成功后 renderer 才能挂载 `ContribController`。新账号第一次连接只能读取
  新写入的 hosted gateway connection config，不能复用旧账号的 connection
  descriptor 或旧 ticket。

典型错误表现是：退出登录后第一次登录看到“AgentOS 无法启动”或
“backend exited before it became ready”，日志中先出现远程 backend ready，随后又
启动旧的本地 Python；点击“重试”后恢复。这个现象必须按 lifecycle race 排查，不能
通过增加固定延时或让用户多点一次重试来掩盖。

自动化验收：

1. 登录账号 A，确认主界面和 gateway 正常。
2. 退出登录，确认旧 backend 已 teardown。
3. 登录账号 B，并在旧 child 退出事件延迟到达的情况下启动新连接。
4. 确认第一次进入主界面无需点击“重试”，连接目标是账号 B 的 hosted gateway。
5. 确认旧 child 的退出日志不会把 boot 状态改成失败，不会触发错误弹窗，也不会
   把新连接切回 local backend。
6. 重复 A -> B -> A 至少三次，确认没有闪烁、白屏、旧账号数据或旧账号会话。

实现参考：

- `apps/desktop/electron/main.ts`：`primaryBackendGeneration`、
  `resetHermesConnection()`、`startHermes()`。
- `apps/desktop/electron/backend-lifecycle.test.cjs`：生命周期隔离回归检查。

### 已启动客户端的远程网关断连恢复

已完成首次启动的客户端与首次启动失败的客户端必须区别处理。远程网关在运行
过程中可能因为服务重启、网络切换、代理返回空响应或短暂超时而不可达；这不
代表本地 AgentOS 安装损坏，也不应把主界面改成“AgentOS 无法启动”。

要求如下：

- `hermes:connection:revalidate` 发现远程 `/api/status` 暂时不可达时，只丢弃
  旧的远程 connection descriptor，并将当前 generation 标记为 recoverable
  reconnect。
- recoverable reconnect 不得重置已完成的 boot progress，不得显示首次启动的
  全屏连接页，也不得写入 `backendStartFailure` 或 `boot.error`。
- 后续 `startHermes()` 失败只记录日志并清空当前失败的 Promise，交给 renderer
  现有指数退避循环继续重试；成功后清除 recoverable 标记并恢复正常网关状态。
- 真实的首次启动、安装失败、凭证错误和 OAuth 过期仍然走原有错误页或重新登录
  流程，不能用“后台重连可恢复”规则掩盖配置错误。
- 远程重连期间主界面、设置、退出登录和草稿必须保持可访问；连接恢复后不得
  重新加载页面或丢失当前会话。

验收场景：

1. 登录并保持客户端主界面运行。
2. 让远程网关短暂返回空响应、连接重置或超时，然后恢复服务。
3. 确认客户端不进入“AgentOS 无法启动”页面、不需要点击“重试”，并自动恢复
   WebSocket。
4. 让远程网关持续不可达，确认客户端仍保留主界面和设置入口，后台按退避策略
   重试；只有明确的认证失效才要求重新登录。

实现参考：`electron/main.ts` 中的 `primaryBackendRecoveryGeneration`、
`resetHermesConnection({ preserveBoot: true, recovery: true })` 和
`startHermes()` 的 `recoverableReconnect` 分支；回归检查与生命周期测试共用
`backend-lifecycle.test.cjs`。

### Runtime 与 VS Code 共享卷的数字身份契约

AgentOS runtime sandbox 与 VS Code sandbox 会把同一个 profile 数据卷挂载到
`/opt/data`。Unix 数据卷记录的是数字 UID/GID，不是容器内的用户名，因此两个
镜像中的服务账号必须使用相同数字身份：

- runtime：`hermes = 10000:10000`
- VS Code：`vscode = 10000:10000`
- `deploy/ai-agent/Dockerfile` 必须在构建时断言上游基础镜像中的 `hermes`
  仍为该身份；上游 UID 漂移时构建应立即失败。
- `deploy/visual-studio-code/Dockerfile` 必须显式创建相同 UID/GID 的 `vscode`
  用户，不得依赖 Debian `useradd -r` 动态分配系统 UID。
- runtime 可以在主服务启动前执行一次受控的旧卷权限迁移；VS Code、browser
  等伴生容器不得在 runtime 已运行时递归执行 `chown -R /opt/data` 或
  `find /opt/data ... chmod`。伴生容器只能修改自己的子目录，例如
  `/opt/data/.code-server`。

违反该契约时，VS Code 启动脚本可能把整个卷改为动态 UID（例如 `999:999`），
随后 runtime 无法读取 mode `640` 的 `config.yaml`，也无法追加 mode `644` 的
`gateway.lock` 或轮转 gateway 日志。直接结果是 gateway 被 s6 反复拉起、
`/api/status` 因 `PermissionError` 变慢或失败、容器 CPU 持续升高，最终触发
客户端远程重连。历史会话加载只是让问题更容易被用户观察到，不是根因。

服务端排查顺序：

1. 确认 runtime 与 VS Code 是否挂载同一个 profile volume。
2. 分别执行 `id hermes`、`id vscode`，比较数字 UID/GID。
3. 检查 `/opt/data/config.yaml`、`gateway.lock`、`state.db` 和 gateway 日志的
   数字属主及 mode。
4. 查看 gateway 日志中是否有 `PermissionError`，并观察 gateway PID 是否频繁
   变化。
5. 修复后持续调用 runtime `http://127.0.0.1:9119/api/status`；要求返回 `200`、
   `gateway_running=true`，且 PID 与属主在至少十分钟内保持稳定。

客户端必须把服务端暂时不可达当作 post-boot recoverable reconnect：指数退避
继续运行，超过持续失败阈值后只显示一个持久警告和手动“重试”操作，不得写入
`boot.error` 或显示“AgentOS 无法启动”。连接恢复后应自动关闭该警告。只有首次
启动失败或明确认证失效才进入恢复页/登录页。

### 历史会话恢复、SQLite 长连接与智能体按需构建

desktop 打开历史会话时会并发执行两个请求：

1. REST `GET /api/sessions/{id}/messages` 读取并尽快展示历史消息。
2. WebSocket `session.resume` 调用 `SessionDB.reopen_session()`，把会话重新
   标记为活跃并注册一个可继续对话的 runtime session。

这两个请求不仅要并发发起，也必须独立完成各自的用户可见职责。REST 消息页返回后，
renderer 先校验响应中的 `session_id` 与当前目标一致（兼容旧服务端省略该字段），
随后立即把历史消息绘制到已选中的会话；不得继续等待 `session.resume`。后者可能还在
恢复 runtime、工具或技能环境，但只能影响输入框何时可继续发送，不能阻塞已经可读的
持久历史。runtime 随后返回时以增量方式合并 live projection；没有 live projection 时
应复用 REST 已绘制的消息数组，避免长会话重复构建 DOM。

从 Bots、群聊或其他插件页面打开 Agent 的 canonical chat 时，`intent: main` 除了写入
session 路由，还必须主动把 `workspace` pane 置前。同一个 Agent 被再次点击时 URL hash
可能完全不变，路由 effect 不会再次运行；只改路由会让插件页继续盖在主会话上，随后
SDK 即使收到了历史也会在用户看不见的主 pane 中等待并最终误报超时。

因此“历史消息已经显示，但顶部又弹出 `resume failed`”不是客户端重复加载：
前一个只读请求成功，后一个写请求失败。不得通过延长客户端超时、重复请求历史
消息或隐藏错误来掩盖它。

2026-07-29 在实例 `inst_bf892ad9d396` 上确认了两个独立根因：

- 目标会话仅 6 条消息、约 291 字节，排除历史数据量问题。旧 dashboard 进程
  对同一 `state.db` 执行 `session.resume` 会立即返回
  `attempt to write a readonly database`；新 dashboard 进程使用同一文件可在
  约 0.1 秒内成功，证明文件未损坏，旧进程持有的 SQLite 写连接已经失效。
- 冷恢复返回后原实现会用 50ms timer 预构建完整 AIAgent。工具、插件、MCP 和
  prompt 发现虽然在 Python worker thread 中执行，仍可能长时间持有 GIL。
  隔离诊断中，恢复返回后连续 4 次 `/api/status` 均在 2 秒超时，预构建结束后
  又恢复到约 30ms。它会让 WebSocket 心跳、历史会话恢复和 hosted gateway
  健康检查同时超时。

实现必须遵守以下契约：

- `SessionDB._execute_write()` 遇到 `SQLITE_READONLY` 时，只允许可写
  `SessionDB` 在锁内重建一次连接并重试原事务。必须比较失败连接的对象身份，
  避免并发写线程重复替换连接。
- 通过 `mode=ro` 创建的聚合查询连接永远不得自动变成可写连接。真实只读挂载
  在重建后仍失败时必须向上返回错误，不能无限重试。
- 普通 `session.resume` 只执行 reopen、历史读取、runtime session 注册和返回；
  不得在用户只是浏览历史记录时调度 `_schedule_agent_build()`。
- Desktop 的 REST transcript prefetch 一旦返回且身份匹配，必须在
  `session.resume` Promise 未完成时就可见；禁止把“历史已加载”与“runtime 已绑定”
  串行化。对于声明 `expectHistory` 的插件打开动作，hydration 以目标 profile、目标
  stored session 和非空 transcript 同时匹配为准；明确空会话才等待 runtime。
- `intent: main` 必须同时导航和 front workspace，且重复打开当前路由也要生效。
- 用户第一次发送消息或执行真正依赖 agent 的操作时，通过 `_sess()` 调用
  `_start_agent_build()`，并沿用恢复会话中保存的 model/provider/reasoning/
  service-tier 覆盖值。
- `session.create` 可以保留响应后的预热，因为新会话通常紧接着会发送消息；
  该规则不能重新扩展到历史会话浏览。
- VS Code entrypoint 只可递归修正 `/opt/data/.code-server` 和自己的 home，
  不得触碰 `state.db`、`state.db-wal`、`state.db-shm`、sessions、skills 或
  其他 runtime 正在使用的数据。

回归验证至少包括：

1. 创建可写 `SessionDB` 后，将内部连接替换为同一路径的 `mode=ro` 连接；
   `reopen_session()` 应自动重连并成功，后续写入仍正常。
2. 直接创建 `SessionDB(read_only=True)` 后写入，仍应抛出 readonly 错误，连接
   对象不得被替换。
3. 普通 `session.resume` 返回完整消息和 lazy info，但不得调用
   `_schedule_agent_build()`；首次 agent 操作仍能按需构建。
4. 同时启动 runtime 和 VS Code 后重复打开历史会话，`state.db*` 数字属主和
   mode 不变，`/api/status` 无连续超时，WebSocket 不断开。
5. 客户端不再出现“历史已显示后恢复失败”，也不会在打开历史会话数分钟后进入
   “AgentOS 无法启动”页面。
6. 将 `session.resume` 保持为 pending，同时让 REST 返回 500 条历史；主消息区应立即
   显示 500 条，待 resume 返回后仍为同一份历史，不发生清空或重复。
7. 在群聊/Bots 页面连续两次点击同一 Agent；即使第二次 session route 未变化，也应
   立即切到主 workspace，不得停留在群聊页并弹出“Timed out loading ... history”。

### 模型目录发现不能阻塞 dashboard 和 hosted gateway

历史会话卡顿并不只来自 session 恢复。模型选择器、命令中心或配置页可能并发请求
`/api/config` 和 `/api/model/options`；模型目录构建又可能访问 `models.dev`、自定义
provider 或公共 DNS。如果这段网络 I/O 持有 `_profile_scope()` 使用的进程级 skills
锁，FastAPI/ASGI 事件循环中的其他配置请求也会等待，同一实例会表现为 dashboard
长时间转圈、WebSocket 心跳失败、desktop 误报远程网关断开。

当前实现必须保留以下隔离：

- `/api/config` 和 `/api/model/options` 使用 `_config_profile_scope(profile)`，只设置
  profile 上下文，不在模型 DNS/HTTP 探测期间持有进程级 skills 锁。不要为了统一
  scope 又换回 `_profile_scope()`。
- `config.yaml` 的 `models_dev.auto_refresh` 是 profile-scoped 行为配置。受限网络、
  私网或离线实例设为 `false` 时，`agent/models_dev.py` 直接读取内存或磁盘快照，
  即使调用方传 `force_refresh=True` 也不得发公共网络请求。
- `auto_refresh` 未显式关闭时维持上游默认 `true`，避免普通联网部署永远使用陈旧目录。
- `/api/model/options` 的非显式刷新请求使用 `_singleflight_model_options`：同一参数的
  并发构建复用结果，结果仅缓存 5 秒，最多保留 32 个 key。`refresh=true` 必须绕过
  short cache，执行用户主动要求的刷新。
- single-flight 只合并目录构建，不能把不同 profile、不同参数或显式刷新混在一起；
  返回数据仍必须经过 AgentOS model/provider 产品策略过滤。

诊断时按下面顺序分离问题：

1. 直接请求 `/api/status`、`/api/config`、`/api/model/options` 并分别记录延迟。
2. 临时把目标 profile 的 `models_dev.auto_refresh` 设为 `false`，确认模型目录是否
   立即从磁盘快照返回；若恢复，根因是公共网络发现，不是会话消息量。
3. 并发请求 `/api/model/options?refresh=false`，确认一次构建后其他请求复用结果；
   再用 `refresh=true` 验证主动刷新不读取 5 秒 short cache。
4. 在模型目录慢请求进行时持续探测 `/api/config`、`/api/status` 和 WebSocket 心跳，
   它们必须保持响应，不能因等待 skills 锁一起超时。

## 9. Profile 和 remote backend 路由

### 为什么要拦截 session 请求

远程 profile 的 session state 在 remote backend 上，不在 desktop 本地。

如果不拦截，以下路径会错：

- sidebar session list。
- 打开历史会话。
- 读取 messages。
- rename/archive/delete session。
- cron run session 打开。

### 拦截入口

函数：

- `interceptSessionRequestForRemote(request)`

挂在：

```js
ipcMain.handle('hermes:api', async (_event, request) => {
  const rerouted = await interceptSessionRequestForRemote(request)
  if (rerouted !== undefined) return rerouted
  ...
})
```

### 被拦截的路径

```text
GET    /api/profiles/sessions
GET    /api/sessions/{id}
GET    /api/sessions/{id}/messages
DELETE /api/sessions/{id}
PATCH  /api/sessions/{id}
```

### Global remote mode

判断：

```js
globalRemoteActive()
```

含义：

- connection config global `mode` 是 remote。
- 或 locked remote gateway 开启。
- 一个 remote backend 服务所有 profile。

规则：

- 对 `/api/profiles/sessions`，优先请求远端 `/api/profiles/sessions`。
- 如果远端 aggregate 为空或失败，回退 `/api/sessions`。
- 如果 request 带 `profile=<name>`，保留 profile 参数。
- 返回 row 如果没有 profile，要补 `default` 或当前 filter。
- 结果按 `last_active` 或 `started_at` 排序，再分页。

### Per-profile remote override

判断：

```js
profileHasRemoteOverride(profile)
```

含义：

- `connection.json.profiles[profile]` 有 remote entry。
- 这个 profile 的 session 属于自己的 remote host。

规则：

- 转发到该 profile remote。
- 对 read 请求不要保留桌面 profile 参数。
- mutation body 中删除 `profile`，避免 remote host 不认识。
- session list 返回时给每行补桌面 profile 名。

### 混合列表

函数：

- `mergeRemoteProfileSessions(searchParams, remoteProfiles)`

行为：

- 先读取 primary local aggregate。
- 删除其中 remoteProfiles 对应的 stale local rows/totals。
- 对每个 remote profile 读取真实 remote sessions。
- 合并、重排、重新分页。
- remote dead 时贡献空 rows，并删除 stale total，不让 sidebar 整体失败。

### 多请求读取固定 connectionId

历史会话页面通常先列出 sessions，再逐个读取 transcript。用户可能在这组异步请求尚未完成
时切换远程网关；如果每次请求都重新读取全局 active connection，就会出现“列表来自连接 A，
消息却从连接 B 读取”的串租户/404 问题。

当前契约：

- `getApiRequestConnection()` 在一批读取开始时取得一次快照。
- `listAllProfileSessions(..., { connectionId })` 和
  `getAllSessionMessages(..., { connectionId })` 复用同一个值。
- `SessionRequestScope.connectionId` 允许 `null`；显式 `null` 表示即使 active connection
  随后变化，这批请求仍固定走本地 pool。
- `connectionScoped()` 只在未传 scope 时读取当前 `_apiConnectionId`。传入快照后不得覆盖。
- connection registry 的远程后端拥有自己的 `state.db`；main process 必须根据
  `request.connectionId` 路由，不能只靠 profile 或当前 UI store 猜目标。

回归测试应在 session list 返回后切换 active connection，再读取 transcript，断言两次 IPC
仍带旧 connectionId；另测本地 pool 的显式 null 不携带 `connectionId` 字段。

## 10. 连接重建和 liveness

### revalidateConnection

IPC：

```text
hermes:connection:revalidate
```

作用：

- 如果 cached connection 是 remote，快速 probe `/api/status`。
- 不通则 `resetHermesConnection()`，让下一次 renderer reconnect 重建 descriptor。
- local backend 不在这里自愈，由 child exit handler 处理。

### applyConnectionConfig

保存并应用 connection：

- 修改 non-primary profile override 时，不重启主窗口 backend，只 stop 对应 pooled backend。
- 修改 global connection 或 primary profile connection 时，teardown primary backend 并 reload main window。

迁移时不要一律 reload，否则切某个非主 profile 的 remote 配置会干扰当前会话。

## 11. 常见误判

### 误判 1：登录成功后把 access token 交给 renderer

错误。token 是 HttpOnly cookie，renderer 不应该读。REST 通过 Electron net + session cookie，WS 通过 main process mint ticket。

### 误判 2：有 refresh token 但没有 access token就要求重新登录

错误。refresh token 还活着时，轻量 `/api/auth/session` 会刷新 access token。认证恢复
不应等待 ws-ticket 或 WebSocket；后两步属于连接可用性检查。

### 误判 3：`remoteUrl` 就是 BFF base

不总是。设置页展示 BFF base，但 connection config 保存的是 hosted gateway URL。

### 误判 4：session list 可以读本地 state.db

远程模式错误。remote profile 的 state.db 在远端。

### 误判 5：WebSocket URL 可以缓存

OAuth mode 错误。ticket 是单次短期，每次连接前 fresh mint。

### 误判 6：`/api/status` 通过就代表 WebSocket 可用

错误。HTTP 可以通过但 WS 被 auth/origin/proxy 拦截；ticket 也可能签发成功，但 BFF
到用户运行实例的上游 WS 仍不可达。connection test 和正常连接必须模拟 renderer 的
WS connect，但手动登录与重启认证恢复不能为此阻塞。

### 误判 7：窗口加载时可以无认证门禁地提前启动 backend

错误。可以并行预热，但必须先等待共享 single-flight 认证结果为成功。直接
`startHermes()` 会制造旧 token 与自动登录的竞态。

### 误判 8：运行实例状态为 ready 就代表 hosted gateway 可用

错误。`ready` 只表示运行实例记录和资源编排状态。BFF 到 OpenSandbox endpoint 仍可能因为 9119 未暴露、安全访问 header 丢失或上游 dashboard 未启动而失败。必须以真实 dashboard HTTP 和 WebSocket 代理结果为准。

## 12. 迁移测试建议

最小测试集：

- `auth-errors.test.cjs`：JSON detail、401/403、404、HTML、长英文错误。
- `dashboard-token.test.ts`：变量提取、AgentOS 优先级、served token drift、foreign backend。
- connection config tests：BFF base 和 hosted URL 互转。
- OAuth cookie tests：AT/RT 任一 live 的判断。
- WS ticket tests：每次 `getGatewayWsUrl(profile)` 都 mint 新 ticket。
- IPC 过期错误测试：自定义字段被序列化丢失后，仍能从明确消息识别 reauth；普通 transport error 不得命中。
- 启动顺序测试：未完成 `auth.getStatus()` 前不调用 `getConnection/startHermes`；过期错误请求顶层认证刷新，不写入普通 boot failure，也不调用 renderer reload。
- auth single-flight 测试：并发两个 `auth.getStatus()`/预启动请求只执行一次 session
  验证或密码登录；完成后下一次独立刷新仍可正常执行。
- BFF 轻量 session 测试：有效 cookie 返回 authenticated 并可轮换 token，且严格断言
  不调用 `get_dashboard_endpoint_async()`；无 cookie/失效 cookie 返回 401/403。
- 认证循环测试：客户端已进入主界面后触发 auth refresh，顶层最多再次调用一次 `auth.getStatus()`；既要覆盖返回 unauthenticated 的情况，也要覆盖返回 authenticated、但下一次 gateway boot 仍报 session expired 的情况。后者必须在第二次 auth refresh 时直接切到 `LoginScreen`，`getStatus()` 总调用次数保持为启动一次加恢复一次，不出现失败页、loader 和白屏之间的循环。
- 登录表单测试：账号密码错误无论以 rejected Promise 还是 `authenticated:false + error` 返回，都必须显示在登录表单中且不得调用 `onAuthenticated`；只有 `authenticated:true` 才能进入主界面。
- 重启恢复测试：`manualLoginRequired:false` 且持久化 OAuth cookie 通过轻量 session
  验证时必须直接恢复 authenticated，不能调用保存密码登录；只有 401/403 或 cookie
  缺失才回退保存凭据。session 探测 timeout/5xx 必须保留 cookie 并交给连接层处理。
  `manualLoginRequired:true` 时两条自动恢复路径都不得执行。
- 冷启动预算测试：首次 ws-ticket 使用一个长请求覆盖服务端运行时冷启动/修复预算，
  不得恢复成多个 8 秒短请求；ticket 成功后再完成真实 WS 握手。
- 敏感信息测试：`auth.json` 中密码只能是 `safeStorage` 密文；Access Token、Refresh Token 只存在 Electron HttpOnly cookie jar，不写入 `auth.json`、`connection.json` 或日志。恢复决策只传递 `hasSavedCredentials` 布尔值，不传递 token 或密码正文。
- OAuth response stream 测试：多段 body 正确合并；`ERR_CONTENT_LENGTH_MISMATCH` 等 response `error` 被 Promise 捕获并 reject，不形成主进程未捕获异常。
- Electron 集成测试：本地 HTTP 服务故意返回错误 `Content-Length`，request/response 两侧错误均有监听器，进程正常退出且不弹 JavaScript error。
- global remote session list fallback：`/api/profiles/sessions` 空时回退 `/api/sessions`。
- per-profile remote session mutation：PATCH/DELETE 不落本地。
- Settings locked mode：只显示 BFF 地址，不显示 token 输入。
- model catalog 隔离测试：`models_dev.auto_refresh:false` 时只读取磁盘快照且不调用网络；多个相同的非刷新 `/api/model/options` 请求只构建一次，`refresh=true` 绕过 short cache。
- ASGI 响应性测试：模型发现阻塞在 DNS/HTTP 时，`/api/config` 和 `/api/status` 仍可返回，不因 process-wide skills lock 被连带阻塞。
