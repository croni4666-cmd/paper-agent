"""Verify: what date does PMID 33119245 have in PubMed's [Date - Publication] field?"""
import urllib.request as ur
import json

# Test 1: query for the specific PMID with date filter
url1 = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=33119245[PMID]&retmode=json&mindate=2020/01/01"
    "&maxdate=2020/12/31&datetype=pdat&tool=paper-agent&email=p@example.com"
)
req = ur.Request(url1, headers={"User-Agent": "diag/1.0"})
with ur.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
print("PMID 33119245 + pdat=2020:")
print("  count:", d["esearchresult"].get("count"))
print("  pmids:", d["esearchresult"].get("idlist"))
print()

# Test 2: same PMID with no date filter
url2 = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=33119245[PMID]&retmode=json&tool=paper-agent&email=p@example.com"
)
req = ur.Request(url2, headers={"User-Agent": "diag/1.0"})
with ur.urlopen(req, timeout=30) as r:
    d2 = json.loads(r.read())
print("PMID 33119245 no date filter:")
print("  count:", d2["esearchresult"].get("count"))
print()

# Test 3: search what the [Date - Publication] for 33119245 actually is
# Use esearch field qualifier: pdat is publication date, we want to know if pdat field is 1993 or 2025
# Actually, the fact that the result returned this PMID when searching 2020/01/01-2020/12/31[pdat]
# implies that pdat IS 2020-something for this record. But pubdate says 1993.
# That suggests the NCBI server considers this pdat=2020 entry — likely because sortpubdate
# is 2025/12/04 but the original "Date - Publication" field was updated.

# Try another way: search for the pdat range 2025/12 only
url3 = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=33119245[PMID]&retmode=json&mindate=2025/12/01"
    "&maxdate=2025/12/31&datetype=pdat&tool=paper-agent&email=p@example.com"
)
req = ur.Request(url3, headers={"User-Agent": "diag/1.0"})
with ur.urlopen(req, timeout=30) as r:
    d3 = json.loads(r.read())
print("PMID 33119245 + pdat=2025/12:")
print("  count:", d3["esearchresult"].get("count"))
print("  pmids:", d3["esearchresult"].get("idlist"))
print()

# Try sortpubdate instead
url4 = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=33119245[PMID]&retmode=json&mindate=2025/12/01"
    "&maxdate=2025/12/31&datetype=sort&tool=paper-agent&email=p@example.com"
)
req = ur.Request(url4, headers={"User-Agent": "diag/1.0"})
with ur.urlopen(req, timeout=30) as r:
    d4 = json.loads(r.read())
print("PMID 33119245 + sort=2025/12:")
print("  count:", d4["esearchresult"].get("count"))
print("  pmids:", d4["esearchresult"].get("idlist"))
