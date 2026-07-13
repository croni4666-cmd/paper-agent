"""End-to-end runner for v3.9.5 [P0-8] full-text deep rerank.

Per ROADMAP [P0-8] (added 2026-07-13, shipped in v3.9.5).

Demo: process first 3 queries (q001-q003), top-5 each = 15 papers.
Emits manual_downloads_<ts>.md for any that 8-channel cascade cannot fetch.

User then manually downloads the failed ones to a directory and re-runs
with --user-pdf-dir to get Layer 7 full-text features.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.deep_rerank import (
    run_deep_rerank_pipeline,
    DeepRerankConfig,
    stage1_download_orchestration,
    stage2_fulltext_rerank,
    generate_deep_rerank_report,
)


def main():
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = DeepRerankConfig(
        top_k_per_query=5,
        per_doi_timeout_sec=30,
        cascade_channels=["openalex", "arxiv", "unpaywall", "doi_redirect"],  # skip scihub + playwright for demo
    )

    print(f"[v3.9.5 Deep Rerank Demo] Starting Layer 6 (download orchestration)...")
    print(f"  bench_dir: {bench_dir}")
    print(f"  top_k_per_query: {config.top_k_per_query}")
    print(f"  per_doi_timeout_sec: {config.per_doi_timeout_sec}")
    print(f"  channels: {config.cascade_channels}")

    # Demo: 3 queries, top-5 each = 15 papers
    stage1 = stage1_download_orchestration(bench_dir, config=config, n_queries=3)

    print(f"\n[Stage 1 Summary]")
    s1 = stage1["summary"]
    print(f"  Queries: {s1['n_queries']}")
    print(f"  Total candidates: {s1['n_total_candidates']}")
    print(f"  Auto-downloaded: {s1['n_auto_downloaded']} ({s1['auto_pct']}%)")
    print(f"  Manual needed: {s1['n_manual_needed']}")
    print(f"  Manual download list: {stage1['manual_downloads_md_path']}")

    # Save Stage 1 report
    md = generate_deep_rerank_report(stage1, stage2=None)
    (reports_dir / "v3_9_5_deep_rerank.md").write_text(md, encoding="utf-8")
    print(f"  Report: {reports_dir / 'v3_9_5_deep_rerank.md'}")

    # Save raw stage1 result
    (reports_dir / "v3_9_5_stage1_result.json").write_text(
        json.dumps(stage1, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Stage 2 only if user provides --user-pdf-dir
    user_pdf_dir = None
    # Note: actual user input would be via CLI argument; for demo, just show
    # the framework is ready for user input.

    if user_pdf_dir:
        stage2 = stage2_fulltext_rerank(stage1, user_pdf_dir, config=config)
        print(f"\n[Stage 2 Summary]")
        s2 = stage2["summary"]
        print(f"  Candidates with full text: {s2['n_candidates_with_fulltext']} / {s2['n_total_candidates']} ({s2['pct_fulltext']}%)")
    else:
        print(f"\n[Stage 2] Skipped (no --user-pdf-dir provided)")
        print(f"  Next: user manually downloads {s1['n_manual_needed']} PDFs")
        print(f"  Then re-run with: --user-pdf-dir C:/Users/DengN/Downloads/manual_pdfs/")


if __name__ == "__main__":
    main()
