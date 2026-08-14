"""Verify ClinicalTrials.gov v2 API."""
import json
import os
import urllib.parse
import urllib.request

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"


def fetch(url, accept="application/json"):
    req = urllib.request.Request(
        url, headers={"User-Agent": "paper-agent/3.9.12.0", "Accept": accept}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


# Test 1: simple search
q = urllib.parse.quote("cervical muscle")
url1 = f"https://clinicaltrials.gov/api/v2/studies?query.term={q}&format=json&pageSize=5"
print(f"--- Test 1: simple search ---")
print(f"URL: {url1[:140]}")
status, body = fetch(url1)
data = json.loads(body)
print(f"status: {status}")
print(f"top-level keys: {list(data.keys())}")
print(f"totalCount: {data.get('totalCount')}")
studies = data.get("studies", [])
print(f"returned {len(studies)} studies")
for s in studies[:3]:
    proto = s.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    print(f"  NCT: {ident.get('nctId')}  status: {status_mod.get('overallStatus')}")
    print(f"    title: {(ident.get('briefTitle') or '')[:80]}")

# Test 2: get a single study by NCT ID
print()
print("--- Test 2: single study detail ---")
nct = studies[0]["protocolSection"]["identificationModule"]["nctId"] if studies else "NCT04372602"
url2 = f"https://clinicaltrials.gov/api/v2/studies/{nct}?format=json"
status, body = fetch(url2)
detail = json.loads(body)
proto = detail.get("protocolSection", {})
print(f"NCT: {proto['identificationModule']['nctId']}")
print(f"  title: {proto['identificationModule']['briefTitle'][:80]}")
print(f"  status: {proto['statusModule']['overallStatus']}")
print(f"  phase: {proto.get('designModule', {}).get('phases')}")
print(f"  enrollment: {proto.get('designModule', {}).get('enrollmentInfo', {}).get('count')}")
cond_mod = proto.get('conditionsModule', {})
conditions = cond_mod.get('conditions', [])
if conditions and isinstance(conditions[0], dict):
    cond_names = [c.get('name', '?') for c in conditions][:5]
else:
    cond_names = conditions[:5]
print(f"  conditions: {cond_names}")
print(f"  interventions: {[i['name'] for i in proto.get('armsInterventionsModule', {}).get('interventions', [])][:5]}")
print(f"  has DOI/PubMed: {bool(proto.get('referencesModule', {}).get('references'))}")
refs = proto.get('referencesModule', {}).get('references', [])
for r in refs[:2]:
    print(f"    ref: {r.get('citation')[:100] if r.get('citation') else '?'}")
