# Live workflow repair verification — 3.10.0.9

Base: `7aaff8e6bc0fd275e81647f647fc2fbbfa4c9f3a` (3.10.0.8).
Branch: `codex/live-task-fixes-20261003`.

## Repairs

| Finding | Repair | Regression evidence |
| --- | --- | --- |
| Search waits after its declared timeout | Spawn a terminable provider process, drain results before joining, use bounded cleanup | Slow provider is stopped; next engine succeeds; no delayed worker writes; 200 KB payload returns |
| Scientific comparisons disappear during markup cleaning | Parse recognized markup before decoding entities; preserve unknown generic tags and spacing | Raw/encoded HbA1c comparisons, quoted `>` attributes, `<T>`/`<int>`, LaTeX escapes |
| arXiv pseudo DOI produces invalid citations | Separate DOI/arXiv ID; emit eprint/archivePrefix and working URL; interpret legacy fields on reading | New and legacy BibTeX/screening roundtrip; real DOI retained; eprint-only batch fetch |
| Actual PDF methods and inline abstract are missed | Recognize Research Method and Analysis and inline Abstract.; handle split major headings while retaining subsection parent labels | Exact-offset PDF fixtures, unknown major heading reset, results subsection inheritance |

## Local automated checks

- Windows, Python 3.13, PyMuPDF 1.28.2.
- Initial 15 regressions were run against unchanged baseline code: 13 assertion
  failures including subtests. Subsequent live testing found subsection inheritance
  needed one additional regression, which failed before its fix.
- Final CI-equivalent run: **26 scripts, 256 unittest cases, zero failures**.
  Three of those scripts use script-style smoke/integration assertions in addition
  to the unittest count. Security audit and evidence M2 are included.
- All **16 new regressions pass**. No network or paid models are used by them.
- Wheel builds successfully. Package contents include the new identifier helper,
  label subpackage and default CSL/data files. A wheel installed into a separate
  target directory passes import/version/text/identifier smoke checks outside
  the source checkout, using the existing verification environment's dependencies.
- `git diff --check` passes. GitHub CI separately covers Python 3.10/3.11/3.12
  and installs the wheel with dependencies in a clean environment.

Run the new regressions directly:

```sh
python test_output/test_live_workflow_repair.py
python test_output/test_live_task_fixes.py
python test_output/test_evidence_m2.py
python test_output/test_security_audit.py
```

The complete offline list is in `.github/workflows/ci.yml`.

## Real task: generative AI at work and software development

Fresh Crossref/OpenAlex query `generative AI at work` returns 5 records per
engine. arXiv query `ti:"Transforming Software Development"` returns 2 records.
All three engine statuses are `ok`; combined BibTeX/screening exports contain
12 records, and all 12 citation placeholders resolve without missing/typoed keys.
An initial incorrect title query returned no records; it was corrected to the
actual title. No synthetic records were added to the real-task corpus.

The eprint-only entry for `2405.01543v1` downloads through project fetch with
`prefer='arxiv'`: one success, zero failures, 625,520 bytes. The result's DOI
remains empty. Its citation URL `https://arxiv.org/abs/2405.01543v1` returns HTTP 200.

| Public PDF | Input | SHA-256 | Evidence check |
| --- | --- | --- | --- |
| Transforming Software Development with Generative AI | Fresh arXiv fetch; 15 pages | `e4a65de2bb75f5ae181f00bb6c1d5da108b1d821d173c751f8d16f15d60cf624` | methods 3 / results 3 spans; required packet ready, 8,188 serialized UTF-8 bytes |
| Generative AI at Work, NBER w31161 | Previously retrieved public snapshot, freshly indexed; 67 pages | `9af82b90f2a94f8757ace8c7b7ef0934b145a00f4156fc806f4fb8a33e1bddc2` | methods 18 / results 20 spans; required packet ready, 9,057 bytes |

Both packets require methods/results, retain exact page offsets and integrity
hashes, and fit a 10,000-byte serialized packet budget. Jev CLI preview validates
both payloads: `network_called=false`, `upload_authorized=false`. This is a local
payload check, not a live Jev decision-quality or billing test. No paid model
calls or manuscript uploads were made.

## Upgrade notes and remaining limits

- Rebuild evidence indexes to apply `headings-v2`; existing schema remains
  readable, but old section labels are not updated automatically.
- Headings and lexical retrieval remain heuristic. Unknown labels, table text,
  and reference fragments still require review; readiness is not evidence quality.
- Python library callers must use an importable script and main guard for spawned
  search workers. The CLI and MCP service entry points already have main guards.
- The 25-second budget covers each search provider's work and process startup,
  with bounded cleanup afterward. Optional enrichment is separate network work.
- Bibliographic exports change newly generated arXiv cite keys to stable
  `arxiv_<id>` keys; explicitly supplied and parsed historical keys are retained.
  Existing drafts should retain their original keys when migrating references.
- Privacy/consent, identity verification, Jev fallback policy and live dispatch
  gates were not relaxed. Keep human review for unpublished material.
