# Search engines

The default search runs six public sources and deduplicates results by DOI.
Use --engine with one engine or a comma-separated list when a focused search is
more useful.

| Engine | Best for | Configuration |
| --- | --- | --- |
| Crossref | Broad DOI and publisher metadata | No key required |
| OpenAlex | Scholarly graph and open-access metadata | Optional OPENALEX_API_KEY |
| arXiv | Physics, mathematics and CS preprints | No key required |
| AMiner | Chinese-language coverage and citation metadata | AMINER_API_KEY; Pro multi-word calls can incur a small fee |
| PubMed | Biomedical literature, abstracts and MeSH terms | Optional NCBI_API_KEY |
| ClinicalTrials.gov | Registered clinical trials rather than papers | No key required |

Use all for a broad first pass, aminer for Chinese research topics, pubmed for
biomedical questions, and clinicaltrials when the question is about registered
studies. CNKI and Semantic Scholar are retired in paper-agent and are rejected
by the CLI.
