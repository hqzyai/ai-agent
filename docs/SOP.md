# Hermes 上游同步与 AgentOS 发布 SOP

## 角色和不可跳过的门禁

| 角色 | 责任 | 不可兼任规则 |
| --- | --- | --- |
| Sync owner | 核验上游、创建分支、处理语义冲突、提交 PR | 不能独自批准人工验收 |
| CI | 执行来源、规格、契约、单测、集成、构建与安全检查 | 失败不可用人工口头豁免 |
| QA / 产品验收人 | 在 RC 产物上执行真实验收并留证 | 必须至少一名非 PR 作者 |
| Release owner | 锁定清单、灰度、晋级、回滚 | 只能晋级已验收的同一产物 |

`main`、`ai-agent/hermes-*` 和 GitHub `production` Environment 应启用保护；正式发布需要 Environment reviewer。CI 额度不足时可使用自托管 runner 或本地脚本生成证据，但不得把必需检查改成“跳过”。

GitHub 配置依据：使用 [deployment environments 与 required reviewers](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) 隔离正式发布；所有第三方 Action 固定到完整 commit SHA，符合 GitHub 的 [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)；候选产物生成并保存 [artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)。

## 1. Intake：发现并核验上游版本

1. 只接受官方仓库 `https://github.com/NousResearch/hermes-agent.git`。
2. 记录 Hermes semver、官方 tag、tag object SHA、peeled commit SHA、Release URL。
3. 阅读从上次锁定 commit 到新 commit 的 release notes、diff、迁移说明和依赖变化。
4. 创建 `release-manifests/vYYYY.MM.DD.candidate.json`；此时状态为 `draft`，不得发布。
5. 用 `python3 scripts/validate_release_manifest.py <manifest>` 校验命名，并用 `python3 scripts/verify_upstream.py <manifest>` 在线核对官方 tag object 与 peeled commit。
6. 用 `python3 scripts/validate_brand_profile.py config/brand.env.example` 校验品牌配置；按 [`BRANDING.md`](BRANDING.md) 映射到目标仓库，禁止在通用同步逻辑中新增租户硬编码。

Hermes tag 与产品版本是两个维度：上游 `0.20.6` + 产品 CalVer `2026.08.31` 映射为产品版本 `v0.20.6-2026.08.31`、同步分支 `ai-agent/hermes-v0.20.6-2026.08.31`、正式 tag `v2026.08.31`。

## 2. 创建同步分支并做语义合并

在干净、最新的 `agentos-desktop/main` checkout 中执行：

```bash
/path/to/ai-agent/scripts/start_sync.sh 0.20.6 v2026.8.27 2026.08.31 main
```

同步 checkout 必须包含完整 Git 历史；不要使用 `--depth`。partial clone 的 `--filter=blob:none` 可以使用，但需保证不是 shallow repository。

脚本固定官方 remote、精确 fetch tag、创建标准分支，并以 `--no-commit` 开始 merge。冲突必须按 `docs/skills/merge-hermes-upstream` 的产品契约逐项解决，禁止整侧覆盖。每个冲突在 PR 中记录：上游意图、AgentOS 约束、最终选择、对应 requirement ID。

贡献者可以把本仓库的 `docs/skills/merge-hermes-upstream` vendored 到目标 checkout 后使用 Skill 内同名脚本。Skill 的来源 commit 和适配后文件摘要由 `config/contributor-skills.lock.json` 锁定。

优先顺序：安全修复和数据格式兼容 > AgentOS 登录/品牌/发布契约 > 上游新功能 > 纯重构。删除既有 AgentOS 行为必须有单独产品决策。

### 2.1 重新应用 bundled plugins

`ai-agent` 是 bundled plugin 的权威下游源码；外部 ZIP 和 `hqzyai/hermes-plugin` 不参与同步分支构建。开始复制前先在治理仓库运行：

```bash
python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json
```

将 `apps/desktop/src/plugins/channels` 和 `plugins/` 中的锁定文件同步到产品 checkout。目标同名目录存在 lock 未声明文件时停止并语义合并，禁止整目录覆盖。

对 `channels` 后端集成先执行：

```bash
git apply --check /path/to/ai-agent/patches/bundled-plugins/channels/hermes-channels-integration.patch
```

检查通过后才可应用补丁。若上游已有等价 API，PR 必须记录接口逐项映射、采用原生实现的理由和 `PLUGIN-*` 自动/人工验收证据；不能为获得绿色 CI 静默跳过或强制应用补丁。完整规则见 [`BUNDLED-PLUGINS.md`](BUNDLED-PLUGINS.md)。

## 3. 本地预检与 PR

