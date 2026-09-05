# PDF retrieval

Start with `scripts/fetch.py DOI --output-dir ABS_DIR`. Use `--prefer auto` unless there is a reason to select a channel; inspect `--help` for accepted values. The wrapper and underlying CLI expose different options.

| Preference | When useful |
| --- | --- |
| `pmc` | Biomedical paper available through PMC |
| `pmc-pdf` | Render PMC JATS XML as PDF; requires Playwright/Chromium |
| `s2` | Semantic Scholar has an open-access PDF link |
| `biorxiv` | bioRxiv/medRxiv preprint |
| `core` | CORE indexes a full-text copy |
| `osf` | OSF-hosted preprint |
| `chemrxiv` | ChemRxiv preprint |
| `arxiv` | arXiv counterpart exists |
| `unpaywall` | Look for an open-access copy |

Underlying fallback sources and order depend on the installed version. Do not assume every source has a wrapper `--prefer` option.

## Operational details

- PMC may return XML or fail to render. A `pmc-pdf` preference does not guarantee success; inspect the saved file before reporting a PDF.
- CORE URLs can be stale or quota-limited. `CORE_API_KEY` and `UNPAYWALL_EMAIL` are relevant configuration values; use actual service errors to diagnose access.
- Preprint hosts can return rate limits or browser challenges. Report blocked items or try an available alternative.
- Inspect returned paths, sizes and channel information. Reject HTML/XML error pages mislabeled as PDFs.
- Cache hits may avoid a download. `--no-cache` skips lookup; it does not imply that successful results will never be cached.
- For BibTeX batches, use `fetch_batch.py --report ABS_JSON --skip-existing` and report failures separately.
