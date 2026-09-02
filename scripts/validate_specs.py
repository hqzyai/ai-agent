#!/usr/bin/env python3
"""Validate that acceptance specifications remain complete and unambiguous."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "specs"
ID_RE = re.compile(r"\*\*([A-Z]+-[0-9]{3})\*\*")


def main() -> int:
    errors: list[str] = []
    seen: dict[str, Path] = {}
    specs = sorted(SPEC_DIR.glob("[0-9][0-9]-*.md"))
    if len(specs) < 8:
        errors.append(f"expected at least 8 numbered specs, found {len(specs)}")
    for path in specs:
        text = path.read_text(encoding="utf-8")
        for heading in ("## Requirements", "## Automated acceptance", "## Manual acceptance"):
            if heading not in text:
                errors.append(f"{path.relative_to(ROOT)} missing {heading}")
        ids = ID_RE.findall(text)
        if not ids:
            errors.append(f"{path.relative_to(ROOT)} has no requirement IDs")
        for requirement_id in ids:
            previous = seen.get(requirement_id)
            if previous:
                errors.append(f"duplicate requirement {requirement_id}: {previous} and {path}")
            seen[requirement_id] = path
        for forbidden in ("TBD", "TODO", "待补充"):
            if forbidden in text:
                errors.append(f"{path.relative_to(ROOT)} contains placeholder {forbidden}")

    source_path = SPEC_DIR / "source" / "agentos-20260825-commits.json"
    if not source_path.exists():
        errors.append("missing generated commit inventory JSON")
    else:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        if source.get("matchedCommitCount") != len(source.get("commits", [])):
            errors.append("commit inventory count does not match commits array")
        if source.get("matchedCommitCount") != 79:
            errors.append(f"expected audited baseline of 79 commits, got {source.get('matchedCommitCount')}")
        shas = [commit.get("sha") for commit in source.get("commits", [])]
        if len(shas) != len(set(shas)):
            errors.append("commit inventory contains duplicate SHAs")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {len(specs)} specs with {len(seen)} unique requirements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
