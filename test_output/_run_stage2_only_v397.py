"""Re-run deep_rerank Layer 7 only (skip stage1 cascade) with renamed user PDFs.

Stage1 result is reconstructed from previous outputs (auto PDFs in
~/.paper-agent/deep_rerank/auto/ + manual_needed from manual_downloads_UPDATED_20260713_1730.md).

This avoids re-running the slow 8-channel fetch cascade (60s × 6 channels × 10 DOIs).
"""
import json
import time
from pathlib import Path
from pa_cli.deep_rerank import (
    stage2_fulltext_rerank,
    generate_deep_rerank_report,
)


def build_stage1_from_previous_run(n_queries: int = 5, top_k: int = 10) -> dict:
    """Reconstruct stage1 dict from previous run artifacts."""
    auto_dir = Path.home() / ".paper-agent" / "deep_rerank" / "auto"
    manual_retry_dir = Path.home() / ".paper-agent" / "deep_rerank" / "manual_retry"

    auto_downloaded = []
    manual_needed = []

    # Read auto PDFs (openalex successes)
    if auto_dir.exists():
        for qid_dir in sorted(auto_dir.iterdir()):
            if not qid_dir.is_dir():
                continue
            qid = qid_dir.name
            for pdf in sorted(qid_dir.glob("*.pdf")):
                # qid in pdf path is the query
                doi = pdf.stem  # doi_slug
                # convert slug back to doi format: 10_1001_jamanetworkopen_2021_49008 -> 10.1001/jamanetworkopen.2021.49008
                # best effort: first 2 underscore-separated = prefix, then split rest
                # We use the cached filename pattern
                doi_guess = _slug_to_doi(doi)
                size = pdf.stat().st_size
                auto_downloaded.append({
                    "qid": qid,
                    "doi": doi_guess,
                    "title": "(reconstructed from cache)",
                    "saved_as": str(pdf),
                    "via_channel": "openalex (cache)",
                    "size_bytes": size,
                })

    # Read manual_retry (scihub successes) — these were the 3 scihub downloads
    if manual_retry_dir.exists():
        for qid_dir in sorted(manual_retry_dir.iterdir()):
            if not qid_dir.is_dir():
                continue
            qid = qid_dir.name
            for pdf in sorted(qid_dir.glob("*.pdf")):
                doi_slug = pdf.stem
                doi_guess = _slug_to_doi(doi_slug)
                size = pdf.stat().st_size
                # The manual_retry PDFs were scihub retries for items in manual_needed
                auto_downloaded.append({
                    "qid": qid,
                    "doi": doi_guess,
                    "title": "(reconstructed from manual_retry cache)",
                    "saved_as": str(pdf),
                    "via_channel": "scihub (manual_retry cache)",
                    "size_bytes": size,
                })

    # Now read manual_needed list from previous markdown report
    md_path = Path("C:/Users/DengN/.paper-agent/deep_rerank/manual_downloads_UPDATED_20260713_1730.md")
    md_text = md_path.read_text(encoding="utf-8")

    # Parse lines like: | 1 | q001 | `10.1186/s41239-021-00292-9` | The impact ... | Springer paywall ... |
    import re
    pattern = re.compile(r"^\|\s*\d+\s*\|\s*(q\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", re.M)
    for m in pattern.finditer(md_text):
        qid, doi, title, reason = m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()
        # Hegewisch 2010 (DOI 10.1037/e686432011-001) will be replaced by user_pdfs/A 2014 substitute
        # All other manual_needed items either got user PDF or stayed manual
        manual_needed.append({
            "qid": qid,
            "doi": doi,
            "title": title,
            "reason": reason[:200],
            "channels_tried": ["openalex", "arxiv", "unpaywall", "doi_redirect", "scihub", "playwright"],
        })

    # Save markdown to a stable path for stage1 contract
    out_md = Path("C:/Users/DengN/.paper-agent/deep_rerank/manual_downloads_v397_reconstructed.md")
    out_md.write_text(md_text, encoding="utf-8")

    n_total = len(auto_downloaded) + len(manual_needed)
    return {
        "auto_downloaded": auto_downloaded,
        "manual_needed": manual_needed,
        "manual_downloads_md_path": str(out_md),
        "summary": {
            "n_queries": n_queries,
            "top_k_per_query": top_k,
            "n_total_candidates": n_total,
            "n_auto_downloaded": len(auto_downloaded),
            "n_manual_needed": len(manual_needed),
            "auto_pct": round(100 * len(auto_downloaded) / max(1, n_total), 1),
        },
    }


