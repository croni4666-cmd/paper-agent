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
| **LTR (LambdaMART)** | **0.7323 ± 0.0800** | **0.6628** | **0.4680** |
| combined (linear 0.5/0.5) | 0.7227 | 0.7051 | 0.4920 |
| **Δ (LTR − baseline)** | **+0.0096** | **-0.0423** | **-0.0240** |

## Honest interpretation (per memory discipline)

**Δ NDCG@10 = +0.0096** on n=25 queries, n<100 deltas, no significance test, no holdout. 
Per `MEMORY.md` discipline 'Don't overclaim n<100 metric deltas':
- This delta is within the noise band of n=25 with no statistical test.
- It is NOT a 'finding' or 'insight' — it's a single point estimate.
- Direction matters (LTR should not hurt), but magnitude is not a useful negative result.

**Status**: ✅ LTR architecture works (training + prediction + per-query CV + reporting pipeline).
**Status**: ⚠️ Δ magnitude not statistically validated.

## Per-fold metrics

| Fold | n_train_q | n_test_q | NDCG@10 | Recall@10 | Precision@10 |
|---:|---:|---:|---:|---:|---:|
| 0 | 20 | 5 | 0.7955 | 0.6777 | 0.6600 |
| 1 | 20 | 5 | 0.7180 | 0.5839 | 0.4600 |
| 2 | 20 | 5 | 0.5819 | 0.5941 | 0.3000 |
| 3 | 20 | 5 | 0.7775 | 0.7352 | 0.4000 |
| 4 | 20 | 5 | 0.7886 | 0.7233 | 0.5200 |

## Feature importance (gain)

| Feature | Avg gain |
|---|---:|
| `combined_score` | 325.88 |
| `biencoder_score` | 282.89 |
| `log_cite_count` | 169.33 |
| `bm25_score` | 152.82 |
| `year` | 87.53 |
| `prf_score` | 58.59 |
| `has_abstract` | 7.33 |
| `is_recent` | 1.78 |

## Per-query LTR vs baseline (top 5 best, top 5 worst)

| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |
|---|---:|---:|---:|
| q013 | 0.6831 | 0.4086 | **+0.2744** |
| q010 | 1.0000 | 0.7889 | **+0.2111** |
| q012 | 0.8693 | 0.6831 | **+0.1862** |
| q001 | 0.5072 | 0.3820 | **+0.1252** |
| q009 | 0.6910 | 0.5914 | **+0.0996** |

| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |
|---|---:|---:|---:|
| q024 | 0.6668 | 0.7472 | -0.0804 |
| q022 | 0.2839 | 0.4179 | -0.1340 |
| q006 | 0.8022 | 0.9594 | -0.1572 |
| q014 | 0.6436 | 0.8167 | -0.1731 |
| q004 | 0.5551 | 0.7861 | -0.2310 |

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
- ⚠️ **Code exists but unverified metric magnitude**: Δ NDCG@10 = +0.0096 on n=25, no significance test, no holdout.
- ❌ **NOT a 'finding' or 'insight'**: per memory discipline, single point estimates on n<100 are noise, not signal.

## 5-check Global Rule audit

1. ✅ Runs for $0 (lightgbm + numpy + pandas pure local)
2. ✅ No hosted service
3. ✅ Maintenance: ~350 LOC new in pa_cli/ltr.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: no third-party API used
