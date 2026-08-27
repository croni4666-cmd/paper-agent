---
name: paper-agent
description: |
  Academic paper search, PDF fetch, and literature review synthesis.
  Use this skill when the user wants to: search for academic papers by
  topic or keyword across 8 engines (Crossref / OpenAlex / Semantic
  Scholar / arXiv / AMiner / CNKI / PubMed / ClinicalTrials), fetch
  a paper PDF by DOI using 14 fallback channels (incl. S2 openAccessPdf,
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
  version: 3.9.25.1
  pa_cli_version: 3.9.25.0
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
8 pre-vetted wrapper scripts in `scripts/` that Codex can invoke
deterministically. The full `pa` CLI (30+ subcommands) is also
available via `python -m pa_cli.cli <command>` if needed.

## When to trigger

**Trigger this skill when the user's request matches any of**:

| User says | Use script |
| --- | --- |
| "search for papers about X" / "find me papers on Y" | `scripts/search.py` |
| "fetch the PDF for 10.xxxx/xxx" / "download paper DOI 10.xxxx" | `scripts/fetch.py` |
| "fetch all PDFs in this BibTeX" / "batch download refs.bib" | `scripts/fetch_batch.py` |
| "build a lit review from refs.bib" / "synthesize a literature review" | `scripts/review.py` |
| "cluster my corpus by topic" / "group papers by theme" | `scripts/review.py --topics` |
| "show my API key status" / "check AMiner / OpenAlex / S2 keys" | `scripts/keys.py` |
| "how many papers in cache" / "show cache stats" / "clean old PDFs" | `scripts/cache.py` |
| "walk citations of 10.xxxx" / "what papers cite this one" | `scripts/citations.py` |
| "what version of paper-agent" / "is playwright installed" | `scripts/version.py` |

**Do NOT trigger for**:
- General web search (use Codex's built-in `web_search`)
- Code documentation lookup
- Reading a PDF (use a PDF reader skill)
- Non-academic queries (news, weather, etc.)

## Quick start

```bash
# Search
python scripts/search.py "数字普惠金融 家庭消费" --engine all --limit 20

# Fetch single PDF
python scripts/fetch.py 10.1038/nature12373 --prefer pmc-pdf

# Batch fetch from BibTeX
python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/

# Lit review synthesis
python scripts/review.py refs.bib --output lit_review.md --topic "数字普惠金融"

# Citations (forward + backward)
python scripts/citations.py 10.1038/nature12373 --direction both --limit 50
```

## Installation

The skill's 8 wrapper scripts depend on the **paper-agent Python package** (pa_cli) — the actual CLI that does the work. The skill cannot function without pa_cli installed. **v3.9.23.1 added auto-install** to handle the most common setup error ("No module named 'pa_cli'").

### Recommended: run bootstrap once

```bash
python <skill-dir>/scripts/bootstrap.py
```

This will:
1. Check if pa_cli is importable (exit 0 → done)
2. If not, auto-detect the paper-agent repo at common locations
3. Run `pip install -e <repo>` to install in editable mode
4. Verify the install succeeded

If the repo is not in a common location, pass `--repo <path>`:
```bash
python <skill-dir>/scripts/bootstrap.py --repo G:\minimax - workspace\Paper agent
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

The 8 wrapper scripts share a `_pa_root.py` helper that tries 4 strategies in order:

1. `$PAPER_AGENT_ROOT` env var (explicit override)
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



### `scripts/search.py` — Search 8 engines (v3.9.22.0+)

```bash
python scripts/search.py QUERY [options]
  --engine [crossref|openalex|semanticscholar|arxiv|aminer|cnki|pubmed|all]  default=all
  --limit N                          default=20
  --year-min YYYY                    default=None
  --year-max YYYY                    default=None
  --output FORMAT [json|markdown]    default=json
```

Returns JSON list of papers with `title / authors / year / venue / doi /
abstract / tldr / open_access / cites / engine`. `all` runs all 8
engines in parallel and dedupes by DOI. AMiner is best for Chinese
papers; PubMed for biomedical; arXiv for preprints; ClinicalTrials
returns trial registry records.

### `scripts/fetch.py` — Fetch single paper PDF

```bash
python scripts/fetch.py DOI [options]
  --prefer [arxiv|pmc|pmc-pdf|unpaywall|s2|biorxiv|core|osf|chemrxiv|auto]  default=auto
  --output-dir DIR                  default=.
  --no-cache                        skip cache lookup
```

Tries 14 channels in cascade order. Returns JSON with `saved_as /
via_channel / via_url / size_bytes / elapsed_sec`. For PMC papers
(PubMed Central), use `--prefer pmc-pdf` to force JATS XML → real PDF
render via headless Chromium (~20-25s).

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

### `scripts/review.py` — Literature review synthesis

```bash
python scripts/review.py CORPUS [options]
  --output FILE                     default=lit_review.md
  --topic "topic name"              focus synthesis on a theme
  --max-papers N                    default=50
  --topics                          cluster corpus by topic instead
  --top-k-clusters N                default=5
```

`CORPUS` is a directory containing PDFs or a BibTeX file. Synthesizes
a Markdown lit review with: introduction, theme-based sections, paper
summaries, gap analysis, and references. The `--topics` flag does
clustering instead (TF-IDF + KMeans) and writes cluster summaries.

### `scripts/citations.py` — Walk citation graph

```bash
python scripts/citations.py DOI [options]
  --direction [forward|backward|both]  default=both
  --limit N                          default=50
  --output FILE                     default=None (stdout)
```

Uses OpenAlex API (no key required). Forward = papers that THIS paper
cites; backward = papers that cite THIS paper.

### `scripts/keys.py` — API key management

```bash
python scripts/keys.py [command]
  list                              show all keys + status
  check SERVICE_ID                  live-probe a single service
  add SERVICE_ID KEY                add a new key
  audit                             show expiry warnings
```

Reads from `.env` + `~/.paper-agent/keys.json`. Never logs the actual
key value (only last 4 chars).

### `scripts/cache.py` — Cache management

```bash
python scripts/cache.py [command]
  stats                             show cache size + oldest entry
  clean --older-than-days N         delete old PDFs
  list                              list all cached papers
  clear                             remove all (with confirmation)
```

Cache lives at `~/.paper-agent/cache/`. Stores PDFs + metadata.

### `scripts/version.py` — Show version + dep status

```bash
python scripts/version.py
```

Prints paper-agent version, Python version, key dep status
(playwright, requests, etc.). Useful for first-time setup validation.

## Common workflows

### 1. Search → fetch → Zotero push

```bash
# 1. Search
python scripts/search.py "long-term care insurance" --engine all --limit 30 > results.json

# 2. Extract DOIs and fetch
jq -r '.[].doi' results.json | head -10 | xargs -I {} python scripts/fetch.py {}

# 3. Push to Zotero (uses pa zotero-push directly)
python -m pa_cli.cli zotero push --corpus results.json
```

### 2. BibTeX → batch PDF → lit review

```bash
# 1. Batch fetch
python scripts/fetch_batch.py refs.bib --output-dir ./pdfs/ --report fetch_report.json

# 2. Synthesize lit review
python scripts/review.py ./pdfs/ --output lit_review.md --topic "long-term care"
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

- All scripts return **JSON to stdout** on success and **error JSON
  to stderr** on failure. Parse both.
- All scripts support `--help`.
- All scripts are idempotent (cache-aware; safe to re-run).
- This skill is read-only on the agent's project workspace unless
  the user explicitly asks for fetch/review which write files.
