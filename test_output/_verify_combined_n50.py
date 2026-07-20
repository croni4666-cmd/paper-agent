"""Verify combined baseline NDCG@10 = 0.8141 (v3.9.7.3 ltr report claim)."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon

# 1) Load labels (n=50 mixed)
labels_path = Path('bench/v01/labels_n50_mixed.json')
if not labels_path.exists():
    print(f'NOT FOUND: {labels_path}')
    raise SystemExit(1)
labels_raw = json.load(open(labels_path, encoding='utf-8'))
labels = labels_raw['labels']  # nested under 'labels' key
print(f'labels_n50_mixed: {len(labels)} queries')

# 2) DCG/NDCG
def dcg_at_k(rels, k=10):
    rels = rels[:k]
    return sum(r / np.log2(i+2) for i, r in enumerate(rels))

def ndcg_at_k(rels, k=10):
    ideal = sorted(rels, reverse=True)
    idcg = dcg_at_k(ideal, k)
    if idcg == 0: return 0.0
    return dcg_at_k(rels, k) / idcg

# 3) Recompute combined baseline NDCG@10 from system_outputs_combined
combined_dir = Path('bench/v01/system_outputs_combined')
ndcgs_combined = []
ndcgs_biencoder = []
ndcgs_bm25 = []

for qfile in sorted(combined_dir.glob('*.json')):
    qid = qfile.stem
    if qid not in labels:
        continue
    qdata = json.load(open(qfile, encoding='utf-8'))
    cands = qdata.get('results', qdata.get('candidates', qdata if isinstance(qdata, list) else []))
    if not cands:
        continue
    # Each candidate has 'doi' or 'id' for label matching
    q_labels = labels[qid]  # labels is already d['labels']: {qid: {doi: {label, reason}}}
    rels = []
    scores_bm25 = []
    scores_biencoder = []
    scores_combined = []  # v4_score = 0.5*norm(bm25) + 0.5*norm(biencoder)
    for c in cands[:10]:
        cid = c.get('doi') or c.get('id') or c.get('paper_id') or c.get('title', '')
        # nested label dict
        label_obj = q_labels.get(str(cid).strip(), 0)
        if isinstance(label_obj, dict):
            rels.append(int(label_obj.get('label', 0)))
        else:
            rels.append(int(label_obj))
        scores_bm25.append(c.get('bm25_score', 0))
        scores_biencoder.append(c.get('biencoder_score', 0))
        scores_combined.append(c.get('v4_score', 0))
    # combined baseline: candidates are ALREADY sorted by v4_score (from rerank step)
    # Just use them as-is for NDCG
    ndcgs_combined.append(ndcg_at_k(rels, 10))
    # 单独 bm25/biencoder 排序后的 NDCG (re-sort to compare)
    order_bm25 = np.argsort(scores_bm25)[::-1]
    order_bi = np.argsort(scores_biencoder)[::-1]
    ndcgs_bm25.append(ndcg_at_k([rels[i] for i in order_bm25], 10))
    ndcgs_biencoder.append(ndcg_at_k([rels[i] for i in order_bi], 10))

print(f'\nn_paired = {len(ndcgs_combined)}')
print(f'combined baseline NDCG@10: {np.mean(ndcgs_combined):.4f} ± {np.std(ndcgs_combined):.4f}')
print(f'BM25 only NDCG@10:        {np.mean(ndcgs_bm25):.4f} ± {np.std(ndcgs_bm25):.4f}')
print(f'biencoder only NDCG@10:   {np.mean(ndcgs_biencoder):.4f} ± {np.std(ndcgs_biencoder):.4f}')
print(f'\nv3.9.7.3 ltr report claim: combined baseline = 0.8141')
print(f'v3.9.7.3 wilcoxon claim:  biencoder = 0.8016')

# Wilcoxon combined vs biencoder
if len(ndcgs_combined) == len(ndcgs_biencoder):
    diffs = np.array(ndcgs_combined) - np.array(ndcgs_biencoder)
    w_stat, w_p = wilcoxon(diffs, alternative='two-sided')
    print(f'\ncombined vs biencoder: mean Δ = {diffs.mean():.4f}, Wilcoxon p = {w_p:.6f}')
