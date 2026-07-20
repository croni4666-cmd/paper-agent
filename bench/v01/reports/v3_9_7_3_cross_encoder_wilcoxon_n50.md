# v3.9.7.3 Wilcoxon — Cross-encoder (BGE-reranker) vs Biencoder on n=48

> Generated 2026-07-15. Source: `v3_9_7_3_cross_encoder_n50.json`
> Label source: n50_mixed (q001-q025 real + q026-q050 A2 auto)
> Auto labels use BGE as tie-breaker (A2 hybrid) — small positive bias for BGE

## Aggregate paired metrics

| Metric | Biencoder mean | BGE mean | delta mean | Wilcoxon stat | p-value | Significant (α=0.05) |
|---|---:|---:|---:|---:|---:|:---:|
| NDCG@10 | 0.8016 | 0.6952 | -0.1064 | 270.0 | 0.0008 | ✅ yes |
| Recall@10 | 0.7655 | 0.6783 | -0.1442 | 123.0 | 0.0409 | ✅ yes |
| Precision@10 | 0.4979 | 0.4562 | -0.0690 | 135.5 | 0.0750 | ❌ no |

## Cross-version comparison

| Version | n (paired) | biencoder NDCG@10 | BGE NDCG@10 | Δ NDCG@10 | Wilcoxon p (NDCG) | Notes |
|---|---:|---:|---:|---:|---:|---|
| v3.9.3 (original) | 25 | 0.7205 | 0.6928 | -0.0277 | not run | baseline |
| v3.9.7.1 (re-eval) | 25 | 0.7205 | 0.6928 | -0.0277 | 0.5424 (n.s.) | same candidates as v3.9.3 |
| v3.9.7.2 (n=50 nominal / n=25 actual) | 25 | 0.7572 | 0.7192 | -0.0380 | 0.3525 (n.s.) | new candidates from v4_rerank n=50 |
| v3.9.7.3 (n=48 with auto labels) | 48 | 0.8016 | 0.6952 | **-0.1064** | **0.000825 (sig.)** | auto labels include BGE as tie-breaker (small +bias) |

**Interpretation** (per memory discipline, corrected 2026-07-20):
- ✅ Δ = -0.1064 is bigger than v3.9.7.1/2's -0.03 to -0.04 — at n=48, Wilcoxon p=0.000825 is now **statistically significant** at α=0.05
- ✅ Sample size doubled (25→48) reveals what n<100 noise was hiding: BGE-rerank is **significantly worse** than bi-encoder on academic abstracts
- ⚠️ Auto-label circularity (BGE used as A2 tie-breaker) gives BGE a small +bias — true gap is **larger** than -0.1064
- ❌ "BGE does NOT clearly beat biencoder" — corrected to: **BGE-rerank significantly loses to bi-encoder on n=48 academic benchmark (Wilcoxon p=0.000825, two-sided)**
- ❌ "LTR is the better path forward" — corrected to: see v3_9_7_3_ltr_n50.json, LTR (LambdaMART 100 trees) **also loses to combined baseline** by -0.0335 NDCG@10 at n=50. The correct path is: drop BGE, deprecate LTR for n<200, use combined (0.5*BM25 + 0.5*bi-encoder) as default.

**Audit trail**: this MD originally (2026-07-15) mis-read the JSON's p=0.000825 as "n.s. due to n<100". The same Mavis session that wrote v3.9.7.2 (also mis-diagnosed labels缺口 vs code bug) repeated the pattern of trusting a summary number over the source JSON. Re-verified 2026-07-20 via `test_output/_verify_wilcoxon_recompute.py` against the same per_query_ndcg dict.
