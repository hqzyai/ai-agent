# Changelog

本文件记录 AgentOS `ai-agent` 产品发布差异；Hermes 上游变更通过对应官方 release 链接追溯。

## [Unreleased]

### Added

- 建立 Hermes 上游来源锁定、产品版本映射、同步分支、PR 门禁和候选晋级流程。
- 建立 ARM64/AMD64 镜像与 Linux/macOS/Windows 桌面客户端的统一发布清单。
- 将 `agentos-20260825` 上目标作者的 79 个提交沉淀为 8 组可验收产品规格。
- 接入 Hermes Agent `v0.21.0`（官方 tag `v2026.8.31`）的 `v2026.09.02` 本地 dry-run 候选。
- 增加按品牌、公司、应用和 Skill Hub 分域的可移植环境配置与校验。
- vendored 并适配 contributor `merge-hermes-upstream` Skill，强制精确 tag 和标准同步分支。
- 将 Desktop `channels` 与 Qwen 图片/视频、OpenSERP Hermes plugins 作为 bundled plugin 权威源码纳入仓库，并增加来源锁、CI 校验和发布验收规范。

### Changed

- 计划同步 Hermes Agent `v0.20.6`（官方 tag `v2026.8.27`）到产品候选 `v0.20.6-2026.08.31`。
- 默认应用身份调整为 `com.hqzyai.agentos`；组织变量统一为 `ORG_NAME=hqzyai`，实际 app 数据根统一为 `{APP_DATA_DIR}/profiles/{ORG_NAME}`。

### Release status

- `v2026.08.31` 尚未发布；只有 release manifest 通过自动化和真实人工验收后才能从本节转为正式版本。
