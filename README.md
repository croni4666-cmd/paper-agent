# paper-agent

Academic paper search, fetch, and literature-review synthesis CLI.
8 default search engines (Crossref, OpenAlex, arXiv, S2, AMiner, CNKI, PubMed,
ClinicalTrials.gov) + 1 opt-in engine (CORE, local-only) + pa judge relevance
collection + pa build manuscript pipeline + Tier 2 research-topic project
management + Zotero local DB check + batch job manager (status/tail/resume).

**Note on CORE engine** (v3.9.11.1+): CORE code is isolated from the public
repo. After cloning, run once:
```bash
python tools/install_core.py   # generates pa_cli/_engines_local/core.py (gitignored)
```
Then `pa search --engine core "..."` works. Public clone without this step will
raise a clear "not installed" error if you try `--engine core`. See
`tools/install_core.py` docstring for the isolation rationale.

## Quick start (5 commands)

### 1. Search — 6 engines in one call
```bash
pa search "AI literacy K-12" --year-min 2020 --limit 30 -o results.json
```

### 2. Validate citation skeleton before building
```bash
pa cite-check refs.bib skeleton.md    # 3 buckets: missing / typo / orphan
```

### 3. Batch PDF download
```bash
pa fetch-batch refs.bib --out-dir ./pdfs/ --skip-existing --report failed.md
```

### 4. Mark relevance for screening
```bash
pa judge add --query "AI literacy" --paper-key smith2023 --relevance 2 --reason "Direct hit"
```

### 5. Build manuscript from refs.bib + filled-in skeleton
```bash
pa build refs.bib skeleton.md -o paper.pdf
```

## Core workflow

```
search results       pa cite-check        pa fetch-batch
  (JSON)        -->  (3 buckets)    -->   (PDFs)
       \              |                    |
        \             v                    v
       Bibtex (refs.bib) + Skeleton --> pa build (PDF/HTML/DOCX)
                       |
                       v
                  pa judge (mark relevance)
                       |
                       v
              pa export-screening (CSV for Notion/Excel/RevMan)
                       |
                       v
                pa project (per-topic corpus)
```

## Available commands

| Command | What | Effort |
|---|---|---|
| `pa search` | 8-engine search | — |
| `pa fetch` | Single PDF download | — |
| `pa fetch-batch` | Batch PDF from Bibtex | 1 call |
| `pa cite-check` | Validate `[@key]` in skeleton | Pre-build check |
| `pa judge` | Mark relevance (sqlite) | `add/bulk/list/stats/export/import` |
| `pa export-screening` | Bibtex + judge → CSV | For Notion/Excel |
| `pa build` | Bibtex + skeleton → PDF/HTML | Pandoc wrapper |
| `pa scaffold` | Bibtex → outline skeleton | Quick start |
| `pa dedup-strict` | Fuzzy + arxiv dedup | Stricter than default DOI-only |
| `pa search-saved` | Named search presets | Skip retyping flags |
| `pa project` | Per-topic corpus management | Phase 1 done; Phase 2 needs user input |
| `pa zotero check` | Read-only Zotero local DB check | "Do I already have this DOI?" |
| `pa zotero push` | Write to Zotero Web API library | pyzotero, idempotent via DOI dedup |
| `pa zotero search` | Query Zotero Web API library | "long-term care" style qmode |
| `pa zotero sync` | check + search + push (3-step) | Combined workflow |
| `pa zotero project create/list/status/note/add/search` | Zotero collection-as-research-project | Per-topic master note + items |
| `pa obsidian init/project/inbox` | Research sub-vault in your Obsidian | 0-Research/ + project + atomic notes + inbox |
| `pa search-and-import --query X --project Y` | End-to-end research workflow | search → fetch → bucket → push → project + note |
| `pa jobs start/list/status/tail/resume` | Batch fetch job manager | Inspired by InstSci |
| `pa mcp-fetch-serve` | MCP server for fetch tools | Codex/Claude Code integration |
| `pa mcp install` | Install public `paper-search-mcp` | One-shot setup |

