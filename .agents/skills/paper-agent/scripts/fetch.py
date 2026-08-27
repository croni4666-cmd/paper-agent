#!/usr/bin/env python3
"""scripts/fetch.py 鈥?Wrapper for `pa fetch` (14 PDF fetch channels).

Fetches a single paper PDF by DOI using the cascade of 14 channels:
pmc 鈫?s2 鈫?biorxiv 鈫?core 鈫?osf 鈫?chemrxiv 鈫?arxiv 鈫?openalex 鈫?unpaywall 鈫?doi_redirect 鈫?scihub 鈫?playwright. Returns JSON to stdout.

Usage:
    python scripts/fetch.py 10.1038/nature12373 --prefer pmc-pdf
    python scripts/fetch.py 10.1371/journal.pone.0000001 --prefer s2
    python scripts/fetch.py 10.1101/2023.12.30.573731 --prefer biorxiv
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
        description="Fetch a single paper PDF by DOI (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 10.1038/nature12373 --prefer pmc-pdf   # Force JATS鈫扨DF render
  %(prog)s 10.1371/journal.pone.0000001            # Auto-cascade (default)
  %(prog)s 10.1101/2023.12.30.573731 --output-dir ./pdfs/
        """,
    )
    parser.add_argument("doi", help="Paper DOI (e.g. 10.1038/nature12373). DOIs usually don't contain spaces.")
    parser.add_argument(
        "--prefer",
        choices=["arxiv", "pmc", "pmc-pdf", "unpaywall", "s2", "biorxiv", "core", "osf",
                 "chemrxiv", "annas", "cnki", "scihub", "auto"],
        default="auto",
        help="Channel to try first (default: auto = cascade)",
    )
    parser.add_argument("--output-dir", default=".", help="Where to save PDF (default: .)")
    parser.add_argument("--no-cache", action="store_true", help="Skip cache lookup")
    parser.add_argument("--max-total-sec", type=int, default=300, help="Hard cap on total runtime (default: 300s)")
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

    cmd = [
        PYTHON, "-m", "pa_cli.cli", "fetch",
        args.doi,
        "--prefer", args.prefer,
        "--output-dir", args.output_dir,
        "--max-total-sec", str(args.max_total_sec),
    ]
    if args.no_cache:
        cmd.append("--no-cache")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=args.max_total_sec + 30,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "fetch_timeout",
            "message": f"`pa fetch` exceeded {args.max_total_sec + 30}s timeout.",
            "hint": "Try a specific --prefer channel or reduce --max-total-sec.",
        }), file=sys.stderr)
        return 2

    # pa fetch returns JSON to stdout with saved_as/via_channel/size_bytes/etc.
    if result.returncode == 0:
        print(result.stdout, end="")
        return 0

    # Failure: try to parse the stderr/stdout for the error JSON
    out = result.stdout.strip()
    if out:
        try:
            data = json.loads(out)
            if data.get("error"):
                print(json.dumps(data), file=sys.stderr)
                return 1
        except json.JSONDecodeError:
            pass

    # Generic failure
    print(json.dumps({
        "error": "pa_fetch_failed",
        "exit_code": result.returncode,
        "doi": args.doi,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
