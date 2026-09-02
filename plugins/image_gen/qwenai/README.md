# QwenAI image generation plugin

This Hermes provider is intentionally text-to-image only. It reads the live
model catalog after setup and excludes chat, editing, and video models.

Configuration shared with the video plugin:

- `QWENAI_API_KEY` — your QwenAI / DashScope API key

The Base URL is fixed to
`https://dashscope.aliyuncs.com/compatible-mode/v1` and is not shown in setup.

Select it through `hermes tools` → Image Generation. After the API key is
saved, Hermes refreshes the provider catalog and prompts for one of the
discovered text-to-image models.
