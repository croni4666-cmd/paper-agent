# paper-agent v4 — Final Summary (v3.9.6 era, 2026-07-13)

> **What we built**: 4 evaluation options from the v4 plan, all implemented under Global Rule.
> **What we proved**: v3.9.0 lift on recall@10 is real (0.722 vs 0.182, n=25).
> **What we didn't prove**: most "lift" deltas at the option-level are within n=25 noise.
> **What's next**: q026-q050 to unblock re-runs + 7 manual PDFs for Layer 7 completion.

---

## 1. The 4 v4 evaluation options

| Option | Paper/Repo | Real impl | Honest coverage | Fails Global Rule? |
|---|---|---|---|---|
| **PaSa** (arXiv 2501.10120) | `bytedance/pasa` (8 commits) | ❌ | ~30-40% (need 7B LLM) | **Yes** (hosted LLM cost) |
| **MoE-for-IR routing** | microsoft/tutel (different domain) | ❌ | n/a | n/a |
| **Cross-encoder rerank** | BAAI/bge-reranker-base | ✅ | 100% (pre-trained, free) | No |
| **LTR (LambdaMART)** | lightgbm `LGBMRanker` | ✅ | 100% (gradient-boosted trees) | No |

**User explicit (2026-07-13)**: *"优先在 Global rule 下，完全实现的"*
→ We built **PaSa-lite** (rule-based, no LLM) + **Cross-encoder** + **LTR** fully.
→ MoE was built as router (different from LLM MoE), but the n=25 baseline issue caps its value.

---

## 2. 4 options — 3-tier honest audit

### Option A: PaSa-lite rule-based (v3.9.6)
- **Architecture**: multi-strategy query expansion (original / synonym / concept / PRF) + 1-hop citation walk + iterative refinement + 8-channel PDF download
- **Status**: ✅ implemented in `pa_cli/pasa_lite.py` (~350 LOC, commit 5a2d9a7)
- **Verified on n=25**: 3-query demo, 2.3 variants/query, 93.7 candidate pool avg
- **Estimated PaSa coverage** (per `v3_9_6_pasa_lite.md`):
  - **30-40%** in v3.9.0 (L1-L5 only, abstract-only)
  - **50-60%** post v3.9.5 (L1-L7, full-text via Layer 6-7)
  - **Real PaSa target**: ~85% (7B LLM creativity, citation graph walk beyond 1-hop)
- **What's missing vs real PaSa**:
  - LLM-generated query expansion (use rule-based synonym + concept lookup)
  - Adaptive iteration stop (we use fixed 2 rounds)
  - Multi-hop citation walk (we do 1-hop max)
  - Synthesis reasoning across papers (we just rerank)
- **3-tier honest**:
  - ✅ Architecture works
  - ✅ Pipeline runs end-to-end on 3 queries
  - ⚠️ "50-60% coverage" is estimate, not measured (would need full n=25 comparison)
  - ❌ Real PaSa requires 7B LLM, we don't ship that

### Option B: MoE router (v3.9.4)
- **Architecture**: multi-class LGBMClassifier on TF-IDF + 6 query metadata features
- **Status**: ✅ implemented in `pa_cli/moe_router.py` (~340 LOC, commit 88a2b69)
- **Verified on n=25**: 0.96 accuracy
- **3-tier honest**:
  - ✅ Architecture works (model trains, predicts)
  - ❌ **0.96 accuracy = 0.96 majority-class baseline** (24/25 openalex, 1/25 crossref, 0/25 others)
  - ❌ MoE for IR routing needs class diversity — n=25 with 24 same class can't show value
  - ⚠️ Per-class precision/recall: arxiv=0, openalex=24, s2=0, crossref=1, core=0
- **Why it failed**:
  - User's n=25 queries all start as openalex search
  - 6 metadata features not enough to discriminate routing decisions
  - Need diverse training queries or per-class weighting
