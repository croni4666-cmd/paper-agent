#!/usr/bin/env python3
"""scripts/cache.py —Wrapper for `pa cache` (cache management).

Manages the local paper PDF + metadata cache at ~/.paper-agent/cache/.
Supports stats, list, clean (with age threshold), and clear.

Usage:
    python scripts/cache.py stats
    python scripts/cache.py list --limit 20
    python scripts/cache.py clean --older-than-days 90
    python scripts/cache.py clear --confirm
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
        description="Manage local paper cache (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats
  %(prog)s list --limit 20
  %(prog)s clean --older-than-days 90
  %(prog)s clear --confirm
        """,
    )
    parser.add_argument(
        "command",
        choices=["stats", "list", "clean", "clear"],
        help="Cache subcommand",
    )
    parser.add_argument("--older-than-days", type=int, help="(clean) Delete entries older than N days")
    parser.add_argument("--limit", type=int, help="(list) Max entries to show")
    parser.add_argument("--confirm", action="store_true", help="(clear) Skip confirmation prompt")
    parser.add_argument("--as-json", action="store_true", default=True, help="Output as JSON (default)")
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


    cmd = [PYTHON, "-m", "pa_cli.cli", "cache", args.command]
    if args.older_than_days is not None:
        cmd.extend(["--older-than-days", str(args.older_than_days)])
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.confirm:
        cmd.append("--confirm")
    if args.as_json:
        cmd.append("--json")  # pa uses --json, not --as-json

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "cache_timeout",
            "message": "`pa cache` exceeded 60s timeout.",
        }), file=sys.stderr)
        return 2

    if result.returncode == 0:
        print(result.stdout, end="")
        return 0

    print(json.dumps({
        "error": "pa_cache_failed",
        "exit_code": result.returncode,
        "command": args.command,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
