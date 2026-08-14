"""Diagnose 8-channel fetch issues. Direct probe of each mirror/source."""
import os
import sys
import json
import socket
import urllib.request as ur
import urllib.error

sys.path.insert(0, ".")

print("=" * 60)
print("Proxy env (in Python):")
print("=" * 60)
for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    print(f"  {k} = {os.environ.get(k, '<unset>')!r}")
print()

# Step 1: Direct probe sci-hub mirrors
print("=" * 60)
print("Step 1: Direct probe (raw urllib, no paper-agent code)")
print("=" * 60)
socket.setdefaulttimeout(8)

urls_to_test = [
    # Sci-hub mirrors
    "https://sci-hub.shop",
    "https://sci-hub.ee",
    "https://sci-hub.vg",
    "https://sci-hub.se",
    "https://sci-hub.ru",
    "https://www.sci-hub.st",
    # Anna's archive
    "https://annas-archive.org",
    "https://zh.annas-archive.org",
    # Reference: known working sites
    "https://www.google.com",
    "https://api.openalex.org/works?search=test",
]

for url in urls_to_test:
    try:
        req = ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with ur.urlopen(req, timeout=8) as r:
            body = r.read()
            print(f"  OK  {url:50s} status={r.status} len={len(body)}")
    except ur.HTTPError as e:
        print(f"  HTTP {e.code:3d}  {url:50s}")
    except Exception as e:
        print(f"  ERR  {url:50s} {type(e).__name__}: {str(e)[:80]}")
print()

# Step 2: status_report() with proxy
print("=" * 60)
print("Step 2: status_report() (paper-agent's own probe)")
print("=" * 60)
from pa_cli import fetch
try:
    report = fetch.status_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"  ERR: {type(e).__name__}: {e}")
print()

# Step 3: fetch() with a known DOI
print("=" * 60)
print("Step 3: fetch() with a known DOI (auto cascade)")
print("=" * 60)
try:
    result = fetch.fetch(doi="10.1038/nature12373", out_path="test_output/_diag_nature.pdf")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
except Exception as e:
    print(f"  ERR: {type(e).__name__}: {e}")
