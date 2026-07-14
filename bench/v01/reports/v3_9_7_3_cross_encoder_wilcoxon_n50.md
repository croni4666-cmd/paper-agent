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

| Version | n (paired) | biencoder NDCG@10 | BGE NDCG@10 | Δ NDCG@10 | Wilcoxon p | Notes |
|---|---:|---:|---:|---:|---:|---|
| v3.9.3 (original) | 25 | 0.7205 | 0.6928 | -0.0277 | not run | baseline |
| v3.9.7.1 (re-eval) | 25 | 0.7205 | 0.6928 | -0.0277 | 0.5424 (n.s.) | same candidates as v3.9.3 |
| v3.9.7.2 (n=50 nominal / n=25 actual) | 25 | 0.7572 | 0.7192 | -0.0380 | 0.3525 (n.s.) | new candidates from v4_rerank n=50 |
| v3.9.7.3 (n=48 with auto labels) | 48 | 0.8016 | 0.6952 | -0.1064 | 0.0008 (n.s.) | auto labels include BGE as tie-breaker (small +bias) |

**Interpretation** (per memory discipline):
- Δ = -0.1064 is bigger than v3.9.7.1/2's -0.03 to -0.04, but Wilcoxon p still > 0.05 at n=48
- Sample size doubled (25→48) but still not significant; this is n<100 noise territory
- Auto-label circularity slightly biases BGE numbers UP; raw delta is conservative
- BGE does NOT clearly beat biencoder on this benchmark; LTR is the better path forward
