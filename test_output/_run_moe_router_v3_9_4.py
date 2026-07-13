"""End-to-end runner for v3.9.4 MoE router training.

Per ROADMAP [P1-11] (added 2026-07-13, shipped in v3.9.4).
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

    config = MoEConfig(
        n_estimators=50,
        learning_rate=0.05,
        num_leaves=7,
        min_data_in_leaf=3,
        max_features=5000,
        ngram_range=(1, 2),
    )

    print(f"[v3.9.4 MoE Router] Starting pipeline...")
    print(f"  bench_dir: {bench_dir}")
    print(f"  config: {config}")

    result = run_moe_pipeline(bench_dir, config=config, n_folds=5, seed=42)

    # Save markdown report
    md_path = reports_dir / "v3_9_4_moe_router.md"
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
    json_path = reports_dir / "v3_9_4_moe_router.json"
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  json: {json_path}")

    # Print summary
    print()
    print("=" * 60)
    print("RESULTS (5-fold CV, multi-class classification)")
    print("=" * 60)
    print(f"  Mean accuracy: {result['cv_aggregate']['mean_accuracy']:.4f} ± {result['cv_aggregate']['std_accuracy']:.4f}")
    print(f"  Random baseline: {1.0 / len(ENGINES):.4f}")
    print(f"  Lift over random: {result['cv_aggregate']['mean_accuracy'] - 1.0/len(ENGINES):+.4f}")
    print()
    print("Per-class distribution (training labels):")
    for engine in ENGINES:
        n = result["label_distribution"].get(engine, 0)
        print(f"  {engine:12s} {n:3d} queries")
    print()
    print("Per-fold accuracies:")
    for f in result["cv_full"]["folds"]:
        print(f"  fold {f['fold']}: n_train={f['n_train']}, n_test={f['n_test']}, acc={f['accuracy']:.4f}")

    # Demo: predict weights for a sample query
    from pa_cli.moe_router import fit_router, assemble_dataset
    print()
    print("Sample inference (predict weights for q001 query):")
    dataset = assemble_dataset(bench_dir)
    router = fit_router(dataset, config=config)
    if dataset["query_texts"]:
        sample_query = dataset["query_texts"][0]
        weights = predict_weights(router, sample_query)
        print(f"  query: {sample_query[:80]}...")
        for engine, w in weights.items():
            print(f"    {engine:12s} {w:.4f}")


if __name__ == "__main__":
    main()
