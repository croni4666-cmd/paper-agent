---
name: paper-agent
description: Use when searching academic papers, fetching PDFs by DOI or BibTeX, extracting page-aware evidence, verifying claims and provenance, using Zotero or topic projects, generating PRISMA diagrams, tracing citations, clustering a corpus, drafting literature reviews, or managing paper-agent keys and cache. Not for general web search.
metadata:
  version: 4.1.1
  pa_cli_version: 4.1.1
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

`review` in 4.1.1 produces a source inventory with completeness marked unverified.
It does not adjudicate scientific claims or certify full text from word count.
See the release validation attachment for tested paths and remaining boundaries.

Prefix each entry with `python "<skill-dir>/scripts/…"`. Use the selected script's `--help` for full options.

| Task | Script and main arguments |
| --- | --- |
| Search | `search.py QUERY --engine all --limit 20` |
| Fetch one PDF | `fetch.py DOI --output-dir ABS_DIR` |
| Fetch BibTeX PDFs | `fetch_batch.py ABS_BIB --output-dir ABS_DIR --report ABS_JSON --skip-existing` |
| Draft literature review | `review.py ABS_CORPUS --output ABS_MD` |
| Cluster corpus | `review.py ABS_CORPUS --topics --output ABS_JSON` |
| Trace citations | `citations.py DOI --direction forward --limit 50 --output ABS_JSON` |
| Key status | `keys.py list`, `check SERVICE_ID`, `audit` |
| Cache inspection / cleanup | `cache.py stats`, `path`, `clean --older-than-days N --dry-run` |
| Page-aware evidence / claims / provenance | `evidence.py --help`, `verify_claim.py --help`, `provenance.py --help` |
| Zotero / topic projects / PRISMA | `zotero.py --help`, `project.py --help`, `prisma.py --help` |

`ABS_CORPUS` is a local directory. Search accepts `--year-min`, `--year-max`, `--strategy`, `--source`, `--quality-mode`, and `--output markdown`; `--limit` is per engine. Use wrapper help for the supported engine choices.

## Execution notes

- Select the operation requested; search alone does not imply downloading, reviewing, or syncing to Zotero.
- Inspect exit status, stdout, stderr, and actual output files. Output is often JSON, but format varies by command. Report partial failures instead of assuming every paper succeeded.
- On timeout, narrow the engine or limit; on quota/authentication failures, use an available alternative or report the missing configuration. Avoid indefinite retries.
- For PMC XML-to-PDF rendering, use `fetch.py --prefer pmc-pdf`; this requires Playwright. Confirm the result is a PDF before reporting a successful download.
- Citation `forward` means citing papers; `backward` means references. Run each direction separately for both sets. Legacy `both` is rejected rather than forwarded as an invalid CLI option.
- Review output is a draft. Check its citations and distinguish abstract-based findings from full-text evidence.
- Real-corpus collection, human labeling and dependent scientific evaluation remain indefinitely suspended. Generated fixtures only verify software behavior.
- Cache cleanup deletes files; key updates and external sync change persistent state. Perform them only within the user's requested scope. Do not expose key values.

## References — load only as needed

- [Engines](references/engines.md): database selection and API-key requirements.
- [Fetch channels](references/channels.md): retrieval fallback details.
- [CLI cheatsheet](references/cli-cheatsheet.md): advanced operations such as Zotero, PRISMA, and sample pools. Confirm syntax with `python -m pa_cli.cli <command> --help` in the configured environment; installed help takes precedence over reference examples.
