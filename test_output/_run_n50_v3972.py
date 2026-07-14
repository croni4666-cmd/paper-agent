"""v3.9.7.2 — Re-run MoE + Wilcoxon on n=50 (with new q026-q050 user batch).

Per user 2026-07-14 22:30 — Option A: write v3 into queries.json, run n=50 re-eval.

Compares:
- n=25 (q001-q025) v3.9.7.1 numbers
- n=50 (q001-q050) v3.9.7.2 numbers

Output:
- bench/v01/reports/v3_9_7_2_moe_router_n50.{md,json}
- bench/v01/reports/v3_9_7_2_cross_encoder_wilcoxon_n50.{md,json}
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.moe_router import run_moe_pipeline, MoEConfig, check_deps, ENGINES


def main_moe_n50():
    print("=" * 78)
    print("[v3.9.7.2 MoE] n=50 re-run (q001-q050 with user batch q026-q050)")
    print("=" * 78)
    check_deps()
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = MoEConfig(
        n_estimators=50,
        learning_rate=0.05,
        num_leaves=7,
        min_data_in_leaf=3,
        max_features=5000,
        ngram_range=(1, 2),
        class_weight="balanced",  # v3.9.7.1 default
        report_balanced_metrics=True,
    )

    # 5-fold CV on n=50
    result = run_moe_pipeline(bench_dir, config=config, n_folds=5, seed=42)

    # Save outputs
    md_path = reports_dir / "v3_9_7_2_moe_router_n50.md"
    md_path.write_text(result["report_markdown"], encoding="utf-8")
    print(f"  report: {md_path}")

    raw = {
        "version": "v3.9.7.2",
        "n_queries": result["n_queries"],
        "config": result["config"],
        "label_distribution": result["label_distribution"],
        "cv_aggregate": result["cv_aggregate"],
        "folds": result["cv_full"]["folds"],
    }
    json_path = reports_dir / "v3_9_7_2_moe_router_n50.json"
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  json: {json_path}")

    # Print summary
    print()
    print("RESULTS (5-fold CV, multi-class, n=50, class_weight='balanced')")
    print("-" * 78)
    print(f"  Mean accuracy:          {result['cv_aggregate']['mean_accuracy']:.4f} +/- {result['cv_aggregate']['std_accuracy']:.4f}")
    print(f"  Mean balanced accuracy: {result['cv_aggregate']['mean_balanced_accuracy']:.4f} +/- {result['cv_aggregate']['std_balanced_accuracy']:.4f}")
    print(f"  Mean macro F1:          {result['cv_aggregate']['mean_macro_f1']:.4f} +/- {result['cv_aggregate']['std_macro_f1']:.4f}")
    print()
    print(f"  Random uniform:       {1.0/len(ENGINES):.4f}")
    print(f"  Majority class:       {max(result['label_distribution'].values())/sum(result['label_distribution'].values()):.4f}")
    print()
    print("Per-class distribution (training labels):")
    for engine in ENGINES:
        n = result["label_distribution"].get(engine, 0)
        bar = "#" * int(n * 50 / 50)  # 1 char per query, max 50 wide
        print(f"  {engine:12s} {n:3d} queries  {bar}")
    print()
    print("Per-fold accuracies:")
    for f in result["cv_full"]["folds"]:
        print(f"  fold {f['fold']}: n_train={f['n_train']:2d}, n_test={f['n_test']:2d}, "
              f"acc={f['accuracy']:.4f}, bal_acc={f['balanced_accuracy']:.4f}, "
              f"macro_f1={f['macro_f1']:.4f}")
    print()
    print("Per-class metrics (averaged across folds):")
    print(f"  {'Engine':12s} {'Prec':>7s} {'Recall':>7s} {'F1':>7s} {'Support':>8s}")
    for engine in ENGINES:
        per_fold = [f["per_class_metrics"][engine] for f in result["cv_full"]["folds"]]
        prec = sum(m["precision"] for m in per_fold) / len(per_fold)
        rec = sum(m["recall"] for m in per_fold) / len(per_fold)
        f1 = sum(m["f1"] for m in per_fold) / len(per_fold)
        sup = int(sum(m["support"] for m in per_fold) / len(per_fold))
        print(f"  {engine:12s} {prec:>7.4f} {rec:>7.4f} {f1:>7.4f} {sup:>8d}")


if __name__ == "__main__":
    main_moe_n50()