def _slug_to_doi(slug: str) -> str:
    """Convert doi_slug back to doi: 10_1001_jamanetworkopen_2021_49008 -> 10.1001/jamanetworkopen.2021.49008

    Heuristic: first 3 segments (10_NNNN_xxx) reconstruct publisher prefix, rest is path.
    Special: APA 10.1037/e686432011-001 style has 'e' prefix on article ID.
    """
    # Split by underscore
    parts = slug.split("_")
    if len(parts) < 3:
        return slug
    # Heuristic: rebuild DOI as 10.NNNN/<rest>
    # But '.' in '10.NNNN' is replaced to '_' too. So we need to know which '_' was originally '.'
    # APA: 10.1037/e686432011-001 — original = 10.1037/e686432011-001
    #   slug = 10_1037_e686432011-001 — only 3 parts split by '_'
    # Elsevier: 10.1016/j.jebo.2020.07.014
    #   slug = 10_1016_j_jebo_2020_07_014 — 8 parts
    # So: 10_NNNN stays, then everything after 3rd underscore was originally <path with .>
    # 10.<NNNN>.<rest> -> first 3 _-separated = 10_NNNN_<first_path_token>
    # Rest was path with . -> we join with .
    if len(parts) == 3:
        # APA-style: 10_NNNN_xxxxx
        return f"{parts[0]}.{parts[1]}/{parts[2]}"
    else:
        # 10_NNNN_<rest> where rest was originally "x.y.z" -> join with .
        rest = ".".join(parts[2:])
        return f"{parts[0]}.{parts[1]}/{rest}"


def main():
    from pa_cli import __version__
    print(f"pa_cli version: {__version__}")

    # 1) Reconstruct stage1 from previous run artifacts
    stage1 = build_stage1_from_previous_run(n_queries=5, top_k=10)
    print(f"\nReconstructed stage1:")
    print(f"  n_queries: {stage1['summary']['n_queries']}")
    print(f"  n_auto_downloaded: {stage1['summary']['n_auto_downloaded']}")
    print(f"  n_manual_needed: {stage1['summary']['n_manual_needed']}")
    print(f"  auto_pct: {stage1['summary']['auto_pct']}%")
    print(f"\n  auto_downloaded DOIs:")
    for a in stage1["auto_downloaded"]:
        print(f"    [{a['qid']}] {a['doi']} ({a['size_bytes']/1024:.0f} KB, {a['via_channel']})")
    print(f"\n  manual_needed DOIs:")
    for m in stage1["manual_needed"]:
        print(f"    [{m['qid']}] {m['doi']} (reason: {m['reason'][:60]})")

    # 2) Stage 2: extract fulltext
    user_pdf_dir = Path("C:/Users/DengN/Downloads/manual_pdfs/")
    print(f"\nuser_pdf_dir: {user_pdf_dir}")
    user_pdfs = sorted(p.name for p in user_pdf_dir.glob("*.pdf"))
    print(f"user PDFs ({len(user_pdfs)}):")
    for p in user_pdfs:
        print(f"  - {p}")

    # Run stage2 with reconstructed stage1
    from pa_cli.deep_rerank import DeepRerankConfig
    cfg = DeepRerankConfig()
    stage2 = stage2_fulltext_rerank(stage1, user_pdf_dir, config=cfg)

    # Read stage2 output
    out_json = Path(stage2["output_path"])
    if out_json.exists():
        data = json.loads(out_json.read_text(encoding="utf-8"))
        print(f"\nstage2 results:")
        print(f"  n_fulltext_extracted: {data['n_fulltext_extracted']} / {data['n_total_candidates']}")
        print(f"\nper_candidate:")
        for c in data["per_candidate"]:
            ft = c.get("fulltext_features", {})
            doi = c.get("doi", "")[:60]
            extracted = c.get("fulltext_extracted")
            chars = ft.get("fulltext_length_chars", 0)
            bm25 = ft.get("fulltext_bm25", 0)
            path_short = c.get("pdf_path", "")[-60:]
            print(
                f"  [{c.get('source'):>12s}] {c.get('qid')} | {doi:<60s} | "
                f"ext={extracted} | chars={chars:>6d} | bm25={bm25:.4f}"
            )

    # Generate report
    report = generate_deep_rerank_report(stage1, stage2)
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = (
        Path("bench/v01/reports") / f"v3_9_7_deep_rerank_with_8_user_pdfs_{ts}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    # Save full stage2 JSON to bench/v01/reports for traceability
    final_json = Path("bench/v01/reports") / f"v3_9_7_layer7_output_{ts}.json"
    final_json.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Full stage2 JSON: {final_json}")


if __name__ == "__main__":
    main()