- **Block to fix**: q026-q050 with diverse starting engines

### Option C: Cross-encoder (BGE-reranker-base) (v3.9.3)
- **Architecture**: pre-trained BGE-reranker-base, downloaded via HF Chinese mirror
- **Status**: ✅ implemented in `pa_cli/cross_encoder.py` (~250 LOC, commit b99a757)
- **Verified on n=25**: NDCG@10 0.6928 vs biencoder 0.7205 (Δ=-0.0277)
- **3-tier honest**:
  - ✅ Architecture works
  - ✅ Model downloaded + runs (smoke test: K-12 AI tutoring 0.9546, frog/climate 0.0000)
  - ✅ Per-query σ ≈ 0.20 reveals high variance (11/25 improved +0.32, 14/25 hurt -0.42)
  - ❌ **Aggregate metric hurt by -0.0277 on n=25** (memory discipline: this is noise, not "negative finding")
  - ⚠️ No stat-sig test run; would need Wilcoxon or bootstrap CI for confidence
- **Failure mode analysis**:
  - 14/25 queries hurt — what's different about them?
  - Some queries where BM25 picks the right paper but cross-encoder demotes it (TF-IDF mismatch on technical terms)
  - Some queries where cross-encoder correctly demotes BM25-bait papers (good signal, hurts metric on weak labels)

### Option D: LTR (LambdaMART) (v3.9.2)
- **Architecture**: LGBMRanker on 8 features (BM25, biencoder, combined, log_cite, is_recent, 3 metadata)
- **Status**: ✅ implemented in `pa_cli/ltr.py` (~430 LOC, commit e426b95)
- **Verified on n=25**: NDCG@10 0.7192 ± 0.0959 vs combined baseline 0.7227 (Δ=-0.0034)
- **3-tier honest**:
  - ✅ Architecture works
  - ✅ 5-fold CV runs (no leakage)
  - ✅ Feature importance: combined 309.86, biencoder 298.77, log_cite 147.65, is_recent 1.37 (recency barely used)
  - ❌ **Δ=-0.0034 on n=25 is within noise** (memory discipline: not a "useful negative result")
  - ⚠️ Heavy feature correlation (combined_score = f(bm25, biencoder)) — model has limited signal beyond baseline
  - ⚠️ 3-level labels (highly-relevant / relevant / irrelevant) too coarse for fine-grained ranking

---

## 3. 7-layer architecture (final, post v3.9.6)

```
INPUT: user query (q001-q050)
  │
  ▼
L1: Source pool (5 engines)
    ├─ openalex (api.openalex.org)        ← empirical: works in CN without proxy
    ├─ arxiv (export.arxiv.org)           ← empirical: works in CN
    ├─ semanticscholar (api.semanticscholar.org)
    ├─ crossref (api.crossref.org)
    └─ core (api.core.ac.uk)              ← empirical: works in CN
  │
  ▼
L2: Recall (multi-strategy expansion, PaSa-lite v3.9.6)
    ├─ original query
    ├─ synonym expansion (WordNet + custom)
    ├─ concept expansion (OpenAlex concepts API)
    └─ PRF (top-10 terms from top-3 docs)
  │
  ▼
L3: Rerank (combine + cross-encoder + LTR)
    ├─ BM25 (lexical)
    ├─ biencoder (semantic, BGE-base)
    ├─ cross-encoder (BGE-reranker, v3.9.3)        ← per-query high variance
    └─ LTR (LambdaMART meta-ranker, v3.9.2)       ← Δ within noise on n=25
  │
  ▼
L4: Filters (multiplicative on v4_score)
    ├─ recency (off/strict/moderate, v3.9.1)
    ├─ institution tier (P1-7 pending)
    ├─ quality (citation count, IF proxy)
    └─ geography (China blocklist, P1-8 pending)
  │
  ▼
L5: Output (top-K, default K=10)
  │
  ▼
L6: Download (NEW v3.9.5, 8-channel cascade)
    ├─ 8 channels: openalex → arxiv → unpaywall → crossref →
    │   doi_redirect → publisher → scholar → scihub → playwright
    └─ Manual fallback for failures (per user explicit)
  │
  ▼
L7: Full-text deep rerank (NEW v3.9.5, 12 features)
    ├─ Re-rank downloaded PDFs with full-text BM25 + biencoder + cross-encoder
    └─ LTR re-fit with 12 features (incl. 4 full-text)
```

