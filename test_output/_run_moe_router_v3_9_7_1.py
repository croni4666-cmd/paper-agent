"""End-to-end runner for v3.9.7.1 MoE router with class_weight='balanced'.

Per ROADMAP [P1-11.1] (added 2026-07-14, follow-up to v3.9.4).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.moe_router import run_moe_pipeline, MoEConfig, check_deps, predict_weights, ENGINES


def main():
    check_deps()
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # v3.9.7.1: class_weight='balanced' is now the default
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

    print(f"[v3.9.7.1 MoE Router] Starting pipeline (class_weight='balanced')...")
    print(f"  bench_dir: {bench_dir}")
    print(f"  config: {config}")

    result = run_moe_pipeline(bench_dir, config=config, n_folds=5, seed=42)

    # Save markdown report
    md_path = reports_dir / "v3_9_7_1_moe_router_balanced.md"
    md_path.write_text(result["report_markdown"], encoding="utf-8")
    print(f"  report: {md_path}")

    # Save raw JSON
    raw = {
        "config": result["config"],
        "n_queries": result["n_queries"],
        "label_distribution": result["label_distribution"],
        "cv_aggregate": result["cv_aggregate"],
        "folds": result["cv_full"]["folds"],
    }
    json_path = reports_dir / "v3_9_7_1_moe_router_balanced.json"
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  json: {json_path}")

    # Print summary
    print()
    print("=" * 70)
    print("RESULTS (5-fold CV, multi-class, class_weight='balanced')")
    print("=" * 70)
    print(f"  Mean accuracy:          {result['cv_aggregate']['mean_accuracy']:.4f} ± {result['cv_aggregate']['std_accuracy']:.4f}")
    print(f"  Mean balanced accuracy: {result['cv_aggregate']['mean_balanced_accuracy']:.4f} ± {result['cv_aggregate']['std_balanced_accuracy']:.4f}")
    print(f"  Mean macro F1:          {result['cv_aggregate']['mean_macro_f1']:.4f} ± {result['cv_aggregate']['std_macro_f1']:.4f}")
    print()
    print("  Baselines:")
    print(f"    Random uniform:       {1.0 / len(ENGINES):.4f}")
    print(f"    Majority (openalex):  {max(result['label_distribution'].values()) / sum(result['label_distribution'].values()):.4f}")
    print()
    print("Per-class distribution (training labels):")
    for engine in ENGINES:
        n = result["label_distribution"].get(engine, 0)
        print(f"  {engine:12s} {n:3d} queries")
    print()
    print("Per-fold accuracies:")
    for f in result["cv_full"]["folds"]:
        print(f"  fold {f['fold']}: n_train={f['n_train']:2d}, n_test={f['n_test']:2d}, "
              f"acc={f['accuracy']:.4f}, bal_acc={f['balanced_accuracy']:.4f}, macro_f1={f['macro_f1']:.4f}")
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
    main()
