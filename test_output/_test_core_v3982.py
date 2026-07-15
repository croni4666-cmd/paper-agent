"""Smoke test for v3.9.8.2 CORE fix — no-key + key modes."""
import os
import sys
sys.path.insert(0, "G:/minimax - workspace/Paper agent")

from pa_cli.search import search_core

print("=== search_core() smoke test ===")

# Mode 1: no key
if "CORE_API_KEY" in os.environ:
    del os.environ["CORE_API_KEY"]
r = search_core("long-term care insurance", year_min=2022, year_max=2024, limit=3)
print(f"no-key mode: n={len(r)}")
if r:
    print(f"  first: {r[0]['title'][:60]} | year={r[0]['year']} | doi={r[0]['doi']}")

# Mode 2: with key (query param style)
os.environ["CORE_API_KEY"] = "<REDACTED-CORE-KEY>"
r2 = search_core("long-term care insurance", year_min=2022, year_max=2024, limit=3)
print(f"with-key mode: n={len(r2)}")
if r2:
    print(f"  first: {r2[0]['title'][:60]} | year={r2[0]['year']} | doi={r2[0]['doi']}")

# Mode 3: explicit --engine core (skip the unified dedup)
from pa_cli.search import run_search
r3 = run_search("long-term care insurance", year_min=2022, year_max=2024, limit=3, engine="core")
print(f"explicit --engine core: n={len(r3['results'])} | by_engine={list(r3['by_engine'].keys())}")
