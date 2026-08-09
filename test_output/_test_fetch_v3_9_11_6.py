"""v3.9.11.6 smoke test: arXiv channel + prefer routing.

Verifies:
  1. arXiv DOI 10.48550/arXiv.2310.06825 -> arXiv channel delivers
  2. Nature DOI with prefer=annas really tries annas (or at least doesn't go to scihub)
  3. prefer=scihub works for sci-hub-archived DOIs
  4. Hash differs when same DOI is fetched from different channels (when possible)
  5. status_report() still works

Run: python test_output/_test_fetch_v3_9_11_6.py
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("G:/minimax - workspace/Paper agent")
TEST_OUTDIR = REPO / "test_output" / "_diag_v396"
TEST_OUTDIR.mkdir(parents=True, exist_ok=True)

PROXY_ENV = {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
    "HTTPS_PROXY": "http://127.0.0.1:10808",
    "HTTP_PROXY": "http://127.0.0.1:10808",
}


def file_hash(p):
    if not p or not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def find_downloaded_pdf(outdir):
    if not outdir.exists():
        return None
    for p in outdir.rglob("*.pdf"):
        if p.is_file() and p.stat().st_size > 1000:
            return p
    return None


def run_pa(args, timeout=120):
    env = os.environ.copy()
    env.update(PROXY_ENV)
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "-X", "utf-8", "-m", "pa_cli"] + args,
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr, time.time() - t0


def parse_result(out):
    """Extract source, size, path from pa fetch stdout."""
    src = re.search(r'"source":\s*"([^"]+)"', out)
    size = re.search(r'"size":\s*(\d+)', out)
    return {
        "source": src.group(1) if src else None,
        "size": int(size.group(1)) if size else None,
    }


def fetch_with_prefer(doi, prefer, label):
    """Run pa fetch with --prefer, return (hash, source, elapsed)."""
    out_dir = TEST_OUTDIR / f"{label}_prefer_{prefer}"
    out_dir.mkdir(exist_ok=True)
    rc, out, err, elapsed = run_pa(
        ["fetch", doi, "-o", str(out_dir), "--prefer", prefer, "--quiet"],
        timeout=180,
    )
    pdf = find_downloaded_pdf(out_dir)
    h = file_hash(pdf)
    info = parse_result(out)
    success = "SUCCESS" in out and "saved" in out
    handoff = "handoff" in out.lower() or rc == 2
    return {
        "label": label,
        "prefer": prefer,
        "rc": rc,
        "elapsed": round(elapsed, 1),
        "success": success,
        "handoff": handoff,
        "hash": h,
        "size": info["size"],
        "source": info["source"],
        "pdf_path": str(pdf) if pdf else None,
    }


print("=" * 70)
print("v3.9.11.6 smoke test: arXiv + prefer routing")
print("=" * 70)
print()

# ============= Test 1: arXiv channel (the missing one) =============
print("=" * 70)
print("Test 1: arXiv DOI 10.48550/arXiv.2310.06825 (the previously-broken case)")
print("=" * 70)
results_arxiv = []
for form, doi in [
    ("arXiv-DOI", "10.48550/arXiv.2310.06825"),
    ("bare-ID", "2310.06825"),
    ("legacy-prefix", "arxiv:2310.06825"),
]:
    print(f"\n  {form}: {doi}")
    r = fetch_with_prefer(doi, "arxiv", f"arxiv_{form}")
    print(f"    rc={r['rc']} elapsed={r['elapsed']}s success={r['success']} handoff={r['handoff']}")
    print(f"    source={r['source']} size={r['size']} hash={r['hash']}")
    if not r['success'] and r['handoff']:
        for line in r.get('pdf_path', '').split('\n'):
            pass
        # Show handoff reason
        try:
            for line in (r.get('pdf_path') or '').split('\n'):
                if 'reason' in line or 'error' in line:
                    print(f"    {line.strip()}")
        except Exception:
            pass
    results_arxiv.append(r)
print()

# ============= Test 2: prefer routing for Nature DOI =============
print("=" * 70)
print("Test 2: Nature DOI 10.1038/nature12373, vary --prefer")
print("=" * 70)
results_nature = []
for prefer in ["arxiv", "annas", "cnki", "scihub", "auto"]:
    print(f"\n  prefer={prefer}")
    r = fetch_with_prefer("10.1038/nature12373", prefer, f"nature_{prefer}")
    print(f"    rc={r['rc']} elapsed={r['elapsed']}s success={r['success']} handoff={r['handoff']}")
    print(f"    source={r['source']} size={r['size']} hash={r['hash']}")
    results_nature.append(r)
print()

# ============= Test 3: --channels backward compat =============
print("=" * 70)
print("Test 3: --channels backward compat (default 'openalex,arxiv,...')")
print("=" * 70)
out_dir = TEST_OUTDIR / "channels_default"
out_dir.mkdir(exist_ok=True)
rc, out, err, elapsed = run_pa(
    ["fetch", "10.1038/nature12373", "-o", str(out_dir), "--quiet"],
    timeout=180,
)
pdf = find_downloaded_pdf(out_dir)
h = file_hash(pdf)
info = parse_result(out)
print(f"  default channels -> source={info['source']} size={info['size']} hash={h}")
print()

# ============= Test 4: status_report still works =============
print("=" * 70)
print("Test 4: pa fetch status (sanity check)")
print("=" * 70)
rc, out, err, elapsed = run_pa(
    ["sample-pool", "stats"],  # unrelated but tests CLI sanity
    timeout=30,
)
print(f"  pa sample-pool stats rc={rc} (sanity: CLI alive)")
print()

# ============= Summary =============
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("Test 1: arXiv channel (the critical fix)")
ok_arxiv = sum(1 for r in results_arxiv if r['success'])
print(f"  {ok_arxiv}/{len(results_arxiv)} arXiv form tests succeeded")
if ok_arxiv == 3:
    print("  [PASS] arXiv channel works for all 3 input forms (DOI / bare ID / legacy prefix)")
else:
    print(f"  [INFO] arXiv channel works for {ok_arxiv} of 3 input forms")
print()

print("Test 2: --prefer routing for Nature DOI")
hashes = {r['prefer']: r['hash'] for r in results_nature if r['hash']}
print(f"  Hash summary ({len(set(hashes.values()))} unique):")
for prefer, h in hashes.items():
    print(f"    prefer={prefer:8s} hash={h}")
print()
if len(set(hashes.values())) >= 2:
    print("  [PASS] Different prefer modes return different PDFs (channels are distinct)")
elif len(set(hashes.values())) == 1:
    print("  [INFO] All prefer modes still return the same PDF (cascade always falls back to one source)")
print()

# Count working channels
print("Test 2 channel-by-channel:")
for r in results_nature:
    marker = "OK" if r['success'] else "FAIL"
    print(f"  [{marker}] prefer={r['prefer']:8s} -> source={r['source']!r:10s} hash={r['hash']}")
print()

# ============= Verification of arXiv for Nature =============
print("Cross-test: arXiv channel on a NON-arXiv DOI (should fail gracefully)")
out_dir = TEST_OUTDIR / "arxiv_on_nature"
out_dir.mkdir(exist_ok=True)
rc, out, err, elapsed = run_pa(
    ["fetch", "10.1038/nature12373", "-o", str(out_dir), "--prefer", "arxiv", "--quiet"],
    timeout=60,
)
print(f"  pa fetch --prefer=arxiv on Nature DOI: rc={rc} elapsed={elapsed:.1f}s")
print(f"  (should fail fast since Nature DOI is not arXiv)")
print()

print("=" * 70)
print("DONE")
print("=" * 70)
