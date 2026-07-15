"""Insert v3.9.8.2 CORE honest re-evaluation into CHANGELOG.md."""
import re
from pathlib import Path

CHANGELOG = Path("G:/minimax - workspace/Paper agent/CHANGELOG.md")
content = CHANGELOG.read_text(encoding="utf-8")

new_entry = """

## [Unreleased] - 2026-07-15 (CORE cleanup + honest re-evaluation)

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
"""

# Insert before the next '## [' heading after the docs unreleased block
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
print("CHANGELOG.md updated, length:", len(content))
