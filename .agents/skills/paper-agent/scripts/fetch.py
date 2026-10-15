#!/usr/bin/env python3
"""scripts/fetch.py —Wrapper for `pa fetch` (14 PDF fetch channels).

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
from _pa_runtime import run_pa, emit_result, json_object, validate_pdf  # noqa: E402


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
    args.output_dir = str(Path(args.output_dir).expanduser().resolve())

    # Find paper-agent root
    pa_root = find_pa_root()
    if not pa_root:
        return emit_result({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, 'failed', 4)

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
        result = run_pa(
            cmd, timeout=args.max_total_sec + 30,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        return emit_result({
            "error": "fetch_timeout",
            "message": f"`pa fetch` exceeded {args.max_total_sec + 30}s timeout.",
            "hint": "Try a specific --prefer channel or reduce --max-total-sec.",
        }, 'failed', 2)
    except OSError as exc:
        return emit_result({'error': 'runtime_error', 'message': str(exc)}, 'failed', 3)

    if result.returncode != 0:
        return emit_result({'error': 'pa_fetch_failed', 'doi': args.doi,
                            'cli_exit_code': result.returncode,
                            'stderr_tail': result.stderr[-500:]}, 'failed', 1)
    try:
        data = json_object(result.stdout)
        if data.get('error') or data.get('success') is False:
            return emit_result(data, 'failed', 1)
        path, size = validate_pdf(data.get('saved_as') or data.get('path')
                                  or data.get('out_path'), Path(pa_root))
    except (ValueError, OSError) as exc:
        return emit_result({'error': 'invalid_download', 'doi': args.doi,
                            'message': str(exc)}, 'failed', 1)
    data.update(saved_as=str(path), size_bytes=size, validation='signature_and_eof')
    return emit_result(data, 'success')


if __name__ == "__main__":
    sys.exit(main())
