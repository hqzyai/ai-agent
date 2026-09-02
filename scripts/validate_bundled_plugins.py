#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


FORBIDDEN_PARTS = {".git", ".idea", "__MACOSX", "__pycache__", "node_modules"}
FORBIDDEN_NAMES = {".DS_Store"}
MANIFEST_KEYS = {"name", "version", "description", "author", "kind", "requires_env"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_manifest_keys(path: Path) -> tuple[set[str], str | None, bool]:
    keys: set[str] = set()
    kind: str | None = None
    has_required_env_value = False
    in_required_env = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith((" ", "\t")):
            if in_required_env and raw_line.strip().startswith("-") and raw_line.strip()[1:].strip():
                has_required_env_value = True
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s*(.*))?$", raw_line)
        if not match:
            in_required_env = False
            continue
        key, value = match.group(1), (match.group(2) or "").strip().strip('"\'')
        keys.add(key)
        in_required_env = key == "requires_env"
        if key == "kind":
            kind = value
    return keys, kind, has_required_env_value


def is_forbidden(path: PurePosixPath) -> bool:
    return (
        path.name in FORBIDDEN_NAMES
        or path.suffix == ".pyc"
        or any(part in FORBIDDEN_PARTS for part in path.parts)
    )


def validate_source(bundle_id: str, source: object) -> list[str]:
    if not isinstance(source, dict):
        return [f"{bundle_id}: source must be an object"]
    kind = source.get("kind")
    if kind == "git":
        errors = []
        if not isinstance(source.get("repository"), str) or not source["repository"].startswith("https://github.com/"):
            errors.append(f"{bundle_id}: git source repository must be an https GitHub URL")
        if not isinstance(source.get("commit"), str) or not COMMIT_RE.fullmatch(source["commit"]):
            errors.append(f"{bundle_id}: git source commit must be a full 40-character SHA")
        if not safe_relative_path(source.get("sourcePath")):
            errors.append(f"{bundle_id}: unsafe path in sourcePath: {source.get('sourcePath')!r}")
        return errors
    if kind == "archive":
        digest = source.get("archiveSha256")
        errors = []
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"{bundle_id}: archiveSha256 must be lowercase SHA-256")
        if not isinstance(source.get("archiveName"), str) or not source["archiveName"]:
            errors.append(f"{bundle_id}: archiveName is required")
        if not safe_relative_path(source.get("memberPrefix")):
            errors.append(f"{bundle_id}: unsafe path in memberPrefix: {source.get('memberPrefix')!r}")
        return errors
    return [f"{bundle_id}: unsupported source kind: {kind!r}"]


