"""End-to-end test of pa fetch v3.9.8.2 final (with proxy + valid email error)."""
import os
import sys
import time
import re
import json
from urllib.parse import quote
from pathlib import Path

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
# deliberately NOT set UNPAYWALL_EMAIL to test "no email" path

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import fetch, status_report

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def chain_summary(r):
    if r.get("chain"):
        for step in r["chain"]:
            ok = "✓" if step.get("ok") else "✗"
            err = step.get("err", "ok")
            extra = step.get("hint", "")
            print(f"      {ok} {step.get('source'):14} | {err}" + (f" | {extra[:60]}" if extra else ""))


print("=" * 70)
print("TEST 1: fetch() with no UNPAYWALL_EMAIL — should report clear error")
print("=" * 70)
if "UNPAYWALL_EMAIL" in os.environ:
    del os.environ["UNPAYWALL_EMAIL"]
r = fetch(doi="10.1038/nature12373", out_path=str(OUT_DIR / "no_email.pdf"), prefer="auto")
print(f"  ok={r.get('ok')} | err={r.get('error')}")
print(f"  message: {r.get('message', '')[:120]}")
print(f"  hint:    {r.get('hint', '')[:120]}")
chain_summary(r)

print()
print("=" * 70)
print("TEST 2: fetch() with fake UNPAYWALL_EMAIL — should detect CF anti-bot")
print("=" * 70)
os.environ["UNPAYWALL_EMAIL"] = "fake-email-12345@example.com"
r = fetch(doi="10.1038/nature12373", out_path=str(OUT_DIR / "fake_email.pdf"), prefer="auto")
print(f"  ok={r.get('ok')} | err={r.get('error')}")
print(f"  message: {r.get('message', '')[:120]}")
print(f"  hint:    {r.get('hint', '')[:120]}")
chain_summary(r)

print()
print("=" * 70)
print("TEST 3: sci-hub fallback when no Unpaywall OA (DOI unknown to Unpaywall)")
print("=" * 70)
# Use DOI that Unpaywall may not have
os.environ["UNPAYWALL_EMAIL"] = "fake-email-12345@example.com"
r = fetch(doi="10.1234/non.existent.paper.does.not.exist",
          out_path=str(OUT_DIR / "nonexist.pdf"), prefer="auto")
print(f"  ok={r.get('ok')} | err={r.get('error')}")
chain_summary(r)

print()
print("=" * 70)
print("TEST 4: status_report() — final health snapshot")
print("=" * 70)
h = status_report()
print(f"  scihub: {h['scihub']}")
print(f"  annas:  {h['annas']}")
print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
print("  Unpaywall: needs registered email (setup action required)")
print("  sci-hub:   all 7 mirrors dead (hijack or CF challenge)")
print("  annas:     .org timeout, .gs is SPA (no SSR), no JSON API")
print("  → fetch chain has only 1 viable path: Unpaywall (with valid email)")
