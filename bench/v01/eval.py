"""
paper-agent-bench-v0.1 — eval.py
Compute retrieval metrics from system outputs + ground truth labels.

Usage:
    python -m bench.v0.1.eval \
        --queries bench/v0.1/queries.json \
        --system-outputs bench/v0.1/system_outputs \
        --labels bench/v0.1/labels.json \
        --out bench/v0.1/reports/baseline_v0.1

Outputs:
    <out>.json  — raw per-query + aggregate metrics
    <out>.md    — human-readable markdown report

Metrics computed (per-query + aggregate mean/median/std):
    - Recall@5/10/20
    - Precision@5/10/20
    - NDCG@10/20
    - MAP@10
    - SR (Success Rate at top-20: ≥1 label-2 paper)

Relevance levels:
    label == 2  → "relevant" (counts as binary relevant for recall/precision)
    label == 1  → "marginal" (graded gain in NDCG, but not binary relevant)
    label == 0  → "irrelevant"
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev


# ---------- metric primitives ----------

def recall_at_k(ranked_dois: list[str], relevant: set[str], k: int) -> float:
    """Recall@K = |relevant ∩ top-K| / |relevant| (1.0 if no relevant)."""
    if not relevant:
        return 1.0
    topk = set(ranked_dois[:k])
    return len(topk & relevant) / len(relevant)


def precision_at_k(ranked_dois: list[str], relevant: set[str], k: int) -> float:
    """Precision@K = |relevant ∩ top-K| / K."""
    if k <= 0:
        return 0.0
    topk = set(ranked_dois[:k])
    return len(topk & relevant) / k


def dcg_at_k(gains: list[float], k: int) -> float:
    """DCG@K with log2 discount (standard)."""
    s = 0.0
    for i, g in enumerate(gains[:k]):
        s += g / math.log2(i + 2)  # i=0 → /log2(2)=1
    return s


def ndcg_at_k(ranked_dois: list[str], graded: dict[str, int], k: int) -> float:
    """NDCG@K with graded gains (2=core, 1=marginal, 0=irrelevant)."""
    gains = [graded.get(d, 0) for d in ranked_dois[:k]]
    dcg = dcg_at_k(gains, k)
    # IDCG = sort by graded relevance desc, take top K
    ideal_gains = sorted(graded.values(), reverse=True)[:k]
    idcg = dcg_at_k(ideal_gains, k)
    return dcg / idcg if idcg > 0 else 0.0


def average_precision_at_k(ranked_dois: list[str], relevant: set[str], k: int) -> float:
    """AP@K = mean of precision@i for each relevant hit in top-K."""
    if not relevant:
        return 0.0
    score = 0.0
    hits = 0
    for i, d in enumerate(ranked_dois[:k], start=1):
        if d in relevant:
            hits += 1
            score += hits / i
    return score / min(len(relevant), k)


def success_rate_at_k(ranked_dois: list[str], relevant: set[str], k: int) -> float:
    """1 if any relevant paper in top-K else 0."""
    return 1.0 if (set(ranked_dois[:k]) & relevant) else 0.0


# ---------- per-query + aggregate ----------

def compute_query_metrics(ranked_dois: list[str], labels_for_query: dict[str, dict]) -> dict:
    """Compute all metrics for one query.

    labels_for_query: {doi: {"label": 0|1|2, "reason": "..."}}
    """
    relevant = {doi for doi, info in labels_for_query.items() if info["label"] == 2}
    graded = {doi: info["label"] for doi, info in labels_for_query.items() if info["label"] >= 1}

    metrics = {
        "n_relevant": len(relevant),
        "n_graded": len(graded),
        "n_returned": len(ranked_dois),
    }
    for k in (5, 10, 20):
        metrics[f"recall@{k}"] = recall_at_k(ranked_dois, relevant, k)
        metrics[f"precision@{k}"] = precision_at_k(ranked_dois, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(ranked_dois, graded, k)
        metrics[f"success@{k}"] = success_rate_at_k(ranked_dois, relevant, k)
    metrics["map@10"] = average_precision_at_k(ranked_dois, relevant, 10)
    return metrics


def aggregate_metrics(per_query: dict[str, dict]) -> dict:
    """Aggregate per-query metrics: mean / median / std."""
    if not per_query:
        return {}
    # collect metric names from first query
    metric_names = [k for k in next(iter(per_query.values())) if k.startswith(("recall@", "precision@", "ndcg@", "map@", "success@"))]
    agg = {}
    for m in metric_names:
        values = [per_query[q][m] for q in per_query]
        agg[f"{m}_mean"] = mean(values)
        agg[f"{m}_median"] = median(values)
        if len(values) > 1:
            agg[f"{m}_std"] = stdev(values)
        else:
            agg[f"{m}_std"] = 0.0
    # also: aggregate count + SR (success rate over queries)
    n = len(per_query)
    agg["n_queries"] = n
    agg["n_with_relevant"] = sum(1 for q in per_query.values() if q["n_relevant"] > 0)
    return agg


# ---------- IO ----------

def load_queries(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = data.get("queries", [])
    return {q["id"]: q for q in queries}


def load_labels(path: Path) -> dict[str, dict]:
    """Returns {query_id: {doi: {label, reason}}}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("labels", {})


