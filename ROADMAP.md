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

**Owner**: Mavis (mavis)
**Last reviewed**: 2026-07-04 (initial scaffold)
**Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6 + §7 + §8 (the original brainstorming; preserved here as the inception log)

---

## Active items

### [P0-1] Bibtex export

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P0
- **Effort**: 1-2 days
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.1
- **Rationale**: PyPaperBot has built-in Bibtex export; missing from paper-agent v3.3.0. Academic users need Bibtex for Zotero / Mendeley / Overleaf workflows. Without Bibtex, paper-agent loses one of the primary reasons users migrate from PyPaperBot.
- **Acceptance criteria**:
  - `pa search <query> --format bibtex --output results.bib` produces standard `.bib` file
  - Entries use DOI as cite-key with collision handling (`doi_v2`, `doi_v3` for duplicates)
  - Author list, journal, year, volume, issue, pages all populated from OpenAlex / Crossref metadata
- **Dependencies**: None (uses existing search API metadata)

### [P0-2] Local cache (avoid re-download)

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P0
- **Effort**: 0.5 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.2
- **Rationale**: Same DOI re-fetched wastes bandwidth; iterative lit-review iteration needs to skip already-downloaded papers. Daily cron `pa-keys-daily-check` already wastes a probe per API per day — caching for 30 min saves 24x duplicate requests.
- **Acceptance criteria**:
  - `~/.paper-agent/cache/{doi_slug}.pdf` + `{doi_slug}.meta.json` (download timestamp, sha256, source channel)
  - `pa fetch <DOI>` checks cache first; if PDF magic valid + sha256 unchanged, return without re-downloading
  - `pa keys check` caches 30 min — second invocation in same window skips HTTP probe
  - `pa cache stats` shows size / count / oldest / newest
  - `pa cache clean --older-than 30d` removes cold entries

### [P0-3] MCP server (expose `pa` as Model Context Protocol tool)

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P0
- **Effort**: 0.5 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.3
- **Rationale**: User's strong preference for "one-time investment, long-term reuse" patterns. Claude Code / OpenCode / Cursor all support MCP; exposing `pa fetch / search / review / keys status` as MCP tools means agent sessions can call them inline without terminal-switching. Long-term leverage — install once, use across all future agent sessions.
- **Acceptance criteria**:
  - `python -m pa_cli mcp-serve` runs as stdio JSON-RPC server
  - Exposes 4 tools: `pa_fetch(doi)`, `pa_search(query, year_min, year_max)`, `pa_review(corpus_dir)`, `pa_keys_status()`
  - All tool results are JSON-serialisable (no raw bytes)
  - Error states return structured errors (handoff from paper-agent v4 surfaces as `user_action_required` field)

### [P1-1] Forward / backward citation walk

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P1
- **Effort**: 2 days
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.4
- **Rationale**: Lit review requires both directions of citation traversal — papers that cite X (forward) and papers X cites (backward). Neither paper-agent v3.3.0 nor PyPaperBot offers this; OpenAlex provides `cited_by_count` + `referenced_works[]` natively, so the work is API surface + dedup + output formatting.
- **Acceptance criteria**:
  - `pa citations <DOI> --direction forward [--save-bib]` outputs deduped JSON of citing papers
  - `pa citations <DOI> --direction backward` outputs referenced papers
  - Pagination handled (OpenAlex cursor-based)

### [P1-2] OpenAlex concepts semantic filtering

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P1
- **Effort**: 1 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.5
- **Rationale**: Keyword search misses synonyms ("AI literacy" misses "generative AI fluency" / "ChatGPT competence"). OpenAlex's hierarchical concept IDs (e.g. C154945302 for AI Education) provide semantic scoping. OpenAlex's own benchmark shows +30% recall when concepts are used as filters.
- **Acceptance criteria**:
  - `pa search "AI literacy" --concepts C154945302` filters by concept
  - Multiple concept IDs supported (OR / AND modes)
  - Concept name auto-resolution (`--concept "Artificial Intelligence Education"` looks up ID)

