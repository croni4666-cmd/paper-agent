"""[P0-8] LTR re-fit with 12 features -- fast version (pre-warm OpenAlex cache).

ASCII-only output (GBK-safe on Windows console).
OpenAlex venue cache is saved to ._openalex_cache.json for fast re-runs.
"""
import json
import sys
import time
import math
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, '.')

from pa_cli.ltr import (
    FEATURE_NAMES, LTRConfig, ndcg_at_k, recall_at_k, precision_at_k,
    build_features_one, _normalize_bm25_in_query, check_lightgbm,
)
from pa_cli.deep_rerank import compute_fulltext_features, _openalex_venue_prestige
import pa_cli.deep_rerank as dr

check_lightgbm()
import lightgbm as lgb

BENCH = Path("bench/v01")
SYSTEM_OUT = BENCH / "system_outputs_combined"
LABELS_FILE = BENCH / "labels_clean.json"
CACHE_FILE = BENCH / "_openalex_venue_cache.json"


def load_venue_cache() -> int:
    """Load cached OpenAlex venue prestige lookups from disk. Returns count loaded."""
    if not CACHE_FILE.exists():
        return 0
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        dr._VENUE_PRESTIGE_CACHE.update(data)
        return len(data)
    except Exception as e:
        print(f"  [WARN] Failed to load venue cache: {e}")
        return 0


