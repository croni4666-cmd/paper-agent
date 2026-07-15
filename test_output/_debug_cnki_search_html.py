"""Debug: dump full search HTML to find download/detail URL patterns."""
import os
import sys
from pathlib import Path

# Force proxy OFF
for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(v, None)

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.cnki_channel import CNKIClient
from playwright.sync_api import sync_playwright

client = CNKIClient()
client.load()
print(f"cookies loaded: {len(client._cookies)}")

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    ctx = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
    )
    ctx.add_cookies(client._cookies)
    page = ctx.new_page()

    try:
        proxy_base = client._bootstrap_in_context(ctx, page)
        print(f"proxy_base: {proxy_base}")

        # Search for the test DOI
        query_json = client._build_query_json(
            "10.3969/j.issn.1003-9031.2022.04.008", "FT", "WD0FTY92", "CROSSDB", None, None)
        html = client._post_brief_page_in_context(
            ctx, page, proxy_base, query_json, 1)

        # Save full HTML
        out = Path("G:/minimax - workspace/Paper agent/test_output/_debug_cnki_search.html")
        out.write_text(html, encoding="utf-8")
        print(f"Saved search HTML to {out} ({len(html)} chars)")

        # Find ALL hrefs in HTML
        import re
        all_hrefs = re.findall(r'href="([^"]+)"', html)
        unique_hosts = set()
        for h in all_hrefs:
            if h.startswith("http"):
                m = re.match(r"https?://([^/]+)", h)
                if m:
                    unique_hosts.add(m.group(1))
        print(f"\nUnique hosts in hrefs: {len(unique_hosts)}")
        for h in sorted(unique_hosts):
            print(f"  {h}")

        # Find URLs with download/vvip/pdf/caj
        download_hrefs = [h for h in all_hrefs if any(
            kw in h.lower() for kw in ("download", "vvip", "caj", "pdf", "file", "vvip"))]
        print(f"\nDownload-related hrefs: {len(download_hrefs)}")
        for h in download_hrefs[:10]:
            print(f"  {h[:150]}")

        # Find hrefs on kns.cnki.net
        kns_hrefs = [h for h in all_hrefs if "kns.cnki" in h or "kns8s" in h or "kcms" in h]
        print(f"\nKNS/kcms hrefs: {len(kns_hrefs)}")
        for h in kns_hrefs[:10]:
            print(f"  {h[:150]}")

    finally:
        browser.close()
