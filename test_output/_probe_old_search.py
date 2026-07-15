"""probe_old_search.py — One-shot probe of legacy search.cnki.net / .com.cn.

Per user request 2026-07-15: test if 2017-era search.cnki.net interface still
returns cite/dl counts in the list view HTML.

Hypothesis:
  - search.cnki.net + rank=citeNumber historically returns 20 results/page with
    cite/dl visible in HTML
  - May have been 302-redirected to kns.cnki.net (which doesn't expose cite)
  - May need xueshu789 cookies to be reachable at all

Output: test_output/_probe_old_search_report.md
"""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CNKI_COOKIES = Path.home() / ".paper-agent" / "cookies" / "cnki.json"
XUESHU_ENTRY = "https://www.xueshu789.com/dbItem/1"
KEYWORD = "东数西算"  # 4-char Chinese term, will URL-encode

# Two old endpoints to probe
ENDPOINTS = [
    ("search.cnki.net (post-2017)", "https://search.cnki.net/search.aspx?q={KW}&rank=citeNumber&cluster=all&val=CDFDTOTAL&p=0"),
    ("search.cnki.com.cn (pre-2017)", "https://search.cnki.com.cn/Search.aspx?q={KW}&rank=citeNumber&cluster=all&val=&p=0"),
]

REPORT = []
REPORT.append("# Probe: legacy search.cnki.net / .com.cn cite/dl availability\n")
REPORT.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
REPORT.append(f"**Cookie age**: {((time.time() - CNKI_COOKIES.stat().st_mtime) / 3600):.1f}h\n\n")
REPORT.append(f"**Keyword**: `{KEYWORD}` (4-char Chinese, 强制 URL encode)\n\n")
REPORT.append("---\n\n")

if not CNKI_COOKIES.exists():
    REPORT.append("❌ No cookies file. Run Export-CNKICookies.ps1 first.\n")
    print("".join(REPORT))
    sys.exit(1)

cookies = json.loads(CNKI_COOKIES.read_text(encoding="utf-8"))
REPORT.append(f"**Loaded cookies**: {len(cookies)} entries\n\n")

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
    ctx.add_cookies(cookies)
    page = ctx.new_page()

    # Step 1: Bootstrap (mimic v3.9.7.5 flow)
    REPORT.append("## Step 1: xueshu789 bootstrap\n\n")
    try:
        page.goto(XUESHU_ENTRY, wait_until="networkidle", timeout=45_000)
        time.sleep(2.0)  # let JS redirect complete
        final_url = page.url
        REPORT.append(f"After bootstrap, final URL: `{final_url}`\n\n")
    except Exception as e:
        REPORT.append(f"❌ Bootstrap failed: {e}\n\n")
        final_url = "(bootstrap failed)"

    # Step 2: Probe each endpoint
    for label, url_template in ENDPOINTS:
        url = url_template.replace("{KW}", KEYWORD)
        REPORT.append(f"## Step 2: {label}\n\n")
        REPORT.append(f"**Request**: `{url}`\n\n")
        try:
            # Track the navigation chain
            nav_history = []
            def on_request(req):
                if 'cnki' in req.url or 'xueshu' in req.url:
                    nav_history.append(f"  → {req.method} {req.url[:120]}")
            page.on("request", on_request)

            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(2.0)  # let any JS or AJAX settle

            page.remove_listener("request", on_request)
            status = response.status if response else "no response"
            landed_url = page.url
            html_len = len(page.content())

            REPORT.append(f"**HTTP status**: {status}\n\n")
            REPORT.append(f"**Landed at**: `{landed_url}`\n\n")
            REPORT.append(f"**HTML length**: {html_len} bytes\n\n")

            # Save raw HTML for inspection
            slug = label.split(" ")[0].replace(".", "_")
            out_path = Path("G:/minimax - workspace/Paper agent/test_output") / f"_probe_old_search_{slug}.html"
            out_path.write_text(page.content(), encoding="utf-8")
            REPORT.append(f"**Raw HTML saved**: `{out_path.name}`\n\n")

            # Check for cite/dl indicators
            content = page.content()
            indicators = {
                "被引": content.count("被引"),
                "下载": content.count("下载"),
                "引用次数": content.count("引用次数"),
                "被引次数": content.count("被引次数"),
                "下载次数": content.count("下载次数"),
                "cite": content.count("cite"),
                "download": content.count("download"),
                "captcha": content.count("captcha") + content.count("安全验证"),
                "登录": content.count("登录") + content.count("login"),
            }
            REPORT.append("**Field indicators in HTML**:\n\n")
            for k, v in indicators.items():
                flag = "✅" if v > 0 and k not in ("captcha", "登录") else ("⚠️" if v > 0 else "·")
                REPORT.append(f"- {flag} `{k}`: {v} occurrences\n")
            REPORT.append("\n")

            # Check title to identify the page
            try:
                title = page.title()
                REPORT.append(f"**Page title**: `{title}`\n\n")
            except Exception:
                pass

        except Exception as e:
            REPORT.append(f"❌ Request failed: {e}\n\n")

        REPORT.append("---\n\n")

    # Step 3: Check if any endpoint was redirected to new kns.cnki.net
    REPORT.append("## Verdict\n\n")
    REPORT.append("**Read this to decide:**\n\n")
    REPORT.append("1. If `Landed at` for both endpoints is `kns.cnki.net/...` → 302'd, **old interface dead**, fall back to v3.9.7.5 list (no cite).\n")
    REPORT.append("2. If `被引` / `引用次数` / `下载次数` HTML count > 0 AND `cite` field appears in saved HTML → **old interface alive**, can wire cite/dl into v3.9.7.6.\n")
    REPORT.append("3. If `captcha` / `安全验证` > 0 → blocked, need different cookie set.\n\n")

    browser.close()

# Write report
out_report = Path("G:/minimax - workspace/Paper agent/test_output/_probe_old_search_report.md")
out_report.write_text("".join(REPORT), encoding="utf-8")
print(f"Report written to: {out_report}")
print("---")
# Echo verdict summary to stdout
verdict = "".join(REPORT)
print(verdict)