1. 执行 `run_acceptance.py --mode quick`，修复所有失败。
2. 更新清单 `sourceCommit` 为 PR HEAD 的完整 40 位 SHA。
3. 使用 `.github/PULL_REQUEST_TEMPLATE/upstream-sync.md` 创建 Draft PR。
4. PR 必须包含完整 diff 范围、上游 provenance、风险区域、冲突决策、规格映射和回滚方式。
5. 禁止把 secrets、真实用户目录或生产 token 带入测试；验收脚本会移除常见 secret 环境变量。
6. PR 必须列出 bundled plugin lock 是否变化、SDK/manifest 兼容结果、patch check 结果和受影响 `PLUGIN-*`。

## 4. 自动化验收门禁

PR 依次通过：

1. L0 治理：版本/分支/tag/SHA/规格/Action pin 校验。
2. L1 静态：`git diff --check`、Python/TS 类型和 lint。
3. L2 单元：上游测试、desktop UI/electron/platform/plugin 测试。
4. L3 产品契约：登录、远程 gateway、品牌、技能、文件、消息、模型、更新器审计。
5. L4 集成：本地/远程 session、WebSocket、MCP、A2A、cron、文件/媒体链路。
6. L5 构建：ARM64/AMD64 镜像和三端桌面安装包必须全部产生。
7. L6 安装/升级：全新安装、上一正式版升级、失败回滚、离线 runtime 完整性。
8. L7 供应链：依赖/镜像扫描、SBOM、产物 SHA-256、来源证明。
9. Bundled plugins：来源锁、Backend 单测、Desktop SDK/build、patch、镜像/安装包包含性和升级持久化。

检查失败只能通过修复或有时限、所有者、风险说明的书面例外处理；安全、来源、安装/升级和人工验收不可豁免。

## 5. 候选构建与真实人工验收

将 PR HEAD 锁入 manifest 后，手动运行 `candidate.yml`。该工作流从精确 commit 构建：

- `linux/amd64` + `linux/arm64` RC 镜像；
- Linux AppImage、macOS 安装包、Windows NSIS 安装包；
- checksums、测试报告和候选 evidence；
- Draft prerelease `vYYYY.MM.DD-rc.<source_sha_12>`。

QA 必须安装这些候选产物，而不是在源码开发环境中代替验收。按 [`manual-acceptance-template.md`](manual-acceptance-template.md) 至少覆盖新装、升级、登录、核心对话/工具、文件媒体、技能、远程 gateway、cron、更新与卸载。Windows 自包含 Python/distlib launcher 未闭环时必须 fail closed，不能发布在线下载或不完整离线包作为替代。

把设备/OS、候选 tag、镜像 digest、安装包 SHA、结果和证据 URL 回填清单；`automated` 与 `manual` 均设为 `passed`，状态改为 `approved`。变更 source commit 后，原人工验收自动失效，必须重建和重验。

下载 candidate workflow 的 `acceptance-report`、`candidate-evidence.json` 与三个 `*.artifacts.json` 后，可先导入机器证据（该脚本不会批准人工验收）：

```bash
python3 scripts/finalize_candidate_manifest.py release-manifests/vYYYY.MM.DD.candidate.json \
  --evidence candidate-evidence.json --acceptance acceptance-report.json \
  --artifact-manifest linux.artifacts.json \
  --artifact-manifest macos.artifacts.json \
  --artifact-manifest windows.artifacts.json
```

## 6. 合并、灰度与正式发布

1. 人工验收通过后合并同步 PR 到 `main`；确认 merge 后包含已验收 source commit，不允许夹带未验收变更。
2. 灰度环境按 digest 部署 RC 镜像；桌面内部渠道仍使用相同 RC 安装包。
3. 观察至少一个约定窗口：启动/升级成功率、gateway 连接、session 错误、工具失败率、崩溃和回滚指标。
4. 运行 `release.yml`，由 `production` Environment reviewer 批准。
5. 发布工作流只把已验收的 RC 镜像 manifest 晋级为 `vYYYY.MM.DD`，并把相同安装包发布到正式 Release；不得重编译。
6. 更新 `CHANGELOG.md`，将候选章节改为发布日期，附上游链接、已知问题、升级/回滚说明。

## 7. 回滚

- 容器：按 digest 切回上一正式版本，不依赖可变 tag。
- 桌面：停止新版本更新 feed；恢复上一版本元数据和下载链接；保留用户数据格式向后兼容。
- 数据或配置迁移：每个迁移必须有向后读取或显式恢复脚本；没有回滚路径时必须在发布前写清备份和恢复步骤。
- 发布事故：暂停晋级，记录 manifest、commit、digest、受影响平台和时间线；修复必须创建新的 CalVer 候选，不覆盖已发布资产。
