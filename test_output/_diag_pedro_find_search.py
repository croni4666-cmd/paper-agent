"""Find the real PEDro search page (newsletter page is a red herring)."""
import re
import urllib.request

# Test homepage for search link
req = urllib.request.Request(
    "https://pedro.org.au/",
    headers={"User-Agent": "paper-agent/3.9.11.9"}
)
with urllib.request.urlopen(req, timeout=20) as r:
    html = r.read().decode("utf-8", errors="replace")

# Find all internal links containing 'search' or 'advanced'
links = re.findall(r'href=["\']([^"\']+)["\']', html)
search_links = [l for l in links if "search" in l.lower() or "advanced" in l.lower()]
print("Search-related links on homepage:")
for l in sorted(set(search_links))[:20]:
    print(f"  {l}")