## Performance (v3.9.10.2 honest, n=50 single 30/20 holdout)

| Ranker | NDCG@10 | Notes |
|---|---:|---|
| **Combined (0.5\*BM25 + 0.5\*bi-encoder)** | **0.8988** | **Default; no training, no overfit** |
| RidgeClassifier (α=1.0) | 0.8526 | Linear; interpretable coefficients |
| LogisticRegression (C=1.0) | 0.8409 | Linear; more stable than Ridge |
| BGE-reranker | 0.6952 | **DEPRECATED** (Wilcoxon p=0.0008, significantly worse) |
| LambdaMART 100 trees (LTR) | 0.7679 | **DEPRECATED at n<200** (overfit) |
| MoE router macro F1 | 0.5173 | Honest n=47 estimate; needs more data |

## Friendly-neighbor projects (complementary, not competing)

paper-agent focuses on **search + rerank + fetch (gray-area fallback)**. For
some workflows, a complementary tool is the friendlier path. We don't replace
these — we do different things well.

### `Rimagination/instsci` (288⭐, MIT)

> OA-first + browser-backed institutional access for academic papers.
> Agent-friendly MCP server + visible CloakBrowser for SSO flows.

**Why pair it with paper-agent**:
- If you have **university SSO** (CARSI / Shibboleth / EZproxy / WebVPN), InstSci
  is the **legitimate** way to download closed papers (Elsevier, Wiley, Springer,
  IEEE, Nature, etc.) — these are the publishers paper-agent's gray-area
  channels can't reliably reach
- InstSci has an **MCP server** (`instsci-mcp`) that drives the same
  fetch workflows paper-agent does, but routed through your institution
- Paper-agent is a **better search + rerank engine** (8 engines, LTR, MoE);
  InstSci is a **better institutional fetch** (10+ publisher workflows)

**Use it for**: closed papers you can legally access via your school's
subscription; batch institutional downloads with SSO 2FA.

**Side-by-side config** (MCP client with both):
```json
{
  "mcpServers": {
    "paper-search-mcp": {
      "command": "uvx",
      "args": ["paper-search-mcp"]
    },
    "paper-agent-fetch": {
      "command": "python",
      "args": ["-m", "pa_cli.mcp_fetch"]
    },
    "instsci-mcp": {
      "command": "uvx",
      "args": ["instsci-mcp"]
    }
  }
}
```

Now Codex / Claude Code can choose: search with `paper-search-mcp` (broad,
free), gray-area fetch with `paper-agent-fetch` (Sci-Hub fallback), or
institutional fetch with `instsci-mcp` (legitimate, requires SSO).

**Install InstSci**: `pipx install git+https://github.com/Rimagination/instsci.git`
or `uv tool install git+https://github.com/Rimagination/instsci.git`

**`deathcats4/instsci-workflow`** (52⭐, MIT, modified fork):
- Adds **Zotero handoff** (`instsci zotero sync --attachment-mode linked_file`)
- Adds **public/private evidence separation** (`public-audit`)
- Useful as inspiration for our own Zotero sync design — and as of
  **v3.9.15.0**, our [P2-17] `pa zotero push` and [P2-18] `pa zotero sync`
  ship as the paper-agent equivalent. See the Zotero integration section
  below.

## Zotero integration (v3.9.14.0 + v3.9.15.0)

paper-agent ships a **bidirectional Zotero workflow** without ever
needing Zotero's UI:

| Direction | Command | What |
|---|---|---|
| **Read local** (no API) | `pa zotero check --corpus refs.bib` | Which DOIs in my corpus are already in my Zotero library? |
| **Write API** (push) | `pa zotero push --corpus refs.bib` | Push new Bibtex entries to my Zotero library (idempotent, DOI dedup) |
| **Read API** (search) | `pa zotero search --query "long-term care"` | Search my Zotero library for papers matching a query |
| **Combined** | `pa zotero sync --corpus refs.bib` | check + search + push in 3 steps |

