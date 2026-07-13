"""End-to-end test runner for v3.9.2 LTR (LambdaMART).

Per ROADMAP [P0-6] (added 2026-07-13, shipped in v3.9.2).

Runs full pipeline:
1. assemble_dataset from v3.9.0 bench data
2. 5-fold CV with per-query group
3. Compare vs 'combined' baseline (linear 0.5*bm25 + 0.5*biencoder)
4. Save markdown report to bench/v01/reports/v3_9_2_ltr.md
5. Save raw JSON to bench/v01/reports/v3_9_2_ltr.json
"""
import json
import sys
from pathlib import Path

# Add parent to path for pa_cli import
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.ltr import run_ltr_pipeline, LTRConfig, check_lightgbm


def main():
    check_lightgbm()
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = LTRConfig(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=5,
        label_gain=[0, 1, 3],
    )

    print(f"[v3.9.2 LTR] Starting pipeline...")
    print(f"  bench_dir: {bench_dir}")
    print(f"  config: {config}")

    result = run_ltr_pipeline(bench_dir, config=config, n_folds=5, seed=42)

    # Save markdown report
    md_path = reports_dir / "v3_9_2_ltr.md"
    md_path.write_text(result["report_markdown"], encoding="utf-8")
    print(f"  report: {md_path}")

    # Save raw JSON (exclude non-serializable items)
    raw = {
        "config": result["config"],
        "n_queries": result["n_queries"],
        "n_labeled_pairs": result["n_labeled_pairs"],
        "n_folds": result["n_folds"],
        "cv_aggregate": result["cv_aggregate"],
        "baseline_aggregate": result["baseline_aggregate"],
        "feature_importance": result["feature_importance"],
        "delta_ndcg_at_10": result["cv_aggregate"]["mean_ndcg_at_10"] - result["baseline_aggregate"]["mean_ndcg_at_10"],
        "delta_recall_at_10": result["cv_aggregate"]["mean_recall_at_10"] - result["baseline_aggregate"]["mean_recall_at_10"],
        "delta_precision_at_10": result["cv_aggregate"]["mean_precision_at_10"] - result["baseline_aggregate"]["mean_precision_at_10"],
    }
    json_path = reports_dir / "v3_9_2_ltr.json"
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  json: {json_path}")

    # Print summary
    print()
    print("=" * 60)
    print("RESULTS (5-fold CV, n=25 queries, per-query group)")
    print("=" * 60)
    print(f"  LTR (LambdaMART):")
    print(f"    NDCG@10     = {result['cv_aggregate']['mean_ndcg_at_10']:.4f} ± {result['cv_aggregate']['std_ndcg_at_10']:.4f}")
    print(f"    Recall@10   = {result['cv_aggregate']['mean_recall_at_10']:.4f}")
    print(f"    Precision@10= {result['cv_aggregate']['mean_precision_at_10']:.4f}")
    print(f"  combined (linear 0.5/0.5) baseline:")
    print(f"    NDCG@10     = {result['baseline_aggregate']['mean_ndcg_at_10']:.4f}")
    print(f"    Recall@10   = {result['baseline_aggregate']['mean_recall_at_10']:.4f}")
    print(f"    Precision@10= {result['baseline_aggregate']['mean_precision_at_10']:.4f}")
    print(f"  Δ (LTR − baseline):")
    print(f"    NDCG@10     = {raw['delta_ndcg_at_10']:+.4f}")
    print(f"    Recall@10   = {raw['delta_recall_at_10']:+.4f}")
    print(f"    Precision@10= {raw['delta_precision_at_10']:+.4f}")
    print()
    print("Feature importance (gain):")
    for name, val in sorted(result["feature_importance"].items(), key=lambda x: -x[1]):
        print(f"  {name:20s} {val:8.2f}")
    print()
    print(f"Honest interpretation: Δ={raw['delta_ndcg_at_10']:+.4f} on n=25, no significance test.")
    print(f"Per discipline 'Don't overclaim n<100 metric deltas': treat as noise, not finding.")


if __name__ == "__main__":
    main()
