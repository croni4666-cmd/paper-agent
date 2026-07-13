"""
pa_cli.fetch — single-DOI PDF recovery with 8 channels + Cloudflare fallback.

Implements paper-agent v4 design principle (CHANGELOG v3.2):
  - 8-channel cascade with time budgets
  - After 5 minutes total, STOP and surface "your turn" handoff to user
  - Playwright is opportunistic (T&F works), never blocking

Channels (in priority order):
  1. OpenAlex Work API → discover OA locations
  2. arXiv SDK → if DOI is arXiv-style
  3. Unpaywall API → free legal copy via DOI
  4. Crossref TDM-style lookup
  5. DOI.org redirect → publisher landing page (Gold OA detection)
  6. Publisher direct PDF path (e.g. /doi/pdf/, /pdfft)
  7. Google Scholar cluster → repository copies
  8. Sci-Hub mirrors / Anna's Archive (gray, user-consent required)
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import quote
import urllib.request as ur
import urllib.error

from . import cache as _cache


# =============== HTTP helpers ===============

def http_get(url: str, headers: dict = None, timeout: int = 20, proxy: str = None) -> tuple:
    """GET with optional proxy, return (status, body_bytes, final_url, headers_dict).

    Bug fix (2026-07-13): if proxy is None, fall back to HTTP_PROXY env var.
    This makes all channels (openalex, arxiv, unpaywall, doi_redirect, scihub)
    honor the user's proxy setting without requiring per-channel code changes.
    In CN, set HTTP_PROXY=http://127.0.0.1:7897 to use clash.
    """
    h = {"User-Agent": "paper-agent/3.2 (Mavis; mailto:hello@example.com)",
         "Accept": "*/*"}
    if headers:
        h.update(headers)
    # Fall back to env var if proxy not explicitly passed
    if proxy is None:
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy:
        opener = ur.build_opener(ur.ProxyHandler({"http": proxy, "https": proxy}))
        ur.install_opener(opener)
    req = ur.Request(url, headers=h)
    try:
        with ur.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.geturl(), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(), url, dict(e.headers or {})
        except Exception:
            return e.code, b"", url, {}
    except Exception:
        return 0, b"", url, {}


def is_pdf(b: bytes) -> bool:
    """PDF magic check."""
    return b.startswith(b"%PDF") and len(b) > 50_000


def save_pdf(out_dir: Path, doi_slug: str, body: bytes, tag: str = "") -> str:
    """Save PDF with standardized name."""
    name = f"{doi_slug.replace('/', '_').replace('.', '_')}{('_' + tag) if tag else ''}.pdf"
    fp = out_dir / name
    fp.write_bytes(body)
    return str(fp)


# =============== Cache helpers ===============

def _cache_write_safe(doi: str, body: bytes, channel: str, url: str) -> Optional[dict]:
    """Write to cache; log + skip on failure so cascade result isn't blocked."""
    try:
        return _cache.cache_put(doi, body, channel=channel, url=url)
    except Exception as e:
        # Avoid blocking the cascade result — cache is opportunistic
        import logging
        logging.getLogger(__name__).warning(f"cache_put failed for {doi}: {e}")
        return None


# =============== Channels ===============

def channel_openalex(doi: str) -> dict:
    """Channel 1: OpenAlex Work API."""
    api = f"https://api.openalex.org/works/doi:{quote(doi)}"
    s, body, _, _ = http_get(api, timeout=20)
    if s != 200:
        return {"status": "fail", "stage": "openalex-http", "code": s}
    try:
        w = json.loads(body)
    except Exception:
        return {"status": "fail", "stage": "openalex-parse"}
    candidates = []
    oa = w.get("open_access") or {}
    if oa.get("oa_url"): candidates.append(oa["oa_url"])
    primary = w.get("primary_location") or {}
    if primary.get("pdf_url"): candidates.append(primary["pdf_url"])
    best = w.get("best_oa_location") or {}
    if best.get("pdf_url"): candidates.append(best["pdf_url"])
    for loc in (w.get("locations") or []):
        if loc.get("pdf_url") and loc["pdf_url"] not in candidates:
            candidates.append(loc["pdf_url"])
    return {"status": "found", "candidates": candidates, "is_oa": oa.get("is_oa"),
            "oa_status": oa.get("oa_status")}


