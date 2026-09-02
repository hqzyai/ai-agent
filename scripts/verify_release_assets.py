#!/usr/bin/env python3
"""Verify desktop release files against an approved manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("asset_dir", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors: list[str] = []
    for platform, entries in data["artifacts"]["desktop"].items():
        for entry in entries:
            path = args.asset_dir / entry["name"]
            if not path.is_file():
                errors.append(f"missing {platform} asset: {entry['name']}")
            elif digest(path) != entry["sha256"]:
                errors.append(f"SHA-256 mismatch for {entry['name']}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("verified desktop release assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
