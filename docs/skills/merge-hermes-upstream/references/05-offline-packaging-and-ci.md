# 离线客户端打包和 CI 发布规范

给人看的出包步骤与更新模式位于仓库 `docs/desktop-packaging-and-updates.md`。本文是上游合并时的硬性验收标准。

本文记录 AgentOS desktop 的离线打包、bundled agent payload、跨平台 artifact、客户端更新、server 派生镜像和 GitHub Actions 发布流程。后续智能体改造新 desktop 时必须把这里当作硬性验收标准。

核心原则：

```text
installer 构建成功不代表离线可用。
只有 bundled agent manifest 和 payload 内容都验证通过，才算离线客户端可发布。
```

## 1. 关键文件

package 和 builder：

- `apps/desktop/package.json`
- `apps/desktop/scripts/run-electron-builder.mjs`
- `apps/desktop/scripts/before-build.mjs`
- `apps/desktop/scripts/before-pack.mjs`
- `apps/desktop/scripts/after-pack.mjs`
- `apps/desktop/scripts/set-exe-identity.mjs`
- `apps/desktop/scripts/stage-installer-script.cjs`
- `apps/desktop/scripts/stage-native-deps.mjs`
- `apps/desktop/scripts/electron-builder-win.cjs`

offline payload：

- `apps/desktop/scripts/stage-agent-payload.cjs`
- `apps/desktop/electron/bundled-agent.cjs`
- `apps/desktop/electron/bootstrap-runner.ts`
- `apps/desktop/electron/backend-command.ts`
- `apps/desktop/electron/git-review-ops.ts`

客户端更新：

- `apps/desktop/electron/client-package-update.cjs`
- `apps/desktop/electron/electron-net-request.cjs`
- `apps/desktop/electron/installer.nsh`
- `apps/desktop/electron/release-config.cjs`
- `apps/desktop/scripts/write-release-config.cjs`
- `apps/desktop/src/app/updates-overlay.tsx`
- `apps/desktop/src/store/updates.ts`

server 镜像：

- `Dockerfile`
- `Dockerfile.source-build`
- `docker-compose.yml`
- `docs/docker-server-update.md`

CI：

- `.github/workflows/sync-hermes-agent.yml`

配置：

- `apps/desktop/config/defaults.json`

## 2. package.json scripts 规范

重要 scripts：

```json
{
  "build": "node scripts/assert-root-install.mjs && node scripts/write-build-stamp.mjs && node scripts/write-release-config.cjs && node scripts/stage-installer-script.cjs && node scripts/stage-agent-payload.cjs && vite build && node scripts/bundle-electron-main.mjs && node scripts/stage-native-deps.mjs",
  "dist": "cross-env HERMES_DESKTOP_BUNDLE_AGENT=1 npm run build && npm run builder",
  "dist:mac": "cross-env HERMES_DESKTOP_BUNDLE_AGENT=1 npm run build && npm run builder -- --mac",
  "dist:mac:publish": "npm run dist:mac && npm run upload:tos",
  "dist:win": "npm run sync:root-deps && cross-env HERMES_DESKTOP_BUNDLE_AGENT=1 HERMES_DESKTOP_TARGET_PLATFORM=win32 HERMES_DESKTOP_TARGET_ARCH=x64 npm run build && cross-env HERMES_DESKTOP_TARGET_PLATFORM=win32 HERMES_DESKTOP_TARGET_ARCH=x64 npm run builder -- --win nsis --x64 --config scripts/electron-builder-win.cjs",
  "dist:win:publish": "npm run dist:win && npm run upload:tos",
  "dist:linux": "cross-env HERMES_DESKTOP_BUNDLE_AGENT=1 npm run build && npm run builder -- --linux AppImage deb rpm"
}
```

规范：

- 所有 dist 脚本默认 `HERMES_DESKTOP_BUNDLE_AGENT=1`。
- `dist:*` 只生成本地产物，不能因为缺少 TOS 凭证而失败；上传属于独立发布阶段。
- `dist:*:publish` 显式串联构建与 `upload:tos`，仅在具备租户发布凭证的机器或 CI 上执行。
- `build` 必须先校验根依赖，写 build stamp 和租户 release config，再 stage installer/payload，
  构建 renderer 与 Electron main，最后 stage native deps；`postbuild` 的
  `assert-dist-built.mjs` 仍由 npm 生命周期自动执行。
- 不要把 `stage-agent-payload` 放到 electron-builder 后面。payload 必须作为 `extraResources` 被打进包。
- 不存在的脚本不要留在 `package.json`。当前分支没有可用 `build-clients.cjs` 时，必须移除 `dist:clients`，否则后续智能体或 CI 会踩一个“看起来有入口、实际必炸”的假规范。
- `test:desktop:platforms` 应包含 bundled-agent、stage-agent-payload、auth-errors、dashboard-token 等 main process tests。

## 3. Electron builder 资源

`package.json build.extraResources` 包括：

```json
[
  { "from": "build/install-stamp.json", "to": "install-stamp.json" },
  { "from": "build/desktop-release.json", "to": "desktop-release.json" },
  { "from": "build/bundled-installer", "to": "bundled-installer" },
  { "from": "build/bundled-agent", "to": "bundled-agent" },
  { "from": "assets/icon.ico", "to": "icon.ico" }
]
```

当前 `package.json` 仍可能保留 `{ from:"build/native-deps", to:"native-deps" }` 的旧兼容项，
但当前 `stage-native-deps.mjs` 不再生成该目录，而是写入 `dist/node_modules`。新合并和清洁
出包不得依赖工作区碰巧残留的 `build/native-deps`；确认没有旧运行时消费者后应删除该
extraResources 项。原生依赖的发布验收路径见第 6 节。

关键要求：

- `build/bundled-agent` 必须存在。
- 它会进入 app resources。
- `bundled-agent` 中要有 `manifest.json` 和 `hermes-home/`。
- `hermes-home/hermes-agent` 是可 seed 的完整 runtime。
- 打包图标不能只替换 `assets/icon.png`。macOS installer/App icon 读取 `assets/icon.icns`，Windows 读取 `assets/icon.ico`，`extraResources` 还会把 `assets/icon.ico` 复制为 packaged resources 下的 `icon.ico`。
- 标准头像源来自品牌配置的 `BRAND_ASSETS_DIR`。迁移或换肤时必须用该目录中的同一源图重新生成：
  - `apps/desktop/assets/icon.png`
  - `apps/desktop/assets/icon.icns`
  - `apps/desktop/assets/icon.ico`
  - `apps/desktop/public/apple-touch-icon.png`
- `apps/desktop/public/apple-touch-icon.png` 是开发/运行时窗口图标、Dock `app.dock.setIcon(...)`、favicon 和 `BrandMark` 的统一来源；不要让登录页、安装页、关于页继续引用旧的 `nous-girl.jpg`。
- `apps/desktop/dist/apple-touch-icon.png` 是构建产物副本，通常由 `vite build` 从 `public` 生成。临时验证已构建包时可以覆盖它，但源码规范以 `public/apple-touch-icon.png` 为准。
- 如果 `public/nous-girl.jpg`、`dist/nous-girl.jpg` 或已打包 `app.asar.unpacked/dist/nous-girl.jpg` 还作为兼容资源保留，内容也必须由同一个 AgentOS icon 源图重新生成，不能继续保留旧头像。
- 已打包产物不会自动读取源码目录。临时验证旧包时，还要同步覆盖：
  - `apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/icon.icns`
  - `apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/icon.ico`
  - `apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/app.asar.unpacked/dist/apple-touch-icon.png`
  - `apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/app.asar.unpacked/dist/nous-girl.jpg`
  - `apps/desktop/release/win-unpacked/resources/icon.ico`
  - `apps/desktop/release/win-unpacked/resources/app.asar.unpacked/dist/apple-touch-icon.png`
  - `apps/desktop/release/win-unpacked/resources/app.asar.unpacked/dist/nous-girl.jpg`
- 验收时执行 `rg -n "nous-girl" apps/desktop/src apps/desktop/electron apps/desktop/index.html apps/desktop/DESIGN.md`，必须没有代码/设计说明引用。

## 4. stage-agent-payload 设计

文件：

- `apps/desktop/scripts/stage-agent-payload.cjs`

目标：

构建时准备一个完整 Hermes Agent runtime，用于 packaged desktop 首次启动离线 seed。

输出：

```text
apps/desktop/build/bundled-agent/
  manifest.json
  hermes-home/
    bin/browser-use
    uv-tools/browser-use/
    hermes-agent/
      hermes_cli/main.py
      venv/bin/python 或 venv/Scripts/python.exe
      venv/bin/hermes 或 venv/Scripts/hermes.exe
      ...
```

### 启用和跳过

启用：

```text
HERMES_DESKTOP_BUNDLE_AGENT=1
```

显式跳过：

```text
HERMES_DESKTOP_SKIP_AGENT_PAYLOAD=1
```

未启用或显式跳过时会写 skip marker：

```json
{
  "schemaVersion": 2,
  "bundled": false,
  "skipped": true,
  "reason": "...",
  "builtAt": "..."
}
```

发行构建中 skip marker 必须失败。

