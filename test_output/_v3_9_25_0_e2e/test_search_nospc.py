"""e2e test: pa search with AMiner for Wilson Disease.

Bypasses click's argv splitting by using Python directly.
"""
import json
import sys
from pathlib import Path

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
sys.path.insert(0, str(PA_ROOT))

from pa_cli.search import run_search


def show_results(label, results, top_n=5):
    papers = results.get("results", [])
    by_engine = results.get("by_engine", {})
    print(f"\n=== {label} ===")
    print(f"by_engine: {by_engine}")
    print(f"total dedup: {len(papers)}")
    if not papers:
        print("(no results)")
        return
    print(f"top {min(top_n, len(papers))} by relevance/year:")
    for i, p in enumerate(papers[:top_n], 1):
        rel = p.get("title_relevance", "n/a")
        match = p.get("match_type", "n/a")
        year = p.get("year", "?")
        title = p.get("title", "?")[:70]
        print(f"  {i}. rel={rel} mt={match} yr={year} | {title}")


# Test 1: AMiner basic (legacy, free)
results = run_search("Wilson Disease", limit=20, engine="aminer", aminer_mode="basic", sort_by="relevance")
show_results("AMiner basic mode (free)", results)

# Test 2: AMiner auto (pro for multi-word, costs ¥0.01)
# Skip if no token
import os
if os.environ.get("AMINER_API_KEY"):
    results = run_search("Wilson Disease", limit=20, engine="aminer", aminer_mode="auto", sort_by="relevance")
    show_results("AMiner auto mode (pro)", results)
else:
    print("\n(skipped AMiner auto mode: AMINER_API_KEY not set)")
    print("To test: set $env:AMINER_API_KEY = '<your JWT token>'")

# Test 3: Single-word (should use basic even in auto mode)
results = run_search("Wilson's", limit=10, engine="aminer", aminer_mode="auto", sort_by="relevance")
show_results("AMiner auto mode (single-word 'Wilson's')", results)
