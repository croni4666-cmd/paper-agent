"""Test xueshu789 /doDownload/ endpoint with real URL from user."""
import os
import sys
import time

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.cnki_channel import load_cookies
from urllib.parse import unquote

# User provided URL (2026-07-16 08:50)
URL = ("https://www.xueshu789.com/doDownload/?url=https%3A%2F%2Fkns.cnki.net%2Fkcms2%"
       "2Farticle%2Fabstract%3Fv%3Df9AMVDUgxC_OuazwymVvBxgHDIBv4x52x9Rkpx7zB-geVMjbVsf"
       "H5I80mL6RZM84X1vJ5gmsuTNZqRWzwdbEZN26eX4mQ6UjqU6y1GII2Lb1aAnEnZL3ehSOmu"
       "GZYoYFg_u_7JSIMCpfT1KZgUwPVaJxrwXIlH-KSqyxxXg4r-J6sKBFoFCZYQ%3D%3D%26uniplat"
       "form%3DNZKPT%26language%3DCHS&ddata=TJJC2026071000N%7CCAPJ%7C%E6%95%B0%E5%AD%97%"
       "E6%99%AE%E6%83%A0%E9%87%91%E8%9E%8D%E8%B5%8B%E8%83%BD%E5%8E%BF%E5%9F%9F%E7%BB%"
       "8F%E6%B5%8E%E9%AB%98%E8%B4%A8%E9%87%8F%E5%8F%91%E5%B1%95%EF%BC%9A%E7%BB%9F%"
       "E8%AE%A1%E6%B5%8B%E5%BA%A6%E4%B8%8E%E6%95%88%E5%BA%94%E6%A3%80%E9%AA%8C%7CCAPJ%"
       "7C7724aa3100d17d57a8193034fb81ba13")

print(f"URL length: {len(URL)}")
print(f"Decoded ddata: {unquote(URL.split('ddata=', 1)[1])[:200]}")
print()

# Load user cookies
cookies = load_cookies()
print(f"Loaded {len(cookies)} cookies from cnki.json")
for c in cookies:
    print(f"  {c['name']:15} = {c['value'][:20]}... | domain={c.get('domain')}")

# Build cookie header string
cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
print(f"\nCookie header: {cookie_header[:100]}...")

# Use urllib with cookies + proxy
import urllib.request as ur
import urllib.error

req = ur.Request(URL, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cookie": cookie_header,
    "Referer": "https://www.xueshu789.com/dbList/1",
})

print("\nFetching via urllib (with cookies + clash proxy on 7897)...")
t0 = time.time()
try:
    with ur.urlopen(req, timeout=30) as r:
        body = r.read()
        dt = time.time() - t0
        print(f"  HTTP {r.status} | t={dt:.1f}s | {len(body):,}B")
        for h, v in r.getheaders()[:8]:
            print(f"    {h}: {v[:80]}")
        # Check if PDF
        is_pdf = body[:4] == b"%PDF"
        if is_pdf:
            print(f"\n  [OK] IS PDF! Saving to disk...")
            out = "G:/minimax - workspace/Paper agent/test_output/_fetch_e2e_cnki/dodownload_real.pdf"
            import os
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(body)
            print(f"  Saved: {out} ({len(body):,}B)")
        else:
            head = body[:2000].decode("utf-8", errors="replace")
            print(f"\n  [X] Not PDF. First 1500 chars:")
            print(head[:1500])
            # Save to debug file
            dbg = "G:/minimax - workspace/Paper agent/test_output/_debug_dodownload.html"
            with open(dbg, "w", encoding="utf-8") as f:
                f.write(head)
            print(f"\n  Saved to {dbg}")
except urllib.error.HTTPError as e:
    body = e.read() if hasattr(e, "read") else b""
    dt = time.time() - t0
    print(f"  HTTP {e.code} | t={dt:.1f}s | {len(body):,}B")
    print(f"  body: {body[:200]!r}")
except Exception as e:
    dt = time.time() - t0
    print(f"  ERR t={dt:.1f}s: {e}")

import time
