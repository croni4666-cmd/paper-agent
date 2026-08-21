"""ChemRxiv channel (v3.9.22+, 2026-08-21).

ChemRxiv is a free preprint server for chemistry, operated by ACS in
partnership with Cambridge University Press, RSC, and GDCh. 40K+ preprints
in chemistry + materials science + chemical engineering + biochemistry.

DOI pattern: 10.26434/chemrxiv-*

API: Open Engage API (https://api.figshare.com/v2/) — ChemRxiv is built
on Figshare infrastructure. We use the public Figshare endpoint directly
(no key needed for read).

Legal: ✅ ACS + Cambridge + RSC + GDCh; CC-BY licenses
"""
import json
import logging
import re
import time
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

# ChemRxiv runs on Figshare. Public endpoint: search by DOI
FIGSHARE_API = "https://api.figshare.com/v2/articles/search"
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
                logger.warning(f"ChemRxiv PDF exceeds {max_bytes} bytes, truncating")
                return data[:max_bytes]
            return data
    except Exception as e:
        logger.debug(f"ChemRxiv PDF download failed: {url}: {e}")
        return None


def fetch_chemrxiv_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a PDF from ChemRxiv by DOI.

    Triggers only on `10.26434/chemrxiv-*` DOIs.

    Returns dict with:
      - source: "chemrxiv_pdf"
      - doi, pdf_url, size, path
      - title, authors, published_date
      - error: only on total failure
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    if not doi.lower().startswith("10.26434/chemrxiv-"):
        return {"error": E_NOT_CHEMRXIV,
                "doi": doi,
                "message": "DOI is not a ChemRxiv preprint (10.26434/chemrxiv-*)",
                "hint": "ChemRxiv channel only handles ChemRxiv preprints"}

    # Figshare search by DOI
    api_url = f"{FIGSHARE_API}?search_for={urllib.parse.quote(doi)}&item_type=3"
    status, data = _http_get_json(api_url, timeout=20)
    if status != 200 or not isinstance(data, list):
        return {"error": E_API_ERROR,
                "doi": doi,
                "status": status,
                "message": f"Figshare API returned status {status}",
                "hint": "Check DOI or rate limit"}

    # Filter to ChemRxiv records
    matches = [a for a in data if a.get("doi") == doi]
    if not matches and data:
        # Figshare search may not require exact DOI match; try first record
        matches = [data[0]]
    if not matches:
        return {"error": E_API_ERROR,
                "doi": doi,
                "message": "Figshare has no ChemRxiv record for this DOI",
                "hint": "Check DOI or try other channels"}

    record = matches[0]
    article_id = record.get("id")
    title = record.get("title")
    published_date = record.get("published_date")

    # Get file details to find the PDF download URL
    files_url = f"https://api.figshare.com/v2/articles/{article_id}/files"
    f_status, f_data = _http_get_json(files_url, timeout=15)
    if f_status != 200 or not isinstance(f_data, list) or not f_data:
        return {"error": E_NO_PDF,
                "doi": doi,
                "title": title,
                "message": "ChemRxiv record has no files",
                "hint": "Try other channels"}

    # Find the PDF (name ends with .pdf or content_type is application/pdf)
    pdf_file = None
    for f in f_data:
        name = (f.get("name") or "").lower()
        if name.endswith(".pdf") or f.get("content_type") == "application/pdf":
            pdf_file = f
            break
    if not pdf_file:
        pdf_file = f_data[0]  # fall back to first file

    download_url = pdf_file.get("download_url")
    if not download_url:
        return {"error": E_NO_PDF,
                "doi": doi,
                "title": title,
                "message": "ChemRxiv file has no download_url",
                "hint": "Try other channels"}

    # Download
    pdf_bytes = _download_pdf(download_url, timeout=60)
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "pdf_url": download_url,
                "title": title,
                "hint": "ChemRxiv returned a download URL but fetch failed or not a real PDF"}

    result = {
        "source": "chemrxiv_pdf",
        "doi": doi,
        "pdf_url": download_url,
        "size": len(pdf_bytes),
        "title": title,
        "published_date": published_date,
        "figshare_id": article_id,
    }
    if out_path:
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)
        result["path"] = str(out_p.resolve())
    return result
