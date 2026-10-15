# Local run report (P3-44)

`pa run-report` summarizes result JSON files you explicitly select. It does not
start searches, downloads or reviews. No credentials, dotenv, provider SDK,
private corpus, journal database or linked output document is read.

```console
pa run-report --search search.json --fetch batch.json --review review-receipt.json --output run.md
pa run-report --fetch batch.json --format json --strict
```

Any nonempty selection is supported. Missing stages are listed under
`omitted_stages`; they are never inferred successful. The overall status applies
only to supplied stages. `--output` requires an existing parent directory; omit
it to print the report. Exit 0 means a report was produced, even if a stage
failed. `--strict` exits 1 unless every supplied stage reports success. Usage and
publication failures remain nonzero independently of `--strict`.

## Supported contracts

The output JSON schema is `paper-agent-run-report`, version **1**. Input adapters
are explicitly identified as `pa-v4-search-legacy/1`, `pa-v4-fetch-legacy/1` and
`pa-v4-review-legacy/1`. They support the following existing **unversioned** v4
formats; this does not promise compatibility with arbitrary external JSON.

| Input option | Accepted source | Reported facts |
| --- | --- | --- |
| `--search` | `pa search` JSON, or search wrapper JSON retaining `engine_status`, `engine_errors`, `by_engine`, `dedup_count`, `results` | Engines reporting ok/error and result count; an empty successful search remains successful |
| `--fetch` | `pa fetch-batch --summary-json batch.json`, wrapper `--report` JSON, or full wrapper JSON containing `summary`, `status`, `exit_code`, `cli_exit_code` | Disjoint total/success/failure/skipped counts, records reporting available, global timeouts; a failing child downgrades completion |
| `--review` | Saved JSON from `.agents/skills/paper-agent/scripts/review.py` | `completed` process receipt for synthesis/clustering, or recognized wrapper failure receipt; output document and evidence remain unverified |

Save JSON output rather than interleaved console logs. A review Markdown draft or
evidence manifest is not a wrapper receipt. Selected search failures without the
full engine summary, and fetch failures without a batch summary, remain unknown.

`success`, `partial`, `failed` describe the supplied records, not newly checked
artifacts. `unknown` covers unreadable, unsupported, empty-batch or inconsistent
input. Unknown dominates the overall status; otherwise mixed success/failure or
any partial stage produces partial. No relationship, shared run ID, source
coverage, exclusions or scientific quality is inferred between separate files.

Skipped batch records require special care: `skipped-existing` with true success
is reported available; `global-timeout` with false success is incomplete. Both
belong to the existing `n_skipped` count. Aggregate counts must exactly agree
with the per-record flags. A process completion receipt cannot establish that
the referenced review document exists or is valid.

## Privacy, snapshots and failure behavior

- Only regular files are accepted, at most 8 MiB per selected input. JSON must
  be UTF-8 (optional BOM). Duplicate keys, non-finite numbers, malformed shapes
  and declared versioned input formats are rejected as unknown.
- Each readable, size-bounded input has a SHA-256 of the exact bytes used for
  parsing. The fixed `source_ref` is its input role (`search`, `fetch`, `review`).
  A digest identifies this JSON snapshot; it is not a PDF hash or evidence-binding
  guarantee, and does not assert that the source stayed unchanged afterward.
- Paths, filenames, URLs, queries, titles, free-text errors and credential values
  are omitted rather than copied then pattern-redacted. Output references from
  source records are intentionally not reproduced. Input failures use finite
  reason codes and do not hide the other selected stages.
- Output is written to a temporary file beside the chosen destination, flushed
  and replaced atomically. A write or replacement failure preserves an existing
  destination. Input paths, resolved aliases and existing hard links cannot be
  used as output. These are publication semantics, not a durability guarantee
  across power loss or a transaction across multiple selected input files.

Evidence identity and binding remain separate, blocked on the PR #16 fixes.
This report delivers the bounded operational part of historical M4; its evidence
coverage and real-corpus acceptance remain deferred. Generated fixtures and CI
validate engineering behavior only. No new dependencies or release are needed.
