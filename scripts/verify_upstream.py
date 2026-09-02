#!/usr/bin/env python3
"""Verify a manifest's Hermes tag against the official remote repository."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


OFFICIAL_URL = "https://github.com/NousResearch/hermes-agent.git"


def remote_refs(tag: str) -> tuple[str, str]:
    ref = f"refs/tags/{tag}"
    output = subprocess.check_output(
        ["git", "ls-remote", "--tags", OFFICIAL_URL, ref, f"{ref}^{{}}"],
        text=True,
    )
    values = {name: sha for sha, name in (line.split() for line in output.splitlines())}
    if ref not in values:
        raise ValueError(f"official upstream tag does not exist: {tag}")
    return values[ref], values.get(f"{ref}^{{}}", values[ref])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    upstream = data["upstream"]
    tag_object, commit = remote_refs(upstream["tag"])
    if tag_object != upstream["tagObjectSha"]:
        parser.error(f"official tag object changed or manifest is wrong: {tag_object}")
    if commit != upstream["commitSha"]:
        parser.error(f"official peeled commit changed or manifest is wrong: {commit}")
    print(f"verified official Hermes {upstream['tag']} -> {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
