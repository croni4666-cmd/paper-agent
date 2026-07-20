# v3.9.7.3 action plan — BGE/LTR deprecation + combined default

> Generated 2026-07-20. Triggered by v3.9.7.3 three-tier findings + 2026-07-20
> verification that the v3.9.7.3 wilcoxon MD report mis-stated p>0.05 (real p=0.000825).
> Supersedes v3.9.7.2's "LTR beats baseline +0.0096" claim (which was n=25 with bug-skipped data).

## TL;DR

**Three method changes for v3.9.10 (next release)**:

1. **BGE-reranker → deprecated** for academic abstract ranking (Wilcoxon p=0.000825 sig. negative, Δ=-0.1064 NDCG@10 at n=48). Keep code for future academic-domain reranker comparison.
2. **LTR (LambdaMART 100 trees) → deprecated for n<200** (loses to combined baseline -0.0335 NDCG@10 at n=50; overfit). Keep code, re-evaluate at n>200 with real labels.
3. **combined (0.5*BM25 + 0.5*bi-encoder) → new default** in `bench/v01/_v4_rerank.py`. Mean NDCG@10 = 0.8141 on n=50 mixed labels.

## Evidence

| Source | Key result | Decision driver |
|---|---|---|
| `v3_9_7_3_cross_encoder_wilcoxon_n50.json` | BGE vs bi-encoder: Δ NDCG@10 = -0.1064, Wilcoxon p=0.000825 (sig.) | BGE **does not** work for academic abstracts |
| `v3_9_7_3_cross_encoder_wilcoxon_n50.json` | BGE loses on 36/48 queries (75%); wins on 12/48 | Direction is clear, not a noise artifact |
| `v3_9_7_3_ltr_n50.json` | LTR (LambdaMART 100 trees) NDCG@10 = 0.7806; combined baseline = 0.8141; Δ = -0.0335 | LTR **overfits** at n=50 |
| `v3_9_7_3_ltr_n50.json` | LTR feature importance: combined_score 617, biencoder 593, log_cite_count 233 | LTR mostly uses combined_score + biencoder — why train 100 trees to learn what 0.5+0.5 already does? |
| `v3_9_7_3_moe_router_n50.json` | MoE macro F1 = 0.609 (n=47, 3-engine-only) | MoE 0.89 was n=25 artifact; honest number is 0.61 |

## What "default ranker" means for paper-agent

| Layer | Current behavior | Action |
|---|---|---|
| `pa search` CLI | 6-engine search, no rerank, `--sort-by {cite\|year\|relevance}` (default: cite) | **No change** — pa search doesn't use BGE/LTR, so nothing to deprecate |
| `bench/v01/_v4_rerank.py` | `--condition {bm25,biencoder,combined,prf,random}` — no default, user must pick | **Update docstring** to mark `combined` as recommended for academic abstract ranking |
| `pa_cli/cross_encoder.py` | BGE-reranker code (used by `bench/v01` scripts, not `pa search`) | **Mark DEPRECATED in module docstring**; keep for academic-domain reranker comparison |
| `pa_cli/ltr.py` | LambdaMART 100-tree implementation | **Mark DEPRECATED FOR n<200 in docstring**; keep for n>200 evaluation |
| `pa_cli/moe_router.py` | MoE routing | **Update** docstring from "macro F1 0.89" to "macro F1 0.61 (n=47, 3-engine-only)" |

## Specific code changes

### 1. `pa_cli/cross_encoder.py` — add DEPRECATED note

At top of file (after module docstring), add:

```python
# DEPRECATED 2026-07-20 (v3.9.7.3 finding):
# BGE-reranker-base is significantly WORSE than bi-encoder for academic abstract
# ranking (Wilcoxon p=0.000825, n=48 paired, Δ NDCG@10 = -0.1064).
# Source: bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.json
# Root cause: BGE-reranker-base was trained on MS MARCO (web search), not academic
# abstracts. Academic abstract distribution differs (long queries, technical jargon,
# research-relevance, multilingual). Replacement path: investigate monoT5 / ColBERT /
# LLM-based full-text rerank on academic corpora.
# DO NOT remove this code — keep for future academic-domain reranker comparison.
```

