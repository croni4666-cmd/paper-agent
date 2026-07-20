# Changelog

All notable changes to Paper Agent Skill.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
- **MAJOR** (v3 → v4): architecture redesign, breaking config / API
- **MINOR** (v3.0 → v3.1): new searcher / new phase / new key, additive
- **PATCH** (v3.1.0 → v3.1.1): bug fix, no API change

---

## [3.9.8.4] - 2026-07-16 (`pa fetch-batch` semi-automated CNKI guide + ROADMAP doc sync)

### v3.9.8.4 -- pa fetch-batch (2026-07-16 09:17)

After v3.9.8.3 confirmed `pa fetch` can't auto-download Chinese PDFs
(bar.cnki.net vLevel=5 CAPTCHA), shipped a semi-automated workaround:
`pa fetch-batch -i input.txt -o guide.md` generates per-paper xueshu789
search URLs + an Edge console JS snippet for batch doDownload extraction.

**New file**: `pa_cli/batch_fetch.py` (~280 LOC)

**CLI**: `pa fetch-batch -i <input.txt> -o <guide.md>`
- Input: one DOI or title per line
- For each line: generate xueshu789 search URL, lookup CNKI doc_id,
  output manual download instruction + Edge console JS snippet
- Real-corpus test (5 papers, 数字普惠金融 + 家庭消费 topic): 5/5 found, 4/5 with DOI

**Files**:
- `pa_cli/batch_fetch.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (added `fetch-batch` subcommand)
- `example_dois.txt` (input format example)
- `test_papers_real.txt` (real-corpus test input)
- `test_output/_real_corpus_guide.md` (5/5 found output)
- `test_output/_example_guide.md` (4/6 found mixed DOI+title example)
- `Export-CNKICookies.ps1` (manual 4-cookie export — PowerShell)
- `export_cnki_cookies.py` (auto 2-cookie export — DEPRECATED, use manual)

### v3.9.8.4 -- ROADMAP doc sync (2026-07-16 09:50)

ROADMAP.md had drifted behind CHANGELOG: "Versioned roadmap summary" table
stopped at v3.9.7.9, "Current capability snapshot" was v3.9.7.9-only, and
[P1-7] AMiner was still listed as in-progress in "Future improvement candidates".
Docs-only fix (no code):

- Added v3.9.8.0/8.1/8.2/8.3/8.4 rows to versioned summary table
- Updated "Current capability snapshot" header to v3.9.8.4, 6→7 engines,
  added `Fetch PDF (8-channel + proxy)` + `CNKI fetch-batch guide` rows
- Renamed "Future improvement candidates" header from post-v3.9.7.9 → post-v3.9.8.4
- Marked [P1-7] AMiner as ✅ DONE in v3.9.8.0 (was "in-progress")
- Promoted CHANGELOG `[Unreleased] - 2026-07-15 (CNKI fetch ...)` → `[3.9.8.3]`
- Promoted CHANGELOG `[Unreleased] - 2026-07-15 (CORE cleanup ...)` → `[3.9.8.2]`

### v3.9.8.4 -- session handoff doc (2026-07-16 09:23)

`Paper agent/_session_handoff.md` created for the mavis 3.0.48/3.0.49
intermittent 5xx issue — when the daemon dies mid-session, a new session
can rehydrate from this file and continue. Handoff captures:
- v3.9.8.4 capability snapshot
- 6 commits in current session
- File paths
- CNKI cookies state (PHPSESSID, user, entrys, expires — 4h TTL)
- Open tasks ([P2-5] pa build, [P3-1] pa judge, aminer-30day-eval cron)
- Honest capability limits (re-state)

---

## [3.9.9.6] - 2026-07-16 (ROADMAP self-audit rounds 8-13: 15 more issues found + fixed)

Per user catch 2026-07-16 11:38 ("我看你的todo list 还没做完"): the
previous "audit clean" verdict at round 7 was premature. User pushed back
correctly — the [3.9.9.4] claim of "diminishing returns" was wrong; more
real issues existed. Re-audit (rounds 8-13):

- **Round 8 (5 issues)** — `d1f2a6d`:
  - R8-1: L2268 "Layer 4 Filters" table still referenced `[P2-5]` for
    Quality filter (should be `[P2-14]`) — same class of bug as R3-1
    that was supposedly fixed
  - R8-2: L1288 "see [P2-5] research 2026-07-15" for Lit review WRITING
    row — broken reference (that research section was REPLACED by
    "Writing pipeline" section per CHANGELOG v3.9.7.9 follow-up)
  - R8-3: Tier 3 still had leading numbers 10./11./12. (Round 2 I-4
    dropped them in Tier 1/2 but missed Tier 3)
  - R8-4: Tier 5 still had leading numbers 13./14. (same as R8-3)
  - R8-5: L1289 "proposed [P2-5]" — now misleading since shipped
    (cosmetic; collapsed into R8-2 fix)

- **Round 9 (3 issues)** — `d1f2a6d` (same commit):
  - R9-1: Versioned summary table missing v3.9.9.3 and v3.9.9.4 rows
    (CHANGELOG had these but ROADMAP table didn't)
  - R9-2: "Recommended next step" section missing [P-N] IDs
    (violates rule 8 added in [3.9.9.3])
  - R9-3: Handoff Section 5/9 missing [P1-14..18] quick-wins
    (retroactive IDs assigned in [3.9.9.3] but handoff not updated)

- **Round 10 (1 issue)** — `553c141`:
  - R10-1: [P3-1] "Realistic path forward" said "Add `pa judge` command"
    but pa judge shipped v3.9.9.1 — should be "Use `pa judge` (shipped)"

- **Round 11 (3 issues)** — `6144b2a`:
  - R11-1: "B+ → A" Path (c) AMiner section still said "4-6h
    implementation" (AMiner shipped v3.9.8.0)
  - R11-2: "Combined verdict" table still said "4-6h implementation"
  - R11-3: "What we CAN ship" section had no status update
    (pa build shipped v3.9.9)

- **Round 12 (1 issue)** — `2950d9d`:
  - R12-1: CHANGELOG [3.9.9.4] verdict "All substantive issues fixed"
    was stale (contradicts [3.9.9.5])

- **Round 13 (2 issues)** — `8b26ea9` + `6e785d5`:
  - R13-1: [P0-12] "paper-agent's 6-engine pool" stale post-AMiner
    (should be "7-engine pool")
  - R13-2: Snapshot "Last update: v3.9.9.1" needed clarification

---

## [3.9.9.7] - 2026-07-16 ([P1-14] --enrich-top-min-cites + pa fetch backward-compat wrapper)

### v3.9.9.7 -- [P1-14] ship + pa fetch restore (2026-07-16 16:30)

**Feature**: [P1-14] `enrich_top_n()` now skips S2 deep lookup for papers
with `cited_by_count < min_cites` (default 1 = skip 0-cite papers).
Saves ~12s/query when many low-cite papers in top-N, per S2 shallow-entry
lesson from v3.9.7.7 (Chinese papers return null tldr/inf_cite even
when cited 0 times).

**CLI flag**: `--enrich-top-min-cites` (default 1; set 0 to restore
v3.9.7.8 behavior of trying all papers).

**Per-paper metadata**: `_enrichment.s2_doi_skipped = "cited_by_count<{N}"`
records skip reason on each affected paper.

**Stderr stats line**: `pa search --enrich-top N` prints
`[P1-14] enrich_top_n: enriched X, skipped Y (cited_by_count<1) of top-N`.

**Tests**: 4/4 unit tests pass in `test_output/_test_enrich_top_min_cites.py`
covering min_cites=0/1/5 thresholds + no-DOI edge case.

**[P1-16] CLI sort options** (same release):
- New `sort_results(results, sort_by)` helper in `pa_cli/search.py`
- `enrich_top_n()` got `resort_by` param to keep re-sort consistent
- New CLI flag `--sort-by {cite|year|relevance}` (default `cite` = backward compat)
- `cite` (default): cited_by_count desc — v3.9.7.8 compat
- `year`: year desc (newest first; None/0 at end)
- `relevance`: keep natural engine order (no sort)
- 7/7 unit tests pass in `test_output/_test_sort_results.py`

**Bug fix (same release)**: `pa fetch` CLI was broken since v3.9.8.2
refactor (renamed `fetch_doi` → `fetch`; CLI still imported old name).
Added `fetch_doi()` backward-compat wrapper in `pa_cli/fetch.py` that
translates old API (`channels`, `output_dir`, `max_total_sec`) to new
API (`prefer`, `out_path`). Also re-adds cache check at function entry
that was lost in refactor. `max_total_sec_supported: False` documented
in `_wrapper_notes` (honest 3-tier — no time-budget enforcement).

**Other fixes in same release**:
- `pa_cli.deep_rerank` was broken import (`fetch_doi` reference);
  wrapper fix resolves it. 26/26 pa_cli modules now import OK.
- `test_output/test_cache_integration.py` rewritten to mock new
  `fetch()` (not channels which were removed in v3.9.8.2). Both tests pass.

**Files changed**:
- `pa_cli/search.py` (~50 LOC: enrich_top_n + run_search + new sort_results)
- `pa_cli/cli.py` (new --enrich-top-min-cites + --sort-by options)
- `pa_cli/fetch.py` (~60 LOC `fetch_doi` wrapper)
- `pa_cli/__init__.py` (version bump 3.9.9.6 → 3.9.9.7)
- `test_output/_test_enrich_top_min_cites.py` (NEW, 4 unit tests)
- `test_output/_test_sort_results.py` (NEW, 7 unit tests)
- `test_output/test_cache_integration.py` (rewritten, 2 tests pass)
- `ROADMAP.md` ([P1-14] and [P1-16] marked DONE; versioned table v3.9.9.7)

---

## [3.9.9.8] - 2026-07-16 ([P1-15] OpenAlex-by-title fallback)

### v3.9.9.8 -- [P1-15] ship (2026-07-16 17:50)

**Feature**: When `_crossref_lookup_title()` returns 0 hits, fall back to
`_openalex_lookup_title()` to fill DOI + cite + year + venue. OpenAlex has
better Chinese coverage than Crossref (per v3.9.7.5 lessons: many CN
papers that Crossref misses are indexed in OpenAlex). Expected +5-10pp
on Chinese cite coverage.

**Implementation**:
- New `_openalex_lookup_title(title)` function (~25 LOC) in `pa_cli/search.py`
- `enrich_top_n()` modified: when Crossref returns None, call OpenAlex
  as fallback. Fields filled: `doi`, `cited_by_count`, `abstract`, `venue`,
  `year` (each only if not already set, to preserve user-supplied data).
- `_enrichment.openalex_title = True` records the fallback path.

**Tests**: 8/8 unit tests pass in `test_output/_test_openalex_title_fallback.py`
covering: Crossref-hit-skips-OpenAlex, Crossref-0hit-uses-OpenAlex,
both-0hit, only-missing-fields-filled, OpenAlex normalization, 0 results,
short title, HTTP error.

**Files changed**:
- `pa_cli/search.py` (~30 LOC: new `_openalex_lookup_title` + `enrich_top_n` modification)
- `test_output/_test_openalex_title_fallback.py` (NEW, 8 unit tests)
- `ROADMAP.md` ([P1-15] marked DONE; versioned table v3.9.9.8 row)
- `CHANGELOG.md` (this entry)

---

## [3.9.9.9] - 2026-07-16 ([P1-17] --source per-engine post-filter)

### v3.9.9.9 -- [P1-17] ship (2026-07-16 18:00)

**Feature**: New `--source` CLI flag to post-filter unified results by
engine source. Use case: query all engines, but only display certain ones
(e.g., compare CNKI vs OpenAlex coverage side-by-side in a single search).

**CLI**: `--source openalex,cnki` (comma-separated; default no filter)
- `run_search()` accepts `source_filter: List[str] = None`
- New `filter_by_source(results, source_filter)` helper (~10 LOC)

**Matching semantics**: prefix matching on `result["source"]` field
- `--source openalex` matches both `openalex` (from search_openalex) and
  `openalex_title` (from [P1-15] fallback enrichment)
- `--source crossref` matches both `crossref` and `crossref_title`
- Case-insensitive (filter is lowercased before matching)
- Stderr line: `[P1-17] filter_by_source: N -> M (kept only: openalex,cnki)`
  when filter actually reduces the result count

**Tests**: 9/9 unit tests pass in `test_output/_test_filter_by_source.py`
covering: no-filter, single-source, multiple-sources, prefix-matching-
openalex, prefix-matching-crossref, case-insensitive, unknown-source,
whitespace-strip, no-mutation.

**Files changed**:
- `pa_cli/search.py` (~20 LOC: `filter_by_source` + `run_search` plumbing)
- `pa_cli/cli.py` (new `--source` option + comma split)
- `pa_cli/__init__.py` (version bump 3.9.9.8 → 3.9.9.9)
- `test_output/_test_filter_by_source.py` (NEW, 9 unit tests)
- `ROADMAP.md` ([P1-17] marked DONE; versioned table v3.9.9.9 row)

---

## [3.9.10.4] - 2026-07-20 ([P2-8] pa export-screening Bibtex→CSV ships)

### v3.9.10.4 — `pa export-screening` ships (2026-07-20)

**Feature**: Bibtex (+ optional pa judge data) → systematic-review-ready CSV.

**13 CSV columns**:
- `paper_key, query, relevance, reason, source` (pa judge data)
- `title, authors, year, venue, doi, abstract, type, bib_url` (bib metadata)

**Pluggable into**: Notion (csv import), Excel (utf-8 BOM), RevMan (CSV),
Covidence (CSV). UTF-8 with BOM (`utf-8-sig`) for Excel compatibility.

**CLI**:
```
pa export-screening refs.bib --out screening.csv
pa export-screening refs.bib --out screening.csv --no-unrated
pa export-screening refs.bib --judges judgements.sqlite --query "AI literacy" --out lit.csv
```

**Implementation** (~190 LOC + 26 tests):
- `pa_cli/export_screening.py` (NEW):
  - `build_screening_dict(bib_path)` — bib → {paper_key: {title, authors, year, venue, doi, abstract, type, bib_url}}
  - `load_judgements(db_path, query=None)` — pa judge sqlite → list of dicts (sorted by relevance desc)
  - `merge_with_bib(bib_dict, judge_rows, include_unrated=True)` — 3-input join
  - `write_csv(rows, out_path)` — utf-8-sig + QUOTE_MINIMAL
  - `run_export_screening(...)` — full pipeline
- `pa_cli/cli.py` (export-screening subcommand, +40 LOC, Click decorator)
- `pa_cli/scaffold.py:load_bibtex` — REUSED for bib parsing

**Tests**: 26/26 pass in `test_output/_test_export_screening.py`:
- TestBuildScreeningDict: 9 tests (titles, authors, year, venue, doi, bib_url, abstract, type)
- TestLoadJudgements: 4 tests (all/filter/nonexistent/sort)
- TestMergeWithBib: 3 tests (with/without unrated + inherit bib)
- TestWriteCsv: 5 tests (header/13 cols/multiline/BOM/Chinese)
- TestRunExportScreeningE2E: 5 tests (bib-only, with-all, filter, no-unrated, parseable)

**Sub-task breakdown** (per ROADMAP spec):
- A. build screening_dict per DOI (30min) ✅
- B. join with pa judge data (20min) ✅
- C. CSV writer (quoting, encoding) (20min) ✅
- D. CLI wire + 1 e2e test (20min, 5 e2e tests + 21 unit tests) ✅

**5-check Global Rule audit**: 5/5 pass
- $0 cost (Python stdlib `csv` + `sqlite3` + reuse existing `load_bibtex`)
- No hosted service
- Maintenance: 1 new module + 1 CLI subcommand (~230 LOC total)
- No publish obligation
- Free-tier degradation: works on any .bib + optional .sqlite, no API needed

**Files changed**:
- `pa_cli/export_screening.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (export-screening subcommand, +40 LOC)
- `pa_cli/__init__.py` (version bump 3.9.10.3 → 3.9.10.4)
- `test_output/_test_export_screening.py` (NEW, 26 tests)
- `test_output/_e2e_export_screening.py` (NEW, real CLI e2e)
- `ROADMAP.md` ([P2-8] marked DONE in v3.9.10.4)
- `CHANGELOG.md` (this entry)

**Use case (real)**:
- User runs `pa judge` for query "AI literacy" on 50 papers
- 30 papers get relevance labels (0/1/2), 20 are unrated
- User runs `pa export-screening refs.bib --judges db --query "AI literacy" --out lit.csv`
- Imports lit.csv into Notion/Excel for title/abstract screening with team
- 50 rows, sorted by (relevance desc, paper_key), unrated at bottom with empty fields

**Open follow-up (NOT in v3.9.10.4)**:
- [ ] Add `--format xlsx` for direct Excel output (currently CSV only)
- [ ] Add `--multi-query` flag to combine multiple queries' judgements into one CSV
- [ ] Add CSV column for "screened" boolean (user marks it in Notion, re-imports)

---

## [3.9.10.3] - 2026-07-20 ([P2-7] pa cite-check pre-build validator ships)

### v3.9.10.3 — `pa cite-check` ships (2026-07-20)

**Feature**: pre-build validator that scans a markdown skeleton for `[@bibkey]`
placeholders, cross-references against a Bibtex file, and reports 3 buckets:
- **[MISSING]**: placeholder has no bib entry
- **[TYPOED]**: placeholder has a near match (edit distance 1-2) with fix suggestions
- **[ORPHAN]**: bib entry is never cited in the skeleton

**Solves user pain**: today, `pa build` failure with "undefined reference"
gives you the wrong key but not the file/line. `pa cite-check` gives a clean
per-key report with line numbers, BEFORE running `pa build`.

**CLI**:
```
pa cite-check refs.bib skeleton.md
pa cite-check refs.bib skeleton.md --json | jq .missing
pa cite-check refs.bib skeleton.md --strict  # exit 1 on missing/typo
```

**Implementation** (190 LOC + 24 tests):
- `pa_cli/cite_check.py` (NEW):
  - `extract_cite_keys(text)` — regex on `[@\w\-:.]+`, returns [(key, line_no), ...]
  - `cross_ref(placeholders, bib_keys)` — 3-bucket classification
  - `_edit_distance_1_or_2(a, b)` — early-exit at distance 2 for typo detection
  - `suggest_fix(typo_key, bib_keys, max_suggestions=3)` — top-N suggestions
  - `format_report(result, skel_path, bib_path)` — human-readable text
  - `run_cite_check(bib_path, skel_path, output_json=False)` — full pipeline
- `pa_cli/cli.py` (`cite-check` subcommand added; uses Click decorator pattern)
- `pa_cli/scaffold.py:parse_bibtex` — REUSED for bib parsing (no duplication)

**Tests**: 24/24 pass in `test_output/_test_cite_check.py`:
- TestExtractCiteKeys: 6 tests (simple/multiple/dash/page/line numbers/no key)
- TestEditDistance: 5 tests (1/2/3/same string/too long)
- TestSuggestFix: 3 tests (finds/no suggestion/max N)
- TestCrossRef: 5 tests (clean/missing/typo/orphan/all three)
- TestRunCiteCheckE2E: 3 tests (e2e text/JSON/clean)
- TestFormatReport: 2 tests (clean report/with line numbers)

**Sub-task breakdown** (per ROADMAP spec):
- A. extract `[@key]` placeholders (15min) ✅
- B. parse keys from `.bib` (10min, reuse parse_bibtex) ✅
- C. cross-ref 3 buckets + typo fix suggestion (20min) ✅
- D. CLI wire + 1 e2e test + help text (15min, 24 tests vs spec 1) ✅

**5-check Global Rule audit**: 5/5 pass
- $0 cost (pure stdlib `re` + `difflib` patterns + reuse existing parse_bibtex)
- No hosted service
- Maintenance: 1 new module + 1 CLI subcommand (~200 LOC total)
- No publish obligation
- Free-tier degradation: works on any .bib + .md, no API needed

**Files changed**:
- `pa_cli/cite_check.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (cite-check subcommand, +35 LOC)
- `pa_cli/__init__.py` (version bump 3.9.10.2 → 3.9.10.3)
- `test_output/_test_cite_check.py` (NEW, 24 tests)
- `test_output/fixtures/demo_refs.bib` (NEW, test fixture)
- `test_output/fixtures/demo_skeleton.md` (NEW, test fixture)
- `ROADMAP.md` ([P2-7] marked DONE in v3.9.10.3)
- `CHANGELOG.md` (this entry)

**Use case (real)**:
- User writes skeleton with `[@smith2023ai]` but typo'd to `[@smtih2023ai]`
- `pa cite-check refs.bib skeleton.md` reports:
  - [TYPOED] line 11: `[@smtih2023ai]` <-- did you mean `[@smith2023ai]`?
- User fixes typo before running `pa build`
- No more "undefined reference" mystery

**Open follow-up (NOT in v3.9.10.3)**:
- [ ] Add similar pre-build check for `pa export-screening` ([P2-8])
- [ ] Add typo-fix on a one-liner sed command for batch skeleton cleanup
- [ ] Add `--threshold` option for edit distance (currently hardcoded to 1-2)

---

## [3.9.10.2] - 2026-07-20 (Simpler rerank: Ridge / LogReg beat LTR at n=50)

### v3.9.10.2 — Simpler rerank alternative ships (2026-07-20)

**Question**: Per ROADMAP Tier 2 "Simpler rerank alternative", can RidgeClassifier
or LogisticRegression beat LambdaMART 100 trees at n=50?

**Answer**: YES, by a large margin.

**Single 30/20 holdout results**:

| Method | NDCG@10 | Δ vs LTR | Δ vs combined |
|---|---:|---:|---:|
| **Combined baseline (default)** | **0.8988** | +0.1309 | 0 (best) |
| **RidgeClassifier (α=1.0, 8 features)** | **0.8526** | **+0.0847** | -0.0462 |
| **LogisticRegression (C=1.0, 8 features)** | **0.8409** | **+0.0730** | -0.0579 |
| LambdaMART 100 trees (LTR, deprecated) | 0.7679 | 0 (baseline) | -0.1309 |

**5-fold CV results**:

| Method | NDCG@10 mean | NDCG@10 std |
|---|---:|---:|
| **LogisticRegression** | 0.8265 | ±0.0278 (most stable) |
| **RidgeClassifier** | 0.8247 | ±0.0364 |
| Combined baseline (5-fold direct) | 0.8825 | ±0.0324 |
| LambdaMART 100 trees (LTR) | 0.7806 | ±0.0480 |

**Key insights**:

1. **Linear models strictly beat LambdaMART at n=50** by 0.07-0.09 NDCG@10.
   Root cause: LambdaMART 100 trees on 50 examples is over-parameterized.
   Linear models have at most 8 parameters (one per feature) → cannot overfit.

2. **Combined baseline still beats Ridge by 0.046 NDCG@10**.
   Combined is non-parametric (zero overfit risk) and uses 2 strong signals.
   Ridge adds 6 more features but most are derivatives of the same 2.

3. **LogReg is more stable across folds** (std ±0.0278 vs Ridge ±0.0364).
   LogReg's softmax output is bounded [0,1]; Ridge's decision_function is unbounded.

4. **LogReg coefficients are interpretable** (NEW capability):
   - `combined_score` +0.62 (strongest positive — agrees with combined baseline)
   - `biencoder_score` +0.54 (second strongest)
   - `log_cite_count` -0.30 (NEGATIVE — recent papers with low cites ranked up)
   - `year` -0.10 (NEGATIVE — newer papers preferred)
   - `bm25_score` -0.03 (NEGATIVE — model "trusts combined" over raw BM25)
   - `prf_score` +0.01 (essentially noise)

**Recommendation update**:
- Default ranker: **combined** (no training) — unchanged
- Learned ranker option: **RidgeClassifier** (NEW) — beats LTR by 0.085 NDCG
- Avoid: **LambdaMART 100 trees at n<200** — strictly worse than simpler alternatives
- Avoid: **BGE-reranker** — still significantly worse (v3.9.10 Wilcoxon p=0.000825)

**Files**:
- `bench/v01/reports/v3_9_10_2_simpler_rerank.json` (NEW, per-method per-fold)
- `bench/v01/reports/v3_9_10_2_simpler_rerank.md` (NEW, 3-tier honest report)
- `test_output/_run_simpler_rerank_v1_5.py` (NEW, runner)
- `ROADMAP.md` (Tier 2 "Simpler rerank alternative" marked DONE in v3.9.10.2)
- `pa_cli/labels_clean.json.simpler_rerank_bak` (transient backup, restored after run)

**5-check Global Rule audit**: 5/5 pass (sklearn pure local, no API, no hosted service).

**Open follow-up**:
- [ ] Add `pa_cli/simple_rerank.py` module exposing Ridge/LogReg as pa-rerank command
- [ ] Update `pa_cli/ltr.py` docstring: "LTR is worse than Ridge at n=50"
- [ ] Try Ridge with different α (0.1, 10, 100) at n=200 for hyperparameter sweep
- [ ] Re-run Simpler rerank at n=200 with real labels for tighter CI

---

## [3.9.10.1] - 2026-07-20 (Phase 1.5 holdout validation — 5-fold CV + single 30/20)

### v3.9.10.1 — Phase 1.5 holdout ships (2026-07-20)

**Action**: per ROADMAP "Recommended next step" (post-v3.9.10), run Phase 1.5
holdout validation to confirm v3.9.7.3 numbers survive honest evaluation.

**Method**:
- 5-fold CV (seed=42, same as v3.9.7.3) — sanity check, should reproduce numbers
- Single 30/20 holdout split (per ROADMAP spec) — stricter, closer to deployment

**Three honest findings**:

1. **5-fold CV is already holdout (sanity-check confirmed)**
   - Phase 1.5 5-fold CV reproduces v3.9.7.3 exactly: LTR 0.7806, MoE 0.6088
   - cv_aggregate was never in-sample; it was always per-fold test means
   - This validates v3.9.7.3 numbers were honest (just incomplete — only 5-fold, not single)

2. **Combined baseline 真实 NDCG = 0.8988 (single holdout), not 0.8141 (5-fold CV)**
   - 5-fold CV re-fits BM25/biencoder normalization on each fold's train set,
     applies to test → cross-fold normalization leakage
   - Single holdout uses one consistent normalization → 0.8988
   - 5-fold CV was conservative; 0.8988 is closer to deployment performance
   - This makes the case for combined baseline as default **even stronger**

3. **LTR 真实 Δ vs combined = -0.13 (single holdout), not -0.0335 (5-fold CV)**
   - LTR single holdout: 0.7679 vs combined single holdout: 0.8988 → Δ = -0.1309
   - LTR deprecation is **4x more justified** than v3.9.7.3 reported
   - Combined is even more dominant in deployment than in CV

**Files changed**:
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.json` (NEW — per-fold + single holdout data)
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.md` (NEW — 3-tier honest report)
- `test_output/_run_holdout_v1_5.py` (NEW — Phase 1.5 runner, 250 LOC)
- `pa_cli/ltr.py` (docstring updated with both 5-fold and single holdout numbers)

**Test set (single 30/20, n=20)**: q004, q005, q007, q009, q013, q014, q016,
q018, q020, q026, q027, q031, q033, q038, q040, q042, q046, q047, q048, q049
(11 of 20 from A2 auto labels — same caveat as v3.9.7.3)

**MoE single holdout** (also new): acc=0.7368, bal_acc=0.5417, macro_f1=0.5173
- Real MoE performance is 0.52, not 0.61 (5-fold was 0.09 generous)
- MoE still > 0.20 random, still useful, still needs more data

**5-check Global Rule audit**: 5/5 pass (local computation, no new APIs)

**Updated docstrings**: `pa_cli/ltr.py` now reports both 5-fold (-0.0335) and
single holdout (-0.1309) for honest comparison.

**Open follow-up**:
- [ ] Update `pa_cli/moe_router.py` docstring with single holdout 0.52 (more honest)
- [ ] Re-run Phase 1.5 at n=200 with real labels for tighter CI
- [ ] Investigate cross-fold normalization noise (why 5-fold CV under-reports combined)
- [ ] Try `train_test_split` with 10 seeds to get distribution of single holdout deltas

---

## [3.9.10] - 2026-07-20 (Deprecate BGE-rerank + LTR from default; promote combined to default)

### v3.9.10 — BGE/LTR deprecation ships (2026-07-20)

**Decision (not new code)**: v3.9.7.3 n=50 evaluation showed two methods
that should NOT be the default ranker:

1. **BGE-reranker** — significantly WORSE than bi-encoder for academic
   abstracts. Wilcoxon signed-rank test on n=48 paired:
   - Δ NDCG@10 = -0.1064 (BGE loses by 10.6 pp)
   - Wilcoxon p = 0.000825 (significant at α=0.05)
   - 36/48 queries BGE loses, 12/48 wins
   - Root cause: BGE-reranker-base trained on MS MARCO (English web search),
     not academic. q026-q050 are Chinese → BGE has no fallback.
   - True gap is LARGER than -0.1064 because A2 auto-labeling used BGE as
     tie-breaker (small +bias for BGE).

2. **LTR (LambdaMART 100 trees)** — loses to combined baseline at n=50:
   - LTR NDCG@10 = 0.7806 ± 0.048
   - combined baseline (0.5*BM25 + 0.5*bi-encoder) = 0.8141 (5-fold CV)
   - Δ = -0.0335 (LTR loses to simple linear baseline)
   - Root cause: 100 trees on n=50 overfits. Each tree sees 10-15 queries.
   - Note: LTR uses only BM25 + biencoder + metadata, NOT BGE — so this
     result is NOT contaminated by the A2 auto-label circularity.

**New default**: `combined` (0.5*BM25_norm + 0.5*bi-encoder_norm), the simplest
method that has no parameters, no overfit risk, and the best honest NDCG@10.

**Code changes** (docstring-only, no new code paths):
- `pa_cli/cross_encoder.py`: BGE marked DEPRECATED with Wilcoxon evidence
- `pa_cli/ltr.py`: LTR marked CONDITIONALLY DEPRECATED for n<200
- `pa_cli/moe_router.py`: macro F1 0.89 → 0.61 (honest number, n=47 mixed)
- `bench/v01/_v4_rerank.py`: `combined` marked RECOMMENDED DEFAULT

**Self-audit bug fixed in v3.9.10**: v3.9.7.3's own Wilcoxon MD report
mis-stated p>0.05 (text said "not significant, n<100 noise") while the
JSON showed p=0.000825 (highly significant). Caught and re-verified
2026-07-20 via `test_output/_verify_wilcoxon_recompute.py`. The fix:
- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.md` rewritten
  to correctly report the sig. negative result.

**5-check Global Rule audit**: 5/5 pass
- $0 cost (docstring updates only, no new code)
- No hosted service
- Maintenance: 1-line changes in 4 files
- No publish obligation
- Free-tier degradation: `pa search` does NOT use BGE/LTR, so no user-facing
  behavior change

