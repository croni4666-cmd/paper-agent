# Session Handoff — paper-agent v3.9.7.4 (2026-07-15)

> **Purpose**: Compact context for fresh sessions to quickly rehydrate.
> **Current state**: 2026-07-15, after Plan 1 commit `c4b228e` + version bump `19b032d`.
> **Next step**: Plan 2 — write `Export-CNKICookies.ps1` (CNKI cookies export script).

## TL;DR — what changed in 2026-07-15 sessions

Three major commits:
- `b89694e` v3.9.7.3: true n=50 evaluation + auto labels + bug fix
- `753db95` ROADMAP update: 4 schemes eval (LTR/BGE/MoE/PaSa-lite)
- `7342008` BENCHMARK_TODO.md: LTR + BGE back-burner
- `c4b228e` v3.9.7.4 Plan 1: CNKI skeleton + fulltext 2 features + CLI
- `19b032d` version bump 3.9.7.2 → 3.9.7.4

## Critical findings (3-tier honest)

### Bug fix (v3.9.7.3)
`pa_cli/moe_router.py:202` + `pa_cli/ltr.py:165` had `qfile.suffix != ""` that **skipped `.json` files**.
Effect: v3.9.7.2 reported "n=50 nominal, n=25 actual" but real cause was code, not labels.
Fixed by accepting both `.json` and no-ext, dedupe preferring `.json`.

### n=50 real evaluation (v3.9.7.3)
| Method | n=25 (fake) | n=48-50 (real) | Verdict |
|---|---|---|---|
| MoE macro F1 | 0.889 | **0.609** | n=25 was 24/1 class distribution; n=47 has 24/20/3 (true) |
| BGE-rerank Δ NDCG@10 | -0.0277 (n.s.) | **-0.1064 (p=0.0008)** | BGE significantly worse; deprecate |
| LTR Δ NDCG@10 | -0.0034 | **-0.0335** | LTR loses to baseline; deprecate |

### A2 auto-labeling (v3.9.7.3)
- 522 auto labels for q026-q050 (L2 rate 26.8%, real is 27.8%)
- Useful for method comparison; NOT for "X% better than expert" claims
- q041-q043 L2=0: system genuinely can't find narrow medical queries
- BGE is tie-breaker → BGE-vs-biencoder comparison is slightly +biased for BGE

### BGE deprecation rationale
v3.9.7.3 n=48 paired Wilcoxon (q001-q050 with mixed labels):
- BGE mean NDCG@10 = 0.6952 vs bi-encoder 0.8016
- Wilcoxon p=0.0008 (significant), direction negative
- n=25 was n.s. (p=0.54) — true direction hidden by low power
- Hypotheses: BGE trained on MS MARCO web, not academic; max_length=512 truncation; bi-encoder (all-MiniLM-L6-v2) more robust for academic

### LTR deprecation rationale
v3.9.7.3 n=50 (5-fold CV, mixed labels):
- LTR NDCG@10 = 0.7806 vs combined baseline 0.8141 (Δ=-0.0335)
- 100 trees on n=50 likely overfit
- Combined baseline (0.5*BM25 + 0.5*biencoder linear) hard to beat for academic abstracts

## Current code state (v3.9.7.4)

### Active features
- 5 English search engines: crossref / openalex / arxiv / semanticscholar / core
- v4_rerank: 5 conditions (bm25, biencoder, combined, prf, random) on n=50
- MoE router (`pa_cli/moe_router.py`): real 0.61 macro F1 on n=47
- BGE-rerank: **code exists but deprecated from default**
- LTR (LambdaMART): **code exists but deprecated from default**
- combined (0.5/0.5 linear) is default rerank
- Layer 6 (PDF download via 8-channel cascade) + Layer 7 (fulltext features):
  - `fulltext_bm25` ✅
  - `fulltext_citation_density` ✅ (v3.9.7.4 wired real page_count + citation_count)
  - `fulltext_venue_score` ✅ (v3.9.7.4, OpenAlex /sources lookup)
  - `fulltext_cross_encoder` ❌ (back-burner, BGE at abstract-level loses)
- CNKI skeleton (`pa_cli/cnki_channel.py`): cookies management + error codes + placeholder search; real playwright + parser **NOT wired** (waiting for user proxy + cookies)

### Disabled features
- semanticscholar + core engines: demo-api-key EXPIRED (per `pa keys check` output)
- BGE-rerank: deprecated (n=48 paired p=0.0008 negative)
- LTR: deprecated (loses to baseline in n=50)

### CLI subcommands
- `pa search` (5+1 engines with graceful CNKI skip)
- `pa fetch` (8-channel cascade)
- `pa review` / `pa review-topics` (lit review synthesis + topic clustering)
- `pa prisma` (PRISMA 2020 flow diagram)
- `pa cache` (P0-2 local cache)
- `pa mcp` (P0-3 public MCP install)
- `pa citations` (forward + backward citation walk via OpenAlex)
- `pa cnki {status,setup,search}` (NEW in v3.9.7.4)
- `pa keys` (API key registry)
- `pa version`

## Key files (paths from `G:\minimax - workspace\Paper agent`)

