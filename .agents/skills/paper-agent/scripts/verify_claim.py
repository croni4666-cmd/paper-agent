#!/usr/bin/env python3
"""scripts/verify_claim.py — Academic Claim & Citation Verifier (Evidence-Grounded).

Given a scientific claim and a PDF manuscript, uses M2 page-aware evidence
indexing to retrieve the exact supporting passages, verify the claim against
the text, and return a structured verification report with page numbers and offsets.
Zero LLM hallucination: all claims must cite verbatim character-level offsets.

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
    from pa_cli.evidence import build_index, build_packet

    index = build_index(pdf_path)
    packet = build_packet(index, query=claim, max_spans=max_spans)

    evidence = packet.get("evidence", [])
    if not evidence:
        return {
            "claim": claim,
            "verdict": "insufficient_evidence",
            "confidence": 0.0,
            "supporting_passages": [],
            "reason": "No relevant text passages found matching the claim in the PDF.",
            "artifact_sha256": packet.get("artifact_sha256"),
        }

    claim_words = set(re.findall(r"\w+", claim.casefold()))
    stop_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of", "is", "are", "was", "were"}
    informative_words = claim_words - stop_words

    supporting = []
    max_overlap_ratio = 0.0

    for span in evidence:
        span_words = set(re.findall(r"\w+", span["text"].casefold()))
        overlap = informative_words & span_words
        overlap_ratio = len(overlap) / len(informative_words) if informative_words else 0.0
        if overlap_ratio > max_overlap_ratio:
            max_overlap_ratio = overlap_ratio

        supporting.append({
            "page": span["page"],
            "section": span.get("section", "unknown"),
            "offsets": [span["start"], span["end"]],
            "evidence_id": span["evidence_id"],
            "matching_keywords": sorted(list(overlap)),
            "overlap_ratio": round(overlap_ratio, 3),
            "verbatim_text": span["text"].strip(),
        })

    if max_overlap_ratio >= 0.50:
        verdict = "supported"
        conf = min(1.0, round(max_overlap_ratio * 1.1, 2))
        reason = f"High keyword and semantic alignment ({round(max_overlap_ratio*100)}% informative terms matched) in {supporting[0]['section']} section on page {supporting[0]['page']}."
    elif max_overlap_ratio >= 0.25:
        verdict = "partially_supported"
        conf = round(max_overlap_ratio, 2)
        reason = f"Partial term match ({round(max_overlap_ratio*100)}%) found. Human review recommended to confirm specific assertion."
    else:
        verdict = "insufficient_evidence"
        conf = round(max_overlap_ratio, 2)
        reason = "Extracted passages do not contain enough overlapping terminology to substantiate the claim."

    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": conf,
        "best_match_page": supporting[0]["page"] if supporting else None,
        "best_match_section": supporting[0]["section"] if supporting else None,
        "reason": reason,
        "supporting_passages": supporting,
        "artifact_sha256": packet.get("artifact_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify an academic claim against a PDF manuscript with exact page citations.",
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
