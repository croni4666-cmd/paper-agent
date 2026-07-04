"""Test for pa_cli.keys cmd_check 30-min in-memory cache (P0-2)."""

import sys
import time
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli import keys as k


def main():
    # Use test mode to bypass real cache reads
    import os
    os.environ["PA_TEST"] = "1"

    # Track probe calls
    probe_count = [0]

    def fake_probe(url, headers=None, timeout=15):
        probe_count[0] += 1
        return (200, "mocked-ok")

    # 1) Cache cold start: cmd_check should NOT hit cache, should probe
    with patch.object(k, "_probe", side_effect=fake_probe):
        with patch.object(k, "load_registry", return_value={
            "openalex": {"name": "OpenAlex", "env_var": "OPENALEX_API_KEY",
                        "service_url": "http://test/ow",
                        "tier": "free", "expires": None, "notes": "",
                        "last_checked": None, "last_used": None},
        }):
            with patch.object(k, "save_registry", return_value="/tmp/fake"):
                os.environ["OPENALEX_API_KEY"] = "fakekey"
                # First call: cache miss
                # Disable test-mode cache bypass to actually exercise cache
                with patch.dict(os.environ, {}, clear=True):
                    os.environ["PA_TEST"] = "0"
                    os.environ["OPENALEX_API_KEY"] = "fakekey"
                    # Wait — we need test bypass disabled for cache to work,
                    # but we want to ensure first-call-no-cache logic works.
                    # First call: not in cache yet -> probe
                    r1 = k.cmd_check("openalex")
                    print(f"call 1: cache_hit={r1.get('cache_hit')}, "
                          f"probe_count={probe_count[0]}")
                    assert r1.get("cache_hit") is not True  # First call, should NOT be cache hit

                    # Second call within TTL: should hit cache
                    r2 = k.cmd_check("openalex")
                    print(f"call 2: cache_hit={r2.get('cache_hit')}, "
                          f"cache_age={r2.get('cache_age_sec')}s, "
                          f"probe_count={probe_count[0]}")
                    assert r2.get("cache_hit") is True
                    assert r2.get("cache_age_sec", -1) >= 0
                    # Probe count should still be 1 (cache served request)
                    assert probe_count[0] == 1, f"expected 1 probe, got {probe_count[0]}"
                    print("OK: 2nd call within TTL served from cache, no extra probe")

                    # Different service_id busts cache
                    r3 = k.cmd_check(None)
                    print(f"call 3 (diff service_id=None): cache_hit={r3.get('cache_hit')}")
                    assert r3.get("cache_hit") is not True
                    assert probe_count[0] == 2, f"expected 2 probes, got {probe_count[0]}"
                    print("OK: different service_id busts cache, fresh probe")

                    # Same service_id=None should now hit cache
                    r4 = k.cmd_check(None)
                    print(f"call 4 (same service_id=None): cache_hit={r4.get('cache_hit')}")
                    assert r4.get("cache_hit") is True
                    print("OK: same service_id reuses cache")

                    # Manual cache clear
                    k._check_cache_clear()
                    r5 = k.cmd_check(None)
                    print(f"call 5 (after manual clear): cache_hit={r5.get('cache_hit')}")
                    assert r5.get("cache_hit") is not True
                    print("OK: manual clear invalidates cache")

    print("\n=== ALL KEYS CACHE TESTS PASSED ===")


if __name__ == "__main__":
    main()
