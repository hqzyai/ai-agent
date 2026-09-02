# 聊天展示、工具行、媒体和会话产物规范

本文记录 AgentOS desktop 在聊天消息、工具调用、媒体渲染、远程文件下载、会话产物上的改造细节。新 desktop 迁移时，最容易漏的是远程文件和媒体。请先记住一条主规则：

```text
remote mode 下，agent 看到的文件路径通常属于远端 gateway 机器，不属于 desktop 本机。
```

所以 renderer 不能直接用 `file://` 读远端产物。

## 1. 关键文件

聊天消息处理：

- `apps/desktop/src/lib/chat-messages.ts`
- `apps/desktop/src/lib/chat-runtime.ts`
- `apps/desktop/src/app/session/hooks/use-message-stream.ts`
- `apps/desktop/src/app/session/hooks/use-prompt-actions.ts`

工具行处理：

- `apps/desktop/src/components/assistant-ui/tool-fallback-model.ts`
- `apps/desktop/src/components/assistant-ui/tool-fallback.tsx`
- `apps/desktop/src/lib/summarize-command.ts`
- `apps/desktop/src/store/tool-diffs.ts`
- `apps/desktop/src/store/tool-dismiss.ts`
- `apps/desktop/src/store/tool-view.ts`

媒体处理：

- `apps/desktop/src/lib/media.ts`
- `apps/desktop/src/components/assistant-ui/markdown-text.tsx`
- `apps/desktop/src/components/chat/generated-image-result.tsx`

文件下载和产物：

- `apps/desktop/src/lib/files.ts`
- `apps/desktop/electron/main.ts`
- `apps/desktop/electron/preload.cjs`
- `apps/desktop/src/app/artifacts/index.tsx`
- `apps/desktop/src/app/chat/session-artifacts-dialog.tsx`

## 2. ChatMessage 数据模型

`ChatMessage` 是 desktop renderer 内部模型：

```ts
export type ChatMessage = {
  id: string
  role: SessionMessage['role']
  parts: ChatMessagePart[]
  timestamp?: number
  pending?: boolean
  error?: string
  branchGroupId?: string
  hidden?: boolean
  attachmentRefs?: string[]
}
```

重要字段：

- `parts`：assistant-ui message content，不是单纯 string。
- `hidden`：隐藏消息参与合并逻辑，但不应渲染。
- `attachmentRefs`：用户提交时附带的 composer ref。
- `pending`：前端 optimistic message 或 streaming 状态。

迁移时不要把消息简化成 `{ role, content }`，否则会丢失工具行、reasoning、media、附件、branch group、hidden retry 等行为。

## 3. 用户消息显示规则

函数：

- `displayContentForMessage(role, content)`

### 剥离 cron delivery hint

cron job 执行时，后端会把用户 prompt 包在 delivery hint 后面。UI 显示历史消息时不能把内部 hint 当作用户输入。

识别：

```ts
const CRON_DELIVERY_HINT_START = '[IMPORTANT: You are running as a scheduled cron job.'
const CRON_DELIVERY_HINT_END = 'nothing more.]'
```

规则：

- 如果 user message 以该 hint 开头，截掉 hint 到 `nothing more.]`。
- 显示剩余真实 prompt。

### 剥离 attached context

标记：

```text
--- Attached Context ---
```

后面可能是文件、目录、URL、图片、工具、终端上下文。

UI 展示规则：

- `--- Attached Context ---` 前的真实用户输入作为正文。
- attached context 中的 ref 提取为单独 ref 展示。
- `--- Context Warnings ---` 后面的 warning 不作为用户正文展示。

ref regex 支持：

```text
@file:
@folder:
@url:
@image:
@tool:
@terminal:
```

### 图片附件 optimistic 展示

函数：

- `optimisticAttachmentRef(attachment)`

规则：

