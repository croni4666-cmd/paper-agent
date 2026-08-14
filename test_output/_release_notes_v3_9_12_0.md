# v3.9.12.0 — ClinicalTrials.gov engine & 7 prior commits

**First public release since v3.9.11.3 (8/1/2026 docs sync).**

## Highlights

- **2 new search engines** (8 total, all opt-in/opt-out via `--engine {crossref,openalex,arxiv,semanticscholar,aminer,cnki,pubmed,clinicaltrials}`)
- **Global Sample Pool** — cross-Mavis-session SQLite, 13 CLI subcommands, 3 iron rules
- **arXiv prefer mode** — arXiv preprints fetchable as a first-class channel (was: 0 channels, now: works)
- **2 PATCH bugfixes** on PubMed year filter + fetch_doi arxiv routing
- **AGPL-3.0 + No-AI-Training** license (research-only)

---

## What's new

### Search engines (8 default, all `pa search --engine <name>`)

| # | Engine           | Domain                       | Auth   | Notes                                    |
|---|------------------|------------------------------|--------|------------------------------------------|
| 1 | crossref         | DOI-rich peer-reviewed       | none   | works                                    |
| 2 | openalex         | OA + concepts                | none   | works (concept filter has pre-existing bug) |
| 3 | arxiv            | physics/math/CS/bio preprints| none   | **NEW v3.9.11.6/7**: prefer mode + routing fix |
| 4 | semanticscholar  | citations + TLDR             | none   | works                                    |
| 5 | aminer           | Chinese papers               | key    | works (gated by `AMINER_API_KEY`)         |
| 6 | cnki             | Chinese (CNKI)               | cookies| works for Chinese journals               |
| 7 | **pubmed**       | 36M biomedical               | none   | **NEW v3.9.11.8/9**: NCBI E-utilities + year filter post-filter |
| 8 | **clinicaltrials** | 500K trial registry        | none   | **NEW v3.9.12.0**: returns `nct_id` (not DOI) |

**Opt-in (local install)**: `core` via `tools/install_core.py`

### Sample Pool (P3-26, v02, user-level)

**Location**: `~/.paper-agent/sample_pool/` (cross-platform, NOT in git, cross-Mavis-session)

- 13 CLI subcommands under `pa sample-pool`:
  `init / verify / list / get / stats / count / query / suggest / add / label / deprecate / export / audit`
- 3 iron rules (enforced at API + CLI):
  1. **user-only write**: add/label/deprecate require `--confirm-y` or interactive y/n
  2. **Mavis read-only**: list/get/stats/count/query/export for any session
  3. **training-isolated**: export writes to OUT path, never touches `pool.sqlite`
- Schema v2: `relevance_labels.label` nullable (incremental labeling)
- 5 gates (all LOCKED at n=0):
  - `moe_merge_n30` (n≥30 + aminer≥1)
  - `ltr_eval_n100` (n≥100)
  - `ltr_12feat_n200` (n≥200)
  - `holdout_eval_n200` (n≥200)
  - `mldl_rerank_n500` (n≥500)

### Other additions

- `pa fetch --prefer {arxiv|annas|cnki|scihub|auto}` (new, takes precedence over `--channels`)
- Fetch cascade reordered: arXiv → CNKI → annas → unpaywall → sci-hub
- PubMed abstract + MeSH: **deferred to v3.9.13+** (needs `efetch` XML, ~+150 LOC)
- PEDro: **deferred to v3.9.13+** (no public JSON API, only HTML form + CSRF + JS rendering)

---

## Bug fixes

- **v3.9.11.9**: PubMed year filter (esearch `pdat` online date vs `year` print field differ for epub-ahead-of-print papers). Post-filter by `year` after `esummary` in `pa_cli/search.py:search_pubmed()` (~10 LOC). Trade-off: count may drop below `limit` for some queries (correctness > completeness).
- **v3.9.11.7**: `fetch_doi` arxiv routing. Default `channels` list (with `scihub+unpaywall`) was routing arXiv DOIs to wrong channel. Fix: arxiv_id-first check, route to arxiv unconditionally if DOI is arXiv-shaped AND "arxiv" in channels.
- **v3.9.11.6**: `pa fetch --prefer` was unpaywall+sci-hub only; added arxiv, annas, cnki options.

---

## Docs

- **v3.9.11.5**: `pa fetch` proxy port doc fix (7897 → **10808**). All fetches require `$env:HTTPS_PROXY = http://127.0.0.1:10808` on networks behind GFW.
- **v3.9.12.0**: `--engine` help text now lists all 8 default engines.

---

## Verification

| Component          | Tests  | Status                |
|--------------------|--------|-----------------------|
| PubMed engine      | 4/4    | PASS                  |
| PubMed year filter | 8/8    | PASS (8 edge cases)   |
| ClinicalTrials.gov | 6/6    | PASS                  |
| arXiv fetch (4 input forms) | 4/4 | PASS (3.7 MB PDF)   |
| fetch prefer modes | 6/6    | PASS                  |
| sample pool 13 cmd | smoke  | PASS                  |
| legacy --channels  | smoke  | backward compat        |

2 independent verifier sessions (5/6 + 5/6 PASS) cross-checked v3.9.11.8 backward compat.

---

## Honest limitations

- **Pre-existing bugs (not v3.9.11.x related)**:
  - Unpaywall SSL EOF on `/v2/<doi>` (server-side, intermittently)
  - OpenAlex concept filter returns 0 results (pre-existing)
  - PubMed abstract + MeSH not yet exposed
  - PEDro no public JSON API
- **3-tier reporting**:
  - ✅ 4 new engines all work (verified end-to-end)
  - ⚠️ arXiv fetch and PubMed year filter have known caveats (in body)
  - ❌ PubMed abstract/MeSH + PEDro not in this release

---

## Upgrade

```bash
git pull origin main
pip install -e . --proxy http://127.0.0.1:10808
pa --version    # should print 3.9.12.0
```

No breaking changes. All v3.9.11.3 commands work unchanged.

---

## License

**AGPL-3.0 + No-AI-Training** — research use only, no derivative AI training, full source disclosure.

See `LICENSE` and `NO_AI_TRAINING.md` for full text.

---

## Links

- CHANGELOG: [`CHANGELOG.md`](./CHANGELOG.md)
- ROADMAP: [`ROADMAP.md`](./ROADMAP.md)
- Repo: `croni4666-cmd/paper-agent`
- Previous release: v3.9.11.3 (commit `20cf6da`, 2026-08-01 docs sync)
