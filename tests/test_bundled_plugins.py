from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config" / "bundled-plugins.lock.json"
VALIDATOR = ROOT / "scripts" / "validate_bundled_plugins.py"
FIXTURE_MANIFEST = """name: demo
version: 1.0.0
description: demo plugin
author: hqzyai
kind: backend
requires_env:
  - DEMO_TOKEN
"""
FIXTURE_SHA256 = "0c791f19e0a870099899f74e480a74da5d15465bfb1c1ae809b028aa6dde85ce"


class BundledPluginRepositoryTests(unittest.TestCase):
    def test_authoritative_plugin_sources_are_present(self) -> None:
        expected = (
            "apps/desktop/src/plugins/channels/plugin.tsx",
            "apps/desktop/src/plugins/channels/page.tsx",
            "plugins/image_gen/qwenai/plugin.yaml",
            "plugins/video_gen/qwenai/plugin.yaml",
            "plugins/web/openserp/plugin.yaml",
            "patches/bundled-plugins/channels/hermes-channels-integration.patch",
        )
        self.assertEqual([path for path in expected if not (ROOT / path).is_file()], [])

    def test_channels_uses_its_downstream_identity(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "apps/desktop/src/plugins/channels").glob("*.tsx")
        )
        self.assertIn("id: 'channels'", source)
        self.assertIn("path: '/channels'", source)
        self.assertNotIn("im-channels", source.lower())
        self.assertNotIn("ImChannels", source)

    def test_lock_records_approved_initial_sources(self) -> None:
        self.assertTrue(LOCK.is_file(), LOCK)
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["schemaVersion"], 1)
        bundles = {bundle["id"]: bundle for bundle in lock["bundles"]}
        self.assertEqual(
            bundles["desktop-channels"]["source"]["archiveSha256"],
            "76ed98ed53ca5df1e31e10634eec87dd948b0467f5617c7fe837917d56e49ed1",
        )
        for bundle_id in ("image-gen-qwenai", "video-gen-qwenai", "web-openserp"):
            self.assertEqual(
                bundles[bundle_id]["source"]["commit"],
                "a605cf524311a0fceae3e60b9354c2535a741378",
            )

    def test_repository_snapshot_passes_the_executable_validator(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_bundled_plugins.py", str(LOCK)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated 4 bundled plugins", result.stdout)


class BundledPluginValidatorTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        plugin_dir = root / "plugins/web/demo"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.yaml").write_text(FIXTURE_MANIFEST, encoding="utf-8")
        lock = {
            "schemaVersion": 1,
            "policy": "authoritative-downstream-source",
            "excludedInputs": [],
            "bundles": [
                {
                    "id": "web-demo",
                    "type": "backend",
                    "localPaths": ["plugins/web/demo"],
                    "source": {
                        "kind": "git",
                        "repository": "https://github.com/hqzyai/demo.git",
                        "commit": "a" * 40,
                        "sourcePath": "web/demo",
                    },
                    "files": {"plugins/web/demo/plugin.yaml": FIXTURE_SHA256},
                }
            ],
        }
        path = root / "lock.json"
        path.write_text(json.dumps(lock), encoding="utf-8")
        return path

    def run_validator(self, root: Path, lock: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(lock)],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def test_valid_minimal_backend_plugin_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_validator(root, self.make_fixture(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hash_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self.make_fixture(root)
            (root / "plugins/web/demo/plugin.yaml").write_text(FIXTURE_MANIFEST + "# changed\n")
            result = self.run_validator(root, lock)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sha256 mismatch", result.stderr)

    def test_undeclared_and_forbidden_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self.make_fixture(root)
            (root / "plugins/web/demo/.DS_Store").write_text("metadata")
            result = self.run_validator(root, lock)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden file", result.stderr)
            self.assertIn("undeclared file", result.stderr)

    def test_unsafe_and_duplicate_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self.make_fixture(root)
            data = json.loads(lock.read_text())
            duplicate = json.loads(json.dumps(data["bundles"][0]))
            duplicate["id"] = "duplicate"
            duplicate["localPaths"] = ["../escape"]
            data["bundles"].append(duplicate)
            lock.write_text(json.dumps(data))
            result = self.run_validator(root, lock)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe path", result.stderr)
            self.assertIn("declared by multiple bundles", result.stderr)

    def test_backend_manifest_requires_environment_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = self.make_fixture(root)
            manifest = root / "plugins/web/demo/plugin.yaml"
            manifest.write_text("name: demo\nversion: 1.0.0\nkind: backend\n")
            data = json.loads(lock.read_text())
            data["bundles"][0]["files"]["plugins/web/demo/plugin.yaml"] = (
                "d04048f4fd92457f5d6534d4329a93d707e076fe182f898b6118a59d48f8af74"
            )
            lock.write_text(json.dumps(data))
            result = self.run_validator(root, lock)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing manifest keys", result.stderr)


if __name__ == "__main__":
    unittest.main()
