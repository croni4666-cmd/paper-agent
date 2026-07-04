# Changelog

All notable changes to Paper Agent Skill.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
- **MAJOR** (v3 → v4): architecture redesign, breaking config / API
- **MINOR** (v3.0 → v3.1): new searcher / new phase / new key, additive
- **PATCH** (v3.1.0 → v3.1.1): bug fix, no API change

---

## [3.3.0] - 2026-07-04

### Added — `pa_cli/keys.py` API key registry + reminder system (validated)

Complete 5-command group under `pa keys` for managing API key lifecycles.

**Commands** (all validated end-to-end 2026-07-04):
- `pa keys list` — table view with status indicators (✓/⏰/⚠/🚨/❌/✗)
- `pa keys check [service]` — live HTTP probe per service, updates `last_checked`
- `pa keys add <service> <value>` — add/rotate, writes `.env` + registry, auto-probes
- `pa keys audit` — count active/expiring/missing, show never-checked/never-used
- `pa keys remind` — print expiry warnings + write alerts file

**Live probe results (2026-07-04)**:
| service | endpoint | status | http |
|---|---|---|---|
| openalex | api.openalex.org | ok | 200 |
| semanticscholar | api.semanticscholar.org | http-429 (transient rate limit; unrelated to key config) | 429 |
| core | api.core.ac.uk | ok | 200 |
| unpaywall | api.unpaywall.org | ok (real email <REDACTED-UNPAYWALL-EMAIL>) | 200 |
| demo-api-key | (no service_url set) | no-probe-url (skipped) | n/a |

**End-to-end `pa fetch` validation**:
- DOI `10.1038/nature12373` (Nature article)
- 8-channel pipeline ran in <2s
- OpenAlex → arxiv.org/pdf/1304.1068 → 2.36 MB PDF saved
- `%PDF-1.5` magic verified, valid PDF
- Confirms: fetch pipeline + openalex channel + Unpaywall integration all wired correctly

**Auto-reminder hook**:
- `main()` calls `load_env_into_environ()` then `cmd_remind(quiet=False)` on every CLI invocation
- stderr-line reminder: `[pa-keys] ⚠ demo-api-key: expires in 5 days — schedule rotation → pa keys add demo-api-key <new_key>`
- Non-intrusive: only fires when warnings exist

**Daily cron** (`pa-keys-daily-check`, mavis agent):
- schedule `0 9 * * *` Asia/Shanghai
- Runs `pa keys check --write-alerts ~/.mavis/state/api_key_alerts.json`
- Reads alerts file + surfaces warnings to user

**Registry on disk** (`keys_registry.json`):
- 5 services registered with metadata (service / env_var / tier / expires / notes)
- Committed to git (NO secrets; only metadata)
- Real `.env` (gitignored) holds the actual keys

### Fixed — bug fixes from end-to-end smoke test

1. `.env` loader regex: allow hyphens in env var names (e.g. `DEMO-API-KEY_API_KEY`)
   old: `r'^[A-Z_][A-Z0-9_]*'` — fails on hyphens
   new: `r'^[A-Za-z_][A-Za-z0-9_-]*'` — covers all OpenAlex-style mixed-case names
2. `cmd_remind` auto-trigger: was `quiet=True` (suppressed) — now `quiet=False`
   so every CLI invocation prints expiring/expired warnings to stderr.
   User feedback: "记得提醒我再导入之" — proactive reminders required.
3. Click `--write-alerts` / `--alert-file` options: now accept optional string
   via `metavar="PATH"` instead of bare `default=None` — no more "requires an argument".

### Validation — pa-keys smoke test summary

| step | result |
|---|---|
| `pa keys list` (5 keys) | 4 active + 1 expiring-week |
| `pa keys check` | 3 ok + 1 transient-429 + 1 skipped |
| `pa keys add unpaywall <real-email>` | live probe 200 OK |
| `pa keys add demo-api-key --expires +5d` | warn + write + auto-probe |
| `pa fetch 10.1038/nature12373` | 2.36 MB PDF via openalex/arxiv |
| Startup auto-reminder | stderr line printed on every CLI call |
| Daily cron registered | `mavis cron` shows `pa-keys-daily-check` |

---

## [3.2.0] - 2026-07-04

### Added — `pa_cli/` package (paper-agent CLI)

Lightweight Click-based CLI exposing 4 commands for programmatic + scriptable access:

