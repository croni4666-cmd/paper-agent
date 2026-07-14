"""v3.9.7.2 n=50 — Cross-encoder (BGE-reranker) run on n=50 candidates.

Reuses v3.9.3 architecture but:
- Reads from system_outputs_biencoder/*.json (50 files, n=50 candidate sets)
- Outputs v3_9_7_2_cross_encoder_n50.json with per-query metrics
- Used downstream by Wilcoxon test
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.cross_encoder import BGEReranker, DEFAULT_CACHE_DIR


def load_biencoder_results(bench_dir: Path):
    """Load biencoder-ranked candidates per query from v3.9.7.2 (n=50)."""
    out = {}
    for qfile in sorted((bench_dir / "system_outputs_biencoder").glob("q*.json")):
        qid = qfile.stem
        obj = json.loads(qfile.read_text(encoding="utf-8"))
        out[qid] = {
            "query": obj.get("query", ""),
            "results": obj.get("results", []),
        }
    return out


def load_labels(bench_dir: Path) -> dict:
    return json.loads((bench_dir / "labels_clean.json").read_text(encoding="utf-8"))["labels"]


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

    print(f"[v3.9.7.2 Cross-encoder] n=50 run")
    print(f"  bench_dir: {bench_dir}")
    print(f"  model: {DEFAULT_CACHE_DIR}")

    biencoder_results = load_biencoder_results(bench_dir)
    labels_data = load_labels(bench_dir)
    print(f"  loaded {len(biencoder_results)} queries from biencoder (.json)")
    print(f"  loaded {len(labels_data)} queries from labels_clean.json")

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
            # No L2 labels for this query — BGE rerank still computed but metrics meaningless
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
        "version": "v3.9.7.2",
        "n_queries_in_biencoder": len(biencoder_results),
        "n_queries_with_l2_labels": n_with_labels,
        "n_queries_skipped_no_labels": n_skipped_no_labels,
        "aggregate": agg,
        "delta": delta,
        "per_query": per_query_metrics,
    }
    out_path = reports_dir / "v3_9_7_2_cross_encoder_n50.json"
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