def validate_lock(repo_root: Path, lock_path: Path) -> list[str]:
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"could not read lock: {error}"]

    errors: list[str] = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if data.get("policy") != "authoritative-downstream-source":
        errors.append("policy must be authoritative-downstream-source")
    bundles = data.get("bundles")
    if not isinstance(bundles, list) or not bundles:
        return errors + ["bundles must be a non-empty list"]

    bundle_ids: set[str] = set()
    path_owners: dict[str, str] = {}
    root_owners: dict[str, str] = {}
    declared_files: set[str] = set()
    valid_roots: list[str] = []

    for bundle in bundles:
        if not isinstance(bundle, dict):
            errors.append("bundle entry must be an object")
            continue
        bundle_id = bundle.get("id")
        if not isinstance(bundle_id, str) or not bundle_id:
            errors.append("bundle id must be a non-empty string")
            bundle_id = "<invalid>"
        elif bundle_id in bundle_ids:
            errors.append(f"duplicate bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)

        bundle_type = bundle.get("type")
        if bundle_type not in {"desktop", "backend"}:
            errors.append(f"{bundle_id}: type must be desktop or backend")
        errors.extend(validate_source(bundle_id, bundle.get("source")))

        local_paths = bundle.get("localPaths")
        if not isinstance(local_paths, list) or not local_paths:
            errors.append(f"{bundle_id}: localPaths must be a non-empty list")
            local_paths = []
        safe_roots: list[str] = []
        for local_path in local_paths:
            if not safe_relative_path(local_path):
                errors.append(f"{bundle_id}: unsafe path in localPaths: {local_path!r}")
                continue
            owner = root_owners.setdefault(local_path, bundle_id)
            if owner != bundle_id:
                errors.append(f"{local_path}: declared by multiple bundles: {owner}, {bundle_id}")
            safe_roots.append(local_path)
            valid_roots.append(local_path)

        files = bundle.get("files")
        if not isinstance(files, dict) or not files:
            errors.append(f"{bundle_id}: files must be a non-empty object")
            continue
        for relative, expected_digest in files.items():
            if not safe_relative_path(relative):
                errors.append(f"{bundle_id}: unsafe path in files: {relative!r}")
                continue
            if not any(relative == root or relative.startswith(root + "/") for root in safe_roots):
                errors.append(f"{bundle_id}: file is outside localPaths: {relative}")
            owner = path_owners.setdefault(relative, bundle_id)
            if owner != bundle_id:
                errors.append(f"{relative}: declared by multiple bundles: {owner}, {bundle_id}")
            declared_files.add(relative)
            posix_path = PurePosixPath(relative)
            if is_forbidden(posix_path):
                errors.append(f"{bundle_id}: forbidden file declared: {relative}")
            if not isinstance(expected_digest, str) or not SHA256_RE.fullmatch(expected_digest):
                errors.append(f"{bundle_id}: invalid sha256 for {relative}")
                continue
            actual_path = repo_root / relative
            if not actual_path.is_file():
                errors.append(f"{bundle_id}: missing file: {relative}")
                continue
            if actual_path.is_symlink():
                errors.append(f"{bundle_id}: symlink is not allowed: {relative}")
                continue
            actual_digest = sha256(actual_path)
            if actual_digest != expected_digest:
                errors.append(
                    f"{bundle_id}: sha256 mismatch for {relative}: expected {expected_digest}, got {actual_digest}"
                )

        if bundle_type == "backend":
            manifests = [relative for relative in files if relative.endswith("/plugin.yaml")]
            if len(manifests) != 1:
                errors.append(f"{bundle_id}: backend bundle must declare exactly one plugin.yaml")
            elif (repo_root / manifests[0]).is_file():
                keys, manifest_kind, has_env = parse_manifest_keys(repo_root / manifests[0])
                missing = sorted(MANIFEST_KEYS - keys)
                if missing:
                    errors.append(f"{bundle_id}: missing manifest keys: {', '.join(missing)}")
                if manifest_kind != "backend":
                    errors.append(f"{bundle_id}: plugin.yaml kind must be backend")
                if "requires_env" in keys and not has_env:
                    errors.append(f"{bundle_id}: requires_env must declare at least one variable")

        if bundle_type == "desktop":
            for relative in files:
                if not relative.endswith((".ts", ".tsx", ".js", ".jsx")):
                    continue
                path = repo_root / relative
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    if "im-channels" in text.lower() or "ImChannels" in text:
                        errors.append(f"{bundle_id}: legacy im-channels identity remains in {relative}")

    actual_files: set[str] = set()
    for relative_root in valid_roots:
        root = repo_root / relative_root
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() and not path.is_symlink():
                continue
            relative = path.relative_to(repo_root).as_posix()
            actual_files.add(relative)
            pure = PurePosixPath(relative)
            if is_forbidden(pure):
                errors.append(f"forbidden file: {relative}")
            if path.is_symlink():
                errors.append(f"symlink is not allowed: {relative}")

    for relative in sorted(actual_files - declared_files):
        errors.append(f"undeclared file: {relative}")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: validate_bundled_plugins.py LOCK", file=sys.stderr)
        return 2
    lock_path = Path(args[0]).resolve()
    errors = validate_lock(Path.cwd().resolve(), lock_path)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    bundle_count = len(json.loads(lock_path.read_text(encoding="utf-8"))["bundles"])
    print(f"validated {bundle_count} bundled plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
