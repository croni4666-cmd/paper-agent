#!/usr/bin/env python3
"""Generate a deterministic review draft or topic clusters from a corpus directory.

This backend does not perform LLM narrative synthesis or read BibTeX as a corpus.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root, get_install_instructions  # noqa: E402

PYTHON = find_pa_python()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./pdfs/ --output lit_review.md
  %(prog)s ./pdfs/ --topics --output topics.json
        """,
    )
    parser.add_argument("corpus", help="Directory of PDF, Markdown or text papers")
    parser.add_argument("--output", help="Output path (default: lit_review.md or topics.json in caller directory)")
    parser.add_argument("--topics", action="store_true", help="Cluster corpus instead of generating a draft")
    parser.add_argument("--word-count-min", type=int, default=1000, help="Backend full-text classification threshold, not an evidence quality score")
    # Recognize old advertised options to give a clear error, never silently ignore them.
    for flag in ('--topic', '--max-papers', '--top-k-clusters', '--model'):
        parser.add_argument(flag, help=argparse.SUPPRESS)
    args = parser.parse_args()
    unsupported = [name for name in ('topic', 'max_papers', 'top_k_clusters', 'model')
                   if getattr(args, name) is not None]
    if unsupported:
        print(json.dumps({'error': 'unsupported_review_options', 'options': unsupported,
                          'message': 'Backend generates a deterministic draft; LLM and fixed-k options are unsupported.'}), file=sys.stderr)
        return 2
    args.corpus = str(Path(args.corpus).expanduser().resolve())
    args.output = str(Path(args.output or ('topics.json' if args.topics else 'lit_review.md')).expanduser().resolve())

    # Find paper-agent root
    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        return 4


    if not Path(args.corpus).is_dir():
        print(json.dumps({
            "error": "corpus_directory_required",
            "message": f"Expected a corpus directory, not a BibTeX file: {args.corpus}",
        }), file=sys.stderr)
        return 1

    if args.topics:
        # Cluster mode
        cmd = [
            PYTHON, "-m", "pa_cli.cli", "review-topics",
            args.corpus,
            "--output", args.output,
            "--word-count-min", str(args.word_count_min),
        ]
    else:
        # Full review mode
        cmd = [
            PYTHON, "-m", "pa_cli.cli", "review",
            args.corpus,
            "--output", args.output,
            "--word-count-min", str(args.word_count_min),
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=600,
            cwd=str(pa_root),
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({
            "error": "review_timeout",
            "message": "Corpus processing exceeded 600s timeout.",
            "hint": "Try a smaller corpus.",
        }), file=sys.stderr)
        return 2

    if result.returncode == 0:
        if not Path(args.output).is_file():
            print(json.dumps({'error': 'review_output_missing', 'output': args.output}), file=sys.stderr)
            return 1
        out = {
            "status": "completed",
            "corpus": args.corpus,
            "output": args.output,
            "mode": "clustering" if args.topics else "draft",
            "requires_evidence_review": True,
        }
        if args.topics:
            try:
                out["clusters"] = json.loads(Path(args.output).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                print(json.dumps({'error': 'invalid_topics_output', 'message': str(exc)}), file=sys.stderr)
                return 1
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
