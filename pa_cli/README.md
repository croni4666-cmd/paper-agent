# pa-cli (paper-agent CLI)

Lightweight CLI for **fetching academic papers and synthesizing lit reviews**.

Implements the **paper-agent v4 design principle**: after 5 minutes of Cloudflare
challenge failure, stop iterating and surface a "your turn" handoff to the user
via a real browser session.

## Quickstart

```bash
# From the project root
python -m pa_cli <command> [options]

# Or after install
pa <command> [options]
```

## Commands

### `pa fetch <DOI>` — Single PDF recovery with 8 channels

```bash
python -m pa_cli fetch 10.1016/j.caeo.2024.100184 \
  --output-dir ./pdfs \
  --proxy http://127.0.0.1:7897 \
  --max-total-sec 300
```

Channels (priority order, all optional via `--channels`):

| # | Channel | When it works |
|---|---|---|
| 1 | `openalex` | Almost always (API call; OA flag returned) |
| 2 | `arxiv` | Only for `10.48550/...` DOIs |
| 3 | `unpaywall` | Requires registered email; legal OA |
| 4 | `doi_redirect` | DOI.org → publisher landing page |
| 5 | `playwright_pdf` | `/doi/pdf/` URL pattern (T&F works) |
| 6 | `playwright` | Last-ditch; full Cloudflare bypass needed |
| 7 | `scihub` | Gray; user consent assumed |
| 8 | `unpaywall_pdf` | Inline fetch after Unpaywall URL discovery |

Returns JSON with per-channel results, `saved_as` path on success, and a
`handoff` block on 5-minute timeout with `user_action_required` instructions.

### `pa search <query>` — 5-engine search

```bash
python -m pa_cli search "AI literacy higher education" \
  --year-min 2023 --year-max 2025 --limit 30 \
  --engine openalex,crossref \
  --output results.json
```

Engines: `crossref`, `openalex`, `arxiv`, `semanticscholar`, `core`. Set
`CORE_API_KEY`, `S2_API_KEY`, `OPENALEX_API_KEY` env vars for higher rate
limits. Results are deduped by DOI (arXiv ID fallback) and merged with
`found_by: [...]` arrays.

### `pa review <corpus_dir>` — Lit review synthesis

```bash
python -m pa_cli review ./pdfs --output lit_review.md --word-count-min 1000
```

Walks a directory of PDFs, extracts text via PyMuPDF, classifies each paper
as full-text (≥1000 words) or abstract-only, and outputs a structured
markdown template ready for LLM-driven deeper synthesis. Papers below the
word-count threshold are flagged for human handoff per paper-agent v4.

### `pa version` — Dependency status

```bash
python -m pa_cli version
```

Shows paper-agent version and key dep status (click, pymupdf, arxiv, requests).

### `pa keys` — API key registry + expiry reminders

```bash
python -m pa_cli keys list                 # show all known keys with status
python -m pa_cli keys check                # live probe each key, write alerts file
python -m pa_cli keys check openalex       # probe one key
python -m pa_cli keys add openalex <key> --expires 2027-01-01 --tier paid
python -m pa_cli keys audit                # count active/expiring/missing
python -m pa_cli keys remind               # print warnings + write alerts file
```

Two-layer storage:
- `.env` (gitignored): actual secrets
- `keys_registry.json` (committed): metadata only — service, tier, expiry,
  last-checked, last-used, notes

**Auto-reminder**: every CLI invocation silently runs `keys remind`. If any
key expires within 14 days or is already expired/missing, a single-line
warning prints to stderr before the subcommand's output. No exit code
change; non-intrusive.

**Daily cron**: `pa-keys-daily-check` (mavis agent, `0 9 * * *` Asia/Shanghai)
probes all keys + writes alerts to `~/.mavis/state/api_key_alerts.json`. The
Mavis session-start hook reads this file to surface reminders proactively.

Status indicators:
- `✓ active` — healthy
- `⏰ expiring-soon` — ≤14 days
- `⚠ expiring-week` — ≤7 days
- `🚨 expiring-today` — within 24h
- `❌ EXPIRED` — already past expiry
- `✗ missing` — env var not set

## Architecture

```
pa_cli/
├── __init__.py        # version + public API surface
├── __main__.py        # python -m pa_cli entry point
├── cli.py             # Click command group (fetch / search / review / version / keys)
├── fetch.py           # 8-channel PDF recovery with CF timeout
├── search.py          # 5-engine academic search with dedup
├── review.py          # corpus → lit review synthesizer (PyMuPDF + template)
└── keys.py            # API key registry + expiry reminders
```

Companion files (project root):
- `.env` (gitignored): actual secrets
- `keys_registry.json` (committed): metadata only

## The v4 Design Principle

> "After 5 minutes of Cloudflare challenge failure, stop iterating and
> surface a 'your turn' handoff."

Cloudflare protects ~70% of academic PDF endpoints (Elsevier, T&F,
worktribe, ResearchGate, Anna's Archive) with checks that Playwright headless
**cannot reliably pass**:

1. TLS JA3 fingerprint
2. HTTP/2 frame order
3. Canvas / WebGL fingerprint
4. `navigator.webdriver` flag
5. Sec-CH-UA-* client hint headers
6. Mouse-movement entropy (real human Bezier)
7. `cf_clearance` cookie timing (15-30 min TTL, bound to IP + UA + TLS hash)

A real human browser session bypasses all 7 — but is not automatable. The CLI
therefore **detects** the failed handoff, surfaces the OA URL(s) discovered,
and lets the user click them in Chrome themselves. Total automation cost:
~5 minutes; total human handoff cost: ~30 seconds.

See `CHANGELOG.md` v3.2 entry for the empirical basis.

## Install (optional)

For system-wide `pa` command:

```bash
cd "G:\minimax - workspace\Paper agent"
pip install -e .
```

Then `pa fetch ...` works from any directory.