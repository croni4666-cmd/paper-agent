# PDF fetch channels

Use pa fetch with --prefer to select a source, or auto to use the configured
cascade.

| Preference | Best for | Notes |
| --- | --- | ---|
| pmc | Papers in PubMed Central | May retrieve JATS XML. |
| pmc-pdf | PMC papers needing a PDF | Renders valid JATS XML using local Chromium. |
| biorxiv | bioRxiv and medRxiv | For 10.1101 DOI records. |
| core | Repository-indexed papers | CORE_API_KEY can raise service limits. |
| osf | OSF community preprints | For 10.31219/osf.io records. |
| chemrxiv | Chemistry preprints | Uses Open Engage metadata, then the official DOI-PDF URL. |
| arxiv | arXiv counterparts | Best when a DOI maps to an arXiv preprint. |
| unpaywall | Legal open copies | Uses registered email configuration. |
| annas and scihub | User-selected last-resort routes | Check local policy and applicable law. |

The auto cascade may also use internal redirect and browser-assisted fallback
steps. Those are implementation details, not stable user preferences.

## Download statistics

Run pa fetch-stats --json to review local, privacy-minimal source outcomes.
It records the final channel, success flag, timestamp and elapsed time. It does
not store titles, URLs, DOI values or API keys.
