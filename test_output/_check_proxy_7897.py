"""Test if 127.0.0.1:7897 is clash HTTP proxy that bypasses GFW."""
import urllib.request as ur
import urllib.error
import json
import time

PROXIES = {
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897",
}

# Build opener with proxy
proxy_handler = ur.ProxyHandler(PROXIES)
opener = ur.build_opener(proxy_handler)
ur.install_opener(opener)


def test(name, url, hdr=None, timeout=15):
    req = ur.Request(url, headers=hdr or {"User-Agent": "paper-agent/3.9.8.2 (proxy test)"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read()
            dt = time.time() - t0
            head = body[:200].decode("utf-8", errors="replace")
            print(f"  {name:30} HTTP {r.status} t={dt:.1f}s | {len(body):7d}B | {head[:80].replace(chr(10),' ')!r}")
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        dt = time.time() - t0
        print(f"  {name:30} HTTP {e.code} t={dt:.1f}s | {len(body):7d}B | {body[:100]!r}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  {name:30} ERR  t={dt:.1f}s | {str(e)[:80]}")


print("=" * 70)
print("With proxy 127.0.0.1:7897")
print("=" * 70)
test("annas home",      "https://annas-archive.org/")
test("zh.annas home",   "https://zh.annas-archive.org/")
test("sci-hub.ee",      "https://sci-hub.ee/10.1038/nature12373")
test("sci-hub.shop",    "https://sci-hub.shop/10.1038/nature12373")
test("unpaywall (real)", "https://api.unpaywall.org/v2/10.1038/nature12373?email=test@example.com")
test("crossref",         "https://api.crossref.org/works?query.bibliographic=test&rows=1")
test("aminer",          "https://datacenter.aminer.cn/gateway/open_platform/api/paper/search?query=test&size=1")
