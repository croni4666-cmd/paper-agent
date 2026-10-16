from unittest.mock import patch

from pa_cli import search
from pa_cli.europepmc import _text
from pa_cli.engine_probe import probe_search_engines
from test_europepmc_integration import row, payload
import hashlib
import json
from pathlib import Path
import pytest


def test_abstract_keeps_literal_and_encoded_scientific_comparisons():
    text = '<p>p < 0.05 and score > 3; CI &lt; 2.0.</p>'
    assert _text(text) == 'p < 0.05 and score > 3; CI < 2.0.'


def test_shared_record_remains_visible_under_each_source_filter():
    with patch.object(search, 'search_pubmed', return_value=[{
            'pmid':'123','title':'Menopause sleep','source':'pubmed'}]), \
            patch.object(search,'http_get_json',return_value=(200,payload([row()]))):
        r=search.run_search('sleep',engine='pubmed,europepmc',source_filter=['europepmc'])
    assert len(r['results'])==1 and r['results'][0]['found_by']==['pubmed','europepmc']


def test_identifier_only_record_gains_title_year_and_upstream_provenance():
    with patch.object(search,'search_pubmed',return_value=[{'pmid':'123','title':'','year':None,'source':'pubmed'}]), \
            patch.object(search,'http_get_json',return_value=(200,payload([row()]))):
        p=search.run_search('sleep',engine='pubmed,europepmc')['results'][0]
    assert p['title']=='Menopause sleep therapy' and p['year']==2025
    assert p['europepmc_id']=='123' and p['upstream_source']=='MED'


def test_two_papers_from_same_trial_remain_two_papers():
    papers=[{'doi':'10.1000/main','nct_id':'NCT00000001','title':'Primary paper'},
            {'doi':'10.1000/followup','nct_id':'NCT00000001','title':'Followup paper'}]
    with patch.object(search,'search_pubmed',return_value=papers):
        r=search.run_search('sleep',engine='pubmed')
    assert len(r['results'])==2


def test_registry_record_not_collapsed_into_paper_referencing_it():
    with patch.object(search,'search_pubmed',return_value=[{
            'doi':'10.1000/main','nct_id':'NCT00000001','title':'Paper','source':'pubmed'}]), \
            patch.object(search,'search_clinicaltrials',return_value=[{
            'nct_id':'NCT00000001','title':'Registry','source':'clinicaltrials'}]):
        r=search.run_search('sleep',engine='pubmed,clinicaltrials')
    assert len(r['results'])==2


def test_registry_duplicates_still_merge():
    records=[{'nct_id':'NCT00000001','title':'Registry','source':'clinicaltrials'},
             {'nct_id':'NCT00000001','title':'Updated registry','source':'clinicaltrials'}]
    with patch.object(search,'search_clinicaltrials',return_value=records):
        assert len(search.run_search('sleep',engine='clinicaltrials')['results'])==1


def test_health_probe_preserves_partial_results_status():
    r=probe_search_engines('sleep',engines=('europepmc',),runner=lambda *a,**kw: {
        'by_engine':{'europepmc':1},'engine_status':{'europepmc':{'status':'partial','count':1}}})
    assert r['engines'][0]['status']=='partial' and r['engines'][0]['result_count']==1


def test_corrupted_old_version_cache_cannot_resurrect_bad_abstract(tmp_path):
    from pa_cli.research_cache import CachedSearch
    request={'protocol':'pubmed-esearch-order-v2-exact-depth-1','query':'sleep',
             'options':{'engine':'europepmc'}}
    key=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    old={'results':[{'pmid':'123','abstract':'p 3'}],
         'engine_status':{'europepmc':{'status':'ok','count':1}}}
    (tmp_path/(key+'.json')).write_text(json.dumps({'request':request,'retrieved_at':100,'response':old}))
    fresh={'results':[{'pmid':'123','abstract':'p < 0.05 and score > 3'}],
           'engine_status':{'europepmc':{'status':'ok','count':1}}}
    calls=[]
    def runner(*a,**kw):calls.append(1);return fresh
    cache=CachedSearch(runner,tmp_path,clock=lambda:101)
    r=cache('sleep',engine='europepmc')
    assert calls==[1] and r['results'][0]['abstract']==fresh['results'][0]['abstract']
    assert (tmp_path/(key+'.json')).exists()


@pytest.mark.parametrize('case',json.loads((Path(__file__).parent/'fixtures/europepmc_comparison_abstracts.json').read_text(encoding='utf-8')),
                         ids=lambda r:r['pmid'])
def test_exported_comparison_abstracts_keep_all_expected_text(case):
    assert _text(case['raw'])==case['expected']
