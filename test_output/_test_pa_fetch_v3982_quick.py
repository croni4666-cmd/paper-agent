"""Quick v3.9.8.2 sanity test (no slow fallbacks)."""
import os
import sys

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import fetch, status_report, _http_get_bytes

print("=" * 60)
print("SANITY 1: fetch() with no UNPAYWALL_EMAIL")
print("=" * 60)
if "UNPAYWALL_EMAIL" in os.environ:
    del os.environ["UNPAYWALL_EMAIL"]
r = fetch(doi="10.1038/nature12373", prefer="unpaywall_only")
print(f"  ok={r.get('ok')} | err={r.get('error')}")
print(f"  hint: {r.get('hint','')[:100]}")

print()
print("=" * 60)
print("SANITY 2: fetch() with fake email")
print("=" * 60)
os.environ["UNPAYWALL_EMAIL"] = "fake@example.com"
r = fetch(doi="10.1038/nature12373", prefer="unpaywall_only")
print(f"  ok={r.get('ok')} | err={r.get('error')}")
print(f"  message: {r.get('message','')[:100]}")
print(f"  hint: {r.get('hint','')[:100]}")

print()
print("=" * 60)
print("SANITY 3: status_report (final)")
print("=" * 60)
h = status_report()
print(f"  scihub: {h['scihub']}")
print(f"  annas:  {h['annas']}")
