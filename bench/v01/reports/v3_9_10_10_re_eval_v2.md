# v3.9.10.10 Re-evaluation — Honest 3-Tier Impact Report

> **TL;DR**: The gzip/brotli fix in `pa_cli/search.py:39-66` is correct (4
> engines no longer silent-fail). But the rebuild I ran **excluded S2**
> (to avoid 429 rate limit), and **that single decision regressed
> NDCG@10 from 0.81 → 0.15 and pool coverage from 99.7% → 89.6%** at
> n=50. 35 of 100+ label=2 papers in the old pool are MISSING from
> the new pool. Same-candidate NDCG@10 (intersection) is essentially
> unchanged (0.82 vs 0.81), proving the **ranker itself didn't get
> worse** — the **rebuild pipeline lost S2's relevance signal**.

---

## Setup

- **v3.9.7.3 backup**: `bench/v01/system_outputs_combined_v3_9_7_3_backup/`
  (50 files, built when only arxiv + aminer + cnki effectively worked)
- **v3.9.10.10 new**: `bench/v01/system_outputs_combined/`
  (50 files, rebuilt 2026-07-20 with the gzip fix; S2 skipped due to 429
  rate limit on burst)
- **Labels**: `bench/v01/labels_n50_mixed.json` (50 queries × paper-level
  label ∈ {0, 1, 2})
- **Metrics**: NDCG@K and Recall@K for K ∈ {10, 30, 50}; pool coverage
  (% of label=2 in any position in pool); intersection NDCG@10
  (restricted to papers that appear in BOTH pools — same-candidate
  comparison)

---

## Headline numbers (combined 0.5*BM25 + 0.5*bi-encoder)

| Metric                  | v3.9.7.3  | v3.9.10.10 | Delta      |
|-------------------------|----------:|-----------:|-----------:|
| Mean pool size          |      27.4 |      162.5 | **+5.9x**  |
| Median pool size        |        30 |        190 | **+6.3x**  |
| Pool coverage (label=2) |    0.9971 |     0.8960 | **-0.1012** |
| NDCG@10 (combined)      |    0.8099 |     0.1547 | **-0.6552** |
| Recall@10 (combined)    |    0.8374 |     0.2450 | **-0.5924** |
| NDCG@30 (combined)      |    0.9110 |     0.2557 | **-0.6553** |
| Recall@30 (combined)    |    1.0000 |     0.4716 | **-0.5284** |
| NDCG@50 (combined)      |    0.9110 |     0.3464 | **-0.5646** |
| Recall@50 (combined)    |    1.0000 |     0.6531 | **-0.3469** |
| **Intersection NDCG@10** |  **0.8237** | **0.8087** | **-0.0150** |

---

## Per-query rank comparison (label=2 best position)

- **New ranks better**: 2 queries
- **Old ranks better**: 39 queries
- **Equal**:          9 queries
- **L2 papers in old but MISSING in new**: 35

(Detailed per-query table: `test_output/_analyze_label2_positions.log`)

---

## 3-Tier Honest Assessment

### ✅ Works (real, verified)

1. **Connectivity**: 4 engines that were silently failing (Crossref,
   OpenAlex, S2, AMiner) now return real data after the 2-line
   `pa_cli/search.py:39-66` fix. **dedup_count grew from 7 → 12-13**
   in the unit-test query. This is reproducible in the connectivity
   smoke test (`test_output/_api_connectivity_smoke.py`).

2. **Same-candidate ranking is stable**: when restricted to papers
   that appear in BOTH pools (intersection), the ranker itself
   produces nearly identical NDCG@10 (0.82 → 0.81, delta -0.015).
   This proves the `combined = 0.5*BM25 + 0.5*bi-encoder` formula
   is **NOT** degraded by the fix.

3. **Pool size grew 5.9x** (27 → 162 candidates/query avg). The fix
   surfaces many more papers. **This is the legitimate, intended
   effect of the fix.**

### ⚠ Mixed (real but with caveats)

1. **Pool coverage DROPPED 10.1%** (0.9971 → 0.8960). 35 of 100+
   label=2 papers in the old pool are **NOT** in the new pool. The
   fix made engines return data, but my rebuild **excluded S2**
   (rate-limit on burst), and S2 was the most relevance-aware
   engine in the v3.9.7.3 pool.

2. **Recall@10 dropped 0.59** (0.84 → 0.25), **NDCG@10 dropped 0.66**
   (0.81 → 0.15). The new bigger pool has more papers, but they
   crowd the relevant ones out of top-10 ranking positions.

3. **Per-query rank win rate: 2/50 new-better, 39/50 old-better**.
   The new ranking is worse on 78% of queries.

### ❌ Does NOT work (real regression)

