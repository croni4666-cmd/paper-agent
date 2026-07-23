# paper-agent

Academic paper search, fetch, and literature-review synthesis CLI.
6 default search engines (Crossref, OpenAlex, arXiv, S2, AMiner, CNKI) + 1 opt-in
engine (CORE, local-only) + pa judge relevance collection + pa build manuscript
pipeline + Tier 2 research-topic project management.

**Note on CORE engine** (v3.9.11.1+): CORE code is isolated from the public
repo. After cloning, run once:
```bash
python tools/install_core.py   # generates pa_cli/_engines_local/core.py (gitignored)
```
Then `pa search --engine core "..."` works. Public clone without this step will
raise a clear "not installed" error if you try `--engine core`. See
`tools/install_core.py` docstring for the isolation rationale.

## Quick start (5 commands)

```bash
# 1. Search — 6 engines in one call
pa search "AI literacy K-12" --year-min 2020 --limit 30 -o results.json

# 2. Validate citation skeleton before building
pa cite-check refs.bib skeleton.md                    # 3 buckets: missing/typo/orphan

# 3. Batch PDF download
pa fetch-batch refs.bib --out-dir ./pdfs/ --skip-existing --report failed.md

# 4. Mark relevance for screening
pa judge add --query "AI literacy" --paper-key smith2023 --relevance 2 --reason "Direct hit"

# 5. Build manuscript from refs.bib + filled-in skeleton
pa build refs.bib skeleton.md -o paper.pdf
```

## Core workflow

```
search results       pa cite-check        pa fetch-batch
  (JSON)        -->  (3 buckets)    -->   (PDFs)
       \              |                    |
        \             v                    v
       Bibtex (refs.bib) + Skeleton --> pa build (PDF/HTML/DOCX)
                       |
                       v
                  pa judge (mark relevance)
                       |
                       v
              pa export-screening (CSV for Notion/Excel/RevMan)
                       |
                       v
                pa project (per-topic corpus)
```

## Available commands

| Command | What | Effort |
|---|---|---|
| `pa search` | 6-engine search | — |
| `pa fetch` | Single PDF download | — |
| `pa fetch-batch` | Batch PDF from Bibtex | 1 call |
| `pa cite-check` | Validate `[@key]` in skeleton | Pre-build check |
| `pa judge` | Mark relevance (sqlite) | `add/bulk/list/stats/export/import` |
| `pa export-screening` | Bibtex + judge → CSV | For Notion/Excel |
| `pa build` | Bibtex + skeleton → PDF/HTML | Pandoc wrapper |
| `pa scaffold` | Bibtex → outline skeleton | Quick start |
| `pa dedup-strict` | Fuzzy + arxiv dedup | Stricter than default DOI-only |
| `pa search-saved` | Named search presets | Skip retyping flags |
| `pa project` | Per-topic corpus management | Phase 1 done; Phase 2 needs user input |

## Performance (v3.9.10.2 honest, n=50 single 30/20 holdout)

| Ranker | NDCG@10 | Notes |
|---|---:|---|
| **Combined (0.5\*BM25 + 0.5\*bi-encoder)** | **0.8988** | **Default; no training, no overfit** |
| RidgeClassifier (α=1.0) | 0.8526 | Linear; interpretable coefficients |
| LogisticRegression (C=1.0) | 0.8409 | Linear; more stable than Ridge |
| BGE-reranker | 0.6952 | **DEPRECATED** (Wilcoxon p=0.0008, significantly worse) |
| LambdaMART 100 trees (LTR) | 0.7679 | **DEPRECATED at n<200** (overfit) |
| MoE router macro F1 | 0.5173 | Honest n=47 estimate; needs more data |

## Known limitations

- **1 of 6 default engines returns 0 hits** in current config (S2 — demo API key
  expired; user must set `S2_API_KEY` in `.env` to enable)
- **CORE engine** is opt-in (v3.9.11.1+) — run `python tools/install_core.py`
  after clone; also requires `CORE_API_KEY` in `.env` for higher rate limit
  (anonymous requests work at low rate)
