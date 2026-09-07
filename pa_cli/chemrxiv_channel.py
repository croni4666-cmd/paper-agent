"""ChemRxiv open-access PDF channel.

ChemRxiv migrated from Figshare to Cambridge Open Engage in 2021. This module
uses the documented public Open Engage DOI endpoint and follows the canonical
asset URL returned in its metadata. A DOI-PDF endpoint is retained as a
metadata-free fallback for transient API outages.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

E_NO_DOI = "no_doi"
E_NOT_CHEMRXIV = "chemrxiv_not_chemrxiv_doi"
E_API_ERROR = "chemrxiv_api_error"
E_NO_PDF = "chemrxiv_no_pdf"
E_DOWNLOAD_FAIL = "chemrxiv_download_failed"

OPEN_ENGAGE_API = "https://chemrxiv.org/engage/chemrxiv/public-api/v1"
DOI_PDF_URL = "https://chemrxiv.org/doi/pdf/{doi}?download=true&redirectToLatest=false"
USER_AGENT = "paper-agent/3.9 (+github.com/croni4666-cmd/paper-agent)"


def _http_get_json(url: str, timeout: int = 20) -> tuple[int, Any]:
    """GET JSON; return (status, parsed_json_or_error_dict)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {"error": str(exc)}
    except Exception as exc:
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def _download_pdf(url: str, max_bytes: int = 50 * 1024 * 1024,
                  timeout: int = 60) -> Optional[bytes]:
    """Download a PDF URL, returning bytes only when it is a real PDF."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                logger.warning("ChemRxiv PDF exceeds %s bytes", max_bytes)
                return None
            return data if data.startswith(b"%PDF") else None
    except Exception as exc:
        logger.debug("ChemRxiv PDF download failed: %s: %s", url, exc)
        return None


def _open_engage_pdf_url(record: Any) -> Optional[str]:
    """Return the canonical PDF asset URL from an Open Engage item."""
    if not isinstance(record, dict):
        return None
    record = record.get("item", record)
    direct = record.get("pdfUrl")
    if isinstance(direct, str) and direct:
        return direct
    asset = record.get("asset")
    if isinstance(asset, dict):
        original = asset.get("original")
        if isinstance(original, dict):
            url = original.get("url")
            if isinstance(url, str) and url:
                return url
    return None


def _write_result(doi: str, pdf_url: str, pdf_bytes: bytes, record: Any,
                  out_path: Optional[str], source: str) -> Dict[str, Any]:
    """Build a stable result shape and optionally persist the PDF."""
    item = record.get("item", record) if isinstance(record, dict) else {}
    result: Dict[str, Any] = {
        "source": source,
        "doi": doi,
        "pdf_url": pdf_url,
        "size": len(pdf_bytes),
        "title": item.get("title"),
        "published_date": item.get("publishedDate"),
        "chemrxiv_id": item.get("id"),
    }
    if out_path:
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf_bytes)
        result["path"] = str(target.resolve())
    return result


def fetch_chemrxiv_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a ChemRxiv PDF using its public Open Engage service."""
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}
    if not doi.lower().startswith("10.26434/chemrxiv-"):
        return {
            "error": E_NOT_CHEMRXIV, "doi": doi,
            "message": "DOI is not a ChemRxiv preprint (10.26434/chemrxiv-*)",
            "hint": "ChemRxiv channel only handles ChemRxiv preprints",
        }

    api_url = f"{OPEN_ENGAGE_API}/items/doi/{urllib.parse.quote(doi, safe='/')}"
    status, record = _http_get_json(api_url, timeout=20)
    pdf_url = _open_engage_pdf_url(record) if status == 200 else None
    if pdf_url:
        pdf_bytes = _download_pdf(pdf_url, timeout=60)
        if pdf_bytes:
            return _write_result(doi, pdf_url, pdf_bytes, record, out_path,
                                 "chemrxiv_pdf")
        api_error = E_DOWNLOAD_FAIL
    else:
        api_error = E_NO_PDF if status == 200 else E_API_ERROR

    # Public canonical fallback: useful when metadata service is temporarily down.
    fallback_url = DOI_PDF_URL.format(doi=urllib.parse.quote(doi, safe="/"))
    fallback_bytes = _download_pdf(fallback_url, timeout=60)
    if fallback_bytes:
        return _write_result(doi, fallback_url, fallback_bytes, record, out_path,
                             "chemrxiv_doi_pdf")

    if api_error == E_API_ERROR:
        message = f"Open Engage API returned status {status}"
        hint = "ChemRxiv may be rate-limiting or challenging this network; retry later."
    elif api_error == E_NO_PDF:
        message = "Open Engage record has no PDF asset"
        hint = "The preprint may have been withdrawn or have no downloadable PDF."
    else:
        message = "ChemRxiv returned a PDF URL but it was unavailable or not a PDF"
        hint = "Retry later or use another open-access source."
    return {
        "error": api_error, "doi": doi, "status": status,
        "message": message, "hint": hint, "fallback_url": fallback_url,
    }
