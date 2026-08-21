"""CORE (Connecting REpositories) channel (v3.9.22+, re-added 2026-08-21).

CORE is the world's largest aggregator of open-access research papers
(260M+ metadata, 36M+ full text, 14K+ data providers). Returns a direct
`downloadUrl` PDF link when the paper is full-text available.

Was previously removed in v3.9.11.1 with the (incorrect) reasoning that
"OpenAlex covers 4.7M papers" — OpenAlex only has metadata, CORE has full
text. Re-added in v3.9.22 with this correction.

API: https://api.core.ac.uk/v3/works/{doi}
Auth: `Authorization: Bearer $CORE_API_KEY` (free at core.ac.uk/services/api)
Legal: ✅ Open University; explicitly designed for text mining and reuse

Rate limits (free tier):
  - Unregistered: 100 tokens/day, 10/min
  - Registered: 1,000 tokens/day, 25/min
"""
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

E_NO_DOI = "no_doi"
E_NOT_FOUND = "core_not_found"
E_NO_FULLTEXT = "core_no_fulltext"
E_API_ERROR = "core_api_error"
E_DOWNLOAD_FAIL = "core_download_failed"

CORE_API_BASE = "https://api.core.ac.uk/v3"
USER_AGENT = "paper-agent/3.9.22 (+github.com/croni4666-cmd/paper-agent)"


def _http_get_json(url: str, timeout: int = 20,
                   require_auth: bool = True) -> tuple[int, Any]:
    """GET JSON; return (status, parsed_json_or_error_dict)."""
    headers = {"User-Agent": USER_AGENT}
    core_key = os.environ.get("CORE_API_KEY")
    if core_key:
        headers["Authorization"] = f"Bearer {core_key}"
    elif require_auth:
        return 0, {"error": "CORE_API_KEY not set",
                   "hint": "Register free at core.ac.uk/services/api and set $CORE_API_KEY"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def _download_pdf(url: str, max_bytes: int = 100 * 1024 * 1024,
                  timeout: int = 90) -> Optional[bytes]:
    """Download a PDF URL, return bytes or None on failure. CORE files can be large."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
            if len(data) > max_bytes:
                logger.warning(f"CORE PDF exceeds {max_bytes} bytes, truncating")
                return data[:max_bytes]
            return data
    except Exception as e:
        logger.debug(f"CORE PDF download failed: {url}: {e}")
        return None


def fetch_core_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a PDF from CORE by DOI.

    Returns dict with:
      - source: "core_pdf"
      - doi, pdf_url, size, path
      - title, year, authors, repository
      - error: only on total failure

    Requires $CORE_API_KEY env var. Without it, returns E_API_ERROR.
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    # v3 works/{doi} — direct lookup
    api_url = f"{CORE_API_BASE}/works/{urllib.parse.quote(doi, safe='/')}"
    status, data = _http_get_json(api_url, timeout=20)
    if status == 404:
        return {"error": E_NOT_FOUND,
                "doi": doi,
                "message": "DOI not found in CORE",
                "hint": "Try --prefer pmc, unpaywall, or scihub"}
    if status != 200 or not isinstance(data, dict):
        return {"error": E_API_ERROR,
                "doi": doi,
                "status": status,
                "message": data.get("error", f"CORE API returned status {status}"),
                "hint": "Check $CORE_API_KEY or rate limit"}

    download_url = data.get("downloadUrl")
    fulltext_status = data.get("fulltextStatus")
    source_fulltext_urls = data.get("sourceFulltextUrls") or []
    urls_list = data.get("urls") or []

    # v3.9.22 fix: downloadUrl from works/{doi} can be a stale Azure blob URL
    # (returns 404). Cross-check via outputs/{id} for live downloadUrl + status.
    if not download_url or fulltext_status == "disabled" or not data.get("fullText"):
        # Try outputs/{id} for richer metadata
        outputs = data.get("outputs") or []
        for out_url in outputs:
            out_id = out_url.rstrip("/").split("/")[-1]
            out_api = f"{CORE_API_BASE}/outputs/{out_id}"
            o_status, o_data = _http_get_json(out_api, timeout=20)
            if o_status == 200 and isinstance(o_data, dict):
                # Get the rich downloadUrl + status
                if o_data.get("downloadUrl") and o_data.get("fulltextStatus") != "disabled":
                    download_url = o_data["downloadUrl"]
                    fulltext_status = o_data.get("fulltextStatus", "available")
                # Also pick up sourceFulltextUrls (the real OA source URL)
                src_urls = o_data.get("sourceFulltextUrls") or []
                if src_urls:
                    source_fulltext_urls = src_urls
                urls_list = o_data.get("urls") or []
                break

    # v3.9.22 fix: CORE's downloadUrl is often a stale Azure blob that returns
    # 404. The REAL full text URL is in sourceFulltextUrls (preferred) or
    # urls[] of type=fulltext. Try these as primary.
    candidate_urls = []
    for u in source_fulltext_urls:
        if u and u not in candidate_urls:
            candidate_urls.append(u)
    for u in urls_list:
        if u.get("type") == "fulltext" and u.get("url") and u["url"] not in candidate_urls:
            candidate_urls.append(u["url"])
    if download_url and download_url not in candidate_urls:
        candidate_urls.append(download_url)  # fallback last

    if not candidate_urls:
        return {"error": E_NO_FULLTEXT,
                "doi": doi,
                "title": data.get("title"),
                "fulltext_status": fulltext_status,
                "message": "CORE has metadata but no full-text PDF URL",
                "hint": "Try --prefer unpaywall for OA copy or pmc/scihub"}

    # Try each candidate URL until one returns a real PDF
    pdf_bytes = None
    last_error = None
    for url in candidate_urls:
        pdf_bytes = _download_pdf(url, timeout=60)
        if pdf_bytes and pdf_bytes.startswith(b"%PDF"):
            break
        last_error = f"download failed for {url}"
        pdf_bytes = None

    if not pdf_bytes:
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "candidate_urls": candidate_urls[:3],
                "title": data.get("title"),
                "message": last_error or "all CORE download URLs failed",
                "hint": "Try --prefer unpaywall or pmc/scihub"}
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "pdf_url": download_url,
                "title": data.get("title"),
                "hint": "CORE returned a download URL but fetch failed or not a real PDF"}

    result = {
        "source": "core_pdf",
        "doi": doi,
        "pdf_url": download_url,
        "size": len(pdf_bytes),
        "title": data.get("title"),
        "year": data.get("yearPublished"),
        "authors": [a.get("name") for a in (data.get("authors") or []) if a.get("name")],
        "repository": data.get("repository", {}).get("name") if isinstance(data.get("repository"), dict) else None,
    }
    if out_path:
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)
        result["path"] = str(out_p.resolve())
    return result
