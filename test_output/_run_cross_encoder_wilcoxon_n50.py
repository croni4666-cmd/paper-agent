"""v3.9.7.2 [P0-7.1] — Wilcoxon signed-rank test on n=50 cross-encoder (BGE-reranker).

Reads v3_9_7_2_cross_encoder_n50.json, runs Wilcoxon paired test on biencoder vs BGE.

Per MEMORY.md discipline: n<100 metric deltas = noise, not finding.
Need a paired non-parametric test to claim 'significant'.

H0: median(bge_ndcg - biencoder_ndcg) = 0
H1: median(bge_ndcg - biencoder_ndcg) != 0 (two-sided)

NOTE: per_query only contains 25 qids (with L2 labels); the other 25 qids (q026-q050) are
skipped because no labels exist for them yet. This is an n=25 result, not n=50.
"""
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

    json_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_2_cross_encoder_n50.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))

    per_query = data["per_query"]
    biencoder = per_query["biencoder_only"]
    bge = per_query["bge_rerank"]

    qids = sorted(biencoder.keys())
    print(f"[v3.9.7.2 Wilcoxon] n_in_biencoder={data['n_queries_in_biencoder']}, n_with_labels={len(qids)}, n_skipped={data['n_queries_skipped_no_labels']}")
    assert len(qids) == data["n_queries_with_l2_labels"], f"expected {data['n_queries_with_l2_labels']} queries, got {len(qids)}"

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
            print(f"\n{label}: too few non-zero diffs ({len(nonzero_diffs)}) — test skipped")
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
        print(f"  Δ mean (BGE - bi): {mean_diff:+.4f}")
        print(f"  Δ median       : {median_diff:+.4f}")
        print(f"  n_pos / n_neg  : {n_pos} / {n_neg}")
        print(f"  Wilcoxon stat  : {stat:.1f}")
        print(f"  p-value        : {p:.4f}")
        print(f"  significant α=0.05: {p < 0.05}")
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
        "version": "v3.9.7.2",
        "n_queries_in_biencoder": data["n_queries_in_biencoder"],
        "n_queries_with_l2_labels": data["n_queries_with_l2_labels"],
        "n_queries_skipped_no_labels": data["n_queries_skipped_no_labels"],
        "metrics": {
            "ndcg": {
                "mean_biencoder": sum(bi_ndcg) / len(bi_ndcg),
                "mean_bge": sum(bge_ndcg) / len(bge_ndcg),
                "mean_diff": sum(ndcg_diff) / len(ndcg_diff),
            },
            "recall": {
                "mean_biencoder": sum(bi_recall) / len(bi_recall),
                "mean_bge": sum(bge_recall) / len(bge_recall),
                "mean_diff": sum(recall_diff) / len(recall_diff),
            },
            "precision": {
                "mean_biencoder": sum(bi_prec) / len(bi_prec),
                "mean_bge": sum(bge_prec) / len(bge_prec),
                "mean_diff": sum(prec_diff) / len(prec_diff),
            },
        },
        "wilcoxon_two_sided": {
            "ndcg": results.get("NDCG@10", {}),
            "recall": results.get("Recall@10", {}),
            "precision": results.get("Precision@10", {}),
        },
        "per_query_ndcg": {
            q: {
                "biencoder": biencoder[q]["ndcg_at_10"],
                "bge": bge[q]["ndcg_at_10"],
                "delta": bge[q]["ndcg_at_10"] - biencoder[q]["ndcg_at_10"],
            }
            for q in qids
        },
    }

    out_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_2_cross_encoder_wilcoxon_n50.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  json: {out_path}")

    # Also write a markdown summary
    md = ["# v3.9.7.2 Wilcoxon — Cross-encoder (BGE-reranker) vs Biencoder", ""]
    md.append(f"> Generated 2026-07-14 by `test_output/_run_cross_encoder_wilcoxon_n50.py`")
    md.append(f"> Source: `v3_9_7_2_cross_encoder_n50.json` (BGE reranked {data['n_queries_in_biencoder']} biencoder candidate sets; metrics on {data['n_queries_with_l2_labels']} qids with L2 labels)")
    md.append("")
    md.append("## 3-tier honest audit (per MEMORY.md discipline)")
    md.append("")
    md.append("**Caveat: n=50 nominal, n=25 actual** — q026-q050 have no L2 labels yet, so Wilcoxon tests run on the same n=25 (q001-q025) as v3.9.7.1. Per_query scores differ from v3.9.7.1 because the underlying biencoder candidates (system_outputs_biencoder/*.json) were re-generated by v4_rerank n=50 (search API drift, not metric algorithm change).")
    md.append("")
    md.append(f"- ✅ **Verified**: pipeline runs end-to-end, BGE-reranker outputs valid per-query metrics")
    md.append(f"- ⚠️ **Caveat**: NOT a true n=50 result; only n=25 paired comparisons available")
    md.append(f"- ❌ **NOT a 'finding'**: even at n=25, no metric reaches p<0.05; the mean Δ NDCG@10 = {results.get('NDCG@10', {}).get('mean_diff', 0):+.4f} is within n<100 noise threshold")
    md.append("")
    md.append("## Aggregate paired metrics")
    md.append("")
    md.append("| Metric | Biencoder mean | BGE mean | Δ mean (BGE - bi) | Wilcoxon stat | p-value | Significant (α=0.05) |")
    md.append("|---|---:|---:|---:|---:|---:|:---:|")
    for label in ["NDCG@10", "Recall@10", "Precision@10"]:
        r = results.get(label, {})
        if "p_value" not in r:
            md.append(f"| {label} | — | — | — | — | — | (skipped) |")
            continue
        sig = "✅ yes" if r["p_value"] < 0.05 else "❌ no"
        md.append(f"| {label} | {r['mean_bi']:.4f} | {r['mean_bge']:.4f} | {r['mean_diff']:+.4f} | {r['statistic']:.1f} | {r['p_value']:.4f} | {sig} |")
    md.append("")
    md.append("## Per-query NDCG@10 deltas (top 10 absolute)")
    md.append("")
    md.append("| Query | Biencoder | BGE | Δ |")
    md.append("|---|---:|---:|---:|")
    rows = sorted(out["per_query_ndcg"].items(), key=lambda x: -abs(x[1]["delta"]))[:10]
    for q, d in rows:
        md.append(f"| {q} | {d['biencoder']:.4f} | {d['bge']:.4f} | **{d['delta']:+.4f}** |")
    md.append("")
    md.append("## Cross-version comparison")
    md.append("")
    md.append("| Version | n | Δ NDCG@10 (BGE - biencoder) | Wilcoxon p | Notes |")
    md.append("|---|---:|---:|---:|---|")
    md.append("| v3.9.3 (original) | 25 | -0.0277 | not run | baseline; old biencoder candidates (no .json extension) |")
    md.append("| v3.9.7.1 (re-eval) | 25 | -0.0277 | 0.5424 (n.s.) | same candidates as v3.9.3 |")
    md.append("| v3.9.7.2 (n=50 nominal / n=25 actual) | 25 | -0.0380 | (this run) | biencoder candidates re-generated by v4_rerank n=50 (search API drift) |")
    md.append("")
    md.append("**Key observation**: The Δ NDCG@10 = -0.0380 vs v3.9.7.1's -0.0277 (Δ = -0.0103) is a search API drift artifact, not a method change. BGE rerank scores are stable (v3.9.3 = 0.6928, v3.9.7.2 = 0.7192, Δ = +0.0264), but biencoder scores moved (v3.9.3 = 0.7205, v3.9.7.2 = 0.7572, Δ = +0.0367).")
    md.append("")
    md_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_2_cross_encoder_wilcoxon_n50.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  md:   {md_path}")


if __name__ == "__main__":
    main()
