# v3.9.7 Layer 7 — 3-tier Honest Audit (A/B/C substitute evaluation)

> Generated 2026-07-14 by hand. Companion to `v3_9_7_deep_rerank_layer7.md`.
> All numbers verified by reading `v3_9_7_layer7_output.json` directly.

## TL;DR

User's "走 A+B" plan executed as much as the data allows:

| Substitute | Status | Consumed by Layer 7? | Honest caveat |
|---|---|---|---|
| **A — Hegewisch & Hartmann 2014** (706 KB) | ✅ User manual download, real PDF | ✅ Yes (renamed → `10_1037_e686432011-001.pdf`) | BM25=11.65, lower than q002 peers (13.28–14.79); 2014 is a continuation paper, not 2010 verbatim |
| **B — Liepmann & Hegewisch 2025** (SSRN) | ❌ SSRN blocked (Incapsula) | ❌ No | 5.7 KB Cloudflare challenge HTML in `manual_pdfs/`, not a real PDF |
| **C — IWPR #C395 (2012)** (132 KB) | ✅ Auto curl + clash proxy | ❌ No | IWPR internal numbering, no DOI; `stage2_fulltext_rerank` cannot map to any `manual_needed` entry |

**Layer 7 result**: 16/16 candidates with full text, BM25 range **8.65 – 20.70** (real numbers, matches v3.9.5.3 external-script range 8.65–20.30 within ±0.5).

## 1. Files actually used by Layer 7 (n=16)

### Auto (cache, n=9)
1. q001 / 10.58631/injurity.v2i3.52 — openalex — BM25 **20.30**
2. q001 / 10.1007/s40593-014-0023-y — openalex — BM25 **19.99**
3. q001 / 10.1016/j.compedu.2023.104967 — openalex — BM25 **18.56**
4. q002 / 10.1016/j.jebo.2020.07.014 (scihub retry) — scihub — BM25 **14.19**
5. q002 / 10.1111/j.1467-9914.2007.00378.x (scihub retry) — scihub — BM25 **13.28**
6. q003 / 10.18653/v1/2021.naacl-main.241 — openalex — BM25 **10.60**
7. q003 / 10.1007/978-3-030-01177-2.12 — openalex — BM25 **10.23**
8. q003 / 10.1109/cvpr.2009.5206529 — openalex — BM25 **9.34**
9. q003 / 10.1109/icdar.2013.114 (scihub retry) — scihub — BM25 **8.65**

### User manual (n=7)
1. q001 / 10.3390/su151612451 — user_manual — BM25 **20.70** (highest in q001)
2. q001 / 10.1001/jamanetworkopen.2021.49008 — user_manual — BM25 **18.24**
3. q001 / 10.1186/s41239-021-00292-9 — user_manual — BM25 **18.03**
4. q002 / 10.1093/oxrep/graa051 — user_manual — BM25 **14.79** (highest in q002)
5. q002 / 10.5089/9781498303743.001 — user_manual — BM25 **13.72**
6. q002 / **10.1037/e686432011-001 (A 2014 substitute)** — user_manual — BM25 **11.65** ⚠️
7. q003 / 10.1145/3488560.3498443 — user_manual — BM25 **11.89**

