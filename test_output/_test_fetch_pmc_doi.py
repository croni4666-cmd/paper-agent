"""End-to-end test of fetch_pmc_doi with jats_to_pdf fallback."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.fetch import fetch_pmc_doi

doi = "10.3389/fendo.2026.1798827"
out_dir = ROOT / "test_output" / "fetch_pmc_doi_v2"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = str(out_dir / f"{doi.replace('/', '_').replace('.', '_')}.pdf")

print(f"[fetch_pmc_doi] doi={doi}")
print(f"               out={out_path}")
t0 = time.time()
r = fetch_pmc_doi(doi, out_path=out_path)
elapsed = time.time() - t0

print(f"\n=== RESULT ({elapsed:.1f}s) ===")
for k, v in r.items():
    if isinstance(v, str) and len(v) > 100:
        v = v[:97] + "..."
    print(f"  {k}: {v}")

# Verify
if r.get("pdf_path"):
    p = Path(r["pdf_path"])
    print(f"\n[verify] PDF at {p}")
    print(f"  exists: {p.exists()}, size: {p.stat().st_size:,} bytes")
    data = p.read_bytes()
    print(f"  magic: {data[:8]}")
    assert data.startswith(b"%PDF-"), "not a valid PDF"
    print("  [PASS] valid PDF")
else:
    print(f"\n[FAIL] no pdf_path in result. error={r.get('pdf_error_europe')} / {r.get('pdf_error_jats')}")
