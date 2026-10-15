# paper-agent usage guide

This guide covers the common local workflow: search, curate references, work with papers you are authorized to access, and create review or manuscript drafts. Commands that search, download, enrich, or sync data may contact external services; paper-agent itself does not make the resulting literature review scientifically validated.

For gateway accounting and v3-to-v4 migration, see [the v4 gateway guide](gateway-v4.md). For every command and option available in your installation, run `pa --help` or `pa <command> --help`.

## 1. Install

Python 3.10 or newer is required. From a local checkout:

```console
python -m pip install -e .
pa --version
pa --help
pa doctor
```

`pa doctor --json` inventories optional packages, Pandoc on PATH and credentials
already present in the process environment. It makes no network requests, starts
no browser and reads no cookie files, `.env`, key registry or paper collection.
Missing optional capabilities produce `attention`, not a broken CLI. `ready`
means locally discoverable/configured only; package imports, browser installation
and credential validity still need separate verification.

The base install is enough for core CLI workflows. Some integrations and optional features need extra packages or credentials. Install only the extras you need, and never commit API keys, tokens, or private configuration files.

## 2. Search and save references

Search the supported metadata providers and save BibTeX for later steps:

```console
pa search "AI literacy" --year-min 2020 --limit 20 --format bibtex -o refs.bib
```

For machine-readable search results, use JSON (the default):

```console
pa search "AI literacy" --year-min 2020 --limit 20 -o results.json
```

Use `--engine` to select providers, `--year-min` / `--year-max` to constrain publication years, and `--limit` to cap results per provider. Results depend on provider coverage and availability; inspect the records and deduplicate or correct them before relying on the bibliography. Some providers may require an API key for full access or enrichment. Use `pa keys --help` to manage supported keys.

### Export references as RIS

To hand off references as a local RIS file, use:

```console
pa export refs.bib --target ris -o refs.ris
pa export results.json --target ris -o results.ris
pa project export ai-literacy --format ris -o project.ris
```

RIS export reads bibliography metadata only; it does not fetch/parse PDFs or
upload to a reference manager. JSON may contain a record list or `papers`,
`entries`, or search `results`. Unicode, repeated authors and available DOI/arXiv
metadata are retained. Missing optional fields are omitted. RIS metadata reports
`n_pdfs: null` because the PDF inventory is not inspected. Output cannot alias
source files; failed file publication preserves an existing destination. Verify
the chosen reference manager's import behavior; no universal client compatibility
or TeX-to-Unicode conversion is claimed.

## 3. Fetch papers you may access

For a single DOI, choose a source appropriate to the paper and your access rights. For example, try Unpaywall or arXiv first where applicable:

```console
pa fetch 10.1234/example --prefer unpaywall --output-dir ./pdfs
pa fetch 10.48550/arXiv.2401.01234 --prefer arxiv --output-dir ./pdfs
```

The DOI values above are examples. Check `pa fetch --help` for supported channels, caching, timeouts, and source selection. The fetch cascade can contact multiple services; use only sources you are authorized to use and follow the relevant provider, publisher, and institutional terms.

For batch processing, paper-agent accepts a BibTeX file:

```console
pa fetch-batch refs.bib --out-dir ./pdfs --skip-existing --report fetch-report.md
```

Review the selected channels and behavior in `pa fetch-batch --help` before running a batch. A failed fetch does not mean the paper is unavailable through your library or institution.

## 4. Draft a literature review from local PDFs

Put PDFs you are permitted to process into a folder, then generate a Markdown working draft:

```console
pa review ./pdfs --output literature-review.md
```

The output is a draft for human verification. Check quotations, citations, extracted claims, study characteristics, and exclusions against the source papers. For systematic reviews, screening decisions and PRISMA counts must reflect your actual review process; the tool cannot certify them.

You can also make a PRISMA flow diagram from counts you have checked:

```console
pa prisma --identified 100 --after-screening 30 --after-eligibility 20 --included 15 -o prisma.md
```

## 5. Build a manuscript from your own draft

Create an outline from a BibTeX file, edit it into your own manuscript, check citation keys, and build an output:

```console
pa scaffold refs.bib --out skeleton.md
# Edit skeleton.md and write/verify the manuscript text.
pa cite-check refs.bib skeleton.md --strict
pa build refs.bib --skeleton skeleton.md --out manuscript.docx
```

The `build` command formats a supplied Markdown skeleton; it does not write or validate scholarly arguments. Output support depends on installed tools. PDF output may require a PDF engine; see `pa build --help`.

## 6. Keep a topic project

Projects keep topic-specific references and related local state together:

```console
pa project init "ai-literacy" --title "AI literacy"
pa project status "ai-literacy"
pa project --help
```

Project capabilities vary by subcommand. Use `pa project --help` and `pa project <subcommand> --help` before importing or removing data.

## 7. Optional integrations

Zotero and Obsidian are optional. They can read or write data outside the local project, so check the target library or vault and command options before applying changes.

```console
pa zotero --help
pa zotero check --help
pa zotero push --help
pa obsidian --help
```

Zotero API workflows require credentials such as `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID`. Keep secrets in a secure local configuration and never place actual credentials in shell history, examples, reports, or version control.

## 8. Gateway accounting in v4

The gateway evaluates requests locally and accounts for reservations in a transactional SQLite journal. It does not itself call an external provider. To inspect a journal, use `status`, `doctor`, and `audit`; to migrate an existing v3 ledger, follow [the migration guide](gateway-v4.md) first. Do not run v3 and v4 writers against the same accounting domain at the same time.

## 9. Summarize saved run results offline

```console
pa run-report --search search.json --fetch batch.json --output run.md
pa run-report --fetch batch.json --format json --strict
```

The report summarizes only the JSON files you select, lists omitted stages and
marks failed, partial or unknown results. It never repeats a run or opens linked
PDFs. A review completion receipt does not verify its output or evidence. See
[supported formats and report behavior](local-run-report.md). `--strict` returns
nonzero if any supplied stage is incomplete or unknown.

## Troubleshooting

- **`pa` is not found:** activate the environment where you installed the package, or invoke it with `python -m pa_cli`.
- **A provider returns no results or an error:** check its status in the output, retry later, reduce the query scope, or select another provider. Network access, quotas, and provider APIs can change.
- **A fetch fails:** verify the DOI and try a source you are entitled to use, including your library or institutional access.
- **A command option differs:** the installed CLI's `--help` is authoritative for that version.
- **A v3 gateway ledger is present:** stop old writers and follow the migration and backup steps in [gateway-v4.md](gateway-v4.md) before evaluating requests with v4.

## Scope of validation

Real-corpus work, human labels, and corpus-dependent evaluation are indefinitely suspended. Automated checks and generated fixtures support software consistency only; they are not evidence that summaries, rankings, extracted claims, or scientific conclusions are accurate.
