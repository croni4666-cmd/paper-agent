"""Direct test of fetch_unpaywall_doi for v3.9.8.2 email validation."""
import os
import sys

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import fetch_unpaywall_doi

print("=" * 60)
print("TEST 1: no UNPAYWALL_EMAIL → 'unpaywall_no_email' error")
print("=" * 60)
if "UNPAYWALL_EMAIL" in os.environ:
    del os.environ["UNPAYWALL_EMAIL"]
r = fetch_unpaywall_doi("10.1038/nature12373")
print(f"  err={r.get('error')}")
print(f"  message: {r.get('message','')[:80]}")
print(f"  hint:    {r.get('hint','')[:120]}")

print()
print("=" * 60)
print("TEST 2: fake UNPAYWALL_EMAIL → 'unpaywall_email_invalid' (CF anti-bot detected)")
print("=" * 60)
os.environ["UNPAYWALL_EMAIL"] = "fake-email-12345@example.com"
r = fetch_unpaywall_doi("10.1038/nature12373")
print(f"  err={r.get('error')}")
print(f"  message: {r.get('message','')[:120]}")
print(f"  hint:    {r.get('hint','')[:120]}")
