# 05 模型请求会话关联

## Requirements

- **MODEL-001** 所有支持 HTTP header 的主调用、流式调用、重试、fallback、迭代总结和辅助模型调用携带精确 `HERMES_SESSION_ID`。
- **MODEL-002** 同时发送值完全相同的 `X-LiteLLM-Session-ID`；旧 `SESSION_ID` 在 transport 前删除。
- **MODEL-003** 已有大小写变体被当前 durable session ID 规范化，鉴权和 Provider 专用 header 保留。
- **MODEL-004** 并发会话通过 task-local context 隔离，标题、压缩、评审等辅助调用不能串号。
- **MODEL-005** Gemini native 普通/SSE 都传递 headers；Relay 在最后边界重新规范化。Bedrock 和 Codex app-server 不接收不支持的 OpenAI header kwargs。
- **MODEL-006** 会话 ID 是关联标识而非认证凭据，拒绝 CR/LF，不在普通 UI 展示。

## Automated acceptance

- 用抓包 transport 覆盖主调用、stream、retry、fallback、summary、compression、title 和 auxiliary，断言两个 header 唯一且相等。
- 并发启动两个会话并触发辅助调用，断言 ID 从不交换。
- 覆盖大小写 header、旧 `SESSION_ID`、自定义 header、Gemini SSE、Relay callback、Bedrock 与 Codex app-server。
- 对 CR/LF 输入 fail closed，并对日志/UI 断言无可见会话 header。

## Manual acceptance

在预发布 AI Gateway 中完成两条并发长会话，确认 LiteLLM metadata、用量记录和 trace 分别归属正确 durable session。
