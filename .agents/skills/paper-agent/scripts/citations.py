#!/usr/bin/env python3
"""scripts/citations.py — Wrapper for `pa citations` (OpenAlex citation walk).

Walks the citation graph for a paper via OpenAlex API (no key required).
Forward = papers THIS paper cites; backward = papers that cite THIS paper.

Usage:
    python scripts/citations.py 10.1038/nature12373 --direction both --limit 50
    python scripts/citations.py 10.1038/nature12373 --direction forward --output forward_cites.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PA_ROOT = SKILL_ROOT.parent.parent.parent
PYTHON = sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Walk citation graph via OpenAlex (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 10.1038/nature12373 --direction both --limit 50
  %(prog)s 10.1038/nature12373 --direction forward --output forward.json
  %(prog)s 10.1038/nature12373 --direction backward --limit 100
        """,
    )
    parser.add_argument("doi", help="Paper DOI (e.g. 10.1038/nature12373)")
    parser.add_argument(
        "--direction",
        choices=["forward", "backward", "both"],
        default="both",
        help="Which direction to walk (default: both)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max papers to return (default: 50)")
    parser.add_argument("--output", help="Optional output file (default: stdout)")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-paper progress")
    args = parser.parse_args()

    cmd = [
        PYTHON, "-m", "pa_cli.cli", "citations",
        args.doi,
        "--direction", args.direction,
        "--limit", str(args.limit),
    ]
    if args.output:
        cmd.extend(["--output", args.output])
    if args.quiet:
        cmd.append("--quiet")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=str(PA_ROOT),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "citations_timeout",
            "message": "`pa citations` exceeded 120s timeout.",
            "hint": "OpenAlex can be slow for high-citation papers; try --limit 20.",
        }), file=sys.stderr)
        return 2

    if result.returncode == 0:
        if args.output:
            # pa writes JSON to --output file
            try:
                with open(args.output, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(json.dumps({
                    "status": "completed",
                    "doi": args.doi,
                    "direction": args.direction,
                    "output_file": args.output,
                    "count": data.get("count", len(data.get("forward", [])) + len(data.get("backward", []))),
                }, indent=2))
            except (json.JSONDecodeError, OSError) as e:
                print(json.dumps({"status": "completed", "output": args.output, "note": str(e)}))
        else:
            # pa prints to stdout
            print(result.stdout, end="")
        return 0

    print(json.dumps({
        "error": "pa_citations_failed",
        "exit_code": result.returncode,
        "doi": args.doi,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
