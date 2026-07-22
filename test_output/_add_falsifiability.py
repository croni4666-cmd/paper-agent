"""[P1-10] Add a falsifiability summary to the library.

Per user decision 2026-07-22:
- User finishes research on a topic
- User asks the session (e.g. "summarize the falsifiability of [topic]")
- Session produces a structured summary
- User runs this script to commit the summary to the library

Usage:
    # Interactive (will prompt for fields)
    python test_output/_add_falsifiability.py

    # Parameterized
    python test_output/_add_falsifiability.py \\
        --topic "DEA-Tobit second-stage" \\
        --question "Does 算力券享受 have a non-zero effect on DMU efficiency?" \\
        --evidence "16 DMU real data, p=0.31, direction matches hypothesis" \\
        --verdict "supported-with-caveats" \\
        --severity "weak" \\
        --paper-dois "10.1016/... 10.1016/..." \\
        --session "mvs_ca3a2a9a5dbf467396047cf4aa04075c"

Verdicts:
- supported:        data supports hypothesis
- supported-with-caveats: data supports, but limited sample
- inconclusive:    not enough data
- refuted:          data refutes hypothesis

Severity (Popperian 'severity of test'):
- weak:    routine test, low info gain
- moderate: standard test
- strong:  high-stakes test, would shift the conclusion if result were different
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
SUMMARIES_PATH = BENCH / "falsifiability_summaries.json"

VALID_VERDICTS = {"supported", "supported-with-caveats", "inconclusive", "refuted"}
VALID_SEVERITIES = {"weak", "moderate", "strong"}


def add_summary(args):
    if not SUMMARIES_PATH.exists():
        print(f"ERROR: {SUMMARIES_PATH} not found")
        sys.exit(1)
    data = json.loads(SUMMARIES_PATH.read_text(encoding="utf-8-sig"))
    summaries = data.get("summaries", [])

    if args.verdict not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict: {args.verdict!r}. Must be one of {VALID_VERDICTS}")
    if args.severity not in VALID_SEVERITIES:
        raise ValueError(f"Invalid severity: {args.severity!r}. Must be one of {VALID_SEVERITIES}")

    dois = [d.strip() for d in args.paper_dois.split(",") if d.strip()] if args.paper_dois else []

    entry = {
        "id": f"fs{len(summaries) + 1:03d}",
        "topic": args.topic,
        "question": args.question,
        "evidence": args.evidence,
        "verdict": args.verdict,
        "severity": args.severity,
        "paper_dois": dois,
        "session": args.session,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
    }
    summaries.append(entry)
    data["summaries"] = summaries
    tmp = SUMMARIES_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SUMMARIES_PATH)
    print(f"  [P1-10] {entry['id']} added (topic={args.topic!r}, verdict={args.verdict})")

    from _status_lookups import status_falsifiability
    print()
    status_falsifiability()


def main():
    parser = argparse.ArgumentParser(
        description="[P1-10] Add a falsifiability summary to the library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--topic", required=True, help="Research topic (e.g. 'DEA-Tobit second-stage')")
    parser.add_argument("--question", required=True, help="The falsifiable question (e.g. 'Does X have Y effect?')")
    parser.add_argument("--evidence", required=True, help="Brief evidence summary")
    parser.add_argument("--verdict", required=True, choices=sorted(VALID_VERDICTS),
                        help="Verdict of the falsifiability test")
    parser.add_argument("--severity", required=True, choices=sorted(VALID_SEVERITIES),
                        help="Severity of the test (Popperian 'severity')")
    parser.add_argument("--paper-dois", default="",
                        help="Comma-separated DOIs of papers used as evidence")
    parser.add_argument("--session", default="",
                        help="mavis session ID where this summary was generated")
    args = parser.parse_args()
    add_summary(args)


if __name__ == "__main__":
    main()
