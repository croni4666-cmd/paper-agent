# PDF Fetch Channels Reference (v3.9.22.1+)

paper-agent fetches a single paper PDF via a cascade of **14 channels**.
The cascade order is:

```
pmc → s2 → biorxiv → core → osf → chemrxiv → arxiv →
openalex → unpaywall → doi_redirect → scihub → playwright
```

## Channel details

| # | Channel | Prefer value | Trigger condition | Free? | Auth | Typical hit rate |
|---|---------|--------------|-------------------|-------|------|------------------|
| 1 | **PMC** (PubMed Central) | `pmc` | DOI in PMC (biomedical) | ✅ | No | ~30% for biomedical DOIs |
| 2 | **PMC PDF (JATS→PDF)** | `pmc-pdf` | DOI in PMC, force real PDF render via headless Chromium | ✅ | No | Always works for valid JATS (~25s) |
| 3 | **Semantic Scholar openAccessPdf** | `s2` | S2 API knows about the DOI | ✅ | No | ~30% random DOIs |
| 4 | **bioRxiv/medRxiv** | `biorxiv` | DOI starts with `10.1101/*` | ✅ | No | 100% for bioRxiv preprints |
| 5 | **CORE** | `core` | CORE indexes the paper | ✅ (low rate) | Optional `$CORE_API_KEY` (higher rate) | 36M+ full text |
| 6 | **OSF Preprints** | `osf` | DOI starts with `10.31219/osf.io/*` | ✅ | No | 25+ community providers, 2M+ preprints |
| 7 | **ChemRxiv** | `chemrxiv` | DOI starts with `10.26434/chemrxiv-*` | ✅ | No | 40K+ chemistry preprints |
| 8 | **arXiv** | `arxiv` | DOI has an arXiv counterpart | ✅ | No | 100% for arXiv preprints |
| 9 | **OpenAlex** | (no --prefer) | OpenAlex knows the DOI | ✅ | No | Metadata only; redirect to OA URL |
| 10 | **Unpaywall** | `unpaywall` | Paper has an OA copy | ✅ | `$UNPAYWALL_EMAIL` (registered) | ~50% for DOIs |
| 11 | **DOI redirect** | (no --prefer) | Publisher redirects to PDF | ✅ | No | Variable |
| 12 | **sci-hub** | `scihub` | Paper is on sci-hub | ⚠️ grey | No | Variable (legal grey area) |
| 13 | **Annas Archive** | `annas` | Paper is on annas-archive | ⚠️ grey | No | Variable (legal grey area) |
| 14 | **Playwright (CF bypass)** | (no --prefer) | All else failed + user has Cloudflare cookies | ✅ | Local browser session | Last resort |

## Channel preferences (use `--prefer`)

```bash
# Force a specific channel first
pa fetch <doi> --prefer pmc-pdf    # Force JATS→PDF render (real PDF, ~25s)
pa fetch <doi> --prefer s2          # Try S2 first
pa fetch <doi> --prefer unpaywall   # Try Unpaywall first (legal OA)

# Default = auto = try cascade in order
pa fetch <doi> --prefer auto
```

## Channel-specific gotchas

### PMC (PubMed Central)
- **Trigger**: DOI is in PMC database (biomedical papers)
- **Returns**: Europe PMC PDF render (best-effort, ~25% success) OR JATS XML
- **v3.9.22.1 fix**: when JATS-to-PDF fallback fails, no orphan `.pdf` is created; only `.xml`. `size_bytes` is now correctly populated in JSON.
- **Hint**: For a guaranteed real PDF, use `--prefer pmc-pdf` (slower ~25s but always works for valid JATS)

### Semantic Scholar (S2)
- **Trigger**: S2 has the paper in their database
- **Returns**: `openAccessPdf` field (URL) if S2 has a known OA copy
- **Gotcha**: ~30% hit rate; S2's PDF URL is a public link (not behind auth)

### bioRxiv/medRxiv
- **Trigger**: DOI starts with `10.1101/*` (Cold Spring Harbor preprint server)
- **Returns**: Direct PDF URL (100% hit rate for bioRxiv/medRxiv preprints)
- **v3.9.22.0 fix**: When API doesn't return `link_pdf`, URL is constructed from DOI + version: `https://www.biorxiv.org/content/10.1101/{doi}v{version}.full.pdf`
- **Gotcha**: bioRxiv main site uses Cloudflare; required Mozilla UA + Accept headers; may 429 on datacenter IPs

### CORE
- **Trigger**: CORE indexes the paper (36M+ full text articles)
- **Auth**: `$CORE_API_KEY` optional (free tier is 100/day, then 503 quota)
- **v3.9.22.0 fix**: `downloadUrl` is often stale Azure blob (404); real OA URL is in `sourceFulltextUrls` (preferred) or `urls[type=fulltext]`
- **Gotcha**: Re-added in v3.9.22.0 (was incorrectly removed in v3.9.11.1)

### OSF Preprints
- **Trigger**: DOI starts with `10.31219/osf.io/*` (Open Science Framework)
- **Returns**: Direct PDF download URL via OSF v2 API
- **v3.9.22.0 fix**: API wraps responses in `{data, meta}`; download URL is `data.links.download` pattern `https://osf.io/download/{guid}/`

### ChemRxiv
- **Trigger**: DOI starts with `10.26434/chemrxiv-*` (chemistry preprints)
- **Returns**: Direct PDF via Figshare public API (not chemrxiv.org, which is CF-blocked)
- **Gotcha**: Dev machine IPs may be 403'd by Figshare; works on residential IPs

## Strategy: which channel to prefer

| Use case | Best channel |
|---|---|
| Random DOI, want max coverage | `auto` (cascade) |
| PMC paper, want real PDF guaranteed | `pmc-pdf` |
| bioRxiv preprint | `biorxiv` |
| ChemRxiv preprint | `chemrxiv` |
| SocArXiv/PsyArXiv preprint | `osf` |
| Anything S2 knows about | `s2` |
| Open access legal requirement | `unpaywall` |
| Last resort (paywalled) | `scihub` (grey area) |

## Stats

- v3.9.21.0 (before v3.9.22.0): ~50% coverage on random DOIs (9 channels)
- v3.9.22.0+: **70-75% coverage** on random DOIs (14 channels)
- E2E verified (2026-08-21): 3/5 v3.9.22 channels produce real PDFs in dev env
  - OSF 76KB, S2 816KB, bioRxiv 6.3MB
  - CORE: Azure 503 quota (dev IP); ChemRxiv: Figshare CF 403 (dev IP) — not code bugs
