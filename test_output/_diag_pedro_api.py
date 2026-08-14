"""Test if PEDro has a clean JSON API or only HTML search form."""
import json
import os
import urllib.request
import urllib.error

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"


def test_url(url, method="GET", data=None, accept="*/*"):
    """Try URL, return (status, content_type, first 500 bytes of body, error)."""
    try:
        req = urllib.request.Request(
            url, method=method, data=data,
            headers={"User-Agent": "paper-agent/3.9.11.9", "Accept": accept}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()[:500]
            return r.status, r.headers.get("Content-Type", "?"), body, None
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "?") if e.headers else "?", b"", f"HTTP {e.code}"
    except Exception as e:
        return 0, "?", b"", f"{type(e).__name__}: {e}"


print("=" * 70)
print("PEDro API reality check")
print("=" * 70)

# Test 1: simple search form (advanced search page)
status, ct, body, err = test_url(
    "https://pedro.org.au/english/search/",
    accept="text/html"
)
print(f"\n--- Test 1: search form GET (HTML) ---")
print(f"  status: {status}, content-type: {ct}")
print(f"  body[:200]: {body[:200]!r}")
print(f"  err: {err}")

# Test 2: POST search with simple query (mimics the form submit)
# Per PEDro website, the search form posts to itself with form data
search_data = urllib.parse.urlencode({
    "search_text": "cervical muscle training",
    "submit": "Search",
}).encode()
status, ct, body, err = test_url(
    "https://pedro.org.au/english/search/",
    method="POST", data=search_data,
    accept="text/html"
)
print(f"\n--- Test 2: search form POST (cervical muscle training) ---")
print(f"  status: {status}, content-type: {ct}")
print(f"  body[:300]: {body[:300]!r}")
print(f"  err: {err}")

# Test 3: look for any obvious JSON endpoint
for guess in [
    "https://pedro.org.au/api/search",
    "https://pedro.org.au/english/api/search",
    "https://api.pedro.org.au/v1/search",
    "https://pedro.org.au/search.json?q=cervical",
]:
    status, ct, body, err = test_url(guess, accept="application/json")
    print(f"\n--- {guess} ---")
    print(f"  status: {status}, content-type: {ct}, err: {err}")
    print(f"  body[:200]: {body[:200]!r}")

# Test 4: OAI-PMH endpoint (some databases have this)
status, ct, body, err = test_url(
    "https://pedro.org.au/oai-pmh/",
    accept="application/xml"
)
print(f"\n--- Test 4: OAI-PMH endpoint ---")
print(f"  status: {status}, content-type: {ct}")
print(f"  body[:200]: {body[:200]!r}")
print(f"  err: {err}")