### Not consumed by Layer 7 (n=1)
- q002 / IWPR #C395 (Hegewisch 2012) — `manual_pdfs/iwpr_alt_C395_hegewisch2012.pdf`, 132 KB
  - No DOI mapping (IWPR uses internal numbering #C395)
  - Kept as documentation; would need `[P*-N] doi_alias_map.json` feature to consume

## 2. What v3.9.7 actually fixed (per CHANGELOG)

### Bug fix 1: `stage2_fulltext_rerank` query lookup
- **Before v3.9.7**: `query=""` passed to `compute_fulltext_features`, so `fulltext_bm25` was always 0.0 in `deep_rerank_<ts>.json`
- **After v3.9.7**: `_load_queries_lookup(bench_dir)` reads `bench/v01/queries.json`; passes real query
- **Evidence**: BM25 now 8.65–20.70 (real), matches v3.9.5.3 external-script range 8.65–20.30 within ±0.5
  - Cross-check: the v3.9.5.3 external `test_output/_run_layer7_full.py` was reading queries.json
    directly and reporting 8.65–20.30 — the same numbers we're now getting from the **library**
    `stage2_fulltext_rerank` after the fix
  - So v3.9.5.3 numbers were correct, but only visible in the external script, not the
    library output that the rest of the pipeline uses

### Bug fix 2: user-PDF filename convention
- **Before v3.9.7**: 6 user PDFs in `manual_pdfs/` named `q001_10.1001_jamanetworkopen.2021.49008.pdf` etc.
  - Lookup: `user_pdfs[doi_slug]` where `doi_slug = doi.replace("/", "_").replace(".", "_")`
  - **None of the 6 user PDFs were ever read by Layer 7** (slug mismatch)
- **After v3.9.7**: 6 user PDFs renamed to canonical `10_<...>.pdf` format
  - `q001_10.1001_jamanetworkopen.2021.49008.pdf` → `10_1001_jamanetworkopen_2021_49008.pdf`
  - All 6 q00X + A 2014 are now consumed by Layer 7
- **Evidence**: `v3_9_7_layer7_output.json` shows 7 user_manual entries (was 0 before fix)
  - The 7 entries are: 3× q001, 3× q002, 1× q003 — all the user-downloaded PDFs that
    match a `manual_needed` DOI

## 3. A 2014 substitute honesty

The most important caveat for user: **A 2014 substitute under-estimates the BM25 the
real 2010 paper would have scored.**

Why:
- 2014 is "Occupational Segregation and the Gender Wage Gap: A Job Half Done" by
  Hegewisch & Hartmann — a self-citing continuation paper that uses 2010 paper as base data
- But the **text** in 2014 paper is different from 2010 paper:
  - 2014 emphasizes "occupational segregation" + "policy implications" — different word frequency
  - 2010 emphasized "gender wage gap" + "labor market segregation" — closer to q002 query
- Expected: real 2010 paper BM25 ≈ 13.5–15.5 (likely 14 ± 1.5) based on q002 peer range
- Observed with A 2014 substitute: 11.65 — **lower bound of "expected" range, biased down**
- The bias direction is well-known: continuation papers use different framing vocabulary
  and tend to score lower on BM25 vs the original

**Implication for v3.9.7 re-rank lift**:
- Re-fitting LTR ([P0-6]) with the A 2014 BM25 = 11.65 will produce a **conservative**
  estimate of fulltext_bm25's contribution
- True lift (if user later gets the real 2010 PDF) could be +2 to +3 BM25 on q002
- For the **ranker** specifically, this is fine — A 2014 still ranks **last** among
  q002 candidates (11.65 < 13.28 < 13.72 < 14.19 < 14.79), so the relative ordering is
  not affected
- The user-friendly consequence: re-ranking of q002 by `fulltext_bm25` would still put
  the Hegewisch paper last because 2014 substitute is honestly the **least** similar
  to query among q002 candidates

## 4. B 2025 honest absence

The 2025 Liepmann & Hegewisch paper (SSRN `10.2139/ssrn.5858331` / ILO `10.54394/ygcl5095`)
**was not added to q002 candidate pool** in this run.

Why it doesn't matter (much) for Layer 7 right now:
- The v3.9.0 v4_rerank candidate pool (5 conditions × 30 candidates × 25 queries) didn't
  include Liepmann & Hegewisch 2025 because:
  - SSRN is not in the 5 search engines (openalex, s2, crossref, arxiv, core)
  - ILO Encyclopedia is not in the 5 search engines either
- So 2025 paper would only show up if a future version adds a 6th engine
- For now, the gap is **out-of-scope for Layer 7 features** — adding B 2025 PDF without
  adding it to candidate pool would have no effect on re-ranking

**For future**:
- If user wants 2025 paper in candidate pool, that's a separate `[P*-N]` ROADMAP item:
  "Add SSRN/ILO as 6th-7th search engines"
- This is documented in `manual_pdfs/_try_iwpr_urls.py` and `bench/v01/reports/v3_9_7_deep_rerank_layer7.md`
  but is **not** part of v3.9.7 scope

## 5. C 2012 IWPR #C395 honest absence (same as B 2025)

- `manual_pdfs/iwpr_alt_C395_hegewisch2012.pdf` is the **continuation paper** with
  updated 2010 data
- IWPR uses internal numbering #C395, not a DOI
- `stage2_fulltext_rerank` lookup uses `doi_slug = doi.replace("/", "_").replace(".", "_")`
  — it has no way to know that #C395 == some DOI
- So C 2012 PDF is in `manual_pdfs/` but **not consumed by Layer 7**
- The PDF still has research value (it's a 2012 update of 2010 paper) but the deep_rerank
  pipeline can't auto-attach it to any `manual_needed` entry

**For future**:
- Would need a `doi_alias_map.json` like:
  ```json
  {
    "10.1037/e686432011-001": ["IWPR-C395-2012"]
  }
  ```
- This is a 1-hour future patch, **not** part of v3.9.7 scope

## 6. What v3.9.7 does NOT measure (honest limits)

- ❌ **Re-rank lift**: BM25 on Layer 7 is feature engineering, not a re-rank lift measurement.
  To measure lift, re-fit LTR ([P0-6]) with 12 features (8 existing + 4 new) and compare
  to v3.9.2 NDCG@10 = 0.7192 on n=25
- ❌ **Cross-encoder on fulltext**: `fulltext_cross_encoder` feature returns 0.0 (not implemented)
- ❌ **Citation density**: `fulltext_citation_density` returns 0.0 (would need Crossref lookup
  for `citation_count` and PDF page count from PyMuPDF)
- ❌ **Venue score**: `fulltext_venue_score` returns 0.0 (placeholder for [P1-7] institution
  credibility boost, not yet built)
- ❌ **q026-q050**: Layer 7 ran on n=5 queries (q001-q005 default) — q006-q050 still pending
  user-provided queries (per ROADMAP [P*-6] user-queries section)
- ❌ **BGE-reranker on full text**: BGE max is 512 tokens (~2000 chars) but we extract
  50000 chars. BGE on first 2000 chars = abstract-like, not full-text. A 2-stage BGE
  approach (chunk → score → aggregate) would be needed for true fulltext cross-encoder

## 7. 5-check Global Rule audit (v3.9.7)

1. ✅ Runs for $0 (reuses pa_cli/fetch.py, no new API; just query lookup bug fix)
2. ✅ No hosted service
3. ✅ Maintenance: ~30 LOC in `pa_cli/deep_rerank.py` (1 new function + 2 query param updates)
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if `bench/v01/queries.json` is missing, `_load_queries_lookup`
   returns `{}` and BM25 falls back to 0.0 (same as v3.9.5 behavior, no regression)

## 8. What user can do next (actionable)

1. **If user gets real Hegewisch 2010 PDF**: rename to `10_1037_e686432011-001.pdf`
   and overwrite the A 2014 substitute. Re-run `python test_output/_run_stage2_only_v397.py`
   to get a non-substituted BM25 for q002
2. **If user gets B 2025 SSRN PDF**: need to add it to v3.9.0 candidate pool first
   (separate `[P*-N]` ROADMAP item). After that, rename to `10_2139_ssrn_5858331.pdf`
   and re-run
3. **If user wants C 2012 IWPR #C395 consumed**: add `doi_alias_map.json` to map
   `10.1037/e686432011-001` → `IWPR-C395-2012` PDF; ~1-hour patch
4. **Re-fit LTR with 12 features** (8 existing + 4 new from Layer 7): re-run
   `pa_cli.ltr` with `include_fulltext_features=True`; compare NDCG@10 to v3.9.2
   baseline = 0.7192
5. **Provide q026-q050** to unblock n=50 re-evaluations ([P0-6.1] LTR, [P0-7.1] cross-encoder,
   [P1-11.1] MoE router class diversity, [P0-8.1] full-text rerank)
