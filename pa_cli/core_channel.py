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
    if not download_url:
        return {"error": E_NO_FULLTEXT,
                "doi": doi,
                "title": data.get("title"),
                "message": "CORE has metadata but no full-text PDF",
                "hint": "Try --prefer unpaywall for OA copy or pmc/scihub"}

    # Download
    pdf_bytes = _download_pdf(download_url, timeout=90)
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
