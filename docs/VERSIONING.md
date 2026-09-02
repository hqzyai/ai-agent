# 版本与分支规则

| 对象 | 格式 | 示例 |
| --- | --- | --- |
| Hermes 版本 | `MAJOR.MINOR.PATCH` | `0.20.6` |
| Hermes 官方 tag | 上游原样记录 | `v2026.8.27` |
| AgentOS 产品版本 | `v<hermes>-YYYY.MM.DD` | `v0.20.6-2026.08.31` |
| 同步分支 | `ai-agent/hermes-v<hermes>-YYYY.MM.DD` | `ai-agent/hermes-v0.20.6-2026.08.31` |
| 正式 release tag | `vYYYY.MM.DD` | `v2026.08.31` |
| 候选 release tag | `vYYYY.MM.DD-rc.<sha12>` | `v2026.08.31-rc.0123456789ab` |

CalVer 表示 AgentOS 完成整体验收的版本日，不伪装成 Hermes 的发布日期。同一 Hermes 版本产生多个产品修订时使用新的 CalVer，不覆盖旧 tag、镜像或安装包。
