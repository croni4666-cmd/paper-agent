"""[P0-7.1] Wilcoxon signed-rank test on v3.9.3 cross-encoder per-query NDCG@10.

Reuses v3.9.3 cross-encoder JSON (25 paired queries, biencoder vs BGE-rerank).

Per MEMORY.md discipline: n<100 metric deltas = noise, not finding.
Need a paired non-parametric test to claim 'significant'.

H0: median(bge_ndcg - biencoder_ndcg) = 0
H1: median(bge_ndcg - biencoder_ndcg) ≠ 0 (two-sided)
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

    json_path = ROOT / "bench" / "v01" / "reports" / "v3_9_3_cross_encoder.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))

    per_query = data["per_query"]
    biencoder = per_query["biencoder_only"]
    bge = per_query["bge_rerank"]

    qids = sorted(biencoder.keys())
    assert len(qids) == 25, f"expected 25 queries, got {len(qids)}"

    # Paired NDCG@10
    bi_ndcg = [biencoder[q]["ndcg_at_10"] for q in qids]
    bge_ndcg = [bge[q]["ndcg_at_10"] for q in qids]
    ndcg_diff = [b - a for a, b in zip(bi_ndcg, bge_ndcg)]

    # Paired Recall@10
    bi_recall = [biencoder[q]["recall_at_10"] for q in qids]
    bge_recall = [bge[q]["recall_at_10"] for q in qids]
    recall_diff = [b - a for a, b in zip(bi_recall, bge_recall)]

    # Paired Precision@10
    bi_prec = [biencoder[q]["precision_at_10"] for q in qids]
    bge_prec = [bge[q]["precision_at_10"] for q in qids]
    prec_diff = [b - a for a, b in zip(bi_prec, bge_prec)]

    print("=" * 78)
    print("Wilcoxon signed-rank test (two-sided) on per-query metrics, n=25")
    print("=" * 78)
    print()
    print("H0: median(BGE - biencoder) = 0")
    print("H1: median(BGE - biencoder) != 0")
    print()

    for label, bi_arr, bge_arr, diff in [
        ("NDCG@10", bi_ndcg, bge_ndcg, ndcg_diff),
        ("Recall@10", bi_recall, bge_recall, recall_diff),
        ("Precision@10", bi_prec, bge_prec, prec_diff),
    ]:
        # Wilcoxon requires non-zero diffs
        nonzero_diffs = [d for d in diff if abs(d) > 1e-9]
        n_zero = len(diff) - len(nonzero_diffs)
        if len(nonzero_diffs) < 5:
            print(f"\n{label}: too few non-zero diffs ({len(nonzero_diffs)}) — test skipped")
            continue
        try:
            # zero_method='wilcox' drops zero diffs (default)
            # alternative='two-sided' default
            stat, p = wilcoxon(nonzero_diffs, alternative="two-sided")
        except ValueError as e:
            print(f"\n{label}: Wilcoxon error: {e}")
            continue
        median_diff = float(sorted(nonzero_diffs)[len(nonzero_diffs) // 2])
        n_pos = sum(1 for d in nonzero_diffs if d > 0)
        n_neg = sum(1 for d in nonzero_diffs if d < 0)
        mean_bi = sum(bi_arr) / len(bi_arr)
        mean_bge = sum(bge_arr) / len(bge_arr)
        print(f"\n{label} (n_paired={len(diff)}, n_zero={n_zero}, n_pos={n_pos}, n_neg={n_neg}):")
        print(f"  Mean biencoder:  {mean_bi:.4f}")
        print(f"  Mean BGE-rerank: {mean_bge:.4f}")
        print(f"  Mean diff:       {(mean_bge - mean_bi):+.4f}")
        print(f"  Median non-zero diff: {median_diff:+.4f}")
        print(f"  Wilcoxon statistic:  {stat:.2f}")
        print(f"  p-value (two-sided): {p:.4f}")
        if p < 0.001:
            sig = "*** (p<0.001)"
        elif p < 0.01:
            sig = "** (p<0.01)"
        elif p < 0.05:
            sig = "* (p<0.05)"
        else:
            sig = "n.s. (p≥0.05)"
        print(f"  Significance: {sig}")
        print(f"  Honest verdict: {'BGE effect is statistically distinguishable from noise' if p < 0.05 else 'Cannot reject H0 — observed Δ consistent with random noise on n=25'}")

    # Per-query breakdown
    print()
    print("=" * 78)
    print("Per-query NDCG@10 breakdown (sorted by absolute difference)")
    print("=" * 78)
    qid_diffs = [(q, biencoder[q]["ndcg_at_10"], bge[q]["ndcg_at_10"]) for q in qids]
    qid_diffs.sort(key=lambda x: abs(x[2] - x[1]), reverse=True)
    print(f"  {'qid':6s} {'biencoder':>12s} {'BGE':>12s} {'Δ':>8s}  {'verdict'}")
    for q, bi, bge_val in qid_diffs[:15]:
        delta = bge_val - bi
        verdict = "BGE wins" if delta > 0.05 else ("BGE loses" if delta < -0.05 else "tie")
        print(f"  {q:6s} {bi:>12.4f} {bge_val:>12.4f} {delta:>+8.4f}  {verdict}")
    print(f"  ... ({len(qid_diffs) - 15} more queries)")

    # Effect size: matched-pairs rank-biserial correlation
    # r = 1 - 2W / (n*(n+1)/2) where W is Wilcoxon T (sum of signed ranks)
    print()
    print("=" * 78)
    print("Honest effect-size estimate (matched-pairs rank-biserial correlation)")
    print("=" * 78)
    import math
    for label, diff in [("NDCG@10", ndcg_diff), ("Recall@10", recall_diff), ("Precision@10", prec_diff)]:
        nonzero = [d for d in diff if abs(d) > 1e-9]
        n = len(nonzero)
        if n < 5:
            continue
        ranks = sorted(range(n), key=lambda i: abs(nonzero[i]))
        abs_ranks = [abs(nonzero[i]) for i in ranks]
        # Compute signed ranks: rank with sign
        signed_ranks = []
        for i, idx in enumerate(ranks):
            sign = 1 if nonzero[idx] > 0 else -1
            # handle ties (use mid-rank)
            signed_ranks.append(sign * (i + 1))
        W_pos = sum(r for r in signed_ranks if r > 0)
        W_neg = -sum(r for r in signed_ranks if r < 0)
        # Rank-biserial r = (W_pos - W_neg) / (W_pos + W_neg) = (sum of signed ranks) / (sum of abs ranks)
        r_rb = sum(signed_ranks) / sum(abs(r) for r in signed_ranks) if sum(abs(r) for r in signed_ranks) > 0 else 0
        print(f"  {label}: r_rb = {r_rb:+.4f}  (|r|>0.3 = medium effect, |r|>0.5 = large)")

    # Save result
    out = {
        "n_queries": 25,
        "metrics": {
            "ndcg": {"mean_biencoder": sum(bi_ndcg) / 25, "mean_bge": sum(bge_ndcg) / 25,
                     "mean_diff": sum(ndcg_diff) / 25},
            "recall": {"mean_biencoder": sum(bi_recall) / 25, "mean_bge": sum(bge_recall) / 25,
                       "mean_diff": sum(recall_diff) / 25},
            "precision": {"mean_biencoder": sum(bi_prec) / 25, "mean_bge": sum(bge_prec) / 25,
                          "mean_diff": sum(prec_diff) / 25},
        },
        "wilcoxon_two_sided": {},
        "per_query_ndcg": {q: {"biencoder": biencoder[q]["ndcg_at_10"],
                                "bge": bge[q]["ndcg_at_10"],
                                "delta": bge[q]["ndcg_at_10"] - biencoder[q]["ndcg_at_10"]}
                            for q in qids},
    }
    for label, diff in [("ndcg", ndcg_diff), ("recall", recall_diff), ("precision", prec_diff)]:
        nonzero = [d for d in diff if abs(d) > 1e-9]
        n = len(nonzero)
        if n < 5:
            continue
        stat, p = wilcoxon(nonzero, alternative="two-sided")
        out["wilcoxon_two_sided"][label] = {
            "n_paired": 25,
            "n_nonzero": n,
            "statistic": float(stat),
            "p_value": float(p),
        }
    out_path = ROOT / "bench" / "v01" / "reports" / "v3_9_7_1_cross_encoder_wilcoxon.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
