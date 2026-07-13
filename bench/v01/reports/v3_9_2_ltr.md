# v3.9.2 LTR (LambdaMART) Rerank Report

> Generated 2026-07-13 by `pa_cli/ltr.py` per ROADMAP [P0-6].
> 5-fold CV over 25 queries, per-query group, 3-level labels.

## Summary

- **n_queries**: 25
- **n_labeled_pairs**: 726
- **n_folds**: 5
- **features**: 8 (bm25_score, biencoder_score, combined_score, prf_score, log_cite_count, year, is_recent, has_abstract)

## Side-by-side: LTR vs combined baseline

| Method | NDCG@10 | Recall@10 | Precision@10 |
|---|---:|---:|---:|
| **LTR (LambdaMART)** | **0.7192 ± 0.0959** | **0.6174** | **0.4640** |
| combined (linear 0.5/0.5) | 0.7227 | 0.7051 | 0.4920 |
| **Δ (LTR − baseline)** | **-0.0034** | **-0.0877** | **-0.0280** |

## Honest interpretation (per memory discipline)

**Δ NDCG@10 = -0.0034** on n=25 queries, n<100 deltas, no significance test, no holdout. 
Per `MEMORY.md` discipline 'Don't overclaim n<100 metric deltas':
- This delta is within the noise band of n=25 with no statistical test.
- It is NOT a 'finding' or 'insight' — it's a single point estimate.
- Direction matters (LTR should not hurt), but magnitude is not a useful negative result.

**Status**: ✅ LTR architecture works (training + prediction + per-query CV + reporting pipeline).
**Status**: ⚠️ Δ magnitude not statistically validated.

## Per-fold metrics

| Fold | n_train_q | n_test_q | NDCG@10 | Recall@10 | Precision@10 |
|---:|---:|---:|---:|---:|---:|
| 0 | 20 | 5 | 0.7760 | 0.6491 | 0.6400 |
| 1 | 20 | 5 | 0.7099 | 0.3770 | 0.4400 |
| 2 | 20 | 5 | 0.5362 | 0.5941 | 0.3000 |
| 3 | 20 | 5 | 0.7863 | 0.7399 | 0.4000 |
| 4 | 20 | 5 | 0.7878 | 0.7267 | 0.5400 |

## Feature importance (gain)

| Feature | Avg gain |
|---|---:|
| `combined_score` | 309.86 |
| `biencoder_score` | 298.77 |
| `log_cite_count` | 147.65 |
| `bm25_score` | 134.73 |
| `prf_score` | 111.89 |
| `year` | 80.12 |
| `has_abstract` | 7.12 |
| `is_recent` | 1.37 |

## Per-query LTR vs baseline (top 5 best, top 5 worst)

| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |
|---|---:|---:|---:|
| q012 | 0.8982 | 0.6831 | **+0.2152** |
| q010 | 1.0000 | 0.7889 | **+0.2111** |
| q025 | 0.6503 | 0.5477 | **+0.1026** |
| q009 | 0.6769 | 0.5914 | **+0.0855** |
| q013 | 0.4844 | 0.4086 | **+0.0758** |

| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |
|---|---:|---:|---:|
| q022 | 0.3027 | 0.4179 | -0.1152 |
| q005 | 0.7442 | 0.8741 | -0.1298 |
| q020 | 0.6483 | 0.7968 | -0.1485 |
| q004 | 0.5394 | 0.7861 | -0.2467 |
| q006 | 0.7120 | 0.9594 | -0.2474 |

## Configuration

```python
LTRConfig(
    objective='lambdarank',
    metric='ndcg',
    n_estimators=100,
    learning_rate=0.05,
    num_leaves=31,
    min_data_in_leaf=5,
    feature_fraction=0.9,
    bagging_fraction=0.8,
    bagging_freq=5,
    label_gain=[0, 1, 3],
    random_state=42,
    verbose=-1,
)
```

## 3-tier honest audit (per MEMORY.md discipline)

- ✅ **Verified on real data**: code runs end-to-end on 25 v3.9.0 queries, 5-fold CV produces per-fold metrics, report generated.
- ✅ **Verified architecture**: LTR + LightGBM training pipeline, feature engineering, per-query group CV all functional.
- ⚠️ **Code exists but unverified metric magnitude**: Δ NDCG@10 = -0.0034 on n=25, no significance test, no holdout.
- ❌ **NOT a 'finding' or 'insight'**: per memory discipline, single point estimates on n<100 are noise, not signal.

## 5-check Global Rule audit

1. ✅ Runs for $0 (lightgbm + numpy + pandas pure local)
2. ✅ No hosted service
3. ✅ Maintenance: ~350 LOC new in pa_cli/ltr.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: no third-party API used
