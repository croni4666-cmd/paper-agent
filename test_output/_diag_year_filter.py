"""Diagnose the year filter issue: does PubMed API return wrong-year papers??"""
import urllib.request as ur
import json
import os

# Fetch esummary for the 5 PMIDs returned with 2020/01/01-2020/12/31 pdat filter
pmids = ['33119245', '38046874', '36969130', '36969114', '36753223']
ids_str = ",".join(pmids)
url = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    f"?db=pubmed&id={ids_str}&retmode=json&tool=paper-agent&email=paper-agent@example.com"
)
req = ur.Request(url, headers={"User-Agent": "diag/1.0"})
with ur.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
print("Diagnostic: dates for PMIDs returned by diabetes+2020/01/01-2020/12/31[pdat] search")
print("=" * 78)
for p in pmids:
    rec = d["result"].get(p, {})
    print(f"PMID {p}:")
    print(f"  pubdate:     {rec.get('pubdate')!r}")
    print(f"  epubdate:    {rec.get('epubdate')!r}")
    print(f"  sortpubdate: {rec.get('sortpubdate')!r}")
    print(f"  title:       {rec.get('title', '')[:70]!r}")
    print()
