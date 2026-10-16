from urllib.parse import parse_qs,urlparse
import pytest

from pa_cli.research_graph import reference_candidates,select_review_seeds


def test_review_seeds_rank_title_coverage_before_original_result_order():
    groups=[{'original_terms':['menopause','menopausal']},{'original_terms':['sleep']}]
    papers=[{'pmid':'1','title':'Menopause management','doi':'10.1000/a','pub_types':['Review']},
            {'pmid':'2','title':'Menopausal sleep','doi':'10.1000/b','pub_types':['Review']},
            {'pmid':'3','title':'Menopausal sleep trial','doi':'10.1000/c','pub_types':['Clinical Trial']}]
    assert [r['pmid'] for r in select_review_seeds(papers,groups,2)]==['2','1']


def test_reference_metadata_is_batched_and_missing_ids_are_visible():
    calls=[]
    refs=['https://openalex.org/W'+str(i) for i in range(101)]
    def get(url,**kwargs):
        calls.append(url)
        if '/works/doi:' in url:return 200,{'id':'https://openalex.org/W999','referenced_works':refs}
        ids=parse_qs(urlparse(url).query)['filter'][0].split(':',1)[1].split('|')
        return 200,{'results':[{'id':'https://openalex.org/'+i,'doi':'https://doi.org/10.1000/'+i,'title':i} for i in ids if i!='W50']}
    result=reference_candidates({'doi':'10.1000/source','pmid':'9'},limit=101,request=get)
    assert len(calls)==3
    assert len(result['results'])==100
    assert result['missing_reference_ids']==['W50']
    assert result['status']=='partial'
    assert result['requests']==3 and result['truncated'] is False
    assert all(r['evidence_verified'] is False for r in result['results'])


def test_graph_failure_is_error_not_zero_references():
    result=reference_candidates({'doi':'10.1000/source'},request=lambda *a,**k:(503,{}))
    assert result['status']=='error' and result['results']==[]
    assert result['requests']==1


def test_invalid_reference_ids_never_become_request_targets():
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return 200,{'referenced_works':['http://127.0.0.1/secret','W1 OR cancer']}
    result=reference_candidates({'doi':'10.1000/source'},request=get)
    assert len(calls)==1
    assert result['invalid_reference_ids']==2
    assert result['status']=='partial'


def test_reference_limit_and_doi_are_validated_before_network():
    with pytest.raises(ValueError):reference_candidates({'doi':'bad'},request=lambda *a,**k:pytest.fail('No network'))
    with pytest.raises(ValueError):reference_candidates({'doi':'10.1000/a'},limit=0)


def test_research_graph_candidates_are_separate_and_keep_reference_provenance():
    from pa_cli.research_search import run_research
    spec={'original_question':'更年期睡眠','groups':[{'id':'population','terms':['menopause']},
                                                {'id':'outcome','terms':['sleep']}]}
    review={'pmid':'1','doi':'10.1000/a','title':'Menopause sleep','abstract':'Menopause sleep review','pub_types':['Review']}
    result=run_research(spec,searcher=lambda *a,**k:{'results':[review],'engine_status':{'pubmed':{'status':'ok'}}},
                        max_sources=0,reference_seeds=1,
                        graph_fetcher=lambda *a,**k:{'status':'ok','requests':2,'seed_doi':'10.1000/a',
                            'results':[{'doi':'10.1000/b','title':'Menopause sleep study','abstract':'Menopause sleep results'}]})
    assert len(result['records'])==1
    assert len(result['citation_candidates'])==1
    assert result['reference_work']['requests']==2
    assert result['citation_candidates'][0]['reference_seed_dois']==['10.1000/a']
    assert result['citation_candidates'][0]['evidence_verified'] is False


def test_graph_errors_do_not_discard_primary_records():
    from pa_cli.research_search import run_research
    def failing(*a,**k):raise TimeoutError('network')
    result=run_research({'original_question':'睡眠','groups':[{'id':'outcome','terms':['sleep']}]},
        searcher=lambda *a,**k:{'results':[{'pmid':'1','doi':'10.1000/a','title':'Sleep','abstract':'Sleep','pub_types':['Review']}],
                                'engine_status':{'pubmed':{'status':'ok'}}},
        reference_seeds=1,graph_fetcher=failing,max_sources=0)
    assert len(result['records'])==1
    assert result['reference_walks'][0]['status']=='error'
