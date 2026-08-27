"""Fix mojibake in skill files."""
import sys
from pathlib import Path

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")

# Files to fix
files = [
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "SKILL.md",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "search.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "fetch.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "fetch_batch.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "review.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "citations.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "keys.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "cache.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "version.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "_pa_root.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "bootstrap.py",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "references" / "channels.md",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "references" / "engines.md",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "references" / "cli-cheatsheet.md",
    PA_ROOT / ".agents" / "skills" / "paper-agent" / "agents" / "openai.yaml",
]

# Common mojibake patterns (UTF-8 bytes that got interpreted as cp1252 then re-saved)
MOJIBAKE_MAP = {
    # Em-dash "—" (U+2014) as UTF-8 E2 80 94 → cp1252 interprets as "鈥?" (E9 88 A5 3F)
    b'\xe9\x88\xa5\x3f': '—',  # —
    b'\xe9\x88\xa5': '—',     # Sometimes without the ?
    # En-dash "–" (U+2013) as UTF-8 E2 80 93 → cp1252 "鈥?" (E9 88 A5 3F - same?)
    # Actually let me check the actual byte sequences
}

# More comprehensive: walk through and find any non-printable high-Unicode
# bytes that look like mojibake
import re

# Just scan for the known mojibake byte sequence
TARGET_MOJIBAKE = b'\xe9\x88\xa5'  # "鈥" — common mojibake for "—" and similar
TARGET_MOJIBAKE_Q = b'\xe9\x88\xa5\x3f'  # "鈥?" with trailing ?
TARGET_MOJIBAKE_NOSPACE = b'\xe9\x88'  # partial

# Also some files may have UTF-8 BOM that's not stripped
BOM = b'\xef\xbb\xbf'

for f in files:
    if not f.exists():
        print(f"  {f.name}: NOT FOUND")
        continue
    data = f.read_bytes()
    orig = data
    changes = []

    # Strip BOM if present
    if data.startswith(BOM):
        data = data[3:]
        changes.append("BOM")

    # Replace 鈥? → —
    if TARGET_MOJIBAKE_Q in data:
        count = data.count(TARGET_MOJIBAKE_Q)
        data = data.replace(TARGET_MOJIBAKE_Q, '—'.encode('utf-8'))
        changes.append(f"鈥?({count}x)→—")

    # Replace 鈥 alone → —
    if TARGET_MOJIBAKE in data:
        count = data.count(TARGET_MOJIBAKE)
        data = data.replace(TARGET_MOJIBAKE, '—'.encode('utf-8'))
        changes.append(f"鈥({count}x)→—")

    if data != orig:
        f.write_bytes(data)
        print(f"  {f.name}: fixed ({', '.join(changes)})")
    else:
        print(f"  {f.name}: clean")
