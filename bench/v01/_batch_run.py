"""
bench/v01/_batch_run.py — Batch pa search + abstract enrichment for all 25 real queries.

Stage 1+2+3 combined: pa search (sequential) → abstract enrichment (parallel) → save.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BENCH_DIR = Path("bench/v01")
QUERIES_PATH = BENCH_DIR / "queries.json"
SYSTEM_OUT_DIR = BENCH_DIR / "system_outputs"
CACHE_DIR = BENCH_DIR / "cache" / "abstracts"

SYSTEM_OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PA_TIMEOUT = 180           # sec per pa search
ABSTRACT_TIMEOUT = 8       # sec per OpenAlex request
ABSTRACT_WORKERS = 15      # 15 concurrent OpenAlex requests
TOP_N = 30


def pa_search(query: str, limit: int = TOP_N) -> list[dict]:
    """Run pa_cli search and return results list. Reads from stdout."""
    cmd = [
        sys.executable, "-m", "pa_cli", "search",
        query,
        "--limit", str(limit),
        "--format", "json",
        "--quiet",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=PA_TIMEOUT, cwd=str(BENCH_DIR.parent.parent))
    if r.returncode != 0:
        print(f"    [pa] FAIL returncode={r.returncode} stderr={r.stderr[:200]}")
        return []
    # pa_cli with --format json writes to stdout
    try:
        data = json.loads(r.stdout)
        return data.get("results", [])
    except json.JSONDecodeError as e:
        print(f"    [pa] JSON decode error: {e}; stdout head={r.stdout[:200]}")
        return []


def doi_to_cache_path(doi: str) -> Path:
    """Convert DOI to safe cache filename."""
    safe = doi.replace("/", "_").replace("\\", "_").replace(":", "_").strip()
    if not safe:
        safe = "_no_doi_"
    return CACHE_DIR / f"{safe}.json"


def fetch_openalex_abstract(doi: str) -> str:
    """Try OpenAlex. Returns '' if not found. Caches result + failures."""
    if not doi:
        return ""
    cache_path = doi_to_cache_path(doi)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("abstract", "")
        except Exception:
            pass

    url = f"https://api.openalex.org/works/doi:{doi}?select=abstract"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent-bench/0.1 (mailto:hi@example.com)"})
    # Use OpenAlex API key if available (polite pool, 10x rate limit)
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        # OpenAlex uses ?api_key= query param, not header
        url = url + f"&api_key={api_key}"
    try:
        with urllib.request.urlopen(req, timeout=ABSTRACT_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
            abstract = data.get("abstract") or ""
            cache_path.write_text(
                json.dumps({"doi": doi, "abstract": abstract, "source": "openalex"}, ensure_ascii=False),
                encoding="utf-8",
            )
            return abstract
    except Exception as e:
        cache_path.write_text(
            json.dumps({"doi": doi, "abstract": "", "source": "openalex", "error": str(e)[:200]},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        return ""


def enrich_abstracts_parallel(results: list[dict]) -> tuple[int, int]:
    """Enrich all missing abstracts in parallel. Returns (n_filled, n_attempted)."""
    missing = [r for r in results if not r.get("abstract") and r.get("doi")]
    if not missing:
        return 0, 0
    n_filled = 0
    with ThreadPoolExecutor(max_workers=ABSTRACT_WORKERS) as executor:
        future_to_r = {executor.submit(fetch_openalex_abstract, r["doi"]): r for r in missing}
        for future in as_completed(future_to_r):
            r = future_to_r[future]
            try:
                abstract = future.result()
                if abstract:
                    r["abstract"] = abstract[:2000]
                    n_filled += 1
            except Exception:
                pass
    return n_filled, len(missing)


def to_snapshot(qid: str, query: str, topic_bucket: str, source: str,
                raw_results: list[dict], top_n: int = TOP_N) -> dict:
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
            "engines_found_in": r.get("found_by", []),
            "score": 0.0,
            "source": r.get("source", ""),
            "type": r.get("type", ""),
        })
    return {
        "query_id": qid,
        "query": query,
        "topic_bucket": topic_bucket,
        "source": source,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": "baseline-v0.1",
        "top_n": top_n,
        "n_returned": len(out_results),
        "results": out_results,
    }


def process_query(q: dict) -> dict | None:
    """Process one query: pa search + abstract enrichment + save."""
    qid = q["id"]
    query = q["query"]
    out_path = SYSTEM_OUT_DIR / f"{qid}.json"

    if out_path.exists():
        print(f"  [SKIP] {qid} (already exists)")
        return json.loads(out_path.read_text(encoding="utf-8"))

    t0 = time.time()
    raw = pa_search(query)
    t_pa = time.time() - t0
    if not raw:
        print(f"  [FAIL] {qid}: no results from pa search ({t_pa:.1f}s)")
        return None

    n_filled, n_attempted = enrich_abstracts_parallel(raw)
    t_total = time.time() - t0
    n_with_abstract = sum(1 for r in raw if r.get("abstract"))
    print(f"  [OK] {qid}: {len(raw)} raw → top-30 saved, "
          f"{n_with_abstract}/30 have abstract ({n_filled} filled), "
          f"pa={t_pa:.0f}s total={t_total:.0f}s")

    snap = to_snapshot(qid, query, q.get("topic_bucket", ""), q.get("source", ""), raw, top_n=TOP_N)
    out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap


def main():
    queries_data = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    all_queries = queries_data["queries"]
    real_queries = [q for q in all_queries if not q["query"].startswith("[USER-PROVIDED")]
    print(f"[batch] {len(real_queries)} real queries (out of {len(all_queries)} total)")

    t0 = time.time()
    success = 0
    failed = []
    for q in real_queries:
        result = process_query(q)
        if result:
            success += 1
        else:
            failed.append(q["id"])

    t_total = time.time() - t0
    print()
    print(f"[batch] done: {success}/{len(real_queries)} succeeded, {len(failed)} failed, {t_total:.0f}s total")
    if failed:
        print(f"[batch] failed: {failed}")


if __name__ == "__main__":
    main()
