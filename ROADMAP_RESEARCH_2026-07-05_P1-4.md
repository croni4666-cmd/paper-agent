# P1-4 Research: Lit Review Synthesis Tools (2026-07-05)

## Why this doc exists

User explicit (last turn): "搜索 github 和搜索引擎 看看有没有类似我们情况的解决方案" — wanted to verify paper-agent's P1-4 trajectory isn't duplicating something already built before investing further in it.

## Scope of search

What we were looking for: **personal-scale mixed-format corpus → topic clustering + relation extraction + LLM-prompt-pack output** for literature review synthesis. Single-user, CLI, $0-cost, no hosted service.

## Candidates considered

### Tier 1: Real, shipped, comparable tools

| Project | Stars | Last commit | License | Interface | Verdict |
|---|---|---|---|---|---|
| **CoLRev-Environment/colrev** | 43 | active (Feb 2026 release) | MIT | CLI + Programmatic (GUI planned) | Real competitor but **different scope** — see below |
| **NLeSC/litstudy** | smaller | older | MIT | Jupyter Notebook | Older, narrower scope, NB-only |
| **clbustos/buhos** | smaller | older | MIT | Ruby web-UI | Wrong language, server-based |
| **Covidence** | n/a | n/a | proprietary | web | Not OSS, out of scope |

### Tier 2: Research papers, no code released

| Paper | Authors | Year | Code | Relevant? |
|---|---|---|---|---|
| **AHAM** (arxiv 2312.15784) | Koloski, Lavrač, Cestnik, Pollak, Škrlj, Kastrin (Slovene academic) | Dec 2023 | ❌ no GitHub, no PyPI | **YES** — BERTopic + LLaMa2 one-shot topic definitions on literature-mining corpus; published to IDA 2024. Method paper, not tool |
| **LLM-Assisted Topic Reduction for BERTopic** (arxiv 2509.19365) | Janssens, Bogaert, Van den Poel (Ghent U) | Sep 2025 | ❌ no code | **YES** — BERTopic + LLM iterative merging on Twitter/X; ECML PKDD 2025 Workshop. Method paper, not tool |
| **Automated Lit Review Using LLMs** (Springer 2025) | academic | 2025 | ❌ | Pipeline concept, GPT-3.5 + Arxiv-focused. Not a tool |
| **TowardsDataScience BERTopic guide** | tutorial | n/a | n/a | Just shows BERTopic.representation_model can be `OpenAI` / `KeyBERTInspired` / `MMR` / `ZeroShotClassification` — confirms pattern |

### Tier 3: Not relevant / noise

- Zotero / EndNote / Mendeley — reference managers, not synthesizers
- ChatPaper, GPT Academic — paper Q&A, not synthesis
- PyPaperBot, IA sandcrawler — fetch tools only

## CoLRev deep dive

**CoLRev-Environment/colrev** (`https://github.com/CoLRev-Environment/colrev`)

- 4,664 commits, 35 releases, latest **v0.16.2 (Feb 24, 2026)**
- Python 91.3% / TeX 8.2%, MIT license
- CLI + Programmatic interface
- 19 search APIs (Crossref, OpenAlex, etc.) — comparable to paper-agent v3.x's 5 engines
- 111 extensions
- Covers full pipeline: problem formulation → search → dedupe → (pre)screen → PDF retrieval → preparation → synthesis
- 9 contributors with academic affiliations
- Comparison table from their README shows: more comprehensive than LitStudy (Python/Jupyter), BUHOS (Ruby/web), Covidence (proprietary)
- **Different design center**: Git-based **collaborative** multi-author workflow + full SLR process. They own the data repo; multiple authors commit review status to shared git repo; status tracking, retract checks, screen disagreements are first-class.
- DOI: 10.5281/zenodo.18762354 (peer-reviewed core libraries)

