"""Plan 3 step F: test real CNKI search on multiple queries."""
import json
import sys
import time
from pa_cli.cnki_channel import search_cnki

tests = [
    ("东数西算", 5, "subject", "all"),
    ("东数西算", 25, "subject", "all"),  # tests pagination (25 > 20)
    ("深度学习", 5, "subject", "journal"),
    ("保险精算", 5, "title", "all"),
]

for query, limit, field, db in tests:
    print(f'\n=== Test: query={query!r} limit={limit} field={field} db={db} ===', file=sys.stderr)
    t0 = time.time()
    r = search_cnki(query, limit=limit, field=field, db=db)
    t1 = time.time()

    print(f'  Time: {t1-t0:.1f}s', file=sys.stderr)
    print(f'  Results: {len(r)}', file=sys.stderr)
    if r and 'error' in r[0]:
        print(f'  ERROR: {r[0]}', file=sys.stderr)
        continue
    for i, p in enumerate(r):
        if 'error' in p:
            print(f'  [{i}] ERROR: {p}', file=sys.stderr)
            break
        print(f'  [{i}] {p.get("title", "")[:60]}', file=sys.stderr)
        print(f'       venue={p.get("venue")!r}, year={p.get("year")}, type={p.get("type")!r}', file=sys.stderr)
        print(f'       cited={p.get("cited_by_count")}, dl={p.get("download_count")}', file=sys.stderr)
        print(f'       authors={p.get("authors")}', file=sys.stderr)
        print(f'       cnki_filename={p.get("cnki_filename")!r}', file=sys.stderr)
        print(f'       doi={p.get("doi", "")[:40]!r}', file=sys.stderr)
        print(f'       cnki_url[:80]={p.get("cnki_url", "")[:80]!r}', file=sys.stderr)
        print(f'       full source={p.get("source")!r}, abstract={p.get("abstract", "")[:50]!r}', file=sys.stderr)
        print(file=sys.stderr)
