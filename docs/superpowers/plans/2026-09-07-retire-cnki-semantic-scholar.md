# CNKI and Semantic Scholar Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove CNKI and Semantic Scholar while retaining AMiner, supported search, and PMC PDF rendering.

**Architecture:** Rebase on a main branch containing PR #17, #18, and #19, or integrate their commits first. Remove retired engines at registration and fetch boundaries, delete dedicated modules, and retain Playwright only for JATS-to-PDF.

**Tech Stack:** Python 3.12, Click, unittest, Playwright, pwsh, rg.

**Spec:** docs/superpowers/specs/2026-09-07-retire-cnki-semantic-scholar-design.md

## Global Constraints

- Use pwsh and rg.
- Do not accept cnki, semanticscholar, S2_API_KEY, CNKI cookie, or CNKI proxy as product interfaces.
- Retain Playwright and Chromium only for PMC JATS-to-PDF.
- Preserve historical records; remove active instructions and operational scripts.
- Never output credentials or cookie content.

---

### Task 1: Remove search registrations

**Files:**
- Modify: pa_cli/search.py
- Modify: pa_cli/cli.py
- Test: tests/test_retired_engines.py

**Interfaces:**
- Consumes: run_search(query, engine, limit, ...)
- Produces: all-engine list of crossref, openalex, arxiv, aminer, pubmed, clinicaltrials; Click rejects retired values.

- [ ] **Step 1: Write failing tests**

```python
def test_all_search_has_no_retired_engine():
    result = search.run_search("machine learning", engine="all", limit=1)
    assert "cnki" not in result["by_engine"]
    assert "semanticscholar" not in result["by_engine"]

def test_cli_rejects_retired_engine():
    result = CliRunner().invoke(main, ["search", "x", "--engine", "cnki"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output
```

- [ ] **Step 2: Verify red**

Run: python -m unittest discover -s tests -p test_retired_engines.py -v

Expected: FAIL because both engines are registered.

- [ ] **Step 3: Implement the minimal removal**

```python
engines = ["crossref", "openalex", "arxiv", "aminer", "pubmed", "clinicaltrials"]
funcs = {
    "crossref": search_crossref, "openalex": search_openalex,
    "arxiv": search_arxiv, "aminer": search_aminer,
    "pubmed": search_pubmed, "clinicaltrials": search_clinicaltrials,
}
```

Delete S2 search/retry code and CNKI lazy import. Remove both values from Click Choice and help.

- [ ] **Step 4: Verify green**

Run: python -m unittest discover -s tests -p test_retired_engines.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add pa_cli/search.py pa_cli/cli.py tests/test_retired_engines.py
git commit -m "refactor: retire CNKI and Semantic Scholar search"
```

### Task 2: Remove fetch, MCP, and setup paths

**Files:**
- Modify: pa_cli/fetch.py
- Modify: pa_cli/mcp_fetch.py
- Modify: pa_cli/keys.py
- Modify: pa_cli/cli.py
- Delete: pa_cli/cnki_channel.py, pa_cli/s2_channel.py, Export-CNKICookies.ps1, export_cnki_cookies.py, pa_cli/batch_fetch.py
- Test: tests/test_retired_engines.py

**Interfaces:**
- Consumes: fetch_doi(doi, output_dir, prefer, channels, ...)
- Produces: supported fetch preferences without cnki or s2.

- [ ] **Step 1: Extend failing tests**

```python
def test_cli_rejects_retired_fetch_preferences():
    for preference in ("cnki", "s2"):
        result = CliRunner().invoke(main, ["fetch", "10.1/example", "--prefer", preference])
        assert result.exit_code != 0

def test_fetch_source_has_no_retired_branch():
    source = Path("pa_cli/fetch.py").read_text(encoding="utf-8")
    assert "fetch_cnki_detail" not in source
    assert "fetch_s2_doi" not in source
