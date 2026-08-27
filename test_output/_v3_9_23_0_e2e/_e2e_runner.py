"""E2E runner: test all 8 scripts with valid args (when possible)."""
import json
import subprocess
import sys
from pathlib import Path

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
SCRIPTS = PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts"

results = {}

def run(name, *args, timeout=60):
    script = SCRIPTS / name
    if not script.is_file():
        results[name] = {"error": "script_not_found"}
        return
    try:
        r = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PA_ROOT),
        )
        results[name] = {
            "exit_code": r.returncode,
            "stdout_len": len(r.stdout),
            "stderr_len": len(r.stderr),
        }
        if r.stdout:
            results[name]["stdout_first_200"] = r.stdout[:200]
        if r.returncode != 0 and r.stderr:
            results[name]["stderr_first_200"] = r.stderr[:200]
    except subprocess.TimeoutExpired:
        results[name] = {"error": "timeout", "timeout": timeout}

# Test all 8 scripts
print("=== Testing all 8 scripts ===\n")

# 1. version (no args needed, simplest)
print("1. version.py")
run("version.py", timeout=15)
print(json.dumps(results.get("version.py", {}), indent=2))
print()

# 2. keys.py list (might fail if no keys, but should produce JSON)
print("2. keys.py list")
run("keys.py", "list", timeout=30)
print(json.dumps(results.get("keys.py", {}), indent=2))
print()

# 3. keys.py check with no service (should fail)
print("3. keys.py check (missing service)")
run("keys.py", "check", timeout=15)
print(json.dumps(results.get("keys.py", {}), indent=2))
print()

# 4. cache.py stats (no args, returns JSON)
print("4. cache.py stats")
run("cache.py", "stats", timeout=30)
print(json.dumps(results.get("cache.py", {}), indent=2))
print()

# 5. search.py with real query
print("5. search.py BERT")
run("search.py", "BERT", "--engine", "semanticscholar", "--limit", "2", timeout=60)
print(json.dumps(results.get("search.py", {}), indent=2))
print()

# 6. fetch.py with real DOI
print("6. fetch.py 10.1371/journal.pone.0000001 --prefer s2")
run("fetch.py", "10.1371/journal.pone.0000001", "--prefer", "s2", "--output-dir", str(PA_ROOT / "test_output" / "_v3_9_23_0_e2e"), timeout=120)
print(json.dumps(results.get("fetch.py", {}), indent=2))
print()

# 7. citations.py with real DOI
print("7. citations.py 10.1038/nature12373 --direction forward --limit 3")
run("citations.py", "10.1038/nature12373", "--direction", "forward", "--limit", "3", timeout=60)
print(json.dumps(results.get("citations.py", {}), indent=2))
print()

# 8. review.py with empty corpus arg (should fail gracefully)
print("8. review.py (missing corpus)")
run("review.py", timeout=15)
print(json.dumps(results.get("review.py", {}), indent=2))

# Final summary
print("\n=== Final Summary ===")
for name, r in results.items():
    if "error" in r:
        status = "ERROR"
    elif r.get("exit_code") == 0:
        status = "OK"
    else:
        status = f"FAIL (exit {r.get('exit_code')})"
    print(f"  {name}: {status}")
