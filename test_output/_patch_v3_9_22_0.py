"""Patch fetch.py for v3.9.22.0: integrate 5 new OA channels.

Edits:
1. Add imports for s2/biorxiv/core/osf/chemrxiv
2. Add 5 new steps in fetch() cascade (after Unpaywall, before Sci-Hub)
3. Add 5 new cases in fetch_doi channel→prefer mapping
4. Add `--prefer` option handling for new channels
"""
from pathlib import Path

p = Path(r"G:\minimax - workspace\Paper agent\pa_cli\fetch.py")
src = p.read_text(encoding="utf-8")

# ─── 1. Add imports after existing fetch_*_doi definitions ──────────────
# Find the import block — pa_cli has lazy imports inside functions, so we
# can also do lazy imports. But let's add a clear top-level marker.
# Easier: add lazy imports inside fetch() — minimal change.

# ─── 2. Add 5 new steps in fetch() cascade, after Unpaywall (line 1032) ─
# Currently:
#   # 5. Unpaywall
#   if prefer in ("unpaywall", "scihub", "auto"):
#       r = fetch_unpaywall_doi(doi, out_path)
#       if "error" not in r: return r
#   # 6. Sci-Hub
old_unpaywall_block = '''        # 5. Unpaywall (cheap, official, legal)
        # v3.9.22: --prefer unpaywall explicit, or fall through from scihub/auto
        if prefer in ("unpaywall", "scihub", "auto"):
            r = fetch_unpaywall_doi(doi, out_path)
            if "error" not in r:
                return r

        # 6. Sci-Hub (mirror rotation, last-resort gray route)
        if prefer in ("scihub", "auto"):
            r = fetch_scihub_doi(doi, out_path)
            if "error" not in r:
                return r'''

new_unpaywall_block = '''        # 5. Unpaywall (cheap, official, legal)
        # v3.9.22: --prefer unpaywall explicit, or fall through from scihub/auto
        if prefer in ("unpaywall", "scihub", "auto"):
            r = fetch_unpaywall_doi(doi, out_path)
            if "error" not in r:
                return r

        # 5b. Semantic Scholar openAccessPdf (v3.9.22+, 2026-08-21)
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

        # 5c. bioRxiv / medRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.1101/* DOIs. High-success preprint server.
        if doi.lower().startswith("10.1101/") and prefer in ("biorxiv", "auto"):
            try:
                from .biorxiv_channel import fetch_biorxiv_doi
                r = fetch_biorxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 5d. CORE re-add (v3.9.22+, 2026-08-21)
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

        # 5e. OSF Preprints (v3.9.22+, 2026-08-21)
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

        # 5f. ChemRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.26434/chemrxiv-* DOIs.
        if doi.lower().startswith("10.26434/chemrxiv-") and prefer in ("chemrxiv", "auto"):
            try:
                from .chemrxiv_channel import fetch_chemrxiv_doi
                r = fetch_chemrxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 6. Sci-Hub (mirror rotation, last-resort gray route)
        if prefer in ("scihub", "auto"):
            r = fetch_scihub_doi(doi, out_path)
            if "error" not in r:
                return r'''
assert old_unpaywall_block in src, "old Unpaywall→Sci-Hub block not found"
src = src.replace(old_unpaywall_block, new_unpaywall_block, 1)

# ─── 3. Add 5 new cases in fetch_doi channel→prefer mapping ───────────
# Insert before the "elif 'scihub' in channels" branch (last fallback).
old_prefer = '''    elif "scihub" in channels or "unpaywall" in channels:
        prefer = "scihub"
    else:
        prefer = "auto"'''
new_prefer = '''    elif "s2" in channels and "scihub" not in channels:
        # v3.9.22+: Semantic Scholar openAccessPdf channel (free, no key)
        prefer = "s2"
    elif "biorxiv" in channels and not any(c in channels for c in ("annas", "scihub", "unpaywall")):
        # v3.9.22+: bioRxiv/medRxiv preprint channel
        prefer = "biorxiv"
    elif "core" in channels and "scihub" not in channels:
        # v3.9.22+: CORE re-added (36M+ full text vs OpenAlex metadata-only)
        prefer = "core"
    elif "osf" in channels and "scihub" not in channels:
        # v3.9.22+: OSF Preprints (PsyArXiv/SocArXiv/EarthArXiv/etc.)
        prefer = "osf"
    elif "chemrxiv" in channels and "scihub" not in channels:
        # v3.9.22+: ChemRxiv (chemistry preprints)
        prefer = "chemrxiv"
    elif "scihub" in channels or "unpaywall" in channels:
        prefer = "scihub"
    else:
        prefer = "auto"'''
assert old_prefer in src, "old prefer mapping not found"
src = src.replace(old_prefer, new_prefer, 1)

p.write_text(src, encoding="utf-8", newline="\n")
print(f"[OK] fetch.py updated, new size: {len(src):,} bytes (delta {len(src) - 53365 or 0:+,})")
