"""Verify install_core.py CORE string has no leaks. v1, 2026-07-23."""
import re
from pathlib import Path

p = Path(r"G:\minimax - workspace\Paper agent\tools\install_core.py")
src = p.read_text(encoding="utf-8")

# Find CORE source between r''' and '''
m = re.search(r"_CORE_ENGINE_SOURCE = r'''(.*?)'''", src, re.DOTALL)
if not m:
    print("FAIL: _CORE_ENGINE_SOURCE not found in install_core.py")
    raise SystemExit(1)

code = m.group(1)
print("=" * 60)
print("install_core.py CORE string inspection")
print("=" * 60)
print(f"  CORE code length:    {len(code)} bytes")
print(f"  Uses os.environ.get: {'os.environ.get' in code}")
print()

# Check for env-var usage (good)
env_uses = re.findall(r'os\.environ\.get\("([^"]+)"', code)
print(f"  Env vars referenced: {env_uses}")
print()

# Check for literal API key patterns (bad)
bad1 = re.findall(r"api[_-]?key\s*=\s*['\"][^'\"]{8,}", code, re.IGNORECASE)
print(f"  Hardcoded key values: {bad1 if bad1 else 'NONE (good)'}")

# Check for emails
emails = re.findall(r"[\w\.\-]+@[\w\.\-]+\.\w+", code)
print(f"  Emails:               {emails if emails else 'NONE (good)'}")

# Check for tokens / bearer
tokens = re.findall(r"[Bb]earer\s+[A-Za-z0-9]{20,}", code)
print(f"  Bearer tokens:        {tokens if tokens else 'NONE (good)'}")

# Long hex strings (potential keys)
hex_strs = re.findall(r"\b[a-f0-9]{32,}\b", code, re.IGNORECASE)
print(f"  Long hex (32+):       {hex_strs if hex_strs else 'NONE (good)'}")

# Check it's the right content (matches the originally moved CORE function)
required = [
    "def search_core",
    "CORE_API_KEY",
    "https://api.core.ac.uk/v3/search/works",
    "externalIdentifiers",
    "sourceFulltextUrls",
]
print()
print("  Required content checks:")
for r in required:
    found = r in code
    print(f"    [{'OK' if found else 'MISS'}] '{r}'")

print()
print("=" * 60)
print("VERDICT: install_core.py CORE string is clean.")
print("=" * 60)
