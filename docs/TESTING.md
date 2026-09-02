# 上游合并测试策略

## 核心原则

测试对象是“AgentOS 产品差异 + 新 Hermes 上游”的组合行为，不只是上游测试能否通过。每条长期产品差异必须有稳定 requirement ID；自动化报告和人工验收记录都引用这些 ID。

| 层级 | 何时运行 | 主要证据 | 阻断条件 |
| --- | --- | --- | --- |
| L0 治理 | 每个 PR | manifest/spec/provenance 校验 | 来源、版本、分支、SHA 任一错误 |
| L1 静态 | 每个 PR | diff/type/lint 报告 | 任一错误 |
| L2 单元 | 每个 PR | Python、UI、Electron、plugin 报告 | 任一回归 |
| L3 契约 | 每个同步 PR | `audit-agentos-contracts.sh` + specs | AgentOS 契约缺失 |
| L4 集成 | 同步 PR/夜间 | session/gateway/MCP/A2A/cron 链路 | 核心链路失败 |
| L5 构建 | 候选 | 2 个镜像架构 + 3 个客户端平台 | 任一平台缺失 |
| L6 安装升级 | 候选 | 新装/升级/回滚记录 | 数据丢失、启动或回滚失败 |
| L7 供应链 | 候选/发布 | SHA、SBOM、扫描、provenance | 高危问题或来源不可证 |
| L8 人工真实验收 | 候选 | 模板、截图/日志、批准人 | 任一 P0/P1 场景失败 |

## 变更影响到测试的映射

- `auth/gateway/remote`：本地登录、token 失效、远程登录 URL、安全认证 WebSocket、断线重连。
- `sessions/files/media/artifacts`：会话持久化、拖拽/选择器、重名、取消、二进制与大文件、跨平台路径。
- `skills/hub/workflows`：安装/启停/删除、系统技能保护、Hub 失败回退、workflow CRUD、重启后持久化。
- `models/request/observability`：模型选择、请求详情、usage、错误展示、敏感字段脱敏。
- `messaging/cron/desktop`：消息发送/接收、cron 创建执行取消、通知、托盘、窗口与升级交互。
- `packaging/updater/release`：离线 runtime、签名、校验和、新装、上一版升级、失败恢复、三端产物命名。
- `branding/i18n/policy`：AgentOS 文案/logo/链接/存储目录、中文和英文、隐私与危险操作提示。
- `apps/desktop/src/plugins`、`plugins`、`patches/bundled-plugins`：来源锁、manifest、SDK/API、provider 行为、patch 兼容、镜像/安装包包含性和升级持久化。

## PR 与候选的执行命令

快速 PR 门禁：

```bash
python3 scripts/run_acceptance.py --source /path/to/agentos-desktop --mode quick
python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json
python3 -m unittest tests.test_bundled_plugins -v
```

候选前完整门禁：

```bash
python3 scripts/run_acceptance.py --source /path/to/agentos-desktop --mode full
```

报告必须记录 source commit、每条命令、退出码和耗时。跨平台构建、安装和真实 UI 操作由 candidate workflow 与人工模板补足，不能用 Linux 单机脚本冒充三端结果。

## Flaky 和例外

失败先按真实回归处理。确认 flaky 后，必须记录 issue、owner、复现概率和最长修复期限；重跑结果与首次失败一并留证。连续重跑直至偶然通过不能作为通过依据。
