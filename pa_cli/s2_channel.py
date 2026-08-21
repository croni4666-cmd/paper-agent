"""Semantic Scholar openAccessPdf channel (v3.9.22+, 2026-08-21).

Queries the Semantic Scholar Academic Graph API for `openAccessPdf` field,
which exposes a direct PDF URL when the paper is open-access. Cross-domain
(200M+ papers) and S2's `externalIds` field can also redirect to arXiv/PMC
for fallback.

API: https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,externalIds
Auth: Optional `x-api-key: $S2_API_KEY` for 1 RPS sustained (no key = 100 req/5min shared pool)
Legal: ✅ Allen Institute for AI; data sources comply with publisher terms

v3.9.22 integration: only triggers on explicit `--prefer s2` OR fallback
when DOI is in cross-domain context and no other channel hit.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

E_NO_DOI = "no_doi"
E_API_ERROR = "api_error"
E_NO_PDF = "s2_no_openaccess_pdf"
E_DOWNLOAD_FAIL = "s2_download_failed"

S2_BASE = "https://api.semanticscholar.org/graph/v1"
USER_AGENT = "paper-agent/3.9.22 (+github.com/croni4666-cmd/paper-agent)"


def _http_get_json(url: str, timeout: int = 20) -> tuple[int, Any]:
    """GET JSON; return (status, parsed_json_or_error_dict)."""
    headers = {"User-Agent": USER_AGENT}
    s2_key = os.environ.get("S2_API_KEY")
    if s2_key:
        headers["x-api-key"] = s2_key
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # S2 returns 404 for unknown DOIs
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
                logger.warning(f"S2 PDF exceeds {max_bytes} bytes, truncating")
                return data[:max_bytes]
            return data
    except Exception as e:
        logger.debug(f"S2 PDF download failed: {url}: {e}")
        return None


def fetch_s2_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Fetch a PDF from Semantic Scholar's `openAccessPdf` field by DOI.

    Returns dict with:
      - source: "s2_pdf"
      - doi, pdf_url, size, path
      - pmcid, arxiv_id (if S2 has them in externalIds, useful for fallbacks)
      - error: only on total failure
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    # Use DOI: prefix (S2 supports DOI:NNNN, ARXIV:NNNN, PMID:NNNN, etc.)
    api_url = f"{S2_BASE}/paper/DOI:{urllib.parse.quote(doi)}?fields=openAccessPdf,externalIds,title,year,isOpenAccess"
    status, data = _http_get_json(api_url, timeout=20)
    if status != 200 or not isinstance(data, dict):
        return {"error": E_API_ERROR,
                "doi": doi,
                "status": status,
                "message": f"S2 API returned status {status}",
                "hint": "Check DOI or S2_API_KEY rate limit"}

    oa = data.get("openAccessPdf")
    if not oa or not oa.get("url"):
        return {"error": E_NO_PDF,
                "doi": doi,
                "message": "S2 has no openAccessPdf for this DOI",
                "is_open_access": data.get("isOpenAccess", False),
                "title": data.get("title"),
                "hint": "Try --prefer pmc, --prefer unpaywall, or --prefer scihub"}

    pdf_url = oa["url"]
    title = data.get("title")
    external_ids = data.get("externalIds") or {}
    pmcid = external_ids.get("PMCID")
    arxiv_id = external_ids.get("ArXiv")

    # Download the PDF
    pdf_bytes = _download_pdf(pdf_url, timeout=60)
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return {"error": E_DOWNLOAD_FAIL,
                "doi": doi,
                "pdf_url": pdf_url,
                "title": title,
                "hint": "S2 returned a PDF URL but download failed or not a real PDF"}

    result = {
        "source": "s2_pdf",
        "doi": doi,
        "pdf_url": pdf_url,
        "size": len(pdf_bytes),
        "title": title,
        "year": data.get("year"),
        "pmcid": pmcid,
        "arxiv_id": arxiv_id,
    }
    if out_path:
        out_p = Path(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)
        result["path"] = str(out_p.resolve())
    return result
