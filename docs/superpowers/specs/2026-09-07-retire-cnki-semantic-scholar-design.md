# Retire CNKI and Semantic Scholar

**Status:** approved design, awaiting implementation approval  
**Date:** 2026-09-07

## Purpose

Make paper-agent's default research path reliable in the current user environment. CNKI relies on short-lived local cookies, a proxy flow, and anti-automation controls. Semantic Scholar returns 429 without a configured API key and has not provided a measurable benefit in the current environment. AMiner has successfully supplied Chinese and multi-word search results and becomes the Chinese-coverage engine.

## Decision

Remove CNKI and Semantic Scholar as product capabilities, not merely from the default engine list.

The supported search engines become Crossref, OpenAlex, arXiv, AMiner, PubMed, ClinicalTrials, and CORE when explicitly configured. AMiner remains optional when its key is absent, but is the supported replacement for Chinese and multi-word retrieval.

Playwright and Chromium remain optional dependencies because the PMC JATS-to-PDF path uses them. Their removal is out of scope.

## Public interface

Remove these commands and options:

- pa cnki status, pa cnki setup, and pa cnki search
- pa cnki-guide
- --engine cnki and --engine semanticscholar
- pa fetch --prefer cnki and pa fetch --prefer s2
- CNKI and Semantic Scholar values in MCP fetch schemas

A retired engine name must be rejected by Click's normal option validation. It must never appear as an accepted-but-silently-skipped engine.

pa doctor must no longer inspect CNKI or Semantic Scholar. It retains Playwright/Chromium because the PDF renderer depends on it, and reports AMiner, arXiv, PubMed, and the local browser runtime.

## Code and data removal

Delete dedicated CNKI and Semantic Scholar modules:

- pa_cli/cnki_channel.py
- pa_cli/s2_channel.py
- CNKI cookie-export scripts
- the CNKI batch-guide module when it has no remaining non-CNKI caller

Remove their imports, fetch cascade branches, engine registration, API-key registry entries, cached-enrichment hooks, user hints, and documentation references.

Keep historical benchmark and roadmap records as historical evidence. Add one concise dated retirement note; do not rewrite past release history. Delete only operational instructions that tell users to configure or invoke retired engines.

## Data flow after removal

pa search QUERY --engine all queries Crossref, OpenAlex, arXiv, AMiner when configured, PubMed, and ClinicalTrials. It collects source status, deduplicates results, then applies existing quality filters.

pa fetch DOI --prefer auto uses the supported legal/open and existing fallback channels without CNKI or Semantic Scholar. A Chinese DOI follows the same supported cascade rather than opening a browser session.

For Chinese retrieval, users use AMiner through normal search. The system does not claim that AMiner can retrieve paywalled CNKI full text.

## Failure behavior

Missing AMINER_API_KEY continues to skip AMiner with an explicit engine status and remediation hint. No retired-engine key, cookie, proxy, or browser warning is emitted.

A missing Playwright browser remains unavailable in pa doctor, because it prevents local JATS-to-PDF rendering. This is independent of the retired CNKI functionality.

## Validation

Implementation must include tests that prove:

1. pa search --engine all does not schedule CNKI or Semantic Scholar.
2. Retired engine and fetch-preference values are rejected by the CLI.
3. pa doctor --json contains neither retired engine nor retired-key advice.
4. pa fetch --prefer auto has no CNKI or Semantic Scholar branch.
5. Existing supported engines still return structured result/status data.
6. A real low-volume AMiner query and a PMC JATS-to-PDF retrieval still succeed.

Run compilation, the complete unit suite, CLI help checks, the real AMiner query, and the real open-access PDF test before creating a pull request.

## Non-goals

This work does not replace Semantic Scholar's recommendation, embedding, or citation graph APIs with a new paid AMiner relation integration. Those additions require a separate evidence-based proposal. It does not attempt to bypass CNKI authentication, CAPTCHA, or institutional access controls.
