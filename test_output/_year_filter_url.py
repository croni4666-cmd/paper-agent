"""Test esearch URL with/without date filter."""
import json
import urllib.parse
import urllib.request

q = urllib.parse.quote("diabetes")
url1 = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
         f"?db=pubmed&term={q}&retmode=json&retmax=3"
         f"&mindate=2020/01/01&maxdate=2020/12/31&datetype=pdat&tool=paper-agent")
url2 = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
         f"?db=pubmed&term={q}&retmode=json&retmax=3&tool=paper-agent")

for label, url in [("WITH pdat filter 2020", url1), ("NO filter", url2)]:
    print(f"--- {label} ---")
    print(f"URL: {url[:140]}")
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent/3.9.11.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
        cnt = d["esearchresult"]["count"]
        ids = d["esearchresult"]["idlist"][:3]
        print(f"  count: {cnt}")
        print(f"  pmids: {ids}")
        # Also show the raw web environment for filter
        if "webenv" in d["esearchresult"]:
            print(f"  webenv: {d['esearchresult']['webenv'][:50]}...")
