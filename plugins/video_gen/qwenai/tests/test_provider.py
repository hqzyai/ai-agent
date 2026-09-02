from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


PLUGIN_PATH = Path(__file__).parents[1] / "__init__.py"


def _load_plugin() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hermes_qwenai_video_plugin_test", PLUGIN_PATH)
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


class QwenAIVideoProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = _load_plugin()

    def test_catalog_contains_only_text_to_video_models(self) -> None:
        payload = {
            "data": [
                {"id": "wan2.7-t2v-2026-06-12"},
                {"id": "wan2.7-i2v"},
                {"id": "wan2.7-image-pro"},
                {"id": "wan3.0-video", "capabilities": ["text-to-video", "image-to-video"]},
                {"id": "wan27-reference-to-video"},
                {"id": "wan2.1-t2v-plus"},
                {"id": "pixverse/pixverse-v6-t2v"},
                {"id": "vidu/viduq3-pro_text2video"},
                {"id": "qwen3.8-max"},
            ]
        }

        provider = self.plugin.QwenAIVideoGenProvider(
            environ={
                "QWENAI_BASE_URL": "https://ignored.example/v1",
                "QWENAI_API_KEY": "test-key",
            },
            config_loader=lambda: {},
            http_get=lambda *args, **kwargs: _FakeResponse(payload),
        )

        self.assertEqual(
            [row["id"] for row in provider.list_models()],
            ["wan2.7-t2v-2026-06-12", "wan3.0-video"],
        )
        self.assertTrue(all(row["modalities"] == ["text"] for row in provider.list_models()))
        self.assertEqual(
            [item["key"] for item in provider.get_setup_schema()["env_vars"]],
            ["QWENAI_API_KEY"],
        )

    def test_catalog_merges_all_official_text_to_video_openapi_specs(self) -> None:
        spec_models = {
            "openapi-happyhorse-text-to-video.json": ["happyhorse-1.1-t2v", "happyhorse-1.0-t2v"],
            "openapi-wan-text-to-video.json": [
                "wan2.6-t2v",
                "wan2.5-t2v-preview",
                "wan2.2-t2v-plus",
                "wan2.1-t2v-turbo",
                "wan2.1-t2v-plus",
            ],
            "openapi-wan27-text-to-video.json": [
                "wan2.7-t2v",
                "wan2.7-t2v-2026-06-12",
                "wan2.7-t2v-2026-04-25",
            ],
        }

        def fake_get(url: str, **kwargs: object) -> _FakeResponse:
            if url.endswith("/models"):
                return _FakeResponse({"data": []})
            models = spec_models[url.rsplit("/", 1)[-1]]
            return _FakeResponse(
                {
                    "components": {
                        "schemas": {
                            "Request": {
                                "properties": {
                                    "model": {"type": "string", "enum": models},
                                }
                            }
                        }
                    }
                }
            )

        provider = self.plugin.QwenAIVideoGenProvider(
            environ={"QWENAI_API_KEY": "test-key"},
            config_loader=lambda: {},
            http_get=fake_get,
        )
        model_ids = [row["id"] for row in provider.list_models()]

        self.assertEqual(len(model_ids), 8)
        self.assertIn("happyhorse-1.1-t2v", model_ids)
        self.assertIn("wan2.7-t2v-2026-06-12", model_ids)
        self.assertNotIn("wan2.1-t2v-plus", model_ids)
        self.assertNotIn("wan2.1-t2v-turbo", model_ids)
        self.assertFalse(any(model_id.startswith("pixverse/") for model_id in model_ids))
        self.assertFalse(any(model_id.startswith("vidu/") for model_id in model_ids))

    def test_provider_specific_parameter_shapes(self) -> None:
        self.assertEqual(self.plugin._resolution_for_model("happyhorse-1.0-t2v", "480p"), "720p")
        self.assertEqual(self.plugin._resolution_for_model("happyhorse-1.1-t2v", "480p"), "480p")
        happyhorse = self.plugin._parameters_for_model(
            "happyhorse-1.1-t2v",
            aspect_ratio="9:16",
            resolution="1080p",
            duration=8,
            audio=True,
            seed=42,
        )
        self.assertEqual(happyhorse["resolution"], "1080P")
        self.assertEqual(happyhorse["ratio"], "9:16")
        self.assertNotIn("prompt_extend", happyhorse)

    def test_latest_text_to_video_posts_polls_and_saves(self) -> None:
        post_calls: list[tuple[str, dict[str, Any]]] = []
        get_calls: list[tuple[str, dict[str, Any]]] = []
        saved: list[str] = []

        def fake_post(url: str, **kwargs: object) -> _FakeResponse:
            post_calls.append((url, dict(kwargs)))
            return _FakeResponse({"output": {"task_id": "task-1", "task_status": "PENDING"}})

        def fake_get(url: str, **kwargs: object) -> _FakeResponse:
            get_calls.append((url, dict(kwargs)))
            return _FakeResponse(
                {
                    "output": {
                        "task_id": "task-1",
                        "task_status": "SUCCEEDED",
                        "video_url": "https://cdn.example.com/result.mp4",
                    }
                }
            )

        def fake_save(url: str, **kwargs: object) -> str:
            saved.append(url)
            return "/tmp/qwenai-result.mp4"

        provider = self.plugin.QwenAIVideoGenProvider(
            environ={
                "QWENAI_BASE_URL": "https://ignored.example/v1",
                "QWENAI_API_KEY": "test-key",
                "QWENAI_VIDEO_MODEL": "wan2.7-t2v-2026-06-12",
            },
            config_loader=lambda: {},
            http_get=fake_get,
            http_post=fake_post,
            sleep=lambda seconds: None,
            monotonic=lambda: 0.0,
            video_saver=fake_save,
        )

        result = provider.generate(
            "a neon city in the rain",
            aspect_ratio="9:16",
            resolution="1080p",
            duration=10,
            negative_prompt="blurry",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["video"], "/tmp/qwenai-result.mp4")
        self.assertEqual(result["modality"], "text")
        self.assertEqual(saved, ["https://cdn.example.com/result.mp4"])
        self.assertEqual(
            post_calls[0][0],
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
        )
        self.assertEqual(post_calls[0][1]["headers"]["X-DashScope-Async"], "enable")
        self.assertEqual(
            post_calls[0][1]["json"]["parameters"],
            {
                "duration": 10,
                "prompt_extend": True,
                "watermark": False,
                "resolution": "1080P",
                "ratio": "9:16",
            },
        )
        self.assertEqual(post_calls[0][1]["json"]["input"]["negative_prompt"], "blurry")
        self.assertEqual(
            get_calls[0][0],
            "https://dashscope.aliyuncs.com/api/v1/tasks/task-1",
        )

    def test_legacy_model_uses_size_and_fixed_duration(self) -> None:
        post_bodies: list[dict[str, object]] = []

        def fake_post(url: str, **kwargs: object) -> _FakeResponse:
            post_bodies.append(kwargs["json"])
            return _FakeResponse(
                {
                    "output": {
                        "task_id": "task-2",
                        "task_status": "SUCCEEDED",
                        "video_url": "https://cdn.example.com/legacy.mp4",
                    }
                }
            )

        provider = self.plugin.QwenAIVideoGenProvider(
            environ={"QWENAI_API_KEY": "test-key", "QWENAI_VIDEO_MODEL": "wan2.2-t2v-plus"},
            config_loader=lambda: {},
            http_post=fake_post,
            video_saver=lambda *args, **kwargs: "/tmp/legacy.mp4",
        )
        result = provider.generate("a paper airplane", duration=12, resolution="720p")

        self.assertTrue(result["success"])
        self.assertEqual(result["duration"], 5)
        self.assertEqual(post_bodies[0]["parameters"]["size"], "1920*1080")
        self.assertNotIn("resolution", post_bodies[0]["parameters"])

    def test_image_input_is_rejected_without_a_request(self) -> None:
        provider = self.plugin.QwenAIVideoGenProvider(
            environ={"QWENAI_API_KEY": "test-key", "QWENAI_VIDEO_MODEL": "wan2.7-t2v"},
            config_loader=lambda: {},
            http_post=lambda *args, **kwargs: self.fail("HTTP request should not run"),
        )
        result = provider.generate("animate this", image_url="https://example.com/frame.png")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "unsupported_modality")

    def test_register_uses_qwenai_provider_name(self) -> None:
        registered: list[object] = []
        self.plugin.register(SimpleNamespace(register_video_gen_provider=registered.append))
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0].name, "qwenai")
        self.assertEqual(registered[0].capabilities()["modalities"], ["text"])
        self.assertFalse(registered[0].capabilities()["supports_audio"])


if __name__ == "__main__":
    unittest.main()