```

- [ ] **Step 2: Verify red**

Run: python -m unittest discover -s tests -p test_retired_engines.py -v

Expected: FAIL because both fetch preferences and functions exist.

- [ ] **Step 3: Implement minimal removal**

Delete CNKI/S2 fetch functions, imports, error constants, preference mappings, DOI heuristic, MCP enum values, CNKI guide command, and S2 key registry entry. Keep pmc-pdf and JATS Playwright code.

- [ ] **Step 4: Verify green**

Run: python -m unittest discover -s tests -p test_retired_engines.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add -A pa_cli/fetch.py pa_cli/mcp_fetch.py pa_cli/keys.py pa_cli/cli.py pa_cli/cnki_channel.py pa_cli/s2_channel.py Export-CNKICookies.ps1 export_cnki_cookies.py pa_cli/batch_fetch.py tests/test_retired_engines.py
git commit -m "refactor: remove retired retrieval channels"
```

### Task 3: Update doctor and active documentation

**Files:**
- Modify: pa_cli/doctor.py
- Modify: README.md, pa_cli/README.md, requirements-optional.txt, ROADMAP.md, SECURITY.md
- Test: tests/test_doctor.py

**Interfaces:**
- Consumes: build_report() from PR #19.
- Produces: a report without retired-engine advice and active documentation for retained engines only.

- [ ] **Step 1: Write failing test**

```python
def test_doctor_omits_retired_integrations():
    rendered = json.dumps(doctor.build_report())
    assert "cnki" not in rendered.lower()
    assert "semantic" not in rendered.lower()
    assert "S2_API_KEY" not in rendered
```

- [ ] **Step 2: Verify red**

Run: python -m unittest discover -s tests -p test_doctor.py -v

Expected: FAIL because doctor still reports CNKI and Semantic Scholar.

- [ ] **Step 3: Implement minimal documentation changes**

Remove both doctor checks and related setup advice. Keep Playwright and state it supports PMC PDF rendering. Remove active CNKI/S2 references from CLI help, README and security/configuration documents. Add a dated retirement note to ROADMAP without rewriting historical release entries.

- [ ] **Step 4: Verify green**

Run: python -m unittest discover -s tests -p 'test_*.py' -v

Run: python -m pa_cli.cli search --help

Run: python -m pa_cli.cli fetch --help

Expected: tests pass and help exposes no retired option.

- [ ] **Step 5: Commit**

```text
git add pa_cli/doctor.py README.md pa_cli/README.md requirements-optional.txt ROADMAP.md SECURITY.md tests/test_doctor.py
git commit -m "docs: remove retired engine guidance"
```

### Task 4: Real acceptance and pull request

**Files:**
- Test only: current branch

**Interfaces:**
- Consumes: retained search engines, doctor, and PMC JATS-to-PDF.
- Produces: release evidence and a reviewable pull request.

- [ ] **Step 1: Run static and unit validation**

```text
python -W error::SyntaxWarning -m compileall -q pa_cli
python -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

- [ ] **Step 2: Run real retained-engine checks**

```text
python -X utf8 -m pa_cli.cli doctor --json
python -X utf8 -m pa_cli.cli search "machine learning" --engine aminer --limit 1 --format json
python -X utf8 -m pa_cli.cli search "machine learning" --engine openalex --limit 1 --format json
```

Expected: doctor omits retired engines and both searches return structured results.

- [ ] **Step 3: Run real PDF check**

```text
python -X utf8 -m pa_cli.cli fetch 10.3389/fendo.2026.1798827 --prefer pmc-pdf --output-dir $env:TEMP\paper-agent-retirement-pdf
```

Expected: SUCCESS through pmc_jats_pdf or another PMC route; output begins with %PDF-.

- [ ] **Step 4: Request independent review**

Review removed paths, retained Playwright behavior, public help, and credential handling. Resolve Critical and Important findings.

- [ ] **Step 5: Create pull request**

```text
git push -u origin refactor/retire-cnki-semantic-scholar-20260907
gh pr create --base main --title "refactor: retire CNKI and Semantic Scholar" --body-file $env:TEMP\paper-agent-retirement-pr.md
```


