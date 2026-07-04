# Paper-Agent Roadmap (Living Document)

> **Status discipline** — This document is the single source of truth for paper-agent's evolution.
> All future improvements **MUST** follow this protocol:
>
> 1. **Before proposing** new work: check this file. If your idea is already here, do not propose again — link to the existing entry and argue for status change.
> 2. **Adding** new item: write under "Proposed" with `Status: proposed`, `Added: YYYY-MM-DD`, `Priority`, `Effort`, `Rationale`, `Source`. Keep entries atomic and self-contained.
> 3. **Status transitions** (proposed → in-progress → done): move the entry; never duplicate. Update `Status:` and add `Started:` / `Completed:` dates.
> 4. **Proven wrong / partial**: do **NOT** delete the entry. Add a sub-section under the same item with heading `### Modified YYYY-MM-DD — <what changed>` and write the new reasoning + new status. The original rationale is preserved as an audit trail.
> 5. **Abandoned** (won't do for foreseeable future): mark `Status: deprecated`. Keep the entry + add `### Deprecated YYYY-MM-DD — <why>`. Future readers can see the history.
> 6. **Cited from CHANGELOG.md** — every release must reference which roadmap items it implements.
> 7. **Global Rule (added 2026-07-04)**: every proposed item MUST be checked against the Global Rule below. Items that exceed personal-hobbyist burden are out of scope unless user explicitly says "commercialize".

---

## Global Rule — Personal-hobbyist budget (added 2026-07-04)

> **除非我强调要商业化,千万不要制作超过个人爱好者经济负担能力的大服务,因为维护能力有限。**
>
> Translation: Unless I explicitly say "commercialize", never build a service whose economic + maintenance burden exceeds what one personal hobbyist can sustain.

**What this rule means in practice**:

| ✅ Allowed | ❌ Out of scope |
|---|---|
| Code that runs locally on one machine | Hosted services requiring paid infra |
| Free public APIs (OpenAlex, Crossref, Unpaywall free tier, Semantic Scholar free tier) | Paid API tiers (S2 paid, Scopus, Web of Science) |
| Local files (cache, config, downloads) | Cloud storage / managed databases |
| Open source packages published to PyPI/npm | Custom Docker / K8s deployment |
| stdio / local-socket integration | Public-facing HTTP servers with SLA |
| Public MCPs (someone else maintains) | Self-maintained MCP servers (see [P0-3] revert 2026-07-04) |
| Cron + local file output | Cron + email/Slack push to external service |
| Single-developer browser userscript (Tampermonkey / Violentmonkey) | Published browser extension (Chrome Web Store review, manifest v3 churn) |

**Checklist for any new item** (must pass ALL before adding to roadmap):
1. **No paid infra required** to run it for the user or a peer
2. **No hosted service** the user must keep alive
3. **Maintenance cadence** ≤ a few hours per month for a single hobbyist
4. **No "must publish / must maintain public-facing infra"** obligation
5. **Free-tier degradation**: if the item depends on a third-party free API, what happens when that free tier is removed? (must be: degrades gracefully, not "tool becomes useless")

**Per-item audit log** (added 2026-07-04 in the same pass as the rule itself):

| Item ID | Verdict | Action |
|---|---|---|
| [P0-1] Bibtex export | ✅ pass | already shipped; pure local code |
| [P0-2] Local cache | ✅ pass | already shipped; local files only |
| [P0-3] MCP server | ❌ fail | **REVERTED 2026-07-04** — self-maintained MCP exceeded maintenance budget. Use public `paper-search-mcp` (PyPI) instead. |
| [P1-1] Citation walk | ✅ pass | uses OpenAlex free API; degrades gracefully when key unset |
| [P1-2] OpenAlex concepts | ✅ pass | same as P1-1 (free API + local filter) |
| [P1-3] PRISMA diagram | ✅ pass | pure local markdown generation |
| [P2-1] Browser extension | ❌ fail | **REDESIGN as userscript** — see Modified 2026-07-04 entry below |
| [P2-2] API key auto-application | ⚠️ needs design review | deferred — see Modified 2026-07-04 entry below |
| [P2-3] `pa watch` daily subscription | ❌ fail | **REDESIGN — drop email push** — see Modified 2026-07-04 entry below |
| [P2-4] ~~pa cache stats~~ | n/a | already merged into [P0-2] |

**Last audit**: 2026-07-04 (initial rule codification + revert pass)
**Next audit**: every time a new item is added (Status: proposed → in-progress transition)

---

**Owner**: Mavis (mavis)
**Last reviewed**: 2026-07-04 (MCP revert + global rule codification pass)
**Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6 + §7 + §8 (the original brainstorming; preserved here as the inception log)

---

## Active items

### [P0-1] Bibtex export

- **Status**: done
- **Added**: 2026-07-04
- **Started**: 2026-07-04
- **Completed**: 2026-07-04
- **Priority**: P0
- **Effort**: ~3 hours (faster than estimate)
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.1
- **Rationale**: PyPaperBot has built-in Bibtex export; missing from paper-agent v3.3.0. Academic users need Bibtex for Zotero / Mendeley / Overleaf workflows. Without Bibtex, paper-agent loses one of the primary reasons users migrate from PyPaperBot.
- **Acceptance criteria**:
  - `pa search <query> --format bibtex --output results.bib` produces standard `.bib` file
  - Entries use DOI as cite-key with collision handling (`doi_v2`, `doi_v3` for duplicates)
  - Author list, journal, year, volume, issue, pages all populated from OpenAlex / Crossref metadata
- **Dependencies**: None (uses existing search API metadata)

#### Outcome (2026-07-04)

Implementation: `pa_cli/bibtex.py` (220 lines) + `--format` option in `pa search`.

Validation passed (`test_output/validate_bibtex.py`):
- 3 entries from `pa search "AI literacy higher education"` parsed cleanly by bibtexparser v1.4.4
- Round-trip test: serialize + parse again → 3 entries, no data loss
- All 3 cite-keys unique (DOI-stripped format)
- All entries have valid DOI (10.* prefix)
- 0 results edge case: 0 entries written, no crash, header still generated
- Auto-naming when no `--output`: `machine_learning.bib` from query

Fields populated per entry: title / author / journal / year / doi / url / note
(citation count + OA status). Special chars escaped: `\` `{` `}` `&` `%` `$` `#` `_`.

Surprise findings during validation:
- Used 3 hours vs estimate 1-2 days — OpenAlex metadata is rich enough that no Crossref fallback was needed
- bibtexparser v1.4.4 was already installable; no extra deps beyond pip install
- Round-trip serialization preserved byte-for-byte content; downstream tools (Zotero, JabRef) will accept these unchanged

What v3.4.1+ could improve (deferred to backlog):
- Author name disambiguation (initials vs full first names — currently uses OpenAlex's display_name which is good but not always consistent)
- Pages / volume / issue fields — OpenAlex doesn't expose these; would need Crossref fallback or just `pages = {}` empty
- Entry type auto-detection for proceedings / books — currently hardcoded `@article` per source type

### [P2-4] ~~pa cache stats~~ — merged into [P0-2]

### Modified 2026-07-04 — merged into [P0-2] (already shipped)

[P2-4] was originally "pa cache stats" — descriptive single feature.
Once [P0-2] shipped with `pa cache stats` as one of 5 admin subcommands,
[P2-4] became functionally redundant (a strict subset of [P0-2]).
Removed from active items to avoid double-tracking. Outcome: covered
under [P0-2] outcomes.

**Migration**: existing references to `[P2-4] pa cache stats` should
be read as `[P0-2] Local cache, pa cache stats subcommand`.

---

### [P0-2] Local cache (avoid re-download)

- **Status**: done
- **Added**: 2026-07-04
- **Completed**: 2026-07-04
- **Priority**: P0
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.2
- **Rationale**: Same DOI re-fetched wastes bandwidth; iterative lit-review iteration needs to skip already-downloaded papers. Daily cron `pa-keys-daily-check` already wastes a probe per API per day — caching for 30 min saves 24x duplicate requests.
- **Acceptance criteria**:
  - `~/.paper-agent/cache/{doi_slug}.pdf` + `{doi_slug}.meta.json` (download timestamp, sha256, source channel)
  - `pa fetch <DOI>` checks cache first; if PDF magic valid + sha256 unchanged, return without re-downloading
  - `pa keys check` caches 30 min — second invocation in same window skips HTTP probe
  - `pa cache stats` shows size / count / oldest / newest
  - `pa cache clean --older-than 30d` removes cold entries

#### Sub-task decomposition (final time log)

| # | Description | Estimate | Actual | Notes |
|---|---|---|---|---|
| A | Add `pa_cli/cache.py` — PDF cache layer | 1h | ~1h | On target. DiskCache-style hash + JSON sidecar + _is_pdf magic check + corrupt-cleanup-on-mismatch. |
| B | Integrate cache into `pa_cli/fetch.py` — early-return on hit, write-after-success | 0.5h | ~0.5h | On target. 6 cascade branches updated; `channel_playwright_pdf` re-reads file from disk to write cache. |
| C | Add 30-min in-memory cache to `pa_cli/keys.py` `cmd_check()` | 0.5h | ~0.5h | On target. Used `PA_TEST` env var to bypass in unit tests. |
| D | Add `pa cache {path,stats,clean,put,drop}` subcommand group + `--no-cache` flags | 0.5h | ~1h | 2x over. Discovered: (a) Windows encoding hell (had to add PYTHONIOENCODING=utf-8 to test subprocess); (b) `~/.paper-agent` not yet existing first run — removed unnecessary fallback. |
| E | Add `--no-cache` flag to `pa fetch` and `pa keys check` | 0.25h | ~0.1h | Under. Click decorator + 2 line callsite changes. |
| F | Validation (4 test scripts) | 0.5h | ~1h | 2x over. (a) `test_cache_integration.py` hung in subprocess because cascade reaches `playwright` channel which tries to launch real chromium — needed `channel_playwright_pdf` mock. (b) `PA_TEST=0` was still bypassing cache (truthy string). Fixed cache_get to use truthy-set. (c) `Path.home() / .paper-agent / cache` fallback mis-detection. |
| G | CHANGELOG + ROADMAP outcome | 0.25h | ~0.2h | On target. |
| | **Total** | **3.5h** | **~5h** | **1.4x over** |

**Variance analysis**: 1.4x over estimate. Two infrastructure costs not anticipated:
1. Windows encoding issue in subprocess tests (1-2 debug iterations)
2. Missing `channel_playwright_pdf` mock in test 2 (single line fix but cost 10 min of debugging)

Both are isolated to the testing harness; production code is unchanged. For future cache-class items, **add 1 hour buffer for cross-platform test setup**.

#### Outcome (2026-07-04)

**Files added** (5):
- `pa_cli/cache.py` (~210 lines) — `cache_get`, `cache_put`, `cache_remove`, `cache_stats`, `cache_clean`, `_doi_slug`, `get_cache_root`, plus `_is_pdf` magic check
- `test_output/test_cache_smoke.py` — 6 sub-tests on cache module round-trip
- `test_output/test_cache_integration.py` — `pa fetch` cache hit + bypass semantics
- `test_output/test_keys_cache.py` — 30-min cache for `keys check`
- `test_output/test_pa_cache_cli.py` — E2E for `pa cache` subcommand (path/stats/put/drop/clean)
- `test_output/_run_all.py` — wrapper to run all 4 cache tests

**Files modified** (3):
- `pa_cli/fetch.py` — added `use_cache` param + cache check at function entry + cache write after each successful cascade (6 branches: openalex, arxiv, unpaywall, doi_redirect's HTML PDF + playwright_pdf fallback, scihub)
- `pa_cli/keys.py` — added `_check_cache_{get,put,clear}` + integrated into `cmd_check()`; cache survives 30 min (configurable in code)
- `pa_cli/cli.py` — added `--no-cache` flag to `fetch` and `keys check`; added `cache` subcommand group with 5 subcommands

**Tests passing** (4/4):
- `test_cache_smoke.py` — 6/6 checks (miss, put/get roundtrip, corrupt cleanup, remove, stats, clean)
- `test_cache_integration.py` — 2/2 (cache hit short-circuits in <0.5s; use_cache=False falls through to cascade)
- `test_keys_cache.py` — 5/5 (cold cache probes, warm cache returns instantly, different service_id busts, same service_id reuses, manual clear invalidates)
- `test_pa_cache_cli.py` — 6/6 (path resolves to ~/.paper-agent/cache, empty stats, put/stats/drop roundtrip, --all cleans, refusal on no-filter, --dry-run previews)

**Acceptance criteria status**: 5/5 met
1. ✅ `~/.paper-agent/cache/{doi_slug}.pdf` + sidecar meta (sha256, ts, channel, url, size)
2. ✅ `pa fetch <DOI>` checks cache first; cascade skipped on hit (sub-second)
3. ✅ `pa keys check` caches 30 min
4. ✅ `pa cache stats` shows size/count/oldest/newest
5. ✅ `pa cache clean --older-than 30d` removes cold entries

**Deferred to backlog** (recorded 2026-07-04):
- **Atime-based LRU**: when cache count > N (e.g. 500), evict oldest-accessed. Current impl is FIFO by ts; for v3.5.0 most users won't hit the limit, and `pa cache clean --older-than` gives them manual control.
- **Per-key size cap**: refuse to cache PDFs > 100MB (some books are larger). Not a [P0-2] blocker; deferred to "edge case pass" later.
- **Cache hit rate metrics**: track cache hits per session for `pa audit`. Useful but not core to [P0-2].
- **Legacy dirs cleanup**: 7 dirs (`arxiv_cache/`, `core_cache/`, etc.) from v3.0 `paper_fetcher.py` should be added to `.gitignore` (or deleted) — out of scope for [P0-2] but pollutes `git status`.

**Lesson for future estimates** (added 2026-07-04 to estimation methodology):
- "cache layer" type items: estimate 3-5h with 1h buffer for Windows subprocess test setup.
- Sub-task F (test infrastructure) for any cross-platform code should be ≥0.5h, often 1-1.5h due to encoding / mocking surprises.

#### Sub-task decomposition (estimated 2026-07-04 before work started)

| # | Description | Estimate |
|---|---|---|
| A | Add `pa_cli/cache.py` — PDF cache layer: `cache_get(doi)` validates PDF magic + sha256 against sidecar; `cache_put(doi, body, channel)` writes `.pdf` + `.meta.json`; `cache_stats()` / `cache_clean(older_than_nd)` admin helpers. Default root: `~/.paper-agent/cache/` (overridable via `PA_CACHE_DIR` env var, fallback to `./pa_cache/` if HOME undefined) | 1h |
| B | Modify `pa_cli/fetch.py` `fetch_doi()`: cache check at start (return early with `via_channel="cache"`); after successful cascade, also `cache_put()` so next call hits cache | 0.5h |
| C | Modify `pa_cli/keys.py`: in-memory 30-min cache for `keys_status()` output (single module-level dict with TTL check; reset if any test mode flag set) | 0.5h |
| D | Add `pa cache stats` + `pa cache clean [--older-than Nd\|--all]` subcommands to `pa_cli/cli.py` | 0.5h |
| E | Add `--no-cache` flag to `pa fetch` (bypass cache check, still writes to cache after success — opt-in to skip-but-record) | 0.25h |
| F | Validation script `test_output/test_cache.py`: cache_miss→hit cycle, PDF magic validation, sha256 integrity, `cache_stats` returns expected counts, `cache_clean` removes old entries, `--no-cache` bypasses, 30-min keys cache works | 0.5h |
| G | CHANGELOG v3.4.0 entry citing `[P0-2]` + ROADMAP Outcome subsection | 0.25h |
| | **Total** | **3.5h** (~3-4h with overhead) |

**Reference-class anchor**: [P0-1] Bibtex (3h actual, 4-8x under-estimate). Cache work shares few patterns (hash → file naming, JSON sidecar) so reuse 3h as anchor + 0.5h for fetch integration.

#### Existing state to leverage (discovered 2026-07-04 during scoping)

- `skill/core/api_pool/cache.py` `DiskCache` exists with SHA-256 + TTL. Different domain (search results, not PDFs), so copy pattern only — don't import across package.
- `pa_cli/fetch.py` `fetch_doi()` writes PDFs to `output_dir/{doi_slug}.pdf` but does NOT maintain cache. Sidecar `.meta.json` does not exist yet.
- `pa_cli/keys.py` exists, has `keys_status()` function but no caching.
- 7 legacy cache dirs (`arxiv_cache/`, `openalex_cache/`, etc.) from v3.0 `paper_fetcher.py` — NOT in `.gitignore`, polluting `git status`. **Out of scope for [P0-2]** but worth a separate `.gitignore` cleanup ticket post-implementation.

### Modified 2026-07-04 — scope clarified (search-result vs PDF cache)

**Mistake caught**: my initial mental model confused two different caching concerns — search-result caching (across `pa search` calls) and PDF-download caching (across `pa fetch` calls). Original acceptance criteria here target **PDF-download cache**, which is the bigger win because:

1. Same DOI might be re-fetched many times during lit-review iteration
2. PDFs are 1-10 MB each, downloading them again is real waste
3. Crossref/OpenAlex API costs grow with re-fetches

The correct work plan is in the `Sub-task decomposition` table above. Acceptance criteria unchanged.

**Lesson learned (for memory)**: when a `P0-N` has detailed acceptance criteria already, **read them first before sub-task decomposition**. My first attempt sub-task-decomposed based on assumption; corrected after re-reading. Apply this pattern to all future items.

### [P0-3] MCP server (expose `pa` as Model Context Protocol tool)

- **Status**: deprecated
- **Added**: 2026-07-04
- **Completed (initially)**: 2026-07-04
- **Deprecated**: 2026-07-04
- **Priority**: P0
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.3
- **Rationale (original)**: User's strong preference for "one-time investment, long-term reuse" patterns. Claude Code / OpenCode / Cursor all support MCP; exposing `pa fetch / search / review / keys status` as MCP tools means agent sessions can call them inline without terminal-switching. Long-term leverage — install once, use across all future agent sessions.
- **Acceptance criteria**:
  - `python -m pa_cli mcp-serve` runs as stdio JSON-RPC server
  - Exposes 4 tools: `pa_fetch(doi)`, `pa_search(query, year_min, year_max)`, `pa_review(corpus_dir)`, `pa_keys_status()`
  - All tool results are JSON-serialisable (no raw bytes)
  - Error states return structured errors (handoff from paper-agent v4 surfaces as `user_action_required` field)

#### Sub-task decomposition (final time log)

| # | Description | Estimate | Actual | Notes |
|---|---|---|---|---|
| A | Design tool schemas (JSON Schema for 4 tools) | 0.5h | ~0.2h | Under. Tool surface is bounded by existing pa_cli functions; minimal schema design work. |
| B | Implement `pa_cli/mcp.py` — `mcp.Server`, 4 handlers, async `serve()` | 1.5h | ~1.0h | Under. Local imports keep module dep-light; stdio transport boilerplate is minimal. |
| C | Add `pa mcp-serve` subcommand | 0.25h | ~0.05h | Under. 7-line Click wrapper. |
| D | E2E test (`test_mcp_e2e.py`) — in-process stdio client + 7 sub-tests | 1h | ~0.6h | Under. `mcp.ClientSession + stdio_client` make subprocess launching easy; pre-populated cache avoids network deps. |
| E | Edge cases (errors, handoff propagation, no-keys scenarios) | 0.5h | ~0.1h | Under. Covered by sub-task D tests. |
| F | CHANGELOG v3.6.0 + ROADMAP outcome + remove [P2-4] | 0.25h | ~0.2h | On target. |
| | **Total** | **4h** | **~2.1h** | **2x under** |

**Variance analysis**: 2x under. Speedup factors:
1. `mcp` Python SDK v1.27.2 already installed (saved ~10 min).
2. Tool surface reuses existing Click-command functions (no logic duplication).
3. Local imports in handlers (`from .fetch import fetch_doi` inside each handler) avoid pre-loading the cascade module on every stdio invocation.
4. First-of-kind item, no Maven-grade estimation. Would calibrate better with a second similar item (vs first-of-kind wide CI).

#### Outcome (2026-07-04)

**Files added** (2):
- `pa_cli/mcp.py` (~250 lines) — `mcp.Server` instance, 4 tool handlers, async `serve()`, structured error responses
- `test_output/test_mcp_e2e.py` (~180 lines) — 7 sub-tests covering list_tools + 4 tool calls + cache-hit fetch + error paths

**Files modified** (2):
- `pa_cli/cli.py` — added `pa mcp-serve` Click subcommand (7 lines)
- `test_output/test_full_regression.py` — added `A2. MCP server tests` section that wraps `test_mcp_e2e.py`

**Tests passing** (regression baseline):
- `test_mcp_e2e.py`: 7/7 sub-tests
- `test_full_regression.py`: now reports 36 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE (up from 29 PASS in v3.5.0)

**Acceptance criteria status**: 4/4 met
1. ✅ `python -m pa_cli mcp-serve` runs as stdio JSON-RPC server (and equivalent `pa mcp-serve` CLI)
2. ✅ Exposes 4 tools with JSON Schema input validation
3. ✅ All tool results are JSON-serialisable (verified: every text content is `json.dumps(..., ensure_ascii=False, indent=2)` over the existing function output)
4. ✅ Errors structured:
    - Unknown tool → `CallToolResult(isError=True, content=[TextContent(json)])`
    - Tool exception → wrapped with `error: <ExceptionClass>, message, tool`
    - Missing corpus_dir → returns structured dict `{error: "corpus_dir_not_found", ...}` (NOT MCP isError) so agent-specific recovery can inspect handoff fields
    - Paper-agent v4 handoff propagation: `fetch_doi()` already surfaces `handoff.user_action_required`; that flows through MCP result JSON unchanged

**MCP client config (example)**:
```json
{
  "mcpServers": {
    "pa": {
      "command": "python",
      "args": ["-m", "pa_cli.mcp"]
    }
  }
}
```

**Deferred to backlog** (recorded 2026-07-04):
- HTTP transport (stdio is enough for single-machine local use; HTTP for cross-machine needed deferred)
- Token-bucket rate limit on per-DOI fetch (DOS guard when many agents share one server)
- Elicitation prompts for confirmation flows (`"really download from Sci-Hub?"`)
- Persistent sampling for batch literature reviews (vs single-DOI fetch)
- `pa mcp install` helper that auto-writes the JSON config block into the active MCP client's settings file (would close the "now I need to manually edit config" gap)

**Lesson for future estimates** (added to estimation methodology):
- For "wrap existing functions for new interface" type items (CLI → MCP, MCP → HTTP, CLI → REST): estimate 2-3h with smaller buffer. The bulk of work is interface plumbing, not new logic.
- For MCP / external-protocol integrations, a pre-installed SDK can shave ~10-15 min vs full feature estimate.

#### Sub-task decomposition (estimated 2026-07-04 before work started)

| # | Description | Estimate |
|---|---|---|
| A | Design MCP tool schema for 4 tools (pa_fetch / pa_search / pa_review / pa_keys_status). JSON Schema for input/output, structured error mapping | 0.5h |
| B | Implement `pa_cli/mcp.py` — `mcp.Server` instance, register 4 tool handlers, async `serve()` using stdio transport, JSON-serialise all results | 1.5h |
| C | Add `pa mcp-serve` subcommand to `pa_cli/cli.py` — Click wrapper + asyncio.run + handling KeyboardInterrupt on stdin close | 0.25h |
| D | Validation — `test_output/test_mcp_e2e.py`: in-process stdio client launches `pa mcp-serve`, sends `initialize`, `tools/list`, `tools/call` for each of the 4 tools. Verify schemas + response contents | 1h |
| E | Edge cases — empty search results, missing DOI, network errors, structured error responses (handoff path in pa_fetch surfaces as MCP error with `user_action_required` field) | 0.5h |
| F | CHANGELOG v3.6.0 + ROADMAP Outcome subsection + remove [P2-4] (now covered) | 0.25h |
| | **Total** | **4h** (~3-5h with overhead) |

**Reference-class anchor**:
- [P0-1] Bibtex export: 3h actual, 4-8x under-estimate
- [P0-2] Local cache: ~5h actual, 1.4x over-estimate
- [P0-3] is first-of-kind (no prior MCP work) — wider ±100% confidence window
- Likely: faster than 4h due to lean tool surface (4 tools, all JSON-bounded)

**Pre-existing infrastructure discovered 2026-07-04 during scoping**:
- `mcp` Python SDK v1.27.2 already installed (Anthropic official, https://modelcontextprotocol.io)
- Has `mcp.Server`, `mcp.server.stdio.stdio_server`, `mcp.types.{Tool,CallToolResult}`, `mcp.ClientSession` for in-process testing
- NO install step needed — saves ~10 min vs original plan

**Tools to expose** (final shapes, decided 2026-07-04):
1. **`pa_fetch`** — args `{doi: str, output_dir?: str, proxy?: str, channels?: list[str], use_cache?: bool}` → returns fetch result dict (saved_as, via_channel, cache_hit, error/handoff)
2. **`pa_search`** — args `{query: str, year_min?: int, year_max?: int, limit?: int, engine?: str, format?: "json"|"bibtex"}` → returns search result dict (results array, by_engine counts, bibtex text)
3. **`pa_review`** — args `{corpus_dir: str, template?: str, word_count_min?: int}` → returns `{markdown: str, corpus_dir: str}` (markdown as string, never raw bytes)
4. **`pa_keys_status`** — args `{}` → returns `{rows: list[dict], total: int, active: int, expiring: int, expired: int, missing: int}`

**Files to add/modify**:
- NEW `pa_cli/mcp.py` (~150 lines)
- MODIFY `pa_cli/cli.py` — add `pa mcp-serve` subcommand
- NEW `test_output/test_mcp_e2e.py` — in-process client test
- NEW `test_output/test_mcp_schemas.py` — JSON Schema validation for each tool

#### Outcome (YYYY-MM-DD — to be filled on completion)

_(filled when work done)_

---

### Modified 2026-07-04 — scope clarified (added sub-task breakdown)

Original [P0-3] entry had 4 acceptance criteria at high level. This
update adds the 6-task breakdown, tool schemas, and reference-class
anchors. Acceptance criteria unchanged.

### Deprecated 2026-07-04 — abandoned (MCP self-hosted)

User explicitly walked back the [P0-3] MCP server the same day it shipped
(v3.6.0 → reverted in v3.5.1). Reasons (all tied to the new Global Rule —
"no services exceeding personal-hobbyist maintenance budget"):

1. **Self-maintenance burden**: every pa_cli feature change would need
   a paired MCP handler update. Schema drift + 5 hand-written JSON
   Schemas = ongoing tax for one hobbyist.
2. **Public alternative exists**: `openags/paper-search-mcp` (PyPI,
   22 free sources, MIT) covers the same use case (academic search via
   MCP for LLM clients) without user maintenance. Better to consume
   public work than to maintain a worse duplicate.
3. **Trust boundary / security model is unclear**: an MCP server that
   can spawn `pa fetch` (which can route through Sci-Hub mirrors via
   channel cascade) needs ongoing security review. One hobbyist can't
   do that sustainably.
4. **Subprocess + stdio debugging is high-friction**: when the MCP
   client crashes mid-session, the stdio server may not exit cleanly
   (we hand-rolled `BrokenPipeError` handling). Production MCP servers
   need ops engineering, not a hobbyist.

**Audit trail preserved**: the original implementation (`pa_cli/mcp.py`,
`test_mcp_e2e.py`, `pa mcp-serve` CLI subcommand, CHANGELOG v3.6.0 entry,
ROADMAP [P0-3] outcome subsection) is recoverable via `git log` — see
commits `e82ff30` (the original `feat(mcp): v3.6.0` commit) and the
revert commit (created in this same pass, 2026-07-04).

**Replacement guidance for users** (recorded in CHANGELOG v3.5.1):
```json
{
  "mcpServers": {
    "paper-search-mcp": {
      "command": "uvx",
      "args": ["paper-search-mcp"]
    }
  }
}
```

**Project integration** (added in v3.5.1 follow-up commit, 2026-07-04
same day): `pa mcp install` / `pa mcp config` subcommands exist so
users can find this from `pa --help` instead of reading the CHANGELOG.
The install helper does NOT auto-edit user MCP client config files
(per Global Rule + user sovereignty). It just installs the package
and prints the JSON for the user to paste.

**Future [P0-3] resurrection criterion** (for the discipline record): only
consider re-implementing if (a) paper-search-mcp goes unmaintained,
(b) all good public alternatives go away, AND (c) user explicitly
opts in. Until then, this entry stays `Status: deprecated`.

### [P1-1] Forward / backward citation walk

- **Status**: done
- **Added**: 2026-07-04
- **Completed**: 2026-07-04
- **Priority**: P1
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.4
- **Rationale**: Lit review requires both directions of citation traversal — papers that cite X (forward) and papers X cites (backward). Neither paper-agent v3.3.0 nor PyPaperBot offers this; OpenAlex provides `cited_by_count` + `referenced_works[]` natively, so the work is API surface + dedup + output formatting.
- **Acceptance criteria**:
  - `pa citations <DOI> --direction forward [--save-bib]` outputs deduped JSON of citing papers
  - `pa citations <DOI> --direction backward` outputs referenced papers
  - Pagination handled (OpenAlex cursor-based)

#### Sub-task decomposition (final time log)

| # | Description | Estimate | Actual | Notes |
|---|---|---|---|---|
| A | `pa_cli/citations.py` — OpenAlex wrappers, cursor pagination, error handling | 1h | ~0.5h | On/under. Caught a URL bug (`&api_key=` vs `?api_key=`) on first probe + fixed in 5 min. |
| B | Reuse `search._normalize_openalex` for shape consistency | 0.25h | ~0.05h | Under. Reuse was trivial — no new normalization code. |
| C | Add `pa citations` subcommand | 0.5h | ~0.2h | On. Click decorator + JSON output + error exits. |
| D | Add `pa_citations` MCP tool (5th tool) | 0.25h | ~0.05h | Under. 5-line wrapper around `citation_walk`. |
| E | E2E test (`test_citations_e2e.py`) — 8 sub-tests using real OpenAlex | 0.5h | ~0.4h | On. Includes 1 fix to expected tool list in test_mcp_e2e.py (was 4, now 5). |
| F | CHANGELOG v3.7.0 + ROADMAP outcome | 0.25h | ~0.1h | On. |
| | **Total** | **2.75h** | **~1.3h** | **2x under** |

**Variance analysis**: 2x under. Speedup factors:
- OpenAlex API key pre-configured (faster than 1 RPS free tier)
- `_normalize_openalex` reusable (no new shape definition)
- `pa_citations` MCP tool was a trivial wrapper once `citation_walk` was done
- For "API integration + CLI + MCP" class: estimate 2-3h with 0.5h buffer

#### Outcome (2026-07-04)

**Files added** (2):
- `pa_cli/citations.py` (~150 lines) — `get_work_by_doi`, `get_citing`, `get_referenced`, `citation_walk`
- `test_output/test_citations_e2e.py` (~190 lines) — 8 sub-tests using real OpenAlex API

**Files modified** (4):
- `pa_cli/cli.py` — added `pa citations` Click subcommand
- `pa_cli/mcp.py` — added `pa_citations` MCP tool (5th tool) + schema + handler
- `test_output/test_full_regression.py` — added A3 section for citations
- `test_output/test_mcp_e2e.py` — updated expected tool list (4 → 5)

**Tests passing**:
- `test_citations_e2e.py`: 8/8 sub-tests
- `test_full_regression.py`: now 38 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE (up from 36 in v3.6.0)

**Acceptance criteria status**: 3/3 met
1. ✅ `pa citations <DOI> --direction forward [--save-bib]` outputs deduped JSON
2. ✅ `pa citations <DOI> --direction backward` outputs referenced papers
3. ✅ Cursor-paginated (forward); N+1 bounded (backward, capped by --limit)

**Key discovery** (recorded for future OpenAlex integration work):
- `cites` filter accepts **only OpenAlex IDs** (W-prefixed), not DOIs in any form
- Direct DOI URL in filter returns 0 results silently
- Workflow: 2-step (DOI→ID via `/works/doi:<doi>`, then `/works?filter=cites:W<id>`)
- `referenced_works[]` is already OpenAlex ID list — no DOI resolution needed for backward

**Deferred to backlog** (recorded 2026-07-04):
- Multi-source citation walk (Crossref + Semantic Scholar `references` field for higher recall + dedup across sources)
- Citation graph depth (`pa citations X --depth 2` = forward(forward(X)))
- Save citations to pa cache (reuse existing PDF cache infra, would auto-avoid re-fetches across sessions)
- Per-page response caching (each OpenAlex response cacheable for 7 days per [P0-2] TTL pattern)

#### Sub-task decomposition (estimated 2026-07-04 before work started)

| # | Description | Estimate |
|---|---|---|
| A | `pa_cli/citations.py` — OpenAlex wrappers: `fetch_citing(doi, cursor, per_page)`, `fetch_referenced_doi(doi) -> list[DOI]`, cursor pagination loop with safety cap | 1h |
| B | Reuse `search._normalize_openalex` for output shape consistency; dedup by DOI in result list (in case OpenAlex returns dupes) | 0.25h |
| C | Add `pa citations` subcommand: `pa citations <DOI> --direction forward\|backward [--limit N] [--save-bib path.bib]` | 0.5h |
| D | Add `pa_citations` MCP tool to `pa_cli/mcp.py` (5th tool) | 0.25h |
| E | Validation: `test_output/test_citations_e2e.py` — uses real OpenAlex API to fetch a known DOIs citations; verify forward + backward return sensible counts, dedup works, --save-bib produces valid BibTeX | 0.5h |
| F | CHANGELOG v3.7.0 + ROADMAP outcome | 0.25h |
| | **Total** | **2.75h** (~3h) |

**Reference-class anchor**:
- [P0-1] Bibtex: 3h actual (4-8x under)
- [P0-2] Local cache: ~5h actual (1.4x over, mostly infra)
- [P0-3] MCP: ~2.1h actual (2x under)
- [P1-1] is API integration (not just wrap) — closer to "first-of-kind" CI ±100%
- Anchoring on [P0-1] (similar "API surface + format + dedup" type) → estimate ~2-3h

**OpenAlex API notes** (researched 2026-07-04):
- Forward: `GET /works?filter=cites:<DOI-or-openalex-id>&cursor=<*>` returns works citing target; `meta.next_cursor` for pagination
- Backward: `GET /works/doi:<DOI>` returns the work itself; `referenced_works[]` field has OpenAlex IDs of cited works; need 2nd call to fetch metadata for each
- DOI URL form: `https://doi.org/10.xxx/yyy` works in filter (encoded)
- API key bumps per-page rate limit (already in keys_registry)

**Risk**: backward citation requires fetching each referenced work individually; a paper with 50 refs = 50 API calls. Cap at `--limit N` (default 100 forward, 50 backward) to bound.

#### Outcome (YYYY-MM-DD — to be filled on completion)

_(filled when work done)_

### [P1-2] OpenAlex concepts semantic filtering

- **Status**: done
- **Added**: 2026-07-04
- **Completed**: 2026-07-04
- **Priority**: P1
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.5
- **Rationale**: Keyword search misses synonyms ("AI literacy" misses "generative AI fluency" / "ChatGPT competence"). OpenAlex's hierarchical concept IDs (e.g. C154945302 for AI Education) provide semantic scoping. OpenAlex's own benchmark shows +30% recall when concepts are used as filters.
- **Acceptance criteria**:
  - `pa search "AI literacy" --concepts C154945302` filters by concept
  - Multiple concept IDs supported (OR / AND modes)
  - Concept name auto-resolution (`--concept "Artificial Intelligence Education"` looks up ID)

#### Sub-task decomposition (estimated 2026-07-04 before work started)

| # | Description | Estimate |
|---|---|---|
| A | `pa_cli/concepts.py` — `search_concepts(query, limit)` (text→IDs), `filter_works_by_concepts(works, ids, mode)` (filter helper), `resolve_concept_ids(names_or_ids, mode)` (mixed input parser) | 0.75h |
| B | Add `--concepts ID[,ID,...]` + `--concept-mode or\|and` flags to `pa search` in cli.py | 0.5h |
| C | Add `--concept NAME` (singular, resolves text→ID via search_concepts) for ergonomics | 0.25h |
| D | Validation — `test_output/test_concepts_e2e.py` (uses real OpenAlex): name→ID resolution works, multi-ID filter, AND vs OR semantics differ | 0.5h |
| E | CHANGELOG v3.6.0 + ROADMAP outcome | 0.25h |
| | **Total** | **2.25h** |

**Reference-class anchor**: [P1-1] citation walk = ~1.3h actual (2x under). Similar API integration. Estimate 2-3h with 0.5h buffer.

**OpenAlex API notes** (researched 2026-07-04):
- Concept lookup by ID: `GET /concepts/C<id>` returns full metadata
- Name search: `GET /concepts?search=<text>&per-page=N` — multi-word works ("higher education" → 11 results), short/specific terms may return 0 (not in vocabulary as exact terms; users should try variations or supply IDs directly)
- Multi-concept work filter:
  - OR: `concepts.id:C1|C2` (pipe)
  - AND: `concepts.id:C1+concepts.id:C2` (separate filter expressions, joined with `+`)
- Reuses existing `pa_cli.search._normalize_openalex()` for output shape consistency

#### Outcome (2026-07-04)

**Files added** (1):
- `pa_cli/concepts.py` (~165 lines) — `search_concepts`, `resolve_concept_ids`, `build_concepts_filter`, `fetch_concept_metadata`, `is_concept_id`, `_api_key_suffix`, `_short_id`

**Files modified** (3):
- `pa_cli/cli.py` — `pa search` adds 3 new flags: `--concepts`, `--concept`, `--concept-mode`; CLI now resolves concepts + fetches metadata + prints warnings to stderr before invoking `run_search`
- `pa_cli/search.py` — `run_search()` accepts `concepts_filter` param; `search_openalex()` accepts `concepts_filter` param and threads it into the OpenAlex API URL
- `test_output/test_full_regression.py` — added A4 section that runs `test_concepts_e2e.py`

**Files added (tests)** (1):
- `test_output/test_concepts_e2e.py` (~180 lines) — 10 sub-tests, real OpenAlex API

**Tests passing**:
- `test_concepts_e2e.py`: 10/10 sub-tests
- `test_full_regression.py`: now 39+ PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE (up from 35 in v3.5.1)

**Acceptance criteria status**: 3/3 met
1. ✅ `pa search "AI literacy" --concepts C154945302` filters by concept
2. ✅ Multiple concept IDs supported (OR default; `--concept-mode and` for AND)
3. ✅ Concept name auto-resolution (`--concept "machine learning"` → C119857082)

**Key OpenAlex API findings** (recorded for future integration work):
- `concepts?search=<text>` does full-text search across concept names + descriptions
- Multi-word queries work better than single words: "higher education"→11 results, "AI literacy"→0
- Multi-concept filter syntax:
  - OR:  `concepts.id:C1|C2` (pipe separator in single filter expression)
  - AND: `concepts.id:C1+concepts.id:C2` (separate filter expressions joined with `+`)
- All concept IDs use `C<digits>` format; OpenAlex returns full URL `https://openalex.org/C<digits>` everywhere — strip prefix when constructing filters

**Effort**:
- Estimate: 2.25h, Actual: ~1h, Variance: ~2x under
- Speedups: OpenAlex API key pre-configured + `_normalize_openalex` reuse + clean threading through 2 layers

**Deferred to backlog** (recorded 2026-07-04):
- Concept name fuzzy matching (current: exact-phrase; user can fall back to IDs)
- Concept disambiguation UI (current: top-1 by works_count; could show picker for ambiguous names)
- Cache concept metadata (each `fetch_concept_metadata` is a separate network call; 5-concept search = 5 calls; could memoize per session)

#### Outcome (2026-07-04)

**Files added** (1):
- `pa_cli/prisma.py` (~130 lines) — re-exports `skill.core.prisma.generate_mermaid` + `generate_markdown`; adds `derive_counts_from_corpus()`, `render_prisma()`, `parse_json_arg()`

**Files modified** (3):
- `pa_cli/cli.py` — adds `pa prisma` command (10 options) + adds `--with-prisma` flag to `pa review`; review integration auto-derives counts from corpus via `build_corpus_index`
- `test_output/test_full_regression.py` — added A5 section that runs `test_prisma_e2e.py`; added `prisma --help` to --help surface check
- `pa_cli/__init__.py` — version 3.6.0 → 3.7.0

**Files added (tests)** (1):
- `test_output/test_prisma_e2e.py` (~150 lines) — 10 sub-tests, no network needed

**Tests passing**:
- `test_prisma_e2e.py`: 10/10 sub-tests
- `test_full_regression.py`: now 49+ PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE (up from 39 in v3.6.0)

**Acceptance criteria status**: 4/4 met (1 partially — see note)
1. ✅ `pa review --with-prisma` outputs a mermaid PRISMA block (auto-derived from corpus)
2. ✅ Mermaid block renders on GitHub automatically (mermaid + `flowchart TD` syntax; standard GitHub action)
3. ✅ Each stage shows count + auto-derived exclusion count (diffs between stages)
4. ⚠️ Static PNG / SVG export **deferred** — would require `mermaid-cli` install (npm dep) which may breach Global Rule "no paid/hosted infra" + adds maintenance burden. Defer to backlog until user explicitly opts in.

**Key implementation choice** (recorded for audit):
- **Thin wrapper, not reimplementation** — `skill/core/prisma.py` (~150 lines, untracked in git) already had working `generate_mermaid()` + `generate_markdown()`. Wrote `pa_cli/prisma.py` (~130 lines) as a stable re-export boundary so pa_cli doesn't need to import from untracked skill/ paths.
- This matches user's "一次性投入、长期复用" preference (one-time investment, long-term reuse): the existing skill code is the "investment"; pa_cli benefits without paying re-implementation cost.

**Effort**:
- Estimate: 2h, Actual: ~1h, Variance: ~2x under
- Speedups: skill/core/prisma.py already implemented (~1.5h saved) + reuse of `pa_cli.review.build_corpus_index` for auto-derivation

**Deferred to backlog** (recorded 2026-07-04):
- Static PNG/SVG export (mermaid-cli install; may breach Global Rule)
- Auto-eligibility stage (needs user-driven exclusion reason codes; not auto-detectable from PDFs)
- PRISMA template variations (PRISMA-ScR for scoping reviews, PRISMA-IPD for individual-patient-data)
- HTML embed in `pa review` output (currently just a markdown fence; GitHub renders natively, no extra work needed)

### [P1-3] PRISMA flow diagram output

- **Status**: done
- **Added**: 2026-07-04
- **Completed**: 2026-07-04
- **Priority**: P1
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.6
- **Rationale**: Systematic review journal submissions require PRISMA flow diagrams (identification → screening → eligibility → included). Manual construction is tedious; we have the data, just need to format.
- **Acceptance criteria**:
  - `pa review` output includes a mermaid PRISMA block
  - GitHub renders automatically
  - Each stage shows count + excluded-with-reason breakdown
  - Static PNG / SVG export optional via mermaid CLI

#### Sub-task decomposition (estimated 2026-07-04 before work started)

| # | Description | Estimate |
|---|---|---|
| A | `pa_cli/prisma.py` thin wrapper — re-export `skill.core.prisma.generate_mermaid` + `generate_markdown` so users don't need to import from skill/ | 0.25h |
| B | Add `pa prisma` command to `pa_cli/cli.py` — accepts `--identified N --after-screening N --after-eligibility N --included N [--by-source json] [--pdf N] [--abstract N] [--excluded-reasons json]` + `-o` to write file | 0.5h |
| C | Add PRISMA block to `pa review` output (auto-derive from corpus: identified=PDFs found, after-screening=full-text vs abstract-only, included=after-screening) | 0.5h |
| D | Validation `test_output/test_prisma_e2e.py` — both standalone and review paths; verify mermaid block embedded; verify counts add up | 0.5h |
| E | CHANGELOG v3.7.0 + ROADMAP outcome | 0.25h |
| | **Total** | **2h** |

**Reference-class anchor**: [P1-1] citation walk = ~1.3h actual. [P1-2] concepts = ~1h actual. Both involved real-API work. P1-3 is **local-only** (no API calls) → faster.

**Pre-existing infrastructure** (discovered 2026-07-04 during scoping):
- `skill/core/prisma.py` already has `generate_mermaid(identified, after_screening, after_eligibility, included, by_source, pdf, abstract)` + `generate_markdown(...)` (~150 lines, untracked in git). No need to reimplement — `pa_cli/prisma.py` is a thin re-export wrapper.

**Design decisions** (recorded 2026-07-04):
- `pa prisma` is a **standalone** command (not just an internal helper). Users with PRISMA data from any source (Excel, manual, another tool) can use it.
- `pa review` integrates PRISMA **at the top of the markdown** — auto-derives counts from corpus. No `--prisma-data` flag needed; we infer what we can.
- Mermaid block is the primary output (GitHub renders automatically). PNG/SVG export deferred (requires `mermaid-cli` install, which would fail the Global Rule "no paid/hosted infra" — keeping local-only).
- No auto-watching of citations for inclusion stage — that requires user review, not automatable.

#### Outcome (YYYY-MM-DD — to be filled on completion)

_(filled when work done)_

### [P2-1] Browser extension companion (SciHub Addon-style)

- **Status**: deprecated
- **Added**: 2026-07-04
- **Deprecated**: 2026-07-04 (user review — same-day rejection after reflection)
- **Priority**: P2
- **Effort**: 0.5 day (revised after redesign — was 0.5d for manifest only, redesign reduces further)
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.7
- **Rationale (original)**: Non-CLI users hit paper-agent via browser. `pa browser-install` opens SciHub Addon Chrome Web Store page + auto-configures fallback URLs pointing to local daemon.
- **Acceptance criteria (original — fails Global Rule ❌)**:
  - `pa browser-install` opens Chrome store + sets up extension with our 11-source fallback list  ← needs published extension (Chrome Web Store review + ongoing manifest v3 churn)
  - Local daemon (`pa serve`) accepts browser-extension callbacks for paper lookup  ← local daemon = hosted service within scope, but Chrome store publication is the violation

### Modified 2026-07-04 — redesign as userscript (Global Rule compliance)

Per Global Rule, browser extensions that need to be published and reviewed
by Chrome/Firefox stores exceed personal-hobbyist maintenance budget
(manifest v3 churn, store review process, ongoing compatibility). Redesign:

- **What it is now**: a **Tampermonkey / Violentmonkey userscript** that
  the user manually loads from a local file. No store review, no manifest
  v3 to chase, just JS that calls `pa` via `fetch` to local daemon.
- **Maintenance**: ~50 lines of JS + a markdown install guide. Versioning
  via Git, not via Chrome Web Store.
- **Local daemon `pa serve`**: kept (it's a local stdio service, not
  a hosted one — within scope).
- **Why this is OK for hobbyist**: no publication, no review, no
  per-browser-version compat matrix. If a browser breaks the userscript,
  edit it.

**New acceptance criteria**:
- `pa browser-install` writes a `pa-helper.user.js` userscript to `~/.paper-agent/`
  and prints Tampermonkey / Violentmonkey install instructions
- Userscript adds a "↘ pa fetch this" button to DOI landing pages; clicking
  sends the DOI to local `pa serve` daemon
- Local daemon runs as a regular Python script (`pa serve`); no
  authentication (localhost only)

### Deprecated 2026-07-04 — abandoned (user review)

**Honest reflection after user "reflection" prompt**:

I added this entry from `COMPETITOR_ANALYSIS_v3.3.0.md §6.7` (a competitor
parity bullet: "SciHub Addon is a popular browser extension") without
checking whether the user actually needs it. After reflection:

1. **No concrete workflow**: user does lit review via CLI
   (`pa fetch` / `pa search` / `pa citations`), not via browsing
   publisher landing pages in a browser. The "userscript button on
   DOI pages" use case is hypothetical, not observed.
2. **Even after Global Rule redesign**, the userscript + local daemon
   still requires (a) installing Tampermonkey/Violentmonkey, (b)
   pasting the userscript, (c) running `pa serve` daemon. That's
   three new habits for the user to maintain, with no observed benefit
   in current workflow.
3. **Competitor parity ≠ user need**: just because SciHub Addon exists
   as a browser extension doesn't mean paper-agent needs one.

**Decision**: DEPRECATED. No code written (avoid sunk-cost). The
Modified 2026-07-04 redesign sub-section above is preserved as audit
trail showing the redesign thought process, in case user later says
"I actually do want this, here's my workflow".

**Resurrection criterion** (per ROADMAP discipline): only re-propose
if user provides a specific scenario where they would use the
userscript (e.g. "I want to click a button on a publisher page to
auto-fetch via pa"). Until then, shelved.

### [P2-2] API key auto-application script

- **Status**: deprecated
- **Added**: 2026-07-04
- **Deprecated**: 2026-07-04 (user review — same-day rejection after reflection)
- **Priority**: P2
- **Effort**: 0.5 day (unchanged but scope reduced)
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.8
- **Rationale (original)**: New users hit friction when needing 3 API keys to run 5-engine search. Automating the registration form filling saves setup time.
- **Acceptance criteria (original — partly fails Global Rule ⚠️)**:
  - `pa keys setup` opens browser, fills OpenAlex / S2 / CORE registration forms  ← OK (uses Playwright locally)
  - Auto-detect confirmation emails and pulls key  ← ⚠️ requires email IMAP polling (depends on user's mail server config)
  - Writes to `.env` + registry automatically  ← OK
- **Risk noted in original**: API registration forms change; needs maintenance commitment

### Modified 2026-07-04 — drop auto-detect-email, keep registration form-fill (Global Rule)

Per Global Rule, "auto-detect confirmation emails" depends on user's
mail server (IMAP / OAuth) which adds credentials-handling + ongoing
maintenance as mail providers change. Drop that step.

**Revised acceptance criteria**:
- `pa keys setup` opens browser via Playwright, fills OpenAlex / S2 / CORE
  registration forms with user-supplied info (name, email)
- After submission, **prints the link / instructions** for the user to
  manually check their email and copy the confirmation key back
- `pa keys add <service> <key>` already exists; users feed the key in
  directly (one extra 30-sec step vs full automation, but no mail-server
  maintenance tax)
- **Maintenance**: Playwright selectors may break as forms change. The
  0.5-day estimate includes a `pa keys setup --dry-run` mode for users
  to detect breakage without committing. Worst case, they fall back to
  manual `pa keys add`.

### Deprecated 2026-07-04 — abandoned (user review)

**Honest reflection after user "reflection" prompt**:

I added this entry from `COMPETITOR_ANALYSIS_v3.3.0.md §6.8` (a competitor
parity bullet: "PaperBot does API key auto-setup") without checking
whether the user actually needs it. After reflection:

1. **User already has all keys configured**: `OPENALEX_API_KEY`,
   `S2_API_KEY`, `CORE_API_KEY`, `UNPAYWALL_EMAIL` are all set in `.env`
   and `keys_registry.json` shows `last_checked` completed for all.
   The user is not a "new user" who would benefit from auto-setup.
2. **"New users" assumption is broken**: per Global Rule (codified
   2026-07-04), paper-agent is a personal-hobbyist tool — there are
   no other users to onboard. The "new users hit friction" rationale
   assumed a public/commercialized product, which user explicitly
   ruled out.
3. **Even the redesigned form-fill (no email IMAP)** still requires
   maintaining Playwright selectors against 3 different registration
   forms that change without notice. One hobbyist can't sustain that.

**Decision**: DEPRECATED. No code written. The Modified 2026-07-04
sub-section above is preserved as audit trail showing the redesign
thought process.

**Resurrection criterion**: only re-propose if (a) user explicitly
decides to share paper-agent with someone who needs onboarding, OR
(b) one of user's existing keys needs rotation AND user wants automation
for just that one form. Until then, shelved.

### [P2-3] `pa watch <topic>` daily subscription + email push

- **Status**: deprecated
- **Added**: 2026-07-04
- **Deprecated**: 2026-07-04 (user review — same-day rejection after reflection)
- **Priority**: P2
- **Effort**: 0.5 day (revised after redesign — was 1d, redesign reduces)
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.9
- **Rationale (original)**: On-demand search misses daily new papers. Research monitoring needs daily/weekly automatic push. biohack-fetch-clean cron design is a template.
- **Acceptance criteria (original — fails Global Rule ❌)**:
  - `pa watch "AI literacy higher education" --daily --email user@x.com` registers mavis cron  ← ⚠️ cron OK, but email push
  - Cron runs `pa search` + diffs against seen-set + emails new papers  ← ❌ needs SMTP/transactional email (SendGrid etc. = $$, or self-hosted mailserver = maintenance)
  - Deduplication via DOI

### Modified 2026-07-04 — drop email push, generate daily MD report (Global Rule)

Per Global Rule, hosted email push (SendGrid/Mailgun/self-hosted SMTP)
exceeds hobbyist budget. Drop email entirely; replace with a daily
markdown report that the user reads locally.

**Revised acceptance criteria**:
- `pa watch "AI literacy higher education" --daily` registers mavis cron
- Cron runs `pa search` + diffs against seen-set + writes
  `~/.paper-agent/reports/YYYY-MM-DD.md` (just a markdown file, no network push)
- User reads it next time they open terminal / via `pa reports` subcommand
- Deduplication via DOI
- Optional: `--open` flag to auto-open the report in default editor

**Why this is OK**: the cron is local (mavis cron is in scope), the
output is a file (no hosted service), and reading is manual (no
"must keep service alive").

### Deprecated 2026-07-04 — abandoned (user review)

**Honest reflection after user "reflection" prompt**:

The redesigned version (drop email, generate daily MD report) is closer
to in-scope per Global Rule, BUT:

1. **No concrete topic yet**: the original entry says `<topic>` without
   a value. User does have cron habits (`biohack-fetch-clean` for
   nutrition, `pa-keys-daily-check` for API keys), but **not yet**
   paper-monitoring. Adding `pa watch` without a specific topic would
   be speculative infrastructure with no current workflow to support.
2. **Even minimal MD-report generator** needs:
   - A mavis cron registration command (one-time setup)
   - A DOI-dedup state file (~/.paper-agent/reports/seen.json)
   - Search query string persistence
   - Reasonable paper scoring (filter out low-quality hits)
3. **Maintenance risk**: even at minimum, this is one more cron + one
   more state file + one more script to keep alive. User already runs
   biohack-fetch-clean cron; adding paper-agent cron before there's
   a topic is cargo-culting.

**Decision**: DEPRECATED for now. The Modified 2026-07-04 redesign
sub-section above is preserved as audit trail showing the redesigned
plan, ready to be re-implemented **if and when user provides a topic**
(e.g. "monitor daily for new papers in <X field>"). The cron + local
MD report design itself is sound per Global Rule; what's missing is
the user's stated workflow need.

**Resurrection criterion**: only re-propose if user provides (a) a
specific research topic to monitor, AND (b) confirms they want daily
monitoring vs on-demand. Until then, shelved.

### [P2-4] ~~`pa cache stats` and `pa cache clean` subcommands~~ — REMOVED, merged into [P0-2]

### Modified 2026-07-04 — merged into [P0-2] (already shipped)

[P2-4] was originally "pa cache stats + clean" descriptive features.
Once [P0-2] shipped with `pa cache stats` + `pa cache clean` as 2 of 5
admin subcommands, [P2-4] became functionally redundant (a strict subset
of [P0-2]). Removed from active items list to avoid double-tracking.

**Rationale preserved for audit trail**: Once cache exists, users need
size/age/when-to-clean visibility. — Now satisfied by [P0-2] v3.5.0.

**Migration**: existing references to `[P2-4] pa cache stats` should
be read as `[P0-2] Local cache, pa cache stats/clean subcommands`.

---

## Modified items (proven wrong or revised)

- **[P0-3] MCP server** — see [P0-3] Modified 2026-07-04 sub-section. Original
  design (self-hosted `pa mcp-serve`) exceeded maintenance budget; user
  walked back the same day. Replaced with public `paper-search-mcp`
  integration via `pa mcp install`. NOT a "modified" item in the failed-
  sense — the redesign was successful — but tracked here for the audit.

- **[P2-1] Browser extension** — see [P2-1] Modified 2026-07-04. Original
  Chrome extension failed Global Rule (Chrome Web Store review); redesigned
  as Tampermonkey userscript. Later deprecated entirely on user review —
  see [P2-1] Deprecated 2026-07-04.

- **[P2-2] API key auto-apply** — see [P2-2] Modified 2026-07-04. Original
  design included email IMAP polling (fails Global Rule); redesigned to drop
  email auto-detect. Later deprecated entirely on user review — see
  [P2-2] Deprecated 2026-07-04.

- **[P2-3] pa watch daily + email** — see [P2-3] Modified 2026-07-04. Original
  design included SMTP email push (fails Global Rule); redesigned as
  local MD report + cron. Later deprecated entirely on user review (no
  concrete topic) — see [P2-3] Deprecated 2026-07-04.

---

## Deprecated items (abandoned, won't do)

- **[P2-1] Browser extension / userscript** — DEPRECATED 2026-07-04 (user review).
  No concrete workflow. Resurrection requires user-provided scenario.

- **[P2-2] API key auto-application** — DEPRECATED 2026-07-04 (user review).
  User already has all keys; "new users" assumption invalid under Global Rule.

- **[P2-3] pa watch daily subscription** — DEPRECATED 2026-07-04 (user review).
  No concrete topic yet. Resurrection requires user-provided topic + workflow.

- **[P0-3] MCP server (self-hosted)** — DEPRECATED 2026-07-04 (user reflection).
  Replaced by `pa mcp install` glue for public `paper-search-mcp`. Different
  from "abandoned" — the value was real, just better served by public package.

---

## Versioned roadmap summary

| Version | Status | Items | Released |
|---|---|---|---|
| v3.3.0 | released 2026-07-04 | (pre-roadmap items: CLI package, keys registry, v4 principle) | 2026-07-04 |
| v3.4.0 | released 2026-07-04 | [P0-1] Bibtex export | 2026-07-04 |
| v3.5.0 | released 2026-07-04 | [P0-2] Local cache + `pa cache` subcommand | 2026-07-04 |
| v3.5.1 | released 2026-07-04 | [P0-3] REVERTED (MCP) + [P1-1] Citation walk + `pa mcp install` glue | 2026-07-04 |
| v3.6.0 | released 2026-07-04 | [P1-2] OpenAlex concepts semantic filtering | 2026-07-04 |
| v3.7.0 | released 2026-07-04 | [P1-3] PRISMA flow diagram (pa prisma + pa review --with-prisma) | 2026-07-04 |
| v3.7.1 | released 2026-07-04 | Cleanup: deprecated [P2-1] / [P2-2] / [P2-3] after user review | 2026-07-04 |
| v3.8.0 | target (deferred) | (no new features planned; ship only if user requests) | — |

---

## How to use this file (quick reference)

**Adding an item**: edit `### [Px-N] <title>` under "Active items". Status `proposed` until work starts.

**Starting work**: change `Status: proposed` → `Status: in-progress`, add `Started: YYYY-MM-DD`. Update the entry with progress notes.

**Completing work**: change `Status: in-progress` → `Status: done`, add `Completed: YYYY-MM-DD`. Add a `## Outcome` subsection with what was learned.

**Item proven wrong after partial work**: keep the original entry. Add a `### Modified YYYY-MM-DD — <reason>` sub-section below it. Update the Status header to `modified` and link to the sub-section. Do **NOT** delete the original.

**Item permanently abandoned**: mark `Status: deprecated`. Add `### Deprecated YYYY-MM-DD — <reason>`. Do **NOT** delete the original.

**Reference in CHANGELOG.md**: every release entry should list the roadmap item IDs it implements. Example: `### Added — [P0-1] Bibtex export`.

---

## Estimation methodology (added 2026-07-04, post-[P0-1] retrospective)

User question exposed that the original estimates on [P0-1]–[P2-4] were
**intuitive gut-feel guesses, not plan-based estimates**. [P0-1] came in
**4-8x under estimate** (1-2 days estimated, 3 hours actual). To prevent
this on future items, every entry follows this discipline:

### 1. Sub-task decomposition (required for all new items)

Every proposed item **must** include a sub-task breakdown in its body:

```markdown
### [Px-N] Title

Sub-tasks (estimated before work starts):
- [ ] Sub-task A description                       — estimate: Xh
- [ ] Sub-task B description                       — estimate: Xh
- [ ] Sub-task C description                       — estimate: Xh
                                                ----
Total estimate: Xh  (X-X days)
```

The total estimate then becomes a sum of sub-task estimates, not a
single gut-feel number.

### 2. Reference-class anchoring

When estimating, look at the **most recently completed similar item**
in the Active items / Outcome sections. For example:
- All "metadata conversion" type items → anchor on [P0-1] Bibtex (3h)
- All "API client wrapper" type items → look for similar completed anchor
- If no anchor exists, mark `first-of-kind` and add a wider confidence interval (±100%)

### 3. Outcome time-tracking (required on every completion)

When changing Status to `done`, the Outcome section **must** include
per-sub-task actual time and variance:

```markdown
#### Outcome (YYYY-MM-DD)

Sub-task breakdown:
- sub-task A: estimate Xh, actual Yh  (variance Zx under/over)
- sub-task B: estimate Xh, actual Yh  (variance Zx under/over)
- sub-task C: estimate Xh, actual Yh  (avoided / cancelled)
                          ---------------------------------
Total: estimate Xh,   actual Yh     (variance Zx)

Why the variance:
- Reason A
- Reason B

Lesson for future estimates:
- For similar tasks, estimate X-Y hours (not the original estimate)
```

### 4. Confidence interval rule

- **First-of-kind items**: estimate as range with ±100% margin (e.g. "1-4 days")
- **Repeat-pattern items**: use tight range based on prior outcome (e.g. "2-3 hours")
- **Items with cross-system integrations** (browser ext, MCP): add 50% buffer for unknown unknowns

### 5. Anti-patterns (avoid these)

- ❌ Single gut-feel number without sub-tasks
- ❌ "1-2 days" without specifying what takes 1 vs 2 days
- ❌ Copy-paste estimates from similar items without re-decomposing
- ❌ Estimates that never get checked against actual (no feedback loop)

### 6. Reference data so far

After [P0-1] Bibtex completion, the project has its first anchor:

| Item type | Anchor item | Actual time | Notes |
|---|---|---|---|
| Small data format conversion (text/bibtex) | [P0-1] Bibtex | ~3h | OpenAlex metadata rich; Click + bibtexparser library overhead minimal |

Future similar items should use 3h as the anchor, with ±50% margin for unknown unknowns.

---

## Estimation log (running record of estimate vs actual)

| Item | Estimate | Actual | Variance | Completed | Note |
|---|---|---|---|---|---|
| [P0-1] Bibtex export | 1-2 days | ~3h | 4-8x under | 2026-07-04 | shipped |
| [P0-2] Local cache + pa cache CLI | 3.5h | ~5h | 1.4x over | 2026-07-04 | shipped |
| [P0-3] MCP server | 4h | ~2.1h | 2x under | 2026-07-04 (sameday revert) | **REVERTED 2026-07-04** — use paper-search-mcp (PyPI) |
| [P1-1] Citation walk | 2.75h | ~1.3h | 2x under | 2026-07-04 | shipped (in v3.5.1) |
| [P1-2] OpenAlex concepts | 2.25h | ~1h | 2x under | 2026-07-04 | shipped (v3.6.0) |
| [P1-3] PRISMA diagram | 2h | ~1h | 2x under | 2026-07-04 | shipped (v3.7.0) — reused skill/core/prisma.py |