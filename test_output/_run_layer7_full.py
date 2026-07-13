"""Run Layer 7 with proper query text from v3.9.0 bench (BM25 etc. now meaningful)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.deep_rerank import (
    extract_fulltext,
    compute_fulltext_features,
    DeepRerankConfig,
)


def main():
    # Load queries from v3.9.0 bench
    bench_dir = ROOT / "bench" / "v01"
    queries = {}
    for qfile in (bench_dir / "system_outputs_combined").iterdir():
        if not qfile.is_file() or qfile.suffix != "":
            continue
        qid = qfile.stem
        obj = json.loads(qfile.read_text(encoding="utf-8"))
        if obj.get("query"):
            queries[qid] = obj["query"]

    # Locate all 8 auto-downloaded PDFs
    deep_rerank_dir = Path.home() / ".paper-agent" / "deep_rerank"
    pdf_paths = []
    auto_dir = deep_rerank_dir / "auto"
    if auto_dir.exists():
        for pdf in auto_dir.rglob("*.pdf"):
            pdf_paths.append({
                "qid": pdf.parent.name,
                "doi_slug": pdf.stem,
                "pdf_path": str(pdf),
                "source": "v3.9.5",
            })
    manual_retry_dir = deep_rerank_dir / "manual_retry"
    if manual_retry_dir.exists():
        for qdir in manual_retry_dir.iterdir():
            if not qdir.is_dir():
                continue
            for pdf in qdir.glob("*.pdf"):
                pdf_paths.append({
                    "qid": qdir.name,
                    "doi_slug": pdf.stem.replace("_scihub", ""),
                    "pdf_path": str(pdf),
                    "source": "v3.9.5.2",
                })

    # Extract full text + compute features WITH QUERY
    per_candidate = []
    for p in pdf_paths:
        fulltext = extract_fulltext(Path(p["pdf_path"]), max_chars=50000)
        if fulltext is None:
            continue
        q_text = queries.get(p["qid"], "")
        ft = compute_fulltext_features(
            query=q_text,
            fulltext=fulltext,
            abstract="",
            citation_count=0,
            year=None,
            page_count=0,
            venue="",
        )
        per_candidate.append({
            "qid": p["qid"],
            "doi_slug": p["doi_slug"],
            "pdf_path": p["pdf_path"],
            "source": p["source"],
            "query": q_text,
            "fulltext_length_words": len(fulltext.split()),
            "fulltext_features": ft,
        })

    # Save output
    cfg = DeepRerankConfig()
    out_path = deep_rerank_dir / "deep_rerank_layer7_full.json"
    out_path.write_text(
        json.dumps({
            "n_candidates": len(per_candidate),
            "per_candidate": per_candidate,
            "n_with_fulltext": sum(1 for c in per_candidate if c.get("fulltext_length_words", 0) > 0),
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )

    print(f"[Layer 7] {len(per_candidate)} candidates processed")
    print(f"  Output: {out_path}")
    print(f"\n  Per-candidate stats:")
    for c in per_candidate:
        ft = c.get("fulltext_features", {})
        q_short = c["query"][:50] + "..." if len(c["query"]) > 50 else c["query"]
        print(f"    {c['qid']:5s} {Path(c['pdf_path']).name[:40]:40s}")
        print(f"      Query: {q_short}")
        print(f"      Fulltext: {c['fulltext_length_words']:6d} words  |  BM25={ft.get('fulltext_bm25', 0):.2f}  |  cite_density={ft.get('fulltext_citation_density', 0):.3f}")


if __name__ == "__main__":
    main()
