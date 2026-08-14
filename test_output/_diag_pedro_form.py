"""Inspect PEDro form HTML to find action URL + input names."""
import re
import urllib.request

req = urllib.request.Request(
    "https://pedro.org.au/english/search/",
    headers={"User-Agent": "paper-agent/3.9.11.9"}
)
with urllib.request.urlopen(req, timeout=20) as r:
    html = r.read().decode("utf-8", errors="replace")

# Find form actions
actions = re.findall(r'<form[^>]+action=["\']([^"\']+)["\']', html)
inputs = re.findall(r'<input[^>]+name=["\']([^"\']+)["\']', html)
print("form actions found:", actions[:5])
print("input names found (first 20):", inputs[:20])

# Also check if there's a JS-based search via /api or ajax
if "ajax" in html.lower():
    print("mentions 'ajax' in HTML")
if "api" in html.lower():
    print("mentions 'api' in HTML")
