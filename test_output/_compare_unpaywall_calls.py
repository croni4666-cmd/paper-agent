"""Compare web_fetch vs pa_cli for same Unpaywall call."""
import os
import sys
import json

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import urllib.request as ur
import urllib.error

URL = "https://api.unpaywall.org/v2/10.1038/nature12373?email=developers@unpaywall.org"


def call_with(method_name, headers, use_proxy):
    print(f"\n=== {method_name} (proxy={use_proxy}) ===")
    print(f"  headers: {headers}")
    if use_proxy:
        opener = ur.build_opener(ur.ProxyHandler({
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }))
    else:
        opener = ur.build_opener()
    req = ur.Request(URL, headers=headers)
    try:
        with opener.open(req, timeout=20) as r:
            body = r.read()
            print(f"  HTTP {r.status} | body={len(body)}B | first16={body[:16].hex()}")
            for h, v in r.getheaders()[:8]:
                print(f"    {h}: {v[:80]}")
            try:
                d = json.loads(body)
                print(f"  ✓ JSON OK | title={d.get('title','')[:40]!r} | "
                      f"oa={((d.get('best_oa_location') or {}).get('url','') or '')[:60]}")
            except Exception as e:
                print(f"  ✗ JSON fail: {e}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            d = json.loads(body)
            print(f"  HTTP {e.code} | err: {d.get('message','')[:100]}")
        except Exception:
            print(f"  HTTP {e.code} | {body[:100]!r}")


# Test 1: simple UA, no proxy (mimics web_fetch)
call_with("simple UA, no proxy", {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}, use_proxy=False)

# Test 2: simple UA, with proxy
call_with("simple UA, with proxy", {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}, use_proxy=True)

# Test 3: paper-agent UA, no proxy
call_with("paper-agent UA, no proxy", {
    "User-Agent": "paper-agent/3.2 (Mavis; mailto:hello@example.com)",
    "Accept": "application/json",
}, use_proxy=False)

# Test 4: paper-agent UA, with proxy
call_with("paper-agent UA, with proxy", {
    "User-Agent": "paper-agent/3.2 (Mavis; mailto:hello@example.com)",
    "Accept": "application/json",
}, use_proxy=True)

# Test 5: full browser headers, no proxy
call_with("full Chrome 120, no proxy", {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://unpaywall.org/",
}, use_proxy=False)

# Test 6: full Chrome 120, with proxy
call_with("full Chrome 120, with proxy", {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://unpaywall.org/",
}, use_proxy=True)
