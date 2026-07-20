"""[P2-14] Quality filter — flag/drop papers with no-abstract + low-cite + no-year.

Per ROADMAP [P2-14] (added 2026-07-13, source: user spot-check q005 #30
"no year, low cites = low quality paper, should be removed"):

  - low_quality: abstract is None/empty AND citation_count < 50 AND year is None
  - outdated:    year < (now - 25) AND citation_count < 100

Two flags, mutually exclusive in priority order: low_quality first
(strongest negative signal), then outdated. If a paper has high
cites OR has abstract OR has year, neither flag fires — the
"high-cites paper without abstract" case is intentionally NOT flagged
because the paper may still be valuable.

Quality flags are returned as a `quality_flag` field on each result.
They are NOT auto-dropped; the CLI option `--quality-mode filter` will
drop `low_quality` results from the final list, while `flag` only
annotates and `off` disables.

Usage:
  from pa_cli.quality_filter import flag_quality, apply_quality_filter
  for r in results:
      r['quality_flag'] = flag_quality(r, now=2026)
  filtered = apply_quality_filter(results, mode="filter")

CLI integration (pa search):
  pa search <q> --quality-mode flag   # annotate, don't drop (default)
  pa search <q> --quality-mode filter # drop low_quality
  pa search <q> --quality-mode off    # skip filter

5-check Global Rule audit: 5/5 pass (pure local code; no API; no
maintenance; no publish obligation; degrades gracefully if year/cites
are missing — just doesn't flag).
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional


def _now_year() -> int:
    return datetime.now(timezone.utc).year


def flag_quality(paper: dict, now: Optional[int] = None) -> Optional[str]:
    """Return one of: 'low_quality' | 'outdated' | None.

    Priority: 'low_quality' fires first if all 3 conditions met.
    'outdated' fires next if year > 25y old + cites < 100.

    Args:
        paper: a search result dict. Looks for keys:
               - 'abstract' (str | None | empty)
               - 'year' (int | None)
               - 'cited_by_count' (int, default 0)
        now:    override current year (for testing)
    """
    if now is None:
        now = _now_year()

    abstract = (paper.get("abstract") or "").strip()
    has_abstract = bool(abstract)
    year = paper.get("year")
    has_year = year is not None and year > 0
    cites = int(paper.get("cited_by_count") or 0)

    # low_quality: no abstract + low cites + no year (the user's spec)
    if not has_abstract and cites < 50 and not has_year:
        return "low_quality"
    # outdated: very old + still under-cited (likely not impactful)
    if has_year and (now - year) > 25 and cites < 100:
        return "outdated"
    return None


def apply_quality_filter(results: list[dict], mode: str = "flag",
                          now: Optional[int] = None) -> list[dict]:
    """Annotate or drop results based on quality flags.

    Args:
        results: list of result dicts (mutated in place: adds 'quality_flag' field)
        mode:    'flag' (default) — annotate, don't drop
                 'filter' — drop 'low_quality' results, keep outdated
                 'off'   — no-op (don't even annotate)
        now:     override current year (for testing)

    Returns:
        The (possibly filtered) results list.

    Side effects:
        Sets `r['quality_flag']` on every result if mode != 'off'.
    """
    mode = mode.lower()
    if mode not in ("flag", "filter", "off"):
        raise ValueError(f"quality-mode must be flag|filter|off, got {mode!r}")

    if mode == "off":
        return results

    for r in results:
        r["quality_flag"] = flag_quality(r, now=now)

    if mode == "filter":
        return [r for r in results if r.get("quality_flag") != "low_quality"]

    return results


def summarize_quality(results: list[dict]) -> dict:
    """Count papers by quality flag. Returns dict with counts."""
    counts = {"none": 0, "low_quality": 0, "outdated": 0}
    for r in results:
        flag = r.get("quality_flag")
        if flag is None:
            counts["none"] += 1
        else:
            counts[flag] = counts.get(flag, 0) + 1
    return counts
