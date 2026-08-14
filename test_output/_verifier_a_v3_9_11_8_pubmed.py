"""Independent verifier for paper-agent v3.9.11.8 PubMed engine.

Tests the 6 scenarios required by the verifier brief. Does NOT trust the
main session's test results — runs them ourselves and reports honestly.

Required tests:
  1. Functional: ACE inhibitors hypertension RCT, year>=2024, limit=5
  2. Edge 1: Empty result (gibberish query)
  3. Edge 2: Year range both bounds (diabetes, 2020 only)
  4. Edge 3: Bare query (no quotes) — aspirin
  5. Rate limit: 5 searches quick succession
  6. Format check: --format json parseable, --format bibtex has @article
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)

LOG_PATH = Path("test_output") / "_verifier_a_v3_9_11_8.log"
LOG = open(LOG_PATH, "w", encoding="utf-8")


def log(msg=""):
    """Write to both stdout and the log file."""
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def run_pa_search_raw(args, timeout_sec=120):
    """Run pa search with given args, return (returncode, stdout, stderr, elapsed)."""
    cmd = [sys.executable, "-m", "pa_cli", "search"] + args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = PROJ + os.pathsep + env.get("PYTHONPATH", "")
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_sec, encoding="utf-8", errors="replace",
            env=env,
        )
        elapsed = time.time() - t0
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return -1, "", f"TIMEOUT after {timeout_sec}s", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        return -2, "", f"EXCEPTION: {type(e).__name__}: {e}", elapsed


def parse_json_output(stdout: str):
    """Strip [pa] log lines, find first { or [, return parsed JSON or None + reason."""
    cleaned = "\n".join(L for L in stdout.splitlines() if not L.startswith("[pa]"))
    # Find first { or [
    for i, c in enumerate(cleaned):
        if c in "{[":
            start = i
            break
    else:
        return None, f"No JSON/object. tail={stdout[-200:]!r}"
    text = cleaned[start:].strip()
    if not text:
        return None, f"Empty after start. tail={stdout[-200:]!r}"
    # Try to find the matching end (single top-level dict or list)
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse: {e}. text[:300]={text[:300]!r}"


def first_paper_pubmed(data):
    """Get first paper from result (whether list or dict with results key)."""
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        papers = data.get("results", [])
        return papers[0] if papers else None
    return None


def count_papers(data):
    """Get number of papers in result."""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return len(data.get("results", []))
    return 0


def get_pubmed_papers(data):
    """Get papers that came from pubmed source."""
    if not isinstance(data, dict):
        return []
    return [p for p in data.get("results", []) if p.get("source") == "pubmed"]


log("=" * 78)
log("INDEPENDENT VERIFIER — paper-agent v3.9.11.8 PubMed engine")
log("=" * 78)
log(f"Project dir: {PROJ}")
log(f"Log file:    {LOG_PATH}")
log(f"Python:      {sys.version}")
log(f"Working dir: {os.getcwd()}")
log("")

# ── Confirm v3.9.11.8 is HEAD ──────────────────────────────────────────
log("[0] Confirm v3.9.11.8 is HEAD")
git_log_proc = subprocess.run(
    ["git", "log", "--oneline", "-3"],
    capture_output=True, text=True, encoding="utf-8", cwd=PROJ,
)
log("git log --oneline -3:")
log(git_log_proc.stdout.rstrip())
git_hash_proc = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    capture_output=True, text=True, encoding="utf-8", cwd=PROJ,
)
head_short = git_hash_proc.stdout.strip()
log(f"HEAD short: {head_short}")
v3_9_11_8_ok = "c816fca" in head_short or "v3.9.11.8" in git_log_proc.stdout
log(f"v3.9.11.8 confirmed: {v3_9_11_8_ok}")
log("")

results = {}

# ════════════════════════════════════════════════════════════════════════
# Test 1: Functional — ACE inhibitors hypertension RCT
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 1: Functional — pa search 'ACE inhibitors hypertension RCT'")
log("        --engine pubmed --year-min 2024 --limit 5")
log("─" * 78)
rc, stdout, stderr, elapsed = run_pa_search_raw(
    ["ACE inhibitors hypertension RCT",
     "--engine", "pubmed", "--year-min", "2024",
     "--limit", "5", "--format", "json"],
    timeout_sec=120,
)
log(f"  rc={rc}  elapsed={elapsed:.1f}s  stdout_len={len(stdout)}")
if stderr.strip():
    log(f"  stderr: {stderr.strip()[:300]}")
data, perr = parse_json_output(stdout)
if perr:
    log(f"  PARSE ERROR: {perr}")
    results["T1"] = ("FAIL", perr, None, None)
else:
    papers = get_pubmed_papers(data)
    n = len(papers)
    log(f"  pubmed papers returned: {n}")
    if papers:
        for i, p in enumerate(papers[:5]):
            log(f"  [{i+1}] pmid={p.get('pmid', '-')!s:10s} year={p.get('year', '-')!s:5s} "
                f"doi={p.get('doi', '-') or '-':40s}")
            log(f"      title:  {(p.get('title') or '')[:80]}")
            log(f"      venue:  {(p.get('venue') or '-')[:50]}")
    first = papers[0] if papers else None
    has_pmid = bool(first and first.get("pmid"))
    has_doi = bool(first and first.get("doi"))
    has_year = bool(first and first.get("year"))
    has_venue = bool(first and first.get("venue"))
    n_ok = n >= 3
    fields_ok = has_pmid and has_doi and has_year and has_venue
    # year must be >= 2024
    year_ok = bool(first and first.get("year") and int(first["year"]) >= 2024)
    if n_ok and fields_ok and year_ok:
        results["T1"] = ("PASS", f"{n} papers, first pmid={first['pmid']} doi={first.get('doi')}",
                         first, papers)
    else:
        results["T1"] = ("FAIL",
                         f"n_ok={n_ok} fields_ok={fields_ok} year_ok={year_ok} n={n}",
                         first, papers)
    log(f"  n>=3: {n_ok}  has pmid+doi+year+venue: {fields_ok}  year>=2024: {year_ok}")
log(f"  Test 1: {results['T1'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# Test 2: Edge 1 — Empty result
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 2: Edge 1 — pa search 'asdfqwerzxcvbnmlkjhgf' --engine pubmed --limit 5")
log("        Should return [] (empty list), not an error")
log("─" * 78)
rc, stdout, stderr, elapsed = run_pa_search_raw(
    ["asdfqwerzxcvbnmlkjhgf",
     "--engine", "pubmed", "--limit", "5", "--format", "json"],
    timeout_sec=60,
)
log(f"  rc={rc}  elapsed={elapsed:.1f}s  stdout_len={len(stdout)}")
if stderr.strip():
    log(f"  stderr: {stderr.strip()[:300]}")
data, perr = parse_json_output(stdout)
if perr:
    log(f"  PARSE ERROR: {perr}")
    results["T2"] = ("FAIL", perr, None, None)
else:
    n = count_papers(data)
    if isinstance(data, dict):
        # unified shape
        by_engine = data.get("by_engine", {})
        pubmed_n = by_engine.get("pubmed", 0)
    else:
        pubmed_n = n
    log(f"  total papers: {n}  pubmed count: {pubmed_n}")
    log(f"  full JSON: {json.dumps(data)[:200]!r}")
    if rc == 0 and n == 0 and pubmed_n == 0:
        results["T2"] = ("PASS", "Empty result, no error, rc=0", data, None)
    elif rc == 0 and (n == 0 or pubmed_n == 0):
        results["T2"] = ("PASS", f"Empty or no pubmed papers (n={n}, pubmed_n={pubmed_n})", data, None)
    else:
        results["T2"] = ("FAIL", f"Expected empty. Got n={n} pubmed_n={pubmed_n} rc={rc}",
                         data, None)
log(f"  Test 2: {results['T2'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# Test 3: Edge 2 — Year range both bounds
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 3: Edge 2 — pa search 'diabetes' --engine pubmed "
    "--year-min 2020 --year-max 2020 --limit 5")
log("        Should return 2020-only papers")
log("─" * 78)
rc, stdout, stderr, elapsed = run_pa_search_raw(
    ["diabetes",
     "--engine", "pubmed", "--year-min", "2020", "--year-max", "2020",
     "--limit", "5", "--format", "json"],
    timeout_sec=60,
)
log(f"  rc={rc}  elapsed={elapsed:.1f}s  stdout_len={len(stdout)}")
if stderr.strip():
    log(f"  stderr: {stderr.strip()[:300]}")
data, perr = parse_json_output(stdout)
if perr:
    log(f"  PARSE ERROR: {perr}")
    results["T3"] = ("FAIL", perr, None, None)
else:
    papers = get_pubmed_papers(data)
    n = len(papers)
    years = [p.get("year") for p in papers]
    log(f"  pubmed papers: {n}  years: {years}")
    for i, p in enumerate(papers[:5]):
        log(f"  [{i+1}] pmid={p.get('pmid', '-')!s:10s} year={p.get('year', '-')!s:5s} "
            f"doi={(p.get('doi') or '-')[:40]}")
        log(f"      title: {(p.get('title') or '')[:80]}")
    all_2020 = n > 0 and all(y == 2020 for y in years)
    if all_2020:
        results["T3"] = ("PASS", f"{n} papers, all 2020", papers[0], papers)
    else:
        results["T3"] = ("FAIL", f"n={n} years={years} not_all_2020={not all_2020}",
                         papers[0] if papers else None, papers)
log(f"  Test 3: {results['T3'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# Test 4: Edge 3 — Bare query (no quotes)
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 4: Edge 3 — pa search aspirin --engine pubmed --limit 3")
log("        No quotes on query, single word")
log("─" * 78)
rc, stdout, stderr, elapsed = run_pa_search_raw(
    ["aspirin", "--engine", "pubmed", "--limit", "3", "--format", "json"],
    timeout_sec=60,
)
log(f"  rc={rc}  elapsed={elapsed:.1f}s  stdout_len={len(stdout)}")
if stderr.strip():
    log(f"  stderr: {stderr.strip()[:300]}")
data, perr = parse_json_output(stdout)
if perr:
    log(f"  PARSE ERROR: {perr}")
    results["T4"] = ("FAIL", perr, None, None)
else:
    papers = get_pubmed_papers(data)
    n = len(papers)
    log(f"  pubmed papers: {n}")
    for i, p in enumerate(papers[:3]):
        log(f"  [{i+1}] pmid={p.get('pmid', '-')!s:10s} year={p.get('year', '-')!s:5s} "
            f"doi={(p.get('doi') or '-')[:40]}")
        log(f"      title: {(p.get('title') or '')[:80]}")
    if n > 0 and all(p.get("pmid") for p in papers):
        results["T4"] = ("PASS", f"{n} papers, all have pmid", papers[0], papers)
    else:
        results["T4"] = ("FAIL", f"n={n} or missing pmid", papers[0] if papers else None, papers)
log(f"  Test 4: {results['T4'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# Test 5: Rate limit — 5 searches in quick succession
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 5: Rate limit — 5 searches in quick succession")
log("        Each should succeed; observe 429s or throttle behavior")
log("─" * 78)
queries = [
    "cancer immunotherapy 2024",
    "CRISPR gene editing",
    "machine learning medical diagnosis",
    "Alzheimer disease biomarkers",
    "long COVID symptoms",
]
t0_all = time.time()
rate_results = []
for q in queries:
    rc, stdout, stderr, elapsed = run_pa_search_raw(
        [q, "--engine", "pubmed", "--limit", "3", "--format", "json"],
        timeout_sec=60,
    )
    data, perr = parse_json_output(stdout)
    n = count_papers(data) if data else 0
    if "429" in stderr or "429" in stdout or "Too Many Requests" in (stderr + stdout):
        status = "THROTTLED_429"
    elif rc != 0:
        status = f"RC_{rc}"
    elif perr:
        status = f"PARSE_ERR"
    elif n == 0:
        status = "EMPTY"
    else:
        status = f"OK_{n}"
    rate_results.append((q, rc, n, elapsed, status, stderr.strip()[:100]))
    log(f"  [{len(rate_results)}] q='{q[:35]}'  rc={rc}  n={n}  "
        f"elapsed={elapsed:.1f}s  status={status}")
total_elapsed = time.time() - t0_all
n_ok = sum(1 for r in rate_results if r[2] > 0 and r[1] == 0)
n_throttled = sum(1 for r in rate_results if r[4] == "THROTTLED_429")
log(f"  Total elapsed: {total_elapsed:.1f}s  successful: {n_ok}/{len(queries)}  "
    f"throttled: {n_throttled}/{len(queries)}")
if n_throttled == 0 and n_ok == len(queries):
    results["T5"] = ("PASS", f"All 5 queries succeeded, no 429s, {total_elapsed:.1f}s total",
                     None, None)
elif n_throttled > 0:
    results["T5"] = ("FAIL", f"{n_throttled}/5 throttled with 429", None, None)
elif n_ok < len(queries):
    results["T5"] = ("FAIL", f"Only {n_ok}/{len(queries)} succeeded", None, None)
else:
    results["T5"] = ("WARN", f"Mixed results — {n_ok}/{len(queries)} OK, see above", None, None)
log(f"  Test 5: {results['T5'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# Test 6: Format check
# ════════════════════════════════════════════════════════════════════════
log("─" * 78)
log("Test 6: Format check — --format json parseable, --format bibtex has @article")
log("─" * 78)
# 6a: JSON format on a simple query
rc, stdout, stderr, elapsed = run_pa_search_raw(
    ["hypertension treatment", "--engine", "pubmed", "--limit", "3", "--format", "json"],
    timeout_sec=60,
)
log(f"  [6a JSON] rc={rc}  elapsed={elapsed:.1f}s  stdout_len={len(stdout)}")
if stderr.strip():
    log(f"    stderr: {stderr.strip()[:200]}")
data, perr = parse_json_output(stdout)
json_ok = False
if perr:
    log(f"    PARSE ERROR: {perr}")
else:
    # Check it's structured data with results
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        log(f"    JSON valid: {len(data['results'])} papers in results array")
        json_ok = True
    elif isinstance(data, list):
        log(f"    JSON valid: top-level list with {len(data)} papers")
        json_ok = True
    else:
        log(f"    JSON parsed but unexpected shape: type={type(data).__name__}")

# 6b: BibTeX format
rc2, stdout2, stderr2, elapsed2 = run_pa_search_raw(
    ["hypertension treatment", "--engine", "pubmed", "--limit", "3", "--format", "bibtex"],
    timeout_sec=60,
)
log(f"  [6b BibTeX] rc={rc2}  elapsed={elapsed2:.1f}s  stdout_len={len(stdout2)}")
if stderr2.strip():
    log(f"    stderr: {stderr2.strip()[:200]}")
bibtex_text = stdout2
n_articles = len(re.findall(r"@\w+\s*\{", bibtex_text))
n_at_article = bibtex_text.count("@article")
log(f"    @-entries: {n_articles}  @article count: {n_at_article}")
# Show first 400 chars of bibtex
if bibtex_text:
    log(f"    bibtex preview: {bibtex_text[:300]!r}")
bibtex_ok = n_at_article >= 1
if json_ok and bibtex_ok:
    results["T6"] = ("PASS", f"JSON parseable, BibTeX has {n_at_article} @article",
                     None, None)
elif not json_ok:
    results["T6"] = ("FAIL", "JSON not parseable", None, None)
else:
    results["T6"] = ("FAIL", f"BibTeX has only {n_at_article} @article entries", None, None)
log(f"  Test 6: {results['T6'][0]}")
log("")

# ════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════
log("=" * 78)
log("INDEPENDENT VERIFIER SUMMARY")
log("=" * 78)
log("")
log("Test                                              Result  Detail")
log("-" * 78)
labels = {
    "T1": "1. Functional: ACE inhibitors + RCT, year>=2024",
    "T2": "2. Edge 1:    Empty result on gibberish query",
    "T3": "3. Edge 2:    Year range both bounds (2020 only)",
    "T4": "4. Edge 3:    Bare query (aspirin, no quotes)",
    "T5": "5. Rate limit: 5 quick searches, no 429s",
    "T6": "6. Format:    --format json parseable, --format bibtex has @article",
}
n_pass = 0
for k in ("T1", "T2", "T3", "T4", "T5", "T6"):
    status, detail, _, _ = results.get(k, ("?", "no result", None, None))
    if status == "PASS":
        n_pass += 1
    log(f"  {labels[k]:55s}  {status:6s}  {detail}")
log("")
log(f"  TOTAL: {n_pass}/6 PASS")
log("")

if n_pass == 6:
    log("VERDICT: PubMed engine is solid for production use.")
    log("         All 6 scenarios pass: functional, edge cases, rate limit, format.")
    sys.exit_code = 0
elif n_pass >= 4:
    log("VERDICT: Mostly working, some edge cases need attention. See FAIL above.")
    sys.exit_code = 1
else:
    log("VERDICT: PubMed engine is NOT production-ready. Multiple failures.")
    sys.exit_code = 2

log("")
log(f"Log saved to: {LOG_PATH}")
log(f"Exit code: {sys.exit_code}")

LOG.close()
sys.exit(sys.exit_code)
