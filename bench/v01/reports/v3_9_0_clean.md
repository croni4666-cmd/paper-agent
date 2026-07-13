# v3.9.0 v4 Stack — User Spot-Check Clean Labels Report

> **Source**: `bench/v01/labels_clean.json` (built from 25 SPOT_CHECK_qNNN.md files,
> 13 overrides applied). All metrics re-computed on clean labels.
>
> **Date**: 2026-07-13
> **Labels**: user spot-check verified (5 priority queries reviewed in full, 20 queries no-objection)
> **Conditions**: same 5 v4 conditions + 1 ablation = 6 conditions on 25 queries

---

## Side-by-side metrics — Mavis vs User spot-check labels

| Condition | recall@10 (Mavis) | recall@10 (Clean) | Δ recall | precision@10 (Mavis) | precision@10 (Clean) | Δ precision | ndcg@10 (Mavis) | ndcg@10 (Clean) | Δ ndcg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original (citation count) | 0.182 | 0.185 | +0.003 | 0.180 | 0.180 | 0.000 | 0.362 | 0.363 | +0.001 |
| random shuffle | 0.321 | 0.323 | +0.002 | 0.300 | 0.296 | -0.004 | 0.486 | 0.486 | 0.000 |
| bm25 (lexical) | 0.612 | 0.613 | +0.001 | 0.472 | 0.464 | -0.008 | 0.702 | 0.701 | -0.001 |
| biencoder (semantic) | 0.690 | 0.685 | -0.005 | 0.528 | 0.508 | -0.020 | 0.816 | 0.799 | -0.017 |
| **combined (0.5/0.5)** | **0.722** | **0.721** | **-0.001** | **0.544** | **0.532** | **-0.012** | **0.790** | **0.785** | **-0.005** |
| prf (Rocchio BM25) | 0.595 | 0.590 | -0.005 | 0.456 | 0.436 | -0.020 | 0.704 | 0.691 | -0.013 |

## Lift vs original (citation count baseline) — User spot-check

| Condition | recall@10 lift | Interpretation |
|---|---:|---|
| **original** | reference | citation count ordering (negative signal per v3.9 finding) |
| random | +0.138 | even random shuffle beats citation count by 75% |
| bm25 | +0.428 | 3.3x lift over baseline |
| biencoder | +0.500 | 3.7x lift |
| **combined** | **+0.536** | **3.9x lift (preserved)** |
| prf | +0.405 | 3.2x lift |

## Per-query n_relevant change (Mavis → Clean)

