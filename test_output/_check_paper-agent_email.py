"""Check if paper-agent@mavis.local is actually registered with Unpaywall."""
import os
import sys
import json
from urllib.parse import quote

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import _http_get_bytes

# The default email that paper-agent used
for email in ["paper-agent@mavis.local", "dengn@mavis.local"]:
    print(f"\n--- email={email} ---")
    s, body = _http_get_bytes(
        f"https://api.unpaywall.org/v2/10.1038/nature12373?email={quote(email, safe='@')}",
        timeout=20,
    )
    print(f"  HTTP {s}, body={len(body)}B")
    if s == 200:
        head = body[:16].hex()
        print(f"  first 16 bytes hex: {head}")
        # Try JSON
        try:
            d = json.loads(body)
            print(f"  ✓ JSON OK | title={d.get('title','')[:50]!r}")
            print(f"  best_oa_url={(d.get('best_oa_location') or {}).get('url','')[:80]}")
        except Exception as e:
            print(f"  JSON fail: {e}")
            # Try decompress
            import gzip, zlib
            for label, fn in [("gzip", lambda: gzip.decompress(body)),
                              ("zlib", lambda: zlib.decompress(body))]:
                try:
                    decoded = fn()
                    print(f"  {label} decode OK → {len(decoded)}B")
                    try:
                        d = json.loads(decoded)
                        print(f"  ✓ JSON after {label} | title={d.get('title','')[:50]!r}")
                    except Exception as je:
                        print(f"  JSON fail after {label}: {je}")
                    break
                except Exception as de:
                    pass
    else:
        try:
            d = json.loads(body)
            print(f"  JSON err: {d.get('message','')[:200]}")
        except Exception:
            print(f"  raw: {body[:200]!r}")
