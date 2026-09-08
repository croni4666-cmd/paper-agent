# Paper-Agent Roadmap

Last updated: 2026-09-08
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

### P0.2 — Engine contract tests and live-smoke harness

Status: in progress

Implemented: opt-in `pa engine-probe` JSON reports, sequential engine execution,
validated limits and engine selection, and fixed diagnostics that do not copy
provider exception text. Formal tests cover probe validation and error handling.

Added: offline normalized-result fixtures for all six public engines (AMiner Pro and Basic
paths), including Crossref empty dates and OpenAlex missing-author/date regressions.
Added: bioRxiv, CORE, OSF, and ChemRxiv downloader contracts for success,
non-PDF/empty responses, exact size limits, oversize, and connection/read failures.
Added: main HTTP response lifecycle, gzip/deflate decoding, HTTP error bodies,
and safe transport-failure return contracts.
Added: JATS cold-cache paths, malformed/error XML, invalid IDs, network failures,
and unavailable-cache contracts.
Added: standalone/namespaced JATS rendering contracts and an opt-in real Chromium
PDF test (`PA_TEST_BROWSER=1`, with Playwright browser and pypdf installed).
Added: figure response size/header checks, safe failure logs, embedding attributes,
and temporary-file/browser cleanup contracts. Opt-in tests use a local HTTP fixture
and real Chromium to verify a PDF image object, encoded file paths, and cleanup
after a stalled image times out. Tested with the declared Playwright 1.60 extra.
Run the browser tests with `PA_TEST_BROWSER=1` after installing `.[browser]`,
`pypdf`, and Playwright Chromium. Default CI skips browser integration tests.
Limits: publisher-specific layouts, lazy images across pages, and external
provider behavior remain unverified. The image size limit applies to Python
embedding downloads; failed embedding still leaves the existing browser URL
fallback. Image header checks are not a full image decode. Page-load timeout
is not an end-to-end conversion deadline.
Added: PMC PDF versus XML-only outcomes, automatic fallback, CLI exit status,
batch XML preservation, and saved-file validation contracts. The default CLI
now uses the automatic cascade; explicit source choices retain their routing.
The wrapper checks PDF headers, not full document integrity.
Remaining: other retrieval paths and size limits need equivalent coverage.
P0.2 is not complete.

Added: per-call proxy restoration across success/error/exception outcomes,
MCP-to-wrapper source forwarding, explicit-preference validation/precedence,
and forced JATS mode contracts. MCP handler tests stub the optional transport
SDK; they do not verify a live stdio MCP client/server session.

Next retrieval fixes identified during contract review:

- Implement a real, cancellable end-to-end runtime deadline. The legacy option
  remains unenforced and the CLI now states that limitation explicitly.

Added: best-effort PDF cache writes after wrapper success (also with cache lookup
disabled), small-PDF cache acceptance, per-call Unpaywall email precedence and
cleanup, and private diagnostic contracts. Formal tests isolate the PDF cache.
Cache acceptance checks headers only, not complete document integrity.

Separate deterministic offline contract tests from opt-in live probes. Each
supported engine should have a fixture for result normalization and a small,
rate-limited probe that records availability, latency, result count, and
actionable failures without exposing credentials.

Acceptance criteria:

- Every public search engine has normalized-schema contract coverage.
- Every retrieval channel has success, non-PDF, oversize, and network-failure
  coverage where applicable.
- Live probes are explicitly opt-in and emit a machine-readable report.
- A failing external service is reported as an environmental result, not a
  flaky unit-test failure.

Why now: provider behavior changes more often than core code, and the current
test suite mostly covers recent fixes rather than all engine contracts.

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

- 3.9.29.1: proxy credential redaction, unified network validation, JATS
  network-state fix, compatible dependency constraints, and a full security
  audit.
- 3.9.29.0: CNKI and Semantic Scholar retirement, PubMed abstract and MeSH
  enrichment, PMC JATS cache, ChemRxiv migration, fetch statistics, and
  formal-test isolation.

Older release details are retained in CHANGELOG.md. Historical research notes
remain in the repository only when they support a current decision.
