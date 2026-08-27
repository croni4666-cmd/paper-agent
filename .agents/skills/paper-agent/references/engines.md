# Search Engines Reference (v3.9.22.0+)

paper-agent searches across **7 academic search engines**. Default is
`--engine all` which runs all 7 in parallel and dedupes by DOI.

| # | Engine | Best for | API key | Cite lift (vs no AMiner) |
|---|--------|----------|---------|--------------------------|
| 1 | **Crossref** | General academic, English | No | baseline |
| 2 | **OpenAlex** | Largest OA graph, citation walks | Optional `$OPENALEX_API_KEY` (higher rate) | baseline |
| 3 | **Semantic Scholar (S2)** | Recent CS / AI / ML papers | Optional `$S2_API_KEY` (higher rate) | baseline |
| 4 | **arXiv** | Physics, math, CS preprints | No | baseline |
| 5 | **AMiner (智谱学术)** | **Chinese papers**, 3.3亿 papers | `$AMINER_API_KEY` (60-day JWT) | **+7.1pp** for Chinese |
| 6 | **CNKI** | Chinese journals (CSSCI) | Optional cookie-based | baseline for Chinese |
| 7 | **PubMed** | Biomedical (35M+ citations) | Optional `$NCBI_API_KEY` (higher rate) | baseline for biomedical |

## Engine-specific notes

### AMiner (智谱学术) — Chinese paper advantage
- **Quota**: 3880 calls 一次性体验金 (one-time trial)
- **Strength**: 3.3亿 papers, strong Chinese coverage, citation tracking
- **Weakness**: 0% abstract coverage (JATS-style metadata only), bucketed citation field (low granularity)
- **Citation lift**: verified **+7.1pp** for Chinese economics queries (vs 5-engine baseline)
- **Renewal decision**: 30-day eval cron; renew if lift > +7pp

### Crossref
- **Coverage**: ~140M DOIs, broadest English coverage
- **API**: `api.crossref.org/works?query=...`
- **Free**: No key needed
- **Rate limit**: Polite pool (with `mailto=` param) gives higher rate

### OpenAlex
- **Coverage**: ~250M works (largest OA graph)
- **API**: `api.openalex.org/works?search=...`
- **API key**: `?api_key=...` query param (NOT Bearer header) — raises rate limit
- **Best for**: citation walks, OA detection

### Semantic Scholar
- **Coverage**: 200M+ papers, strong CS/AI
- **API**: `api.semanticscholar.org/graph/v1/paper/search`
- **API key**: `x-api-key` header
- **Best for**: tldr, citation context, recent ML/AI

### arXiv
- **Coverage**: 2.4M preprints, physics/math/CS
- **API**: `export.arxiv.org/api/query`
- **Free**: No key
- **Best for**: preprints, full abstract + categories

### CNKI
- **Coverage**: Chinese journals (CSSCI index)
- **Auth**: Cookie-based (requires browser session for full-text)
- **Status**: Optional 6th engine (off by default in some configs)

### PubMed
- **Coverage**: 36M biomedical citations
- **API**: NCBI E-utilities (`eutils.ncbi.nlm.nih.gov/entrez/eutils/`)
- **API key**: `?api_key=...` query param
- **Free**: No key needed
- **Best for**: biomedical search

## Search output schema

```json
{
  "results": [
    {
      "title": "...",
      "authors": [{"name": "..."}, ...],
      "year": 2024,
      "venue": "Nature",
      "doi": "10.1038/...",
      "abstract": "...",
      "tldr": "...",  // S2 only
      "open_access": true,  // OA detection
      "cites": 42,
      "engine": "semanticscholar"
    }
  ]
}
```

## DEDUP

When `--engine all` is used, results from all 7 engines are merged and
deduped by DOI. The first occurrence wins (priority order:
S2 → Crossref → OpenAlex → arXiv → PubMed → AMiner → CNKI based on
metadata quality).

## Engine choice tips

| Query | Best engine |
|---|---|
| Chinese economics / finance | `--engine aminer` (best cite lift) |
| English general / humanities | `--engine crossref` (broadest English) |
| AI / ML recent | `--engine semanticscholar` (best tldr) |
| Physics / math | `--engine arxiv` (only authoritative source) |
| Biomedical | `--engine pubmed` (authoritative) |
| Need all results | `--engine all` (parallel + dedup) |
| Test setup | `--engine openalex` (no key needed, fast) |

## Stats

- Single engine (best hit): 30-60% recall on random queries
- All 7 engines parallel: 80-90% recall with DEDUP
- Average result count: 20 per engine (limit=20 default)
