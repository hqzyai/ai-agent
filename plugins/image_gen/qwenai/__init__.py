from __future__ import annotations

import base64
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Optional, Protocol, cast

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    save_url_image,
    success_response,
)


_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_API_KEY_URL = "https://platform.qianwenai.com/docs/api-reference/preparation/api-key"
_CATALOG_TIMEOUT_SECONDS = 20.0
_REQUEST_TIMEOUT_SECONDS = 300.0

_LEGACY_IMAGE_SIZES = {
    "landscape": "1664*928",
    "square": "1328*1328",
    "portrait": "928*1664",
}
_HIGH_RES_IMAGE_SIZES = {
    "landscape": "2048*1152",
    "square": "2048*2048",
    "portrait": "1152*2048",
}
_Z_IMAGE_SIZES = {
    "landscape": "1536*864",
    "square": "1536*1536",
    "portrait": "864*1536",
}


class _HTTPResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> object: ...


class _HTTPGet(Protocol):
    def __call__(self, url: str, **kwargs: object) -> _HTTPResponse: ...


class _HTTPPost(Protocol):
    def __call__(self, url: str, **kwargs: object) -> _HTTPResponse: ...


def _load_config() -> Mapping[str, object]:
    from hermes_cli.config import load_config

    config = load_config()
    return cast(Mapping[str, object], config) if isinstance(config, dict) else {}


def _default_http_get(url: str, **kwargs: object) -> _HTTPResponse:
    import requests

    return cast(_HTTPResponse, requests.get(url, **kwargs))


def _default_http_post(url: str, **kwargs: object) -> _HTTPResponse:
    import requests

    return cast(_HTTPResponse, requests.post(url, **kwargs))