| File | Purpose |
|---|---|
| `pa_cli/cnki_channel.py` | CNKI 6th engine skeleton (new in v3.9.7.4) |
| `pa_cli/search.py` | 5+1 engine pool, `_try_import_cnki()` graceful skip |
| `pa_cli/cli.py` | Click command group, all `pa` subcommands |
| `pa_cli/__init__.py` | `__version__ = "3.9.7.4"` |
| `pa_cli/deep_rerank.py` | Layer 6+7, `extract_fulltext()` returns (text, page_count), `_openalex_venue_prestige()` |
| `pa_cli/moe_router.py` | Multi-class LightGBM router, line 202 fixed (qfile.suffix) |
| `pa_cli/ltr.py` | LambdaMART, line 165 fixed (qfile.suffix) |
| `pa_cli/cross_encoder.py` | BGE-reranker, deprecated from default |
| `pa_cli/ltr.py` | LambdaMART, deprecated from default |
| `bench/v01/queries.json` | 50 queries (q001-q025 real + q026-q050 user batch) |
| `bench/v01/labels_n50_mixed.json` | 50 queries with mixed labels (25 real + 25 auto A2) |
| `bench/v01/labels_q026_q050_auto.json` | 522 auto labels for q026-q050 |
| `bench/v01/labels_clean.json.real.bak` | Backup of real n=25 labels (v3.9.7.3 swap) |
| `bench/v01/system_outputs_combined/` | 50 .json files + 25 no-ext legacy (q001-q025) |
| `bench/v01/reports/v3_9_7_3_*.{json,md}` | v3.9.7.3 evaluation reports |
| `bench/v01/reports/v3_9_7_3_three_tier.md` | **Most important audit document** |
| `ROADMAP.md` | Source of truth, status discipline protocol |
| `BENCHMARK_TODO.md` | Back-burner list (LTR + BGE re-activation gates) |
| `CHANGELOG.md` | Per-version changelog, v3.9.7.3 + v3.9.7.4 entries |

## Pending user actions (blockers for next steps)

### For [P0-9] CNKI real implementation
User must provide:
1. **代理入口 URL** (校园 VPN / EZproxy / 机构图书馆代理)
2. **Login credentials** (账号密码 / 校园卡 / SSO)
3. **Test 1 cookie export session TTL** (典型 4-8h, vs CNKI direct 7-30d)

After user provides, next steps:
- Plan 2 (this session, if user wants): `Export-CNKICookies.ps1` (~50 LOC, 30 min)
- Plan 3 (after Plan 2): wire real playwright + HTML parser in `pa_cli/cnki_channel.py.search()` (1-2 day)

### For [P1-12] fulltext_cross_encoder
Back-burner per `BENCHMARK_TODO.md`. Will try monoT5/ColBERT after P0/P1 done.

### For [P1-13] n=100 expansion
A2 auto labels ready (test_output/_auto_label_q026_q050.py template).
User should review 5 sample queries (q026, q032, q040, q048, q049) to validate
A2 quality before doing n=100.

## Plan 2 — Export-CNKICookies.ps1 (next session work)

**Goal**: PowerShell script that exports CNKI cookies from user's logged-in
Chrome to `~/.paper-agent/cookies/cnki.json` (the file `pa_cli/cnki_channel.py`
reads from).

**Path**: `C:\Users\DengN\.mavis\bin\Export-CNKICookies.ps1` (per ROADMAP [P0-9])

**Design**:
1. Check playwright Python module installed
2. Launch Chromium (or use user's existing Chrome with remote-debugging-port)
3. Navigate to cnki.net (user must be logged in via proxy)
4. Extract cookies for `.cnki.net` domain
5. Save to `~/.paper-agent/cookies/cnki.json` (Playwright `context.add_cookies()` format)
6. Print: "CNKI cookies exported. N cookies. Run `pa cnki status` to verify."

**Estimated effort**: 30-60 min

**Files to add**:
- `C:\Users\DengN\.mavis\bin\Export-CNKICookies.ps1` (~50 LOC)
- Possibly `test_output/_test_export_cnki_cookies.ps1` (smoke test)

## Useful commands for fresh sessions

```bash
# Check current state
git -C "G:\minimax - workspace\Paper agent" log --oneline -8
git -C "G:\minimax - workspace\Paper agent" status -s

# Run pa CLI (smoke test)
cd "G:\minimax - workspace\Paper agent"
python -m pa_cli version
python -m pa_cli cnki status
python -m pa_cli search "deep learning" --limit 1

# Run v3.9.7.3 evaluation
python test_output/_run_n50_v3973.py
python test_output/_run_cross_encoder_wilcoxon_n50_v3973.py

# Inspect CNKI skeleton
python -m pa_cli cnki setup  # print user-facing instructions
```

## Memory notes

- agent memory has `iterdir + suffix filter — easy to skip unexpected files`
  (added 2026-07-15 from v3.9.7.3 bug discovery)
- user memory: "label 你帮我做吧" (2026-07-15, user delegates labeling to Mavis)
- project memory: see `ROADMAP.md` + `BENCHMARK_TODO.md` + this file

## Honest limits of this handoff

- **Auto labels are NOT expert-validated** — 522 pairs in `labels_q026_q050_auto.json`
- **CNKI search returns placeholder** — real playwright + parser NOT wired
- **BGE + LTR are deprecated but code still in repo** — easy to accidentally re-enable
- **demo-api-key EXPIRED** — S2 + CORE engines return empty; engines reported as 0 in by_engine
