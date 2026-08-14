# -*- coding: utf-8 -*-
"""Show abstracts of key papers found"""
import os
import json

out_dir = r"G:\minimax - workspace\Paper agent\test_output"

KEY_DOI_FRAGMENTS = [
    ("Lactobacillus in AITD 2026", "10.3389/fimmu.2026.1905146"),
    ("Gut microbiota hypothyroidism 2025", "10.3389/fmicb.2025.1661211"),
    ("Intestinal microbiota gut-thyroid 2024", "10.1007/s10238-024-01304-4"),
    ("Thyroid-Gut-Axis 2020 Nutrients", "10.3390/nu12061769"),
    ("Significance Gut Microbiota Graves 2024", "10.2147/ijgm.s467888"),
    ("Microbiota Endocrine Diseases 2024", "10.3390/biomedicines12010221"),
    ("Intestinal Dysbiosis AID 2020", "10.3389/fimmu.2020.573079"),
    ("Hashimoto oxidative stress interplay 2023", "10.3389/fimmu.2023.1211231"),
]

# Load all search results
search_files = [
    "probiotics_Q1_probiotics_Hashimoto.json",
    "probiotics_Q2_gut_microbiome_thyroid.json",
    "probiotics_Q3_specific_strains_antibodies.json",
    "probiotics_Q4_probiotic_RCT_TPOAb.json",
    "probiotics_Q5_specific_strains_hashimoto.json",
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
        deduped.append(r)  # keep ones without DOI

# Sort by cited_by_count descending
deduped.sort(key=lambda x: -(x.get("cited_by_count", 0) or 0))

# Show top 12 abstracts
print(f"Total unique: {len(deduped)}")
print("=" * 80)
for i, r in enumerate(deduped[:12], 1):
    print(f"\n[{i}] {r.get('title', '')[:90]}")
    print(f"    Year: {r.get('year')}, Cited: {r.get('cited_by_count', '?')}")
    print(f"    DOI: {r.get('doi', '-')}")
    auths = r.get("authorships", r.get("authors", []))
    if isinstance(auths, list) and auths:
        first_auth = auths[0]
        if isinstance(first_auth, dict):
            name = first_auth.get("author", {}).get("display_name", first_auth.get("name", "?"))
        else:
            name = str(first_auth)
        print(f"    First author: {name}")
    venue = r.get("primary_location", {}).get("source", {}).get("display_name") or r.get("venue", "")
    if venue:
        print(f"    Venue: {venue[:60]}")
    abstract = r.get("abstract", "")
    if abstract:
        # Clean up abstract (often inverted index from openalex)
        abstract_clean = abstract.replace("[", "").replace("]", "").replace(" ,", ",")[:600]
        print(f"    Abstract: {abstract_clean}")

# Save sorted top results
with open(os.path.join(out_dir, "probiotics_top12.json"), "w", encoding="utf-8") as f:
    json.dump(deduped[:12], f, ensure_ascii=False, indent=2)
print(f"\n\nTop 12 saved to probiotics_top12.json")
