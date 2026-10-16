import pytest

from pa_cli.research_search import run_research
from pa_cli.institution_sources import route_sources, inspect_page


def spec():
    return {'original_question':'更年期失眠', 'domain':'medicine','topics':['sleep'],
            'groups':[{'id':'population','terms':['menopause'],'required':True},
                      {'id':'outcome','terms':['insomnia'],'required':True},
                      {'id':'delivery','terms':['online','internet'],'required':False}]}


def response(records=(),status='ok'):
    return {'results':list(records),'engine_status':{'pubmed':{'status':status,'count':len(records)}}}


def record(pmid='1',abstract='Menopause insomnia treatment improved.'):
    return {'pmid':pmid,'title':'Menopause insomnia','abstract':abstract,'doi':'10.1/'+pmid}


def test_network_failures_do_not_count_as_saturation():
    calls=[]
    def searcher(query,**kwargs):
        calls.append(query)
        return response(status='error') if len(calls)<3 else response([record()])
    result=run_research(spec(),searcher=searcher,max_queries=4,patience=1,max_sources=0,strategy='legacy')
    assert len(calls)>=3
    assert result['inspectable_candidate_count']==1
    assert result['research_verified'] is False


def test_metadata_only_results_are_not_counted_as_evidence_gain():
    result=run_research(spec(),searcher=lambda *a,**k:response([record(abstract='')]),
                        max_queries=4,patience=1,max_sources=0)
    assert result['inspectable_candidate_count']==0
    assert result['records'][0]['access']=='metadata_only'
    assert result['stop_reason']!='candidate_gain_plateau'


def test_query_budget_and_duplicate_candidates_are_recorded():
    result=run_research(spec(),searcher=lambda *a,**k:response([record()]),
                        max_queries=2,patience=10,max_sources=0,strategy='legacy')
    assert len(result['query_runs'])==2
    assert len(result['records'])==1
    assert len(result['records'][0]['query_ids'])==2
    assert result['stop_reason']=='query_budget'


def test_partial_evidence_and_off_topic_candidates_are_retained_separately():
    unrelated={**record('2'),'title':'Cancer trial','abstract':'Cancer therapy trial.'}
    result=run_research(spec(),searcher=lambda *a,**k:response([record(),unrelated]),
                        max_queries=1,max_sources=0)
    assert len(result['records'])==2
    assert result['inspectable_candidate_count']==1
    rejected=next(r for r in result['records'] if r['pmid']=='2')
    assert rejected['screening']['missing_required_groups']
    assert result['limitations']


def test_successful_zero_hit_search_has_zero_hits_not_error():
    result=run_research(spec(),searcher=lambda *a,**k:response(),max_queries=1,max_sources=0)
    assert result['query_runs'][0]['status']=='ok'
    assert result['status']=='insufficient_candidates'


def test_budget_parameters_are_validated():
    with pytest.raises(ValueError):run_research(spec(),max_queries=0)
    with pytest.raises(ValueError):run_research(spec(),patience=0)


def registry():
    return {'schema_version':1,'sources':[
        {'id':'sleep','domain':'medicine','topics':['sleep'],'name':'Institute',
         'url':'https://www.nhlbi.nih.gov/health/insomnia/treatment',
         'allowed_hosts':['www.nhlbi.nih.gov'],'role':'clinical_information',
         'document_type':'topic_page','entry_kind':'topic_page'},
        {'id':'finance','domain':'economics','topics':['finance'],'name':'Bank',
         'url':'https://www.bis.org/publications/working-paper','allowed_hosts':['www.bis.org'],
         'role':'research_publisher','document_type':'working_paper_list','entry_kind':'listing'}]}


def test_source_routing_respects_domain_and_topics():
    routed=route_sources(spec(),registry(),limit=2)
    assert [r['id'] for r in routed]==['sleep']
    assert 'site:www.nhlbi.nih.gov' in routed[0]['suggested_site_query']


def test_registry_rejects_private_or_unapproved_urls():
    reg=registry();reg['sources'][0]['url']='http://127.0.0.1/private'
    with pytest.raises(ValueError):route_sources(spec(),reg,limit=2)


def test_challenge_page_is_not_full_text():
    source=registry()['sources'][0]
    result=inspect_page(source,b'<html><title>Checking your browser</title>Verify you are human</html>',200,'text/html')
    assert result['access']=='blocked'
    assert result['status']=='blocked'


def test_listing_page_never_counts_as_inspected_effect_evidence():
    source=registry()['sources'][1]
    result=inspect_page(source,b'<html><title>Research papers</title><body>'+b'Working papers '*30+b'</body></html>',200,'text/html')
    assert result['access']=='metadata_only'
    assert result['candidate_only'] is True


def test_topic_page_is_partial_text_and_separate_from_paper_results():
    source=registry()['sources'][0]
    html=b'<html><title>Insomnia treatment</title><nav>Skip this</nav><body><p>'+b'CBT-I for insomnia. '*30+b'</p></body></html>'
    parsed=inspect_page(source,html,200,'text/html')
    assert parsed['access']=='partial_text'
    assert 'Skip this' not in parsed['text_excerpt']
    result=run_research(spec(),searcher=lambda *a,**k:response(),registry=registry(),
                        source_fetcher=lambda *a,**k:parsed,max_queries=1,max_sources=1)
    assert result['records']==[]
    assert len(result['institutional_sources'])==1


def test_nonmedical_execution_does_not_send_pubmed_field_queries():
    nonmedical={**spec(),'domain':'economics'}
    with pytest.raises(ValueError,match='medicine'):
        run_research(nonmedical,searcher=lambda *a,**k:pytest.fail('Must not send PubMed queries'))


def test_bundled_registry_has_topics_and_explicit_hosts():
    from pa_cli.institution_sources import default_registry
    reg=default_registry()
    assert len(reg['sources'])>=11
    assert all(s['topics'] and s['allowed_hosts'] for s in reg['sources'])


def test_pubmed_prefix_wildcard_matches_candidate_screening():
    profile=spec()
    profile['groups'][0]['terms']=['postmenopaus*']
    paper={'pmid':'123','title':'Postmenopausal insomnia','abstract':'Treatment for postmenopausal insomnia.'}
    result=run_research(profile,searcher=lambda *a,**k:response([paper]),max_queries=1,max_sources=0)
    assert result['inspectable_candidate_count']==1


def test_source_only_dry_run_does_not_need_mesh_index(tmp_path,monkeypatch,capsys):
    import json,sys
    from pa_cli.research_search import main
    path=tmp_path/'question.json';path.write_text(json.dumps(spec()),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['research_search',str(path),'--sources-only','--dry-run',
                                   '--mesh-index',str(tmp_path/'missing.sqlite')])
    assert main()==0
    assert json.loads(capsys.readouterr().out)['executed'] is False
