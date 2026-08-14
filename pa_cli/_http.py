"""pa_cli._http - Shared HTTP utilities for all engines (v3.9.13.3).

Centralizes the proxy + TLS validation logic that was previously
duplicated across 6+ files (search.py, keys.py, aminer_channel.py,
batch_fetch.py, cross_encoder.py, deep_rerank.py). All bare
`ur.urlopen` / `urllib.request.urlretrieve` / `requests.get` calls
in pa_cli/ should now go through this module so the v3.9.13.0
plaintext-proxy check fires for every network operation.

Public API:
    - get_proxy_dict() -> Dict[str, str]
        Returns urllib ProxyHandler dict ({"http": p, "https": p})
        or empty dict if no proxy. Validates proxy with
        validate_proxy_security() (refuses remote HTTP, warns on local).
    - validate_proxy_security(proxy_url, allow_remote=False) -> None
        Raises RuntimeError for remote HTTP proxy unless
        PAPER_AGENT_ALLOW_REMOTE_PROXY=1.
    - build_opener() -> urllib.request.OpenerDirector
        urllib opener with proxy support.
    - http_get(url, headers=None, timeout=30) -> bytes
        GET request with proxy support. Returns raw bytes.
    - http_get_json(url, headers=None, timeout=30) -> dict
        GET request, parse JSON. Returns dict (or {} on parse fail).
    - http_post(url, data=None, headers=None, timeout=30) -> bytes
        POST request with form data and proxy support.
    - http_request_get(url, headers=None, timeout=5) -> (int, dict)
        For requests.get-style use (returns status + json body).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request as ur
import warnings
from typing import Any, Dict, Optional, Tuple


def get_allow_remote_proxy() -> bool:
    """Check if user explicitly allows remote (non-local) proxies."""
    return os.environ.get("PAPER_AGENT_ALLOW_REMOTE_PROXY", "").strip() in (
        "1", "true", "yes"
    )


def validate_proxy_security(proxy_url: str, allow_remote: bool = False) -> None:
    """Validate proxy URL for plaintext-leak risk. Warn or raise.

    Threat model (v3.9.13.0):
    - http:// proxy = plaintext CONNECT handshake. Target hostname visible
      to anyone on path between client and proxy. After CONNECT, data
      flow is TLS-encrypted to target, so API key in URL (?api_key=...)
      is NOT visible.
    - https:// proxy = encrypted CONNECT. Hostname hidden. Best.
    - socks5:// proxy = plaintext SOCKS5 handshake. Hostname visible.

    Local Clash/V2RayN on 127.0.0.1: http:// is acceptable (user-controlled
    proxy), but we WARN for awareness.

    Remote HTTP proxy: refused unless allow_remote=True.
    """
    import ipaddress
    import urllib.parse as up

    try:
        parsed = up.urlparse(proxy_url)
    except Exception:
        return  # cannot parse; let urllib deal with it

    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    if scheme not in ("http", "https", "socks5", "socks5h"):
        return  # unknown scheme, skip

    is_local = False
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        is_local = True
    elif host.startswith(("10.", "192.168.")):
        is_local = True
    elif host.startswith("172."):
        try:
            ip = ipaddress.IPv4Address(host)
            if ip in ipaddress.IPv4Network("172.16.0.0/12"):
                is_local = True
        except ValueError:
            pass

    if scheme in ("https",):
        return  # HTTPS proxy: encrypted, no leak

    if scheme in ("socks5", "socks5h"):
        if is_local:
            warnings.warn(
                f"paper-agent: proxy {proxy_url} uses SOCKS5 (plaintext hostname "
                f"leak). For local proxy this is acceptable; for remote consider "
                f"using HTTPS proxy or VPN.",
                stacklevel=3,
            )
        else:
            if not allow_remote:
                raise RuntimeError(
                    f"paper-agent: REFUSING remote SOCKS5 proxy {proxy_url}. "
                    f"SOCKS5 leaks target hostname in plaintext. Either:\n"
                    f"  - Run a local SOCKS5 proxy (Clash/V2RayN on 127.0.0.1)\n"
                    f"  - Use HTTPS proxy instead\n"
                    f"  - Set environment variable PAPER_AGENT_ALLOW_REMOTE_PROXY=1 "
                    f"to override (NOT recommended for untrusted networks)"
                )
        return

    if scheme == "http":
        if is_local:
            warnings.warn(
                f"paper-agent: proxy {proxy_url} uses HTTP (plaintext CONNECT "
                f"handshake - target hostname visible to anyone on path). For "
                f"local Clash/V2RayN this is acceptable. For REMOTE proxy, "
                f"consider HTTPS proxy or VPN.",
                stacklevel=3,
            )
        else:
            if not allow_remote:
                raise RuntimeError(
                    f"paper-agent: REFUSING remote HTTP proxy {proxy_url}. "
                    f"HTTP proxy leaks target hostname in plaintext CONNECT. "
                    f"Either:\n"
                    f"  - Run a local HTTP proxy (Clash/V2RayN on 127.0.0.1)\n"
                    f"  - Use HTTPS proxy instead\n"
                    f"  - Set environment variable PAPER_AGENT_ALLOW_REMOTE_PROXY=1 "
                    f"to override (NOT recommended for untrusted networks)"
                )
            warnings.warn(
                f"paper-agent: using remote HTTP proxy {proxy_url} "
                f"(PAPER_AGENT_ALLOW_REMOTE_PROXY=1). Target hostname will be "
                f"visible in plaintext CONNECT. This is your decision; do not use "
                f"on untrusted networks.",
                stacklevel=3,
            )


def get_proxy_dict() -> Dict[str, str]:
    """Read proxy from env vars. Supports HTTP_PROXY / HTTPS_PROXY / ALL_PROXY.

    v3.9.13.0 (Round 11): added validate_proxy_security() check.
    v3.9.13.3 (Round 13): extracted from pa_cli.fetch to pa_cli._http so all
    8 search engines + fetch-batch + cross-encoder + deep-rerank + aminer
    + keys-probe share the same TLS validation.
    """
    p = (os.environ.get("HTTPS_PROXY")
         or os.environ.get("HTTP_PROXY")
         or os.environ.get("ALL_PROXY")
         or os.environ.get("https_proxy")
         or os.environ.get("http_proxy")
         or os.environ.get("all_proxy")
         or "").strip()
    if not p:
        return {}
    if not p.startswith(("http://", "https://", "socks5://", "socks5h://")):
        p = "http://" + p
    validate_proxy_security(p, allow_remote=get_allow_remote_proxy())
    return {"http": p, "https": p}


def build_opener() -> "ur.OpenerDirector":
    """Build urllib opener with proxy support (cached per call)."""
    proxies = get_proxy_dict()
    if proxies:
        return ur.build_opener(ur.ProxyHandler(proxies))
    return ur.build_opener()


def http_get(url: str, headers: Optional[Dict[str, str]] = None,
              timeout: int = 30) -> bytes:
    """GET with proxy support, returns raw bytes.

    v3.9.13.3: extracted from pa_cli.fetch:_http_get_bytes for shared use.
    """
    final_headers = {
        "User-Agent": "paper-agent/3.9.13.3 (Mavis)",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if headers:
        final_headers.update(headers)
    opener = build_opener()
    req = ur.Request(url, headers=final_headers)
    resp = opener.open(req, timeout=timeout)
    body = resp.read()
    # Auto-decode gzip/deflate/br
    ce = resp.headers.get("Content-Encoding", "").lower()
    if ce == "gzip":
        import gzip
        body = gzip.decompress(body)
    elif ce == "deflate":
        import zlib
        body = zlib.decompress(body)
    elif ce == "br":
        try:
            import brotli
            body = brotli.decompress(body)
        except ImportError:
            pass
    return body


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None,
                   timeout: int = 30) -> Tuple[int, Any]:
    """GET with proxy support, returns (status, json-or-bytes).

    v3.9.13.3: extracted from pa_cli.search:http_get_json for shared use.
    Returns (status, parsed_dict) on success, (status, error_dict) on
    HTTP error, (0, {}) on connection error.
    """
    try:
        body = http_get(url, headers=headers, timeout=timeout)
        try:
            return 200, json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 200, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            return e.code, json.loads(body.decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def http_post(url: str, data: Optional[Dict[str, Any]] = None,
               headers: Optional[Dict[str, str]] = None,
               timeout: int = 30) -> bytes:
    """POST with proxy support, returns raw bytes.

    v3.9.13.3: shared helper for batch_fetch.py and other future POST needs.
    """
    final_headers = {
        "User-Agent": "paper-agent/3.9.13.3 (Mavis)",
        "Accept": "*/*",
    }
    if headers:
        final_headers.update(headers)
    body_data = None
    if data is not None:
        body_data = urllib.parse.urlencode(data).encode("utf-8")
    opener = build_opener()
    req = ur.Request(url, data=body_data, headers=final_headers, method="POST")
    resp = opener.open(req, timeout=timeout)
    return resp.read()


def http_request_get(url: str, headers: Optional[Dict[str, str]] = None,
                      timeout: int = 5) -> Tuple[int, Any]:
    """requests.get-style call returning (status, json-or-text).

    v3.9.13.3: wrapper for deep_rerank.py / other files that use requests
    library. Uses the same get_proxy_dict() to honor HTTPS_PROXY.
    """
    try:
        import requests
    except ImportError:
        return 0, {"error": "requests library not available"}

    try:
        proxies = get_proxy_dict()
        resp = requests.get(url, timeout=timeout, headers=headers or {}, proxies=proxies)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text
    except Exception as e:
        return 0, {"error": str(e)[:200]}
