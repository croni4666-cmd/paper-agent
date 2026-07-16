"""Integration test: pa fetch hits cache before cascade (v3.9.9.6 wrapper).

v3.9.9.6 wrapper:
  - `pa fetch` (CLI) uses `pa_cli.fetch.fetch_doi()` which:
    1. Checks cache if `use_cache=True` (default)
    2. Falls through to new `pa_cli.fetch.fetch()` (renamed from `fetch_doi`
       in v3.9.8.2; new signature is `fetch(doi, out_path, prefer)`)
  - Old `fetch._cache` alias was removed; cache integration is via
    `from . import cache as _cache_mod` inside the wrapper.

Test 1: cache hit should short-circuit, no fetch call.
Test 2: use_cache=False should bypass cache, call fetch, return failure.

Run from repo root:
  python test_output/test_cache_integration.py
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli import fetch, cache as pa_cache


# Fake PDF body -- valid magic header + padding (must exceed 50KB threshold)
fake_pdf = b"%PDF-1.4\n%test\n" + b"%% padding " * 6000  # ~66KB


def test_cache_hit():
    """Pre-populate cache, call fetch_doi(use_cache=True), assert cache hit."""
    print("\n=== test 1: cache hit short-circuits cascade ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()

        doi = "10.1234/cachehit"
        from pa_cli import cache as c

        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            # Pre-populate cache (the wrapper's `_cache_mod` resolves to the
            # same pa_cli.cache module, so this patch affects both).
            c.cache_put(doi, fake_pdf, channel="openalex",
                        url="http://example.test/cache.pdf", root=cache_root)
            print(f"  cache populated: {list(cache_root.iterdir())}")

            # Mock fetch to assert it's NOT called (cache hit should short-circuit)
            with patch.object(fetch, "fetch",
                              side_effect=AssertionError("fetch should not be called on cache hit")):
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
    print("  [OK] cache hit test passed")


def test_cache_bypass_with_no_cache_flag():
    """use_cache=False should bypass cache, call fetch, return failure."""
    print("\n=== test 2: use_cache=False bypasses cache, falls through to cascade ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()

        doi = "10.1234/bypasstest"

        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            # Pre-populate cache
            pa_cache.cache_put(doi, fake_pdf, channel="openalex", root=cache_root)
            print(f"  cache populated with valid PDF")

            # Mock fetch to return error (simulating all channels failed)
            with patch.object(fetch, "fetch",
                              return_value={"error": "fetch_all_mirrors_failed",
                                            "message": "Test mock: all mirrors failed",
                                            "hint": "Check network"}):
                r = fetch.fetch_doi(doi, output_dir=str(tmp_path / "out"),
                                    use_cache=False)

        # Should NOT have cache_hit flag (bypassed), and final_status should reflect failure
        print(f"  result: via_channel={r.get('via_channel')}, "
              f"final_status={r['final_status']}, cache_hit={r.get('cache_hit')}")
        assert r.get("cache_hit") is None, f"expected no cache_hit, got {r.get('cache_hit')}"
        assert r["final_status"] == "ALL_FAIL"
        print("  PASS: use_cache=False bypassed cache, cascade attempted (and failed as expected)")
    print("  [OK] cache bypass test passed")


def main():
    test_cache_hit()
    test_cache_bypass_with_no_cache_flag()
    print("\n=== ALL INTEGRATION TESTS PASSED ===")


if __name__ == "__main__":
    main()
