# Session Handoff — paper-agent v3.9.11.3 (2026-07-23, post-GitHub-push)

> **Purpose**: Compact context for fresh sessions to quickly rehydrate.
> **Current state**: 2026-07-23, after stable release v3.9.11.0 + security audit v3.9.11.1-3 + GitHub push + LICENSE change to AGPL-3.0+No-AI-Training.
> **Latest commit**: `87f4275` (pushed to `https://github.com/croni4666-cmd/paper-agent`)
> **Next step (when user asks)**: continue any [P-N] from ROADMAP.md or wait for sample library data from user.

> **Older handoffs (superseded, archived)**:
> - `_session_handoff.md` — v3.9.9.6 era (2026-07-16). See ARCHIVED banner at top of that file.
> - Earlier `SESSION_HANDOFF.md` (v3.9.7.4) was OVERWRITTEN by this version.

---

## TL;DR — what changed 2026-07-20 to 2026-07-23 (v3.9.10.x → v3.9.11.3)

| Period | What shipped | Net effect |
|---|---|---|
| **v3.9.10.0 - 10.13** (2026-07-20) | 13 patch releases: simpler-rerank, pa-cite-check, pa-export-screening, pa-search-saved, pa-dedup-strict, pa-fetch-batch, pa-project (phase 1), README, http-get-json gzip fix, S2 throttle, quality filter, P0-8 12-feature LTR baseline, _load_dotenv() | All Tier-1/2 ROADMAP items from earlier audit shipped; P0-8 path A confirmed 12-feat = 8-feat (honest negative at n=25) |
| **v3.9.11.0** (2026-07-23) | STABLE series marker (MINOR bump, no code) | Signals to downstream: "v3.9.11.x is the maintenance series; no more 3.9.10.x patches" |
| **v3.9.11.1** (2026-07-23) | **CORE engine isolated** to `pa_cli/_engines_local/core.py` (gitignored) + `tools/install_core.py` (CORE code as string) | Public repo: CORE not in functional form. User runs `python tools/install_core.py` once after clone |
| **v3.9.11.2** (2026-07-23) | **Scanner fix** (`_pre_github_secret_scan.py` now checks BOTH `+` AND `-` lines in `git log -p`); filter-branch backup ref (`refs/original/`) deleted; gc prune | Pre-push scanner actually catches secrets in deleted content |
| **v3.9.11.3** (2026-07-23) | **Dangling blob cleanup** (1 dangling blob with leaked key found + removed via `git gc --prune=now`); `_test_verify_blob_clean.py` fixture (key obfuscated at runtime) | 0 leaks verified by 6 independent scans (1322 blobs checked) |
| **LICENSE change** (commit `1a25ca4`) | MIT → **AGPL-3.0 + No-AI-Training-1.0** | Company fork must open-source; no AI/ML/LLM training allowed (carve-outs for eval/personal use) |
| **GitHub push** (commits `1a25ca4` + `4aecdff` + `87f4275`) | `gh` CLI installed via winget; user authenticated via PAT (`repo`+`admin:org` scopes, stored at `$env:USERPROFILE\.gh_token`); repo `croni4666-cmd/paper-agent` (public) | All 6 v3.9.11.x commits pushed successfully via Clash proxy 7897 (Hangzhou IP rate-limited direct GitHub 443) |

## Current state — 3-tier honest report (v3.9.11.3)

### ✅ Working (production-quality)
- 7 search engines: **CNKI + AMiner + Crossref + OpenAlex + S2 + arXiv + CORE (opt-in via install script)**
- `pa fetch` (8-channel cascade, proxy-aware)
- `pa fetch-batch` (English batch, 7 Sci-Hub mirrors dead, ~3-4 channels deliver)
- `pa fetch-batch` CNKI guide (manual download workflow via xueshu789)
- `pa review` / `pa review-topics` (lit review synthesis + topic clustering)
- `pa build` / `pa scaffold` (manuscript pipeline, pandoc + GB/T 7714 CSL)
- `pa judge` (relevance judgement collection, sqlite)
- `pa cite-check` / `pa export-screening` / `pa search-saved` / `pa dedup-strict`
- `pa project` (multi-corpus, phase 1 done — init/list/status)
- `pa citations` (forward + backward citation walk)
- `pa prisma` (PRISMA 2020 flow diagram)
- `pa cache` (P0-2 local cache)
- `pa mcp install` (public MCP glue, replaces self-hosted [P0-3] revert 2026-07-04)
- **Default rerank**: combined (0.5*BM25 + 0.5*biencoder linear) — NDCG@10 = 0.814
- **NEW v3.9.11.x**: pre-commit hook (Python AST-based + git log -p scanner) prevents secret leaks

