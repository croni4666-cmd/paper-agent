# Europe PMC optional medical source

Public, keyless REST search is available through `--engine europepmc`.
The historical `all` source set and the default PubMed research workflow are
unchanged. Errors never silently switch sources. Explicit source selection:

```powershell
python -m pa_cli.cli search 'TITLE_ABS:menopause AND TITLE_ABS:sleep' --engine europepmc --limit 32
python -m pa_cli.research_search profile.json --engine europepmc --expansion none --strategy single --limit 32 --max-sources 0 --output results.json
python -m pa_cli.cli engine-probe sleep --engine europepmc --limit 1
```

The generic search command accepts Europe PMC syntax as supplied; it does not
translate PubMed field labels or Chinese. Structured research profiles compile
their declared terms into TITLE_ABS/TITLE blocks. This adapter supports only
`expansion=none`; synonym expansion is disabled explicitly in REST requests.
Core results preserve abstract text, PMID, PMCID, DOI, publication types, license
and eligible OA XML links. Links do not mean the article was downloaded or read.
Preprints remain identifiable through `upstream_source` and `pub_types`.

No account/key or payment setup is needed for this public route. Automated
retrieval must use official services and respect each article's license.
The adapter serializes request starts at least one second apart within a process,
does not retry, and exposes 429/failures/partial rows. This is local pacing,
not a guaranteed provider quota. Search limits are 1..1000 in one request;
research requests remain capped at 200. Opt-in exact-response caching separates
sources and never reuses partial/error responses. Cross-source PMID/DOI matches
merge into one record with `found_by` provenance; they are not independent studies.

Official documentation: https://europepmc.org/RestfulWebService
and https://europepmc.org/help .