**Auth** (留痕 discipline — env vars only, NOT `.env`):
```bash
# Per-session (never persist to disk)
export ZOTERO_API_KEY="<your-key-from-zotero.org/settings/keys>"
export ZOTERO_LIBRARY_ID="<numeric-library-id>"
pa zotero push --corpus refs.bib
```

**Install the dep** (only if you need push/search/sync):
```bash
python -m pip install --user pyzotero  # >= 1.14
```

**Local check is read-only** ([P2-16] hard guarantee): SQLite `mode=ro`
URI makes writes impossible at SQLite level, verified by test.

**PDF upload deferred to v3.9.16** ([P2-17.1]): v3.9.15.0 ships
metadata-only push. PDF attachment via `item.attachment_simple()` is a
follow-up because it requires separate API call + Zotero file storage
quota (~300MB free).

See `THIRD_PARTY.md` for the full third-party notice including InstSci.

## Zotero project (v3.9.16.0)

A "project" in paper-agent is a **Zotero collection** (= folder). After
`pa zotero push` populates your library, organize by topic with
`pa zotero project create`:

```bash
# 1. Create a project (= Zotero collection, idempotent)
pa zotero project create --name "long-term care"

# 2. Push papers to your library (existing [P2-17] workflow)
pa zotero push --corpus refs.bib

# 3. Attach papers to the project
pa zotero project add --name "long-term care" --corpus refs.bib

# 4. Attach a master note (= research log + synthesis)
pa zotero project note --name "long-term care" --content-file note.md
pa zotero project note --name "long-term care" --append "2026-08-18: read 5 papers on X"

# 5. Browse
pa zotero project list
pa zotero project status --name "long-term care"
pa zotero project search --query "long-term care insurance"
```

**All subcommands**: `create` / `list` / `status` / `note` / `add` / `search`.

**Idempotent**: `create` returns the existing key if a collection with
the same name already exists. Safe to re-run in scripts.

**Master note**: attached to the collection as a regular Zotero note
(HTML, supports `<pre>` whitespace preservation). `--append` mode
appends a timestamped line to the latest master note (creates one
if missing).

## Obsidian research sub-vault (v3.9.16.0)

Manage research projects, directions, and unformed thoughts in your
existing Obsidian vault. We do NOT create a full vault template (you
already have one) — we add a `0-Research/` sub-folder.

**Setup** (one-time):
```bash
# Windows + GTD vault example
setx PAPER_AGENT_OBSIDIAN_VAULT "G:\Todo list\Todo List"

# Per-session:
# $env:PAPER_AGENT_OBSIDIAN_VAULT = "G:\Todo list\Todo List"

pa obsidian init   # creates 0-Research/ + Inbox/ + Projects/ + README.md
```

**Layout** (auto-created by `pa obsidian init`):
```
<vault>/0-Research/
├── Inbox/                  # uncategorized thoughts
│   └── YYYY-MM-DD_HHMMSS_<slug>.md
└── Projects/
    └── <project-slug>/
        ├── index.md        # project home: topic, direction, question
        ├── ideas.md        # raw / unformed thoughts
        ├── notes/          # atomic notes (one concept per file)
        └── synthesis.md    # cross-paper synthesis
```

**Workflow**:
```bash
# Project
pa obsidian project create --name "long-term care" \
    --research-question "How does public LTCI affect family caregivers?" \
    --direction "empirical microeconomics, China policy"

pa obsidian project thought --name "long-term care" --content "Wang 2020 has good ID but small sample"
pa obsidian project note --name "long-term care" --type reading \
    --content "Wang (2020) finds X. Key insight: pilot cities had 12% reduction in family caregiver burden."
pa obsidian project list
pa obsidian project status --name "long-term care"

# Inbox (uncategorized thoughts)
pa obsidian inbox add --content "cross-ref: paper X about Y"
pa obsidian inbox list
```

