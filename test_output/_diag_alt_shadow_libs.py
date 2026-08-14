"""Test alternative shadow library domains for reachability."""
import os
import re
import socket
import urllib.parse
import urllib.request

# Try both direct and via proxy
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

candidates = [
    # annas-archive mirrors
    ("https://annas-archive.org", "annas main"),
    ("https://annas-archive.se", "annas .se"),
    # z-library mirrors
    ("https://z-lib.org", "z-lib main"),
    ("https://1lib.sk", "1lib.sk"),
    # libgen mirrors
    ("https://libgen.rs", "libgen.rs"),
    ("https://libgen.li", "libgen.li"),
    ("https://libgen.st", "libgen.st"),
    # bookfi / booksc
    ("https://bookfi.net", "bookfi.net"),
    ("https://booksc.org", "booksc.org"),
    # sci-hub (already works, sanity check)
    ("https://sci-hub.se", "sci-hub.se"),
    # Anna's archive MD5 mirror
    ("https://aannas.com", "aannas (third-party)"),
    ("https://annas-archive.li", "annas .li"),
]

print("=" * 70)
print("Alternative shadow lib reachability (direct + proxy)")
print("=" * 70)
print(f"{'Domain':45s}  {'Direct':12s}  {'Proxy':12s}")
print("-" * 70)
for url, label in candidates:
    host = url.replace("https://", "").replace("http://", "")
    label_str = f"{label} ({host})"[:43]
    # Direct
    direct = "?"
    try:
        s = socket.create_connection((host, 443), timeout=8)
        s.close()
        direct = "OK"
    except Exception as e:
        direct = f"FAIL ({type(e).__name__})"
    # Via proxy
    proxy_res = "?"
    try:
        proxy_handler = urllib.request.ProxyHandler({
            "http": "http://127.0.0.1:10808",
            "https": "http://127.0.0.1:10808",
        })
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(
            f"https://{host}/",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with opener.open(req, timeout=15) as resp:
            proxy_res = f"OK ({resp.status})"
    except Exception as e:
        proxy_res = f"FAIL ({type(e).__name__})"
    print(f"{label_str:45s}  {direct:12s}  {proxy_res:12s}")
