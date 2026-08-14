"""Test annas through HTTPS_PROXY=10808 (already configured proxy)."""
import os
import re
import urllib.parse
import urllib.request
import socket

# Set proxy before anything else
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10808"

domains = [
    "https://annas-archive.org",
    "https://annas-archive.se",
]

q = urllib.parse.quote("nature genetics")
print("=" * 70)
print("annas via HTTPS_PROXY=10808")
print("=" * 70)
for d in domains:
    print(f"\n--- {d} ---")
    try:
        url = f"{d}/search?q={q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/120.0.0.0"},
        )
        # Use ProxyHandler from urllib
        proxy_handler = urllib.request.ProxyHandler({
            "http": "http://127.0.0.1:10808",
            "https": "http://127.0.0.1:10808",
        })
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(req, timeout=30) as resp:
            body = resp.read()
            print(f"  HTTPS via proxy: status={resp.status}  bytes={len(body)}")
            pat = re.compile(r'/md5/([a-f0-9]{32})')
            hits = pat.findall(body.decode("utf-8", errors="replace"))
            print(f"  md5 hits: {len(hits)}")
            if hits:
                print(f"  first 3: {hits[:3]}")
    except Exception as e:
        print(f"  EXC: {type(e).__name__}: {e}")

# Also: check if the paper-agent _get_proxy_dict picks it up
print()
print("=" * 70)
print("paper-agent _get_proxy_dict behavior")
print("=" * 70)
import sys
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
from pa_cli.fetch import _get_proxy_dict
pd = _get_proxy_dict()
print(f"  proxy dict: {pd}")