**5 note types**: `idea` (raw thought) / `reading` (per-paper
synthesis) / `synthesis` (cross-paper) / `question` (open question)
/ `evidence` (data point). Each gets YAML frontmatter (title, type,
project, created).

**Auto-create**: `thought` and `note` auto-create the project if it
doesn't exist (with minimal index.md), so you can capture an idea
before formalizing the project.

**No new dep**: pure stdlib (`pathlib`, `re`, `datetime`, `dataclass`,
`unicodedata`).

**Cross-link to Zotero**: by convention, use the same name on both
sides (Zotero collection + Obsidian project) and reference each in
the other's master note / `index.md`. NO automatic coupling (per
user intent) — keeps the two systems independent.

## End-to-end research workflow (v3.9.17.0)

`pa search-and-import` collapses the search → fetch → push → project +
note loop into a single command. This is the "every time I run
paper-agent to study a topic, set up the Zotero project automatically"
workflow.

**7 steps in one call**:

1. **Search** — 8 default engines via `pa search`
2. **Write Bibtex** — convert results to a temp `.bib`
3. **Fetch PDFs** — `pa fetch-batch` cascade (arxiv → unpaywall →
   scihub → annas → cnki → playwright → openalex)
4. **Bucket** — split into `downloaded` (PDF saved) vs `failed`
5. **Push to library** — push downloaded DOIs to your Zotero library
   (idempotent via `pyzotero.check_items()`)
6. **Create Zotero project** — auto-create Zotero collection if
   missing (idempotent by name)
7. **Add items + master note** — attach papers to the project + write
   a markdown fetch log (downloaded + failed tables) to the project's
   master note

**Example**:
```bash
pa search-and-import \
    --query "long-term care insurance" \
    --project "long-term care"

pa search-and-import \
    --query "数字普惠金融" \
    --project "digital-finance" \
    --limit 30 --year-min 2018

# Dry-run fetch only (skip push + project)
pa search-and-import \
    --query "..." --project "..." \
    --no-push --no-project
```

**Output** (human-readable summary):
```
[search-and-import] DONE
  query:           'long-term care insurance'
  project:         'long-term care'
  search results:  18
  downloaded:      12
  failed:          6
  Zotero push:     ok  (pushed=12 skipped=0 failed=0)
  Zotero project:  'long-term care'  (created, key=ABC123)
  items added:     12
  master note:     key=DEF456  (created)
```

Or `--json` for the full structured report (steps, errors, downloaded
list, failed list, summary stats).

**After a successful run**, a hint tells you the corresponding
`pa obsidian project` commands for the Obsidian side (cross-link
by same name):

```
[search-and-import] Hint: also create an Obsidian project page with:
  pa obsidian project create --name "long-term care" \
      --research-question "..." --direction "..."
  pa obsidian project thought --name "long-term care" \
      --content "(see Zotero project ABC123 for papers)"
```

**Why this is its own command**: chaining 4-5 commands
(`pa search` → `pa fetch-batch` → `pa zotero push` → `pa zotero
project create` → `pa zotero project add` → `pa zotero project note`)
loses track of which corpus matches which project. `pa
search-and-import` makes the match explicit by tying the project
name to the search query at the call site.

**Required env vars** (for steps 5-7):
- `$ZOTERO_API_KEY` — get at https://www.zotero.org/settings/keys
- `$ZOTERO_LIBRARY_ID` — numeric ID, same page

**Deferred to v3.9.17.1** ([P3-29.1]): `--with-obsidian` flag for
auto-sync to Obsidian (1-line `pa obsidian project create + thought`
after Zotero step). Currently you run those 2 commands manually
after a `pa search-and-import` for the full loop.

See `THIRD_PARTY.md` for the full third-party notice including InstSci.



## Known limitations

- **API key rate limits**: Some engines (S2, CORE) have higher rate limits with
  free API keys. See [`.env.example`](./.env.example) for which keys unlock
  which engines. No keys are required for basic use (anonymous rate limits
  work for low-volume academic work).
