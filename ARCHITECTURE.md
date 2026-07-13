# Paper-Agent Architecture (v3.9.1)

> **Last updated**: 2026-07-13 14:46 (post v3.9.1 patch — P0-4 + P1-5)
> **Code root**: `G:\minimax - workspace\Paper agent\`
> **Status**: 13 of 20 ROADMAP items shipped (8 done + 1 reverted + 4 deferred); 7 in backlog (1 P0/P1 + 4 P1 + 1 P1-research + 1 P2)

---

## 1. 5-layer system architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ L1  USER INTERFACE (CLI)                                                      │
│   pa search <query>              pa fetch <doi>               pa review <dir> │
│   pa review-topics <dir>         pa citations <doi>           pa prisma        │
│   pa mcp install                 pa keys {list,check,add,audit,remind}        │
│   pa cache {path,stats,clean,put,drop}                                       │
│   pa version                                                                       │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ L2  pa_cli/ PACKAGE — business logic + utilities                              │
│                                                                              │
│   Core retrieval:           |   Lit-review output:        |   Cross-cutting:  │
│   ─ search.py (5-engine     |   ─ review.py (corpus→MD)   |   ─ keys.py       │
│     SearchPool)             |   ─ topics.py (clustering)  |   ─ cache.py      │
│   ─ fetch.py (8-channel     |   ─ labels/ (pluggable      |   ─ bibtex.py     │
│     PDF cascade)            |     label generators)      |   ─ doi.py ◀ NEW │
│   ─ citations.py (forward/  |   ─ prisma.py (flow         |   ─ recency.py ◀ │
│     backward walk)          |     diagram)                |     NEW            │
│   ─ concepts.py (OpenAlex   |                            |   ─ mcp_setup.py   │
│     concept filter)         |                            |   ─ cli.py         │
│                                                                              │
│   v3.9.1 NEW: doi.py (P0-4) + recency.py (P1-5)                                 │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ L3  EXTERNAL APIs (5 search engines + 1 PDF provider)                        │
│                                                                              │
│   OpenAlex ──────► (free, key optional)         has institution data         │
│   Semantic Scholar ► (free, key optional)       has citation graph           │
│   CORE ──────────► (free, key required)         good for OA papers           │
│   Crossref ──────► (free, polite email)         has DOI metadata             │
│   arxiv ─────────► (free, no key)               preprints                    │
│   Unpaywall ─────► (free, email required)       OA PDF link resolver         │
│   (Sci-Hub) ─────► (optional, fallback only)    per v4 Cloudflare 5-min rule │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ L4  LOCAL STORAGE                                                              │
│                                                                              │
│   ~/.paper-agent/                                                            │
│     ├ cache/<doi_slug>.pdf        (PDFs, sha256 sidecar)                     │
│     ├ cache/<doi_slug>.meta.json  (channel, ts, size)                        │
│     ├ keys_registry.json          (key metadata, last_checked)               │
│     └ reports/                    (per-task MD reports if --open)            │
│                                                                              │
│   .env (gitignored)                  keys actually live here                 │
│   bench/v01/                        (benchmark-specific)                       │
│     ├ system_outputs/  qNNN.json     (snapshot — 25 queries × 30 candidates) │
│     ├ system_outputs_{bm25,biencoder,combined,prf,random}/  (v4 reranks)     │
│     ├ labels.json / labels_clean.json (ground truth, Mavis + 13 user fixes)  │
│     ├ spot_check/SPOT_CHECK_qNNN.md (user-annotated)                        │
│     └ reports/  v3_9_0_clean.md / .json (side-by-side metrics)              │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ L5  BENCHMARK LAYER (bench/v01/) — evaluation infrastructure                  │
│                                                                              │
│   snapshot.py  ──►  _v4_rerank.py  ──►  eval.py                              │
│   (fetch top-N     (5 conditions +     (recall@K,                              │
│    candidates)      recency filter)     precision@K,                            │
│                                                                  ndcg@K,      │
│   _gen_labeling_views.py                _build_clean_labels.py                map@K)     │
│   (markdown for                         (parse user spot-check,                              │
│    Mavis labels)                          override + audit log)                              │
│                                                                              │
│   _gen_spot_check.py  ──►  user fills in  ──►  _build_clean_labels.py         │
│   (priority order,                                                    │        │
│    navigation index)                                                   │        │
│                                                                          │        │
│   _v4_run_all.py  ──►  6 invariant checks + 3-tier audit + JSON+MD reports       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. v4 rerank stack (v3.9.0) — the flagship feature

```
INPUT:  system_outputs/qNNN.json  (30 candidates, Mavis's pre-rerank order)
        OR
        pa search <query>  →  30 candidates via SearchPool

                          ┌──────────────────────┐
                          │  _v4_rerank.py        │
                          │  (5 conditions)      │
                          └──────────────────────┘
                                       │
        ┌──────────┬──────────┬─────────┴─────────┬──────────┐
        ▼          ▼          ▼                   ▼          ▼
     bm25     biencoder   combined           prf (Roc-  random
     (lexical) (semantic)  (0.5*BM25 +       chio BM25,  (ablation
                (all-Mini- 0.5*BE)            top-5→8     baseline)
                 LM-L6-v2)                   terms)
        │          │          │                   │          │
        └──────────┴──────────┴─────────┬─────────┴──────────┘
                                        │
                                        ▼
                          ┌──────────────────────┐
                          │  pa_cli/recency.py   │  ◀── NEW v3.9.1
                          │  (--recency-mode     │      [P1-5]
                          │   {off,strict,       │
                          │    moderate})        │
                          └──────────────────────┘
                                        │
        ┌──────────┬──────────┬──────────┴───────────┬──────────┐
        ▼          ▼          ▼                      ▼          ▼
   system_       system_     system_              system_    system_
   outputs_      outputs_    outputs_             outputs_   outputs_
   bm25/         biencoder/  combined/            prf/       random/
   qNNN.json     qNNN.json   qNNN.json            qNNN.json  qNNN.json

                          ┌──────────────────────┐
                          │  eval.py             │
                          │  + labels_clean.json │
                          │  = recall@K, prec@K, │
                          │    ndcg@K, map@K,    │
                          │    success@K         │
                          └──────────────────────┘
                                        │
                                        ▼
                          ┌──────────────────────┐
                          │  reports/v3_9_0_clean│
                          │  .md / .json         │
                          │  + 3-tier audit      │
                          └──────────────────────┘
```

**5 conditions in detail**:

| Condition | Algorithm | What it measures |
|---|---|---|
| `bm25` | BM25 (k1=1.5, b=0.75) on title + abstract | Lexical overlap |
| `biencoder` | `all-MiniLM-L6-v2` cosine on (query, title+abstract) | Semantic similarity |
| `combined` | 0.5 × norm(bm25) + 0.5 × norm(biencoder) | Both, equally weighted |
| `prf` | Pseudo-relevance feedback: take top-5 by BM25, expand query with their top-8 terms, re-BM25 | Term expansion (current loser) |
| `random` | random.random() | Ablation |

**v3.9.1 added** ([P1-5] recency filter):
- `--recency-mode off` (default, backward compatible)
- `--recency-mode strict`: 0.1x for ancient + low-cite papers
- `--recency-mode moderate`: 0.5x for ancient + low-cite papers
- Field-stale warning: stderr message if `median(candidate_year) < now - 5`

---

## 3. v3.9.1 NEW modules in detail

### `pa_cli/doi.py` (P0-4) — DOI canonicalization

```
Raw DOI from OpenAlex / Crossref / S2 / CORE
              │
              ▼
   canonicalize_doi(doi)
              │
              ├─► KNOWN_TYPO_FIXES lookup (5 known: 10.3380 → 10.3389)
              ├─► strip whitespace
              ├─► strip uppercase J. (10.1016/J.CHIECO → 10.1016/j.chieco)
              └─► lowercase prefix + journal part
              │
              ▼
   Canonical DOI:  10.1016/j.chieco.2015.12.009
```

**Why it matters**:
- 19 unique DOIs renamed in `labels.json` (748 → 741 keys after dedup)
- 102 DOIs canonicalized across 150 candidate files
- 7 case-variant duplicates collapsed (e.g. q014 #15/#17, #18/#19, #26/#27)
- 5 typo'd Frontiers DOIs fixed (10.3380 → 10.3389)

**Used by**:
- `bench/v01/_build_clean_labels.py` (after user spot-check, before saving labels)
- `bench/v01/_migrate_doi_canonical.py` (one-time migration of labels + overrides)
- `bench/v01/_migrate_candidate_dois.py` (one-time migration of 6 system_outputs subdirs)
- Future: should be wired into `pa_cli/snapshot.py` to write canonical DOIs at fetch time (TODO)

### `pa_cli/recency.py` (P1-5) — Recency + citation threshold filter

```
candidate {year, citation_count, bi_encoder_score}
              │
              ▼
   recency_factor(year, cite, bi, query_citation_stats)
              │
              ├─► age = now - year
              ├─► query_stats = {mean, std} of citation_count over candidates
              ├─► threshold_old = mean + 2*std
              ├─► threshold_ancient = mean + 2.5*std
              │
              ▼
   if bi > 0.7 AND cite > threshold_old:  return 1.0  (rescued)
   elif age > 20 AND cite < threshold_ancient:
       return 0.1  (strict) or 0.5  (moderate)  (ancient)
   elif age > 10 AND cite < threshold_old:
       return 0.5  (old)
   else:  return 1.0  (fresh)
              │
              ▼
   multiplier applied to v4_score in rerank pipeline
```

**Field-stale warning** (independent of downweight):
```
[recency warning] field_may_be_stale: median candidate year = 2013 (13 years ago).
User rule: if many cited papers are old, the field may be outdated.
Consider narrowing query or adding 'since 2020' filter.
```
Fires for 16 of 25 queries in our benchmark. The actionable output.

---

## 4. Data flow examples

### 4.1 `pa search "AI in higher education" --top-n 30`

```
pa search "AI in higher education" --top-n 30
    │
    ▼
pa_cli/cli.py → pa_cli/search.py
    │
    ├─► SearchPool.fetch_all(query)
    │     ├─► openalex.searcher.search(query, n=10)  [OpenAlex API]
    │     ├─► s2.searcher.search(query, n=10)        [S2 API]
    │     ├─► core.searcher.search(query, n=10)       [CORE API]
    │     ├─► crossref.searcher.search(query, n=10)   [Crossref API]
    │     └─► arxiv.searcher.search(query, n=10)      [arXiv API]
    │
    ├─► dedup by DOI (cross-source)
    ├─► enrich with citation_count + venue + year (OpenAlex)
    │
    ▼
Output: list[dict] with rank, doi, title, abstract, year, venue, citation_count
```

### 4.2 `pa review-topics <corpus_dir>` (v3.8.0+)

```
pa review-topics G:\MyPapers\
    │
    ▼
pa_cli/topics.py
    │
    ├─► build_corpus_index(corpus_dir) — walks .pdf/.md/.txt
    │     ├─► extract_text() — PDF via PyMuPDF, MD/TXT via UTF-8
    │     └─► build {filename: {doi, title, year, venue, cited_by, concepts}}
    │
    ├─► cluster_topics(method="auto")
    │     ├─► if n ≥ 5: BERTopic (UMAP → HDBSCAN → c-TF-IDF → KeyBERTInspired)
    │     │   └─► 60s timeout on sentence-transformers download
    │     └─► if n < 5 or BERTopic fails: hand-roll (TF-IDF + cosine + Agglom)
    │
    ├─► LabelGenerator.generate(topics=...)
    │     ├─► CTFIDFLabelGenerator (default)
    │     ├─► HandrollLabelGenerator (fallback)
    │     └─► CustomLabelGenerator (post-processor for --custom-labels)
    │
    ▼
Output: topics.json with cluster + label + keywords + filenames
```

### 4.3 Bench pipeline (v3.9.0+)

```
1. snapshot.py
   bench/v01/queries.json (25 queries)
   → pa search (system) → top-30 candidates each
   → system_outputs/qNNN.json (25 files)

2. _v4_rerank.py --condition X
   system_outputs/qNNN.json
   → 5-condition rerank (BM25 / biencoder / combined / prf / random)
   → system_outputs_<X>/qNNN.json

3. eval.py --labels labels_clean.json
   system_outputs_<X>/qNNN.json
   → recall@K / precision@K / ndcg@K / map@K / success@K
   → reports/v3_9_0_<X>.json (per-condition aggregate)

4. _v4_run_all.py
   → runs all conditions + 6 invariant checks + 3-tier audit
   → reports/v3_9_0_clean.md (side-by-side)
```

---

## 5. Module responsibilities (pa_cli/)

| Module | LOC (approx) | Responsibility | New in v3.9.1? |
|---|---:|---|---|
| `__init__.py` | 24 | version, public API | |
| `__main__.py` | small | `python -m pa_cli` entry | |
| `cli.py` | 800+ | Click subcommand definitions | |
| `search.py` | 600+ | 5-engine SearchPool | |
| `fetch.py` | 800+ | 8-channel PDF cascade (per v4 5-min Cloudflare rule) | |
| `review.py` | 400+ | corpus → MD synthesis | |
| `topics.py` | 900+ | topic clustering (BERTopic + handroll + pluggable labels) | |
| `labels/` | 340 | pluggable label generator ABC + 4 implementations | |
| `citations.py` | 200+ | forward/backward citation walk | |
| `concepts.py` | 200+ | OpenAlex concept filter | |
| `prisma.py` | 130 | PRISMA flow diagram | |
| `bibtex.py` | 220 | BibTeX export | |
| `cache.py` | 210 | PDF cache layer | |
| `keys.py` | 400+ | API key registry + daily reminder | |
| `mcp_setup.py` | 100+ | MCP install glue for public `paper-search-mcp` | |
| `doi.py` | 165 | **DOI canonicalization** | ✅ v3.9.1 |
| `recency.py` | 190 | **Recency + citation threshold filter** | ✅ v3.9.1 |
| **Total** | **~6,000 LOC** | | |

---

## 6. Versioned history

| Version | Date | What |
|---|---|---|
| v3.0.0 | 2026-06-25 | Initial 4-searcher pool (no CORE) |
| v3.0.1 | 2026-07-02 | 4 searcher bug fixes |
| v3.1.0 | 2026-07-03 | + CORE searcher, 5-engine pool, OpenAlex key |
| v3.2.x | 2026-07-04 | v4 principle (Cloudflare 5-min rule) + bibtex [P0-1] |
| v3.4.0 | 2026-07-04 | [P0-1] Bibtex export |
| v3.5.0 | 2026-07-04 | [P0-2] Local cache |
| v3.5.1 | 2026-07-04 | [P0-3] REVERTED (MCP) + [P1-1] Citation walk |
| v3.6.0 | 2026-07-04 | [P1-2] OpenAlex concepts |
| v3.7.0 | 2026-07-04 | [P1-3] PRISMA diagram |
| v3.7.1 | 2026-07-04 | Cleanup (deprecate P2-1/2/3) |
| v3.8.0 | 2026-07-05 | [P1-4] Topic clustering |
| v3.8.1 | 2026-07-05 | [P1-4 polish] Pluggable labels |
| v3.8.2 | 2026-07-05 | [P1-4 polish-2] Heuristics + real-corpus test |
| v3.8.3 | 2026-07-05 | [P1-4 polish-3] Close v3.8.1 unverified gaps |
| **v3.9.0** | **2026-07-12** | **v4 multi-condition rerank stack (5 conditions + 1 ablation)** |
| **v3.9.1** | **2026-07-13** | **[P0-4] DOI canonicalization + [P1-5] recency filter** |

---

## 7. Future architecture (planned [P1-6..P1-10], awaiting user input)

```
                     L2 pa_cli/  (future additions)
                              │
                              ├── decompose.py        ◀── [P1-6] Sub-topic decomposition
                              │     └─► agriculture → {ag_econ, climate_adapt, supply_chain, ...}
                              │
                              ├── institutions.py    ◀── [P1-7] Institutional credibility tiers
                              │     └─► IMF/WB/Oxford/MaxPlanck → 1.3x boost
                              │
                              ├── exclusions.py       ◀── [P1-8] China political-institution blocklist
                              │     └─► 国际关系研究院 + 马克思主义学院
                              │
                              ├── geography.py        ◀── [P1-9] Country extraction (ISO 3166-1)
                              │     └─► "OECD" / "Sub-Saharan Africa" → boost
                              │
                              └── falsifiability.py   ◀── [P1-10] 5-dimension score
                                    └─► hypothesis / variable / prediction / boundary / novelty

              L2 ───┐
                    ▼
         Each filter outputs a multiplier ∈ [0.1, 1.5]
              │
              ▼
         final_score = v4_score × recency × institution × geo × (subtopic_weight)
              │
              ▼
         Output: top-K candidates with all factors applied
```

**Architecture principle**: All filters are **multiplicative** on the rerank score. Labels stay ground-truth accurate; filters affect ranking, not relevance. This is the cleanest decomposition because:
- User can opt in/out of each filter independently
- Labels (researcher ground truth) are decoupled from filters (user preferences)
- Easy to A/B test filter impact (turn off all, turn on one, etc.)

---

## 8. Personal-hobbyist ceiling (Global Rule)

Every new module passes 5 checks before shipping:
1. **Runs for $0** — no paid infra, no hosted LLM
2. **No hosted service** — all local computation
3. **Maintenance ≤ a few hours/month** — single hobbyist
4. **No "must publish" obligation** — no Chrome Web Store, no SaaS
5. **Free-tier API degrades gracefully** — tool still works when third-party free tier removed

Per discipline: any item failing the 5 checks goes back to `proposed` with redesign notes, or `deprecated` with reason.

---

**End of architecture.md** (2026-07-13 14:46)
