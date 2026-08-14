# -*- coding: utf-8 -*-
"""Targeted search for Hashimoto + probiotic specific RCTs/reviews"""
import os
import subprocess
import json

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

CWD = r"G:\minimax - workspace\Paper agent"

QUERIES = [
    {
        "label": "Q6_Hashimoto_specific_probiotic",
        "query": "Hashimoto's thyroiditis probiotic supplementation antibodies levothyroxine",
        "engine": "openalex",
        "year_min": 2015,
    },
    {
        "label": "Q7_synbiotic_Hashimoto",
        "query": "synbiotic selenium Hashimoto thyroiditis intervention",
        "engine": "openalex",
        "year_min": 2015,
    },
]

out_dir = r"G:\minimax - workspace\Paper agent\test_output"

for q in QUERIES:
    print(f"\n{'=' * 70}")
    print(f"## {q['label']}")
    print(f"## query: {q['query']}")
    print('=' * 70)

    out_file = os.path.join(out_dir, f"probiotics_{q['label']}.json")
    cmd = [
        "python", "-m", "pa_cli", "search",
        q["query"],
        "--engine", q["engine"],
        "--year-min", str(q["year_min"]),
        "--limit", "15",
        "--format", "json",
        "--output", out_file,
        "--sort-by", "cite",
        "--quality-mode", "filter",
    ]
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=90)
    if r.returncode != 0:
        print(f"FAILED: {r.stderr[:500]}")
    else:
        if os.path.exists(out_file):
            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            results_list = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results_list, list):
                print(f"  Found: {len(results_list)} results")
                for i, item in enumerate(results_list[:10], 1):
                    title = item.get("title", "")[:90]
                    year = item.get("year", item.get("publication_year", ""))
                    cites = item.get("cited_by_count", item.get("citations", "?"))
                    doi = item.get("doi", "")
                    abstract = (item.get("abstract", "") or "")[:300].replace("\n", " ")
                    print(f"  [{i}] {title}  ({year}, cited: {cites})")
                    print(f"      DOI: {doi}")
                    if abstract:
                        print(f"      Abstract: {abstract}...")
                    print()
