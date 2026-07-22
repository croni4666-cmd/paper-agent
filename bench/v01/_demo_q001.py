"""
bench/v01/_demo_q001.py — End-to-end demo on q001 "AI tutoring systems K-12".

What it does:
  1. Run pa search for q001 → save raw output
  2. For each result without abstract, try to fetch from OpenAlex /works/doi:...
  3. Convert to snapshot.py schema → save system_outputs/q001.json
  4. Save abstract list to _demo_q001_abstracts.json for Mavis pre-label
"""
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

BENCH_DIR = Path("bench/v01")
RAW_OUT = BENCH_DIR / "_demo_q001_raw.json"
SYSTEM_OUT = BENCH_DIR / "system_outputs" / "q001.json"
ABSTRACT_OUT = BENCH_DIR / "_demo_q001_abstracts.json"


def pa_search(query: str, limit: int = 30) -> list[dict]:
    """Run pa_cli search and return results list."""
    cmd = [
        sys.executable, "-m", "pa_cli", "search",
        query,
        "--limit", str(limit),
        "--format", "json",
        "-o", str(RAW_OUT),
        "--quiet",
    ]
    print(f"[demo] running: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # pa_cli writes to file but also prints status to stdout/stderr
    if r.returncode != 0:
        print(f"[demo] pa_cli returned {r.returncode}", file=sys.stderr)
        print(r.stderr[:500], file=sys.stderr)
    if not RAW_OUT.exists():
        print("[demo] ERROR: raw output file not created", file=sys.stderr)
        return []
    data = json.loads(RAW_OUT.read_text(encoding="utf-8"))
    return data.get("results", [])


def fetch_openalex_abstract(doi: str) -> str:
    """Try to fetch abstract from OpenAlex. Returns '' if not found."""
    if not doi:
        return ""
    url = f"https://api.openalex.org/works/doi:{doi}?select=abstract"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent-bench/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            abstract = data.get("abstract") or ""
            # OpenAlex abstracts are inverted-index style: "word[1-5] word2[3-7]"
            # We can keep it as-is, it's still readable for label judgement
            return abstract
    except Exception as e:
        return ""


def enrich_abstracts(results: list[dict], max_enrich: int = 0) -> list[dict]:
    """For results with empty abstract, try OpenAlex.
    max_enrich=0 means skip enrichment (fastest). Set to N to enrich top-N.
    """
    if max_enrich <= 0:
        n_missing = sum(1 for r in results if not r.get("abstract"))
        print(f"[demo] skipping abstract enrichment ({n_missing}/{len(results)} missing) — label by title only")
        return results
    enriched = 0
    target = [r for r in results if not r.get("abstract")][:max_enrich]
    for r in target:
        doi = r.get("doi", "")
        abs_text = fetch_openalex_abstract(doi) if doi else ""
        if abs_text:
            r["abstract"] = abs_text[:2000]
            enriched += 1
    print(f"[demo] enriched {enriched}/{len(target)} abstracts from OpenAlex (cap={max_enrich})")
    return results


def to_snapshot(qid: str, query: str, raw_results: list[dict], top_n: int = 30) -> dict:
    """Convert pa_cli results → snapshot.py expected schema."""
    out_results = []
    for i, r in enumerate(raw_results[:top_n], start=1):
        doi = r.get("doi") or ""
        out_results.append({
            "rank": i,
            "doi": doi,
            "title": r.get("title", ""),
            "abstract": r.get("abstract", ""),
            "year": r.get("year"),
            "venue": r.get("venue", ""),
            "citation_count": r.get("cited_by_count", 0) or 0,
            "engines_found_in": r.get("found_by", []),  # map found_by → engines_found_in
            "score": 0.0,  # pa_cli doesn't expose score
            "source": r.get("source", ""),
            "type": r.get("type", ""),
        })
    return {
        "query_id": qid,
        "query": query,
        "topic_bucket": "edu_ai",
        "source": "pub",
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "config": "baseline-v0.1",
        "top_n": top_n,
        "n_returned": len(out_results),
        "results": out_results,
    }


def write_abstracts_for_labeling(snapshot: dict) -> None:
    """Write a clean abstract list for Mavis (me) to label."""
    items = []
    for r in snapshot["results"]:
        if not r["doi"]:
            continue  # skip no-DOI CORE results
        items.append({
            "rank": r["rank"],
            "doi": r["doi"],
            "title": r["title"],
            "year": r["year"],
            "venue": r["venue"],
            "citations": r["citation_count"],
            "engines": r["engines_found_in"],
            "abstract": r["abstract"][:800] if r["abstract"] else "[NO ABSTRACT — judge by title only]",
        })
    ABSTRACT_OUT.write_text(
        json.dumps({"qid": snapshot["query_id"], "query": snapshot["query"], "items": items},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[demo] wrote {len(items)} labelable items to {ABSTRACT_OUT.name} (skipped no-DOI)")


def main():
    QID = "q001"
    QUERY = "AI tutoring systems and their effect on K-12 student learning outcomes"
    TOP_N = 30

    raw = pa_search(QUERY, limit=TOP_N)
    print(f"[demo] pa_cli returned {len(raw)} raw results")

    raw = enrich_abstracts(raw)

    snap = to_snapshot(QID, QUERY, raw, top_n=TOP_N)
    SYSTEM_OUT.parent.mkdir(parents=True, exist_ok=True)
    SYSTEM_OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[demo] wrote {SYSTEM_OUT}")
    print(f"[demo] {snap['n_returned']} candidates saved")

    write_abstracts_for_labeling(snap)
    print("[demo] done. next: Mavis labels the abstracts file.")


if __name__ == "__main__":
    main()
