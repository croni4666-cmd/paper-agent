"""Per-query position analysis: where do label=2 papers rank in new pool?"""
import json
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, '.')

bench_dir = Path('bench/v01')
labels_n50 = json.load(open(bench_dir / 'labels_n50_mixed.json', encoding='utf-8'))['labels']
new_pool_dir = bench_dir / 'system_outputs_combined'
old_pool_dir = bench_dir / 'system_outputs_combined_v3_9_7_3_backup'


def get_lbl(qid, doi):
    lbl = labels_n50.get(qid, {}).get(doi, 0)
    if isinstance(lbl, dict):
        lbl = lbl.get('label', 0)
    return int(lbl)


def load_pool_topn(combined_dir: Path, topn: int = 200) -> dict:
    pool = {}
    for qfile in sorted(combined_dir.glob('q*.json')):
        qid = qfile.stem
        if qid not in labels_n50:
            continue
        qdata = json.load(open(qfile, encoding='utf-8'))
        rows = []
        for c in qdata.get('results', [])[:topn]:
            doi = c.get('doi', '') or c.get('arxiv_id', '') or ''
            if doi.startswith('https://doi.org/'):
                doi = doi[len('https://doi.org/'):]
            v4 = float(c.get('v4_score', 0) or 0)
            rows.append({'doi': doi, 'v4_score': v4, 'title': c.get('title', '')[:60]})
        pool[qid] = rows
    return pool


def main():
    new_pool = load_pool_topn(new_pool_dir, topn=200)
    old_pool = load_pool_topn(old_pool_dir, topn=200)

    # For each query, find label=2 papers and their positions in new pool
    print('QID  | L2_in_pool | L2_in_old | BestPosNew | BestPosOld | InBothPools')
    print('-' * 80)

    new_better_count = 0
    old_better_count = 0
    equal_count = 0
    missing_in_new = 0

    for qid in sorted(new_pool.keys()):
        if qid not in old_pool:
            continue
        # Find label=2 papers in labels
        l2_dois = [doi for doi, lbl in labels_n50.get(qid, {}).items()
                   if (int(lbl.get('label', 0) if isinstance(lbl, dict) else lbl) == 2)]

        # Position in new pool
        new_doi_to_pos = {r['doi']: i+1 for i, r in enumerate(new_pool[qid])}
        old_doi_to_pos = {r['doi']: i+1 for i, r in enumerate(old_pool[qid])}

        new_positions = [new_doi_to_pos.get(d, 999) for d in l2_dois]
        old_positions = [old_doi_to_pos.get(d, 999) for d in l2_dois]

        # Count in pool (position <= 200)
        in_new = sum(1 for p in new_positions if p <= 200)
        in_old = sum(1 for p in old_positions if p <= 200)
        in_both = sum(1 for d in l2_dois if d in new_doi_to_pos and d in old_doi_to_pos)
        best_new = min([p for p in new_positions if p <= 200], default=999)
        best_old = min([p for p in old_positions if p <= 200], default=999)

        if l2_dois:
            print(f'{qid} | {in_new:2d}/{len(l2_dois):2d}     | {in_old:2d}/{len(l2_dois):2d}    | '
                  f'{best_new:3d}       | {best_old:3d}        | {in_both:2d}')

        if best_new < best_old:
            new_better_count += 1
        elif best_old < best_new:
            old_better_count += 1
        else:
            equal_count += 1

        # Track papers in old but missing in new
        for d in l2_dois:
            if d not in new_doi_to_pos and d in old_doi_to_pos:
                missing_in_new += 1

    print('-' * 80)
    print(f'\nNew ranks better: {new_better_count}')
    print(f'Old ranks better: {old_better_count}')
    print(f'Equal:            {equal_count}')
    print(f'L2 papers in old but missing in new: {missing_in_new}')


if __name__ == '__main__':
    main()
