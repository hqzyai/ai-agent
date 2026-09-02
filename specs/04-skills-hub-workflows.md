# 04 Skill Hub、技能发现与专家工作流

## Requirements

- **SKILL-001** Hub 唯一产品来源为 `nacos`，显示名“华清严选”；`source=all` 仅作旧客户端到 Nacos 的兼容别名。
- **SKILL-002** Nacos miss、timeout 或空结果不得回退 Nous/public catalog；非 Nacos source、标识符和 traversal 路径返回拒绝。
- **SKILL-003** `skills.external_dirs` 支持 profile-scoped 多路径配置；技能发现、`skill_view`、skills prompt 和 slash index 使用当前 home 的动态路径。
- **SKILL-004** 安装、更新、卸载或 lock file 变化后，不重启、不 sleep，下一次读取立即刷新技能列表、prompt、slash catalog/completion/dispatch。
- **SKILL-005** `skill_view` 支持短名、冲突时 `category/skill` 和兼容的多级分类写法；非法 plugin namespace 与 traversal 始终拒绝。
- **WORKFLOW-001** Capabilities 默认打开“专家技能”，按差旅报销、项目研判、投资合同审核、文书起草顺序显示。
- **WORKFLOW-002** 点击专家卡片创建全新主会话并把完整 slash 模板作为可编辑草稿，不自动提交、不直接请求 backend。
- **WORKFLOW-003** `【...】` 是可编辑占位字段，序列化后保持原文；普通 JSON/代码大括号不高亮。

## Automated acceptance

- 使用真实 `NacosSkillSource` 和可控 HTTP 响应，预热索引后安装嵌套分类技能，立即验证 list/view/prompt/catalog/completion/dispatch。
- 统计 public source 的 search/inspect/fetch 调用必须为零。
- 在同进程从 home A 切换 home B，断言所有技能路径和结果随当前 home 变化。
- Desktop 组件/E2E 验证四卡顺序、fresh session、replace/main、无 submit、模板字段数量与纯文本往返。

## Manual acceptance

1. 从“华清严选”安装技能后立即在新会话和 slash palette 中使用。
2. 断网或 Nacos 超时时只显示中文错误/空态，不出现公网内容。
3. 四个专家模板均可逐字段编辑，发送内容与编辑器纯文本一致。
