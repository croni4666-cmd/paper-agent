#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 entry_probiotic_meta.json 每个 candidate 加 user_label 字段"""
import json
from pathlib import Path

p = Path(r'G:\minimax - workspace\Paper agent\search_results\entry_probiotic_meta.json')
data = json.loads(p.read_text(encoding='utf-8'))

# 更新 _comment
data['_comment'] = (
    'Entry draft for Mavis user review. Use: pa sample-pool add --from-file '
    'entry_probiotic_meta.json --confirm-y. user_label is for human assessment '
    '(initially null; user fills in entry_probiotic_meta.md, then Mavis syncs '
    'back to this JSON). Mavis label = Mavis suggestion only; user can override '
    'via pa sample-pool label --confirm-y after add.'
)

# 给每个 candidate 加 user_label 默认 null + 插在 label_notes 前
for i, c in enumerate(data.get('candidates', [])):
    if 'user_label' not in c:
        new_c = {}
        for k, v in c.items():
            if k == 'label_notes':
                new_c['user_label'] = None
                new_c['user_label_notes'] = ''
            new_c[k] = v
        data['candidates'][i] = new_c

# 加 user_label_summary 占位
data['_user_label_summary'] = {
    '_note': 'user_label 分布，等 Mavis 同步 user 在 .md 里的打分后填',
    '3 (highly relevant)': [],
    '2 (relevant)': [],
    '1 (marginal)': [],
    '0 (irrelevant)': [],
    'skipped (-)': []
}

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[done] {p}')
print(f'  candidates updated: {len(data["candidates"])}')
print(f'  new field: user_label (default null) + user_label_notes (default "")')
print(f'  size now: {p.stat().st_size / 1024:.1f} KB')
