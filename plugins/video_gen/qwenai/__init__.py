from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional, Protocol, cast

from agent.video_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
    save_url_video,
    success_response,
)


_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_API_KEY_URL = "https://platform.qianwenai.com/docs/api-reference/preparation/api-key"
_CATALOG_TIMEOUT_SECONDS = 20.0
_REQUEST_TIMEOUT_SECONDS = 120.0
_POLL_TIMEOUT_SECONDS = 900.0
_POLL_INTERVAL_SECONDS = 5.0
_ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4")
_RESOLUTIONS = ("480p", "720p", "1080p")
_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "UNKNOWN"})
_SUCCESS_STATUSES = frozenset({"SUCCEEDED"})
_OFFICIAL_MODEL_SPEC_URLS = (
    "https://platform.qianwenai.com/docs/openapi-happyhorse-text-to-video.json",
    "https://platform.qianwenai.com/docs/openapi-wan-text-to-video.json",
    "https://platform.qianwenai.com/docs/openapi-wan27-text-to-video.json",
)
_EXCLUDED_MODEL_PREFIXES = ("pixverse/", "vidu/", "wan2.1-t2v")

_VIDEO_SIZES = {
    "480p": {
        "16:9": "832*480",
        "9:16": "480*832",
        "1:1": "640*640",
        "4:3": "640*480",
        "3:4": "480*640",
    },
    "720p": {
        "16:9": "1280*720",
        "9:16": "720*1280",
        "1:1": "960*960",
        "4:3": "1104*832",
        "3:4": "832*1104",
    },
    "1080p": {
        "16:9": "1920*1080",
        "9:16": "1080*1920",
        "1:1": "1440*1440",
        "4:3": "1648*1248",
        "3:4": "1248*1648",
    },
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


def _auth_headers(api_key: str, *, async_request: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if async_request:
        headers["X-DashScope-Async"] = "enable"
    return headers


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


def _openapi_model_records(payload: object) -> list[object]:
    """Extract model enums from QwenAI's public text-to-video OpenAPI files."""
    records: list[object] = []

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            model_schema = value.get("model")
            if isinstance(model_schema, Mapping):
                enum_values = model_schema.get("enum")
                if isinstance(enum_values, list):
                    records.extend(item for item in enum_values if _nonempty(item) is not None)
            for child in value.values():
                visit(child)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for child in value:
                visit(child)

    visit(payload)
    return records


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


def _looks_like_text_to_video(record: object) -> bool:
    model_id = _model_id(record)
    if model_id is None:
        return False
    normalized = model_id.lower()
    metadata = _metadata_text(record)

    if normalized.startswith(_EXCLUDED_MODEL_PREFIXES):
        return False

    excluded_markers = (
        "image-to-video",
        "image_to_video",
        "video-edit",
        "video_edit",
        "reference-to-video",
        "reference_to_video",
        "ref-to-video",
        "-i2v",
    )
    if any(marker in normalized for marker in excluded_markers):
        return False

    declared_text_to_video = any(
        marker in metadata
        for marker in (
            "text-to-video",
            "text_to_video",
            "text2video",
            "video_generation",
        )
    )
    if declared_text_to_video:
        return True
    if any(marker in metadata for marker in excluded_markers):
        return False
    if any(marker in normalized for marker in ("-t2v", "text-to-video", "text_to_video")):
        return True
    return normalized.startswith(("wan", "wanx")) and "video" in normalized and "image" not in normalized


def _catalog_rows(records: Sequence[object]) -> list[dict[str, object]]:
    model_ids = sorted({_model_id(record) for record in records if _looks_like_text_to_video(record)} - {None})
    return [
        {
            "id": model_id,
            "display": model_id,
            "speed": "async",
            "strengths": "text to video",
            "price": "QwenAI",
            "modalities": ["text"],
        }
        for model_id in model_ids
    ]


def _uses_wan27_schema(model_id: str) -> bool:
    normalized = model_id.lower()
    return any(marker in normalized for marker in ("wan2.7", "wan-2.7", "wan3", "wan-3"))


def _resolution_for_model(model_id: str, requested: str) -> str:
    normalized = model_id.lower()
    resolution = requested.lower() if requested.lower() in _RESOLUTIONS else DEFAULT_RESOLUTION
    if normalized.startswith("happyhorse-1.0"):
        return "720p" if resolution != "1080p" else "1080p"
    if normalized.startswith("happyhorse"):
        if resolution == "480p":
            return "480p"
        if resolution == "720p":
            return "720p"
        return "1080p"
    if "wan2.2" in normalized and resolution not in {"480p", "1080p"}:
        return "1080p" if resolution == "720p" else "480p"
    if "wan2.6" in normalized and resolution not in {"720p", "1080p"}:
        return "720p"
    if _uses_wan27_schema(model_id) and resolution not in {"720p", "1080p"}:
        return "720p"
    return resolution


def _duration_for_model(model_id: str, requested: Optional[int], resolution: str) -> int:
    normalized = model_id.lower()
    duration = requested if isinstance(requested, int) else 5
    if normalized.startswith("happyhorse"):
        return min(max(duration, 3), 15)
    if "wan2.2" in normalized:
        return 5
    if "wan2.5" in normalized:
        return 5 if duration < 8 else 10
    return min(max(duration, 2), 15)


def _parameters_for_model(
    model_id: str,
    *,
    aspect_ratio: str,
    resolution: str,
    duration: int,
    audio: Optional[bool],
    seed: Optional[int],
) -> dict[str, object]:
    normalized = model_id.lower()
    parameters: dict[str, object] = {"duration": duration, "watermark": False}
    if isinstance(seed, int):
        parameters["seed"] = min(max(seed, 0), 2_147_483_647)

    if normalized.startswith("happyhorse"):
        parameters.update({"resolution": resolution.upper(), "ratio": aspect_ratio})
    elif _uses_wan27_schema(model_id):
        parameters.update(
            {
                "resolution": resolution.upper(),
                "ratio": aspect_ratio,
                "prompt_extend": True,
            }
        )
    else:
        parameters.update(
            {
                "size": _VIDEO_SIZES[resolution][aspect_ratio],
                "prompt_extend": True,
            }
        )
    return parameters


def _task_output(payload: object) -> Mapping[str, object]:
    if isinstance(payload, Mapping):
        output = payload.get("output")
        if isinstance(output, Mapping):
            return output
        return payload
    return {}


def _task_status(payload: object) -> str:
    output = _task_output(payload)
    return (_nonempty(output.get("task_status")) or _nonempty(output.get("status")) or "UNKNOWN").upper()


def _task_id(payload: object) -> str | None:
    output = _task_output(payload)
    return _nonempty(output.get("task_id")) or _nonempty(output.get("id"))


def _task_error(payload: object) -> str:
    output = _task_output(payload)
    for key in ("message", "error_message", "code"):
        value = _nonempty(output.get(key))
        if value is not None:
            return value
    if isinstance(payload, Mapping):
        for key in ("message", "error_message", "code"):
            value = _nonempty(payload.get(key))
            if value is not None:
                return value
    return _task_status(payload)


def _extract_video_url(payload: object) -> str | None:
    if isinstance(payload, Mapping):
        for key in ("video_url", "video", "url"):
            value = _nonempty(payload.get(key))
            if value is not None and value.startswith(("http://", "https://")):
                return value
        for key in ("output", "results", "data"):
            if key in payload:
                found = _extract_video_url(payload[key])
                if found is not None:
                    return found
        for value in payload.values():
            found = _extract_video_url(value)
            if found is not None:
                return found
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            found = _extract_video_url(item)
            if found is not None:
                return found
    return None


class QwenAIVideoGenProvider(VideoGenProvider):
    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        config_loader: Callable[[], Mapping[str, object]] = _load_config,
        http_get: _HTTPGet = _default_http_get,
        http_post: _HTTPPost = _default_http_post,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        video_saver: Callable[..., object] = save_url_video,
    ) -> None:
        self._environ = environ if environ is not None else os.environ
        self._use_hermes_env = environ is None
        self._config_loader = config_loader
        self._http_get = http_get
        self._http_post = http_post
        self._sleep = sleep
        self._monotonic = monotonic
        self._video_saver = video_saver
        self._catalog_cache_key: str | None = None
        self._catalog_cache: list[dict[str, Any]] | None = None

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
            "tag": "Auto-discovered QwenAI text-to-video models",
            "env_vars": [
                {
                    "key": "QWENAI_API_KEY",
                    "prompt": "QwenAI API key",
                    "url": _API_KEY_URL,
                },
            ],
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "modalities": ["text"],
            "aspect_ratios": list(_ASPECT_RATIOS),
            "resolutions": list(_RESOLUTIONS),
            "min_duration": 2,
            "max_duration": 15,
            "supports_audio": False,
            "supports_negative_prompt": True,
            "max_reference_images": 0,
        }

    def list_models(self) -> list[dict[str, Any]]:
        api_key = self._api_key()
        if api_key is None:
            return []
        if self._catalog_cache_key == api_key and self._catalog_cache is not None:
            return [dict(row) for row in self._catalog_cache]
        base_url = self._base_url()
        endpoints = (
            f"{_catalog_base_url(base_url)}/models",
            f"{_native_api_base_url(base_url)}/models",
        )
        records: list[object] = []
        requests_to_make = [
            (endpoint, True) for endpoint in dict.fromkeys(endpoints)
        ] + [(endpoint, False) for endpoint in _OFFICIAL_MODEL_SPEC_URLS]

        def fetch_catalog(endpoint: str, authenticated: bool) -> list[object]:
            kwargs: dict[str, object] = {"timeout": _CATALOG_TIMEOUT_SECONDS}
            if authenticated:
                kwargs["headers"] = _auth_headers(api_key)
            response = self._http_get(endpoint, **kwargs)
            payload = _checked(response).json()
            return _model_records(payload) if authenticated else _openapi_model_records(payload)

        with ThreadPoolExecutor(max_workers=len(requests_to_make)) as executor:
            futures = {
                executor.submit(fetch_catalog, endpoint, authenticated): endpoint
                for endpoint, authenticated in requests_to_make
            }
            for future in as_completed(futures):
                try:
                    records.extend(future.result())
                except Exception:
                    continue
        rows = [dict(row) for row in _catalog_rows(records)]
        self._catalog_cache_key = api_key
        self._catalog_cache = rows
        return [dict(row) for row in rows]

    def _configured_model(self) -> str | None:
        try:
            config = self._config_loader()
        except Exception:
            return None
        video_gen = config.get("video_gen")
        return _nonempty(video_gen.get("model")) if isinstance(video_gen, Mapping) else None

    def default_model(self) -> Optional[str]:
        override = self._env("QWENAI_VIDEO_MODEL") or self._configured_model()
        if override is not None:
            return override
        models = self.list_models()
        return cast(str, models[0]["id"]) if models else None

    def _resolve_model(self, explicit: object) -> str | None:
        return (
            _nonempty(explicit)
            or self._env("QWENAI_VIDEO_MODEL")
            or self._configured_model()
            or self.default_model()
        )

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        api_key = self._api_key()
        return message.replace(api_key, "<redacted>") if api_key else message

    def _await_task(self, api_key: str, initial_payload: object) -> object:
        task_id = _task_id(initial_payload)
        if task_id is None:
            raise ValueError("QwenAI video response did not include a task_id")
        payload = initial_payload
        deadline = self._monotonic() + _POLL_TIMEOUT_SECONDS
        while _task_status(payload) not in _TERMINAL_STATUSES:
            if self._monotonic() >= deadline:
                raise TimeoutError(f"QwenAI video task {task_id} exceeded the 900s timeout")
            self._sleep(_POLL_INTERVAL_SECONDS)
            response = self._http_get(
                f"{_native_api_base_url(self._base_url())}/tasks/{task_id}",
                headers=_auth_headers(api_key),
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            payload = _checked(response).json()
        return payload

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[list[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        clean_prompt = (prompt or "").strip()
        aspect = aspect_ratio if aspect_ratio in _ASPECT_RATIOS else DEFAULT_ASPECT_RATIO
        resolved_model = self._resolve_model(model)
        api_key = self._api_key()

        if not clean_prompt:
            return error_response(
                error="Prompt is required",
                error_type="invalid_input",
                provider=self.name,
                model=resolved_model or "",
                aspect_ratio=aspect,
            )
        if _nonempty(image_url) is not None or reference_image_urls:
            return error_response(
                error="The QwenAI video plugin supports text-to-video only",
                error_type="unsupported_modality",
                provider=self.name,
                model=resolved_model or "",
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )
        if api_key is None:
            return error_response(
                error="QWENAI_API_KEY is not set. Run `hermes tools` and configure QwenAI.",
                error_type="auth_required",
                provider=self.name,
                model=resolved_model or "",
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )
        if resolved_model is None:
            return error_response(
                error="No QwenAI text-to-video model is discoverable",
                error_type="no_model_available",
                provider=self.name,
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )

        selected_resolution = _resolution_for_model(resolved_model, resolution)
        selected_duration = _duration_for_model(resolved_model, duration, selected_resolution)
        parameters = _parameters_for_model(
            resolved_model,
            aspect_ratio=aspect,
            resolution=selected_resolution,
            duration=selected_duration,
            audio=audio,
            seed=seed,
        )

        input_payload: dict[str, object] = {"prompt": clean_prompt}
        clean_negative_prompt = _nonempty(negative_prompt)
        if clean_negative_prompt is not None and resolved_model.lower().startswith(("wan", "wanx")):
            input_payload["negative_prompt"] = clean_negative_prompt
        body = {"model": resolved_model, "input": input_payload, "parameters": parameters}

        try:
            response = self._http_post(
                f"{_native_api_base_url(self._base_url())}/services/aigc/video-generation/video-synthesis",
                headers=_auth_headers(api_key, async_request=True),
                json=body,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            payload = self._await_task(api_key, _checked(response).json())
            status = _task_status(payload)
            if status not in _SUCCESS_STATUSES:
                return error_response(
                    error=f"QwenAI video task ended with status {status}: {_task_error(payload)}",
                    error_type="job_failed",
                    provider=self.name,
                    model=resolved_model,
                    prompt=clean_prompt,
                    aspect_ratio=aspect,
                )
            video_url = _extract_video_url(payload)
            if video_url is None:
                raise ValueError("QwenAI video task succeeded without a video_url")
            try:
                video = str(self._video_saver(video_url, prefix="qwenai"))
            except Exception:
                video = video_url
            return success_response(
                video=video,
                model=resolved_model,
                prompt=clean_prompt,
                modality="text",
                aspect_ratio=aspect,
                duration=selected_duration,
                provider=self.name,
            )
        except Exception as exc:
            return error_response(
                error=f"QwenAI video request failed: {self._safe_error(exc)}",
                error_type="provider_error",
                provider=self.name,
                model=resolved_model,
                prompt=clean_prompt,
                aspect_ratio=aspect,
            )


def register(ctx: Any) -> None:
    ctx.register_video_gen_provider(QwenAIVideoGenProvider())
