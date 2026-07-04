"""End-to-end CLI test for pa cache subcommand group (P0-2).

Exercises:
  pa cache path        -- returns str cache root
  pa cache stats       -- on empty cache / after put
  pa cache put         -- manual insert
  pa cache drop        -- manual remove
  pa cache clean       -- delete by age filter
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


# A small valid-looking PDF for testing purposes
FAKE_PDF = b"%PDF-1.4\n%test\n" + b"%% padding " * 6000  # ~66KB


# Force UTF-8 in subprocess output (Windows console defaults to GBK/CP936)
_SUBENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def run_pa_cache(*args, env=None, cwd=None):
    """Run pa cache subcommand, return (returncode, stdout, stderr).

    Always merges parent's env (with PYTHONUTF8) so commands like `pa cache path`
    that use Path.home() still resolve correctly. Pass `env` as a dict of
    ADDITIONAL/override vars.
    """
    cmd = [sys.executable, "-m", "pa_cli", "cache"] + list(args)
    full_env = {**_SUBENV, **(env or {})}
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            env=full_env, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def test_pa_cache_path():
    print("\n=== test: pa cache path ===")
    rc, out, err = run_pa_cache("path")
    print(f"  rc={rc}, stdout={out.strip()!r}, stderr_excerpt={err[:80]!r}")
    assert rc == 0
    # Resolve default cache root from python directly
    expected_default = str(Path.home() / ".paper-agent" / "cache")
    assert "paper-agent" in out and out.strip().endswith("cache"), \
        f"expected to mention paper-agent and end with cache, got {out!r}"
    print("  PASS")


def test_pa_cache_stats_empty():
    print("\n=== test: pa cache stats (empty) ===")
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, err = run_pa_cache("stats", env={"PA_CACHE_DIR": str(Path(tmp) / "cache")})
        # Note: PA_CACHE_DIR won't apply to already-resolved root unless
        # the helpers resolve at invocation time (they do via get_cache_root each call)
        print(f"  rc={rc}, stdout_excerpt={out[:200]!r}")
        assert rc == 0
        assert "0 PDF" in out


def test_pa_cache_put_and_stats():
    print("\n=== test: pa cache put + stats + drop ===")
    # Use a temp PDF + override cache dir via env
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(FAKE_PDF)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        env = {"PA_CACHE_DIR": str(cache_root)}

        # pa cache stats (should be empty / 0 entries)
        rc, out, err = run_pa_cache("stats", env=env)
        print(f"  cache stats (empty):\n{out!r}, stderr={err[:100]!r}")
        assert rc == 0, f"rc={rc} stderr={err!r}"
        assert "0 PDF" in out

        # pa cache put 10.1234/test test.pdf --channel openalex
        rc, out, err = run_pa_cache("put", "10.1234/test", str(pdf_path),
                                    "--channel", "openalex", env=env)
        print(f"  cache put: rc={rc}, out={out.strip()[:200]!r}")
        assert rc == 0
        assert "cached" in out
        assert "sha256:" in out

        # pa cache stats (should be 1 entry)
        rc, out, _ = run_pa_cache("stats", env=env)
        print(f"  cache stats (1 entry):\n{out}")
        assert "1 PDF(s)" in out or "1 PDF" in out
        assert "openalex" not in out  # channel isn't shown in stats, just size/count

        # pa cache drop 10.1234/test
        rc, out, _ = run_pa_cache("drop", "10.1234/test", env=env)
        print(f"  cache drop: out={out.strip()!r}")
        assert rc == 0

        # cache should be empty again
        rc, out, _ = run_pa_cache("stats", env=env)
        assert "0 PDF" in out
        print(f"  cache stats (after drop):\n{out}")

        # cache drop on nonexistent entry returns success but no-op
        rc, out, _ = run_pa_cache("drop", "10.1234/nonexistent", env=env)
        assert rc == 0
        assert "nothing to drop" in out
        print(f"  cache drop (nonexistent): out={out.strip()!r}")

        print("  PASS")


def test_pa_cache_clean_all():
    print("\n=== test: pa cache clean --all ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        env = {"PA_CACHE_DIR": str(cache_root),
               "PATH": __import__("os").environ.get("PATH", "")}

        # put 2 entries
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(FAKE_PDF)
        for i in ("a", "b"):
            run_pa_cache("put", f"10.9999/{i}", str(pdf), env=env)

        # clean all
        rc, out, _ = run_pa_cache("clean", "--all", env=env)
        print(f"  clean --all: rc={rc}, out={out!r}")
        assert rc == 0
        assert "Removed:" in out
        assert "4 file(s)" in out  # 2 PDFs + 2 metas

        # stats should be empty
        rc, out, _ = run_pa_cache("stats", env=env)
        assert "0 PDF" in out
        print("  PASS")


def test_pa_cache_clean_refuses_without_filter():
    print("\n=== test: pa cache clean (no filter, refuses) ===")
    rc, out, err = run_pa_cache("clean")
    # Should print error to stderr and exit 2
    print(f"  rc={rc}, stderr={err.strip()[:200]!r}")
    assert rc == 2
    assert "Refusing" in err


def test_pa_cache_clean_dry_run():
    print("\n=== test: pa cache clean --dry-run ===")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        env = {"PA_CACHE_DIR": str(cache_root),
               "PATH": __import__("os").environ.get("PATH", "")}
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(FAKE_PDF)
        run_pa_cache("put", "10.9999/a", str(pdf), env=env)

        rc, out, _ = run_pa_cache("clean", "--all", "--dry-run", env=env)
        print(f"  dry-run: rc={rc}, out={out.strip()!r}")
        assert rc == 0
        assert "dry-run" in out

        # entries should still be there
        rc, out, _ = run_pa_cache("stats", env=env)
        assert "1 PDF" in out


def main():
    test_pa_cache_path()
    test_pa_cache_stats_empty()
    test_pa_cache_put_and_stats()
    test_pa_cache_clean_all()
    test_pa_cache_clean_refuses_without_filter()
    test_pa_cache_clean_dry_run()
    print("\n=== ALL PA-CACHE CLI TESTS PASSED ===")


if __name__ == "__main__":
    main()
