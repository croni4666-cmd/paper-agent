# Paper Agent skill reliability roadmap — 2026-09

This delivery roadmap supplements the repository's long-term
[ROADMAP.md](../ROADMAP.md). It covers the local Codex skill wrapper only:
reliable execution, honest download results, discoverable search controls and
evidence-traceable reviews. It does not reopen model-reranking research already
gated by the Global Sample Pool.

## Guiding rules

- Keep the workflow local-first: no hosted service, paid API or mandatory
  account.
- Report partial results and missing evidence explicitly; never equate a process
  exit code with a verified artifact.
- Preserve user-selected files, queries and source choices. New automation is
  opt-in unless it only makes existing output more truthful.
- Measure changes with fixture tests first, then a small manual smoke check
  against public sources after review.

## Delivery sequence

| Milestone | Status | Scope | Evidence of completion |
| --- | --- | --- | --- |
| M0 — concise skill guidance | Ready in [PR #11](https://github.com/croni4666-cmd/paper-agent/pull/11) | Remove stale and duplicate wrapper guidance; keep command and reference routing | Skill validation plus reference-link check |
| M1 — verified retrieval | Ready in [PR #12](https://github.com/croni4666-cmd/paper-agent/pull/12) | One child interpreter, UTF-8 execution, caller-relative paths, PDF signature/EOF validation, explicit success/partial/failure batch states | 15 offline wrapper tests; one reviewed smoke fetch after merge |
| M2 — searchable quality controls | Ready in [PR #13](https://github.com/croni4666-cmd/paper-agent/pull/13) | Strategy presets, source filtering, existing quality labels and transparent quality summary | 7 offline wrapper tests; compare source counts on two representative queries |
| M3 — evidence-traceable reviews | Planned | Corpus manifest, stable evidence IDs, review citations that resolve to the manifest, and a post-generation validation report | Fixture corpus test verifies every citation resolves and every listed input is classified |
| M4 — research workflow audit | Proposed | A single local run report joining search, retrieval and review: selected sources, exclusions, failed downloads and evidence coverage | Run on a small user-selected corpus; no external synchronization |

## Merge and verification order

1. Review and merge #11 independently; it changes documentation only.
2. Review and merge #12. Run its offline tests, then perform one manual fetch
   with a known open-access DOI and inspect the returned file.
3. Rebase or merge #13 after #12. Confirm `fast`, `biomedical` and the default
   engine mode return their declared source metadata.
4. Start M3 only after #12 and #13 are merged. It builds on their consistent
   paths, statuses and search metadata.
5. Consider M4 only after M3 supplies a validated evidence manifest.

## M3 design boundary

M3 will generate a sidecar manifest, not rewrite source PDFs or fabricate
citations. Each manifest entry records a stable ID, file path, available
identifier (DOI or equivalent), title when known, source metadata and evidence
basis (`full_text`, `abstract`, `metadata`, or `unavailable`). The generated
review uses these IDs in its claims and produces a validation report for
unresolved IDs, unused inputs and claims based only on abstracts.

M3 does not assess the scientific truth of a claim, identify a paper from a
PDF without reliable metadata, or turn abstract evidence into full-text
evidence. Those distinctions must stay visible in output.

## Success metrics

| Metric | Baseline | Target for this roadmap |
| --- | --- | --- |
| Wrapper result ambiguity | A successful process may hide bad files or partial batches | Every fetch result has an explicit terminal status and verified file metadata where applicable |
| Search provenance | Users infer source coverage from raw results | `by_engine`, `found_by`, strategy metadata and quality summary are present |
| Review traceability | Theme claims may not identify supporting inputs | Every M3 evidence ID resolves to exactly one manifest entry; unresolved IDs fail validation |
| Scope discipline | Advanced reranking can start without adequate labels | No new reranker is started before the existing Global Sample Pool gates unlock |

## Deferred work

- New embedding, cross-encoder, LLM-listwise or cascade rerank methods remain
  governed by the existing sample-pool gates in `ROADMAP.md`.
- PDF identity matching, malware scanning and full PDF conformance validation
  are out of scope for M1; its check only rejects common non-PDF and truncated
  artifacts.
- Zotero, Obsidian and any external synchronization are excluded from M4 until
  the local manifest and run report have proven useful.