- image attachment 如果有 `previewUrl` 且是 `data:`，优先显示 data URL。
- 不要先展示 `@image:<localpath>`，因为 remote mode 下 gateway 读不到本地临时路径，会闪 fallback chip。
- 非 image 或 post-sync ref 走普通 `attachmentDisplayText`。

## 4. Assistant 文本和媒体标签

### MEDIA 标签

函数：

- `renderMediaTags(text)`
- `assistantTextPart(text)`

支持格式：

```text
MEDIA: /path/to/video.mp4
MEDIA: "file:///path/to/audio.wav"
MEDIA: `https://.../video.webm`
```

也会检测裸媒体路径：

- `file:///...mp4`
- `/...mp4`
- `./...mp4`
- `../...mp4`
- `~/...mp4`
- `https://...mp4`

支持扩展名：

- video：`avi`、`mkv`、`mov`、`mp4`、`webm`
- audio：`flac`、`m4a`、`mp3`、`ogg`、`wav`

渲染为：

```md
[Video: name.mp4](#media:<encoded path>)
```

然后 markdown renderer 中 `mediaPathFromMarkdownHref` 把 `#media:` 链接转为 `MediaAttachment`。

迁移要点：

- 不要让 `MEDIA:` 原样显示。
- 不要只支持图片，音频/视频也要支持。
- 不要把 `#media:` 当普通 anchor。

## 5. Tool row 展示规则

### ToolView 模型

文件：

- `tool-fallback-model.ts`

`ToolView` 包含：

- `title`
- `subtitle`
- `detail`
- `detailLabel`
- `status`
- `tone`
- `icon`
- `inlineDiff`
- `previewTarget`
- `imageUrl`
- `mediaPath`
- `stdout`
- `stderr`
- `rendersAnsi`
- `hidden`
- `rawArgs`
- `rawResult`

不要绕过 `buildToolView` 自己在组件里解析工具结果，否则会丢掉错误归一、diff、stdout/stderr 分离、search results 和 media path。

### 工具 metadata

常见工具映射：

- `terminal` -> terminal tone，`Ran command`。
- `execute_code` -> terminal tone，`Ran code`。
- `image_generate` -> image tone，`Generated image`。
- `read_file`/`write_file`/`edit_file`/`patch` -> file tone。
- `browser_*` -> browser tone。
- `web_*` -> web tone。
- `cronjob` -> agent tone。
- `todo` -> agent tone。

未知工具：

- 自动 title case tool name。
- browser/web 前缀会自动归类。

### 成功 terminal/execute_code 隐藏

函数：

```ts
function hideToolRow(part: ToolPart, status: ToolStatus): boolean {
  return (part.toolName === 'execute_code' || part.toolName === 'terminal') && status === 'success'
}
```

含义：

- 成功执行的终端命令和代码执行不作为普通工具 row 长期占据聊天。
- 这不是删除数据。raw args/result 仍在 message/tool state 中。
- running/error 状态仍展示。
- approval 等待仍展示。

迁移时不要误删 terminal 工具，也不要把 stdout 直接塞进 assistant 文本。

### 非零 exit code 不一定是错误

`toolErrorText` 的规则：

- `part.isError` 是错误。
- result.error 字符串是错误。
- `success:false` 或 `ok:false` 是错误。
- status 包含 error/failed/failure 是错误。
- 非零 `exit_code` 只有在没有 stdout/stderr/output 时才当错误。

原因：

- `grep` 无匹配返回 1。
- `diff` 有差异返回 1。
- pipeline 可能返回最后一段的码。
- 很多 CLI 把有用信息写 stderr。

迁移时不要简单 `exit_code !== 0` 就红色报错。

### stdout/stderr 分离

对于 `terminal` 和 `execute_code`：

- `rendersAnsi: true`
- `stdout` 单独显示。
- `stderr` 单独显示。
- stderr 使用中性色块，不等于 error tone。
- 如果没有 split stream，则展示 merged `detail`。

