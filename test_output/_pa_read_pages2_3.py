# -*- coding: utf-8 -*-
"""Read pages 2-3 for clinical findings from each PDF"""
import os
from pypdf import PdfReader

CWD = r"G:\minimax - workspace\Paper agent"

PDFs = [
    ("10_3389_fimmu_2026_1905146.pdf", "Lactobacillus_AITD_2026"),
    ("10_3389_fmicb_2025_1661211.pdf", "Gut_microbiota_hypothyroidism_2025"),
    ("10_3389_fcimb_2024_1465928.pdf", "Gut_microbiota_thyroid_2024_fcimb"),
]

for fn, label in PDFs:
    path = os.path.join(CWD, fn)
    if not os.path.exists(path):
        continue
    r = PdfReader(path)
    print(f"\n{'=' * 80}")
    print(f"## {label} (n_pages={len(r.pages)})")
    print('=' * 80)
    # Look for key terms: "probiotic", "TPOAb", "Lactobacillus", "strain", "intervention"
    full_text = ""
    for i, p in enumerate(r.pages):
        try:
            full_text += p.extract_text() + "\n"
        except:
            pass

    # Search for key terms
    import re
    # Find sentences with key terms
    sentences = re.split(r'(?<=[.!?])\s+', full_text.replace("\n", " "))
    for keyword in ["TPOAb", "Lactobacillus", "Bifidobacterium", "probiotic", "strain", "RCT", "randomized", "intervention", "antibod", "selenium"]:
        hits = [s for s in sentences if keyword.lower() in s.lower() and 50 < len(s) < 400]
        for h in hits[:2]:
            print(f"  [{keyword}] {h[:400]}")
    print()
