"""OSF (Open Science Framework) Preprints channel (v3.9.22+, 2026-08-21).

OSF aggregates preprints from 25+ community providers including:
  - osf (multidisciplinary)
  - psyarxiv (psychology)
  - socarxiv (social sciences)
  - eartharxiv (earth sciences)
  - engrxiv (engineering)
  - medarxiv (medical)
  - nutrixiv (nutrition)
  - biohackrxiv (bioinformatics)
  - and more

Total: 2M+ preprints.

API: https://api.osf.io/v2/preprints/?filter[doi]={doi}
     Returns preprint metadata + relationships.primary_file → files/{id}/versions/ → links.download
Auth: No key needed for read access (rate-limited)
Legal: ✅ Center for Open Science; CC-BY licenses

DOI patterns:
  - 10.31219/osf.io/{id}
  - 10.31234/osf.io/{id}
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
E_NOT_OSF = "osf_not_osf_doi"
E_API_ERROR = "osf_api_error"
E_NO_FILE = "osf_no_file"
E_DOWNLOAD_FAIL = "osf_download_failed"

OSF_API_BASE = "https://api.osf.io/v2"
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
                logger.warning(f"OSF PDF exceeds {max_bytes} bytes, truncating")
                return data[:max_bytes]
            return data
    except Exception as e:
        logger.debug(f"OSF PDF download failed: {url}: {e}")
        return None


def fetch_osf_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a PDF from OSF Preprints by DOI.

    Triggers only on `10.31219/osf.io/*` or `10.31234/osf.io/*` DOIs.

    Returns dict with:
      - source: "osf_pdf" (or "{provider}_pdf" like "psyarxiv_pdf")
      - doi, pdf_url, size, path
      - title, provider, license
      - error: only on total failure
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    doi_lower = doi.lower()
    if not (doi_lower.startswith("10.31219/osf.io/") or
            doi_lower.startswith("10.31234/osf.io/")):
        return {"error": E_NOT_OSF,
                "doi": doi,
                "message": "DOI is not an OSF preprint (10.31219/osf.io/* or 10.31234/osf.io/*)",
                "hint": "OSF channel only handles OSF-hosted preprints"}

    # OSF v2 doesn't support filter[doi] directly. We need to use the
    # /preprints/{id}/ endpoint, but we only have the DOI. Try a
    # search via /preprints/ (no filter, then match DOI in response) — OR
    # use the GUID-based download if the DOI maps to one.
    #
    # OSF DOI format is: 10.31219/osf.io/{short_id}  (e.g. nqzs5)
    # The short_id is the OSF preprint ID we need.
    short_id = None
    doi_lower = doi.lower()
    if doi_lower.startswith("10.31219/osf.io/"):
        short_id = doi.split("/")[-1]
    elif doi_lower.startswith("10.31234/osf.io/"):
        short_id = doi.split("/")[-1]
    if not short_id:
        return {"error": E_NOT_OSF,
                "doi": doi,
                "message": "Could not extract OSF short_id from DOI",
                "hint": "Expected 10.31219/osf.io/{id} or 10.31234/osf.io/{id}"}

    # Get the preprint directly by short_id (with version suffix optional)
    api_url = f"{OSF_API_BASE}/preprints/{short_id}/"
    status, data = _http_get_json(api_url, timeout=20)
    if status == 404:
        # Try with version suffix (e.g. nqzs5_v1)
        api_url = f"{OSF_API_BASE}/preprints/{short_id}_v1/"
        status, data = _http_get_json(api_url, timeout=20)
    if status != 200 or not isinstance(data, dict) or "data" not in data:
        return {"error": E_API_ERROR,
                "doi": doi,
                "status": status,
                "message": f"OSF API returned status {status} for short_id={short_id}",
                "hint": "Check DOI or rate limit"}

    preprint = data["data"]
    attributes = preprint.get("attributes", {})

    # Get the primary file relationship → file object
    primary_file = preprint.get("relationships", {}).get("primary_file", {})
    primary_file_data = primary_file.get("data") or {}
    file_id = primary_file_data.get("id")
    if not file_id:
        return {"error": E_NO_FILE,
                "doi": doi,
                "title": attributes.get("title"),
                "message": "OSF preprint has no primary_file relationship",
                "hint": "Preprint metadata exists but no PDF"}

    # Get the file's download URL via /files/{id}/
    file_url = f"{OSF_API_BASE}/files/{file_id}/"
    file_status, file_data = _http_get_json(file_url, timeout=15)
    if file_status != 200 or not isinstance(file_data, dict):
        return {"error": E_NO_FILE,
                "doi": doi,
                "file_url": file_url,
                "message": f"OSF file API returned status {file_status}",
                "hint": "Try other channels"}

    # The download URL is in data.links.download (pattern: https://osf.io/download/{guid}/)
    # file_data has the wrapper structure: {data: {...}, meta: {...}}
    file_inner = file_data.get("data", {})
    download_url = file_inner.get("links", {}).get("download")
    if not download_url:
        return {"error": E_NO_FILE,
                "doi": doi,
                "message": "OSF file has no download link",
                "hint": "Try other channels"}

    # Download
    pdf_bytes = _download_pdf(download_url, timeout=60)
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "pdf_url": download_url,
                "title": attributes.get("title"),
                "hint": "OSF returned a download URL but fetch failed or not a real PDF"}

    # Determine provider
    provider_data = relationships.get("provider", {}).get("data", {})
    provider = provider_data.get("id", "osf") if provider_data else "osf"

    result = {
        "source": f"osf_{provider}_pdf" if provider != "osf" else "osf_pdf",
        "doi": doi,
        "pdf_url": download_url,
        "size": len(pdf_bytes),
        "title": attributes.get("title"),
        "provider": provider,
        "date_published": attributes.get("date_published"),
    }
    if out_path:
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)
        result["path"] = str(out_p.resolve())
    return result
