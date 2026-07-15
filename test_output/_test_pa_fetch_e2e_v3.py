"""End-to-end test of pa fetch with clash proxy on 7897."""
import os
import sys
import time
import re
from pathlib import Path

# Force UTF-8 stdout for emoji / non-ASCII
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Set proxy BEFORE importing pa_cli.fetch
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"

sys.path.insert(0, "G:/minimax - workspace/Paper agent")

from pa_cli.fetch import (
    status_report,
    fetch_unpaywall_doi,
    fetch_scihub_doi,
    fetch_annas_search,
    fetch_annas_md5,
    fetch,
    _http_get_bytes,
    SCIHUB_MIRRORS,
    ANNAS_DOMAINS,
)

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("STEP 1: Health check (via proxy 7897)")
print("=" * 70)
h = status_report()
print(f"  scihub: {h['scihub']}")
print(f"  annas:  {h['annas']}")

print()
print("=" * 70)
print("STEP 2: Unpaywall — try various emails")
print("=" * 70)
from urllib.parse import quote

for email in ["paper-agent@mavis.local", "test@example.com", "dengn@example.com"]:
    url = f"https://api.unpaywall.org/v2/10.1038/nature12373?email={quote(email, safe='@')}"
    s, body = _http_get_bytes(url, timeout=15)
    head = body[:300].decode("utf-8", errors="replace")
    if s == 200 and '"title"' in head:
        import json
        try:
            d = json.loads(body)
            oa = (d.get("best_oa_location") or {}).get("url", "")
            print(f"  email={email:35} | HTTP {s} | title={d.get('title','')[:40]!r} | oa_url={oa[:60]}")
        except Exception:
            print(f"  email={email:35} | HTTP {s} | (json parse fail)")
    else:
        # avoid !r repr (PowerShell GBK codec) — just print slice
        print(f"  email={email:35} | HTTP {s} | first150={head[:150]}")

print()
print("=" * 70)
print("STEP 3: sci-hub each mirror (real DOI path)")
print("=" * 70)
for m in SCIHUB_MIRRORS:
    url = f"{m}/10.1038/nature12373"
    t0 = time.time()
    s, body = _http_get_bytes(url, timeout=20)
    dt = time.time() - t0
    head = body[:600].decode("utf-8", errors="replace")
    is_pdf = body[:4] == b"%PDF"
    has_doi_link = "doi" in head.lower() and ("download" in head.lower() or ".pdf" in head.lower())
    if is_pdf:
        mark = f"✓ PDF {len(body)}B"
    elif "Sci-Hub" in head and ("article" in head.lower() or "pdf" in head.lower()):
        # extract PDF link
        pdfs = re.findall(r'(https?://[^"\'<>\s]+\.pdf)', head)
        mark = f"✓ real sci-hub page | embed_pdfs={pdfs[:1]}"
    elif "Mirror" in head or "Telegram" in head:
        mark = "⚠️ HIJACK"
    elif "Cloudflare" in head:
        mark = "⚠️ CF"
    else:
        t_match = re.search(r"<title>([^<]+)</title>", head)
        mark = f"HTML | {t_match.group(1)[:50] if t_match else '?'}"
    print(f"  {m:30} HTTP {s:3} t={dt:5.1f}s | {len(body):8d}B | {mark}")

print()
print("=" * 70)
print("STEP 4: fetch_scihub_doi() — actual function with all mirrors")
print("=" * 70)
r = fetch_scihub_doi("10.1038/nature12373", out_path=str(OUT_DIR / "scihub_nature.pdf"))
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | err={r.get('error')}")
if r.get("tried_mirrors"):
    print(f"  tried: {r['tried_mirrors']}")

print()
print("=" * 70)
print("STEP 5: annas-archive — search via real query (via proxy)")
print("=" * 70)
for d in ANNAS_DOMAINS:
    url = f"{d}/search?q=attention+is+all+you+need"
    t0 = time.time()
    s, body = _http_get_bytes(url, timeout=25)
    dt = time.time() - t0
    head = body.decode("utf-8", errors="replace")
    md5s = list(dict.fromkeys(re.findall(r'/md5/([a-f0-9]{32})', head)))[:3]
    t_match = re.search(r"<title>([^<]+)</title>", head)
    title = t_match.group(1)[:40] if t_match else "?"
    print(f"  {d:35} HTTP {s:3} t={dt:5.1f}s | {len(body):8d}B | title={title!r} | md5s={md5s}")

print()
print("=" * 70)
print("STEP 6: fetch_annas_search() — actual function")
print("=" * 70)
r = fetch_annas_search("attention is all you need", limit=5)
print(f"  ok={r.get('ok')} | n={r.get('n', 0)} | err={r.get('error')}")
for it in r.get("results", [])[:5]:
    print(f"  - {str(it.get('title',''))[:60]:60} | md5={it.get('md5','')[:16]:16} | size={it.get('size','')}")

print()
print("=" * 70)
print("STEP 7: end-to-end fetch() with prefer='auto' (DOI 10.1038/nature12373)")
print("=" * 70)
r = fetch(doi="10.1038/nature12373", out_path=str(OUT_DIR / "auto_nature.pdf"), prefer="auto")
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | err={r.get('error')}")
if r.get("chain"):
    for step in r["chain"]:
        ok = "✓" if step.get("ok") else "✗"
        print(f"  {ok} {step.get('source'):12} | {step.get('err', 'ok')}")