组件：

- `tool-fallback.tsx`
- `AnsiText`

### inline diff

工具结果可能含 `inline_diff`。UI 应：

- 去掉 diff chrome。
- 在 tool row 展示 diff preview。
- 支持 live side diff store `$toolInlineDiffs`。
- 保留 copy payload。

### command summary

文件：

- `apps/desktop/src/lib/summarize-command.ts`

目标：

把 agent 包装过的 shell command 展示成用户关心的主命令。

处理步骤：

1. quote-aware 分割 compound command：`&&`、`||`、`;`、newline。
2. 不把 pipe 作为主分段。
3. 去掉 pipe tail：`| head`、`| tail`、`| wc`、`| sort`、`| uniq`。
4. 跳过 setup segment：`cd`、`pushd`、`popd`、`export`、`set`、`unset`、`source`、`.`、`true`、`false`、`:`。
5. 去掉 redirection。
6. 跳过 boundary/status echo。
7. 如果只剩一个核心命令，显示它。
8. 如果多个，显示 `first command + N commands`。

注意：

- 这是 display-only。
- full command 必须仍可复制/查看。

## 6. Media URL 解析

文件：

- `apps/desktop/src/lib/media.ts`

### mediaKind 和 MIME

扩展名映射：

- image：`bmp`、`gif`、`jpeg`、`jpg`、`png`、`svg`、`webp`
- audio：`flac`、`m4a`、`mp3`、`ogg`、`opus`、`wav`
- video：`avi`、`mkv`、`mov`、`mp4`、`webm`
- 其他：`file`

函数：

- `mediaKind(path)`
- `mediaMime(path)`
- `mediaName(path)`

### mediaMarkdownHref

```ts
export function mediaMarkdownHref(path: string): string {
  return `#media:${encodeURIComponent(path)}`
}
```

这是内部 markdown 协议，不是普通 URL。

### mediaExternalUrl

本地模式：

- HTTP URL 原样。
- 文件路径转 `file://`。

远程模式：

- 如果 connection 有 token，可生成 `/api/files/download?path=...&token=...`。
- OAuth remote path 不回退到 `file://`，返回空字符串，调用方应走 `downloadManagedFile/openManagedFile`。

原因：

- OAuth cookie 是 HttpOnly，普通 anchor 无法附带 Electron session cookie。
- 远程文件不在本机。

### 音视频流式播放

本地：

```text
hermes-media://stream/<encoded local path>
```

远程：

```text
hermes-media://remote/<encoded remote path>?profile=<profile>
```

规则：

- 音视频不要用巨大 data URL。
- remote audio/video 用 custom protocol stream，避免二进制损坏并支持 seek。

### resolveMediaSrc

优先级：

1. `data:` 原样返回。
2. HTTP 图片/音视频先 `persistGeneratedMedia`，成功后递归解析 cached path。
3. 查询本地 media cache。
4. remote gateway：
   - audio/video -> `remoteMediaPlaybackUrl`
   - image -> `/api/media`，失败回退 `/api/files/read`
5. local audio/video -> `hermes-media://stream`
6. 非 Electron 环境 -> `mediaExternalUrl`
7. Electron local file -> `readFileDataUrl`

## 7. 远程媒体 cache

main process 相关函数：

- `resolveLocalMediaCache(payload)`
- `persistGeneratedMediaOnGateway(payload)`
- `fetchRemoteManagedFileBuffer(filePath, profile)`
- `remoteHermesHomeCandidates(profile, cacheSubdir, filename)`
- `uploadRemoteMediaBuffer(profile, targetPath, buffer, mimeType)`

### 生成媒体持久化

HTTP 生成图片/视频有效期短，所以要持久化：

