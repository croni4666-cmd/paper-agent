"""Diagnose Unpaywall auth: is it really email-gated, or IP-gated via clash?"""
import os
import sys
import urllib.request as ur
import urllib.error
import json
import gzip
import zlib
from urllib.parse import quote

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Build proxy opener
proxy_handler = ur.ProxyHandler({
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897"
})
opener = ur.build_opener(proxy_handler)


def test_with_headers(url, label):
    """Get response with full headers and try all decode methods."""
    print(f"\n--- {label} ---")
    print(f"  URL: {url}")
    req = ur.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://unpaywall.org/",
    })
    try:
        with opener.open(req, timeout=20) as r:
            body = r.read()
            print(f"  HTTP {r.status}")
            # Show ALL response headers
            for h, v in r.getheaders():
                print(f"    {h}: {v[:80]}")
            # Try gzip then zlib then raw
            decoded = None
            for label_d, fn in [
                ("raw", lambda: body),
                ("gzip", lambda: gzip.decompress(body)),
                ("zlib", lambda: zlib.decompress(body)),
                ("zlib_raw", lambda: zlib.decompress(body, -15)),
            ]:
                try:
                    out = fn()
                    if label_d == "raw":
                        decoded = out
                    else:
                        print(f"  {label_d} decode OK → {len(out)}B")
                        decoded = out
                        break
                except Exception as e:
                    if label_d != "raw":
                        print(f"  {label_d} decode FAIL: {e}")
            if decoded:
                text = decoded.decode("utf-8", errors="replace")[:500]
                print(f"  first 300 chars: {text[:300]}")
                # Try JSON parse
                try:
                    d = json.loads(decoded)
                    print(f"  JSON OK | title={d.get('title','')[:50]!r} | "
                          f"best_oa={(d.get('best_oa_location') or {}).get('url','')[:60]}")
                except Exception:
                    pass
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            d = json.loads(body.decode("utf-8"))
            print(f"  HTTP {e.code} | JSON err: {d.get('message','')[:150]}")
        except Exception:
            print(f"  HTTP {e.code} | {len(body)}B | first100={body[:100]!r}")


# Test 1: With DengN's likely real email
test_with_headers("https://api.unpaywall.org/v2/10.1038/nature12373?email=impactstory@example.com",
                  "Test 1: random plausible email via proxy")

# Test 2: Same email, NO proxy
print("\n\n=== WITHOUT PROXY ===")
del os.environ["HTTPS_PROXY"]
del os.environ["HTTP_PROXY"]
opener_noproxy = ur.build_opener()
# Re-patch the test function
def test_noproxy(url, label):
    print(f"\n--- {label} ---")
    print(f"  URL: {url}")
    req = ur.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/html,*/*",
    })
    try:
        with opener_noproxy.open(req, timeout=20) as r:
            body = r.read()
            print(f"  HTTP {r.status}")
            for h, v in r.getheaders()[:5]:
                print(f"    {h}: {v[:80]}")
            try:
                d = json.loads(body.decode("utf-8"))
                print(f"  JSON OK | title={d.get('title','')[:50]!r} | "
                      f"best_oa={(d.get('best_oa_location') or {}).get('url','')[:60]}")
            except Exception as e:
                print(f"  NOT JSON: {e} | first200={body[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            d = json.loads(body.decode("utf-8"))
            print(f"  HTTP {e.code} | JSON err: {d.get('message','')[:150]}")
        except Exception:
            print(f"  HTTP {e.code} | first100={body[:100]!r}")
    except Exception as e:
        print(f"  ERR: {e}")

test_noproxy("https://api.unpaywall.org/v2/10.1038/nature12373?email=impactstory@example.com",
             "Test 3: same email WITHOUT proxy")
