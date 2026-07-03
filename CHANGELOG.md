# Changelog

All notable changes to Paper Agent Skill.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
- **MAJOR** (v3 → v4): architecture redesign, breaking config / API
- **MINOR** (v3.0 → v3.1): new searcher / new phase / new key, additive
- **PATCH** (v3.1.0 → v3.1.1): bug fix, no API change

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
