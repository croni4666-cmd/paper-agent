#!/usr/bin/env python3
"""Skill wrapper for paper-agent public search engines."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root, get_install_instructions

PYTHON = find_pa_python()


def main() -> int:
    parser = argparse.ArgumentParser(description="Search public academic engines.")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument(
        "--engine", default="all",
        help="Engine or comma-separated list; default all uses public engines",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum results per engine")
    parser.add_argument("--year-min", type=int, default=None)
    parser.add_argument("--year-max", type=int, default=None)
    parser.add_argument("--output", choices=["json", "markdown"], default="json")
    args = parser.parse_args()

    root = find_pa_root()
    if not root:
        print(json.dumps({"error": "pa_cli_not_found",
                          "hint": get_install_instructions().strip()}), file=sys.stderr)
        return 4

    command = [PYTHON, "-m", "pa_cli.cli", "search", " ".join(args.query),
               "--engine", args.engine, "--limit", str(args.limit), "--quiet"]
    if args.year_min is not None:
        command.extend(["--year-min", str(args.year_min)])
    if args.year_max is not None:
        command.extend(["--year-max", str(args.year_max)])

    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                timeout=180, cwd=str(root))
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "search_timeout"}), file=sys.stderr)
        return 2
    if result.returncode:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    if args.output == "json":
        print(result.stdout, end="")
    else:
        try:
            data = json.loads(result.stdout)
            items = data.get("results", data.get("papers", [])) if isinstance(data, dict) else data
            for item in items:
                print(f"- {item.get('title', '')} ({item.get('year', '')})")
        except json.JSONDecodeError:
            print(result.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
