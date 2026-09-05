# Search engines

Use `scripts/search.py --help` for supported engine choices and filters. The wrapper accepts the seven named engines below plus `all`; underlying CLI capabilities may differ.

| Engine | Useful for | Configuration |
| --- | --- | --- |
| Crossref | Broad DOI and publication metadata | No key setting required by the wrapper |
| OpenAlex | Works, open-access links, citation graphs | `OPENALEX_API_KEY` |
| Semantic Scholar | CS/AI papers, abstracts and TLDRs when available | `S2_API_KEY` |
| arXiv | Physics, mathematics and CS preprints | No key setting required by the wrapper |
| AMiner | Chinese and international academic literature | `AMINER_API_KEY` |
| CNKI | Chinese journals | May require a browser session; availability depends on configuration |
| PubMed | Biomedical literature | `NCBI_API_KEY` |

Check configured services with `scripts/keys.py list` or `check SERVICE_ID`. Authentication requirements and quotas can change; use the service's current response rather than historical counts.

## Query handling

- Quote the whole query as one shell argument, preserving any inner quotes and field tags.
- PubMed accepts ESearch syntax, including MeSH fields, title/abstract fields and Boolean operators. For example, pass `"ATP7B"[Title/Abstract] AND human[MeSH Terms]` as the query with `--engine pubmed`.
- For AMiner multi-word queries, inspect underlying `pa search --help` if the wrapper's defaults return poor results; advanced CLI flags are not automatically wrapper flags.
- `--limit` is per engine. Broad searches merge results; check DOI/title duplicates and missing abstracts before synthesis.
- If ClinicalTrials records appear in underlying CLI results, identify them as trial registrations rather than publications. The wrapper has no `--engine clinicaltrials` choice.
