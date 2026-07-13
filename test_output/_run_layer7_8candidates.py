"""Run Layer 7 on 8 auto-downloaded PDFs (5 from v3.9.5 + 3 from v3.9.5.2 retry).

Output: deep_rerank_<ts>.json with full-text features per candidate.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.deep_rerank import (
    stage1_download_orchestration,
    stage2_fulltext_rerank,
    DeepRerankConfig,
    generate_deep_rerank_report,
    extract_fulltext,
    compute_fulltext_features,
)


def main():
    # Locate all 8 auto-downloaded PDFs
    deep_rerank_dir = Path.home() / ".paper-agent" / "deep_rerank"
    pdf_paths = []
    # 5 from v3.9.5 (in auto/ subdirs)
    auto_dir = deep_rerank_dir / "auto"
    if auto_dir.exists():
        for pdf in auto_dir.rglob("*.pdf"):
            pdf_paths.append({
                "qid": pdf.parent.name,
                "doi": pdf.stem.replace("_", "/", 1).replace("_", "."),  # crude reverse
                "pdf_path": str(pdf),
                "source": "v3.9.5",
            })
    # 3 from v3.9.5.2 retry (in manual_retry/ subdirs)
    manual_retry_dir = deep_rerank_dir / "manual_retry"
    if manual_retry_dir.exists():
        for qdir in manual_retry_dir.iterdir():
            if not qdir.is_dir():
                continue
            for pdf in qdir.glob("*.pdf"):
                pdf_paths.append({
                    "qid": qdir.name,
                    "doi": pdf.stem.replace("_", "/", 1).replace("_", "."),
                    "pdf_path": str(pdf),
                    "source": "v3.9.5.2",
                })

    print(f"[Layer 7] Found {len(pdf_paths)} auto-downloaded PDFs")
    for p in pdf_paths:
        size = Path(p["pdf_path"]).stat().st_size
        print(f"  {p['source']:10s} {p['qid']:5s} {Path(p['pdf_path']).name[:50]:50s} ({size/1024:.0f} KB)")

    # Extract full text + compute features
    per_candidate = []
    for p in pdf_paths:
        fulltext = extract_fulltext(Path(p["pdf_path"]), max_chars=50000)
        if fulltext is None:
            print(f"  SKIP {p['qid']} (PyMuPDF not installed or PDF unreadable)")
            continue
        ft = compute_fulltext_features(
            query="",  # we don't have query in this simplified runner
            fulltext=fulltext,
            abstract="",  # not available here
            citation_count=0,
            year=None,
            page_count=0,
            venue="",
        )
        per_candidate.append({
            "qid": p["qid"],
            "doi": p["doi"],
            "pdf_path": p["pdf_path"],
            "source": p["source"],
            "fulltext_length_chars": len(fulltext),
            "fulltext_length_words": len(fulltext.split()),
            "fulltext_features": ft,
        })

    # Save output
    cfg = DeepRerankConfig()
    out_dir = Path.home() / ".paper-agent" / "deep_rerank"
    out_path = out_dir / f"deep_rerank_layer7_8candidates.json"
    out_path.write_text(
        json.dumps({
            "n_candidates": len(per_candidate),
            "per_candidate": per_candidate,
            "n_fulltext_extracted": sum(1 for c in per_candidate if c.get("fulltext_features", {}).get("fulltext_length_words", 0) > 0),
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8"
    )

    print(f"\n[Layer 7 Summary]")
    print(f"  Candidates: {len(per_candidate)}")
    n_with_text = sum(1 for c in per_candidate if c.get("fulltext_features", {}).get("fulltext_length_words", 0) > 0)
    print(f"  With full text extracted: {n_with_text}")
    print(f"  Output: {out_path}")

    # Per-candidate fulltext stats
    print(f"\n  Per-candidate full text stats:")
    for c in per_candidate:
        ft = c.get("fulltext_features", {})
        print(f"    {c['qid']:5s} {Path(c['pdf_path']).name[:40]:40s} {ft.get('fulltext_length_words', 0):6d} words  BM25={ft.get('fulltext_bm25', 0):.2f}")


if __name__ == "__main__":
    main()
