# -*- coding: utf-8 -*-
"""Search for specific RCTs of probiotics on Hashimoto's antibodies"""
import os
import subprocess
import json

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

CWD = r"G:\minimax - workspace\Paper agent"

QUERIES = [
    {
        "label": "Q4_probiotic_RCT_TPOAb",
        "query": "probiotic supplementation TPOAb TGAb Hashimoto clinical trial",
        "engine": "openalex",
        "year_min": 2018,
    },
    {
        "label": "Q5_specific_strains_hashimoto",
        "query": "Lactobacillus reuteri Bifidobacterium animalis Hashimoto thyroiditis",
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
                for i, item in enumerate(results_list[:8], 1):
                    title = item.get("title", "")[:80]
                    year = item.get("year", item.get("publication_year", ""))
                    cites = item.get("cited_by_count", item.get("citations", "?"))
                    doi = item.get("doi", item.get("externalIds", {}).get("DOI", ""))
                    print(f"  [{i}] {title}  ({year}, cited: {cites})")
                    if doi:
                        print(f"      DOI: {doi}")
