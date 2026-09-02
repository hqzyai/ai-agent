#!/usr/bin/env python3
"""Validate an ai-agent candidate or approved release manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CALVER_RE = re.compile(r"^20[0-9]{2}\.(0[1-9]|1[0-2])\.([0-2][0-9]|3[01])$")
HERMES_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate(path: Path, for_release: bool, for_candidate: bool = False) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    require(errors, data.get("schemaVersion") == 1, "schemaVersion must be 1")
    require(errors, data.get("product") == "ai-agent", "product must be ai-agent")
    calver = data.get("calver", "")
    upstream = data.get("upstream", {})
    hermes_version = upstream.get("version", "")
    require(errors, bool(CALVER_RE.fullmatch(calver)), "calver must be YYYY.MM.DD")
    require(errors, bool(HERMES_RE.fullmatch(hermes_version)), "invalid Hermes version")
    require(errors, data.get("productVersion") == f"v{hermes_version}-{calver}", "productVersion mismatch")
    require(errors, data.get("releaseTag") == f"v{calver}", "releaseTag mismatch")
    require(
        errors,
        data.get("sourceBranch") == f"ai-agent/hermes-v{hermes_version}-{calver}",
        "sourceBranch mismatch",
    )
    require(errors, upstream.get("repository") == "NousResearch/hermes-agent", "wrong upstream repository")
    require(errors, bool(SHA_RE.fullmatch(upstream.get("tagObjectSha", ""))), "invalid tag object SHA")
    require(errors, bool(SHA_RE.fullmatch(upstream.get("commitSha", ""))), "invalid upstream commit SHA")
    require(errors, upstream.get("tag", "").startswith("v2026."), "upstream tag must be a release tag")
    platforms = data.get("artifacts", {}).get("container", {}).get("platforms", [])
    require(errors, platforms == ["linux/amd64", "linux/arm64"], "container platforms must be amd64 + arm64")
    desktop = data.get("artifacts", {}).get("desktop", {})
    require(errors, set(desktop) == {"linux", "macos", "windows"}, "desktop must contain three platforms")
    if for_candidate or for_release:
        require(errors, bool(SHA_RE.fullmatch(data.get("sourceCommit") or "")), "sourceCommit must be locked")
        require(
            errors,
            data.get("status") in {"candidate", "approved"},
            "candidate manifest status must be candidate or approved",
        )
    if for_release:
        acceptance = data.get("acceptance", {})
        require(errors, data.get("status") == "approved", "release manifest status must be approved")
        require(errors, acceptance.get("automated") == "passed", "automated acceptance must pass")
        require(errors, acceptance.get("manual") == "passed", "manual acceptance must pass")
        require(errors, bool(acceptance.get("approvedBy")), "manual approver list is empty")
        require(errors, bool(acceptance.get("evidenceUrl")), "manual evidence URL is empty")
        container = data.get("artifacts", {}).get("container", {})
        require(errors, bool(container.get("digest")), "container digest is empty")
        for platform in ("linux", "macos", "windows"):
            entries = desktop.get(platform, [])
            require(errors, bool(entries), f"desktop {platform} artifacts are empty")
            for entry in entries:
                require(errors, bool(entry.get("name")), f"desktop {platform} artifact name is empty")
                require(
                    errors,
                    bool(re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", ""))),
                    f"desktop {platform} artifact SHA-256 is invalid",
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--for-candidate", action="store_true")
    parser.add_argument("--for-release", action="store_true")
    args = parser.parse_args()
    try:
        errors = validate(args.manifest, args.for_release, args.for_candidate)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated release manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
