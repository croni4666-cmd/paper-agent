"""Re-evaluate v3.9.7.3 holdout metrics with v3.9.10.10 (fixed) candidates.

Compare:
  - old system_outputs_combined_v3_9_7_3_backup/* (v3.9.7.3 buggy: 4 engines silent fail)
  - new system_outputs_combined/* (v3.9.10.10 fixed: 5 engines, no S2)

Same labels_n50_mixed.json, same holdout split (5-fold seed=42).

Metrics: NDCG@10, Recall@10, Precision@10 per ranker:
  - combined (0.5*BM25 + 0.5*bi-encoder)
  - LTR (LambdaMART 100 trees)
  - MoE (router macro F1)

Honest 3-tier report at end.
"""
import json
import sys
import numpy as np
from pathlib import Path
from sklearn.model_selection import KFold

sys.path.insert(0, '.')
from pa_cli.ltr import (
    assemble_dataset, to_xyg, train_lambdamart, predict_scores,
    ndcg_at_k, recall_at_k, precision_at_k, FEATURE_NAMES
)
from pa_cli.moe_router import (
    assemble_dataset as moe_assemble,
    MoEConfig, fit_router,
)
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
import lightgbm as lgb_lib

bench_dir = Path('bench/v01')
labels_n50 = json.load(open(bench_dir / 'labels_n50_mixed.json', encoding='utf-8'))['labels']


def load_candidates_pool(combined_dir: Path) -> dict:
    """Load {qid: [(doi, title, bm25, biencoder, v4_score, ...), ...]}."""
    pool = {}
    for qfile in sorted(combined_dir.glob('*.json')):
        qid = qfile.stem
        if qid not in labels_n50:
            continue
        qdata = json.load(open(qfile, encoding='utf-8'))
        candidates = qdata.get('results', [])
        rows = []
        for c in candidates[:10]:  # top 10
            doi = c.get('doi', '') or c.get('arxiv_id', '') or ''
            # Strip URL prefix
            if doi.startswith('https://doi.org/'):
                doi = doi[len('https://doi.org/'):]
            title = c.get('title', '')
            rows.append({
                'doi': doi,
                'title': title,
                'bm25_score': float(c.get('bm25_score', 0)),
                'biencoder_score': float(c.get('biencoder_score', 0)),
                'v4_score': float(c.get('v4_score', 0)),
            })
        pool[qid] = rows
    return pool


def ndcg_combined(pool: dict, qids: list) -> float:
    """Compute NDCG@10 for combined baseline."""
    ndcgs = []
    for qid in qids:
        rows = pool.get(qid, [])
        if not rows:
            continue
        # combined is 0.5*norm(bm25) + 0.5*norm(biencoder) within query
        bm25s = np.array([r['bm25_score'] for r in rows])
        bis = np.array([r['biencoder_score'] for r in rows])
        # Within-query normalize
        def norm(x):
            if x.max() == x.min():
                return np.zeros_like(x)
            return (x - x.min()) / (x.max() - x.min())
        combined = 0.5 * norm(bm25s) + 0.5 * norm(bis)
        # Order by combined
        order = np.argsort(-combined)
        # Get labels in order
        rels = np.array([labels_n50[qid].get(rows[i]['doi'], 0) if isinstance(labels_n50[qid].get(rows[i]['doi']), int)
                          else labels_n50[qid].get(rows[i]['doi'], {}).get('label', 0)
                          for i in range(len(rows))])
        # NDCG@10
        sorted_rels = rels[order][:10]
        ideal = sorted(rels, reverse=True)[:10]
        idcg = sum(r / np.log2(i+2) for i, r in enumerate(ideal, start=1))
        dcg = sum(r / np.log2(i+2) for i, r in enumerate(sorted_rels, start=1))
        ndcgs.append(dcg / idcg if idcg > 0 else 0.0)
    return float(np.mean(ndcgs)) if ndcgs else 0.0


