"""Test annas-archive.li search API via proxy — does it return MD5 hits?"""
import os
import re
import urllib.parse
import urllib.request

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10808"

queries = [
    "10.1038/nature12373",
    "nature genetics",
    "10.1038/nature14539",  # Deep learning Nature paper
]

proxy_handler = urllib.request.ProxyHandler({
    "http": "http://127.0.0.1:10808",
    "https": "http://127.0.0.1:10808",
})
opener = urllib.request.build_opener(proxy_handler)

for q in queries:
    q_enc = urllib.parse.quote(q)
    url = f"https://annas-archive.li/search?q={q_enc}"
    print(f"\n--- query: {q!r} ---")
    print(f"    url: {url}")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/120.0.0.0"},
        )
        with opener.open(req, timeout=30) as resp:
            body = resp.read()
            print(f"    status: {resp.status}  bytes: {len(body)}")
            pat = re.compile(r'href="(/md5/[a-f0-9]{32})"')
            hits = pat.findall(body.decode("utf-8", errors="replace"))
            print(f"    md5 hits: {len(hits)}")
            for h in hits[:3]:
                print(f"      {h}")
            # also check page title
            title_match = re.search(r"<title>(.*?)</title>", body.decode("utf-8", errors="replace"))
            if title_match:
                print(f"    page title: {title_match.group(1)[:80]!r}")
    except Exception as e:
        print(f"    EXC: {type(e).__name__}: {e}")