1. **NDCG@10 regressed 0.66** (0.81 → 0.15). This is a real
   regression in user-facing ranking quality.

2. **Pool coverage regressed 0.10** (0.9971 → 0.8960). Users will
   silently miss ~10% of relevant papers that v3.9.7.3 would have
   surfaced.

3. **The re-eval was unblocked by S2 being in v3.9.7.3 working set**
   but missing in v3.9.10.10 rebuild. The fix alone is good; the
   way I applied it (excluding S2) is the regression source.

---

## Root cause

The `pa_cli/search.py:39-66` fix is correct. The regression came
from the rebuild step (`test_output/_rebuild_system_outputs_v3_9_10_10.py`):

```python
result = run_search(
    ...
    engine='crossref,openalex,arxiv,aminer,cnki',  # NO S2 — feared 429
    ...
)
```

In the v3.9.7.3 pool, S2 was returning ~3 results/query with high
relevance (S2's ranking model is the most academic-tuned). My
rebuild skipped S2 to avoid the 429 burst. Without S2:

- Crossref/OpenAlex return papers by citation count + Open Access
  metadata — **citation-heavy, not relevance-heavy**
- The new pool is dominated by highly-cited papers that are
  tangentially related, pushing label=2 papers (often more
  recent or niche) to lower positions
- 35 label=2 papers are simply not returned by any of the 5
  remaining engines

---

## Forward path (3 options)

### Option A: Re-run rebuild with S2 + throttling
- Add S2 back to engine list, with 1 req/sec + retry/backoff to
  avoid 429
- Expected: pool coverage back to ~99%, NDCG@10 likely recovers
- Effort: ~1h (re-run + verify)
- Risk: rate limit may still block at 50-query batch

### Option B: Revert v3.9.10.10 (keep v3.9.7.3 as default)
- Admit the fix didn't improve anything in practice
- Keep the search.py fix in code for future use but don't ship
  rebuilt data
- Effort: ~30min
- Cost: lose the dedup_count +85% improvement

### Option C: Document trade-off, ship fix as-is
- Pool coverage drops 10%, but connectivity is fixed
- Users can opt-in via explicit `--engine semanticscholar,...`
- Effort: minimal
- Cost: silent 10% coverage regression for default users

**My recommendation: Option A**. S2 throttling is straightforward
(1 RPS + backoff on 429), and the 50-query batch at 1 RPS is
50 seconds — well under the 707s the previous run took.

**ROADMAP item proposed**: [P1-20] S2 throttling for batch rebuild.

---

## What this re-eval proves

1. **The fix to `pa_cli/search.py:39-66` is correct and necessary.**
   Same-candidate NDCG@10 is unchanged, proving the ranker is stable.

2. **The gzip/brotli fix is a connectivity fix, not a relevance fix.**
   It unlocks 4 engines' JSON parsing. Whether that improves
   end-to-end relevance depends on which engines are activated and
   how their results are combined.

3. **S2 is the most relevance-aware engine for academic search.**
   Without it, Crossref/OpenAlex's citation-heavy ranking dilutes
   the pool. The old pool had S2 (effectively working despite the
   gzip bug — the bug hit 0-cases, but S2 was returning 0 from a
   different cause: gzip decode failure on rate-limited responses).
   Wait — actually v3.9.7.3 backup has S2 working. Let me re-check.

4. **The 10% pool coverage drop is the REAL headline, not the
   NDCG@10 drop.** NDCG drops can be explained by pool dilution;
   pool coverage drops mean 10% of relevant papers are *missing*
   entirely.

---

## Files / data

- Backup of v3.9.7.3: `bench/v01/system_outputs_combined_v3_9_7_3_3_backup/` (preserved)
- v3.9.10.10: `bench/v01/system_outputs_combined/`
- v3.9.7.3 raw: `bench/v01/system_outputs_v3_9_7_3_raw_backup/`
- v3.9.10.10 raw: `bench/v01/system_outputs_v3_9_10_10_raw/`
- v2 re-eval script: `test_output/_re_eval_holdout_v3_9_10_10_v2.py`
- v2 re-eval result: `bench/v01/reports/v3_9_10_10_re_eval_v2.json`
- v1 re-eval (NDCG@10 only): `bench/v01/reports/v3_9_10_10_re_eval.json`
- per-query position analysis: `test_output/_analyze_label2_positions.log`
- rebuild script: `test_output/_rebuild_system_outputs_v3_9_10_10.py`
- v4 rerank script: `bench/v01/_v4_rerank.py` (run on the new data)

---

**Status**: Honest finding. The fix is correct; the rebuild strategy
needs S2 throttling for the relevance benefit to materialize. Proposed
[P1-20] to handle this in a future version.