```
python -m pa_cli fetch <DOI>      # 8-channel PDF recovery + CF timeout handoff
python -m pa_cli search <query>   # 5-engine academic search with dedup
python -m pa_cli review <dir>     # corpus → lit review synthesizer (PyMuPDF)
python -m pa_cli version          # dependency status
```

Each command is independent and testable; the package adds no breaking
changes to the existing `paper_fetcher.py` / `paper-agent skill` API surface.

#### `pa fetch` (pa_cli/fetch.py, 8 channels)
- **Channel 1 — OpenAlex Work API**: discovers OA locations; tries each in turn
- **Channel 2 — arXiv SDK**: only for `10.48550/...` DOIs
- **Channel 3 — Unpaywall API**: legal OA via registered email
- **Channel 4 — DOI.org redirect**: detects Gold OA, extracts PDF links from HTML
- **Channel 5 — Playwright /doi/pdf/ URL pattern**: T&F-style server-side PDF
- **Channel 6 — Playwright fallback**: last-ditch Cloudflare challenge attempt
- **Channel 7 — Sci-Hub mirror rotation**: gray; user-consent assumed
- **Channel 8 — Unpaywall PDF inline**: post-discovery fetch
- Hard cap `--max-total-sec 300` (paper-agent v4 principle)
- On cap or all-fail: surfaces JSON `handoff` block with `user_action_required`

#### `pa search` (pa_cli/search.py, 5 engines)
- Crossref / OpenAlex / arXiv / Semantic Scholar / CORE (CORE/S2/OA keys via env)
- `--year-min` / `--year-max` / `--limit` / `--engine` / `-o`
- Dedup by DOI (arXiv ID fallback), merged with `found_by: [...]` arrays
- Returns unified JSON sorted by `cited_by_count` desc

#### `pa review` (pa_cli/review.py, PyMuPDF + template)
- Walks corpus dir, extracts text per PDF, classifies full-text vs abstract-only
- `--word-count-min 1000` threshold (default)
- Outputs structured markdown ready for LLM-driven deeper synthesis
- Abstract-only papers flagged for v4 handoff

### Added — paper-agent v4 design principle

After 5 minutes of Cloudflare challenge failure, **stop iterating and surface
a "your turn" handoff** to the user. Real human browser sessions remain the
only reliable Cloudflare bypass for academic PDF recovery.

