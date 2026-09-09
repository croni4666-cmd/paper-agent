# Paper-Agent Roadmap

Last updated: 2026-09-09
Current release: 3.9.29.1

## Product Direction

Paper-agent is a local-first research workflow tool. Its core job is to turn a
topic into a reviewable corpus: search across reliable public sources, preserve
metadata and provenance, acquire open-access full text where possible, and
produce material that can move into Zotero, Obsidian, or a manuscript.

The project will improve reliability and evidence quality before adding more
providers or model-heavy ranking features.

## Current Capability

- Search: Crossref, OpenAlex, arXiv, AMiner, PubMed, and ClinicalTrials.gov.
- Retrieval: DOI-based open-access cascade with local cache, batch jobs,
  channel statistics, and a Playwright fallback.
- Corpus work: BibTeX export, strict deduplication, screening export, topic
  clustering, PRISMA output, and literature-review synthesis.
- Research workflow: local projects, Zotero synchronization, optional
  Obsidian projects, and manuscript scaffold/build commands.
- Safety baseline: proxy validation, credential redaction, dependency
  compatibility constraints, formal tests, and a security policy.

## Recommended execution order

| Order | Item | User-visible gain | Completion evidence |
|---|---|---|---|
| 1 | P0.4: cache concurrency and direct-call semantics | Consistent cache and public entry-point behavior | Concurrent-writer and direct-call contracts |
| 2 | P0.2: browser CI, remaining channels, real MCP | Catch environment/transport regressions before release | Repeatable CI and stdio integration |
| 3 | P1.1: diagnostic reports and resumable batches | Retry only eligible failed papers with clear reasons | Interrupted-job restart tests |
| 4 | P0.3: shared provenance schema | Trace records from search to downloaded/exported evidence | Compatible schema and merge/export tests |
| 5 | P1.2: evidence-linked synthesis | Separate supported claims from missing/contradictory evidence | Deterministic citation-linked outputs |
| 6 | P2.1/P2.2: command modularization and reproducible release | Reduce maintenance and installation regressions | CLI compatibility and clean-install checks |

Keep six engines for now. Evaluate retrieval success, relevance, latency and
API cost on a fixed, opt-in query/DOI corpus before adding providers or ranking
models. No current AMiner price or renewal recommendation is inferred from tests.

## Active Roadmap

### P0.1 — Release and compatibility gate

Status: complete

Add a GitHub Actions workflow that runs the formal test suite on supported
Python versions, compiles the package, checks dependency resolution, and runs
the dependency vulnerability audit. The release path should fail before a
broken environment or known vulnerable dependency reaches users.

Acceptance criteria:

- Tests run on Python 3.10, 3.11, and 3.12.
- Dependency resolution uses the project metadata and requirements file.
- Vulnerability audit is visible in pull requests.
- Release documentation names the required checks.

Verified in merged PR #33: Python 3.10/3.11/3.12 tests, dependency resolution,
and dependency audit all passed.

### P0.2 — Engine and retrieval contract coverage

Status: in progress; verified improvements merged through PR #48

Completed coverage:

- Six public search engines have offline normalization fixtures; AMiner Basic
  and Pro paths are covered. `pa engine-probe` provides opt-in sequential JSON
  availability reports with validated inputs and sanitized errors.
- bioRxiv, CORE, OSF and ChemRxiv have download success, invalid-content,
  size-limit and transport-failure contracts. Main HTTP responses are closed
  consistently and decoding/error handling has regression coverage.
- PMC JATS cache validation, cold-cache output, XML-only failure and automatic
  PDF fallback are covered. Explicit source selection and Unpaywall email/proxy
  precedence have contracts. MCP handler coverage uses transport SDK stubs.
- Real Chromium tests cover article text, embedded image objects, special local
  paths and timeout cleanup. They use local HTTP fixtures, not publisher sites.
