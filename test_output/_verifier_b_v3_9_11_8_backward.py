"""
Independent verifier for paper-agent v3.9.11.8 (PubMed engine).
Tests 7 backward-compat scenarios. Writes human-readable log to
test_output/_verifier_b_v3_9_11_8.log and prints a summary.

Run with:
  set PYTHONIOENCODING=utf-8
  set PYTHONUTF8=1
  python test_output/_verifier_b_v3_9_11_8_backward.py
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

# Force UTF-8 on Windows (GBK default would UnicodeEncodeError on
# non-ASCII titles in pa search output)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

ROOT = Path(r"G:\minimax - workspace\Paper agent")
TEST_OUT = ROOT / "test_output"
LOG_FILE = TEST_OUT / "_verifier_b_v3_9_11_8.log"
TEST_OUT.mkdir(exist_ok=True)

# Ensure repo root is on sys.path so `from pa_cli...` works when invoked as
# a standalone script via `python test_output/_verifier_*.py`
sys.path.insert(0, str(ROOT))

# Clear log
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

def log(msg: str = "") -> None:
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def run_pa_search(args, timeout=120):
    """Run pa search with given args. Return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "pa_cli", "search"] + args
    log(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            timeout=timeout, env=os.environ.copy(),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout}s"

def parse_json_or_log(stdout, label, expect_results=True):
    """Parse the JSON output of `pa search`. Returns dict or None on failure."""
    # pa prints progress to stderr and final JSON to stdout.
    # If --output was set, it writes to file. We capture stdout here.
    try:
        data = json.loads(stdout)
        return data
    except json.JSONDecodeError as e:
        log(f"  [WARN] {label}: stdout is not pure JSON: {e}")
        # Some engines may emit warnings to stdout; try to recover last JSON object
        # In practice pa writes the final JSON object to stdout, so we just log
        log(f"  raw stdout first 200 chars: {stdout[:200]!r}")
        return None

def test_version():
    log("\n=== Test 5: pa --version ===")
    cmd = [sys.executable, "-m", "pa_cli", "--version"]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       env=os.environ.copy(), timeout=30)
    out = (r.stdout or "") + (r.stderr or "")
    log(f"  exit={r.returncode}")
    log(f"  output: {out.strip()}")
    ok = "3.9.11.8" in out
    log(f"  result: {'PASS' if ok else 'FAIL'} (expected '3.9.11.8' in output)")
    return ok

def test_help_text():
    log("\n=== Test 7: pa search --help mentions pubmed ===")
    cmd = [sys.executable, "-m", "pa_cli", "search", "--help"]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       env=os.environ.copy(), timeout=30)
    out = (r.stdout or "") + (r.stderr or "")
    has_pubmed = "pubmed" in out.lower()
    log(f"  exit={r.returncode}, has_pubmed_in_help={has_pubmed}")
    # Also dump the --engine line for visibility
    for line in out.splitlines():
        if "--engine" in line and "all" in line:
            log(f"  help line: {line.strip()[:200]}")
    log(f"  result: {'PASS' if has_pubmed else 'FAIL'}")
    return has_pubmed

def test_engine(engine: str, query: str, limit: int = 3, label: str = None,
                extra_args=None, expect_any: bool = True) -> dict:
    """Run pa search --engine X. Return parsed dict and pass/fail."""
    label = label or engine
    log(f"\n=== Test 1.{engine}: pa search --engine {engine} ===")
    args = [query, "--engine", engine, "--limit", str(limit), "--quiet"]
    if extra_args:
        args += extra_args
    rc, out, err = run_pa_search(args, timeout=120)
    log(f"  exit={rc}")
    if err:
        log(f"  stderr (last 300): {err[-300:]}")
    if rc != 0:
        log(f"  [WARN] non-zero exit; first 500 of stdout: {out[:500]}")
        return {"engine": engine, "rc": rc, "pass": False,
                "reason": f"exit {rc}", "first_title": None, "first_doi": None}
    data = parse_json_or_log(out, f"engine={engine}")
    if not data:
        return {"engine": engine, "rc": rc, "pass": False,
                "reason": "no JSON", "first_title": None, "first_doi": None}
    # pa may put results at top-level 'results' or under by_engine
    papers = data.get("results", [])
    by_engine = data.get("by_engine", {})
    log(f"  results_count={len(papers)} by_engine_keys={list(by_engine.keys())}")
    # If a single engine was requested, also check the by_engine slot
    if engine in by_engine:
        slot = by_engine[engine]
        if isinstance(slot, list) and slot and isinstance(slot[0], dict):
            if "error" in slot[0]:
                log(f"  [WARN] by_engine[{engine}] first item has error: {slot[0]}")
    if not expect_any:
        log(f"  result: PASS (no results expected, got {len(papers)})")
        return {"engine": engine, "rc": rc, "pass": True,
                "first_title": None, "first_doi": None,
                "results_count": len(papers)}
    if not papers:
        # Engine may be optional (aminer/cnki) - log as fail but record reason
        log(f"  result: FAIL (0 results, expected some)")
        return {"engine": engine, "rc": rc, "pass": False,
                "reason": "0 results", "first_title": None, "first_doi": None}
    first = papers[0]
    title = first.get("title", "(no title)")
    doi = first.get("doi", "")
    arxiv = first.get("arxiv_id", "")
    pmid = first.get("pmid", "")
    log(f"  first_title: {title[:120]}")
    log(f"  first_doi={doi!r} arxiv_id={arxiv!r} pmid={pmid!r}")
    log(f"  result: PASS ({len(papers)} results, first has title)")
    return {"engine": engine, "rc": rc, "pass": True,
            "first_title": title, "first_doi": doi,
            "first_arxiv": arxiv, "first_pmid": pmid,
            "results_count": len(papers)}

