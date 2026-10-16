---
name: paper-agent
description: |
  Academic paper search, PDF fetch, and literature review synthesis.
  Use this skill when the user wants to: search for academic papers by
  topic or keyword across 6 public engines (Crossref / OpenAlex / arXiv / AMiner / PubMed / ClinicalTrials), fetch
  a paper PDF by DOI through the configured open-access cascade (including
  bioRxiv, CORE, OSF, ChemRxiv, JATS-to-PDF for PMC, Unpaywall, sci-hub),
  batch-fetch PDFs from a BibTeX file, walk citation graphs (OpenAlex),
  cluster corpus papers by topic, synthesize a literature review markdown
  from a corpus, manage API keys for academic databases, or check
  cache stats. Triggers include: "search for papers about X",
  "fetch the PDF for 10.1038/nature12373", "build a lit review from
  refs.bib", "show my API key status", "cluster my corpus by topic",
  "fetch all PDFs in this BibTeX", "how many papers are in cache".
  Do NOT use this skill for: general web search, code documentation
  lookup, non-academic research, or PDF reading (use a different
  skill for that).
metadata:
  version: 3.9.30
  pa_cli_version: 3.9.30
  author: paper-agent team (croni4666-cmd)
  license: AGPL-3.0-only WITH No-AI-Training-1.0
  homepage: https://github.com/croni4666-cmd/paper-agent
allowed-tools:
  - Bash
  - Read
  - Write
---

# paper-agent — Academic paper search, fetch, and lit-review Skill

A Codex Skill wrapper around the `paper-agent` Python CLI/MCP. Provides
wrapper scripts in `scripts/` that Codex can invoke
deterministically. The full `pa` CLI (30+ subcommands) is also
available via `python -m pa_cli.cli <command>` if needed.

## When to trigger

**Trigger this skill when the user's request matches any of**:

| User says | Use script |
| --- | --- |
| "search for papers about X" / "find me papers on Y" | `scripts/search.py` |
| "fetch the PDF for 10.xxxx/xxx" / "download paper DOI 10.xxxx" | `scripts/fetch.py` |
| "fetch all PDFs in this BibTeX" / "batch download refs.bib" | `scripts/fetch_batch.py` |
| "prepare a review from a corpus" | `scripts/review.py` (deterministic draft; inspect evidence and synthesize separately) |
| "cluster my corpus by topic" / "group papers by theme" | `scripts/review.py --topics` |
| "show my API key status" / "check OpenAlex / CORE / Unpaywall settings" | `scripts/keys.py` |
| "how many papers in cache" / "show cache stats" / "clean old PDFs" | `scripts/cache.py` |
| "walk citations of 10.xxxx" / "what papers cite this one" | `scripts/citations.py` |
| "what version of paper-agent" / "is playwright installed" | `scripts/version.py` |

