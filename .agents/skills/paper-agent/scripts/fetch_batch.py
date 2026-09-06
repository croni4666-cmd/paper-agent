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
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402
from _pa_runtime import run_pa, emit_result, json_object, validate_batch  # noqa: E402


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

    args.bibtex = str(Path(args.bibtex).expanduser().resolve())
    args.output_dir = str(Path(args.output_dir).expanduser().resolve())
    report = args.report or args.summary_json
    report = Path(report).expanduser().resolve() if report else None
    pa_root = find_pa_root()
    if not pa_root:
        return emit_result({'error': 'pa_cli_not_found',
                            'hint': get_install_instructions().strip()}, 'failed', 4)
    if not Path(args.bibtex).is_file():
        return emit_result({'error': 'bibtex_not_found', 'bibtex': args.bibtex}, 'failed', 1)

    payload = {'bibtex': args.bibtex, 'output_dir': args.output_dir}
    try:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        # A fresh report is required even when the user does not request one.
        # Never read an old user report as evidence for this run.
        with tempfile.TemporaryDirectory(prefix='paper-agent-report-') as temporary:
            summary_path = Path(temporary) / 'summary.json'
            cmd = [PYTHON, '-m', 'pa_cli', 'fetch-batch', args.bibtex,
                   '--out-dir', args.output_dir, '--max-total-sec', str(args.max_total_sec),
                   '--summary-json', str(summary_path)]
            if args.skip_existing:
                cmd.append('--skip-existing')
            if args.clean_xml:
                cmd.append('--clean-xml')
            result = run_pa(cmd, cwd=str(pa_root), timeout=args.max_total_sec + 60)
            summary, status = validate_batch(
                json_object(summary_path.read_text(encoding='utf-8-sig')), Path(pa_root))
        if result.returncode != 0:
            status = 'partial' if any(r['success'] for r in summary['results']) else 'failed'
        payload.update(summary=summary, cli_exit_code=result.returncode)
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        if status != 'success':
            payload['error'] = 'pa_fetch_batch_incomplete'
        return emit_result(payload, status, 0 if status == 'success' else 1)
    except subprocess.TimeoutExpired:
        return emit_result(dict(payload, error='fetch_batch_timeout'), 'failed', 2)
    except (OSError, ValueError) as exc:
        return emit_result(dict(payload, error='batch_result_error', message=str(exc)), 'failed', 1)


if __name__ == "__main__":
    sys.exit(main())