**Why CoLRev is NOT a substitute for paper-agent**:
1. **Scope**: CoLRev is end-to-end SLR including deduplication, screen, PDF retrieval. paper-agent v3 focuses on **single-user paper fetch + light lit review synthesis** (corpus → topics → prompt pack). CoLRev's `synthesis` step is a hook for external tools, not a built-in topic modeler.
2. **Use case**: CoLRev = multi-author systematic review (PhD student + supervisor, or research team). paper-agent = one researcher curating their own reading list.
3. **Architecture**: CoLRev uses Git as the database (every reviewed record is a YAML file with status field). paper-agent uses local JSON cache keyed by DOI. Heavier to set up CoLRev than paper-agent for solo use.
4. **Cost/learning curve**: CoLRev's 4.6k commits and 19 search APIs + extensions suggest a heavier setup. paper-agent's design center is "5-min setup, zero-config pip install".
5. **LLM prompt-pack output**: CoLRev's synthesis step is human-driven via CoLRev-controlled templates + jinja. They don't auto-cluster topics with BERTopic. Their `colrev package install` extensions include some LLM add-ons but the core flow is human review.

## AHAM + LLM-Topic-Reduction papers

Both are **academic method papers** that describe how to combine BERTopic + LLM (LLaMa2 / GPT / etc.) for better topic naming. Neither released code. They prove the **direction paper-agent is heading is well-established in academic literature** (Sep 2025 paper = fresh evidence), but they don't compete with paper-agent because:
- They're research, not tools
- The methods they describe (LLM labeling of BERTopic clusters) are exactly what paper-agent P1-6 (LLM prompt pack) should adopt as the synthesis step
- Adopting their pattern in P1-6 = following best practice, not duplicating a tool

## Honest assessment

**The niche paper-agent fills is not occupied by any OSS tool as of 2026-07-05**:

- CoLRev covers the **team SLR** niche (closer, but different scope + heavier)
- AHAM / LLM-Topic-Reduction prove the **method** but ship no code
- No tool does: `personal mixed-format corpus → topic cluster (BERTopic) → topic labels (LLM, optional) → relations (citation/concept graph) → synthesis prompt pack → Mavis session writes narrative`

**Risks**:
- CoLRev could pivot toward LLM-driven synthesis in a future release (their extensions ecosystem allows it). Low probability in 2026.
- Academic tooling space moves fast — by 2027 a small OSS tool could appear. Probability: medium.

**Recommendation**: **Keep going with current P1-4 trajectory**. Commit `pa review-topics` as v3.8.0. Continue P1-5 (relations) → P1-6 (synthesize/prompt pack). The combination of `pa review` + `pa review-topics` + future `pa review-relations` + `pa review-synthesize` is paper-agent's unique value proposition.

**If user wants to adopt CoLRev**: that's a 6-12 month commitment to learn their git-based workflow + write custom extensions. Out of scope for personal-hobbyist ceiling (per user Global Rule). Documented in ROADMAP as "considered, rejected with rationale" so we don't re-litigate.

## What we learned (and should write down)

1. **BERTopic + LLM labeling is the right architecture** (AHAM, LLM-Topic-Reduction confirm). paper-agent P1-6 should support `representation_model = {KeyBERTInspired, OpenAI, local}` like BERTopic's own API.
2. **No need to compete on scale** — CoLRev is the scale play (111 extensions, 19 APIs); paper-agent's edge is "5-min setup, single-user, opinionated prompt pack output".
3. **CoLRev is the closest threat** — if a user wants a real SLR tool, they'll find CoLRev first. paper-agent's positioning must be: "I already have my reading list as PDFs/MDs; I don't want to learn git-based multi-author workflow; I just want topic clusters + a narrative draft."

## Audit trail

- Search date: 2026-07-05
- Search channels: web_search (4 queries), webfetch (3 sources: CoLRev README, AHAM arxiv, LLM-Topic-Reduction arxiv)
- Reviewed by: Mavis (self), as part of P1-4 verification before commit
- Conclusion: P1-4 greenlit; commit as v3.8.0; P1-5 next