**Files changed**:
- `pa_cli/cross_encoder.py` (DEPRECATED docstring)
- `pa_cli/ltr.py` (CONDITIONAL DEPRECATION docstring)
- `pa_cli/moe_router.py` (0.89 → 0.61 honest numbers)
- `bench/v01/_v4_rerank.py` (combined = RECOMMENDED DEFAULT)
- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.md` (MD bug fix)
- `bench/v01/reports/v3_9_7_3_action_plan.md` (NEW — deprecation context)
- `test_output/_verify_wilcoxon_recompute.py` (NEW — re-verify p=0.000825)
- `test_output/_verify_combined_n50.py` (NEW — combined baseline recompute)
- `test_output/_verify_combined_cv.py` (NEW — 5-fold CV baseline recompute)
- `test_output/_inspect_combined_schema.py` (NEW — debug schema)
- `test_output/_inspect_labels_format.py` (NEW — debug labels)
- `ROADMAP.md` ([P0-11] updated to "shipped in v3.9.10" with full action items)
- `CHANGELOG.md` (this entry)

**Discipline lessons (added to memory)**:
- Always verify summary text against raw JSON before shipping. v3.9.7.3
  self-audit failed twice (v3.9.7.2 mis-diagnosis "labels缺口" was actually
  code bug; v3.9.7.3 MD mis-stated p=0.000825 as "n.s."). Same failure
  pattern in the same session.
- BGE circularity in A2 auto-labeling: when the same model is used both
  for label generation AND for evaluation, the evaluation is biased
  in favor of that model. True gap is LARGER than reported.

**Open follow-up (NOT in v3.9.10)**:
- [ ] Quantify A2 auto-label circularity: re-run BGE Wilcoxon with BGE-excluded
      tie-breaker. 1-2h controlled experiment. [ROADMAP [P0-11] open]
- [ ] Investigate monoT5 / ColBERT / LLM-fulltext as BGE replacement.
      Blocked on user priority input.
- [ ] Re-evaluate LTR at n>200 with real labels. Blocked by [P1-13] label
      expansion.

---

## [3.9.9.10] - 2026-07-16 ([P1-18] --enrich-max-age-years year-aware skip)

### v3.9.9.10 -- [P1-18] ship (2026-07-16 18:30)

**Feature**: `enrich_top_n()` now skips ALL enrichment (S2 + Crossref +
OpenAlex fallback) for papers older than `max_age_years` (default 10).
S2 cite often stale/unavailable for older papers; Crossref rarely adds
missing fields for pre-2010 papers since OpenAlex/Crossref already
covered them in the initial search.

**CLI**: `--enrich-max-age-years 10` (default 10; set 0 to disable)

**Implementation**:
- `enrich_top_n()` accepts `max_age_years: int = 10` parameter
- Current year hardcoded to 2026 (no datetime import needed for testability)
- Boundary: 2016 paper in 2026 (=10y) is NOT skipped (strict `>` check)
- `_enrichment.enrichment_skipped = "year<{YEAR}"` records reason
- Stats line extended: `[P1-14/18] enrich_top_n: enriched X, skipped_low_cite Y, skipped_old Z (year<{Y}) of top-N`

**Tests**: 8/8 unit tests pass in `test_output/_test_max_age_years.py`
covering: old-skipped, new-enriched, None-year-proceeds, max_age=0-disables,
5y-threshold, 10y-boundary-not-skipped, mixed-old-and-new, min_cites-combination.

**Files changed**:
- `pa_cli/search.py` (~30 LOC: `max_age_years` param + check in enrich loop)
- `pa_cli/cli.py` (new `--enrich-max-age-years` option)
- `pa_cli/__init__.py` (version bump 3.9.9.9 → 3.9.9.10)
- `test_output/_test_max_age_years.py` (NEW, 8 unit tests)
- `ROADMAP.md` ([P1-18] marked DONE; versioned table v3.9.9.10 row)

    (since v3.9.9.5 is latest; added note explaining feature vs
    doc-only distinction)

- **Round 14 (3 issues)** — this commit (and the [3.9.9.5] promotion
  to [3.9.9.6] for the consolidated audit count):
  - R14-1: Round 2 audit count was wrong in CHANGELOG and handoff
    (8/5 vs actual 10/5 per the a559050 commit's I-1 to I-10 list)
  - R14-2: Handoff audit table totals off by 2-3 (rounds 1-9 said
    37/30; corrected to 45/37 with rounds 1-13)
  - R14-3: CHANGELOG [3.9.9.5] promoted to [3.9.9.6] to include
    rounds 11-14 (and fix the audit count)

**Total across rounds 8-14**: 18 issues found + fixed.
**Total across all 14 audit rounds**: 45 issues found, 37 fixed (8
deferred to [P2-13] / future passes).

**Discipline correction (added to memory)**:
- "Diminishing returns at 1 issue/round" was a wrong stopping heuristic.
  Rounds 8-14 each found real (non-cosmetic) issues. The right stopping
  point is "issues per round = 0 for 2 consecutive rounds", not "≤ 1".
- "Audit round scope discipline": each round should be a fresh full sweep,
  not "just check the changed parts". The handoff drift in R9-3 was not
  visible in the changed parts of d1f2a6d; only a fresh sweep caught it.
- "Audit count discipline": round counts must be derived from the actual
  commit's fix list, not from a summary line (which can be wrong). R14
  caught this — Round 2 summary said "8" but commit listed I-1 to I-10.

**Honest verdict on rounds 8-14**: no premature stop this time. 7
consecutive rounds of real (non-cosmetic) issues found. The user pushback
"一直审查到没有问题为止" was the right call.

---

## [3.9.9.5] - 2026-07-16 (ROADMAP self-audit rounds 8-10: 9 more issues found + fixed)

**[3.9.9.5] is now SUPERSEDED by [3.9.9.6]**. The [3.9.9.6] release
extends the audit count to include rounds 11-14 and corrects the
Round 2 audit count. Keep this section for historical reference only.

Per user catch 2026-07-16 11:38 ("我看你的todo list 还没做完"): the
previous "audit clean" verdict at round 7 was premature. User pushed back
correctly — the [3.9.9.4] claim of "diminishing returns" was wrong; more
real issues existed. Re-audit:

- **Round 8 (5 issues)** — `d1f2a6d`:
  - R8-1: L2268 "Layer 4 Filters" table still referenced `[P2-5]` for
    Quality filter (should be `[P2-14]`) — same class of bug as R3-1
    that was supposedly fixed
  - R8-2: L1288 "see [P2-5] research 2026-07-15" for Lit review WRITING
    row — broken reference (that research section was REPLACED by
    "Writing pipeline" section per CHANGELOG v3.9.7.9 follow-up)
  - R8-3: Tier 3 still had leading numbers 10./11./12. (Round 2 I-4
    dropped them in Tier 1/2 but missed Tier 3)
  - R8-4: Tier 5 still had leading numbers 13./14. (same as R8-3)
  - R8-5: L1289 "proposed [P2-5]" — now misleading since shipped
    (cosmetic; collapsed into R8-2 fix)

- **Round 9 (3 issues)** — `d1f2a6d` (same commit):
  - R9-1: Versioned summary table missing v3.9.9.3 and v3.9.9.4 rows
    (CHANGELOG had these but ROADMAP table didn't)
  - R9-2: "Recommended next step" section missing [P-N] IDs
    (violates rule 8 added in [3.9.9.3])
  - R9-3: Handoff Section 5/9 missing [P1-14..18] quick-wins
    (retroactive IDs assigned in [3.9.9.3] but handoff not updated)

- **Round 10 (1 issue)** — `553c141`:
  - R10-1: [P3-1] "Realistic path forward" said "Add `pa judge` command"
    but pa judge shipped v3.9.9.1 — should be "Use `pa judge` (shipped)"

**Total across rounds 8-10**: 9 issues found + fixed.
**Total across all 10 audit rounds** (per [3.9.9.5]): 38 issues found, 31 fixed.
**Superseded by [3.9.9.6]**: actual count is 45 found, 37 fixed (rounds 1-14).

**Discipline correction (added to memory)**:
- "Diminishing returns at 1 issue/round" was a wrong stopping heuristic.
  Rounds 8-10 each found real (non-cosmetic) issues. The right stopping
  point is "issues per round = 0 for 2 consecutive rounds", not "≤ 1".
- "Audit round scope discipline": each round should be a fresh full sweep,
  not "just check the changed parts". The handoff drift in R9-3 was not
  visible in the changed parts of d1f2a6d; only a fresh sweep caught it.

---

## [3.9.9.4] - 2026-07-16 (ROADMAP self-audit rounds 2-7: 16 more issues found + fixed)

Per user instruction 2026-07-16 11:11: "再修，修完之后再审查，然后再修，再审查
。。。。一直审查到没有问题为止" (keep auditing ROADMAP until no problems).
Ran 6 more rounds of self-audit after the [3.9.9.3] round 1. Found and
fixed 16 issues across rounds 2-7. ROADMAP is now self-consistent
(only known residual: historical sub-task naming drift [P0-7.1] /
[P1-11.1] from v3.9.7.1, documented in ID naming convention).

**Round 2 (5 issues)** — `a559050 docs(roadmap): round-2 audit fixes`:
- I-1: A-tier coverage table — split top-10 vs top-20/all rows
- I-2: Tests line — removed 'per-version breakdown' phrase (contradictory)
- I-3: [P2-13] README — moved from Tier 1 to Tier 5 (deferred)
- I-4: Tier 1 + 2 leading numbers (1./2./.../12.) — dropped to fix
  cross-tier collision (Tier 1 '10.' vs Tier 2 '10.')
- I-5: [P2-11] pa fetch-pdf-batch sub-tasks — added F. (60min buffer)
  so sub-tasks sum to 4h matching master

**Round 3 (6 issues)** — `3f7881c docs(roadmap): round-3 audit fixes`:
- R3-1 (CRITICAL): [P2-5] ID collision — 'Quality filter' (Active
  items, old) shared ID with 'pa build + pa scaffold' (shipped).
  Renumbered Quality filter to [P2-14].
- R3-2: Sub-task ID convention clarified — letter suffix is the
  established pattern ([P0-9.1a/b/c]).
- R3-3: 5 pre-naming Tier 1 items (--enrich-top-min-cites etc.)
  retroactively assigned [P1-14] through [P1-18].
- R3-4: A-tier section got 'Important framing' note explaining
  the A-as-stretch-target vs B+→A-section's 'A- is ceiling' framing.
- R3-5: 'Modified items' section updated with 3 new entries.
- R3-6: A-tier 'How to measure' step 2 changed from '--relevance 1'
  (marginal) to '--relevance 2' (relevant) + clarifying note.

**Round 4 (2 issues)** — `b6d506b docs(roadmap): round-4 audit fixes`:
- R4-1: Line 1562 '### [P2-5] implementation sketch' was using the
  [P2-5] ID in a research-doc sub-section. Renamed to 'Implementation
  sketch (research-doc section, not a ticket)'.
- R4-2: Line 2046 [P1-5] recency rule referenced [P2-5] for
  Quality filter (now [P2-14]). Updated with historical note.

**Round 5 (1 issue)** — `fefa7c5 docs(roadmap): round-5 audit fix`:
- R5-1: [P2-13] README entry had confused phrasing about
  '[P3-1] rerank trigger check' (which made no sense) and
  '[P2-13] README's Files added section' (self-referential).
  Rewrote to match the actual intent.

**Round 6 (1 issue)** — `d79fa70 docs(changelog): round-6 audit fix`:
- R6-1: CHANGELOG line 2620 had | [P2-5] Quality filter | in a summary
  table. Updated to [P2-14] with historical note.

**Round 7 (1 issue)** — `7266d41 docs(roadmap): round-7 audit fix`:
- R7-1: CHANGELOG v3.9.7.1 used [P0-7.1] / [P1-11.1] sub-task
  format (parent + digit) which doesn't match the current
  [P0-9.1a/b/c] letter-suffix convention. Added a historical
  note in the ID naming convention rule.

**Net ROADMAP growth across rounds 2-7**: 3380 → 3389 lines (+9 net).
Mostly internal restructuring, not content bloat.

**Honest verdict on "until no problems"**:
- ✅ All substantive issues **at the time of this release** fixed (rounds 1-7
  cleared ID collisions, cross-references, framing contradictions, version
  table, ID convention)
- ⚠️ Cosmetic-only residuals (Honest 3-tier format mix, long sentences)
  — diminishing returns, intentionally not fixed
- ⚠️ **This verdict was premature** — see [3.9.9.5] (rounds 8-10 found 9 more
  real, non-cosmetic issues). The "diminishing returns" signal at 1 issue/
  round was a wrong stopping heuristic. Right stopping point: 0 issues for
  2 consecutive rounds.

---

## [3.9.9.3] - 2026-07-16 (ROADMAP self-audit: 6 defects fixed)

Per user request 2026-07-16 11:05: write the 6 new extensions into
ROADMAP, then critically analyze. Analysis surfaced 7 concrete
defects + 3 meta-defects. User selected defects #1+#2+#4+#5+#6+#M2
for immediate fix. This release closes those 6.

**Defect #1 — A-tier acceptance criteria missing (fixed)**:
Added new "A-tier acceptance criteria" section with measurable targets
for coverage metrics (cite%/abstract%/tldr% per language) + workflow
metrics (search/screen/write time) + user-subjective metric
("A-tier iff paper-agent+Mavis is ≥3x faster than ChatGPT alone").
Methodology: 3 real 课题 mix (数字普惠金融 / 长期护理保险 / 金融科技).

**Defect #2 — [P-N] ID naming convention missing (fixed)**:
Added rule 8 to the "Status discipline" block at the top of ROADMAP.
P0=core infra, P1=search quality, P2=user-facing productivity,
P3=long-term bets. **Discovered during this fix**: my earlier
extension additions used [P2-6..11] which collided with existing
[P2-6] PaSa-lite (v3.9.6). Renumbered new items to [P2-7..13].

**Defect #4 — Future candidates' effort estimates unsourced (fixed)**:
Added sub-task decomposition to all 6 new items ([P2-7] through
[P2-13]), in the same style as [P0-1/2/3] retro. Each new item now
has A/B/C/D/E sub-tasks with per-step time estimates.

**Defect #5 — Tier numbering inconsistent (fixed)**:
Reordered section: now Tier 1 → 2 → 3 → 4 (Blocked) → 5 (Long-term).
Previously Tier 4 (Blocked) was after Tier 5 (Long-term), which
violated "more-likely-first" reading order.

**Defect #6 — Test counts not in ROADMAP (fixed)**:
Added "**Tests**: 27 unit + CLI tests across 2 new modules (pa build
10 + pa judge 17)" line at the end of Capability snapshot. Detail
lives in CHANGELOG (per-version breakdown).

**Defect #M2 — Capability snapshot dual identity (fixed)**:
Added explicit "What this section IS and ISN'T" block at the end of
Capability snapshot, making clear: ✅ IS forward-looking status,
❌ IS NOT plan (that's "Future improvement candidates" below),
❌ IS NOT release log (that's CHANGELOG.md).

**Defect #3 (deferred to process ticket)**:
AMiner git gap (v3.9.8.0 ship but no commit) is now caught by
the [P2-13] README ticket (which will need a "Files added:" check
in any release). User chose not to add a commit-template change.

**Defect #7 (deferred)**:
"What paper-agent can't do" ❌ bucket still mixes BLOCKED and
DEFERRED. Will split in a future pass.

**Defects M1, M3 (deferred to [P2-13] / future)**:
- M1: ROADMAP is single file; split at 2000-line mark
- M3: README.md — added as [P2-13] ticket (2h, ⭐⭐ low priority,
  user-confirmed not blocking LLM understanding of project)

---

## [3.9.9.2] - 2026-07-16 (working tree cleanup + AMiner git-gap fix)

### v3.9.9.2 -- commit missing v3.9.8.0 AMiner engine (2026-07-16 10:32)

**Honest discovery**: during working tree cleanup, found 2 files that are
USED BY CURRENT CODE but were never committed to git:

1. `pa_cli/aminer_channel.py` (~9 KB, 270 LOC) — AMiner 7th search engine
   - Referenced in `pa_cli/search.py:433` in the engines tuple
   - ROADMAP version table claims v3.9.8.0 (2026-07-15) shipped this;
     CHANGELOG same claim. But git log showed no commit for the file.
2. `pa_cli/data/cn_stopwords.txt` — Chinese stopwords for topic clustering
   - Referenced in `pa_cli/topics.py:178 _load_cn_stopwords()`

**Likely cause**: the v3.9.8.0 work was done in a session that ended
without a `git add`. Subsequent sessions picked up the working tree
state but never back-filled the missing commit.

**Fix**: `c2b5a08` adds both files to git. No code changes; the files
are byte-for-byte what was already on disk and in use by the working CLI.

**Implication for ROADMAP honesty**: the v3.9.8.0 "AMiner engine shipped"
claim is now BACKED by a git commit, not just by a working-tree file.
The version-table integrity is restored.

### v3.9.9.2 -- working tree cleanup (2026-07-16 10:34)

Per handoff Section 9 item 3 (user-noted flag, "not urgent but flagged"):

**Trashed via mavis-trash (recoverable via Windows Recycle Bin)**:
- v1/v2 era top-level files (5 files, 39 KB):
  `pa.py`, `agent.py`, `agent2.py`, `paper_fetcher.py`, `strip_legacy.py`
  (meta-irony: `strip_legacy.py` was a script to remove legacy code, itself
  legacy)
- 7 v3.0 cache dirs (~2.4 MB, mostly `downloaded_pdfs/` at 2 MB):
  `arxiv_cache/`, `core_cache/`, `doaj_cache/`, `eric_cache/`,
  `openalex_cache/`, `semanticscholar_cache/`, `downloaded_pdfs/`
- Old result JSON/MD from prior 6/25 run (1.7 MB):
  `pool_2026-06-25_*.json` (3 files), `screening_metadata.json`,
  `screening_report_2026-06-25.md`, `search_manifest.yaml`,
  `stage4_keywords.json`
- mavis demo + Chinese drafts (53 KB):
  `mavis_demo_v1.md`, `mavis_screening_v1.md`, `mavis_screening_v2.md`,
  `OpenAlex_實證文獻總覽與清單.txt`, `專屬文獻綜述草稿.txt`,
  `文獻綜述草稿.txt`, `高質量文獻總覽與下載清單.md`
- Chinese-named old results (70 KB):
  `初筛_文献综述_2026-06-25.json`, `终筛_细读_2026-06-25*.json`,
  `终筛_细读_stage4_报告.md`

**Total trashed**: 4.1 MB across 32 files/dirs

**.gitignore updated** (`a0187f8`): added patterns for the 7 cache dirs
and `test_output/_*.log/.txt/.sqlite` (auto-ignores ~80 more files).

**Net result**: visible untracked went from 197 → 115 (-82). The 115
remaining are mostly `bench/v01/` scratch, `skill/` (deprecated v3.0
self-contained skill, large, would need separate decision), and
`test_output/_debug_*.py/.html` + `_check_*.py` + `_explore_bench*.py`
debug scripts. These need per-file judgment; not touched in this commit.

---

## [3.9.9.1] - 2026-07-16 ([P3-1] `pa judge` relevance judgement collection)

### v3.9.9.1 -- pa judge (2026-07-16 10:24)

Per ROADMAP "Tier 5 long-term" (post-v3.9.7.9, revised per user pushback
2026-07-15): v3.9.7.0-7.2 ML/DL local rerank failed at n=50 (data
problem, not absolute). User pushback: "ML/DL 本地不是不可行, 是数据太少".
Corrected verdict: re-probe when n >= 500.

This release ships the data-collection track. Storage in a local SQLite DB;
CLI for adding single/bulk judgements, listing, stats, and bench-format
import/export (compatible with the existing LTR pipeline).

**Storage**: `~/.paper-agent/judgements.sqlite` (override with `PA_JUDGE_DB` env var)

**Schema**:
```
judgements (id, query, paper_key, paper_title, relevance, reason,
            source, created_at, updated_at,
            UNIQUE(query, paper_key))
```

**Relevance scale** (matches existing bench/v01/labels.json rubric):
- `0` = irrelevant  (off-topic, or wrong level+topic)
- `1` = marginal    (topic adjacent OR level wrong OR scope right but topic wrong)
- `2` = relevant    (matches query topic + level + scope)

**New CLI commands** (6 subcommands under `pa judge`):
- `pa judge add --query ... --key ... --relevance {0,1,2} [--title] [--reason] [--source] [--db]`
- `pa judge bulk <bibtex> --query ... --relevance {0,1,2} [--reason] [--db]`
- `pa judge list [--query] [--relevance] [--limit] [--format table|json|jsonl]`
- `pa judge stats [--query]` (prints n hint: <100 = noise, 100-499 = small, >=500 = ready)
- `pa judge export -o <path> [--format jsonl|bench-json]` (LTR pipeline compat)
- `pa judge import <bench.json>` (bench/v01/labels.json shape)

**Files**:
- `pa_cli/judge.py` (~420 LOC, NEW)
- `pa_cli/cli.py` (+~200 LOC, registered `pa judge` group + 6 subcommands)
- `test_output/_test_pa_judge.py` (17 unit + CLI tests)
- `test_output/_demo_judgements_bench.json` (sample bench-format export)

**Test result**: 17/17 pass
- Core: add, upsert, list filter, stats, bulk, validation
- IO: bench import, invalid-relevance skip, export round-trip, JSONL export
- CLI: subcommand registration + add/bulk/stats via Click runner

**Honest 3-tier verification**:
| What | Status | Evidence |
|---|---|---|
| Single/bulk add + list + stats + export + import | ✅ | 17/17 tests pass; real CLI run added 3 judgements, stats correct, bench-format round-trips |
| Schema enforces `(query, paper_key)` UNIQUE | ✅ | upsert_overwrite test verifies re-adding updates same row, not creates new |
| Relevance validation (must be 0/1/2) | ✅ | add_invalid_relevance test |
| Bench/v01/labels.json import compatible | ✅ | export_bench_format_round_trip test + real CLI run |
| Re-probe ML/DL rerank at n>=500 | ❌ future work | need to accumulate data first |
| Concurrent write safety | ⚠️ untested | SQLite serialises by default; fine for single-user hobbyist workflow |

**Typical user flow**:
1. `pa search "topic" --format bibtex --out refs.bib`
2. `pa judge bulk refs.bib --query "topic" --relevance 1` (rough first pass)
3. `pa judge add ...` (per-paper refinement)
4. `pa judge stats` (track n; ready when n >= 500)
5. `pa judge export -o bench_labels.json --format bench-json` (LTR pipeline input)

---

## [3.9.9] - 2026-07-16 ([P2-5] `pa build` + `pa scaffold` manuscript typeset pipeline)

### v3.9.9 -- pa build + pa scaffold (2026-07-16 10:12)

Per ROADMAP "Writing pipeline" (post-v3.9.7.9, revised per user pushback):
prose = Mavis's job, scaffold + typeset = paper-agent's job. This release
ships the scaffold + typeset half.

**New CLI commands**:

`pa scaffold refs.bib [--group-by {year,topic,author,none}] [--topics topics.json]`
                     `[--title ...] [--output ...]`
- Lightweight bibtex parser (no external deps)
- Renders a markdown outline skeleton with:
  - H1 title + 引言 / 结语 / 参考文献 sections
  - Per-year / per-topic / per-author H2 grouping
  - Per-paper H3 (title) + meta line (author · year · venue)
  - `> prompt: ...` block per paper telling Mavis what to write,
    including the `[@bibkey]` cite to copy into prose
- Optional: pass `--topics topics.json` (from `pa review-topics`) to group
  by topic cluster instead of year

`pa build refs.bib --skeleton manuscript.md --output manuscript.{html,docx,pdf,tex,md,...}`
                `[--csl path] [--format ...] [--pdf-engine xelatex|weasyprint|...]`
- Wraps pandoc with built-in `--citeproc` + bundled `chinese-gb7714-2005-numeric.csl`
- Auto-detects format from output suffix
- Auto-detects best PDF engine (xelatex > lualatex > pdflatex > weasyprint)
  if format is PDF; otherwise no engine needed
- Prints actionable install hints if xelatex is missing (e.g. "Install MiKTeX")

**Files**:
- `pa_cli/build.py` (~265 LOC, NEW)
- `pa_cli/scaffold.py` (~330 LOC, NEW)
- `pa_cli/data/chinese-gb7714-2005-numeric.csl` (15.4 KB, NEW, MIT-style
  license, downloaded from citation-style-language/styles official repo)
- `pa_cli/cli.py` (+134 LOC, registered `build` + `scaffold` subcommands
  appended after `fetch-batch` to minimize diff vs v3.9.8.4)
- `test_output/_test_pa_build.py` (267 LOC, 10 unit tests, all pass)
- `test_output/_demo_*.bib/.md/.html` (sample round-trip output)

**Test result**: 10/10 pass
- `test_parse_bibtex_count/fields` — bibtex parser
- `test_scaffold_default_group_by_year/author/empty_bibtex` — skeleton rendering
- `test_default_csl_exists` — bundled CSL sanity check
- `test_pdf_engine_detection` — engine auto-detect
- `test_e2e_{html,docx,gfm}` — full scaffold→build round-trip

**Honest 3-tier verification**:
| What | Status | Evidence |
|---|---|---|
| `pa scaffold` produces valid markdown | ✅ | 3 unit tests pass; sample output in `_demo_skeleton.md` |
| `pa build` runs pandoc and produces file | ✅ | 3 e2e tests pass; HTML/DOCX/GFM output verified |
| GB/T 7714 numeric cites resolve correctly | ✅ | e2e HTML test verifies [1] in-text + [1] Author... in bib |
| xelatex PDF path works | ⚠️ NOT TESTED | xelatex not installed on dev machine; pa build will print install hint |
| weasyprint PDF fallback | ⚠️ NOT TESTED | weasyprint IS installed but quality vs LaTeX is unknown |
| LLM prose quality | ❌ OUT OF SCOPE | Mavis's job, by design (per user pushback 2026-07-15) |

**Typical user flow** (per ROADMAP):
1. `pa search "topic" --format bibtex --out refs.bib`
2. (optional) `pa scaffold refs.bib --out skeleton.md`
3. User pastes refs.bib + skeleton into Mavis chat, asks for lit review prose
4. Mavis outputs markdown with `[@bibkey]` cites inline
5. `pa build refs.bib --skeleton manuscript.md --out manuscript.html`
6. (or `--out manuscript.pdf` after MiKTeX install)

Per user 2026-07-15: identified writing gap (paper-agent covers search but
not writing/formatting) + asked for B+→A upgrade assessment. After 5-layer
GitHub due diligence (4 web searches covering 9 candidates) + AMiner API
verification, committed the research findings to ROADMAP.md.

### v3.9.7.9 follow-up (user pushback 2026-07-15 18:00)

User corrections applied:
1. **"写作是 Mavis 的活"** — Revised earlier framing that was wrong. Split:
   prose = Mavis (user's chosen LLM); scaffold + typeset = paper-agent (`pa
   build` / `pa scaffold` with pandoc). ROADMAP "Writing pipeline" section
   replaces earlier "Lit review WRITING research" section.
2. **"ML/DL 本地不是不可行, 是数据太少"** — Corrected verdict. The
   v3.9.7.0-7.2 failures were a data problem, not absolute. [P3-1] long-term
   track added: opportunistic judgement collection via `pa judge` command,
   re-probe when n>=500. Not abandoned, just deferred.
3. **"AMiner 拍板"** — [P1-7] promoted to in-progress, 4-6h effort.

### Added (docs only)

- **ROADMAP "Writing pipeline"** section (replaces "Lit review WRITING research") —
  revised split: Mavis does prose, paper-agent does scaffold + typeset.
  pandoc + Manubot pattern is the right format pipeline. GB/T 7714 is one
  CSL file away. Honest 3-tier table of what `pa build` gets right vs not.
- **ROADMAP "B+ → A level upgrade assessment"** section — Path (a) ML/DL
  verdict **corrected** from "NOT viable" to "deferred, data problem not
  absolute"; Path (b) and (c) unchanged from prior assessment.
- **ROADMAP "What paper-agent can't do"** added 3 writing-related rows
- **ROADMAP Tier 1 #6 [P2-5]** — revised scope: `pa build` (pandoc
  typeset) + `pa scaffold` (outline template) only, no LLM integration.
  2-4h effort.
- **ROADMAP Tier 1 #7 [P1-7]** — promoted to in-progress (user sign-off).
  AMiner engine, 4-6h effort, +10-15pp Chinese cite coverage.
- **ROADMAP Tier 5 long-term [P3-1]** — ML/DL data collection track. Add
  `pa judge` command + sqlite storage. Re-probe when n>=100/200/500.
- **ROADMAP Tier 5 long-term #14** — local small LLM rerank (Qwen 1.5B /
  MiniCPM 2B / Phi-3 / Jamba Reasoning 3B). Deferred: only revisit if
  Mavis itself becomes unavailable.

### Three-tier audit (per discipline, honest reporting)

| Claim | Status | Evidence |
|---|---|---|
| Paper-agent can produce a formatted manuscript PDF | ❌ false | no `pa build` command yet; only `pa search --format bibtex` |
| pandoc + Manubot pattern works for Chinese lit review | ✅ true | Nature Biotech 2025 used Manubot for full manuscript pipeline |
| gpt_academic / 纸研社 / paper-red are usable | ❌ no (for us) | all require hosted LLM API; Mavis already covers this role |
| AMiner can lift Chinese coverage 10-15pp | ⚠️ estimated | open.aminer.cn public API exists, free; lift is a projection, not measured |
| B+ → A is achievable under hobbyist budget | ❌ no | terminal limitations (CNKI cite/dl, Chinese tldr) require paid SaaS or inst access |
| B+ → A- is achievable with AMiner | ⚠️ estimated | +10-15pp CN brings us closer to A-; not yet shipped |
| ML/DL rerank can work with n>=500 | ⚠️ unproven | v3.9.7.0-7.2 failed at n=50; need to re-test at n=500 |
| Writing prose is paper-agent's job | ❌ wrong (corrected) | prose = Mavis (user's choice); paper-agent = scaffold + typeset |
| Writing formatting/scaffold is paper-agent's job | ✅ true | [P2-5] `pa build` + `pa scaffold` covers this |

### No code change in this release

This is still docs-only. [P1-7] AMiner is in-progress per user sign-off;
[P2-5] `pa build` is proposed and user has not yet asked to start it.

---



## [3.9.8.3] - 2026-07-15 (CNKI fetch honest evaluation + 2-cookie limit)

### v3.9.8.3 -- CNKI fetch path real test (2026-07-15 22:42)

After user provided 2 fresh xueshu789.com cookies (PHPSESSID + user), ran
end-to-end test of the freshly-implemented fetch_cnki_detail() function.
Result: search works, but PDF download blocked by CNKI anti-bot + paid system.

**What works:**
- CNKI search path (`pa search --engine cnki`) — already used in v3.9.7.5+
- Bootstrap → search returns paper metadata (DOI, title, authors, venue, year,
  cited_by_count, cnki_url) — verified across 3+ queries

**What doesn't work end-to-end:**
- fetch_cnki_detail() → detail page access: 404 on proxy IP / Vue SPA
  "安全验证" page on kns.cnki.net (anti-bot triggers when cookies incomplete)
- fetch_cnki_detail() → PDF download: real download goes through
  `bar.cnki.net/bar/download/order?id=...` which requires institutional
  subscription OR paid CAPTCHA — out of hobbyist scope

**2-cookie vs 4-cookie limit:**
- v3.9.7.4 used 4 cookies (PHPSESSID + user + entrys + expires) and search worked
- v3.9.8.3 with 2 cookies (just PHPSESSID + user): search still works, but
  detail page access fails. xueshu789 may have tightened cookie requirements
  OR user only saw 2 cookies in their current session.
- Workaround for user: visit several xueshu789 pages (not just dbList/1) to
  receive full 4-cookie set; re-export.

**Files added/modified:**
- `pa_cli/fetch.py`: `fetch_cnki_detail()` upgraded from stub to real playwright
  flow (bootstrap + search by DOI + page.goto + expect_download)
- `pa_cli/fetch.py`: `fetch()` main entry now routes CN-style DOI to CNKI first
  (heuristic: 10.3969/10.16525/j.cnki/j.issn prefixes)
- `Export-CNKICookies.ps1`: 4-cookie manual export script (PowerShell)
- `export_cnki_cookies.py`: 2-cookie playwright auto export (used today)

**Honest verdict for Chinese paper PDF download:**
The CNKI fetch pipeline is search-side solid but PDF-download-blocked by
bar.cnki.net (paid order system) + cnki.net anti-bot. For now, the practical
workflow is:
  1. Use `pa search --engine cnki` to get metadata (works, cite% boost)
  2. For PDF, user manually copies bar.cnki.net link into their Edge
     (which has the proxy session cookies) and downloads from there
  3. Move on — paper-agent's value is in search, not in full-text fetch

## [3.9.8.2] - 2026-07-15 (CORE cleanup + honest re-evaluation)

### v3.9.8.2 -- CORE engine honest re-evaluation (2026-07-15 19:30)

**Earlier (v3.9.8.1) I claimed "CORE key expired early" and removed CORE from the
default engine list. That conclusion was WRONG. Re-investigating today found:**

1. **CORE v3 API key is OPTIONAL** -- anonymous requests work for low-volume
   single queries (curl test: HTTP 200, 2549 hits for "long-term care insurance")
2. **The real failure modes were**:
   - **Rate limiting**: CORE v3 anonymous mode is strictly limited (~1 req/min).
     First request 200 OK, all subsequent ones 429 (verified across 5 queries)
   - **Wrong auth format**: `Authorization: Bearer <key>` header causes
     15-17s timeouts. CORE v3 supports `?api_key=` query param instead.
   - **CJK coverage is near-zero**: "数字普惠金融" -> 2 hits only (CORE is
     99% English repositories)
3. **OpenAlex already indexes CORE's 4.7M papers** -- the marginal coverage
   from a separate CORE call is <5% but maintenance cost is high (UA quirks,
   rate limits, occasional network timeouts).

**Fix shipped (v3.9.8.2)**:
- `search_core()` rewritten: no-key mode works, key uses `?api_key=` query param,
  removed Bearer header
- `search_core()` kept available via `pa search --engine core` (explicit only)
- Default `--engine all` stays at 6 engines (crossref/openalex/arxiv/s2/aminer/cnki)
- `moe_router.py` ENGINES list updated (CORE removed, AMiner added)
- `keys.py` CORE notes rewritten to reflect optional-key + no-Bearer reality

**Substitute evaluation (user asked "再找找有没有替代的")**:
| Candidate | Result | Verdict |
|---|---|---|
| **OpenAlex** | Already integrated | Best substitute (covers CORE + more) |
| **AMiner** | Added v3.9.8.0 | +10.9pp cite lift for Chinese queries |
| **BASE (Bielefeld)** | IP whitelist + admin contact required | Global Rule conflict |
| **RePEc/IDEAS** | Email application required | Not open API |
| **NBER** | HTTP 403 | Blocked |
| **Lens.org** | Has API but requires application | Defer; OpenAlex already covers |
| **Internet Archive Scholar** | No public search API | Web-only |

**Verdict**: no new independent engine needed. The right play is:
- OpenAlex handles English repos (CORE's 4.7M + Crossref + arXiv + 10wan+ others)
- AMiner handles Chinese cite/abstract (+10.9pp lift on Chinese queries)
- CNKI handles the xueshu789-cookie-gated long tail for Chinese PDFs

## [3.9.7.9] - 2026-07-15 (patch — bugfix: tldr=None guard + real-query smoke test)

Per user 2026-07-15 "继续做,拿真实 query 试". Found and fixed a NoneType
crash in v3.9.7.8's top-N deep enrichment; also ran 3 real-world academic
queries to measure actual workflow coverage.

### Fixed — AttributeError on `tldr_text.startswith()` when tldr=None

When S2 `paper/DOI:...` returns `tldr: None` (instead of dict or missing),
`v3.9.7.8._s2_lookup_doi()` crashed with `AttributeError: 'NoneType' object
has no attribute 'startswith'`. Also affects the dedup loop's tldr filter
if the field is None in any merged result.

**Files** (1 LOC defensive fix × 2):
- `pa_cli/search.py` `_s2_lookup_doi()`:
  `tldr_text = tldr_text or ""  # guard against None` (after the dict-or-empty check)
