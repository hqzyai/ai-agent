from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_script("validate_release_manifest.py")
        self.candidate = ROOT / "release-manifests" / "v2026.08.31.candidate.json"

    def test_candidate_manifest_is_valid_before_release_gate(self) -> None:
        self.assertEqual(self.validator.validate(self.candidate, False), [])

    def test_draft_manifest_cannot_be_released(self) -> None:
        errors = self.validator.validate(self.candidate, True)
        self.assertIn("release manifest status must be approved", errors)
        self.assertIn("manual acceptance must pass", errors)
        self.assertIn("sourceCommit must be locked", errors)

    def test_version_and_branch_are_derived_from_upstream_and_calver(self) -> None:
        data = json.loads(self.candidate.read_text(encoding="utf-8"))
        data["sourceBranch"] = "agentos-20260831"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn("sourceBranch mismatch", self.validator.validate(path, False))

    def test_v0210_dry_run_manifest_is_valid(self) -> None:
        manifest = ROOT / "release-manifests" / "v2026.09.02.candidate.json"
        self.assertEqual(self.validator.validate(manifest, False), [])
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["productVersion"], "v0.21.0-2026.09.02")
        self.assertEqual(data["sourceBranch"], "ai-agent/hermes-v0.21.0-2026.09.02")
        self.assertEqual(data["upstream"]["tag"], "v2026.8.31")
        self.assertEqual(data["upstream"]["tagObjectSha"], "6e8f8418e6378eb2617e4de074e13dedd091b8af")
        self.assertEqual(data["upstream"]["commitSha"], "29112bef099274229cadff79cdff7bf7b99c4b77")


class BrandProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_script("validate_brand_profile.py")

    def test_default_profile_is_valid(self) -> None:
        profile = ROOT / "config/brand.env.example"
        self.assertEqual(self.validator.validate(profile), [])
        values, _ = self.validator.parse(profile)
        self.assertEqual(
            self.validator.profile_data_dir(values),
            "~/.agentos/profiles/hqzyai",
        )

    def test_an_unrelated_brand_is_valid(self) -> None:
        values = {
            "BRAND_NAME": "Acme Agent",
            "BRAND_WORDMARK": "ACME AGENT",
            "BRAND_SLUG": "acme-agent",
            "BRAND_ASSETS_DIR": "branding/acme-agent",
            "ORG_NAME": "acme",
            "APP_NAME": "Acme Agent",
            "APP_ID": "com.acme.agent",
            "APP_DATA_DIR": "~/.acme-agent",
            "APP_DEFAULT_LOCALE": "en-US",
            "SKILL_HUB_NAME": "Acme Skills",
            "SKILL_HUB_SOURCE": "internal",
        }
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "brand.env"
            profile.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
            self.assertEqual(self.validator.validate(profile), [])
            self.assertEqual(
                self.validator.profile_data_dir(values),
                "~/.acme-agent/profiles/acme",
            )

    def test_legacy_catch_all_brand_prefixes_are_rejected(self) -> None:
        source = (ROOT / "config/brand.env.example").read_text(encoding="utf-8")
        source += "BRAND_APP_NAME=Bad\nCOMPANY_NAME=legacy\n"
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "brand.env"
            profile.write_text(source, encoding="utf-8")
            self.assertIn("unsupported variable: BRAND_APP_NAME", self.validator.validate(profile))
            self.assertIn("unsupported variable: COMPANY_NAME", self.validator.validate(profile))


class CommitCollectorTests(unittest.TestCase):
    def test_category_classifier_is_multi_label(self) -> None:
        collector = load_script("collect_agentos_commits.py")
        categories = collector.classify(
            "fix(desktop): login and package update",
            ["apps/desktop/electron/client-package-update.cjs", "apps/desktop/components/login-screen.tsx"],
            ["a"],
        )
        self.assertIn("auth-remote-gateway", categories)
        self.assertIn("packaging-updater-release", categories)

    def test_inventory_has_full_sha_and_unique_commits(self) -> None:
        data = json.loads((ROOT / "specs/source/agentos-20260825-commits.json").read_text(encoding="utf-8"))
        self.assertEqual(data["matchedCommitCount"], 79)
        shas = [commit["sha"] for commit in data["commits"]]
        self.assertEqual(len(shas), len(set(shas)))
        self.assertTrue(all(len(sha) == 40 for sha in shas))


class RepositoryValidationTests(unittest.TestCase):
    def test_check_script_scopes_unittest_to_governance_modules(self) -> None:
        source = (ROOT / "scripts/check.sh").read_text(encoding="utf-8")
        self.assertNotIn("unittest discover -s tests", source)
        for module in (
            "tests.test_governance",
            "tests.test_contributor_skills",
            "tests.test_bundled_plugins",
        ):
            self.assertIn(module, source)

    def test_specs_validator_passes(self) -> None:
        result = subprocess.run([sys.executable, "scripts/validate_specs.py"], cwd=ROOT)
        self.assertEqual(result.returncode, 0)

    def test_all_external_actions_are_commit_pinned(self) -> None:
        result = subprocess.run([sys.executable, "scripts/validate_workflows.py"], cwd=ROOT)
        self.assertEqual(result.returncode, 0)


class CandidateEvidenceTests(unittest.TestCase):
    def test_import_requires_all_three_desktop_platforms(self) -> None:
        script = load_script("finalize_candidate_manifest.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = json.loads((ROOT / "release-manifests/v2026.08.31.candidate.json").read_text())
            manifest["sourceCommit"] = "a" * 40
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps({"sourceCommit": "a" * 40, "containerDigest": "sha256:" + "b" * 64}))
            acceptance = root / "acceptance.json"
            acceptance.write_text(json.dumps({"sourceCommit": "a" * 40, "result": "passed"}))
            linux = root / "linux.artifacts.json"
            linux.write_text(json.dumps([{"name": "agent.AppImage", "sha256": "c" * 64}]))
            argv = [
                "finalize_candidate_manifest.py", str(manifest_path), "--evidence", str(evidence),
                "--acceptance", str(acceptance), "--artifact-manifest", str(linux),
            ]
            with mock.patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                script.main()

    def test_import_marks_automated_only_and_preserves_manual_gate(self) -> None:
        script = load_script("finalize_candidate_manifest.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = json.loads((ROOT / "release-manifests/v2026.08.31.candidate.json").read_text())
            manifest["sourceCommit"] = "a" * 40
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps({"sourceCommit": "a" * 40, "containerDigest": "sha256:" + "b" * 64}))
            acceptance = root / "acceptance.json"
            acceptance.write_text(json.dumps({"sourceCommit": "a" * 40, "result": "passed"}))
            artifact_paths = []
            for platform in ("linux", "macos", "windows"):
                path = root / f"{platform}.artifacts.json"
                path.write_text(json.dumps([{"name": f"agent.{platform}", "sha256": "c" * 64}]))
                artifact_paths.extend(["--artifact-manifest", str(path)])
            argv = [
                "finalize_candidate_manifest.py", str(manifest_path), "--evidence", str(evidence),
                "--acceptance", str(acceptance), *artifact_paths,
            ]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(script.main(), 0)
            updated = json.loads(manifest_path.read_text())
            self.assertEqual(updated["status"], "candidate")
            self.assertEqual(updated["acceptance"]["automated"], "passed")
            self.assertEqual(updated["acceptance"]["manual"], "pending")


if __name__ == "__main__":
    unittest.main()
