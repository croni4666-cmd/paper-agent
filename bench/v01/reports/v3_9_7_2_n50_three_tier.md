# v3.9.7.2 n=50 — 3-tier Honest Audit

> Generated 2026-07-14 by hand. Continuation of HANDOFF_v3_9_7_2.md work.
> Reads all numbers directly from `bench/v01/reports/v3_9_7_2_*.{json,md}`.

## TL;DR — the n=50 audit trap

User's plan was "n=50 means we double the queries (q001-q050)". The reality:

| Pipeline step | What user thought | What actually ran | Why |
|---|---|---|---|
| v4_rerank (5 conditions) | n=50 rerank | **n=50 ✓** | Labels-free; just `system_outputs/*.json` → `system_outputs_*/.json` |
| MoE router | n=50 CV | **n=25** | `_dominant_engine_for_query` needs L2 label per query; q026-q050 have no labels |
| LTR (LambdaMART) | n=50 CV | **n=25** | `to_xyg(only_labeled=True)` drops q026-q050 (no L1/L2 labels) |
| Cross-encoder Wilcoxon | n=50 paired | **n=25** | BGE rerank runs on all 50 candidate sets, but metrics only computable for 25 with L2 |
| v4 eval (eval.py) | n=50 metrics | **n=25** | `missing_labels` filter; q026-q050 in `missing_labels` |

**The honest answer**: we have a **n=25 result with a n=50 candidate pool**. This is NOT the same as "n=50 result with statistical doubling of power". The Wilcoxon / MoE / LTR numbers below all rely on the same 25 labeled queries as v3.9.7.1.

**Two key things changed that affect every n=25 metric**:
1. **system_outputs_combined/ now has 50 .json files** (was 25). v4_rerank re-ranked q001-q025 on n=50 batch, so biencoder_score, bm25_score, v4_score all regenerated.
2. **Search API drift**: q001-q025 candidates are slightly different from v3.9.7.1's candidates (different timestamp, network state, possibly different top-30). This causes biencoder NDCG@10 to drift from 0.7205 → 0.7572 even though it's the same model.

## 1. v4_rerank n=50 — what's new

| Condition | n_files (was 25) | n_files (now) | Status |
|---|---:|---:|---|
| bm25 | 25 | **50 ✓** | reranked; top-3 has arXiv:2305.03642v3, 10.7210/jrsj.41.40, etc. |
| biencoder | 25 | **50 ✓** | reranked; cosine on (query, title+abstract) |
| combined | 25 | **50 ✓** | 0.5·BM25 + 0.5·biencoder (alpha=0.5) |
| prf | 25 | **50 ✓** | Rocchio top-5 expansion → re-BM25 |
| random | 25 | **50 ✓** | seeded shuffle (seed=42) |

- **Time**: ~5-8 min total (1-2 min/condition)
- **Method**: `bench/v01/_v4_rerank.py --condition {cond}`, no labels needed
- **Output dir**: `bench/v01/system_outputs_{bm25,biencoder,combined,prf,random}/q*.json`
- **Cleanup**: deleted 25 no-extension legacy files (`q001`, `q002`, …) from v3.9.0 era; restored via `git restore` after spotting the deletion in `git status`. Now all 5 dirs have 50 `.json` files matching v3.9.7.2 schema.

## 2. MoE router — n=25 actual

Source: `bench/v01/reports/v3_9_7_2_moe_router_n50.json`

| Metric | v3.9.7.1 n=25 | v3.9.7.2 "n=50" | Δ | Notes |
|---|---:|---:|---:|---|
| mean_accuracy | 0.96 | 0.96 | 0.00 | identical (same 25 queries) |
| mean_balanced_accuracy | 0.90 | 0.90 | 0.00 | identical |
| mean_macro_f1 | 0.889 | 0.889 | 0.00 | identical |
| label_distribution | {arxiv:0, openalex:24, s2:0, crossref:1, core:0} | (same) | 0 | no new engines fired in q026-q050 (could not — no labels) |