### [P1-3] PRISMA flow diagram output

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P1
- **Effort**: 1 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.6
- **Rationale**: Systematic review journal submissions require PRISMA flow diagrams (identification → screening → eligibility → included). Manual construction is tedious; we have the data, just need to format.
- **Acceptance criteria**:
  - `pa review` output includes a mermaid PRISMA block
  - GitHub renders automatically
  - Each stage shows count + excluded-with-reason breakdown
  - Static PNG / SVG export optional via mermaid CLI

### [P2-1] Browser extension companion (SciHub Addon-style)

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P2
- **Effort**: 0.5 day (manifest + docs only — don't write the extension itself)
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.7
- **Rationale**: Non-CLI users hit paper-agent via browser. `pa browser-install` opens SciHub Addon Chrome Web Store page + auto-configures fallback URLs pointing to local daemon.
- **Acceptance criteria**:
  - `pa browser-install` opens Chrome store + sets up extension with our 11-source fallback list
  - Local daemon (`pa serve`) accepts browser-extension callbacks for paper lookup

### [P2-2] API key auto-application script

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P2
- **Effort**: 0.5 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.8
- **Rationale**: New users hit friction when needing 3 API keys to run 5-engine search. Automating the registration form filling saves setup time.
- **Acceptance criteria**:
  - `pa keys setup` opens browser, fills OpenAlex / S2 / CORE registration forms
  - Auto-detects confirmation emails and pulls key
  - Writes to `.env` + registry automatically
- **Risk**: API registration forms change; needs maintenance commitment

### [P2-3] `pa watch <topic>` daily subscription + email push

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P2
- **Effort**: 1 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.9
- **Rationale**: On-demand search misses daily new papers. Research monitoring needs daily/weekly automatic push. biohack-fetch-clean cron design is a template.
- **Acceptance criteria**:
  - `pa watch "AI literacy higher education" --daily --email user@x.com` registers mavis cron
  - Cron runs `pa search` + diffs against seen-set + emails new papers
  - Deduplication via DOI

### [P2-4] `pa cache stats` and `pa cache clean` subcommands

- **Status**: proposed
- **Added**: 2026-07-04
- **Priority**: P2
- **Effort**: 0.5 day
- **Source**: `COMPETITOR_ANALYSIS_v3.3.0.md` §6.10
- **Rationale**: Once cache exists, users need to know size / age / when to clean.
- **Acceptance criteria**:
  - `pa cache stats` — size, count, oldest, newest
  - `pa cache clean --older-than N` removes cold entries
  - Aligns with existing `arxiv_cache/`, `core_cache/` directories

---

## Modified items (proven wrong or revised)

*(none yet — populated as items are worked on and learn from the outcome)*

---

## Deprecated items (abandoned, won't do)

*(none yet)*

---

## Versioned roadmap summary

| Version | Status | Items | Released |
|---|---|---|---|
| v3.3.0 | released 2026-07-04 | (pre-roadmap items: CLI package, keys registry, v4 principle) | 2026-07-04 |
| v3.4.0 | target 2026-07-15 | [P0-1] Bibtex, [P0-2] Local cache, [P0-3] MCP server | — |
| v3.5.0 | target 2026-07-31 | [P1-1] Citation walk, [P1-2] OpenAlex concepts, [P1-3] PRISMA | — |
| v4.0.0 | target 2026-08-30 | architecture milestone (MCP-first), [P2-*] backlog | — |

---

## How to use this file (quick reference)

**Adding an item**: edit `### [Px-N] <title>` under "Active items". Status `proposed` until work starts.

**Starting work**: change `Status: proposed` → `Status: in-progress`, add `Started: YYYY-MM-DD`. Update the entry with progress notes.

**Completing work**: change `Status: in-progress` → `Status: done`, add `Completed: YYYY-MM-DD`. Add a `## Outcome` subsection with what was learned.

**Item proven wrong after partial work**: keep the original entry. Add a `### Modified YYYY-MM-DD — <reason>` sub-section below it. Update the Status header to `modified` and link to the sub-section. Do **NOT** delete the original.

**Item permanently abandoned**: mark `Status: deprecated`. Add `### Deprecated YYYY-MM-DD — <reason>`. Do **NOT** delete the original.

**Reference in CHANGELOG.md**: every release entry should list the roadmap item IDs it implements. Example: `### Added — [P0-1] Bibtex export`.