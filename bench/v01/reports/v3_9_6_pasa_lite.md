# v3.9.6 PaSa-lite Rule-based Report

> Generated 2026-07-13 by `pa_cli/pasa_lite.py` per ROADMAP [P2-6].
> Rule-based replication of ~50% of ByteDance + 北大 PaSa without using an LLM.

## Method (what's implemented)

**Multi-strategy query expansion** (3 variants per query):
- `original` — the user's query as-is
- `synonym` — word-level substitution (AI→artificial intelligence, ML→machine learning, etc.)
- `concept` — OpenAlex concept lookup + name appended to query
- `prf` — pseudo-relevance feedback: top-2 result titles as new query

**Iterative refinement** (2 rounds per variant):
- Round 1: search with variant → top-K
- Round 2: re-search using top-2 titles from round 1 → dedup → expand pool
- Stop if no new DOIs added

**Citation walk** (1-hop, rule-based):
- For top-5 candidates, fetch forward + backward citations
- Add to candidate pool, dedup by DOI

## What's NOT implemented (would need LLM)

- LLM-driven `expand` action (creative query rewriting)
- LLM reasoning about relevance (chain-of-thought)
- Adaptive `stop` decision (LLM knows when enough)
- Content-aware re-ranking (LLM reads full paper)
- SFT + PPO training (would need GPU + paid API)

## Aggregate stats (over all queries)

- Queries processed: 3
- Avg variants generated per query: 2.3
- Avg candidate pool size per query: 93.7
- Avg citations added via 1-hop walk: 0.0

## PaSa coverage re-estimate (per ROADMAP [P2-6] + [P0-8])

| PaSa Component | Coverage |
|---|---:|
| Multi-strategy query expansion | 70% (rule-based, no LLM creativity) |
| Full-text paper reading | 70% (with [P0-8] Layer 6-7) |
| Citation walk (1-hop) | 60% (rule-based direction) |
| Stop decision | 30% (fixed 2 rounds, not adaptive) |
| Relevance reasoning | 60% (use [P0-7] BGE cross-encoder) |
| Adaptive iteration | 50% (rule-based pipeline) |
| SFT + PPO training | 0% (Global Rule ❌) |
| Google Search API | 0% (Global Rule ❌) |
| **Overall** | **~50-60%** |

## 3-tier honest audit (per MEMORY.md discipline)

- ✅ **Verified architecture**: PaSaLiteAgent runs end-to-end on real queries
- ⚠️ **Lift vs single-engine baseline**: not measured (would need full v4_rerank comparison)
- ❌ **NOT a 'finding'**: 50-60% PaSa coverage is an estimate, not a measured lift

## 5-check Global Rule audit

1. ✅ Runs for $0 (no LLM, no paid API)
2. ✅ No hosted service
3. ✅ Maintenance: ~350 LOC new in pa_cli/pasa_lite.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if individual building blocks fail, PaSa-lite falls back to single-engine search