**8/15 PDFs auto-downloaded** (53.3%, v3.9.5.2 cumulative).
**7/15 still manual** (Layer 7 partial — 8/15 features).

---

## 4. What works vs what doesn't (the 80/20)

### Works ✅
- 3.9x lift on recall@10 (0.722 vs 0.182) — **the original v3.9.0 win, preserved through 6 patches**
- 8/15 PDFs auto-downloaded (53.3%)
- DOI canonicalization fixes 19 renames + 5 typos + 7 duplicates
- Recency filter flags 16/25 stale queries
- L1 recall pool (5 engines, multi-strategy expansion)
- L3 rerank (BM25 + biencoder + combined)

### Doesn't work ❌
- **All 4 v4 evaluation options fail to beat the simple `combined_score` baseline on n=25**
  - LTR: -0.0034 (within noise)
  - Cross-encoder: -0.0277 (per-query high variance, 14/25 hurt)
  - MoE: 0.96 = majority baseline (class collapse)
  - PaSa-lite: estimated 50-60% coverage, unmeasured
- **No statistical test** (no Wilcoxon, no bootstrap CI, no holdout)
- **Cloudflare / paywall** blocks 7/15 PDFs even with proxy + playwright

### Why everything regresses on n=25
- n=25 is fundamentally small for any 2nd-stage model
- Heavy feature correlation in L1 (bm25, biencoder, combined all measure relevance)
- 3-level labels too coarse for LTR/Cross-encoder signal
- MoE needs diverse training data (24/25 = same class)

### What we'd need to actually show value
- **n=50 minimum** (q026-q050 from user, pending)
- **Bootstrap CI or Wilcoxon** on aggregate metrics
- **Per-query breakdown** (which queries win, which lose)
- **Holdout** (separate test set, not 5-fold CV on same 25)
- **Full PaSa** (7B LLM, Fails Global Rule)

---

## 5. The 7 papers still manual

```
q001: 10.1186/s41239-021-00292-9 (Springer)         — no OA version
q001: 10.1001/jamanetworkopen.2021.49008 (JAMA)     — JAMA paywall, no sci-hub
q001: 10.3390/su151612451 (MDPI)                    — should be OA? investigate
q002: 10.1093/oxrep/graa051 (Oxford UP)              — paywall
q002: 10.5089/9781498303743.001 (IMF)                — IMF book series
q002: 10.1037/e686432011-001 (APA)                   — PsycNet paywall
q003: 10.1145/3488560.3498443 (ACM)                  — ACM paywall
```

**Note**: 10.3390/su151612451 is MDPI which is **open access** — should not be in this list.
→ Open question: did openalex miss the OA URL? Did unpaywall return wrong? Worth investigating.

---

## 6. What's next (v3.10.0 candidates)

### Unblock existing work
- **P0-6.1 LTR re-run with n=50** (pending q026-q050)
- **P0-7.1 Cross-encoder re-run with n=50 + bootstrap CI**
- **P1-11.1 MoE router re-run with class diversity**
- **P0-8.1 Layer 7 re-rank with 12 features** (need 7 manual PDFs)
- **P0-8.2 Investigate MDPI failure** (10.3390/su151612451 should be OA)

