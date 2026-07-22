"""Strip UTF-8 BOM from labels_clean.json (pre-existing file from v3.9.0 era)."""
import os
from pathlib import Path

p = Path("bench/v01/labels_clean.json")
raw = p.read_bytes()
if raw[:3] == b"\xef\xbb\xbf":
    new = raw[3:]
    p.write_bytes(new)
    print(f"Stripped BOM from {p}: {len(raw)} -> {len(new)} bytes")
else:
    print(f"No BOM in {p} (first 3 bytes: {raw[:3].hex()})")