**Per-fold breakdown** (5-fold CV, same as v3.9.7.1):
- fold 0/1/2/4: acc=1.0, macro_f1=1.0 (all openalex, easy to predict)
- fold 3: acc=0.8, macro_f1=0.44 (the 1 crossref query in test fold breaks macro_f1)

**Honest reading**: This is **not a new result**; it's v3.9.7.1 n=25 re-run with `assemble_dataset` reading from the n=50 combined dir. The script correctly skipped q026-q050 (no L2 label → can't determine dominant engine). File `v3_9_7_2_moe_router_n50.json` carries a `note` field documenting this.

**Why class_weight='balanced' didn't help here**: even after balancing, support=0 classes (arxiv, s2, core) still get 0/0/0 metrics. The fundamental problem is the **3-engine-only state** (crossref, openalex, arxiv; s2 + core are disabled because demo API key is expired). v3.9.7.1 honest-3-tier-report already noted this: "no class diversity to balance".

## 3. Cross-encoder (BGE-reranker) — n=25 actual

Source: `bench/v01/reports/v3_9_7_2_cross_encoder_n50.json`, `v3_9_7_2_cross_encoder_wilcoxon_n50.json`

| Metric | v3.9.3 n=25 (old) | v3.9.7.1 n=25 (old) | v3.9.7.2 n=50 nominal (n=25 actual) |
|---|---:|---:|---:|
| Biencoder mean NDCG@10 | 0.7205 | 0.7205 | **0.7572** |
| BGE-rerank mean NDCG@10 | 0.6928 | 0.6928 | **0.7192** |
| Δ NDCG@10 (BGE − biencoder) | -0.0277 | -0.0277 | **-0.0380** |
| Wilcoxon p (NDCG@10) | not run | 0.5424 (n.s.) | **0.3525 (n.s.)** |
| Wilcoxon p (Recall@10) | not run | 0.7760 (n.s.) | **0.6413 (n.s.)** |
| Wilcoxon p (Precision@10) | not run | 0.8868 (n.s.) | **0.6784 (n.s.)** |

