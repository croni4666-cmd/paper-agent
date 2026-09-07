#!/usr/bin/env python3
"""Skill wrapper for paper-agent PDF fetch."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions

PYTHON = sys.executable
PREFERENCES = ["arxiv", "annas", "scihub", "pmc", "pmc-pdf", "unpaywall",
               "biorxiv", "core", "osf", "chemrxiv", "auto"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch one paper PDF by DOI.")
    parser.add_argument("doi")
    parser.add_argument("--prefer", choices=PREFERENCES, default="auto")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--max-total-sec", type=int, default=300)
    args = parser.parse_args()

    root = find_pa_root()
    if not root:
        print(json.dumps({"error": "pa_cli_not_found",
                          "hint": get_install_instructions().strip()}), file=sys.stderr)
        return 4

    command = [PYTHON, "-m", "pa_cli.cli", "fetch", args.doi, "--prefer",
               args.prefer, "--output-dir", args.output_dir, "--max-total-sec",
               str(args.max_total_sec)]
    if args.no_cache:
        command.append("--no-cache")
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=args.max_total_sec + 30, cwd=str(root))
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "fetch_timeout"}), file=sys.stderr)
        return 2
    print(result.stdout, end="")
    if result.returncode and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