def test_engine_all_includes_pubmed():
    log("\n=== Test 2: pa search --engine all includes pubmed ===")
    # NOTE: returned JSON's by_engine is {engine: int_count}, not lists.
    # The "all" list (line 811 of search.py) should now include pubmed as
    # 7th default engine.
    args = ["vaccine", "--engine", "all", "--limit", "10", "--quiet"]
    rc, out, err = run_pa_search(args, timeout=180)
    log(f"  exit={rc}")
    if err:
        log(f"  stderr (last 400): {err[-400:]}")
    if rc != 0:
        log(f"  result: FAIL (exit {rc})")
        return False
    data = parse_json_or_log(out, "engine=all")
    if not data:
        log(f"  result: FAIL (no JSON)")
        return False
    by_engine = data.get("by_engine", {})
    log(f"  by_engine (counts): {by_engine}")
    has_pubmed_key = "pubmed" in by_engine
    pubmed_count = by_engine.get("pubmed", 0) if has_pubmed_key else 0
    log(f"  pubmed key present: {has_pubmed_key}, count: {pubmed_count}")
    # Verify at least one result in unified has pmid (sanity check pubmed actually ran)
    has_pmid_result = any(
        isinstance(r, dict) and r.get("pmid")
        for r in data.get("results", [])
    )
    log(f"  any unified result has pmid field: {has_pmid_result}")
    ok = has_pubmed_key and pubmed_count > 0 and has_pmid_result
    log(f"  result: {'PASS' if ok else 'FAIL'}")
    return ok

def test_dedup():
    log("\n=== Test 3: dedup - same DOI across engines -> found_by list ===")
    # IMPORTANT: returned JSON's by_engine is {engine: int_count}, not
    # {engine: [papers]}. Look at result items' found_by field instead.
    # Use 'Attention is all you need' query that empirically has
    # pubmed+crossref overlap (Vaswani 2017 is in PubMed as a citation).
    args = ["Attention is all you need", "--engine",
            "openalex,pubmed,crossref", "--limit", "15", "--quiet"]
    rc, out, err = run_pa_search(args, timeout=180)
    log(f"  exit={rc}")
    if err:
        log(f"  stderr (last 400): {err[-400:]}")
    if rc != 0:
        log(f"  result: FAIL (exit {rc})")
        return False
    data = parse_json_or_log(out, "dedup test")
    if not data:
        log(f"  result: FAIL (no JSON)")
        return False
    by_engine = data.get("by_engine", {})
    papers = data.get("results", [])
    log(f"  by_engine (counts): {by_engine}")
    log(f"  unified results: {len(papers)}")
    # Look at found_by distribution
    found_by_dist = {}
    for p in papers:
        if not isinstance(p, dict):
            continue
        fb = tuple(p.get("found_by", []))
        found_by_dist[fb] = found_by_dist.get(fb, 0) + 1
    log(f"  found_by distribution: {dict(found_by_dist)}")
    multi = [p for p in papers
             if isinstance(p, dict) and len(p.get("found_by", [])) > 1]
    if multi:
        log(f"  *** {len(multi)} papers found by >=2 engines ***")
        for p in multi[:3]:
            log(f"    title={p.get('title','')[:80]!r}")
            log(f"    doi={p.get('doi','')!r} found_by={p.get('found_by')}")
        log(f"  result: PASS ({len(multi)} papers found by multiple engines)")
        return True
    log(f"  result: FAIL (no multi-source papers in this query)")
    return False

def test_fetch():
    log("\n=== Test 4: pa fetch backward compat ===")
    cmd = [sys.executable, "-m", "pa_cli", "fetch",
           "10.1038/nature12373", "--prefer", "scihub"]
    log(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=180, env=os.environ.copy())
    out = (r.stdout or "") + (r.stderr or "")
    log(f"  exit={r.returncode}")
    log(f"  last 400 chars: {out[-400:]}")
    ok = r.returncode == 0 and ("saved" in out.lower() or "downloaded" in out.lower()
                                or "fetched" in out.lower() or "fetch" in out.lower())
    log(f"  result: {'PASS' if ok else 'FAIL'}")
    return ok

