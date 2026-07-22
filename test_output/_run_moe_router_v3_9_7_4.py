"""v3.9.7.4 MoE router with 12 supplementary samples (q051-q062).

Per bench/moe-keyword-samples.md, this evaluates whether adding 12 keyword
samples (crossref=5, s2=3, openalex=2, arxiv=2) improves MoE router from
v3.9.7.3 macro F1=0.609 (n=47, 3-engine-only) to 0.70-0.75 (n=59, 4 engines).

Uses v3.9.7.3 system_outputs backup (where q001-q050 have label=2 papers in
top-10) so existing labels remain valid.

For q051-q062, the synthetic system_outputs files are in system_outputs_combined/.

Implementation:
1. Copy v3.9.7.3 backup q001-q050 to system_outputs_combined/ (overwriting v3.9.10.11)
2. Keep q051-q062 (the new synthetic samples)
3. Run existing MoE pipeline
4. Compare to v3.9.7.3 baseline
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
SYS_OUT = BENCH / "system_outputs_combined"
V3973_BACKUP = BENCH / "system_outputs_combined_v3_9_7_3_backup"
NEW_SAMPLES_DIR = BENCH / "system_outputs_v3_9_10_11_with_12samples"  # we'll create this

# Step 1: create a hybrid v3.9.7.4 directory: q001-q050 from v3.9.7.3 + q051-q062 from new
V3974_DIR = BENCH / "system_outputs_v3_9_7_4"
if V3974_DIR.exists():
    shutil.rmtree(V3974_DIR)
V3974_DIR.mkdir(parents=True, exist_ok=True)

# Copy q001-q050 from v3.9.7.3 backup (preserves label=2 paper positions in top-10)
n_v3973 = 0
for f in sorted(V3973_BACKUP.glob("q*.json")):
    shutil.copy(f, V3974_DIR / f.name)
    n_v3973 += 1
print(f"Copied {n_v3973} files from v3.9.7.3 backup")

# Copy q051-q062 (synthetic) from current system_outputs_combined
n_new = 0
for qid in range(51, 63):
    qid_str = f"q{qid:03d}"
    src = SYS_OUT / f"{qid_str}.json"
    if src.exists():
        shutil.copy(src, V3974_DIR / f"{qid_str}.json")
        n_new += 1
print(f"Copied {n_new} synthetic files (q051-q062)")

# Step 2: backup current system_outputs_combined and replace with hybrid
# (we want run_moe_pipeline to read from system_outputs_combined)
BACKUP_CURRENT = BENCH / "system_outputs_combined.v31011backup"
if not BACKUP_CURRENT.exists():
    if SYS_OUT.exists():
        shutil.copytree(SYS_OUT, BACKUP_CURRENT)
        print(f"Backed up current system_outputs_combined to {BACKUP_CURRENT}")

# Replace system_outputs_combined with hybrid v3.9.7.4
if SYS_OUT.exists():
    shutil.rmtree(SYS_OUT)
shutil.copytree(V3974_DIR, SYS_OUT)
print(f"Replaced system_outputs_combined with v3.9.7.4 hybrid (n={n_v3973 + n_new})")

# Step 3: run MoE pipeline
print()
print("=" * 70)
print("Running MoE router on v3.9.7.4 hybrid (n={} = 47 + 12)".format(n_v3973 + n_new))
print("=" * 70)
print()

sys.path.insert(0, '.')
from pa_cli.moe_router import run_moe_pipeline, MoEConfig, check_deps, ENGINES

check_deps()
config = MoEConfig(
    n_estimators=50, learning_rate=0.05, num_leaves=7, min_data_in_leaf=3,
    max_features=5000, ngram_range=(1, 2), class_weight="balanced",
    report_balanced_metrics=True,
)

result = run_moe_pipeline(BENCH, config=config, n_folds=5, seed=42)

# Save report
md_path = BENCH / "reports" / "v3_9_7_4_moe_router_with_12samples.md"
md_path.write_text(result["report_markdown"], encoding="utf-8")
print(f"  report: {md_path}")

# Save JSON
raw = {
    "version": "v3.9.7.4-moe-router-with-12samples",
    "config": result["config"],
    "n_queries": result["n_queries"],
    "label_distribution": result["label_distribution"],
    "cv_aggregate": result["cv_aggregate"],
    "folds": result["cv_full"]["folds"],
    "comparison_to_v3_9_7_3": {
        "v3_9_7_3_macro_f1": 0.609,
        "v3_9_7_3_n_queries": 47,
        "v3_9_7_4_macro_f1": result["cv_aggregate"]["mean_macro_f1"],
        "v3_9_7_4_n_queries": result["n_queries"],
        "delta_macro_f1": result["cv_aggregate"]["mean_macro_f1"] - 0.609,
    },
}
json_path = BENCH / "reports" / "v3_9_7_4_moe_router_with_12samples.json"
json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"  json: {json_path}")

# Print summary
print()
print("=" * 70)
print(f"RESULTS (n={result['n_queries']}, 5-fold CV, class_weight='balanced')")
print("=" * 70)
print(f"  Mean accuracy:          {result['cv_aggregate']['mean_accuracy']:.4f} ± {result['cv_aggregate']['std_accuracy']:.4f}")
print(f"  Mean balanced accuracy: {result['cv_aggregate']['mean_balanced_accuracy']:.4f} ± {result['cv_aggregate']['std_balanced_accuracy']:.4f}")
print(f"  Mean macro F1:          {result['cv_aggregate']['mean_macro_f1']:.4f} ± {result['cv_aggregate']['std_macro_f1']:.4f}")
print()
print("  v3.9.7.3 baseline (n=47): macro F1 = 0.609")
print(f"  v3.9.7.4 with +12:        macro F1 = {result['cv_aggregate']['mean_macro_f1']:.4f}  (delta {result['cv_aggregate']['mean_macro_f1']-0.609:+.4f})")
print()
print("  Per-class distribution:")
for engine in ENGINES:
    n = result["label_distribution"].get(engine, 0)
    print(f"    {engine:12s} {n:3d} queries")

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

print()
print("Per-fold accuracies:")
for f in result["cv_full"]["folds"]:
    print(f"  fold {f['fold']}: n_train={f['n_train']:2d}, n_test={f['n_test']:2d}, "
          f"acc={f['accuracy']:.4f}, bal_acc={f['balanced_accuracy']:.4f}, macro_f1={f['macro_f1']:.4f}")