- **CORE engine** is opt-in (v3.9.11.1+) — run `python tools/install_core.py`
  after clone to enable. Anonymous requests work at low rate.
- **CNKI** requires user cookies / EZproxy / institution library access
- **Layer 7 fulltext features** (3 of 4) still at 0.0 — need PDF download first
- **Pa judge data** scales to ~5-50 projects; beyond that needs SQLite tuning
- **BGE alternative** (monoT5/ColBERT/LLM-fulltext) not yet evaluated

## Project layout (default)

```
~/.paper-agent/
  saved_searches.json          # pa search-saved presets
  judgements.sqlite            # pa judge data (global)
  projects/                    # pa project (per-topic)
    digital-finance/
      meta.json
      refs.bib
      judges.sqlite
    elder-care/
      ...
```

## Documentation

- [ROADMAP.md](ROADMAP.md) — what's done, what's next, full priority plan
- [CHANGELOG.md](CHANGELOG.md) — version-by-version release notes (v3.9.10.8 latest)
- [ARCHITECTURE.md](ARCHITECTURE.md) — system design + Cloudflare handling
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md) — current state for new sessions

## CLI: try `pa --help` and `pa <command> --help`

```bash
pa --help
pa search --help
pa fetch-batch --help
pa judge --help
pa project --help
```

## Files added in v3.9.10 (current stable)

For defense against "shipped but not committed" gaps, this is the
machine-checked list of files added/modified in the v3.9.10.x series:

### v3.9.10 (deprecate BGE/LTR)
- `pa_cli/cross_encoder.py` (DEPRECATED docstring)
- `pa_cli/ltr.py` (CONDITIONAL DEPRECATION docstring)
- `pa_cli/moe_router.py` (0.89 → 0.61 honest numbers)
- `bench/v01/_v4_rerank.py` (combined marked RECOMMENDED DEFAULT)
- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.md` (bug fix)
- `bench/v01/reports/v3_9_7_3_action_plan.md` (NEW)

### v3.9.10.1 (Phase 1.5 holdout)
- `test_output/_run_holdout_v1_5.py` (NEW)
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.{json,md}` (NEW)

### v3.9.10.2 (Simpler rerank)
- `pa_cli/cross_encoder.py` and `pa_cli/ltr.py` docstring updates
- `test_output/_run_simpler_rerank_v1_5.py` (NEW)
- `bench/v01/reports/v3_9_10_2_simpler_rerank.{json,md}` (NEW)

### v3.9.10.3 ([P2-7] pa cite-check)
- `pa_cli/cite_check.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (cite-check subcommand)
- `test_output/_test_cite_check.py` (NEW, 24 tests)
- `test_output/fixtures/demo_refs.bib` (NEW)
- `test_output/fixtures/demo_skeleton.md` (NEW)

### v3.9.10.4 ([P2-8] pa export-screening)
- `pa_cli/export_screening.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (export-screening subcommand)
- `test_output/_test_export_screening.py` (NEW, 26 tests)
- `test_output/_e2e_export_screening.py` (NEW)

### v3.9.10.5 ([P2-9] pa search-saved)
- `pa_cli/search_saved.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (search-saved subcommand group)
- `test_output/_test_search_saved.py` (NEW, 26 tests)

### v3.9.10.6 ([P2-10] pa dedup-strict)
- `pa_cli/dedup_strict.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (dedup-strict subcommand)
- `test_output/_test_dedup_strict.py` (NEW, 36 tests)

### v3.9.10.7 ([P2-11] pa fetch-batch)
- `pa_cli/fetch_batch.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (fetch-batch subcommand)
- `test_output/_test_fetch_batch.py` (NEW, 17 tests)

### v3.9.10.8 ([P2-12] pa project Phase 1)
- `pa_cli/project.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (project subcommand group)
- `test_output/_test_project.py` (NEW, 26 tests)

### v3.9.11.0 (Stable release marker)
- No code change; MINOR bump to mark natural code-level ceiling
- See `CHANGELOG.md [3.9.11.0]` for full stable-release notes

