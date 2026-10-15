"""Opt-in, keyless public endpoint checks. No PDFs, corpus, dotenv or SDKs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ENDPOINTS = {
    "crossref": "https://api.crossref.org/works?query.bibliographic=science&rows=1",
    "openalex": "https://api.openalex.org/works?search=science&per_page=1",
    "semanticscholar": "https://api.semanticscholar.org/graph/v1/paper/search?query=science&limit=1&fields=title",
    "arxiv": "https://export.arxiv.org/api/query?search_query=all:science&max_results=1",
    "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=science&retmode=json&retmax=1&tool=paper-agent",
    "clinicaltrials": "https://clinicaltrials.gov/api/v2/studies?query.term=science&pageSize=1&format=json",
}
MAX_BYTES = 2 * 1024 * 1024
CHILD_TIMEOUT = 15
STATUSES = {"healthy", "empty", "rate_limited", "access_denied", "unavailable", "timeout",
            "schema_changed", "response_too_large", "not_checked", "probe_failed"}


def validate_body(engine, raw):
    if engine == "arxiv":
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("unsupported XML")
        root = ET.fromstring(raw)
        if root.tag != "{http://www.w3.org/2005/Atom}feed":
            raise ValueError("not Atom")
        rows = root.findall("{http://www.w3.org/2005/Atom}entry")
        for row in rows:
            identifier = row.findtext("{http://www.w3.org/2005/Atom}id") or ""
            title = row.findtext("{http://www.w3.org/2005/Atom}title") or ""
            if "/api/errors" in identifier or not identifier.startswith("http") or not title.strip():
                raise ValueError("invalid Atom entry")
        return len(rows)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or "error" in data or "errors" in data:
        raise ValueError("not a result object")
    if engine == "crossref":
        rows = data["message"]["items"]
    elif engine == "pubmed":
        if data["esearchresult"].get("errorlist"):
            raise ValueError("query error")
        rows = data["esearchresult"]["idlist"]
    else:
        rows = data[{"openalex": "results", "semanticscholar": "data", "clinicaltrials": "studies"}[engine]]
    if not isinstance(rows, list) or not all(isinstance(row, str) if engine == "pubmed" else isinstance(row, dict) for row in rows):
        raise ValueError("invalid records")
    for row in rows:
        if engine == "pubmed":
            valid = row.isdigit()
        elif engine == "crossref":
            valid = isinstance(row.get("DOI"), str) and row["DOI"] and (row.get("title") is None or
                    isinstance(row["title"], list) and all(isinstance(title, str) for title in row["title"]))
        elif engine == "openalex":
            valid = isinstance(row.get("id"), str) and row["id"] and (row.get("title") is None or isinstance(row["title"], str))
        elif engine == "semanticscholar":
            valid = isinstance(row.get("paperId"), str) and row["paperId"] and (row.get("title") is None or isinstance(row["title"], str))
        else:
            protocol = row.get("protocolSection")
            identification = protocol.get("identificationModule") if isinstance(protocol, dict) else None
            if not isinstance(identification, dict):
                raise ValueError("missing identification")
            valid = isinstance(identification.get("nctId"), str) and identification["nctId"].startswith("NCT") and (identification.get("briefTitle") is None or isinstance(identification["briefTitle"], str))
        if not valid:
            raise ValueError("missing normalized fields")
    return len(rows)


def probe(engine):
    started = time.monotonic()
    result = {"engine": engine, "status": "probe_failed"}
    try:
        # No inherited proxy credentials, API keys, cookies, redirects to login or retries.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        request = urllib.request.Request(ENDPOINTS[engine], headers={
            "User-Agent": "paper-agent-maintenance/1", "Accept-Encoding": "identity"})
        with opener.open(request, timeout=10) as response:
            result["http_status"] = response.status
            if response.status != 200:
                result["status"] = "unavailable"
            else:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    result["status"] = "response_too_large"
                else:
                    count = validate_body(engine, raw)
                    result.update(status="healthy" if count else "empty", sample_count=count)
    except urllib.error.HTTPError as error:
        result.update(http_status=error.code, status="rate_limited" if error.code == 429 else
                      "access_denied" if error.code in (401, 403) else "unavailable")
        error.close()
    except (TimeoutError,):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        result["status"] = "timeout" if isinstance(error.reason, TimeoutError) else "unavailable"
    except (ValueError, KeyError, TypeError, ET.ParseError, RecursionError):
        result["status"] = "schema_changed"
    except OSError:
        result["status"] = "unavailable"
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def collect(live=False, engines=None):
    selected = list(ENDPOINTS) if engines is None else list(dict.fromkeys(engines))
    if not selected or set(selected) - set(ENDPOINTS):
        raise ValueError("Select a supported engine")
    checks = []
    for engine in selected:
        row = {"engine": engine, "status": "not_checked"}
        if live:
            try:
                child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe-child", engine],
                                       capture_output=True, timeout=CHILD_TIMEOUT)
                candidate = json.loads(child.stdout)
                if (child.returncode != 0 or not isinstance(candidate, dict) or candidate.get("engine") != engine
                        or candidate.get("status") not in STATUSES):
                    raise ValueError("invalid child receipt")
                # Allowlist fields; never relay arbitrary child text or stderr.
                row = {key: candidate[key] for key in ("engine", "status", "http_status", "sample_count", "elapsed_seconds")
                       if key in candidate}
            except subprocess.TimeoutExpired:
                row["status"] = "timeout"
            except (OSError, ValueError, TypeError):
                row["status"] = "probe_failed"
        checks.append(row)
    return {"schema": "paper-agent-engine-health", "schema_version": 1,
            "checked_at": datetime.now(timezone.utc).isoformat(), "mode": "live-keyless" if live else "offline",
            "scope": "Endpoint shape/access only, not installed SDK or scientific quality; no response bodies retained.",
            "checks": checks, "unselected_engines": [engine for engine in ENDPOINTS if engine not in selected],
            "optional_not_probed": ["aminer", "cnki", "core", "pdf-download-channels"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="One public request per engine, no keys/retries/PDFs")
    parser.add_argument("--engine", action="append", choices=ENDPOINTS, help="Limit checks to named engines (repeatable)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--probe-child", choices=ENDPOINTS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe_child:
        print(json.dumps(probe(args.probe_child)))
        return 0
    report = collect(args.live, args.engine)
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from pa_cli.run_report import write_report
        try:
            write_report(args.output, content, [Path(__file__)])
        except (OSError, ValueError):
            parser.exit(2, "Cannot publish engine health report\n")
    else:
        print(content, end="")
    return 0 if not args.live or all(row["status"] == "healthy" for row in report["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
