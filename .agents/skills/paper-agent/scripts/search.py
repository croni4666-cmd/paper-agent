#!/usr/bin/env python3
"""scripts/search.py — Wrapper for `pa search` (8 search engines).

Searches academic papers by query across 8 engines (Crossref, OpenAlex,
Semantic Scholar, arXiv, AMiner, CNKI, PubMed, ClinicalTrials).
Returns JSON to stdout.

v3.9.24.0: documented MeSH field syntax support via PubMed ESearch
(quoted terms, [MeSH Terms], [Title/Abstract], boolean operators).

Usage:
    python scripts/search.py "digital finance household consumption" --engine all
    python scripts/search.py "long-term care" --engine pubmed --year-min 2020 --limit 10
    python scripts/search.py "数字普惠金融 家庭消费" --engine aminer --limit 30
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402
from _pa_runtime import run_pa  # noqa: E402

PYTHON = sys.executable  # Used as a placeholder; _pa_runtime selects the child interpreter.


STRATEGIES = {
    "broad": ("all", "cite"),
    "fast": ("openalex,crossref", "relevance"),
    "biomedical": ("pubmed,openalex", "relevance"),
    "preprints": ("arxiv,semanticscholar", "relevance"),
    "chinese": ("aminer,cnki,openalex", "relevance"),
}


def summarize_quality(results):
    """Describe result completeness without changing ranking or filtering."""
    flags = {}
    multi_source = 0
    for paper in results:
        flag = paper.get("quality_flag", "unclassified")
        flags[flag] = flags.get(flag, 0) + 1
        if len(paper.get("found_by") or []) > 1:
            multi_source += 1
    return {"total": len(results), "by_flag": dict(sorted(flags.items())),
            "multi_source": multi_source}


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
    parser.add_argument("--strategy", choices=sorted(STRATEGIES),
                        help="Choose a source set: broad, fast, biomedical, preprints, or chinese")
    parser.add_argument("--sort-by", choices=["cite", "year", "relevance"],
                        help="Override the strategy's ranking; default stays cite-ranked")
    parser.add_argument("--source",
                        help="Keep only results found by these sources after deduplication (comma-separated)")
    parser.add_argument("--quality-mode", choices=["flag", "filter", "off"], default="flag",
                        help="Quality labels from paper-agent: flag (default), filter, or off")
    parser.add_argument("--limit", type=int, default=20, help="Max results per engine (default: 20)")
    parser.add_argument("--year-min", type=int, default=None, help="Filter: min publication year")
    parser.add_argument("--year-max", type=int, default=None, help="Filter: max publication year")
    parser.add_argument("--output", choices=["json", "markdown"], default="json", help="Output format (default: json)")
    args = parser.parse_args()
    if args.strategy and args.engine != "all":
        parser.error("--strategy cannot be combined with an explicit non-all --engine")

    engine = args.engine
    sort_by = args.sort_by
    if args.strategy:
        engine, strategy_sort = STRATEGIES[args.strategy]
        sort_by = sort_by or strategy_sort

    # Find paper-agent root (pa_cli must be importable)
    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
            "skill_help": "See SKILL.md 'Installation' section, or run scripts/bootstrap.py",
        }, indent=2), file=sys.stderr)
        return 4

    # Join multi-word query with spaces (AMiner prefers single-string queries)
    query = " ".join(args.query)

    # Build pa search command
    # NOTE: pa search outputs JSON to stdout BY DEFAULT (no --output flag needed).
    # We don't pass --output to pa; we reformat ourselves if user wants markdown.
    cmd = [
        PYTHON, "-m", "pa_cli.cli", "search",
        query,
        "--engine", engine,
        "--limit", str(args.limit),
        "--quality-mode", args.quality_mode,
        "--quiet",  # pa search prints progress to stderr; --quiet suppresses
    ]
    if sort_by:
        cmd.extend(["--sort-by", sort_by])
    if args.source:
        cmd.extend(["--source", args.source])
    if args.year_min is not None:
        cmd.extend(["--year-min", str(args.year_min)])
    if args.year_max is not None:
        cmd.extend(["--year-max", str(args.year_max)])

    try:
        # Run from pa_root so pa_cli is importable
        result = run_pa(
            cmd,
            timeout=180,
            cwd=str(pa_root),
        )
    except OSError as exc:
        print(json.dumps({'status': 'failed', 'error': 'runtime_error', 'message': str(exc)}), file=sys.stderr)
        return 3
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "search_timeout",
            "message": f"`pa search` exceeded 180s timeout. Try --engine <single> or --limit 5.",
            "hint": "First call after install may be slow (engine warmup).",
        }), file=sys.stderr)
        return 2

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

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(json.dumps({"error": "invalid_search_response",
                          "message": "paper-agent returned non-JSON search output"}), file=sys.stderr)
        return 1
    results = data.get("results", []) if isinstance(data, dict) else data
    if not isinstance(results, list):
        print(json.dumps({"error": "invalid_search_response",
                          "message": "paper-agent search results are not a list"}), file=sys.stderr)
        return 1
    if isinstance(data, list):
        data = {"results": data}
    data["quality_summary"] = summarize_quality(results)
    if args.strategy:
        data["strategy"] = args.strategy
        data["strategy_engine"] = engine
    if args.output == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
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
