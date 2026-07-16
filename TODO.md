# Paper-Agent TODO / Backlog (Living Document)

> **Last updated**: 2026-07-16 13:04 (post v3.9.9.6 audit, 17 rounds)
> **Owner**: Mavis (mavis)
> **Source of truth for forward work**: `ROADMAP.md` (formal status, audit trail) + this file (intentions + research / design notes)
>
> **Roadmap discipline**: every "Status" below corresponds to a `ROADMAP.md` `[Px-N]` entry. This file goes DEEPER on **why** and **how** — `ROADMAP.md` is the formal ledger, this is the working notes.

---

## 📍 Current state (2026-07-13 14:32)

- **v3.9.0 shipped 2026-07-12**: 5-condition rerank stack (BM25 / biencoder / combined / PRF / random) on 25 queries × 30 candidates. 3.9x lift on recall@10 vs original (citation count). 6/6 invariant checks PASS.
- **v3.9.0 user spot-check 2026-07-13** (this session): 13 of 374 labels overridden (3.5%); clean labels re-run preserves 3.9x lift (0.722 → 0.721 recall@10). User feedback 7 themes captured (see "User spot-check insights" in `ROADMAP.md`).
- **v3.9.1 patch shipped 2026-07-13 (this session)**: P0-4 (DOI canonicalization) + P1-5 (recency + citation threshold filter). See CHANGELOG v3.9.1.

---

## ✅ Done today (2026-07-13)