### 构建步骤

`stage-agent-payload.cjs` 做这些事：

1. 读取 `build/install-stamp.json`。
2. 创建临时 work root，必须在 repo 外。
3. 把 repo checkout 拷贝到 `hermes-home/hermes-agent`，复制阶段拒绝敏感凭据路径。
4. 写 `.install_method` 为 `bundled`。
5. Windows 下准备 managed uv。
6. 按平台执行 install stages。
7. 验证初始 staged payload，包含 agent 与 browser-use entrypoint。
8. 拷贝 `hermesHome` 到 `build/bundled-agent/hermes-home` 并物化 symlink。
9. 把 agent venv 与 browser-use venv 的 Python base/stdlib 合并进各自环境，删除 `pyvenv.cfg`。
10. 清除凭据、editable-install 绝对路径和构建机 metadata，重写 console entrypoint 为可迁移路径。
11. 运行自包含、凭据、绝对路径、entrypoint、平台工具完整性验证。
12. 所有验证通过后最后写 schema 2 成功 manifest。
13. 清理临时 work root。

### 为什么 work root 必须在 repo 外

注释里说明：

```text
Must live outside REPO_ROOT — staging under apps/desktop/build/ would be copied into itself when we rsync the checkout.
```

如果临时目录在 repo 内，copy repo 时会递归复制自身，导致错误或巨型 payload。

### 拷贝排除列表

`COPY_SKIP_DIRS` 排除：

- `node_modules`
- `.venv`
- `venv`
- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.idea`
- `.cursor`
- `.git`
- `build`
- `release`
- `dist`
- `.agent-payload-work`
- `bundled-agent`
- `bundled-installer`
- `native-deps`
- `website`
- `tests`
- `.github`
- `desktop`
- `bootstrap-installer`

无论目录是否在上面的体积排除表中，以下内容都不得进入 payload：

- `.env`、`.env.*`、`.envrc`、`.netrc`、`.npmrc`、`.pypirc`、`.git-credentials`。
- `.aws`、`.azure`、`.gcloud`、`.gnupg`、`.kube`、`.ssh`。
- `credentials*`、`secrets.*`、`token*.json`、`auth.json`、`id_rsa`、`id_ed25519`。
- 完整 private-key PEM block，以及配置文件中名字像 token/password/api_key/secret 的真实字面值。

复制前由 `shouldCopyRelative()` 拒绝，输出后还要由 `removeSensitivePayloadFiles()` 清理并由
`assertPayloadSafe()` fail closed。不能只依赖 `.gitignore` 或构建机“应该没有凭据”。

`apps/` 使用白名单而不是安装包后缀黑名单：遍历 `apps/` 时只允许复制运行时 workspace `apps/shared`，`apps/desktop`、`apps/bootstrap-installer` 以及直接遗留在 `apps/` 根目录的 DMG、ZIP、EXE、AppImage 等文件全部拒绝。这样新增格式或改名后的安装产物也不会被再次装入 payload。

原因：

- 减小 payload。
- 避免 Windows MAX_PATH。
- 避免 WiX LGHT0103。
- 避免非 runtime 内容进入离线包。
- 避免“安装包套安装包”：repo 根下 `apps/` 中残留的旧 DMG、AppImage、EXE 被复制进 bundled agent 后，会让下一次 DMG 从约 300MB 膨胀到 1GB 以上。

迁移新 desktop 时，如果新增非 runtime 大目录，要加入排除。

### install stages

macOS/Linux：

```js
['prerequisites', 'venv', 'python-deps', 'node-deps', 'path', 'config']
```

Windows：

```js
[
  'uv',
  'python',
  'git',
  'node',
  'system-packages',
  'venv',
  'dependencies',
  'node-deps',
  'path',
  'config-templates',
  'platform-sdks'
]
```

Windows stage 名来自 `install.ps1`，不同于 `install.sh`。不要强行统一。

### stage 执行参数

macOS/Linux：

```text
scripts/install.sh
  --stage <stage>
  --non-interactive
  --json
  --dir <installDir>
  --hermes-home <hermesHome>
  --skip-setup
  --branch <branch>
  --commit <commit>
```

Windows：

```text
powershell.exe -File scripts/install.ps1
  -Stage <stage>
  -NonInteractive
  -Json
  -SkipSetup
  -HermesHome <hermesHome>
  -InstallDir <installDir>
  -Commit <commit>
  -Branch <branch>
```

### stage 失败处理

`runInstallStage`：

- capture stdout/stderr。
- 从 stdout 最后一段 JSON 解析 stage result。
- process exit 非 0 时报错。
- JSON `ok === false` 且不是 skipped 时报错。
- 报错要包含 stdout/stderr，方便 CI 定位。

### payload 验证

`verifyStagedPayload(hermesHome, installDir)` 检查：

- `hermes_cli/main.py` 存在。
- 平台 venv python 存在：
  - Windows：`venv/Scripts/python.exe`
  - 其他：`venv/bin/python`
- 对应平台 `hermes` console entrypoint 存在。
- `hermes-home/bin/browser-use` 与 `hermes-home/uv-tools/browser-use` 的 Python 存在。

这些只是文件完整性入口。输出 manifest 前还必须通过 `assertSelfContainedPythonPayload()` 和
`assertPayloadSafe()`；只存在一个 symlink 或指向构建机的 launcher 不能算完整。

### Python 与 console entrypoint 可迁移性

普通 uv venv 的 `pyvenv.cfg`、解释器 symlink 和 console-script shebang 会指向构建机。
schema 2 使用以下规则消除这个依赖：

- `makePythonEnvironmentsSelfContained()` 对 agent venv 和 `uv-tools/browser-use` 各自找到
  Python base，先物化环境内 symlink，再把完整 base prefix 和标准库合并进环境。
- 删除 `pyvenv.cfg`、activation scripts、`direct_url.json`、`uv-receipt.toml`，并重写
  `_sysconfigdata_*.py` 中的 build prefix。
- `makeEditableInstallRelocatable()` 移除指向临时 checkout 的 editable `.pth`/finder 痕迹。
- `makePythonEntrypointsRelocatable()` 将 Unix Python console script 改为按自身目录寻找
  相对解释器；发现残留绝对 Python shebang 立即失败。
- `UV_TOOL_DIR` 与 `UV_TOOL_BIN_DIR` 必须指向 staged `HERMES_HOME`，保证 browser-use 的
  launcher 和解释器都在包中，而不是用户全局 uv 目录。

当前实现对 Windows standalone Python 与 distlib launcher 的迁移尚未完成，因此 schema 2
构建在 Windows 会明确 `refusing bundle`，不能通过关闭校验或写假 manifest 绕过。要恢复
Windows 正式离线出包，必须先实现并在重定位后的 Windows 临时目录实际执行
`python.exe`、`hermes.exe` 和 `browser-use.exe`，再移除这道 fail-closed 门禁。

### symlink 物化

函数：

- `materializeSymlinks(root)`

行为：

- 遍历 payload。
- 如果遇到 symlink，解析真实路径。
- 删除 symlink。
- 如果目标是目录，复制目录并递归物化。
- 如果目标是文件，复制文件。

原因：

- packaged installer 中 symlink 指向 build temp 或 workspace 会失效。
- Windows/Linux 打包时如果 payload 内保留 symlink，可能出现 `No such file or directory` 或 7za 警告。
- node workspace `file:` 依赖尤其容易生成 symlink。

### manifest

成功 manifest：

```json
{
  "schemaVersion": 2,
  "commit": "...",
  "branch": "...",
  "platform": "darwin|win32|linux",
  "arch": "...",
  "builtAt": "...",
  "source": "local",
  "sanitized": true,
  "relocatable": true,
  "pythonRuntimeBundled": true
}
```

规范：

- schemaVersion 当前为 2。
- commit 必须来自 build stamp。
- branch 可为 null。
- platform/arch 不只是诊断；启动器要求与 `process.platform/process.arch` 精确一致。
- 三个安全能力字段必须都是布尔 `true`，缺失或字符串值都无效。
- 成功 manifest 必须在复制、清理、重写和最终验证之后最后写入，避免半成品被启动器接受。
- 不要把 skipped manifest 当成功。

## 5. packaged app 首次启动 seed

文件：

- `apps/desktop/electron/bundled-agent.cjs`

目标：

packaged app 启动时，如果资源中有完整 bundled agent payload，可以离线 seed 到用户 Hermes home。

### resolveBundledAgentRoot

候选路径：

1. `resourcesPath/bundled-agent`
2. `appRoot/build/bundled-agent`

第二个支持 dev/build 环境测试。

### readBundledAgentManifest

返回 null 条件：

- manifest 读不到。
- JSON 无效。
- schemaVersion 不匹配。
- `skipped === true`。
- `bundled === false`。
- `sanitized`、`relocatable` 或 `pythonRuntimeBundled` 不是 `true`。
- manifest platform/arch 与当前客户端不一致。
- commit 不是长度至少 7 的字符串。

### isAgentTreeComplete

检查：

- `hermes_cli/main.py`
- venv python。
- `hermes` console entrypoint。
- agent venv 是自包含 Python 环境，不存在 `pyvenv.cfg`，并包含 `encodings`、`ssl.py`、`sqlite3` 等标准库锚点。

`isBundledToolingComplete()` 另行检查 browser-use launcher、browser-use Python 和自包含标准库。

### hasBundledAgentPayload

只有 root、schema 2 manifest、agent tree、browser-use tooling 和 payload 安全扫描都有效才返回 true。

### seedBundledAgent

输入：

- `resourcesPath`
- `appRoot`
- `hermesHome`
- `activeRoot`
- `emit`
- `installStamp`

流程：

1. 找 bundled-agent root。
2. 读 manifest。
3. 验证 source agent tree、browser-use、自包含 Python 与 payload 安全性。
4. emit stage running。
5. 创建 hermesHome。
6. 如果 activeRoot 已存在，删除。
7. 复制 sourceHome 下所有内容到 hermesHome。
8. 复制后再次验证 activeRoot、`bin` 和 `uv-tools`；只扫描产品复制的目录，不因用户已有
   `HERMES_HOME` 中合法的个人 credential 文件误判整个 home。
9. emit stage succeeded。
10. 返回 `{ ok:true, manifest, pinnedCommit, pinnedBranch }`。

失败：

- emit stage failed。
- 返回 `{ ok:false, error }`。

迁移注意：

- seed 是 replace activeRoot，不是 merge。
- stage event 用于 boot progress UI。
- pinnedCommit/pinnedBranch 用于 installer/bootstrap 后续逻辑。

## 6. native-deps、JS 依赖和本地打包入口

文件：

- `apps/desktop/scripts/stage-native-deps.mjs`
- `apps/desktop/scripts/bundle-electron-main.mjs`
- `apps/desktop/electron/git-review-ops.ts`
- `apps/desktop/scripts/electron-builder-win.cjs`
- `package-lock.json`

目标：

Electron packaged app 的 main process 不能依赖 repo-root `node_modules` 一定存在。当前主进程
通过 esbuild 输出自包含的 `dist/electron-main.mjs`：普通纯 JS 依赖直接 bundle，Electron
runtime 与原生模块才 externalize 并按平台 stage。不要恢复旧版“每个 JS 包都手工找
`resources/native-deps/vendor/node_modules`”的解析链。

### stage-native-deps 输出

输出目录：

```text
apps/desktop/dist/node_modules/
  node-pty/
  get-windows/   # 支持的平台/架构才存在
