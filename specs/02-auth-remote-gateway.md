# 02 认证与远程 Gateway

## Requirements

- **AUTH-001** 默认登录路径为账号密码调用 `BFF /auth/login`；renderer 不接触 access token、refresh token、密码或 WS ticket。
- **AUTH-002** main process 使用持久化 HttpOnly Cookie；密码仅在登录成功后通过安全存储保存，失败提交不得覆盖已验证密码。
- **AUTH-003** 飞书扫码仅在 BFF 明确启用且用户主动选择时出现；只允许已绑定 AgentOS 账号，不自动回退旧密码。
- **AUTH-004** 重启恢复先调用轻量 session 接口，不因实例冷启动阻塞；明确 401/403 才进入重新认证，DNS、超时、连接拒绝和 5xx 属于连接故障。
- **GATEWAY-001** 每次 WebSocket 建连都申请一次性 ticket，禁止缓存或复用 WS URL。
- **GATEWAY-002** 连接测试必须覆盖实际 REST 与 WebSocket/auth leg，不能用 `/api/status` 200 代替。
- **GATEWAY-003** 账号切换、退出、profile 切换和重试使用 generation/child identity 隔离旧 backend 的晚到事件。
- **GATEWAY-004** 首次启动失败可进入恢复页；已启动后的瞬时断线只显示可恢复警告并后台退避重连，不制造 boot failure。
- **AUTH-005** 日志、错误、配置和 crash 证据不得包含 token、密码或 Cookie 值。

## Automated acceptance

- 使用临时 BFF/Gateway 服务完成密码登录、Cookie 安装、session 恢复、ticket mint、WS 建连、断线重连和退出。
- 并发调用认证状态时只执行一次底层恢复；两个连续 WS 连接使用不同 ticket。
- 注入明确 401/403、timeout、DNS、5xx、截断 body 和错误 Content-Length，断言错误分类与 UI 状态。
- 延迟账号 A child 的 exit/error，登录账号 B，断言旧事件不能修改 B 的连接状态。
- 对日志、测试 artifact 和配置运行 secret scanner。

## Manual acceptance

1. 密码登录、应用重启自动恢复、主动退出、切换账号均一次成功。
2. 飞书扫码关闭、失败、未绑定和成功四条路径保持在正确页面且不泄露 token。
3. 在网络抖动与 Gateway 重启期间，主界面和历史会话保持可用，恢复后警告消失。
