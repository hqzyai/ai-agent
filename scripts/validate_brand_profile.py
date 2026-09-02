#!/usr/bin/env python3
"""Validate a portable product-brand environment profile."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED = {
    "BRAND_NAME", "BRAND_WORDMARK", "BRAND_SLUG", "BRAND_ASSETS_DIR",
    "ORG_NAME", "APP_NAME", "APP_ID", "APP_DATA_DIR",
    "APP_DEFAULT_LOCALE", "SKILL_HUB_NAME", "SKILL_HUB_SOURCE",
}
FORBIDDEN = {
    "BRAND_APP_NAME", "BRAND_APP_ID", "BRAND_DATA_DIR",
    "COMPANY_NAME", "BRAND_COMPANY_NAME", "BRAND_SKILL_HUB_NAME",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
APP_ID_RE = re.compile(r"^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)+$")
LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


def parse(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line {number} is not KEY=VALUE")
            continue
        key, value = line.split("=", 1)
        if key in values:
            errors.append(f"duplicate variable: {key}")
        values[key] = value
    return values, errors


def validate(path: Path) -> list[str]:
    try:
        values, errors = parse(path)
    except OSError as exc:
        return [str(exc)]
    for key in sorted(REQUIRED - values.keys()):
        errors.append(f"missing variable: {key}")
    for key in sorted(values.keys() - REQUIRED):
        errors.append(f"unsupported variable: {key}")
    for key in sorted(FORBIDDEN & values.keys()):
        message = f"unsupported variable: {key}"
        if message not in errors:
            errors.append(message)
    for key in REQUIRED & values.keys():
        if not values[key]:
            errors.append(f"empty variable: {key}")
    if values.get("BRAND_SLUG") and not SLUG_RE.fullmatch(values["BRAND_SLUG"]):
        errors.append("BRAND_SLUG must be a lowercase slug")
    if values.get("ORG_NAME") and not SLUG_RE.fullmatch(values["ORG_NAME"]):
        errors.append("ORG_NAME must be a lowercase path-safe slug")
    if values.get("APP_ID") and not APP_ID_RE.fullmatch(values["APP_ID"]):
        errors.append("APP_ID must be a reverse-domain style identifier")
    if values.get("APP_DEFAULT_LOCALE") and not LOCALE_RE.fullmatch(values["APP_DEFAULT_LOCALE"]):
        errors.append("APP_DEFAULT_LOCALE must be ll or ll-CC")
    assets = values.get("BRAND_ASSETS_DIR", "")
    if assets.startswith(("/", "~")) or ".." in Path(assets).parts:
        errors.append("BRAND_ASSETS_DIR must be a repository-relative path")
    data_dir = values.get("APP_DATA_DIR", "")
    if not (data_dir.startswith("~/") or data_dir.startswith("/")):
        errors.append("APP_DATA_DIR must be an absolute or home-relative path")
    return errors


def profile_data_dir(values: dict[str, str]) -> str:
    """Return the organization-scoped application data directory."""
    return f"{values['APP_DATA_DIR'].rstrip('/')}/profiles/{values['ORG_NAME']}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    errors = validate(args.profile)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated brand profile {args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
