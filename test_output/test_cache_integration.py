"""Integration test: pa fetch hits cache before cascade.

Approach: pre-populate cache with a fake PDF (PDF magic + padding),
mock all network channels to return failure, call fetch_doi, assert:
1. via_channel = 'cache:openalex' (or similar cache marker)
2. final_status = 'SUCCESS_CACHE_HIT'
3. elapsed_sec < 0.5 (no cascade attempted)
4. cache_hit flag set in result dict

Negative test: use_cache=False should fall through to cascade (which fails
because channels are mocked to fail), demonstrating the bypass semantics.
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli import fetch, cache as pa_cache


# Fake PDF body — valid magic header + padding (must exceed 50KB threshold)
fake_pdf = b"%PDF-1.4\n%test\n" + b"%% padding " * 6000  # ~66KB

# A no-network HTTP that always fails
def http_get_fail(url, headers=None, timeout=20, proxy=None):
    return (0, b"", url, {})


# Stand-in channels returning failure shapes
def fail_openalex(doi):
    return {"status": "fail", "stage": "openalex-mocked"}

def fail_arxiv(doi):
    return {"status": "skip", "reason": "test-mock"}

def fail_unpaywall(doi, email):
    return {"status": "fail", "stage": "unpaywall-mocked"}

def fail_doi_redirect(doi):
    return {"status": "fail", "stage": "doi-redirect-mocked"}

def fail_scihub(doi):
    return {"status": "fail", "stage": "scihub-mocked"}


def fail_playwright(*args, **kwargs):
    """Mock channel_playwright_pdf to skip — would otherwise launch real chromium."""
    return {"status": "skip", "reason": "test-mock-playwright-bypass"}


def test_cache_hit():
    print("\n=== test 1: cache hit short-circuits cascade ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()

        # Pre-populate cache
        doi = "10.1234/cachehit"
        cache_root_real = pa_cache.get_cache_root()  # save + restore
        try:
            from pa_cli import cache as c
            # Patch global cache root by using root= kwarg throughout
            # Need to patch both fetch._cache.cache_get and cache.put paths

            with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
                # Re-patch fetch's reference to the cache module's functions
                with patch.object(fetch._cache, "get_cache_root", return_value=cache_root):
                    # Pre-populate
                    c.cache_put(doi, fake_pdf, channel="openalex",
                                url="http://example.test/cache.pdf", root=cache_root)
                    print(f"  cache populated: {list(cache_root.iterdir())}")

                    # Call fetch with mocked-all-fail channels
                    with patch.multiple("pa_cli.fetch",
                                       http_get=fetch.http_get,  # let default helpers through
                                       channel_openalex=fail_openalex,
                                       channel_arxiv=fail_arxiv,
                                       channel_unpaywall=fail_unpaywall,
                                       channel_doi_redirect=fail_doi_redirect,
                                       channel_scihub_mirror=fail_scihub):
                        # Override http_get to fail whenever cache miss happens
                        with patch("pa_cli.fetch.http_get", side_effect=http_get_fail):
                            t0 = time.time()
                            r = fetch.fetch_doi(doi, output_dir=str(tmp_path / "out"),
                                              use_cache=True)
                            elapsed = time.time() - t0

                    # Validate
                    print(f"  result: via_channel={r['via_channel']}, "
                          f"final_status={r['final_status']}, elapsed={r['elapsed_sec']}s "
                          f"(real {elapsed:.3f}s)")
                    assert r["via_channel"].startswith("cache:"), f"expected cache: prefix, got {r['via_channel']}"
                    assert r["final_status"] == "SUCCESS_CACHE_HIT"
                    assert r.get("cache_hit") is True
                    assert r.get("cache_sha256") is not None
                    assert r["saved_as"].endswith(".pdf")
                    assert r["elapsed_sec"] < 0.5, f"expected <0.5s, got {r['elapsed_sec']}"
                    print("  PASS: cache hit short-circuited in <0.5s, all flags set")
        finally:
            pass  # no global state to restore
    print("  ✓ cache hit test passed")


def test_cache_bypass_with_no_cache_flag():
    print("\n=== test 2: use_cache=False bypasses cache, falls through to cascade ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()

        doi = "10.1234/bypasstest"

        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            with patch.object(fetch._cache, "get_cache_root", return_value=cache_root):
                # Pre-populate cache
                pa_cache.cache_put(doi, fake_pdf, channel="openalex", root=cache_root)
                print(f"  cache populated with valid PDF")

                # Now call with use_cache=False — should bypass cache and hit cascade
                with patch.multiple("pa_cli.fetch",
                                   channel_openalex=fail_openalex,
                                   channel_arxiv=fail_arxiv,
                                   channel_unpaywall=fail_unpaywall,
                                   channel_doi_redirect=fail_doi_redirect,
                                   channel_scihub_mirror=fail_scihub,
                                   channel_playwright_pdf=fail_playwright):
                    with patch("pa_cli.fetch.http_get", side_effect=http_get_fail):
                        r = fetch.fetch_doi(doi, output_dir=str(tmp_path / "out"),
                                          use_cache=False)

                # Should NOT have cache_hit flag, and final_status should reflect failure
                print(f"  result: via_channel={r.get('via_channel')}, "
                      f"final_status={r['final_status']}, cache_hit={r.get('cache_hit')}")
                assert r.get("cache_hit") is None, f"expected no cache_hit, got {r.get('cache_hit')}"
                assert r["final_status"] == "ALL_FAIL"
                print("  PASS: use_cache=False bypassed cache, cascade attempted")
    print("  ✓ cache bypass test passed")


def main():
    test_cache_hit()
    test_cache_bypass_with_no_cache_flag()
    print("\n=== ALL INTEGRATION TESTS PASSED ===")


if __name__ == "__main__":
    main()
