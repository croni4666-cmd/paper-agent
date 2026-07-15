"""End-to-end test of pa fetch fallback chain v2 (graceful JSON parsing)."""
import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, "G:/minimax - workspace/Paper agent")

from pa_cli.fetch import (
    status_report,
    _http_get_bytes,
    SCIHUB_MIRRORS,
    ANNAS_DOMAINS,
    COMMON_HEADERS,
)

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def detect(body, url):
    """Return marker for what we got back."""
    if not body:
        return "EMPTY"
    if body[:4] == b"%PDF":
        return "✓ PDF"
    head = body[:500].decode("utf-8", errors="ignore")
    if "<html" in head.lower():
        if "Mirror" in head or "mirror" in head:
            return "⚠️ HIJACK-mirror-nav"
        if "Telegram" in head or "@" in head:
            return "⚠️ HIJACK-telegram"
        if "Cloudflare" in head or "cf-chl" in head:
            return "⚠️ CF-challenge"
        if "404" in head or "Not Found" in head:
            return "✗ 404"
        if "<title" in head:
            # Extract title
            import re
            t = re.search(r"<title>([^<]+)</title>", head)
            return f"HTML title={t.group(1)[:40] if t else '?'}"
        return "HTML"
    if b"{" in body[:10]:
        try:
            json.loads(body[:5000].decode("utf-8", errors="ignore"))
            return "JSON"
        except Exception:
            pass
    return f"raw({len(body)}B)"


print("=" * 70)
print("STEP 1: Health check")
print("=" * 70)
h = status_report()
print(f"  scihub: {h['scihub']}")
print(f"  annas:  {h['annas']}")

print()
print("=" * 70)
print("STEP 2: Unpaywall direct (DOI 10.1038/nature12373)")
print("=" * 70)
for email in ["paper-agent@mavis.local", "test@example.com"]:
    url = f"https://api.unpaywall.org/v2/10.1038/nature12373?email={email}"
    t0 = time.time()
    try:
        s, body = _http_get_bytes(url, timeout=20)
        dt = time.time() - t0
        mark = detect(body, url)
        # Try JSON parse
        try:
            d = json.loads(body.decode("utf-8", errors="ignore"))
            oa = d.get("oa_locations") or []
            best = d.get("best_oa_location") or {}
            print(f"  email={email[:30]:30} | HTTP {s} t={dt:.1f}s | {mark} | "
                  f"title={d.get('title','')[:40]!r} | best_oa={best.get('url_for_pdf', best.get('url',''))[:60]}")
        except Exception:
            print(f"  email={email[:30]:30} | HTTP {s} t={dt:.1f}s | {mark} | "
                  f"first200={body[:200]!r}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  email={email[:30]:30} | ERR  t={dt:.1f}s | {str(e)[:80]}")

print()
print("=" * 70)
print("STEP 3: sci-hub each mirror, real DOI path (10.1038/nature12373)")
print("=" * 70)
for m in SCIHUB_MIRRORS:
    url = f"{m}/10.1038/nature12373"
    t0 = time.time()
    try:
        s, body = _http_get_bytes(url, timeout=20)
        dt = time.time() - t0
        mark = detect(body, url)
        # If HTML, look for embedded PDF link
        pdf_url = ""
        if mark.startswith("HTML"):
            import re
            embeds = re.findall(r'(https?://[^"\'<>\s]+\.pdf)', body.decode("utf-8", errors="ignore"))
            if embeds:
                pdf_url = f" | embed_pdf={embeds[0][:60]}"
            # Also check for /download/ or /cache/ or sci-hub.box
            downloads = re.findall(r'(https?://[^"\'<>\s]*(?:/download/|/cache/|sci-hub\.box)[^"\'<>\s]*)',
                                   body.decode("utf-8", errors="ignore"))
            if downloads:
                pdf_url += f" | dl={downloads[0][:60]}"
        print(f"  {m:30} HTTP {s:3} t={dt:5.1f}s | {len(body):8d}B | {mark}{pdf_url}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  {m:30} ERR  t={dt:5.1f}s | {str(e)[:80]}")

print()
print("=" * 70)
print("STEP 4: annas-archive — search via real query")
print("=" * 70)
for d in ANNAS_DOMAINS:
    url = f"{d}/search?q=attention+is+all+you+need"
    t0 = time.time()
    try:
        s, body = _http_get_bytes(url, timeout=20)
        dt = time.time() - t0
        mark = detect(body, url)
        # Try to find md5 paths
        import re
        md5s = re.findall(r'/md5/([a-f0-9]{32})', body.decode("utf-8", errors="ignore"))
        unique_md5s = list(dict.fromkeys(md5s))[:3]
        print(f"  {d:35} HTTP {s:3} t={dt:5.1f}s | {len(body):8d}B | {mark}"
              + (f" | md5s found: {unique_md5s}" if unique_md5s else ""))
    except Exception as e:
        dt = time.time() - t0
        print(f"  {d:35} ERR  t={dt:5.1f}s | {str(e)[:80]}")

print()
print("=" * 70)
print("STEP 5: annas-archive — try one MD5 download")
print("=" * 70)
# Use a known MD5 from a famous paper (Attention Is All You Need arxiv 1706.03762)
# MD5 not easily guessed; use any MD5 found in step 4
print("  (if step 4 found MD5, will try download)")
print("  (otherwise: try annas /download/<md5> route directly)")

# Manually try a known public-domain paper MD5
# Anna's archive MD5s for arxiv preprints are findable
TEST_MD5 = "5e5d5b5d5e5d5b5d5e5d5b5d5e5d5b5d"  # placeholder
for d in ANNAS_DOMAINS[:2]:
    for path in [f"/md5/{TEST_MD5}", f"/download/{TEST_MD5}"]:
        url = f"{d}{path}"
        t0 = time.time()
        try:
            s, body = _http_get_bytes(url, timeout=15, headers={"Referer": f"{d}/"})
            dt = time.time() - t0
            mark = detect(body, url)
            print(f"  {d}{path:30} HTTP {s:3} t={dt:.1f}s | {mark} | "
                  f"first200={body[:200]!r}")
        except Exception as e:
            dt = time.time() - t0
            print(f"  {d}{path:30} ERR  t={dt:.1f}s | {str(e)[:80]}")

print()
print("=" * 70)
print("STEP 6: end-to-end fetch() with prefer='auto'")
print("=" * 70)
from pa_cli.fetch import fetch
r = fetch(doi="10.1038/nature12373", out_path=str(OUT_DIR / "auto_nature12373.pdf"),
          prefer="auto")
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | err={r.get('error')}")
if r.get("chain"):
    for step in r["chain"]:
        ok = "✓" if step.get("ok") else "✗"
        print(f"  {ok} {step.get('source'):12} | {step.get('err','ok')}")