1. renderer 看到 HTTP media path。
2. `persistGeneratedMedia(path, kind)` 调 Electron IPC。
3. main process 下载 HTTP resource。
4. 限制大小，超过 `REMOTE_MEDIA_CACHE_MAX_BYTES` 报错。
5. 写本地 cache。
6. 查询远程 Hermes home 候选路径：
   - `/api/status` 的 `hermes_home`。
   - `/api/files` 的 `locked_root` 或 `root`。
   - `/api/files` 的 `path`，拼成 `<path>/.hermes/cache/<subdir>/<filename>`。
   - fallback `cache/<images|videos>/<filename>`。
7. 通过 `/api/files/upload` 上传到远端。
8. 记录 URL -> local/remote mapping。
9. 返回 remote path，后续对话用稳定 remote path。

如果所有远端上传失败：

- 保留本地 cache。
- 返回本地 path。
- 记录 log。

迁移时不要只本地缓存，否则 remote session 历史在另一台机器/另一个窗口打开时可能失效。

### 远程文件本地 cache

`resolveLocalMediaCache` 用于 remote path 本地缓存：

- 先查 mapping。
- 如果 cache hit 且文件存在，直接返回。
- 如果 `fetchIfMissing` 为 false，返回 miss。
- HTTP URL 不走这个缓存。
- remote 文件通过 `/api/files/download` 或 `/api/files/read` 取 buffer。
- 超过大小限制则不缓存。
- 保存到本地 generated media cache，并记录 mapping。

## 8. 文件下载规范

renderer 文件：

- `apps/desktop/src/lib/files.ts`

main process 文件：

- `apps/desktop/electron/main.ts`

preload 暴露：

```js
downloadRemoteFile: payload => ipcRenderer.invoke('hermes:downloadRemoteFile', payload)
downloadRemoteFilesBatch: payload => ipcRenderer.invoke('hermes:downloadRemoteFilesBatch', payload)
listDownloads: () => ipcRenderer.invoke('hermes:downloads:list')
onDownloadProgress: callback => ...
```

### managedPath

renderer 会把 `file://` 解成普通 path。下载函数应接受：

- plain path
- `file://` path
- HTTP URL

### isRemoteManagedPath

远程 managed path 条件：

- 不是空。
- 不是 HTTP URL。
- 当前 `$connection.mode === "remote"`。

### downloadManagedFile

优先级：

1. 如果 Electron IPC `downloadRemoteFile` 存在，统一走 IPC。
2. 如果没有 IPC 且是 HTTP URL，fallback 用 `<a download>`。
3. remote mode 且旧环境没有 IPC 时：
   - token mode 可构造 `/api/files/download?path=...&token=...`。
   - 否则 fallback `/api/files/read` data URL。
4. 都不满足则抛 `Download is unavailable in this environment`。

新 desktop 应保留 IPC 作为主路径。

迁移注意：

- 当前 `downloadManagedFile` 会先检查 IPC，再检查 HTTP URL。
- 在 Electron 桌面环境里，任意 HTTP URL 如果直接传给 `downloadManagedFile`，会先进入 main process 的 `downloadRemoteManagedFile`。
- main process 的 `shouldFetchManagedFileRemotely` 对 HTTP URL 返回 false，随后本地文件解析也会返回 null，最终可能抛 `File not found`。
- 因此普通 HTTP 媒体下载应走 `downloadMediaPath` / `downloadHref` 这条路径，或者在重构时把 HTTP URL 分支前移。
- `downloadManagedFile` 更适合 managed file path：远端 gateway path、本地 path、`file://` path。

### openManagedFile

远程 path：

- 有 IPC 且 remote -> `downloadRemoteFile({ openAfter:true })`。
- token URL 可 `openExternal`。
- legacy remote fallback 下载。

本地 path：

- `openExternal(file://...)`。

### batch download

`downloadManagedFilesBatch(paths)`：

- 如果 IPC batch 存在，走 main process batch。
- 否则逐个 `downloadManagedFile`。

main process batch：

