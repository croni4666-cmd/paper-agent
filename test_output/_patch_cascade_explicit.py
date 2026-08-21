"""Patch fetch.py: when explicit prefer fails, return that error (not E_ALL_MIRRORS).

5 new channels added in v3.9.22 (s2/biorxiv/core/osf/chemrxiv) need explicit
prefer handling so users get the actual error message.
"""
from pathlib import Path

p = Path(r"G:\minimax - workspace\Paper agent\pa_cli\fetch.py")
src = p.read_text(encoding="utf-8")

# Find each "if prefer in (...): ... if " error in r: pass" block and
# add "if prefer == X: return r" after the except

# S2
old_s2 = '''        # 5b. Semantic Scholar openAccessPdf (v3.9.22+, 2026-08-21)
        # Cross-domain, fast, ~30% hit rate. Sits between Unpaywall and
        # Sci-Hub because it's free + legal + S2-API-key optional.
        if prefer in ("s2", "auto"):
            try:
                from .s2_channel import fetch_s2_doi
                r = fetch_s2_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass'''
new_s2 = '''        # 5b. Semantic Scholar openAccessPdf (v3.9.22+, 2026-08-21)
        # Cross-domain, fast, ~30% hit rate. Sits between Unpaywall and
        # Sci-Hub because it's free + legal + S2-API-key optional.
        if prefer in ("s2", "auto"):
            try:
                from .s2_channel import fetch_s2_doi
                r = fetch_s2_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass
            if prefer == "s2":
                return r  # v3.9.22: explicit prefer, return s2's actual error'''
assert old_s2 in src
src = src.replace(old_s2, new_s2, 1)

# bioRxiv
old_biorxiv = '''        # 5c. bioRxiv / medRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.1101/* DOIs. High-success preprint server.
        if doi.lower().startswith("10.1101/") and prefer in ("biorxiv", "auto"):
            try:
                from .biorxiv_channel import fetch_biorxiv_doi
                r = fetch_biorxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass'''
new_biorxiv = '''        # 5c. bioRxiv / medRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.1101/* DOIs. High-success preprint server.
        if doi.lower().startswith("10.1101/") and prefer in ("biorxiv", "auto"):
            try:
                from .biorxiv_channel import fetch_biorxiv_doi
                r = fetch_biorxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass
            if prefer == "biorxiv":
                return r  # v3.9.22: explicit prefer'''
assert old_biorxiv in src
src = src.replace(old_biorxiv, new_biorxiv, 1)

# CORE
old_core = '''        # 5d. CORE re-add (v3.9.22+, 2026-08-21)
        # Re-added because OpenAlex only has metadata, CORE has 36M+ full text.
        # Requires $CORE_API_KEY (free at core.ac.uk/services/api).
        if prefer in ("core", "auto"):
            try:
                from .core_channel import fetch_core_doi
                r = fetch_core_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass'''
new_core = '''        # 5d. CORE re-add (v3.9.22+, 2026-08-21)
        # Re-added because OpenAlex only has metadata, CORE has 36M+ full text.
        # Requires $CORE_API_KEY (free at core.ac.uk/services/api).
        if prefer in ("core", "auto"):
            try:
                from .core_channel import fetch_core_doi
                r = fetch_core_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass
            if prefer == "core":
                return r  # v3.9.22: explicit prefer'''
assert old_core in src
src = src.replace(old_core, new_core, 1)

# OSF
old_osf = '''        # 5e. OSF Preprints (v3.9.22+, 2026-08-21)
        # Only triggers for 10.31219/osf.io/* or 10.31234/osf.io/* DOIs.
        if (doi.lower().startswith("10.31219/osf.io/") or
            doi.lower().startswith("10.31234/osf.io/")) and prefer in ("osf", "auto"):
            try:
                from .osf_channel import fetch_osf_doi
                r = fetch_osf_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass'''
new_osf = '''        # 5e. OSF Preprints (v3.9.22+, 2026-08-21)
        # Only triggers for 10.31219/osf.io/* or 10.31234/osf.io/* DOIs.
        if (doi.lower().startswith("10.31219/osf.io/") or
            doi.lower().startswith("10.31234/osf.io/")) and prefer in ("osf", "auto"):
            try:
                from .osf_channel import fetch_osf_doi
                r = fetch_osf_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass
            if prefer == "osf":
                return r  # v3.9.22: explicit prefer'''
assert old_osf in src
src = src.replace(old_osf, new_osf, 1)

# ChemRxiv
old_chemrxiv = '''        # 5f. ChemRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.26434/chemrxiv-* DOIs.
        if doi.lower().startswith("10.26434/chemrxiv-") and prefer in ("chemrxiv", "auto"):
            try:
                from .chemrxiv_channel import fetch_chemrxiv_doi
                r = fetch_chemrxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass'''
new_chemrxiv = '''        # 5f. ChemRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.26434/chemrxiv-* DOIs.
        if doi.lower().startswith("10.26434/chemrxiv-") and prefer in ("chemrxiv", "auto"):
            try:
                from .chemrxiv_channel import fetch_chemrxiv_doi
                r = fetch_chemrxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass
            if prefer == "chemrxiv":
                return r  # v3.9.22: explicit prefer'''
assert old_chemrxiv in src
src = src.replace(old_chemrxiv, new_chemrxiv, 1)

p.write_text(src, encoding="utf-8", newline="\n")
print(f"[OK] fetch.py updated with 5 explicit-prefer returns, new size: {len(src):,} bytes")
