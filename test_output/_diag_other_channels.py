"""Diagnostic: 30-min, see which 'broken' channels are fixable.

Tests:
  A. annas — does fetch_annas_search actually search correctly?
     Test 1: query "10.1038/nature12373" (full DOI)
     Test 2: query "nature12373" (DOI tail)
     Test 3: query by title "Epigenetic inheritance"
  B. unpaywall — what kind of SSL/TLS error is it really?
     Test 1: urllib (current implementation)
     Test 2: requests library with verify=True
     Test 3: requests library with verify=False
  C. annas direct — does annas.org have the paper?
     (we'll just test the API endpoint via curl conceptually;
      skip if too involved)
"""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=" * 78)
print("Diagnostic: annas + unpaywall — bug or 'correctly no-hit'?")
print("=" * 78)

# ─── A. annas ─────────────────────────────────────────────────
print()
print("=" * 78)
print("A. annas — fetch_annas_search behavior")
print("=" * 78)

try:
    from pa_cli.fetch import fetch_annas_search
    queries = [
        "10.1038/nature12373",          # full DOI
        "nature12373",                  # DOI tail
        "Epigenetic inheritance",       # title
    ]
    for q in queries:
        print(f"\n  query: {q!r}")
        try:
            results = fetch_annas_search(q, limit=3)
            if not results:
                print(f"    -> [] (no results)")
            else:
                for i, r in enumerate(results[:3]):
                    md5 = r.get("md5_path", r.get("md5", "?"))
                    domain = r.get("domain", "?")
                    title = (r.get("title") or r.get("name") or "")[:60]
                    print(f"    [{i+1}] md5={md5}  domain={domain}  title={title!r}")
        except Exception as e:
            print(f"    -> EXCEPTION: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  fetch_annas_search not importable: {e}")

# ─── B. unpaywall ──────────────────────────────────────────────
print()
print("=" * 78)
print("B. unpaywall — TLS/SSL real cause")
print("=" * 78)

import socket
import urllib.request
import urllib.error
import ssl

email = os.environ.get("UNPAYWALL_EMAIL", "").strip() or "hello@example.com"
test_doi = "10.1038/nature12373"
url = f"https://api.unpaywall.org/v2/{test_doi}?email={email}"

print(f"\n  url: {url}")
print(f"  email: {email!r}")

# B.1: urllib (current implementation)
print("\n  B.1 urllib (default)...")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent/diagnostic"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        print(f"    -> status={resp.status}  body[:200]={body[:200]!r}")
except urllib.error.URLError as e:
    print(f"    -> URLError: {e.reason} (errno={getattr(e, 'errno', None)})")
    if hasattr(e, 'reason') and isinstance(e.reason, ssl.SSLError):
        print(f"    -> SSLError: {e.reason.reason}  (verify={e.reason.verify}")
        print(f"    -> verify_mode: {e.reason.verify_mode}")
except Exception as e:
    print(f"    -> {type(e).__name__}: {e}")

# B.2: requests with verify=True
print("\n  B.2 requests with verify=True...")
try:
    import requests
    r = requests.get(url, timeout=30, verify=True)
    print(f"    -> status={r.status_code}  body[:200]={r.content[:200]!r}")
except requests.exceptions.SSLError as e:
    print(f"    -> SSLError: {e}")
except Exception as e:
    print(f"    -> {type(e).__name__}: {e}")

# B.3: requests with verify=False
print("\n  B.3 requests with verify=False...")
try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(url, timeout=30, verify=False)
    print(f"    -> status={r.status_code}  body[:200]={r.content[:200]!r}")
except Exception as e:
    print(f"    -> {type(e).__name__}: {e}")

# B.4: SSL handshake detail
print("\n  B.4 SSL handshake detail (what cipher is offered)...")
try:
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(socket.socket(), server_hostname="api.unpaywall.org") as s:
        s.settimeout(10)
        s.connect(("api.unpaywall.org", 443))
        cert = s.getpeercert()
        print(f"    -> connected. cipher={s.cipher()!r}")
        # Print first cert subject
        if cert and 'subject' in cert:
            print(f"    -> cert subject: {cert['subject'][0]}")
except Exception as e:
    print(f"    -> {type(e).__name__}: {e}")

# ─── C. PA-level fetch with annas prefer ────────────────────
print()
print("=" * 78)
print("C. pa fetch with --prefer annas (Nature DOI) — see what query gets used")
print("=" * 78)

try:
    from pa_cli.fetch import fetch
    r = fetch("10.1038/nature12373", prefer="annas")
    print(f"  result: {r}")
except Exception as e:
    print(f"  EXCEPTION: {type(e).__name__}: {e}")
