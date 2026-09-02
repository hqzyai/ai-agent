#!/usr/bin/env python3
"""Run the fixed AgentOS upstream-sync acceptance baseline locally or in CI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


QUICK = [
    ["bash", "docs/skills/merge-hermes-upstream/scripts/audit-agentos-contracts.sh"],
    ["git", "diff", "--check"],
    ["npm", "--prefix", "apps/desktop", "run", "typecheck"],
    ["npm", "--prefix", "apps/desktop", "run", "test:desktop:platforms"],
    ["npm", "--prefix", "apps/desktop", "run", "test:ui", "--", "--run"],
]

FULL = QUICK + [
    ["scripts/run_tests.sh"],
    ["npm", "--prefix", "apps/desktop", "run", "build"],
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--report", type=Path, default=Path("acceptance-report.json"))
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    if not (args.source / ".git").exists():
        parser.error(f"source is not a Git checkout: {args.source}")

    commands = QUICK if args.mode == "quick" else FULL
    report = {
        "schemaVersion": 1,
        "source": str(args.source.resolve()),
        "sourceCommit": subprocess.check_output(
            ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
        ).strip(),
        "mode": args.mode,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commands": [],
    }
    failed = False
    clean_env = os.environ.copy()
    for secret in list(clean_env):
        if secret.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
            clean_env.pop(secret, None)
    for command in commands:
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=args.source, env=clean_env, text=True)
            exit_code = result.returncode
            error = None
        except OSError as exc:
            exit_code = 127
            error = str(exc)
        entry = {
            "command": command,
            "exitCode": exit_code,
            "durationSeconds": round(time.monotonic() - started, 3),
        }
        if error:
            entry["error"] = error
        report["commands"].append(entry)
        if exit_code:
            failed = True
            if not args.continue_on_failure:
                break
    report["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["result"] = "failed" if failed else "passed"
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"acceptance {report['result']}; report={args.report}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
