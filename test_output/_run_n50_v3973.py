"""v3.9.7.3 — Run MoE / BGE / LTR / eval on n=50 mixed labels (q001-q025 real + q026-q050 auto).

Reuses v3.9.7.2 infrastructure but reads labels_n50_mixed.json instead of labels_clean.json.

Output:
- bench/v01/reports/v3_9_7_3_moe_router_n50.{json,md}
- bench/v01/reports/v3_9_7_3_cross_encoder_n50.json (re-run BGE on n=50)
- bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.{json,md}
- bench/v01/reports/v3_9_7_3_ltr_n50.json
- bench/v01/reports/v3_9_7_3_v4_eval_n50.{json,md} (per-condition recall/precision/ndcg)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.moe_router import run_moe_pipeline, MoEConfig, check_deps, ENGINES

LABELS_N50 = ROOT / "bench" / "v01" / "labels_n50_mixed.json"
LABELS_CLEAN = ROOT / "bench" / "v01" / "labels_clean.json"


def main_moe():
    print("=" * 78)
    print("[v3.9.7.3 MoE] n=50 (q001-q025 real + q026-q050 auto)")
    print("=" * 78)
    check_deps()
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Use labels_n50_mixed.json — need to swap it in for assemble_dataset to read
    # assemble_dataset reads labels_clean.json by hardcoded path.
    # So we temporarily swap labels_clean.json with labels_n50_mixed.json's labels
    # (Backup real one, restore after)
    real_clean = json.loads(LABELS_CLEAN.read_text(encoding="utf-8"))
    n50_mixed = json.loads(LABELS_N50.read_text(encoding="utf-8"))
    # Backup real labels_clean.json
    backup_path = LABELS_CLEAN.with_suffix(".json.real.bak")
    backup_path.write_text(json.dumps(real_clean, ensure_ascii=False, indent=2), encoding="utf-8")
    # Write n50_mixed's labels into labels_clean.json
    swapped = {
        "version": "v3.9.7.3-n50-mixed-temp",
        "n_queries": 50,
        "labels": n50_mixed["labels"],
    }
    LABELS_CLEAN.write_text(json.dumps(swapped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Swapped labels_clean.json → n=50 mixed (backup at {backup_path})")

    try:
        config = MoEConfig(
            n_estimators=50,
            learning_rate=0.05,
            num_leaves=7,
            min_data_in_leaf=3,
            max_features=5000,
            ngram_range=(1, 2),
            class_weight="balanced",
            report_balanced_metrics=True,
        )
        result = run_moe_pipeline(bench_dir, config=config, n_folds=5, seed=42)

        md_path = reports_dir / "v3_9_7_3_moe_router_n50.md"
        md_path.write_text(result["report_markdown"], encoding="utf-8")
        print(f"  report: {md_path}")

        raw = {
            "version": "v3.9.7.3",
            "n_queries": result["n_queries"],
            "config": result["config"],
            "label_distribution": result["label_distribution"],
            "cv_aggregate": result["cv_aggregate"],
            "folds": result["cv_full"]["folds"],
            "note": (
                "n=50 mixed labels: q001-q025 from v3.9.0 user era, q026-q050 from "
                "v3.9.7.3 A2 auto-labeling (keyword + BGE/biencoder tie-breaker). "
                "Auto labels are NOT expert-validated; treat as method-comparison tool only."
            ),
            "label_source": n50_mixed["label_source"],
        }
        json_path = reports_dir / "v3_9_7_3_moe_router_n50.json"
        json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  json: {json_path}")

        print()
        print(f"RESULTS (5-fold CV, n={result['n_queries']}, class_weight='balanced')")
        print("-" * 78)
        print(f"  Mean accuracy:          {result['cv_aggregate']['mean_accuracy']:.4f} +/- {result['cv_aggregate']['std_accuracy']:.4f}")
        print(f"  Mean balanced accuracy: {result['cv_aggregate']['mean_balanced_accuracy']:.4f} +/- {result['cv_aggregate']['std_balanced_accuracy']:.4f}")
        print(f"  Mean macro F1:          {result['cv_aggregate']['mean_macro_f1']:.4f} +/- {result['cv_aggregate']['std_macro_f1']:.4f}")
        print()
        print("Per-class distribution (training labels):")
        for engine in ENGINES:
            n = result["label_distribution"].get(engine, 0)
            bar = "#" * int(n * 50 / max(1, result["n_queries"]))
            print(f"  {engine:12s} {n:3d} queries  {bar}")
        print()
        print("Per-fold accuracies:")
        for f in result["cv_full"]["folds"]:
            print(f"  fold {f['fold']}: n_train={f['n_train']:2d}, n_test={f['n_test']:2d}, "
                  f"acc={f['accuracy']:.4f}, bal_acc={f['balanced_accuracy']:.4f}, "
                  f"macro_f1={f['macro_f1']:.4f}")

    finally:
        # Restore real labels_clean.json
        LABELS_CLEAN.write_text(json.dumps(real_clean, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Restored real labels_clean.json (n=25, v3.9.0 era)")
        # Don't delete backup — keep as audit trail


if __name__ == "__main__":
    main_moe()