### [P0-4] DOI canonicalization
- New `pa_cli/doi.py` (~165 lines): `canonicalize_doi()`, `normalize_labels_dict()`
- Migration scripts: `_migrate_doi_canonical.py` + `_migrate_candidate_dois.py`
- **102 DOIs canonicalized** across 150 candidate files (5 typo'd Frontiers DOIs + 17 case-variant duplicates + arxiv/aer/ssrn uppercase variants)
- **19 renames** in labels.json (748 → 741 keys)
- All 9 smoke test cases pass
- **Honest caveat**: metric numbers shifted slightly (-0.003 to -0.014 across conditions) because duplicate-counted n_relevant collapsed. 3.9x lift preserved.

### [P1-5] Recency + citation threshold filter
- New `pa_cli/recency.py` (~190 lines): `RecencyConfig`, `recency_factor()`, `apply_recency_to_results()`, `check_field_staleness()`
- CLI flag: `_v4_rerank.py --recency-mode {strict|moderate|off}` (default: off — backward compatible)
- **Rules implemented per user spec**:
  - `age > 10y AND cite < mean + 2*std` → 0.5x (strict + moderate)
  - `age > 20y AND cite < mean + 2.5*std` → 0.1x (strict) or 0.5x (moderate)
  - `bi_score > 0.7 AND cite > mean + 2*std` → 1.0x (rescue)
  - Field-stale warning: `median(candidate_year) < now - 5` → emit stderr warning
- **Surprising finding (filter implemented per user spec; metric deltas treated as noise)**:
  - Strict mode shows combined recall@10 0.718 → 0.689 (-0.029)
  - Biencoder 0.671 → 0.651 (-0.020); prf 0.590 → 0.580 (-0.010)
  - **Per user feedback 2026-07-13**: "Recency filter 实际降低了 benchmark 数字，这个理解成随机波动即可。我不认为它是必然造成提升的。" Treat metric deltas as random noise on n=25 (no significance test, no holdout). The filter is a user-preference signal, orthogonal to ground-truth labels.
  - **Actionable output of the filter** (the real value): 16 of 25 queries emit field-stale warning (median year > 5y old). User can act on the warning regardless of whether they want the downweight.
- **Decision**: ship with `--recency-mode off` as default for benchmark eval; user opts in with `--recency-mode strict` for own research. The two use cases (benchmark vs own-paper curation) have different optimal settings.

---

## ⏭️ Next actions (short term)

### 🔥 Blocked on user input

- **q026-q050 real queries**: user said "我需要时间提交，等明天给你" (2026-07-13). Without these, can't run Phase 1.5/1.6/2/6.5/7. **First action when queries arrive**: replace placeholders in `bench/v01/queries.json`, run `bench/v01/snapshot.py` to fetch candidates, run `_v4_rerank.py` to score.
- **`paper-agent-phase-b` cron decision**: still injects 6/29 stale "全部完成" text into session start. 3 options: disable / rename / leave. User hasn't decided.

### 🟢 Doable today / this week (no user input needed)

- **Update snapshot.py to write canonical DOIs**: `pa_cli/snapshot.py` is the candidate fetcher. Currently writes whatever DOI OpenAlex/Crossref returns (which is why we had 17 non-canonical DOIs in pool). Add `from pa_cli.doi import canonicalize_doi` and apply before writing. ~30 minutes.
- **Add `--recency-mode` flag to `_v4_run_all.py`**: currently run-all defaults to off. Should accept `--recency-mode` and pass to all sub-rerank invocations. ~15 minutes.
- **Write the v3.9.1 patch report (`reports/v3_9_1_recency.md`)**: side-by-side off / moderate / strict modes, with the HURT-metric honesty. ~30 minutes.
- **Disable / rename `paper-agent-phase-b` cron**: just `mavis cron rm` and `mavis cron new` with correct snapshot. 5 minutes. (Awaits user decision.)

---

## 📋 P1 / P2 backlog (from ROADMAP, awaiting user confirmation)

### [P1-6] Sub-topic granularity decomposition
- **Why**: User said "agriculture is too broad — need sub-topic decomposition"
- **Plan**: static lookup table (~30 known sub-topic domains: agriculture → {ag_econ, climate_adaptation, supply_chain, food_security, ag_tech}; AI_education → {intelligent_tutoring, adaptive_learning, learning_analytics, ...}; protein_structure → {structure_prediction, function_prediction, binding_site, ...})
- **Effort**: ~3-4h
- **Status**: needs user to confirm lookup table content before I build. Do you want the 30 domains to be: (a) hand-curated from a CS-econ-bio-philosophy set, or (b) auto-mined from a paper corpus?

### [P1-7] Institutional credibility boost
- **Why**: User said "Qs top-50 + ESMFold + IMF + World Bank + famous national research institutes → even partial relevance should be promoted"
- **Plan**: `pa_cli/institutions.py` with `INSTITUTION_TIERS` lookup (Tier 1 = top-10 univ + IMF/WB/OECD/NBER/Federal Reserve/ESMFold/AlphaFold team; Tier 2 = Qs top-50 + famous national institutes). Boost factor multiplies rerank score (NOT label — labels stay ground-truth).
- **Effort**: ~2h
- **Status**: needs user to confirm tier definitions and boost magnitudes. Default I propose: Tier 1 = 1.3x, Tier 2 = 1.1x, Tier 3 = 1.0x.

### [P1-8] China political-institution exclusion
- **Why**: User said "针对中国,排除任何国际关系研究院以及马克思主义学院"
- **Plan**: small blocklist applied at retrieval time. ~10 institutions to start (CASS international relations institutes, all levels of Marxism schools).
- **Effort**: ~1h
- **Status**: needs user to confirm exact list. I propose starting with: 中国国际关系研究院, 中国社科院国际关系研究所, 中国现代国际关系研究院, 中央党校国际战略研究院, 各级大学马克思主义学院 (regex match on institution name). If user wants more, easy to extend.

### [P1-9] Geographic / country metadata extraction
- **Why**: User said "geographic/country info is essential for empirical claims"
- **Plan**: `pa_cli/geography.py` with `extract_country(title, abstract, venue) -> list[str]` using ISO 3166-1 alpha-2 codes (~250 countries). Boost factor when query has country mentions.
- **Effort**: ~3h
- **Status**: needs user to confirm country list completeness (especially small African / Pacific island nations; some edge cases like "EU" vs individual countries).

### [P1-10] Falsifiability philosophy integration (RESEARCH) — see deep dive below
- **Why**: User said "架构哲学应考虑可证伪性的确认"
- **Status**: see Section 5 below

### [P2-5] Quality filter (no-abstract + low-cite = low quality)
- **Why**: User (q005 #30): "no year + low cite = low quality paper"
- **Plan**: flag / drop candidates with `abstract is None AND citation_count < 50 AND year is None`
- **Effort**: ~1h
- **Status**: low priority — can be folded into [P1-5] recency filter if user wants

---

## 🧠 Section 5 — 可证伪性哲学架构方法 (DEEP DIVE)

> **User's prompt** (2026-07-13): "你的架构哲学里面也应该考虑 可证伪性的确认，尤其是当代可证伪性哲学方法应用在博士以及学术界层面（这个我不知道GitHub 上面有没有，可以搜索一下）"
>
> **What this section is**: A research deliverable, not a feature spec. User wants me to (a) understand contemporary falsifiability philosophy, (b) understand how it's applied at PhD / academic level, (c) decide whether to encode it in paper-agent, and (d) design if so.

### 5.1 简介 (Introduction)

**Falsifiability** (可证伪性) is the philosophical principle that a proposition is only scientific if it can be **proven wrong** by some conceivable observation. Originated by **Karl Popper** in *The Logic of Scientific Discovery* (1934 / 1959 English). Central to the demarcation problem: what separates science from non-science.

A claim like "all swans are white" is falsifiable (a single black swan proves it wrong). A claim like "there is an invisible dragon in my garage" is unfalsifiable (no observation can disprove it). Paper-agent is in the business of *retrieving* claims; user implicitly wants the agent to *evaluate* them too.

### 5.2 当代哲学传统 (Contemporary philosophical traditions)

Beyond Popper, the tradition has four major branches that are **directly relevant to paper-agent**:

| Philosopher | Key idea | How it applies to paper-agent |
|---|---|---|
| **Karl Popper** (1934) | A theory is scientific iff it makes **risky predictions** that could be refuted | A "result" paper that claims "X is correlated with Y" without specifying the effect size, p-value threshold, or replication conditions is **low-falsifiability** — easier to publish, harder to verify |
| **Imre Lakatos** (1970) | A "research programme" is **progressive** if its new predictions are corroborated, **degenerating** if it only explains away anomalies | A research programme that has been "degenerating" for N years (no novel predictions confirmed) is a candidate for the **field-stale** warning (similar to our [P1-5] check, but stricter: looks at *new* predictions, not just years) |
| **Paul Feyerabend** (1975) | "Anything goes" — there is no single scientific method; incommensurable paradigms can each have their own standards | Risk: paper-agent's evaluation of a paper may be biased by the dominant paradigm (e.g., assuming RCTs > observational studies). Need to encode paradigm-aware evaluation |
| **Dudley Shapere** (1974) | Scientific reasoning is **domain-internal** — there is no algorithm that works across all fields; the "relevant" evidence is what the field treats as relevant | Suggests paper-agent should learn field-specific relevance criteria rather than apply one-size-fits-all filters |

### 5.3 当代 PhD / 学术层应用 (How it's applied at PhD / academic level)

User asked specifically about "PhD and academic-level" application. The contemporary operationalization is via **"research question" criteria**:

A PhD-level research question is **falsifiable** iff it satisfies:
1. **Specificity**: claims an effect (X causes Y), not just "we explore X"
2. **Testability**: there exists at least one observation that would refute it
3. **Boundary conditions**: specifies scope (which population, time window, geography)
4. **Novelty**: not already answered by existing literature
5. **Specificity of prediction**: predicts *which way* the effect goes, not just "there is an effect"

Most papers in our 25-query benchmark fail at least one of these. Examples from user's spot-check:
- q013 #28 (DeepProSite ESMFold binding): the paper's "structural prediction" is **vague** — uses ESMFold as a feature extractor, not as a primary output. **Low falsifiability** because the claim is "binding site prediction can be improved" — almost any DL paper could claim this.
- q007 #17 (2002 typology): "we describe a typology" — **descriptive**, not predictive. **Low falsifiability** by Popperian standard.

### 5.4 GitHub 调研结果 (GitHub research results)

I searched GitHub 2026-07-13 for "falsifiability philosophy academic research method tool Popper". Findings:

| Repo | Stars | Last commit | Verdict |
|---|---|---|---|
| **K-Dense-AI/scientific-agent-skills** | 27.6k | active | Closest match. 140+ skills for scientific research. Has `scientific-writing` and `peer-review` skills that touch on argument structure but **no dedicated falsifiability skill** |
| **comorichico/PhD-Methodology-Notebook** | 0.05k | 2023 | PhD workflow but no falsifiability integration |
| **citation-js/citation-js** | 1.9k | active | Citation parser; no philosophy layer |
| **OpenScienceFramework** | various | active | OSF has a "Preregistration" feature that **operationalizes falsifiability** — researchers must specify hypotheses + analysis plan BEFORE running study. Strong signal that the community wants this as a tool |

**Verdict**: No direct falsifiability tool. The closest actionable design is OSF preregistration pattern: encode "hypothesis + variables + prediction + boundary conditions" as a structured query, surface papers that match this structure.

### 5.5 paper-agent 该怎么编码 (How paper-agent should encode it)

Based on the philosophy + GitHub research, I propose the following architectural addition to paper-agent (call it **[P1-10] v3.10.0 or later**):

**`pa review-falsifiability <corpus_dir>`** — A new subcommand that scores each paper on 5 falsifiability dimensions:

1. **Hypothesis clarity**: does the abstract state a testable claim? (binary; LLM-style NLI or rule-based pattern: "we hypothesize that...", "X causes Y", etc.)
2. **Variable specificity**: are IV/DV explicitly named? (NER on "we measured X", "Y was the dependent variable")
3. **Prediction direction**: does the paper predict *which way* the effect goes? (regex: "we predicted that X would be larger than Y")
4. **Boundary conditions**: are population / time / geography specified? (regex: "in [country]", "during [year range]", "for [population]")
5. **Novelty check**: has this exact question been answered in earlier literature? (citation graph depth, requires [P1-1] citation walk)

Score: count of dimensions satisfied (0-5). Output: per-paper score + corpus-level distribution. Use as **ranking signal** (NOT label change) so users can prioritize high-falsifiability papers.

**Important constraint**: per Global Rule, this must run **local-only** (no hosted LLM, no API beyond OpenAlex free tier). Heuristic-based first version; LLM-rerank deferred to v4+.

### 5.6 设计草案 (Design draft)

```python
# pa_cli/falsifiability.py (DRAFT, not built yet)

@dataclass
class FalsifiabilityScore:
    hypothesis_clarity: int  # 0 or 1
    variable_specificity: int  # 0 or 1
    prediction_direction: int  # 0 or 1
    boundary_conditions: int  # 0 or 1
    novelty: int  # 0 or 1
    total: int  # sum, 0-5

def score_falsifiability(title: str, abstract: str, citation_count: int = None,
                          references: list[str] = None) -> FalsifiabilityScore:
    """Score a paper on 5 falsifiability dimensions.
    
    Local-only heuristics:
    - hypothesis_clarity: regex "we hypothes(i|y)ze that", "X causes Y"
    - variable_specificity: NER for "X was the dependent variable"
    - prediction_direction: regex "we predicted", "we expected"
    - boundary_conditions: regex for country/year/population mentions
    - novelty: skip if citation_count > 100 (likely built on prior work; not new)
    """
    ...
```

**Status**: research deliverable, not code yet. Awaiting user feedback on:
1. Should this ship as a new subcommand, or a `--falsifiability-mode` flag on existing `pa review`?
2. Are the 5 dimensions the right set? (Popperian minimal: 1+2; Lakatosian: novelty = citations < N)
3. How should the score combine with `pa review-topics` output?

---

## ⏸ Blocked on user (waiting for input)

| Item | What I need | Why |
|---|---|---|
| q026-q050 real queries | User fills in 25 placeholder slots in `bench/v01/queries.json` | Cannot run Phase 1.5/1.6/2/6.5/7 without them |
| `paper-agent-phase-b` cron | User picks: disable / rename / leave | Daily 00:00 injects stale text into session start |
| Daily crons (5 missed) | User says "trigger them" or "leave them" | `daily-missed.json` showed 5 not-run today |
| [P1-6..P1-10] sub-topic / institution / China / country / falsifiability | User confirms lookup tables | Avoid building from intuition; user has clearer domain knowledge |
| Phase 7 (CHANGELOG v3.9.0 commit) | User confirms ROADMAP outcomes look right | Last step before git commit |

---

## 🧹 Cleanup (low priority)

- Disable / rename `paper-agent-phase-b` cron (see above)
- v3.8.1 / v3.8.2 / v3.8.3 ROADMAP Modified sub-sections could be consolidated into a single "audit trail" appendix (low priority, not blocking)
- The `_v01/_labeling/` directory still has some v3.8.0-era view files; could be cleaned up after Phase 7 commit
- The `pa_keys_daily_check` cron already exists; the new `pa_watch_daily` from [P2-3] remains deprecated (no topic)

### 🟠 CHANGELOG ordering issues (deferred from audit rounds 16-21, 2026-07-16)

> **Why deferred**: each fix requires moving 50-150 lines of release content;
> CHANGELOG is now 3681 lines and the historical blocks are heavily
> referenced. High risk of breaking chronological references if moved wrong.
> Cleanup-only, no content error. **Do in a quiet session** (not when
> other CHANGELOG edits are pending).

- **[3.6.0] duplicate entries** — L3117 has [P1-2] OpenAlex concepts
  under "## [3.6.0]"; L3339 has [P0-3] MCP server under "## [3.6.0]".
  Both are dated 2026-07-04. **Verdict**: there should be ONE
  [3.6.0] entry that covers BOTH concepts and MCP (the MCP was later
  reverted in [3.5.1]). Fix: merge the two sections, keep the [3.6.0]
  header once, list both features under it.
- **[3.5.1] duplicate entries** — L3170 has "follow-up commit" with
  real-machine verification table; L3261 has "post-MCP-revert state"
  with [P0-3] revert + [P1-1] + [P1-3] + [P2-4]. **Verdict**:
  L3170's content is a follow-up addition to L3261's release. Fix:
  rename L3170 header from "## [3.5.1]" to "## [3.5.1] follow-up:
  pa mcp install integration" (sub-section of L3261), or merge them
  into one [3.5.1] block.
- **[3.9.6] out of order** — L1839 has "## [3.9.6]" between [3.9.5.1]
  and [3.9.5]. Semver order requires [3.9.5.x] (all 4 patches) →
  [3.9.6] → [3.9.7]. Fix: move the entire [3.9.6] block (L1839-1916,
  ~80 lines) to AFTER the [3.9.5] block at L1917.
- **[3.9.7.3] out of order** — L1453 has "## [3.9.7.3]" between
  [3.9.7.1] (L1332) and [3.9.7.2] (L1524). Semver order is [3.9.7.1]
  → [3.9.7.2] → [3.9.7.3]. Fix: move the [3.9.7.3] block (L1453-1522,
  ~70 lines) to AFTER the [3.9.7.2] block at L1524.

**Estimated total effort**: 30 min if done carefully (read each block
before moving, verify line counts after).

**Risk if done wrong**: cross-references like "see v3.9.5 below" or
"replaces earlier X" may point to wrong sections after moves. Mitigation:
re-grep for "v3.9.5", "v3.9.6", "v3.9.7", "[3.5.1]", "[3.6.0]" after
each move to verify no broken cross-refs.

### 🔴 [P0-8] deep_rerank.py is broken (audit round 22, 2026-07-16)

> **Status in ROADMAP**: was `done` (2026-07-13), now `broken` (revised
> 2026-07-16). 25/26 pa_cli modules import cleanly; `pa_cli.deep_rerank`
> is the only one with a broken import.

**Root cause**:
- v3.9.8.2 (commit `acca2a8`, 2026-07-15 19:53) renamed
  `pa_cli.fetch.fetch_doi(doi, output_dir, channels, max_total_sec, use_cache)`
  → `pa_cli.fetch.fetch(doi, title, md5_path, out_path, prefer)`.
- `pa_cli/deep_rerank.py:52` still has
  `from pa_cli.fetch import fetch_doi` → ImportError on module load.

**Gaps**:
- `pa deep-rerank` CLI command **was never wired up** (acceptance
  criteria said "新增 `pa deep-rerank <CORPUS_DIR>...` CLI" but no
  `@main.command()` for it exists). So even if the import is fixed,
  the feature is still uncallable.
- `test_output/_run_deep_rerank_v3_9_5.py` and
  `test_output/_run_deep_rerank_v397.py` both import
  `pa_cli.deep_rerank` — they would fail at import.

**Three options**:

1. **Fix the code** (~1-2h, HIGH RISK):
   - Update `pa_cli/deep_rerank.py:52` to use new `fetch` API
   - Update call site at `pa_cli/deep_rerank.py:127` to match new
     signature (no `output_dir`/`channels`/`use_cache` — use
     `out_path` + manual loop)
   - Add `pa deep-rerank` CLI wrapper in `pa_cli/cli.py`
   - Re-run import smoke test to verify
   - Risk: requires understanding both the old and new `fetch` API
     plus the multi-channel cascade logic; might surface more bugs
     that have been silently broken since v3.9.8.2

2. **Delete dead code** (~5 min, LOW RISK):
   - If no plan to actually use Layer 7 deep rerank in the next
     课题 iteration (current roadmap shows [P1-12] 3 of 4 fulltext
     features as "proposed" not "in-progress")
   - Delete: `pa_cli/deep_rerank.py` + 2 stale test files
     (`_run_deep_rerank_v3_9_5.py`, `_run_deep_rerank_v397.py`) +
     any other deep_rerank references
   - Update ROADMAP [P0-8] Status to `deprecated`
   - Update capability snapshot to remove "1/4 Layer 7 features
     working" (was the only partial implementation)

3. **Mark TODO, defer** (0 min, current state):
   - ROADMAP [P0-8] Status = `broken` (done above)
   - This TODO entry documents the issue
   - Fix when [P1-12] 3-of-4 fulltext features is actually started
     (expected to be 1-2d effort per the [P1-12] estimate)
   - Lowest risk, no code change

**Recommendation**: Option 3 (current state) — feature isn't on the
near-term roadmap, and the fix touches the multi-channel fetch cascade
which is high-risk. Re-evaluate when starting [P1-12].

**Detect in CI**: `test_output/_import_smoke.py` now catches this
(fails if `pa_cli.deep_rerank` doesn't import). Run as part of
regression.

---

## 📚 Reference

- **ROADMAP.md** — formal status of all items
- **CHANGELOG.md** — version history with honest three-tier audit per release
- **pa-cli/v3.8.3+** — the `labels/` subpackage is the closest existing design to what falsifiability-score would look like (pluggable, ABC-based, post-processor)
- **scratchpad** — session-level working notes; not authoritative
- **Britannica "Philosophy of science"** — good Popper-Lakatos-Feyerabend-Shapere overview
- **Open Science Framework preregistration** — operationalized falsifiability pattern

---

**End of TODO.md** (2026-07-13 14:32)
