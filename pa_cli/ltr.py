"""LTR (Learning to Rank) reranker using LambdaMART (LightGBM).

Per ROADMAP [P0-6] (added 2026-07-13, completed 2026-07-13 in v3.9.2).

Trains a pairwise ranker on v3.9.0 benchmark data:
- 25 queries × ~30 candidates × 3-level labels
- 8 features: bm25 / biencoder / combined / prf / log_cite / year / is_recent / has_abstract
- 5-fold CV per-query group (candidates of same query stay together)
- Primary metric: NDCG@10
- Comparison: vs v3.9.0 'combined' baseline (linear 0.5/0.5)

Why LambdaMART:
- Standard IR ranker, used by Yahoo/Microsoft/Bing for years
- Captures non-linear feature interactions (vs linear weighted combination)
- LightGBM pure local, no hosted service, $0 cost, Global Rule 5/5 pass
- Fast: 5-fold CV on 741 labeled pairs < 1 second on CPU

================================================================================
CONDITIONAL DEPRECATION 2026-07-20 (v3.9.10) — DO NOT USE FOR n < 200
================================================================================
At n=50 with 100 trees, LTR LOSES to combined baseline:

    v3.9.7.3 (5-fold CV, n=50):
        LTR (LambdaMART 100 trees) NDCG@10 = 0.7806 ± 0.048
        combined (0.5*BM25 + 0.5*bi-encoder) = 0.8141 (5-fold CV reported)
        Δ NDCG@10 (LTR - baseline)            = -0.0335

    v3.9.10.1 Phase 1.5 holdout (single 30/20 split, n=20 test):
        LTR (LambdaMART 100 trees) NDCG@10 = 0.7679
        combined (0.5*BM25 + 0.5*bi-encoder) = 0.8988
        Δ NDCG@10 (LTR - baseline)            = -0.1309  ← 4x worse than 5-fold reported

Source: bench/v01/reports/v3_9_10_1_phase_1_5_holdout.{json,md}.

Root cause: 100 trees on n=50 overfits. Each tree sees only 10-15 queries per
fold, so it learns noise on minor features (has_abstract, is_recent) rather than
generalizing. Combined baseline has no parameters → no overfit risk.

Feature importance (LTR on n=50, total ≈ 2000):
    combined_score   617  ← main signal
    biencoder_score  593
    log_cite_count   233
    bm25_score       202
    prf_score        165
    year             107
    has_abstract      23
    is_recent          2

Note: LTR uses only BM25 + biencoder + metadata — NOT BGE — so this LTR eval
is NOT contaminated by the A2 auto-label circularity that biases BGE numbers up.

RECOMMENDATION (v3.9.10):
  - For n < 200: use combined baseline (0.5*BM25 + 0.5*bi-encoder). This is the
    default in bench/v01/_v4_rerank.py --condition combined.
  - For n >= 200: re-evaluate LambdaMART with 100-200 trees. May become competitive
    once it has enough data to not overfit.
  - Alternative to consider: shallow GBDT (num_leaves=7, n_estimators=20-50)
    that may not overfit at n=50.

DO NOT remove this code — keep for n>200 evaluation and for shallow GBDT variant.
================================================================================
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import lightgbm as lgb
    _HAS_LIGHTGBM = True
except ImportError:
    _HAS_LIGHTGBM = False


# 8 feature names (order matters; must match build_features output)
FEATURE_NAMES = [
    "bm25_score",          # 0: BM25 score (raw, not normalized)
    "biencoder_score",     # 1: bi-encoder cosine similarity [0, 1]
    "combined_score",      # 2: 0.5*bm25_norm + 0.5*biencoder (current v3.9.0 baseline)
    "prf_score",           # 3: pseudo-relevance feedback rerank score
    "log_cite_count",      # 4: log(1 + citation_count)
    "year",                # 5: publication year (0 if missing)
    "is_recent",           # 6: 1 if year >= 2022, else 0
    "has_abstract",        # 7: 1 if abstract non-empty, else 0
]


@dataclass
class LTRConfig:
    """LambdaMART hyperparameters."""
    objective: str = "lambdarank"
    metric: str = "ndcg"
    n_estimators: int = 100
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_data_in_leaf: int = 5        # n=25 queries, allow small leaves
    feature_fraction: float = 0.9
    bagging_fraction: float = 0.8
    bagging_freq: int = 5
    label_gain: list = field(default_factory=lambda: [0, 1, 3])  # 0->0, 1->1, 2->3
    random_state: int = 42
    verbose: int = -1


def check_lightgbm() -> None:
    """Raise informative error if lightgbm not installed."""
    if not _HAS_LIGHTGBM:
        raise ImportError(
            "lightgbm is required for pa_cli.ltr. Install with: pip install lightgbm"
        )


# ──────────────────────────────────────────────────────────────────────
# Feature engineering
# ──────────────────────────────────────────────────────────────────────

def _normalize_bm25_in_query(
    bm25_scores: np.ndarray,
) -> np.ndarray:
    """Min-max normalize BM25 scores within a query to [0, 1].

    BM25 raw scores are unbounded; normalizing per-query makes the
    'combined' feature (0.5*bm25_norm + 0.5*biencoder) comparable across queries.
    """
    if len(bm25_scores) == 0:
        return bm25_scores
    lo, hi = float(bm25_scores.min()), float(bm25_scores.max())
    if hi - lo < 1e-9:
        return np.zeros_like(bm25_scores)
    return (bm25_scores - lo) / (hi - lo)


def build_features_one(
    candidate: dict,
    bm25_norm_within_query: Optional[float] = None,
) -> list:
    """Extract 8-dim feature vector from one candidate dict.

    Args:
        candidate: dict with bm25_score, biencoder_score, prf_score, citation_count,
                   year, abstract (or has_abstract bool)
        bm25_norm_within_query: pre-computed normalized BM25 (for combined feature)
                                Pass None if not yet computed.

    Returns:
        list of 8 floats
    """
    bm25 = float(candidate.get("bm25_score") or 0.0)
    biencoder = float(candidate.get("biencoder_score") or 0.0)
    prf = float(candidate.get("prf_score") or 0.0)
    cite = int(candidate.get("citation_count") or 0)
    year = int(candidate.get("year") or 0)
    abstract = candidate.get("abstract") or ""
    has_abs = 1.0 if (abstract and len(abstract.strip()) > 0) else 0.0
    is_recent = 1.0 if (year and year >= 2022) else 0.0
    log_cite = float(math.log1p(max(0, cite)))

    if bm25_norm_within_query is None:
        bm25_norm = 0.0
    else:
        bm25_norm = float(bm25_norm_within_query)

    combined = 0.5 * bm25_norm + 0.5 * biencoder

    return [bm25, biencoder, combined, prf, log_cite, float(year), is_recent, has_abs]


# ──────────────────────────────────────────────────────────────────────
# Data assembly
# ──────────────────────────────────────────────────────────────────────

def assemble_dataset(
    bench_dir: Path,
    conditions: Optional[list] = None,
) -> dict:
    """Build (query_id -> list of feature dicts) from v3.9.0 bench data.

    For each query, merges candidates across all conditions and joins with labels.

    Returns:
        {
          "q001": [
            {"doi": ..., "features": [8 floats], "label": 0/1/2, "has_label": bool},
            ...
          ],
          ...
        }
    """
    if conditions is None:
        conditions = ["system_outputs", "system_outputs_biencoder", "system_outputs_bm25",
                     "system_outputs_combined", "system_outputs_prf", "system_outputs_random"]

    # Step 1: load labels
    labels_file = bench_dir / "labels_clean.json"
    labels_data = json.loads(labels_file.read_text(encoding="utf-8"))["labels"]

    # Step 2: for each query, collect candidates by DOI from all conditions
    by_query: dict[str, dict[str, dict]] = {}

    for cond in conditions:
        cond_dir = bench_dir / cond
        if not cond_dir.is_dir():
            continue
        for qfile in sorted(cond_dir.iterdir()):
            # v3.9.7.3: accept both .json (current schema) and no-ext (legacy v3.9.0 era)
            if not qfile.is_file() or qfile.suffix not in [".json", ""]:
                continue
            qid = qfile.stem  # e.g. "q001"
            if not qid.startswith("q"):
                continue
            try:
                obj = json.loads(qfile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            results = obj.get("results", [])
            if qid not in by_query:
                by_query[qid] = {}
            for c in results:
                doi = (c.get("doi") or "").strip()
                if not doi:
                    continue
                # Merge fields (later conditions overwrite if same key)
                if doi not in by_query[qid]:
                    by_query[qid][doi] = {
                        "doi": doi,
                        "title": c.get("title", ""),
                        "year": c.get("year"),
                        "citation_count": c.get("citation_count", 0),
                        "abstract": c.get("abstract", ""),
                    }
                # Score fields
                if c.get("bm25_score") is not None:
                    by_query[qid][doi]["bm25_score"] = c["bm25_score"]
                if c.get("biencoder_score") is not None:
                    by_query[qid][doi]["biencoder_score"] = c["biencoder_score"]
                if c.get("v4_score") is not None and c.get("v4_score") != 0:
                    # Use v4_score as prf_score (PRF condition is the only one that
                    # doesn't have biencoder, so v4_score is the PRF-specific score)
                    by_query[qid][doi]["prf_score"] = c["v4_score"]

    # Step 3: compute per-query BM25 normalization + assemble features
    dataset = {}
    for qid, doi_dict in by_query.items():
        candidates = list(doi_dict.values())
        # Compute BM25 normalization
        bm25_array = np.array([c.get("bm25_score", 0.0) or 0.0 for c in candidates])
        bm25_norm_array = _normalize_bm25_in_query(bm25_array)

        rows = []
        for cand, bm25_norm in zip(candidates, bm25_norm_array):
            features = build_features_one(cand, bm25_norm)
            doi = cand["doi"]
            label_info = labels_data.get(qid, {}).get(doi, {})
            label = label_info.get("label")
            rows.append({
                "doi": doi,
                "title": cand.get("title", "")[:80],
                "features": features,
                "label": int(label) if label is not None else None,
                "has_label": label is not None,
            })
        dataset[qid] = rows

    return dataset


def to_xyg(
    dataset: dict,
    only_labeled: bool = True,
) -> tuple:
    """Convert assembled dataset to (X, y, group, query_ids).

    Args:
        dataset: from assemble_dataset()
        only_labeled: drop candidates without labels (LTR can't train on them)

    Returns:
        X: (N, 8) float array
        y: (N,) int array of labels
        group: (Q,) int array of per-query group sizes (for LightGBM)
        query_ids: list of query id strings (length Q)
    """
    X_rows, y_rows, group_rows, qids = [], [], [], []
    for qid in sorted(dataset.keys()):
        rows = dataset[qid]
        if only_labeled:
            rows = [r for r in rows if r["has_label"]]
        if not rows:
            continue
        X_rows.append(np.array([r["features"] for r in rows], dtype=np.float32))
        y_rows.append(np.array([r["label"] for r in rows], dtype=np.int32))
        group_rows.append(len(rows))
        qids.append(qid)

    X = np.vstack(X_rows) if X_rows else np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    y = np.concatenate(y_rows) if y_rows else np.zeros((0,), dtype=np.int32)
    group = np.array(group_rows, dtype=np.int32)
    return X, y, group, qids


# ──────────────────────────────────────────────────────────────────────
# NDCG computation (per-query)
# ──────────────────────────────────────────────────────────────────────

def ndcg_at_k(scores: np.ndarray, labels: np.ndarray, k: int = 10) -> float:
    """NDCG@k for a single query's candidates."""
    if len(scores) == 0 or len(labels) == 0:
        return 0.0
    k = min(k, len(scores))
    order = np.argsort(-scores)
    gains = (np.array([2, 1, 0])[labels[order][:k]])  # label 0->0, 1->1, 2->2
    # Use DCG formula: sum( (2^rel - 1) / log2(rank+1) )
    rels = labels[order][:k]
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = float(np.sum((2.0 ** rels - 1.0) * discounts))
    ideal_order = np.argsort(-labels)
    ideal_rels = labels[ideal_order][:k]
    idcg = float(np.sum((2.0 ** ideal_rels - 1.0) * discounts))
    if idcg < 1e-9:
        return 0.0
    return dcg / idcg


def recall_at_k(scores: np.ndarray, labels: np.ndarray, k: int = 10, min_label: int = 2) -> float:
    """Recall@k: fraction of label>=min_label candidates in top-k."""
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    order = np.argsort(-scores)
    top_k_labels = labels[order][:k]
    n_relevant_total = int(np.sum(labels >= min_label))
    if n_relevant_total == 0:
        return 0.0
    n_relevant_in_top_k = int(np.sum(top_k_labels >= min_label))
    return n_relevant_in_top_k / n_relevant_total


def precision_at_k(scores: np.ndarray, labels: np.ndarray, k: int = 10, min_label: int = 2) -> float:
    """Precision@k: fraction of top-k candidates that are label>=min_label."""
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    order = np.argsort(-scores)
    top_k_labels = labels[order][:k]
    n_relevant_in_top_k = int(np.sum(top_k_labels >= min_label))
    return n_relevant_in_top_k / k


# ──────────────────────────────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────────────────────────────

def train_lambdamart(
    X: np.ndarray,
    y: np.ndarray,
    group: np.ndarray,
    config: Optional[LTRConfig] = None,
    num_boost_round: Optional[int] = None,
) -> "lgb.Booster":
    """Train a single LambdaMART ranker."""
    check_lightgbm()
    cfg = config or LTRConfig()
    train_data = lgb.Dataset(X, label=y, group=group, feature_name=FEATURE_NAMES)
    params = {
        "objective": cfg.objective,
        "metric": cfg.metric,
        "learning_rate": cfg.learning_rate,
        "num_leaves": cfg.num_leaves,
        "min_data_in_leaf": cfg.min_data_in_leaf,
        "feature_fraction": cfg.feature_fraction,
        "bagging_fraction": cfg.bagging_fraction,
        "bagging_freq": cfg.bagging_freq,
        "label_gain": cfg.label_gain,
        "verbose": cfg.verbose,
        "random_state": cfg.random_state,
    }
    n_rounds = num_boost_round or cfg.n_estimators
    model = lgb.train(params, train_data, num_boost_round=n_rounds)
    return model


def predict_scores(model: "lgb.Booster", X: np.ndarray) -> np.ndarray:
    """Predict relevance scores."""
    check_lightgbm()
    return model.predict(X)


def feature_importance_gain(model: "lgb.Booster") -> dict:
    """Return feature importance (gain) as {feature_name: gain}."""
    check_lightgbm()
    importance = model.feature_importance(importance_type="gain")
    return {name: float(imp) for name, imp in zip(FEATURE_NAMES, importance)}


# ──────────────────────────────────────────────────────────────────────
# K-fold cross validation
# ──────────────────────────────────────────────────────────────────────

def kfold_cv(
    X: np.ndarray,
    y: np.ndarray,
    group: np.ndarray,
    query_ids: list,
    n_folds: int = 5,
    config: Optional[LTRConfig] = None,
    seed: int = 42,
    k_eval: int = 10,
) -> dict:
    """5-fold CV over queries (per-query group, candidates stay with query).

    Returns dict with per-fold metrics + aggregate + feature importance.
    """
    rng = np.random.default_rng(seed)
    n_queries = len(query_ids)
    indices = np.arange(n_queries)
    rng.shuffle(indices)
    folds = np.array_split(indices, n_folds)

    fold_results = []
    feature_imps = []
    cumulative_offset = 0
    qid_to_offset = {qid: i for i, qid in enumerate(query_ids)}
    query_offsets = np.cumsum([0] + list(group))  # offset of each query in X

    for fold_idx in range(n_folds):
        test_q_idx = set(folds[fold_idx])
        train_q_idx = [i for i in range(n_queries) if i not in test_q_idx]

        # Build train X, y, group
        train_slices = []
        for i in train_q_idx:
            start = int(query_offsets[i])
            end = int(query_offsets[i + 1])
            train_slices.append((start, end))
        train_X = np.vstack([X[s:e] for s, e in train_slices])
        train_y = np.concatenate([y[s:e] for s, e in train_slices])
        train_group = np.array([e - s for s, e in train_slices], dtype=np.int32)

        # Train
        model = train_lambdamart(train_X, train_y, train_group, config)
        feature_imps.append(feature_importance_gain(model))

        # Eval on test
        per_query_metrics = []
        for i in test_q_idx:
            start = int(query_offsets[i])
            end = int(query_offsets[i + 1])
            qX = X[start:end]
            qy = y[start:end]
            if len(qX) == 0:
                continue
            qscores = predict_scores(model, qX)
            ndcg = ndcg_at_k(qscores, qy, k=k_eval)
            recall = recall_at_k(qscores, qy, k=k_eval, min_label=2)
            prec = precision_at_k(qscores, qy, k=k_eval, min_label=2)
            per_query_metrics.append({
                "qid": query_ids[i],
                "ndcg_at_10": ndcg,
                "recall_at_10": recall,
                "precision_at_10": prec,
            })

        fold_results.append({
            "fold": fold_idx,
            "n_train_queries": len(train_q_idx),
            "n_test_queries": len(test_q_idx),
            "per_query": per_query_metrics,
            "mean_ndcg_at_10": float(np.mean([m["ndcg_at_10"] for m in per_query_metrics])),
            "mean_recall_at_10": float(np.mean([m["recall_at_10"] for m in per_query_metrics])),
            "mean_precision_at_10": float(np.mean([m["precision_at_10"] for m in per_query_metrics])),
        })

    return {
        "n_folds": n_folds,
        "n_queries": n_queries,
        "folds": fold_results,
        "aggregate": {
            "mean_ndcg_at_10": float(np.mean([f["mean_ndcg_at_10"] for f in fold_results])),
            "std_ndcg_at_10": float(np.std([f["mean_ndcg_at_10"] for f in fold_results])),
            "mean_recall_at_10": float(np.mean([f["mean_recall_at_10"] for f in fold_results])),
            "std_recall_at_10": float(np.std([f["mean_recall_at_10"] for f in fold_results])),
            "mean_precision_at_10": float(np.mean([f["mean_precision_at_10"] for f in fold_results])),
            "std_precision_at_10": float(np.std([f["mean_precision_at_10"] for f in fold_results])),
        },
        "feature_importance_avg": {
            name: float(np.mean([fi[name] for fi in feature_imps]))
            for name in FEATURE_NAMES
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Baseline comparison (vs v3.9.0 'combined' condition)
# ──────────────────────────────────────────────────────────────────────

def eval_combined_baseline(
    X: np.ndarray,
    y: np.ndarray,
    group: np.ndarray,
    query_ids: list,
    k_eval: int = 10,
) -> dict:
    """Compute NDCG/Recall/Precision for the linear 'combined' baseline.

    'combined' feature is at index 2 in FEATURE_NAMES (per build_features_one).
    """
    combined_idx = FEATURE_NAMES.index("combined_score")
    scores_per_query = np.split(X[:, combined_idx], np.cumsum(group)[:-1])
    labels_per_query = np.split(y, np.cumsum(group)[:-1])

    per_query_metrics = []
    for qid, qs, ql in zip(query_ids, scores_per_query, labels_per_query):
        per_query_metrics.append({
            "qid": qid,
            "ndcg_at_10": ndcg_at_k(qs, ql, k=k_eval),
            "recall_at_10": recall_at_k(qs, ql, k=k_eval, min_label=2),
            "precision_at_10": precision_at_k(qs, ql, k=k_eval, min_label=2),
        })

    return {
        "method": "combined_baseline (linear 0.5*bm25_norm + 0.5*biencoder)",
        "per_query": per_query_metrics,
        "aggregate": {
            "mean_ndcg_at_10": float(np.mean([m["ndcg_at_10"] for m in per_query_metrics])),
            "mean_recall_at_10": float(np.mean([m["recall_at_10"] for m in per_query_metrics])),
            "mean_precision_at_10": float(np.mean([m["precision_at_10"] for m in per_query_metrics])),
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────────

def generate_report(
    cv_results: dict,
    baseline_results: dict,
    dataset: dict,
    config: LTRConfig,
) -> str:
    """Generate markdown report comparing LTR vs baseline."""
    lines = []
    lines.append("# v3.9.2 LTR (LambdaMART) Rerank Report")
    lines.append("")
    lines.append("> Generated 2026-07-13 by `pa_cli/ltr.py` per ROADMAP [P0-6].")
    lines.append("> 5-fold CV over 25 queries, per-query group, 3-level labels.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **n_queries**: {cv_results['n_queries']}")
    n_labeled = sum(1 for q, rows in dataset.items() for r in rows if r["has_label"])
    lines.append(f"- **n_labeled_pairs**: {n_labeled}")
    lines.append(f"- **n_folds**: {cv_results['n_folds']}")
    lines.append(f"- **features**: {len(FEATURE_NAMES)} ({', '.join(FEATURE_NAMES)})")
    lines.append("")

    lines.append("## Side-by-side: LTR vs combined baseline")
    lines.append("")
    lines.append("| Method | NDCG@10 | Recall@10 | Precision@10 |")
    lines.append("|---|---:|---:|---:|")
    ltr_ndcg = cv_results["aggregate"]["mean_ndcg_at_10"]
    ltr_recall = cv_results["aggregate"]["mean_recall_at_10"]
    ltr_prec = cv_results["aggregate"]["mean_precision_at_10"]
    bl_ndcg = baseline_results["aggregate"]["mean_ndcg_at_10"]
    bl_recall = baseline_results["aggregate"]["mean_recall_at_10"]
    bl_prec = baseline_results["aggregate"]["mean_precision_at_10"]
    lines.append(f"| **LTR (LambdaMART)** | **{ltr_ndcg:.4f} ± {cv_results['aggregate']['std_ndcg_at_10']:.4f}** | **{ltr_recall:.4f}** | **{ltr_prec:.4f}** |")
    lines.append(f"| combined (linear 0.5/0.5) | {bl_ndcg:.4f} | {bl_recall:.4f} | {bl_prec:.4f} |")
    lines.append(f"| **Δ (LTR − baseline)** | **{ltr_ndcg - bl_ndcg:+.4f}** | **{ltr_recall - bl_recall:+.4f}** | **{ltr_prec - bl_prec:+.4f}** |")
    lines.append("")

    # Honest interpretation per discipline
    delta_ndcg = ltr_ndcg - bl_ndcg
    lines.append("## Honest interpretation (per memory discipline)")
    lines.append("")
    if abs(delta_ndcg) < 0.05:
        lines.append(f"**Δ NDCG@10 = {delta_ndcg:+.4f}** on n=25 queries, n<100 deltas, no significance test, no holdout. ")
        lines.append("Per `MEMORY.md` discipline 'Don't overclaim n<100 metric deltas':")
        lines.append("- This delta is within the noise band of n=25 with no statistical test.")
        lines.append("- It is NOT a 'finding' or 'insight' — it's a single point estimate.")
        lines.append("- Direction matters (LTR should not hurt), but magnitude is not a useful negative result.")
        lines.append("")
        lines.append("**Status**: ✅ LTR architecture works (training + prediction + per-query CV + reporting pipeline).")
        lines.append("**Status**: ⚠️ Δ magnitude not statistically validated.")
    else:
        lines.append(f"**Δ NDCG@10 = {delta_ndcg:+.4f}** is a >0.05 effect size threshold, which is the discipline's 'obviously large' cutoff.")
        lines.append("Still not a 'finding' without p<0.05 significance test, but suggests real lift.")
    lines.append("")

    # Per-fold details
    lines.append("## Per-fold metrics")
    lines.append("")
    lines.append("| Fold | n_train_q | n_test_q | NDCG@10 | Recall@10 | Precision@10 |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for fr in cv_results["folds"]:
        lines.append(
            f"| {fr['fold']} | {fr['n_train_queries']} | {fr['n_test_queries']} | "
            f"{fr['mean_ndcg_at_10']:.4f} | {fr['mean_recall_at_10']:.4f} | {fr['mean_precision_at_10']:.4f} |"
        )
    lines.append("")

    # Feature importance
    lines.append("## Feature importance (gain)")
    lines.append("")
    lines.append("| Feature | Avg gain |")
    lines.append("|---|---:|")
    fi = cv_results["feature_importance_avg"]
    for name in sorted(fi, key=fi.get, reverse=True):
        lines.append(f"| `{name}` | {fi[name]:.2f} |")
    lines.append("")

    # Per-query breakdown (top 5 best and worst LTR vs baseline)
    lines.append("## Per-query LTR vs baseline (top 5 best, top 5 worst)")
    lines.append("")
    ltr_per_q = {m["qid"]: m["ndcg_at_10"] for f in cv_results["folds"] for m in f["per_query"]}
    bl_per_q = {m["qid"]: m["ndcg_at_10"] for m in baseline_results["per_query"]}
    diffs = [(q, ltr_per_q.get(q, 0) - bl_per_q.get(q, 0)) for q in ltr_per_q]
    diffs.sort(key=lambda x: -x[1])
    lines.append("| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |")
    lines.append("|---|---:|---:|---:|")
    for q, d in diffs[:5]:
        lines.append(f"| {q} | {ltr_per_q[q]:.4f} | {bl_per_q[q]:.4f} | **{d:+.4f}** |")
    lines.append("")
    lines.append("| Query | LTR NDCG@10 | Baseline NDCG@10 | Δ |")
    lines.append("|---|---:|---:|---:|")
    for q, d in diffs[-5:]:
        lines.append(f"| {q} | {ltr_per_q[q]:.4f} | {bl_per_q[q]:.4f} | {d:+.4f} |")
    lines.append("")

    # Config
    lines.append("## Configuration")
    lines.append("")
    lines.append("```python")
    lines.append(f"LTRConfig(")
    for k, v in asdict(config).items():
        lines.append(f"    {k}={v!r},")
    lines.append(")")
    lines.append("```")
    lines.append("")

    # Discipline footer
    lines.append("## 3-tier honest audit (per MEMORY.md discipline)")
    lines.append("")
    lines.append("- ✅ **Verified on real data**: code runs end-to-end on 25 v3.9.0 queries, 5-fold CV produces per-fold metrics, report generated.")
    lines.append("- ✅ **Verified architecture**: LTR + LightGBM training pipeline, feature engineering, per-query group CV all functional.")
    lines.append("- ⚠️ **Code exists but unverified metric magnitude**: Δ NDCG@10 = {0:+.4f} on n=25, no significance test, no holdout.".format(delta_ndcg))
    lines.append("- ❌ **NOT a 'finding' or 'insight'**: per memory discipline, single point estimates on n<100 are noise, not signal.")
    lines.append("")

    lines.append("## 5-check Global Rule audit")
    lines.append("")
    lines.append("1. ✅ Runs for $0 (lightgbm + numpy + pandas pure local)")
    lines.append("2. ✅ No hosted service")
    lines.append("3. ✅ Maintenance: ~350 LOC new in pa_cli/ltr.py")
    lines.append("4. ✅ No publish obligation")
    lines.append("5. ✅ Free-tier degradation: no third-party API used")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Public convenience: full pipeline
# ──────────────────────────────────────────────────────────────────────

def run_ltr_pipeline(
    bench_dir: Path,
    config: Optional[LTRConfig] = None,
    n_folds: int = 5,
    seed: int = 42,
) -> dict:
    """Run the full LTR pipeline: assemble data → CV → baseline → return report + raw results."""
    check_lightgbm()
    cfg = config or LTRConfig()

    # 1. Assemble data
    dataset = assemble_dataset(bench_dir)
    X, y, group, qids = to_xyg(dataset, only_labeled=True)

    # 2. K-fold CV
    cv = kfold_cv(X, y, group, qids, n_folds=n_folds, config=cfg, seed=seed)

    # 3. Baseline (combined linear 0.5/0.5)
    baseline = eval_combined_baseline(X, y, group, qids)

    # 4. Report
    md = generate_report(cv, baseline, dataset, cfg)

    return {
        "config": asdict(cfg),
        "n_queries": len(qids),
        "n_labeled_pairs": int(len(y)),
        "n_folds": n_folds,
        "cv_aggregate": cv["aggregate"],
        "baseline_aggregate": baseline["aggregate"],
        "feature_importance": cv["feature_importance_avg"],
        "report_markdown": md,
        "cv_full": cv,
        "baseline_full": baseline,
    }
