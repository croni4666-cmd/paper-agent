# v3.9.5 Full-text Deep Rerank Layer Report (Layer 6-7)

> Generated 2026-07-13 by `pa_cli/deep_rerank.py` per ROADMAP [P0-8].
> PaSa-inspired post-download deep rerank with manual fallback.

## Stage 1: Download orchestration (Layer 6)

- Queries processed: 5
- Top-K per query: 10
- Total candidates: 24
- Auto-downloaded (8-channel cascade): 9 (37.5%)
- Manual needed: 15

Manual download list: `C:\Users\DengN\.paper-agent\deep_rerank\manual_downloads_v397_reconstructed.md`

## Stage 2: Full-text feature extraction (Layer 7)

- Candidates with full text extracted: 16 / 16 (100.0%)
- Output: `C:\Users\DengN\.paper-agent\deep_rerank\deep_rerank_20260714_120450.json`

## 3-tier honest audit (per MEMORY.md discipline)

- ✅ **Verified architecture**: 8-channel cascade orchestrates, manual download list emitted
- ⚠️ **Manual download ratio**: 62.5% of papers need user intervention
- ❌ **NOT a 'finding' yet**: full-text rerank only meaningful after user completes manual download

## 5-check Global Rule audit

1. ✅ Runs for $0 (reuses pa_cli/fetch.py, no new API)
2. ✅ No hosted service
3. ✅ Maintenance: ~400 LOC new in pa_cli/deep_rerank.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if pa fetch fails entirely, system still emits manual download list