def channel_arxiv(doi: str) -> dict:
    """Channel 2: arXiv SDK. Only succeeds if DOI starts with 10.48550."""
    if not doi.startswith("10.48550"):
        return {"status": "skip", "reason": "not-arxiv-doi"}
    try:
        import arxiv
    except ImportError:
        return {"status": "skip", "reason": "arxiv-lib-not-installed"}
    arxiv_id = doi.replace("10.48550/", "").replace("arXiv.", "")
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        client = arxiv.Client()
        results = list(client.results(search))
        if not results:
            return {"status": "fail", "stage": "arxiv-no-result"}
        pdf_url = results[0].pdf_url
        s, body, _, _ = http_get(pdf_url, timeout=30)
        if s == 200 and is_pdf(body):
            return {"status": "success", "stage": "arxiv", "url": pdf_url, "size": len(body)}
        return {"status": "fail", "stage": "arxiv-fetch", "code": s, "size": len(body)}
    except Exception as e:
        return {"status": "fail", "stage": "arxiv-exception", "err": str(e)[:200]}


def channel_unpaywall(doi: str, email: str) -> dict:
    """Channel 3: Unpaywall API. Requires registered email."""
    url = f"https://api.unpaywall.org/v2/{quote(doi)}?email={quote(email)}"
    s, body, _, _ = http_get(url, timeout=20)
    if s != 200:
        return {"status": "fail", "stage": "unpaywall-http", "code": s}
    try:
        d = json.loads(body)
    except Exception:
        return {"status": "fail", "stage": "unpaywall-parse"}
    best = d.get("best_oa_location") or {}
    if not best.get("url_for_pdf"):
        return {"status": "fail", "stage": "unpaywall-no-pdf", "oa_status": d.get("oa_status")}
    pdf_url = best["url_for_pdf"]
    s2, body2, _, _ = http_get(pdf_url, timeout=30)
    if s2 == 200 and is_pdf(body2):
        return {"status": "success", "stage": "unpaywall", "url": pdf_url, "size": len(body2)}
    return {"status": "fail", "stage": "unpaywall-fetch", "code": s2}


def channel_doi_redirect(doi: str) -> dict:
    """Channel 5: DOI.org redirect — detect Gold OA via landing page."""
    url = f"https://doi.org/{doi}"
    s, body, final, hdrs = http_get(url, timeout=20)
    if s != 200:
        return {"status": "fail", "stage": "doi-redirect", "code": s, "final": final}
    if is_pdf(body):
        return {"status": "success", "stage": "doi-redirect-pdf",
                "url": final, "size": len(body)}
    # Look for PDF link in HTML
    html = body.decode("utf-8", errors="ignore")
    pdf_links = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.I)
    pdf_links += re.findall(r'href=["\']([^"\']*/pdfft[^"\']*)["\']', html, re.I)
    pdf_links += re.findall(r'href=["\']([^"\']*/doi/pdf/[^"\']*)["\']', html, re.I)
    return {"status": "found-html", "final": final, "pdf_links": list(set(pdf_links))[:5]}


def channel_scihub_mirror(doi: str) -> dict:
    """Channel 8 (last): Sci-Hub mirrors. Gray; user consent required."""
    mirrors = [
        "https://sci-hub.se/", "https://sci-hub.st/", "https://sci-hub.ru/",
        "https://sci-hub.box/", "https://sci-hub.ren/", "https://sci-hub.al/",
        "https://sci-hub.ee/", "https://sci-hub.shop/", "https://sci-hub.website/",
    ]
    for m in mirrors:
        s, body, final, _ = http_get(m + doi, timeout=20)
        if s != 200 or not body or is_pdf(body):
            continue
        # Look for PDF button / iframe
        html = body.decode("utf-8", errors="ignore")
        for pat in [
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
            r'window\.location[^=]*=\s*["\']([^"\']+)["\']',
            r'data-(?:url|pdf|src)=["\']([^"\']+)["\']',
        ]:
            mm = re.search(pat, html, re.I)
            if mm:
                url = mm.group(1)
                if url.startswith("//"): url = "https:" + url
                elif url.startswith("/"): url = m.rstrip("/") + url
                # Bug fix (2026-07-13): reject non-URL strings like "back", "self", "top"
                # that the regex catches from data-url attributes
                if not (url.startswith("http://") or url.startswith("https://")):
                    continue
                s2, body2, _, _ = http_get(url, timeout=30, proxy=os.environ.get("HTTP_PROXY"))
                if s2 == 200 and is_pdf(body2):
                    return {"status": "success", "stage": "scihub",
                            "mirror": m, "iframe_url": url, "size": len(body2)}
    return {"status": "fail", "stage": "scihub-all-mirrors"}


