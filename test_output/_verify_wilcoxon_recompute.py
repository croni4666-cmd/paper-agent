"""Recompute Wilcoxon p-values from v3.9.7.3 per-query NDCG deltas.

This script verifies the v3_9_7_3_cross_encoder_wilcoxon_n50.json stats
are correct (the MD report appears to contradict them).
"""
import json
from scipy.stats import wilcoxon
import numpy as np

with open('bench/v01/reports/v3_9_7_3_cross_encoder_wilcoxon_n50.json') as f:
    d = json.load(f)

per = d['per_query_ndcg']
deltas = np.array([v['delta'] for v in per.values()])
print(f'n={len(deltas)}, n_pos={np.sum(deltas>0)}, n_neg={np.sum(deltas<0)}, n_zero={np.sum(deltas==0)}')
print(f'mean delta={deltas.mean():.4f}, median={np.median(deltas):.4f}')
print(f'std={deltas.std():.4f}')

w_stat, w_p_two = wilcoxon(deltas, alternative='two-sided')
w_stat_1, w_p_one = wilcoxon(deltas, alternative='less')
print(f'\nTwo-sided Wilcoxon: stat={w_stat}, p={w_p_two:.6f}')
print(f'One-sided (delta<0): stat={w_stat_1}, p={w_p_one:.6f}')
print(f'\nJSON-stored statistic for NDCG: 270.0')
print(f'JSON-stored p_value: 0.0008245548')
print(f'My recompute: stat={w_stat}, p={w_p_two:.6f}')

print('\n5 worst BGE queries:')
worst = sorted(per.items(), key=lambda x: x[1]['delta'])[:5]
for q, v in worst:
    print(f'  {q}: bi={v["biencoder"]:.3f} bge={v["bge"]:.3f} delta={v["delta"]:.3f}')

print('5 best BGE queries:')
best = sorted(per.items(), key=lambda x: -x[1]['delta'])[:5]
for q, v in best:
    print(f'  {q}: bi={v["biencoder"]:.3f} bge={v["bge"]:.3f} delta={v["delta"]:.3f}')
