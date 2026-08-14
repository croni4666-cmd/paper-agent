"""Test search.pedro.org.au — the real PEDro search subdomain."""
import urllib.request
import urllib.parse

# Test 1: simple search page (HTML)
req = urllib.request.Request(
    "https://search.pedro.org.au/search",
    headers={"User-Agent": "paper-agent/3.9.11.9"}
)
with urllib.request.urlopen(req, timeout=20) as r:
    html = r.read()[:2000].decode("utf-8", errors="replace")
    print(f"Test 1: search.pedro.org.au/search status={r.status} ct={r.headers.get('Content-Type')}")
    print(f"  body[:500]: {html[:500]!r}")

# Test 2: look for API or form action
import re
forms = re.findall(r'<form[^>]+action=["\']([^"\']+)["\']', html)
inputs = re.findall(r'<input[^>]+name=["\']([^"\']+)["\']', html)
print(f"\nTest 2: forms on search page: {forms[:5]}")
print(f"        inputs: {inputs[:10]}")

# Test 3: POST a real search query
search_data = urllib.parse.urlencode({
    "q": "cervical muscle training",
    "field": "title",
}).encode()
req2 = urllib.request.Request(
    "https://search.pedro.org.au/search",
    data=search_data, method="POST",
    headers={
        "User-Agent": "paper-agent/3.9.11.9",
        "Content-Type": "application/x-www-form-urlencoded",
    }
)
try:
    with urllib.request.urlopen(req2, timeout=20) as r:
        body = r.read()[:2000].decode("utf-8", errors="replace")
        print(f"\nTest 3: POST search status={r.status} ct={r.headers.get('Content-Type')}")
        print(f"        body[:500]: {body[:500]!r}")
except urllib.error.HTTPError as e:
    print(f"\nTest 3: HTTPError {e.code}")
    body = e.read()[:2000].decode("utf-8", errors="replace")
    print(f"        body[:500]: {body[:500]!r}")
except Exception as e:
    print(f"\nTest 3: EXC {type(e).__name__}: {e}")

# Test 4: try JSON endpoint guess
for guess in [
    "https://search.pedro.org.au/api/v1/search",
    "https://search.pedro.org.au/api/search.json",
    "https://search.pedro.org.au/api/trials?q=cervical",
]:
    try:
        req3 = urllib.request.Request(
            guess,
            headers={"User-Agent": "paper-agent/3.9.11.9", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req3, timeout=15) as r:
            body = r.read()[:300]
            print(f"\n{guess}: status={r.status} ct={r.headers.get('Content-Type')} body[:100]={body[:100]!r}")
    except Exception as e:
        print(f"\n{guess}: {type(e).__name__}: {e}")
