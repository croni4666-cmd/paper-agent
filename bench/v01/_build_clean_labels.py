"""
bench/v01/_build_clean_labels.py — Parse user spot-check files, build labels_clean.json.

Reads:
  - bench/v01/labels.json (Mavis preliminary labels)
  - bench/v01/spot_check/SPOT_CHECK_qNNN.md (user spot-check annotations)

Writes:
  - bench/v01/labels_clean.json (clean labels with user overrides applied)
  - bench/v01/spot_check/_overrides.json (audit log of every override + note)

User spot-check patterns handled:
  - [x] in 0/1/2 option → user's choice (overrides Mavis if different)
  - No [x] but user_note non-empty → KEEP Mavis label (note is rationale, not disagreement)
  - Special: q010 #1 (OxCGRT) — user wants institutional credibility boost
    We treat as: user wants this to be at least 1 (Mavis already labeled 1, so no override;
    note preserved as rationale for future institutional-credibility feature)
  - Special: q007 #27 vs #28 — DOI-case duplicates. System-level dedup, not a label change.
"""
import json
import re
from pathlib import Path

BENCH_DIR = Path(r"G:\minimax - workspace\Paper agent\bench\v01")
SPOT_DIR = BENCH_DIR / "spot_check"
LABELS_IN = BENCH_DIR / "labels.json"
LABELS_OUT = BENCH_DIR / "labels_clean.json"
OVERRIDES_OUT = BENCH_DIR / "spot_check" / "_overrides.json"


def parse_spot_check(path: Path) -> dict:
    """Parse a single SPOT_CHECK_qNNN.md file.

    Returns:
        {
            "qNNN": str,
            "overrides": [{"rank": int, "doi": str, "mavis_label": int|None,
                          "user_label": int|None, "user_chose": int|None, "note": str,
                          "kind": "override"|"agree"|"note_only"|"absent"}],
        }
    """
    text = path.read_text(encoding="utf-8")
    qid_match = re.search(r"# Spot-Check: (q\d+)", text)
    if not qid_match:
        return {"qNNN": None, "overrides": []}
    qid = qid_match.group(1)

    overrides = []
    # Each candidate block: starts with "### #N — `DOI`" and ends at next "### #" or "---"
    # The structure we care about:
    #   **Mavis label**: `N` — reason
    #   **User label**: `...`
    #   **User note** (optional, only if disagree): note text
    # And the [x]/[ ] boxes for 0/1/2

    # Split by "### #" headers
    blocks = re.split(r"\n### #(\d+)\s+—\s+`([^`]+)`", text)
    # blocks: [preamble, rank1, doi1, body1, rank2, doi2, body2, ...]

    for i in range(1, len(blocks), 3):
        try:
            rank = int(blocks[i])
            doi = blocks[i + 1]
            body = blocks[i + 2]
        except (IndexError, ValueError):
            continue

        # Extract Mavis label
        mavis_match = re.search(r"\*\*Mavis label\*\*:\s*`(-?\d+|\?)`", body)
        mavis_label = None
        if mavis_match and mavis_match.group(1) != "?":
            try:
                mavis_label = int(mavis_match.group(1))
            except ValueError:
                mavis_label = None

        # Extract user note (the literal text after "User note (optional, only if disagree):")
        note_match = re.search(
            r"\*\*User note\*\* \(optional, only if disagree\):\s*(.*?)(?=\n---|\n###|\Z)",
            body, re.DOTALL,
        )
        note = note_match.group(1).strip() if note_match else ""

        # Extract user label (the literal value in `___` form, if filled)
        user_label_match = re.search(r"\*\*User label\*\*:\s*`([^`]+)`", body)
        user_label_raw = user_label_match.group(1).strip() if user_label_match else ""
        # If user_label is "_something_" or "something" or any non-empty, that's their
        # explanation. The authoritative signal is the [x] mark.

        # Find the [x] mark — which of 0/1/2 did the user pick?
        user_chose = None
        for opt in (0, 1, 2):
            if re.search(rf"\[x\]\s*\*\*{opt}\b", body):
                user_chose = opt
                break

        # Classify
        if user_chose is None:
            if note:
                kind = "note_only"  # user added note but didn't tick — KEEP Mavis
            else:
                kind = "absent"  # no annotation at all — KEEP Mavis
        elif mavis_label is None or user_chose == mavis_label:
            kind = "agree"  # ticked the same as Mavis (or Mavis had no label)
        else:
            kind = "override"  # different from Mavis

        overrides.append({
            "rank": rank,
            "doi": doi,
            "mavis_label": mavis_label,
            "user_chose": user_chose,
            "user_label_raw": user_label_raw,
            "note": note,
            "kind": kind,
        })

    return {"qNNN": qid, "overrides": overrides}