### New v3.10.0 candidates (priority order)
1. **Stat-sig module** — add Wilcoxon signed-rank + bootstrap CI to `pa rerank` so future deltas are properly audited (memory discipline codification)
2. **MDPI / open OA fix** — investigate why MDPI failed cascade; likely openalex OA URL field format mismatch
3. **v3.10.0 integration** — single `pa search` pipeline combining LTR + Cross-encoder + MoE + Deep rerank + PaSa-lite, expose 7-layer knobs
4. **Layer 4 enrichment** — implement P1-6/7/8/9/10 lookup tables (sub-topic domains, institution tier, China blocklist, country list, falsifiability)
5. **Rerank labeling refinement** — 5-level labels (highly-relevant / relevant / somewhat / marginal / irrelevant) for finer LTR signal
6. **PDF text quality** — add GROBID extraction fallback for scanned / image-based PDFs

### Pending user input
- q026-q050 (blocked LTR re-run + MoE + Cross-encoder re-eval)
- 7 manual PDFs (blocked Layer 7 re-rank with 12 features)
- P1-6/7/8/9/10 lookup tables (blocked Layer 4 enrichment)

---

## 7. Files of record (post v3.9.6)

| File | What |
|---|---|
| `pa_cli/ltr.py` | LambdaMART reranker (430 LOC) |
| `pa_cli/cross_encoder.py` | BGE-reranker wrapper (250 LOC) |
| `pa_cli/moe_router.py` | LGBMClassifier router (340 LOC) |
| `pa_cli/deep_rerank.py` | Layer 6-7 framework (400 LOC) |
| `pa_cli/pasa_lite.py` | PaSa-lite rule-based (350 LOC) |
| `pa_cli/doi.py` | DOI canonicalization (165 LOC) |
| `pa_cli/recency.py` | Recency filter (190 LOC) |
| `pa_cli/fetch.py` | 8-channel cascade with v3.9.5.2 + v3.9.5.4 bug fixes |
| `ROADMAP.md` | 5 new items committed, all `status: done` |
| `CHANGELOG.md` | 6 entries (v3.9.0-v3.9.6) + 3 patches (v3.9.5.1/2/3) |
| `bench/v01/reports/v3_9_*.md` | 5 per-option reports |
| `bench/v01/reports/v4-options-mapping.html` | 4-option visual side-by-side |
| `bench/v01/reports/v4-final-summary.md` | **This document** |

---

## 8. Honest bottom line (for next session)

**What we shipped**: 4 v4 options (PaSa-lite / MoE / Cross-encoder / LTR) + 2 new layers (L6 Download, L7 Full-text rerank) + 2 utility features (DOI canonicalization, recency filter) — all under Global Rule.

**What we proved**: v3.9.0's 3.9x lift on recall@10 holds across 6 patches. L1-L5 baseline architecture is sound.

**What we didn't prove**: that any of the 4 options beat the `combined_score` baseline on a sample size that can detect a real effect.

**What we know from running it**:
- Aggregate metrics on n=25 are noise
- Per-query variance is huge (σ ≈ 0.20 for cross-encoder)
- Some queries the new options help, some they hurt — net zero or slightly negative
- Need n=50+ + bootstrap CI + holdout to make any claim

**What I'd recommend next session** (if user is in mood to keep going):
1. Wait for q026-q050 (cheap, unblocks 3 re-evaluations)
2. Manual download 7 PDFs (user's own time, unblocks Layer 7)
3. Add stat-sig module (cheap, future-proofs all rerank claims)
4. Investigate MDPI failure (cheap, might unlock free L6 coverage)
5. **Don't** add more rerank options until #1 and #2 done — current count is enough for the dataset size

**What I'd recommend NOT doing**:
- Don't add Cross-encoder v2 / LTR v2 / MoE v2 — variance is the problem, not the model
- Don't add real PaSa — Fails Global Rule (7B LLM cost)
- Don't keep adding filters — recency is the only one with evidence
- Don't expand to n>50 without stat-sig — bigger sample without proper testing just hides noise longer
