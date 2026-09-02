#!/usr/bin/env python3
"""Reject floating third-party GitHub Action references."""

from __future__ import annotations

import re
import sys
from pathlib import Path


USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def main() -> int:
    errors: list[str] = []
    for path in sorted(Path(".github/workflows").glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for ref in USES_RE.findall(text):
            if ref.startswith("./"):
                continue
            if "@" not in ref:
                errors.append(f"{path}: action has no ref: {ref}")
                continue
            action, revision = ref.rsplit("@", 1)
            if not SHA_RE.fullmatch(revision):
                errors.append(f"{path}: {action} must be pinned to a 40-character commit SHA")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("validated GitHub Action pins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