### 2. `pa_cli/ltr.py` — add CONDITIONAL note

At top of file (after module docstring), add:

```python
# CONDITIONAL DEPRECATION 2026-07-20 (v3.9.7.3 finding):
# LambdaMART 100 trees at n=50 LOSES to combined baseline by -0.0335 NDCG@10
# (combined baseline = 0.8141, LTR = 0.7806, source: v3_9_7_3_ltr_n50.json).
# Root cause: 100 trees on n=50 overfits (each tree sees ~10-15 queries).
# Recommendation: USE combined (0.5*BM25 + 0.5*bi-encoder) for n<200.
# Re-test LTR at n>200 with real labels before re-introducing.
# DO NOT remove this code — keep for n>200 evaluation.
```

### 3. `pa_cli/moe_router.py` — fix the "0.89" claim

Replace any "macro_f1 0.89" or similar claim with "macro_f1 0.61 (n=47 mixed labels, 3-engine-only)".

Search current sources for the stale number first:

```bash
grep -n "0.89\|0.889\|0.96" pa_cli/moe_router.py
```

### 4. `bench/v01/_v4_rerank.py` — update docstring

```python
"""
v4 rerank for n=50 academic abstract benchmark.

Conditions:
  bm25      — BM25 only on (query, title+abstract)
  biencoder — cosine similarity from all-MiniLM-L6-v2  ← RECOMMENDED for single-signal
  combined  — 0.5*BM25 + 0.5*biencoder                      ← RECOMMENDED for default
  prf       — Rocchio top-5 expansion → re-BM25
  random    — seeded shuffle (seed=42) — null baseline

DEPRECATED 2026-07-20: BGE-rerank (cross_encoder.py) loses to bi-encoder
by -0.1064 NDCG@10 (Wilcoxon p=0.000825, n=48). Use combined instead.
For n<200, LTR (LambdaMART 100 trees, ltr.py) also loses to combined by
-0.0335 NDCG@10 due to overfit. Use combined at n<200.

See: bench/v01/reports/v3_9_7_3_action_plan.md
"""
```

## What this does NOT change

- `pa search` command behavior — `pa search` does NOT call BGE or LTR, so no user-facing change.
- Search engines (Crossref, OpenAlex, arXiv, S2, AMiner, CNKI) — all 6 stay active.
- A2 auto-labeling — keeps BGE as tie-breaker (small +bias is documented; re-eval with BGE-excluded labels is in v3.9.7.3 todo).
- The combined baseline definition (0.5*BM25 + 0.5*bi-encoder, alpha=0.5) — unchanged.

## 5-check Global Rule audit

1. ✅ Runs for $0 — no new APIs or models
2. ✅ No hosted service
3. ✅ Maintenance: docstring updates only, no new code paths
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if user runs `pa search` (which doesn't call BGE/LTR), behavior unchanged

## Files to commit (single PR)

- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.md` (MD report bug fix)
- `bench/v01/reports/v3_9_7_3_action_plan.md` (this file, new)
- `pa_cli/cross_encoder.py` (DEPRECATED docstring)
- `pa_cli/ltr.py` (CONDITIONAL DEPRECATION docstring)
- `pa_cli/moe_router.py` (fix 0.89 → 0.61 claim)
- `bench/v01/_v4_rerank.py` (docstring update)
- `CHANGELOG.md` (v3.9.10 entry)
- `ROADMAP.md` ([P0-X] BGE/LTR deprecation section)

## Open follow-up items (NOT in this PR)

- [ ] Quantify A2 auto-label circularity: re-run BGE Wilcoxon with BGE-excluded tie-breaker. 1-2 hours, controlled experiment.
- [ ] Investigate monoT5 / ColBERT / LLM-fulltext as BGE replacement. Requires user input on which to prioritize.
- [ ] Get real labels for q026-q050 to remove auto-label caveat. Requires ~5-10 hours of manual labeling.
- [ ] Re-evaluate LTR at n>200 with real labels. Blocked by previous item.
- [ ] CNKI [P0-9] implementation. Blocked by user proxy cookies.