### v3.9.11.1 (CORE engine isolated)
- `pa_cli/search.py`: removed inline `search_core()` body; lazy-imports
  `pa_cli._engines_local.core.search_core` instead
- `pa_cli/_engines_local/` (NEW, gitignored): CORE engine file, generated
  by `tools/install_core.py` from embedded string constant
- `tools/install_core.py` (NEW, ~6.7KB): install / uninstall / verify
  script. Run once after clone to enable CORE.
- `.gitignore`: added `pa_cli/_engines_local/`
- Trade-off: CORE code IS in public repo (as string in install script);
  it's NOT in functional form. For stricter isolation, see
  `tools/install_core.py` docstring "Trade-off (honest)" section.

### v3.9.11.2 (Pre-push scanner fix + filter-branch backup cleanup)
- `test_output/_pre_github_secret_scan.py`: `scan_git_history()` now checks
  BOTH `+` and `-` lines in `git log -p` (was: only `+`, missed secrets in
  deleted content)
- `test_output/_history_deep_scan.py` (NEW): independent deep scanner using
  `--all`; catches what the pre-push scanner might still miss
- `test_output/_test_install_core.py` (NEW): fixture verifying install_core
  CORE string has no hardcoded keys / emails / tokens
- Local cleanup: deleted `refs/original/refs/heads/main`, gc-pruned dangling
  objects

### v3.9.11.3 (Dangling blob cleanup + direct-blob fixture)
- `test_output/_test_verify_blob_clean.py` (NEW): robust direct blob check.
  v1.1 fixed 3-column parsing bug (`git cat-file --batch-check` outputs
  `sha type size`, not 2 columns). v1.2 obfuscated the key constant
  (built at runtime from 4 substrings) to keep the literal full key off
  public GitHub.
- `test_output/_full_sweep_v3_9_11_3.py` (NEW): 10-check comprehensive
  pre-push verification (tracked files, git log, blobs, refs, fsck, etc.)
- `test_output/_final_cross_check.py` (NEW): 7 additional cross-checks
  (backup files, env-var files, hidden dirs, .env.example placeholders,
  version consistency, install e2e, pre-push scanner sanity)
- All 17 checks run as part of the v3.9.11.3 review+fix loop. After
  2 consecutive 0-issue rounds, the loop terminates.
- Memory entries added for: scanner + and - line bug, git cat-file
  3-column output, pre-commit hook bypass for legitimate fixtures.

## License

This software is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**
with an **additional restriction prohibiting use for AI/ML training** (the "No-AI-Training
restriction"). 

**In plain English**:
- ✅ You can use, modify, and run it for personal / academic / commercial purposes
- ✅ If you modify it, your modifications must also be open-sourced under AGPL-3.0
  (this is the standard AGPL copyleft clause)
- ✅ If you run it as a network service, you must publish your source code
  (this is the AGPL network clause; the key difference from regular GPL)
- ❌ **You may NOT use this software, its source code, or its outputs to train,
  fine-tune, validate, or improve any AI / ML / LLM model** — including LLMs,
  code-generation systems, embedding models, and any system whose weights or
  training data are derived from this software

Full text in [`LICENSE`](./LICENSE). The file contains:
- PART 1: Reference to AGPL-3.0 (canonical text at gnu.org/licenses/agpl-3.0.txt)
- PART 2: Additional restriction (No-AI-Training) — with specific carve-outs
  for evaluation, security review, and personal use
- PART 3: Full AGPL-3.0 text reproduced verbatim for convenience

**SPDX identifiers**:
- `AGPL-3.0-only`
- `LicenseRef-No-AI-Training-1.0`

**Why this combination**: AGPL-3.0 protects the source-sharing intent for any
network use; the No-AI-Training clause adds an explicit 2026-era protection
against LLM/ML training. Together they reflect the author's preference for
**copyleft + no commercial AI training** without prohibiting ordinary use.

If you have questions about whether your intended use is allowed, contact the
copyright holder.
