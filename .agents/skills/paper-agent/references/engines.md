# Search Engines Reference (v3.9.22.0+)

paper-agent searches across **8 academic search engines**. Default is
`--engine all` which runs all 8 in parallel and dedupes by DOI.

> **v3.9.24.0 note**: `ClinicalTrials.gov` is the 8th engine (added v3.9.12.0).
> It returns trial registry records, NOT papers — different content type
> from the other 7 engines. Marked with `source: "clinicaltrials"`.llel and dedupes by DOI.

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

### PubMed (biomedical)

- **Coverage**: 36M biomedical citations
- **API**: NCBI E-utilities (`eutils.ncbi.nlm.nih.gov/entrez/eutils/`)
- **API key**: `?api_key=...` query param (free, raises rate from 3 to 10 RPS)
- **Free**: No key needed
- **Best for**: biomedical search
- **MeSH support (v3.9.24.0)**: pass full PubMed ESearch syntax to narrow results
- **v3.9.24.0 gotcha**: "Wilson Disease" is an ENTRY TERM, not a main MeSH heading.
  Use `"Hepatolenticular Degeneration"[MeSH Terms]` (the canonical MeSH term)
  for ~30× more relevant results than plain `"Wilson Disease"`.

#### PubMed MeSH query syntax

`pa search` passes the query directly to PubMed ESearch with URL encoding
(so brackets and quotes are preserved). This means **any PubMed query
syntax works**, including:

| Pattern | Use case |
| --- | --- |
| `"hepatolenticular degeneration"[MeSH Terms]` | Exact MeSH main heading (most precise) |
| `"Wilson disease"[Title/Abstract]` | Phrase in title or abstract |
| `"ATP7B"[Title/Abstract] AND human[Mesh]` | Boolean combination |
| `"Wilson disease"[MeSH Terms] OR "Wilson disease"[Title/Abstract]` | Fallback chain |
| `"2020"[PDAT] : "2024"[PDAT]` | Date range (alternative to `--year-min`/`--year-max`) |

⚠️ **Click quoting gotcha**: when calling from a shell, you MUST wrap
the query in single quotes to preserve brackets. Otherwise `click`
splits the query on spaces.

```bash
# CORRECT (single quotes around query):
pa search '"Hepatolenticular Degeneration"[MeSH Terms]' --engine pubmed

# WRONG (no quotes, click splits on spaces):
pa search "Hepatolenticular Degeneration"[MeSH Terms] --engine pubmed
# Error: Got unexpected extra arguments (Terms])
```

The skill's `scripts/search.py` wrapper accepts multi-word queries via
`nargs="+"` and re-joins with spaces, so the same query works from the
wrapper without shell-escape gymnastics:

```bash
# Works without shell-escape via the skill wrapper:
python scripts/search.py '"Hepatolenticular Degeneration"[MeSH Terms]' --engine pubmed
```

**Main term vs entry term — why "Wilson Disease" returns 0 in MeSH**:

MeSH (Medical Subject Headings) is structured like a thesaurus:
- Each disease has ONE main heading (the canonical term)
- Multiple "entry terms" (synonyms, lay terms) point to the main heading
- `[MeSH Terms]` field restricts search to **main headings only**

For Wilson disease:
- Main heading: `Hepatolenticular Degeneration` (MeSH ID D006527)
- Entry terms: "Wilson Disease", "Wilson's Disease", "Copper storage disease"

So `"Wilson Disease"[MeSH Terms]` returns 0 papers because the string
"Wilson Disease" is not a main heading. To use MeSH for Wilson disease,
you MUST use the canonical term. If you want to be safe, use OR
fallback:

```bash
pa search '"Hepatolenticular Degeneration"[MeSH Terms] OR "Wilson Disease"[Title/Abstract]'
```



### PubMed (v3.9.24.0 MeSH-aware)

| # | Engine | Best for | API key | Cite lift (vs no AMiner) |
|---|--------|----------|---------|--------------------------|
| 1 | **Crossref** | General academic, English | No | baseline |
| 2 | **OpenAlex** | Largest OA graph, citation walks | Optional `$OPENALEX_API_KEY` (higher rate) | baseline |
| 3 | **Semantic Scholar (S2)** | Recent CS / AI / ML papers | Optional `$S2_API_KEY` (higher rate) | baseline |
| 4 | **arXiv** | Physics, math, CS preprints | No | baseline |
| 5 | **AMiner (智谱学术)** | **Chinese papers**, 3.3亿 papers | `$AMINER_API_KEY` (60-day JWT) | **+7.1pp** for Chinese |
| 6 | **CNKI** | Chinese journals (CSSCI) | Optional cookie-based | baseline for Chinese |
| 7 | **PubMed** | Biomedical (36M+ citations) | Optional `$NCBI_API_KEY` (higher rate) | baseline for biomedical |
| 8 | **ClinicalTrials.gov** | Clinical trial registry (NOT papers) | No | n/a (trials) |

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
