#!/usr/bin/env python3
"""scripts/review.py —Wrapper for `pa review` (lit review synthesis).

Synthesizes a Markdown literature review from a corpus (PDF directory
or BibTeX file). Supports topic-focused synthesis and topic clustering.

Usage:
    python scripts/review.py ./pdfs/ --output lit_review.md
    python scripts/review.py refs.bib --output lit_review.md --topic "long-term care"
    python scripts/review.py ./pdfs/ --topics --top-k-clusters 5
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
        description="Synthesize lit review from corpus (paper-agent wrapper).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./pdfs/ --output lit_review.md
  %(prog)s refs.bib --output lit_review.md --topic "long-term care"
  %(prog)s ./pdfs/ --topics --top-k-clusters 5
        """,
    )
    parser.add_argument("corpus", help="Path to corpus: directory of PDFs or .bib file. Use quotes if path has spaces.")
    parser.add_argument("--output", default="lit_review.md", help="Output markdown file (default: lit_review.md)")
    parser.add_argument("--topic", help="Focus synthesis on a specific topic/theme")
    parser.add_argument("--max-papers", type=int, default=50, help="Max papers to include (default: 50)")
    parser.add_argument("--topics", action="store_true", help="Cluster corpus by topic instead of full review")
    parser.add_argument("--top-k-clusters", type=int, default=5, help="Number of topic clusters (default: 5)")
    parser.add_argument("--model", default=None, help="LLM model for synthesis (default: from pa config)")
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


    if not Path(args.corpus).exists():
        print(json.dumps({
            "error": "corpus_not_found",
            "message": f"Corpus not found: {args.corpus}",
        }), file=sys.stderr)
        return 1

    if args.topics:
        # Cluster mode
        cmd = [
            PYTHON, "-m", "pa_cli.cli", "review-topics",
            args.corpus,
            "--top-k", str(args.top_k_clusters),
        ]
    else:
        # Full review mode
        cmd = [
            PYTHON, "-m", "pa_cli.cli", "review",
            args.corpus,
            "--output", args.output,
            "--max-papers", str(args.max_papers),
        ]
        if args.topic:
            cmd.extend(["--topic", args.topic])
        if args.model:
            cmd.extend(["--model", args.model])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=600,  # Lit review can be slow (LLM synthesis)
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "review_timeout",
            "message": "Synthesis exceeded 600s timeout.",
            "hint": "Try smaller --max-papers or check LLM API connectivity.",
        }), file=sys.stderr)
        return 2

    if result.returncode == 0:
        out = {
            "status": "completed",
            "corpus": args.corpus,
            "output": args.output if not args.topics else "(topic clusters printed to stdout)",
            "mode": "clustering" if args.topics else "synthesis",
        }
        if args.topics:
            out["clusters"] = result.stdout  # pa review-topics prints clusters
        print(json.dumps(out, indent=2))
        return 0

    print(json.dumps({
        "error": "pa_review_failed",
        "exit_code": result.returncode,
        "corpus": args.corpus,
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
