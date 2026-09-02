# AgentOS / ai-agent 可验收规格

本目录把 `agentos-20260825` 上目标作者的 79 个 commits 收敛为稳定的产品契约。原始证据见：

- `source/agentos-20260825-commits.json`：完整 commit、作者、父提交、文件和分类。
- `source/agentos-20260825-commits.md`：按分类与时间整理的可读清单。
- `scripts/collect_agentos_commits.py`：可重复生成上述证据。

## 规格索引

| 规格 | 范围 | 必须阻断发布 |
| --- | --- | --- |
| `01-branding-i18n-policy.md` | 品牌、中文、Provider/Tool/Skill 产品策略 | 是 |
| `02-auth-remote-gateway.md` | BFF 登录、Cookie、WS ticket、远程连接恢复 | 是 |
| `03-sessions-files-media-artifacts.md` | 远程会话、文件、媒体、产物和隐私 | 是 |
| `04-skills-hub-workflows.md` | Nacos Skill Hub、技能发现、专家工作流 | 是 |
| `05-model-session-observability.md` | 模型请求会话标识与并发隔离 | 是 |
| `06-desktop-messaging-cron-ux.md` | 桌面壳、国内消息平台、定时任务 | 是 |
| `07-packaging-updater-release.md` | 离线 payload、安装、更新、镜像与三端制品 | 是 |
| `08-upstream-sync-governance.md` | 上游来源、版本锁、分支、PR、验收和晋级 | 是 |
| `09-bundled-plugins.md` | Desktop/Hermes bundled plugins、来源锁、打包与升级 | 是 |

## 规格写法

每条需求都有稳定 ID。`Automated acceptance` 是 CI 的最低证据；`Manual acceptance` 是真实人工验收，不可用“CI 绿色”替代。上游同步 PR 必须给出每个受影响需求 ID 的结果：`pass`、`not-affected` 或带 owner 的 `waived`。`waived` 不能用于安全、认证、更新完整性和离线 payload 需求。

## 证据等级

1. 静态护栏：路径、配置、禁用入口和来源限制。
2. 行为单测：执行真实函数或组件，不读取源码文本假装测试行为。
3. 集成测试：真实 BFF/Gateway/数据库/文件链路。
4. 打包测试：在目标 OS 生成并检查安装包。
5. 安装升级 E2E：N-1/N-2 到候选版本，验证重启和回滚。
6. 人工验收：使用候选制品完成规定场景并保存签名记录。

低等级证据不能替代高等级需求。例如，`manifest.json` 存在不能证明离线首次启动成功。
