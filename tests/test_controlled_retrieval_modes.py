import pytest

from pa_cli.query_plan import build_plan
from pa_cli.research_search import run_research
from test_mesh_query_plan import mesh


def question():
    return {'original_question':'更年期女性的睡眠卫生教育与失眠', 'groups':[
        {'id':'population','terms':['menopause'],'mesh':['D001'],'required':True},
        {'id':'outcome','terms':['insomnia'],'mesh':['D002'],'required':True},
        {'id':'intervention','terms':['sleep hygiene'],'required':True},
        {'id':'context','terms':['anxiety'],'required':False}]}


def primary(plan):
    qid=plan['query_strategies']['single'][0]
    return next(q for q in plan['queries'] if q['id']==qid)


def test_no_expansion_is_a_real_original_terms_control(mesh):
    index,_=mesh
    query=primary(build_plan(question(),index,expansion='none'))['query']
    assert query=='("menopause"[Title/Abstract]) AND ("insomnia"[Title/Abstract]) AND ("sleep hygiene"[Title/Abstract])'
    assert 'Climacteric' not in query and '[MeSH Terms]' not in query


def test_headings_expansion_does_not_add_dictionary_synonyms(mesh):
    index,_=mesh
    query=primary(build_plan(question(),index,expansion='headings'))['query']
    assert '"Menopause"[MeSH Terms]' in query
    assert 'Climacteric' not in query and 'Sleeplessness' not in query
    full=primary(build_plan(question(),index,expansion='full'))['query']
    assert 'Climacteric' in full and 'Sleeplessness' in full


def test_headings_accept_resolved_mesh_only_group_without_fabricating_plain_terms(mesh):
    index,_=mesh
    spec=question();spec['groups'][0]['terms']=[]
    plan=build_plan(spec,index,expansion='headings')
    query=primary(plan)['query']
    assert query.startswith('("Menopause"[MeSH Terms]) AND ')
    assert all('()' not in q['query'] for q in plan['queries'])
    assert plan['groups'][0]['terms']==[]
    with pytest.raises(ValueError):build_plan(spec,index,expansion='none')


def test_mapped_heading_only_candidate_is_screened_without_contaminating_none_control(mesh):
    index,_=mesh
    spec={'original_question':'更年期', 'groups':[{'id':'population','mesh':['D001'],'required':True}]}
    def searcher(*args,**kwargs):
        return {'results':[{'pmid':'123','title':'Clinical study','abstract':'Adults studied.',
                            'mesh_terms':['Menopause']}], 'engine_status':{'pubmed':{'status':'ok'}}}
    result=run_research(spec,index,searcher=searcher,expansion='headings',max_sources=0)
    assert result['inspectable_candidate_count']==1
    assert result['records'][0]['screening']['missing_required_groups']==[]
    spec['groups'][0]['terms']=['postmenopaus*']
    control=run_research(spec,index,searcher=searcher,expansion='none',max_sources=0)
    assert control['inspectable_candidate_count']==0


def test_portfolio_focuses_fields_without_dropping_required_groups(mesh):
    index,_=mesh
    plan=build_plan(question(),index,expansion='none')
    portfolio=[q for qid in plan['query_strategies']['portfolio'] for q in plan['queries'] if q['id']==qid]
    assert len(portfolio)==4
    assert '"sleep hygiene"[Title]' in portfolio[1]['query']
    for q in portfolio:
        assert set(q['group_ids'])=={'population','outcome','intervention'}
        assert q['relaxed_optional_groups']==['context']
    assert '"insomnia"[Title/Abstract]' in portfolio[1]['query']


def test_default_single_query_uses_32_slots_and_preserves_search_diagnostics():
    calls=[]
    def searcher(q,**kwargs):
        calls.append((q,kwargs))
        return {'results':[], 'engine_status':{'pubmed':{'status':'ok','search_details':{'total_matches':87,'truncated':True}}}}
    result=run_research(question(),searcher=searcher,max_sources=0)
    assert len(calls)==1
    assert calls[0][1]['limit']==32
    assert calls[0][1]['pubmed_diagnostics'] is True
    assert '[MeSH Terms]' not in calls[0][0]
    assert result['query_runs'][0]['engine_status']['pubmed']['search_details']['truncated'] is True
    assert result['budgets']['requested_result_slots']==32
    assert result['strategy']=='single' and result['expansion']=='none'


def test_portfolio_has_explicit_equal_slot_budget_and_query_diversity():
    seen=[]
    def searcher(q,**kwargs):
        seen.append(q)
        return {'results':[],'engine_status':{'pubmed':{'status':'ok'}}}
    result=run_research(question(),searcher=searcher,strategy='portfolio',expansion='none',
                        max_queries=4,limit=8,patience=10,max_sources=0)
    assert len(seen)==4 and len(set(seen))==4
    assert result['budgets']['requested_result_slots']==32


@pytest.mark.parametrize('options',[{'expansion':'invented'},{'strategy':'invented'}])
def test_invalid_control_modes_fail_before_network(options):
    with pytest.raises(ValueError):
        run_research(question(),searcher=lambda *a,**k:pytest.fail('No network for invalid modes'),**options)
