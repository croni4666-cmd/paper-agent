"""Diagnose the actual Unpaywall + annas + sci-hub response details."""
import os
import sys
import time
import re
import json
import zlib
import gzip
from pathlib import Path
from urllib.parse import quote

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import _http_get_bytes, _build_opener

print("=" * 70)
print("DIAGNOSIS 1: Unpaywall — what does the 200 response actually contain?")
print("=" * 70)
s, body = _http_get_bytes("https://api.unpaywall.org/v2/10.1038/nature12373?email=paper-agent@mavis.local",
                          timeout=20)
print(f"  HTTP {s}, raw body: {len(body)}B")
print(f"  first 16 bytes hex: {body[:16].hex()}")
print(f"  looks like gzip? {body[:2] == b'\\x1f\\x8b'}")
print(f"  looks like zlib?  {body[:2] == b'\\x78\\x9c' or body[:2] == b'\\x78\\xda'}")
# Try decoding various ways
for label, fn in [
    ("raw utf-8", lambda: body.decode("utf-8", errors="replace")[:200]),
    ("gzip", lambda: gzip.decompress(body).decode("utf-8", errors="replace")[:200]),
    ("zlib", lambda: zlib.decompress(body).decode("utf-8", errors="replace")[:200]),
    ("zlib (raw)", lambda: zlib.decompress(body, -15).decode("utf-8", errors="replace")[:200]),
]:
    try:
        result = fn()
        print(f"  {label:12} → {result[:150]!r}")
    except Exception as e:
        print(f"  {label:12} → ERR: {str(e)[:80]}")

print()
print("=" * 70)
print("DIAGNOSIS 2: Unpaywall with real-looking email (dengn@gmail.com?)")
print("=" * 70)
for email in ["dengn@gmail.com", "deng.nju@gmail.com"]:
    s, body = _http_get_bytes(
        f"https://api.unpaywall.org/v2/10.1038/nature12373?email={quote(email, safe='@')}",
        timeout=20)
    head = body[:200].decode("utf-8", errors="replace")
    print(f"  {email:30} | HTTP {s} | {len(body):7d}B | first80={head[:80]}")

print()
print("=" * 70)
print("DIAGNOSIS 3: annas-archive — does it have a JSON API?")
print("=" * 70)
# Try common annas API endpoints
for url in [
    "https://annas-archive.org/api/search?q=attention+is+all+you+need",
    "https://annas-archive.gs/api/search?q=attention+is+all+you+need",
    "https://annas-archive.gs/search.json?q=attention+is+all+you+need",
    "https://annas-archive.org/search?q=attention+is+all+you+need&format=json",
    "https://annas-archive.gs/?q=attention+is+all+you+need&format=json",
]:
    s, body = _http_get_bytes(url, timeout=15)
    head = body[:200].decode("utf-8", errors="replace")
    print(f"  {url[:60]:60} | HTTP {s} | {len(body):6d}B | first60={head[:60]}")

print()
print("=" * 70)
print("DIAGNOSIS 4: annas-archive search HTML — extract md5 patterns")
print("=" * 70)
s, body = _http_get_bytes("https://annas-archive.org/search?q=attention+is+all+you+need", timeout=25)
if s == 200:
    head = body.decode("utf-8", errors="replace")
    print(f"  total: {len(body)}B")
    # Find all links that look like /md5/... or /work/...
    md5s = re.findall(r'(?:/md5/|/work/)([a-f0-9]{32})', head)
    unique_md5s = list(dict.fromkeys(md5s))[:5]
    print(f"  md5 patterns found: {unique_md5s}")
    # Find any data attributes
    data_attrs = re.findall(r'data-[a-z\-]+="[^"]+"', head)[:5]
    print(f"  data attrs: {data_attrs}")
    # Find __NEXT_DATA__ or similar
    nd = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', head)
    if nd:
        print(f"  __NEXT_DATA__ present, length={len(nd.group(1))}")
    else:
        print("  no __NEXT_DATA__ (this is a JS-rendered SPA)")
    # Look for any "window.__INITIAL_STATE__" or json blob
    initial = re.search(r'window\.__[A-Z_]+__\s*=\s*(\{)', head)
    if initial:
        print(f"  found initial state, starts at pos {initial.start()}")
    # Sample titles
    titles = re.findall(r'<a[^>]+href="[^"]*md5[^"]*"[^>]*>([^<]+)</a>', head)[:3]
    print(f"  md5-link titles: {titles}")

print()
print("=" * 70)
print("DIAGNOSIS 5: sci-hub mirrors — try different DOIs")
print("=" * 70)
# Pick a well-known DOI that sci-hub probably has
for doi in ["10.1038/nature12373",  # Attention is All You Need
            "10.1126/science.169.3946.635",  # classic
            "10.1145/3422622"]:
    for m in ["https://sci-hub.ee", "https://sci-hub.shop", "https://sci-hub.vg"]:
        url = f"{m}/{doi}"
        s, body = _http_get_bytes(url, timeout=15)
        head = body.decode("utf-8", errors="replace")
        is_pdf = body[:4] == b"%PDF"
        is_hijack = "Mirror" in head or "Telegram" in head
        # Look for sci-hub button or iframe
        has_scihub = "sci-hub" in head.lower() and ("button" in head.lower() or "iframe" in head.lower())
        title_match = re.search(r"<title>([^<]+)</title>", head)
        title = title_match.group(1)[:40] if title_match else "?"
        # extract any pdf link
        pdf_link = re.findall(r'(https?://[^"\'<>\s]+\.pdf)', head)[:1]
        marker = "✓ PDF" if is_pdf else ("⚠️ HIJACK" if is_hijack else
                  f"has_scihub={has_scihub} | title={title} | pdf_link={pdf_link[:1]}")
        print(f"  {m:25} | {doi:35} | HTTP {s:3} | {len(body):6d}B | {marker}")
    print()
