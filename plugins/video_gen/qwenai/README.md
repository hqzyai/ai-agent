# QwenAI video generation plugin

This Hermes provider is intentionally text-to-video only. It merges the
account's live model catalog with QwenAI's current public text-to-video OpenAPI
specifications, then excludes image-to-video, reference-video, editing, image,
chat, and embedding models. The official supplement covers the verified
HappyHorse and Wan text-to-video models even when DashScope's `/models` response
omits them. PixVerse, Vidu, and unavailable Wan 2.1 models are not offered.

Configuration shared with the image plugin:

- `QWENAI_API_KEY` — your QwenAI / DashScope API key

The Base URL is fixed to
`https://dashscope.aliyuncs.com/compatible-mode/v1` and is not shown in setup.

Select it through `hermes tools` → Video Generation. After the API key is
saved, Hermes refreshes the provider catalog and prompts for one of the
discovered text-to-video models.
