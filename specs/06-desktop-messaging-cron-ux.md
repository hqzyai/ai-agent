# 06 Desktop、消息平台与定时任务 UX

## Requirements

- **DESKTOP-001** Desktop 是 Electron/renderer/backend 三方边界清晰的独立聊天面；renderer 不直接获得 Node/Electron 通用能力。
- **DESKTOP-002** titlebar、statusbar、Gateway popover 和 Command Center 不恢复版本 pill、日志尾、重复 agents/cron、开发者噪声或内置 terminal 入口；后端 terminal tool 保留。
- **DESKTOP-003** 状态栏显示“网关/已就绪”，左侧导航保留“子智能体/定时任务”，归档对话位于左下 Gateway 菜单。
- **MSG-001** 产品只显示钉钉、飞书、企业微信、微信、QQ，按此顺序；企业微信优先 `wecom_callback`。
- **MSG-002** 名称、描述、字段 label/help/placeholder、toast、aria-label 全部中文，不能回退后端英文文案。
- **MSG-003** 陌生用户配对回复使用 AgentOS 中文模板及可执行 `agentos pairing approve` 命令。
- **CRON-001** 用户通过时间控件创建/编辑定时任务，不要求手写 cron；协议层仍生成正确五段表达式。
- **CRON-002** delivery 只显示“此桌面”并提交 `local`；旧任务能回填控件，运行历史可打开会话。

## Automated acceptance

- Desktop 组件测试断言隐藏/保留入口和 stale terminal layout 清理。
- 消息平台测试输入乱序和包含海外平台的 catalog，断言五平台中文结果、顺序、字段和 fallback。
- Gateway 配对集成测试完成未授权消息、批准、下一条消息通过及限流提示。
- Cron 属性测试覆盖 daily、weekdays、weekly、monthly、hourly、15 分钟、自定义时间与旧表达式回填。

## Manual acceptance

1. 遍历桌面主壳，无已禁用入口和空 terminal 轨道。
2. 五个平台逐一保存配置并确认中文提示和重启 Gateway 提示。
3. 创建、暂停、恢复、立即执行、编辑和删除定时任务，并从历史打开结果会话。
