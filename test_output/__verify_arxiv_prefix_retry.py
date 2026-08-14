"""Re-verify the 1 FAIL case from supplement: arxiv:1706.03762 with --prefer auto.

Hypothesis: FAIL was arxiv.org throttling, not a code bug.
Test: retry with 5s sleep between, see if the fix is consistent.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)

def run_pa_fetch(doi, prefer=None, timeout_sec=600):
    cmd = ["python", "-m", "pa_cli", "fetch", doi]
    if prefer:
        cmd.extend(["--prefer", prefer])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_sec, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    output = result.stdout + ("\n" + result.stderr if result.stderr else "")
    # Find last balanced { ... } block
    matches, depth, start = [], 0, -1
    for i, ch in enumerate(output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                matches.append(output[start:i + 1])
                start = -1
    if not matches:
        return None, f"No JSON. rc={result.returncode}"
    try:
        return json.loads(matches[-1]), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse err: {e}"


print("Re-test: arxiv:1706.03762 with --prefer auto (3 retries, 5s gap)")
print("=" * 70)

attempts = []
for i in range(3):
    print(f"\nAttempt {i + 1}...")
    out, err = run_pa_fetch("arxiv:1706.03762", prefer="auto")
    if err:
        print(f"  ERROR: {err}")
        attempts.append(("ERROR", 0, "ERROR", 0, err))
    else:
        via = out.get("via_channel", "?")
        size = out.get("size_bytes", 0)
        status = out.get("final_status", "?")
        elapsed = out.get("elapsed_sec", 0)
        print(f"  via: {via}  size: {size:,}  status: {status}  elapsed: {elapsed:.1f}s")
        attempts.append((via, size, status, elapsed, None))
    if i < 2:
        time.sleep(5)

ok = sum(1 for a in attempts if a[0] == "arxiv" and a[2] == "SUCCESS")
print(f"\nSummary: {ok}/3 SUCCESS")
print("\nVerdict:", "CODE IS FINE — FAIL was arxiv throttling" if ok == 3 else "still flaky")
sys.exit(0 if ok == 3 else 1)
