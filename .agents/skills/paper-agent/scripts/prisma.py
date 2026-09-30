#!/usr/bin/env python3
"""scripts/prisma.py — PRISMA 2020 Flow Diagram Generator.

Generates PRISMA 2020 4-stage systematic review flowcharts (Identification, Screening,
Eligibility, Included) in Mermaid or Markdown format.

Usage:
    python scripts/prisma.py --identified 120 --screened 45 --included 18 --format mermaid
    python scripts/prisma.py --corpus ./pdfs/ --format markdown --output prisma_report.md
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
        description="Generate PRISMA 2020 flow diagrams for literature reviews.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --identified 150 --screened 80 --eligible 30 --included 15 --format mermaid
  %(prog)s --corpus ./pdfs/ --format markdown
        """,
    )
    parser.add_argument("--corpus", help="Optional corpus directory of PDFs to auto-derive counts")
    parser.add_argument("--identified", type=int, default=0, help="Total records identified from search")
    parser.add_argument("--screened", type=int, default=0, help="Records screened after deduplication")
    parser.add_argument("--eligible", type=int, default=0, help="Full-text reports assessed for eligibility")
    parser.add_argument("--included", type=int, default=0, help="Studies included in review")
    parser.add_argument("--pdf-count", type=int, default=0, help="Included studies with full PDF")
    parser.add_argument("--abstract-count", type=int, default=0, help="Included studies with abstract-only")
    parser.add_argument(
        "--format",
        choices=["mermaid", "markdown", "json"],
        default="mermaid",
        help="Output format: mermaid (default), markdown, or json",
    )
    parser.add_argument("--output", help="Optional file to save output")
    args = parser.parse_args()

    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        return 4

    if str(pa_root) not in sys.path:
        sys.path.insert(0, str(pa_root))

    try:
        from pa_cli.prisma import derive_counts_from_corpus, generate_mermaid, generate_markdown
    except ImportError as e:
        print(json.dumps({
            "error": "import_failed",
            "message": f"Could not import pa_cli.prisma: {e}",
        }, indent=2), file=sys.stderr)
        return 1

    identified = args.identified
    screened = args.screened
    eligible = args.eligible
    included = args.included
    pdf_count = args.pdf_count
    abstract_count = args.abstract_count

    if args.corpus:
        corpus_path = Path(args.corpus).expanduser().resolve()
        if not corpus_path.is_dir():
            print(json.dumps({
                "error": "directory_not_found",
                "message": f"Corpus directory not found: {corpus_path}",
            }, indent=2), file=sys.stderr)
            return 2
        counts = derive_counts_from_corpus(corpus_path, word_count_min=1000)
        identified = counts["identified"]
        screened = counts["after_screening"]
        eligible = counts["after_eligibility"]
        included = counts["included"]
        pdf_count = counts["pdf_count"]
        abstract_count = counts["abstract_count"]

    if eligible == 0 and screened > 0:
        eligible = screened
    if included == 0 and eligible > 0:
        included = eligible

    if args.format == "json":
        res = json.dumps({
            "identified": identified,
            "screened": screened,
            "eligible": eligible,
            "included": included,
            "pdf_count": pdf_count,
            "abstract_count": abstract_count,
        }, indent=2)
    elif args.format == "markdown":
        res = generate_markdown(
            identified_count=identified,
            after_screening_count=screened,
            after_eligibility_count=eligible,
            included_count=included,
            pdf_count=pdf_count,
            abstract_count=abstract_count,
        )
    else:
        res = generate_mermaid(
            identified_count=identified,
            after_screening_count=screened,
            after_eligibility_count=eligible,
            included_count=included,
            pdf_count=pdf_count,
            abstract_count=abstract_count,
        )

    if args.output:
        Path(args.output).write_text(res, encoding="utf-8")
        print(f"PRISMA output written to {args.output}")
    else:
        print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
