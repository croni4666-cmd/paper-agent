#!/usr/bin/env python3
"""scripts/search.py — Wrapper for `pa search` (7 search engines).

Searches academic papers by query across 7 engines (Crossref, OpenAlex,
Semantic Scholar, arXiv, AMiner, CNKI, PubMed). Returns JSON to stdout.

Usage:
    python scripts/search.py "digital finance household consumption" --engine all
    python scripts/search.py "long-term care" --engine pubmed --year-min 2020 --limit 10
    python scripts/search.py "数字普惠金融" --engine aminer --limit 30
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Resolve paper-agent root: SKILL is at .agents/skills/paper-agent/
# so paper-agent root is 3 levels up
SKILL_ROOT = Path(__file__).resolve().parent.parent
PA_ROOT = SKILL_ROOT.parent.parent.parent  # .agents/skills/paper-agent/scripts/search.py → paper-agent/
PYTHON = sys.executable  # Use the current Python interpreter (Codex env)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search 7 academic engines (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "long-term care insurance" --engine all
  %(prog)s "digital finance" --engine aminer --limit 30
  %(prog)s "machine learning" --engine arxiv --year-min 2023
        """,
    )
    parser.add_argument("query", nargs="+", help="Search query (multi-word; join with spaces for AMiner)")
    parser.add_argument(
        "--engine",
        choices=["crossref", "openalex", "semanticscholar", "arxiv", "aminer", "cnki", "pubmed", "all"],
        default="all",
        help="Engine to search (default: all = parallel + dedup)",
    )
    parser.add_argument("--limit", type=int, default=20, help="Max results per engine (default: 20)")
    parser.add_argument("--year-min", type=int, default=None, help="Filter: min publication year")
    parser.add_argument("--year-max", type=int, default=None, help="Filter: max publication year")
    parser.add_argument("--output", choices=["json", "markdown"], default="json", help="Output format (default: json)")
    args = parser.parse_args()

    # Join multi-word query with spaces (AMiner prefers single-string queries)
    query = " ".join(args.query)

    # Build pa search command
    # NOTE: pa search outputs JSON to stdout BY DEFAULT (no --output flag needed).
    # We don't pass --output to pa; we reformat ourselves if user wants markdown.
    cmd = [
        PYTHON, "-m", "pa_cli.cli", "search",
        query,
        "--engine", args.engine,
        "--limit", str(args.limit),
        "--quiet",  # pa search prints progress to stderr; --quiet suppresses
    ]
    if args.year_min is not None:
        cmd.extend(["--year-min", str(args.year_min)])
    if args.year_max is not None:
        cmd.extend(["--year-max", str(args.year_max)])

    try:
        # Run from PA_ROOT so pa_cli is importable
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(PA_ROOT),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "search_timeout",
            "message": f"`pa search` exceeded 180s timeout. Try --engine <single> or --limit 5.",
            "hint": "First call after install may be slow (engine warmup).",
        }), file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(json.dumps({
            "error": "python_not_found",
            "message": str(e),
            "hint": "Ensure paper-agent is installed: pip install -e .",
        }), file=sys.stderr)
        return 3

    # pa search returns JSON to stdout when --output json
    if result.returncode != 0:
        # Try to parse stderr as JSON error
        try:
            err = json.loads(result.stderr)
            print(json.dumps(err), file=sys.stderr)
        except (json.JSONDecodeError, TypeError):
            print(json.dumps({
                "error": "pa_search_failed",
                "exit_code": result.returncode,
                "stderr_tail": result.stderr[-500:] if result.stderr else "",
            }), file=sys.stderr)
        return 1

    # Success: re-emit or convert to markdown
    if args.output == "json":
        print(result.stdout, end="")
        return 0
    else:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(result.stdout, end="")
            return 0
        # Convert to markdown table
        print(format_markdown(data))
        return 0


def format_markdown(data) -> str:
    """Convert pa search JSON results to a markdown table."""
    if not isinstance(data, list):
        data = data.get("results", data.get("papers", []))
    if not data:
        return "_No results._\n"
    lines = [f"# Search Results ({len(data)} papers)\n"]
    lines.append("| # | Year | Title | Authors | Venue | DOI |")
    lines.append("|---|------|-------|---------|-------|-----|")
    for i, p in enumerate(data[:50], 1):
        year = p.get("year", "?")
        title = (p.get("title") or "")[:80].replace("|", "\\|")
        authors_list = p.get("authors", [])
        if isinstance(authors_list, list):
            authors = ", ".join(
                a.get("name", a) if isinstance(a, dict) else str(a)
                for a in authors_list[:3]
            )
            if len(authors_list) > 3:
                authors += " et al."
        else:
            authors = str(authors_list)[:40]
        venue = (p.get("venue") or p.get("journal") or "")[:30].replace("|", "\\|")
        doi = p.get("doi", "")
        lines.append(f"| {i} | {year} | {title} | {authors} | {venue} | {doi} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
