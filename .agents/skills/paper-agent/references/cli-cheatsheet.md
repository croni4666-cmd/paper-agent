# paper-agent CLI Cheatsheet

The full `pa` CLI is available via `python -m pa_cli.cli <command>`.
This is a quick reference for the most useful subcommands.

## Core commands

### `pa search` — search 7 engines
```bash
pa search "query" [--engine all] [--limit 20] [--year-min 2020] [--output json|markdown]
pa search "数字普惠金融" --engine aminer --limit 30
```

### `pa fetch` — fetch single PDF
```bash
pa fetch <doi> [--prefer auto|pmc-pdf|s2|biorxiv|core|osf|chemrxiv|unpaywall|scihub|...] [--output-dir .]
pa fetch 10.1038/nature12373 --prefer pmc-pdf
```

### `pa fetch-batch` — batch from BibTeX
```bash
pa fetch-batch refs.bib --out-dir ./pdfs/ --max-total-sec 3600 [--skip-existing] [--summary-json report.json]
```

### `pa review` — lit review synthesis
```bash
pa review <corpus_dir_or_bib> --output lit_review.md [--topic "long-term care"] [--max-papers 50]
```

### `pa review-topics` — cluster by topic
```bash
pa review-topics <corpus_dir> --top-k 5
```

### `pa citations` — walk citation graph
```bash
pa citations <doi> [--direction forward|backward|both] [--limit 50] [--output forward.json]
```

### `pa keys` — API key management
```bash
pa keys list                          # Show all keys + status (last 4 chars only)
pa keys check semanticscholar          # Live-probe a service
pa keys audit                          # Show expiry warnings (60-day TTL etc.)
pa keys add <service> <key>            # Add a new key
```

### `pa cache` — local PDF cache
```bash
pa cache stats                         # Show cache size + oldest entry
pa cache list [--limit 20]             # List cached papers
pa cache clean --older-than-days 90    # Delete old PDFs
pa cache clear --confirm               # Wipe cache
```

### `pa version` — show version + deps
```bash
pa version
```

### `pa mcp install` — install MCP server
```bash
pa mcp install                        # Add paper-agent to ~/.codex/config.toml as MCP server
```

## Zotero integration (v3.9.15+)

```bash
pa zotero push --corpus refs.bib [--pdf-dir ./pdfs/] [--mode linked_file|imported_file]
pa zotero search --query "long-term care" [--limit 10]
pa zotero sync --corpus refs.bib [--query Q] [--push/--no-push]
```

## Obsidian integration (v3.9.16+)

```bash
pa search-and-import "query" --project <name> [--with-obsidian]
pa zotero-project pull <project_id> --vault <path>
pa zotero-project diff <project_id>
pa zotero-project sync <project_id>
```

## Sample pool management (v3.9.18+)

```bash
pa sample-pool suggest --query "..." --project <name>     # Preview candidates
pa sample-pool add --qid q001 --relevance 1 --project ...   # Commit to pool
pa sample-pool list --project <name>
pa sample-pool label --qid q001 --relevance 0
pa sample-pool export --project <name> --output pool.json
pa sample-pool audit                                       # Show operations log
```

## PRISMA flow diagram (v3.9.10+)

```bash
pa prisma --identified N --duplicates-removed N --screened N --excluded N \
         --full-text-assessed N --excluded-fulltext N --included N \
         --output prisma.png
```

## Cache behavior

- **By default**: cache is checked first (`~/.paper-agent/cache/`)
- **Cache hit**: returns in <1s with `via_channel: cache:<name>`
- **`--no-cache`**: skip cache lookup, still write on success
- **Cache size**: typically 100MB-1GB for active research

## Network / proxy

- **Default**: no proxy (uses GFW bypass if needed)
- **V2Ray clash verge proxy**: set `--proxy http://127.0.0.1:10808`
- **Env var fallback**: `HTTPS_PROXY` / `HTTP_PROXY`
- **TLS validation** (v3.9.13.0): only allows local proxies (127.0.0.1, ::1, 10.*, 192.168.*, 172.16-31.*)
- **Override for remote proxy**: `PAPER_AGENT_ALLOW_REMOTE_PROXY=1`

## Output format

Most commands support:
- `json` (default for scripts) — parseable
- `markdown` (for human reading)

Use `--quiet` to suppress progress output (useful in scripts).

## Exit codes

- `0` — success
- `1` — pa command failed (e.g. all channels 404)
- `2` — timeout
- `3` — missing dependency (e.g. playwright for JATS-to-PDF)
- `4` — invalid argument
- `5` — auth/quota error
