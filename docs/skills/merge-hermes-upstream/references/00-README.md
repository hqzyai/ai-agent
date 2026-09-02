# AgentOS Desktop 改造规范索引

本目录记录 `agentos-desktop` 最初从 `main` 提炼、并在后续 AgentOS 产品分支持续验证的改造规范。主要变更作者包括 `jiawy`、`jiawenyao401`、`邢磊`、`g642579705-glitch`。写作目标不是复述 commit history，而是给后续 Codex、Cursor 等 AI coding 智能体迁移新 desktop、同步官方 Hermes 上游和排查生产问题时当作知识库使用。

适用范围：

- 仓库：贡献者当前的 `agentos-desktop` checkout（禁止在规范中固化个人绝对路径）
- 初始事实基线：`main`，截止提交 `ea08c505d`。
- 历史审计基线包含 `agentos-20260817` 的 `e15f9c9f7e35`；后续同步必须以 release manifest 锁定的官方 tag object SHA 和 peeled commit SHA 为准，不再接受移动分支作为来源。
- 规范效力：后续产品分支已经实测确认的契约优先于初始 `main` 的中间实现；发现正文与当前审计基线冲突时，必须先按代码和回归测试修正文档，不能继续照搬旧结论。
- 2026-07-22 起，上游同步只允许直接使用 `https://github.com/NousResearch/hermes-agent` 的 `main`；不得再从本仓库的 `main`、镜像仓库或本地 Hermes checkout 合并。
- 重点范围是 `apps/desktop`、`tui_gateway`、`web` 中被桌面壳依赖的契约，以及 `.github/workflows/sync-hermes-agent.yml` 的桌面构建发布流程。

作者身份匹配：

- `jiawy <jiawenyao401@sina.com>`
- `jiawenyao401 <jiawenyao401@users.noreply.github.com>`
- `jiawenyao401 <jiawenyao401@sina.com>`
- `邢磊 <15948250190@139.com>`
- `g642579705-glitch <g642579705@gmail.com>`

## 推荐阅读顺序

1. `01-feature-inventory.md`
   - 总览所有改造块。
   - 说明哪些是最终规范，哪些只是中间打包测试提交。
   - 给后续智能体一个完整地图。

2. `02-auth-and-remote-gateway.md`
   - 最重要的契约。
   - 解释 BFF 账号密码登录、hosted gateway、HttpOnly cookie、WS ticket、profile 远程路由。
   - 新 desktop 如果登录和远程 gateway 走错，其他功能都会表现为随机失败。

3. `03-chat-media-artifacts.md`
   - 聊天消息展示、工具调用隐藏规则、媒体标签、远程文件下载、会话产物。
   - 重点说明为什么远程模式不能用本机 `file://`。

4. `04-cron-messaging-i18n-ui.md`
   - 定时任务、消息平台、汉化、品牌化、登录页、设置页和 AgentOS 产品能力过滤。
   - 这里决定用户看到的是 AgentOS 产品，而不是原始 Hermes 桌面壳。

5. `05-offline-packaging-and-ci.md`
   - 离线客户端、bundled agent payload、manifest 校验、跨平台打包、客户端更新、派生 server 镜像和 GitHub Actions 发布。
   - 新 desktop 打包如果没有严格验证 `build/bundled-agent/manifest.json`，很容易构建成功但离线不可用。

6. `06-ai-agent-migration-checklist.md`
   - 给 AI coding 智能体执行迁移用的 checklist。
   - 包含禁止破坏的契约、建议实施顺序、测试点、常见误判。

7. `bundled-plugins.md`
   - 定义 `apps/desktop/src/plugins`、`plugins/`、来源锁和 channels 集成 patch 的处理方式。
   - 每次 Hermes 合并都必须执行，即使插件目录没有文本冲突。

## 总原则

### 一切以真实请求链路为准

不要把桌面端问题简单理解为 React UI 问题。当前 desktop 是 Electron main process、renderer、tui_gateway、Hermes dashboard、BFF hosted gateway 共同组成的链路。很多问题的症状显示在 React，但源头在 cookie、WebSocket ticket、session state.db、remote file API 或 packaged runtime。

### 不要扩大 core agent surface

桌面改造尽量在桌面壳、BFF/hosted gateway 连接、renderer 展示、打包脚本和 CI 中完成。不要因为 desktop 需要一个 UX，就往 Hermes core model tools 里加新工具。新能力优先走已有 IPC/RPC、gateway API、CLI command、skill 或插件。

### 不要把 remote 当 local

远程模式下，session、files、media、artifacts、Hermes home 都可能在远端机器或 hosted gateway 后面。renderer 所在机器不能直接读 agent 写出的文件。任何文件预览、图片/视频播放、下载都必须经过 Electron IPC 和 gateway API。

### 不要把 token 模式当主路径

当前 AgentOS desktop 的主路径是 BFF 账号密码登录：

```text
desktop login form
  -> BFF /auth/login
  -> hosted gateway /desktop/hosted-gateway
  -> HttpOnly cookies in Electron OAuth partition
  -> POST /api/auth/ws-ticket
  -> WebSocket /api/ws?ticket=...
```

legacy session token 只是兼容 self-hosted 或旧 gateway，不是 AgentOS 产品主路径。

### 打包成功不等于离线可用

installer 构建成功但 `manifest.json` 是 `skipped:true`，或者 payload 缺 `hermes_cli/main.py`、自包含 venv、Hermes console entrypoint、完整 `browser-use` 工具环境，都必须视为失败。当前成功 manifest 是 schema 2，并且必须声明 `sanitized:true`、`relocatable:true`、`pythonRuntimeBundled:true`；离线客户端的验收标准是首次启动能从 `resources/bundled-agent` seed 一个不依赖构建机路径、也不夹带构建机凭据的完整 agent runtime。

