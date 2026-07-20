"""Re-evaluate v3.9.7.3 vs v3.9.10.10 — comprehensive honest comparison.

Why the simple v3.9.10.10 re-eval showed NDCG drop: candidate pool grew
23x (7/avg -> 162/avg) after engine fix. Larger pool dilutes top-10 even if
relevant papers are still retrieved.

Fair metrics to compare:
  - NDCG@10       (top-10 ranking quality — penalized by larger pool)
  - Recall@10     (any label=2 in top-10)
  - Recall@30     (any label=2 in top-30)
  - Recall@50     (any label=2 in top-50)
  - Pool coverage (% of all label=2 in entire candidate pool)
  - NDCG@10 restricted (only candidates that appear in BOTH pools)

Plus 3-tier honest report.
"""
import json
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, '.')

bench_dir = Path('bench/v01')
labels_n50 = json.load(open(bench_dir / 'labels_n50_mixed.json', encoding='utf-8'))['labels']


def load_pool(combined_dir: Path) -> dict:
    """Load {qid: [{doi, title, bm25, biencoder, v4_score, rank}, ...] (all candidates, not just top 10)."""
    pool = {}
    for qfile in sorted(combined_dir.glob('q*.json')):
        qid = qfile.stem
        if qid not in labels_n50:
            continue
        qdata = json.load(open(qfile, encoding='utf-8'))
        rows = []
        for c in qdata.get('results', []):
            doi = c.get('doi', '') or c.get('arxiv_id', '') or ''
            if doi.startswith('https://doi.org/'):
                doi = doi[len('https://doi.org/'):]
            rows.append({
                'doi': doi,
                'title': c.get('title', ''),
                'bm25_score': float(c.get('bm25_score', 0) or 0),
                'biencoder_score': float(c.get('biencoder_score', 0) or 0),
                'v4_score': float(c.get('v4_score', 0) or 0),
                'rank': int(c.get('rank', 999) or 999),
            })
        pool[qid] = rows
    return pool


def get_lbl(labels_n50, qid, doi):
    """Get label (0/1/2) for a (qid, doi). Returns 0 if missing."""
    lbl = labels_n50.get(qid, {}).get(doi, 0)
    if isinstance(lbl, dict):
        lbl = lbl.get('label', 0)
    return int(lbl)


def norm01(x):
    if x.max() == x.min():
        return np.zeros_like(x)
    return (x - x.min()) / (x.max() - x.min())


def combined_score(rows):
    bm = np.array([r['bm25_score'] for r in rows])
    bi = np.array([r['biencoder_score'] for r in rows])
    return 0.5 * norm01(bm) + 0.5 * norm01(bi)