**Do NOT trigger for**:
- General web search (use Codex's built-in `web_search`)
- Code documentation lookup
- Reading a PDF (use a PDF reader skill)
- Non-academic queries (news, weather, etc.)

## Optional Europe PMC source

Use `--engine europepmc` for public medical searches. Structured research accepts
`--engine europepmc --expansion none --strategy single`. Defaults are unchanged.
See `references/europepmc.md` for source syntax, OA limits and provenance.
Review output is an inventory; scientific support/refutation and conflict appraisal remain separate.

## Quick start

### Complex biomedical propositions and official sources

For concept-block query expansion, local MeSH lookup, observable stopping
budgets, or domain-routed institutional pages, read
[`references/concept-search.md`](references/concept-search.md).
Use `scripts/research_search.py` with an explicit question profile; it preserves
the original question and separates paper candidates from official page text.
Use `scripts/terminology.py` to download/import/lookup official MeSH data.
This opt-in workflow defaults to a single original-term query (32 results);
MeSH expansion and multi-query strategies are explicit sensitivity options.
The same reference documents optional review-reference discovery, exact-query
caching and an experimental adaptive slot budget. Reference discovery has an
additional budget; cache hits are historical responses, not new evidence.
It does not replace source appraisal or automatically
validate scientific propositions. Existing `search.py` behavior is unchanged.

```bash
# Search
python scripts/search.py "数字普惠金融 家庭消费" --engine all --limit 20

# Fetch single PDF
python scripts/fetch.py 10.1038/nature12373 --prefer pmc-pdf

# Batch fetch from BibTeX
python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/

# Review draft from downloaded papers (not a BibTeX file)
python scripts/review.py ./pdfs/ --output lit_review.md

# Citations (forward + backward)
python scripts/citations.py 10.1038/nature12373 --direction both --limit 50
```

## Installation

The wrapper scripts depend on the **paper-agent Python package** (`pa_cli`). For an installed skill outside its source checkout, put absolute `root` and `python` paths in `runtime.local.json` beside this file, or set `PAPER_AGENT_ROOT` and `PAPER_AGENT_PYTHON` (environment takes precedence). Use a persistent checkout and virtual environment, not a temporary testing directory. Keep the local configuration out of Git and distributable packages.

Every wrapper uses that selected interpreter for backend commands, even when the host Python lacks dependencies. Without an explicit interpreter, discovery checks `.venv-codex` and `.venv` under the backend root before falling back to the host.

### Recommended: run bootstrap once

```bash
python <skill-dir>/scripts/bootstrap.py
```

This will:
1. Locate the requested or configured backend directory.
2. Check `pa_cli.cli --help` in the selected runtime.
3. If needed, install the backend in that same runtime and recheck.

Use `--check` for a read-only check; it never installs dependencies. A successful check confirms the CLI starts, not that all optional features or external services work.

If the repo is not in a common location, pass `--repo <path>`:
```bash
python <skill-dir>/scripts/bootstrap.py --repo "G:\path with spaces\paper-agent"
```

### Manual install

```bash
# 1. Clone paper-agent repo (if not already)
git clone https://github.com/croni4666-cmd/paper-agent.git

# 2. Install in editable mode
cd paper-agent
pip install -e .

# 3. (Optional) Set PAPER_AGENT_ROOT for explicit path
export PAPER_AGENT_ROOT="/path/to/paper-agent"  # Linux/macOS
$env:PAPER_AGENT_ROOT = "G:\path\to\paper-agent"  # Windows PowerShell
```

### How `find_pa_root()` discovers pa_cli

The wrappers share a `_pa_root.py` helper that tries these locations in order:

1. `$PAPER_AGENT_ROOT` env var, otherwise the `root` in `runtime.local.json`
2. `import pa_cli` (works if pip-installed system-wide)
3. Common paths under `~/minimax - workspace/Paper agent`, `~/code/paper-agent`, `cwd/`, etc.
4. `pa` CLI on PATH (traces back to site-packages)

If all 4 fail, the wrapper returns a clear error:
```json
{
  "error": "pa_cli_not_found",
  "message": "paper-agent (pa_cli) is not installed in this Python environment.",
  "hint": "Run scripts/bootstrap.py or pip install -e <repo>"
}
```

## Scripts (detailed)

### `scripts/bootstrap.py` — Auto-install pa_cli (v3.9.23.1+)

```bash
python scripts/bootstrap.py                  # auto-detect + install
python scripts/bootstrap.py --repo <path>    # explicit path
python scripts/bootstrap.py --check          # verify only
```

See the **Installation** section above for full details.



### `scripts/search.py` — Search current public engines

```bash
python scripts/search.py QUERY [options]
  --engine ENGINE                  default=all; comma-separated lists supported
  --limit N                          default=20
  --year-min YYYY                    default=None
  --year-max YYYY                    default=None
  --output FORMAT [json|markdown]    default=json
```

Returns a JSON envelope whose `results` field contains paper records with `title / authors / year / venue / doi /
abstract / tldr / open_access / cites / engine`. `all` runs the 6 public
engines in parallel and dedupes by DOI. AMiner is best for Chinese
papers; PubMed for biomedical; arXiv for preprints; ClinicalTrials
returns trial registry records.

### `scripts/fetch.py` — Fetch single paper PDF

```bash
python scripts/fetch.py DOI [options]
  --prefer [arxiv|annas|scihub|pmc|pmc-pdf|unpaywall|biorxiv|core|osf|chemrxiv|auto]  default=auto
  --output-dir DIR                  default=.
  --no-cache                        skip cache lookup
  --max-total-sec N                 total worker budget (default 300s)
```

Tries the configured open-access cascade in order. Returns JSON with `saved_as /
via_channel / via_url / size_bytes / elapsed_sec`. For PMC papers
(PubMed Central), use `--prefer pmc-pdf` to force JATS XML → real PDF
render via headless Chromium (~20-25s).


`--no-cache` skips reads; successful downloads still attempt cache writes. Optional writes have a separate 3-second maximum, leaving time to return the PDF. Inspect `cache_status` and `retrieval_trace` when retrieval fails or the cache is unavailable. The trace retains the latest 64 events (`trace_truncated` marks omitted earlier events). Trace entries record reached stages and status, not URLs or exception text; a `started` entry without completion means that stage was still running or the worker ended. Unvisited sources have not been tested.

For an installed skill outside the backend repository, set `PAPER_AGENT_ROOT` and `PAPER_AGENT_PYTHON`, or create `runtime.local.json` beside this SKILL.md with absolute `root` and `python` paths. Environment settings take precedence. Keep that machine-local file out of Git and deployment packages. `runtime.version`, `runtime.entry` and `runtime.trace_schema` identify the backend protocol in fetch results.

### `scripts/fetch_batch.py` — Batch fetch from BibTeX

```bash
python scripts/fetch_batch.py BIBTEX_FILE [options]
  --output-dir DIR                  default=./pdfs
  --max-total-sec N                 default=3600 (1 hour)
  --skip-existing                   skip already-downloaded PDFs
  --report FILE                     write JSON summary
```

Reads a BibTeX file, extracts DOIs, fetches each PDF in sequence. Writes
PDFs to `<output-dir>/<sanitized-cite-key>.pdf`. Generates a JSON
report with success/failure counts and per-paper details.

### `scripts/review.py` — Review draft and topic clusters

```bash
python scripts/review.py CORPUS [options]
  --output FILE                     default=lit_review.md (topics.json with --topics)
  --word-count-min N                default=1000; extraction classification only
  --topics                          cluster corpus by topic instead
```

`CORPUS` is a directory of PDF, Markdown or text papers, not a BibTeX file.
The backend generates a deterministic Markdown draft; it does not call an LLM
or establish factual correctness. Inspect original evidence and write the
narrative synthesis separately. The extraction word-count threshold does not
prove full-text completeness or study quality. Download BibTeX entries with
`fetch_batch.py` first. `--topic`, `--max-papers`, `--model` and
`--top-k-clusters` were previously advertised but are unsupported and now
return explicit errors. Clustering writes JSON and needs `scikit-learn` for
its lightweight fallback; cluster count is selected by the backend.

Input and output paths resolve relative to the caller's directory, not the backend checkout.

### `scripts/citations.py` — Walk citation graph

```bash
python scripts/citations.py DOI [options]
  --direction [forward|backward|both]  default=both
  --limit N                          default=50
  --output FILE                     default=None (stdout)
```

Uses the backend OpenAlex library (there is no `pa citations` CLI command).
Forward = papers that cite this paper; backward = this paper's references.
`both` retains separate directional results under `walks`; the combined
`results` list can contain duplicates across directions. Inspect backend
warnings and truncation flags; a returned subset is not a complete citation graph.

### `scripts/keys.py` — API key management

```bash
python scripts/keys.py [command]
  list                              show all keys + status
  check SERVICE_ID                  live-probe a single service
  audit                             show expiry warnings
```

Uses the backend key registry. `audit` returns its text report in a JSON
`audit_text` field. `check` is a live probe that can update check timestamps
and alert files; it is not a read-only status check. Use `list` for status.

### `scripts/cache.py` — Cache management

```bash
python scripts/cache.py [command]
  stats                             show cache size + oldest entry
  clean --older-than-days N         delete old PDFs
  clear --confirm                   remove all cached papers (explicitly destructive)
```

Cache lives at `~/.paper-agent/cache/`. Stores PDFs + metadata.

### `scripts/version.py` — Show version + dep status

```bash
python scripts/version.py
```

Reports the skill version separately from the configured backend version and
interpreter. It tests Chromium by actually generating an in-memory PDF.
`jats_to_pdf_available: false` may mean a missing browser or host execution
restrictions; inspect `browser_error`. Backend readiness is reported separately.

## Common workflows

### 1. Search → fetch → Zotero push

```bash
# 1. Search
python scripts/search.py "long-term care insurance" --engine all --limit 30 > results.json

# 2. Extract DOIs and fetch
jq -r '.results[].doi // empty' results.json | head -10 | xargs -I {} python scripts/fetch.py {}

# 3. Push to Zotero (uses pa zotero-push directly)
python -m pa_cli.cli zotero push --corpus results.json
```

### 2. BibTeX → batch PDF → lit review

```bash
# 1. Batch fetch
python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/ --report fetch_report.json

# 2. Synthesize lit review
python scripts/review.py ./pdfs/ --output lit_review.md
```

### 3. PRISMA flow diagram (for systematic reviews)

```bash
# After you've identified / screened / included papers:
python -m pa_cli.cli prisma \
  --identified n_total \
  --duplicates-removed n_dups \
  --screened n_screened \
  --excluded n_excluded \
  --full-text-assessed n_fulltext \
  --excluded-fulltext n_fulltext_excluded \
  --included n_included \
  --output prisma.png
```

## Error handling

- **Network errors**: `fetch.py` and `search.py` retry 3x with
  exponential backoff. Cloudflare challenges (5min fail) trigger
  handoff message to user.
- **Quota exceeded** (CORE, AMiner): The script returns a clear
  error code and the channel's status. User should re-try or
  switch to a non-quota channel.
- **Cache hit**: `fetch.py` returns immediately with `via_channel:
  cache:<name>` and `cache_hit: true`.
- **PMC JATS-as-PDF orphan fix** (v3.9.22.1): if JATS-to-PDF
  fails, no orphan `.pdf` is created. The `.xml` is the only
  output. `size_bytes` is now correctly populated in JSON.

## Environment

- **Python**: 3.10+ required
- **Required deps**: requests, urllib3 (already in paper-agent)
- **Optional deps**: playwright (for JATS→PDF render), bibtexparser
  (for fetch-batch), PyMuPDF (for review synthesis)
- **API keys** (optional but recommended): see `references/engines.md`

## When to use the underlying `pa` CLI directly

The 8 wrapper scripts cover ~90% of use cases. For the other ~10%
(advanced: Zotero bidirectional sync, sample pool management, MCP
server install, etc.), invoke the full CLI:

```bash
python -m pa_cli.cli <command> --help
python -m pa_cli.cli zotero search --query "long-term care"
python -m pa_cli.cli sample-pool add --qid q001 --relevance 1
```

## Notes for Codex

- Wrappers normally return JSON; search's Markdown mode is plain text,
  and backend/parser errors may also be text. Check exit status and both streams.
- All scripts support `--help`.
- Output-producing scripts can overwrite their requested output files; preserve existing research artifacts or choose a new output path.
- Fetch/review/citation output writes files; key probes can update state and
  cache cleaning deletes cache entries. Keep mutations within the user's request.
Fetch statistics: run scripts/fetch_stats.py when asked which PDF sources work best locally. It reads local outcomes only and does not fetch papers.
