#!/usr/bin/env python3
"""Import CI candidate evidence into a release manifest without approving it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--artifact-manifest", action="append", type=Path, default=[])
    args = parser.parse_args()

    data = read(args.manifest)
    evidence = read(args.evidence)
    acceptance = read(args.acceptance)
    source = data.get("sourceCommit")
    if not source or evidence.get("sourceCommit") != source or acceptance.get("sourceCommit") != source:
        parser.error("candidate evidence and acceptance report must match manifest sourceCommit")
    if acceptance.get("result") != "passed":
        parser.error("automated acceptance did not pass")
    digest = evidence.get("containerDigest", "")
    if not digest.startswith("sha256:"):
        parser.error("candidate container digest is missing or invalid")

    desktop = {"linux": [], "macos": [], "windows": []}
    for path in args.artifact_manifest:
        platform = path.name.removesuffix(".artifacts.json")
        if platform not in desktop:
            parser.error(f"unknown desktop platform in {path.name}")
        desktop[platform] = read(path)
    missing = [platform for platform, entries in desktop.items() if not entries]
    if missing:
        parser.error(f"missing desktop artifact manifests: {', '.join(missing)}")

    data["status"] = "candidate"
    data["acceptance"]["automated"] = "passed"
    data["artifacts"]["container"]["digest"] = digest
    data["artifacts"]["desktop"] = desktop
    args.manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"imported candidate evidence into {args.manifest}; manual acceptance remains pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
