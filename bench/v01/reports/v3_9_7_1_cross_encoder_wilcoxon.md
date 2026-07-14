# v3.9.7.1 Cross-Encoder Wilcoxon Signed-Rank Test

> Generated 2026-07-14 by `test_output/_run_cross_encoder_wilcoxon_v3_9_7_1.py` per ROADMAP [P0-7.1].
> Re-analysis of v3.9.3 cross-encoder results with non-parametric paired significance test.

## Why this matters

v3.9.3 reported Δ NDCG@10 = -0.0277 (BGE vs biencoder) on n=25 queries.
Per `MEMORY.md` discipline: "n<100 metric deltas = noise, not finding."

**The honest question**: is the -0.0277 Δ statistically distinguishable from zero?
- If yes → BGE is genuinely different (worse in this case) from biencoder
- If no → observed Δ is consistent with random fluctuation; we cannot claim a real effect

Wilcoxon signed-rank test (two-sided) is the right tool here:
- Paired (25 paired queries)
- Non-parametric (no normality assumption, which is critical for n=25)
- Tests H0: median(BGE - biencoder) = 0

## Test setup

- **Sample**: 25 paired queries from `bench/v01/reports/v3_9_3_cross_encoder.json`
- **Test statistic**: Wilcoxon T (sum of signed ranks of |diff|)
- **α (significance)**: 0.05
- **Effect size**: matched-pairs rank-biserial correlation r_rb

## Results (n=25, two-sided)

| Metric | Mean BGE | Mean biencoder | Mean diff | p-value | n.s. (p≥0.05)? | r_rb (effect size) |
|---|---:|---:|---:|---:|---|---:|
| **NDCG@10** | 0.6928 | 0.7205 | **-0.0277** | **0.5424** | YES | -0.1446 (small) |
| **Recall@10** | 0.6569 | 0.6683 | -0.0114 | 0.7760 | YES | -0.1167 (small) |
| **Precision@10** | 0.4560 | 0.4680 | -0.0120 | 0.8868 | YES | -0.0667 (negligible) |

**All three metrics fail to reject H0** at α=0.05. The observed Δ is consistent with random fluctuation on n=25.

## Per-query NDCG@10 breakdown (top 15 by |diff|)

| qid | biencoder | BGE | Δ | verdict |
|---|---:|---:|---:|---|
| q002 | 0.9219 | 0.5050 | -0.4169 | BGE loses |
| q012 | 0.8350 | 0.4471 | -0.3879 | BGE loses |
| q004 | 0.4386 | 0.7563 | +0.3177 | BGE wins |
| q007 | 0.6410 | 0.9576 | +0.3166 | BGE wins |
| q019 | 0.8905 | 0.5921 | -0.2984 | BGE loses |
| q015 | 0.5119 | 0.7645 | +0.2526 | BGE wins |
| q013 | 0.7441 | 0.5044 | -0.2398 | BGE loses |
| q005 | 0.7641 | 0.5417 | -0.2224 | BGE loses |
| q001 | 0.5373 | 0.3458 | -0.1915 | BGE loses |
| q010 | 1.0000 | 0.8098 | -0.1902 | BGE loses |
| q022 | 0.6434 | 0.8078 | +0.1644 | BGE wins |
| q016 | 1.0000 | 0.8438 | -0.1562 | BGE loses |
| q006 | 0.6368 | 0.7906 | +0.1538 | BGE wins |
| q024 | 0.4220 | 0.5709 | +0.1490 | BGE wins |
| q008 | 0.8487 | 0.9783 | +0.1296 | BGE wins |

**Note**: 11 wins / 14 losses for BGE. The 14-11 split is **not significantly different from 12.5-12.5** (binomial test p≈0.65, which is consistent with the Wilcoxon result).

## What this means — honest verdict

- ❌ **v3.9.3 claim "BGE-rerank underperforms biencoder by -0.0277 NDCG@10" is NOT statistically supported.** The observed Δ is consistent with random fluctuation.
- ❌ **v3.9.3 claim "BGE-rerank hurts benchmark metrics" is OVERCLAIMED.** Cannot distinguish from noise.
- ⚠️ **Cannot conclude BGE is better OR worse than biencoder** on this benchmark.

**Why the result is "neutral" rather than "negative"**:
- n=25 is below the threshold where cross-encoder improvements typically become detectable
- The 14-11 win/loss split has high variance (binomial SD ≈ 2.5)
- Effect size r_rb = -0.14 is "small" (< 0.3 = small, < 0.5 = medium, < 0.7 = large)
- The per-query variance (σ ≈ 0.20) is larger than the mean Δ (0.028)

## When would we have statistical power to detect a real effect?

For paired Wilcoxon with 25 pairs to detect effect size r=0.3 (small-to-medium) at α=0.05, β=0.2 (80% power):
- Need n ≈ 50-100 paired observations
- Specifically: Cohen's d ≈ 0.3 with paired t-test needs n ≈ 90; Wilcoxon is ~15% less efficient, so n ≈ 100

**Bottom line**: we need **q026-q050** to even have a chance of detecting a real BGE effect. Without it, this is a coin flip.

## 3-tier honest audit (per `MEMORY.md` discipline)

- ✅ **Verified**: Wilcoxon T, p-value, r_rb computed correctly using scipy.stats.wilcoxon
- ✅ **Verified**: data is correctly extracted from v3.9.3 cross-encoder JSON
- ✅ **Verified architecture**: the test runs end-to-end, output saved to `v3_9_7_1_cross_encoder_wilcoxon.json`
- ⚠️ **Statistical power insufficient**: n=25 cannot reliably detect effect size r<0.3
- ❌ **v3.9.3 "BGE hurts metrics" claim is now RETRACTED** — the -0.0277 Δ is statistically indistinguishable from 0 on this benchmark
- ❌ **Cannot claim a "BGE works"** finding either — observed Δ is symmetric around 0 (11 wins vs 14 losses)

## What user should know

- **v3.9.3 status update**: the v3.9.3 CHANGELOG entry said "Δ NDCG@10 = -0.0277, σ ≈ 0.20". This was correctly reported as a delta fact, not a finding. The Wilcoxon test now **confirms it is noise** — there is no significant BGE effect on n=25.
- **Re-test when q026-q050 lands**: re-run Wilcoxon on n=50. If p < 0.05 and r_rb > 0.3, then we have a real BGE-vs-biencoder signal.
- **Practical implication for v3.9.7 production**: BGE-rerank can stay as an optional `--reranker bge` flag (default `none` = biencoder). No production change needed.

## 5-check Global Rule audit

1. ✅ Runs for $0 (scipy is local Python lib, no API)
2. ✅ No hosted service
3. ✅ Maintenance: ~150 LOC in `test_output/_run_cross_encoder_wilcoxon_v3_9_7_1.py`
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if scipy not installed, script prints error and exits 1
