#!/usr/bin/env python3
"""scripts/zotero.py — Zotero Local & Cloud Integration Wrapper.

Enables AI agents to check if papers already exist in the user's Zotero library,
search the Zotero library, and push BibTeX/PDFs into Zotero collections.
Returns JSON to stdout.

Usage:
    python scripts/zotero.py check --corpus refs.bib
    python scripts/zotero.py check --doi 10.1038/nature12373
    python scripts/zotero.py search "digital finance"
    python scripts/zotero.py push refs.bib [--pdf-dir ./pdfs/]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402


def cmd_check(args, pa_root: Path) -> int:
    try:
        from pa_cli.zotero_local import check_corpus, find_zotero_db, get_library_dois
    except ImportError as e:
        print(json.dumps({"error": "import_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1

    db_path = Path(args.zotero_db) if args.zotero_db else find_zotero_db()
    if not db_path:
        print(json.dumps({
            "error": "zotero_db_not_found",
            "message": "Local zotero.sqlite not found. Please provide --zotero-db <path>",
        }, indent=2), file=sys.stderr)
        return 2

    dois_to_check = []
    if args.doi:
        dois_to_check.extend(args.doi)
    if args.corpus:
        corpus_path = Path(args.corpus).expanduser().resolve()
        if not corpus_path.is_file():
            print(json.dumps({"error": "file_not_found", "message": f"Corpus not found: {corpus_path}"}, indent=2), file=sys.stderr)
            return 2
        from pa_cli.zotero_local import extract_dois_from_bibtex
        dois_to_check.extend(extract_dois_from_bibtex(corpus_path))

    if not dois_to_check:
        print(json.dumps({"error": "no_dois_provided", "message": "Specify --doi <doi> or --corpus <refs.bib>"}, indent=2), file=sys.stderr)
        return 3

    lib_dois = get_library_dois(db_path)
    result = check_corpus(dois_to_check, lib_dois)
    result["db_path"] = str(db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_search(args, pa_root: Path) -> int:
    try:
        from pa_cli.zotero_api import get_client, search_library
    except ImportError as e:
        print(json.dumps({"error": "pyzotero_missing", "message": "pyzotero not installed or import error", "hint": "pip install pyzotero"}, indent=2), file=sys.stderr)
        return 1

    try:
        client = get_client()
        items = search_library(client, query=args.query, limit=args.limit)
        print(json.dumps({"query": args.query, "count": len(items), "items": items}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "search_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_push(args, pa_root: Path) -> int:
    try:
        from pa_cli.zotero_api import get_client, push_bibtex_to_zotero
    except ImportError as e:
        print(json.dumps({"error": "pyzotero_missing", "message": "pyzotero not installed or import error", "hint": "pip install pyzotero"}, indent=2), file=sys.stderr)
        return 1

    corpus_path = Path(args.corpus).expanduser().resolve()
    if not corpus_path.is_file():
        print(json.dumps({"error": "file_not_found", "message": f"Corpus file not found: {corpus_path}"}, indent=2), file=sys.stderr)
        return 2

    pdf_dir = Path(args.pdf_dir).expanduser().resolve() if args.pdf_dir else None
    try:
        client = get_client()
        result = push_bibtex_to_zotero(
            client=client,
            bibtex_path=corpus_path,
            pdf_dir=pdf_dir,
            collection_name=args.collection,
            skip_existing=not args.no_skip_existing,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "push_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zotero local & cloud workflow integration for paper-agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Check
    p_check = subparsers.add_parser("check", help="Check DOIs against local Zotero SQLite library (read-only, no API key)")
    p_check.add_argument("--corpus", help="Path to BibTeX file")
    p_check.add_argument("--doi", action="append", help="One or more DOIs (repeatable)")
    p_check.add_argument("--zotero-db", help="Explicit path to zotero.sqlite")

    # Search
    p_search = subparsers.add_parser("search", help="Search Zotero cloud library via API")
    p_search.add_argument("query", help="Search terms")
    p_search.add_argument("--limit", type=int, default=20, help="Max items to return")

    # Push
    p_push = subparsers.add_parser("push", help="Push BibTeX entries and PDFs to Zotero")
    p_push.add_argument("corpus", help="Path to BibTeX file")
    p_push.add_argument("--pdf-dir", help="Directory containing downloaded PDFs")
    p_push.add_argument("--collection", help="Name of Zotero collection")
    p_push.add_argument("--no-skip-existing", action="store_true", help="Re-push even if DOI already exists in Zotero")

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

    if args.subcommand == "check":
        return cmd_check(args, pa_root)
    elif args.subcommand == "search":
        return cmd_search(args, pa_root)
    elif args.subcommand == "push":
        return cmd_push(args, pa_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
