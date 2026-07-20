"""Simpler rerank alternative — RidgeClassifier + LogisticRegression.

ROADMAP Tier 2 'Simpler rerank alternative':
  - RidgeClassifier / logistic regression on combined features (instead of
    LambdaMART) for 8-feature rerank. Effort: 4h.

Question: at n=50, do these shallow linear models beat LambdaMART 100 trees
(0.7679 single holdout) or combined baseline (0.8988 single holdout)?

Output: bench/v01/reports/v3_9_10_2_simpler_rerank.{json,md}
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.linear_model import RidgeClassifier, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold, train_test_split

repo_root = Path('.').resolve()
sys.path.insert(0, str(repo_root))

from pa_cli.ltr import (
    assemble_dataset, to_xyg, FEATURE_NAMES, ndcg_at_k, recall_at_k, precision_at_k
)

bench_dir = Path('bench/v01')

print('=' * 70)
print('Simpler rerank alternative (RidgeClassifier + LogisticRegression)')
print('Compare: LambdaMART 100 trees (0.7679) vs combined baseline (0.8988)')
print('=' * 70)

# ─── Build dataset ──────────────────────────────────────────────────────
# Same swap-as-v3.9.7.3 trick: temporarily replace labels_clean.json with n=50
labels_clean = bench_dir / 'labels_clean.json'
labels_n50 = bench_dir / 'labels_n50_mixed.json'
backup = labels_clean.with_suffix('.json.simpler_rerank_bak')
if not backup.exists():
    import shutil
    shutil.copy(labels_clean, backup)
    print(f'Backed up labels_clean.json → {backup}')

n50 = json.load(open(labels_n50, encoding='utf-8'))
swapped = {
    'version': 'v3.9.10.2-simpler-temp',
    'n_queries': 50,
    'labels': n50['labels'],
}
labels_clean.write_text(json.dumps(swapped, ensure_ascii=False, indent=2), encoding='utf-8')
print('Swapped labels_clean.json → n=50 mixed (will restore)')

try:
    dataset = assemble_dataset(bench_dir)
    X, y, group, qids = to_xyg(dataset, only_labeled=True)
    print(f'\nDataset: n_queries={len(qids)}, n_labeled_pairs={len(y)}')
    print(f'Features: {FEATURE_NAMES}')

    # ─── Single 30/20 holdout (matches Phase 1.5) ──────────────────────
    print('\n[1/3] Single 30/20 holdout split (seed=42, same as Phase 1.5)...')
    train_qids, test_qids = train_test_split(np.array(qids), test_size=20, random_state=42)
    test_qids_set = set(test_qids.tolist())
    train_qids_set = set(train_qids.tolist())
    print(f'  train n={len(train_qids)}, test n={len(test_qids)}')

    qid_to_idx = {q: i for i, q in enumerate(qids)}
    train_idx = [qid_to_idx[q] for q in qids if q in train_qids_set]
    test_idx = [qid_to_idx[q] for q in qids if q in test_qids_set]
    query_offsets = np.cumsum([0] + list(group))

    def build_train_test(X, y, group, train_idx, test_idx, query_offsets):
        Xt_parts, yt_parts, gt_parts = [], [], []
        Xe_parts, ye_parts, ge_parts = [], [], []
        for i in train_idx:
            s, e = int(query_offsets[i]), int(query_offsets[i+1])
            Xt_parts.append(X[s:e]); yt_parts.append(y[s:e]); gt_parts.append(group[i])
        for i in test_idx:
            s, e = int(query_offsets[i]), int(query_offsets[i+1])
            Xe_parts.append(X[s:e]); ye_parts.append(y[s:e]); ge_parts.append(group[i])
        return (
            np.vstack(Xt_parts), np.concatenate(yt_parts), np.array(gt_parts),
            np.vstack(Xe_parts), np.concatenate(ye_parts), np.array(ge_parts),
        )

    X_tr, y_tr, g_tr, X_te, y_te, g_te = build_train_test(X, y, group, train_idx, test_idx, query_offsets)

    # Standardize features (important for linear models)
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    # Per-query eval
    def per_query_ndcg(model, X_te_s, y_te, g_te):
        """Use class-2 score (highest relevance) for ranking. Both predict_proba
        and decision_function return shape (n_samples, n_classes); we want the
        score for the highest-relevance class to rank candidates by relevance."""
        if hasattr(model, 'predict_proba'):
            # Find class 2 column index (sklearn may sort classes)
            cls2_idx = list(model.classes_).index(2)
            scores = model.predict_proba(X_te_s)[:, cls2_idx]  # P(class=2)
        elif hasattr(model, 'decision_function'):
            # RidgeClassifier: use decision_function for class 2
            if hasattr(model, 'classes_'):
                cls2_idx = list(model.classes_).index(2)
            else:
                cls2_idx = -1  # fallback: last class column
            scores = model.decision_function(X_te_s)[:, cls2_idx]
        else:
            scores = model.predict(X_te_s)
        per_q = []
        offset = 0
        for q_idx, g in enumerate(g_te):
            qscores = scores[offset:offset+g]
            qy = y_te[offset:offset+g]
            offset += g
            if len(qscores) == 0:
                continue
            per_q.append({
                'ndcg_at_10': float(ndcg_at_k(qscores, qy, k=10)),
                'recall_at_10': float(recall_at_k(qscores, qy, k=10, min_label=2)),
                'precision_at_10': float(precision_at_k(qscores, qy, k=10, min_label=2)),
            })
        return per_q

    # RidgeClassifier (regression-like; multi-class one-vs-rest)
    print('\n  Training RidgeClassifier (alpha=1.0, default)...')
    ridge = RidgeClassifier(alpha=1.0, random_state=42)
    ridge.fit(X_tr_s, y_tr)
    ridge_per_q = per_query_ndcg(ridge, X_te_s, y_te, g_te)
    ridge_ndcg = float(np.mean([q['ndcg_at_10'] for q in ridge_per_q]))
    ridge_recall = float(np.mean([q['recall_at_10'] for q in ridge_per_q]))
    ridge_prec = float(np.mean([q['precision_at_10'] for q in ridge_per_q]))
    print(f'  RidgeClassifier single holdout: NDCG={ridge_ndcg:.4f} Recall={ridge_recall:.4f} Prec={ridge_prec:.4f}')

    # LogisticRegression (sklearn 1.6+ uses multinomial by default)
    print('  Training LogisticRegression (C=1.0, default)...')
    logreg = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    logreg.fit(X_tr_s, y_tr)
    logreg_per_q = per_query_ndcg(logreg, X_te_s, y_te, g_te)
    logreg_ndcg = float(np.mean([q['ndcg_at_10'] for q in logreg_per_q]))
    logreg_recall = float(np.mean([q['recall_at_10'] for q in logreg_per_q]))
    logreg_prec = float(np.mean([q['precision_at_10'] for q in logreg_per_q]))
    print(f'  LogReg single holdout: NDCG={logreg_ndcg:.4f} Recall={logreg_recall:.4f} Prec={logreg_prec:.4f}')

    # Get coefficients for interpretability
    if hasattr(logreg, 'coef_'):
        # Find class 2 index (sklearn may sort classes)
        cls2_idx = list(logreg.classes_).index(2)
        coef = logreg.coef_[cls2_idx]
        print(f'\n  LogReg coefficients (class={logreg.classes_[cls2_idx]}, higher=more relevant):')
        for fname, c in sorted(zip(FEATURE_NAMES, coef), key=lambda x: -abs(x[1])):
            print(f'    {fname:25s}: {c:+.4f}')

    # ─── 5-fold CV (sanity check + statistical robustness) ──────────────
    print('\n[2/3] 5-fold CV for RidgeClassifier and LogReg (seed=42)...')
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    ridge_cv_ndcgs, logreg_cv_ndcgs = [], []
    ridge_cv_recalls, logreg_cv_recalls = [], []
    for fold_idx, (tr_idx, te_idx) in enumerate(kf.split(qids)):
        X_tr2, y_tr2, g_tr2, X_te2, y_te2, g_te2 = build_train_test(
            X, y, group, tr_idx, te_idx, query_offsets
        )
        sc = StandardScaler()
        X_tr2_s = sc.fit_transform(X_tr2)
        X_te2_s = sc.transform(X_te2)
        # Ridge
        r = RidgeClassifier(alpha=1.0, random_state=42).fit(X_tr2_s, y_tr2)
        rpq = per_query_ndcg(r, X_te2_s, y_te2, g_te2)
        r_ndcg = np.mean([q['ndcg_at_10'] for q in rpq])
        r_recall = np.mean([q['recall_at_10'] for q in rpq])
        ridge_cv_ndcgs.append(r_ndcg)
        ridge_cv_recalls.append(r_recall)
        # LogReg (sklearn 1.6+ uses multinomial by default)
        lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42).fit(X_tr2_s, y_tr2)
        lpq = per_query_ndcg(lr, X_te2_s, y_te2, g_te2)
        l_ndcg = np.mean([q['ndcg_at_10'] for q in lpq])
        l_recall = np.mean([q['recall_at_10'] for q in lpq])
        logreg_cv_ndcgs.append(l_ndcg)
        logreg_cv_recalls.append(l_recall)
        print(f'  fold {fold_idx}: train={len(tr_idx)} test={len(te_idx)} '
              f'Ridge NDCG={r_ndcg:.4f} | LogReg NDCG={l_ndcg:.4f}')

    ridge_cv_mean = float(np.mean(ridge_cv_ndcgs))
    ridge_cv_std = float(np.std(ridge_cv_ndcgs))
    logreg_cv_mean = float(np.mean(logreg_cv_ndcgs))
    logreg_cv_std = float(np.std(logreg_cv_ndcgs))
    print(f'\n  Ridge 5-fold CV NDCG: {ridge_cv_mean:.4f} ± {ridge_cv_std:.4f}')
    print(f'  LogReg 5-fold CV NDCG: {logreg_cv_mean:.4f} ± {logreg_cv_std:.4f}')

    # ─── Combined baseline on same test set (for direct comparison) ─────
    print('\n[3/3] Combined baseline on same single holdout test set...')
    labels = json.load(open(labels_n50, encoding='utf-8'))['labels']
    def dcg_at_k(rels, k=10):
        rels = rels[:k]
        return sum(r / np.log2(i+2) for i, r in enumerate(rels))
    def ndcg_at_k_list(rels, k=10):
        ideal = sorted(rels, reverse=True)
        idcg = dcg_at_k(ideal, k)
        if idcg == 0: return 0.0
        return dcg_at_k(rels, k) / idcg

    data = {}
    for qfile in sorted((bench_dir / 'system_outputs_combined').glob('*.json')):
        qid = qfile.stem
        if qid not in labels:
            continue
        qdata = json.load(open(qfile, encoding='utf-8'))
        cands = qdata.get('results', [])
        rels = []
        for c in cands[:10]:
            cid = c.get('doi') or c.get('id') or c.get('title', '')
            label_obj = labels[qid].get(str(cid).strip(), 0)
            if isinstance(label_obj, dict):
                rels.append(int(label_obj.get('label', 0)))
            else:
                rels.append(int(label_obj))
        data[qid] = rels

    combined_holdout = [ndcg_at_k_list(data[q], 10) for q in test_qids]
    combined_ndcg = float(np.mean(combined_holdout))
    print(f'  Combined baseline single holdout: {combined_ndcg:.4f}')

    # ─── Save output ────────────────────────────────────────────────────
    out = {
        'version': 'v3.9.10.2-simpler-rerank',
        'date': datetime.now().isoformat(),
        'method': 'RidgeClassifier + LogisticRegression on 8 LTR features',
        'n_queries': len(qids),
        'n_labeled_pairs': int(len(y)),
        'features': FEATURE_NAMES,
        'single_holdout': {
            'method': 'train_test_split seed=42 test_size=20',
            'n_train': int(len(train_qids)),
            'n_test': int(len(test_qids)),
            'ridge_ndcg_at_10': ridge_ndcg,
            'ridge_recall_at_10': ridge_recall,
            'ridge_precision_at_10': ridge_prec,
            'logreg_ndcg_at_10': logreg_ndcg,
            'logreg_recall_at_10': logreg_recall,
            'logreg_precision_at_10': logreg_prec,
            'combined_baseline_ndcg_at_10': combined_ndcg,
        },
        'five_fold_cv': {
            'ridge_ndcg_mean': ridge_cv_mean,
            'ridge_ndcg_std': ridge_cv_std,
            'ridge_recall_mean': float(np.mean(ridge_cv_recalls)),
            'logreg_ndcg_mean': logreg_cv_mean,
            'logreg_ndcg_std': logreg_cv_std,
            'logreg_recall_mean': float(np.mean(logreg_cv_recalls)),
        },
        'comparison_to_v3_9_10_1': {
            'ltr_lambdamart_100_trees_single_holdout_ndcg': 0.7679,
            'combined_baseline_single_holdout_ndcg': 0.8988,
            'ltr_lambdamart_5fold_ndcg': 0.7806,
            'combined_baseline_5fold_direct_ndcg': 0.8825,
        },
    }
    if hasattr(logreg, 'coef_'):
        cls2_idx = list(logreg.classes_).index(2)
        coef = logreg.coef_[cls2_idx]
        out['logreg_coefficients_class2'] = {fname: float(c) for fname, c in zip(FEATURE_NAMES, coef)}

    out_path = bench_dir / 'reports' / 'v3_9_10_2_simpler_rerank.json'
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nWrote: {out_path}')

finally:
    # Restore labels_clean.json
    if backup.exists():
        import shutil
        shutil.copy(backup, labels_clean)
        print(f'\nRestored labels_clean.json from {backup}')

print('\nDONE.')
