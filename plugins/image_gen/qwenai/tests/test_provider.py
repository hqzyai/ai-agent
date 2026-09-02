from __future__ import annotations

import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch


PLUGIN_PATH = Path(__file__).parents[1] / "__init__.py"


def _load_plugin() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hermes_qwenai_image_plugin_test", PLUGIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> object:
        return self._payload


class QwenAIImageProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = _load_plugin()

    def test_catalog_contains_only_text_to_image_models(self) -> None:
        payload = {
            "data": [
                {"id": "qwen-image-3.0-pro"},
                {"id": "qwen-image-edit-plus"},
                {"id": "wan2.7-image-pro", "capabilities": ["text-to-image", "image-edit"]},
                {"id": "wan2.7-t2v-2026-06-12"},
                {"id": "qwen3.8-max"},
                {"id": "z-image-turbo"},
            ]
        }
        seen: list[str] = []

        def fake_get(url: str, **kwargs: object) -> _FakeResponse:
            seen.append(url)
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
            return _FakeResponse(payload)

        provider = self.plugin.QwenAIImageGenProvider(
            environ={
                "QWENAI_BASE_URL": "https://ignored.example/v1",
                "QWENAI_API_KEY": "test-key",
            },
            config_loader=lambda: {},
            http_get=fake_get,
        )

        self.assertEqual(
            [row["id"] for row in provider.list_models()],
            ["qwen-image-3.0-pro", "wan2.7-image-pro", "z-image-turbo"],
        )
        self.assertEqual(
            seen,
            [
                "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                "https://dashscope.aliyuncs.com/api/v1/models",
            ],
        )
        self.assertEqual(
            [item["key"] for item in provider.get_setup_schema()["env_vars"]],
            ["QWENAI_API_KEY"],
        )

    def test_generation_uses_native_multimodal_endpoint(self) -> None:
        image_bytes = b"qwen-image-result"
        calls: list[tuple[str, dict[str, Any]]] = []

        def fake_post(url: str, **kwargs: object) -> _FakeResponse:
            calls.append((url, dict(kwargs)))
            return _FakeResponse(
                {
                    "output": {
                        "choices": [
                            {
                                "message": {
                                    "content": [
                                        {"b64_json": base64.b64encode(image_bytes).decode("ascii")}
                                    ]
                                }
                            }
                        ]
                    }
                }
            )

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            "os.environ", {"HERMES_HOME": temp_dir}, clear=False
        ):
            provider = self.plugin.QwenAIImageGenProvider(
                environ={
                    "QWENAI_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "QWENAI_API_KEY": "test-key",
                    "QWENAI_IMAGE_MODEL": "qwen-image-3.0-pro",
                },
                config_loader=lambda: {},
                http_post=fake_post,
            )
            result = provider.generate("a lighthouse at dusk", "portrait")

            self.assertTrue(result["success"])
            self.assertEqual(Path(result["image"]).read_bytes(), image_bytes)

        self.assertEqual(
            calls[0][0],
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        )
        self.assertEqual(calls[0][1]["json"]["model"], "qwen-image-3.0-pro")
        self.assertEqual(calls[0][1]["json"]["parameters"]["size"], "1152*2048")
        self.assertEqual(
            calls[0][1]["json"]["input"]["messages"][0]["content"],
            [{"text": "a lighthouse at dusk"}],
        )

    def test_image_input_is_rejected_without_a_request(self) -> None:
        provider = self.plugin.QwenAIImageGenProvider(
            environ={"QWENAI_API_KEY": "test-key", "QWENAI_IMAGE_MODEL": "qwen-image-3.0-pro"},
            config_loader=lambda: {},
            http_post=lambda *args, **kwargs: self.fail("HTTP request should not run"),
        )
        result = provider.generate("edit this", image_url="https://example.com/source.png")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "unsupported_modality")

    def test_register_uses_qwenai_provider_name(self) -> None:
        registered: list[object] = []
        self.plugin.register(SimpleNamespace(register_image_gen_provider=registered.append))
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0].name, "qwenai")
        self.assertEqual(registered[0].capabilities()["modalities"], ["text"])


if __name__ == "__main__":
    unittest.main()
