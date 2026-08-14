"""Test all 4 annas domains for reachability."""
import re
import socket
import urllib.parse
import urllib.request

domains = [
    "https://annas-archive.org",
    "https://zh.annas-archive.org",
    "https://annas-archive.gs",
    "https://annas-archive.se",
]

q = urllib.parse.quote("nature genetics")  # use a common term

print("=" * 70)
print("annas-archive 4 domains reachability test")
print("=" * 70)
for d in domains:
    print(f"\n--- {d} ---")
    # DNS resolution
    host = d.replace("https://", "").replace("http://", "")
    try:
        ip = socket.gethostbyname(host)
        print(f"  DNS: {ip}")
    except Exception as e:
        print(f"  DNS FAIL: {type(e).__name__}: {e}")
        continue
    # TCP connect on 443
    try:
        sock = socket.create_connection((host, 443), timeout=10)
        sock.close()
        print(f"  TCP 443: OK")
    except Exception as e:
        print(f"  TCP 443 FAIL: {type(e).__name__}: {e}")
        continue
    # HTTPS GET
    try:
        url = f"{d}/search?q={q}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/120.0.0.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            print(f"  HTTPS: status={resp.status}  bytes={len(body)}")
            pat = re.compile(r'/md5/([a-f0-9]{32})')
            hits = pat.findall(body.decode("utf-8", errors="replace"))
            print(f"  md5 hits in response: {len(hits)}")
            if not hits and b"Just a moment" in body:
                print(f"  Cloudflare challenge detected")
    except Exception as e:
        print(f"  HTTPS FAIL: {type(e).__name__}: {e}")
