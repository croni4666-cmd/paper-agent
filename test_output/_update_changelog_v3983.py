"""Insert v3.9.8.3 CNKI fetch honest-eval into CHANGELOG.md."""
import re
from pathlib import Path

CHANGELOG = Path("G:/minimax - workspace/Paper agent/CHANGELOG.md")
content = CHANGELOG.read_text(encoding="utf-8")

new_entry = """

## [Unreleased] - 2026-07-15 (CNKI fetch honest evaluation + 2-cookie limit)

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
"""

m = re.search(r"## \[Unreleased\] - 2026-07-15 \(docs", content)
if m:
    pos = m.end()
    next_h = re.search(r"\n## \[", content[pos:])
    if next_h:
        ins_pos = pos + next_h.start()
        content = content[:ins_pos] + new_entry + content[ins_pos:]
    else:
        content = content + new_entry
else:
    content = content + new_entry

CHANGELOG.write_text(content, encoding="utf-8")
print("CHANGELOG.md updated, total length:", len(content))
