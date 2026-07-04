"""Smoke test for pa_cli/cache.py — verifies basic round-trip."""

import sys
import tempfile
from pathlib import Path

# Add project root to path so pa_cli is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli import cache as c


# A synthetic "PDF" — magic header + padding to exceed 50KB threshold
fake_pdf = b"%PDF-1.4\n%test\n" + b"%% padding to pass 50KB is_pdf threshold\n" * 1500
print(f"Fake PDF size: {len(fake_pdf)} bytes")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 1) miss returns None
        miss = c.cache_get("10.1234/test", root=tmp_path)
        assert miss is None, f"expected miss, got {miss}"
        print("OK: miss returns None")

        # 2) put + get returns match
        c.cache_put("10.1234/test", fake_pdf, channel="test", url="http://example/x.pdf", root=tmp_path)
        hit = c.cache_get("10.1234/test", root=tmp_path)
        assert hit is not None, "expected hit, got None"
        assert hit["sha256"] == c.cache_get("10.1234/test", root=tmp_path)["sha256"]
        assert hit["size"] == len(fake_pdf)
        assert hit["channel"] == "test"
        print(f"OK: hit size={hit['size']}, sha256={hit['sha256'][:16]}..., channel={hit['channel']}")

        # 3) sha256 mismatch -> treat as miss
        pdf_path, meta_path = c._paths("10.1234/test", tmp_path)
        pdf_path.write_bytes(b"%PDF-1.4\ncorrupt\n" + b"x" * (60_000))
        miss_after_corrupt = c.cache_get("10.1234/test", root=tmp_path)
        assert miss_after_corrupt is None, f"expected miss after corruption, got {miss_after_corrupt}"
        print("OK: corrupt pdf -> miss")

        # 4) cache_remove
        c.cache_put("10.9999/zzz", fake_pdf, channel="x", root=tmp_path)
        removed = c.cache_remove("10.9999/zzz", root=tmp_path)
        assert removed is True
        assert c.cache_get("10.9999/zzz", root=tmp_path) is None
        print("OK: cache_remove returns True and removes entry")

        # 5) cache_stats
        c.cache_put("10.stat/a", fake_pdf, channel="a", root=tmp_path)
        c.cache_put("10.stat/b", fake_pdf, channel="b", root=tmp_path)
        stats = c.cache_stats(root=tmp_path)
        assert stats["paper_count"] == 2
        assert stats["total_size_bytes"] == 2 * len(fake_pdf)
        assert stats["oldest_ts"] is not None
        assert stats["newest_ts"] is not None
        print(f"OK: stats: papers={stats['paper_count']}, size={stats['total_size_bytes']}, "
              f"oldest_age={stats['oldest_age_days']:.4f}d")

        # 6) cache_clean(older_than_days=-1) removes all (everything older than -1 days, i.e. everything)
        clean = c.cache_clean(older_than_days=-1, root=tmp_path)
        assert clean["removed_files"] >= 2
        post = c.cache_stats(root=tmp_path)
        assert post["paper_count"] == 0
        print(f"OK: clean removed {clean['removed_files']} files, freed {clean['freed_bytes']} bytes")

    print("\n=== ALL SMOKE TESTS PASSED ===")


if __name__ == "__main__":
    main()
