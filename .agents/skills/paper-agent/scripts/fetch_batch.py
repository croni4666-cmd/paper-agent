#!/usr/bin/env python3
"""scripts/fetch_batch.py —Wrapper for `pa fetch-batch` (BibTeX 鈫?PDFs).

Reads a BibTeX file, extracts DOIs, fetches each PDF in sequence.
Writes PDFs to <output-dir>/<sanitized-cite-key>.pdf. Generates a JSON
report with success/failure counts and per-paper details.

Usage:
    python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/
    python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/ --skip-existing --report report.json
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
        description="Batch-fetch PDFs from a BibTeX file (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s refs.bib --output-dir ./pdfs/
  %(prog)s refs.bib --output-dir ./pdfs/ --skip-existing --report report.json
  %(prog)s refs.bib --output-dir ./pdfs/ --clean-xml --report report.json
        """,
    )
    parser.add_argument("bibtex", help="Path to BibTeX file (.bib). Use quotes if path has spaces.")
    parser.add_argument("--output-dir", default="./pdfs", help="Where to save PDFs (default: ./pdfs)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip PDFs already in output-dir")
    parser.add_argument("--max-total-sec", type=int, default=3600, help="Hard cap on total runtime (default: 3600s = 1h)")
    parser.add_argument("--clean-xml", action="store_true",
                        help="[v3.9.27.0] Delete .xml intermediate (JATS-to-PDF) after "
                             "successful PDF generation. Reduces clutter in output-dir.")
    parser.add_argument("--report", help="Optional JSON summary output path")
    parser.add_argument("--summary-json", help="(deprecated) alias for --report")
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


    if not Path(args.bibtex).is_file():
        print(json.dumps({
            "error": "bibtex_not_found",
            "message": f"BibTeX file not found: {args.bibtex}",
        }), file=sys.stderr)
        return 1

    # Ensure output dir exists
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        # v3.9.27.0: use 'pa_cli' (package entry point) instead of 'pa_cli.cli'
        # (internal subpackage). The wrapper at pa_cli/__main__.py imports
        # the same cli.main(). User reported the Skill wrapper was failing
        # with "No such option '--out-dir'" — root cause was that
        # 'pa_cli.cli' was loading a CACHED pa_cli.cli with the OLD
        # 'fetch_batch' function (renamed to 'cnki-guide' in v3.9.26.0),
        # not the new 'fetch-batch' PDF downloader. Using 'pa_cli' (the
        # documented entry point) routes through the fresh editable install.
        PYTHON, "-m", "pa_cli", "fetch-batch",
        args.bibtex,
        "--out-dir", args.output_dir,
        "--max-total-sec", str(args.max_total_sec),
    ]
    if args.skip_existing:
        cmd.append("--skip-existing")
    if args.clean_xml:
        # v3.9.27.0: forward --clean-xml to pa fetch-batch
        cmd.append("--clean-xml")
    if args.report or args.summary_json:
        cmd.extend(["--summary-json", args.report or args.summary_json])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=args.max_total_sec + 60,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "fetch_batch_timeout",
            "message": f"Batch fetch exceeded {args.max_total_sec + 60}s timeout.",
            "hint": "Reduce the BibTeX file size or increase --max-total-sec.",
        }), file=sys.stderr)
        return 2

    # pa fetch-batch writes summary JSON to --summary-json path
    # and progress to stdout/stderr
    summary_path = args.report or args.summary_json
    summary = None
    if summary_path and Path(summary_path).is_file():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if result.returncode == 0:
        print(json.dumps({
            "status": "completed",
            "bibtex": args.bibtex,
            "output_dir": args.output_dir,
            "summary": summary,
            "exit_code": 0,
        }, indent=2))
        return 0

    print(json.dumps({
        "error": "pa_fetch_batch_failed",
        "exit_code": result.returncode,
        "bibtex": args.bibtex,
        "summary": summary,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