def save_venue_cache() -> int:
    """Persist current OpenAlex venue cache to disk. Returns count saved."""
    try:
        CACHE_FILE.write_text(
            json.dumps(dr._VENUE_PRESTIGE_CACHE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(dr._VENUE_PRESTIGE_CACHE)
    except Exception as e:
        print(f"  [WARN] Failed to save venue cache: {e}")
        return 0

# Pre-warm OpenAlex cache with short timeout to avoid hangs
_orig_openalex = dr._openalex_venue_prestige


def _fast_openalex(venue_name: str) -> float:
    """OpenAlex with 2s timeout, returns 0 on any failure (fast path)."""
    if not venue_name or not venue_name.strip():
        return 0.0
    v = venue_name.strip()
    if v in dr._VENUE_PRESTIGE_CACHE:
        return dr._VENUE_PRESTIGE_CACHE[v]
    try:
        import requests
        url = f"https://api.openalex.org/sources?search={requests.utils.quote(v)}&per_page=1"
        r = requests.get(url, timeout=2, headers={"User-Agent": "paper-agent/3.9.10.12 (Mavis)"})
        r.raise_for_status()
        data = r.json()
        if not data.get("results"):
            dr._VENUE_PRESTIGE_CACHE[v] = 0.0
            return 0.0
        top = data["results"][0]
        works_count = top.get("works_count", 0) or 0
        cited_by_count = top.get("cited_by_count", 0) or 0
        import math as m
        volume_score = m.sqrt(min(works_count, 1_000_000) / 1_000_000)
        impact_score = m.sqrt(min(cited_by_count, 100_000_000) / 100_000_000)
        prestige = round(0.5 * volume_score + 0.5 * impact_score, 4)
        dr._VENUE_PRESTIGE_CACHE[v] = prestige
        return prestige
    except Exception:
        dr._VENUE_PRESTIGE_CACHE[v] = 0.0
        return 0.0


# Monkey-patch deep_rerank to use fast version
dr._openalex_venue_prestige = _fast_openalex

FEATURE_NAMES_12 = FEATURE_NAMES + [
    "fulltext_bm25",
    "fulltext_cross_encoder",
    "fulltext_citation_density",
    "fulltext_venue_score",
]


def estimate_page_count(abstract: str) -> int:
    if not abstract:
        return 10
    return max(5, len(abstract.split()) // 250 + 5)


def build_features_12(candidate: dict, query_text: str, bm25_norm: Optional[float] = None) -> list:
    base = build_features_one(candidate, bm25_norm)
    abstract = candidate.get("abstract") or ""
    page_count = estimate_page_count(abstract)
    ft = compute_fulltext_features(
        query=query_text, fulltext=None, abstract=abstract,
        citation_count=int(candidate.get("citation_count") or 0),
        year=candidate.get("year"), page_count=page_count,
        venue=candidate.get("venue") or "",
    )
    return base + [
        ft.get("fulltext_bm25", 0.0),
        ft.get("fulltext_cross_encoder", 0.0),
        ft.get("fulltext_citation_density", 0.0),
        ft.get("fulltext_venue_score", 0.0),
    ]


def assemble(bench_dir: Path) -> dict:
    """Build 12-feature dataset, with pre-warmed OpenAlex cache."""
    labels_data = json.loads((bench_dir / "labels_clean.json").read_text(encoding="utf-8-sig"))["labels"]
    by_query = {}
    for qfile in sorted((bench_dir / "system_outputs_combined").glob("q*.json")):
        qid = qfile.stem
        if qid not in labels_data:
            continue
        obj = json.loads(qfile.read_text(encoding="utf-8-sig"))
        query_text = obj.get("query", "")
        results = obj.get("results", [])
        if qid not in by_query:
            by_query[qid] = {}
        for c in results:
            doi = (c.get("doi") or "").strip()
            if not doi:
                continue
            if doi not in by_query[qid]:
                by_query[qid][doi] = {
                    "doi": doi, "title": c.get("title", ""),
                    "year": c.get("year"),
                    "citation_count": c.get("cited_by_count", 0),
                    "abstract": c.get("abstract", ""),
                    "venue": c.get("venue", ""),
                    "query_text": query_text,
                }
            if c.get("bm25_score") is not None:
                by_query[qid][doi]["bm25_score"] = c["bm25_score"]
            if c.get("biencoder_score") is not None:
                by_query[qid][doi]["biencoder_score"] = c["biencoder_score"]
            if c.get("v4_score") is not None and c.get("v4_score") != 0:
                by_query[qid][doi]["prf_score"] = c["v4_score"]

    # Pre-warm OpenAlex cache for unique venues
    unique_venues = set()
    for cands in by_query.values():
        for c in cands.values():
            v = (c.get("venue") or "").strip()
            if v:
                unique_venues.add(v)
    cached = load_venue_cache()
    remaining = sum(1 for v in unique_venues if v not in dr._VENUE_PRESTIGE_CACHE)
    print(f"  Pre-warm: {len(unique_venues)} unique venues, {cached} cached, {remaining} to fetch")
    t0 = time.time()
    for i, v in enumerate(sorted(unique_venues), 1):
        if v in dr._VENUE_PRESTIGE_CACHE:
            continue
        _fast_openalex(v)
        if i % 20 == 0:
            print(f"    {i}/{len(unique_venues)} cached in {time.time()-t0:.0f}s")
    print(f"  Pre-warm done in {time.time()-t0:.0f}s (total cache: {len(dr._VENUE_PRESTIGE_CACHE)})")
    save_venue_cache()

    # Build features
    dataset = {}
    for qid, doi_dict in by_query.items():
        candidates = list(doi_dict.values())
        bm25_array = np.array([c.get("bm25_score", 0.0) or 0.0 for c in candidates])
        bm25_norm_array = _normalize_bm25_in_query(bm25_array)
        rows = []
        for cand, bm25_norm in zip(candidates, bm25_norm_array):
            features = build_features_12(cand, cand["query_text"], bm25_norm)
            doi = cand["doi"]
            label_info = labels_data.get(qid, {}).get(doi, {})
            label = label_info.get("label")
            rows.append({
                "doi": doi, "title": cand.get("title", "")[:80],
                "features": features,
                "label": int(label) if label is not None else None,
                "has_label": label is not None,
            })
        dataset[qid] = rows
    return dataset


def to_xyg(dataset, n_feat):
    X_rows, y_rows, g_rows, qids = [], [], [], []
    for qid in sorted(dataset.keys()):
        rows = [r for r in dataset[qid] if r["has_label"]]
        if not rows:
            continue
        X_rows.append(np.array([r["features"] for r in rows], dtype=np.float32))
        y_rows.append(np.array([r["label"] for r in rows], dtype=np.int32))
        g_rows.append(len(rows))
        qids.append(qid)
    X = np.vstack(X_rows) if X_rows else np.zeros((0, n_feat), dtype=np.float32)
    y = np.concatenate(y_rows) if y_rows else np.zeros((0,), dtype=np.int32)
    return X, y, np.array(g_rows, dtype=np.int32), qids


def kfold(X, y, group, qids, n_folds=5, seed=42, k_eval=10, n_feat=12, n_est=50):
    rng = np.random.default_rng(seed)
    n_q = len(qids)
    indices = np.arange(n_q)
    rng.shuffle(indices)
    folds = np.array_split(indices, n_folds)
    q_offsets = np.cumsum([0] + list(group))
    fold_results = []
    f_imps = []
    for fi in range(n_folds):
        test_q = set(folds[fi])
        train_q = [i for i in range(n_q) if i not in test_q]
        train_slices = [(int(q_offsets[i]), int(q_offsets[i+1])) for i in train_q]
        train_X = np.vstack([X[s:e] for s, e in train_slices])
        train_y = np.concatenate([y[s:e] for s, e in train_slices])
        train_g = np.array([e - s for s, e in train_slices], dtype=np.int32)
        train_data = lgb.Dataset(train_X, label=train_y, group=train_g,
                                  feature_name=FEATURE_NAMES_12[:n_feat])
        params = {"objective": "lambdarank", "metric": "ndcg", "learning_rate": 0.05,
                  "num_leaves": 7, "min_data_in_leaf": 3,
                  "feature_fraction": 0.9, "bagging_fraction": 0.8, "bagging_freq": 5,
                  "label_gain": [0, 1, 3], "verbose": -1, "random_state": 42}
        model = lgb.train(params, train_data, num_boost_round=n_est)
        importance = model.feature_importance(importance_type="gain")
        f_imps.append({n: float(v) for n, v in zip(FEATURE_NAMES_12[:n_feat], importance)})
        per_q = []
        for i in test_q:
            s, e = int(q_offsets[i]), int(q_offsets[i+1])
            qX, qy = X[s:e], y[s:e]
            if len(qX) == 0:
                continue
            qs = model.predict(qX)
            per_q.append({"qid": qids[i], "ndcg_at_10": ndcg_at_k(qs, qy, k=k_eval),
                          "recall_at_10": recall_at_k(qs, qy, k=k_eval, min_label=2),
                          "precision_at_10": precision_at_k(qs, qy, k=k_eval, min_label=2)})
        fold_results.append({"fold": fi, "n_train": len(train_q), "n_test": len(test_q),
                            "per_query": per_q,
                            "mean_ndcg_at_10": float(np.mean([m["ndcg_at_10"] for m in per_q])),
                            "mean_recall_at_10": float(np.mean([m["recall_at_10"] for m in per_q])),
                            "mean_precision_at_10": float(np.mean([m["precision_at_10"] for m in per_q]))})
    return {
        "n_queries": n_q, "folds": fold_results,
        "aggregate": {
            "mean_ndcg_at_10": float(np.mean([f["mean_ndcg_at_10"] for f in fold_results])),
            "std_ndcg_at_10": float(np.std([f["mean_ndcg_at_10"] for f in fold_results])),
            "mean_recall_at_10": float(np.mean([f["mean_recall_at_10"] for f in fold_results])),
            "mean_precision_at_10": float(np.mean([f["mean_precision_at_10"] for f in fold_results])),
        },
        "feature_importance_avg": {n: float(np.mean([fi[n] for fi in f_imps]))
                                    for n in FEATURE_NAMES_12[:n_feat]},
    }


def combined_baseline(X, y, group, qids, k_eval=10):
    combined_idx = FEATURE_NAMES.index("combined_score")
    scores = np.split(X[:, combined_idx], np.cumsum(group)[:-1])
    labels = np.split(y, np.cumsum(group)[:-1])
    per_q = []
    for qid, qs, ql in zip(qids, scores, labels):
        per_q.append({"qid": qid, "ndcg_at_10": ndcg_at_k(qs, ql, k=k_eval),
                      "recall_at_10": recall_at_k(qs, ql, k=k_eval, min_label=2),
                      "precision_at_10": precision_at_k(qs, ql, k=k_eval, min_label=2)})
    return {
        "per_query": per_q,
        "aggregate": {
            "mean_ndcg_at_10": float(np.mean([m["ndcg_at_10"] for m in per_q])),
            "mean_recall_at_10": float(np.mean([m["recall_at_10"] for m in per_q])),
            "mean_precision_at_10": float(np.mean([m["precision_at_10"] for m in per_q])),
        },
    }


def main():
    t0 = time.time()
    print("[P0-8] Building 12-feature dataset (with OpenAlex pre-warm)...")
    dataset = assemble(BENCH)
    n_q = len(dataset)
    n_lab = sum(1 for q, rows in dataset.items() for r in rows if r["has_label"])
    print(f"  n_queries: {n_q}, n_labeled: {n_lab}")

    X12, y12, g12, qids12 = to_xyg(dataset, 12)
    print(f"  X12 shape: {X12.shape}")

    print("\n[P0-8] 12-feature LTR...")
    cv12 = kfold(X12, y12, g12, qids12, n_feat=12)
    ndcg_12 = cv12['aggregate']['mean_ndcg_at_10']
    std_12 = cv12['aggregate']['std_ndcg_at_10']
    recall_12 = cv12['aggregate']['mean_recall_at_10']
    prec_12 = cv12['aggregate']['mean_precision_at_10']
    print(f"  NDCG@10 = {ndcg_12:.4f} +/- {std_12:.4f}")

    print("\n[P0-8] 8-feature LTR (baseline)...")
    X8 = X12[:, :8]
    cv8 = kfold(X8, y12, g12, qids12, n_feat=8)
    ndcg_8 = cv8['aggregate']['mean_ndcg_at_10']
    std_8 = cv8['aggregate']['std_ndcg_at_10']
    recall_8 = cv8['aggregate']['mean_recall_at_10']
    prec_8 = cv8['aggregate']['mean_precision_at_10']
    print(f"  NDCG@10 = {ndcg_8:.4f} +/- {std_8:.4f}")

    print("\n[P0-8] combined baseline (0.5/0.5)...")
    bl = combined_baseline(X12, y12, g12, qids12)
    ndcg_bl = bl['aggregate']['mean_ndcg_at_10']
    recall_bl = bl['aggregate']['mean_recall_at_10']
    prec_bl = bl['aggregate']['mean_precision_at_10']
    print(f"  NDCG@10 = {ndcg_bl:.4f}")

    print()
    print("=" * 78)
    print(f"  [P0-8] Final: 12-feature LTR vs 8-feature LTR vs combined (n={n_q})")
    print("=" * 78)
    print(f"  {'Method':30s} {'NDCG@10':>12s} {'Recall@10':>12s} {'Prec@10':>12s}")
    print(f"  {'combined baseline':30s} {ndcg_bl:12.4f} {recall_bl:12.4f} {prec_bl:12.4f}")
    print(f"  {'LTR 8 features':30s} {ndcg_8:12.4f} {recall_8:12.4f} {prec_8:12.4f}")
    print(f"  {'LTR 12 features (NEW)':30s} {ndcg_12:12.4f} {recall_12:12.4f} {prec_12:12.4f}")
    print()
    print(f"  d (12-feat - 8-feat)   NDCG@10:  {ndcg_12 - ndcg_8:+.4f}  (std_diff ~ {abs(std_12-std_8):.4f})")
    print(f"  d (12-feat - baseline) NDCG@10: {ndcg_12 - ndcg_bl:+.4f}")
    print(f"  d (8-feat - baseline)  NDCG@10: {ndcg_8 - ndcg_bl:+.4f}")
    print()
    fi = cv12['feature_importance_avg']
    print("  Feature importance (12-feature LTR, gain):")
    for name in sorted(fi, key=fi.get, reverse=True):
        print(f"    {name:30s} {fi[name]:.2f}")
    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.0f}s")

    # Honest verdict
    print()
    print("  === 3-tier honest verdict ===")
    if ndcg_12 > ndcg_8 + 0.01:
        print(f"  [PASS] 12-feature LTR beats 8-feature by {ndcg_12 - ndcg_8:+.4f} (>0.01 noise threshold)")
    elif ndcg_12 < ndcg_8 - 0.01:
        print(f"  [FAIL] 12-feature LTR worse than 8-feature by {ndcg_12 - ndcg_8:+.4f}")
    else:
        print(f"  [NEUTRAL] 12-feature LTR ~ 8-feature ({ndcg_12 - ndcg_8:+.4f}, within noise)")

    if abs(ndcg_12 - ndcg_bl) < 0.05:
        print(f"  [NEUTRAL] NDCG@10 diff to combined baseline {ndcg_12 - ndcg_bl:+.4f} (within +/-0.05 noise)")
    if n_q < 100:
        print(f"  [WARN] n={n_q} < 100 -- per memory discipline, deltas are noise not signal")

    # Save
    out = {
        "version": "v3.9.10.12-p0-8-12features",
        "n_queries": n_q, "n_labeled": n_lab, "n_estimators": 50,
        "combined_baseline": {"ndcg_at_10": ndcg_bl, "recall_at_10": recall_bl, "precision_at_10": prec_bl},
        "ltr_8_features": {"ndcg_at_10": ndcg_8, "std_ndcg_at_10": std_8,
                            "recall_at_10": recall_8, "precision_at_10": prec_8},
        "ltr_12_features": {"ndcg_at_10": ndcg_12, "std_ndcg_at_10": std_12,
                             "recall_at_10": recall_12, "precision_at_10": prec_12},
        "delta_12_vs_8_ndcg": ndcg_12 - ndcg_8,
        "delta_12_vs_baseline_ndcg": ndcg_12 - ndcg_bl,
        "delta_8_vs_baseline_ndcg": ndcg_8 - ndcg_bl,
        "feature_importance_12": cv12['feature_importance_avg'],
        "elapsed_seconds": elapsed,
        "folds_12": [{"fold": f["fold"], "n_train": f["n_train"], "n_test": f["n_test"],
                       "mean_ndcg_at_10": f["mean_ndcg_at_10"],
                       "mean_recall_at_10": f["mean_recall_at_10"],
                       "mean_precision_at_10": f["mean_precision_at_10"]} for f in cv12['folds']],
        "folds_8": [{"fold": f["fold"], "n_train": f["n_train"], "n_test": f["n_test"],
                      "mean_ndcg_at_10": f["mean_ndcg_at_10"]} for f in cv8['folds']],
    }
    out_path = BENCH / "reports" / "v3_9_10_12_p0_8_12features_ltr.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
