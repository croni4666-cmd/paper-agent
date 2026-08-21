"""bioRxiv / medRxiv preprint channel (v3.9.22+, 2026-08-21).

Queries the Cold Spring Harbor Laboratory (CSHL) preprint server API for
PDF metadata + download link. Both servers use the same API and the same
DOI prefix (10.1101/*), so we auto-detect based on the response's `server`
field.

API: https://api.biorxiv.org/details/{server}/{DOI}/na/json
     (also: https://api.medrxiv.org/details/...)
Auth: No key, no rate limit (officially)
Legal: ✅ CSHL; preprints CC-BY licensed

Trigger: DOI starts with `10.1101/` (both biorxiv and medrxiv preprints use
this prefix). On hit, returns the versioned PDF URL.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

E_NO_DOI = "no_doi"
E_NOT_PREPRINT = "biorxiv_not_preprint"
E_API_ERROR = "biorxiv_api_error"
E_NO_PDF = "biorxiv_no_pdf_url"
E_DOWNLOAD_FAIL = "biorxiv_download_failed"

BIORXIV_BASE = "https://api.biorxiv.org/details"
USER_AGENT = "paper-agent/3.9.22 (+github.com/croni4666-cmd/paper-agent)"


def _http_get_json(url: str, timeout: int = 20) -> tuple[int, Any]:
    """GET JSON; return (status, parsed_json_or_error_dict)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def _download_pdf(url: str, max_bytes: int = 50 * 1024 * 1024,
                  timeout: int = 60) -> Optional[bytes]:
    """Download a PDF URL, return bytes or None on failure."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
            if len(data) > max_bytes:
                logger.warning(f"bioRxiv PDF exceeds {max_bytes} bytes, truncating")
                return data[:max_bytes]
            return data
    except Exception as e:
        logger.debug(f"bioRxiv PDF download failed: {url}: {e}")
        return None


def fetch_biorxiv_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a PDF from bioRxiv or medRxiv by DOI.

    Triggers only on `10.1101/*` DOIs. Tries both servers (biorxiv first,
    then medrxiv) because the API doesn't reliably tell them apart from
    the DOI alone.

    Returns dict with:
      - source: "biorxiv_pdf" or "medrxiv_pdf"
      - doi, pdf_url, version, server, size, path
      - error: only on total failure
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    if not doi.lower().startswith("10.1101/"):
        return {"error": E_NOT_PREPRINT,
                "doi": doi,
                "message": "DOI does not start with 10.1101/ (bioRxiv/medRxiv prefix)",
                "hint": "bioRxiv channel only handles preprint DOIs"}

    # Try biorxiv first, then medrxiv (DOI is ambiguous at CSHL)
    for server in ("biorxiv", "medrxiv"):
        api_url = f"{BIORXIV_BASE}/{server}/{urllib.parse.quote(doi)}/na/json"
        status, data = _http_get_json(api_url, timeout=20)
        if status == 200 and isinstance(data, dict) and data.get("collection"):
            break
        logger.debug(f"bioRxiv: {server} returned status {status} or empty")
    else:
        return {"error": E_API_ERROR,
                "doi": doi,
                "message": "bioRxiv/medRxiv API did not return metadata for this DOI",
                "hint": "DOI may not be a bioRxiv/medRxiv preprint, or server is down"}

    # The collection is a list of versions (v1, v2, ...) — take the latest
    collection = data.get("collection", [])
    if not collection:
        return {"error": E_API_ERROR,
                "doi": doi,
                "message": "bioRxiv returned empty collection",
                "hint": "Check DOI spelling"}

    # Latest version = last in the list
    latest = collection[-1]
    pdf_url = latest.get("link_pdf")
    if not pdf_url:
        return {"error": E_NO_PDF,
                "doi": doi,
                "server": latest.get("server", server),
                "version": latest.get("version"),
                "message": "bioRxiv metadata has no link_pdf field",
                "hint": "Try --prefer pmc or unpaywall"}

    # Download the PDF
    pdf_bytes = _download_pdf(pdf_url, timeout=60)
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "pdf_url": pdf_url,
                "title": latest.get("title"),
                "hint": "bioRxiv returned a PDF URL but download failed or not a real PDF"}

    result = {
        "source": f"{latest.get('server', server)}_pdf",
        "doi": doi,
        "pdf_url": pdf_url,
        "version": latest.get("version"),
        "server": latest.get("server", server),
        "size": len(pdf_bytes),
        "title": latest.get("title"),
        "authors": latest.get("authors"),
        "category": latest.get("category"),
        "date": latest.get("date"),
    }
    if out_path:
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)
        result["path"] = str(out_p.resolve())
    return result
