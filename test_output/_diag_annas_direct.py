"""Direct hit annas-archive.org search, see what comes back."""
import re
import urllib.parse
import urllib.request

q = urllib.parse.quote("10.1038/nature12373")
url = f"https://annas-archive.org/search?q={q}"
print("URL:", url)

req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    },
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        print("status:", resp.status)
        print("content-type:", resp.headers.get("content-type"))
        print("body length:", len(body))
        print()
        print("--- first 800 chars ---")
        print(body[:800].decode("utf-8", errors="replace"))
        print()
        # Count md5 hits with escaped pattern (Python re)
        pat = re.compile(r'href="(/md5/[a-f0-9]{32})"')
        hits = pat.findall(body.decode("utf-8", errors="replace"))
        print(f"--- md5 hits: {len(hits)} ---")
        for h in hits[:5]:
            print("  ", h)
        # Also try other patterns
        pat2 = re.compile(r'/md5/([a-f0-9]{32})')
        all_md5 = pat2.findall(body.decode("utf-8", errors="replace"))
        print(f"--- any /md5/ ref (loose): {len(all_md5)} ---")
        # Check for Cloudflare challenge
        if b"cf-chl-bypass" in body or b"Just a moment" in body:
            print("--- !!! CLOUDFLARE CHALLENGE DETECTED !!! ---")
        if b"verify you are human" in body.lower():
            print("--- !!! HUMAN VERIFICATION ---")
except Exception as e:
    print("EXC:", type(e).__name__, e)
