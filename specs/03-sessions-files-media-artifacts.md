# 03 会话、文件、媒体与产物

## Requirements

- **SESSION-001** remote/profile 会话列表、读取、恢复、重命名、归档、取消归档和删除全部路由到对应远端，不能落回本机默认 home。
- **SESSION-002** 历史 transcript 返回后立即绘制，不等待完整 Agent 初始化；`session.resume` 仅注册 lazy runtime，首次真实操作再构建 Agent。
- **SESSION-003** 可写 SessionDB 遇到失效只读连接可在锁内重建一次；真正 `read_only=True` 实例继续拒绝写入。
- **FILE-001** 远程文件、图片、音频、视频和 artifact 通过 Gateway API 与 Electron cache/download IPC；renderer 不能直接打开远端绝对路径或构造本地 `file://`。
- **FILE-002** Artifact 仅有 `image`、`file`、`link`，默认 `file`；`?tab=all` 回落到 `file`。
- **FILE-003** 用户界面不显示远端绝对路径；原始路径只作内部下载 key，未知路径只显示脱敏尾部。
- **MEDIA-001** 图片可显示，音视频可播放和 seek，文件可单个/批量下载并支持 `openAfter`；cache 失败明确报错，不回退不安全的 `openExternal`。
- **CHAT-001** attached context、cron delivery hint 和成功的 terminal/execute_code 行默认隐藏；错误、审批、运行中和 stderr 仍可见。

## Automated acceptance

- 启动两个隔离 profile，验证所有 session mutation 到达正确的远端数据库。
- 将 resume Promise 永久 pending，断言 transcript 仍在规定时间内显示且不会二次重建长消息数组。
- 用临时远端文件服务覆盖 media/read/download/upload、Range、缓存命中、批量下载和错误路径。
- 组件测试覆盖 artifact tab 白名单、默认值、路径脱敏和工具行展示规则。

## Manual acceptance

1. 打开长历史会话，消息立即出现，Gateway 心跳持续正常。
2. 在远程模式查看图片、播放音视频、下载文件和打开 artifact，界面不出现服务器绝对路径。
3. 完成归档与取消归档后，会话 ID、标题、消息数量和顺序不变。
