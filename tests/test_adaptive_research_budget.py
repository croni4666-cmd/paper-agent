import pytest
from pa_cli.research_search import run_research


def spec():
    return {'original_question':'更年期失眠与情绪', 'groups':[
        {'id':'population','terms':['menopause']}, {'id':'outcome','terms':['sleep']},
        {'id':'context','terms':['anxiety'],'required':False}]}


def response(total,truncated=True,status='ok'):
    return {'results':[{'pmid':'1','title':'Menopause sleep','abstract':'Menopause sleep anxiety study'}] if status=='ok' else [],
            'engine_status':{'pubmed':{'status':status,'search_details':{'total_matches':total,'truncated':truncated}}}}


def test_adaptive_untruncated_pilot_stops_without_calling_another_query():
    calls=[]
    def search(q,**kw):calls.append((q,kw));return response(3,False)
    result=run_research(spec(),searcher=search,strategy='adaptive',max_sources=0)
    assert len(calls)==1 and calls[0][1]['limit']==16
    assert result['stop_reason']=='untruncated_primary_results'
    assert result['budgets']['requested_result_slots']==16
    assert result['budgets']['max_result_slots']==32


def test_adaptive_context_followup_preserves_groups_and_total32():
    calls=[]
    def search(q,**kw):calls.append((q,kw));return response(300)
    result=run_research(spec(),searcher=search,strategy='adaptive',max_sources=0)
    assert [c[1]['limit'] for c in calls]==[16,16]
    assert '"anxiety"' not in calls[0][0] and '"anxiety"' in calls[1][0]
    for q,_ in calls:assert '"menopause"' in q and '"sleep"' in q
    assert result['budgets']['requested_result_slots']==32


def test_unknown_diagnostics_never_trigger_untruncated_stop():
    calls=[]
    def search(q,**kw):calls.append(q);return {'results':[],'engine_status':{'pubmed':{'status':'ok'}}}
    result=run_research(spec(),searcher=search,strategy='adaptive',max_sources=0)
    assert len(calls)==2
    assert result['stop_reason']!='untruncated_primary_results'


def test_adaptive_does_not_reserve_slots_for_disallowed_second_query():
    limits=[]
    def search(q,**kw):limits.append(kw['limit']);return response(300)
    run_research(spec(),searcher=search,strategy='adaptive',max_queries=1,max_sources=0)
    assert limits==[32]


def test_global_slot_budget_applies_to_portfolio_without_silent_overspend():
    limits=[]
    def search(q,**kw):limits.append(kw['limit']);return response(300)
    result=run_research(spec(),searcher=search,strategy='portfolio',limit=8,max_result_slots=10,
                        max_sources=0,patience=10)
    assert limits==[8,2]
    assert result['stop_reason']=='result_slot_budget'


@pytest.mark.parametrize('budget',[0,-2])
def test_invalid_total_budget_fails_before_network(budget):
    with pytest.raises(ValueError):run_research(spec(),max_result_slots=budget)
