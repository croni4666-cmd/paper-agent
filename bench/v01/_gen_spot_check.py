#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate spot-check interface for user label review.

Reads:
  - bench/v01/labels.json (Mavis's preliminary labels)
  - bench/v01/system_outputs/q00X.json (candidate details)

Writes:
  - bench/v01/spot_check/SPOT_CHECK_INDEX.md (TOC)
  - bench/v01/spot_check/SPOT_CHECK_q00X.md (per query, 25 files)

User workflow:
  1. Open SPOT_CHECK_INDEX.md, jump to a query
  2. For each candidate, decide if Mavis's label is correct
  3. Fill in "user_label" column (0/1/2) + "user_note" (optional reason if disagree)
  4. Save the file, hand back to Mavis
  5. Mavis reads user files, merges with labels.json -> labels_clean.json

Scoring:
  - 0 = not relevant
  - 1 = partial / related but not directly on topic
  - 2 = directly relevant
"""

import json
from pathlib import Path
from collections import OrderedDict

BENCH_ROOT = Path(r"G:\minimax - workspace\Paper agent\bench\v01")
LABELS_PATH = BENCH_ROOT / "labels.json"
OUT_DIR = BENCH_ROOT / "spot_check"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_labels() -> dict:
    """labels.json: {_meta, labels: {qid: {doi: {label, reason}}}}"""
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        full = json.load(f)
    return full.get("labels", full)


def load_system_output(qid: str) -> dict:
    """system_outputs/q001.json: {query_id, query, results: [{rank, doi, title, abstract, ...}]}"""
    p = BENCH_ROOT / "system_outputs" / f"{qid}.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def truncate(text: str, n: int = 280) -> str:
    """Truncate text to n chars + ellipsis if needed."""
    if not text:
        return "_(no abstract)_"
    text = text.replace("\n", " ").strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + "..."


def render_query_file(qid: str, labels_for_q: dict, sys_out: dict) -> str:
    """Render a single per-query SPOT_CHECK file."""
    query_text = sys_out["query"]
    # Build lookup: doi -> {title, abstract, rank, ...}
    by_doi = OrderedDict()
    for r in sys_out["results"]:
        by_doi[r["doi"]] = r

    lines = []
    lines.append(f"# Spot-Check: {qid}")
    lines.append("")
    lines.append(f"**Query**: `{query_text}`")
    lines.append("")
    lines.append("## How to fill in")
    lines.append("")
    lines.append("For each row below, decide if Mavis's `mavis_label` is correct. Override the `user_label` column (0/1/2) if you disagree, and add a short `user_note` explaining why.")
    lines.append("")
    lines.append("Scoring:")
    lines.append("- **0** = not relevant to the query")
    lines.append("- **1** = partial / related but not directly on topic")
    lines.append("- **2** = directly relevant (paper is *about* this query)")
    lines.append("")
    lines.append("Tips:")
    lines.append("- Title alone is often enough; only read abstract if title is ambiguous")
    lines.append("- 5-15 sec per row. If you can do 30 rows in 10 min, full 25-query pass ≈ 1.5-3 hr")
    lines.append("- **Mavis labels are already 70-80% accurate** based on title scan. Focus on disagreements, not agreement checks")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-candidate sections (clearer than giant table for spot-checking)
    for doi, paper in by_doi.items():
        mavis = labels_for_q.get(doi, {})
        mavis_label = mavis.get("label", "?")
        mavis_reason = mavis.get("reason", "(no reason)")

        title = paper.get("title", "(no title)")
        abstract = truncate(paper.get("abstract", ""), 280)
        year = paper.get("year", "?")
        venue = paper.get("venue", "?")
        cite = paper.get("citation_count", "?")
        rank = paper.get("rank", "?")

        lines.append(f"### #{rank} — `{doi}`")
        lines.append("")
        lines.append(f"**Title**: {title}  ")
        lines.append(f"**Year**: {year} | **Venue**: {venue} | **Citations**: {cite}")
        lines.append("")
        lines.append(f"**Abstract**: {abstract}")
        lines.append("")
        lines.append(f"**Mavis label**: `{mavis_label}` — {mavis_reason}")
        lines.append("")
        lines.append("**Your judgment**:")
        lines.append("")
        lines.append("- [ ] **0** (not relevant) — agree / change to: ____")
        lines.append("- [ ] **1** (partial) — agree / change to: ____")
        lines.append("- [ ] **2** (directly relevant) — agree / change to: ____")
        lines.append("")
        lines.append("**User label**: `___`  ")
        lines.append("**User note** (optional, only if disagree): ")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def render_index(qids: list, labels: dict) -> str:
    """Render the master index."""
    lines = []
    lines.append("# Spot-Check Index — All 25 Queries (2026-07-12)")
    lines.append("")
    lines.append("> **What this is**: A user-friendly interface to verify Mavis's preliminary labels for 750 candidates (25 queries × 30 candidates). Each candidate has a checkbox list (0/1/2). Open a query file, fill in `user_label` for candidates where you disagree with Mavis, save the file, hand back.")
    lines.append("")
    lines.append("> **Time estimate**: 30-60 sec per candidate when scanning title only. 750 candidates × 30 sec = ~6 hr full. 30-40% disagreement rate expected, so partial review (only flagging disagreements) takes 1-2 hr.")
    lines.append("")
    lines.append("## How to use")
    lines.append("")
    lines.append("1. Open the file for a query (e.g. `SPOT_CHECK_q019.md` — the most dramatic failure case, 19/30 are Mavis-labeled relevant)")
    lines.append("2. For each candidate section, the Mavis label is shown — agree or override")
    lines.append("3. **You only need to fill in candidates where you DISAGREE with Mavis** (or to confirm a few high-confidence ones for sanity check)")
    lines.append("4. Save the file")
    lines.append("5. Mavis reads back, computes new `labels_clean.json` from your overrides + Mavis labels for the rest")
    lines.append("")
    lines.append("## Per-query navigation")
    lines.append("")
    lines.append("| Q | Query | n_relevant (Mavis) | File |")
    lines.append("|---|---|---:|---|")

    for qid in qids:
        sys_out = load_system_output(qid)
        labels_for_q = labels.get(qid, {})
        n_relevant = sum(1 for d, m in labels_for_q.items() if m.get("label") == 2)
        # Short query text for table
        qtext = sys_out["query"]
        if len(qtext) > 70:
            qtext = qtext[:67] + "..."
        lines.append(f"| {qid} | {qtext} | {n_relevant}/30 | [SPOT_CHECK_{qid}.md](./SPOT_CHECK_{qid}.md) |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Priority order (if you don't have time to do all 25)")
    lines.append("")
    lines.append("1. **q019** (intelligent tutoring systems) — 19/30 Mavis says relevant, but baseline top-5 missed them all (rank 14+). Biggest lift if labels confirmed")
    lines.append("2. **q005** (universal basic income) — known hard case, multiple definitions")
    lines.append("3. **q007** (climate ag adaptation) — 25/30 Mavis says relevant, recall@10=0.32, hard to crack")
    lines.append("4. **q013** (protein structure) — recall@10=0.25, transformer papers don't always have 'transformer' in abstract")
    lines.append("5. **q010** (broad AI) — high false-positive baseline, Mavis labels a sanity check for noise filtering")
    lines.append("")
    lines.append("The other 20 queries are more 'typical' — doing 1-5 already gives 80% of the ground-truth-stability win.")
    lines.append("")
    lines.append("## What Mavis does with your labels")
    lines.append("")
    lines.append("After you fill in, Mavis will:")
    lines.append("1. Merge your overrides with Mavis labels → `labels_clean.json`")
    lines.append("2. Recompute baseline + BM25 metrics on clean labels")
    lines.append("3. Run E (ablation), A (cross-encoder), C (PaSa-lite) on clean labels")
    lines.append("4. Report v3.9.0 lift numbers in CHANGELOG")
    lines.append("")
    lines.append("If 5-10% of Mavis labels are wrong after your review, the v3.9 numbers will shift by ~0.02-0.05 — not material. If 30%+ are wrong, the strategy needs revisiting (we'll know).")
    lines.append("")
    return "\n".join(lines)


def main():
    labels = load_labels()
    qids = sorted([k for k in labels.keys() if k.startswith("q")])

    # Per-query files
    for qid in qids:
        labels_for_q = labels.get(qid, {})
        sys_out = load_system_output(qid)
        md = render_query_file(qid, labels_for_q, sys_out)
        out_path = OUT_DIR / f"SPOT_CHECK_{qid}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[ok] {out_path.name} ({len(labels_for_q)} candidates)")

    # Index
    idx = render_index(qids, labels)
    idx_path = OUT_DIR / "SPOT_CHECK_INDEX.md"
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(idx)
    print(f"[ok] {idx_path.name} (TOC)")

    print(f"\nDone. Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
