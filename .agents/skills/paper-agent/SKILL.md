---
name: paper-agent
description: Use when searching academic papers, fetching PDFs by DOI or BibTeX, tracing citations, clustering a corpus, drafting literature reviews, or managing paper-agent keys and cache. Not for general web search or reading PDFs.
metadata:
  version: 3.9.28.0
  pa_cli_version: 3.9.28.0
  author: paper-agent team (croni4666-cmd)
  license: AGPL-3.0-only WITH No-AI-Training-1.0
  homepage: https://github.com/croni4666-cmd/paper-agent
allowed-tools:
  - Bash
  - Read
  - Write
---

# Paper Agent

Use the bundled Python wrappers for academic search, PDF retrieval, and corpus analysis. Resolve `scripts/` relative to this skill directory. Pass absolute input and output paths: wrappers run the underlying CLI from its package directory.

## Setup

Requires Python 3.10+ and `pa_cli`. Check availability with `python "<skill-dir>/scripts/bootstrap.py" --check`; use `scripts/version.py` for dependency status. If missing, run `scripts/bootstrap.py --repo "<repo-path>"` to install from an existing repository. `PAPER_AGENT_ROOT` selects the repository. Run wrappers with the Python interpreter where `pa_cli` is installed.

## Commands

Prefix each entry with `python "<skill-dir>/scripts/…"`. Use the selected script's `--help` for full options.

| Task | Script and main arguments |
| --- | --- |
| Search | `search.py QUERY --engine all --limit 20` |
| Fetch one PDF | `fetch.py DOI --output-dir ABS_DIR` |
| Fetch BibTeX PDFs | `fetch_batch.py ABS_BIB --output-dir ABS_DIR --report ABS_JSON --skip-existing` |
| Draft literature review | `review.py ABS_CORPUS --output ABS_MD --topic TOPIC` |
| Cluster corpus | `review.py ABS_CORPUS --topics --top-k-clusters 5` |
| Trace citations | `citations.py DOI --direction both --limit 50 --output ABS_JSON` |
| Key status / configuration | `keys.py list`, `check SERVICE_ID`, `audit`, `add SERVICE_ID KEY` |
| Cache inspection / cleanup | `cache.py stats`, `list`, `clean --older-than-days N`, `clear` |

`ABS_CORPUS` is a PDF directory or BibTeX file. Search accepts `--year-min`, `--year-max`, and `--output markdown`; `--limit` is per engine. Supported engine choices are `crossref`, `openalex`, `semanticscholar`, `arxiv`, `aminer`, `cnki`, `pubmed`, and `all`; do not infer wrapper options from engine counts in older documentation.

## Execution notes

- Select the operation requested; search alone does not imply downloading, reviewing, or syncing to Zotero.
- Inspect exit status, stdout, stderr, and actual output files. Output is often JSON, but format varies by command. Report partial failures instead of assuming every paper succeeded.
- On timeout, narrow the engine or limit; on quota/authentication failures, use an available alternative or report the missing configuration. Avoid indefinite retries.
- For PMC XML-to-PDF rendering, use `fetch.py --prefer pmc-pdf`; this requires Playwright. Confirm the result is a PDF before reporting a successful download.
- The citation wrapper documents `forward` as references and `backward` as citing papers. Verify the installed CLI's semantics before choosing a single direction; use `both` when both sets are needed.
- Review output is a draft. Check its citations and distinguish abstract-based findings from full-text evidence.
- Cache cleanup deletes files; key updates and external sync change persistent state. Perform them only within the user's requested scope. Do not expose key values.

## References — load only as needed

- [Engines](references/engines.md): database selection and API-key requirements.
- [Fetch channels](references/channels.md): retrieval fallback details.
- [CLI cheatsheet](references/cli-cheatsheet.md): advanced operations such as Zotero, PRISMA, and sample pools. Confirm syntax with `python -m pa_cli.cli <command> --help` in the configured environment; installed help takes precedence over reference examples.