### ⚠️ Partial / mediocre
- MoE router: 0.61 macro F1 on n=47 (vs 0.89 fake on n=25; honest report)
- Recency filter: shipped but user said "metric deltas treat as noise"
- Layer 7 fulltext features: 3/4 working (BM25, citation_density, venue_score); cross_encoder deferred
- LTR / BGE-rerank: **code kept, deprecated from default** (n=50 paired Wilcoxon showed both lose to combined baseline)

### ❌ Blocked / won't fix (per Global Rule or upstream blocks)
- CNKI cite/dl count (5 paths blocked: CORS/captcha/404/non-DOM/proxy-mirror)
- Chinese paper tldr/inf_cite (S2 shallow entries)
- LLM-driven rerank (no hosted LLM per Global Rule)
- Self-hosted MCP server (already reverted 2026-07-04)
- n<100 label expansion for LTR/BGE evaluation (need user-provided data)

## Sample libraries (5 of them — waiting on user data)

Per user 2026-07-22 decision: all data-driven items transformed to **sample library** form
(add/status/remove scripts + JSON store). Library files are seeded; growth is user-driven.

| Library | Status | Files | Unblock condition |
|---|---|---|---|
| [P1-6] sub-topic | in-progress | `bench/v01/sub_topic_library.json` (4 parents × ~3 sub-topics = 13 total), `test_output/_add_lookup.py sub-topic`, `_status_lookups.py`, `_remove_lookup.py` | ≥10 user-verified sub-topics → thread into rerank |
| [P1-8] China inst exclusion | in-progress | `bench/v01/china_institution_exclusion.json` (4 categories, empty), same scripts | ≥10 user-added institutions |
| [P1-9] country metadata | in-progress | `bench/v01/country_metadata.json`, same scripts | ≥30 user-verified countries |
| [P1-21] MoE samples | in-progress | `bench/v01/moe_samples.json`, `_merge_moe_samples.py` (n=30 gate) | ≥30 user-verified MoE samples |
| (5th TBD) | n/a | n/a | n/a |

## Blocked-on-user items (waiting for data, not for design)

| ID | What I need | Why |
|---|---|---|
| [P1-13] n=50→n=100→n=200 | 25 expert labels (q051-q075) + 25 A2 auto (q076-q100) | n=50 is in noise zone per memory discipline; n=200 needed for LTR lift to be measurable |
| [P1-19] institution boost | P1-8 (≥10 inst) OR P1-9 (≥30 countries) accumulated | Tier definitions need real research data, not intuition |
| CORE key rotation | User applies at core.ac.uk (or escalates support) | User did try 2026-07-23, CORE returned same key. Will try again later or escalate. Until then, CORE is opt-in (v3.9.11.1 isolation) |
| [P0-9.1b] CNKI cite/dl | CNKI removes CORS OR xueshu789 mirrors multi-statusex OR user opts into paid captcha | 5 paths already probed, all blocked |

## Critical context for fresh sessions

### File paths
- `G:\minimax - workspace\Paper agent\` — repo root
- `pa_cli/__init__.py` — `__version__ = "3.9.11.3"`, `__license__ = "AGPL-3.0-only WITH No-AI-Training-1.0 restriction"`
- `pa_cli/search.py` — 7-engine pool, removed `search_core()` body (lazy import + stub)
- `pa_cli/_engines_local/core.py` — gitignored, generated by install script (2670 bytes)
- `pa_cli/_engines_local/__init__.py` — gitignored, auto-created
- `tools/install_core.py` — install/uninstall/verify, CORE code as string constant
- `LICENSE` — 36KB, full AGPL-3.0 + No-AI-Training rider
- `test_output/_pre_github_secret_scan.py` — pre-push scanner (FIXED v3.9.11.2)
- `test_output/_history_deep_scan.py` — independent deep scanner
- `test_output/_test_install_core.py` — fixture verifying install_core CORE string
- `test_output/_test_verify_blob_clean.py` — direct blob check (v1.2 with substring obfuscation)
- `test_output/_full_sweep_v3_9_11_3.py` — 10-check comprehensive sweep
- `test_output/_final_cross_check.py` — 7 additional cross-checks
- `test_output/_test_verify_push.py` — verify GitHub push (BOM-tolerant JSON)
- `$env:USERPROFILE\.gh_token` — user's GitHub PAT (NOT in repo, NOT in `.env`)

### GitHub
- **URL**: https://github.com/croni4666-cmd/paper-agent
- **Owner**: croni4666-cmd
- **Visibility**: public
- **Default branch**: main
- **License**: AGPL-3.0 + No-AI-Training-1.0
- **Description**: "Academic paper search, fetch, and lit-review synthesis CLI. 6 default + 1 opt-in (CORE) engines, pa judge relevance, pa build manuscript pipeline, Tier 2 research-topic projects."

### Commits since previous handoff (last handoff was v3.9.7.4 commit `19b032d`)
```
87f4275  docs: polish README Quick start + Known limitations
4aecdff  test: rename _verify_push.py to _test_verify_push.py (tracked fixture)
1a25ca4  docs: replace MIT with AGPL-3.0 + No-AI-Training-1.0 license
30baa09  docs: reorder CHANGELOG (v3.9.11.x entries above v3.9.11.0) + README + cross-check
76a1a6b  test: add _full_sweep_v3_9_11_3.py (10-check comprehensive sweep)
c841f48  security: v3.9.11.3 dangling blob cleanup + direct-blob fixture
0e048ba  security: v3.9.11.2 scanner fix + filter-branch backup cleanup
9a62200  feat(arch): v3.9.11.1 CORE engine isolated to local-only file
(plus many v3.9.10.x commits, see ROADMAP.md "Versioned roadmap summary" table)
```

### Pre-push security audit (final state, 17/17 checks)
- `_pre_github_secret_scan.py` — "Safe to push to GitHub"
- `_history_deep_scan.py` — NO LEAKS FOUND IN HISTORY
- `_test_install_core.py` — install_core.py CORE string is clean (uses env var)
- `_test_verify_blob_clean.py` — 1895 total objects, 1322 blobs, 0 with key
- `_full_sweep_v3_9_11_3.py` (10 checks) — 0 fails
- `_final_cross_check.py` (7 cross-checks) — 0 fails
- `git fsck --unreachable/--dangling` — empty
- `git count-objects` — garbage: 0, size-garbage: 0
- Refs: only `refs/heads/main` (no `refs/original/`)

### How to use the security infra in future
**Before any GitHub push**, run in this order:
```bash
# 1. Quick check (5-10s)
python test_output/_pre_github_secret_scan.py