- **CNKI** requires user cookies / EZproxy / institution library access
- **Layer 7 fulltext features** (3 of 4) still at 0.0 — need PDF download first
- **Pa judge data** scales to ~5-50 projects; beyond that needs SQLite tuning
- **BGE alternative** (monoT5/ColBERT/LLM-fulltext) not yet evaluated

## Project layout (default)

```
~/.paper-agent/
  saved_searches.json          # pa search-saved presets
  judgements.sqlite            # pa judge data (global)
  projects/                    # pa project (per-topic)
    digital-finance/
      meta.json
      refs.bib
      judges.sqlite
    elder-care/
      ...
```

## Documentation

- [ROADMAP.md](ROADMAP.md) — what's done, what's next, full priority plan
- [CHANGELOG.md](CHANGELOG.md) — version-by-version release notes (v3.9.10.8 latest)
- [ARCHITECTURE.md](ARCHITECTURE.md) — system design + Cloudflare handling
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md) — current state for new sessions

## CLI: try `pa --help` and `pa <command> --help`

```bash
pa --help
pa search --help
pa fetch-batch --help
pa judge --help
pa project --help
```

## Files added in v3.9.10 (current stable)

For defense against "shipped but not committed" gaps, this is the
machine-checked list of files added/modified in the v3.9.10.x series:

### v3.9.10 (deprecate BGE/LTR)
- `pa_cli/cross_encoder.py` (DEPRECATED docstring)
- `pa_cli/ltr.py` (CONDITIONAL DEPRECATION docstring)
- `pa_cli/moe_router.py` (0.89 → 0.61 honest numbers)
- `bench/v01/_v4_rerank.py` (combined marked RECOMMENDED DEFAULT)
- `bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.md` (bug fix)
- `bench/v01/reports/v3_9_7_3_action_plan.md` (NEW)

### v3.9.10.1 (Phase 1.5 holdout)
- `test_output/_run_holdout_v1_5.py` (NEW)
- `bench/v01/reports/v3_9_10_1_phase_1_5_holdout.{json,md}` (NEW)

### v3.9.10.2 (Simpler rerank)
- `pa_cli/cross_encoder.py` and `pa_cli/ltr.py` docstring updates
- `test_output/_run_simpler_rerank_v1_5.py` (NEW)
- `bench/v01/reports/v3_9_10_2_simpler_rerank.{json,md}` (NEW)

### v3.9.10.3 ([P2-7] pa cite-check)
- `pa_cli/cite_check.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (cite-check subcommand)
- `test_output/_test_cite_check.py` (NEW, 24 tests)
- `test_output/fixtures/demo_refs.bib` (NEW)
- `test_output/fixtures/demo_skeleton.md` (NEW)

### v3.9.10.4 ([P2-8] pa export-screening)
- `pa_cli/export_screening.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (export-screening subcommand)
- `test_output/_test_export_screening.py` (NEW, 26 tests)
- `test_output/_e2e_export_screening.py` (NEW)

### v3.9.10.5 ([P2-9] pa search-saved)
- `pa_cli/search_saved.py` (NEW, ~190 LOC)
- `pa_cli/cli.py` (search-saved subcommand group)
- `test_output/_test_search_saved.py` (NEW, 26 tests)

### v3.9.10.6 ([P2-10] pa dedup-strict)
- `pa_cli/dedup_strict.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (dedup-strict subcommand)
- `test_output/_test_dedup_strict.py` (NEW, 36 tests)

### v3.9.10.7 ([P2-11] pa fetch-batch)
- `pa_cli/fetch_batch.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (fetch-batch subcommand)
- `test_output/_test_fetch_batch.py` (NEW, 17 tests)

### v3.9.10.8 ([P2-12] pa project Phase 1)
- `pa_cli/project.py` (NEW, ~280 LOC)
- `pa_cli/cli.py` (project subcommand group)
- `test_output/_test_project.py` (NEW, 26 tests)

### v3.9.11.0 (Stable release marker)
- No code change; MINOR bump to mark natural code-level ceiling
- See `CHANGELOG.md [3.9.11.0]` for full stable-release notes

