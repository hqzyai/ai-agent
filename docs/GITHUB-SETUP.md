# GitHub 仓库一次性配置

## ai-agent 仓库

1. 创建 `production` Environment，只允许 `main` 部署，配置 required reviewers，并开启 prevent self-review（当前 GitHub 套餐支持时）。
2. Branch protection：`main` 必须通过 `Governance validation`，禁止 force push 和 tag 覆盖。
3. 配置 `AGENTOS_SOURCE_TOKEN`：优先使用 GitHub App installation token；只授予 `hqzyai/agentos-desktop` contents/PR 所需最小权限。不要使用个人全组织 PAT。
4. GHCR 对 `ai-agent` package 开启 tag immutability 或等效保留策略；部署始终记录 digest。
5. 正式 tag `v*` 使用 ruleset 限制为 release owner 创建。

## agentos-desktop 仓库

1. 把 `templates/agentos-desktop/.github/workflows/ai-agent-sync-pr.yml` 复制到源码仓库并走 PR 审核。
2. 配置只读 `AI_AGENT_READ_TOKEN`（如两个仓库均为 private）；优先 GitHub App token。
3. `main` 和 `ai-agent/hermes-*` PR 必须通过既有 CI 与 `AgentOS upstream-sync PR gate`。
4. 按组织内真实团队创建 `CODEOWNERS` 后，要求至少一名 code owner 审核；不要在团队名称未确认前提交虚构 handle。同步 PR 作者不能独自完成发布批准。
5. 自托管 runner 使用受限 runner group；持有发布 secret 的 runner 不接收 fork 或未受信代码。

## Required checks 建议

- Governance/provenance
- Existing AgentOS CI orchestrator
- AgentOS contract audit
- Desktop UI/Electron/platform/plugin tests
- Integration tests for affected gateway/MCP/A2A/session paths
- Candidate container amd64 + arm64
- Candidate desktop Linux + macOS + Windows
- Trivy image scan, SBOM and provenance attestations
- Manual acceptance evidence（通过 manifest + production Environment gate 表达）
