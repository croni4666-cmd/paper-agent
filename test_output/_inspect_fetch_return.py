"""Inspect fetch() return shape — what does it actually return for arxiv DOI?"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pa_cli.fetch import fetch  # noqa: E402

print("=== Test: 10.48550/arXiv.2310.06825 --prefer auto (direct call) ===")
r = fetch("10.48550/arXiv.2310.06825", prefer="auto")
print("type:", type(r).__name__)
print("repr:", repr(r)[:500])
print("keys:", list(r.keys()) if isinstance(r, dict) else "(not dict)")
if isinstance(r, dict):
    for k, v in r.items():
        if isinstance(v, str) and len(v) > 80:
            v = v[:80] + "..."
        print(f"  {k}: {v!r}")
