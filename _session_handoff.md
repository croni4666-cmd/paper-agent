# Session Handoff — paper-agent 增强计划 (v3.9.8.4)

**Date**: 2026-07-16 09:19
**From session**: mvs_6bb48cb3cb1e4e5b9bc5625f1a5b3da9
**Reason for handoff**: User experiencing intermittent 内部服务器错误 (mavis
daemon 3.0.48/3.0.49 known bug; watchdog monitors at C:\Users\DengN\.mavis\bin\Watch-Mavis.ps1)

## 1. Project state — current capability snapshot

paper-agent v3.9.8.4 (latest commit):

| Dimension | Status | Notes |
|---|---|---|
| **Search (6 engines)** | ✅ Production | crossref + openalex + arxiv + semanticscholar + aminer + cnki |
| **CNKI search** | ✅ Works (v3.9.7.4+) | xueshu789 cookies required, 4h TTL |
| **AMiner Chinese coverage** | ✅ +10.9pp cite lift on Chinese queries (verified v3.9.8.0) |
| **Fetch (Unpaywall)** | ✅ Works (v3.9.8.2: brotli fix) | Email `developers@unpaywall.org` works; `paper-agent@mavis.local` does not |
| **Fetch (CNKI /doDownload/)** | ❌ Blocked by bar.cnki.net vLevel=5 CAPTCHA | Architecture supports it, but anti-bot blocks all non-real-browser automation |
| **Fetch (sci-hub)** | ❌ All 7 mirrors dead (hijack or CF challenge) |
| **Fetch (annas-archive)** | ❌ .org SSL timeout, .gs is SPA (JS rendered) |
| **Batch fetch guide** | ✅ `pa fetch-batch -i input.txt -o guide.md` (v3.9.8.4) | Generates per-paper xueshu789 search URL + Edge console JS snippet |
| **Review (lit synthesis)** | ✅ `pa review <corpus_dir>` (v3.9.7+) | Synthesizes lit review from PDFs |
| **pa build (writing)** | ⏳ [P2-5] TODO | pandoc + XeLaTeX + GB/T 7714 CSL — 2-4h effort |
| **pa judge (relevance)** | ⏳ [P3-1] TODO | judgements.sqlite + LTR/BGE training data — 1-2h effort |
| **30-day AMiner eval cron** | ✅ Running | `aminer-30day-eval`, next run 2026-08-14 |

## 2. Commits in this session (newest first)

```
bdaa9a6 v3.9.8.3 (cont2): /doDownload/ exists but blocked by bar.cnki.net CAPTCHA vLevel=5
50b5e9c v3.9.8.3 (cont): CNKI 4-cookie confirm — detail page blocked by xueshu789 architecture, not cookies
d3ac3e2 v3.9.8.3: CNKI fetch honest eval + 2-cookie limit
5e3c41b v3.9.8.2: brotli decode fix + Unpaywall email discovery
a242af8 v3.9.8.2: pa fetch proxy support + Unpaywall email validation
acca2a8 v3.9.8.2: CORE engine honest re-evaluation + auth fix
```

Plus today's v3.9.8.4 commits (untracked log):
- `pa_cli/batch_fetch.py` (NEW)
- `pa_cli/cli.py` (added `fetch-batch` subcommand)
- `example_dois.txt` (input format example)
- `test_papers_real.txt` (real "数字普惠金融 家庭消费" test input)
- `test_output/_real_corpus_guide.md` (5/5 found output, 4 with DOI)
- `test_output/_example_guide.md` (4/6 found mixed DOI+title example)
- `Export-CNKICookies.ps1` (manual 4-cookie export)
- `export_cnki_cookies.py` (automated 2-cookie export — DEPRECATED, use manual)

## 3. Key file paths

| Path | Purpose |
|---|---|
| `G:\minimax - workspace\Paper agent\pa_cli\search.py` | 6-engine search (~600 LOC) |
| `G:\minimax - workspace\Paper agent\pa_cli\fetch.py` | Fetch (Unpaywall + cnki + scihub + annas) (~750 LOC) |
| `G:\minimax - workspace\Paper agent\pa_cli\cnki_channel.py` | CNKI search + bootstrap (~700 LOC) |
| `G:\minimax - workspace\Paper agent\pa_cli\aminer_channel.py` | AMiner 7th engine (~270 LOC) |
| `G:\minimax - workspace\Paper agent\pa_cli\batch_fetch.py` | NEW v3.9.8.4 batch guide generator (~280 LOC) |
| `G:\minimax - workspace\Paper agent\pa_cli\cli.py` | Click CLI (entry point) |
| `G:\minimax - workspace\Paper agent\Export-CNKICookies.ps1` | Manual 4-cookie export |
| `C:\Users\DengN\.paper-agent\cookies\cnki.json` | CNKI cookies (4 cookies, fresh = <4h) |
| `C:\Users\DengN\.paper-agent\debug\last_cnki_detail.html` | Last fetch debug HTML |
| `G:\minimax - workspace\Paper agent\ROADMAP.md` | 2554-line project roadmap |
| `G:\minimax - workspace\Paper agent\CHANGELOG.md` | All release notes |
| `G:\minimax - workspace\Paper agent\_session_handoff.md` | **This file** |

## 4. CNKI cookies state

As of 2026-07-16 08:38, user exported 4 cookies:
- `PHPSESSID` = `mtbapuk4vsfjqj7g3stg8rca86` (rotates on each new session)
- `user` = `5Wbv4H9Fy5OUcKW62NADcOgbDzNt_9Zy_xEjZ3MCuU4Y50XWLdPTNfIPOjLELh7fGgbSFeGEgdIYvMxNRG06Ss3` (long-lived)
- `entrys` = `1`
- `expires` = `gvh_qgeTOSNpc_iJ-VKnJoOj3s9UABR`

If new session needs to refetch: run `Export-CNKICookies.ps1` in Edge F12 console.

## 5. Open tasks (next session priorities)

1. **[P2-5] pa build** (2-4h) — pandoc + XeLaTeX + GB/T 7714 CSL
2. **[P3-1] pa judge** (1-2h) — relevance labels collection
3. **aminer-30day-eval cron** (auto, 2026-08-14) — decide AMiner renewal

## 6. Honest capability limits (re-state)

- **paper-agent cannot auto-download Chinese PDFs** — bar.cnki.net vLevel=5
  CAPTCHA is anti-bot final defense, blocks all non-real-browser automation.
  User's Edge + xueshu789 manual workflow is the only working path.
  Semi-automated: `pa fetch-batch` generates guide + Edge console JS to
  batch-extract doDownload URLs.
- **Chinese journal DOIs (10.3969/, 10.16525/, etc.) are NOT in OpenAlex or
  Crossref** — input titles (not DOIs) for AMiner coverage.
- **AMiner search by title is fuzzy** — returned paper may not be the exact
  one user wanted; verify the title in generated guide.

## 7. How to continue in new session

When new session starts, paste this entire file. I'll have full context.
Then:
- "Continue with [P2-5] pa build" → start writing pipeline
- "Continue with [P3-1] pa judge" → start relevance labels
- "Run pa fetch-batch for my real corpus" → need a list of titles/DOIs
- "Test the new cookie export" → may need fresh cookies if 4h TTL expired