def main():
    print(f"[build-clean] loading labels: {LABELS_IN}")
    labels = json.loads(LABELS_IN.read_text(encoding="utf-8"))["labels"]
    print(f"[build-clean] {len(labels)} queries in labels.json")

    all_overrides = {}
    overrides_applied = 0
    notes_preserved = 0
    agrees = 0
    absents = 0
    n_no_mavis = 0  # DOI in spot-check but not in labels.json

    for path in sorted(SPOT_DIR.glob("SPOT_CHECK_q*.md")):
        result = parse_spot_check(path)
        qid = result["qNNN"]
        if not qid:
            continue
        if qid not in labels:
            print(f"  WARN: {qid} not in labels.json")
            continue

        q_overrides = []
        for ov in result["overrides"]:
            doi = ov["doi"]
            mavis = ov["mavis_label"]
            user_chose = ov["user_chose"]

            # Look up Mavis label in labels.json
            mavis_in_json = labels[qid].get(doi, {}).get("label")

            # If DOI in spot-check isn't in labels.json, skip (spot-check DOI
            # may differ in case/typo — e.g. 10.3380 vs 10.3389)
            if doi not in labels[qid]:
                n_no_mavis += 1
                if ov["kind"] in ("override", "note_only"):
                    # Surface the data drift explicitly
                    print(f"  WARN: {qid} #{ov['rank']} DOI {doi!r} in spot-check but not in labels.json — skipping")
                continue

            if ov["kind"] == "override":
                # Apply override
                labels[qid][doi]["label"] = user_chose
                # Add note as rationale (don't lose it)
                if ov["note"]:
                    labels[qid][doi]["reason"] = f"USER OVERRIDE: {ov['note'][:200]}"
                else:
                    labels[qid][doi]["reason"] = f"USER OVERRIDE (no note)"
                overrides_applied += 1
                q_overrides.append({
                    "rank": ov["rank"],
                    "doi": doi,
                    "from": mavis_in_json,
                    "to": user_chose,
                    "note": ov["note"],
                })
            elif ov["kind"] == "note_only":
                # Note preserved but no override
                if ov["note"]:
                    labels[qid][doi]["reason"] = f"USER NOTE: {ov['note'][:200]}"
                notes_preserved += 1
            elif ov["kind"] == "agree":
                agrees += 1
            elif ov["kind"] == "absent":
                absents += 1

        all_overrides[qid] = q_overrides

    print(f"\n[build-clean] summary:")
    print(f"  Overrides applied:   {overrides_applied}")
    print(f"  Notes preserved:     {notes_preserved}")
    print(f"  Agrees (no change):  {agrees}")
    print(f"  Absent (no mark):    {absents}")
    print(f"  DOIs in spot-check but missing from labels.json: {n_no_mavis}")

    # Write outputs
    LABELS_OUT.parent.mkdir(parents=True, exist_ok=True)
    out = {"version": "v0.1-clean", "labels": labels}
    LABELS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[build-clean] wrote {LABELS_OUT}")

    OVERRIDES_OUT.write_text(
        json.dumps(all_overrides, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[build-clean] wrote {OVERRIDES_OUT} (audit log)")

    # Per-query stats: which queries had overrides
    print(f"\n[build-clean] per-query override counts:")
    for qid in sorted(all_overrides.keys()):
        n = len(all_overrides[qid])
        if n:
            print(f"  {qid}: {n} override(s)")


if __name__ == "__main__":
    main()
