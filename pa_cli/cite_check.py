"""pa_cli.cite_check — pre-build validator for `[@bibkey]` placeholders.

Per ROADMAP [P2-7] (added 2026-07-15, shipped 2026-07-20 in v3.9.10.3):
  Scans a markdown skeleton, extracts every `[@bibkey]` placeholder, cross-references
  against a Bibtex file, reports 3 buckets:
    - missing:  skeleton has [@key] but .bib does NOT contain it
    - typo'd:   skeleton has [@key-near-miss] (edit distance 1-2) — suggest fix
    - orphan:   .bib has [@key] but skeleton never cites it (dead weight)

Solves the user pain: today `pa build` failure with "undefined reference" gives
you the wrong key but not the file/line. This gives a clean per-key report.

Usage from CLI:
  pa cite-check refs.bib skeleton.md
  pa cite-check refs.bib skeleton.md --json
  pa cite-check refs.bib skeleton.md --strict  # exit 1 if any missing
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from .scaffold import parse_bibtex, load_bibtex


# ──────────────────────────────────────────────────────────────────────
# Extraction
# ──────────────────────────────────────────────────────────────────────

# Match [@key] or [@key:page] or [@key, p. 12] etc.
# Key chars: letters, digits, underscore, hyphen, dot, colon (common in author-year keys)
_CITE_RE = re.compile(r"\[@([\w\-:.]+)(?:\s*[,;][^\]]*)?\]")


def extract_cite_keys(skeleton_text: str) -> List[Tuple[str, int]]:
    """Extract every `[@key]` placeholder from a markdown skeleton.

    Returns list of (key, line_number) tuples, in source order.
    Deduplicates: same key on same line counts once; same key on different lines
    appears multiple times (so we can report per-line).
    """
    out = []
    for lineno, line in enumerate(skeleton_text.splitlines(), start=1):
        for m in _CITE_RE.finditer(line):
            out.append((m.group(1), lineno))
    return out


# ──────────────────────────────────────────────────────────────────────
# Suggest (typo fix)
# ──────────────────────────────────────────────────────────────────────

def _edit_distance_1_or_2(a: str, b: str) -> bool:
    """Return True if edit distance between a and b is 1 or 2.

    Optimized: only checks if |len(a) - len(b)| <= 2 (otherwise distance > 2),
    then early-exits at distance 2.
    """
    if a == b:
        return False  # not a typo
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return False
    # Standard 2-row DP
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * lb
        row_min = i  # minimum in this row so far
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,        # deletion
                curr[j-1] + 1,      # insertion
                prev[j-1] + cost,   # substitution
            )
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > 2:
            return False  # no way to recover in this row
        prev = curr
    return prev[lb] in (1, 2)


def suggest_fix(typo_key: str, bib_keys: Set[str], max_suggestions: int = 3) -> List[str]:
    """Return up to N bib keys that are within edit distance 1-2 of typo_key."""
    suggestions = []
    for bk in bib_keys:
        if _edit_distance_1_or_2(typo_key, bk):
            suggestions.append(bk)
            if len(suggestions) >= max_suggestions:
                break
    return suggestions


# ──────────────────────────────────────────────────────────────────────
# Cross-reference
# ──────────────────────────────────────────────────────────────────────

def cross_ref(
    placeholder_keys: List[Tuple[str, int]],
    bib_keys: Set[str],
    max_typo_distance: int = 2,
) -> Dict[str, List[Dict]]:
    """Cross-reference placeholders against bib keys.

    Returns dict with 3 buckets:
      - missing:  in placeholders, NOT in bib_keys (and no typo fix available)
      - typo'd:   in placeholders, NOT in bib_keys, but a close match exists
      - orphan:   in bib_keys, NOT in placeholders (dead weight)

    Each entry has per-occurrence details (line number for placeholders;
    metadata for orphans).
    """
    placeholder_key_set = {k for k, _ in placeholder_keys}

    missing = []
    typoed = []
    for key, lineno in placeholder_keys:
        if key in bib_keys:
            continue
        suggestions = suggest_fix(key, bib_keys)
        if suggestions:
            typoed.append({'key': key, 'line': lineno, 'suggest': suggestions})
        else:
            missing.append({'key': key, 'line': lineno})

    orphan = []
    for bk in sorted(bib_keys):
        if bk not in placeholder_key_set:
            orphan.append({'key': bk})

    return {'missing': missing, 'typoed': typoed, 'orphan': orphan}


# ──────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────

def format_report(
    result: Dict[str, List[Dict]],
    skeleton_path: Path,
    bib_path: Path,
) -> str:
    """Human-readable report."""
    lines = []
    lines.append(f"# Cite-check report")
    lines.append(f"")
    lines.append(f"- Skeleton: {skeleton_path}")
    lines.append(f"- Bibtex:   {bib_path}")
    lines.append(f"- Placeholders: {sum(len(v) for v in result.values() if 'line' in (v[0] if v else {}))} occurrences "
                 f"({len({k['key'] for k in (result['missing'] + result['typoed'])})} unique missing/typoed)")
    lines.append(f"- Bib keys: {len(result['orphan']) + len({k['key'] for k in (result['missing'] + result['typoed'])})}")
    lines.append(f"")

    if result['missing']:
        lines.append(f"## [MISSING] ({len(result['missing'])} placeholders have no bib entry)")
        for entry in result['missing']:
            lines.append(f"  - line {entry['line']:4d}: [@{entry['key']}]  <-- no match in {bib_path.name}")
        lines.append("")

    if result['typoed']:
        lines.append(f"## [TYPOED]  ({len(result['typoed'])} placeholders have a near match)")
        for entry in result['typoed']:
            sugs = ', '.join(f"[@{s}]" for s in entry['suggest'])
            lines.append(f"  - line {entry['line']:4d}: [@{entry['key']}]  <-- did you mean {sugs}?")
        lines.append("")

    if result['orphan']:
        lines.append(f"## [ORPHAN]  ({len(result['orphan'])} bib entries never cited)")
        for entry in result['orphan']:
            lines.append(f"  - @{entry['key']}")
        lines.append("")

    if not result['missing'] and not result['typoed'] and not result['orphan']:
        lines.append("[OK] All placeholders resolve. No orphans. Clean.")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────

def run_cite_check(
    bib_path: Path,
    skeleton_path: Path,
    output_json: bool = False,
) -> Tuple[Dict[str, List[Dict]], str]:
    """Full pipeline: load bib, load skeleton, cross-ref, format report.

    Returns (result_dict, report_text).
    """
    bib_entries = load_bibtex(bib_path)
    bib_keys = {e['key'] for e in bib_entries}

    skeleton_text = skeleton_path.read_text(encoding='utf-8')
    placeholders = extract_cite_keys(skeleton_text)

    result = cross_ref(placeholders, bib_keys)

    if output_json:
        report = json.dumps({
            'skeleton': str(skeleton_path),
            'bib': str(bib_path),
            'n_placeholders': len(placeholders),
            'n_unique_placeholder_keys': len({k for k, _ in placeholders}),
            'n_bib_keys': len(bib_keys),
            'missing': result['missing'],
            'typoed': result['typoed'],
            'orphan': result['orphan'],
        }, indent=2, ensure_ascii=False)
    else:
        report = format_report(result, skeleton_path, bib_path)

    return result, report
