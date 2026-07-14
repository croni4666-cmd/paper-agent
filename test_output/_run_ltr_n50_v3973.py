"""v3.9.7.3 — LTR (LambdaMART) n=50 with mixed labels (q001-q025 real + q026-q050 auto).

Uses the v3.9.7.3 moe_router.py + ltr.py fix to dedupe no-ext + .json files.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.ltr import run_ltr_pipeline, LTRConfig, check_lightgbm


def main():
    check_lightgbm()
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Swap labels_clean.json with n=50 mixed version
    real_path = bench_dir / "labels_clean.json"
    real = json.loads(real_path.read_text(encoding="utf-8"))
    n50 = json.load(open(bench_dir / "labels_n50_mixed.json", encoding="utf-8"))
    backup_path = real_path.with_suffix(".json.real.bak")
    backup_path.write_text(json.dumps(real, ensure_ascii=False, indent=2), encoding="utf-8")
    swapped = {"version": "v3.9.7.3-n50-mixed-temp", "n_queries": 50, "labels": n50["labels"]}
    real_path.write_text(json.dumps(swapped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Swapped labels_clean.json → n=50 mixed (backup at {backup_path})")

    config = LTRConfig(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=31,
        min_data_in_leaf=5,
        label_gain=[0, 1, 3],
    )

    try:
        print(f"[v3.9.7.3 LTR] Starting pipeline...")
        print(f"  config: {config}")

        result = run_ltr_pipeline(bench_dir, config=config, n_folds=5, seed=42)

        md_path = reports_dir / "v3_9_7_3_ltr_n50.md"
        md_path.write_text(result["report_markdown"], encoding="utf-8")
        print(f"  report: {md_path}")

        raw = {
            "version": "v3.9.7.3",
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
            "label_source": "n50_mixed (q001-q025 real + q026-q050 A2 auto)",
            "note": (
                "BGE feature importance may be inflated due to A2 auto-label circularity. "
                "Combined baseline unaffected (uses BM25 + biencoder only)."
            ),
        }
        json_path = reports_dir / "v3_9_7_3_ltr_n50.json"
        json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  json: {json_path}")

        print()
        print("=" * 60)
        print(f"RESULTS (5-fold CV, n={result['n_queries']} queries)")
        print("=" * 60)
        print(f"  LTR (LambdaMART):")
        print(f"    NDCG@10     = {result['cv_aggregate']['mean_ndcg_at_10']:.4f} +/- {result['cv_aggregate']['std_ndcg_at_10']:.4f}")
        print(f"    Recall@10   = {result['cv_aggregate']['mean_recall_at_10']:.4f}")
        print(f"    Precision@10= {result['cv_aggregate']['mean_precision_at_10']:.4f}")
        print(f"  combined (linear 0.5/0.5) baseline:")
        print(f"    NDCG@10     = {result['baseline_aggregate']['mean_ndcg_at_10']:.4f}")
        print(f"    Recall@10   = {result['baseline_aggregate']['mean_recall_at_10']:.4f}")
        print(f"    Precision@10= {result['baseline_aggregate']['mean_precision_at_10']:.4f}")
        print(f"  delta (LTR - baseline):")
        print(f"    NDCG@10     = {raw['delta_ndcg_at_10']:+.4f}")
        print(f"    Recall@10   = {raw['delta_recall_at_10']:+.4f}")
        print(f"    Precision@10= {raw['delta_precision_at_10']:+.4f}")
        print()
        print("Feature importance (gain):")
        for name, val in sorted(result["feature_importance"].items(), key=lambda x: -x[1]):
            print(f"  {name:20s} {val:8.2f}")

    finally:
        real_path.write_text(json.dumps(real, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Restored real labels_clean.json (n=25, v3.9.0 era)")


if __name__ == "__main__":
    main()
