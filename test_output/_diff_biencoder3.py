import json
no_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001', encoding='utf-8'))
with_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001.json', encoding='utf-8'))
no_dois = [c.get("doi") for c in no_ext["results"]]
we_dois = [c.get("doi") for c in with_ext["results"]]
# Find diffs
for i, (a, b) in enumerate(zip(no_dois, we_dois)):
    if a != b:
        print(f'  idx {i}: no_ext={a!r}  vs  with_ext={b!r}')
# Compare labels mapping
labels = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\labels_clean.json', encoding='utf-8'))['labels']['q001']
print()
print('q001 labels (cleaned):')
for doi, info in labels.items():
    print(f'  {doi}: label={info.get("label")}')
# In no_ext, build label vector
print()
print('no_ext label vector:')
for c in no_ext["results"]:
    doi = c.get("doi", "").strip()
    label = labels.get(doi, {}).get("label", 0)
    if label:
        print(f'  {doi}: {label}')
print()
print('with_ext label vector:')
for c in with_ext["results"]:
    doi = c.get("doi", "").strip()
    label = labels.get(doi, {}).get("label", 0)
    if label:
        print(f'  {doi}: {label}')
