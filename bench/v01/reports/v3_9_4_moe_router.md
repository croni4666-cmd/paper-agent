# v3.9.4 MoE Router Training Report

> Generated 2026-07-13 by `pa_cli/moe_router.py` per ROADMAP [P1-11].
> 5-class multi-class classifier (LightGBM) predicting dominant engine per query.

## Method

- **Engines** (5 classes): arxiv, openalex, s2, crossref, core
- **Label per query**: engine with most `label=2` candidates in top-10
- **Features**: TF-IDF (max 5000, bigrams) + 6 query metadata features
- **Classifier**: LGBMClassifier (5-class, multi-class)
- **Validation**: 5-fold CV over queries

## Training data — SEVERE class imbalance

| Engine | # queries (label=2 in top-10) |
|---|---:|
| `arxiv` | 0 |
| `openalex` | 24 |
| `s2` | 0 |
| `crossref` | 1 |
| `core` | 0 |
| **Total** | **25** |

⚠️ **24/25 = 96% of queries have `openalex` as dominant engine.**
This is single-engine-dominated. The classifier effectively learns 'always predict openalex'.

## 5-fold CV (per-query group)

| Fold | n_train | n_test | Accuracy |
|---:|---:|---:|---:|
| 0 | 20 | 5 | 1.0000 |
| 1 | 20 | 5 | 1.0000 |
| 2 | 20 | 5 | 1.0000 |
| 3 | 20 | 5 | 0.8000 |
| 4 | 20 | 5 | 1.0000 |
| **Mean** | — | — | **0.9600 ± 0.0800** |

## Honest metric comparison (per MEMORY.md discipline)

| Baseline | Accuracy | Notes |
|---|---:|---|
| Random uniform (1/5) | 0.2000 | Theoretically naive |
| **Majority class (openalex)** | **0.9600** | **Trivial: always predict dominant class** |
| MoE router (5-fold CV) | 0.9600 | LightGBM trained on TF-IDF + metadata |

**The 0.96 MoE accuracy is essentially the majority-class baseline (0.96).**
The model has not learned meaningful routing — it has learned 'openalex wins'.

Lift over random is +0.76, but lift over majority-class baseline is:
- MoE − majority-class = +0.0000

**Conclusion**: MoE architecture is sound, but n=25 with 96% openalex dominance
provides no signal to learn a meaningful router. We need either:
1. **More diverse queries** (q026-q050 expected) — to have more non-openalex dominant queries
2. **Per-class weighting** to balance the loss function
3. **Multi-label approach** (each engine gets a 0/1 label) instead of multi-class

## Per-class accuracy (averaged across folds)

| Engine | Accuracy | n_test_total |
|---|---:|---:|
| `arxiv` | (no test samples) | 0 |
| `openalex` | 1.0000 | 5 |
| `s2` | (no test samples) | 0 |
| `crossref` | 0.0000 | 1 |
| `core` | (no test samples) | 0 |

## 3-tier honest audit (per MEMORY.md discipline)

- ✅ **Verified on real data**: pipeline runs end-to-end on v3.9.0 25 queries
- ✅ **Verified architecture**: multi-class classifier trains, predicts per-engine probabilities, weights sum to 1
- ⚠️ **Code exists but unverified metric magnitude**: 0.96 accuracy is misleading — equals majority-class baseline
- ❌ **NOT a 'finding' or 'insight'**: model has not learned routing; it has memorized 'openalex wins'

## 5-check Global Rule audit

1. ✅ Runs for $0 (lightgbm + sklearn pure local)
2. ✅ No hosted service
3. ✅ Maintenance: ~250 LOC new in pa_cli/moe_router.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if MoE classifier fails, fall back to round-robin

## Layer architecture

MoE router sits at **Layer 1 (Source pool) + Layer 2 (Recall)** as the per-query engine weight predictor.
Replaces 5-engine round-robin with learned per-engine weights.
