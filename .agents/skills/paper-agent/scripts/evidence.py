#!/usr/bin/env python3
"""scripts/evidence.py — Page-aware PDF evidence extractor (M2 evidence packet wrapper).

Extracts verbatim, page-aware evidence passages from academic PDFs with exact
Unicode character offsets, section heuristics (methods/results/etc.), and OCR status.
Returns JSON to stdout.

Usage:
    python scripts/evidence.py paper.pdf --query "sample size"
    python scripts/evidence.py paper.pdf --section methods --max-spans 3
    python scripts/evidence.py paper.pdf --index-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract verbatim page-aware evidence passages from academic PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s paper.pdf --query "randomized controlled trial"
  %(prog)s paper.pdf --section methods --max-spans 4
  %(prog)s paper.pdf --index-only
        """,
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--query", default=None, help="Lexical query to find relevant spans")
    parser.add_argument(
        "--section",
        action="append",
        dest="sections",
        default=[],
        help="Required/preferred sections (e.g. methods, results, limitations, abstract). Repeatable.",
    )
    parser.add_argument("--max-spans", type=int, default=5, help="Maximum number of evidence spans to return (default: 5)")
    parser.add_argument("--max-bytes", type=int, default=16000, help="Max packet UTF-8 byte budget (default: 16000)")
    parser.add_argument("--index-only", action="store_true", help="Return full PDF index without filtering by query")
    parser.add_argument("--output", help="Optional output JSON file (default: stdout)")
    args = parser.parse_args()

    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        return 4

    # Ensure pa_cli is importable
    if str(pa_root) not in sys.path:
        sys.path.insert(0, str(pa_root))

    try:
        from pa_cli.evidence import build_index, build_packet
    except ImportError as e:
        print(json.dumps({
            "error": "import_failed",
            "message": f"Could not import pa_cli.evidence: {e}",
            "hint": "Check PyMuPDF installation: pip install PyMuPDF==1.28.2",
        }, indent=2), file=sys.stderr)
        return 1

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(json.dumps({
            "error": "file_not_found",
            "message": f"PDF file not found: {pdf_path}",
        }, indent=2), file=sys.stderr)
        return 2

    try:
        index = build_index(pdf_path)
    except Exception as e:
        print(json.dumps({
            "error": "index_failed",
            "message": str(e),
        }, indent=2), file=sys.stderr)
        return 3

    if args.index_only:
        result = {
            "schema_version": index.get("schema_version"),
            "artifact_sha256": index.get("artifact_sha256"),
            "index_hash": index.get("index_hash"),
            "extractor": index.get("extractor"),
            "total_pages": len(index.get("pages", [])),
            "total_spans": len(index.get("spans", [])),
            "ocr_status": index.get("ocr_status"),
            "pages_summary": [
                {"page": p["page"], "status": p["status"], "char_count": len(p.get("text", ""))}
                for p in index.get("pages", [])
            ],
        }
    else:
        query = args.query or (args.sections[0] if args.sections else "study")
        try:
            packet = build_packet(
                index,
                query,
                max_bytes=args.max_bytes,
                max_spans=args.max_spans,
                required_sections=tuple(args.sections),
            )
            result = packet
        except Exception as e:
            print(json.dumps({
                "error": "packet_failed",
                "message": str(e),
            }, indent=2), file=sys.stderr)
            return 3

    formatted = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(formatted, encoding="utf-8")
    else:
        print(formatted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
