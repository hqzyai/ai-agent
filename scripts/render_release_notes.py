#!/usr/bin/env python3
"""Render deterministic GitHub release notes from an approved manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    upstream = data["upstream"]
    acceptance = data["acceptance"]
    lines = [
        f"# ai-agent {data['releaseTag']}",
        "",
        f"- Product version: `{data['productVersion']}`",
        f"- Source: `{data['sourceRepository']}@{data['sourceCommit']}`",
        f"- Upstream Hermes: [{upstream['tag']}]({upstream['releaseUrl']}) (`{upstream['commitSha']}`)",
        f"- Manual acceptance: [{acceptance['manual']}]({acceptance['evidenceUrl']})",
        "",
        "## Container",
        "",
        f"- `{data['artifacts']['container']['image']}`",
        f"- Platforms: {', '.join(data['artifacts']['container']['platforms'])}",
        f"- Digest: `{data['artifacts']['container']['digest']}`",
        "",
        "## Desktop artifacts",
        "",
    ]
    for platform, artifacts in data["artifacts"]["desktop"].items():
        lines.append(f"### {platform}")
        lines.append("")
        for artifact in artifacts:
            lines.append(f"- `{artifact['name']}` — SHA-256 `{artifact['sha256']}`")
        if not artifacts:
            lines.append("- No artifact recorded")
        lines.append("")
    args.output.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