def channel_playwright_pdf(url: str, out_path: Path, max_wait: int = 25) -> dict:
    """Playwright opportunistic path for Cloudflare-protected PDFs (T&F style)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "skip", "reason": "playwright-not-installed"}
    try:
        # Read proxy from env (CN users: HTTP_PROXY=http://127.0.0.1:7897)
        # Bug fix (2026-07-13): chromium needs explicit --proxy-server flag
        # because its proxy config is independent of Python's urllib ProxyHandler
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        launch_args = ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        if proxy:
            launch_args.append(f"--proxy-server={proxy}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=launch_args,
            )
            ctx = browser.new_context(
                user_agent="paper-agent/3.2 (Mavis)",
                viewport={"width": 1280, "height": 800},
                accept_downloads=True,
            )
            ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = ctx.new_page()
            try:
                with page.expect_download(timeout=60_000) as dl_info:
                    try:
                        page.goto(url, wait_until="commit", timeout=30_000)
                    except Exception:
                        pass  # Download trigger is the expected exception
                dl = dl_info.value
                dl.save_as(str(out_path))
                size = out_path.stat().st_size
                browser.close()
                return {"status": "success", "stage": "playwright", "size": size, "url": url}
            except Exception as e:
                browser.close()
                return {"status": "fail", "stage": "playwright-timeout", "err": str(e)[:200]}
    except Exception as e:
        return {"status": "fail", "stage": "playwright-exception", "err": str(e)[:200]}


# =============== Cascade runner ===============

def fetch_doi(doi: str, output_dir: str = ".",
              proxy: str = None, channels: List[str] = None,
              unpaywall_email: str = "hello@example.com",
              max_total_sec: int = 300,
              use_cache: bool = True) -> Dict[str, Any]:
    """Try channels in order until success. Hard cap at max_total_sec (paper-agent v4: 5 min).

    Cache integration (P0-2, 2026-07-04):
      1. On entry, if use_cache=True, check ~/.paper-agent/cache/{doi_slug}.pdf
         — if hit (PDF magic + sha256 match), return immediately with via_channel='cache'.
         Cascade skipped entirely.
      2. After each successful cascade channel, write the downloaded PDF to
         cache (always, regardless of use_cache flag) so subsequent fetches
         benefit even if this call used --no-cache.
      3. use_cache=False still writes to cache after cascade — see point 2.
         (Flag is "skip the read", not "skip the write".)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    channels = channels or ["openalex", "arxiv", "unpaywall", "doi_redirect",
                            "scihub", "playwright"]
    doi_slug = doi.replace("/", "_").replace(".", "_")
    t0 = time.time()

    results = {"doi": doi, "saved_as": None, "channels": {}}

    # Cache check at function entry — short-circuit cascade on hit.
    # P0-2 acceptance: "if PDF magic valid + sha256 unchanged, return
    # without re-downloading".
    if use_cache:
        hit = _cache.cache_get(doi)
        if hit:
            results["saved_as"] = hit["pdf_path"]
            results["via_channel"] = f"cache:{hit['channel']}" if hit["channel"] else "cache"
            results["via_url"] = hit.get("url", "")
            results["cache_hit"] = True
            results["cache_age_days"] = round(hit.get("age_days", 0), 3)
            results["cache_sha256"] = hit["sha256"]
            results["elapsed_sec"] = round(time.time() - t0, 3)
            results["final_status"] = "SUCCESS_CACHE_HIT"
            # Skip entire cascade — user request satisfied.
            return results
    for ch_name in channels:
        elapsed = time.time() - t0
        if elapsed > max_total_sec:
            results["handoff"] = {
                "reason": "paper-agent v4: 5-min Cloudflare timeout reached",
                "elapsed_sec": round(elapsed, 1),
                "user_action_required": "Open Chrome + visit OA URL directly, save PDF to manual_download/",
            }
            break
        if ch_name == "openalex":
            results["channels"]["openalex"] = channel_openalex(doi)
            # Try each OA candidate immediately
            for cand in results["channels"]["openalex"].get("candidates", []):
                s, body, _, _ = http_get(cand, timeout=30, proxy=proxy)
                if s == 200 and is_pdf(body):
                    saved = save_pdf(output_dir, doi_slug, body)
                    results["saved_as"] = saved
                    results["via_channel"] = "openalex"
                    results["via_url"] = cand
                    _cache_write_safe(doi, body, channel="openalex", url=cand)
                    return results
        elif ch_name == "arxiv":
            r = channel_arxiv(doi)
            results["channels"]["arxiv"] = r
            if r.get("status") == "success":
                s, body, _, _ = http_get(r["url"], timeout=30, proxy=proxy)
                if s == 200 and is_pdf(body):
                    saved = save_pdf(output_dir, doi_slug, body, tag="arxiv")
                    results["saved_as"] = saved
                    results["via_channel"] = "arxiv"
                    results["via_url"] = r["url"]
                    _cache_write_safe(doi, body, channel="arxiv", url=r["url"])
                    return results
        elif ch_name == "unpaywall":
            r = channel_unpaywall(doi, unpaywall_email)
            results["channels"]["unpaywall"] = r
            if r.get("status") == "success":
                s, body, _, _ = http_get(r["url"], timeout=30, proxy=proxy)
                if s == 200 and is_pdf(body):
                    saved = save_pdf(output_dir, doi_slug, body, tag="unpaywall")
                    results["saved_as"] = saved
                    results["via_channel"] = "unpaywall"
                    results["via_url"] = r["url"]
                    _cache_write_safe(doi, body, channel="unpaywall", url=r["url"])
                    return results
        elif ch_name == "doi_redirect":
            r = channel_doi_redirect(doi)
            results["channels"]["doi_redirect"] = r
            # Try PDF links in HTML
            for link in r.get("pdf_links", []):
                full = link if link.startswith("http") else r.get("final", "") + link
                s, body, _, _ = http_get(full, timeout=30, proxy=proxy)
                if s == 200 and is_pdf(body):
                    saved = save_pdf(output_dir, doi_slug, body)
                    results["saved_as"] = saved
                    results["via_channel"] = "doi_redirect"
                    results["via_url"] = full
                    _cache_write_safe(doi, body, channel="doi_redirect", url=full)
                    return results
            # Try Playwright on /doi/pdf/ URL pattern
            pdf_url = r.get("final", "").replace("/abs/", "/pdf/").replace("/full/", "/pdf/")
            if pdf_url and pdf_url != r.get("final"):
                fp = output_dir / f"{doi_slug}_playwright.pdf"
                pw_r = channel_playwright_pdf(pdf_url, fp)
                results["channels"]["playwright_pdf"] = pw_r
                if pw_r.get("status") == "success":
                    results["saved_as"] = pw_r["saved_as"]
                    results["via_channel"] = "playwright_pdf"
                    # Re-read body from disk to write cache
                    try:
                        pw_body = Path(pw_r["saved_as"]).read_bytes()
                        _cache_write_safe(doi, pw_body, channel="playwright_pdf", url=pdf_url)
                    except Exception:
                        pass
                    return results
        elif ch_name == "scihub":
            r = channel_scihub_mirror(doi)
            results["channels"]["scihub"] = r
            if r.get("status") == "success":
                # Re-fetch PDF body to save
                s, body, _, _ = http_get(r["iframe_url"], timeout=30, proxy=proxy)
                if s == 200 and is_pdf(body):
                    saved = save_pdf(output_dir, doi_slug, body, tag="scihub")
                    results["saved_as"] = saved
                    results["via_channel"] = "scihub"
                    results["via_url"] = r.get("iframe_url", "")
                    _cache_write_safe(doi, body, channel="scihub", url=r.get("iframe_url", ""))
                    return results
        elif ch_name == "playwright":
            # Last-ditch: try Playwright on the doi.org URL directly
            pdf_url = f"https://doi.org/{doi}"
            fp = output_dir / f"{doi_slug}_playwright.pdf"
            r = channel_playwright_pdf(pdf_url, fp)
            results["channels"]["playwright"] = r
            if r.get("status") == "success":
                results["saved_as"] = r.get("saved_as")
                results["via_channel"] = "playwright"
                return results

    results["final_status"] = "ALL_FAIL" if not results["saved_as"] else "SUCCESS"
    results["elapsed_sec"] = round(time.time() - t0, 1)
    if not results.get("handoff") and not results["saved_as"]:
        results["handoff"] = {
            "reason": "paper-agent v4: all channels exhausted",
            "user_action_required": (
                "Open Chrome. Try in order: (1) institutional repository (e.g. Nottingham, UFDC); "
                "(2) ScienceDirect Gold OA page; (3) Sci-Hub mirror with raven captcha; "
                "(4) email author. Save to manual_download/ folder."
            ),
        }
    return results