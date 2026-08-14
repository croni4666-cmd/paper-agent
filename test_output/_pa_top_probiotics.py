# -*- coding: utf-8 -*-
"""Show full abstracts of the 7 top probiotics + Hashimoto papers"""
import os
import json

out_dir = r"G:\minimax - workspace\Paper agent\test_output"

# Search all results files, dedup
search_files = [
    "probiotics_Q1_probiotics_Hashimoto.json",
    "probiotics_Q2_gut_microbiome_thyroid.json",
    "probiotics_Q3_specific_strains_antibodies.json",
    "probiotics_Q4_probiotic_RCT_TPOAb.json",
    "probiotics_Q5_specific_strains_hashimoto.json",
    "probiotics_Q6_Hashimoto_specific_probiotic.json",
    "probiotics_Q7_synbiotic_Hashimoto.json",
]

all_results = []
for sf in search_files:
    f = os.path.join(out_dir, sf)
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        results = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            all_results.extend(results)

# Dedup by DOI
seen_doi = set()
deduped = []
for r in all_results:
    doi = r.get("doi") or ""
    if doi and doi not in seen_doi:
        seen_doi.add(doi)
        deduped.append(r)
    elif not doi:
        deduped.append(r)

# Target DOIs (most relevant for Friend A case)
TARGET_DOIS = [
    "10.3389/fimmu.2026.1905146",  # Lactobacillus in AITD 2026
    "10.3389/fmicb.2025.1661211",  # Gut microbiota hypothyroidism 2025
    "10.1007/s10238-024-01304-4",  # Intestinal microbiota gut-thyroid 2024
    "10.3390/ijms252010918",        # Unveiling Role of Gut Microbiota in AITD 2024
    "10.3389/fcimb.2024.1465928",   # Recent advances gut microbiota thyroid 2024
    "10.3390/nu12061769",           # Thyroid-Gut-Axis 2020
    "10.3389/fimmu.2021.579140",     # Cayres 2021 (already in chain)
]

print("=" * 80)
print("## TOP 7 PROBIOTICS + HASHIMOTO PAPERS (ABSTRACT EXTRACT)")
print("=" * 80)

for doi in TARGET_DOIS:
    paper = next((r for r in deduped if r.get("doi") == doi), None)
    if not paper:
        print(f"\n[NOT FOUND: {doi}]")
        continue
    print(f"\n### {paper.get('title', '?')[:100]}")
    print(f"  **Year**: {paper.get('year', '?')}, **Cited**: {paper.get('cited_by_count', '?')}")
    print(f"  **DOI**: {doi}")
    venue = paper.get("primary_location", {}).get("source", {}).get("display_name") or paper.get("venue", "")
    if venue:
        print(f"  **Venue**: {venue}")
    auths = paper.get("authorships", [])
    if auths:
        first = auths[0]
        name = first.get("author", {}).get("display_name", "?") if isinstance(first, dict) else "?"
        n_auths = len(auths)
        print(f"  **First author**: {name} (n={n_auths})")
    abstract = (paper.get("abstract", "") or "").replace("\n", " ")
    if abstract:
        # Clean OpenAlex inverted index
        import re
        clean = re.sub(r"\s+", " ", abstract)[:1200]
        print(f"  **Abstract**: {clean}...")
    print("  " + "-" * 60)

# Save target list
with open(os.path.join(out_dir, "probiotics_target7.json"), "w", encoding="utf-8") as f:
    target_papers = [r for r in deduped if r.get("doi") in TARGET_DOIS]
    json.dump(target_papers, f, ensure_ascii=False, indent=2)
print(f"\n\nTarget 7 saved to probiotics_target7.json")
