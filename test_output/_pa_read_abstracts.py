# -*- coding: utf-8 -*-
"""Read abstracts from the 3 successfully downloaded PDFs"""
import os
import subprocess
import sys

CWD = r"G:\minimax - workspace\Paper agent"

# Try pypdf
try:
    from pypdf import PdfReader
    has_pypdf = True
except ImportError:
    has_pypdf = False

PDFs = [
    ("10.3389/fimmu.2026.1905146", "Lactobacillus_AITD_2026"),
    ("10.3389/fmicb.2025.1661211", "Gut_microbiota_hypothyroidism_2025"),
    ("10.3389/fcimb.2024.1465928", "Gut_microbiota_thyroid_2024_fcimb"),
]

# Also look for renamed PDF in cwd
print("Files in CWD matching pattern:")
for f in os.listdir(CWD):
    if "10_3389" in f and f.endswith(".pdf"):
        full = os.path.join(CWD, f)
        size = os.path.getsize(full)
        print(f"  {f}  ({size} bytes)")

print("\n" + "=" * 80)
print("## ABSTRACTS")
print("=" * 80)

# Find PDFs
for doi, label in PDFs:
    doi_filename = doi.replace("/", "_").replace(".", "_") + ".pdf"
    # Try common patterns
    candidates = [
        os.path.join(CWD, doi_filename),
        os.path.join(CWD, doi.replace("/", "_") + ".pdf"),
    ]
    for c in candidates:
        if os.path.exists(c):
            print(f"\n### [{label}] {os.path.basename(c)}")
            if has_pypdf:
                try:
                    r = PdfReader(c)
                    # Read first 2 pages
                    for i in range(min(2, len(r.pages))):
                        text = r.pages[i].extract_text()
                        if text:
                            # Look for Abstract section
                            if "Abstract" in text:
                                idx = text.find("Abstract")
                                print(f"  Page {i+1} Abstract+: {text[idx:idx+1200].replace(chr(10), ' ')}")
                                break
                            else:
                                print(f"  Page {i+1} (first 800 chars): {text[:800].replace(chr(10), ' ')}")
                except Exception as e:
                    print(f"  Error: {e}")
            else:
                print("  pypdf not available")
            break
    else:
        print(f"\n### [{label}] PDF not found in CWD")
