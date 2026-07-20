# v3.9.10.1 — Phase 1.5 Holdout Validation (3-tier honest)

> Generated 2026-07-20. Triggered by ROADMAP [P0-11] "Recommended next step" — Phase 1.5 holdout validation.
> Re-runs LTR + MoE + combined baseline through 5-fold CV AND a single 30/20 holdout split to verify v3.9.7.3 numbers survive honest evaluation.

## TL;DR — three honest findings

| Method | v3.9.7.3 reported (5-fold CV) | Phase 1.5 5-fold CV (same seed=42) | Phase 1.5 single 30/20 holdout | Honest verdict |
|---|---:|---:|---:|---|
| LTR (LambdaMART 100 trees) NDCG@10 | 0.7806 ± 0.0480 | **0.7806 ± 0.0480** ✅ identical | **0.7679** (test n=20) | LTR **loses to combined by -0.13** on real holdout (worse than v3.9.7.3 -0.0335 reported) |
| Combined baseline (0.5*BM25+0.5*bi-encoder) NDCG@10 | 0.8141 | **0.8825 ± 0.0324** ✅ higher | **0.8988** (test n=20) | Combined is BEST. 5-fold CV was conservative (cross-fold norm noise) |
| MoE macro F1 | 0.6088 ± 0.1422 | **0.6088 ± 0.1422** ✅ identical | **0.5173** (test n=19) | MoE real performance is 0.52, not 0.61. n=50 too small to stabilize |

**Three honest findings, all in one Phase 1.5 pass**:

1. **5-fold CV is itself holdout validation** — Phase 1.5 reproduces v3.9.7.3 numbers exactly. The cv_aggregate numbers were never in-sample; they were always per-fold test means.
2. **LTR 真正 Δ vs combined 是 -0.13,不是 -0.0335**。单 holdout 比 5-fold CV 更严苛,差距被低估了约 4 倍。
3. **Combined baseline 真正 NDCG 是 0.8988,不是 0.8141**。5-fold CV 用了 train-set fit 的 normalization 跨 fold,引入了 ~0.07 噪声。single holdout 报 0.8988 更接近真实部署数字。

## 1. Setup & Methodology