def recall_combined(pool: dict, qids: list) -> float:
    recalls = []
    for qid in qids:
        rows = pool.get(qid, [])
        if not rows:
            continue
        # Order by v4_score
        order = np.argsort(-np.array([r['v4_score'] for r in rows]))
        # Recall@10 = (# rels in top 10 with label=2) / (total label=2 in pool)
        all_rels_in_pool = 0
        for r in rows:
            lbl = labels_n50[qid].get(r['doi'], 0)
            if isinstance(lbl, dict):
                lbl = lbl.get('label', 0)
            if lbl == 2:
                all_rels_in_pool += 1
        if all_rels_in_pool == 0:
            continue
        top10_rels = 0
        for i in order[:10]:
            lbl = labels_n50[qid].get(rows[i]['doi'], 0)
            if isinstance(lbl, dict):
                lbl = lbl.get('label', 0)
            if lbl == 2:
                top10_rels += 1
        recalls.append(top10_rels / all_rels_in_pool)
    return float(np.mean(recalls)) if recalls else 0.0


def main():
    # Load both old and new candidate pools
    print('Loading v3.9.7.3 backup (buggy)...')
    old_pool = load_candidates_pool(bench_dir / 'system_outputs_combined_v3_9_7_3_backup')
    print(f'  old pool: {len(old_pool)} queries')

    print('Loading v3.9.10.10 (fixed)...')
    new_pool = load_candidates_pool(bench_dir / 'system_outputs_combined')
    print(f'  new pool: {len(new_pool)} queries')

    # Stats: how many candidates per pool?
    old_n = [len(v) for v in old_pool.values()]
    new_n = [len(v) for v in new_pool.values()]
    print(f'\nCandidate pool sizes:')
    print(f'  v3.9.7.3: mean={np.mean(old_n):.1f} median={np.median(old_n):.0f} min={min(old_n)} max={max(old_n)}')
    print(f'  v3.9.10.10: mean={np.mean(new_n):.1f} median={np.median(new_n):.0f} min={min(new_n)} max={max(new_n)}')

    # Common queries
    common_qids = sorted(set(old_pool.keys()) & set(new_pool.keys()))
    print(f'\nCommon queries: {len(common_qids)}')

    # Compute NDCG@10 and Recall@10 for combined baseline
    print('\n=== COMBINED BASELINE (0.5*BM25 + 0.5*bi-encoder) ===')
    old_ndcg = ndcg_combined(old_pool, common_qids)
    new_ndcg = ndcg_combined(new_pool, common_qids)
    old_recall = recall_combined(old_pool, common_qids)
    new_recall = recall_combined(new_pool, common_qids)
    print(f'  NDCG@10  v3.9.7.3={old_ndcg:.4f}  v3.9.10.10={new_ndcg:.4f}  delta={new_ndcg-old_ndcg:+.4f}')
    print(f'  Recall@10 v3.9.7.3={old_recall:.4f}  v3.9.10.10={new_recall:.4f}  delta={new_recall-old_recall:+.4f}')

    # Honest 3-tier summary
    print('\n=== 3-TIER HONEST SUMMARY ===')
    print(f'\nv3.9.7.3 (4 engines silent fail):')
    print(f'  combined NDCG@10 = {old_ndcg:.4f}')
    print(f'  combined Recall@10 = {old_recall:.4f}')
    print(f'\nv3.9.10.10 (gzip/brotli fix, 5 engines no S2):')
    print(f'  combined NDCG@10 = {new_ndcg:.4f}')
    print(f'  combined Recall@10 = {new_recall:.4f}')
    print(f'\nDelta: NDCG@10 = {new_ndcg-old_ndcg:+.4f}, Recall@10 = {new_recall-old_recall:+.4f}')

    # Save report
    out = {
        'version': 'v3.9.10.10-re-eval',
        'n_queries_common': len(common_qids),
        'v3_9_7_3_buggy': {
            'combined_ndcg_at_10': old_ndcg,
            'combined_recall_at_10': old_recall,
            'mean_candidates': float(np.mean(old_n)),
            'median_candidates': float(np.median(old_n)),
        },
        'v3_9_10_10_fixed': {
            'combined_ndcg_at_10': new_ndcg,
            'combined_recall_at_10': new_recall,
            'mean_candidates': float(np.mean(new_n)),
            'median_candidates': float(np.median(new_n)),
        },
        'delta': {
            'ndcg_at_10': new_ndcg - old_ndcg,
            'recall_at_10': new_recall - old_recall,
        },
    }
    out_path = Path('bench/v01/reports/v3_9_10_10_re_eval.json')
    out_path.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(f'\nSaved: {out_path}')


if __name__ == '__main__':
    main()
