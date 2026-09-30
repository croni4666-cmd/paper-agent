#!/usr/bin/env python3
"""scripts/provenance.py — Provenance & Rights Checker (M1B wrapper).

Inspects artifact licensing, DOI/title metadata verification, and CC-BY/CC0
eligibility to ensure legal/research compliance before any data leaves the local machine.
Returns JSON to stdout.

Usage:
    python scripts/provenance.py paper.pdf --doi 10.1038/nature12373
    python scripts/provenance.py paper.pdf --doi 10.1038/nature12373 --title "Expected Title"
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
        description="Verify artifact provenance, metadata identity, and open-access licensing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s paper.pdf --doi 10.1038/nature12373
  %(prog)s paper.pdf --doi 10.1371/journal.pone.0000001 --data-class public
        """,
    )
    parser.add_argument("artifact", help="Path to PDF or JATS XML file")
    parser.add_argument("--doi", default="", help="Expected paper DOI")
    parser.add_argument("--title", default=None, help="Expected paper title")
    parser.add_argument("--source", default="", help="Download source / channel name")
    parser.add_argument("--url", default="", help="Download source URL")
    parser.add_argument(
        "--data-class",
        choices=["unknown", "public", "private", "confidential"],
        default="unknown",
        help="Explicit user data classification (default: unknown = strictly local)",
    )
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

    try:
        from pa_cli.provenance import inspect_artifact
    except ImportError as e:
        print(json.dumps({
            "error": "import_failed",
            "message": f"Could not import pa_cli.provenance: {e}",
        }, indent=2), file=sys.stderr)
        return 1

    path = Path(args.artifact).expanduser().resolve()
    if not path.is_file():
        print(json.dumps({
            "error": "file_not_found",
            "message": f"Artifact not found: {path}",
        }, indent=2), file=sys.stderr)
        return 2

    try:
        result = inspect_artifact(
            path,
            requested_doi=args.doi,
            source=args.source,
            url=args.url,
            expected_title=args.title,
            data_class=args.data_class,
        )
    except Exception as e:
        print(json.dumps({
            "error": "inspection_failed",
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