def _nonempty(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalized_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def _catalog_base_url(value: str) -> str:
    base = _normalized_base_url(value)
    if base.endswith(("/compatible-mode/v1", "/api/v1", "/v1")):
        return base
    if base.endswith("/compatible-mode"):
        return f"{base}/v1"
    return f"{base}/compatible-mode/v1"


def _native_api_base_url(value: str) -> str:
    base = _normalized_base_url(value)
    if base.endswith("/api/v1"):
        return base
    for suffix in ("/compatible-mode/v1", "/compatible-mode", "/v1"):
        if base.endswith(suffix):
            return f"{base[:-len(suffix)]}/api/v1"
    return f"{base}/api/v1"


def _checked(response: _HTTPResponse) -> _HTTPResponse:
    if response.status_code >= 400:
        raise ValueError(f"QwenAI returned HTTP {response.status_code}: {response.text[:500]}")
    return response


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _model_records(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        return []
    for key in ("data", "models"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    output = payload.get("output")
    if isinstance(output, Mapping):
        for key in ("data", "models"):
            value = output.get(key)
            if isinstance(value, list):
                return value
    return []


def _model_id(record: object) -> str | None:
    if isinstance(record, str):
        return _nonempty(record)
    if not isinstance(record, Mapping):
        return None
    for key in ("id", "model", "model_name", "name"):
        value = _nonempty(record.get(key))
        if value is not None:
            return value
    return None


def _metadata_text(value: object) -> str:
    parts: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, str):
            parts.append(item.lower())
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                visit(child)

    visit(value)
    return " ".join(parts)


def _looks_like_text_to_image(record: object) -> bool:
    model_id = _model_id(record)
    if model_id is None:
        return False
    normalized = model_id.lower()
    metadata = _metadata_text(record)

    video_markers = (
        "image-to-video",
        "image_to_video",
        "text-to-video",
        "text_to_video",
        "video-generation",
        "video_generation",
        "-i2v",
        "-t2v",
        "video-edit",
        "ref-to-video",
    )
    if any(marker in normalized for marker in video_markers):
        return False

    declared_image_generation = any(
        marker in metadata
        for marker in (
            "text-to-image",
            "text_to_image",
            "text2image",
            "image-generation",
            "image_generation",
        )
    )
    if declared_image_generation:
        return True
    if any(marker in metadata for marker in video_markers):
        return False

    if normalized.startswith("qwen-image"):
        return "edit" not in normalized
    if normalized.startswith("z-image"):
        return True
    if normalized.startswith(("wan", "wanx")):
        return ("image" in normalized or "t2i" in normalized) and "editing" not in normalized
    return any(marker in normalized for marker in ("stable-diffusion", "sdxl", "flux"))


def _catalog_rows(records: Sequence[object]) -> list[dict[str, object]]:
    model_ids = sorted({_model_id(record) for record in records if _looks_like_text_to_image(record)} - {None})
    return [
        {
            "id": model_id,
            "display": model_id,
            "speed": "live",
            "strengths": "text to image",
            "price": "QwenAI",
        }
        for model_id in model_ids
    ]


def _size_for_model(model_id: str, aspect_ratio: str) -> str:
    normalized = model_id.lower()
    if normalized.startswith("z-image"):
        sizes = _Z_IMAGE_SIZES
    elif any(marker in normalized for marker in ("qwen-image-2", "qwen-image-3", "wan2.7-image")):
        sizes = _HIGH_RES_IMAGE_SIZES
    else:
        sizes = _LEGACY_IMAGE_SIZES
    return sizes.get(aspect_ratio, sizes["landscape"])


def _extract_image_value(payload: object) -> tuple[str, bool] | None:
    if isinstance(payload, Mapping):
        for key in ("image", "image_url", "url"):
            value = _nonempty(payload.get(key))
            if value is not None and value.startswith(("http://", "https://", "data:image/")):
                return value, False
        for key in ("b64_json", "image_base64", "base64"):
            value = _nonempty(payload.get(key))
            if value is not None:
                return value, True
        for key in ("output", "choices", "message", "content", "results", "data"):
            if key in payload:
                found = _extract_image_value(payload[key])
                if found is not None:
                    return found
        for value in payload.values():
            found = _extract_image_value(value)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            found = _extract_image_value(item)
            if found is not None:
                return found
    return None


class QwenAIImageGenProvider(ImageGenProvider):
    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        config_loader: Callable[[], Mapping[str, object]] = _load_config,
        http_get: _HTTPGet = _default_http_get,
        http_post: _HTTPPost = _default_http_post,
    ) -> None:
        self._environ = environ if environ is not None else os.environ
        self._use_hermes_env = environ is None
        self._config_loader = config_loader
        self._http_get = http_get
        self._http_post = http_post

    @property
    def name(self) -> str:
        return "qwenai"

    @property
    def display_name(self) -> str:
        return "QwenAI"

    def _env(self, key: str) -> str | None:
        direct = _nonempty(self._environ.get(key))
        if direct is not None or not self._use_hermes_env:
            return direct
        try:
            from hermes_cli.config import get_env_value

            return _nonempty(get_env_value(key))
        except Exception:
            return None

    def _api_key(self) -> str | None:
        return self._env("QWENAI_API_KEY")

    def _base_url(self) -> str:
        return _DEFAULT_BASE_URL

    def is_available(self) -> bool:
        return self._api_key() is not None

    def get_setup_schema(self) -> dict[str, Any]:
        return {
            "name": "QwenAI",
            "badge": "Alibaba Cloud",
            "tag": "Auto-discovered QwenAI text-to-image models",
            "env_vars": [
                {
                    "key": "QWENAI_API_KEY",
                    "prompt": "QwenAI API key",
                    "url": _API_KEY_URL,
                },
            ],
        }

    def capabilities(self) -> dict[str, Any]:
        return {"modalities": ["text"], "max_reference_images": 0}

    def list_models(self) -> list[dict[str, Any]]:
        api_key = self._api_key()
        if api_key is None:
            return []
        base_url = self._base_url()
        endpoints = (
            f"{_catalog_base_url(base_url)}/models",
            f"{_native_api_base_url(base_url)}/models",
        )
        records: list[object] = []
        for endpoint in dict.fromkeys(endpoints):
            try:
                response = self._http_get(
                    endpoint,
                    headers=_auth_headers(api_key),
                    timeout=_CATALOG_TIMEOUT_SECONDS,
                )
                records.extend(_model_records(_checked(response).json()))
            except Exception:
                continue
        return [dict(row) for row in _catalog_rows(records)]

    def _configured_model(self) -> str | None:
        try:
            config = self._config_loader()
        except Exception:
            return None
        image_gen = config.get("image_gen")
        return _nonempty(image_gen.get("model")) if isinstance(image_gen, Mapping) else None

    def default_model(self) -> Optional[str]:
        override = self._env("QWENAI_IMAGE_MODEL") or self._configured_model()
        if override is not None:
            return override
        models = self.list_models()
        return cast(str, models[0]["id"]) if models else None

    def _resolve_model(self, explicit: object) -> str | None:
        return (
            _nonempty(explicit)
            or self._env("QWENAI_IMAGE_MODEL")
            or self._configured_model()
            or self.default_model()
        )

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        api_key = self._api_key()
        return message.replace(api_key, "<redacted>") if api_key else message

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        clean_prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = self._resolve_model(kwargs.get("model"))
        api_key = self._api_key()

        if not clean_prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_input",
                provider=self.name,
                model=model or "",
                aspect_ratio=aspect,
            )
        if _nonempty(image_url) is not None or reference_image_urls:
            return error_response(
                error="The QwenAI image plugin supports text-to-image only",
                error_type="unsupported_modality",
                provider=self.name,
                model=model or "",
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )
        if api_key is None:
            return error_response(
                error="QWENAI_API_KEY is not set. Run `hermes tools` and configure QwenAI.",
                error_type="auth_required",
                provider=self.name,
                model=model or "",
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )
        if model is None:
            return error_response(
                error="No QwenAI text-to-image model is discoverable",
                error_type="no_model_available",
                provider=self.name,
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )

        parameters: dict[str, object] = {
            "size": _size_for_model(model, aspect),
            "n": 1,
            "watermark": False,
        }
        negative_prompt = _nonempty(kwargs.get("negative_prompt"))
        if negative_prompt is not None:
            parameters["negative_prompt"] = negative_prompt
        body = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": clean_prompt}],
                    }
                ]
            },
            "parameters": parameters,
        }

        try:
            response = self._http_post(
                f"{_native_api_base_url(self._base_url())}/services/aigc/multimodal-generation/generation",
                headers=_auth_headers(api_key),
                json=body,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            payload = _checked(response).json()
            image_value = _extract_image_value(payload)
            if image_value is None:
                raise ValueError("QwenAI response contained no generated image")
            value, is_base64 = image_value
            if is_base64:
                image = str(save_b64_image(value, prefix="qwenai"))
            elif value.startswith("data:image/"):
                _, _, encoded = value.partition(",")
                base64.b64decode(encoded, validate=True)
                image = str(save_b64_image(encoded, prefix="qwenai"))
            else:
                try:
                    image = str(save_url_image(value, prefix="qwenai"))
                except Exception:
                    image = value
            return success_response(
                image=image,
                model=model,
                prompt=clean_prompt,
                aspect_ratio=aspect,
                provider=self.name,
                modality="text",
            )
        except Exception as exc:
            return error_response(
                error=f"QwenAI image request failed: {self._safe_error(exc)}",
                error_type="provider_error",
                provider=self.name,
                model=model,
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )


def register(ctx: Any) -> None:
    ctx.register_image_gen_provider(QwenAIImageGenProvider())
