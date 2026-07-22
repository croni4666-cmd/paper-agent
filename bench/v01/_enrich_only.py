"""
bench/v01/_enrich_only.py — Re-enrich abstracts for all 25 system_outputs without re-running pa search.

Uses OpenAlex's abstract_inverted_index field (the correct field name).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BENCH_DIR = Path("bench/v01")
SYSTEM_OUT_DIR = BENCH_DIR / "system_outputs"
CACHE_DIR = BENCH_DIR / "cache" / "abstracts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WORKERS = 15
TIMEOUT = 8


def inverted_to_text(inv) -> str:
    """Convert OpenAlex inverted-index abstract to plain text."""
    if not inv or not isinstance(inv, dict):
        return ""
    word_positions = []
    for word, positions in inv.items():
        if not isinstance(positions, list):
            continue
        for p in positions:
            if isinstance(p, int):
                word_positions.append((p, word))
    if not word_positions:
        return ""
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


def doi_to_cache_path(doi: str) -> Path:
    safe = (doi or "").replace("/", "_").replace("\\", "_").replace(":", "_").strip()
    if not safe:
        safe = "_no_doi_"
    return CACHE_DIR / f"{safe}.json"


def fetch_oa_abstract(doi: str) -> str:
    """OpenAlex DOI lookup. Returns '' if no abstract. Caches everything."""
    if not doi:
        return ""
    cache_path = doi_to_cache_path(doi)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_abs = data.get("abstract", "")
            if cached_abs or data.get("checked_with_correct_field"):
                return cached_abs
            # else: re-fetch with new field
        except Exception:
            pass

    url = f"https://api.openalex.org/works/doi:{doi}?select=id,doi,abstract_inverted_index"
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        url += f"&api_key={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent-bench/0.1 (mailto:hi@example.com)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
            inv = data.get("abstract_inverted_index") or {}
            abstract = inverted_to_text(inv)
            cache_path.write_text(
                json.dumps({
                    "doi": doi, "abstract": abstract, "source": "openalex-v2",
                    "checked_with_correct_field": True,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            return abstract
    except Exception as e:
        cache_path.write_text(
            json.dumps({
                "doi": doi, "abstract": "", "source": "openalex-v2",
                "error": str(e)[:200], "checked_with_correct_field": True,
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        return ""


def main():
    files = sorted(SYSTEM_OUT_DIR.glob("q*.json"))
    print(f"[enrich] {len(files)} system output files")

    # Collect all candidates missing abstract
    all_candidates = []
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        for r in snap["results"]:
            if not r.get("abstract") and r.get("doi"):
                all_candidates.append((f.stem, r))

    print(f"[enrich] {len(all_candidates)} candidates missing abstract")

    # Dedupe DOIs (many candidates share DOIs across queries)
    unique_dois = list({c[1]["doi"] for c in all_candidates})
    print(f"[enrich] {len(unique_dois)} unique DOIs to fetch")

    t0 = time.time()
    fetched = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_doi = {executor.submit(fetch_oa_abstract, doi): doi for doi in unique_dois}
        for i, future in enumerate(as_completed(future_to_doi), 1):
            doi = future_to_doi[future]
            try:
                abstract = future.result()
                fetched[doi] = abstract
            except Exception as e:
                fetched[doi] = ""
            if i % 50 == 0:
                print(f"  [enrich] {i}/{len(unique_dois)} fetched, {sum(1 for v in fetched.values() if v)} with abstract")

    n_with_abs = sum(1 for v in fetched.values() if v)
    print(f"[enrich] {n_with_abs}/{len(unique_dois)} unique DOIs got abstract, {time.time()-t0:.0f}s")

    # Update system_outputs
    n_updated = 0
    n_total_updated = 0
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        for r in snap["results"]:
            if not r.get("abstract") and r.get("doi") and fetched.get(r["doi"]):
                r["abstract"] = fetched[r["doi"]][:2000]
                n_total_updated += 1
        f.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        n_updated += 1
    print(f"[enrich] updated {n_updated} files, {n_total_updated} candidate abstracts filled")


if __name__ == "__main__":
    main()
