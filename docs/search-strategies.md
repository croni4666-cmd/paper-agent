# Search wrapper strategies

`scripts/search.py` keeps the existing `--engine all` behavior by default.
Use `--strategy` to choose a curated engine set. Strategies set a default sort
only; `--sort-by` overrides it. `--strategy` cannot be combined with an
explicit single `--engine`, because it would be ambiguous which source set
should win.

| Strategy | Engines | Default sort | Use when |
| --- | --- | --- | --- |
| `broad` | all configured engines | citation count | General coverage is more valuable than speed |
| `fast` | OpenAlex, Crossref | relevance | Quickly narrowing a general topic |
| `biomedical` | PubMed, OpenAlex | relevance | Biomedical literature and related open-access records |
| `preprints` | arXiv, Semantic Scholar | relevance | Recent technical preprints |
| `chinese` | AMiner, CNKI, OpenAlex | relevance | Chinese-language or China-focused work |

AMiner and CNKI remain optional. A strategy may return fewer sources when the
current installation lacks its credentials or browser session; inspect
`by_engine` in the response.

## Result quality

The wrapper forwards `--quality-mode flag` by default. The underlying CLI adds
its established `quality_flag` per result without removing papers. Use
`--quality-mode filter` to remove its low-quality results, or `off` to omit
the flags. The wrapper adds `quality_summary`:

- `total`: results after any selected filtering.
- `by_flag`: count per underlying quality label.
- `multi_source`: papers found by more than one engine after DOI/title
  deduplication.

`--source openalex,pubmed` narrows deduplicated results to specified source
prefixes. It works with a strategy and runs after the underlying deduplication.

These fields describe metadata completeness and cross-source overlap. They do
not measure topical relevance, peer-review status, or factual correctness.