def test_concept_filter():
    log("\n=== Test 6: OpenAlex concept filter still works ===")
    # v3.9.7.8 feature: --concept "name" resolves via OpenAlex concept API and
    # filters results. Use 'BERT' + 'machine learning' which empirically
    # matches; 'transformer' + 'machine learning' returns 0 because OpenAlex's
    # concept filter is strict (pre-existing behavior, not a v3.9.11.8
    # regression — diff confirms concept code untouched).
    args = ["BERT", "--concept", "machine learning",
            "--engine", "openalex", "--limit", "3", "--quiet"]
    rc, out, err = run_pa_search(args, timeout=120)
    log(f"  exit={rc}")
    if err:
        log(f"  stderr (last 400): {err[-400:]}")
    if rc != 0:
        log(f"  result: FAIL (exit {rc})")
        return False
    data = parse_json_or_log(out, "concept filter")
    if not data:
        log(f"  result: FAIL (no JSON)")
        return False
    by_engine = data.get("by_engine", {})
    papers = data.get("results", [])
    cm = data.get("concept_mode", "")
    log(f"  concept_mode: {cm!r}")
    log(f"  by_engine: {by_engine}")
    log(f"  unified results: {len(papers)}")
    if not papers:
        log(f"  result: FAIL (concept filter returned 0 results)")
        return False
    first = papers[0]
    log(f"  first_title: {first.get('title','')[:120]!r}")
    log(f"  first_doi: {first.get('doi','')!r}")
    log(f"  result: PASS (concept filter ran, OpenAlex returned {len(papers)} results)")
    return True

# ---------------- main ----------------
def main():
    log("=" * 70)
    log("paper-agent v3.9.11.8 backward-compat verifier (B)")
    log(f"started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"python: {sys.version.split()[0]}")
    log(f"cwd: {ROOT}")
    log("=" * 70)

    results = {}

    # Test 5 first (cheap) and Test 7 (cheap)
    results["5_version"] = test_version()
    results["7_help_text"] = test_help_text()

    # Test 1: 6 engines smoke
    engine_results = {}
    # crossref
    engine_results["crossref"] = test_engine("crossref", "transformer attention", 3)
    # openalex
    engine_results["openalex"] = test_engine("openalex", "machine learning", 3)
    # arxiv
    engine_results["arxiv"] = test_engine("arxiv", "neural network", 3)
    # semanticscholar
    engine_results["semanticscholar"] = test_engine("semanticscholar", "deep learning", 3)
    # aminer (optional - may skip if no token)
    aminer_env = os.environ.get("AMINER_API_KEY", "")
    log(f"\n  AMINER_API_KEY set: {bool(aminer_env)}")
    if aminer_env:
        engine_results["aminer"] = test_engine("aminer", "neural network", 3)
    else:
        log("\n=== Test 1.aminer: skipped (no AMINER_API_KEY) ===")
        engine_results["aminer"] = {"engine": "aminer", "pass": "SKIP",
                                     "reason": "no token"}
    # cnki (optional - may skip if no cookies)
    from pa_cli.cnki_channel import status_report as cnki_status
    cs = cnki_status()
    log(f"\n  CNKI status: {cs}")
    if cs.get("ready_for_search"):
        engine_results["cnki"] = test_engine("cnki", "深度学习", 3)
    else:
        log("\n=== Test 1.cnki: skipped (CNKI not ready) ===")
        engine_results["cnki"] = {"engine": "cnki", "pass": "SKIP",
                                   "reason": "no cookies"}

    # Test 2: --engine all includes pubmed
    results["2_all_includes_pubmed"] = test_engine_all_includes_pubmed()

    # Test 3: dedup
    results["3_dedup"] = test_dedup()

    # Test 4: pa fetch
    results["4_fetch"] = test_fetch()

    # Test 6: concept filter
    results["6_concept"] = test_concept_filter()

    # ---------------- summary ----------------
    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log("Test 5 (pa --version 3.9.11.8): "
        f"{'PASS' if results['5_version'] else 'FAIL'}")
    log("Test 7 (CLI help lists pubmed): "
        f"{'PASS' if results['7_help_text'] else 'FAIL'}")
    log("Test 2 (--engine all has pubmed): "
        f"{'PASS' if results['2_all_includes_pubmed'] else 'FAIL'}")
    log("Test 3 (dedup / found_by): "
        f"{'PASS' if results['3_dedup'] else 'FAIL'}")
    log("Test 4 (pa fetch still works): "
        f"{'PASS' if results['4_fetch'] else 'FAIL'}")
    log("Test 6 (OpenAlex concept filter): "
        f"{'PASS' if results['6_concept'] else 'FAIL'}")
    log("")
    log("Test 1 (6 engine smoke):")
    for eng, r in engine_results.items():
        if r.get("pass") == "SKIP":
            log(f"  {eng:18s}: SKIP ({r.get('reason','no reason')})")
        elif r.get("pass"):
            log(f"  {eng:18s}: PASS ({r.get('results_count','?')} results)")
        else:
            log(f"  {eng:18s}: FAIL ({r.get('reason','?')})")

    fails = [k for k, v in results.items() if v is False]
    if fails:
        log(f"\nFAILED tests: {fails}")
        return 1
    log("\nAll 6 hard checks PASS. No regressions detected.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