- 打开目录选择框。
- 对每个 remote path 按 basename 拼目标路径。
- 下载成功的 path 加入 `localPaths`。
- 用户取消返回 `{ canceled:true, ok:false }`。

### main process 判断远程或本地

函数：

- `shouldFetchManagedFileRemotely(sourcePath, profile)`

规则：

- 空/HTTP 不 remote fetch。
- resolved backend 不是 remote，不 remote fetch。
- 如果本机能 resolve source path，则本地 copy。
- 如果本机不能 resolve，则 remote fetch。

这样支持 remote mode 下偶尔出现本机路径，也支持 local mode。

### 下载历史

main process 维护：

- `MANAGED_DOWNLOADS_DIR`
- `MANAGED_DOWNLOADS_INDEX_PATH`
- `loadManagedDownloadsIndex`
- `rememberManagedDownload`
- `lookupManagedDownloadEntry`

索引：

- `byRemote`：remote path 或 profile:path -> local path。
- `history`：最多 200 条。

openAfter 时如果 cache 存在，直接打开缓存，不重复保存。

### 远程文件浏览的断链容错

server 的 `GET /api/files` 使用 `os.scandir()` 枚举 managed root。容器挂载、用户清理或
工具并发写文件时，目录中可能短暂存在 broken symlink，或 entry 在枚举后、读取 metadata
前被删除。单个这类 entry 不能让整个文件浏览页返回 500：

- `_managed_file_entry()` 因目标消失而抛出的 `HTTPException`，只有其 `__cause__` 是
  `FileNotFoundError` 时才跳过该 entry。
- 权限、越界、敏感路径和其他 HTTP 错误必须继续失败，不能用宽泛 `except` 吞掉安全边界。
- 顶层目标不存在仍返回 404，目标不是目录仍返回 400，目录不可读仍返回 403。
- 返回路径继续经过 managed-files policy 和 display path 脱敏；容错不意味着暴露真实路径。

测试至少放入一个断链 symlink 和一个正常文件，断言列表仍返回正常文件；另用权限或策略
错误证明非 `FileNotFoundError` 不会被忽略。

## 9. 会话产物弹窗

文件：

- `apps/desktop/src/app/chat/session-artifacts-dialog.tsx`

入口 hook：

```ts
useSessionArtifactsAction(session)
```

常见入口：

- session row action menu。
- session actions menu。

加载逻辑：

```text
Promise.all([
  getSessionMessages(session.id, session.profile),
  listHostedSessionArtifacts(session.id, session.profile)
])
```

数据来源 1：消息内解析

- `collectArtifactsForSession(session, messages)`

数据来源 2：hosted gateway API

```text
GET /api/sessions/{sessionId}/artifacts?profile=<profile>
```

合并规则：

- 先放 message artifacts。
- 用 path 去重 hosted artifacts。
- hosted entry 补成 `ArtifactRecord`：
  - `kind: "file"`
  - `href/value: entry.path`
  - `label: entry.name || basename(path)`
  - `timestamp: session.last_active || session.started_at || Date.now()`
- 按 timestamp 倒序。

展示：

- 只显示 `kind === "file" | "image" | "video"`。
- 每个文件有下载按钮。
- footer 有全部下载。
- loading/empty/error 都有本地化文案。

下载：

- 单个：`downloadManagedFile(artifact.value, { suggestedName: artifact.label })`
- 全部：`downloadManagedFilesBatch(fileArtifacts.map(a => a.value))`

## 10. Artifacts 总页

文件：

- `apps/desktop/src/app/artifacts/index.tsx`

职责：