**Why Biencoder NDCG moved from 0.7205 → 0.7572** (Δ = +0.0367): not a method change. The underlying biencoder candidates (system_outputs_biencoder/*.json) were **re-generated** by v4_rerank n=50. Search API drift: same query → different top-30 candidates → different `biencoder_score` distribution → different NDCG ranking quality.

**Why BGE NDCG moved from 0.6928 → 0.7192** (Δ = +0.0264): same reason — BGE reranks the *new* top-30, and some label=2 papers that fell out of the old top-10 are now back in (or vice versa).

**Honest reading**:
- ✅ All three paired Wilcoxon tests still **not significant** at α=0.05
- ⚠️ The point estimate moved by 0.01-0.04 across versions, but all three are still in the same "noise zone" per n<100 discipline
- ❌ The cross-version comparison is **not interpretable** as "v3.9.7.2 has more BGE penalty than v3.9.7.1"; it's "search API drifted, all numbers shifted together"
- Per memory: **n<100 paired deltas = noise, not finding**. State p-values, don't claim insight.

## 4. LTR (LambdaMART) — n=25 actual

Source: `bench/v01/reports/v3_9_2_ltr.json` (re-run with n=50 combined → same n=25 active), copy saved as `v3_9_7_2_ltr_n50.json`

| Metric | v3.9.2 n=25 (old) | v3.9.7.2 "n=50" (n=25 actual) | Δ |
|---|---:|---:|---:|
| LTR (LambdaMART) NDCG@10 | 0.7192 ± 0.0959 | **0.7323 ± 0.0800** | +0.0131 |
| combined (0.5/0.5) baseline NDCG@10 | 0.7227 | 0.7227 | 0.0000 |
| Δ NDCG@10 (LTR − baseline) | -0.0034 | **+0.0096** | +0.0130 |
| LTR Recall@10 | 0.6174 | **0.6628** | +0.0454 |
| LTR Precision@10 | 0.4640 | **0.4680** | +0.0040 |

**Honest reading**:
- ✅ LambdaMART now beats combined baseline by +0.0096 NDCG@10 (v3.9.2 had LTR losing by -0.0034)
- ⚠️ But: combined baseline itself is unchanged (0.7227). The LTR lift comes from the new biencoder_score / v4_score features in the new candidates
- ⚠️ The "lift" of +0.013 NDCG@10 is **within n<100 noise**; per memory discipline, treat as a single point estimate, not a finding
- ❌ LTR **still** doesn't beat baseline by a margin that justifies its 100-tree training cost; the real win is the new biencoder scores, not LTR itself
- Per memory: state the lift factually; don't claim "LTR works now"

## 5. What v3.9.7.2 actually delivered (per 3-tier honest)

### ✅ Verified on real data
1. **v4_rerank pipeline runs on n=50** for all 5 conditions. 50 .json files per condition, top-3 inspection shows real candidates.
2. **MoE pipeline runs end-to-end on n=50 candidate pool** (skips 25 with no labels, trains on 25). No crashes, no schema errors.
3. **BGE-reranker pipeline runs on n=50 candidate sets**, with the same skipping behavior.
4. **Wilcoxon paired test** correctly reports n_paired = 25 (not 50) and gives p-values for all 3 metrics.
5. **LTR pipeline runs on n=50 candidate pool**, trains on 25 labeled queries, outputs NDCG@10 with std.
6. **Git restore safety net works**: deleted 25 no-ext files accidentally, `git restore` recovered them; no permanent damage to v3.9.0 lineage.

### ⚠️ Caveats
1. **n=50 nominal, n=25 actual** for every metric that requires labels. The "n=50" in filenames is a pipeline-level claim, not a statistical claim.
2. **Search API drift between v3.9.7.1 and v3.9.7.2** causes all n=25 metrics to shift by 0.01-0.04. Cross-version "comparisons" are not method comparisons; they are API-state comparisons.
3. **No significance test for LTR delta** of +0.0096. Per memory, n<100 metric deltas are noise.
4. **MoE class imbalance unchanged** — same 24/25 openalex ratio; class_weight='balanced' doesn't add new positive examples; only changes per-class weights, not the data.
5. **3 of 5 search engines still disabled** (S2, CORE) due to expired demo API key. Same state as v3.9.0/v3.9.7.1.

### ❌ NOT findings (do not over-claim)
1. ❌ "n=50 doubles our statistical power" — **NO**, all metrics are still n=25 paired comparisons.
2. ❌ "LTR now beats baseline by +0.0096" — **NO**, within n<100 noise; would need n>100 with significance test to claim.
3. ❌ "BGE penalty got worse (−0.0277 → −0.0380)" — **NO**, both numbers are within 1 std; the apparent "worsening" is search API drift, not a real method change.
4. ❌ "Class diversity improved with class_weight='balanced'" — **NO**, support=0 classes (arxiv, s2, core) still have precision=recall=f1=0; the metric is undefined for absent classes.
5. ❌ "v3.9.7.2 is a real version" — **PARTIAL**: yes for the v4_rerank n=50 step; no for the MoE/CE/LTR work, which is n=25 with new candidates.

## 6. 5-check Global Rule audit (v3.9.7.2)

1. ✅ Runs for $0 (no new APIs; v4_rerank uses local model; BGE cached; MoE/LTR use local models)
2. ✅ No hosted service
3. ✅ Maintenance: 2 new scripts (`_run_cross_encoder_n50.py`, `_run_cross_encoder_wilcoxon_n50.py`), ~250 LOC; all reuse existing pipeline code
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if labels for q026-q050 are missing, MoE/CE/LTR all gracefully fall back to n=25 (no crash)

## 7. What user can do next (actionable)

### If user wants true n=50 statistical power
1. **Provide labels for q026-q050** (25 queries × ~20 candidates each × 5-10 min/query = 5-10 hours of manual labeling). Without this, "n=50" is misleading.
2. Or: run `_run_labels_e2e.py` automation if heuristic labels suffice (probably don't; L2 needs human judgment)

### If user wants the v3.9.7.1 → v3.9.7.2 cross-version comparison to be meaningful
1. **Re-run v3.9.7.1 with the same v4_rerank n=50 candidates** — i.e., replace v3.9.7.1's system_outputs_biencoder/q001 with the new .json, then re-run MoE / CE / LTR with v3.9.7.1 scripts. This isolates "method change" from "API drift". Estimated 30 min.

### If user wants more n=50 work in this session
1. **Run v4 eval (eval.py) on the 5 n=50 conditions** to get recall@10/precision@10/ndcg@10 on the 25 labeled queries with the new candidates — this is a **1-line** eval call per condition
2. **Write ROADMAP entry** documenting "n=50 expansion requires labels" so future sessions don't repeat this trap

### If user wants to move on to CNKI [P0-9]
1. **Tell me your CNKI proxy cookie value** (or institution's EZproxy URL) and I'll start implementing
2. Or: defer to next session after we have a clear "labels first vs CNKI first" priority

## 8. Files added/modified in this session

### New files
- `bench/v01/reports/v3_9_7_2_moe_router_n50.json` (n=50 nominal, n=25 actual; carries `note` field)
- `bench/v01/reports/v3_9_7_2_moe_router_n50.md`
- `bench/v01/reports/v3_9_7_2_cross_encoder_n50.json` (n=50 BGE rerank output)
- `bench/v01/reports/v3_9_7_2_cross_encoder_wilcoxon_n50.{json,md}` (Wilcoxon n=25 paired)
- `bench/v01/reports/v3_9_7_2_ltr_n50.json` (copy of v3_9_2_ltr.json with note)
- `bench/v01/reports/v3_9_7_2_n50_three_tier.md` (this file)
- `bench/v01/reports/v3_9_7_2_moe_router_n25_mislabeled.json` (renamed from misnamed `v3_9_7_2_moe_router_n50.json` that was actually v3.9.7.1 n=25 data)
- `bench/v01/reports/v3_9_7_2_moe_router_n25_mislabeled.md` (same)
- `bench/v01/system_outputs_bm25/q026.json` ... `q050.json` (25 new)
- `bench/v01/system_outputs_biencoder/q026.json` ... `q050.json` (25 new)
- `bench/v01/system_outputs_combined/q026.json` ... `q050.json` (25 new)
- `bench/v01/system_outputs_prf/q026.json` ... `q050.json` (25 new)
- `bench/v01/system_outputs_random/q026.json` ... `q050.json` (25 new)
- `test_output/_run_cross_encoder_n50.py` (BGE on n=50 candidates)
- `test_output/_run_cross_encoder_wilcoxon_n50.py` (Wilcoxon n=25 paired)
- `test_output/_inspect_n50_state.py`, `_inspect_biencoder_q001.py`, `_diff_biencoder.py`, `_diff_biencoder2.py`, `_diff_biencoder3.py` (diagnostic)

### Modified files
- `bench/v01/queries.json` (n=50, 25 user batch q026-q050; from prior session)
- `bench/v01/system_outputs/q026.json` ... `q050.json` (25 new from prior session)

### Deleted (then restored via `git restore`)
- 25 no-extension legacy `system_outputs_*/q001` ... `q025` files from v3.9.0 era — accidentally deleted during cleanup, restored intact

## 9. Honest status for "v3.9.7.2 n=50" claim

| Component | Status |
|---|---|
| **v4_rerank on n=50** | ✅ **Real n=50 result**. All 5 conditions re-ranked on 50 queries. |
| **MoE n=50** | ⚠️ **n=50 nominal, n=25 actual**. Numbers identical to v3.9.7.1. |
| **Cross-encoder n=50** | ⚠️ **n=50 BGE rerank, n=25 metrics**. Wilcoxon on 25 paired, all p > 0.35. |
| **LTR n=50** | ⚠️ **n=50 candidates, n=25 training**. NDCG@10 = 0.7323 (was 0.7192). |
| **v4 eval n=50** | ❌ **NOT RUN** in this session. Would take 5 min, but numbers would still be n=25 because of label filter. |

**One-line summary**: "v3.9.7.2 n=50 = v4_rerank got real n=50; everything else got a new biencoder candidate pool but is still n=25 paired for metrics."
