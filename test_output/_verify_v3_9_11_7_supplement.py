"""v3.9.11.7 supplementary verify — fill in the 3-tier gaps from earlier audit.

Tests (all via `pa fetch` CLI, not programmatic):
  Test 1: 4 arXiv input forms × --prefer auto (should all route to arxiv)
  Test 2: 1 arXiv form × 5 prefer modes (auto/arxiv should SUCCESS; others
          should honestly fail or fast-fail without arxiv fallback)
  Test 3: backward compat — Nature DOI should still go to sci-hub

Output: test_output/_verify_v3_9_11_7_supplement.log
Exit code: 0 if all expected outcomes match, 1 otherwise.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)


def run_pa_fetch(doi, prefer=None, timeout_sec=600):
    """Run `pa fetch <doi> --prefer <prefer>` and return (dict, err_str).

    The CLI prints [pa] log lines + a JSON dict at the end. We extract
    the last balanced { ... } block.
    """
    cmd = ["python", "-m", "pa_cli", "fetch", doi]
    if prefer:
        cmd.extend(["--prefer", prefer])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, f"TIMEOUT after {timeout_sec}s"

    output = result.stdout + ("\n" + result.stderr if result.stderr else "")

    # Find the last balanced { ... } block (the JSON dict)
    matches = []
    depth = 0
    start = -1
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
        return None, (
            f"No JSON in output. rc={result.returncode} "
            f"stdout_tail={result.stdout[-200:]!r} "
            f"stderr_tail={result.stderr[-200:]!r}"
        )

    try:
        return json.loads(matches[-1]), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}. text: {matches[-1][:200]!r}"


def fmt_row(label, via, size, status, cache, elapsed):
    return (
        f"  {label:35s}  via={via:10s}  size={size:>10,}  "
        f"status={status:20s}  cache={str(cache):5s}  elapsed={elapsed:6.1f}s"
    )


print("=" * 78)
print("v3.9.11.7 SUPPLEMENTARY VERIFY — CLI end-to-end (3 tests)")
print("=" * 78)

# ---------------------------------------------------------------- Test 1
print()
print("=" * 78)
print("Test 1: 4 arXiv input forms via `pa fetch --prefer auto` (CLI)")
print("  Expected: all 4 route to via_channel=arxiv, final_status=SUCCESS, size>0")
print("=" * 78)

arXiv_forms = [
    ("arxiv:1706.03762", "arxiv: prefix form"),
    ("10.48550/arXiv.2310.06825", "arXiv DOI form"),
    ("2310.06825", "arXiv bare ID form"),
    ("https://arxiv.org/abs/1706.03762v7", "arXiv URL tail form"),
]

test1_results = []
for inp, label in arXiv_forms:
    out, err = run_pa_fetch(inp, prefer="auto")
    if err:
        print(fmt_row(label, "ERR", 0, "ERROR", "?", 0))
        print(f"    -> {err}")
        test1_results.append((label, "ERR", 0, "ERROR", "?", 0, err))
        continue
    via = out.get("via_channel", "?")
    size = out.get("size_bytes", 0)
    status = out.get("final_status", "?")
    cache = out.get("cache_hit", "?")
    elapsed = out.get("elapsed_sec", 0.0)
    print(fmt_row(label, via, size, status, cache, elapsed))
    test1_results.append((label, via, size, status, cache, elapsed, None))

t1_pass = sum(1 for r in test1_results if r[1] == "arxiv" and r[3] == "SUCCESS" and r[2] > 0)
print(f"\n  Test 1 result: {t1_pass}/{len(test1_results)} PASS")

# ---------------------------------------------------------------- Test 2
print()
print("=" * 78)
print("Test 2: 1 arXiv form × 5 prefer modes (CLI)")
print("  Expected: auto/arxiv -> SUCCESS via arxiv; annas/cnki -> fast-fail")
print("  scihub -> fail or no-hit (arXiv rarely on sci-hub)")
print("=" * 78)

modes = ["auto", "arxiv", "annas", "cnki", "scihub"]
test2_results = []
for mode in modes:
    out, err = run_pa_fetch("10.48550/arXiv.2310.06825", prefer=mode)
    if err:
        print(fmt_row(f"prefer={mode}", "ERR", 0, "ERROR", "?", 0))
        print(f"    -> {err}")
        test2_results.append((mode, "ERR", 0, "ERROR", "?", 0, err))
        continue
    via = out.get("via_channel", "?")
    size = out.get("size_bytes", 0)
    status = out.get("final_status", "?")
    cache = out.get("cache_hit", "?")
    elapsed = out.get("elapsed_sec", 0.0)
    notes = out.get("_wrapper_notes", {})
    print(fmt_row(f"prefer={mode}", via, size, status, cache, elapsed))
    if notes:
        print(f"    notes: {notes}")
    test2_results.append((mode, via, size, status, cache, elapsed, None))

# Expected per mode
expected = {
    "auto": "arxiv-or-some-success",  # any success
    "arxiv": "arxiv-or-some-success",  # any success
    "annas": "fail-or-some-fail",  # arXiv not on annas
    "cnki": "fail-or-some-fail",  # not Chinese journal
    "scihub": "fail-or-some-fail",  # arXiv rarely on sci-hub
}
t2_pass = 0
for mode, via, size, status, cache, elapsed, err in test2_results:
    if mode in ("auto", "arxiv"):
        if via == "arxiv" and status == "SUCCESS" and size > 0:
            t2_pass += 1
    else:  # annas/cnki/scihub
        # Honest: should NOT be arxiv (forced prefer). Should fail.
        if via != "arxiv":
            t2_pass += 1
print(f"\n  Test 2 result: {t2_pass}/{len(test2_results)} expected-outcome PASS")

# ---------------------------------------------------------------- Test 3
print()
print("=" * 78)
print("Test 3: backward compat — Nature DOI via `pa fetch --prefer auto` (CLI)")
print("  Expected: route to scihub (NOT arxiv), size > 0, status=SUCCESS")
print("=" * 78)

out, err = run_pa_fetch("10.1038/nature12373", prefer="auto")
if err:
    print(f"  ERROR: {err}")
    test3_pass = False
else:
    via = out.get("via_channel", "?")
    size = out.get("size_bytes", 0)
    status = out.get("final_status", "?")
    cache = out.get("cache_hit", "?")
    elapsed = out.get("elapsed_sec", 0.0)
    print(fmt_row("Nature 10.1038/nature12373", via, size, status, cache, elapsed))
    test3_pass = (via == "scihub" and size > 0 and status == "SUCCESS")

print(f"\n  Test 3 result: {'PASS' if test3_pass else 'FAIL'}")

# ---------------------------------------------------------------- Summary
print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
print(f"  Test 1 (4 arXiv forms CLI):        {t1_pass}/{len(test1_results)}")
print(f"  Test 2 (5 prefer modes arXiv DOI): {t2_pass}/{len(test2_results)}")
print(f"  Test 3 (Nature backward compat):   {'PASS' if test3_pass else 'FAIL'}")

total_pass = t1_pass + t2_pass + (1 if test3_pass else 0)
total = len(test1_results) + len(test2_results) + 1
print(f"  TOTAL: {total_pass}/{total}")

sys.exit(0 if total_pass == total else 1)