- 浏览最近 session 生成的 artifacts。
- 从消息中收集 artifacts。
- 支持图片、视频、文件。
- remote mode 下打开/下载必须复用 `media.ts` 和 `files.ts`。
- 顶部筛选只展示“图片 / 文件 / 链接”，不要展示“全部 / All”。进入产物页默认落到“文件”筛选，避免首屏直接把全部历史产物铺出来。
- 筛选路由白名单也只能包含 `image / file / link`，不能只在 UI 上隐藏 `all`。历史链接或合并后残留的 `?tab=all` 必须按非法值处理并回落到“文件”，不能继续在后台加载全部产物。页签应直接由同一白名单生成，避免上游合并再次单独加回“全部”。
- “文件”筛选要同时包含普通文件和视频；视频不要单独暴露 tab，也不要因为移除“全部”而丢失。
- 搜索框动态提示和表格“会话”列都来自 session title/preview，历史数据里可能带 `Hermes`、`Hermes Agent` 或 `hermes-agent`。这些地方必须走显示层品牌替换，统一展示为 `AgentOS`，不要回写或改动真实 session 数据。
- 点击文件类产物时必须用原始 managed path 调 `openManagedFile(artifact.value)`。`openManagedFile` 先走 Electron `resolveLocalMediaCache({ fetchIfMissing:true })`，由 main process 通过 Hermes gateway `/api/files/download` 或 `/api/files/read` 拉到本地 cache，再用本地 `file://` 打开预览；如果 cache 拉取失败，直接提示打开失败，不要回退到 `downloadRemoteFile(openAfter:true)` 弹系统“保存为”窗口。不要把 `artifact.href`、`file://` 派生远端 URL 或空 OAuth download URL 直接传给 `openExternal`，否则 remote mode 会报 `Invalid external URL` 或打开本机不存在的路径。
- 文件类产物不展示路径列，图片卡片和本会话文件弹窗也不展示路径副文本。路径映射只留在内部检索、下载和打开逻辑中：`/opt/hermes/...` 映射为 `AgentOS/...`，`~/.hermes/...` 和 `/Users/<user>/.hermes/...` 映射为 `AgentOS data/...`，未知绝对路径映射为脱敏尾部 `AgentOS file/<tail>`。原始路径只保留在 `artifact.value`，用于下载、打开和去重。
- 工具输出中常见的字面 `\n`、`\r` 结尾和包裹引号要在 artifact 收集阶段清掉，否则文件名会带转义字符或引号，下载 API 会找不到真实文件。
- artifact 收集只能收真实文件路径或 URL，不能因为路径中包含 `.hermes` 就把目录当成文件。没有文件扩展名的 remote/local 目录，例如 `/Users/me/.hermes/web_dist`，不得进入产物文件列表。

迁移时不要让 artifacts 页直接读取本机文件。它只能对本机 local path 用本地 API，对 remote path 走 gateway API/IPC。

## 11. 回归测试重点

建议覆盖：

- `renderMediaTags`：
  - line MEDIA。
  - inline MEDIA。
  - quoted/backticked path。
  - naked video/audio path。
  - trailing punctuation。
  - 去重。

- `media.ts`：
  - remote OAuth mode 下 `mediaExternalUrl` 不返回 `file://`。
  - remote token mode 下生成 download URL。
  - audio/video remote path 返回 `hermes-media://remote`。
  - HTTP generated media 调 `persistGeneratedMedia`。

- `files.ts`：
  - `managedPath(file://...)`。
  - remote managed path。
  - IPC download payload 带 profile。
  - fallback legacy token URL。
  - batch cancel。

- `electron/main.ts` remote download：
  - 本地可读 path 用 copy。
  - 本地不可读 remote path 用 gateway fetch。
  - `/api/files/download` 失败回退 `/api/files/read`。
  - cached openAfter 不重复下载。
  - download progress start/done。

- `session-artifacts-dialog`：
  - hosted artifacts 和 message artifacts 去重。
  - empty state。
  - 单个和全部下载。
  - profile query。

- `tool-fallback-model`：
  - terminal success hidden。
  - terminal error shown。
  - exit code 1 with stdout not error。
  - stderr split but neutral。
  - command summary 不影响 copy payload。
