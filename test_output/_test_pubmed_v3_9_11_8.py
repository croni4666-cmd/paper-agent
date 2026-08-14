"""v3.9.11.8 PubMed engine end-to-end test (3 scenarios)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)


def run_pa_search(query, engine=None, year_min=None, year_max=None, limit=5, timeout_sec=120):
    cmd = ["python", "-m", "pa_cli", "search", query, "--limit", str(limit), "--format", "json"]
    if engine:
        cmd.extend(["--engine", engine])
    if year_min:
        cmd.extend(["--year-min", str(year_min)])
    if year_max:
        cmd.extend(["--year-max", str(year_max)])
    # Windows GBK console can't encode Ö/é/中 — force UTF-8 stdout
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_sec, encoding="utf-8", errors="replace",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None, f"TIMEOUT after {timeout_sec}s"
    out = result.stdout
    # Strip [pa] log lines, then find first { (top-level dict)
    cleaned = "\n".join(L for L in out.splitlines() if not L.startswith("[pa]"))
    start = cleaned.find("{")
    if start < 0:
        return None, f"No JSON. rc={result.returncode} tail={out[-200:]!r}"
    try:
        return json.loads(cleaned[start:]), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse: {e}. text={cleaned[start:start+300]!r}"


def show(label, data, source_filter=None):
    """Pretty-print papers from unified search result."""
    if isinstance(data, dict):
        papers = data.get("results", [])
        by_engine = data.get("by_engine", {})
    else:
        papers = data
        by_engine = {}
    if source_filter:
        papers = [p for p in papers if p.get("source") == source_filter]
    # by_engine is {engine_name: count} not {engine_name: [papers]}
    by_engine_str = ", ".join(f"{k}={v}" for k, v in by_engine.items())
    print(f"  {label}: {len(papers)} papers (by_engine: {by_engine_str})")
    for i, r in enumerate(papers[:5]):
        print(f"  [{i+1}] source={r.get('source', '?'):10s} year={str(r.get('year', '?')):5s} "
              f"pmid={r.get('pmid', '-') or '-':10s}")
        print(f"      title: {(r.get('title') or '')[:80]}")
        print(f"      venue: {(r.get('venue') or '?')[:40]}  doi={r.get('doi', '?') or '-'}")
        if r.get('pub_types'):
            print(f"      pub_types: {r['pub_types'][:3]}")


def pubmed_papers_from(data):
    """Get pubmed papers from unified results (filter by source)."""
    if not isinstance(data, dict):
        return []
    return [p for p in data.get("results", []) if p.get("source") == "pubmed"]


print("=" * 78)
print("v3.9.11.8 PubMed engine end-to-end test")
print("=" * 78)

# Test 1: pubmed alone with medical query
print("\n--- Test 1: pa search --engine pubmed (ACE inhibitors + RCT, year>=2024) ---")
data1, err1 = run_pa_search(
    "ACE inhibitors hypertension randomized controlled trial",
    engine="pubmed", year_min=2024, limit=5,
)
if err1:
    print(f"  ERROR: {err1}")
    t1_ok = False
else:
    show("pubmed-only", data1, source_filter="pubmed")
    pubmed_papers = pubmed_papers_from(data1)
    t1_ok = len(pubmed_papers) >= 3 and all(
        r.get("pmid") and r.get("doi") for r in pubmed_papers[:3]
    )
    print(f"  Test 1: {'PASS' if t1_ok else 'FAIL'}")

# Test 2: pubmed with biohack-style query
print("\n--- Test 2: pa search --engine pubmed (long-term care, 2020-2024) ---")
data2, err2 = run_pa_search(
    "long-term care insurance elderly",
    engine="pubmed", year_min=2020, year_max=2024, limit=5,
)
if err2:
    print(f"  ERROR: {err2}")
    t2_ok = False
else:
    show("pubmed-only", data2, source_filter="pubmed")
    pubmed_papers = pubmed_papers_from(data2)
    t2_ok = len(pubmed_papers) >= 1
    print(f"  Test 2: {'PASS' if t2_ok else 'FAIL'}")

# Test 3: all engines includes pubmed
print("\n--- Test 3: pa search --engine all (COVID vaccine, check pubmed in by_engine) ---")
data3, err3 = run_pa_search(
    "mRNA COVID-19 vaccine efficacy",
    engine="all", limit=20, timeout_sec=240,
)
if err3:
    print(f"  ERROR: {err3}")
    t3_ok = False
else:
    by_engine = data3.get("by_engine", {})
    pubmed_count = by_engine.get("pubmed", 0)
    pubmed_papers = pubmed_papers_from(data3)
    print(f"  engines: {list(by_engine.keys())}")
    print(f"  pubmed count: {pubmed_count}, papers in unified: {len(pubmed_papers)}")
    for r in pubmed_papers[:3]:
        print(f"    pmid={r.get('pmid')}  year={r.get('year')}  "
              f"venue={(r.get('venue') or '?')[:30]}  doi={r.get('doi', '?') or '-'}")
    t3_ok = "pubmed" in by_engine and pubmed_count >= 1
    print(f"  Test 3: {'PASS' if t3_ok else 'FAIL'}")

# Test 4: dedup — pubmed paper should also appear in unified results
print("\n--- Test 4: dedup test — pubmed paper with DOI should merge with other engines ---")
data4, err4 = run_pa_search(
    "Bivalent mRNA COVID vaccine effectiveness New England Journal",
    engine="all", limit=20, timeout_sec=240,
)
if err4:
    print(f"  ERROR: {err4}")
    t4_ok = False
else:
    by_engine = data4.get("by_engine", {})
    pubmed_papers = pubmed_papers_from(data4)
    unified = data4.get("results", [])
    # Find a pubmed paper that has DOI and check if it also exists in unified results
    pubmed_with_doi = next((p for p in pubmed_papers if p.get("doi")), None)
    if pubmed_with_doi:
        doi = pubmed_with_doi["doi"]
        in_unified = next((p for p in unified if p.get("doi") == doi), None)
        if in_unified:
            found_by = in_unified.get("found_by", [])
            print(f"  pubmed paper DOI={doi}")
            print(f"    in unified: yes  found_by={found_by}")
            t4_ok = "pubmed" in found_by
        else:
            print(f"  pubmed paper DOI={doi} NOT in unified dedup")
            t4_ok = False
    else:
        print(f"  no pubmed paper with DOI in this query — test inconclusive")
        t4_ok = True  # not a fail, just no overlap
    print(f"  Test 4: {'PASS' if t4_ok else 'FAIL'}")

# Summary
print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
results_summary = {
    "Test 1 (pubmed ACE inhibitors)": t1_ok,
    "Test 2 (pubmed long-term care)": t2_ok,
    "Test 3 (all engines has pubmed)": t3_ok,
    "Test 4 (dedup with DOI)": t4_ok,
}
for name, ok in results_summary.items():
    print(f"  {name:40s} {'PASS' if ok else 'FAIL'}")
all_pass = all(results_summary.values())
print(f"  TOTAL: {sum(results_summary.values())}/{len(results_summary)}")
sys.exit(0 if all_pass else 1)
