#!/usr/bin/env python3
"""scripts/verify_claim.py — Page-aware claim retrieval for human review.

Given a scientific claim and a PDF manuscript, uses M2 page-aware evidence
indexing to retrieve verbatim candidate passages with page numbers and offsets.
Lexical matches do not establish scientific support or contradiction.

Usage:
    python scripts/verify_claim.py paper.pdf --claim "Mistral 7B uses sliding window attention"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402


def verify(pdf_path: Path, claim: str, max_spans: int = 3) -> dict:
    from pa_cli.evidence import review_claim
    return review_claim(pdf_path, claim, max_spans=max_spans)



def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve PDF passages for human claim review; no automatic support verdict.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 2310_06825.pdf --claim "Mistral 7B uses sliding window attention"
        """,
    )
    parser.add_argument("pdf", help="Path to PDF manuscript")
    parser.add_argument("--claim", required=True, help="Specific claim, finding, or sentence to verify")
    parser.add_argument("--max-spans", type=int, default=3, help="Max evidence passages to consider")
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

    if str(pa_root) not in sys.path:
        sys.path.insert(0, str(pa_root))

    pdf_path = Path(args.pdf).expanduser().resolve()
    if args.output and Path(args.output).expanduser().resolve() == pdf_path:
        print(json.dumps({"error": "output_overwrites_source"}), file=sys.stderr)
        return 2
    from _pa_runtime import delegate_to_runtime
    delegated = delegate_to_runtime(__file__, sys.argv[1:], pa_root)
    if delegated is not None:
        return delegated

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(json.dumps({"error": "file_not_found", "message": f"PDF not found: {pdf_path}"}, indent=2), file=sys.stderr)
        return 2

    try:
        report = verify(pdf_path, args.claim, max_spans=args.max_spans)
        formatted = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(formatted, encoding="utf-8")
        else:
            print(formatted)
        return 0
    except Exception as e:
        print(json.dumps({"error": "verification_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