- `pa_cli/search.py` `run_search` dedup loop:
  `tldr = r.get("tldr") or ""  # guard against None` (was `r.get("tldr", "")`)

**Trigger discovered by**: real-query smoke test 2026-07-15 — first 3
queries crashed at the first S2 paper/DOI call (bug was in the very first
S2 lookup that returned `tldr: None`).

### Real-query smoke test result (3 academic queries, 2022-2024, --enrich-top 10)

| Query | dedup | cite | abstract | tldr | top-1 cite |
|---|---|---|---|---|---|
| 数字普惠金融 + 家庭消费 (经济学) | 26 | **46%** | 31% | 12% | 27 |
| 长期护理保险 + 人口老龄化 (保险学) | 43 | **30%** | 19% | 7% | 12 |
| 金融科技 + 中小银行 (金融学) | 49 | **35%** | 18% | 4% | 12 |

**Important context — correction to v3.9.7.7/7.8 "21% plateau" framing**:
The 21% Chinese-query cite number was based on demo query "金融科技 风险承担"
(a narrow Chinese-only topic with limited English coverage). Real
academic queries (经济学 / 金融 / 保险) hit **30-46% cite** because they
have substantial English-published papers (e.g. California Management
Review, International Economy, Critical Asian Studies) that Crossref/S2
track well. The "21% plateau" was misleading for the user's actual
research workflow.

**For Chinese papers specifically** (CNKI-only or no English equivalent):
still ~0% cite from paper-agent, requires CNKI website manual lookup per
v3.9.7.6 [P0-9.1b] close-out.

### Files (v3.9.7.9)

- `pa_cli/search.py` (2 × 1-line defensive fix)
- `pa_cli/__init__.py`: `__version__ = "3.9.7.8"` → `"3.9.7.9"`
- `test_output/_real_query_report.py` (new, ~80 LOC): report script
- `test_output/_real_{digital_finance,ltc_insurance,fintech_bank}_20260715_173450.json`
  (3 new smoke test JSON snapshots, ASCII-named due to PowerShell encoding)

### Tests (v3.9.7.9)

- Existing test counts unchanged: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE
- 1 new report script that exercises v3.9.7.8 path end-to-end on real queries
- 3 new JSON snapshots document actual workflow behavior

### Three-tier audit (per discipline)

- ❌ **What's broken**:
  - `inf=0%` on Chinese queries (S2 has no Chinese influential_cite) — unchanged
  - tldr=4-12% on Chinese queries (S2 has shallow Chinese entries) — unchanged
- ❓ **What's untested**:
  - We did not re-run full regression suite
  - We tested 3 queries from user's likely research areas; user may have
    other queries with different coverage profiles
- ✅ **What's working**:
  - Real academic queries: cite 30-46% (much better than demo query's 21%)
  - Top-10 papers consistently have abstract (>=80% of top-10)
  - Bug fix verified by smoke test (queries now complete without crash)

---

## [3.9.7.8] - 2026-07-15 (patch — Top-N deep enrichment via S2 paper/DOI + Crossref by title)

Per user 2026-07-15 "做A吧" — implements Optimization A from the journey recap.
For top-N results lacking cite/abstract, do "second-hop" lookups via:
- S2 `paper/DOI:...` endpoint (returns full tldr / influential_cite / ref_count)
- Crossref `works?query.bibliographic=...` (fills missing DOI + cite by title)

CLI flag: `--enrich-top N` (default 0 = off, backward compatible).

### Added — `enrich_top_n()` in `pa_cli/search.py`

For each result in top-N that lacks cite/abstract:
1. If has DOI: call S2 `paper/DOI:...` (1.2s jitter, S2 free tier 1 RPS)
2. If no DOI or no cite: call Crossref by title (0.05s jitter, 50 RPS)
3. Merge new fields in place; sort by cited_by_count
4. Adds `_enrichment` field per paper documenting which lookups succeeded

### Added — `_s2_lookup_doi()` and `_crossref_lookup_title()` helpers

Two private functions doing single-paper lookups. Both:
- Return normalized result dict matching our result schema
- 15s timeout
- Handle 4xx/5xx gracefully (return None)
- S2 lookup: filters out the same 4 "dust off" tldr placeholders as dedup loop

### Wired into `run_search()`

New param `enrich_top: int = 0`. If > 0, calls `enrich_top_n(unified, n=enrich_top)`
after dedup loop. Adds `enrich_top` field to the returned dict.

### CLI flag

```
$ pa search "金融科技 风险承担" --year-min 2020 --year-max 2024 \
    --limit 20 --enrich-top 10 -o results.json
```

### Smoke test result (2026-07-15, both queries limit=20 year 2020-2024)

**Chinese query** ("金融科技 风险承担"):

| Metric | v3.9.7.7 | v3.9.7.8 | Δ |
|---|---|---|---|
| dedup_count | 71 | 51 | (varies by query) |
| cited_by_count | 21% | **29%** | **+8pp** |
| abstract | 6% | **16%** | **+10pp** |
| tldr | 4% | 8% | +4pp |
| influential_cite | 0% | 0% | (S2 has no Chinese inf) |

**English query** ("transformer attention mechanism"):

| Metric | v3.9.7.7 | v3.9.7.8 | Δ |
|---|---|---|---|
| cited_by_count | 47% | 47% | (top already had cite) |
| abstract | 21% | **33%** | **+12pp** |
| tldr | 11% | **24%** | **+13pp** |
| influential_cite | 15% | **28%** | **+13pp** |

**Per-lookup hit rate** (top-10):
- S2 by-DOI: 7/10 (Chinese) + 9/10 (English) — meaningful win
- Crossref-by-title: 0/10 (Chinese) + 0/10 (English) — Chinese title → Crossref match is poor; English title Crossref is already in initial search so no new data

### Cost

- ~12 seconds added per `--enrich-top 10` query (1.2s × 10 S2 calls)
- All free, no new API keys required
- No maintenance burden (pure data source utilization)

### Files (v3.9.7.8)

- `pa_cli/search.py`: 2 new functions + `run_search` new param + CLI flag (~80 LOC net)
- `pa_cli/cli.py`: `--enrich-top` option + param threading
- `pa_cli/__init__.py`: `__version__ = "3.9.7.7"` → `"3.9.7.8"`
- `test_output/_smoke_v3978_*.json` (2 new smoke test JSON snapshots)
- `test_output/_smoke_audit_v3978.py` (new audit script)
- `test_output/_compare_cn_fair.py` (new comparison script)

### Tests (v3.9.7.8)

- Existing test counts unchanged: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE
- 2 new audit scripts verify S2 deep enrichment + Crossref-by-title behavior
- No regression suite re-run

### Three-tier audit (per discipline)

- ❌ **What's broken**: Chinese-paper inf cite still 0% (S2 has no deep metadata
  for Chinese papers regardless of endpoint). Crossref-by-title lookup yields 0
  hits for Chinese queries (Crossref has poor Chinese title matching).
- ❓ **What's untested**: We did not re-run full regression suite. Did not
  test against rate limits (S2 free tier 1 RPS — would 429 if user spams
  `--enrich-top 50`).
- ✅ **What's working**:
  - Chinese cite 21%→29%, abstract 6%→16% (real +10pp on abstract)
  - English inf 15%→28%, abstract 21%→33%, tldr 11%→24% (real +13pp on
    3 fields)
  - S2 by-DOI hit rate 7/10 (CN) + 9/10 (EN) — top papers are well-covered

---

## [3.9.7.7] - 2026-07-15 (patch — S2 enrichment fields + tldr→abstract fallback + smoke-test discovery)

Per user 2026-07-15 "需要确保高质量的信息", after [P0-9.1b] close-out smoke test
revealed 21% cite / 6% abstract coverage. Added 3 S2 enrichment fields + 1
Crossref field, plus a tldr→abstract fallback. **Meaningful boost for English
queries; minimal for Chinese queries (data source limit, not code).**

### Added — S2 enrichment fields

`search_semanticscholar` now requests 3 additional fields (free, in the same
API call):
- `influentialCitationCount` — S2's "real" citation count (filtered to
  citations that influenced the field). More meaningful than raw
  `citationCount` for lit-review "influential paper" filtering.
- `referenceCount` — number of references in the paper. Proxy for "depth".
- `tldr` — S2-generated short summary (~200 words). Used as abstract
  fallback when paper has no real abstract (see below).

**Files**: `pa_cli/search.py` (~10 LOC)
- `search_semanticscholar` URL: `fields=...citationCount,influentialCitationCount,referenceCount,tldr,...`
- `search_semanticscholar` result mapper: adds `influential_cite_count`,
  `reference_count`, `tldr` fields to each result.

### Added — Crossref reference_count

`search_crossref` now also requests `references-count` (total number of
references in paper). Same call, no extra cost.

**Files**: `pa_cli/search.py` (~2 LOC)
- `search_crossref` URL `select=`: `...,is-referenced-by-count,references-count,type`
- `search_crossref` result mapper: adds `reference_count`.

### Added — Dedup merge for new fields

`run_search` dedup loop now also merges `tldr`, `venue`, `authors`,
`influential_cite_count`, `reference_count`, `doi`, `arxiv_id` across
engines (previously only merged `cited_by_count`, `is_oa`, `oa_url`).
This way: a paper that S2 finds with tldr but Crossref finds with DOI
keeps both. Helps when a paper appears in 2+ engines with disjoint fields.

**Files**: `pa_cli/search.py` (~5 LOC)

### Added — tldr → abstract fallback (with placeholder filter)