- Single-fetch workers enforce their budget; batches pass each active worker the
  shared remaining budget. Tests check that normal descendants stop on timeout.
- Single and batch output is staged. PDF copy failures/timeouts preserve old
  output; validated XML survives XML-only outcomes and cleanup uses provenance.
- Fresh PDFs and skip-existing candidates use strict pypdf page/content checks.
  Cache hits also revalidate structure under resource limits, DOI, checksum and
  365-day age. Invalid legacy entries remain on disk but return a miss.

Evidence checkpoint: PR #48 code passed 129 tests and 151 subtests locally with
`PA_TEST_BROWSER=1`, plus dependency checks. Its five CI jobs passed on GitHub.
This is historical evidence for that commit, not a new live-provider assessment.
Default CI skips the optional Chromium tests; install `.[browser]` and Chromium
and set `PA_TEST_BROWSER=1` to include them locally.

Remaining acceptance criteria:

- Add equivalent contracts for remaining retrieval channels and size limits.
- Exercise the real MCP stdio transport, not just its handler.
- Establish a reproducible browser CI job and representative JATS layout corpus
  for multi-page content, lazy images and publisher-specific structures.
- Keep external availability/quality probes opt-in and separate from offline CI;
  classify provider failures as environmental results with actionable causes.

P0.2 remains open until those coverage gaps are closed.

### P0.4 — Bounded validation and consistent cache acceptance

Status: in progress

Implemented in the current change:

- PDF parsing runs in a separate worker with a 10-second deadline, 512 MiB memory
  limit and 256 MiB input cap. Windows uses job committed memory; POSIX uses
  virtual address space. Oversized, stalled or failed validation is rejected.
- Every cache hit revalidates and hashes the same byte snapshot. The returned
  policy is `pypdf-strict-pages-v1`; no persistent migration stamp is trusted.
  Invalid legacy entries become misses without deletion; valid entries still hit.

Local evidence (2026-09-09): 133 tests and 151 subtests passed with real
Chromium enabled; the POSIX nested-process cleanup test is skipped on Windows
and must pass Linux CI before merge. Memory-allocation and stalled-parser tests
run real subprocesses. Independent review found the nested-group issue and
confirmed its fix; this is not an external publisher availability test.

Remaining acceptance criteria:

1. Cache read-race detection and deterministic interleaved-process tests are
   implemented: observed PDF/metadata changes cause a miss, mixed publication
   pairs do not hit, and a later coherent write restores the hit. This does not
   provide a lock or stable returned path. Atomic pair publication, changes after
   the final identity check, and crash durability remain unresolved.
2. Consolidate direct `fetch()` and supervised public entry-point semantics.
   Direct calls still use provider timeouts and write directly. Define which
   paths are supported before extending or deprecating legacy behavior.

Limits to retain in user documentation: strict parsing can reject repairable or
encrypted files; readable page streams do not prove visual fidelity, decoded
fonts/images or absence of malicious content. PDF/XML publication is independent,
valid cache writes can outlive output failure, and OS startup/cleanup, publication,
BibTeX parsing and progress callbacks are not a strict whole-command deadline.
POSIX children deliberately detaching into a new session escape process groups.

### P0.3 — Provenance-first result model

Status: planned

Standardize the fields carried from search through export: source engine,
source identifier, DOI normalization result, retrieval URL, retrieval channel,
timestamps, license or open-access status when known, and confidence notes.
Expose these fields in JSONL and screening export without breaking BibTeX
compatibility.

Acceptance criteria:

- One documented result schema is shared by search, fetch, and export.
- Duplicate merging preserves every contributing source.
- Users can trace an exported record back to its metadata and retrieval path.
- Schema migration is backward compatible or has an explicit migration tool.

Why now: the next quality gain comes from making results auditable, not from
adding more loosely normalized results.

### P1.1 — Retrieval diagnostics and resumable batch reporting

Status: planned

