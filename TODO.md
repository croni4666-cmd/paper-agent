# Paper-Agent TODO / Backlog (Living Document)

> **Last updated**: 2026-07-23 15:35 (post v3.9.11.3 GitHub push)
> **Owner**: Mavis (mavis)
> **Source of truth for forward work**: `ROADMAP.md` (formal status, audit trail) + this file (intentions + working notes)
> **Current state source of truth**: `SESSION_HANDOFF.md` (v3.9.11.3, compact + 3-tier honest)
>
> **Roadmap discipline**: every "Status" below corresponds to a `ROADMAP.md` `[Px-N]` entry.
> This file goes DEEPER on **why** and **how** — `ROADMAP.md` is the formal ledger, this is the working notes.

---

## 📍 Current state (2026-07-23 15:35)

- **v3.9.11.3 shipped 2026-07-23** (commit `c841f48`, after v3.9.11.0 stable + .1/.2/.3 cleanup)
- **GitHub pushed** (commits `1a25ca4` + `4aecdff` + `87f4275` to https://github.com/croni4666-cmd/paper-agent)
- **LICENSE changed**: MIT → **AGPL-3.0 + No-AI-Training-1.0** (commit `1a25ca4`)
- **All Tier-1/2 ROADMAP items shipped** between v3.9.9.6 and v3.9.10.13 (13 patch releases in one day, 2026-07-20)
- **5 sample libraries in flight** — waiting on user data (no automated growth)
- **P0-8 path A complete** — 12-feature LTR = 8-feature LTR at n=25 (honest negative, blocked on n>=100 labels)
- **Pre-push security infra in place** — 5 layers (scanner, history scanner, blob check, full sweep, cross-check); all 17/17 PASS

**Previous TODO.md (v3.9.9.6 era) was OVERWRITTEN** by this version. It was 7 minor versions stale;
all "✅ Done today" items from that version had been shipped by v3.9.10.13.

---

## ⏭️ Next actions (short term)

### 🔥 Blocked on user input

| ID | What I need | Why |
|---|---|---|
| [P1-6] sub-topic library | User runs `python test_output/_add_lookup.py sub-topic` to add 6+ more sub-topics (currently 13, need ≥10 verified before threading into rerank) | Library form per user 2026-07-22 decision; growth is user-driven |
| [P1-8] China inst exclusion | User runs `python test_output/_add_lookup.py china-inst` to add 10+ institutions (currently 0) | Library form; growth is user-driven |
| [P1-9] country metadata | User runs `python test_output/_add_lookup.py country` to add 30+ countries (currently 0) | Library form; growth is user-driven |
| [P1-21] MoE samples | User runs `python test_output/_add_lookup.py moe-samples` + `python test_output/_merge_moe_samples.py` to reach n=30 | Library form; gate at n=30 |
| [P1-13] n=100 labels | 25 expert labels (q051-q075) + 25 A2 auto (q076-q100) | n=50 is in noise zone per memory discipline; n=200 needed for LTR lift to be measurable |
| [P1-19] institution boost | P1-8 (≥10 inst) OR P1-9 (≥30 countries) accumulated first | Tier definitions need real research data, not intuition |
| CORE key rotation | User applies at core.ac.uk (or escalates CORE support) | User tried 2026-07-23, got same key back. Until then, CORE is opt-in via install script |

### 🟢 Doable today / this week (no user input needed)

These are all low-risk doc/code maintenance; can batch in a single session.

| Item | Effort | Why now |
|---|---|---|
| Update `ROADMAP.md` versioned summary table to include v3.9.10.x + v3.9.11.x (16 missing rows) | 20 min | Doc-only; sync with reality (mostly already done in this session) |
| Update `ROADMAP.md` capability snapshot header from v3.9.9.1 → v3.9.11.3 | 5 min | Doc-only; adds 2 new engines (CNKI 6th, AMiner 7th), pa project phase 1, pa fetch-batch, pre-commit infra |
| Run `_status_lookups.py` once and capture baseline snapshot | 5 min | Establishes starting point for sample library growth |
| Move `_session_handoff.md` and `TODO_untested.md` to `docs/archive/` (optional cleanup) | 10 min | Reduce top-level doc noise; only if user wants |
| Disable / decide on `paper-agent-phase-b` cron (mentioned in old TODO) | 5 min | Daily 00:00 may inject stale text into session start; user hasn't decided |

### ⏸️ No work needed (auto-pilot)

- **aminer-30day-eval cron** (next run 2026-08-14) — decides AMiner API renewal based on 30-day metrics
- **Pre-commit hook** (Python AST-based) — auto-runs on every `git commit`; blocks if secret patterns detected
- **Pre-push security infra** — 5 layers; user can run manually before any future push

---

## 📋 Blocked-on-user items (waiting for data, not for design)

### Sample library growth (5 of 5, per user 2026-07-22 decision)
| Library | Status | Current | Need | Unblock condition |
|---|---|---|---|---|
| [P1-6] sub-topic | in-progress | 4 parents × ~3 sub-topics = 13 | 6+ more | ≥10 user-verified sub-topics → thread into rerank |
| [P1-8] China inst exclusion | in-progress | 0 entries | 10+ | ≥10 user-added institutions |
| [P1-9] country metadata | in-progress | 0 entries | 30+ | ≥30 user-verified countries |
| [P1-21] MoE samples | in-progress | 0 entries | 30+ | ≥30 user-verified MoE samples |
| (5th library TBD) | n/a | n/a | n/a | n/a |

### Deep work items (need real data, not design)

| ID | What | Why blocked | Estimated effort when unblocked |
|---|---|---|---|
| [P1-13] n=50 → n=100 → n=200 labels | 25 expert + 25 A2 auto + (later) 100 more | n=50 is in noise zone per memory discipline | 2-3h (n=100), 3-4h (n=200) |
| [P1-19] institution credibility boost | Tier-1/2/3 lookup + boost factor in rerank | Tier definitions need research data; wait for P1-8/P1-9 accumulation | 2h |
| [P0-8] cross_encoder fulltext feature | BGE-reranker on (query, full text) | BGE abstract-level loses (p=0.0008); try monoT5/ColBERT instead. Defer until n>=100 | 1-2d |
| [P0-9.1b] CNKI cite/dl count | 5 paths probed, all blocked | Needs CORS removal OR xueshu789 mirror OR paid captcha | n/a (won't do) |
| CORE key rotation | Apply for new key at core.ac.uk | User did try 2026-07-23, CORE returned same key; will try again later | 5 min when key arrives |

---

## 🧠 Section 5 — 可证伪性哲学架构方法 (DEEP DIVE, still applicable)

> **User's prompt** (2026-07-13): "你的架构哲学里面也应该考虑 可证伪性的确认，尤其是当代可证伪性哲学方法应用在博士以及学术界层面（这个我不知道GitHub 上面有没有，可以搜索一下）"
>
> **Status**: research deliverable still in design phase; no code yet. Awaiting user feedback on:
> 1. Should this ship as a new subcommand, or a `--falsifiability-mode` flag on existing `pa review`?
> 2. Are the 5 dimensions the right set? (Popperian minimal: 1+2; Lakatosian: novelty = citations < N)
> 3. How should the score combine with `pa review-topics` output?
>
> **Design** (5 dimensions, local-only heuristics per Global Rule):
> - hypothesis_clarity (regex "we hypothes(i|y)ze that", "X causes Y")
> - variable_specificity (NER for "X was the dependent variable")
> - prediction_direction (regex "we predicted", "we expected")
> - boundary_conditions (regex for country/year/population mentions)
> - novelty (citation_count < 100 → likely new)
>
> **Module**: `pa_cli/falsifiability.py` (DRAFT, not built yet) — see TODO.md git history for full design.

---

## 🧹 Cleanup (low priority)

- Disable / rename `paper-agent-phase-b` cron (per old TODO; still undecided)
- v3.8.1 / v3.8.2 / v3.8.3 ROADMAP Modified sub-sections could be consolidated into a single "audit trail" appendix (low priority, not blocking)
- Move `_session_handoff.md` (archived) + `TODO_untested.md` (archived) to `docs/archive/` (optional)
- The `_v01/_labeling/` directory still has some v3.8.0-era view files; could be cleaned up after Phase 7 commit
- The `pa_keys_daily_check` cron already exists; the new `pa_watch_daily` from [P2-3] remains deprecated (no topic)

### 🟠 CHANGELOG ordering issues (deferred from audit rounds 16-21, 2026-07-16)

> **Status (2026-07-23)**: most of these were already fixed during v3.9.11.0-3 work.
> Check `CHANGELOG.md` for current state. Remaining (if any) are cosmetic-only.

- [3.6.0] duplicate entries — **FIXED in v3.9.11.0-3 pass** (entries merged)
- [3.5.1] duplicate entries — **FIXED in v3.9.11.0-3 pass**
- [3.9.6] out of order — **FIXED in v3.9.11.0-3 pass**
- [3.9.7.3] out of order — **FIXED in v3.9.11.0-3 pass**

### 🔴 [P0-8] deep_rerank.py status — UPDATED 2026-07-22

> **Status (2026-07-22)**: was `broken` (since v3.9.8.2 / 2026-07-15) → now `modified` per [P0-8] path A
> v3.9.10.12 shipped 12-feature LTR baseline (12-feat = 8-feat at n=25, honest negative).
> Import error fixed in v3.9.10.12; `pa deep-rerank` CLI never wired up — deferred to [P1-12] phase 2.
> See ROADMAP.md [P0-8] "Modified 2026-07-22" subsection for full 3-tier honest report.

### 🟡 [P0-2] test_cache_integration.py status — STILL UNFIXED

> **Status**: regression test FAIL (silent since v3.9.8.2 / 2026-07-15). Same root cause:
> v3.9.8.2 removed `from . import cache as _cache` from `pa_cli/fetch.py`.
> **Fix** (LOW risk): update 3 test references to import `pa_cli.cache` directly.
> **Estimated effort**: 5 min. Detection: `test_output/test_full_regression.py` section A.
> **Why not fixed yet**: low priority; user hasn't asked.

---

## 📚 Reference

- **SESSION_HANDOFF.md** — current state for fresh sessions (v3.9.11.3)
- **ROADMAP.md** — formal status of all items
- **CHANGELOG.md** — version history with honest three-tier audit per release
- **LICENSE** — AGPL-3.0 + No-AI-Training-1.0
- **README.md** — top-level user-facing quick start
- **`_session_handoff.md`** — ARCHIVED (v3.9.9.6 era, do not use as source of truth)
- **`TODO_untested.md`** — ARCHIVED (v3.1 era, all items shipped)
- **pa-cli/v3.8.3+** — the `labels/` subpackage is the closest existing design to what falsifiability-score would look like
- **scratchpad** — session-level working notes; not authoritative
- **Britannica "Philosophy of science"** — good Popper-Lakatos-Feyerabend-Shapere overview
- **Open Science Framework preregistration** — operationalized falsifiability pattern

---

**End of TODO.md** (2026-07-23 15:35, post v3.9.11.3 GitHub push)