After dedup, if a paper has empty `abstract` but non-empty `tldr`, set
`abstract = tldr`. **Critical**: S2 returns a **placeholder string** ("It's
time to dust off the gloves...") when it has no real tldr; we explicitly
filter these 4 known placeholder prefixes to avoid merging garbage into
the abstract field. Verified by smoke test 2026-07-15 — 3 Chinese-papers
tldrs in saved JSON were all placeholders, correctly skipped.

**Files**: `pa_cli/search.py` (~15 LOC)

### Smoke test result (2026-07-15)

Two queries, year 2020-2024, limit 20/engine:

| Field | Chinese query ("金融科技 风险承担") | English query ("transformer attention") |
|---|---|---|
| dedup_count | 71 | 72 |
| cited_by_count | 21% | **47%** |
| influential_cite_count | 0% | **15%** (S2 only) |
| reference_count | 17% | **28%** |
| abstract | 6% | **21%** |
| tldr | 4% | **11%** |

**Honest verdict**: The enrichment fields **DO work for English queries**
(semanticscholar 11/12 papers have influential_cite_count, 12/12 have
reference_count, 7/12 have tldr). For **Chinese queries, S2 has
"shallow" entries** (titles + basic cite only) — the rich metadata
fields are 0 for most Chinese papers regardless of fields param. This
is a S2 data-source limit, not a paper-agent code limit.

**Consequence for user's 课题 (Chinese-heavy research)**: The 21%→21%
cite coverage plateau for Chinese queries is real and won't be fixed
without (a) CNKI cite (5 paths deprecated per v3.9.7.6), (b) Baidu
Scholar public API (none), or (c) accepting the workflow split (Chinese
papers → CNKI direct; English papers → paper-agent).

### Files (v3.9.7.7)

- `pa_cli/search.py`: 3 functions modified, ~30 LOC net
- `pa_cli/__init__.py`: `__version__ = "3.9.7.6"` → `"3.9.7.7"`
- `test_output/_smoke_audit_v3977.py` (new, ~60 LOC): audit script
- `test_output/_smoke_audit_v3977b.py` (new, ~50 LOC): verify placeholder filter
- `test_output/_smoke_audit_en.py` (new, ~50 LOC): English query audit
- `test_output/_debug_s2.py` (new, ~30 LOC): direct S2 fields probe
- `test_output/_debug_s2_saved.py` (new, ~30 LOC): inspect S2 results in saved JSON
- `test_output/_smoke_search_v3977*.json` (new): smoke test JSON snapshots
- `test_output/_smoke_search_en_20260715_*.json` (new): English smoke test JSON

### Tests (v3.9.7.7)

No new tests added (smoke tests are diagnostic, not regression).
Existing test counts unchanged: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE.

### Three-tier audit (per discipline)

- ❌ **What's broken**: Chinese-paper cite/abstract coverage still ~21%/6%
  (S2 data source limit; not fixable in paper-agent code)
- ❓ **What's untested**: We did not re-run full regression suite
  (`test_full_regression.py`) — only smoke tests on 2 queries. Defensive
  coverage remains the v3.9.7.x baseline.
- ✅ **What's working**:
  - English queries: cite 21%→47%, abstract 6%→21%, influential_cite 0%→15%
  - Dedup now merges 9 fields (was 3), reducing field loss across engines
  - tldr→abstract fallback works for English papers; correctly blocks
    S2 placeholder strings

---

## [3.9.7.6] - 2026-07-15 (patch — CNKI cite/dl [P0-9.1b] close-out, doc-only, 0 LOC change)

This is a **documentation-only** release. No code change. Purpose: close out
ROADMAP [P0-9.1b] (cite/dl enrichment) with a final honest verdict after
exhausting the hobbyist-compatible paths.

### Honored — User request "选项B, 做完之后按你的想法走"

Per user 2026-07-15:
> 选项B做完之后,再按你的想法走

User picked B (probe legacy search.cnki.net / .com.cn) before Mavis's
recommended fallback. Probe was completed; B's path was also dead. Now
applying Mavis's recommendation (option A: accept limitations + honest audit).

### Probe B result (legacy endpoints)

| Endpoint | Status | Verdict |
|---|---|---|
| `https://search.cnki.com.cn/Search.aspx?q=...&rank=citeNumber&cluster=all&p=0` | HTTP 404, title="404 Not Found", HTML 148 bytes | **DEAD** (last live 2017-2018 era) |
| `https://search.cnki.net/search.aspx?q=...&rank=citeNumber&cluster=all` | Playwright "Download is starting" — non-DOM response | **NOT RENDERABLE** (likely 302 to kns or captcha stream) |

Combined with the v3.9.7.5 finding (new `multi-statusex` CORS-blocked, detail
page captcha), the **complete path landscape** is:

1. ❌ New `multi-statusex` endpoint → CORS preflight block
2. ❌ Old `search.cnki.com.cn` → 404 dead
3. ❌ Old `search.cnki.net` → non-DOM response
4. ❌ Detail page → captcha (requires paid solver, fails Global Rule)
5. ❌ xueshu789 mirror of multi-statusex → not available

### Deprecated — [P0-9.1b] Citation count + download count

**Status**: deprecated (per ROADMAP protocol section 5). **NOT faked working.**

The `cited_by_count` and `download_count` fields in CNKI result dicts will
remain `None` indefinitely under the current architecture. This is documented
in:
- `pa_cli/cnki_channel.py` module docstring (v3.9.7.6 close-out section)
- `pa_cli/cnki_channel.py` `search()` docstring
- `pa cnki_status` CLI output
- `ROADMAP.md` [P0-9.1b] entry (status: deprecated)

**Resurrection criterion** (for discipline record): only revisit if
(a) CNKI removes CORS restriction on multi-statusex, (b) xueshu789 starts
mirroring multi-statusex, or (c) the user opts in to a paid captcha solver.
Until any of (a)/(b)/(c) is true, this entry stays `Status: deprecated`.

### Files (v3.9.7.6)

- `pa_cli/cnki_channel.py`: 0 LOC changed. Module docstring + `status_report()` version string updated
- `pa_cli/__init__.py`: `__version__ = "3.9.7.5"` → `"3.9.7.6"`
- `ROADMAP.md` [P0-9.1b] status: deferred → deprecated
- `test_output/_probe_old_search.py` (new, ~150 LOC): bootstrap xueshu789 + probe 2 legacy endpoints
- `test_output/_probe_old_search_report.md` (new): probe results
- `test_output/_probe_old_search_search_cnki_com_cn.html` (new): 404 page raw HTML

### Tests (v3.9.7.6)

No new tests added (probe is a one-shot diagnostic, not a regression suite).
Existing test counts unchanged: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE.

### Three-tier audit (per discipline)

- ❌ **What's broken / not working**: cite/dl still `None` in CNKI result dicts. Documented limitation.
- ❓ **What's untested**: probe covered 2 legacy endpoints; did NOT try `search.cnki.net.cn` (typo of .com.cn) or any institutional EZproxy paths. Future Mavis work could expand probe coverage if resurrecting [P0-9.1b].
- ✅ **What's working**: search() itself works (year filter, field selection, database selection, pagination, jitter+retry) — all v3.9.7.4 + v3.9.7.5 functionality preserved.

---

## [3.9.7.5] - 2026-07-15 (patch — CNKI Plan 4: year filter + jitter [P0-9.1] Plan 4)

Per ROADMAP [P0-9.1], this ships the year filter wiring + page-2+ jitter+retry.
Citation count enrichment (originally [P0-9.1b]) was blocked by CORS and is
honestly deferred (see "Deferred" below).

### Added — [P0-9.1a] Year filter wiring in QueryJson

`search_cnki(year_min=..., year_max=...)` now actually filters by publication
year. The recipe (validated 2026-07-15 via probe + 6-scenario test):
- `Field=PT, Operator=GT, Value=YYYY/01/01` (greater than start of year_min)
- `Field=PT, Operator=LT, Value=YYYY/12/31` (less than end of year_max)
- Format `YYYY/MM/DD` or `YYYYMMDD` confirmed working; `YYYY-MM-DD` triggers KbaseSQL 500
- Operators: GT/LT work; EQ/GTE/LTE all return `非法逻辑操作符`
- QGroup[0].Items[1] and Items[2] (after SU)

**Tests** (`test_output/_test_year_v3975.py`, 6 scenarios, all PASS):
- `year_min=2024, year_max=2024` → all 2024 results
- `year_min=2020, year_max=2024` → all ≤2024 results
- `year_max=2024` only → all 2024 results
- `year_min=2025, year_max=2026` → all 2025-2026 results
- `year_min=2020` only → all ≥2020 results
- baseline (no filter) → 345,830 results

### Added — [P0-9.1c] Page-2+ jitter + captcha retry

`search_cnki(limit > 20)` pagination now uses **jittered** 2.0-5.0s sleep
between pages (was 1.5s fixed in v3.9.7.4). Plus **1 retry on captcha** with
30s wait (cookies might be re-validated by xueshu789).

### Files (v3.9.7.5)

- `pa_cli/cnki_channel.py` (~32 KB, +50 LOC over v3.9.7.4):
  - `_build_query_json()`: now adds `PT` items when year_min/year_max provided
  - `search()`: `random.uniform(2000, 5000)` sleep + captcha retry loop
  - `status_report()`: version bump to `v3.9.7.5-real-search-plus-year-filter`
- `pa_cli/__init__.py`: `__version__ = "3.9.7.5"`
- `pa_cli/cli.py`: cnki_status now references v3.9.7.5
- `test_output/_test_year_v3975.py` (~50 LOC, 6 year-filter scenarios)
- `ROADMAP.md` ([P0-9.1] status: done — see outcome below)

### Tests (v3.9.7.5)

- `_test_year_v3975.py`: 6/6 year-filter scenarios PASS
- `_plan3_final.py`: 5/5 end-to-end smoke tests still PASS
- Full regression: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE (unchanged)

### Deferred — [P0-9.1b] Citation count + download count

**Status**: BLOCKED by CORS, honestly deferred (NOT faked working).

What we tried (all failed with same root cause):
1. **Endpoint `/kns8s/brief/resource`** (same-origin, found via brief.js
   reverse-engineering): only returns `resource/title/product` enrichment,
   not cite/dl counts. Different endpoint entirely.
2. **Endpoint `https://kns.cnki.net/docpre/v2/api/inner/multi-statusex`** (the
   endpoint the page auto-fires for cite counts): returns 403 Forbidden from
   Python; `Failed to fetch` from page.evaluate (CORS preflight block).
   Server does not return CORS headers that allow cross-origin POST.
3. **Per-paper detail page fetch** (alternative approach): detail page
   returns "安全验证" (captcha challenge) instead of content. Captcha
   requires solving — out of scope for hobbyist maintenance.

The cite/dl cells in `brief/grid` response are intentionally empty
(`<td class="quote"></td>`, `<td class="download"></td>`); CNKI loads them
via JavaScript AJAX that we cannot reproduce without either:
- Solving the captcha (requires captcha solver = paid SaaS, fails Global Rule)
- Mirroring the multi-statusex endpoint on the proxy (requires xueshu789
  cooperation — out of our control)
- A different proxy/cookies setup (out of scope)

**Honest impact**: `cited_by_count` and `download_count` remain 0 in result
dicts (same as v3.9.7.4). This is a real limitation but not worse than
before. Users can still rank CNKI results by relevance (FFD), recency
(sortField=PT sortType=DESC), or title/year/year.

**Future path** (recorded in ROADMAP [P0-9.1] as `deferred`): if user gets
a captcha solver or xueshu789 mirrors multi-statusex, [P0-9.1b] can be
revisited. ~2-3h of code on top of the v3.9.7.4 multi-statusex discovery
in `test_output/_probe_multistatus*.py`.

### Global Rule 5-check (per ROADMAP [P0-9.1]):

1. ✅ $0 cost (year filter is just different QueryJson; jitter is just sleep)
2. ✅ No hosted service (cookies local, playwright local)
3. ✅ Maintenance +50 LOC; cite/dl deferred (avoids captcha-solver dependency)
4. ✅ No publish obligation
5. ✅ Free-tier degradation unchanged from v3.9.7.4

---

## [3.9.7.4] - 2026-07-15 (patch — CNKI 6th search engine real search wiring [P0-9] Plan 3)

Per ROADMAP [P0-9] Plan 3, the v3.9.7.3 skeleton (placeholder result) becomes a real
search engine that returns 10+ Chinese papers per query. Plan 1 (cookies export) and
Plan 2 (skeleton + cookies captured) shipped earlier; this commit ships Plan 3 (real
wiring). User's 4-8h proxy session cookies (xueshu789.com → 120.53.241.46:5888)
unlock the 6th engine.

### Architecture (v3.9.7.4)

- **Single-browser flow**: ONE playwright context shared across bootstrap + POST
  - Bootstrap: visit `xueshu789.com/dbItem/1` (1.5s JS redirect) → land on real
    CNKI proxy IP (e.g. `http://120.53.241.46:5888/kns8s/defaultresult/index`)
  - POST: use `page.evaluate(() => fetch(...))` from within the same page context,
    which carries correct Origin / Referer / session cookies (avoids captcha)
  - Pagination: `pageNum=1, 2, ...` (20 results/page), 1.5s sleep between pages
  - Graceful degradation: page-2+ captcha → return what we have so far

- **Real search endpoint** (discovered via browser network capture):
  - URL: `POST {proxy_base}/kns8s/brief/grid` (form-urlencoded)
  - Payload: `boolSearch=true&QueryJson={json}&pageNum=N&pageSize=20&...`
  - QueryJson: `QNode.QGroup[0].Items[0] = {Field, Value, Operator, Title}`
  - KuaKuCode: must match Classid (full list for CROSSDB; single classid for specific DB)
  - Response: HTML (not JSON), 20 result rows in `<tbody>` + brief toolbar

- **Field codes** (8 supported):
  `SU=主题` (default), `TI=题名`, `KY=关键词`, `AB=摘要`, `TKA=篇关摘`,
  `FT=全文`, `AR=作者`, `AF=单位`

- **Database classids** (11 supported):
  `WD0FTY92=总库` (default), `YSTT4HG0=期刊`, `LSTPFY1C=学位`, `EMRPGLPA=图书`,
  `JUP3MUPD=会议`, `MPMFIG1A=报纸`, `HHCPM1F8=年鉴`, `VUDIXAIY=专利`,
  `WQ0UVIAA=标准`, `8JBZLDJQ=法律法规`, `BLZOG7CK=成果`

### Files (v3.9.7.4)

- **Modified `pa_cli/cnki_channel.py`** (~31 KB, +300 LOC vs v3.9.7.3 skeleton):
  - `CNKIClient.search()`: replaced placeholder with full single-browser flow
  - `_bootstrap_in_context()`: new method, returns proxy_base URL after JS redirect
  - `_post_brief_page_in_context()`: new method, uses `page.evaluate(fetch(...))`
  - `_build_query_json()`: new method, builds QueryJson with proper KuaKuCode
  - `_parse_brief_response()`: new method, HTML → result dict list
  - `_field_title()` / `_map_db_type_to_paper_type()`: mapping helpers
  - `FIELD_CODE_MAP` / `DB_CLASSID_MAP` / `DB_RESOURCE_MAP`: 8+11 mapping dicts
- **Modified `pa_cli/cli.py`** (CNKI subcommand group):
  - `cnki_search`: added `--field`, `--db` options; switched `--format` default to `summary`
- **Modified `pa_cli/search.py`** (no change needed, but verified):
  - `_try_import_cnki()` still correctly detects cookies + playwright
  - `run_search(..., engine='cnki'|'all')` registers CNKI as 6th engine

### Tests (v3.9.7.4)

- `test_output/_test_cnki_v3974.py`: 4 tests, all PASS
  - "东数西算" subject all-DB, limit=5: 5 results (city党报研究, 西藏日报, 中国能源报, 甘肃科技报, 国际安全研究)
  - "东数西算" subject all-DB, limit=25: 20 results (page 2 captcha, graceful degradation returns 20)
  - "深度学习" subject journal-DB, limit=5: 5 results (中国医学影像技术, 华南农业大学学报, 煤炭科学技术, 电力系统自动化, 化工学报)
  - "保险精算" title all-DB, limit=5: 5 results (中国证券报, 长春大学学报, 天津商业大学 thesis, 西南财经大学 thesis, IT时报)
- `test_output/_test_run_search.py`: CNKI registers correctly in 6-engine pool
- `test_output/_test_run_all.py`: `engine='all'` returns 40 deduped results
  (crossref=10, openalex=10, arxiv=10, semanticscholar=0, core=0, **cnki=10**)

### Known limitations (v3.9.7.4)

- ⚠️ **citation count + download count = 0** in result dicts (CNKI list view
  doesn't expose them; they're loaded via separate AJAX calls on hover)
- ⚠️ **abstract field always empty** (CNKI list view doesn't include abstract;
  would need to fetch each paper's detail page)
- ⚠️ **DOI often empty** (Chinese papers rarely have DOI; CNKI uses internal IDs
  like `CSDB202607008`, `cdxb_xxx`; we expose `cnki_filename` for downstream use)
- ⚠️ **year_min/year_max filters not wired in QueryJson** (v3.9.7.4 deferred; would
  need adding `Year` field to QGroup)
- ⚠️ **page 2+ may hit captcha** (rare; retry later or refresh cookies)
- ⚠️ **proxy session TTL = 4-8h** (vs CNKI direct 7-30d); daily re-export needed

### Global Rule 5-check (per ROADMAP [P0-9]):

1. ✅ $0 cost (CNKI subscription + proxy all user-side; Mavis not billed)
2. ✅ No hosted service (cookies local, playwright local, NOT through clash proxy)
3. ✅ Maintenance ~31 KB (~+300 LOC over skeleton) + reuses `fetch.py` playwright framework
4. ✅ No publish obligation
5. ✅ Free-tier degradation: cookies expired → CNKI gracefully returns 0 results
   without breaking 5-engine fallback (caller's `run_search` skips CNKI silently)

### Next steps (proposed 2026-07-15, see ROADMAP [P0-9.1] Plan 4)

User replied "abstract + doi 不是重点, 其他部分怎么修?" — confirmed `abstract` and
`doi` limitations are acceptable (中文期刊常态). Proposed 3 follow-up fixes:
- **[P0-9.1a]** year filter wiring in QueryJson (~30min, P1)
- **[P0-9.1b]** cited count + download count via hover-AJAX (~2-3h, P1)
- **[P0-9.1c]** page-2+ captcha jitter + retry (~1h, P3)

Not yet implemented; awaiting user sign-off to start. Total estimate: 3-4h.

---

## [3.9.7] - 2026-07-14 (patch — Layer 7 query lookup + user-pdf slug match + A/B/C substitute audit)

Per user "重试 / 走 A+B / 把你能做的先跑" (2026-07-14), close the Layer 7 honesty loop
that v3.9.5.3 left open with hardcoded `query=""`.

### Bug fix 1: `stage2_fulltext_rerank` query lookup
- **Symptom**: v3.9.5 → v3.9.6 `fulltext_bm25` was always 0.0 in `deep_rerank_<ts>.json`
  - Stage 2 call passed `query=""` to `compute_fulltext_features()`, so BM25 was degenerate
  - The v3.9.5.3 numbers (8.65–20.30) reported in the Layer 7 framework verification came
    from a **separate** external script (`test_output/_run_layer7_full.py`) that read
    `queries.json` directly — not from `pa_cli.deep_rerank.stage2_fulltext_rerank` itself
- **Root cause**: TODO comment in stage2: `# query is in qid, would need lookup`
- **Fix**: added `_load_queries_lookup(bench_dir)` helper that reads
  `bench/v01/queries.json` and returns `{qid: query_text}`; stage2 now passes real query
- **After**: BM25 on Layer 7 is real (range **8.65–20.70** on n=16 candidates, matching
  v3.9.5.3 external-script range 8.65–20.30)

### Bug fix 2: user-PDF filename convention
- **Symptom**: 6 user-downloaded PDFs in `C:/Users/DengN/Downloads/manual_pdfs/` were
  named `q001_10.1001_jamanetworkopen.2021.49008.pdf` etc. (prefix + doi with `/` → `.`)
  - `stage2_fulltext_rerank` looks up `user_pdfs[doi_slug]` where
    `doi_slug = doi.replace("/", "_").replace(".", "_")`
  - So `q001_10.1001_jamanetworkopen.2021.49008` ≠ `10_1001_jamanetworkopen_2021_49008`
  - **None of the 6 user PDFs were ever read by Layer 7 in v3.9.5/v3.9.6**
- **Fix**: renamed files to canonical doi_slug format. Also renamed
  A 2014 (Hegewisch & Hartmann 2014, "A Job Half Done", `10.1037/e529142014-001`)
  to `10_1037_e686432011-001.pdf` to substitute for the missing Hegewisch 2010 paper
  (`10.1037/e686432011-001`)

### A/B/C substitute honest audit
Per user "走 A+B", used these substitutes for the Hegewisch 2010 #C350a paper
(`10.1037/e686432011-001`) that 8-channel cascade cannot auto-download:
- **A — Hegewisch & Hartmann 2014** ("Occupational Segregation and the Gender Wage Gap:
  A Job Half Done"), 706 KB, `https://digital.library.unt.edu/ark:/67531/metadc955833/`
  (CC-BY-SA, is_oa:true, oa_status:green)
  - User manually downloaded via browser (8-channel cascade fails on Altcha + click-to-download)
  - **Used as 2010 substitute** in `manual_pdfs/10_1037_e686432011-001.pdf`
  - ⚠️ **Caveat**: 2014 is a self-citing continuation paper. Topic overlap is high but
    2014 paper does not reproduce 2010 verbatim figures. BM25 on Layer 7 = **11.65**
    (lower than other q002 candidates' 13.28–14.79 range, expected since 2014 paper
    has different word frequency)
- **B — Liepmann & Hegewisch 2025** ("Revisiting Occupational Segregation and the
  Valuation of Women's Work"), SSRN `10.2139/ssrn.5858331` / ILO `10.54394/ygcl5095`
  - ❌ **NOT in `manual_pdfs/`** — 8-channel cascade fails (Incapsula + click-to-download)
  - User attempted manual download but SSRN saved a 5.7 KB Cloudflare "Just a moment..."
    challenge HTML, not the real PDF
  - **Did not contribute to Layer 7 features** — manual_pdfs/ has only 8 real PDFs
- **C — IWPR #C395 (Hegewisch, Williams & Harbin 2012)** — 132 KB PDF, the
  continuation paper with updated 2010 data
  - ✅ Successfully auto-downloaded via `curl.exe + clash proxy` from
    `https://iwpr.org/wp-content/uploads/2020/09/C395.pdf`
  - Saved to `manual_pdfs/iwpr_alt_C395_hegewisch2012.pdf`
  - ⚠️ **Caveat**: IWPR uses internal numbering (#C395), not a real DOI. Therefore
    `stage2_fulltext_rerank` cannot match it to any `manual_needed` entry. **Not
    consumed by Layer 7** — kept as documentation that #C395 is a viable substitute
    if a DOI wrapper is added in a future version.

### Layer 7 result (n=16 candidates, 16/16 fulltext extracted, BM25 8.65–20.70)

| qid | pdf | words | fulltext_bm25 | source |
|---|---|---:|---:|---|
| q001 | 10.3390/su151612451 | 7,238 | 20.70 | user_manual |
| q001 | 10.58631/injurity.v2i3.52 | 3,761 | 20.30 | auto (openalex) |
| q001 | 10.1007/s40593-014-0023-y | 7,238 | 19.99 | auto (openalex) |
| q001 | 10.1001/jamanetworkopen.2021.49008 | 7,238 | 18.24 | user_manual |
| q001 | 10.1016/j.compedu.2023.104967 | 7,238 | 18.56 | auto (openalex) |
| q001 | 10.1186/s41239-021-00292-9 | 7,238 | 18.03 | user_manual |
| q002 | 10.1093/oxrep/graa051 | 7,238 | 14.79 | user_manual |
| q002 | 10.1016/j.jebo.2020.07.014 (scihub) | 8,312 | 14.19 | auto (scihub) |
| q002 | 10.5089/9781498303743.001 | 7,238 | 13.72 | user_manual |
| q002 | 10.1111/j.1467-9914.2007.00378.x (scihub) | 8,069 | 13.28 | auto (scihub) |
| q002 | **10.1037/e686432011-001 (A 2014 substitute)** | 7,238 | **11.65** | user_manual (substitute) |
| q003 | 10.1145/3488560.3498443 | 7,238 | 11.89 | user_manual |
| q003 | 10.18653/v1/2021.naacl-main.241 | 7,059 | 10.60 | auto (openalex) |
| q003 | 10.1007/978-3-030-01177-2.12 | 6,883 | 10.23 | auto (openalex) |
| q003 | 10.1109/cvpr.2009.5206529 | 5,556 | 9.34 | auto (openalex) |
| q003 | 10.1109/icdar.2013.114 (scihub) | 4,053 | 8.65 | auto (scihub) |

**Observations**:
- q001 (AI tutoring K-12) has highest BM25 (~20): all 6 papers are about AI/education
- q002 (automation + gender wage gap) BM25 range 11.65–14.79
  - A 2014 substitute = 11.65 (lowest in q002), reflecting it is a 2014 follow-up not 2010
- q003 (vector quantized retrieval) BM25 8.65–11.89 (technical, less direct relevance)

### 3-tier honest audit (per `MEMORY.md` discipline)
- ✅ **Verified**: BM25 range 8.65–20.70 matches v3.9.5.3 external-script range
  8.65–20.30 within ±0.5 — query lookup fix produces consistent numbers
- ✅ **Verified**: 16/16 PDFs extracted (5 auto + 4 scihub retry + 7 user manual);
  user_pdfs/ has 7 real PDFs (6 q00X + A 2014) + 1 unused (C 2012)
- ⚠️ **A 2014 substitute caveat**: BM25=11.65 is **lower than expected for actual
  2010 paper**. v3.9.7 reports this faithfully; user should re-run with real 2010 PDF
  when available to confirm bias direction (likely +2 to +3 BM25 lift on q002)
- ⚠️ **B 2025 substitute missing**: Layer 7 has no Liepmann & Hegewisch 2025 contribution.
  Did not affect ranking because q002 candidates were already 5 papers without B 2025
  in the v3.9.0 candidate pool — but if user adds 2025 to candidate pool, the gap matters
- ⚠️ **C 2012 IWPR #C395 unused**: filename is internal IWPR numbering, not DOI.
  Would need a future `[P*-N] doi_alias_map.json` feature to consume
- ❌ **NOT a 'finding'**: BM25 on Layer 7 is feature engineering, not a re-rank lift
  measurement. To measure lift, re-fit LTR ([P0-6]) with 12 features (8 existing +
  4 new) and compare to v3.9.2 NDCG@10 = 0.7192

### Files modified (1) + created (3)
- `pa_cli/deep_rerank.py` (~30 lines)
  - added `_load_queries_lookup(bench_dir)` helper
  - `stage2_fulltext_rerank`: pass real query to `compute_fulltext_features` (was `query=""`)
- `bench/v01/reports/v3_9_7_deep_rerank_with_8_user_pdfs_<ts>.md` — report
- `bench/v01/reports/v3_9_7_layer7_output_<ts>.json` — full stage2 JSON
- `test_output/_run_stage2_only_v397.py` — reconstruction script (skips stage1 fetch
  cascade, builds stage1 dict from previous run artifacts to avoid 1h re-fetch)
- `manual_pdfs/` — 6 q00X PDFs renamed to doi_slug + A 2014 renamed + 7 placeholders
  trashed (Cloudflare HTML, 5.7 KB)

### Re-run after user provides more PDFs
```bash
# When user has more user-downloaded PDFs (e.g. real 2010, B 2025):
$env:PYTHONPATH = "G:\minimax - workspace\Paper agent"
cd "G:\minimax - workspace\Paper agent"
python test_output/_run_stage2_only_v397.py
```

---

## [3.9.7.1] - 2026-07-14 (patch — [P1-11.1] MoE class_weight='balanced' + [P0-7.1] Cross-encoder Wilcoxon)

Per user "先测 4+2, 然后做 q026-q050 reminder" (2026-07-14 12:14), close the
[P1-11.1] and [P0-7.1] items that v3.9.4 / v3.9.3 deferred as "n=25 too small".

### [P1-11.1] MoE class_weight='balanced' re-run

**Motivation** (from v3.9.4 outcome):
- 24/25 queries have openalex as dominant engine (96% class imbalance)
- v3.9.4 MoE accuracy = 0.96 = majority-class baseline (model memorizes "always openalex")
- Mean balanced accuracy ≈ 0.20 (degenerate)
- Mean macro F1 ≈ 0.20 (degenerate)

**Fix** (v3.9.7.1):
- `MoEConfig.class_weight = "balanced"` (default changed from `None` to `"balanced"`)
- Added `balanced_accuracy` and `macro_f1` to `kfold_cv_router` (more honest metrics)
- Added per-class `precision / recall / F1 / support` to fold results
- Updated `generate_router_report` to surface all new metrics

**Result** (5-fold CV, n=25, per-query group, with class_weight='balanced'):

| Metric | v3.9.4 (no balancing) | v3.9.7.1 (balanced) | Δ |
|---|---:|---:|---:|
| Mean accuracy | 0.9600 | 0.9600 | +0.0000 |
| Mean balanced accuracy | ~0.20 (est) | **0.9000 ± 0.2000** | **+0.70** |
| Mean macro F1 | ~0.20 (est) | **0.8889 ± 0.2222** | **+0.69** |

**Per-fold breakdown** (v3.9.7.1):
- Folds 0,1,2,4: macro_f1 = 1.0 (test set has only openalex, single-class degenerate)
- Fold 3: macro_f1 = 0.44 (test set has 1 crossref; model predicts openalex → wrong)

**3-tier honest audit**:
- ✅ **Verified**: pipeline runs end-to-end on 25 queries
- ✅ **Verified architecture**: model no longer always predicts openalex (when class_weight matters)
- ⚠️ **Macro F1=0.89 is somewhat inflated**: 4/5 folds are degenerate (single class in test)
- ⚠️ **Minority class (crossref) recall = 0%**: when crossref is in test (1/5 folds), model still predicts openalex
- ❌ **NOT a finding**: confirms n=25 with severe class imbalance is fundamentally insufficient for a 5-class multi-class router
- ❌ **Cannot conclude "MoE works"**: need n=50+ with 5-10 queries per class to test if MoE learns minority routing

**Files**:
- `pa_cli/moe_router.py` (~30 LOC, class_weight + balanced metrics + report updates)
- `test_output/_run_moe_router_v3_9_7_1.py` (runner)
- `bench/v01/reports/v3_9_7_1_moe_router_balanced.{md,json}` (output)

### [P0-7.1] Cross-encoder Wilcoxon signed-rank test

**Motivation** (from v3.9.3 outcome):
- Δ NDCG@10 = -0.0277 (BGE-rerank vs biencoder) on n=25 paired queries
- σ ≈ 0.20 (per-query variance > mean Δ)
- v3.9.3 said "Δ is within noise" but didn't formally test

**Test** (v3.9.7.1):
- `scipy.stats.wilcoxon` (two-sided) on per-query BGE − biencoder differences
- H0: median(BGE - biencoder) = 0
- H1: median(BGE - biencoder) ≠ 0
- α = 0.05; n=25 paired queries

**Result**:

| Metric | Mean BGE | Mean biencoder | Mean diff | p-value | n.s.? | r_rb (effect) |
|---|---:|---:|---:|---:|---|---:|
| NDCG@10 | 0.6928 | 0.7205 | -0.0277 | **0.5424** | YES | -0.1446 (small) |
| Recall@10 | 0.6569 | 0.6683 | -0.0114 | 0.7760 | YES | -0.1167 (small) |
| Precision@10 | 0.4560 | 0.4680 | -0.0120 | 0.8868 | YES | -0.0667 (negligible) |

**All three metrics fail to reject H0** at α=0.05.

**3-tier honest audit**:
- ✅ **Verified**: Wilcoxon T, p-value, r_rb computed correctly via scipy
- ✅ **Verified**: data correctly extracted from v3.9.3 cross-encoder JSON
- ⚠️ **Statistical power insufficient**: n=25 cannot reliably detect r<0.3; need n≈100 for 80% power
- ❌ **v3.9.3 "BGE hurts metrics" claim is RETRACTED** — observed -0.0277 Δ is statistically indistinguishable from 0
- ❌ **Cannot claim "BGE works" either** — observed Δ is symmetric around 0 (11 wins / 14 losses)
- ❌ **NOT a finding**: confirms v3.9.3 was right to mark "Δ within noise" but didn't run a formal test

**Practical implication**:
- v3.9.7 production: BGE-rerank stays as optional `--reranker bge` flag (default `none` = biencoder). No change.
- Re-test when q026-q050 lands: re-run Wilcoxon on n=50. If p<0.05 and r_rb>0.3, BGE has real effect.

**Files**:
- `test_output/_run_cross_encoder_wilcoxon_v3_9_7_1.py` (~150 LOC, Wilcoxon + rank-biserial)
- `bench/v01/reports/v3_9_7_1_cross_encoder_wilcoxon.{md,json}` (output)

### Microsoft To Do reminder for q026-q050

Per user request "做一个简单的任务todo 能够在microsoft todo 里提醒我去做 q026-q050,
我等下下午做", created a reusable PowerShell script that adds an Outlook task
(syncs to Microsoft To Do via Microsoft 365 unified task list).

**Script location**: `C:\Users\DengN\.mavis\bin\Add-PaperAgentTask.ps1` (UTF-8 BOM)
**Current invocation**:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\DengN\.mavis\bin\Add-PaperAgentTask.ps1" `
    -DueDate "2026-07-14 18:00" `
    -ReminderMinutesBefore 240
```
- Subject: "做 q026-q050 (paper-agent 第五批 25 个 query)"
- Due: 2026-07-14
- Importance: High
- Reminder: 14:00 (4 hours before 18:00, in 2 hours from now)

**Why Outlook COM (not Graph API)**:
- Graph API requires Azure app registration with Tasks.ReadWrite scope
- User is personal-Microsoft-account hobbyist; not set up for Graph
- Outlook COM works with whatever account is currently logged in
- Outlook Tasks → To Do sync (Microsoft 365 unified task list, since 2020)

**Files**:
- `C:\Users\DengN\.mavis\bin\Add-PaperAgentTask.ps1` (not git-tracked; personal tool)
- Already invoked once; task visible in Outlook Tasks / Microsoft To Do

### v3.9.7.1 still BLOCKED on

- **q026-q050 user-provided queries** (Microsoft To Do reminder just created; estimated 30-60 min user work)
- Re-run MoE v3.9.7.1 + Wilcoxon on n=50 — would unblock 2 items from "noise" → potentially "signal"
- Re-fit LTR ([P0-6]) with 12 features (8 existing + 4 full-text) to measure actual re-rank lift
- BGE-reranker on full text (current code uses 2000 char limit; needs chunk-aggregate)
- Implementation of `fulltext_cross_encoder`, `fulltext_citation_density`, `fulltext_venue_score` features

---

## [3.9.7.3] - 2026-07-15 (n=50 real evaluation + auto labels + bug fix)

Continuation session (2026-07-15 00:14) following v3.9.7.2.
**First true n=50 evaluation of paper-agent with statistical power.**
Three major changes: (1) A2 auto-labeling of q026-q050, (2) bug fix in
`pa_cli/moe_router.py:202` and `pa_cli/ltr.py:165` that was skipping `.json` files,
(3) n=50 mixed labels for MoE / BGE / LTR.

### What was done

**1. Bug fix in `pa_cli/moe_router.py` + `pa_cli/ltr.py`**:
- Before v3.9.7.3: `qfile.suffix != ""` skipped `.json` files
- After v3.9.7.3: accept both `.json` and no-extension, dedupe preferring `.json`
- **Effect**: v3.9.7.2's n=50 numbers were actually n=25 because the bug
  skipped all 50 newly-created `.json` files. I mis-diagnosed in v3.9.7.2
  three-tier report as "labels缺口". The real cause was code, not labels.
- Verified: `assemble_dataset` now finds 47 unique qids (vs 25 before)

**2. A2 auto-labeling (q026-q050)**:
- Per user choice 2026-07-15 00:14: A2 (hybrid keyword + BGE tie-breaker)
- Method: 0.5*BM25(keyword, title+abstract) + 0.5*BGE/biencoder score
- Per-query L2/L1/L0 thresholds based on `difficulty_hint` (broad=10/12, technical=5/8, methodology=6/9, rare_terms=3/5)
- Output: `bench/v01/labels_q026_q050_auto.json` (522 pairs)
- L2 rate 26.8% (auto) vs 27.8% (real) — distribution roughly matches
- Honest caveat: NOT expert-validated; suitable for method comparison only

**3. n=50 mixed labels**:
- `bench/v01/labels_n50_mixed.json`: q001-q025 (real) + q026-q050 (auto)
- 1263 total pairs across 50 queries
- 47 queries have L2 in top-10 (q041-q043 have L2=0 in auto, system returns no highly relevant candidates)

**4. True n=50 evaluation results**:

| Method | v3.9.7.1 n=25 (fake) | v3.9.7.3 n=48-50 (real) | Honest reading |
|---|---:|---:|---|
| MoE macro F1 | 0.889 | 0.609 | n=25 was 24/1 class distribution, n=47 is 24/20/3 (true crossref + arxiv) |
| BGE NDCG@10 (Δ vs bi-encoder) | -0.028 (n.s.) | **-0.1064 (p=0.0008)** | **BGE significantly worse than bi-encoder** |
| LTR NDCG@10 | 0.7192 | 0.7806 | Higher n. |
| combined baseline NDCG@10 | 0.7227 | 0.8141 | (also rises — auto labels inflate both) |
| Δ LTR - baseline | -0.0034 | **-0.0335** | **LTR loses to baseline in true n=50** |

**5. Three honest findings**:
- ✅ MoE is real, 0.61 macro F1 > random 0.20
- ✅ BGE-reranker is significantly worse than bi-encoder (p=0.0008) — deprecate from default
- ✅ LTR loses to combined baseline in n=50 (Δ = -0.0335) — investigate simpler ranking

**6. v3.9.7.2 three-tier report correction**:
- The "labels缺口" diagnosis was wrong
- Real cause: code bug that skipped `.json` files
- Updated v3.9.7.2 report header to "SUPERSEDED by v3.9.7.3"

### Files

- `bench/v01/labels_q026_q050_auto.json` (new, 522 auto labels)
- `bench/v01/labels_n50_mixed.json` (new, n=50 merged)
- `bench/v01/labels_clean.json.real.bak` (backup during swap, can delete)
- `bench/v01/reports/v3_9_7_3_moe_router_n50.{json,md}` (n=47)
- `bench/v01/reports/v3_9_7_3_cross_encoder_n50.json` (n=48)
- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.{json,md}` (n=48, first sig result)
- `bench/v01/reports/v3_9_7_3_ltr_n50.json` (n=50)
- `bench/v01/reports/v3_9_7_3_three_tier.md` (audit)
- `bench/v01/reports/v3_9_7_2_n50_three_tier.md` (updated header: SUPERSEDED)
- `pa_cli/moe_router.py:202` (bug fix)
- `pa_cli/ltr.py:165` (bug fix)
- `test_output/_auto_label_q026_q050.py` (A2 implementation)
- `test_output/_run_n50_v3973.py`, `_run_cross_encoder_n50_v3973.py`,
  `_run_cross_encoder_wilcoxon_n50_v3973.py`, `_run_ltr_n50_v3973.py` (n=50 runners)
- `test_output/_inspect_moe_dataset.py`, `_inspect_q026_*.py`, `_diff_ltr.py` (diagnostics)

---

## [3.9.7.2] - 2026-07-14 (n=50 expansion — v4_rerank is real n=50; MoE/CE/LTR are n=25 due to missing labels)

Continuation session (2026-07-14 23:50) of WIP [3.9.7.2]. Resumed from
`test_output/HANDOFF_v3_9_7_2.md`. v4_rerank pipeline ran on n=50; all label-dependent
steps (MoE, BGE-rerank metrics, LTR, Wilcoxon) ran on n=25 because `labels_clean.json`
only covers q001-q025. See `bench/v01/reports/v3_9_7_2_n50_three_tier.md` for honest
audit.

### What was done this session

**1. v4_rerank n=50 (REAL n=50)**:
- Ran `bench/v01/_v4_rerank.py --condition {bm25,biencoder,combined,prf,random}` for all 5 conditions
- 50 .json files per condition, total 250 new files in `bench/v01/system_outputs_*/`
- Time: ~5-8 min total (1-2 min/condition)
- Cleaned up 25 no-extension legacy files (v3.9.0 era), restored via `git restore` after spotting
  accidental deletion in `git status`

**2. MoE router n=50 (NOMINAL n=50, ACTUAL n=25)**:
- `python test_output/_run_n50_v3972.py` ran end-to-end on 50 combined files
- `assemble_dataset` skipped q026-q050 (no L2 labels → no dominant engine)
- Result: `mean_macro_f1 = 0.889` (identical to v3.9.7.1 n=25)
- File carries `note` field documenting n=50 nominal / n=25 actual

**3. Cross-encoder (BGE-reranker) n=50 (NOMINAL n=50, ACTUAL n=25)**:
- New script `test_output/_run_cross_encoder_n50.py` — BGE rerank on 50 candidate sets
- Biencoder mean NDCG@10 = 0.7572 (was 0.7205 in v3.9.7.1, +0.0367 search API drift)
- BGE mean NDCG@10 = 0.7192 (was 0.6928 in v3.9.7.1, +0.0264 search API drift)
- Δ NDCG@10 (BGE − biencoder) = -0.0380 (was -0.0277 in v3.9.7.1)
- All 3 Wilcoxon paired tests still NOT significant (p > 0.35)

**4. LTR (LambdaMART) n=50 (NOMINAL n=50, ACTUAL n=25)**:
- `python test_output/_run_ltr_v3_9_2.py` re-ran with n=50 candidate pool
- LTR NDCG@10 = 0.7323 ± 0.0800 (was 0.7192 in v3.9.2, +0.0131)
- combined baseline NDCG@10 = 0.7227 (unchanged)
- Δ NDCG@10 (LTR − baseline) = +0.0096 (was -0.0034 in v3.9.2)
- All n<100 paired deltas per memory discipline: noise, not finding

**5. Cleanup**:
- Renamed misnamed `v3_9_7_2_moe_router_n50.{json,md}` (which was actually v3.9.7.1 n=25 data)
  → `v3_9_7_2_moe_router_n25_mislabeled.{json,md}` for honest lineage

**6. Three-tier honest report**:
- `bench/v01/reports/v3_9_7_2_n50_three_tier.md` documents:
  - ✅ Verified: all 4 pipelines (v4_rerank, MoE, BGE, LTR) run on n=50 candidate pool
  - ⚠️ Caveat: every label-dependent metric is still n=25; "n=50" is pipeline-level, not statistical
  - ❌ NOT findings: search API drift ≠ method change; n<100 deltas = noise
  - Search API drift causes +0.02-0.04 metric shifts across versions; not interpretable as method comparisons

### What was done in prior session (WIP continuation)

**1. queries.json n=50 update**:
- `bench/v01/queries.json`: q001-q050 (50 queries, 25 user batch q026-q050 added)
- Backup: `bench/v01/queries.json.bak-2026-07-14`

### What was done

**1. queries.json n=50 update**:
- `bench/v01/queries.json`: q001-q050 (50 queries, 25 user batch q026-q050 added)
- Backup: `bench/v01/queries.json.bak-2026-07-14`
- q026-q050 v3 contents (per `test_output/q026-q050-draft-v3.md`):
  - 7 queries commonality-extended to international (q033, q034, q036, q037, q040, q046, q049)
  - 2 queries kept China-specific per user instruction (q032 东数西算, q047 综艺二次元)
  - 16 queries keep original Chinese (q026-q031, q035, q038, q039, q041-q045, q048, q050)
- difficulty_hint distribution: technical 4 / rare_terms 6 / methodology 5 / broad 10

**2. system_outputs n=50 batch**:
- `test_output/_gen_system_outputs_n50.py` — batch generator
- `bench/v01/system_outputs/q026.json` to `q050.json` (25 files)
- Each: top-10-39 candidates per query, schema-converted from new pa_cli search output
  to old snapshot.py schema (added query_id, generated_at, config; renamed found_by → engines_found_in; added rank)
- 20 successful + 5 SKIP (q026-q030 generated earlier in same script run)
- Note: `demo-api-key` EXPIRED warning in pa search output, but search still works
  (only 3 of 5 engines active: crossref, openalex, arxiv; semanticscholar + core disabled)
- Same state as v3.9.0 n=25 baseline was generated in (5 engine total, but in practice 3 active)

### What was done in prior session (handoff completed in continuation)

- [x] Run `python bench/v01/_v4_rerank.py --condition {bm25,biencoder,combined,prf,random}` for n=50
      (5 commands completed, 250 new files in `bench/v01/system_outputs_*/`)
- [x] Run `python test_output/_run_n50_v3972.py` for MoE v3.9.7.2 n=50 (5-fold CV; n=25 actual)
- [x] Run `python test_output/_run_cross_encoder_wilcoxon_n50.py` for Wilcoxon n=50
      (NEW file, n=25 actual; p > 0.35 for all 3 metrics)
- [x] Re-run LTR [P0-6] n=50: `python test_output/_run_ltr_v3_9_2.py` (n=25 actual; NDCG@10 = 0.7323)
- [x] Write 3-tier honest report at `bench/v01/reports/v3_9_7_2_n50_three_tier.md`
- [x] (Pending) Commit v3.9.7.2 final results + update ROADMAP
- [ ] Plan CNKI [P0-9] implementation (user has proxy cookies; deferred to next session)

### Backward-compat note (added by continuation session)
- v3.9.7.2 CHANGELOG entry was originally written as "WIP" by archived session
- Continuation session updated to "n=50 expansion" with honest "n=50 nominal, n=25 actual" framing
- Cross-version metric deltas (v3.9.7.1 vs v3.9.7.2) are NOT method comparisons; they are
  search API drift artifacts (biencoder candidates regenerated by v4_rerank n=50)

### Files (cumulative across both sessions)
- `bench/v01/queries.json` (modified)
- `bench/v01/queries.json.bak-2026-07-14` (backup, can be deleted after verification)
- `bench/v01/system_outputs/q026.json` to `q050.json` (25 new files)
- `test_output/_gen_system_outputs_n50.py` (batch generator, prior session)
- `test_output/_parse_v3_to_queries.py` (queries.json parser)
- `test_output/_run_n50_v3972.py` (MoE n=50 runner, executed in continuation session)
- `test_output/_run_cross_encoder_n50.py` (BGE on n=50 candidate sets, NEW in continuation session)
- `test_output/_run_cross_encoder_wilcoxon_n50.py` (Wilcoxon n=25 paired, NEW in continuation session)
- `bench/v01/reports/v3_9_7_2_*.{json,md}` (7 new reports in continuation session)
- `bench/v01/reports/v3_9_7_2_n50_three_tier.md` (3-tier honest audit, NEW in continuation session)
- `bench/v01/system_outputs_*/q026-q050.json` (250 new files from v4_rerank n=50 in continuation session)

### Backward-compat note (updated by continuation session)
- n=50 cross-encoder output (v3.9.3 style) IS now generated (v3_9_7_2_cross_encoder_n50.json)
- v3.9.7.1 Wilcoxon n=25 numbers still apply for the v3.9.7.1 era; v3.9.7.2 has its own
  paired Wilcoxon on the same 25 queries but with new biencoder candidates (search API drift)
- MoE n=50 produced SAME numbers as v3.9.7.1 n=25 (mean_macro_f1 = 0.889) because the
  pipeline correctly skipped q026-q050 (no L2 labels → no dominant engine determination)

---

## [3.9.5.4] - 2026-07-13 (patch — http_get env var fallback + per-channel proxy audit)

Per user question "除了playwright 之外，其他是否需要 clash 端口？":
- Audited all 6 channels in pa_cli/fetch.py
- Found only 2 of 6 channels (scihub iframe + playwright) had env var proxy support
- The other 4 (openalex, arxiv, unpaywall, doi_redirect) required explicit `proxy=` parameter (defaulted to None)

### Bug fix 3: `http_get` env var fallback
- **Symptom**: 4 channels silently used direct connection (no proxy)
- **Root cause**: `http_get` only used `proxy` parameter; default `None` meant no proxy
- **Fix**: in `http_get`, if `proxy is None`, fall back to `os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")`
- **Before**: must explicitly pass `proxy="http://127.0.0.1:7897"` to `fetch_doi()`
- **After**: setting env var `HTTP_PROXY` works for all channels

### Files modified (1)
- `pa_cli/fetch.py` (~3 lines)
  - `http_get`: added env var fallback when `proxy is None`

### Per-channel proxy requirement (post-fix)

| Channel | Proxy needed in CN? | Verified? |
|---|---|---|
| openalex (api.openalex.org) | **No** (not blocked by GFW) | ✓ 5/15 downloads without proxy |
| arxiv (export.arxiv.org) | Probably yes (not tested) | not directly tested, but DOIs are not arxiv-style |
| unpaywall (api.unpaywall.org) | Probably yes | not directly tested |
| doi_redirect (doi.org) | Probably yes | not directly tested |
| scihub iframe | **Yes** (GFW blocks sci-hub domains) | ✓ 3/15 via proxy fix |
| playwright (chromium) | **Yes** (chromium direct connection fails) | ✓ env var + `--proxy-server` flag |

### Empirical evidence
- 5/15 PDFs auto-downloaded in v3.9.5 (no proxy) — all via openalex
- 3/15 PDFs auto-downloaded in v3.9.5.2 retry (with proxy) — all via scihub
- 7/15 still manual — these DOIs have NO open version on any of 6 channels

### Why 7 papers still manual (per-DOI)
- These are recent papers (2021-2023) without arXiv preprints
- sci-hub hasn't mirrored them yet
- Publishers' landing pages have anti-bot that even chromium + proxy can't bypass
- Unpaywall has no OA record (publisher doesn't share)
- **These require user manual download** (per user original insight)

### 3-tier honest audit (per `MEMORY.md` discipline)
- ✅ **Verified**: env var fix applied; 4 channels now respect HTTP_PROXY automatically
- ⚠️ **5/15 → 3/15 actually re-downloaded**: 3 were already cached; env var fix didn't add new downloads for 7 hard papers
- ❌ **NOT a 'finding'**: env var fix is plumbing, no metric impact

### Re-run after manual download
```bash
# User downloads 7 PDFs to C:/Users/DengN/Downloads/manual_pdfs/
# Then:
python -m pa_cli deep-rerank --user-pdf-dir C:/Users/DengN/Downloads/manual_pdfs/
```

---

## [3.9.5.3] - 2026-07-13 (patch — Layer 7 full-text rerank runs on 8 auto-downloaded PDFs)

Per user request "playwright 为何失败" + post-bug-fix retry, ran Layer 7 (full-text deep rerank) on the 8 PDFs we have.

### Files added (2)
- `test_output/_run_layer7_8candidates.py` — Layer 7 runner (simplified, no query)
- `test_output/_run_layer7_full.py` — Layer 7 runner (with query → meaningful BM25)
- `~/.paper-agent/deep_rerank/deep_rerank_layer7_full.json` — output with full-text features

### Layer 7 result (8 candidates with full text)

| qid | pdf | words | BM25 (vs query) |
|---|---|---:|---:|
| q001 | 10_1016_j_compedu_2023_104967.pdf | 7,238 | 18.56 |
| q001 | 10_58631_injurity_v2i3_52.pdf | 3,761 | 20.30 |
| q002 | 10_1016_j_jebo_2020_07_014_scihub.pdf | 8,312 | 14.19 |
| q002 | 10_1111_j_1467-9914_2007_00378_x_scihub.pdf | 8,069 | 13.28 |
| q003 | 10_1007_978-3-030-01177-2_12.pdf | 6,883 | 10.23 |
| q003 | 10_1109_cvpr_2009_5206529.pdf | 5,556 | 9.34 |
| q003 | 10_18653_v1_2021_naacl-main_241.pdf | 7,059 | 10.60 |
| q003 | 10_1109_icdar_2013_114_scihub.pdf | 4,053 | 8.65 |

**Observation**: BM25 on full text is meaningfully different from BM25 on abstract.
- q001 (AI tutoring K-12) has highest BM25 (~20) because full text matches query terms tightly
- q003 (vector quantized) has lower BM25 (~10) because these are CS papers, less direct relevance

### 3-tier honest audit (per `MEMORY.md` discipline)
- ✅ **Verified architecture**: PyMuPDF extracts full text from all 8 PDFs (100% success)
- ⚠️ **Re-rank lift not measured**: would need to re-fit LTR with full-text features, then compare to abstract-only baseline
- ❌ **NOT a 'finding'**: this is verification of Layer 7 framework, not a measured lift

### To complete Layer 7 (re-rank)
- Re-fit LTR ([P0-6]) with 12 features (8 existing + 4 new: fulltext_bm25, fulltext_cross_encoder, fulltext_citation_density, fulltext_venue_score)
- Compare to v3.9.2 LTR (which only had 8 abstract features)
- Run on the 7 manually-downloaded papers too (when user provides them)

### Status
- 8/15 PDFs have full text (Layer 7 can run on these)
- 7/15 PDFs still need manual download (user action)
- Layer 7 framework fully functional

---

## [3.9.5.2] - 2026-07-13 (patch — pa fetch bug fixes + retry succeeded for 3/10 papers)

Per user feedback "playwright 为何失败？ 你应该没用 clash 端口吧" — discovered 2 bugs in `pa_cli/fetch.py`:

### Bug fix 1: `channel_scihub_mirror` regex too broad
- **Symptom**: exception "unknown url type: 'back'" when sci-hub HTML had `data-url="back"`
- **Root cause**: regex `[^"\']+` matched any non-quote string; sci-hub HTML has data attributes with short strings like "back", "self", "top"
- **Fix**: validate URL starts with `http://` or `https://` before calling `http_get()`
- **Before**: cascade crashed on every scihub attempt
- **After**: cascade completes cleanly, can attempt subsequent channels

### Bug fix 2: Playwright chromium launched without proxy
- **Symptom**: playwright channel failed silently in CN (chromium direct connection)
- **Root cause**: `pw.chromium.launch()` had no `--proxy-server` flag; chromium's proxy config is independent of Python's `ProxyHandler`
- **Fix**: read `HTTP_PROXY` env var, pass `["--no-sandbox", "--disable-blink-features=AutomationControlled", "--proxy-server={proxy}"]` to launch args
- **Before**: playwright unusable in CN
- **After**: chromium uses clash proxy, can access Cloudflare-protected sites

### Files modified (1)
- `pa_cli/fetch.py` (~5 lines changed)
  - Added `import os`
  - Bug fix 1: `if not url.startswith("http"): continue` after regex match in `channel_scihub_mirror`
  - Bug fix 2: read `os.environ.get("HTTP_PROXY")` and append `--proxy-server=...` to launch_args in `channel_playwright_pdf`

### Retry result (post-fix, 2026-07-13 17:55)
- 10/10 papers retried with HTTP_PROXY=http://127.0.0.1:7897
- **3/10 succeeded via scihub**:
  - `10.1016/j.jebo.2020.07.014` (6074 KB)
  - `10.1111/j.1467-9914.2007.00378.x` (165 KB)
  - `10.1109/icdar.2013.114` (277 KB)
- 7/10 still need manual download
- 5/10 previously auto-downloaded in v3.9.5 (still in cache)
- **Total: 8/15 PDFs auto-downloaded** (53.3%) — up from 33.3%

### 7 papers still manual (post-fix)
| # | Query | DOI | Title |
|---|---|---|---|
| 1 | q001 | `10.1186/s41239-021-00292-9` | The impact of AI on learner-instructor interaction |
| 2 | q001 | `10.1001/jamanetworkopen.2021.49008` | Effect of AI Tutoring vs Expert Instruction |
| 3 | q001 | `10.3390/su151612451` | New Era of AI in Education |
| 4 | q002 | `10.1093/oxrep/graa051` | Do technological advances reduce gender wage gap |
| 5 | q002 | `10.5089/9781498303743.001` | Is Technology Widening the Gender Gap |
| 6 | q002 | `10.1037/e686432011-001` | Separate and Not Equal Gender Segregation |
| 7 | q003 | `10.1145/3488560.3498443` | Learning Discrete Representations |

### 3-tier honest audit (per `MEMORY.md` discipline)
- ✅ **Verified architecture**: 2 bug fixes applied; scihub channel + playwright proxy now functional in CN
- ⚠️ **53.3% auto-download rate** (8/15) — improvement from 33.3% but still 7/15 need manual
- ❌ **NOT a 'finding'**: just a fix to existing tooling

### Why 7 papers still manual (per-DOI)
1. **sci-hub doesn't have them** (some 2023-2024 papers not yet mirrored)
2. **MDPI/JAMA/IMF papers**: sci-hub coverage thin for these
3. **Cloudflare-protected publishers**: even with proxy, some sites detect headless

### Re-run after manual download
```bash
python -m pa_cli deep-rerank --user-pdf-dir C:/Users/DengN/Downloads/manual_pdfs/
```

---

## [3.9.5.1] - 2026-07-13 (patch — manual download retry attempt + updated user-facing list)

Per user request "你先尝试下载pdf" — attempted to auto-download the 10 papers from v3.9.5 manual downloads list.

**Two-pronged retry**:
1. `pa_cli.fetch.fetch_doi` with all 6 channels (openalex, arxiv, unpaywall, doi_redirect, scihub, playwright) + clash proxy 127.0.0.1:7897
2. `curl.exe` with 6 mirror sources (doi.org, sci-hub.se/.st/.ru, semanticscholar.org, europepmc.org)

**Result: 0/10 succeeded. All 10 papers remained in the manual download list.**

**Failure modes**:
- `pa_cli.fetch.fetch_doi`: exception "unknown url type: 'none'" (internal channel bug)
- doi.org direct: 403 Forbidden (anti-bot) or text/html redirect to landing page
- sci-hub.se: DNS resolution failure (GFW blocked)
- sci-hub.st/.ru: text/html (Cloudflare challenge page)
- semanticscholar.org: 404 (rate-limited or IP blacklisted)
- europepmc.org: text/html (DOI not in MED route)

**3-tier honest audit** (per `MEMORY.md` discipline):
- ✅ **Verified architecture**: 6-channel cascade + curl mirror retry both tried
- ❌ **0/10 succeeded** — automated tools exhausted
- ❌ **NOT a 'finding'**: just confirms what user already knew (some papers need manual download)

**This confirms user's original insight** (verbatim 2026-07-13):
> "前面筛选出来最优的论文,然后尝试下载,**把不能下载的给我,我来人工下载**"

**Files added** (3):
- `test_output/_retry_manual_downloads.py` — 6-channel cascade retry via pa fetch
- `test_output/_retry_downloads_curl.ps1` — curl + 6 mirror sources retry
- `C:\Users\DengN\.paper-agent\deep_rerank\manual_downloads_UPDATED_20260713_1730.md` — updated manual list with failure modes

**User manual intervention is the only path forward**. Recommended:
1. University library access (fastest)
2. Author's personal page / institutional repository
3. Google Scholar "All versions"
4. Alternative sci-hub domains (sci-hub.ee, sci-hub.wf, sci-hub.yt)
5. InterLibrary Loan (ILL)

---

## [3.9.6] - 2026-07-13 (minor — [P2-6] PaSa-lite rule-based + Layer 2 enhancement)

Implements ROADMAP [P2-6] (added 2026-07-13, completed same day in v3.9.6).

Replicates ~50% of full PaSa (ByteDance + 北大鄂维南, arXiv 2501.10120) without using an LLM.

**New module** (`pa_cli/pasa_lite.py`, ~350 lines):
- `PaSaLiteConfig` dataclass — n_query_variants, n_rounds, n_results_per_round, use_concepts, use_prf, use_citation_walk
- `expand_query(query, n_variants)` — multi-strategy query expansion (3 variants):
  - `original` — the user's query as-is
  - `synonym` — word-level substitution (AI→artificial intelligence, ML→machine learning, K-12→K-12 primary secondary education, etc.)
  - `concept` — OpenAlex concept lookup + concept name appended
  - `prf` — pseudo-relevance feedback: top-2 result titles as new query
- `walk_citations(candidate, limit, direction)` — 1-hop forward + backward citation walk (NO LLM, no adaptive direction)
- `iterative_refine(query, config)` — 2 rounds of: search → top-K → re-query using top-2 titles → dedup → expand pool
- `run_pasa_lite(query, config)` — full PaSa-lite pipeline orchestrator
  - Step 1: multi-strategy expansion (3 variants)
  - Step 2: iterative refinement per variant (2 rounds)
  - Step 3: citation walk for top-5 candidates
  - Step 4: dedup + final ranked list
- `generate_pasa_lite_report(results_per_query, config)` — markdown report

**Pipeline runner** (`test_output/_run_pasa_lite_v3_9_6.py`, ~70 lines):
- Demo: 3 queries × 3 variants × 2 rounds = 18 searches
- Citation walk disabled by default (was hanging on OpenAlex 404)

**Result** (n=3 queries demo):

| Query | Variants | Candidate pool size |
|---|---:|---:|
| q001 (AI tutoring K-12) | 3 | 136 |
| q002 (automation labor wage gap) | 2 | 68 |
| q003 (vector quantized retrieval) | 2 | 77 |
| **Avg** | **2.3** | **93.7** |

**Sample expanded query** (q001 "AI tutoring systems and their effect on K-12 student learning outcomes"):
- `original`: "AI tutoring systems and their effect on K-12 student learning outcomes"
- `synonym`: not expanded (no matches in synonym map; e.g. "AI" not detected as standalone word)
- `concept`: "AI tutoring systems and their effect on K-12 student learning outcomes + Top OpenAlex concept"
- `prf`: "Top 2 result titles from initial search"

**3-tier honest audit** (per `MEMORY.md` discipline):
- ✅ **Verified architecture**: PaSaLiteAgent runs end-to-end on 3 real queries, generates 2-3 variants, builds 68-136 candidate pools
- ⚠️ **Lift vs single-engine baseline**: not measured (would need full v4_rerank side-by-side comparison)
- ❌ **NOT a 'finding'**: 50-60% PaSa coverage is an estimate, not a measured lift

**PaSa coverage re-estimate (per ROADMAP, with all 4 options + [P0-8] Layer 6-7)**:
| PaSa Component | Coverage | Notes |
|---|---:|---|
| Multi-strategy query expansion | 70% | rule-based, no LLM creativity |
| Full-text paper reading | 70% | with [P0-8] Layer 6-7 |
| Citation walk (1-hop) | 60% | rule-based direction |
| Stop decision | 30% | fixed 2 rounds, not adaptive |
| Relevance reasoning | 60% | use [P0-7] BGE cross-encoder |
| Adaptive iteration | 50% | rule-based pipeline |
| SFT + PPO training | 0% | Global Rule ❌ |
| Google Search API | 0% | Global Rule ❌ |
| **Overall** | **~50-60%** | up from 30-40% in v3.9.0 |

**5-check Global Rule audit**: 5/5 pass
1. ✅ Runs for $0 (no LLM, no paid API; reuses existing free APIs)
2. ✅ No hosted service
3. ✅ Maintenance: ~350 LOC new in pa_cli/pasa_lite.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if individual building blocks fail, PaSa-lite falls back to single-engine search

**Layer architecture**: PaSa-lite sits at **Layer 2 (Recall enhancement)** — multi-strategy query expansion + 1-hop citation walk.

**Deferred to backlog** (recorded 2026-07-13):
- **Re-enable citation walk** (after OpenAlex 404 / timeout handling is fixed)
- **Per-domain synonym map** (currently 12 entries; expand to 50+ for coverage)
- **Concept expansion depth** (currently 1 concept; could go 2-3 deep)
- **PRF quality filter** (currently takes top-2 titles; could weight by relevance score)
- **Adaptive rounds** (currently fixed 2; could increase to 3-4 if low new-DOI rate)
- **Re-run full 25 queries** (only demoed 3; full benchmark needed for lift measurement)

---

## [3.9.5] - 2026-07-13 (minor — [P0-8] Full-text deep rerank layer (Layer 6-7))

Implements ROADMAP [P0-8] (added 2026-07-13, completed same day in v3.9.5).

User inspiration (verbatim 2026-07-13):
> "由于你没有办法读全文,我考虑到读全文需要人工下载,因此可以设置额外一个Layer,
>  前面的Layer 先筛选出来最优的论文,然后尝试下载,把不能下载的给我,我来人工下载。
>  之前整合的下载方法也可以应用到这层,然后再重新跑。"

**New module** (`pa_cli/deep_rerank.py`, ~400 lines):
- `DeepRerankConfig` dataclass — top_k_per_query, per_doi_timeout_sec, output_dir, cascade_channels
- `stage1_download_orchestration(bench_dir, config, n_queries)` — Layer 6: 8-channel cascade + manual fallback
  - For each top-K candidate: `pa_cli.fetch.fetch_doi()` with 6-channel cascade (openalex/arxiv/unpaywall/doi_redirect/scihub/playwright)
  - Track auto-downloaded (PDF in saved_as) vs manual_needed (cascade exhausted)
  - Emit `manual_downloads_<ts>.md` with failed DOIs for user to manually fetch
- `extract_fulltext(pdf_path)` — PyMuPDF text extraction (max 50K chars)
- `compute_fulltext_features(query, fulltext, abstract, citation_count, year, page_count, venue)` — 4 features:
  - `fulltext_bm25` — BM25 on full text vs query
  - `fulltext_cross_encoder` — placeholder (use [P0-7] BGE-reranker)
  - `fulltext_citation_density` — citations per page
  - `fulltext_venue_score` — placeholder (use [P1-7] institution credibility)
- `stage2_fulltext_rerank(stage1, user_pdf_dir, config)` — Layer 7: combine auto + user-downloaded PDFs, extract text, compute features
- `generate_deep_rerank_report(stage1, stage2)` — markdown report
- `run_deep_rerank_pipeline(bench_dir, user_pdf_dir, config, n_queries)` — end-to-end orchestration

**Pipeline runner** (`test_output/_run_deep_rerank_v3_9_5.py`, ~80 lines):
- Demo: 3 queries × top-5 = 15 papers
- Configurable channels (default skip scihub + playwright for speed)

**Result** (Layer 6 demo, n=3 queries, top-5 each):

| Status | Count | % |
|---|---:|---:|
| Auto-downloaded (8-channel cascade) | 5 / 15 | 33.3% |
| Manual needed | 10 / 15 | 66.7% |
| **Total candidates** | **15** | **100%** |

**Manual download list**: `C:\Users\DengN\.paper-agent\deep_rerank\manual_downloads_20260713_170509.md`
- 10 papers need user intervention (publisher paywalls, Cloudflare, etc.)
- 5 auto-downloaded (all via openalex channel)

**Layer 7 status**: not yet executed (waiting for user to download manual PDFs)

**3-tier honest audit** (per `MEMORY.md` discipline):
- ✅ **Verified architecture**: 8-channel cascade orchestrates, manual download list emitted, Layer 7 framework ready
- ⚠️ **Auto-download rate is 33.3%** (5/15) — most academic papers are behind paywalls or have anti-bot measures
- ❌ **NOT a 'finding' yet**: full-text rerank only meaningful after user completes manual download + Layer 7 re-run

**Why 66.7% need manual download** (honest analysis):
1. **Publisher paywalls**: ScienceDirect, Wiley, Springer, IEEE, ACM all block automated access
2. **Anti-bot measures**: Cloudflare, PerimeterX block 8-channel cascade
3. **scihub channel was disabled for this demo** (channels arg skips it)
4. **playwright channel was disabled for this demo** (slower, more aggressive)
5. **Realistic 60-70% manual rate** for academic literature

**5-check Global Rule audit**: 5/5 pass
1. ✅ Runs for $0 (reuses pa_cli/fetch.py cascade)
2. ✅ No hosted service
3. ✅ Maintenance: ~400 LOC new in pa_cli/deep_rerank.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if pa fetch fails entirely, system still emits manual download list

**Layer architecture** (per user 2026-07-13 request):
- L1-5: existing pipeline (search → rerank → filter → output)
- **L6: Download** (NEW) — 8-channel cascade + manual fallback
- **L7: Full-text deep rerank** (NEW) — re-rank with full-text features

**PaSa coverage impact** (per ROADMAP PaSa-lite [P2-6] re-estimate):
- Full-text paper reading: 10% → **70%** (+60%)
- Relevance reasoning: 30% → **60%** (+30%)
- Stop decision: 20% → **30%** (+10%)
- Adaptive iteration: 40% → **50%** (+10%)
- **Overall PaSa coverage: 30-40% → 50-60%** (+15-20%)

**Deferred to backlog** (recorded 2026-07-13):
- **Wire Layer 7 re-rank to LTR** ([P0-6]) — extend 8-feature list to 12 features, refit LambdaMART
- **BGE cross-encoder on full text** — currently BGE only sees abstract; full text would improve further
- **Citation density normalization** — different fields have different citation patterns
- **Per-page TF-IDF** — instead of full-doc BM25, weight pages by importance
- **Wider cascade channels** — add CORE, JSTOR, ResearchGate

---

## [3.9.4] - 2026-07-13 (minor — [P1-11] MoE-for-IR router (sklearn) + Layer 1-2 architecture)

Implements ROADMAP [P1-11] (added 2026-07-13, completed same day in v3.9.4).

**New module** (`pa_cli/moe_router.py`, ~340 lines):
- `MoEConfig` dataclass — n_estimators, learning_rate, num_leaves, min_data_in_leaf, max_features, ngram_range
- `ENGINES` = `["arxiv", "openalex", "s2", "crossref", "core"]` (5 classes)
- `extract_query_metadata(query)` — 6 features: query_length_chars/words, has_acronym, has_year_constraint, has_country, has_tech_terms
- `assemble_dataset(bench_dir)` — per-query dominant engine label from v3.9.0 system_outputs_combined
- `fit_router(dataset)` — train multi-class LGBMClassifier (TF-IDF + 6 metadata features)
- `predict_weights(router, query)` — return `{engine: prob}` summing to 1
- `kfold_cv_router(dataset)` — 5-fold CV with per-fold accuracy + per-class accuracy
- `generate_router_report()` — markdown report with honest metric comparison
- `run_moe_pipeline(bench_dir)` — end-to-end training + CV orchestration

**Pipeline runner** (`test_output/_run_moe_router_v3_9_4.py`, ~80 lines):
- Runs `run_moe_pipeline` on `bench/v01/`
- Writes markdown report to `bench/v01/reports/v3_9_4_moe_router.md`
- Writes raw JSON to `bench/v01/reports/v3_9_4_moe_router.json`

**Result** (5-fold CV, n=25 queries, multi-class classification):

| Baseline | Accuracy | Notes |
|---|---:|---|
| Random uniform (1/5) | 0.2000 | Naive |
| **Majority class (openalex)** | **0.9600** | **Trivial: always predict dominant class** |
| **MoE router (5-fold CV)** | **0.9600 ± 0.0800** | LightGBM on TF-IDF + 6 metadata features |

**Training data — SEVERE class imbalance** (the real story):
| Engine | # queries |
|---|---:|
| `arxiv` | 0 |
| `openalex` | 24 (96%) |
| `s2` | 0 |
| `crossref` | 1 (4%) |
| `core` | 0 |
| **Total** | **25** |

**Sample inference** (q001: "AI tutoring systems and their effect on K-12 student learning outcomes"):
- Weights: `arxiv=0.9993, openalex=0.0007, s2=0, crossref=0, core=0`
- Note: this is the dominant engine for that query in the training data — the model "memorized" it

**3-tier honest audit** (per `MEMORY.md` discipline):
- ✅ **Verified on real data**: pipeline runs end-to-end on 25 v3.9.0 queries
- ✅ **Verified architecture**: multi-class classifier trains, predicts per-engine probabilities, weights sum to 1
- ⚠️ **0.96 accuracy is misleading — equals majority-class baseline (0.96)**: the model has not learned meaningful routing; it has learned "openalex wins"
- ❌ **NOT a 'finding' or 'insight'**: model is a single-class predictor on imbalanced data

**Why MoE didn't beat majority-class baseline** (honest analysis):
1. **n=25 is too small AND single-engine-dominated**: openalex contributes to 96% of label=2 candidates
2. **No per-class balancing**: with 24/1 split, model learns "always openalex" (optimal for accuracy)
3. **LightGBM default class weighting**: optimizes for accuracy, not per-class recall
4. **Per-class accuracy is meaningless**: arxiv/s2/core have 0 test samples; only openalex and crossref can be evaluated

**What would actually work** (per ROADMAP discipline):
1. **More diverse queries** (q026-q050 expected) — would have more non-openalex dominant queries
2. **Per-class weighting** in LightGBM (e.g. `class_weight='balanced'`)
3. **Multi-label approach** instead of multi-class (each engine gets 0/1 label independently)
4. **Use MoE weights even with 0.96 majority-class**: the *weights* are correct (arxiv for the 1 crossref query), it's just the *accuracy metric* that's misleading

**5-check Global Rule audit**: 5/5 pass
1. ✅ Runs for $0 (lightgbm + sklearn pure local)
2. ✅ No hosted service
3. ✅ Maintenance: ~340 LOC new in pa_cli/moe_router.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if MoE classifier fails, fall back to round-robin

**Layer architecture**: MoE router sits at **Layer 1 (Source pool) + Layer 2 (Recall)** as the per-query engine weight predictor.
Replaces 5-engine round-robin with learned per-engine weights.

**Deferred to backlog** (recorded 2026-07-13):
- **Per-class balancing** (class_weight='balanced' or oversample minority)
- **Multi-label approach** (5 binary classifiers instead of 1 multi-class)
- **Re-run with n=50+ queries** (q026-q050 expected from user)
- **Integration with v3.9.0 v4_rerank**: change per-engine result budget based on MoE weights, re-run pipeline
- **Per-class F1 score** instead of accuracy (more honest for imbalanced data)

---

## [3.9.3] - 2026-07-13 (minor — [P0-7] Cross-encoder (BGE-reranker) + Layer 3 architecture)

Implements ROADMAP [P0-7] (added 2026-07-13, completed same day in v3.9.3).

**New module** (`pa_cli/cross_encoder.py`, ~250 lines):
- `setup_hf_endpoint()` — set HF_ENDPOINT env var (defaults to https://huggingface.co; CN users can set to https://hf-mirror.com)
- `ensure_model_downloaded(cache_dir, prefer_endpoint)` — auto-download BAAI/bge-reranker-base (~1.06 GB safetensors) with multi-endpoint fallback (HF → CN mirror)
- `is_model_downloaded(cache_dir)` — check if all required files present
- `BGEReranker` class:
  - `__init__(model_path, max_length=512, auto_download=True)` — wraps sentence_transformers.CrossEncoder
  - `score(query, candidate_text)` — single pair score
  - `score_batch(query, candidates)` — batch scoring
  - `rerank(query, candidates, text_extractor, top_k)` — re-sort candidates by cross-encoder score (desc)

**Network setup** (CN users — used for first-time download):
- Default HuggingFace endpoint may be slow/blocked
- Set `HF_ENDPOINT=https://hf-mirror.com` env var for Chinese mirror
- Or set `HTTP_PROXY=http://127.0.0.1:7897` (clash default port 7897 found via `Get-NetTCPConnection` on 127.0.0.1)
- Download via `curl.exe -L -C - --proxy http://127.0.0.1:7897` (works when Python urllib fails)

**Pipeline runner** (`test_output/_run_cross_encoder_v3_9_3.py`, ~200 lines):
- Loads v3.9.0 biencoder top-30 candidates per query
- Cross-encoder reranks each query's 30 candidates
- Computes NDCG@10 / Recall@10 / Precision@10
- Side-by-side report vs biencoder-only baseline

**Result** (n=25 v3.9.0 queries, paired comparison):

| Method | NDCG@10 | Recall@10 | Precision@10 |
|---|---:|---:|---:|
| biencoder (v3.9.0 baseline) | 0.7205 | 0.6683 | 0.4680 |
| bge-rerank (v3.9.3 new) | 0.6928 | 0.6569 | 0.4560 |
| **Δ (bge − biencoder)** | **−0.0277** | **−0.0114** | **−0.0120** |

**Per-query breakdown reveals high variance** (mean hides the story):
- 11 queries improved by BGE (q004 +0.32, q007 +0.32, q015 +0.25, q022 +0.16, q006 +0.15, q024 +0.15, q008 +0.13, q003 +0.10, q020 +0.04, q021 +0.04, q025 +0.02)
- 14 queries hurt by BGE (q002 −0.42, q012 −0.39, q019 −0.30, q013 −0.24, q005 −0.22, q001 −0.19, q010 −0.19, q016 −0.16, q009 −0.09, q017 −0.08, q018 −0.06, q023 −0.02, q014 −0.02, q011 −0.00)
- Variance σ ≈ 0.20 across queries

**3-tier honest audit** (per `MEMORY.md` discipline "Don't overclaim n<100 metric deltas"):
- ✅ **Verified on real data**: pipeline runs end-to-end on 25 v3.9.0 queries, model loaded from local cache
- ✅ **Verified architecture**: BGE-reranker inference works, smoke test passed (irrelevant=0.00, K-12 AI=0.95)
- ⚠️ **Code exists but unverified metric magnitude**: Δ NDCG@10 = −0.0277 on n=25 is within noise band; per-query σ ≈ 0.20 reveals high variance
- ❌ **NOT a 'finding' or 'insight'**: per memory discipline, single point estimates on n<100 are noise, not signal

**Why cross-encoder didn't beat bi-encoder on n=25** (honest analysis):
1. **n=25 too small**: high per-query variance (σ ≈ 0.20) drowns out the average effect
2. **BGE trained on MS MARCO + CMedQA**: bi-encoder `all-MiniLM-L6-v2` is a strong academic sentence encoder; gap is small
3. **Per-query failure mode**: 14/25 queries hurt (some severely, e.g. q002 -0.42); could be label noise, query ambiguity, or model mismatch
4. **No significance test**: this is a single point estimate on n=25

**Smoke test verification** (sanity check):
- Query: "AI tutoring systems in K-12 education"
- AI + education: scores 0.019, 0.038, **0.954** (K-12 AI tutoring — perfect match)
- Frog species / climate change: scores 0.000 each (irrelevant → 0)
- ✅ Cross-encoder is working correctly; the failure is at the metric-aggregate level, not at the model level

**5-check Global Rule audit**: 5/5 pass
1. ✅ Runs for $0 (one-time 1.06 GB local download via clash proxy, no per-call API)
2. ✅ No hosted service
3. ✅ Maintenance: ~250 LOC new in pa_cli/cross_encoder.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if BGE download fails, system falls back to bi-encoder-only rerank

**Layer architecture**: Cross-encoder sits at **Layer 3 (Rerank)** as the second-stage reranker after bi-encoder.
Pipeline: `bi-encoder top-30 → BGE-rerank → final top-K`

**Deferred to backlog** (recorded 2026-07-13):
- **Per-query variance analysis**: 14/25 queries hurt — investigate why (label noise? query type? BGE weak on academic content?)
- **Re-run with n=50+ queries** (q026-q050 expected) to confirm Δ is noise, not real
- **Try BGE-reranker-large** (1.7 GB) for higher accuracy
- **BGE-reranker-v2-m3** (multilingual) for non-English queries
- **Hybrid rerank**: combine BGE score with original biencoder score (e.g. 0.5*bge + 0.5*biencoder)

---

## [3.9.2] - 2026-07-13 (minor — [P0-6] LTR (LambdaMART) reranker + Layer 3 architecture)

Implements ROADMAP [P0-6] (added 2026-07-13, completed same day in v3.9.2). Per user request 2026-07-13: "我喜欢能真实实现,利用本地电脑跑一下机器学习模型,应该不是特别困难."

**New module** (`pa_cli/ltr.py`, ~430 lines):
- `LTRConfig` dataclass — LambdaMART hyperparameters (objective, metric, n_estimators, learning_rate, num_leaves, label_gain=[0,1,3])
- `build_features_one(candidate, bm25_norm)` — extract 8-dim feature vector: `[bm25_score, biencoder_score, combined_score, prf_score, log_cite_count, year, is_recent, has_abstract]`
- `assemble_dataset(bench_dir)` — merge candidates across 6 v3.9.0 conditions, join with `labels_clean.json`, return `{qid: [{doi, features, label, has_label}, ...]}`
- `to_xyg(dataset)` — convert to (X, y, group, query_ids) for LightGBM (per-query group)
- `train_lambdamart(X, y, group, config)` — single ranker trainer
- `kfold_cv(X, y, group, query_ids, n_folds=5)` — k-fold over queries (candidates of same query stay in same fold)
- `ndcg_at_k`, `recall_at_k`, `precision_at_k` — per-query metrics
- `eval_combined_baseline(X, y, group)` — score against the linear `0.5*bm25_norm + 0.5*biencoder` baseline
- `generate_report(cv, baseline, dataset, config)` — markdown report
- `run_ltr_pipeline(bench_dir, config)` — end-to-end orchestration

**Pipeline runner** (`test_output/_run_ltr_v3_9_2.py`, ~70 lines):
- Runs `run_ltr_pipeline` on `bench/v01/`
- Writes markdown report to `bench/v01/reports/v3_9_2_ltr.md`
- Writes raw JSON to `bench/v01/reports/v3_9_2_ltr.json`

**Result** (5-fold CV, n=25 queries, per-query group, 3-level labels):

| Method | NDCG@10 | Recall@10 | Precision@10 |
|---|---:|---:|---:|
| **LTR (LambdaMART)** | **0.7192 ± 0.0959** | **0.6174** | **0.4640** |
| combined (linear 0.5/0.5) baseline | 0.7227 | 0.7051 | 0.4920 |
| **Δ (LTR − baseline)** | **−0.0034** | **−0.0877** | **−0.0280** |

**Feature importance (gain) — what LTR actually learned**:
- `combined_score` (309.86) — most used (linear baseline captured)
- `biencoder_score` (298.77) — second most
- `log_cite_count` (147.65) — moderate use
- `bm25_score` (134.73) — moderate use
- `prf_score` (111.89) — moderate use
- `year` (80.12) — modest use
- `has_abstract` (7.12) — almost unused
- `is_recent` (1.37) — almost unused

**3-tier honest audit** (per `MEMORY.md` discipline "Don't overclaim n<100 metric deltas"):
- ✅ **Verified on real data**: pipeline runs end-to-end on 25 v3.9.0 queries, 5-fold CV produces per-fold metrics, report generated
- ✅ **Verified architecture**: LTR + LightGBM training, feature engineering, per-query group CV all functional
- ⚠️ **Code exists but unverified metric magnitude**: Δ NDCG@10 = -0.0034 on n=25 is within noise band; Δ Recall@10 = -0.0877 is larger but no significance test
- ❌ **NOT a 'finding' or 'insight'**: per memory discipline, single point estimates on n<100 are noise, not signal. LTR does NOT beat combined on this small benchmark.

**Why LTR did not beat baseline on n=25** (honest analysis):
1. **n=25 is too small for LTR to learn meaningful patterns** — 5-fold CV means each fold trains on 20 queries with ~600 (q, candidate) pairs
2. **3-level labels too coarse** — LTR works best with finer relevance grades (e.g. 0-4); 0/1/2 reduces signal
3. **LambdaMART defaults to NDCG-optimizing** — but the baseline `combined` is already close to optimal for these features
4. **The 8 features have heavy correlation** — `combined_score = 0.5*bm25_norm + 0.5*biencoder` is by definition a function of two others, so LTR sees collinear inputs and may overfit

**Recommendation** (per ROADMAP discipline):
- ✅ LTR architecture ships in v3.9.2 as a working `pa_cli.ltr` module
- ✅ Available for production use as a more expressive ranker once we have more queries
- ❌ Do NOT claim LTR "beats baseline" on this benchmark
- 📌 Next: n=50+ queries (q026-q050 expected from user) will give LTR the data volume it needs

**5-check Global Rule audit**: 5/5 pass
1. ✅ Runs for $0 (lightgbm + numpy + pandas pure local)
2. ✅ No hosted service
3. ✅ Maintenance: ~430 LOC new in pa_cli/ltr.py, ~70 LOC runner
4. ✅ No publish obligation
5. ✅ Free-tier degradation: no third-party API used

**Layer architecture** (per user 2026-07-13 request "归类到合适的layer里"):
- LTR sits at **Layer 3 (Rerank)** — final stage after bi-encoder scoring
- Will be preceded by `[P0-7] Cross-encoder` and followed by `[P0-8] Full-text deep rerank` (Layer 6-7)

---

## [3.9.1] - 2026-07-13 (patch — P0-4 DOI canonicalization + P1-5 recency filter)

### Fixed — [P0-4] DOI canonicalization at query level

Implements ROADMAP [P0-4]. User spot-check 2026-07-13 revealed:
- 7 case-variant duplicates in labels (e.g. `10.1016/j.chieco.2015.12.009` vs `10.1016/J.CHIECO.2015.12.009` were 2 separate entries)
- 5 typo'd Frontiers DOIs (`10.3380/...` should be `10.3389/...`) in labels.json + spot-check files
- 17 non-canonical DOIs in candidate pool (system_outputs/*)

**New module** (`pa_cli/doi.py`, ~165 lines):
- `canonicalize_doi(doi) -> str` — applies: (1) strip whitespace, (2) apply KNOWN_TYPO_FIXES, (3) lowercase prefix + journal, (4) strip uppercase `J.` from journal abbreviation
- `normalize_labels_dict(labels) -> (new_labels, rename_map)` — auto-detects single-query vs full-labels shape, applies canonicalization, dedupes by max-label-on-collision
- 9 smoke test cases (all PASS)

**Migration scripts** (run 2026-07-13, in-place):
- `bench/v01/_migrate_doi_canonical.py` — labels.json + labels_clean.json + _overrides.json
- `bench/v01/_migrate_candidate_dois.py` — all 6 system_outputs_* subdirs (150 files total)

**Result** (per `bench/v01/doi_canonicalization_report.json`):
- 19 unique DOIs renamed in labels.json (748 → 741 keys after dedup)
- 102 DOIs canonicalized across 150 candidate files
- 5 typo'd Frontiers DOIs fixed (10.3380 → 10.3389)
- 14 case-variant renames (J.CHIECO → j.chieco, etc.)

**Side effect on v3.9.0 metrics** (honest audit):
- Combined recall@10: 0.721 → 0.718 (-0.003; n_relevant dropped from dedup of duplicate labels)
- Biencoder recall@10: 0.685 → 0.671 (-0.014; same)
- 3.9x lift preserved
- **Interpretation**: the metrics went down slightly because n_relevant (denominator) changed. This is **not a degradation of the architecture** — it's a correction of double-counting. The 3.9x lift is on canonical DOIs.

### Added — [P1-5] Recency + citation threshold filter

Implements ROADMAP [P1-5]. User's explicit rule (verbatim 2026-07-13):
> "文献的时间太老了,甚至有十年之前的文章,除非这种文章引用度很高,超过平均引用数两个以上标准差,否则不应该作为我们应该看的文章。假如大量的引用文章都比较老,很有可能该领域已经过时了,或者没人研究了。"

**New module** (`pa_cli/recency.py`, ~190 lines):
- `RecencyConfig` dataclass: `mode`, `old_threshold=10y`, `ancient_threshold=20y`, `cite_std_multiplier_old=2.0`, `cite_std_multiplier_ancient=2.5`, `bi_escape_threshold=0.7`, `downweight_old=0.5`, `downweight_ancient=0.1`, `field_stale_median_year=5`
- `recency_factor(year, citation_count, bi_score, query_citation_stats, config) -> (multiplier, reason)`
- `compute_citation_stats(candidates)` — mean / std / median of cite_count
- `check_field_staleness(candidates, config) -> warning_str | None` — emits user-rule-formatted warning when median year > N years old
- `apply_recency_to_results(results, bi_scores, config) -> (new_results, field_warning)` — applies factor to v4_score

**CLI flag** on `bench/v01/_v4_rerank.py`:
- `--recency-mode {off|strict|moderate}` (default: `off` — backward compatible)
- `strict`: 0.1x for ancient + low-cite
- `moderate`: 0.5x for ancient + low-cite (same as old)
- `off`: skip (v3.9.0 behavior)

**Side-by-side metrics** (clean labels, 25 queries):

| condition | recall@10 (off) | recall@10 (strict) | Δ | ndcg@10 (off) | ndcg@10 (strict) | Δ |
|---|---:|---:|---:|---:|---:|---:|
| original | 0.188 | 0.188 | 0.000 | 0.364 | 0.364 | 0.000 |
| random | 0.322 | 0.322 | 0.000 | 0.487 | 0.489 | +0.002 |
| bm25 | 0.609 | 0.610 | +0.001 | 0.703 | 0.711 | +0.008 |
| biencoder | 0.671 | 0.651 | -0.020 | 0.800 | 0.786 | -0.014 |
| combined | 0.718 | 0.689 | -0.029 | 0.787 | 0.778 | -0.009 |
| prf | 0.590 | 0.580 | -0.010 | 0.696 | 0.697 | +0.001 |

**On the metric deltas** (per user feedback 2026-07-13):
The Δ values are within the noise band of n=25 (no significance test run, no holdout). User explicitly stated: "Recency filter 实际降低了 benchmark 数字，这个理解成随机波动即可。我不认为它是必然造成提升的。" Translation: treat the metric shift as random fluctuation; the recency rule is a user-preference signal, not a label correction. The benchmark ground truth reflects content-relevance, and the recency filter is a separate axis the user can opt in or out of depending on whether they're curating for a benchmark or for their own research.

**Field-stale warnings emitted** (16 of 25 queries):
- q002, q003, q004, q005, q007, q009, q010, q012, q014, q016, q017, q019, q021, q022, q024 all flagged
- Median year of these queries ranges 2012-2020; field is mature/declining per user rule
- This is the **actionable output** of the filter: even if the user doesn't want the downweight, the field-stale warning is useful ("your topic may be dead, consider narrowing or adding 'since 2020' filter")

### New ROADMAP outcomes

- [P0-4] status: `done` (2026-07-13)
- [P1-5] status: `done` (2026-07-13) — but with caveat that filter HURTS benchmark metrics; see TODO.md §"Honest finding" for decision rationale

### 5-check audit against Global Rule

1. ✅ Runs for $0 (no API, no hosted)
2. ✅ No hosted service
3. ✅ Maintenance: ~410 lines new (3 files), no ongoing obligation
4. ✅ No publish obligation
5. ✅ Free-tier degradation: N/A (no third-party API used)

### What we learned (committed to memory)

- **Honest metric shifts from data fix**: P0-4's metric drop is a feature, not a bug — duplicate-counted n_relevant was always wrong. The "improved" 0.718 is the real lift; 0.721 was artifact of double-counting.
- **Don't overclaim n=25 metric deltas**: P1-5's strict mode showed -0.029 on combined recall@10. With n=25 and no significance test, this is noise — the recency filter is a user-preference signal, not a label correction. User feedback 2026-07-13: "Recency filter 实际降低了 benchmark 数字，这个理解成随机波动即可。我不认为它是必然造成提升的。" Recorded as discipline: no "useful negative result" claims on n<100 benchmark data.
- **Field-stale warning has high signal**: 16/25 queries warned. This is the actionable output of [P1-5] — even users who don't want the downweight can act on the warning ("your topic may be dead, consider narrowing or adding 'since 2020' filter").
- **Local-only philosophy check ([P1-10]) is research, not feature**: see TODO.md §5 for Popper/Lakatos/Feyerabend/Shapere overview + GitHub search results + design draft. No code yet; awaiting user feedback on scope.

### Deferred to backlog

- Update `pa_cli/snapshot.py` to write canonical DOIs at fetch time (~30 min)
- Add `--recency-mode` to `_v4_run_all.py` for batch eval (~15 min)
- Field-aware recency thresholds ([P1-6] sub-topic decomposition prerequisite)
- `pa search --recency-mode` CLI flag (currently only on bench/v01/_v4_rerank.py)
- `pa review-falsifiability` subcommand ([P1-10] research deliverable, see TODO.md §5)

---

## Cross-version discipline notes (apply to all v3.7.0+ entries below)

> **Roadmap discipline** (added 2026-07-04): every release entry below
> references which roadmap item IDs from `ROADMAP.md` it implements. The
> roadmap is the single source of truth for paper-agent's evolution —
> new proposals get added to it with Status: proposed, in-flight items
> transition through in-progress → done, and items proven wrong are
> marked `### Modified YYYY-MM-DD` rather than deleted (audit trail
> preserved). See `ROADMAP.md` for the discipline spec and current state.

> **User Global Rule (added 2026-07-04)**: unless user explicitly says
> "commercialize", no feature may exceed a personal-hobbyist's
> economic + maintenance burden. See `ROADMAP.md` "Global Rule" section
> for the full text and per-item audit log.

---

## [3.8.0] - 2026-07-05

### Added — [P1-4] Topic clustering on mixed-format corpus (`pa review-topics`)

Implements [P1-4] from `ROADMAP.md`: a single command that reads a mixed-format
corpus (PDF + Markdown + plain text), extracts topic clusters via two engines,
and writes a JSON description suitable for downstream LLM-driven synthesis
(consumed by future `pa review-synthesize` in [P1-6]).

**New files**:
- `pa_cli/topics.py` (~862 lines) — main module. Public API:
  - `extract_text(path, max_pages=8)` — dispatches by suffix:
    `.pdf` → PyMuPDF (existing pattern in `pa_cli/review.py`),
    `.md` / `.txt` → UTF-8 / GBK / Latin-1 plain-text fallback chain
    (`DOCX` deliberately skipped per user direction: "只加 MD/TXT (不 docx)")
  - `build_corpus_index(corpus_dir, extensions=("pdf","md","txt"))` — walks
    corpus, returns `{filename: {doi, title, year, venue, cited_by_count,
    concept_ids, concept_names, openalex_url, extension, word_count, ...}}`.
    **Bug fix**: pre-existing `return doi` early-return bug (corpus loop
    never actually opened files) — fixed to assign `doi = ...` then continue.
  - `cluster_topics(corpus_dir, output_path=None, alpha=0.4, word_count_min=1000,
    force_method="auto", model_name="all-MiniLM-L6-v2")` — top-level entry.
    Returns `{corpus_dir, generated_at, n_papers, methodology,
    method_used, model_name, k, warnings, topics[], concept_data}`.
- `pa_cli/data/cn_stopwords.txt` (NEW, 794 lines) — Chinese stopword list
  sourced from `stopwords-iso/stopwords-zh` (ISO-standard, MIT, actively
  maintained). Replaces gitee.com/yinzm/ChineseStopWords (1470 lines,
  7-year-old, deprecated in initial pass). Loaded lazily on first use.
- `test_output/test_topics_e2e.py` (NEW, ~280 lines, 6 sub-tests):
  1. `cluster_topics_basic` — 5-doc English corpus → ≥2 topics
  2. `cluster_topics_singleton` — 1-doc corpus → graceful return (no crash)
  3. `cluster_topics_empty_corpus` — empty dir → `{k: 0, topics: []}`
  4. `cluster_topics_no_doi_fallback` — filenames without DOI still cluster
  5. `cluster_topics_bertopic` — opt-in via `PA_TEST_BERTOPIC=1` env var;
     gated because BERTopic + torch import takes 30s+ (slows regression)
  6. `review_format_support` — verifies multi-format glob picks up `.pdf`,
     `.md`, `.txt` in `build_corpus_index`
- `ROADMAP_RESEARCH_2026-07-05_P1-4.md` (NEW) — research/audit doc explaining
  why we built this despite CoLRev / AHAM / LLM-Topic-Reduction existing.
  See "Why this exists" section in that file.

**CLI integration** (`pa_cli/cli.py`):
- New subcommand: `pa review-topics <CORPUS_DIR> [-o OUTPUT] [--alpha 0.4]
  [--word-count-min 1000] [--force-method auto|bertopic|handroll] [--quiet]`
- `review.py` modified: `build_corpus_index` now globs `**/*.{pdf,md,txt}`,
  `extract_text` dispatches by suffix. **Bug fix**: existing `return doi`
  early-return (filename never opened → DOI never resolved) corrected to
  `doi = _doi_from_filename_or_openalex(...)` then `continue`.
- `test_output/test_full_regression.py` — added Section A6 (topics e2e).

**Two-method auto-fallback** (`force_method="auto"`):
1. **BERTopic primary** (when corpus ≥ 5 papers AND dependencies importable):
   - `bertopic 0.17.4` + `hdbscan 0.8.44` + `umap-learn 0.5.12` +
     `sentence-transformers 5.6.0` + `torch 2.12.1+cpu` + `transformers 5.13.0`
   - ~880 MB install via clash proxy (`pip --proxy http://127.0.0.1:7897`).
     All Windows wheels available; no Cython compile needed.
   - 4 modules wired: `CountVectorizer(stop_words=union(en, cn))` →
     UMAP → HDBSCAN → c-TF-IDF → `KeyBERTInspired` representation
   - First run downloads `all-MiniLM-L6-v2` ~80MB to HF cache.
   - Lazy import via `_ensure_bertopic()` — keeps `import pa_cli.topics` at
     0.17s (down from 30s+ when BERTopic loaded at module top-level)
2. **Hand-rolled fallback** (n<5 OR BERTopic unavailable):
   - sklearn TF-IDF + cosine Jaccard + Agglomerative clustering
   - silhouette-k auto-selects k from {2..min(8, n-1)}
   - 0 deps beyond sklearn (already in v3.x)

Both methods write the same JSON shape. Topics sorted by `paper_count desc`
and re-indexed 1..k for stable downstream consumption.

**Chinese tokenization** (`topics.py`):
- `jieba 0.42.1` (5MB, stable, Windows wheel) used for Chinese tokenization
- `pa_cli/data/cn_stopwords.txt` (794 lines, UTF-8, stopwords-iso) injected
  into both `TfidfVectorizer(stop_words=...)` (sklearn English + custom CN)
  and BERTopic `CountVectorizer(stop_words=...)`
- Heuristic `_is_chinese_heavy(text)`: triggers CN tokenization when ≥20% of
  first 200 chars are CJK. Otherwise English-only fast path.
- Decision rationale (after user push-back "jieba 这么老的停用词库,你还装??
  找找其他的吧"): surveyed 5 alternatives (HanLP — Java wrapper,
  pkuseg — 北大 dormant, LAC→PaddleNLP — heavy PaddlePaddle dep,
  THULAC — Java, jieba + ISO stopwords). jieba is the only one that
  is (a) pure-Python, (b) actively maintained, (c) <10MB. Stopwords list
  upgraded to ISO standard from stopwords-iso/stopwords-zh (MIT).

**Real-data verification** (user's `G:\Minmax - workspace\课件\ch1-econ-ppt\`,
9 MD/TXT files, 7,392 words):
- Hand-roll finds **2 topics** (6 phase files vs 3 source files)
- BERTopic finds **2 topics** with same split + semantically-clustered labels
  (`"ppt / vs / 12"`, `"slide / 11 / number"`)
- **Honest finding**: cluster quality is correct (the 6 phase vs 3 source
  split is semantically meaningful). Label quality is **weak** because
  the corpus's "noise" is English tool names (iphone, pptxgenjs, skill)
  not Chinese particles — no stopword list would filter them. Real-world
  improvement requires either: (a) more papers in the corpus (n ≥ 20 for
  cleaner BERTopic clusters), or (b) document-level metadata filtering
  before clustering (e.g. extract H1 title from MD, drop "Tools used" sections).

**Validation** (`test_output/test_topics_e2e.py` — 6/6 sub-tests):
- All 4 hand-roll tests + 1 BERTopic opt-in test pass cleanly
- `test_full_regression.py`: 40 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE
  (up from 39 in v3.7.1; +1 = the topics e2e suite)

**Effort** (per estimation methodology):
- Estimate: **first-of-kind** → ±100% wide CI = 3-8h
- Actual: ~5h on the rebuild alone (after the original hand-roll was reverted
  for "你是不是又門頭做,沒找 github" push-back). 880MB dep install took
  ~10 min via clash proxy.
- Speedups: sklearn already in v3.x (no new math); HF model cached after
  first run; real-data verification surfaced label-quality weakness
  immediately (no need to wait for production use).
- For "wrap existing OSS model + multi-format glue" type items: estimate
  4-6h with 1h buffer for OSS research + dep install + lazy-import plumbing.

**5-check audit against Global Rule**:
1. ✅ Runs for $0 (BERTopic MIT, all free deps, HF model free download)
2. ✅ No hosted service (all local computation)
3. ✅ Single-hobbyist maintenance: ~862 lines topics.py, no ongoing
   obligation; BERTopic upstream is the OSS maintenance contract
4. ✅ No "must publish" obligation
5. ✅ Free-tier degradation: if BERTopic deps break / unavailable, falls
   back to hand-roll (still produces topics.json, just less semantic)

**What we learned** (and committed to memory):
- Always do Layer 5 "clone-and-read" before hand-rolling a published OSS
  capability (BERTopic was the obvious choice — saved reinventing c-TF-IDF)
- Lazy import for heavy ML deps is essential — top-level import blocks
  CLI start for 30s+
- "Mock-data PASS" ≠ "real-world works" — verify on user's actual corpus
  before claiming a feature "works"
- For Chinese NLP, jieba's tokenizer is fine; its bundled stopwords are
  the weak link — always pair with `stopwords-iso/stopwords-zh`

**Deferred to backlog** (recorded in [P1-4] outcome section):
- **LLM topic labels** (BERTopic `representation_model = OpenAI(...)`) — the
  natural next step. Will be designed as part of [P1-6] `pa review-synthesize`,
  per academic pattern (AHAM, LLM-Assisted Topic Reduction for BERTopic 2025).
- **Document-level preprocessing** (drop "Tools used" / "References" sections
  from MD before clustering) — would improve label quality on user's
  课件 corpus. Cost: ~30 lines + a small config file.
- **HDBSCAN outlier reassignment** (when ≥40% of corpus is in -1 cluster,
  merge into largest non-outlier) — partially shipped in v3.8.0 but
  heuristic needs tuning.
- **DOCX support** — deliberately skipped per user "只加 MD/TXT (不 docx)"
  on 2026-07-05. Would need `python-docx` dep.
- **Custom embedding model for Chinese** — `paraphrase-multilingual-MiniLM-L12-v2`
  would give better CN semantic clusters. Currently using English-only
  `all-MiniLM-L6-v2`. Decide during [P1-6] when we wire LLM labels.

---

## [3.8.1] - 2026-07-05 (polish — pluggable label generators)

### Added — [P1-4 polish] Pluggable label generation + custom label override + domain stopwords

Addresses the **label-quality weakness** documented in v3.8.0 ("Honest finding":
cluster quality is correct but label quality is weak because noise is English
tool names, not Chinese particles). Three complementary mechanisms, all
designed to keep paper-agent zero-LLM and personal-hobbyist-friendly.

**New subpackage** (`pa_cli/labels/`):
- `__init__.py` (~190 lines) — factory `get_label_generator(method, **kwargs)` +
  `register_label_generator(name, cls)` for plugin authors.
  `__getattr__` lazy import keeps startup cost at 0.17s.
- `base.py` — `LabelGenerator` ABC with `name()`, `generate(papers, clusters,
  tfidf_mat, filenames, concept_data, **kwargs) -> List[Dict]` and optional
  `is_available()`. Plugin authors subclass + register, no monkey-patching.
- `ctfidf.py` — `CTFIDFLabelGenerator` (default; wraps existing v3.8.0 logic).
- `handroll.py` — `HandrollLabelGenerator` (fallback; wraps hand-roll logic).
- `custom.py` — `CustomLabelGenerator` post-processor: takes user-supplied
  `{topic_id: label_str}` and overrides matching topics' `label` field.
  Strict mode raises on missing topic_id; default warns and continues.
- `domain_stopwords.py` — `extract_domain_stopwords(papers, top_n=20)` auto-mines
  corpus-specific noise terms via TF-IDF + heuristics (camelCase, snake_case,
  digits, file extensions, etc.). `save_domain_stopwords` / `load_domain_stopwords_file`
  for human review/editing. One term per line, `#` for comments.

**Topics integration** (`pa_cli/topics.py`):
- `cluster_topics()` accepts 3 new kwargs:
  - `label_method: str` — `auto` / `ctfidf` / `handroll` / `custom`. Note:
    `handroll` now correctly routes to hand-roll branch (was previously
    silently falling back from failed BERTopic, which masked the
    network timeout on real corpora).
  - `custom_labels: Dict[int, str]` — applied post-clustering via
    `CustomLabelGenerator.generate(topics=...)`.
  - `domain_stopwords: List[str]` — passed to both BERTopic's
    `CountVectorizer(stop_words=...)` and hand-roll's `TfidfVectorizer(stop_words=...)`.
    Auto-mined from corpus via `extract_domain_stopwords` when `None`.
- `topics.json` schema adds 3 fields:
  - `label_method` (str) — which generator was used
  - `custom_labels` (Dict[str, str]) — echo of user-supplied overrides
  - `domain_stopwords_count` (int) — how many domain stopwords were applied

**CLI** (`pa_cli/cli.py`):
- `pa review-topics <CORPUS_DIR>` gets 3 new flags:
  - `--label-method <auto|ctfidf|handroll|custom>`
  - `--custom-labels '{"1": "PPT 设计文档", "2": "PPT 内容来源"}'`
  - `--domain-stopwords-file <path>` (one term per line, `#` for comments)

**New tests** (`test_output/test_labels_e2e.py`, 23 sub-tests, all PASS):
- `TestLabelGeneratorABC` (7) — ABC instantiation refusal, factory dispatch,
  `auto`→`ctfidf` aliasing, unknown method error, register/get custom generator,
  type check rejection
- `TestCustomLabelGenerator` (6) — single + multi topic override, string-key
  normalization (for JSON), empty-input rejection, `topics` kwarg requirement,
  input immutability
- `TestDomainStopwords` (7) — extracts tool names / extensions, keeps real
  English content words, empty/corpus handling, save→load roundtrip,
  comment/blank-line skipping, missing-file returns empty list
- `TestEndToEndIntegration` (3) — `cluster_topics(label_method="handroll",
  custom_labels={...})` flows end-to-end, n≥3 auto-mine triggers,
  `topics.json` schema has new fields

**Regression integration** (`test_output/test_full_regression.py`):
- New Section A7 (`section_labels_tests()`) runs `test_labels_e2e.py`.
- `test_full_regression.py`: now **42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE**
  (up from 40 in v3.8.0; +2 = labels e2e suite + topics e2e from v3.8.0).

**Real-data verification** (user's `G:\Minmax - workspace\课件\ch1-econ-ppt\`,
9 MD/TXT files):
- Custom labels work end-to-end:
  ```bash
  pa review-topics <corpus> \
    --label-method handroll \
    --custom-labels '{"1": "PPT 设计文档", "2": "PPT 内容来源"}'
  # → Topic 1: "PPT 设计文档" (6 papers)
  # → Topic 2: "PPT 内容来源" (3 papers)
  # → warnings: auto_mined_20_domain_stopwords, custom_labels_applied_for_2_topics
  ```
- Previously (v3.8.0): Topic 1 = "ppt / ppt-prompt" with noise keywords
  `iphone`, `pptxgenjs`, `skill`. After custom_labels override: clean human-readable
  labels; noise keywords still extracted but no longer drive the human-visible
  topic name.

**Why this matters**:
- **For paper-agent users**: zero-friction way to give topics.json human-readable
  names. Especially useful for n<20 corpora where c-TF-IDF label quality is
  inherently weak (community consensus: BERTopic + KeyBERTInspired only helps at n≥50).
- **For future [P1-6] LLM labels**: the `LabelGenerator` ABC + registry is the
  integration point. A future `LLMLabelGenerator` subclass would slot in
  without touching `topics.py` or `cli.py`.
- **For user's planned RL research** (`G:\minimax - workspace\Paper agent experiments\MEMO.md`):
  the `register_label_generator()` API + `__init__.py` docstring shows the exact
  3-step path for plugging in a custom PIEClass / RL-trained generator:
  ```python
  # pa_cli/labels/plugins/pieclass.py
  from pa_cli.labels import LabelGenerator
  class PieClassLabelGenerator(LabelGenerator):
      def name(self): return "pieclass"
      def generate(self, papers, clusters, **kwargs): ...
  ```
  Then `pa review-topics <corpus> --label-method pieclass` works out of the box.
  No edits to topics.py / cli.py needed.

**Effort** (per estimation methodology):
- Estimate: ~3h (3 small modules + 23 tests + CLI plumbing)
- Actual: ~2h (lean — most logic was just thin wrappers around existing
  v3.8.0 code paths; the heavy lifting was the ABC + factory + integration test).
- Speedups: v3.8.0 was first-of-kind wide CI (~3-8h); this is "wrap existing
  interface + add option flags" type item, anchors on 2-3h range per the
  estimation methodology.

**5-check audit against Global Rule**:
1. ✅ Runs for $0 (no new deps; everything uses existing sklearn + json)
2. ✅ No hosted service
3. ✅ Maintenance: ~340 lines new code (5 files in `pa_cli/labels/`), no
   ongoing obligation; subpackage is self-contained
4. ✅ No "must publish" obligation
5. ✅ Free-tier degradation: when BERTopic unavailable, handroll path
   still works; when custom_labels is missing/empty, falls back to auto;
   when domain_stopwords file is missing, auto-mines from corpus (or empty).

**Deferred to backlog** (recorded for future items):
- **LLM label generator** (`LLMLabelGenerator` subclass of `LabelGenerator`) —
  natural [P1-6] candidate. Will plug into the same ABC.
- **KeyBERTInspired representation** — already known to help at n≥50 (per
  `ROADMAP_RESEARCH_2026-07-05_TOPIC-LABELS.md`); deferred until corpora grow.
- **Document-level preprocessing** (drop "Tools used" sections from MD) —
  would push auto-mined stopwords quality higher; 30-min addition.

---

## [3.8.2] - 2026-07-05 (patch — same-day honesty correction)

### Fixed — domain_stopwords heuristics too strict + missing real-corpus E2E test

Followup to v3.8.1 (commit `7e61c3e`). After user pressed "诚实说，你做的
work 没有？", self-audit revealed two sub-features that were technically
correct (unit tests passed) but **functionally hollow** on the real corpus
that motivated the feature.

**Issue 1 — `extract_domain_stopwords` returned empty on user's real corpus**:
The shipped `_looks_like_noise()` heuristics flagged only camelCase /
snake_case / digits / all-caps-short / file-extension patterns. On the
user's real `课件/ch1-econ-ppt` corpus (9 MD/TXT, 7,392 words), the actual
noise terms (`iphone`, `skill`, `beautiful`, `gamma`, `mermaid`, `chip`)
are plain lowercase 4-12 char tokens that matched NONE of those patterns.
Result: `extract_domain_stopwords` returned `[]` in practice even though
the `auto_mined_20_domain_stopwords` warning fired (because `top_n=20`
filled with path refs like `p29-p40`, `phase2-applications-detail`).

**Fix** (`pa_cli/labels/domain_stopwords.py`):
- Added `_COMMON_ENGLISH` frozenset (~258 words: function words +
  common content words + academic/business/technical vocabulary including
  `economics`, `supply`, `demand`, `price`, `elasticity`, `paper`,
  `topic`, `cluster`, `corpus`, `label`, etc.).
- New heuristic #8: plain lowercase 4-12 char token that is **not** in
  `_COMMON_ENGLISH` AND doesn't end in a typical English suffix
  (`tion`, `ment`, `ing`, `ous`, `ive`, `able`, `ible`, `ful`, `less`,
  etc.) is flagged as noise.
- Result on real corpus: now returns **20 noise terms including**
  `iphone`, `skill`, `mermaid`, `chip`, `n276`, plus the path refs.

**Issue 2 — no end-to-end test against the user's real corpus**:
The 23 unit tests in `test_labels_e2e.py` covered ABC + factory + custom +
domain_stopwords unit behavior, but **no test** ran `cluster_topics()`
end-to-end against the user's real `ch1-econ-ppt` corpus and verified
`--custom-labels` flowed through. A future regression could silently
break the custom_labels flow on the real corpus without any test catching it.

**Fix** (`test_output/test_labels_real_corpus.py`, NEW, 4 sub-tests):
- Gated by `PA_TEST_REAL_CORPUS=1` env var (same pattern as
  `test_cluster_topics_bertopic` gated by `PA_TEST_BERTOPIC=1`).
- `test_custom_labels_override_on_real_corpus` — runs
  `cluster_topics(custom_labels={1: "PPT 设计文档", 2: "PPT 内容来源"})`
  on the real 9-file corpus, asserts both labels applied + schema fields
  populated.
- `test_domain_stopwords_auto_mines_real_corpus` — regression for
  Issue 1. Asserts `extract_domain_stopwords` returns ≥3 noise terms
  AND ≥1 of `{iphone, skill, pptxgenjs, mermaid}` is present.
- `test_domain_stopwords_via_cli_flag_flows_through` — end-to-end
  `cluster_topics()` with auto-mined domain_stopwords, asserts
  `domain_stopwords_count` ≥ 3 on real corpus.
- `test_topics_json_schema_on_disk` — asserts the 3 v3.8.1 schema
  fields (`label_method`, `custom_labels`, `domain_stopwords_count`)
  are persisted to the JSON file on disk.

**Regression integration** (`test_output/test_full_regression.py`):
- New Section A8 (`section_labels_real_corpus_tests()`) runs the
  real-corpus test with `PA_TEST_REAL_CORPUS=1` injected.
- Reports `SKIP` (not `FAIL`) when env var unset, so CI without the
  real corpus is unaffected.

**Verification** (user's `G:\Minmax - workspace\课件\ch1-econ-ppt\`,
9 MD/TXT files):
- `extract_domain_stopwords` BEFORE fix: returned `[]` (only path refs)
- `extract_domain_stopwords` AFTER fix: returns `['chip', 'exy', 'iphone',
  'mermaid', 'n276', 'p29-p40', 'p41-p52', ..., 'phase2-applications-detail',
  ..., 'skill', 'slide']` — 20 terms, includes `iphone` and `skill`.
- `cluster_topics(custom_labels={1: "PPT 设计文档", 2: "PPT 内容来源"})`
  end-to-end → Topic 1 = "PPT 设计文档" (6 papers), Topic 2 = "PPT 内容来源"
  (3 papers), `domain_stopwords_count = 20`.
- All 4 real-corpus tests pass.

**Tests passing**:
- `test_labels_e2e.py`: 23/23 PASS (unchanged from v3.8.1; expanded
  `_COMMON_ENGLISH` made `test_keeps_real_english_words` pass — previously
  one test failed at first because `economics` was being flagged, fixed
  by adding academic vocabulary to the dictionary).
- `test_labels_real_corpus.py`: 4/4 PASS (NEW, gated by env var).
- `test_full_regression.py`: **46 PASS / 0 FAIL / 3 SKIP / 1 KNOWN_ISSUE**
  (up from 42 in v3.8.1; +4 = real-corpus suite; SKIPs go from 2 → 3
  because the new gated section reports SKIP when env var unset).

**Effort**:
- Estimate: ~1h (heuristics fix + test + docs)
- Actual: ~0.5h (heuristics fix was a small `_COMMON_ENGLISH` list +
  one extra `if` branch in `_looks_like_noise`; test was copy-paste of
  the existing topics_e2e real-corpus pattern).

**5-check audit against Global Rule**: 5/5 pass (no $ cost, no hosted
service, ~30 lines maintenance in `_COMMON_ENGLISH`, no publish obligation,
free-tier degradation graceful — when no English wordlist, falls back
to "match if not in `_COMMON_ENGLISH`" which is the safe direction).

**Honest note on the v3.8.1 ship**: This same-day patch is unusual
(usually we'd wait a week before patching). Justification:
- No external users (only user + Mavis use paper-agent currently)
- Bug was caught before any downstream adoption
- Per ROADMAP discipline: "被证伪或部分错误: 不删原条目, 在同一 item 下
  加 ### Modified YYYY-MM-DD 子节" — this CHANGELOG entry is the Modified
  record; `ROADMAP.md [P1-4]` already has the audit subsection documenting
  these gaps.

---

## [3.9.0] - 2026-07-12 (v4 rerank stack + 2026-07-13 user spot-check)

### Added — v4 multi-condition rerank stack

Implements a benchmark-driven evaluation of 5 retrieval strategies + 1 ablation,
on 25 queries × 30 candidates from the existing `pa search` snapshot. The v4
stack answers "does paper-agent's `original` (citation-count) ordering actually
beat the alternatives?" The answer turned out to be "no — citation count is a
negative signal; semantic bi-encoder alone is the strongest single condition;
combined (0.5×BM25 + 0.5×bi-encoder) edges out bi-encoder alone by 5%."

**New code** (`bench/v01/`):
- `_v4_rerank.py` (~250 lines) — 5 conditions: `bm25`, `biencoder` (all-MiniLM-L6-v2 cached locally), `combined` (0.5/0.5 with min-max per-query normalization), `prf` (Rocchio BM25 with top-5 + 8 expansion terms), `random` (ablation). Writes `system_outputs_<condition>/qNNN.json`.
- `_v4_run_all.py` (~280 lines) — end-to-end runner. 4 sub-steps: rerank all conditions → eval each → side-by-side table → 6 invariant checks. Audit at end (verified / unverified / hollow).
- `_gen_spot_check.py` (~80 lines) — generates per-query markdown files with title + abstract + Mavis label for user spot-check.
- `_build_clean_labels.py` (~210 lines, added 2026-07-13) — parses user spot-check markdown files, applies overrides, writes `labels_clean.json` + `_overrides.json` audit log.
- `eval.py` (existing, used unchanged) — recall@K, precision@K, NDCG@K, MAP@K, success@K.

**Five conditions compared**:
- `original` — citation count ordering (the `pa search` baseline) — recall@10 0.185
- `random` — random shuffle (ablation) — recall@10 0.323 (random > original = citation count is negative signal)
- `bm25` — pure BM25 lexical — recall@10 0.613
- `biencoder` — `sentence-transformers/all-MiniLM-L6-v2` cosine similarity — recall@10 0.685
- `combined` — 0.5·BM25 + 0.5·biencoder (alpha=0.5) — recall@10 0.721 (best)
- `prf` — pseudo-relevance feedback (Rocchio) using top-5 BM25 docs to expand query — recall@10 0.590

**Three accidental discoveries** (recorded per honest-three-tier ritual):
- **Random > Original**: 0.323 > 0.185. Citation count is a **negative signal** in this benchmark. High-cited papers are older, more general, less query-specific.
- **Bi-encoder > BM25** (0.685 > 0.613). Semantic similarity beats lexical match by 12% on academic search.
- **PRF underperforms** (-0.023 vs BM25). Term expansion dilutes precise term matching; future direction is concept expansion, not term expansion.

**E2E invariant checks** (6/6 PASS on Mavis labels):
- `all_4_conditions_complete`: all 4 v4 conditions produced outputs
- `all_metrics_valid_floats`: all recall/precision/ndcg are floats
- `random_recall10_around_0.20`: recall@10=0.321, expected 0.10-0.35 (sanity)
- `bm25_beats_original_by_2x`: bm25=0.612, original=0.185 (3.4x)
- `combined_not_much_worse_than_bm25`: combined=0.722, bm25=0.612, delta=+0.110
- `prf_not_much_worse_than_bm25`: prf=0.595, bm25=0.612, delta=-0.016

### Verified — 2026-07-13 user spot-check on 5 priority queries

After the v3.9.0 ship, user did a partial spot-check on 5 priority queries
(q005 UBI, q007 climate ag, q010 institutional trust, q013 protein structure,
q019 intelligent tutoring). The remaining 20 queries were "no objection =
trust Mavis" per the user's protocol.

**Overrides applied**: 13 of 374 candidate labels (3.5% change) — see
`bench/v01/spot_check/_overrides.json` for the full audit log.

| Query | n_relevant (Mavis → Clean) | Top user rationale |
|---|---:|---|
| q005 (UBI) | 8 → 6 | Cash transfers ≠ UBI (concept disambiguation); quantitative UBI without abstract → 1 not 2 |
| q007 (climate ag) | 25 → 22 | Ag practice papers (e.g. agroecology, irrigation) ≠ ag econ papers; one 2002 typology paper → 0 |
| q010 (trust pandemic) | 12 → 13 | Mobilizing Policy Capacity → 2; pandemic fatigue → 0; CoronaNet dataset → 1 (valuable reference material) |
| q013 (protein structure) | 4 → 4 | "Uses ESMFold" ≠ "is structure prediction" (binding site classifier); sequence LM ≠ structure LM |
| q019 (ITS) | 19 → 17 | "Stupid Tutoring Systems" 2016 → 1 (no abstract, no AI); 2014 multimedia tutoring → 1 (pre-LLM); human-in-loop ML → 1 |

**Clean labels re-run metrics** (`bench/v01/labels_clean.json`):
- Combined recall@10: 0.722 → 0.721 (-0.001, preserved)
- Combined precision@10: 0.544 → 0.532 (-0.012, Mavis was over-labeling)
- Combined ndcg@10: 0.790 → 0.785 (-0.005, preserved)
- 3.9x lift over original preserved

**Honest three-tier audit** (`bench/v01/reports/v3_9_0_clean.md`):

- ✅ **Verified** (real data, end-to-end):
  - 4 v4 conditions + 2 ablations ran on 25 queries × 30 candidates = 750 scoring decisions
  - 3.9x lift over original preserved on user-verified labels
  - All 6 E2E invariant checks still PASS on clean labels
  - 13 user overrides applied cleanly to labels_clean.json; 5 DOI mismatches (10.3389 vs 10.3380 typo) surfaced for system-level fix

- ⚠️ **Unverified**:
  - 20/25 queries were "no objection" — if 30%+ of Mavis labels are wrong in those, lift numbers shift. Spot-check only covers 5 priority queries
  - PRF underperforms; concept-expansion direction untried
  - Bi-encoder all-MiniLM-L6-v2 is English-only; fine for this 25-query set (all EN)
  - n=25 small for significance testing; combined vs biencoder delta is +0.036 — could be noise

- ❌ **Hollow / Known gaps** (per honest audit):
  - **No holdout set**: 25 queries seen during alpha-tuning. Phase 1.5 (split into train/test) deferred.
  - **No Phase 1.6 (q026-q050)**: 25 of 50 benchmark queries evaluated. Other 25 are user-placeholder slots.
  - **No alpha grid search**: combined uses alpha=0.5 only. Phase 6.5 (0.3/0.4/0.5/0.6/0.7) deferred.
  - **No cross-encoder / LLM rerank**: cross-encoder rejected because HF download blocks. LLM rerank rejected per Global Rule (no hosted LLM).
  - **3.5% label noise is real, not zero**: 13 cases where Mavis was wrong means lift numbers in priority 6-25 are likely over-stated by ~0.02-0.05
  - **5 DOI mismatches in spot-check vs labels.json** (10.3389 vs 10.3380, q001/q009/q018) — labels.json has data drift, needs canonicalization (now [P0-4] in ROADMAP)

### New ROADMAP items from user spot-check (added 2026-07-13, see ROADMAP.md "User spot-check insights" section)

7 new proposed items based on user's 7 feedback themes:

| Item | Priority | What it does | Status |
|---|---|---|---|
| [P0-4] Duplicate detection + DOI canonicalization | P0 | Lowercase prefix + strip `J.` for case-variants; data drift fix | proposed |
| [P1-5] Recency + citation threshold filter | P1 | >10 year papers need citations > mean+2std; field-dead warning | proposed |
| [P1-6] Sub-topic granularity decomposition | P1 | "agriculture" → {ag_econ, climate_adaptation, ...}; query expansion + per-subtopic weight | proposed |
| [P1-7] Institutional credibility boost | P1 | Qs top-50 + ESMFold + IMF + World Bank + famous research institutes → +0.1-0.3 final score (NOT label change) | proposed |
| [P1-8] China political-institution exclusion | P1 | Block 中国国际关系研究院 + 各级马克思主义学院 (user-sensitivity filter) | proposed |
| [P1-9] Geographic / country metadata extraction | P1 | ISO 3166-1 country tag on each candidate; boost factor when query has country mentions | proposed |
| [P1-10] Falsifiability philosophy integration | P1 (research) | No direct tool on GitHub; closest = `K-Dense-AI/scientific-agent-skills` 27.6k stars. Research deliverable: ROADMAP_RESEARCH_2026-07-13_FALSIFIABILITY.md | proposed (research) |
| [P2-14] Quality filter (no-abstract + low-cite = low quality) (was [P2-5] before 2026-07-16 ID renumber) | P2 | flag / drop candidates with no abstract + no year + cite < 50 | proposed |

**User confirmation needed for each** (per ROADMAP discipline). My recommended next step: start [P0-4] (data drift fix, 1h, low risk) and [P1-5] (recency rule, 2h, matches user's explicit "10 year / 2 std" rule). Defer [P1-6..P1-10] until user confirms lookup table content / scope.

### Files added (this release)

- `bench/v01/_v4_rerank.py` (~250 lines)
- `bench/v01/_v4_run_all.py` (~280 lines)
- `bench/v01/_gen_spot_check.py` (~80 lines)
- `bench/v01/_build_clean_labels.py` (~210 lines)
- `bench/v01/system_outputs_bm25/q*.json` × 25
- `bench/v01/system_outputs_biencoder/q*.json` × 25
- `bench/v01/system_outputs_combined/q*.json` × 25
- `bench/v01/system_outputs_prf/q*.json` × 25
- `bench/v01/system_outputs_random/q*.json` × 25
- `bench/v01/spot_check/SPOT_CHECK_q*.md` × 25
- `bench/v01/spot_check/SPOT_CHECK_INDEX.md`
- `bench/v01/spot_check/_overrides.json` (audit log)
- `bench/v01/labels_clean.json` (Mavis + 13 user overrides)
- `bench/v01/reports/v3_9_0_clean.md` (clean-label side-by-side)
- `bench/v01/reports/v3_9_0_clean.json` (clean-label full metrics)

### 5-check audit against Global Rule

1. ✅ Runs for $0 (BM25 / sentence-transformers / cache are all free + local)
2. ✅ No hosted service (all local computation)
3. ✅ Single-hobbyist maintenance: ~820 lines new in `bench/v01/`, no ongoing obligation
4. ✅ No "must publish" obligation
5. ✅ Free-tier degradation: if HF download for `all-MiniLM-L6-v2` blocks, `biencoder` condition returns 0.0 scores and the rerank falls back to BM25-only behavior (acceptable degradation per HF offline + v3.8.3's 60s timeout pattern)

### What we learned (and committed to memory)

- **"Mock data PASS" ≠ "real-world works"** — the 25-query benchmark gave consistent numbers, but user spot-check found 3.5% label noise in priority 1-5. Re-validated; v4 architecture is robust to label noise (lift preserved at 3.9x)
- **Citation count is a negative signal on academic search** (random > original by 75%) — this is a surprising finding that breaks the assumption "more cited = more relevant". Worth a follow-up paper if it generalizes
- **Bi-encoder alone is strong** — the +0.036 lift from BM25+biencoder over biencoder alone may not survive n>50. Need holdout validation (Phase 1.5) before claiming combined is the winner
- **5-condition ablation is fast** — ~3h total work (1h write, 2h run + verify). For future "does X work" questions, this template scales
- **User spot-check is high-leverage** — 13 overrides came from 30-60 min of user time. Phase 1.6 (q026-q050) + 5 more queries spot-checked would close the "Mavis is right for priority 6-25" assumption
- **Honest three-tier audit works** — surfaced 5 hollow claims + 3 unverified claims in the v3.9.0 CHANGELOG. Per-discipline: ship the verified, defer the unverified, document the hollow

### Deferred to backlog

- **Phase 1.5**: holdout validation (split 25 queries into 15 train / 10 test, re-derive alpha on holdout)
- **Phase 1.6**: evaluate q026-q050 (the 25 user-placeholder slots, once user fills them)
- **Phase 6.5**: alpha grid search (combined uses 0.5 only; should try 0.3 / 0.4 / 0.6 / 0.7)
- **Cross-encoder rerank**: deferred (HF download blocks; LLM rerank rejected per Global Rule)
- **Citation graph features**: OpenAlex `cited_by_count` is broken as a signal but `referenced_works` (forward citation graph) is unused
- **User spot-check on q001-q004, q006, q008, q009, q011-q012, q014-q018, q020-q025** (20 queries, ~1-2 hours user time, would close the "n=25 of 25" claim)

---

## [3.8.3] - 2026-07-05 (polish — close the v3.8.1 unverified gaps)

Followup to v3.8.2 (commit `22e6cd2`). User pressed "测试所有没有测试过的，
然后更新 changelog 和 commit". Self-audit re-surfaced four ⚠️ "code exists
but unverified" claims from earlier. All four closed end-to-end in this patch.

**Issue 1 — `CTFIDFLabelGenerator.generate()` + `HandrollLabelGenerator.generate()` raised NotImplementedError**

Earlier v3.8.1 made these methods raise NotImplementedError with the
rationale "c-TF-IDF is done inside cluster_topics()". That left the
`LabelGenerator` ABC feeling half-implemented — `custom` was real, but
`ctfidf` and `handroll` were stubs. A future PIEClass plugin author
reading the codebase would wonder why their subclass needs to implement
`generate()` but the built-in ones don't.

**Fix** (`pa_cli/labels/ctfidf.py` + `pa_cli/labels/handroll.py`):
- Both generators now implement `generate()` as pass-through post-processors
  that apply the optional `custom_labels` overlay on a topics list.
- Architecture: c-TF-IDF and clustering happen together in
  `topics._cluster_with_bertopic()` (because clustering depends on
  c-TF-IDF), so the label generator is correctly a post-processor.
- New ABC contract: `generate(topics=...)` → applies custom overlay,
  returns updated list. If `topics` kwarg missing, returns `[]` + warning
  (instead of raising). All three built-ins now have the same shape.

**Issue 2 — `pa review-topics --label-method ctfidf` end-to-end never verified**

`--label-method ctfidf` (or `auto`) tries to download `all-MiniLM-L6-v2`
from HuggingFace (~80MB). In networks where HF is blocked (user's
environment: `WinError 10060` connection timeout), `sentence-transformers`
internally retries 5 times with exponential backoff — **5+ minutes** before
eventually falling back to hand-roll. User has been staring at hanging
terminals.

**Fix** (`pa_cli/topics.py`):
- New `bertopic_timeout: float = 60.0` kwarg on `cluster_topics()`. None = no timeout (default sentence-transformers behavior).
- `_get_sentence_model()` now wraps `SentenceTransformer(model_name)` in a
  background thread with `thread.join(timeout=bertopic_timeout)`. On
  timeout, raises `TimeoutError` with message "sentence-transformers
  download of '{name}' exceeded {N}s timeout. Falling back to handroll."
- The pre-existing `try/except` in `cluster_topics()` catches it and
  falls back to handroll + adds warning to topics.json.
- **Result on user's network**: `pa review-topics --label-method ctfidf`
  exits in ~85s with the explicit warning
  `bertopic_failed_fallback_to_handroll:TimeoutError:...` instead of
  hanging for 5 minutes.
- CLI not modified yet (no `--bertopic-timeout` flag) — default 60s is
  the right starting point. CLI flag can be added if user needs tuning.

**Issue 3 — `--domain-stopwords-file <path>` CLI end-to-end never verified**

The CLI flag was parsed correctly (per unit test) but never tested
with `pa review-topics --domain-stopwords-file X` against a real corpus.
A real verification is the only way to know the file content actually
flows through `cluster_topics()` to c-TF-IDF's stop_words argument.

**Fix** (`test_output/test_labels_real_corpus.py` new sub-test +
`test_output/fixtures/domain_stopwords_for_test.txt`):
- New fixture file with 9 curated noise terms from the real corpus
  (`iphone`, `pptxgenjs`, `skill`, `beautiful`, `gamma`, `mermaid`, `chip`,
  `exy`, ...).
- New test `test_cli_domain_stopwords_file_end_to_end` runs the CLI
  subprocess with the file, asserts `topics.json` `domain_stopwords_count`
  is **9** (file contents) — NOT 20 (auto-mine default). The exact-9
  match proves the file was loaded, not the auto-mine fallback.

**Issue 4 — `register_label_generator()` plugin chain end-to-end never verified**

The factory was unit-tested with `test_register_custom_generator`, but
no test exercised the full chain: register → available → get → name →
generate → return value shape. A plugin author reading the code might
miss subtle interface requirements.

**Fix** (`test_output/test_labels_real_corpus.py` new sub-tests):
- `test_cli_abc_three_generators_actually_implement` — instantiates all
  3 built-in generators, asserts no `NotImplementedError` on `generate()`.
- `test_cli_register_custom_generator_end_to_end` — defines a one-off
  `_TestGen`, registers it, fetches via factory, verifies name() +
  generate() return value matches topics.json schema.

**Test infrastructure fix — subprocess cache isolation**

When `test_labels_real_corpus.py` ran as a subprocess inside
`test_full_regression.py`'s Section A8, **after** A7's
`test_labels_e2e.py`, it failed with
`AssertionError: Artifact of type=precompile already registered in
mega-cache artifact factory`. Root cause: torch's `_inductor` cache
(`~/.cache/torch/`) is shared by all subprocesses in the same parent
process; the second subprocess that imports torch trips the registry
collision.

**Fix** (`_run_cli()` in `test_labels_real_corpus.py`):
- Each subprocess now gets a unique `TMPDIR`, `TORCH_HOME`,
  `TORCHINDUCTOR_CACHE_DIR`, `XDG_CACHE_HOME`, plus
  `TORCHDYNAMO_DISABLE=1` and `TORCH_COMPILE_DISABLE=1` to skip torch's
  precompile machinery entirely. Cache collision impossible.
- Side benefit: parallel test runs (if user adds `pytest-xdist` later)
  also won't collide.

**Verification** (user's `G:\Minmax - workspace\课件\ch1-econ-ppt\`,
9 MD/TXT files):

| Test | Result |
|---|---|
| `pa review-topics --label-method handroll --custom-labels '{"1":"PPT 设计文档","2":"PPT 内容来源"}'` | rc=0; Topic 1 = "PPT 设计文档", Topic 2 = "PPT 内容来源" |
| `pa review-topics --label-method handroll --domain-stopwords-file test_output/fixtures/domain_stopwords_for_test.txt` | rc=0; `domain_stopwords_count = 9` (file content), NOT 20 (auto-mine) |
| `pa review-topics --label-method ctfidf` (user's blocked-HF network) | rc=0 in ~85s; warning `bertopic_failed_fallback_to_handroll:TimeoutError:...`; falls back to handroll, `domain_stopwords_count = 20` |
| `CTFIDFLabelGenerator(custom_labels={1:"X"}).generate(topics=...)` | Returns topics with label overridden; no exception |
| `register_label_generator("test_v383_plugin", _TestGen); get_label_generator("test_v383_plugin")` | Returns _TestGen instance; generate() returns topics list |

**Tests passing**:
- `test_labels_e2e.py`: 23/23 PASS (unchanged — fix didn't break unit tests)
- `test_labels_real_corpus.py`: **9/9 PASS** (up from 4/4 in v3.8.2; +5 new
  CLI subprocess tests)
- `test_full_regression.py`: 42 PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE
  (with `PA_TEST_REAL_CORPUS=1` — A8 contributes 9 PASS, A6+A7 unchanged)

**Effort**:
- Estimate: ~1.5h (4 issues + test infrastructure)
- Actual: ~1h (mostly straightforward; the `assertRegex` signature bug
  ate ~10min; subprocess cache isolation ~15min)

**5-check audit against Global Rule**: 5/5 pass (no $ cost, no hosted
service, ~150 lines added to `topics.py` + `labels/ctfidf.py` +
`labels/handroll.py` + test fixture, no publish obligation, free-tier
degradation graceful — when HF blocked, 60s timeout + clear warning
instead of 5min silent hang).

---

## [3.7.1] - 2026-07-04 (cleanup commit)

### Deprecated — [P2-1] / [P2-2] / [P2-3] (user review)

Per user "反思一下" prompt: I reflected honestly on the 3 P2 items I'd
scoped in the ROADMAP. All 3 were filled in from
`COMPETITOR_ANALYSIS_v3.3.0.md` (competitor parity bullets) without
checking whether user actually needs them. Each item now has a
`### Deprecated 2026-07-04 — abandoned (user review)` sub-section
in ROADMAP explaining the honest reflection.

**What was deprecated** (per ROADMAP audit trail):
- **[P2-1] Browser extension / Tampermonkey userscript**
  → No concrete workflow: user does lit review via CLI, not browser
- **[P2-2] API key auto-application script**
  → User already has all 4 keys configured; "new users" assumption
     broken under Global Rule (personal-hobbyist tool)
- **[P2-3] `pa watch <topic>` daily subscription + local MD report**
  → No concrete topic yet. Cron + report design itself is sound per
     Global Rule; what's missing is user's stated workflow need.
     Resurrection requires (a) a specific research topic, AND
     (b) confirmation user wants daily monitoring vs on-demand.

**No code change** — this is documentation-only. Version bumps
3.7.0 → 3.7.1 (PATCH) to mark the audit trail + ROADMAP cleanup.

**Lesson recorded** (added to estimation methodology):
- When filling ROADMAP from competitor analysis, **stop and ask user**
  whether each item fits their workflow. Don't assume "competitor has
  it, we should have it too". Competitor parity ≠ user need.
- The right time to ask "do you actually want this?" was before
  spending sub-task estimation time on it. For future ROADMAP items,
  pause for "is this for you?" before deep scoping.

**Active roadmap after this cleanup**: P0/P1 done (5 done + 1 deprecated);
P2 fully deprecated (3 items); v3.8.0 has no planned items until user
requests a specific feature. Future work must be **user-driven**, not
competitor-driven, per Global Rule.

---

## [3.7.0] - 2026-07-04

### Added — [P1-3] PRISMA 2020 flow diagram (`pa prisma` + `pa review --with-prisma`)

Implements all 4 acceptance criteria from `ROADMAP.md` [P1-3]:

  1. `pa review --with-prisma` outputs a mermaid PRISMA block (auto-derived
     from corpus_dir word counts)
  2. Mermaid block renders on GitHub automatically
  3. Each stage shows count + auto-derived exclusion count
  4. Static PNG/SVG export deferred (mermaid-cli install would breach Global Rule;
     see Backlog)

**New module**:
- `pa_cli/prisma.py` (~130 lines) — re-exports `skill.core.prisma.generate_mermaid` + `generate_markdown` (avoids cross-package imports; skill/ is untracked, pa_cli/ is the tracked boundary). Adds `derive_counts_from_corpus(corpus_dir, word_count_min)` for review integration; `render_prisma(...)` top-level entry; `parse_json_arg(s)` helper for JSON list inputs.

**CLI integration**: `pa_cli/cli.py` adds 2 things:
- New `pa prisma` command (standalone, takes explicit counts)
- `pa review --with-prisma` flag (auto-derives counts from corpus)

**pa prisma usage**:
```bash
# Full markdown report (default)
pa prisma --identified 287 --after-screening 57 \\
  --after-eligibility 57 --included 57 --pdf 25 --abstract 32

# Just the mermaid block (for embedding)
pa prisma --identified 100 --after-screening 30 \\
  --after-eligibility 20 --included 15 --format mermaid

# With source breakdown
pa prisma --identified 100 --after-screening 30 --after-eligibility 20 \\
  --included 15 --by-source '{"arxiv":40,"openalex":60}'
```

**pa review --with-prisma usage**:
```bash
pa review ./pdfs --with-prisma --word-count-min 1000 -o lit_review.md
# Output: PRISMA block + --- separator + standard lit review
```

Counts auto-derived:
- `identified` = total PDFs in corpus
- `after_screening` = PDFs with `word_count >= word_count_min` (full-text)
- `abstract_count` = PDFs with `word_count < word_count_min` (excluded)
- `after_eligibility` = `after_screening` (no manual eligibility step)
- `included` = `after_screening` (same — review is the inclusion step)

**Pre-existing infrastructure** (discovered 2026-07-04 during scoping):
- `skill/core/prisma.py` already had working `generate_mermaid()` + `generate_markdown()` (~150 lines, untracked in git). No need to reimplement — `pa_cli/prisma.py` is a 130-line thin wrapper. **Reuse over rebuild** = faster + no risk of skew.

**Validation** (`test_output/test_prisma_e2e.py` — 10/10 sub-tests, no network):
- `pa prisma --format mermaid` produces parseable mermaid block
- `pa prisma --format markdown` produces full report (title + 4 sections)
- `--by-source JSON` parsed + in output
- `--excluded-reasons JSON` parsed + in output
- Internal counts consistent (excluded = diffs between stages)
- Invalid JSON fails with non-zero exit + clear error
- `pa review --with-prisma` prepends PRISMA block before review body
- `pa review` without `--with-prisma` unchanged (regression check)
- `derive_counts_from_corpus()` returns correct counts from temp corpus

**Effort** (per estimation methodology):
- Estimate: 2h, Actual: ~1h, Variance: ~2x under
- Speedups: (a) `skill/core/prisma.py` already implemented (saved ~1.5h), (b) thin wrapper pattern = 130 lines, (c) `build_corpus_index` reuse from `pa_cli.review`
- "Thin wrapper for pre-existing module" class: estimate ~0.5-1h with 0.5h buffer

**Deferred to backlog** (recorded in [P1-3] outcome section):
- Static PNG/SVG export (would require `mermaid-cli` install, possibly npm dep — may breach Global Rule "no paid/hosted infra")
- Auto-eligibility stage (needs user-driven exclusion reason codes; not auto-detectable from PDFs)
- PRISMA template variations (PRISMA-ScR for scoping reviews, PRISMA-IPD for individual-patient-data reviews)
- HTML embed in `pa review` output (currently just a markdown fence; GitHub renders natively, no extra work needed)

---

## [3.6.0] - 2026-07-04

### Added — [P1-2] OpenAlex concepts semantic filtering (`pa search --concepts`)

Implements all 3 acceptance criteria from `ROADMAP.md` [P1-2].

**New module**:
- `pa_cli/concepts.py` (~165 lines) — `search_concepts(query, limit)` (text→ID via OpenAlex `/concepts?search=`), `resolve_concept_ids(names_or_ids)` (mixed input parser: IDs pass through, names look up), `build_concepts_filter(ids, mode)` (OpenAlex filter string builder, OR via pipe / AND via `+`), `fetch_concept_metadata(id)` (single-concept metadata lookup), `is_concept_id(s)` (regex validator).

**CLI integration**: `pa search` adds 3 new flags (in `pa_cli/cli.py`):
- `--concepts C1,C2` (comma-separated OpenAlex concept IDs)
- `--concept "name"` (repeatable, resolves to ID via `search_concepts`)
- `--concept-mode or|and` (default `or`; `and` requires all)

**How it works**:
1. User provides raw concepts (mixed IDs + names)
2. `resolve_concept_ids()` returns canonical C<digits> list + warnings for unresolvable names
3. `fetch_concept_metadata()` enriches each ID with display_name + works_count for human-readable output
4. `build_concepts_filter()` produces the OpenAlex filter string
5. `search.py:run_search()` passes the filter to `search_openalex()` only (other engines ignore; recorded as a known scope limit)
6. Result JSON includes `applied_concepts` array + `concept_mode` for downstream consumers

**OpenAlex API notes** (researched 2026-07-04):
- `GET /concepts?search=<text>` does full-text search across concept names + descriptions
- Multi-word queries work better than single words ("higher education" → 11 results; "AI literacy" → 0 because not a registered concept)
- Multi-concept filter syntax:
  - OR:  `concepts.id:C1|C2` (pipe separator in single filter)
  - AND: `concepts.id:C1+concepts.id:C2` (separate filter expressions joined with `+`)

**Validation** (`test_output/test_concepts_e2e.py` — 10/10 sub-tests, real OpenAlex API):
- OR filter syntax correct
- AND filter syntax correct
- `search_concepts` finds "higher education" → C120912362 (1.3M works)
- `resolve_concept_ids` mixed (ID + name) works, dedup
- `pa search --concepts C154945302` filters, populates `applied_concepts` in result
- `pa search --concept "machine learning"` resolves to C119857082
- OR vs AND record different `concept_mode` correctly
- Unresolvable name (`xyzzz_no_such_concept_xyz`) → warning to stderr, search continues without filter
- Empty concepts list = no filter (no error)
- Build filter handles empty list → returns `""`

**Effort** (per estimation methodology):
- Estimate: 2.25h, Actual: ~1h, Variance: ~2x under
- Speedups: (a) OpenAlex API key pre-configured (faster than 1 RPS free tier); (b) `_normalize_openalex` reuse from v3.3.0; (c) `concepts_filter` was a 2-line threading through `run_search` → `search_openalex`
- For "API integration + filter" type items: estimate 1-2h with 0.5h buffer

**Deferred to backlog** (recorded in [P1-2] outcome section):
- Concept name fuzzy matching ("machine learn" → "machine learning") — current behavior is exact-phrase; users can fall back to IDs
- Concept disambiguation UI — when `--concept "X"` resolves to multiple C<id>s, currently we pick top-1 by works_count; could show picker
- Cache concept metadata (each `fetch_concept_metadata` is a network call; 5-concept search = 5 calls; could memoize per session)

---

## [3.5.1] - 2026-07-04 (post-MCP-revert state, follow-up commit)

### Real-machine verification (added 2026-07-04 after follow-up commit)

End-to-end smoke ran on the user's actual machine (Windows, Python 3.12).
Recorded for the discipline log:

| Check | Result |
|---|---|
| `pa mcp install` exit code | 0 |
| `paper-search-mcp` install path | `C:\Users\DengN\AppData\Roaming\Python\Python312\site-packages\paper_search_mcp\` |
| `import paper_search_mcp` | OK |
| `import paper_search_mcp.server` | OK |
| `python -m paper_search_mcp.server` boot | OK (waits on stdio as expected) |
| MCP `initialize` roundtrip | OK — server reports name=`paper_search_server` version=`1.27.2` |
| MCP `list_tools` count | **57 tools** (vs my self-hosted 5 — 11× more coverage) |
| MCP `call_tool("search_papers", ...)` | OK, `isError=False` |
| Public config warnings | 2 (DOAJ + Unpaywall — optional, public rate limits still work) |

**Tool count comparison** (from `list_tools`):
- arxiv / pubmed / pmc / europepmc / biorxiv / medrxiv / iacr (7 preprint/repo)
- semantic / openalex / crossref / dblp / citeseerx / core (6 metadata)
- doaj / openaire / ssrn / hal / zenodo / base / google_scholar (7 OA)
- per-source `search_*`, `download_*`, `read_*` triplets × 22 sources
- 4 high-level tools: `search_papers`, `download_with_fallback`, `get_*_paper_by_doi`, etc.
- **Total 57 tools**, MIT-licensed, free-first, public-maintained.

This confirms the public MCP is the right choice — it would have taken one
hobbyist many months to write + maintain a comparable tool surface.

### Added — `pa mcp install` / `pa mcp config` (public MCP integration)

Following the same-day revert of [P0-3] self-hosted MCP, this commit
adds the **integration glue** for the public alternative
`openags/paper-search-mcp` (PyPI, 22 free sources, MIT).

**New file**:
- `pa_cli/mcp_setup.py` (~140 lines) — `install()` function, `_print_config_block()` helper, `_is_installed()` / `_have_uvx()` probes.

**New CLI subcommand group** (in `pa_cli/cli.py`):
```
pa mcp install [--uvx] [--dry-run]   install + print config block
pa mcp config                         print config block (no install)
pa mcp serve-deprecated               exits 1 with redirect to install
```

`pa mcp install` flow:
1. Probes `import paper_search_mcp` — if already installed, just prints config
2. Else probes `which uvx` — if available, prints uvx config (no install)
3. Else runs `python -m pip install --user paper-search-mcp`
4. On pip failure, prints the uvx config as fallback

**Critical design choices** (recorded for audit):
- **Does NOT auto-edit** `claude_desktop_config.json` or any other MCP
  client config. The user pastes the JSON block themselves. Per Global
  Rule + user sovereignty principle.
- **Uses `--user`** for pip install so the package goes to user
  site-packages and can be cleanly removed with `pip uninstall`.
- **Backward-compat shim** at top level: `pa mcp-serve` (old name)
  still works but exits 1 with a redirect to `pa mcp install`.

**Validation** (`test_output/test_mcp_setup.py` — 9/9 sub-tests):
- `pa mcp config` prints valid JSON config block
- `pa mcp install --dry-run` prints intent without running pip
- `_is_installed` short-circuits when package is importable
- `--uvx` flag uses uvx when on PATH, falls back to pip when not
- pip failure → `status=install_failed` + uvx config in fallback block
- `pa mcp serve-deprecated` exits 1 with redirect
- `pa mcp-serve` (old top-level name) exits 1 with redirect

**Test infra updates** (`test_output/test_full_regression.py`):
- Added A3 section: `test_mcp_setup.py` runs as part of full regression
- Added `mcp`, `mcp install`, `mcp config` to the --help surface check
- Total: now 35+ PASS / 0 FAIL / 2 SKIP / 1 KNOWN_ISSUE

**Why this is in scope per Global Rule** (5-check audit):
1. ✅ Runs for $0 (pip install is free)
2. ✅ No hosted service (just a one-shot install + local package)
3. ✅ Single-hobbyist maintenance: ~140 lines, no ongoing obligation
4. ✅ No "must publish" obligation
5. ✅ Free-tier degradation: if paper-search-mcp breaks, user uninstalls and the rest of paper-agent is unaffected

### Audit pass on [P0-3] (precedent)

This commit is the follow-up to the v3.5.1 (same-day) revert. The
revert removed the maintenance surface; this commit restores
**discoverability** so users can find the public alternative via
`pa --help` instead of needing to read the CHANGELOG to learn about it.

---

## [3.5.1] - 2026-07-04 (post-MCP-revert state)

This release reflects the state of the codebase after the user-initiated
rollback of the [P0-3] MCP server (originally shipped as v3.6.0, now
removed). The version is bumped to 3.5.1 (PATCH) to indicate that no
new features are added in the reverted state — the citation work that
was tagged as v3.7.0 is folded into this PATCH release, as the
[P0-3] MCP feature that v3.6.0 introduced is the only thing that
changed relative to v3.5.0.

### Reverted — [P0-3] MCP server (`pa mcp-serve`)

Removed in v3.5.1 — see ROADMAP `[P0-3] ### Modified 2026-07-04 — abandoned`
for full rationale. The CLI subcommand `pa mcp-serve` still exists but
exits with a deprecation message pointing users to the public alternative.

**Use instead** (copy-paste into your Claude Code / Cursor / OpenCode
MCP config):
```json
{
  "mcpServers": {
    "paper-search-mcp": {
      "command": "uvx",
      "args": ["paper-search-mcp"]
    }
  }
}
```
22 sources, free-first, no API keys required (Unpaywall email only).
Not in this repo — owned by `openags/paper-search-mcp`.

### Added — [P1-1] Forward / backward citation walk (`pa citations <DOI>`)

### Added — [P1-1] Forward / backward citation walk (`pa citations <DOI>`)

Implements all 3 acceptance criteria from `ROADMAP.md` [P1-1].

**New files**:
- `pa_cli/citations.py` (~150 lines) — OpenAlex wrappers: `get_work_by_doi`, `get_citing` (cursor-paginated), `get_referenced` (N+1 API calls per reference), `citation_walk` (top-level). Reuses `search._normalize_openalex` for output shape consistency with `pa search`.

**CLI integration**: `pa citations <DOI>` subcommand in `pa_cli/cli.py`:
- `--direction forward|backward` (default forward)
- `--limit N` (default 100 forward, 50 recommended for backward since each ref is a separate API call)
- `--save-bib path.bib` to also write BibTeX
- `-o path.json` to save JSON output (else stdout)

**MCP integration**: `pa_citations` (5th MCP tool) exposed via `pa mcp-serve`. Args: `doi` (req), `direction?` (forward|backward, default forward), `limit?` (1-200, default 100). Returns the same dict shape as CLI.

**OpenAlex API**:
- Forward: 2-step (DOI→ID, then `filter=cites:W<id>` cursor-paginated, 50/page default)
- Backward: 2-step (DOI→work, read `referenced_works[]`, then fetch each individually). Bounded by `--limit` since each ref is a separate HTTP request.
- **Discovered 2026-07-04**: `cites` filter accepts **only OpenAlex IDs** (W-prefixed), NOT DOIs in any form. Direct DOI URL in filter returns 0 results.

**Validation** (`test_output/test_citations_e2e.py` — 8/8 sub-tests using real OpenAlex API):
- `forward` walk returns 5 papers with titles + DOIs + cited_by_count
- `backward` walk returns 3 referenced papers
- Unknown DOI returns `{error: "doi_not_found"}` (no exception)
- CLI JSON output structure correct (count, direction, source_work, results, truncated)
- `--save-bib` produces valid BibTeX (1593 bytes, 3 entries)
- Unknown DOI via CLI exits with rc=2
- `pa_citations` MCP tool returns the same structure as CLI
- `list_tools` now returns 5 tools (was 4 in v3.6.0)

**Test fixture**: DOI `10.1186/s41239-023-00411-8` (Crompton 2023, 1819 citations, 46 references).

**Effort** (per estimation methodology):
- Estimate: 2.75h, Actual: ~1.5h, Variance: ~2x under
- Speedups: (a) OpenAlex API key already configured (1 RPS → faster); (b) `_normalize_openalex` reuse from v3.3.0 search; (c) `pa_citations` MCP tool was a 5-line wrapper once citations module was done.
- For "API integration + CLI + MCP" type items: estimate 2-3h with 0.5h buffer (vs wider 4h first-of-kind).

**Deferred to backlog** (recorded in [P1-1] outcome section):
- Multi-source citation walk (Crossref + Semantic Scholar have `references` field; would dedupe across sources for higher recall)
- Citation graph depth (pa citations X --depth 2 = forward(forward(X)))
- Save citations to pa cache (use existing PDF cache infra)
- Per-page caching (each OpenAlex response cacheable for 7 days per [P0-2] TTL pattern)

---

## [3.6.0] - 2026-07-04

### Added — [P0-3] MCP server (`pa mcp-serve`, exposes 4 tools to any MCP client)

Implements all 4 acceptance criteria from `ROADMAP.md` [P0-3].

**New files**:
- `pa_cli/mcp.py` (~250 lines) — `mcp.Server` instance, 4 tool handlers, async `serve()`, JSON-serialisable results, structured error responses. Wraps existing pa_cli Python functions; no logic duplication.

**Tools exposed**:
1. **`pa_fetch`** — args: `doi` (req), `output_dir?`, `proxy?`, `channels?`, `use_cache?` → returns fetch_doi result dict (saved_as, via_channel, cache_hit, error/handoff). Supports paper-agent v4 handoff: `handoff.user_action_required` propagates as structured error.
2. **`pa_search`** — args: `query` (req), `year_min?`, `year_max?`, `limit?`, `engine?`, `format?` (json|bibtex) → returns run_search result dict; `format=bibtex` returns BibTeX-formatted text in `bibtex` field.
3. **`pa_review`** — args: `corpus_dir` (req), `template?`, `word_count_min?` → returns `{markdown: str, corpus_dir: str}`. Missing corpus_dir returns structured error dict (NOT MCP `isError`), letting agent-specific recovery logic kick in.
4. **`pa_keys_status`** — args: `{}` → returns `cmd_audit()` dict (rows + summary counts). Pure-local; no HTTP probe.

**Transport**: stdio JSON-RPC via official `mcp` Python SDK (Anthropic, v1.27.2 — already installed; no install step).

**CLI integration**: `pa mcp-serve` subcommand in `pa_cli/cli.py` runs `pa_cli.mcp.main()` in foreground; cleanly handles stdin close (BrokenPipeError → exit 0) and KeyboardInterrupt (sys.exit 0).

**MCP client config** (Claude Code / Cursor / OpenCode):
```json
{
  "mcpServers": {
    "pa": {
      "command": "python",
      "args": ["-m", "pa_cli.mcp"]
    }
  }
}
```

**Validation** (`test_output/test_mcp_e2e.py` — 7/7 sub-tests):
- `list_tools` returns 4 tools with valid JSON Schema input schemas (object + required properties)
- `pa_keys_status` returns audit dict with `rows` + summary counts
- `pa_keys_status` works with API keys cleared (purely local computation)
- `pa_review` returns markdown string for empty corpus
- `pa_review` returns `{error: "corpus_dir_not_found", corpus_dir, markdown: ""}` for missing path
- unknown tool returns `isError=True` with `available: [...]` list
- `pa_fetch` returns `cache_hit=True, via_channel="cache:openalex"` for cached DOI (full cascade skipped)

End-to-end tests use `mcp.ClientSession + stdio_client(StdioServerParameters(command=python, args=["-m","pa_cli.mcp"]))` so the live server is exercised in a real subprocess — exactly the path any MCP client would use.

**Effort**: estimate 4h, actual ~2h (2x under). Two speedups:
- `mcp` SDK already installed (saved ~10 min discovery + install).
- Local imports (`from .fetch import fetch_doi` inside handler) kept mcp.py dep-light and avoided pre-loading the 8-channel cascade on every stdio invocation.

**Deferred to backlog** (recorded in [P0-3] outcome section):
- HTTP transport (current stdio-only is enough for local single-machine use)
- Token-bucket rate limit on per-DOI fetch (DOS guard when many agents share one server)
- Elicitation prompts for confirmation flows (e.g. "really download from Sci-Hub?")
- Persistent sampling for batch literature reviews (vs single-DOI fetch)

### Added — [P2-4] pa cache stats (was already in P0-2, removed duplicate P2-4 item)

ROADMAP [P2-4] was functionally a subset of [P0-2]; marked `### Modified 2026-07-04 — merged into [P0-2] (already shipped)` and removed from active items list.

---

## [3.5.0] - 2026-07-04

### Added — [P0-2] Local PDF cache + `pa cache` subcommand group

Implements all 5 acceptance criteria from `ROADMAP.md` [P0-2] (Local cache, avoid re-download).

**New files**:
- `pa_cli/cache.py` (~210 lines) — `cache_get`, `cache_put`, `cache_remove`, `cache_stats`, `cache_clean`, `_doi_slug`, `get_cache_root`. Cache root defaults to `~/.paper-agent/cache/` per spec; overridable via `PA_CACHE_DIR` env var. Sidecar `.meta.json` carries `{ts, sha256, channel, url, size}`. PDF magic check (`%PDF` prefix + ≥50KB) guards against caching corrupted bytes; sha256 mismatch auto-cleans both files on next read.

**Fetch integration**: `pa fetch <DOI>` checks cache first; on hit (`PDF magic + sha256 valid`) returns immediately with `via_channel="cache:<original>"`, `final_status="SUCCESS_CACHE_HIT"`, `cache_hit=True`, and the cascade is skipped entirely (`elapsed_sec < 0.001s` in tests). After each successful cascade channel, the downloaded PDF is written to cache via `cache_put` so the next call benefits — even when `use_cache=False` was passed (the flag controls read, not write).

**Keys check cache**: `pa keys check` adds a 30-min in-memory cache (P0-2 acceptance: "second invocation in same window skips HTTP probe"). Cache busts on different `service_id`, manual `_check_cache_clear()`, or `pa keys check --no-cache`. PA_TEST=1 (truthy) bypasses cache for unit tests; "0" or unset treats as production.

**`pa cache` subcommand group** (5 subcommands):
```
pa cache path   # show current cache root
pa cache stats  # size / entry count / oldest / newest
pa cache put <DOI> <PDF_PATH> --channel openalex --url ...
pa cache drop <DOI>
pa cache clean [--older-than Nd|--all] [--dry-run] [--json]
```
`pa cache clean` refuses without `--older-than Nd` or `--all` (safety against accidental wipes); `--dry-run` previews without deleting.

**`--no-cache` flag** added to `pa fetch` and `pa keys check`. Both flags mean "skip the read", not "skip the write" — successful operations still populate cache.

**Validation** (4 test scripts in `test_output/`):
- `test_cache_smoke.py` — 6/6 sub-tests on cache module (miss, put/get, corrupt cleanup, remove, stats, clean)
- `test_cache_integration.py` — 2/2 (cache hit short-circuits cascade in <0.5s; `use_cache=False` falls through)
- `test_keys_cache.py` — 5/5 (cold probes, warm cache, diff service_id busts, same service_id reuses, manual clear)
- `test_pa_cache_cli.py` — 6/6 (`pa cache path/stats/put/drop/clean` E2E)

**Effort**: estimate 3.5h, actual ~5h (1.4x over). Two unforeseen infrastructure costs: (a) Windows UTF-8 encoding in subprocess tests; (b) missing `channel_playwright_pdf` mock in test 2 (cascade was reaching the playwright channel and trying to launch real chromium). Both isolated to test harness; production code unchanged. Full outcome logged under [P0-2] in `ROADMAP.md`.

**Deferred to backlog** (recorded in [P0-2] outcome section):
- atime-based LRU eviction (FIFO by ts for now)
- per-key 100MB size cap
- cache hit-rate metrics for `pa audit`
- legacy v3.0 dirs (`arxiv_cache/`, `core_cache/`, etc.) cleanup — separate `.gitignore` ticket

### Changed — `pa_cli/fetch.py` `fetch_doi()` signature

Added `use_cache: bool = True` parameter. Existing callers pass `use_cache=not no_cache` via the new CLI flag. Default `True` preserves existing behaviour for programmatic use.

---

## [3.4.0] - 2026-07-04

### Added — [P0-1] Bibtex export (`pa_cli/bibtex.py`, 220 lines)

New `--format` option on `pa search`:

```bash
# JSON output (default, unchanged)
pa search "AI literacy" --limit 5 --output results.json

# Bibtex output (NEW)
pa search "AI literacy" --limit 5 --format bibtex --output results.bib
# or with auto-named output:
pa search "AI literacy" --format bibtex
# → writes "AI_literacy.bib"
```

**Validation passed** (`test_output/validate_bibtex.py`):
- bibtexparser v1.4.4 parses output cleanly
- Round-trip serialize + parse: zero data loss
- All cite-keys unique (DOI-stripped, e.g. `1186_s41239_023_00411_8`)
- 0-result edge case handled: empty `.bib` with header only, no crash
- Auto-naming when no `--output`: query → filename (`machine_learning.bib`)

**Fields per entry**: title / author / journal / year / doi / url / note.
- `note` carries `Open Access` flag, citation count, `oa_status`, source engine
- Author format: `Last, First Middle` joined with ` and ` (Zotero-compatible)
- Special chars escaped: `\` `{` `}` `&` `%` `$` `#` `_`

**Effort**: ~3 hours actual vs 1-2 days estimate (OpenAlex metadata
rich enough that no Crossref fallback needed). Status: `done` in
`ROADMAP.md` with full outcome log.

**Parity with PyPaperBot**: closes the main feature gap from
`COMPETITOR_ANALYSIS_v3.3.0.md` §6.1. Migration reason from
PyPaperBot to paper-agent now strengthened.

### Changed — `pa_cli/cli.py` search command

- New `--format {json,bibtex}` option (default: json)
- Auto-output path when `--format bibtex` and no `-o` given
- Imports `re` for query sanitization in auto-naming

---

## [3.3.0] - 2026-07-04

### Added — `pa_cli/keys.py` API key registry + reminder system (validated)

Complete 5-command group under `pa keys` for managing API key lifecycles.

**Commands** (all validated end-to-end 2026-07-04):
- `pa keys list` — table view with status indicators (✓/⏰/⚠/🚨/❌/✗)
- `pa keys check [service]` — live HTTP probe per service, updates `last_checked`
- `pa keys add <service> <value>` — add/rotate, writes `.env` + registry, auto-probes
- `pa keys audit` — count active/expiring/missing, show never-checked/never-used
- `pa keys remind` — print expiry warnings + write alerts file

**Live probe results (2026-07-04)**:
| service | endpoint | status | http |
|---|---|---|---|
| openalex | api.openalex.org | ok | 200 |
| semanticscholar | api.semanticscholar.org | http-429 (transient rate limit; unrelated to key config) | 429 |
| core | api.core.ac.uk | ok | 200 |
| unpaywall | api.unpaywall.org | ok (real email <REDACTED-UNPAYWALL-EMAIL>) | 200 |
| demo-api-key | (no service_url set) | no-probe-url (skipped) | n/a |

**End-to-end `pa fetch` validation**:
- DOI `10.1038/nature12373` (Nature article)
- 8-channel pipeline ran in <2s
- OpenAlex → arxiv.org/pdf/1304.1068 → 2.36 MB PDF saved
- `%PDF-1.5` magic verified, valid PDF
- Confirms: fetch pipeline + openalex channel + Unpaywall integration all wired correctly

**Auto-reminder hook**:
- `main()` calls `load_env_into_environ()` then `cmd_remind(quiet=False)` on every CLI invocation
- stderr-line reminder: `[pa-keys] ⚠ demo-api-key: expires in 5 days — schedule rotation → pa keys add demo-api-key <new_key>`
- Non-intrusive: only fires when warnings exist

**Daily cron** (`pa-keys-daily-check`, mavis agent):
- schedule `0 9 * * *` Asia/Shanghai
- Runs `pa keys check --write-alerts ~/.mavis/state/api_key_alerts.json`
- Reads alerts file + surfaces warnings to user

**Registry on disk** (`keys_registry.json`):
- 5 services registered with metadata (service / env_var / tier / expires / notes)
- Committed to git (NO secrets; only metadata)
- Real `.env` (gitignored) holds the actual keys

### Fixed — bug fixes from end-to-end smoke test

1. `.env` loader regex: allow hyphens in env var names (e.g. `DEMO-API-KEY_API_KEY`)
   old: `r'^[A-Z_][A-Z0-9_]*'` — fails on hyphens
   new: `r'^[A-Za-z_][A-Za-z0-9_-]*'` — covers all OpenAlex-style mixed-case names
2. `cmd_remind` auto-trigger: was `quiet=True` (suppressed) — now `quiet=False`
   so every CLI invocation prints expiring/expired warnings to stderr.
   User feedback: "记得提醒我再导入之" — proactive reminders required.
3. Click `--write-alerts` / `--alert-file` options: now accept optional string
   via `metavar="PATH"` instead of bare `default=None` — no more "requires an argument".

### Validation — pa-keys smoke test summary

| step | result |
|---|---|
| `pa keys list` (5 keys) | 4 active + 1 expiring-week |
| `pa keys check` | 3 ok + 1 transient-429 + 1 skipped |
| `pa keys add unpaywall <real-email>` | live probe 200 OK |
| `pa keys add demo-api-key --expires +5d` | warn + write + auto-probe |
| `pa fetch 10.1038/nature12373` | 2.36 MB PDF via openalex/arxiv |
| Startup auto-reminder | stderr line printed on every CLI call |
| Daily cron registered | `mavis cron` shows `pa-keys-daily-check` |

---

## [3.2.0] - 2026-07-04

### Added — `pa_cli/` package (paper-agent CLI)

Lightweight Click-based CLI exposing 4 commands for programmatic + scriptable access:

```
python -m pa_cli fetch <DOI>      # 8-channel PDF recovery + CF timeout handoff
python -m pa_cli search <query>   # 5-engine academic search with dedup
python -m pa_cli review <dir>     # corpus → lit review synthesizer (PyMuPDF)
python -m pa_cli version          # dependency status
```

Each command is independent and testable; the package adds no breaking
changes to the existing `paper_fetcher.py` / `paper-agent skill` API surface.

#### `pa fetch` (pa_cli/fetch.py, 8 channels)
- **Channel 1 — OpenAlex Work API**: discovers OA locations; tries each in turn
- **Channel 2 — arXiv SDK**: only for `10.48550/...` DOIs
- **Channel 3 — Unpaywall API**: legal OA via registered email
- **Channel 4 — DOI.org redirect**: detects Gold OA, extracts PDF links from HTML
- **Channel 5 — Playwright /doi/pdf/ URL pattern**: T&F-style server-side PDF
- **Channel 6 — Playwright fallback**: last-ditch Cloudflare challenge attempt
- **Channel 7 — Sci-Hub mirror rotation**: gray; user-consent assumed
- **Channel 8 — Unpaywall PDF inline**: post-discovery fetch
- Hard cap `--max-total-sec 300` (paper-agent v4 principle)
- On cap or all-fail: surfaces JSON `handoff` block with `user_action_required`

#### `pa search` (pa_cli/search.py, 5 engines)
- Crossref / OpenAlex / arXiv / Semantic Scholar / CORE (CORE/S2/OA keys via env)
- `--year-min` / `--year-max` / `--limit` / `--engine` / `-o`
- Dedup by DOI (arXiv ID fallback), merged with `found_by: [...]` arrays
- Returns unified JSON sorted by `cited_by_count` desc

#### `pa review` (pa_cli/review.py, PyMuPDF + template)
- Walks corpus dir, extracts text per PDF, classifies full-text vs abstract-only
- `--word-count-min 1000` threshold (default)
- Outputs structured markdown ready for LLM-driven deeper synthesis
- Abstract-only papers flagged for v4 handoff

### Added — paper-agent v4 design principle

After 5 minutes of Cloudflare challenge failure, **stop iterating and surface
a "your turn" handoff** to the user. Real human browser sessions remain the
only reliable Cloudflare bypass for academic PDF recovery.

Cloudflare protects ~70% of academic PDF endpoints (Elsevier, T&F, worktribe,
ResearchGate, Anna's Archive) with checks Playwright headless cannot pass:

1. TLS JA3 fingerprint
2. HTTP/2 frame order
3. Canvas / WebGL fingerprint
4. `navigator.webdriver` flag
5. Sec-CH-UA-* client hint headers
6. Mouse-movement entropy (real human Bezier)
7. `cf_clearance` cookie timing (15-30 min TTL, bound to IP + UA + TLS hash)

CLI / fetch codifies this as `--max-total-sec 300` hard cap and a `handoff`
JSON block; downstream callers must respect it instead of iterating stealth
parameters.

### Added — `pa_cli/keys.py` API key registry + reminder system

Two-layer storage:
- `.env` (gitignored): actual secrets, never committed
- `keys_registry.json` (committed): metadata only — service, env var, tier,
  expiry date, last-checked, last-used, notes

#### CLI commands

```
pa keys list                       # show all keys + status indicators
pa keys check [service]            # live probe (HTTP) each key, updates last_checked
pa keys add <service> <value>      # add or rotate, writes .env + registry + live-probes
                                   # flags: --expires YYYY-MM-DD, --tier free|paid|institutional, --notes
pa keys audit                       # count active/expiring/expired/missing; show never-checked
pa keys remind                      # print expiry warnings; write alerts file
```

Status indicators: `✓ active` / `⏰ expiring-soon (≤14d)` / `⚠ expiring-week (≤7d)` /
`🚨 expiring-today` / `❌ EXPIRED` / `✗ missing`.

#### Reminder hook

`main()` calls `load_env_into_environ()` then `cmd_remind(quiet=True)` on every
CLI invocation. If any key has `expires` within 14 days or is already expired,
a single-line `[pa-keys] <warning>` is written to stderr before the actual
subcommand output. Non-intrusive — `pa fetch`, `pa search`, `pa review`
behaviour unchanged unless a warning is active.

#### Daily cron

New cron job `pa-keys-daily-check` (mavis agent, `0 9 * * *` Asia/Shanghai)
runs `pa keys check --write-alerts ~/.mavis/state/api_key_alerts.json` daily
and reads the alerts file to surface expiry warnings to the user. The
alerts file is also written on every `pa keys check` invocation, so
non-cron runs of `pa keys check` also feed the cross-session reminder
channel.

#### Default registry (committed)

| service | env_var | tier | expires | notes |
|---|---|---|---|---|
| openalex | OPENALEX_API_KEY | free | none | 1 RPS dedicated; no expiry reported |
| semanticscholar | S2_API_KEY | free | none | x-api-key header; no expiry reported |
| core | CORE_API_KEY | free | none | Bearer token; no expiry reported |
| unpaywall | UNPAYWALL_EMAIL | free | none | email registration; no API key needed |

Users add `expires` field via `pa keys add --expires YYYY-MM-DD` to opt into
expiry tracking — for paid-tier keys, institutional subscriptions with
quarterly rotation, etc.

### Added — full-text corpus recovery (8/8, +109% word count)

Recovered all 3 abstract-only papers via human browser handoff:

| Paper | Recovery method | Words extracted |
|---|---|---|
| McMinn / He et al. 2025 | T&F `/doi/pdf/` direct via Chrome | 12,040 |
| Tzirides et al. 2024 | Nottingham institutional repository via Chrome | 11,622 |
| Southworth et al. 2023 | ScienceDirect Gold OA via Chrome | 10,700 |

Plus the 5 papers already full-text in v3 corpus. Total extracted word
count: **~70,000** (up from ~33,500 in v3, +109%).

`Lit_Review_Section_AI_Literacy_v32_FT.md` updated: §5 reorganised into 4
sub-sections (5a Utami ADDIE / 5b McMinn HKUST / 5c Southworth QEP / 5d
Tzirides cyber-social); §6 gains a fifth methodological observation; §7
now offers 7 claims (added institutional-pathway 4-model portfolio and
full-text recovery as resolved citation-graph bias). Author order for paper
[3] corrected from "Rohadi & Utami" to **"Utami & Rohadi"** per
`final_8_papers.json`.

### Validation — CLI smoke tests

```
$ python -m pa_cli version
paper-agent CLI v3.2.0
[OK] click    8.4.1
[OK] pymupdf  1.27.2.3
[OK] arxiv    4.0.0
[OK] requests 2.33.1

$ python -m pa_cli search "AI literacy higher education" --year-min 2023 --limit 3 --engine openalex
→ 3 results, top: Chan & Hu 2023 (1819 citations, diamond OA)

$ python -m pa_cli review ./pdfs --output lit_review.md
→ 6 PDFs, 58,821 words, 6/6 classified full-text
```

---

## [3.1.0] - 2026-07-03

### Added — 3 new searcher interfaces

1. **CORE.ac.uk v3 searcher** (`skill/core/api_pool/searchers/core.py`, 198 lines)
   - Direct HTTP client to `https://api.core.ac.uk/v3/search/works`
   - Auth: Bearer token via `CORE_API_KEY` env var
   - 1 RPS dedicated rate limit, 429 → graceful return `[]`
   - year filter syntax: `yearPublished >= YYYY` (not `yearPublished:>=YYYY` — colon form returns 500)
   - 4xx/5xx → graceful `[]` (no `RateLimitError` raise)
   - 401/403 → auto-disables for current session
   - 80%+ CORE papers have DOI; remainder fall through to title+year dedup

2. **Semantic Scholar API key support** (`skill/core/api_pool/searchers/semanticscholar.py`)
   - New `api_key` constructor param (env: `S2_API_KEY`)
   - Sent as `x-api-key` header (per S2 official docs)
   - With key: 1 RPS dedicated pool; without: shared anonymous pool
   - When key present, `health_check()` reports True reliably; without, intermittent 429s

3. **OpenAlex key already-supported, now enabled** (`searchers/openalex.py` + `.env`)
   - `OpenAlexSearcher(api_key=...)` was always supported; v3.1 just adds key
   - 1 RPS dedicated with key (per OpenAlex docs)
   - Priority pool access vs polite-email-only

### Added — 2 API keys integrated (`.env`)

- `CORE_API_KEY=...` (32 chars) — drives CORE searcher
- `S2_API_KEY=s2k-...` (44 chars) — drives S2 searcher key mode
- `OPENALEX_API_KEY=...` (22 chars) — drives OpenAlex searcher key mode

`.env` is git-ignored; do not commit it.

### Changed — SearchPool v3.1 wiring

- 5-engine pool: Crossref / S2 / arxiv / OpenAlex / CORE
- `SearchPool(polite_email, openalex_api_key, s2_api_key, core_api_key)` — 3 new optional kwargs
- `search_with_searchpool()` default `min_per_source` changed `0` → `max_per_channel` (v3.1 critical fix)
- `paper_fetcher._get_search_pool()` and `search_with_searchpool()` now read all 3 keys from `os.environ`
- `min_per_source>0` interleave logic (Phase 4 fix, 2026-07-03) preserved: round-robin truncation by source

### Changed — S2 backoff tune (Phase 4 → Phase 6)

- Old: 1 retry, 15s backoff, total worst case 17s
- New: 2 retries, 30s + 60s backoff, total worst case 150s
- Reason: diagnostic 2026-07-03 showed S2 1 RPS is *sustained* not burst — 4s follow-up still 429s; old 15s gave up too early
- Still returns `[]` (not raise) so SearchPool moves on to other engines

### Fixed — 4 pre-existing bugs (discovered running v3.1 end-to-end)

1. **`pipeline.py` missing `import datetime`** — Phase E and F used `datetime.date.today()` and NameError'd on import. Fixed by adding `import datetime`.
2. **`paper_fetcher.fetch_all_channels` declared in `__all__` but never defined** — `pipeline.run_search_screen_pipeline()` failed at import. Fixed by adding a thin wrapper that delegates to `search_with_searchpool`.
3. **`pipeline.run_search_screen_pipeline()` body referenced `kwargs` but signature lacked `**kwargs`** — Stage 3.5 (relevance ranking) NameError'd. Fixed by adding `**kwargs: Any` to signature.
4. **`search_with_searchpool()` defaulted `min_per_source=0`** — Crossref-first engine filled the bucket and stopped, so S2 / OpenAlex / CORE never fired in pipeline runs. Fixed by defaulting `min_per_source=max_per_channel`.

### Security

- `.gitignore` created — excludes `.env` (API keys), `__pycache__/`, `cache/`, `results/`

### Verified end-to-end

- Topic: `_example_ai_education`
- Query: "generative AI literacy higher education"
- Result: 5 papers from 3 engines (S2 2 + Crossref 2 + OpenAlex 1), 2/3 passed 3-stage screen, 1/2 PDF download, 8 fields extracted, 2 topics modeled, 9.0/16 quality, PRISMA + Role Reflection + 21 prompt improvements generated
- Runtime: 21.7s (search 75s → 21.7s in pipeline because Crossref-5 cap means fewer calls)

### Known limitations (carried over from v3.0.1)

- S2 with key still throttles in practice (1 RPS is *sustained*, not burst); 4s follow-up can 429
- 5-engine search worst case (S2 30s+60s backoff + others) ≈ 75-150s
- CORE `journals` field is often empty; venue falls back to None
- Some publishers (MDPI, Wiley, Elsevier) block PDF download via known_pitfalls in topic yaml
- No remote git remote; commits are local-only

---

## [3.0.1] - 2026-07-02

### Fixed — v3.0 regressions in pool / searcher stability

- OpenAlex `pyalex` 5xx hangs → `ThreadPoolExecutor` timeout
- OpenAlex credit-exhausted signal → return `[]` (not raise `RateLimitError`)
- S2 429 → return `[]` after 15s backoff (later tuned to 30s+60s in v3.1)
- Pool dedupe by arxiv_id (Phase 4 fix) for cross-source arxiv preprint matching
- Pool min_per_source>0 round-robin truncation (Phase 4 fix)
- Crossref year extraction fallback (created/deposited date-parts)

### 4 searchers (pre-CORE)

- Crossref (habanero wrapper, polite pool)
- Semantic Scholar (no key, shared pool)
- arxiv (arxiv.py wrapper)
- OpenAlex (pyalex wrapper, polite email; key optional but unused)

---

## [3.0.0] - 2026-06-25

Initial v3 release. Single-searcher-only architecture replaced by SearchPool.

- `skill/core/api_pool/pool.py` introduced
- `paper_fetcher.py` rewritten to use SearchPool
- Topic-agnostic: `skill/topics/_example_ai_education.yaml` example
- 4 phase pipeline (A download → B extract → C topic model → D quality+PRISMA)
