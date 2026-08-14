"""Test PubMed E-utilities API — works from this machine?"""
import json
import os
import urllib.parse
import urllib.request

# NCBI requires email + tool parameters per their etiquette
EMAIL = os.environ.get("NCBI_EMAIL", "paper-agent@example.com")
TOOL = "paper-agent"

# Test 1: esearch
q = urllib.parse.quote("ACE inhibitors hypertension randomized controlled trial 2024")
url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
       f"?db=pubmed&term={q}&retmode=json&retmax=5&tool={TOOL}&email={EMAIL}")
print("=" * 70)
print("Test 1: esearch")
print("=" * 70)
print(f"URL: {url[:200]}")
try:
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/3.9.11.7 ({EMAIL})"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        print(f"status: {resp.status}")
        print(f"total count: {data.get('esearchresult', {}).get('count')}")
        print(f"pmids: {data.get('esearchresult', {}).get('idlist')}")
        ids = data.get("esearchresult", {}).get("idlist", [])
        if ids:
            # Test 2: esummary
            ids_str = ",".join(ids)
            url2 = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    f"?db=pubmed&id={ids_str}&retmode=json&tool={TOOL}&email={EMAIL}")
            print()
            print("=" * 70)
            print(f"Test 2: esummary for {len(ids)} PMIDs")
            print("=" * 70)
            req2 = urllib.request.Request(url2, headers={"User-Agent": f"{TOOL}/3.9.11.7 ({EMAIL})"})
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                data2 = json.loads(resp2.read())
                result = data2.get("result", {})
                uids = result.get("uids", [])
                for uid in uids:
                    r = result.get(uid, {})
                    print(f"\n  PMID {uid}:")
                    print(f"    title:   {(r.get('title') or '')[:80]}")
                    print(f"    journal: {r.get('fulljournalname') or r.get('source')}")
                    print(f"    year:    {r.get('pubdate', '')[:4]}")
                    authors = r.get("authors", [])
                    if authors:
                        names = [a.get("name", "") for a in authors[:3]]
                        print(f"    authors: {', '.join(names)}{' et al.' if len(authors) > 3 else ''}")
                    # DOI
                    articleids = r.get("articleids", [])
                    doi = next((a.get("value") for a in articleids if a.get("idtype") == "doi"), "")
                    print(f"    doi:     {doi}")
                    # MeSH
                    mesh_list = r.get("meshlist", [])
                    if mesh_list:
                        terms = [m.get("descriptorname", "") for m in mesh_list[:5]]
                        print(f"    mesh:    {terms}")
                    # Publication type
                    pub_types = r.get("pubtype", [])
                    if pub_types:
                        print(f"    pubtype: {pub_types[:3]}")
                    # Abstract (esummary doesn't include abstract; only efetch does)
                    print(f"    has abstract: {bool(r.get('abstract') or r.get('summary'))}")
except Exception as e:
    print(f"EXC: {type(e).__name__}: {e}")