```

`node-pty` 和 `get-windows` 含 native/helper 文件，按真实 target platform/arch 复制到
`dist/node_modules`。`dist/**` 位于 `asarUnpack`，打包后路径是
`resources/app.asar.unpacked/dist/node_modules/...`。`before-pack.mjs` 必须根据
electron-builder 的实际 target 再 stage 一次，不能只相信 host build 的架构。

### simple-git 与 Electron main bundle 规范

当前源码是 `apps/desktop/electron/git-review-ops.ts`，可直接
`import simpleGit from 'simple-git'`，因为 `bundle-electron-main.mjs` 的 external allowlist
只有 `electron`、`node-pty`、`get-windows`、`fs`；`simple-git` 及其纯 JS closure 会进入
`dist/electron-main.mjs`。

验收规则：

1. 根 workspace 安装后 `npm run build` 必须能解析并 bundle `simple-git`。
2. `dist/electron-main.mjs` 不得保留运行时 `require('simple-git')` 或
   `Resources/native-deps/vendor/node_modules/simple-git` 路径。
3. packaged app 无 repo-root `node_modules` 时，Review/Git IPC 仍可加载。
4. `node-pty`/`get-windows` 继续 externalize，不能被当作普通 JS 打进 main bundle。
5. 旧 `build/native-deps` 或 `extraResources/native-deps` 只可能是迁移残留，不得作为
   simple-git 的新依赖路径；清洁构建验收以 `app.asar.unpacked/dist/node_modules` 为准。

故障样例：

```text
Cannot find module '/.../node_modules/electron/dist/Electron.app/Contents/Resources/native-deps/vendor/node_modules/simple-git'
Require stack:
- apps/desktop/electron/git-review-ops.cjs
- apps/desktop/dist/electron-main.mjs（源码入口是 `electron/main.ts`）
```

这个错误属于旧架构残留：说明还在运行未重新 bundle 的旧 `git-review-ops.cjs`/main 产物，
或热替换只改了 renderer。清理旧 `dist` 后从仓库根按 lock 安装并完整执行 `npm run build`；
不要重新添加 vendor fallback 来掩盖旧产物。

### package-lock 同步

`apps/desktop/package.json` 包名从 Hermes 迁到 AgentOS 壳后，repo-root `package-lock.json` 中 workspace link 也要同步。例如：

```text
node_modules/huaqing-desktop -> apps/desktop
```

不要留下旧的 `node_modules/hermes -> apps/desktop` link，否则 `npm install` 后依赖树和包名会漂移。

### 当前分支没有 build-clients.cjs

历史文档和提交里出现过 `build-clients.cjs`，但当前迁移分支没有可用的 `apps/desktop/scripts/build-clients.cjs`。规范是：

- 不要在 `package.json` 留 `dist:clients` 指向不存在的脚本。
- 三平台构建以 GitHub Actions matrix 和 `dist:mac`、`dist:win`、`dist:linux` 为准。
- 如果未来重新实现一键三端脚本，必须同时补脚本、测试、文档，并恢复 payload verification 门禁。

### Windows builder config

Windows 构建入口必须显式使用：

```text
--config scripts/electron-builder-win.cjs
```

原因：跨平台构建 Windows 时不能误用当前 host 的 Electron runtime。`electron-builder-win.cjs` 应负责跳过本机 Electron dist 或指向 win32-x64 runtime。

### Windows 客户端覆盖更新

Windows 已安装客户端必须采用原目录覆盖升级，不能先执行一个对用户可见的独立卸载，再尝试安装新版。electron-builder 的 NSIS 升级流程会先调用旧卸载器清理旧程序文件，并自动传入 `/KEEP_APP_DATA --updated`；这一步只替换程序目录，不应删除 Electron `userData`、登录态、租户配置或会话数据。

更新源确认当前安装包已经是最新版本时，这是正常成功终态，不是更新失败。主进程必须返回 `ok: true, noUpdate: true`，不得发送 `error` 进度；渲染层必须清除可能过期的 `updateAvailable/targetSha`，回到 `idle` 并保持更新弹窗可关闭。界面只显示“已是最新版本”和关闭入口，禁止同时出现红色错误图标、“更新未完成”、“重试”或“暂不”。

运行中的 Windows 进程会锁定 `AgentOS.exe`、`app.asar` 和已加载 DLL，因此禁止在桌面进程仍存活时直接启动 NSIS。正确交接顺序：

1. 下载到 `{APP_DATA_DIR}/profiles/{ORG_NAME}/cache/client-updates`，使用 `.part`、断点续传、大小上限、SHA-256 和 `MZ` 文件头校验。
2. 停止 AgentOS 后端及子进程，确认后端文件锁释放。
3. 在 `updates.json.clientPackage.pendingInstall` 写入安装包指纹、版本、安装包路径、结果文件路径和开始时间；此时不得更新 `appliedFingerprint`。
4. 启动独立 PowerShell 交接进程，并用它的 PID 写 `.hermes-update-in-progress`。
5. 桌面展示交接提示后退出。PowerShell 必须等待旧桌面 PID 消失，再额外等待文件句柄释放。
6. PowerShell 执行 `AgentOS-update.exe /S --updated /D=<原安装目录>`。`/D=` 必须是最后一个参数，以兼容带空格的路径。禁止传 `--force-run`：electron-builder 的 assisted NSIS 在静默模式收到该参数会走框架隐式启动分支，旧客户端无法对启动时序和结果进行可靠观测。
7. Windows 安装包自身必须通过 `nsis.include` 挂载 `customInstall`，在静默安装完成时调用 `${StdUtils.ExecShellAsUser}` 直接启动 `$INSTDIR\${APP_EXECUTABLE_FILENAME} --updated`。不得依赖 `$launchLink`：覆盖升级期间快捷方式可能尚未刷新、被用户删除或仍指向旧位置。新安装包自启动是跨版本兜底：升级时先执行的是旧客户端代码，而新安装包是本次升级中唯一保证能够运行的新代码；因此不能只修桌面交接脚本，否则从未包含修复的旧客户端升级时，本次升级仍会按旧逻辑结束。
8. NSIS 返回 0 后，PowerShell 先确认旧客户端传入的真实 `process.execPath` 仍存在，再删除 `.hermes-update-in-progress` 并验证文件确实消失。删除失败时最多重试 20 次，每次间隔 250 毫秒；仍然存在则写失败结果并退出，禁止一边声称清理成功、一边让新客户端被仍存活的交接 PID 卡在更新门禁。
9. 清除标记后，PowerShell 按完整、不区分大小写的 EXE 路径查找安装包已经启动的 AgentOS 进程。找到则接管；未找到才执行 `Start-Process -FilePath <process.execPath> -ArgumentList --updated -WorkingDirectory <原安装目录> -PassThru`。禁止根据产品名、默认安装目录或快捷方式猜测路径。启动请求发出后必须轮询真实 EXE 进程，不能把 `Start-Process` 返回过当作客户端已经启动。
10. Windows 文件释放、安全软件扫描和单实例锁切换存在短暂延迟。交接脚本最多执行 3 次启动尝试，每次等待真实 EXE 进程出现最多 15 秒，出现后再观察至少 5 秒；进程未出现或提前退出时记录本次 attempt 并重试。只有进程持续存活，才写入成功结果并删除临时安装包；新客户端读取结果后才把待安装指纹提交为 `appliedFingerprint/appliedVersion`。静默安装返回非零时自动打开可见安装向导作为恢复通道；若向导启动了 AgentOS，同样复用该进程，不得再启动第二个实例。三次均失败或交接超时必须清理 `pendingInstall`、保留旧 applied 状态，使同一个包可以重试。

若安装后的可执行文件不存在、更新标记无法删除，或三次启动/稳定性检查全部失败，交接脚本必须写入非零结果、保留临时安装包，并显示“更新完成但自动重启失败”的原生提示，指导用户从开始菜单手动打开。不得在只提交了启动命令、尚未确认进程存活时宣称更新完整成功。

安装包不能下载到应用安装目录，否则旧版本清理可能删除正在运行的安装器；也不要放进 `userData`，避免未来卸载数据策略误删交接文件。交接进程要等待安装器自身退出，不能把安装器启动的 AgentOS 当作安装器本身来等待。

每次 Windows 客户端覆盖更新必须写独立持久日志 `HERMES_HOME/logs/client-update-handoff.log`，与 `desktop.log` 同目录。Windows 未设置自定义 `HERMES_HOME` 时默认位置为 `%LOCALAPPDATA%\hqzy\AgentOS\agent-data\logs\client-update-handoff.log`。至少记录：交接开始、旧桌面 PID 退出、静默/恢复安装器 PID 与退出码、更新标记每次删除结果、每次启动请求、真实 EXE 出现或超时、实际接管的 AgentOS PID、稳定性结果和异常堆栈。日志不得包含更新 URL 查询参数、Access Token、Refresh Token、密码或对象存储临时凭证；临时安装包和 `.result` 可以清理，交接日志必须保留用于现场定位。

回归测试必须覆盖：

- 安装目录和用户名含空格或单引号。
- 安装器启动语句位于等待旧桌面 PID 的逻辑之后。
- 静默参数包含 `/S --updated`、不包含 `--force-run`，且 `/D=` 位于最后。
- `package.json` 与生产 Windows 构建入口 `scripts/electron-builder-win.cjs` 导出的最终配置都必须保留 `nsis.include: electron/installer.nsh`；测试必须直接加载 Windows 构建入口断言该值，不能只检查 `package.json` 或陈旧的 `builder-effective-config.yaml`。该文件的 `customInstall` 必须在 `${Silent}` 分支通过 `${StdUtils.ExecShellAsUser}` 直接启动 `$INSTDIR\${APP_EXECUTABLE_FILENAME} --updated`，以覆盖旧客户端交接代码尚未更新的首次升级。
- 更新标记删除语句必须位于最后一次 `$installer.WaitForExit()` 之后、新客户端启动语句之前。
- 新客户端启动使用旧客户端传入的真实可执行文件路径；必须验证更新标记确实删除，并以完整路径轮询真实 EXE。最多尝试 3 次，每次等待进程出现最多 15 秒并确认至少持续存活 5 秒，之后才能写成功结果和删除临时安装包。
- 可见恢复安装器已经启动 AgentOS 时，交接脚本按完整、不区分大小写的 EXE 路径识别并复用该进程，不得因二次启动命中单实例锁而误报重启失败。
- `client-update-handoff.log` 必须能还原安装、清标记、启动和存活检查的完整顺序；验收失败时先取该文件，禁止继续只根据界面现象猜测。
- `process.execPath` 为空、安装后目标文件不存在、`Start-Process` 失败或新客户端在观察窗口内退出时，必须写入非零结果、保留可重试现场并给出原生失败提示，禁止把“安装器返回 0 但客户端未稳定拉起”报告为完整成功。
- 安装成功前 `appliedFingerprint` 不变化。
- 非零退出码和陈旧 pending 都恢复为可重试状态。
- 覆盖安装后用户数据、登录态、租户配置和快捷方式仍在。

### macOS 客户端覆盖更新

macOS 打包客户端与 Windows 使用同一套租户安装包更新状态和对象存储网络层，但安装载体是 DMG，交接进程是独立 bash。禁止恢复“macOS 只显示未配置更新源、让用户手工下载”的旧逻辑。

检查与下载契约：

1. `resources/desktop-release.json` schema 3 必须包含 `downloads.mac`，值为无 URL credentials 的 HTTPS `.dmg`；开发模式和 schema v1/v2 旧包可以从其内置 `defaults.json` 补齐 Mac URL。
2. HEAD、Range 元数据回退、重定向、超时、重试和 `.part` 续传必须复用 Electron session requester，不能改用裸 Node TLS。
3. `x-tos-meta-version` 优先做 SemVer 判断；固定对象没有版本元数据时首次只建指纹基线，后续 ETag/Last-Modified/Content-Length 变化才提示更新，且不得静默降级。
4. macOS 自动安装强制要求 `x-tos-meta-sha256`。缺失时在下载前返回 `integrity-metadata-missing`，提示通过发布脚本重新上传；禁止因为历史包是 ad-hoc 签名而关闭完整性校验。
5. 下载后必须同时验证 SHA-256、完整长度、大小上限和 UDIF 文件尾距末尾 512 字节处的 `koly` 标记；任一失败不得挂载或执行安装。

覆盖交接契约：

1. 客户端必须从持久安装路径启动：目标是 `resolveRemovableAppPath(process.execPath)` 得到的 `.app`，且不得位于 `/Volumes`。从 DMG 直接运行时明确提示先安装到“应用程序”。
2. DMG、handoff、privileged helper、result 和 mount point 全部放在 `{APP_DATA_DIR}/profiles/{ORG_NAME}/cache/client-updates`；先写 `pendingInstall.platform = "mac"`，成功前不得提交 applied 状态。
3. 停止 bundled/本地 Agent 后端并确认安装目录锁已释放，再启动 detached `/bin/bash <handoff>`；主进程用交接 PID 写更新标记、展示退出提示后退出。
4. handoff 等待旧桌面 PID 完全消失，使用 `hdiutil attach -nobrowse -readonly -mountpoint ...` 只读挂载。优先选择根目录 `AgentOS.app`；否则根目录必须恰好只有一个 `.app`，禁止猜测多个候选。
5. 普通发行的源 bundle、staging 和安装后的目标都必须验证 `CFBundleIdentifier = com.hqzyai.agentos`。旧 `com.nousresearch.hermes` 只可作为迁移前客户端的历史身份；唯一例外是 appId 首次切换时通过专用 `dist:mac:appid-bridge` 生成的单版本桥接 DMG。桥接版本 N 发布并完成迁移后，必须以更高版本 N+1 发布最终新身份包，后续不得继续产出桥接包。
6. 当前已安装 app 有真实 TeamIdentifier 时，源 app 必须是相同 TeamIdentifier 且 `codesign --verify --deep --strict` 通过；历史 ad-hoc app 没有 TeamIdentifier 时，仍必须经过第 4 条 TOS SHA-256 门禁。
7. helper 用 `ditto` 复制到目标目录下 staging，旧 app 原子移动为 backup，再把 staging 移到原路径。目标父目录可写时直接执行；只有权限不足时才通过 `osascript ... with administrator privileges` 调用同一个参数化 helper。
8. 安装后必须删除并确认 `.hermes-update-in-progress` 消失，再读取真实 `CFBundleExecutable`，用 `open -n <原 app 路径> --args --updated` 拉起；轮询真实 executable 路径并确认至少持续存活 5 秒，才能写 result `0`、删除 backup/DMG/scripts。
9. 挂载、bundle 校验、安装、清标记、重启或稳定性任一步失败，都要恢复 backup；若尚未替换则直接沿用原 app。必须先写非零 result、再清更新标记并重新打开旧 app，使恢复进程启动时可立即对账并保留 applied 状态，相同对象仍可重试。新 app 已换入但回滚也失败时必须记录独立失败码，禁止继续启动不确定的目标。
10. `HERMES_HOME/logs/client-update-handoff.log` 必须记录等待、挂载、安装、清标记、重启、稳定性和回滚结果，但不得写完整对象 URL、query、token 或云凭证。

回归测试至少覆盖：路径含空格/单引号、`/Volumes` 拒绝、脚本 `bash -n`、等待旧 PID 位于挂载之前、只读挂载、bundle ID/TeamIdentifier 校验、staging/backup 顺序、清标记位于重启之前、5 秒存活门禁、失败回滚与旧版重启，以及成功前 applied 状态不变。

Windows 更换运行时 appId 时，NSIS `guid` 和 MSI `upgradeCode` 必须显式保留历史安装产品值，覆盖更新仍传 `/D=<原目录>`；禁止让 electron-builder 根据新 appId 重新派生安装 GUID，否则系统会保留两个卸载项。macOS appId 桥接发布必须走独立构建/上传命令，普通 `dist:mac` 的产物和自动更新校验始终使用 `com.hqzyai.agentos`。普通对象存储上传必须按文件名排除所有 `appid-bridge` 产物，即使当前版本正式包缺失也不得回退选择桥接包；专用桥接上传反过来只接受 `appid-bridge` 命名的 DMG。

### Windows 更新网络栈

对象存储在浏览器中可以下载，不代表 Node `https` 一定能访问。生产 Windows 经常
依赖系统代理、PAC、企业证书或 Chromium/Electron 的网络配置；直接用 Node socket
会出现 `Client network socket disconnected before secure TLS connection was
established`，即使用户的浏览器访问完全正常。

最终实现使用 `electron-net-request.cjs` 创建统一 requester，并同时传给
`fetchPackageMetadata()` 和 `downloadPackage()`：

- 优先使用当前 Electron session 的 `session.fetch`，没有可用 session 时回退
  `electron.net.fetch`，从而继承系统代理、PAC 和受信任证书。
- 元数据先发 `HEAD`；对象存储不支持 HEAD 时发 `Range: bytes=0-0`。如果服务端
  忽略 Range 返回 200，拿到响应头后立即取消 body，禁止为检查版本下载完整 EXE。
- 正式下载复用 `.part` 文件并根据已有字节发送 Range；服务端不支持续传时安全地
  重新下载，不能把两段内容拼成损坏安装包。
- 每次连接和流式读取的无活动超时为 15 秒；连接最多尝试 3 次，重试间隔按
  `250ms * attempt` 线性增加。不能无限重试，也不能因一次瞬时 TLS 失败立即宣告更新失败。
- 最多跟随 5 次重定向；HTTPS 源只能继续跳转到 HTTPS，禁止静默降级 HTTP。
- 更新包最大 1 GiB，并校验完整 Content-Length、SHA-256（对象提供时）和 Windows
  `MZ` 文件头。任一校验失败都不得运行安装器。
- UI 只显示归一后的中文可操作提示，例如“无法连接更新服务器，请检查网络或系统
  代理后重试”；原始 socket/TLS 错误写日志用于诊断，但日志不得包含带签名查询参数
  的完整对象存储 URL。

回归测试至少覆盖：session requester 被实际调用、Range header 保留、连接失败后第三次
成功、HTTPS 降级被拒绝、网络错误中文归一、HEAD fallback、断点续传和完整性校验。

### dev server 端口故障

`npm run dev` 可能失败：

```text
Error: Port 5174 is already in use
```

这不是 `simple-git` 或 Electron main process 崩溃。先检查旧 Vite/node 进程，再重新运行 dev。不要把端口占用误判成 packaged dependency 问题。

### Vite dependency optimization 依赖故障

`npm run dev` 也可能在 Vite 已经监听成功后失败：

```text
Error during dependency optimization:
Could not resolve '../_internal/isEqualsSameValueZero.mjs' in node_modules/es-toolkit/dist/compat/index.mjs
Could not resolve './array/castArray.mjs' in node_modules/es-toolkit/dist/compat/index.mjs
```

这是 `mermaid -> es-toolkit` 的上游依赖包内容和入口文件不匹配，不是桌面业务代码错误。当前审计基线用根 `package.json` 的 `overrides.es-toolkit = "1.48.0"` 固定到已验证包含 `dist/_internal/isEqualsSameValueZero.mjs` 和 `dist/compat/array/castArray.mjs` 的版本。

验收：

- `npm ls es-toolkit --all` 只能解析到 `es-toolkit@1.48.0`，不能出现 invalid。
- `test -f node_modules/es-toolkit/dist/_internal/isEqualsSameValueZero.mjs` 通过。
- `test -f node_modules/es-toolkit/dist/compat/array/castArray.mjs` 通过。
- `npm run dev` 中 Vite optimizer 不再输出 `UNRESOLVED_IMPORT`。

### assistant-ui 导出与旧 node_modules

Windows 干净构建或切换分支后可能出现 `MISSING_EXPORT`，涉及
`fromThreadMessageLike`、`generateId`、`tailBoundedRemend` 或
`normalizeMathDelimiters`。源码和锁文件当前要求：

- `@assistant-ui/core@0.2.23`
- `@assistant-ui/react@0.14.24`
- `@assistant-ui/react-streamdown@0.3.5`

这三个已锁定版本包含上述导出。相同源码只在某台机器失败时，优先判定该机器根
`node_modules` 残留旧包或与 `package-lock.json` 不一致，不要通过删除业务功能规避。
`scripts/assert-root-install.mjs` 必须在 Vite 启动前校验声明版本、实际安装版本和必需导出；
`fromThreadMessageLike`、`generateId` 应直接从其归属包 `@assistant-ui/core` 导入，不依赖
React 包的转导出。

Windows 修复命令必须从仓库根目录执行：

```powershell
Remove-Item -Recurse -Force node_modules
npm install
npm --prefix apps/desktop run build
```

禁止只在 `apps/desktop` 目录单独安装依赖，否则 npm workspace 的 hoist 结果仍可能与根锁
文件不一致。每次上游合并修改 assistant-ui 版本或相关导入后，必须在无旧 `node_modules`
的 Windows runner 验证一次 `npm run dist:win`。

### Windows 单命令打包入口

Windows 正式打包统一从仓库根目录执行：

```powershell
cd D:\Users\Administrator\PycharmProjects\agentos-desktop
npm run dist:win
```

根 `package.json` 的 `dist:win` 是稳定入口，负责转发到 desktop workspace；desktop 自己的
`dist:win`、`dist:win:nsis`、`dist:win:msi` 必须先调用 `sync:root-deps`。npm 执行 workspace
脚本时工作目录固定为 `apps/desktop`，所以 `sync:root-deps` 必须由
`scripts/sync-root-deps.mjs` 解析仓库绝对路径，再执行根 workspace 安装；禁止依赖 shell 的
`cd ../..`，否则 Windows、PowerShell 和 npm workspace 的工作目录差异容易再次破坏安装。
实际安装等价于
`npm --prefix <repo-root> install --workspace apps/desktop --no-save`。`--no-save` 用于避免不同
npm 版本仅因元数据归一化改写 `package-lock.json`，导致发布包被错误标记为 dirty。

根 `.npmrc` 同时使用 `min-release-age` 和 `min-release-age-exclude`。npm 11.10.0 至 11.16.x
只识别前者、不识别例外列表，会先打印 `Unknown project config`，随后在
`engine-strict=true` 下以 `EBADENGINE` 终止。因此根 `package.json` 必须用
`packageManager: npm@11.17.0` 固定一个可用自举版本；`sync-root-deps.mjs` 必须直接探测
`npm_execpath --version`，不能信任可能继承自外层进程的 `npm_config_user_agent`。发现禁用区间
时，在系统临时目录通过当前 npm 的 `exec --package npm@11.17.0` 启动临时 npm，再用仓库
绝对 prefix 安装依赖。该流程不得全局升级或替换用户的 npm，也不得关闭 `engine-strict`。

自举阶段必须删除从父 npm 脚本继承的 `npm_config_engine_strict`、
`npm_config_local_prefix`、`npm_config_min_release_age` 和
`npm_config_min_release_age_exclude`，避免旧 npm 在取得 11.17.0 之前先被仓库配置拦截；临时
npm 执行带根 prefix 的正式安装时会重新读取根 `.npmrc`，安全策略仍然生效。网络代理、npm
cache 等用户配置必须保留。最外层旧 npm 可能在进入脚本前打印一次未知配置 warning，这是
旧 npm 自身行为，不是构建失败；后续不能再出现 `EBADENGINE` 或 `ETARGET`。

调用方可以从仓库根目录使用标准入口；即使直接在 `apps/desktop` 执行 Windows 打包，
也必须得到相同的自动依赖同步行为。不能依赖操作者按当前目录拼接 `node_modules`
清理路径。该契约解决以下易错场景：

- 根目录执行 `npm run dist:win` 报 `Missing script: "dist:win"`。
- 源码已更新但根 `node_modules` 仍保留旧 assistant-ui 版本。
- 在 `apps/desktop` 中误删 `apps/desktop/apps/desktop/node_modules`，实际根依赖未清理。
- 直接从 `apps/desktop` 打包时绕过根脚本，旧 assistant-ui 依赖再次进入 Vite。
- Node 24 搭配 npm 11.10 至 11.16 时，自动安装在 Vite 构建前以 `EBADENGINE` 退出。

`apps/desktop/scripts/assert-root-install.mjs` 仍是打包前的最终一致性闸门，自动安装
后如果声明版本、实际版本或必需导出仍不一致，必须终止打包，不能带病生成安装包。
产物位于 `apps/desktop/release/AgentOS-<version>-win-x64.exe`。

固定回归必须包含：`npm 10.9.8` 直接同步路径、`npm 11.13.0` 临时切换至 11.17.0 的真实
同步路径、`scripts/sync-root-deps.test.mjs`、`scripts/assert-root-install.mjs`、desktop
`typecheck` 和完整 `build`。测试后 `package-lock.json` 不得产生变化。

## 7. GitHub Actions workflow

文件：

- `.github/workflows/sync-hermes-agent.yml`

当前名称：

```yaml
name: Build desktop app
```

触发：

- push to `main`
- `workflow_dispatch`

权限：

```yaml
permissions:
  contents: write
```

这用于 release upload。

### matrix

OS：

- `ubuntu-latest`
- `macos-latest`
- `windows-latest`

package cmd：

- Ubuntu：
  - `npm run build`
  - `npm run builder -- --linux AppImage`
- macOS：
  - `npm run dist:mac`
- Windows：
  - `npm run dist:win`

Windows 正式包只能在 `windows-latest` 或等价 Windows 构建机执行。`dist:win` 会设置
`HERMES_DESKTOP_BUNDLE_AGENT=1` 并生成 Windows 原生 Python、uv、node-pty 等 payload；
macOS/Linux 不得伪造该 payload。跨平台排查 NSIS 配置时可以显式设置
`HERMES_DESKTOP_BUNDLE_AGENT=0`，但产物只用于编译验证，禁止发布。

`scripts/run-electron-builder.mjs` 是 ESM 入口。上游同步或冲突处理后必须满足：

- 主模块判断使用 `import.meta.url`/`fileURLToPath`，禁止出现 `require.main` 或裸 `module`。
- 对外使用 `export`，禁止在 `.mjs` 中写 `module.exports`。
- `scripts/run-electron-builder.test.cjs` 必须动态导入真实的 `.mjs` 文件，不能引用已删除的
  `run-electron-builder.mjs`。
- 合并后至少执行 `node --test scripts/run-electron-builder.test.cjs`，并让 Windows runner 执行
  一次完整 `npm run dist:win`。

timeout：

- 120 minutes。

concurrency：

- group `desktop-build-${{ matrix.os }}`
- `cancel-in-progress: false`

### setup

steps：

- checkout main，fetch-depth 0。
- setup Node.js 24。
- setup Python 3.11。
- setup uv。
- Linux 安装：
  - git
  - curl
  - xz-utils
  - build-essential
  - ripgrep
- `npm install`。

注意：

- 使用 `npm install`，不是 `npm ci`，因为 workspace `file:` deps 需要兼容。

### 注入 BFF config

发行构建配置：

```bash
# 裸打包使用 write-release-config.cjs 内置的当前正式云机。
npm run dist:mac

# 租户包必须显式覆盖 BFF，不改源码 defaults。
AGENTOS_DESKTOP_BFF_BASE_URL="https://tenant.example.com:5443" \
AGENTOS_DESKTOP_TENANT_ID="tenant-a" \
npm run dist:mac
```

规范：

- `write-release-config.cjs` 在每次构建时选择裸打包默认 BFF 或租户显式参数。
- 校验 URL 必须为 HTTP(S)，不得带用户名、密码、query 或 fragment。
- 规范化并移除误传的 `/desktop/hosted-gateway` 后缀。
- 写入 `build/desktop-release.json`，禁止改写 `apps/desktop/config/defaults.json`。

不要把这个值理解为源码默认值。源码默认仍可本地。

迁移注意：

- 上面的 `115.190.254.114:5001` 是 `write-release-config.cjs` 当前裸打包默认的正式云机值，
  不是源码默认值或新 desktop 的永久协议；当前源码联调默认是 `192.168.2.10:5001`。
  发行时按租户实际环境通过环境变量替换，并保留部署所需的显式端口。
- 新 desktop 必须把发行 BFF 作为 CI/secrets/release 参数输入，再写入独立发行配置；不要改写 defaults。
- 文档、UI 和源码都应继续表达“BFF base”，不要写成 hosted gateway URL。

### Build env

```yaml
env:
  CSC_IDENTITY_AUTO_DISCOVERY: false
  HERMES_DESKTOP_BUNDLE_AGENT: "1"
  AGENTOS_DESKTOP_BFF_BASE_URL: ${{ secrets.AGENTOS_DESKTOP_BFF_BASE_URL }}
  GITHUB_SHA: ${{ github.sha }}
  GITHUB_REF_NAME: ${{ github.ref_name }}
```

### 租户级客户端更新源

客户端安装包更新不经过 BFF。检查版本、下载 Windows EXE/macOS DMG、断点续传和完整性校验均直接访问对象存储。每个租户使用不同更新源时，不允许把租户 ID 作为运行时参数传给公共下载接口，也不允许登录后临时拼接对象地址；应在构建该租户安装包时写入固定更新源。

构建参数：

```bash
AGENTOS_DESKTOP_TENANT_ID=tenant-a \
AGENTOS_DESKTOP_UPDATE_URL_MAC=https://tenant-a-download.example.com/desktop/AgentOS-mac-arm64.dmg \
AGENTOS_DESKTOP_UPDATE_URL_WINDOWS=https://tenant-a-download.example.com/desktop/AgentOS-win-x64.exe \
npm run dist:mac

AGENTOS_DESKTOP_TENANT_ID=tenant-a \
AGENTOS_DESKTOP_UPDATE_URL_WINDOWS=https://tenant-a-download.example.com/desktop/AgentOS-0.19.0-win-x64.exe \
npm run dist:win
```

PowerShell：

```powershell
$env:AGENTOS_DESKTOP_TENANT_ID = "tenant-a"
$env:AGENTOS_DESKTOP_BFF_BASE_URL = "https://tenant-a.example.com:5443"
$env:AGENTOS_DESKTOP_UPDATE_URL_MAC = "https://tenant-a-download.example.com/desktop/AgentOS-mac-arm64.dmg"
$env:AGENTOS_DESKTOP_UPDATE_URL_WINDOWS = "https://tenant-a-download.example.com/desktop/AgentOS-0.19.0-win-x64.exe"
npm run dist:win
```

实现契约：

- `scripts/write-release-config.cjs` 在每次 `build` 时生成 `build/desktop-release.json`，禁止复用上一次租户构建的临时配置。
- electron-builder 必须把该文件复制为 `resources/desktop-release.json`。
- `desktop-release.json` 当前 schema 为 3，同时持久化 `downloads.windows` 与 `downloads.mac`；Electron main process 在 packaged 模式从 resources 文件读取 BFF 与当前平台更新源。开发模式、缺少该文件的旧安装包，以及 schema v1/v2 旧包缺失的字段，才从该安装包内置的 `config/defaults.json` 补齐。
- `AGENTOS_DESKTOP_BFF_BASE_URL` 必须是 HTTP(S) base URL，禁止凭证、query 和 fragment；允许传入 hosted gateway URL，但落盘前必须去掉该后缀。
- `AGENTOS_DESKTOP_UPDATE_URL_WINDOWS` 必须是 HTTPS，路径必须以 `.exe` 结尾，禁止 URL 内嵌用户名或密码。
- `AGENTOS_DESKTOP_UPDATE_URL_MAC` 必须是 HTTPS，路径必须以 `.dmg` 结尾，禁止 URL 内嵌用户名或密码。
- 同一租户发布的新 EXE/DMG 必须继续内置该租户自己的两平台更新源，否则更新后会切回错误租户的对象存储。
- `scripts/upload_tos.py` 必须使用与 `write-release-config.cjs` 相同的环境变量优先级；显式租户 URL 优先于 `defaults.json`。禁止出现安装包内置租户 A 地址、publish 阶段却把文件上传到默认租户对象的分叉。
- 不在日志和 UI 中展示完整对象存储 URL；构建日志最多输出 origin。

目标版本来源按优先级为：

1. 对象响应头 `x-tos-meta-version`、`x-agentos-version` 或 `x-version`。
2. `Content-Disposition` 文件名中的 `x.y.z`。
3. 对象 URL 文件名中的 `x.y.z`，例如 `AgentOS-0.19.0-win-x64.exe`。

预发布版本必须使用对象元数据明确写入，例如 `x-tos-meta-version: 0.20.5-rc.1`。文件名回退只解析稳定的 `x.y.z`，避免把平台/架构后缀误识别成预发布后缀。Windows 建议、macOS 强制同时发布 `x-tos-meta-sha256`；统一使用 `npm run upload:tos` 写入 version/sha256 元数据，禁止把手工上传但缺元数据的 DMG 作为正式自动更新对象。

更新弹窗必须显示：

- 已是最新：显示当前客户端版本。
- 有可用更新：显示“当前版本 vX.Y.Z”和“更新至 vA.B.C”。
- 目标对象未提供版本信息时，不得伪造目标版本；更新可继续按 ETag/Last-Modified/Content-Length 指纹判断，但发行流程应修复对象元数据。

### 客户端更新与后端运行时更新的边界

Desktop 产品只有一种更新目标：当前租户发布的 AgentOS 客户端安装包。

- 系统页、关于页、命令面板、更新弹窗、启动检查、30 分钟轮询和窗口聚焦检查，全部必须调用 Electron 安装包更新 bridge。连接本地或远程网关不得改变更新目标。
- Desktop renderer 不得导入或调用 `checkHermesUpdate()` / `updateHermes()`，不得访问 `/api/hermes/update/check` 或 `POST /api/hermes/update`。后端 contract 落后只提示部署方升级，不提供“立即更新后端”操作。
- 上游多连接注册表即使提供“更新所有实例”能力，AgentOS Desktop 也只能保留连接的新增、编辑、测试、切换和删除。必须删除 `hermes:connections:update-all` IPC、preload bridge 及设置页批量更新按钮，禁止 Electron main 逐个向本地、远程或 SSH 实例发送 `POST /api/hermes/update`。服务端镜像和运行时版本由部署流程统一发布，不能由终端用户的客户端跨实例修改。
- server/dashboard 可保留 `/api/hermes/update*` 兼容路由给独立管理面使用；其 action name 仍必须是 `agentos-update`，日志必须是 `agentos-update.log`。容器部署应返回 externally-managed/unsupported。
- Electron main 仅从 `resources/desktop-release.json` 解析当前平台的租户包地址。Windows 使用 `.exe`，macOS 使用 `.dmg`；未配置、地址无效或当前平台尚未支持时必须 fail closed，返回 `supported: false` / `agentos-package-source-unavailable`，不得尝试 Git checkout、Nous release feed、staged updater、`hermes update` 或源码重建。
- 首次安装和修复只能使用当前发行包的 `bundled-agent` 与 `bundled-installer`。打包资源缺失是发行失败，不是下载 Nous/Hermes 安装脚本或使用旧 Hermes checkout 的理由。
- 关于页和版本 IPC 显示 `app.getVersion()` 的 AgentOS 包版本，不显示后端 Hermes 运行时版本，不链接 Nous release notes。`apps/desktop/package.json` 的 author/Linux maintainer，以及 Windows EXE 的 ProductName、FileDescription、CompanyName 和版权都必须是 AgentOS。
- UI 按钮、进度、完成状态、错误、SSH 升级建议和远程安装建议统一写 AgentOS；禁止向用户展示 Nous/Hermes 安装地址。历史 action `hermes-update` 可在显示层映射为 `agentos-update`。
- Desktop README、首次接入页和帮助入口不得把 Nous/Hermes release、文档或社区地址描述为 AgentOS 的安装、更新或支持渠道；当前租户没有配置对应入口时应隐藏链接，而不是回退到上游链接。
- `apps/desktop/electron/update-source-policy.test.ts` 是更新边界的静态回归门禁；合并上游后必须保持通过，禁止删除断言来迁就重新引入的 Hermes/Nous 更新代码。

普通新产物必须使用 `com.hqzyai.agentos` appId/AUMID。Windows NSIS 新装目录固定为 `%LOCALAPPDATA%\Programs\hqzy\AgentOS`，MSI 用 `menuCategory=hqzy` 形成同级目录；macOS PKG/DMG 安装命令固定为 `/Applications/hqzy/AgentOS.app`，DMG 不得保留指向 `/Applications` 的拖放快捷方式；自动更新继续按当前真实路径原位覆盖，避免运行中移动自身。正式 DMG 上传与一次性 appId 桥接 DMG 上传必须双向隔离，任何缺包回退或显式文件参数都不得让桥接包进入正式对象键。客户端默认 userData、sessionData、更新缓存、Electron 日志、crash dump 和 Desktop 管理的 Agent 数据统一放在 `{APP_DATA_DIR}/profiles/{ORG_NAME}`，并按 `desktop/`、`cache/`、`logs/electron/`、`crash-dumps/`、`agent-data/` 分区。WSL 字体配置/缓存也必须放在 profile 的 `cache/fontconfig` 并通过 `FONTCONFIG_FILE` 使用，不得重新写 `~/.config/fontconfig`；本地 SSH ControlMaster 仅可使用短期、权限校验后的 `/tmp/hqzy-agentos-ssh-<uid>` socket，不得重建旧 `~/.hermes`。

旧 Electron userData 与 `%LOCALAPPDATA%\hermes` / `~/.hermes` 必须在读取认证前无损迁移；目标有冲突时新目录优先，旧树保留到 `migration-backups/`，禁止覆盖或删除恢复副本。`HERMES_DESKTOP_USER_DATA_DIR` 仍只用于测试隔离，显式非默认 `HERMES_HOME` 仍受支持。`hermes:*` IPC、`HERMES_HOME` 环境变量名、`.hermes-update-in-progress` 和底层 `hermes` 可执行文件继续作为后端兼容协议保留；远程实例路径不随本地客户端目录迁移。

### payload verification

macOS/Linux bash：

- manifest 必须存在。
- manifest 不能 skipped/bundled false。
- 检查 `hermes_cli/main.py`。
- 检查 `venv/bin/python`。

Windows PowerShell：

- manifest 必须存在。
- skipped/bundled false fail。
- 检查 `hermes_cli/main.py`。
- 检查 `venv/Scripts/python.exe`。

重要：

- Windows path 用 PowerShell。
- 非 Windows 不要检查 Windows python。

### Release upload

tag：

```text
desktop-v<version>
```

逻辑：

- 如果 release 不存在，创建。
- title 是 tag。
- notes 包含日期和 offline bundled Agent runtime。
- 上传 `apps/desktop/release` 下文件，`--clobber`。

## 8. Server 源码覆盖镜像和部署隔离

### 两种镜像构建方式

仓库同时保留两个用途不同的 Dockerfile：

- `Dockerfile` 是源码覆盖派生镜像。默认 `ARG HERMES_BASE_IMAGE=hermes-agent:hqzy-runtime`，
  从已验证可运行的基础镜像继承系统包、Python venv、Node、浏览器及其他大依赖，只
  覆盖当前源码，重新构建 `web`、`ui-tui`，并用现有 venv 执行
  `uv pip install --no-deps -e .`。它适合代码、前端和 Python 包变更但依赖集合未变化
  的快速验证与发布。
- `Dockerfile.source-build` 从基础操作系统完整构建全部运行环境。只有构建机没有
  可信基础镜像、底层系统/Python/Node/.NET/浏览器依赖发生变化，或需要重建可审计
  基线时才使用；不要把它和快速源码覆盖当成同一个入口。

源码覆盖构建必须重新生成前端 bundle，不能只 COPY 一个 Python 文件。`COPY . .`
会覆盖基础镜像中曾打过的补丁，因此 Dockerfile 还要重放飞书卡片和 dashboard 产品策略
补丁，并写入 `.hermes_build_sha` 供运行时审计。

源码覆盖镜像复用基础镜像的 `/opt/hermes/.venv`，所以不能假定其核心数值依赖与当前
源码 lock 一致。当前 Dockerfile 在 editable 源码安装后显式执行
`uv pip install --no-deps "numpy==2.4.3"`；上游修改锁定版本时必须同步这里并运行
voice/wake/STT import 测试，避免可选音频包加载到旧 NumPy ABI。

另外，被动 dashboard/voice/wake 状态探测不得触发 `faster-whisper` 安装。只有通过验证的
真实转写路径可以调用有界 lazy install；并发请求共享一次安装 flight。源码镜像默认
`HERMES_DISABLE_LAZY_INSTALLS=1` 时，这条路径应快速返回不可用，而不是阻塞 gateway WS reader。

### 镜像大小如何解释

派生镜像显示约 3.93 GB 不代表本次源码层增加了 3.93 GB；`docker images` 展示的是
镜像可见文件系统的虚拟总大小，包含全部基础层。应使用 `docker history <image>`、
`docker image inspect` 和层 digest 区分基础镜像体积与新增源码层。旧
`hermes-agent` 显示 14 GB 通常意味着它来自不同的完整构建、包含浏览器/编译缓存/
多套依赖或历史大层；不能仅凭 tag 名认定两者是同一基础。

构建新 tag 不会修改已有基础镜像，也不会影响基于该基础镜像的其他派生镜像。镜像层
按 digest 不可变并可共享；真正有风险的是复用同一个可变 tag、删除/prune 共享层，或
重建已有容器。生产和验收必须使用新 tag，发布时优先固定 digest。

### 与现有 AgentOS Docker 环境并行验证

本地验证必须加入现有 `agentos-network`，并使用独立资源，不能把一个临时测试容器
直接替换成现有服务：

```bash
docker build \
  --build-arg HERMES_BASE_IMAGE=hermes-agent:hqzy-runtime \
  --build-arg HERMES_GIT_SHA=$(git rev-parse HEAD) \
  -t agentos:local-$(git rev-parse --short HEAD) \
  -f Dockerfile .

docker run -d \
  --name agentos-source-test \
  --network agentos-network \
  -p 19129:9119 \
  -v agentos-source-test-data:/opt/data \
  agentos:local-$(git rev-parse --short HEAD)
```

端口、启动命令和健康检查可按实际镜像入口调整，但以下隔离不可省略：

- 容器名、host port、volume、image tag 都与现有实例不同。
- gateway 和 dashboard 在正式 Compose 中使用同一个 `HERMES_IMAGE`，避免前后端代码版本不一致。
- 配置、凭据、会话和租户数据位于 `/opt/data`；换镜像只替换 `/opt/hermes` 代码，
  不得把生产 `/opt/data` 挂给临时测试容器进行写测试。
- 禁止执行 `docker compose down -v`、`docker system prune` 或删除基础 tag 来“清理”
  测试环境；只停止并删除本次独立测试容器和 volume。
- 回滚通过把 `HERMES_IMAGE` 切回上一固定 tag/digest 并重建 gateway/dashboard 完成，
  不在运行容器中手工覆盖源码。

### 派生镜像验收

- `cat /opt/hermes/.hermes_build_sha` 与目标提交一致。
- `/api/status`、`/api/config`、`/api/model/options` 和 hosted gateway WebSocket 可用。
- dashboard 前端是本次源码构建产物，不保留旧 Hermes/Nous 用户可见品牌。
- AgentOS 模型、技能和工具集产品策略生效。
- gateway/dashboard 读取同一代码镜像，数据卷升级前后完整。
- 删除测试容器后，原有基础镜像、其他派生镜像和正在运行的 AgentOS 容器不受影响。

## 9. 哪些历史逻辑不是最终规范

早期 workflow 名字仍叫 `sync-hermes-agent.yml`，但当前内容是 build desktop app，不是 daily upstream sync。

不要把以下作为最终目标：

- 每日自动同步 upstream。
- merge upstream 后清理 workflow 文件。
- no-commit merge 排除 source workflow。

这些是历史迭代过程。最终规范是：

- main push 构建 desktop。
- 构建前注入 BFF。
- 三平台 package。
- 验证 bundled agent。
- 上传 release。

## 10. 常见失败模式

### 构建成功但离线启动失败

检查：

- `build/bundled-agent/manifest.json` 是否 `skipped:true`。
- `build/bundled-agent/hermes-home/hermes-agent/hermes_cli/main.py` 是否存在。
- schema 是否为 2，三个安全能力字段是否都为 true，platform/arch 是否匹配。
- agent 与 browser-use 的 Python、标准库和 console entrypoint 是否都存在。
- payload 内是否有 `pyvenv.cfg`、symlink/shebang/editable metadata 指向 build temp 或构建机。
- payload 内是否有凭据路径、private key 或真实 secret assignment。

### Windows installer 构建失败

检查：

- 是否使用 win32-x64 Electron runtime。
- `electron-builder-win.cjs` 是否传入。
- `HERMES_ELECTRON_BUILDER_SKIP_LOCAL_DIST=1` 是否设置。
- 当前 schema 2 staging 是否明确报 `Windows standalone Python bundling is not yet verified` 或
  `Windows offline payload relocation is not yet verified`。这是有意的 fail-closed，不是可以
  跳过的普通 builder 错误；先实现并执行重定位后的 Windows Python/Hermes/browser-use 验证。
- path 是否过长，payload 是否包含 website/tests。

### macOS DMG 体积异常

如果 `npm run dist:mac` 生成的 DMG 接近或超过 1GB，先拆分检查：

```bash
du -sh apps/desktop/build/bundled-agent
du -sh apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/*
du -sh apps/desktop/release/mac-arm64/AgentOS.app/Contents/Resources/bundled-agent/hermes-home/hermes-agent/apps
find apps/desktop/build/bundled-agent -type f \( -name 'AgentOS-*.dmg' -o -name 'AgentOS-*.zip' -o -name 'AgentOS-*.exe' -o -name 'AgentOS-*.AppImage' \)
```

典型错误是 `hermes-agent/apps` 中包含上一次生成的三平台安装包。修复后该目录只能包含 `shared`，`find` 命令必须无输出；`stage-agent-payload.test.cjs` 还必须同时断言 `apps/shared` 被保留、`apps/AgentOS-*` 被排除。

当前完全离线 macOS arm64 包的量级参考：

- `bundled-agent` 未压缩约 800MB，主要是 Python venv 和 Node runtime dependencies。
- `AgentOS.app` 未压缩约 1.1GB。
- DMG 压缩后约 300-400MB。

不要仅凭 APP 未压缩体积判断异常；关键是检查是否出现嵌套安装包，以及 DMG 压缩后的最终体积。

### Linux AppImage 找不到

electron-builder 可能输出：

- `AgentOS-<version>-linux-x64.AppImage`
- `AgentOS-<version>-linux-x86_64.AppImage`

build script 应查两个候选并复制成统一 x64 文件名。

### CI payload skip

可能原因：

- `HERMES_DESKTOP_BUNDLE_AGENT` 没设置。
- `HERMES_DESKTOP_SKIP_AGENT_PAYLOAD=1` 被错误设置。
- install stamp 缺失。
- install script 缺失。
- stage 失败。

CI 必须 fail，不允许继续 upload。


### Electron 启动时报 simple-git 缺失

症状：

```text
Cannot find module '.../Resources/native-deps/vendor/node_modules/simple-git'
Require stack:
- apps/desktop/electron/git-review-ops.cjs
- apps/desktop/dist/electron-main.mjs（源码入口是 `electron/main.ts`）
```

检查：

- repo root 是否执行过 `npm install`。
- `node -p "require.resolve('simple-git')"` 在 `apps/desktop` 下是否能解析。
- 是否仍在运行旧 `git-review-ops.cjs`/旧 `electron-main.mjs`；当前源码入口应是
  `git-review-ops.ts`，`simple-git` 应被打入新 main bundle。
- `npm run build` 是否执行了 `stage-native-deps.mjs`。
- `dist/electron-main.mjs` 是否已经重新生成，且不含 vendor fallback 路径。
- packaged app 的 `app.asar.unpacked/dist/node_modules/node-pty`（以及适用时 `get-windows`）
  是否存在；这与 simple-git 的纯 JS bundle 是两条链路。

修复原则：

- dev 构建从 root `node_modules` 解析输入依赖，再由 esbuild 生成 main bundle。
- packaged 模式的纯 JS 依赖来自 bundle；native external 来自
  `app.asar.unpacked/dist/node_modules`，不再读取 `process.resourcesPath/native-deps/vendor`。
- 构建阶段缺纯 JS 依赖应立即失败；不能发布一个等到用户打开 Review 才报缺模块的包。

### npm run dev 端口占用

症状：

```text
Error: Port 5174 is already in use
```

检查：

- 是否有旧的 Vite/node dev server 占用 5174。
- 停掉旧进程后再跑 `npm run dev`。
- 如果要验证 Electron main process，可在 renderer 已启动时单独跑 `npm run dev:electron`。

这个问题和 bundled payload、simple-git staged resources 无关，不要混在一起修。

### BFF 地址错误

症状：

- 登录页访问错误服务。
- 服务端 HTML 被返回。
- hosted gateway path 重复追加。

检查：

- `defaults.json` 是 BFF base。
- Settings 展示 BFF base。
- 保存 connection 写 hosted gateway URL。
- login 调 BFF `/auth/login`。

## 11. 迁移 checklist

新 desktop 打包前确认：

- `dist:*` 都默认 `HERMES_DESKTOP_BUNDLE_AGENT=1`。
- `build` 包含 `stage-installer-script.cjs`、`stage-agent-payload.cjs`、`stage-native-deps.mjs`。
- `build` 包含 `write-release-config.cjs`，每次构建重新生成租户发行配置。
- 裸 `dist:*` 生成的发行配置使用当前正式云机；租户构建通过 `AGENTOS_DESKTOP_BFF_BASE_URL` 覆盖，且不得修改源码 defaults。
- `extraResources` 包含 `build/desktop-release.json`、`build/bundled-installer`、
  `build/bundled-agent`；native external 由 `dist/node_modules` 随 `dist/**` 进入 asar unpacked。
- 不依赖工作区残留的 `build/native-deps`；删除 legacy extraResources 前后都用 clean build
  验证 packaged app。
- `stage-agent-payload` 在 repo 外 staging。
- 排除非 runtime 大目录。
- Windows 和 Unix install stages 分开。
- schema 2 manifest 成功和 skip marker 语义保留，成功 manifest 最后写入。
- symlink 物化；agent/browser-use Python 自包含，entrypoint 可迁移，平台/架构严格匹配。
- 构建机凭据、secret、private key、`pyvenv.cfg`、绝对 Python/work-root/editable 路径全部拒绝。
- packaged app `seedBundledAgent` 支持 resources path。
- `simple-git` 等纯 JS main-process 依赖进入 `electron-main.mjs`；只有 external/native
  依赖从 `app.asar.unpacked/dist/node_modules` 解析。
- `package-lock.json` 中 workspace 包名和 `apps/desktop/package.json` 保持一致。
- CI 注入 BFF config。
- CI 按租户注入 `AGENTOS_DESKTOP_TENANT_ID`、`AGENTOS_DESKTOP_UPDATE_URL_WINDOWS` 和 `AGENTOS_DESKTOP_UPDATE_URL_MAC`；客户端更新直接走该租户对象存储，不经过 BFF。
- 客户端版本检查和安装包下载共用 Electron session requester，系统代理/PAC/TLS、重试、重定向、超时、Range 和完整性校验契约都保留。
- server 代码改动按依赖变化选择源码覆盖或完整构建；新镜像使用独立 tag/digest，并在 `agentos-network` 通过隔离容器、端口和 volume 验证。
- CI 三平台都验证 payload。
- release upload 不上传空文件。
- 普通 `dist:mac` / `dist:win` 不调用上传脚本；只有 `upload:tos` 与 `dist:*:publish` 可以写对象存储。
