# Skill wrapper runtime and download results

The command wrappers (`search`, `fetch`, `fetch_batch`, `review`, `citations`,
`cache`, `keys`) use a shared launcher. It selects `PAPER_AGENT_PYTHON` when
provided, otherwise the repository's `.venv-codex` or `.venv`, then the calling
Python interpreter. A missing explicit interpreter is an error, not a silent
fallback. `PAPER_AGENT_ROOT` continues to select the repository. Bootstrap and
version diagnostics still describe the interpreter used to invoke them; run
them with the selected Python executable.

Child processes and wrapper output use UTF-8. File arguments for downloads,
reviews and citation exports are resolved relative to the caller before the
CLI changes directory. Paths may contain spaces or non-ASCII characters.

## Download result contract

`fetch.py` and `fetch_batch.py` emit one JSON object with `status` and
`exit_code`. Existing download metadata and batch `summary` fields remain.

| Status | Exit code | Stream | Meaning |
| --- | --- | --- | --- |
| `success` | 0 | stdout | All reported artifacts passed verification |
| `partial` | 1 | stderr | Some batch artifacts passed; others failed or timed out |
| `failed` | nonzero | stderr | No verified success, invalid report, or runtime error |

**Compatibility change:** batch `status: completed` becomes `success`,
`partial` or `failed`. Consumers must inspect stderr for nonzero exits;
partial batches no longer exit successfully. `cli_exit_code`, where present,
preserves the underlying process status separately from the wrapper exit code.
Other command result formats are unchanged.

Verification checks an existing file for `%PDF-` and a final `%%EOF` marker,
then records its actual size as `size_bytes`. `validation: signature_and_eof`
names this check explicitly: it is not a full PDF parser, malware scan or
confirmation that the PDF matches the requested paper. Invalid files are
reported and left in place for inspection.

Batch downloads always request a fresh temporary summary. Successful and
`--skip-existing` artifacts are both checked; old user reports cannot make a
new run appear successful. `--report` (or legacy `--summary-json`) writes the
verified summary, with corrected counts and sizes. `n_skipped` retains the
CLI convention covering cached skips and global-timeout entries; inspect each
row's `success` and `error` to distinguish them. Hard process timeouts that
prevent a fresh report are reported as failed, with files left in place.

## v4 command compatibility (2026-10-15)

The review wrapper requires a corpus directory, not a BibTeX file. It forwards
only options supported by the installed v4 CLI; legacy `--topic`, `--model`,
`--max-papers` and `--top-k-clusters` fail explicitly. Topic clustering chooses
its count automatically and writes to `--output`.

Citation `forward` means citing papers, `backward` means references. The default
is now `forward`; use two explicit invocations for both directions, since v4
does not accept `both`. Cache wrappers support `stats`, `path` and `clean`, with
`--dry-run` for a preview. Removed `list`/`clear` commands were never accepted by
the current CLI. Key `check`/`audit` omit the unsupported JSON flag.

Search strategy/quality fields describe metadata only. The wrapper rejects
non-object result rows with a JSON error instead of raising an uncaught error.

## Offline regression tests (v4)

From the repository root:

```sh
python -m unittest discover -s tests -p "test_*wrapper*.py" -v
```

Tests run real wrapper subprocesses against an isolated fixture CLI and
temporary files. They do not access paper services or modify user caches.