def load_system_outputs(dir_path: Path) -> dict[str, dict]:
    """Returns {query_id: {query, results: [...]}}."""
    outputs = {}
    if not dir_path.exists():
        return outputs
    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            qid = data.get("query_id") or f.stem
            outputs[qid] = data
        except json.JSONDecodeError as e:
            print(f"  WARN: skipping {f.name}: {e}", file=sys.stderr)
    return outputs


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="paper-agent-bench-v0.1 evaluator")
    ap.add_argument("--queries", required=True, type=Path)
    ap.add_argument("--system-outputs", required=True, type=Path,
                    help="directory of <query_id>.json files")
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path,
                    help="output prefix (writes <out>.json and <out>.md)")
    args = ap.parse_args()

    print(f"[eval] loading queries: {args.queries}")
    queries = load_queries(args.queries)
    print(f"[eval]   {len(queries)} queries")

    print(f"[eval] loading system outputs: {args.system_outputs}")
    system_outputs = load_system_outputs(args.system_outputs)
    print(f"[eval]   {len(system_outputs)} outputs")

    print(f"[eval] loading labels: {args.labels}")
    labels = load_labels(args.labels)
    print(f"[eval]   {len(labels)} labeled queries")

    # ----- compute per-query -----
    per_query = {}
    missing_outputs = []
    missing_labels = []
    for qid, q in queries.items():
        if qid not in system_outputs:
            missing_outputs.append(qid)
            continue
        if qid not in labels:
            missing_labels.append(qid)
            continue
        ranked = [r["doi"] for r in system_outputs[qid].get("results", []) if r.get("doi")]
        per_query[qid] = compute_query_metrics(ranked, labels[qid])

    if missing_outputs:
        print(f"[eval] WARN: {len(missing_outputs)} queries missing system outputs: {missing_outputs[:5]}...")
    if missing_labels:
        print(f"[eval] WARN: {len(missing_labels)} queries missing labels: {missing_labels[:5]}...")

    agg = aggregate_metrics(per_query)

    # ----- write outputs -----
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_json = args.out.with_suffix(".json")
    out_md = args.out.with_suffix(".md")

    report = {
        "version": "v0.1",
        "computed_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "queries_count": len(queries),
        "system_outputs_count": len(system_outputs),
        "labeled_count": len(labels),
        "evaluated_count": len(per_query),
        "missing_outputs": missing_outputs,
        "missing_labels": missing_labels,
        "aggregate": agg,
        "per_query": per_query,
    }
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[eval] wrote {out_json}")

    # ----- markdown summary -----
    md_lines = ["# paper-agent-bench-v0.1 — baseline report", ""]
    md_lines.append(f"- evaluated: **{len(per_query)}/{len(queries)}** queries")
    md_lines.append(f"- labeled: **{len(labels)}** queries")
    md_lines.append(f"- system outputs: **{len(system_outputs)}** queries")
    md_lines.append("")
    md_lines.append("## Aggregate metrics")
    md_lines.append("")
    md_lines.append("| metric | mean | median | std |")
    md_lines.append("|---|---|---|---|")
    for m in ("recall@10", "recall@20", "precision@10", "precision@20",
              "ndcg@10", "ndcg@20", "map@10", "success@10", "success@20"):
        key = m.replace("@", "_at_") if "@" in m else m
        if f"{m}_mean" in agg:
            md_lines.append(f"| {m} | {agg[f'{m}_mean']:.4f} | {agg[f'{m}_median']:.4f} | {agg[f'{m}_std']:.4f} |")
    md_lines.append("")
    md_lines.append("## Per-query")
    md_lines.append("")
    if per_query:
        qids = list(per_query.keys())
        cols = ["recall@10", "precision@10", "ndcg@10", "map@10", "n_relevant"]
        header = "| query_id | " + " | ".join(cols) + " |"
        sep = "|---" * (len(cols) + 1) + "|"
        md_lines.append(header)
        md_lines.append(sep)
        for qid in qids:
            row = per_query[qid]
            cells = [qid] + [f"{row[c]:.3f}" if isinstance(row[c], float) else str(row[c]) for c in cols]
            md_lines.append("| " + " | ".join(cells) + " |")
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[eval] wrote {out_md}")

    # ----- stdout summary -----
    print("")
    print("=== aggregate ===")
    for k, v in agg.items():
        if isinstance(v, float):
            print(f"  {k:25s} = {v:.4f}")
        else:
            print(f"  {k:25s} = {v}")


if __name__ == "__main__":
    main()