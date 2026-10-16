from copy import deepcopy
import json

import pytest

from pa_cli.research_cache import CachedSearch


def successful():
    return {'results':[{'pmid':'1','title':'Study','abstract':'Abstract'}],
            'engine_status':{'pubmed':{'status':'ok','count':1}}}


def test_exact_repeat_reuses_success_and_isolates_return_value_mutations(tmp_path):
    calls=[]
    def search(query,**kwargs):calls.append((query,kwargs));return successful()
    cached=CachedSearch(search,tmp_path,ttl_seconds=60)
    a=cached('sleep',engine='pubmed',limit=8,pubmed_sort='relevance')
    a['results'][0]['title']='Caller changed it'
    b=cached('sleep',engine='pubmed',limit=8,pubmed_sort='relevance')
    assert len(calls)==1
    assert b['results'][0]['title']=='Study'
    assert a['cache']['state']=='miss' and b['cache']['state']=='hit'
    assert b['cache']['retrieved_at']<=b['cache']['read_at']


def test_depth_sort_and_query_are_isolated_but_transport_timeout_is_not(tmp_path):
    calls=[]
    def search(*args,**kwargs):calls.append(1);return successful()
    cached=CachedSearch(search,tmp_path)
    for query,limit,sort in [('sleep',8,'relevance'),('sleep',32,'relevance'),
                              ('sleep',8,'pub_date'),('insomnia',8,'relevance')]:
        cached(query,engine='pubmed',limit=limit,pubmed_sort=sort,engine_timeout=45)
    cached('sleep',engine='pubmed',limit=8,pubmed_sort='relevance',engine_timeout=20)
    assert len(calls)==4


def test_failure_is_never_cached_and_malformed_success_is_not_cacheable(tmp_path):
    for result in [{'results':[],'engine_status':{'pubmed':{'status':'error'}}},
                   {'results':'bad','engine_status':{'pubmed':{'status':'ok'}}}]:
        calls=[]
        def search(*args,**kwargs):calls.append(1);return deepcopy(result)
        cached=CachedSearch(search,tmp_path)
        cached('sleep',engine='pubmed');cached('sleep',engine='pubmed')
        assert len(calls)==2
    assert list(tmp_path.glob('*.json'))==[]


def test_expired_refresh_and_corrupt_entries_fall_back_to_live_search(tmp_path):
    now=[1000.0];calls=[]
    def search(*args,**kwargs):calls.append(1);return successful()
    cached=CachedSearch(search,tmp_path,ttl_seconds=10,clock=lambda:now[0])
    cached('sleep',engine='pubmed')
    now[0]=1011
    assert cached('sleep',engine='pubmed')['cache']['state']=='miss'
    refresh=CachedSearch(search,tmp_path,refresh=True,clock=lambda:now[0])
    assert refresh('sleep',engine='pubmed')['cache']['state']=='refresh'
    for path in tmp_path.glob('*.json'):path.write_text('{bad',encoding='utf-8')
    cached('sleep',engine='pubmed')
    assert len(calls)==4


def test_json_valid_but_schema_corrupt_cache_does_not_block_live_fallback(tmp_path):
    calls=[]
    def search(*a,**k):calls.append(1);return successful()
    cached=CachedSearch(search,tmp_path)
    cached('sleep',engine='pubmed')
    path=next(tmp_path.glob('*.json'))
    entry=json.loads(path.read_text(encoding='utf-8'))
    entry['response']['engine_status']=[]
    path.write_text(json.dumps(entry),encoding='utf-8')
    result=cached('sleep',engine='pubmed')
    assert len(calls)==2 and result['results'][0]['pmid']=='1'
    assert result['cache']['state']=='miss'


def test_cache_write_failure_keeps_live_result(tmp_path):
    blocker=tmp_path/'file';blocker.write_text('cannot be directory')
    cached=CachedSearch(lambda *a,**k:successful(),blocker)
    result=cached('sleep',engine='pubmed')
    assert result['results'][0]['pmid']=='1'
    assert result['cache']['state']=='write_error'


def test_research_cache_reuses_exact_run_and_exposes_live_search_call_count(tmp_path):
    from pa_cli.research_search import run_research
    spec={'original_question':'失眠','groups':[{'id':'outcome','terms':['sleep']} ]}
    calls=[]
    def search(*a,**k):
        calls.append(1)
        return {'results':[{'pmid':'1','title':'Sleep','abstract':'Sleep study'}],
                'engine_status':{'pubmed':{'status':'ok'}}}
    first=run_research(spec,searcher=search,query_cache=tmp_path,max_sources=0)
    second=run_research(spec,searcher=search,query_cache=tmp_path,max_sources=0)
    assert len(calls)==1
    assert first['retrieval_work']=={'live_search_calls':1,'cache_hits':0}
    assert second['retrieval_work']=={'live_search_calls':0,'cache_hits':1}
    assert second['query_runs'][0]['cache']['state']=='hit'
    assert second['research_verified'] is False


@pytest.mark.parametrize('ttl',[0,-1,float('inf'),float('nan')])
def test_invalid_ttl_fails_visibly(tmp_path,ttl):
    with pytest.raises(ValueError):CachedSearch(lambda *a,**k:successful(),tmp_path,ttl_seconds=ttl)
