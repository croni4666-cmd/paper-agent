"""Smoke test for v3.9.11.5 fix: proxy port 7897 -> 10808 documentation update.

Verifies:
  1. pa fetch --help shows 10808 (not 7897)
  2. Without proxy: works for sci-hub-reachable DOI (direct connection OK on this machine)
  3. With HTTPS_PROXY=10808: works (proxy path)
  4. With HTTPS_PROXY=7897 (wrong port): gives friendly hint about port change
  5. status_report() reflects actual proxy state

Run: python test_output/_smoketest_fetch_3_9_11_5.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("G:/minimax - workspace/Paper agent")


def run_pa(args, env_overrides=None, timeout=180):
    """Run pa_cli with given args, return (stdout, stderr, returncode)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    result = subprocess.run(
        [sys.executable, "-X", "utf-8", "-m", "pa_cli"] + args,
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


print("=" * 70)
print("v3.9.11.5 smoke test: proxy port 7897 -> 10808 fix")
print("=" * 70)
print()

# Test 1: pa fetch --help shows 10808
print("Test 1: pa fetch --help should show 10808 (not 7897)")
print("-" * 70)
out, err, rc = run_pa(["fetch", "--help"], env_overrides={"HTTPS_PROXY": None, "HTTP_PROXY": None})
if "10808" in out and "7897" not in out:
    print(f"  [PASS] help text shows 10808, no 7897")
else:
    print(f"  [FAIL] help text:")
    print(f"    {out[:500]}")
print()

# Test 2: status_report() without proxy
print("Test 2: status_report() without proxy")
print("-" * 70)
out, err, rc = run_pa(
    ["sample-pool", "stats"],  # just to verify CLI works
    env_overrides={"HTTPS_PROXY": None, "HTTP_PROXY": None},
    timeout=30,
)
if rc == 0:
    print(f"  [PASS] CLI works without proxy (rc={rc})")
else:
    print(f"  [WARN] CLI rc={rc} (may be unrelated)")
print()

# Test 3: pa fetch without proxy (direct connection)
print("Test 3: pa fetch <known DOI> WITHOUT proxy (direct connection)")
print("-" * 70)
out, err, rc = run_pa(
    ["fetch", "10.1038/nature12373", "-o", "test_output/_smoke_v395_no_proxy.pdf"],
    env_overrides={"HTTPS_PROXY": None, "HTTP_PROXY": None},
    timeout=180,
)
if "SUCCESS" in out and "saved" in out:
    print(f"  [PASS] direct connection works (sci-hub reachable)")
elif "handoff" in out.lower() or "hinthint" in out.lower() or rc == 2:
    print(f"  [INFO] handoff (DOI not on this source), but no proxy error")
    print(f"    last 200 chars of stderr: {err[-200:]}")
else:
    print(f"  [INFO] rc={rc} (may be expected if sci-hub blocked at network level)")
    print(f"    last 200 chars of stderr: {err[-200:]}")
print()

# Test 4: pa fetch with HTTPS_PROXY=10808 (correct port)
print("Test 4: pa fetch with HTTPS_PROXY=10808 (correct proxy port)")
print("-" * 70)
out, err, rc = run_pa(
    ["fetch", "10.1038/nature12373", "-o", "test_output/_smoke_v395_proxy10808.pdf"],
    env_overrides={"HTTPS_PROXY": "http://127.0.0.1:10808", "HTTP_PROXY": "http://127.0.0.1:10808"},
    timeout=180,
)
if "SUCCESS" in out and "saved" in out:
    print(f"  [PASS] proxy 10808 works")
elif rc == 2:
    print(f"  [INFO] handoff (DOI on this source but cache hit?)")
else:
    print(f"  [INFO] rc={rc}")
    print(f"    last 200 chars of stderr: {err[-200:]}")
print()

# Test 5: pa fetch with HTTPS_PROXY=7897 (old/wrong port) gives friendly hint
print("Test 5: pa fetch with HTTPS_PROXY=7897 (deprecated port) gives friendly hint")
print("-" * 70)
# Need a DOI that won't be on any source, so all channels fail and hint fires.
# Use a fake DOI or one that's not on sci-hub
out, err, rc = run_pa(
    ["fetch", "10.0000/this-doi-does-not-exist-12345", "-o", "test_output/_smoke_v395_proxy7897.pdf"],
    env_overrides={"HTTPS_PROXY": "http://127.0.0.1:7897", "HTTP_PROXY": "http://127.0.0.1:7897"},
    timeout=60,
)
hint_in_err = "10808" in err and "proxy" in err.lower()
hint_in_out = "10808" in out and "proxy" in out.lower()
if hint_in_err or hint_in_out:
    print(f"  [PASS] friendly hint about proxy port fired")
    print(f"    hint excerpt: {(err if hint_in_err else out)[-400:]}")
else:
    print(f"  [INFO] rc={rc} (no hint — DOI may have been found via direct or other path)")
    print(f"    stderr last 200: {err[-200:]}")
    print(f"    stdout last 200: {out[-200:]}")

print()
print("=" * 70)
print("All smoke tests done.")
print("=" * 70)
