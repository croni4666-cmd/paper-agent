#!/usr/bin/env python3
"""scripts/keys.py —Wrapper for `pa keys` (API key management).

Manages API keys for academic databases. Reads from .env and
~/.paper-agent/keys.json. Never logs the actual key value (only
the last 4 chars).

Usage:
    python scripts/keys.py list
    python scripts/keys.py check semanticscholar
    python scripts/keys.py audit
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage API keys (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                 # Show all keys + status
  %(prog)s check semanticscholar # Live-probe a single service
  %(prog)s audit                # Show expiry warnings
        """,
    )
    parser.add_argument(
        "command",
        choices=["list", "check", "audit"],
        help="Subcommand to run",
    )
    parser.add_argument("service_id", nargs="?", help="Service ID (only for 'check')")
    parser.add_argument("--as-json", action="store_true", help="Output as JSON (default)")
    args = parser.parse_args()

    # Find paper-agent root
    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        return 4


    if args.command == "check" and not args.service_id:
        parser.error("'check' requires a SERVICE_ID argument")

    cmd = [PYTHON, "-m", "pa_cli.cli", "keys", args.command]
    if args.service_id:
        cmd.append(args.service_id)
    cmd.append("--json")  # pa uses --json, not --as-json

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "keys_timeout",
            "message": "`pa keys` exceeded 30s timeout.",
        }), file=sys.stderr)
        return 2

    if result.returncode == 0:
        print(result.stdout, end="")
        return 0

    # pa keys returns error JSON on failure (e.g. unknown service)
    if result.stdout:
        try:
            err = json.loads(result.stdout)
            print(json.dumps(err), file=sys.stderr)
            return 1
        except json.JSONDecodeError:
            pass

    print(json.dumps({
        "error": "pa_keys_failed",
        "exit_code": result.returncode,
        "command": args.command,
        "service_id": args.service_id,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