Only 5 of 25 queries had user overrides (priority 1-5 reviewed; priority 6-25 not reviewed but Mavis labels were accepted as-is per user's "no objection = agree" rule):

| Query | n_relevant (Mavis) | n_relevant (Clean) | Δ | User rationale |
|---|---:|---:|---:|---|
| q005 (UBI labor supply) | 8 | 6 | -2 | cash transfers ≠ UBI; quantitative eval unverified without abstract |
| q007 (climate ag adaptation) | 25 | 22 | -3 | non-econ ag-practice papers are 1 not 2; one is pure cultivation → 0 |
| q010 (institutional trust pandemic) | 12 | 13 | +1 | Mobilizing Policy → 2; pandemic fatigue → 0; CoronaNet → 1 (dataset is good reference material) |
| q013 (protein structure prediction) | 4 | 4 | 0 | ESMFold binding-site paper → 0 (uses ESMFold ≠ is structure prediction); sequence LM → 0 |
| q019 (intelligent tutoring systems) | 19 | 17 | -2 | human-in-loop ML → 1; "Stupid Tutoring Systems" 2016 → 1 (no abstract, probably no AI); 2014 multimedia tutoring → 1 (no AI era) |

**Total changes**: 13 labels overridden (3.5% of 374 candidates) — but these are all in priority 1-5 queries and shift the precision floor slightly downward because user removed some "Mavis called it relevant" papers that were actually marginal.

## Three-tier honest audit

### ✅ Verified
- All 4 v4 conditions ran on 25 queries with **clean user-verified labels** (no crashes, no empty outputs)
- **Combined lift preserved at 3.9x** (recall@10 0.722 → 0.721 vs original 0.185; only -0.001 from Mavis labels)
- BM25 lift also preserved at 3.3x (0.613 vs 0.185)
- 13 user overrides applied cleanly; 5 DOI mismatches between spot-check and labels.json (typo: 10.3389 vs 10.3380, 2 papers each) — skipped with WARN, surfaced for system-level data drift fix

### ⚠️ Unverified / Caveats
- **Only 5 of 25 queries were user-spot-checked** (priority 1-5). The other 20 queries are "no objection = trust Mavis" — if 30%+ of Mavis labels are wrong in those 20 queries, the strategy needs revisiting (per spot-check INDEX expectation)
- **Lift is on 25 queries**, n=25 is small for significance testing
- **PRF still underperforms** BM25 (-0.023) on clean labels — same as Mavis labels. PRF direction (term expansion) may be wrong; concept expansion would be better
- **Bi-encoder all-MiniLM-L6-v2 is English-only** — not ideal for some non-English queries (no impact on this 25-query set; all EN)
- **No LLM-based rerank** (cross-encoder rejected because HF download blocks)

### ❌ Hollow / Known gaps
- **5/25 queries = 20% of benchmark was actually user-verified**. The other 20 queries' n_relevant and lift numbers are Mavis-claimed. v3.9.0 final number is **NOT user-validated** for the wider benchmark — it is validated for the 5 priority queries only
- **n=25 too small for any "statistically significant" claim** about the combined condition's superiority over biencoder alone (delta +0.036 recall@10 — could be noise)
- **No holdout set** — clean labels only on these 25 queries; can't verify "doesn't overfit" claim
- **No Phase 1.5/1.6 done** (q026-q050 not evaluated; alpha grid search not run)
- **3.5% label noise is real, not zero** — user found 13/374 cases where Mavis was wrong. This may understate the noise in priority 6-25 queries that weren't spot-checked
- **Spot-check 5 DOI mismatches** (10.3389 vs 10.3380) — labels.json has typo'd DOIs that don't match the actual papers. Need system-level DOI canonicalization

## User feedback patterns (now visible in clean labels + override notes)

User's spot-check reveals **7 distinct quality issues** with Mavis's auto-labeling that go beyond "minor disagreements":

1. **Time decay too gentle** — Mavis keeps 20-year-old papers with citation_count > 122. User says "should remove unless > mean+2std" (5 papers affected: q019 #26, #10, #14, #15, #16)
2. **Granularity too coarse** — UBI ≠ cash transfers (q005 #22), structure prediction ≠ binding-site prediction (q013 #28), AI in higher ed ≠ ITS (q019). Query decomposition missing
3. **Field/discipline not in label** — ag practice paper ≠ ag econ paper (q007 #13, #16, #17). Need venue/journal classifier
4. **No institutional credibility signal** — q010 #1 (OxCGRT Oxford COVID tracker) is partial relevance but high reference value due to Oxford's institutional brand. Need institution lookup table
5. **No China political-exclusion** — User wants to exclude 国际关系研究院, 马克思主义学院. Need a blocklist
6. **No abstract → unverifiable** — multiple "no abstract" papers where Mavis guessed 2 but user can't verify. Need to flag these for user-verified-only promotion
7. **Duplicate detection missing at query level** — q007 #27/#28 same DOI; q017 #3/#5; q014 #15/#17, #18/#19, #26/#27. Need DOI-case-insensitive dedup

See `ROADMAP.md` for the 7 corresponding [P0-4] through [P1-10] proposed items.

---

## Files (this report's deliverables)

- `bench/v01/labels_clean.json` — clean labels (Mavis + 13 user overrides)
- `bench/v01/spot_check/_overrides.json` — full audit log of every user change
- `bench/v01/reports/v3_9_0_clean.json` — full metrics JSON
- `bench/v01/reports/v3_9_0_clean.md` — this file
- `bench/v01/_build_clean_labels.py` — parser (re-runnable)
