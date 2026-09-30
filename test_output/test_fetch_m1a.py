"""Offline regression tests for ROADMAP [P3-32] M1A Fetch correctness.

Run from the repository root:
    python test_output/test_fetch_m1a.py
"""

import hashlib
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli import cache as pa_cache
from pa_cli import fetch as fetch_module
from test_output.fetch_m1a_helpers import (
    FAKE_PDF,
    invalid_artifact_fetch,
    slow_fetch,
    successful_pdf_fetch,
    xml_only_fetch,
)


def test_successful_fetch_writes_cache_and_returns_sha():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_root = root / "cache"
        cache_root.mkdir()
        doi = "10.1234/m1a-cache-write"
        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            result = fetch_module.fetch_doi(
                doi,
                output_dir=str(root / "out"),
                max_total_sec=2,
                _fetch_fn=successful_pdf_fetch,
            )
            hit = pa_cache.cache_get(doi, root=cache_root)

        expected_sha = hashlib.sha256(FAKE_PDF).hexdigest()
        assert result["final_status"] == "SUCCESS"
        assert result["artifact_type"] == "pdf"
        assert result["artifact_sha256"] == expected_sha
        assert result["cache_sha256"] == expected_sha
        assert result["cache_written"] is True
        assert hit is not None
        assert hit["sha256"] == expected_sha


def test_no_cache_bypasses_lookup_but_still_writes_success():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_root = root / "cache"
        cache_root.mkdir()
        doi = "10.1234/m1a-no-cache"
        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            result = fetch_module.fetch_doi(
                doi,
                output_dir=str(root / "out"),
                max_total_sec=2,
                use_cache=False,
                _fetch_fn=successful_pdf_fetch,
            )
            hit = pa_cache.cache_get(doi, root=cache_root)

        assert result["cache_hit"] is False
        assert result["cache_written"] is True
        assert hit is not None


def test_xml_only_result_is_truthful_and_not_pdf_cached():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_root = root / "cache"
        cache_root.mkdir()
        doi = "10.1234/m1a-xml-only"
        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            result = fetch_module.fetch_doi(
                doi,
                output_dir=str(root / "out"),
                max_total_sec=2,
                _fetch_fn=xml_only_fetch,
            )
            hit = pa_cache.cache_get(doi, root=cache_root)

        assert result["final_status"] == "SUCCESS_XML_ONLY"
        assert result["artifact_type"] == "xml"
        assert result["saved_as"].endswith(".xml")
        assert result["cache_written"] is False
        assert hit is None


def test_invalid_success_result_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_root = root / "cache"
        cache_root.mkdir()
        doi = "10.1234/m1a-invalid"
        with patch.object(pa_cache, "get_cache_root", return_value=cache_root):
            result = fetch_module.fetch_doi(
                doi,
                output_dir=str(root / "out"),
                max_total_sec=2,
                _fetch_fn=invalid_artifact_fetch,
            )
            hit = pa_cache.cache_get(doi, root=cache_root)

        assert result["final_status"] == "INVALID_ARTIFACT"
        assert result["saved_as"] is None
        assert result["cache_written"] is False
        assert hit is None


def test_total_timeout_terminates_worker_and_returns_promptly():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        started = time.monotonic()
        result = fetch_module.fetch_doi(
            "10.1234/m1a-timeout",
            output_dir=str(root / "out"),
            max_total_sec=0.05,
            use_cache=False,
            _fetch_fn=slow_fetch,
        )
        elapsed = time.monotonic() - started

        assert result["final_status"] == "TIMEOUT"
        assert result["error"] == "fetch_timeout"
        assert result["saved_as"] is None
        assert elapsed < 0.35, elapsed
        time.sleep(0.55)
        assert not (root / "out").exists() or not any((root / "out").glob("*.pdf"))


def main():
    tests = [
        test_successful_fetch_writes_cache_and_returns_sha,
        test_no_cache_bypasses_lookup_but_still_writes_success,
        test_xml_only_result_is_truthful_and_not_pdf_cached,
        test_invalid_success_result_is_rejected,
        test_total_timeout_terminates_worker_and_returns_promptly,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("\n=== ALL M1A FETCH TESTS PASSED ===")


if __name__ == "__main__":
    main()