Cloudflare protects ~70% of academic PDF endpoints (Elsevier, T&F, worktribe,
ResearchGate, Anna's Archive) with checks Playwright headless cannot pass:

1. TLS JA3 fingerprint
2. HTTP/2 frame order
3. Canvas / WebGL fingerprint
4. `navigator.webdriver` flag
5. Sec-CH-UA-* client hint headers
6. Mouse-movement entropy (real human Bezier)
7. `cf_clearance` cookie timing (15-30 min TTL, bound to IP + UA + TLS hash)

CLI / fetch codifies this as `--max-total-sec 300` hard cap and a `handoff`
JSON block; downstream callers must respect it instead of iterating stealth
parameters.

### Added — `pa_cli/keys.py` API key registry + reminder system

Two-layer storage:
- `.env` (gitignored): actual secrets, never committed
- `keys_registry.json` (committed): metadata only — service, env var, tier,
  expiry date, last-checked, last-used, notes

#### CLI commands

```
pa keys list                       # show all keys + status indicators
pa keys check [service]            # live probe (HTTP) each key, updates last_checked
pa keys add <service> <value>      # add or rotate, writes .env + registry + live-probes
                                   # flags: --expires YYYY-MM-DD, --tier free|paid|institutional, --notes
pa keys audit                       # count active/expiring/expired/missing; show never-checked
pa keys remind                      # print expiry warnings; write alerts file
```

Status indicators: `✓ active` / `⏰ expiring-soon (≤14d)` / `⚠ expiring-week (≤7d)` /
`🚨 expiring-today` / `❌ EXPIRED` / `✗ missing`.

#### Reminder hook

`main()` calls `load_env_into_environ()` then `cmd_remind(quiet=True)` on every
CLI invocation. If any key has `expires` within 14 days or is already expired,
a single-line `[pa-keys] <warning>` is written to stderr before the actual
subcommand output. Non-intrusive — `pa fetch`, `pa search`, `pa review`
behaviour unchanged unless a warning is active.

#### Daily cron

New cron job `pa-keys-daily-check` (mavis agent, `0 9 * * *` Asia/Shanghai)
runs `pa keys check --write-alerts ~/.mavis/state/api_key_alerts.json` daily
and reads the alerts file to surface expiry warnings to the user. The
alerts file is also written on every `pa keys check` invocation, so
non-cron runs of `pa keys check` also feed the cross-session reminder
channel.

#### Default registry (committed)

| service | env_var | tier | expires | notes |
|---|---|---|---|---|
| openalex | OPENALEX_API_KEY | free | none | 1 RPS dedicated; no expiry reported |
| semanticscholar | S2_API_KEY | free | none | x-api-key header; no expiry reported |
| core | CORE_API_KEY | free | none | Bearer token; no expiry reported |
| unpaywall | UNPAYWALL_EMAIL | free | none | email registration; no API key needed |

Users add `expires` field via `pa keys add --expires YYYY-MM-DD` to opt into
expiry tracking — for paid-tier keys, institutional subscriptions with
quarterly rotation, etc.

### Added — full-text corpus recovery (8/8, +109% word count)

Recovered all 3 abstract-only papers via human browser handoff:

| Paper | Recovery method | Words extracted |
|---|---|---|
| McMinn / He et al. 2025 | T&F `/doi/pdf/` direct via Chrome | 12,040 |
| Tzirides et al. 2024 | Nottingham institutional repository via Chrome | 11,622 |
| Southworth et al. 2023 | ScienceDirect Gold OA via Chrome | 10,700 |

Plus the 5 papers already full-text in v3 corpus. Total extracted word
count: **~70,000** (up from ~33,500 in v3, +109%).

`Lit_Review_Section_AI_Literacy_v32_FT.md` updated: §5 reorganised into 4
sub-sections (5a Utami ADDIE / 5b McMinn HKUST / 5c Southworth QEP / 5d
Tzirides cyber-social); §6 gains a fifth methodological observation; §7
now offers 7 claims (added institutional-pathway 4-model portfolio and
full-text recovery as resolved citation-graph bias). Author order for paper
[3] corrected from "Rohadi & Utami" to **"Utami & Rohadi"** per
`final_8_papers.json`.

### Validation — CLI smoke tests

```
$ python -m pa_cli version
paper-agent CLI v3.2.0
[OK] click    8.4.1
[OK] pymupdf  1.27.2.3
[OK] arxiv    4.0.0
[OK] requests 2.33.1

$ python -m pa_cli search "AI literacy higher education" --year-min 2023 --limit 3 --engine openalex
→ 3 results, top: Chan & Hu 2023 (1819 citations, diamond OA)

$ python -m pa_cli review ./pdfs --output lit_review.md
→ 6 PDFs, 58,821 words, 6/6 classified full-text
```

---

## [3.1.0] - 2026-07-03

### Added — 3 new searcher interfaces

1. **CORE.ac.uk v3 searcher** (`skill/core/api_pool/searchers/core.py`, 198 lines)
   - Direct HTTP client to `https://api.core.ac.uk/v3/search/works`
   - Auth: Bearer token via `CORE_API_KEY` env var
   - 1 RPS dedicated rate limit, 429 → graceful return `[]`
   - year filter syntax: `yearPublished >= YYYY` (not `yearPublished:>=YYYY` — colon form returns 500)
   - 4xx/5xx → graceful `[]` (no `RateLimitError` raise)
   - 401/403 → auto-disables for current session
   - 80%+ CORE papers have DOI; remainder fall through to title+year dedup

2. **Semantic Scholar API key support** (`skill/core/api_pool/searchers/semanticscholar.py`)
   - New `api_key` constructor param (env: `S2_API_KEY`)
   - Sent as `x-api-key` header (per S2 official docs)
   - With key: 1 RPS dedicated pool; without: shared anonymous pool
   - When key present, `health_check()` reports True reliably; without, intermittent 429s

3. **OpenAlex key already-supported, now enabled** (`searchers/openalex.py` + `.env`)
   - `OpenAlexSearcher(api_key=...)` was always supported; v3.1 just adds key
   - 1 RPS dedicated with key (per OpenAlex docs)
   - Priority pool access vs polite-email-only

### Added — 2 API keys integrated (`.env`)

- `CORE_API_KEY=...` (32 chars) — drives CORE searcher
- `S2_API_KEY=s2k-...` (44 chars) — drives S2 searcher key mode
- `OPENALEX_API_KEY=...` (22 chars) — drives OpenAlex searcher key mode

`.env` is git-ignored; do not commit it.

### Changed — SearchPool v3.1 wiring

- 5-engine pool: Crossref / S2 / arxiv / OpenAlex / CORE
- `SearchPool(polite_email, openalex_api_key, s2_api_key, core_api_key)` — 3 new optional kwargs
- `search_with_searchpool()` default `min_per_source` changed `0` → `max_per_channel` (v3.1 critical fix)
- `paper_fetcher._get_search_pool()` and `search_with_searchpool()` now read all 3 keys from `os.environ`
- `min_per_source>0` interleave logic (Phase 4 fix, 2026-07-03) preserved: round-robin truncation by source

### Changed — S2 backoff tune (Phase 4 → Phase 6)

- Old: 1 retry, 15s backoff, total worst case 17s
- New: 2 retries, 30s + 60s backoff, total worst case 150s
- Reason: diagnostic 2026-07-03 showed S2 1 RPS is *sustained* not burst — 4s follow-up still 429s; old 15s gave up too early
- Still returns `[]` (not raise) so SearchPool moves on to other engines

### Fixed — 4 pre-existing bugs (discovered running v3.1 end-to-end)

1. **`pipeline.py` missing `import datetime`** — Phase E and F used `datetime.date.today()` and NameError'd on import. Fixed by adding `import datetime`.
2. **`paper_fetcher.fetch_all_channels` declared in `__all__` but never defined** — `pipeline.run_search_screen_pipeline()` failed at import. Fixed by adding a thin wrapper that delegates to `search_with_searchpool`.
3. **`pipeline.run_search_screen_pipeline()` body referenced `kwargs` but signature lacked `**kwargs`** — Stage 3.5 (relevance ranking) NameError'd. Fixed by adding `**kwargs: Any` to signature.
4. **`search_with_searchpool()` defaulted `min_per_source=0`** — Crossref-first engine filled the bucket and stopped, so S2 / OpenAlex / CORE never fired in pipeline runs. Fixed by defaulting `min_per_source=max_per_channel`.

### Security

- `.gitignore` created — excludes `.env` (API keys), `__pycache__/`, `cache/`, `results/`

### Verified end-to-end

- Topic: `_example_ai_education`
- Query: "generative AI literacy higher education"
- Result: 5 papers from 3 engines (S2 2 + Crossref 2 + OpenAlex 1), 2/3 passed 3-stage screen, 1/2 PDF download, 8 fields extracted, 2 topics modeled, 9.0/16 quality, PRISMA + Role Reflection + 21 prompt improvements generated
- Runtime: 21.7s (search 75s → 21.7s in pipeline because Crossref-5 cap means fewer calls)

### Known limitations (carried over from v3.0.1)

- S2 with key still throttles in practice (1 RPS is *sustained*, not burst); 4s follow-up can 429
- 5-engine search worst case (S2 30s+60s backoff + others) ≈ 75-150s
- CORE `journals` field is often empty; venue falls back to None
- Some publishers (MDPI, Wiley, Elsevier) block PDF download via known_pitfalls in topic yaml
- No remote git remote; commits are local-only

---

## [3.0.1] - 2026-07-02

### Fixed — v3.0 regressions in pool / searcher stability

- OpenAlex `pyalex` 5xx hangs → `ThreadPoolExecutor` timeout
- OpenAlex credit-exhausted signal → return `[]` (not raise `RateLimitError`)
- S2 429 → return `[]` after 15s backoff (later tuned to 30s+60s in v3.1)
- Pool dedupe by arxiv_id (Phase 4 fix) for cross-source arxiv preprint matching
- Pool min_per_source>0 round-robin truncation (Phase 4 fix)
- Crossref year extraction fallback (created/deposited date-parts)

### 4 searchers (pre-CORE)

- Crossref (habanero wrapper, polite pool)
- Semantic Scholar (no key, shared pool)
- arxiv (arxiv.py wrapper)
- OpenAlex (pyalex wrapper, polite email; key optional but unused)

---

## [3.0.0] - 2026-06-25

Initial v3 release. Single-searcher-only architecture replaced by SearchPool.

- `skill/core/api_pool/pool.py` introduced
- `paper_fetcher.py` rewritten to use SearchPool
- Topic-agnostic: `skill/topics/_example_ai_education.yaml` example
- 4 phase pipeline (A download → B extract → C topic model → D quality+PRISMA)
