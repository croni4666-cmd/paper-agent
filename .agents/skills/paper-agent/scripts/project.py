#!/usr/bin/env python3
"""scripts/project.py — Multi-Corpus Project & Topic Management Wrapper ([P2-12]).

Enables AI agents to initialize, inspect, search, merge, and check research topic
corpora with exact BibTeX deduplication and local Zotero synchronization.
Returns structured JSON to stdout.

Usage:
    python scripts/project.py init <slug> --title "Fertility Dynamics"
    python scripts/project.py list
    python scripts/project.py status <slug>
    python scripts/project.py search <slug> "family planning"
    python scripts/project.py merge <target_slug> <source_bib_or_slug>
    python scripts/project.py add <slug> --doi "10.1016/j.jfineco.2023.01.001"
    python scripts/project.py check-zotero <slug>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402


def _ensure_pa_imported():
    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        sys.exit(4)
    if str(pa_root) not in sys.path:
        sys.path.insert(0, str(pa_root))


def cmd_init(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import init_project, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        meta = init_project(args.slug, title=args.title or args.slug, description=args.description or "", root=root)
        print(json.dumps({"status": "created", "project": meta}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "init_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_list(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import list_projects, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        projects = list_projects(root)
        print(json.dumps({"root": str(root), "count": len(projects), "projects": projects}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "list_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_status(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_status, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        status = project_status(args.slug, root)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "status_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_search(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import corpus_search, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        results = corpus_search(args.slug, args.query, root=root)
        print(json.dumps({
            "slug": args.slug,
            "query": args.query,
            "count": len(results),
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "search_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_merge(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import corpus_merge, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        res = corpus_merge(args.target_slug, args.source, root=root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "merge_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_add(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import corpus_add, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    if not args.doi and not args.bibtex:
        print(json.dumps({"error": "missing_arg", "message": "Specify --doi or --bibtex"}, indent=2), file=sys.stderr)
        return 2
    try:
        res = corpus_add(
            args.slug,
            doi=args.doi,
            bibtex_str=args.bibtex,
            title=args.title,
            author=args.author,
            year=args.year,
            root=root,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "add_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_check_zotero(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import corpus_check_zotero, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    db_path = Path(args.zotero_db) if args.zotero_db else None
    try:
        res = corpus_check_zotero(args.slug, root=root, zotero_db=db_path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "check_zotero_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_scan(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import scan_directory_dois
    try:
        res = scan_directory_dois(args.path, recursive=not args.no_recursive)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "scan_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_import_dir(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import import_directory_to_project, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        res = import_directory_to_project(
            args.slug,
            args.path,
            title=args.title,
            root=root,
            recursive=not args.no_recursive,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "import_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_fetch(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_fetch, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        res = project_fetch(
            args.slug,
            root=root,
            skip_existing=not args.no_skip_existing,
            max_total_sec=args.max_total_sec,
            prefer=args.prefer,
            clean_xml=not args.no_clean_xml,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "fetch_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_prisma(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_prisma, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        diagram = project_prisma(
            args.slug,
            root=root,
            word_count_min=args.word_count_min,
            output_format=args.format,
            out_file=args.output,
        )
        if args.json:
            print(json.dumps({"slug": args.slug, "format": args.format, "diagram": diagram}, ensure_ascii=False, indent=2))
        else:
            print(diagram)
        return 0
    except Exception as e:
        print(json.dumps({"error": "prisma_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_review(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_review, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        review_md = project_review(
            args.slug,
            root=root,
            template=args.template,
            word_count_min=args.word_count_min,
            with_prisma=not args.no_prisma,
            out_file=args.output,
        )
        if args.json:
            print(json.dumps({"slug": args.slug, "review": review_md}, ensure_ascii=False, indent=2))
        else:
            print(review_md)
        return 0
    except Exception as e:
        print(json.dumps({"error": "review_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_topics(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_topics, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    c_labels = None
    if args.custom_labels:
        try:
            c_labels = {int(k): str(v) for k, v in json.loads(args.custom_labels).items()}
        except Exception as e:
            print(json.dumps({"error": "invalid_custom_labels", "message": str(e)}, indent=2), file=sys.stderr)
            return 1
    domain_stops = None
    if args.domain_stopwords_file:
        try:
            domain_stops = [line.strip() for line in Path(args.domain_stopwords_file).read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as e:
            print(json.dumps({"error": "read_stopwords_failed", "message": str(e)}, indent=2), file=sys.stderr)
            return 1
    try:
        res = project_topics(
            args.slug,
            root=root,
            alpha=args.alpha,
            word_count_min=args.word_count_min,
            force_method=args.method,
            label_method=args.label_method,
            custom_labels=c_labels,
            domain_stopwords=domain_stops,
            out_file=args.output,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "topics_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_stats(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_stats, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        stats = project_stats(args.slug, root=root, top_n=args.top)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "stats_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_cite_check(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_cite_check, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        summary, report = project_cite_check(args.slug, args.doc, root=root)
        if args.raw:
            print(report)
        else:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.strict and not summary["clean"]:
            return 1
        return 0
    except Exception as e:
        print(json.dumps({"error": "cite_check_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_export(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_export, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        res = project_export(args.slug, format=args.format, out_file=args.output, root=root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "export_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def cmd_enrich(args) -> int:
    _ensure_pa_imported()
    from pa_cli.project import project_enrich, DEFAULT_ROOT
    root = Path(args.root) if args.root else DEFAULT_ROOT
    try:
        res = project_enrich(args.slug, limit=args.limit, force=args.force, root=root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": "enrich_failed", "message": str(e)}, indent=2), file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Multi-Corpus Project & Topic Management Wrapper ([P2-12]).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Create new project topic skeleton")
    p_init.add_argument("slug", help="Project identifier (alphanumeric + _-.)")
    p_init.add_argument("--title", help="Human-readable title")
    p_init.add_argument("--description", help="Description")
    p_init.add_argument("--root", help="Custom projects root directory")

    # list
    p_list = subparsers.add_parser("list", help="List all research projects")
    p_list.add_argument("--root", help="Custom projects root directory")

    # status
    p_status = subparsers.add_parser("status", help="Get project status")
    p_status.add_argument("slug", help="Project identifier")
    p_status.add_argument("--root", help="Custom projects root directory")

    # search
    p_search = subparsers.add_parser("search", help="Search within project refs.bib")
    p_search.add_argument("slug", help="Project identifier")
    p_search.add_argument("query", help="Keywords or phrase")
    p_search.add_argument("--root", help="Custom projects root directory")

    # merge
    p_merge = subparsers.add_parser("merge", help="Merge external BibTeX file or project into target project")
    p_merge.add_argument("target_slug", help="Target project identifier")
    p_merge.add_argument("source", help="Source BibTeX file path or source project slug")
    p_merge.add_argument("--root", help="Custom projects root directory")

    # add
    p_add = subparsers.add_parser("add", help="Add paper DOI or BibTeX entry to project")
    p_add.add_argument("slug", help="Project identifier")
    p_add.add_argument("--doi", help="DOI")
    p_add.add_argument("--title", help="Title")
    p_add.add_argument("--author", help="Author(s)")
    p_add.add_argument("--year", help="Publication year")
    p_add.add_argument("--bibtex", help="BibTeX snippet")
    p_add.add_argument("--root", help="Custom projects root directory")

    # check-zotero
    p_cz = subparsers.add_parser("check-zotero", help="Check project DOIs against local Zotero sqlite")
    p_cz.add_argument("slug", help="Project identifier")
    p_cz.add_argument("--zotero-db", help="Explicit path to zotero.sqlite")
    p_cz.add_argument("--root", help="Custom projects root directory")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan folder for academic DOIs across markdown/text/bib files")
    p_scan.add_argument("path", help="Folder or file path to scan")
    p_scan.add_argument("--no-recursive", action="store_true", help="Do not scan subdirectories")

    # import-dir
    p_imp = subparsers.add_parser("import-dir", help="Scan folder and import discovered DOIs into project refs.bib")
    p_imp.add_argument("slug", help="Project identifier")
    p_imp.add_argument("path", help="Folder path to scan and import")
    p_imp.add_argument("--title", help="Human-readable title")
    p_imp.add_argument("--no-recursive", action="store_true", help="Do not scan subdirectories")
    p_imp.add_argument("--root", help="Custom projects root directory")

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Batch download PDFs for papers in a project")
    p_fetch.add_argument("slug", help="Project identifier")
    p_fetch.add_argument("--no-skip-existing", action="store_true", help="Re-fetch even if PDF already exists")
    p_fetch.add_argument("--max-total-sec", type=int, default=1800, help="Max total seconds for batch fetch")
    p_fetch.add_argument("--prefer", default="auto", help="Fetch channel preference")
    p_fetch.add_argument("--no-clean-xml", action="store_true", help="Keep temporary XML files")
    p_fetch.add_argument("--root", help="Custom projects root directory")

    # prisma
    p_prisma = subparsers.add_parser("prisma", help="Generate PRISMA 2020 flow diagram for a project topic")
    p_prisma.add_argument("slug", help="Project identifier")
    p_prisma.add_argument("--format", default="markdown", choices=["markdown", "mermaid"], help="Output format")
    p_prisma.add_argument("--word-count-min", type=int, default=1000, help="Min word count for full-text classification")
    p_prisma.add_argument("-o", "--output", help="Write diagram to output file")
    p_prisma.add_argument("--json", action="store_true", help="Output result as JSON object")
    p_prisma.add_argument("--root", help="Custom projects root directory")

    # review
    p_review = subparsers.add_parser("review", help="Generate structured literature review for a project topic")
    p_review.add_argument("slug", help="Project identifier")
    p_review.add_argument("--template", default="v32", help="Review template version")
    p_review.add_argument("--word-count-min", type=int, default=1000, help="Min word count for full-text classification")
    p_review.add_argument("--no-prisma", action="store_true", help="Exclude PRISMA diagram from review")
    p_review.add_argument("-o", "--output", help="Write review to output file")
    p_review.add_argument("--json", action="store_true", help="Output result as JSON object")
    p_review.add_argument("--root", help="Custom projects root directory")

    # topics
    p_topics = subparsers.add_parser("topics", help="Cluster papers in a project topic into sub-topics")
    p_topics.add_argument("slug", help="Project identifier")
    p_topics.add_argument("-o", "--output", help="Write topics.json to output file")
    p_topics.add_argument("--alpha", type=float, default=0.4, help="Concept-Jaccard vs TF-IDF cosine weight")
    p_topics.add_argument("--word-count-min", type=int, default=1000, help="Min word count for full-text classification")
    p_topics.add_argument("--method", default="auto", choices=["auto", "bertopic", "handroll"], help="Clustering method")
    p_topics.add_argument("--label-method", default="auto", choices=["auto", "ctfidf", "handroll", "custom"], help="Label generator")
    p_topics.add_argument("--custom-labels", help="JSON dict {topic_id: label_str} to override auto labels")
    p_topics.add_argument("--domain-stopwords-file", help="File with domain-specific stopwords")
    p_topics.add_argument("--root", help="Custom projects root directory")

    # stats
    p_stats = subparsers.add_parser("stats", help="Get aggregate bibliometric stats for a project")
    p_stats.add_argument("slug", help="Project identifier")
    p_stats.add_argument("--top", type=int, default=10, help="Number of top authors and venues to show")
    p_stats.add_argument("--root", help="Custom projects root directory")

    # cite-check
    p_cc = subparsers.add_parser("cite-check", help="Check document [@bibkey] placeholders against project refs.bib")
    p_cc.add_argument("slug", help="Project identifier")
    p_cc.add_argument("doc", help="Markdown document path")
    p_cc.add_argument("--strict", action="store_true", help="Exit 1 if any missing placeholders")
    p_cc.add_argument("--raw", action="store_true", help="Print human-readable report instead of JSON")
    p_cc.add_argument("--root", help="Custom projects root directory")

    # export
    p_exp = subparsers.add_parser("export", help="Export project corpus to Markdown digest, BibTeX, or JSON")
    p_exp.add_argument("slug", help="Project identifier")
    p_exp.add_argument("--format", default="markdown", choices=["markdown", "bibtex", "json"], help="Export format")
    p_exp.add_argument("-o", "--output", help="Write export to destination file")
    p_exp.add_argument("--root", help="Custom projects root directory")

    # enrich
    p_enr = subparsers.add_parser("enrich", help="Enrich stub project references with rich metadata (title, author, venue, abstract)")
    p_enr.add_argument("slug", help="Project identifier")
    p_enr.add_argument("--limit", type=int, default=0, help="Max stub papers to enrich (0 = all)")
    p_enr.add_argument("--force", action="store_true", help="Force re-enrichment of all papers with DOIs")
    p_enr.add_argument("--root", help="Custom projects root directory")

    args = parser.parse_args()

    handlers = {
        "init": cmd_init,
        "list": cmd_list,
        "status": cmd_status,
        "search": cmd_search,
        "merge": cmd_merge,
        "add": cmd_add,
        "check-zotero": cmd_check_zotero,
        "scan": cmd_scan,
        "import-dir": cmd_import_dir,
        "fetch": cmd_fetch,
        "prisma": cmd_prisma,
        "review": cmd_review,
        "topics": cmd_topics,
        "stats": cmd_stats,
        "cite-check": cmd_cite_check,
        "export": cmd_export,
        "enrich": cmd_enrich,
    }
    return handlers[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
