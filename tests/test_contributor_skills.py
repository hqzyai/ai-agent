from __future__ import annotations

import hashlib
import json
import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "docs" / "skills"
LOCK = ROOT / "config" / "contributor-skills.lock.json"
BRAND_PROFILE = ROOT / "config" / "brand.env.example"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


class ContributorSkillsTests(unittest.TestCase):
    def load_lock(self) -> dict:
        return json.loads(LOCK.read_text(encoding="utf-8"))

    def test_snapshot_is_locked_to_requested_source(self) -> None:
        lock = self.load_lock()
        self.assertEqual(lock["schemaVersion"], 1)
        self.assertEqual(lock["sourceRepository"], "hqzyai/agentos-desktop")
        self.assertEqual(lock["sourceBranch"], "agentos-20260825")
        self.assertEqual(lock["sourceCommit"], "b67e620899a50ad717dae3ff384ca9c8050f853a")

    def test_every_skill_has_entrypoint_and_locked_files_match(self) -> None:
        lock = self.load_lock()
        skill_dirs = sorted(path for path in SKILLS.iterdir() if path.is_dir())
        self.assertEqual([path.name for path in skill_dirs], lock["skills"])
        for skill in skill_dirs:
            self.assertTrue((skill / "SKILL.md").is_file(), skill)

        actual_files = sorted(path for path in SKILLS.rglob("*") if path.is_file())
        expected_paths = sorted(lock["files"])
        self.assertEqual([path.relative_to(ROOT).as_posix() for path in actual_files], expected_paths)
        for path in actual_files:
            relative = path.relative_to(ROOT).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, lock["files"][relative], relative)

    def test_skill_scripts_remain_executable(self) -> None:
        scripts = list(SKILLS.glob("*/scripts/*"))
        self.assertTrue(scripts)
        for path in scripts:
            self.assertTrue(path.stat().st_mode & stat.S_IXUSR, path)

    def test_merge_skill_uses_product_version_branch_and_exact_tag(self) -> None:
        skill = (SKILLS / "merge-hermes-upstream" / "SKILL.md").read_text(encoding="utf-8")
        start = (SKILLS / "merge-hermes-upstream" / "scripts" / "start-merge.sh").read_text(encoding="utf-8")
        validate = (SKILLS / "merge-hermes-upstream" / "scripts" / "validate-merge.sh").read_text(encoding="utf-8")
        combined = skill + start + validate
        self.assertIn("ai-agent/hermes-v", combined)
        self.assertIn("UPSTREAM_TAG", start)
        self.assertIn("refs/tags/", start)
        self.assertNotIn("agentos-YYYYMMDD", combined)
        self.assertNotIn('merge "$UPSTREAM_REMOTE/main"', start)

    def test_vendored_skill_is_portable(self) -> None:
        for path in SKILLS.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("/Users/jiawy/", text, path)
                self.assertNotIn("agentos-YYYYMMDD", text, path)

    def test_brand_profile_uses_domain_namespaces(self) -> None:
        profile = load_env(BRAND_PROFILE)
        self.assertEqual(profile["BRAND_NAME"], "AgentOS")
        self.assertEqual(profile["BRAND_WORDMARK"], "AGENT OS")
        self.assertEqual(profile["BRAND_SLUG"], "agentos")
        self.assertEqual(profile["BRAND_ASSETS_DIR"], "branding/agentos")
        self.assertEqual(profile["ORG_NAME"], "hqzyai")
        self.assertEqual(profile["APP_NAME"], "AgentOS")
        self.assertEqual(profile["APP_ID"], "com.hqzyai.agentos")
        self.assertEqual(profile["APP_DATA_DIR"], "~/.agentos")
        self.assertEqual(profile["APP_DEFAULT_LOCALE"], "zh-CN")
        self.assertEqual(profile["SKILL_HUB_NAME"], "华清严选")
        self.assertEqual(profile["SKILL_HUB_SOURCE"], "nacos")
        self.assertNotIn("BRAND_APP_NAME", profile)
        self.assertNotIn("BRAND_SKILL_HUB_NAME", profile)
        self.assertNotIn("COMPANY_NAME", profile)
        self.assertNotIn("BRAND_COMPANY_NAME", profile)

    def test_merge_skill_documents_brand_profile_contract(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in SKILLS.rglob("*")
            if path.is_file()
        )
        for name in (
            "BRAND_NAME",
            "BRAND_ASSETS_DIR",
            "ORG_NAME",
            "APP_NAME",
            "APP_ID",
            "APP_DATA_DIR",
            "SKILL_HUB_NAME",
            "SKILL_HUB_SOURCE",
        ):
            self.assertIn(name, text)

        self.assertIn("{APP_DATA_DIR}/profiles/{ORG_NAME}", text)

    def test_merge_skill_enforces_bundled_plugin_contract(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SKILLS / "merge-hermes-upstream").rglob("*")
            if path.is_file()
        )
        for contract in (
            "apps/desktop/src/plugins",
            "plugins/",
            "config/bundled-plugins.lock.json",
            "validate_bundled_plugins.py",
            "git apply --check",
            "PLUGIN-",
        ):
            self.assertIn(contract, text)


if __name__ == "__main__":
    unittest.main()