### 产品面过滤不等于删除底层兼容能力

AgentOS 对模型、技能、工具集和供应商采用 server 侧集中产品策略。产品 API、桌面端和 dashboard 不得重新暴露被屏蔽能力；但已有配置、内部模块名、兼容路由和运行时协议可以继续保留。迁移时不要只在 React 隐藏，也不要为清除 Hermes 字样盲目重命名内部路径或删除底层实现。

### 客户端更新是独立生产链路

客户端安装包更新直接访问租户对象存储，不经过 BFF。版本检查、系统代理、断点续传、完整性校验、覆盖安装、交接进程和安装后自动重启必须作为一条完整链路验收。Desktop 只有这一种更新目标：禁止轮询或调用 `/api/hermes/update*`，禁止回退到 Nous/Hermes 的 Git、release feed、安装脚本或 `hermes update`。服务端兼容路由部署管理面负责，不是桌面端更新源。

### 官方上游同步只使用仓库内 skill

仓库内固定入口为 `docs/skills/merge-hermes-upstream/SKILL.md`。执行时必须满足：

- 以明确 base branch 为基线，新建 `ai-agent/hermes-v<semver>-YYYY.MM.DD`；目标分支已存在时停止并核对，禁止覆盖。
- `hermes` remote 必须精确指向 `https://github.com/NousResearch/hermes-agent.git`，只 fetch/merge release manifest 锁定的精确官方 tag。
- 合并使用 `--no-ff --no-commit`，先解决冲突，再审计 Git 自动合并区域；不能只检查冲突文件。
- 冲突结果必须同时保留上游行为修复和本规范定义的 AgentOS 产品契约。
- 提交前运行 skill 内 `audit-agentos-contracts.sh`，提交后运行 `validate-merge.sh`，确认官方提交确实是新分支祖先。
- 工作区原有改动必须先按唯一名称暂存，合并提交并推送后再精确恢复，禁止误提交或丢弃用户改动。
- Bundled plugin 必须来自显式 `ai-agent` checkout 的锁定源码；禁止在合并期间直接拉取 `hqzyai/hermes-plugin/main` 或重新解压未核验附件。

### 2026-08-17 官方同步后的桌面结构基线

`ba1077072` 同步后，后续智能体必须按当前文件系统识别所有者，不能把旧版文件重新创建回来：

- renderer 顶层认证门仍在 `apps/desktop/src/app/index.tsx`，认证成功后挂载的是 `ContribController`；其实现位于 `apps/desktop/src/app/contrib/controller.tsx`，并通过 `apps/desktop/src/app/contrib/index.ts` 导出。
- 上游已经删除旧的 `desktop-controller.tsx` 和 `shell/app-shell.tsx`。AgentOS 的认证、gateway、状态栏、消息平台和产物契约应接入 `app/contrib` 当前组合层，禁止为解决冲突复活旧控制器。
- Electron 主进程及多数辅助模块已经从 CommonJS 迁到 TypeScript。当前入口是 `apps/desktop/electron/main.ts`、`preload.ts` 和 `connection-config.ts`；`auth-errors.cjs`、部分构建脚本和兼容测试仍是 CommonJS，必须以实际扩展名为准，不能机械地全量改名。
- 聊天 markdown/media 使用上游共享解析和 resolver 链。AgentOS 只在远程文件映射、下载授权、可见文案与安全策略处扩展，不再维护一套平行 markdown 解析器。
- 上游单元测试如果使用 AgentOS 产品面已屏蔽的平台或供应商作为夹具，必须换成允许的平台、本地供应商或通用假数据。通用组件行为测试可以显式指定 locale；产品契约测试必须继续断言中文和 AgentOS 可见范围。

## 文档维护建议

后续如果继续改造 desktop，应同步更新本目录：

- 新增登录字段、BFF 路由、cookie 名称、gateway API 时，更新 `02-auth-and-remote-gateway.md`。
- 新增远程会话恢复、SQLite 连接、模型目录发现或 server 请求阻塞修复时，也更新 `02-auth-and-remote-gateway.md`。
- 新增 artifact 类型、media 类型、下载策略时，更新 `03-chat-media-artifacts.md`。
- 新增定时任务 UI、消息平台、汉化 key、品牌护栏或产品能力过滤时，更新 `04-cron-messaging-i18n-ui.md`。
- 新增打包资源、CI matrix、发布路径、manifest 字段、native dependency staging、更新器、派生镜像或 dev/build 启动修复时，更新 `05-offline-packaging-and-ci.md`。
- 变更 appId/AUMID、安装目录、userData、sessionData、缓存、日志、crash dump 或 `HERMES_HOME` 默认布局时，必须把安装身份兼容、旧数据迁移、失败回滚和跨版本发布顺序一起写入 `05-offline-packaging-and-ci.md`，并在 `spec-map.md` 增加不可回退契约；不能只改 `package.json`。
- 每次改动专题文档后，同步更新 `01-feature-inventory.md` 的功能地图和 `06-ai-agent-migration-checklist.md` 的验收项；只改专题正文仍属于文档维护不完整。
- 本目录是 contributor workflow 的版本化规范来源。修改后必须同步 00–06、`brand-profile.md` 与 `spec-map.md`，更新 contributor skill lock；禁止依赖机器本地的第二份规范。
- 每次迁移新 desktop 前，先执行 `06-ai-agent-migration-checklist.md`。
