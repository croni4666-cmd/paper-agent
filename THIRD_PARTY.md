# Third-Party Notices

This document lists third-party software, services, data sources, and
other materials that `paper-agent` interacts with, depends on, or
incorporates. All third-party materials are used in accordance with
their respective licenses and terms of service.

## Search engine APIs (no install required, queried at runtime)

| Service                  | URL                                                    | Auth            | ToS / License      | Notes                                   |
|--------------------------|--------------------------------------------------------|-----------------|--------------------|-----------------------------------------|
| Crossref                 | https://api.crossref.org                               | none            | https://www.crossref.org/terms-and-conditions/ | Recommended by Crossref                 |
| OpenAlex                 | https://api.openalex.org                               | optional key    | https://openalex.org/terms                      | OA + concepts                            |
| arXiv                    | https://arxiv.org/abs/ + https://export.arxiv.org/pdf | none            | https://arxiv.org/help/api/tou                  | Preprints                                |
| Semantic Scholar         | https://api.semanticscholar.org                        | optional key    | https://www.semanticscholar.org/product/api     | Citation-rich                            |
| AMiner                   | https://datacenter.aminer.cn                           | required key    | https://www.aminer.org/                          | Chinese papers                           |
| CNKI                     | https://kns.cnki.net                                   | user cookies    | https://kns.cnki.net/kns8s/defaultreader/index   | User-must-supply cookies; no scraping    |
| PubMed (NCBI E-utilities)| https://eutils.ncbi.nlm.nih.gov                        | optional key    | https://www.ncbi.nlm.nih.gov/home/about/policies.shtml | 36M biomedical, no auth            |
| ClinicalTrials.gov       | https://clinicaltrials.gov                             | none            | https://clinicaltrials.gov/about-site/terms     | 500K trial registry                      |

**Note on CNKI**: paper-agent does NOT scrape CNKI. Users must supply
their own authenticated session cookies (4 cookies, 4-8h TTL). This
is to comply with CNKI's ToS which prohibits automated scraping.

## PDF full-text sources (cascade, used by `pa fetch`)

| Service              | URL pattern                    | Auth | License / ToS                                       | Notes                            |
|----------------------|--------------------------------|------|------------------------------------------------------|----------------------------------|
| Sci-Hub mirrors      | sci-hub.{al,ee,in,mk,ren,shop} | none | Legal status disputed in some jurisdictions          | Last-resort fallback only        |
| Anna's Archive       | annas-archive.{gs,org,se}      | none | https://annas-archive.org/about                      | Mirror aggregator, fallback      |
| Unpaywall            | https://api.unpaywall.org/v2   | email| https://unpaywall.org/legal                          | Requires verified email          |
| xueshu789            | http://120.53.241.46:5888 (example) | CNKI cookies | Reseller of CNKI access                     | Proxy discovered from redirect; no public API |

**Note on Sci-Hub**: Use is at user's own risk. Sci-Hub is a
last-resort channel when no legal source is available. paper-agent
implements it as a fallback only, not a default. AGPL-3.0 + No-AI-
Training does NOT endorse or license Sci-Hub content; users are
responsible for compliance with their local laws.

**Note on Anna's Archive**: Similar last-resort fallback. AGPL-3.0 +
No-AI-Training does not endorse or license content from shadow
libraries; users are responsible for compliance.

## Embedded / installed dependencies (PyPI)

This section tracks Python packages that the project depends on. Note:
the project has historically lacked a `requirements.txt` / `pyproject.toml`;
this is a known gap. A canonical dependency list is being prepared.

| Package                | Version (env)  | License       | Notes                                  |
|------------------------|----------------|---------------|----------------------------------------|
| `click`                | 8.4.2          | BSD-3-Clause  | CLI framework                          |
| `numpy`                | 1.26.4         | BSD-3-Clause  | Numerics                               |
| `urllib3`              | 2.7.0          | MIT           | HTTP client (stdlib in most uses)      |
| `requests`             | 2.33.1         | Apache-2.0    | HTTP client (some legacy paths)        |
| `requests-cache`       | 1.2.1          | BSD-2-Clause  | HTTP response cache                    |
| `charset-normalizer`   | 3.4.7          | MIT           | Encoding detection                     |
| `cryptography`         | 49.0.0         | Apache-2.0/BSD| TLS / hashing                          |
| `python-dotenv`        | 1.2.2          | BSD-3-Clause  | .env loader                            |
| `PyYAML`               | 6.0.3          | MIT           | YAML parser                            |
| `tiktoken`             | 0.13.0         | MIT           | OpenAI tokenizer (for LLM rerank only) |

**Note on optional engines**: The project also conditionally uses
`sentence-transformers`, `transformers`, `torch`, `openai`,
`langchain-openai`, `httpx`, `pandas`, `scikit-learn`, etc. — but
ONLY for the optional LLM rerank / cross-encoder path (`pa moe-router`
+ LTR features). These are NOT in the core search/fetch path. Users
who don't run `pa moe-router` don't need them.

**Note on `paper-search-mcp`**: The official MCP install path is
via the public `paper-search-mcp` PyPI package (MIT license,
22 free sources), installed by `pa mcp install` (`pa_cli/mcp_setup.py`).
This is a third-party package with its own license.

## Bench data (academic paper metadata)

The `bench/` directory contains academic paper metadata (DOIs, titles,
abstracts, journal names) used for offline evaluation. This data is:
- Sourced from public APIs (Crossref, OpenAlex, Semantic Scholar) under
  their respective ToS
- Used for non-commercial research evaluation only
- Subject to the No-AI-Training restriction (cannot be used to train
  models)

## Test fixtures

The `test_output/` directory contains test scripts, sample outputs,
and diagnostic logs. Some of these reference public APIs and external
services. All such data is used only for development and testing
purposes.

## Reporting concerns

If you believe a third-party notice is missing, inaccurate, or
incomplete, please open an issue at the upstream repository
(croni4666-cmd/paper-agent on GitHub).

## Version

- **v1.0** (2026-08-14): Initial third-party notice. Replaces ad-hoc
  mentions in CHANGELOG and source code comments.
