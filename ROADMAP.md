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

| Item | Estimate | Actual | Variance | Completed |
|---|---|---|---|---|
| [P0-1] Bibtex export | 1-2 days | ~3h | 4-8x under | 2026-07-04 |