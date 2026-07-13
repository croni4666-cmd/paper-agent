"""
pa_cli/recency.py — Recency + citation threshold filter for paper-agent v3.9.1.

ROADMAP [P1-5] (added 2026-07-13, executed 2026-07-13):
User explicit rule (verbatim):
  "文献的时间太老了,甚至有十年之前的文章,除非这种文章引用度很高,超过平均引用数
  两个以上标准差,否则不应该作为我们应该看的文章。假如大量的引用文章都比较老,
  很有可能该领域已经过时了,或者没人研究了。"

Translation:
  - Papers >10 years old need citation_count > mean + 2*std (per query) to keep full weight
  - Papers >20 years old are stricter: downweight to 0.1x unless their bi-encoder
    relevance score is high (signal that they're still semantically on-topic)
  - If a query's top-30 candidates have median year > 5 years ago, emit a
    "field-may-be-stale" warning (helps user know their topic is dead)

Mode flags (CLI):
  - 'strict' (default): apply the rules above
  - 'moderate': only downweight to 0.5x, never 0.1x
  - 'off': skip the filter (current v3.9.0 behavior)

Score multiplier: applied at the rerank stage, multiplying `final_score`. Labels
stay ground-truth accurate — this is a ranking signal, not a label change.
"""
from __future__ import annotations
import statistics
import warnings
from dataclasses import dataclass


@dataclass
class RecencyConfig:
    """Configuration for recency filter."""
    mode: str = "strict"  # 'strict' | 'moderate' | 'off'
    now_year: int = 2026  # override for testing
    old_threshold: int = 10  # years — paper older than this is "old"
    ancient_threshold: int = 20  # years — paper older than this is "ancient"
    cite_std_multiplier_old: float = 2.0  # old papers need cite > mean + N*std
    cite_std_multiplier_ancient: float = 2.5  # ancient papers need cite > mean + N*std
    bi_escape_threshold: float = 0.7  # bi-encoder score above this can rescue old papers
    cite_rescue_multiplier: float = 1.0  # papers with cite > mean + N*std escape downweight
    downweight_old: float = 0.5
    downweight_ancient: float = 0.1
    field_stale_median_year: int = 5  # warn if median(year) < now - N


def recency_factor(
    year: int | None,
    citation_count: int | None,
    bi_score: float | None = None,
    query_citation_stats: dict | None = None,
    config: RecencyConfig | None = None,
) -> tuple[float, str]:
    """Compute the recency multiplier for a single candidate.

    Args:
        year: publication year (None if unknown)
        citation_count: number of citations (None if unknown)
        bi_score: bi-encoder relevance score (None if not computed yet)
        query_citation_stats: dict with keys 'mean', 'std', 'median' (computed over the query's candidates)
        config: RecencyConfig; defaults to strict mode

    Returns:
        (multiplier, reason) — multiplier in [0.1, 1.0], reason is human-readable
    """
    if config is None:
        config = RecencyConfig()
    if config.mode == "off":
        return 1.0, "recency:off"

    # If year is unknown, can't apply the rule — keep full weight (caller can apply
    # [P2-5] quality filter separately for no-year + low-cite papers)
    if year is None or year <= 0:
        return 1.0, "recency:no-year"

    age = config.now_year - year

    # Compute cite threshold (mean + N*std)
    if query_citation_stats and query_citation_stats.get("std") is not None:
        cite_mean = query_citation_stats.get("mean", 0)
        cite_std = query_citation_stats.get("std", 0)
    else:
        cite_mean = 0
        cite_std = 0

    cite = citation_count or 0
    is_old = age > config.old_threshold
    is_ancient = age > config.ancient_threshold
    is_above_old_threshold = cite > (cite_mean + config.cite_std_multiplier_old * cite_std)
    is_above_ancient_threshold = cite > (cite_mean + config.cite_std_multiplier_ancient * cite_std)
    bi_high = bi_score is not None and bi_score > config.bi_escape_threshold

    # Bi-encoder rescue: if the paper is highly semantically relevant to the query,
    # keep it at full weight even if old. (User's note: "应该设法区分人主导还是机器主导"
    # — old but highly on-topic papers still have research value.)
    if is_old and bi_high and is_above_old_threshold:
        return 1.0, f"recency:rescued(bi={bi_score:.2f},cite={cite},mean={cite_mean:.0f}+{config.cite_std_multiplier_old}σ)"

    # Mode-specific ancient handling
    if is_ancient and not is_above_ancient_threshold:
        if config.mode == "moderate":
            # moderate: downweight to 0.5x (same as old), never 0.1x
            return config.downweight_old, f"recency:ancient-moderate(age={age}y,cite={cite}<mean+{config.cite_std_multiplier_ancient}σ)"
        return config.downweight_ancient, f"recency:ancient(age={age}y,cite={cite}<mean+{config.cite_std_multiplier_ancient}σ)"
    if is_old and not is_above_old_threshold:
        return config.downweight_old, f"recency:old(age={age}y,cite={cite}<mean+{config.cite_std_multiplier_old}σ)"

    return 1.0, "recency:fresh"


