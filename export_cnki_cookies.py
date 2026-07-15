"""export_cnki_cookies.py — Fully automated CNKI cookie export.

User just runs this; playwright opens Edge (using existing user profile so the
xueshu789 session is preserved), visits the entry URL, waits for redirect,
extracts all xueshu789.com cookies, saves to ~/.paper-agent/cookies/cnki.json.

Why this is needed: xueshu789.com has anti-bot (CAPTCHA on first visit), so
manual cookies export via DevTools is fragile. Using user's existing Edge
profile = cookies are already valid (user has the proxy session).
"""
import os
import sys
import json
import time
from pathlib import Path

# Force proxy OFF — we want the user's real IP, not clash
for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(v, None)

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Find user's Edge profile (any of these)
EDGE_PROFILE_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data",
    Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data",
    Path("C:/Users/DengN/AppData/Local/Microsoft/Edge/User Data"),
]

COOKIES_OUTPUT = Path.home() / ".paper-agent" / "cookies" / "cnki.json"
ENTRY_URL = "https://www.xueshu789.com/dbItem/1"


def find_edge_profile():
    for p in EDGE_PROFILE_CANDIDATES:
        if p.exists() and (p / "Default").exists():
            return p / "Default"
        if p.exists() and (p / "Profile 1").exists():
            return p / "Profile 1"
    return None


def main():
    print("=" * 70)
    print("CNKI cookies auto-export (v3.9.8.3)")
    print("=" * 70)

    edge_profile = find_edge_profile()
    if not edge_profile:
        print("✗ Could not find Edge profile directory.")
        print("  Tried:", [str(p) for p in EDGE_PROFILE_CANDIDATES])
        print("  → Fall back to manual DevTools method (see README)")
        sys.exit(1)
    print(f"  Edge profile: {edge_profile}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("✗ playwright not installed: pip install playwright")
        sys.exit(1)

    COOKIES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        # Use channel='msedge' to launch Microsoft Edge (not bundled chromium)
        # Use user_data_dir so we inherit the existing xueshu789 session
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(edge_profile),
                headless=False,  # MUST be visible — Edge will detect headless as bot
                channel="msedge",
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
                accept_downloads=True,
            )
        except Exception as e:
            print(f"✗ Failed to launch Edge: {e}")
            print("  → Make sure Edge is CLOSED before running this script")
            print("  → Or fall back to manual DevTools method")
            sys.exit(1)

        # Persistent context creates a default page; reuse it
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print(f"  Opened Edge with user profile")
        print(f"  Visiting {ENTRY_URL} ...")
        try:
            page.goto(ENTRY_URL, timeout=20_000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  ⚠ goto error (continuing): {e}")

        # Wait up to 12s for redirect to CNKI proxy IP
        import re
        proxy_url = None
        for i in range(24):
            time.sleep(0.5)
            if re.match(r".*\d+\.\d+\.\d+\.\d+:\d+.*", page.url):
                proxy_url = page.url
                break
        if not proxy_url:
            # Even if redirect didn't fire, try cookies on xueshu789.com directly
            print(f"  ⚠ Redirect didn't fire (current URL: {page.url})")
            print(f"    Trying cookies on xueshu789.com anyway...")

        # Extract all cookies from context (includes xueshu789 + kns.cnki.net)
        all_cookies = ctx.cookies()
        xueshu_cookies = [c for c in all_cookies
                          if "xueshu789" in c.get("domain", "")]
        cnki_cookies = [c for c in all_cookies
                        if "cnki" in c.get("domain", "")]

        print(f"\n  Total cookies: {len(all_cookies)}")
        print(f"  xueshu789.com cookies: {len(xueshu_cookies)}")
        print(f"  cnki.net cookies: {len(cnki_cookies)}")

        if not xueshu_cookies:
            print("\n✗ No xueshu789.com cookies found!")
            print("  → Did the JS redirect fire? Try refreshing the page in the opened Edge window.")
            print("  → Then re-run this script (cookies should appear).")
            ctx.close()
            sys.exit(1)

        # Required xueshu789 cookies: PHPSESSID, user, entrys, expires
        # (from past v3.9.7.4 observations)
        # We save ALL xueshu789 cookies — even if some are missing, downstream
        # code will only use the ones present.
        cookie_names = sorted(c["name"] for c in xueshu_cookies)
        print(f"  xueshu789 cookie names: {cookie_names}")
        required = {"PHPSESSID", "user", "entrys", "expires"}
        missing = required - set(cookie_names)
        if missing:
            print(f"  ⚠ Missing expected cookies: {missing}")
            print(f"    (Bootstrap might still work if some are present, but full set recommended)")

        # Save in Playwright-compatible format (cnki_channel expects this)
        out = []
        for c in xueshu_cookies:
            out.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            })
        with open(COOKIES_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\n  ✓ Saved {len(out)} cookies to {COOKIES_OUTPUT}")
        print(f"  File size: {COOKIES_OUTPUT.stat().st_size} bytes")

        # Verify
        print("\n  Verifying with cnki_channel import...")
        from pa_cli.cnki_channel import cookies_exist, cookie_age_hours
        print(f"    cookies_exist: {cookies_exist()}")
        age = cookie_age_hours()
        print(f"    cookie_age_hours: {age:.2f}h" if age is not None else "    cookie_age_hours: None")

        print("\n✓ Done! You can now run:")
        print("    pa fetch --doi 10.3969/j.issn.1003-9031.2022.04.008 --out test.pdf")
        print("  Or test the search pipeline:")
        print("    pa search \"数字普惠金融 家庭消费\" --engine cnki --year-min 2022 --year-max 2024")

        ctx.close()


if __name__ == "__main__":
    main()