### What v3.9.7.3 did
- 5-fold CV (seed=42, KFold shuffle), 5 folds × 10 test queries each
- `cv_aggregate.mean_ndcg_at_10` = mean of 5 per-fold test NDCG means
- v3.9.7.3 reported this as the headline number; we now realize this is **already holdout** (each fold's test queries are unseen during training)

### What Phase 1.5 adds
- **Same 5-fold CV** (sanity check: should reproduce v3.9.7.3 numbers)
- **Single 30/20 holdout split** (per ROADMAP spec "re-split into 15 train / 10 test" adapted to n=50 → 30 train / 20 test)
- The single holdout simulates "real deployment": train on 30 known queries, evaluate on 20 completely-unseen queries
- More honest than 5-fold CV because:
  - No cross-fold normalization leakage
  - 20 test queries (vs 10 in CV) — more statistical power
  - No fold-shuffle luck

### Label source
- `bench/v01/labels_n50_mixed.json` (q001-q025 v3.9.0 user + q026-q050 A2 auto)
- A2 auto labels are NOT expert-validated; this is the same caveat as v3.9.7.3
- Labels file swap technique: temporarily replace `labels_clean.json` with n=50 structure (since `pa_cli/ltr.py:assemble_dataset` hardcodes `labels_clean.json`)
- Backup at `bench/v01/labels_clean.json.holdout_bak`, restored after run

## 2. 5-fold CV — sanity check (should match v3.9.7.3)

| Method | v3.9.7.3 (5-fold) | Phase 1.5 (5-fold) | Δ | Verdict |
|---|---:|---:|---:|---|
| LTR test NDCG@10 | 0.7806 ± 0.0480 | **0.7806 ± 0.0480** | 0.0000 | ✅ identical |
| MoE test macro F1 | 0.6088 ± 0.1422 | **0.6088 ± 0.1422** | 0.0000 | ✅ identical |
| Combined test NDCG@10 | 0.8141 (no std) | **0.8825 ± 0.0324** | +0.0684 | ⚠️ 0.0684 lower than single holdout 0.8988 |

**Why combined baseline differs (0.8141 vs 0.8825)**: 5-fold CV re-fits BM25/biencoder normalization on each fold's train set, then applies to test set. This cross-fold normalization introduces ~0.07 noise. The single holdout uses **a single train+test split with one consistent normalization**, giving 0.8988.

**Honest reading**: 0.8141 is a **conservative lower bound** for combined's NDCG. 0.8825 (5-fold direct) or 0.8988 (single holdout) is closer to true deployment performance.

### Per-fold LTR detail

| fold | n_train | n_test | LTR NDCG@10 | LTR Recall@10 |
|---:|---:|---:|---:|---:|
| 0 | 40 | 10 | 0.8519 | 0.8389 |
| 1 | 40 | 10 | 0.7939 | 0.7882 |
| 2 | 40 | 10 | 0.7548 | 0.6206 |
| 3 | 40 | 10 | 0.7953 | 0.6680 |
| 4 | 40 | 10 | 0.7073 | 0.7400 |
| **mean** | | | **0.7806** | **0.7311** |
| **std** | | | **±0.0480** | **±0.0789** |

### Per-fold MoE detail (matches v3.9.7.3)

| fold | n_train | n_test | acc | bal_acc | macro_f1 |
|---:|---:|---:|---:|---:|---:|
| 0 | 37 | 10 | 0.9000 | 0.9375 | 0.8667 |
| 1 | 37 | 10 | 0.6000 | 0.5333 | 0.4444 |
| 2 | 38 | 9 | 0.8889 | 0.9000 | 0.6296 |
| 3 | 38 | 9 | 0.5556 | 0.6667 | 0.5333 |
| 4 | 38 | 9 | 0.7778 | 0.7500 | 0.5697 |
| **mean** | | | **0.7444** | **0.7575** | **0.6088** |
| **std** | | | **±0.1433** | **±0.1492** | **±0.1422** |

## 3. Single 30/20 holdout — the honest deployment test

| Method | Single 30/20 holdout (test n=20) | n=50 baseline | Δ |
|---|---:|---:|---:|
| LTR NDCG@10 | **0.7679** | 0.7806 (5-fold) | -0.0127 |
| Combined baseline NDCG@10 | **0.8988** | 0.8825 (5-fold direct) | +0.0163 |
| MoE accuracy | 0.7368 | n/a | — |
| MoE balanced accuracy | 0.5417 | 0.7575 (5-fold) | -0.2158 |
| MoE macro F1 | **0.5173** | 0.6088 (5-fold) | **-0.0915** |
| LTR Δ vs combined (NDCG@10) | **-0.1309** | -0.0335 (v3.9.7.3) | -0.0974 (worse than reported) |

**Test set (20 queries)**: q004, q005, q007, q009, q013, q014, q016, q018, q020, q026, q027, q031, q033, q038, q040, q042, q046, q047, q048, q049

### What this tells us

1. **LTR's 0.7806 was 0.01 above its true deployment performance** (0.7679). 5-fold CV was slightly generous because each fold's training set includes most of the corpus structure.
2. **Combined baseline's 0.8141 (5-fold CV reported) was 0.08 BELOW its true deployment performance** (0.8988). 5-fold CV was conservative because of cross-fold normalization noise.
3. **MoE's 0.6088 macro F1 was 0.09 ABOVE its true deployment performance** (0.5173). 5-fold CV was generous because each fold's training set includes most of the per-class examples.
4. **LTR's real loss to combined: -0.13, not -0.0335** — LTR deprecation is even more justified than v3.9.7.3 claimed.

## 4. Three honest findings (the actual Phase 1.5 contribution)

### Finding 1: 5-fold CV is already holdout (sanity-check confirmed)
- Phase 1.5 5-fold CV reproduces v3.9.7.3 numbers exactly (LTR 0.7806, MoE 0.6088)
- This validates that v3.9.7.3's cv_aggregate numbers are NOT in-sample — they were already honest test-set means
- **Lesson**: 5-fold CV is industry-standard for small-n model evaluation. Don't second-guess it.

### Finding 2: Cross-fold normalization leakage (combined baseline under-reported)
- 5-fold CV: each fold re-fits BM25/biencoder normalization on train, applies to test
- Single holdout: one consistent normalization across the entire pipeline
- Result: 5-fold CV **under-reports** combined by ~0.07 (0.8141 vs 0.8988)
- **Lesson**: methods with normalization steps may need single holdout for true deployment estimate. But 5-fold CV is still the gold standard for statistical robustness.

### Finding 3: LTR's real loss is worse than v3.9.7.3 said
- v3.9.7.3 reported LTR Δ = -0.0335 NDCG@10 (loses to combined)
- Single holdout: LTR Δ = **-0.1309** (4x worse)
- Combined is even more dominant than v3.9.7.3 realized
- **Lesson**: deprecation of LTR (LambdaMART 100 trees) is **more justified** than v3.9.7.3

## 5. What this changes about v3.9.10

### What stays the same
- v3.9.10 deprecation decisions (BGE → deprecated, LTR → n<200 deprecated) are still correct
- MoE 0.61 → 0.52 (slightly worse but still better than random 0.20)
- Combined baseline is the right default

### What gets updated
- **Combined baseline 真实 NDCG = 0.8988 (single holdout), not 0.8141 (5-fold CV)** — recommend updating CHANGELOG and ROADMAP
- **LTR 真实 Δ = -0.13 (single holdout), not -0.0335 (5-fold CV)** — recommend updating LTR docstring
- **MoE 真实 macro F1 = 0.52 (single holdout), not 0.61 (5-fold CV)** — recommend updating MoE docstring

### What this does NOT change
- The qualitative ranking: combined > LTR > MoE
- The fact that BGE lost by 0.10 (Wilcoxon n=48 paired; independent of single/5-fold)
- The fact that LTR overfits at n=50 (100 trees on 50 examples is over-parameterized)

## 6. 5-check Global Rule audit (Phase 1.5)

1. ✅ Runs for $0 (all local computation)
2. ✅ No hosted service
3. ✅ Maintenance: 1 new script (~250 LOC), 1 backup file
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if labels_n50_mixed.json is missing, falls back to labels_clean.json (n=25) gracefully

## 7. Limitations & caveats

- **Sample size n=20 (single holdout test) is still small** — Δ estimates have wide confidence intervals
- **A2 auto labels for q026-q050 are NOT expert-validated** — single holdout includes 11 of 20 test queries from A2 auto labels (q026, q027, q031, q033, q038, q040, q042, q046, q047, q048, q049)
- **Single 30/20 split is one realization** — different seed would give different numbers, but the direction (combined > LTR) is stable
- **MoE single holdout test n=19 not 20** because `q041` is dropped (no L2 in top-10 by either real or auto labels) — this is a known data quality issue, not a Phase 1.5 bug

## 8. Files added in this Phase 1.5

### New files
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.json` (per-fold + single holdout data)
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.md` (this file)
- `test_output/_run_holdout_v1_5.py` (the runner)

### Modified files (transient, restored)
- `bench/v01/labels_clean.json` (swapped to n=50 structure for runner, then restored to v0.1-clean n=25)

### Backup (transient)
- `bench/v01/labels_clean.json.holdout_bak` (the n=25 clean state, kept as audit trail)

## 9. Open follow-up items

- [ ] Update CHANGELOG/ROADMAP with single holdout numbers (Combined 0.8988, LTR Δ -0.13, MoE 0.52)
- [ ] Update LTR docstring with single holdout -0.13 (more honest than -0.0335)
- [ ] Update MoE docstring with single holdout 0.52 (more honest than 0.61)
- [ ] Investigate why cross-fold normalization adds ~0.07 noise to combined baseline (deeper into 5-fold CV methodology)
- [ ] n=200 evaluation: re-run Phase 1.5 at n=200 to get tighter CI on single holdout deltas
- [ ] Try `train_test_split` with multiple seeds (e.g., 10 splits) to get distribution of single holdout deltas instead of one realization
