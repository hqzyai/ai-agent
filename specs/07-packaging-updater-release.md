# 07 离线打包、客户端更新与发布制品

## Requirements

- **PKG-001** Linux、macOS、Windows 正式包默认包含 bundled Agent；`skipped:true` 或 payload 不完整必须阻断发布。
- **PKG-002** bundled manifest schema 2 必须在最终验证后最后写入，且 `sanitized`、`relocatable`、`pythonRuntimeBundled` 均为布尔 true，platform/arch 精确匹配。
- **PKG-003** payload 包含 Agent 源码、自包含 Python、Hermes entrypoint、browser-use launcher/环境；不含构建机路径、editable metadata、凭据、SSH key、token、private key 或递归安装包。
- **PKG-004** 普通 JS 依赖进入 Electron main bundle；原生 `node-pty`/`get-windows` 位于 `app.asar.unpacked/dist/node_modules`。
- **IDENTITY-001** 新包使用 `com.hqzyai.agentos`，实际 app 数据位于 `{APP_DATA_DIR}/profiles/{ORG_NAME}`；Windows 保留历史 NSIS/MSI 安装身份，macOS 身份迁移遵循单次 bridge 链。
- **UPDATE-001** Desktop 只更新租户 AgentOS 安装包，直接访问 release config 的对象存储；禁止 `/api/hermes/update*`、`hermes update`、Nous/Git fallback。
- **UPDATE-002** 下载继承系统代理/PAC/证书，支持 Range 续传、最多五次安全重定向、无活动超时、有限重试、SHA-256 和平台身份校验。
- **UPDATE-003** Windows/macOS 原位更新后从原安装路径重启并稳定至少 5 秒；失败恢复旧版本且不删除恢复证据。
- **RELEASE-001** 容器发布同一 digest 的 `linux/amd64`、`linux/arm64` manifest；Desktop 发布 Linux、macOS、Windows 三端候选制品。
- **RELEASE-002** 构建一次后按 digest/SHA 晋级，不在灰度与正式环境重新构建。

## Automated acceptance

- 在各目标 runner 生成安装包，重定位 payload 后实际执行 Python、Hermes、browser-use。
- 对安装包解包后验证 manifest、敏感信息、绝对路径、原生依赖、品牌身份、release config、文件名和 SHA-256。
- 执行 fresh install、N-1→N、N-2→N、自定义目录、旧数据迁移、失败回滚和自动重启 E2E。
- 用 Buildx 构建双架构镜像并验证 manifest list；对镜像运行 gateway/dashboard smoke test。

## Manual acceptance

1. 三端候选包在干净机器首次离线启动、登录、聊天并使用 browser-use。
2. 从真实 N-1 客户端升级，历史会话、Cookie、Skills、Cron、Profiles 保留。
3. 断网、校验失败和安装失败均回到可用旧版本；上传签名验收记录和日志。
