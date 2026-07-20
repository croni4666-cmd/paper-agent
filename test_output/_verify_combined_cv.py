"""Replicate LTR n=50 baseline using 5-fold CV split (matching v3.9.7.3 methodology)."""
import json
import numpy as np
from pathlib import Path
from sklearn.model_selection import KFold

labels_path = Path('bench/v01/labels_n50_mixed.json')
labels_raw = json.load(open(labels_path, encoding='utf-8'))
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
combined_dir = Path('bench/v01/system_outputs_combined')
data = {}
for qfile in sorted(combined_dir.glob('*.json')):
    qid = qfile.stem
    if qid not in labels:
        continue
    qdata = json.load(open(qfile, encoding='utf-8'))
    cands = qdata.get('results', [])
    q_labels = labels[qid]
    rels = []
    scores = []
    for c in cands[:10]:
        cid = c.get('doi') or c.get('id') or c.get('title', '')
        label_obj = q_labels.get(str(cid).strip(), 0)
        if isinstance(label_obj, dict):
            rels.append(int(label_obj.get('label', 0)))
        else:
            rels.append(int(label_obj))
        scores.append(c.get('v4_score', 0))
    data[qid] = {'rels': rels, 'v4': scores}

qids = sorted(data.keys())
print(f'n_queries in data: {len(qids)}')

# 5-fold CV
kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_ndcgs = []
for fold_idx, (train_idx, test_idx) in enumerate(kf.split(qids)):
    test_qids = [qids[i] for i in test_idx]
    test_ndcgs = []
    for qid in test_qids:
        d = data[qid]
        # v4_score sort 已经在 candidates 顺序里 (system_outputs_combined 已是 v4 排序)
        test_ndcgs.append(ndcg_at_k(d['rels'], 10))
    fold_mean = np.mean(test_ndcgs)
    cv_ndcgs.append(fold_mean)
    print(f'fold {fold_idx}: n_test={len(test_qids)}, mean NDCG@10={fold_mean:.4f}')

print(f'\n5-fold CV mean NDCG@10: {np.mean(cv_ndcgs):.4f} ± {np.std(cv_ndcgs):.4f}')
print(f'v3.9.7.3 ltr report: combined baseline = 0.8141')

# Direct (no CV) for comparison
direct = [ndcg_at_k(data[qid]['rels'], 10) for qid in qids]
print(f'\nDirect (no CV) mean NDCG@10: {np.mean(direct):.4f} ± {np.std(direct):.4f}')
