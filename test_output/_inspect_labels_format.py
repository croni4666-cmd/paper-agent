"""Inspect labels_n50_mixed.json format."""
import json
labels = json.load(open('bench/v01/labels_n50_mixed.json', encoding='utf-8'))
print(f'n_queries: {labels["n_queries"]}')
print(f'label_source: {labels["label_source"]}')
print(f'labels type: {type(labels["labels"]).__name__}')
print(f'labels keys (first 5): {list(labels["labels"].keys())[:5]}')
first_q = list(labels['labels'].keys())[0]
first_l = labels['labels'][first_q]
print(f'first_q={first_q}, type={type(first_l).__name__}, len={len(first_l) if hasattr(first_l,"__len__") else "N/A"}')
if isinstance(first_l, list):
    print(f'first item: {first_l[0]}')
elif isinstance(first_l, dict):
    print(f'first 3 items: {list(first_l.items())[:3]}')
