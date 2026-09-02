# AgentOS 候选版本人工验收记录

## 候选身份

- Release manifest：
- Product version：
- Source commit：
- RC release tag：
- Container digest：
- 验收人（至少一名非 PR 作者）：
- 日期：

## 设备矩阵

| 平台 | OS/版本 | 架构 | 产物名与 SHA-256 | 新装 | 上一版升级 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| Linux | | x86_64 | | | | |
| macOS | | Apple Silicon | | | | |
| macOS | | Intel（若支持） | | | | |
| Windows | | x86_64 | | | | |

## 必测场景

| 场景 | Requirement IDs | 预期 | 实际/证据 | 结果 |
| --- | --- | --- | --- | --- |
| 启动、AgentOS 品牌与中英文 | BRAND-* | 无 Hermes 残留；本地化完整 | | |
| 登录、退出、token 失效恢复 | AUTH-* | 状态正确且不泄露凭证 | | |
| 本地/远程 gateway 与重连 | GATE-* | 鉴权、断线和恢复正确 | | |
| 新会话、多轮对话、重启恢复 | SESSION-* | 历史和状态一致 | | |
| 文件、图片、媒体和 artifact | FILE-* | 上传/预览/下载/取消正确 | | |
| Skills Hub 与 workflow | SKILL-* | 安装、启停、持久化正确 | | |
| 模型切换、请求详情、usage | MODEL-* | 参数与统计正确且脱敏 | | |
| 消息、cron、通知 | MSG-* | 执行、取消、通知正确 | | |
| Bundled plugins | PLUGIN-* | channels 三种扫码与 Qwen/OpenSERP 正常；缺凭据安全失败；升级保留配置 | | |
| 自动更新、失败恢复 | RELEASE-* | 校验、暂停 gateway、回滚正确 | | |
| 卸载/重装与用户数据 | RELEASE-* | 数据策略符合说明 | | |

## 结论

- P0/P1 缺陷：
- 已知问题及用户影响：
- 回滚验证：
- 结论：通过 / 不通过
- 证据 URL：
- 签字：
