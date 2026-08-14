import json
data = json.load(open('search_sez_fdi.json', encoding='utf-8'))
results = data.get('results', [])
print(f"Total results: {len(results)}")
print(f"By engine: {data.get('by_engine')}")
print()
print("=== Filtered by author (Liu/Plouffe) or title (SEZ/FDI/Shantou) ===")
for i, p in enumerate(results):
    title = (p.get('title') or '').lower()
    auth = ' '.join([a.get('name','') if isinstance(a, dict) else str(a) for a in (p.get('authors') or [])]).lower()
    if ('liu' in auth or 'plouffe' in auth or
        'special economic' in title or
        'foreign direct investment' in title or
        'shantou' in title or 'shenzhen' in title or 'shantou' in title):
        title_disp = (p.get('title') or '')[:100]
        auth_disp = ' '.join([a.get('name','') if isinstance(a, dict) else str(a) for a in (p.get('authors') or [])])[:80]
        eng = p.get('engine', '?')
        yr = p.get('year', '?')
        doi = p.get('doi') or ''
        url = p.get('source_url') or p.get('url') or ''
        print(f"{i:2d}. [{eng:12s}|{yr}] {title_disp}")
        print(f"    auth: {auth_disp}")
        if doi: print(f"    doi:  {doi}")
        if url: print(f"    url:  {url[:100]}")
        cited = p.get('cited_by_count')
        if cited is not None:
            print(f"    cited_by: {cited}")
        print()