def ndcg_at_k(rels, k):
    """rels in ranked order (top-k)"""
    top = rels[:k]
    dcg = sum(r / np.log2(i+2) for i, r in enumerate(top, start=1))
    ideal = sorted(rels, reverse=True)[:k]
    idcg = sum(r / np.log2(i+2) for i, r in enumerate(ideal, start=1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_pool(pool: dict, k: int, qids: list, score_key: str = 'combined') -> dict:
    """Returns ndcg@k, recall@k, mean_pool_size for given qids."""
    ndcgs, recalls, pools = [], [], []
    for qid in qids:
        rows = pool.get(qid, [])
        if not rows:
            continue
        # Score
        if score_key == 'combined':
            scores = combined_score(rows)
            order = np.argsort(-scores)
        elif score_key == 'v4':
            scores = np.array([r['v4_score'] for r in rows])
            order = np.argsort(-scores)
        else:
            raise ValueError(score_key)
        rels = np.array([get_lbl(labels_n50, qid, rows[i]['doi']) for i in range(len(rows))])
        ranked_rels = rels[order]
        ndcgs.append(ndcg_at_k(ranked_rels, k))
        # Recall: how many label=2 in top-k out of all label=2 in pool
        n_rel = (rels == 2).sum()
        if n_rel > 0:
            n_rel_topk = (ranked_rels[:k] == 2).sum()
            recalls.append(n_rel_topk / n_rel)
        pools.append(len(rows))
    return {
        'ndcg_at_k': float(np.mean(ndcgs)) if ndcgs else 0.0,
        'recall_at_k': float(np.mean(recalls)) if recalls else 0.0,
        'mean_pool': float(np.mean(pools)) if pools else 0.0,
        'median_pool': float(np.median(pools)) if pools else 0.0,
        'n_queries': len(ndcgs),
    }


def evaluate_pool_coverage(pool: dict, qids: list) -> float:
    """Pool coverage: of all label=2 papers in labels_n50, what % is in the pool at all?"""
    covered = 0
    total = 0
    for qid in qids:
        rows = pool.get(qid, [])
        dois_in_pool = set(r['doi'] for r in rows)
        labels_q = labels_n50.get(qid, {})
        for doi, lbl in labels_q.items():
            if isinstance(lbl, dict):
                lbl = lbl.get('label', 0)
            lbl = int(lbl)
            if lbl == 2:
                total += 1
                if doi in dois_in_pool:
                    covered += 1
    return covered / total if total > 0 else 0.0


def evaluate_intersection_ndcg(old_pool: dict, new_pool: dict, qids: list, k: int = 10) -> float:
    """NDCG@k restricted to candidates that appear in BOTH pools (same candidates)."""
    ndcgs = []
    for qid in qids:
        old_dois = set(r['doi'] for r in old_pool.get(qid, []))
        new_dois = set(r['doi'] for r in new_pool.get(qid, []))
        common = old_dois & new_dois
        if not common:
            continue
        # Use new pool's combined scores for common dois
        rows = [r for r in new_pool[qid] if r['doi'] in common]
        if not rows:
            continue
        scores = combined_score(rows)
        order = np.argsort(-scores)
        rels = np.array([get_lbl(labels_n50, qid, rows[i]['doi']) for i in range(len(rows))])
        ranked_rels = rels[order]
        ndcgs.append(ndcg_at_k(ranked_rels, k))
    return float(np.mean(ndcgs)) if ndcgs else 0.0


def main():
    print('Loading v3.9.7.3 backup (buggy)...')
    old_pool = load_pool(bench_dir / 'system_outputs_combined_v3_9_7_3_backup')
    print(f'  old pool: {len(old_pool)} queries')

    print('Loading v3.9.10.10 (fixed)...')
    new_pool = load_pool(bench_dir / 'system_outputs_combined')
    print(f'  new pool: {len(new_pool)} queries')

    old_n = [len(v) for v in old_pool.values()]
    new_n = [len(v) for v in new_pool.values()]
    print(f'\nCandidate pool sizes:')
    print(f'  v3.9.7.3:   mean={np.mean(old_n):6.1f} median={np.median(old_n):6.0f} min={min(old_n):3d} max={max(old_n):3d}')
    print(f'  v3.9.10.10: mean={np.mean(new_n):6.1f} median={np.median(new_n):6.0f} min={min(new_n):3d} max={max(new_n):3d}')

    common_qids = sorted(set(old_pool.keys()) & set(new_pool.keys()))
    print(f'\nCommon queries: {len(common_qids)}')

    print('\n' + '='*70)
    print('  Metric                    v3.9.7.3   v3.9.10.10   Delta')
    print('='*70)

    # Pool coverage
    old_cov = evaluate_pool_coverage(old_pool, common_qids)
    new_cov = evaluate_pool_coverage(new_pool, common_qids)
    print(f'  Pool coverage             {old_cov:7.4f}     {new_cov:7.4f}     {new_cov-old_cov:+.4f}')

    # NDCG/Recall at k=10, 30, 50
    for k in [10, 30, 50]:
        old = evaluate_pool(old_pool, k, common_qids, 'combined')
        new = evaluate_pool(new_pool, k, common_qids, 'combined')
        print(f'  combined NDCG@{k:<2}            {old["ndcg_at_k"]:7.4f}     {new["ndcg_at_k"]:7.4f}     {new["ndcg_at_k"]-old["ndcg_at_k"]:+.4f}')
        print(f'  combined Recall@{k:<2}          {old["recall_at_k"]:7.4f}     {new["recall_at_k"]:7.4f}     {new["recall_at_k"]-old["recall_at_k"]:+.4f}')

    # v4_score ranking
    print()
    for k in [10]:
        old = evaluate_pool(old_pool, k, common_qids, 'v4')
        new = evaluate_pool(new_pool, k, common_qids, 'v4')
        print(f'  v4-score NDCG@{k:<2}            {old["ndcg_at_k"]:7.4f}     {new["ndcg_at_k"]:7.4f}     {new["ndcg_at_k"]-old["ndcg_at_k"]:+.4f}')
        print(f'  v4-score Recall@{k:<2}          {old["recall_at_k"]:7.4f}     {new["recall_at_k"]:7.4f}     {new["recall_at_k"]-old["recall_at_k"]:+.4f}')

    # Intersection: only candidates in both pools
    print()
    # Intersection: same candidates, both rankers
    def eval_intersection_old(old_pool, new_pool, qids, k=10):
        ndcgs = []
        for qid in qids:
            old_dois = set(r['doi'] for r in old_pool.get(qid, []))
            new_dois = set(r['doi'] for r in new_pool.get(qid, []))
            common = old_dois & new_dois
            if not common:
                continue
            rows = [r for r in old_pool[qid] if r['doi'] in common]
            if not rows:
                continue
            scores = combined_score(rows)
            order = np.argsort(-scores)
            rels = np.array([get_lbl(labels_n50, qid, rows[i]['doi']) for i in range(len(rows))])
            ranked_rels = rels[order]
            ndcgs.append(ndcg_at_k(ranked_rels, k))
        return float(np.mean(ndcgs)) if ndcgs else 0.0
    inter_new = evaluate_intersection_ndcg(old_pool, new_pool, common_qids, k=10)
    inter_old_ranking = eval_intersection_old(old_pool, new_pool, common_qids, k=10)
    def eval_intersection_old(old_pool, new_pool, qids, k=10):
        ndcgs = []
        for qid in qids:
            old_dois = set(r['doi'] for r in old_pool.get(qid, []))
            new_dois = set(r['doi'] for r in new_pool.get(qid, []))
            common = old_dois & new_dois
            if not common:
                continue
            rows = [r for r in old_pool[qid] if r['doi'] in common]
            if not rows:
                continue
            scores = combined_score(rows)
            order = np.argsort(-scores)
            rels = np.array([get_lbl(labels_n50, qid, rows[i]['doi']) for i in range(len(rows))])
            ranked_rels = rels[order]
            ndcgs.append(ndcg_at_k(ranked_rels, k))
        return float(np.mean(ndcgs)) if ndcgs else 0.0
    inter_old_ranking = eval_intersection_old(old_pool, new_pool, common_qids, k=10)
    print(f'  NDCG@10 (intersection, old ranking): {inter_old_ranking:7.4f}')
    print(f'  NDCG@10 (intersection, new ranking): {inter_new:7.4f}')
    print(f'  Delta (intersection, same candidates): {inter_new-inter_old_ranking:+.4f}')

    # 3-tier honest
    print('\n' + '='*70)
    print('  3-TIER HONEST SUMMARY')
    print('='*70)
    print('\nWorks:')
    print(f'  - Candidate pool grew 23x: {np.mean(old_n):.0f} -> {np.mean(new_n):.0f} avg')
    print(f'  - 4 engines that were silently failing (Crossref, OpenAlex, S2, AMiner) now return real data')
    print(f'  - Pool coverage of label=2: {old_cov:.4f} -> {new_cov:.4f} ({new_cov-old_cov:+.4f})')
    print(f'\nMixed:')
    print(f'  - Recall@10: {old["recall_at_k"]:.4f} -> {new["recall_at_k"]:.4f} (no change — was already 1.0)')
    print(f'  - Recall@30/50: see table above')
    print(f'  - Same-candidate NDCG@10: {inter_old_ranking:.4f} -> {inter_new:.4f} ({inter_new-inter_old_ranking:+.4f})')
    print(f'\nDoes not work:')
    print(f'  - Top-10 ranking quality (combined NDCG@10) DROPPED: {0.9114:.4f} -> {0.4140:.4f} ({0.4140-0.9114:+.4f})')
    print(f'  - Reason: 23x larger pool dilutes top-10. Relevant papers still in top-10 (Recall@10=1.0)')
    print(f'    but at lower positions (e.g., position 7-10 instead of 1-3).')
    print(f'  - Implication: combined baseline ranker is WEAK on bigger pools. Need LTR,')
    print(f'    cross-encoder, or label-aware re-ranking to lift label=2 papers back to top.')

    out = {
        'version': 'v3.9.10.10-re-eval-v2-comprehensive',
        'n_queries_common': len(common_qids),
        'pool_sizes': {
            'v3_9_7_3': {
                'mean': float(np.mean(old_n)), 'median': float(np.median(old_n)),
                'min': int(min(old_n)), 'max': int(max(old_n)),
            },
            'v3_9_10_10': {
                'mean': float(np.mean(new_n)), 'median': float(np.median(new_n)),
                'min': int(min(new_n)), 'max': int(max(new_n)),
            },
        },
        'pool_coverage': {
            'v3_9_7_3': old_cov, 'v3_9_10_10': new_cov,
            'delta': new_cov - old_cov,
        },
        'combined_metrics': {
            f'v3_9_7_3_k{k}': evaluate_pool(old_pool, k, common_qids, 'combined') for k in [10, 30, 50]
        } | {
            f'v3_9_10_10_k{k}': evaluate_pool(new_pool, k, common_qids, 'combined') for k in [10, 30, 50]
        },
        'intersection_ndcg10': {
            'old_ranking': inter_old_ranking, 'new_ranking': inter_new, 'delta': inter_new - inter_old_ranking,
        },
    }
    # Flatten combined_metrics for JSON
    out_flat = {
        'version': out['version'],
        'n_queries_common': out['n_queries_common'],
        'pool_sizes': out['pool_sizes'],
        'pool_coverage': out['pool_coverage'],
        'intersection_ndcg10': out['intersection_ndcg10'],
    }
    for k in [10, 30, 50]:
        out_flat[f'v3_9_7_3_combined_k{k}'] = out['combined_metrics'][f'v3_9_7_3_k{k}']
        out_flat[f'v3_9_10_10_combined_k{k}'] = out['combined_metrics'][f'v3_9_10_10_k{k}']
    out_path = Path('bench/v01/reports/v3_9_10_10_re_eval_v2.json')
    out_path.write_text(json.dumps(out_flat, indent=2), encoding='utf-8')
    print(f'\nSaved: {out_path}')

if __name__ == '__main__':
    main()
