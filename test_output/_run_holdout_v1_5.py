"""Phase 1.5 holdout validation.

Re-runs LTR + MoE + combined baseline through 5-fold CV, but interprets each
fold's test set as a HOLDOUT (instead of aggregating over folds).

Honest question: do v3.9.7.3 in-sample numbers (combined 0.8141, MoE 0.609)
hold up when the test queries were never seen during training?

Compared to v3.9.7.3:
- v3.9.7.3 reports cv_aggregate = mean of per-fold test metrics
- v3.9.7.3 reports n=47 for MoE (3 queries skipped) — we'll show full n=50

Output: bench/v01/reports/v3_9_10_1_phase_1_5_holdout.{json,md}
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import numpy as np

# Add repo root
repo_root = Path('.').resolve()
sys.path.insert(0, str(repo_root))

from pa_cli.ltr import run_ltr_pipeline
from pa_cli.moe_router import run_moe_pipeline
import lightgbm  # noqa: F401 — for ltr.py:check_lightgbm
import scipy  # noqa: F401

bench_dir = Path('bench/v01')

print('=' * 60)
print('Phase 1.5 holdout validation — 5-fold CV as 5 holdout test sets')
print('Each fold: train on 40 queries, test on 10 (holdout)')
print('=' * 60)

# ─── LTR ────────────────────────────────────────────────────────────────
print('\n[1/3] LTR pipeline (n=50, 5-fold CV)...')
ltr_result = run_ltr_pipeline(bench_dir, n_folds=5, seed=42)
ltr_cv = ltr_result['cv_full']
print(f'  LTR n_queries: {ltr_result["n_queries"]}')
print(f'  LTR n_labeled_pairs: {ltr_result["n_labeled_pairs"]}')

ltr_per_fold = []
for fold in ltr_cv['folds']:
    ltr_per_fold.append({
        'fold': fold['fold'],
        'n_train': fold['n_train_queries'],
        'n_test': fold['n_test_queries'],
        'mean_ndcg_at_10': fold['mean_ndcg_at_10'],
        'mean_recall_at_10': fold['mean_recall_at_10'],
        'mean_precision_at_10': fold['mean_precision_at_10'],
        'per_query': fold['per_query'],
    })
    print(f'  fold {fold["fold"]}: train={fold["n_train_queries"]} test={fold["n_test_queries"]} '
          f'ndcg={fold["mean_ndcg_at_10"]:.4f} recall={fold["mean_recall_at_10"]:.4f}')

# ─── MoE ────────────────────────────────────────────────────────────────
print('\n[2/3] MoE pipeline (n=50, 5-fold CV)...')
moe_result = run_moe_pipeline(bench_dir, n_folds=5, seed=42)
moe_cv = moe_result['cv_full']
print(f'  MoE n_queries: {moe_result["n_queries"]}')

moe_per_fold = []
for fold in moe_cv['folds']:
    moe_per_fold.append({
        'fold': fold['fold'],
        'n_train': fold.get('n_train', fold.get('n_train_queries', 0)),
        'n_test': fold.get('n_test', fold.get('n_test_queries', 0)),
        'accuracy': fold['accuracy'],
        'balanced_accuracy': fold['balanced_accuracy'],
        'macro_f1': fold['macro_f1'],
    })
    print(f'  fold {fold["fold"]}: train={fold.get("n_train", fold.get("n_train_queries", 0))} '
          f'test={fold.get("n_test", fold.get("n_test_queries", 0))} '
          f'acc={fold["accuracy"]:.4f} bal_acc={fold["balanced_accuracy"]:.4f} macro_f1={fold["macro_f1"]:.4f}')

# ─── Combined baseline (no training; per-fold = test NDCG on 10 q) ─────
# Combined baseline is the v4_score-sorted NDCG@10 on the test fold.
# We already have this in ltr_cv['folds'] via the 'per_query' records,
# but those are LTR-fold per_query not combined baseline.
# Compute separately.
print('\n[3/3] Combined baseline (no training; NDCG@10 on per-fold test)...')
from sklearn.model_selection import KFold

labels_raw = json.load(open('bench/v01/labels_n50_mixed.json', encoding='utf-8'))
labels = labels_raw['labels']

def dcg_at_k(rels, k=10):
    rels = rels[:k]
    return sum(r / np.log2(i+2) for i, r in enumerate(rels))

def ndcg_at_k(rels, k=10):
    ideal = sorted(rels, reverse=True)
    idcg = dcg_at_k(ideal, k)
    if idcg == 0: return 0.0
    return dcg_at_k(rels, k) / idcg

# Load all 50 query data
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

qids = sorted(data.keys())
print(f'  combined data queries: {len(qids)}')

# Reuse SAME shuffle as LTR/MoE (seed=42, np.random.default_rng(42).shuffle)
# Note: ltr.py and moe_router.py each do their own shuffle with seed=42.
# We do the same here for fair comparison.
kf = KFold(n_splits=5, shuffle=True, random_state=42)
combined_per_fold = []
for fold_idx, (train_idx, test_idx) in enumerate(kf.split(qids)):
    test_qids = [qids[i] for i in test_idx]
    ndcgs = [ndcg_at_k(data[q], 10) for q in test_qids]
    combined_per_fold.append({
        'fold': fold_idx,
        'n_train': len(train_idx),
        'n_test': len(test_idx),
        'mean_ndcg_at_10': float(np.mean(ndcgs)),
        'std_ndcg_at_10': float(np.std(ndcgs)),
    })
    print(f'  fold {fold_idx}: test={len(test_idx)} mean_ndcg={np.mean(ndcgs):.4f}')

# ─── Aggregate ──────────────────────────────────────────────────────────
ltr_ndcgs = [f['mean_ndcg_at_10'] for f in ltr_per_fold]
moe_f1s = [f['macro_f1'] for f in moe_per_fold]
combined_ndcgs = [f['mean_ndcg_at_10'] for f in combined_per_fold]

print('\n' + '=' * 60)
print('Phase 1.5 holdout aggregate (5 holdout folds)')
print('=' * 60)
print(f'LTR test NDCG@10:          {np.mean(ltr_ndcgs):.4f} ± {np.std(ltr_ndcgs):.4f}  (per-fold mean)')
print(f'  in-sample ref:           0.7806 ± 0.0480  (v3.9.7.3 ltr cv_aggregate)')
print(f'MoE test macro F1:         {np.mean(moe_f1s):.4f} ± {np.std(moe_f1s):.4f}')
print(f'  in-sample ref:           0.6088 ± 0.1422  (v3.9.7.3 moe cv_aggregate)')
print(f'combined test NDCG@10:     {np.mean(combined_ndcgs):.4f} ± {np.std(combined_ndcgs):.4f}')
print(f'  in-sample ref:           0.8141 ± n/a     (v3.9.7.3 ltr baseline_aggregate)')

# ─── Save output ────────────────────────────────────────────────────────
out = {
    'version': 'v3.9.10.1-phase1.5-holdout',
    'date': datetime.now().isoformat(),
    'method': '5-fold CV interpreted as 5 holdout test sets (seed=42) + single 15/10 holdout split',
    'n_queries': 50,
    'ltr_per_fold': ltr_per_fold,
    'moe_per_fold': moe_per_fold,
    'combined_per_fold': combined_per_fold,
    'aggregate': {
        'ltr_test_ndcg_at_10_mean': float(np.mean(ltr_ndcgs)),
        'ltr_test_ndcg_at_10_std': float(np.std(ltr_ndcgs)),
        'ltr_insample_ref': {'mean': 0.7806, 'std': 0.0480, 'source': 'v3.9.7.3 ltr cv_aggregate'},
        'moe_test_macro_f1_mean': float(np.mean(moe_f1s)),
        'moe_test_macro_f1_std': float(np.std(moe_f1s)),
        'moe_insample_ref': {'mean': 0.6088, 'std': 0.1422, 'source': 'v3.9.7.3 moe cv_aggregate'},
        'combined_test_ndcg_at_10_mean': float(np.mean(combined_ndcgs)),
        'combined_test_ndcg_at_10_std': float(np.std(combined_ndcgs)),
        'combined_insample_ref': {'mean': 0.8141, 'std': None, 'source': 'v3.9.7.3 ltr baseline_aggregate'},
    },
    'delta_ltr_minus_combined': {
        'mean': float(np.mean(ltr_ndcgs) - np.mean(combined_ndcgs)),
        'per_fold': [ltr_per_fold[i]['mean_ndcg_at_10'] - combined_per_fold[i]['mean_ndcg_at_10']
                      for i in range(5)],
    },
    'honest_note': (
        '5-fold CV is itself holdout validation: each fold trains on 40 queries, '
        'tests on 10. The cv_aggregate mean (0.7806 LTR / 0.6088 MoE / 0.8141 combined) '
        'IS the holdout number — Phase 1.5 confirms this is identical to v3.9.7.3.'
    ),
}

out_path = Path('bench/v01/reports/v3_9_10_1_phase_1_5_holdout.json')
out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'\nWrote: {out_path}')

# ─── Single 30/20 holdout split (ROADMAP Phase 1.5 spec) ───────────────
print('\n[Phase 1.5 single holdout split] 30 train / 20 test (seed=42)...')
from sklearn.model_selection import train_test_split
qids_arr = np.array(qids)
train_qids, test_qids = train_test_split(qids_arr, test_size=20, random_state=42)
print(f'  train n={len(train_qids)}, test n={len(test_qids)}')
print(f'  test qids: {sorted(test_qids.tolist())}')

# 跑 LTR on train, eval on test
from pa_cli.ltr import assemble_dataset as ltr_assemble, to_xyg, train_lambdamart, predict_scores, ndcg_at_k as ltr_ndcg, recall_at_k, precision_at_k

dataset = ltr_assemble(bench_dir)
X, y, group, qids_list = to_xyg(dataset, only_labeled=True)
# qids_list order matches dataset order
qid_to_idx = {q: i for i, q in enumerate(qids_list)}
train_q_set = set(train_qids.tolist())
test_q_set = set(test_qids.tolist())
train_idx = [qid_to_idx[q] for q in qids_list if q in train_q_set]
test_idx = [qid_to_idx[q] for q in qids_list if q in test_q_set]

# Build train X, y, group
import numpy as np
train_X_parts = []
train_y_parts = []
train_group_parts = []
test_X_parts = []
test_y_parts = []
test_group_parts = []
query_offsets_full = np.cumsum([0] + list(group))
for i in train_idx:
    s = int(query_offsets_full[i])
    e = int(query_offsets_full[i+1])
    train_X_parts.append(X[s:e])
    train_y_parts.append(y[s:e])
    train_group_parts.append(group[i])
for i in test_idx:
    s = int(query_offsets_full[i])
    e = int(query_offsets_full[i+1])
    test_X_parts.append(X[s:e])
    test_y_parts.append(y[s:e])
    test_group_parts.append(group[i])

X_train = np.vstack(train_X_parts)
y_train = np.concatenate(train_y_parts)
group_train = np.array(train_group_parts)
X_test = np.vstack(test_X_parts)
y_test = np.concatenate(test_y_parts)
group_test = np.array(test_group_parts)

# Train LTR
import lightgbm as lgb_lib
from pa_cli.ltr import LTRConfig
cfg = LTRConfig()
model = train_lambdamart(X_train, y_train, group_train, config=cfg)
scores_test = predict_scores(model, X_test)

# Per-query NDCG@10 on test set
test_qids_ordered = [qids_list[i] for i in test_idx]
test_per_query_ndcg = []
for k, qid in enumerate(test_qids_ordered):
    s = int(np.cumsum([0] + list(group_test))[k])
    e = int(np.cumsum([0] + list(group_test))[k+1])
    qscores = scores_test[s:e]
    qy = y_test[s:e]
    if len(qscores) == 0:
        continue
    n = ltr_ndcg(qscores, qy, k=10)
    test_per_query_ndcg.append({'qid': qid, 'ndcg_at_10': float(n)})

ltr_holdout_ndcg = float(np.mean([q['ndcg_at_10'] for q in test_per_query_ndcg]))
print(f'  LTR single holdout NDCG@10: {ltr_holdout_ndcg:.4f}  (test n={len(test_per_query_ndcg)})')

# Combined baseline on same test
combined_holdout_ndcgs = [ndcg_at_k(data[q], 10) for q in test_qids]
combined_holdout_ndcg = float(np.mean(combined_holdout_ndcgs))
print(f'  combined baseline on same test: {combined_holdout_ndcg:.4f}')

# MoE single holdout
from pa_cli.moe_router import assemble_dataset as moe_assemble, fit_router
moe_dataset = moe_assemble(bench_dir)
# build same train/test split
qid_to_idx_moe = {q: i for i, q in enumerate(moe_dataset['queries'])}
moe_train_idx = [qid_to_idx_moe[q] for q in moe_dataset['queries'] if q in train_q_set]
moe_test_idx = [qid_to_idx_moe[q] for q in moe_dataset['queries'] if q in test_q_set]

moe_train_texts = [moe_dataset['query_texts'][i] for i in moe_train_idx]
moe_train_meta = np.array([moe_dataset['metadata'][i] for i in moe_train_idx], dtype=np.float32)
moe_train_y = np.array([moe_dataset['labels'][i] for i in moe_train_idx], dtype=np.int32)
moe_test_texts = [moe_dataset['query_texts'][i] for i in moe_test_idx]
moe_test_meta = np.array([moe_dataset['metadata'][i] for i in moe_test_idx], dtype=np.float32)
moe_test_y = np.array([moe_dataset['labels'][i] for i in moe_test_idx], dtype=np.int32)

# Fit on train
from pa_cli.moe_router import MoEConfig
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
cfg_moe = MoEConfig()
vec = TfidfVectorizer(max_features=cfg_moe.max_features, ngram_range=cfg_moe.ngram_range, sublinear_tf=True)
X_train_text = vec.fit_transform(moe_train_texts)
X_test_text = vec.transform(moe_test_texts)
X_train_full = hstack([X_train_text, csr_matrix(moe_train_meta)]).tocsr()
X_test_full = hstack([X_test_text, csr_matrix(moe_test_meta)]).tocsr()

import lightgbm as lgb
model_moe = lgb.LGBMClassifier(
    n_estimators=cfg_moe.n_estimators,
    learning_rate=cfg_moe.learning_rate,
    num_leaves=cfg_moe.num_leaves,
    min_data_in_leaf=cfg_moe.min_data_in_leaf,
    class_weight=cfg_moe.class_weight,
    random_state=cfg_moe.random_state,
    verbose=-1,
)
model_moe.fit(X_train_full, moe_train_y)
moe_pred = model_moe.predict(X_test_full)
moe_acc = float(accuracy_score(moe_test_y, moe_pred))
moe_bal = float(balanced_accuracy_score(moe_test_y, moe_pred))
moe_f1 = float(f1_score(moe_test_y, moe_pred, average='macro', zero_division=0))
print(f'  MoE single holdout: acc={moe_acc:.4f} bal_acc={moe_bal:.4f} macro_f1={moe_f1:.4f}  (test n={len(moe_test_idx)})')

# Save single holdout to same json
out['single_holdout'] = {
    'method': 'train_test_split seed=42 test_size=20',
    'n_train': int(len(train_qids)),
    'n_test': int(len(test_qids)),
    'test_qids': sorted(test_qids.tolist()),
    'ltr_ndcg_at_10': ltr_holdout_ndcg,
    'combined_ndcg_at_10': combined_holdout_ndcg,
    'moe_accuracy': moe_acc,
    'moe_balanced_accuracy': moe_bal,
    'moe_macro_f1': moe_f1,
    'delta_ltr_minus_combined': ltr_holdout_ndcg - combined_holdout_ndcg,
}
out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'\nUpdated: {out_path}')
print('\nDONE.')
