# P0-8 path A: 12-feature LTR baseline + honest 3-tier finding

**Date**: 2026-07-22
**Version**: v3.9.10.12
**Status**: Path A COMPLETE — 12-feature LTR pipeline ships, honest negative finding recorded.

---

## Setup

- **Features**: 12 = 8 LTR base + 4 fulltext
  - 8 base: `bm25_score`, `biencoder_score`, `combined_score`, `prf_score`, `log_cite_count`,
    `year`, `is_recent`, `has_abstract`
  - 4 fulltext: `fulltext_bm25`, `fulltext_cross_encoder`, `fulltext_citation_density`,
    `fulltext_venue_score`
- **Data**: n_queries=25 (q001-q025), n_labeled=736
- **Method**: LambdaMART, n_estimators=50, 5-fold CV, learning_rate=0.05, num_leaves=7
- **OpenAlex pre-warm**: 368 unique venues, 552s on first run
  (cache now persisted to `bench/v01/_openalex_venue_cache.json` for fast re-runs)
- **Script**: `test_output/_ltr_12feature_eval.py`

---

## Result

| Method                  | NDCG@10   | Recall@10 | Prec@10 |
|-------------------------|-----------|-----------|---------|
| combined baseline       | 0.7210    | 0.6947    | 0.5000  |
| LTR 8 features          | 0.7543    | 0.7234    | 0.5080  |
| LTR 12 features (NEW)   | 0.7543    | 0.7234    | 0.5080  |
| d (12-feat - 8-feat)    | +0.0000   | -         | -       |
| d (12-feat - baseline)  | +0.0333   | -         | -       |
| d (8-feat - baseline)   | +0.0333   | -         | -       |

LTR 12-feat and 8-feat produce **identical NDCG@10** (and identical per-fold results —
see `folds_12` vs `folds_8` in the JSON). Reason: all 4 fulltext features have 0 LTR
importance gain, so LightGBM with 12 features is functionally equivalent to LightGBM
with 8 features.

---

## Feature importance (12-feature LTR, gain)

| Feature                    | Importance | Notes                                            |
|----------------------------|-----------:|--------------------------------------------------|
| prf_score                  |     205.28 | 4th most important, dominant                     |
| biencoder_score            |     204.06 | close second                                     |
| combined_score             |     140.74 | mid-tier                                         |
| bm25_score                 |      84.43 | still important                                  |
| year                       |      27.76 | recency signal helps                             |
| has_abstract               |       1.94 | weak                                             |
| is_recent                  |       0.62 | weak                                             |
| log_cite_count             |       0.00 | not used (likely subsumed by combined_score)     |
| **fulltext_bm25**          |    **0.00** | **0 because no fulltext PDF in dataset**        |
| **fulltext_cross_encoder** |    **0.00** | **placeholder (BGE-reranker not implemented)**  |
| **fulltext_citation_density** | **0.00** | **has real values but LTR doesn't use it**     |
| **fulltext_venue_score**   |    **0.00** | **has real values but LTR doesn't use it**     |

**Key insight**: even the 2 "working" fulltext features (`fulltext_citation_density`,
`fulltext_venue_score`) have **0 LTR importance**. The values are real (citation_count /
page_count ranges 0-10, OpenAlex venue prestige 0-1) but LTR doesn't find them
differentiating at n=25.

---

## 3-tier honest verdict

### Pass

- 12-feature LTR pipeline works end-to-end (n=25, 5-fold CV, JSON+cache persisted)
- LTR (8 or 12 features) beats combined baseline by +0.033 NDCG@10
- 3 of 4 fulltext features have working computation in `pa_cli/deep_rerank.py:288-296`
  (`fulltext_bm25`, `fulltext_citation_density`, `fulltext_venue_score` work;
  `fulltext_cross_encoder` is the only placeholder)
- OpenAlex venue cache persistence works (552s first run, future runs will be < 30s)

### Neutral

- **12-feat = 8-feat (delta=0.0000)** — adding 4 fulltext features does not lift NDCG@10
  at n=25 because all 4 have 0 LTR importance gain
- The +0.033 LTR-vs-baseline lift is within +/-0.05 noise threshold

### Fail

- **n=25 is below n>=100 noise threshold per memory discipline**; the +0.033 LTR-vs-baseline
  lift may be noise, not signal
- **2 of 4 fulltext features (fulltext_bm25, fulltext_cross_encoder) are 0** because no
  PDF fulltext is in the dataset. Full-text deep rerank requires Layer 6 PDF download to
  be effective
- **Even the 2 "working" fulltext features (citation_density, venue_score) have 0 LTR
  importance** — they don't differentiate label=2 from label=0 papers at n=25

---

## Verdict for paper-agent

- **Path A COMPLETE**: 12-feature LTR pipeline + honest 3-tier finding
- **Code state**: 3 of 4 fulltext features work; cross_encoder is the only unimplemented
  feature; import error (broken since 2026-07-15) is fixed
- **Recommended next step**: NOT cross_encoder implementation. Instead:
  1. Expand label set (n=50 -> n=200 per [P1-13]) so LTR can learn from fulltext features
  2. Or: implement Layer 6 PDF download so fulltext_bm25 has real signal
  3. Or: re-evaluate fulltext_citation_density + venue_score on a larger sample
- **Priority**: low — adding fulltext features does not help LTR at n=25
- **n=25 -> n=200 is the actual bottleneck**, not feature engineering

---

## Files

- Created: `test_output/_ltr_12feature_eval.py` (~15KB, OpenAlex pre-warm + 12-feature LTR + cache persistence)
- Created: `bench/v01/_openalex_venue_cache.json` (368 venue prestige values, ~16KB)
- Created: `bench/v01/reports/v3_9_10_12_p0_8_12features_ltr.json` (eval results, 2.9KB)
- Created: `bench/v01/reports/v3_9_10_12_p0_8_12features_ltr.md` (this report)
- Modified: `pa_cli/deep_rerank.py:288-296` (3/4 fulltext features already working — verified)
- Modified: `pa_cli/__init__.py` (version 3.9.10.11 -> 3.9.10.12)
- Modified: `CHANGELOG.md` (v3.9.10.12 entry)
- Modified: `ROADMAP.md` ([P0-8] broken -> modified; [P1-12] cross_encoder deferred to n>=100)
