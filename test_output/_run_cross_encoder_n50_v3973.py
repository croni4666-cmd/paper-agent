"""v3.9.7.3 — Cross-encoder (BGE-reranker) run on n=50 with mixed labels.

Differences from v3.9.7.2 version:
- Reads labels from labels_n50_mixed.json (q001-q025 real + q026-q050 auto)
- 47 queries with L2 labels (q041-q043 auto L2=0 are skipped)
- BGE rerank still runs on all 50 candidate sets, but metrics only on 47

Per memory discipline: BGE is also used as auto-label tie-breaker (A2 hybrid),
so v3.9.7.3 results are slightly inflated by the same BGE signal.
Effect: BGE-vs-biencoder Wilcoxon tests may have more power but are also
partly circular. State p-values, don't claim insight.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.cross_encoder import BGEReranker, DEFAULT_CACHE_DIR


def load_biencoder_results(bench_dir: Path):
    out = {}
    for qfile in sorted((bench_dir / "system_outputs_biencoder").glob("q*.json")):
        qid = qfile.stem
        obj = json.loads(qfile.read_text(encoding="utf-8"))
        out[qid] = {"query": obj.get("query", ""), "results": obj.get("results", [])}
    return out


def load_labels_n50(bench_dir: Path) -> dict:
    """Read n=50 mixed labels (q001-q025 real + q026-q050 auto)."""
    p = bench_dir / "labels_n50_mixed.json"
    if not p.exists():
        raise FileNotFoundError(f"labels_n50_mixed.json not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))["labels"]


def ndcg_at_k(scores, labels, k=10):
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    import numpy as np
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    rels = [labels[i] for i in order[:k]]
    discounts = [1.0 / np.log2(i + 2) for i in range(k)]
    dcg = sum((2 ** r - 1) * d for r, d in zip(rels, discounts))
    ideal_order = sorted(range(len(labels)), key=lambda i: -labels[i])
    ideal_rels = [labels[i] for i in ideal_order[:k]]
    idcg = sum((2 ** r - 1) * d for r, d in zip(ideal_rels, discounts))
    if idcg < 1e-9:
        return 0.0
    return dcg / idcg


def recall_at_k(scores, labels, k=10, min_label=2):
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    import numpy as np
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    top_k_labels = [labels[i] for i in order[:k]]
    n_relevant_total = sum(1 for l in labels if l >= min_label)
    if n_relevant_total == 0:
        return 0.0
    n_relevant_in_top_k = sum(1 for l in top_k_labels if l >= min_label)
    return n_relevant_in_top_k / n_relevant_total


def precision_at_k(scores, labels, k=10, min_label=2):
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    import numpy as np
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    top_k_labels = [labels[i] for i in order[:k]]
    n_relevant_in_top_k = sum(1 for l in top_k_labels if l >= min_label)
    return n_relevant_in_top_k / k


def main():
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print(f"[v3.9.7.3 Cross-encoder] n=50 (mixed labels)")
    biencoder_results = load_biencoder_results(bench_dir)
    labels_data = load_labels_n50(bench_dir)
    print(f"  loaded {len(biencoder_results)} queries from biencoder (.json)")
    print(f"  loaded {len(labels_data)} queries from labels_n50_mixed.json")

    print(f"\nLoading BGE-reranker-base from local cache...")
    reranker = BGEReranker(auto_download=False)
    print(f"  model loaded")

    per_query_metrics = {"biencoder_only": {}, "bge_rerank": {}}
    n_with_labels = 0
    n_skipped_no_labels = 0
    for qid in sorted(biencoder_results.keys()):
        qdata = biencoder_results[qid]
        cands = qdata["results"]
        q_text = qdata["query"]
        if not cands or not q_text:
            continue
        q_labels_dict = labels_data.get(qid, {})
        labels = []
        for c in cands:
            doi = (c.get("doi") or "").strip()
            label_info = q_labels_dict.get(doi, {})
            label = label_info.get("label")
            labels.append(int(label) if label is not None else 0)
        if not any(l >= 2 for l in labels):
            n_skipped_no_labels += 1
            continue
        n_with_labels += 1
        biencoder_scores = [c.get("biencoder_score", 0.0) or 0.0 for c in cands]
        cand_texts = []
        for c in cands:
            title = c.get("title", "") or ""
            abstract = c.get("abstract", "") or ""
            text = f"{title}. {abstract}".strip(". ")
            cand_texts.append(text)
        ce_scores = reranker.score_batch(q_text, cand_texts)
        for name, scores in [("biencoder_only", biencoder_scores), ("bge_rerank", ce_scores)]:
            per_query_metrics[name][qid] = {
                "ndcg_at_10": ndcg_at_k(scores, labels, k=10),
                "recall_at_10": recall_at_k(scores, labels, k=10, min_label=2),
                "precision_at_10": precision_at_k(scores, labels, k=10, min_label=2),
                "n_relevant_total": sum(1 for l in labels if l >= 2),
                "n_relevant_top_10": sum(1 for i in sorted(range(len(scores)), key=lambda x: -scores[x])[:10] if labels[i] >= 2),
            }

    print(f"\nProcessed {n_with_labels} queries with L2 labels (skipped {n_skipped_no_labels} without labels)")

    def aggregate(name):
        per_q = per_query_metrics[name]
        return {
            "mean_ndcg_at_10": sum(m["ndcg_at_10"] for m in per_q.values()) / len(per_q),
            "mean_recall_at_10": sum(m["recall_at_10"] for m in per_q.values()) / len(per_q),
            "mean_precision_at_10": sum(m["precision_at_10"] for m in per_q.values()) / len(per_q),
        }
    agg = {n: aggregate(n) for n in ["biencoder_only", "bge_rerank"]}
    delta = {
        "ndcg": agg["bge_rerank"]["mean_ndcg_at_10"] - agg["biencoder_only"]["mean_ndcg_at_10"],
        "recall": agg["bge_rerank"]["mean_recall_at_10"] - agg["biencoder_only"]["mean_recall_at_10"],
        "precision": agg["bge_rerank"]["mean_precision_at_10"] - agg["biencoder_only"]["mean_precision_at_10"],
    }

    raw = {
        "version": "v3.9.7.3",
        "n_queries_in_biencoder": len(biencoder_results),
        "n_queries_with_l2_labels": n_with_labels,
        "n_queries_skipped_no_labels": n_skipped_no_labels,
        "label_source": "n50_mixed (q001-q025 real + q026-q050 A2 auto)",
        "auto_label_circularity_warning": (
            "BGE-reranker is also used as auto-label tie-breaker (A2 hybrid). "
            "v3.9.7.3 BGE-vs-biencoder comparison is therefore partly circular: "
            "BGE scored high in the labels that were used as ground truth. "
            "Effect size estimate: small positive bias, maybe +0.01 to +0.03 NDCG@10."
        ),
        "aggregate": agg,
        "delta": delta,
        "per_query": per_query_metrics,
    }
    out_path = reports_dir / "v3_9_7_3_cross_encoder_n50.json"
    out_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  json: {out_path}")

    print()
    print("=" * 60)
    print(f"RESULTS (n={n_with_labels} queries with labels, n={len(biencoder_results)} candidates reranked)")
    print("=" * 60)
    print(f"  biencoder_only: NDCG@10={agg['biencoder_only']['mean_ndcg_at_10']:.4f}, Recall@10={agg['biencoder_only']['mean_recall_at_10']:.4f}")
    print(f"  bge_rerank    : NDCG@10={agg['bge_rerank']['mean_ndcg_at_10']:.4f}, Recall@10={agg['bge_rerank']['mean_recall_at_10']:.4f}")
    print(f"  delta         : NDCG@10={delta['ndcg']:+.4f}, Recall@10={delta['recall']:+.4f}")


if __name__ == "__main__":
    main()