def compute_citation_stats(candidates: list[dict]) -> dict:
    """Compute mean, std, median of citation_count over the candidate pool.

    Args:
        candidates: list of {doi, year, citation_count, ...}

    Returns:
        {"mean": float, "std": float, "median": float, "n": int}
    """
    cites = [c.get("citation_count", 0) or 0 for c in candidates]
    if not cites:
        return {"mean": 0, "std": 0, "median": 0, "n": 0}
    mean = statistics.mean(cites)
    std = statistics.stdev(cites) if len(cites) > 1 else 0.0
    median = statistics.median(cites)
    return {"mean": mean, "std": std, "median": median, "n": len(cites)}


def check_field_staleness(candidates: list[dict], config: RecencyConfig | None = None) -> str | None:
    """Return a warning string if the field appears stale, else None.

    User's rule: "假如大量的引用文章都比较老,很有可能该领域已经过时了,或者没人研究了"
    (If many cited papers are old, the field may be outdated).

    Heuristic: if median publication year of candidates is > N years before now, warn.
    """
    if config is None:
        config = RecencyConfig()
    years = [c.get("year") for c in candidates if c.get("year") and c.get("year") > 0]
    if not years:
        return None
    median_year = statistics.median(years)
    age = config.now_year - median_year
    if age > config.field_stale_median_year:
        return (
            f"[recency warning] field_may_be_stale: median candidate year = {int(median_year)} "
            f"({int(age)} years ago). User rule: if many cited papers are old, the field "
            f"may be outdated. Consider narrowing query or adding 'since 2020' filter."
        )
    return None


def apply_recency_to_results(
    results: list[dict],
    bi_scores: list[float] | None = None,
    config: RecencyConfig | None = None,
) -> tuple[list[dict], str | None]:
    """Apply recency factor to each candidate's v4_score.

    Args:
        results: list of {doi, title, year, citation_count, v4_score, ...} in current rank order
        bi_scores: parallel list of bi-encoder scores (for rescue logic)
        config: RecencyConfig

    Returns:
        (new_results, field_warning) — new_results have v4_score * recency_factor;
        field_warning is a string if the field appears stale, else None
    """
    if config is None:
        config = RecencyConfig()
    if config.mode == "off":
        return results, None

    # Compute query-level citation stats
    stats = compute_citation_stats(results)
    field_warning = check_field_staleness(results, config)

    new_results = []
    for i, r in enumerate(results):
        bi = bi_scores[i] if bi_scores and i < len(bi_scores) else None
        factor, reason = recency_factor(
            year=r.get("year"),
            citation_count=r.get("citation_count"),
            bi_score=bi,
            query_citation_stats=stats,
            config=config,
        )
        r_new = dict(r)
        old_score = r.get("v4_score", 0) or 0
        r_new["v4_score"] = old_score * factor
        r_new["recency_factor"] = factor
        r_new["recency_reason"] = reason
        new_results.append(r_new)
    return new_results, field_warning


if __name__ == "__main__":
    # Quick smoke test
    import json
    test_candidates = [
        {"doi": "10.1/a", "year": 2024, "citation_count": 100, "v4_score": 1.0},
        {"doi": "10.1/b", "year": 2014, "citation_count": 50, "v4_score": 0.9},   # old, low cite
        {"doi": "10.1/c", "year": 2000, "citation_count": 800, "v4_score": 0.95}, # ancient, high cite
        {"doi": "10.1/d", "year": 2003, "citation_count": 200, "v4_score": 0.85}, # ancient, low cite
        {"doi": "10.1/e", "year": None, "citation_count": 5, "v4_score": 0.7},     # no year
    ]
    print("Test 1: default strict mode")
    new, warn = apply_recency_to_results(test_candidates, bi_scores=[0.5, 0.5, 0.95, 0.6, 0.4])
    for r in new:
        print(f"  {r['doi']:18s} year={r['year']!s:5s} cite={r['citation_count']:4d} v4={r['v4_score']:.3f} factor={r['recency_factor']} reason={r['recency_reason']}")
    print(f"  WARN: {warn}")
    print()
    print("Test 2: moderate mode")
    cfg = RecencyConfig(mode="moderate")
    new, warn = apply_recency_to_results(test_candidates, bi_scores=[0.5, 0.5, 0.95, 0.6, 0.4], config=cfg)
    for r in new:
        print(f"  {r['doi']:18s} year={r['year']!s:5s} cite={r['citation_count']:4d} v4={r['v4_score']:.3f} factor={r['recency_factor']} reason={r['recency_reason']}")
    print(f"  WARN: {warn}")