Expand fetch statistics into per-attempt diagnostics for batch jobs: source
order, response class, elapsed time, cache outcome, retry decision, and final
reason. Provide a concise report that helps users decide whether a source is
blocked, a DOI is unavailable, or configuration needs attention.

Acceptance criteria:

- Batch result records include sanitized attempt histories.
- A report groups failures by actionable cause.
- Resume skips verified files and retries only eligible failures.
- Diagnostic output never includes API keys, cookies, or proxy credentials.

Why now: local aggregate channel statistics exist, but they cannot yet explain
an individual failure well enough to guide a user.

### P1.2 — Evidence-linked review synthesis

Status: planned

Improve review output so each synthesized claim can be traced to its supporting
paper keys and available metadata. Add structured sections for evidence gaps,
contradictory findings, study type, and missing full text; keep generation
local-first and useful without an LLM.

Acceptance criteria:

- Review markdown contains stable citation keys for claims and summaries.
- It distinguishes metadata-only records from records with checked full text.
- Contradictions and evidence gaps are emitted as review tasks, not hidden.
- Output remains deterministic for the same corpus and options.

Why now: the product already creates a corpus and a draft review; traceability
is the highest-value upgrade before adding new synthesis models.

### P2.1 — Maintainable command architecture

Status: planned

Split the large command registration module into focused command modules while
preserving command names, help text, and exit behavior. Create a small command
registry and integration tests for the public command surface.

Acceptance criteria:

- Command registration is organized by feature area.
- Existing commands and options remain compatible.
- Importing a simple command does not eagerly load heavyweight optional
  integrations.
- CLI help and command-entry tests cover the public surface.

Why now: the main command module is the largest file in the package and is a
growing source of coupling risk.

### P2.2 — Reproducible installation and release artifacts

Status: parking lot

Evaluate a lockfile or constraints workflow for supported Python versions,
publish a minimal install verification command, and produce signed or
checksummed release artifacts if distribution expands beyond GitHub source
installs.

This follows P0.1 because automation must exist before adding release
mechanics.

## Explicit Non-Goals

- Do not restore CNKI or Semantic Scholar. AMiner is the Chinese-language
  alternative; the retired services did not provide enough reliable lift.
- Do not add a self-maintained general MCP server, email subscriptions, or a
  browser extension.
- Do not claim full-text coverage from metadata-only results.
- Do not enable model-based reranking by default until held-out relevance data
  demonstrates a measurable improvement.
- Do not add a provider merely to increase engine count; it must improve
  coverage, reliability, or provenance against a repeatable evaluation.

## Decision Gates

Before starting a roadmap item:

1. State the user-visible outcome and a measurable acceptance criterion.
2. Prefer local code and public APIs; require a clear reason for a new hosted
   dependency, credential, or browser automation path.
3. Add deterministic tests before implementation and live probes only where
   external behavior must be measured.
4. Run the full formal suite, security scans relevant to the change, and
   dependency checks before release.
5. Update this Roadmap and CHANGELOG only with verified outcomes.

## Completed Recently

Merged on main, still **Unreleased** (release remains 3.9.29.1):

- PR #34–#42: probes/contracts, HTTP/JATS reliability, source routing and options.
- PR #43–#44: cache population, identity/checksum/expiry and staged writes.
- PR #45–#47: real worker cancellation and protected batch/single file publication.
- PR #48: strict fresh-PDF/page-content validation and real PDF test fixtures.

Published release history:

- 3.9.29.1: proxy credential redaction, unified network validation, JATS
  network-state fix, compatible dependency constraints, and a full security
  audit.
- 3.9.29.0: CNKI and Semantic Scholar retirement, PubMed abstract and MeSH
  enrichment, PMC JATS cache, ChemRxiv migration, fetch statistics, and
  formal-test isolation.

Older release details are retained in CHANGELOG.md. Historical research notes
remain in the repository only when they support a current decision.
