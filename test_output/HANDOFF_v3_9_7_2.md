# Handoff: v3.9.7.2 n=50 work (continuation from archived session mvs_5d7baad3d503426f87c787de5ef247d8)

**Date**: 2026-07-14 23:50
**Archived session**: mvs_5d7baad3d503426f87c787de5ef247d8 (length was too long, internal server errors)

## What's done

1. ✅ queries.json n=50: 25 user queries q026-q050 added (v3, commonality-extended to international where applicable, China-specific kept per user instruction for q032/q047)
2. ✅ system_outputs/q026-q050.json: 25 batch-generated via test_output/_gen_system_outputs_n50.py (20 success + 5 from earlier in same script run)
3. ✅ v3.9.7.2 CHANGELOG entry written
4. ✅ version bumped 3.9.7.1 → 3.9.7.2

## What's remaining (next session)

1. **Run v4_rerank n=50**: 5 commands, ~5-10 min total
   `ash
   cd "G:\minimax - workspace\Paper agent"
   python bench/v01/_v4_rerank.py --condition bm25
   python bench/v01/_v4_rerank.py --condition biencoder
   python bench/v01/_v4_rerank.py --condition combined
   python bench/v01/_v4_rerank.py --condition prf
   python bench/v01/_v4_rerank.py --condition random
   `

2. **Run MoE v3.9.7.2 n=50** (5-fold CV):
   `ash
    = "G:\minimax - workspace\Paper agent"
   python test_output/_run_n50_v3972.py
   `
   Output: ench/v01/reports/v3_9_7_2_moe_router_n50.{md,json}

3. **Cross-encoder Wilcoxon n=50**:
   - First, need to run cross-encoder on n=50 system_outputs_combined (similar to v3.9.3 but for n=50)
   - Then run Wilcoxon test
   - Use 	est_output/_run_cross_encoder_wilcoxon_v3_9_7_1.py as template
   - Output: ench/v01/reports/v3_9_7_2_cross_encoder_wilcoxon_n50.{md,json}

4. **LTR [P0-6.1] n=50**:
   - Update 	est_output/_run_ltr_v3_9_2.py to read n=50 system_outputs_combined
   - Run 5-fold CV
   - Compare to v3.9.2 NDCG@10 = 0.7192 (n=25)

5. **Write 3-tier honest report** at ench/v01/reports/v3_9_7_2_n50_three_tier.md:
   - ✅ Verified: pipeline runs on n=50
   - ⚠️ Caveats: same as n=25 but with more statistical power
   - ❌ NOT findings: confirm if any n=50 numbers are noise or signal

6. **Commit v3.9.7.2 final results**

7. **CNKI [P0-9] implementation** (separate work):
   - User has CNKI access via "其他代理" (校园 VPN / EZproxy / 机构图书馆代理)
   - User wants me to implement CNKI 6th search engine with cookies maintenance
   - See ROADMAP [P0-9] section for full spec

## Key context

- **Demo API key is EXPIRED** but pa search still works (3 of 5 engines: crossref, openalex, arxiv)
- **search command**: pa search "<query>" --limit 10 --format json -o <path> (--limit 10 gives ~30 deduped candidates, matching n=25 baseline)
- **Schema conversion needed**: new pa search output has ound_by field, old snapshot.py expects engines_found_in (handled in _gen_system_outputs_n50.py)

## Files of interest

- ench/v01/queries.json — 50 queries (q001-q050)
- ench/v01/system_outputs/q001.json to q050.json — 50 snapshot files
- ench/v01/system_outputs_combined/ — v4_rerank output (pending)
- pa_cli/moe_router.py — has v3.9.7.1 class_weight='balanced' + balanced metrics
- 	est_output/_run_n50_v3972.py — ready to run, will read 50 system_outputs_combined
- 	est_output/_run_cross_encoder_wilcoxon_v3_9_7_1.py — n=25 template, needs n=50 cross-encoder output
- ROADMAP.md [P0-9] CNKI section — full spec for CNKI implementation
- CHANGELOG.md v3.9.7.2 entry — what was done, what remains

## Quick verification

After running v4_rerank n=50 + MoE n=50, verify:
- ench/v01/system_outputs_combined/q050.json exists
- ench/v01/reports/v3_9_7_2_moe_router_n50.json has 50 queries
- MoE mean macro F1 should be > 0.89 (v3.9.7.1 n=25 number) if class diversity truly improved
  - Expected: openalex drops from 96% to 80-85%, other engines increase