# 2. Deep history check (10-30s)
python test_output/_history_deep_scan.py

# 3. Direct blob check (3-10s)
python test_output/_test_verify_blob_clean.py

# 4. Comprehensive sweep (30-60s)
python test_output/_full_sweep_v3_9_11_3.py

# 5. Cross-check (20-40s)
python test_output/_final_cross_check.py
```
All 5 must show 0 fails before pushing. If any fail, **fix locally + amend** (no force-push with secrets in history).

## Useful commands for fresh sessions

```bash
# Check current state
git -C "G:\minimax - workspace\Paper agent" log --oneline -10
git -C "G:\minimax - workspace\Paper agent" status -s
git -C "G:\minimax - workspace\Paper agent" remote -v

# Run pa CLI (smoke test)
cd "G:\minimax - workspace\Paper agent"
python -m pa_cli version
python -m pa_cli search "deep learning" --limit 1
python -m pa_cli cnki status

# GitHub push (if network blocked, use Clash 7897)
$env:HTTPS_PROXY = "http://127.0.0.1:7897"
git push origin main
$env:HTTPS_PROXY = $null

# Check sample library status
python test_output/_status_lookups.py
```

## Honest limits of this handoff

- **5 sample libraries waiting on user data** — no automated growth; user must run `add` scripts
- **CORE engine opt-in** — new clone won't have CORE; user must `python tools/install_core.py`
- **CORE key in same state as last handoff** — user applied 2026-07-23, got same key back; no real rotation yet
- **GitHub username `croni4666-cmd`** — auto-generated by GitHub OAuth; user chose not to rename
- **Hangzhou China Telecom rate-limits GitHub 443** — use Clash proxy 7897 for push (7897=HTTP, 7899=SOCKS5, NOT default 7890)
- **Pre-commit hook + scanner** — both layers must be in place before any future push
- **PaSa full fork = not done** — pasa_lite is the rule-based 50% subset; full PaSa requires LLM (Global Rule violation)
- **n=25 LTR evaluations** — in noise zone per memory discipline; n>=100 needed for honest signal

## What user wants from Mavis (cross-project preferences in play)

- **Honest 3-tier reporting** (✅ / ⚠️ / ❌) over polished summaries — always lead with this
- **No 1-by-1+1** "test until done" / "audit until 0 issues 2 consecutive rounds" — discipline matters
- **No new dependencies** unless absolutely necessary (used stdlib `gzip` for brotli fix, stdlib `unittest.mock` for scanner)
- **Module-level isolation, not just key-level** for security-sensitive code (CORE pattern)
- **Clash proxy 7897** for network-blocked pushes (verge-mihomo, non-default port)
- **AGPL-3.0 + No-AI-Training** license for any project user owns

## Memory notes (already in agent memory)

- Secret scanner must check BOTH `+` AND `-` lines in `git log -p`
- `git cat-file --batch-check` output has 3 columns (sha type size), not 2
- Pre-commit hook may block legitimate search-pattern fixtures — use `--no-verify`
- User prefers module-level isolation for security-licensed code
- User's local Clash ports: 7897 (HTTP), 7899 (SOCKS5)
- PaSa vs pasa-lite: don't fork
- Mavis = synthesis LLM, paper-agent = CLI tool (don't conflate)

---

**End of SESSION_HANDOFF.md** (2026-07-23 15:33, post-v3.9.11.3 + GitHub push)
