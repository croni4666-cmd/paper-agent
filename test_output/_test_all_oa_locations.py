"""Try ALL oa_locations for ColabFold — find which one has real PDF."""
import os
import sys
import json

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ.setdefault("UNPAYWALL_EMAIL", "developers@unpaywall.org")
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import _http_get_bytes
from urllib.parse import quote

doi = "10.1038/s41592-022-01488-1"
url = f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}?email=developers@unpaywall.org"
s, body = _http_get_bytes(url, timeout=30)
data = json.loads(body)

print("Trying ALL oa_locations for ColabFold (DOI 10.1038/s41592-022-01488-1):")
print("=" * 70)
for i, loc in enumerate(data.get("oa_locations", [])):
    pdf_candidate = loc.get("url_for_pdf") or loc.get("url")
    print(f"\n[Location {i+1}]")
    print(f"  url:         {loc.get('url','')[:90]}")
    print(f"  url_for_pdf: {loc.get('url_for_pdf')}")
    print(f"  host_type:   {loc.get('host_type')}")
    print(f"  evidence:    {loc.get('evidence')}")
    print(f"  is_best:     {loc.get('is_best')}")
    if not pdf_candidate:
        print("  no url to try")
        continue
    s2, b2 = _http_get_bytes(pdf_candidate, timeout=60)
    is_pdf = b2[:4] == b"%PDF"
    head = b2[:200].decode("utf-8", errors="replace").replace("\n", " ")
    mark = "✓ PDF" if is_pdf else f"✗ {head[:80]}"
    print(f"  → HTTP {s2} | {len(b2):,}B | {mark}")
