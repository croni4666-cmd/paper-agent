"""Fix truncated UTF-8 em-dash sequences (0xE2 0x80 without 0x94) in pa_cli/*.py.

PowerShell `-replace` on the multi-byte em-dash character left behind
truncated 2-byte sequences. Replace all (0xE2 0x80) followed by NOT
0x94 with ASCII "--" (double hyphen) so Python 3.12 can parse.
"""
import os
import re

FIXED = 0
for root, dirs, files in os.walk("pa_cli"):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        data = open(path, "rb").read()
        new = bytearray()
        i = 0
        while i < len(data):
            # Detect "0xE2 0x80 NOT 0x94" (truncated em-dash)
            if (
                i + 1 < len(data)
                and data[i] == 0xE2
                and data[i + 1] == 0x80
                and (i + 2 >= len(data) or data[i + 2] != 0x94)
            ):
                new.extend(b"--")
                i += 2
                FIXED += 1
            else:
                new.append(data[i])
                i += 1
        if bytes(new) != data:
            open(path, "wb").write(bytes(new))
            print(f"fixed: {path}")
print(f"total fixes: {FIXED}")
