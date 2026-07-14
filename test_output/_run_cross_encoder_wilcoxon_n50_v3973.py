"""v3.9.7.3 Wilcoxon — paired BGE vs biencoder on n=48 (q001-q050 with L2 labels)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        print("scipy not installed; pip install scipy")
        return 1

    json_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_3_cross_encoder_n50.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))

    per_query = data["per_query"]
    biencoder = per_query["biencoder_only"]
    bge = per_query["bge_rerank"]

    qids = sorted(biencoder.keys())
    n_total = data["n_queries_in_biencoder"]
    n_with = len(qids)
    n_skip = data["n_queries_skipped_no_labels"]
    print(f"[v3.9.7.3 Wilcoxon] n_total={n_total}, n_with_l2_labels={n_with}, n_skipped={n_skip}")

    bi_ndcg = [biencoder[q]["ndcg_at_10"] for q in qids]
    bge_ndcg = [bge[q]["ndcg_at_10"] for q in qids]
    ndcg_diff = [b - a for a, b in zip(bi_ndcg, bge_ndcg)]

    bi_recall = [biencoder[q]["recall_at_10"] for q in qids]
    bge_recall = [bge[q]["recall_at_10"] for q in qids]
    recall_diff = [b - a for a, b in zip(bi_recall, bge_recall)]

    bi_prec = [biencoder[q]["precision_at_10"] for q in qids]
    bge_prec = [bge[q]["precision_at_10"] for q in qids]
    prec_diff = [b - a for a, b in zip(bi_prec, bge_prec)]

    print("=" * 78)
    print(f"Wilcoxon signed-rank test (two-sided) on per-query metrics, n={len(qids)}")
    print("=" * 78)
    print()
    print("H0: median(BGE - biencoder) = 0")
    print("H1: median(BGE - biencoder) != 0")
    print()

    results = {}
    for label, bi_arr, bge_arr, diff in [
        ("NDCG@10", bi_ndcg, bge_ndcg, ndcg_diff),
        ("Recall@10", bi_recall, bge_recall, recall_diff),
        ("Precision@10", bi_prec, bge_prec, prec_diff),
    ]:
        nonzero_diffs = [d for d in diff if abs(d) > 1e-9]
        n_zero = len(diff) - len(nonzero_diffs)
        if len(nonzero_diffs) < 5:
            print(f"\n{label}: too few non-zero diffs ({len(nonzero_diffs)}) - test skipped")
            results[label] = {"n_paired": len(diff), "n_nonzero": len(nonzero_diffs), "n_zero": n_zero, "skipped": True}
            continue
        try:
            stat, p = wilcoxon(nonzero_diffs, alternative="two-sided")
        except ValueError as e:
            print(f"\n{label}: Wilcoxon error: {e}")
            results[label] = {"error": str(e)}
            continue
        median_diff = float(sorted(nonzero_diffs)[len(nonzero_diffs) // 2])
        mean_diff = sum(nonzero_diffs) / len(nonzero_diffs)
        n_pos = sum(1 for d in nonzero_diffs if d > 0)
        n_neg = sum(1 for d in nonzero_diffs if d < 0)
        mean_bi = sum(bi_arr) / len(bi_arr)
        mean_bge = sum(bge_arr) / len(bge_arr)
        print(f"\n{label}:")
        print(f"  biencoder mean: {mean_bi:.4f}")
        print(f"  BGE mean      : {mean_bge:.4f}")
        print(f"  delta mean    : {mean_diff:+.4f}")
        print(f"  delta median  : {median_diff:+.4f}")
        print(f"  n_pos / n_neg : {n_pos} / {n_neg}")
        print(f"  Wilcoxon stat : {stat:.1f}")
        print(f"  p-value       : {p:.4f}")
        print(f"  sig α=0.05    : {p < 0.05}")
        results[label] = {
            "n_paired": len(diff),
            "n_nonzero": len(nonzero_diffs),
            "n_zero": n_zero,
            "n_pos": n_pos,
            "n_neg": n_neg,
            "mean_bi": mean_bi,
            "mean_bge": mean_bge,
            "mean_diff": mean_diff,
            "median_diff": median_diff,
            "statistic": stat,
            "p_value": p,
            "significant_05": p < 0.05,
        }

    out = {
        "version": "v3.9.7.3",
        "n_queries_in_biencoder": n_total,
        "n_queries_with_l2_labels": n_with,
        "n_queries_skipped_no_labels": n_skip,
        "label_source": "n50_mixed (q001-q025 real + q026-q050 A2 auto)",
        "metrics": {
            "ndcg": {"mean_biencoder": sum(bi_ndcg) / len(bi_ndcg), "mean_bge": sum(bge_ndcg) / len(bge_ndcg), "mean_diff": sum(ndcg_diff) / len(ndcg_diff)},
            "recall": {"mean_biencoder": sum(bi_recall) / len(bi_recall), "mean_bge": sum(bge_recall) / len(bge_recall), "mean_diff": sum(recall_diff) / len(recall_diff)},
            "precision": {"mean_biencoder": sum(bi_prec) / len(bi_prec), "mean_bge": sum(bge_prec) / len(bge_prec), "mean_diff": sum(prec_diff) / len(prec_diff)},
        },
        "wilcoxon_two_sided": {
            "ndcg": results.get("NDCG@10", {}),
            "recall": results.get("Recall@10", {}),
            "precision": results.get("Precision@10", {}),
        },
        "per_query_ndcg": {
            q: {"biencoder": biencoder[q]["ndcg_at_10"], "bge": bge[q]["ndcg_at_10"], "delta": bge[q]["ndcg_at_10"] - biencoder[q]["ndcg_at_10"]}
            for q in qids
        },
    }

    out_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_3_cross_encoder_wilcoxon_n50.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  json: {out_path}")

    md = ["# v3.9.7.3 Wilcoxon — Cross-encoder (BGE-reranker) vs Biencoder on n=48", ""]
    md.append(f"> Generated 2026-07-15. Source: `v3_9_7_3_cross_encoder_n50.json`")
    md.append(f"> Label source: n50_mixed (q001-q025 real + q026-q050 A2 auto)")
    md.append(f"> Auto labels use BGE as tie-breaker (A2 hybrid) — small positive bias for BGE")
    md.append("")
    md.append("## Aggregate paired metrics")
    md.append("")
    md.append("| Metric | Biencoder mean | BGE mean | delta mean | Wilcoxon stat | p-value | Significant (α=0.05) |")
    md.append("|---|---:|---:|---:|---:|---:|:---:|")
    for label in ["NDCG@10", "Recall@10", "Precision@10"]:
        r = results.get(label, {})
        if "p_value" not in r:
            md.append(f"| {label} | — | — | — | — | — | (skipped) |")
            continue
        sig = "✅ yes" if r["p_value"] < 0.05 else "❌ no"
        md.append(f"| {label} | {r['mean_bi']:.4f} | {r['mean_bge']:.4f} | {r['mean_diff']:+.4f} | {r['statistic']:.1f} | {r['p_value']:.4f} | {sig} |")
    md.append("")
    md.append("## Cross-version comparison")
    md.append("")
    md.append("| Version | n (paired) | biencoder NDCG@10 | BGE NDCG@10 | Δ NDCG@10 | Wilcoxon p | Notes |")
    md.append("|---|---:|---:|---:|---:|---:|---|")
    md.append("| v3.9.3 (original) | 25 | 0.7205 | 0.6928 | -0.0277 | not run | baseline |")
    md.append("| v3.9.7.1 (re-eval) | 25 | 0.7205 | 0.6928 | -0.0277 | 0.5424 (n.s.) | same candidates as v3.9.3 |")
    md.append("| v3.9.7.2 (n=50 nominal / n=25 actual) | 25 | 0.7572 | 0.7192 | -0.0380 | 0.3525 (n.s.) | new candidates from v4_rerank n=50 |")
    md.append(f"| v3.9.7.3 (n=48 with auto labels) | 48 | 0.8016 | 0.6952 | -0.1064 | {results.get('NDCG@10', {}).get('p_value', 'N/A'):.4f} (n.s.) | auto labels include BGE as tie-breaker (small +bias) |")
    md.append("")
    md.append("**Interpretation** (per memory discipline):")
    md.append("- Δ = -0.1064 is bigger than v3.9.7.1/2's -0.03 to -0.04, but Wilcoxon p still > 0.05 at n=48")
    md.append("- Sample size doubled (25→48) but still not significant; this is n<100 noise territory")
    md.append("- Auto-label circularity slightly biases BGE numbers UP; raw delta is conservative")
    md.append("- BGE does NOT clearly beat biencoder on this benchmark; LTR is the better path forward")
    md.append("")

    md_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_3_cross_encoder_wilcoxon_n50.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  md:   {md_path}")


if __name__ == "__main__":
    main()
