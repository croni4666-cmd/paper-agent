"""Test: does PubMed MeSH field syntax work end-to-end via pa search?"""
import json
import sys
from urllib.parse import quote

# 1. Simulate the URL that pa search would build
query = '"Wilson Disease"[MeSH Terms] OR "hepatolenticular degeneration"[Title/Abstract]'
encoded = quote(query)
url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded}&retmode=json&retmax=5&tool=paper-agent&email=paper-agent@example.com"
print(f"Query: {query}")
print(f"Encoded URL: {url[:200]}...")
print()

# 2. Test ESearch directly with the MeSH query
import urllib.request
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    esearchresult = body.get("esearchresult", {})
    pmids = esearchresult.get("idlist", [])
    count = esearchresult.get("count", "0")
    print(f"ESearch with MeSH: count={count}, pmids[:5]={pmids[:5]}")
    print()
except Exception as e:
    print(f"ESearch failed: {e}")
    print()

# 3. Compare with plain query
plain = "Wilson Disease"
plain_encoded = quote(plain)
plain_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={plain_encoded}&retmode=json&retmax=5&tool=paper-agent&email=paper-agent@example.com"
try:
    req = urllib.request.Request(plain_url)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    esearchresult = body.get("esearchresult", {})
    pmids = esearchresult.get("idlist", [])
    count = esearchresult.get("count", "0")
    print(f"ESearch with 'Wilson Disease' plain: count={count}, pmids[:5]={pmids[:5]}")
except Exception as e:
    print(f"Plain ESearch failed: {e}")
print()

# 4. Test with just "Wilson" (the user said this returns author-related results)
q3 = "Wilson"
q3_encoded = quote(q3)
q3_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={q3_encoded}&retmode=json&retmax=5&tool=paper-agent&email=paper-agent@example.com"
try:
    req = urllib.request.Request(q3_url)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    esearchresult = body.get("esearchresult", {})
    pmids = esearchresult.get("idlist", [])
    count = esearchresult.get("count", "0")
    print(f"ESearch with 'Wilson' alone: count={count}, pmids[:5]={pmids[:5]}")
except Exception as e:
    print(f"Wilson alone ESearch failed: {e}")
print()

# 5. Fetch one esummary for the MeSH results to check title relevance
if pmids:
    pmids_str = ",".join(pmids[:3])
    esummary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmids_str}&retmode=json&tool=paper-agent&email=paper-agent@example.com"
    try:
        req = urllib.request.Request(esummary_url)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
        result_root = body.get("result", {})
        print("First 3 MeSH result titles:")
        for uid in result_root.get("uids", [])[:3]:
            r = result_root.get(uid, {})
            print(f"  PMID {uid}: {r.get('title', '?')[:80]}")
    except Exception as e:
        print(f"eSummary failed: {e}")
