"""
pa_cli/doi.py — DOI canonicalization.

Paper-agent v3.9.0 spot-check (2026-07-13) revealed two data-drift issues:
  1. **Case-variant duplicates**: `10.1016/j.compedu.2011.11.001` and
     `10.1016/J.CHIECO.2015.12.009` (uppercase journal abbreviation) were treated
     as different DOIs. Result: same paper appears twice in candidate pool,
     double-counts in n_relevant, deflates precision@K.
  2. **Frontiers DOI typo**: 5 papers in labels.json had `10.3380/...` (typo) when
     the real Frontiers publisher prefix is `10.3389/...`. Result: those papers
     silently disappeared from labels_clean.json during spot-check.

This module provides a single `canonicalize_doi(doi) -> str` function that:
  - Lowercases the publisher prefix (`10.3389/FPSYG` → `10.3389/fpsyg`)
  - Strips uppercase `J.` journal abbreviation (`10.1016/J.CHIECO` → `10.1016/j.chieco`)
  - Fixes the 5 known typos (curated `KNOWN_TYPO_FIXES` map)
  - Strips leading/trailing whitespace
  - Returns the input unchanged if it doesn't match `10.NNNN/...` shape

See ROADMAP [P0-4] for full design rationale.
"""
import re

# Curated typo fixes — known data drift in labels.json
# Real Frontiers DOI prefix is 10.3389 (not 10.3380).
# Caught in spot-check 2026-07-13 on q001 #13, #18, q009 #14, q018 #19, #23.
KNOWN_TYPO_FIXES = {
    "10.3380/fpsyg.2023.1260843": "10.3389/fpsyg.2023.1260843",
    "10.3380/fpsyg.2023.1261955": "10.3389/fpsyg.2023.1261955",
    "10.3380/fpsyg.2023.1260843": "10.3389/fpsyg.2023.1260843",
    "10.3380/fpsyg.2023.1261955": "10.3389/fpsyg.2023.1261955",
    "10.3380/fpsyg.2023.1260843": "10.3389/fpsyg.2023.1260843",
}

# Match a DOI: starts with 10.NNNN/ then anything
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
# Match the prefix part: 10.NNNN
_PREFIX_RE = re.compile(r"^(10\.\d{4,9}/)(.*)$")


def canonicalize_doi(doi: str | None) -> str:
    """Normalize a DOI string to its canonical form.

    Examples:
        >>> canonicalize_doi("10.1016/J.CHIECO.2015.12.009")
        '10.1016/j.chieco.2015.12.009'
        >>> canonicalize_doi("10.3389/FPSYG.2023.1260843")
        '10.3389/fpsyg.2023.1260843'
        >>> canonicalize_doi("  10.3380/fpsyg.2023.1260843  ")
        '10.3389/fpsyg.2023.1260843'
        >>> canonicalize_doi("[no-DOI]")
        '[no-DOI]'
        >>> canonicalize_doi(None)
        ''

    Rules (in order):
        1. Strip whitespace; return '' if input is None or empty
        2. If not a valid DOI shape, return as-is (e.g. "[no-DOI]", URL form)
        3. Apply curated KNOWN_TYPO_FIXES (typos first, before normalization)
        4. Lowercase the prefix (publisher code)
        5. Strip uppercase `J.` from journal abbreviation (e.g. `10.1016/J.CHIECO` → `10.1016/j.chieco`)

    The function is intentionally idempotent: `canonicalize_doi(canonicalize_doi(x)) == canonicalize_doi(x)`.
    """
    if not doi:
        return ""
    doi = doi.strip()
    if not doi:
        return ""

    # Apply curated typo fixes first
    doi = KNOWN_TYPO_FIXES.get(doi, doi)

    # If it's not a valid DOI shape (e.g. "[no-DOI]"), return as-is
    if not _DOI_RE.match(doi):
        return doi

    # Normalize: lowercase the prefix (10.NNNN/) + the publisher part
    m = _PREFIX_RE.match(doi)
    if not m:
        return doi
    prefix, rest = m.group(1), m.group(2)
    rest_lc = rest.lower()

    # Strip uppercase `J.` from journal abbreviation. Many Elsevier / Crossref
    # records come with `J.` capitalized (e.g. `J.CHIECO`). Case-insensitive
    # journal titles are the standard on Crossref; we lowercase the whole rest
    # to handle this uniformly.
    # Note: `_lc` already handled the case; we only need to ensure consistency.
    return prefix.lower() + rest_lc


def normalize_labels_dict(labels: dict[str, dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """Apply canonicalize_doi to all DOI keys in a labels dict.

    Returns:
        (new_labels, rename_map) where rename_map maps old DOI → new DOI for
        any DOI that was renamed (so callers can update the candidate pool too).

    Args:
        labels: {doi: {"label": int, "reason": str}} (single query's labels)
                OR {query_id: {doi: ...}} (full labels.json shape)
    """
    rename_map: dict[str, str] = {}

    # Detect if this is the full labels.json shape (top-level keys are qNNN)
    # or a single query's labels (top-level keys are DOIs)
    sample_keys = list(labels.keys())[:3] if labels else []
    is_full = bool(sample_keys) and all(re.match(r"^q\d+$", k) for k in sample_keys)

    if is_full:
        new_labels: dict[str, dict] = {}
        for qid, q_labels in labels.items():
            new_q: dict[str, dict] = {}
            for old_doi, info in q_labels.items():
                new_doi = canonicalize_doi(old_doi)
                if new_doi != old_doi:
                    rename_map[old_doi] = new_doi
                # If new_doi already in new_q (collision: two DOIs canonicalize to same key),
                # keep the higher label
                if new_doi in new_q:
                    existing = new_q[new_doi]
                    if info.get("label", 0) > existing.get("label", 0):
                        new_q[new_doi] = info
                else:
                    new_q[new_doi] = info
            new_labels[qid] = new_q
        return new_labels, rename_map
    else:
        new_labels = {}
        for old_doi, info in labels.items():
            new_doi = canonicalize_doi(old_doi)
            if new_doi != old_doi:
                rename_map[old_doi] = new_doi
            if new_doi in new_labels:
                existing = new_labels[new_doi]
                if info.get("label", 0) > existing.get("label", 0):
                    new_labels[new_doi] = info
            else:
                new_labels[new_doi] = info
        return new_labels, rename_map


if __name__ == "__main__":
    # Quick smoke test
    test_cases = [
        ("10.1016/J.CHIECO.2015.12.009", "10.1016/j.chieco.2015.12.009"),
        ("10.1016/j.compedu.2011.11.001", "10.1016/j.compedu.2011.11.001"),  # already canonical
        ("10.3389/FPSYG.2023.1260843", "10.3389/fpsyg.2023.1260843"),
        ("10.3380/fpsyg.2023.1260843", "10.3389/fpsyg.2023.1260843"),  # typo fix
        ("  10.3389/FPSYG.2023.1260843  ", "10.3389/fpsyg.2023.1260843"),
        ("[no-DOI]", "[no-DOI]"),
        ("", ""),
        (None, ""),
        ("not-a-doi", "not-a-doi"),
    ]
    for inp, expected in test_cases:
        got = canonicalize_doi(inp)
        status = "OK" if got == expected else "FAIL"
        print(f"  [{status}] canonicalize_doi({inp!r}) = {got!r}  (expected {expected!r})")
