# 08 上游同步与发布治理

## Requirements

- **SYNC-001** 上游代码只来自 `https://github.com/NousResearch/hermes-agent.git` 正式 Release tag；默认拒绝 draft/prerelease 和移动的 `main`。
- **SYNC-002** 每次同步锁定 Hermes version、tag object SHA、peeled commit SHA、Release URL、前一上游 SHA 和 source commit。
- **SYNC-003** 分支格式为 `ai-agent/hermes-v<hermesVersion>-<YYYY.MM.DD>`；产品版本为 `v<hermesVersion>-<YYYY.MM.DD>`，发布 tag 为 `v<YYYY.MM.DD>`。
- **SYNC-004** 从当前产品主分支创建分支，以 `--no-ff --no-commit` 合并锁定 SHA；冲突按 base/AgentOS/upstream 三方语义解决，禁止无审查整文件 ours/theirs。
- **SYNC-005** 自动合并文件同样执行 AgentOS 契约审计；新增产品适配必须更新 specs 并添加可重复验证。
- **PR-001** 同步 workflow 自动创建 PR，PR 记录来源、diff 风险、冲突决策、受影响规格、自动测试和人工验收清单。
- **PR-002** 合并需要产品、Desktop、Backend 和 Release owner 中适用的审批；CI 全绿不能替代人工候选验收。
- **ACCEPT-001** 人工验收使用候选分支构建的同一不可变制品，结果写入签名记录；通过后才允许合入主分支和正式晋级。
- **RELEASE-003** 正式发布 tag `vYYYY.MM.DD`，Release Notes 来自 manifest、CHANGELOG、上游 Release 和验收证据。
- **ROLLBACK-001** 回滚通过将发行指针恢复到上一组已验证 digest/SHA 实现，不删除候选或历史制品。

## Automated acceptance

- 校验 tag object 与 peeled SHA、官方仓库 URL、分支/版本格式、祖先关系和 lock/manifest 一致性。
- 上游同步 PR 无论 diff 分类都运行固定基线；影响映射只增加测试，不能减少基线。
- workflow lint、spec validator、release manifest validator、本地 acceptance runner 全部通过。
- Release job 仅接受 `status=approved`、人工验收通过、source SHA 与候选制品 provenance 一致的 manifest。

## Manual acceptance

1. Reviewer 逐项确认冲突决策和自动合并高风险目录。
2. QA 使用候选镜像与三端安装包填写验收记录并签名。
3. Release owner 确认回滚目标、制品 digest、更新渠道和监控阈值后批准晋级。
