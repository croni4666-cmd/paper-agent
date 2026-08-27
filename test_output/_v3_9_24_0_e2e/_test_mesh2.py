"""Test PubMed MeSH queries with the CORRECT MeSH term for Wilson disease.

Per MeSH (https://meshb.nlm.nih.gov/record/ui?ui=D006527):
  Main heading: Hepatolenticular Degeneration
  Entry terms: Wilson Disease, Wilson's Disease, Copper storage disease, etc.

So the correct MeSH query is:
  "Hepatolenticular Degeneration"[MeSH Terms]
NOT "Wilson Disease"[MeSH Terms] (which is an entry term, not a main heading).
"""
import json
import urllib.request
from urllib.parse import quote

queries = [
    ('Plain "Wilson Disease"', "Wilson Disease"),
    ('"Wilson Disease"[MeSH] (entry term, may not match)', '"Wilson Disease"[MeSH Terms]'),
    ('"Hepatolenticular Degeneration"[MeSH] (CORRECT)', '"Hepatolenticular Degeneration"[MeSH Terms]'),
    ('"Hepatolenticular Degeneration"[MeSH] OR "Wilson Disease"[Title/Abstract]', '"Hepatolenticular Degeneration"[MeSH Terms] OR "Wilson Disease"[Title/Abstract]'),
    ('Just "Hepatolenticular Degeneration"', "Hepatolenticular Degeneration"),
]

for label, q in queries:
    encoded = quote(q)
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded}&retmode=json&retmax=5&tool=paper-agent&email=paper-agent@example.com"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read())
        esearchresult = body.get("esearchresult", {})
        count = esearchresult.get("count", "0")
        pmids = esearchresult.get("idlist", [])
        print(f"{label}")
        print(f"  count={count}, pmids[:3]={pmids[:3]}")

        # Fetch titles for first 3 PMIDs
        if pmids:
            pmids_str = ",".join(pmids[:3])
            esum_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmids_str}&retmode=json&tool=paper-agent&email=paper-agent@example.com"
            req2 = urllib.request.Request(esum_url)
            with urllib.request.urlopen(req2, timeout=20) as r:
                body2 = json.loads(r.read())
            result_root = body2.get("result", {})
            for uid in result_root.get("uids", [])[:3]:
                r2 = result_root.get(uid, {})
                print(f"    PMID {uid}: {r2.get('title', '?')[:80]}")
        print()
    except Exception as e:
        print(f"{label}: FAILED - {e}")
        print()