### v3.9.11.1 (CORE engine isolated)
- `pa_cli/search.py`: removed inline `search_core()` body; lazy-imports
  `pa_cli._engines_local.core.search_core` instead
- `pa_cli/_engines_local/` (NEW, gitignored): CORE engine file, generated
  by `tools/install_core.py` from embedded string constant
- `tools/install_core.py` (NEW, ~6.7KB): install / uninstall / verify
  script. Run once after clone to enable CORE.
- `.gitignore`: added `pa_cli/_engines_local/`
- Trade-off: CORE code IS in public repo (as string in install script);
  it's NOT in functional form. For stricter isolation, see
  `tools/install_core.py` docstring "Trade-off (honest)" section.

### v3.9.11.2 (Pre-push scanner fix + filter-branch backup cleanup)
- `test_output/_pre_github_secret_scan.py`: `scan_git_history()` now checks
  BOTH `+` and `-` lines in `git log -p` (was: only `+`, missed secrets in
  deleted content)
- `test_output/_history_deep_scan.py` (NEW): independent deep scanner using
  `--all`; catches what the pre-push scanner might still miss
- `test_output/_test_install_core.py` (NEW): fixture verifying install_core
  CORE string has no hardcoded keys / emails / tokens
- Local cleanup: deleted `refs/original/refs/heads/main`, gc-pruned dangling
  objects

### v3.9.11.3 (Dangling blob cleanup + direct-blob fixture)
- `test_output/_test_verify_blob_clean.py` (NEW): robust direct blob check.
  v1.1 fixed 3-column parsing bug (`git cat-file --batch-check` outputs
  `sha type size`, not 2 columns). v1.2 obfuscated the key constant
  (built at runtime from 4 substrings) to keep the literal full key off
  public GitHub.
- `test_output/_full_sweep_v3_9_11_3.py` (NEW): 10-check comprehensive
  pre-push verification (tracked files, git log, blobs, refs, fsck, etc.)
- `test_output/_final_cross_check.py` (NEW): 7 additional cross-checks
  (backup files, env-var files, hidden dirs, .env.example placeholders,
  version consistency, install e2e, pre-push scanner sanity)
- All 17 checks run as part of the v3.9.11.3 review+fix loop. After
  2 consecutive 0-issue rounds, the loop terminates.
- Memory entries added for: scanner + and - line bug, git cat-file
  3-column output, pre-commit hook bypass for legitimate fixtures.

## License

This software is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**
with an **additional restriction prohibiting use for AI/ML training** (the "No-AI-Training
restriction"). 

**In plain English**:
- ✅ You can use, modify, and run it for personal / academic / commercial purposes
- ✅ If you modify it, your modifications must also be open-sourced under AGPL-3.0
  (this is the standard AGPL copyleft clause)
- ✅ If you run it as a network service, you must publish your source code
  (this is the AGPL network clause; the key difference from regular GPL)
- ❌ **You may NOT use this software, its source code, or its outputs to train,
  fine-tune, validate, or improve any AI / ML / LLM model** — including LLMs,
  code-generation systems, embedding models, and any system whose weights or
  training data are derived from this software

Full text in [`LICENSE`](./LICENSE). The file contains:
- PART 1: Reference to AGPL-3.0 (canonical text at gnu.org/licenses/agpl-3.0.txt)
- PART 2: Additional restriction (No-AI-Training) — with specific carve-outs
  for evaluation, security review, and personal use
- PART 3: Full AGPL-3.0 text reproduced verbatim for convenience

**SPDX identifiers**:
- `AGPL-3.0-only`
- `LicenseRef-No-AI-Training-1.0`

**Why this combination**: AGPL-3.0 protects the source-sharing intent for any
network use; the No-AI-Training clause adds an explicit 2026-era protection
against LLM/ML training. Together they reflect the author's preference for
**copyleft + no commercial AI training** without prohibiting ordinary use.

If you have questions about whether your intended use is allowed, contact the
copyright holder.
