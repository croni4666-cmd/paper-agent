"""Cross-surface failures found during the full functional review."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pa_cli import search, citations, doctor
from pa_cli.research_search import run_research
from pa_cli.research_graph import reference_candidates
from pa_cli.review import build_corpus_index, synthesize
from pa_cli.bibtex import to_bibtex, format_authors
from pa_cli.cite_check import extract_cite_keys, run_cite_check
from test_skill_runtime_health import backend,run_wrapper


@pytest.mark.parametrize('code,data,state',[(200,{},'error'),(200,{'message':{}},'error'),
    (200,{'message':{'items':'invalid'}},'error'),(429,{},'rate_limited')])
def test_crossref_rejects_missing_result_schema(code,data,state):
    with patch.object(search,'http_get_json',return_value=(code,data)):
        r=search.run_search('sleep',engine='crossref')
    assert r['engine_status']['crossref']['status']==state


def test_pubmed_summary_missing_requested_pmid_is_partial():
    responses=[(200,{'esearchresult':{'idlist':['1','2']}}),
        (200,{'result':{'uids':['1','2'],'1':{'uid':'1','title':'Valid','pubdate':'2025'},
                        '2':{'uid':'2','error':'not available'}}})]
    with patch.object(search,'http_get_json',side_effect=responses), \
         patch.object(search,'_pubmed_throttle'),patch.object(search,'_fetch_pubmed_details',return_value={}):
        r=search.run_search('sleep',engine='pubmed')
    assert r['engine_status']['pubmed']['status']=='partial'
    assert len(r['results'])==1


WORK={'id':'https://openalex.org/W9','doi':'https://doi.org/10.1000/source',
      'title':'Source','referenced_works':[]}


def test_citation_transport_failure_not_mislabeled_not_found():
    with patch.object(citations,'http_get_json',return_value=(503,{})):
        r=citations.citation_walk('10.1000/source')
    assert r.get('status')=='error' and r.get('error')!='doi_not_found'


def test_forward_citation_page_failure_not_successful_empty_graph():
    def get(url,**kw):return (200,WORK) if '/works/doi:' in url else (503,{})
    with patch.object(citations,'http_get_json',side_effect=get):
        r=citations.citation_walk('10.1000/source')
    assert r.get('status')=='error' and r.get('error')


def test_forward_keeps_title_only_records_and_uses_one_source_lookup():
    calls=[]
    def get(url,**kw):
        calls.append(url)
        return (200,WORK) if '/works/doi:' in url else (200,{
            'results':[{'id':'https://openalex.org/W1','title':'Article without DOI'}],
            'meta':{'next_cursor':None}})
    with patch.object(citations,'http_get_json',side_effect=get):
        r=citations.citation_walk('10.1000/source',limit=5)
    assert r['count']==1 and r.get('status')=='ok'
    assert sum('/works/doi:' in x for x in calls)==1


def test_forward_partial_pages_remain_partial():
    pages=[(200,{'results':[{'id':'https://openalex.org/W1','title':'First','doi':'10.1000/first'}],
                 'meta':{'next_cursor':'next'}}),(503,{})]
    def get(url,**kw):return (200,WORK) if '/works/doi:' in url else pages.pop(0)
    with patch.object(citations,'http_get_json',side_effect=get):
        r=citations.citation_walk('10.1000/source',limit=5)
    assert r['count']==1 and r.get('status')=='partial' and r.get('complete') is False


def test_reference_batch_one_malformed_record_does_not_drop_valid_ones():
    def get(url,**kw):
        if '/works/doi:' in url:return 200,{**WORK,'referenced_works':['W1','W2']}
        return 200,{'results':[{'id':'https://openalex.org/W1','title':'Good'},
            {'id':'https://openalex.org/W2','authorships':[{'author':'bad schema'}]}]}
    r=reference_candidates({'doi':'10.1000/source'},request=get)
    assert r['status']=='partial' and len(r['results'])==1
    assert r['missing_reference_ids']==['W2']


def spec():
    return {'original_question':'Sleep therapy','groups':[
        {'id':'sleep','terms':['sleep']},
        {'id':'delivery','required':False,'terms':['online','internet']}]}


def test_research_same_doi_acquires_pmid_without_becoming_new_paper():
    calls=[]
    def runner(*a,**kw):
        calls.append(1)
        row={'doi':'10.1000/paper','title':'Sleep trial','abstract':'Sleep intervention.'}
        if len(calls)>1:row['pmid']='123'
        return {'results':[row],'engine_status':{'pubmed':{'status':'ok'}}}
    r=run_research(spec(),searcher=runner,strategy='legacy',max_queries=2,max_sources=0,patience=10)
    assert len(r['records'])==1 and len(r['records'][0]['query_ids'])==2
    assert r['query_runs'][1]['new_inspectable_topic_candidates']==0


def test_reference_merge_does_not_erase_existing_abstract():
    def runner(*a,**kw):
        return {'results':[{'doi':'10.1000/r1','title':'Sleep review','pub_types':['Review']},
            {'doi':'10.1000/r2','title':'Sleep review 2','pub_types':['Review']}],
            'engine_status':{'pubmed':{'status':'ok'}}}
    calls=[]
    def graph(seed,**kw):
        calls.append(1)
        return {'status':'ok','requests':1,'results':[{
            'doi':'10.1000/trial','title':'Sleep trial','abstract':'Sleep results' if len(calls)==1 else ''}]}
    r=run_research(spec(),searcher=runner,graph_fetcher=graph,reference_seeds=2,max_sources=0)
    assert r['citation_candidates'][0]['abstract']=='Sleep results'
    assert r['citation_candidates'][0]['access']=='partial_text'


@pytest.mark.parametrize('option,value',[('timeout_seconds',float('nan')),('max_queries',True),
                                       ('limit',1.5),('max_result_slots',False)])
def test_invalid_budgets_fail_before_calling_sources(option,value):
    runner=Mock()
    with pytest.raises(ValueError):run_research(spec(),searcher=runner,max_sources=0,**{option:value})
    runner.assert_not_called()


def test_generated_inventory_never_becomes_another_paper(tmp_path):
    (tmp_path/'article.txt').write_text('An actual research article on sleep.',encoding='utf-8')
    (tmp_path/'inventory.md').write_text(synthesize(tmp_path),encoding='utf-8')
    assert len(build_corpus_index(tmp_path))==1


def test_bibtex_keeps_abstract_and_stable_medical_ids():
    bib=to_bibtex({'doi':'10.1000/a','title':'Study','abstract':'p < 0.05; benefit.',
                   'pmid':'123','pmcid':'PMC456','license':'CC BY'})
    assert 'abstract = {p < 0.05; benefit.}' in bib
    assert 'pmid = {123}' in bib and 'pmcid = {PMC456}' in bib


def test_already_comma_formatted_author_is_not_reversed_again():
    assert format_authors(['Smith, Jane','John Doe'])=='Smith, Jane and Doe, John'


def test_grouped_citations_check_every_key_once_per_line():
    assert extract_cite_keys('See [@present; @missing], and [@present].')==[('present',1),('missing',1)]


def test_citation_report_counts_resolved_citations_and_real_bib_keys(tmp_path):
    bib=tmp_path/'refs.bib';md=tmp_path/'paper.md'
    bib.write_text('@article{a, title={A}}\n@article{b, title={B}}',encoding='utf-8')
    md.write_text('Citation [@a].',encoding='utf-8')
    result,report=run_cite_check(bib,md)
    assert '- Placeholders: 1 occurrences' in report and '- Bib keys: 2' in report


def test_offline_browser_check_is_supervised_and_bounded():
    with patch('pa_cli.fetch_deadline.run_fetch',return_value={'installed':True}) as worker, \
         patch('playwright.sync_api.sync_playwright',side_effect=RuntimeError('driver not available')):
        assert doctor._chromium_installed() is True
    assert worker.call_count==1 and worker.call_args.args[1]<=10


def test_missing_corpus_is_not_reported_as_zero_papers(tmp_path):
    from pa_cli.corpus_stats import compute_corpus_stats,format_corpus_stats_human
    r=compute_corpus_stats(tmp_path/'missing.bib')
    assert r.get('status')=='error' and r['n_papers'] is None
    assert 'unavailable' in format_corpus_stats_human(r)


def test_valid_empty_corpus_has_zero_papers(tmp_path):
    from pa_cli.corpus_stats import compute_corpus_stats
    p=tmp_path/'empty.bib';p.write_text('',encoding='utf-8')
    r=compute_corpus_stats(p)
    assert r.get('status')=='ok' and r['n_papers']==0


def test_citation_wrapper_keeps_successful_direction_when_other_fails(backend,tmp_path):
    (backend/'pa_cli/citations.py').write_text(
        "def citation_walk(doi,direction,limit):\n"
        "    return {'status':'error','error':'offline','results':[]} if direction=='backward' else "
        "{'status':'ok','results':[{'title':'Available paper'}]}\n",encoding='utf-8')
    p=run_wrapper('citations.py',['10.1000/source','--direction','both'],backend,tmp_path)
    assert p.returncode==0,p.stderr
    r=json.loads(p.stdout)
    assert r.get('status')=='partial' and r['count']==1
    assert r['walks']['backward']['error']=='offline'


def test_pubmed_second_summary_chunk_failure_preserves_first_chunk():
    ids=[str(i) for i in range(1,102)]
    first={'uids':ids[:100],**{pid:{'uid':pid,'title':'Sleep '+pid,'pubdate':'2025'} for pid in ids[:100]}}
    calls=[(200,{'esearchresult':{'idlist':ids}}),(200,{'result':first}),(503,{})]
    with patch.object(search,'http_get_json',side_effect=calls),patch.object(search,'_pubmed_throttle'), \
            patch.object(search,'_fetch_pubmed_details',return_value={}):
        r=search.run_search('sleep',engine='pubmed',limit=101)
    assert r['engine_status']['pubmed']['status']=='partial' and len(r['results'])==100


@pytest.mark.parametrize('options',[{'limit':0},{'limit':True},{'engine_timeout':float('nan')},
                                   {'year_min':2026,'year_max':2020}])
def test_generic_search_rejects_invalid_budgets_before_network(options):
    with patch.object(search,'search_crossref') as provider:
        with pytest.raises(ValueError):search.run_search('sleep',engine='crossref',**options)
        provider.assert_not_called()


def test_saved_search_really_invokes_search_callback(tmp_path):
    from pa_cli import search_saved
    from pa_cli.cli import main
    from click.testing import CliRunner
    path=tmp_path/'saved.json'
    search_saved.add('sleep','sleep',engine='crossref',path=path)
    with patch.object(search_saved,'DEFAULT_PATH',path),patch.object(search,'search_crossref',return_value=[{'title':'Study'}]):
        r=CliRunner().invoke(main,['search-saved','run','sleep','--quiet'])
    assert r.exit_code==0,r.output
    assert json.loads(r.stdout)['results'][0]['title']=='Study'


def test_failed_search_does_not_overwrite_import_bibliography(tmp_path):
    from pa_cli.search_and_import import search_to_bibtex
    p=tmp_path/'refs.bib';p.write_text('Existing bibliography',encoding='utf-8')
    failure={'results':[],'engine_status':{'pubmed':{'status':'error'}}}
    with patch('pa_cli.search_and_import._import_run_search',return_value=lambda *a,**kw:failure):
        with pytest.raises(RuntimeError):search_to_bibtex('sleep',out_bib_path=p,quiet=True)
    assert p.read_text(encoding='utf-8')=='Existing bibliography'


def test_fuzzy_dedup_does_not_delete_distinct_doi_papers():
    from pa_cli.dedup_strict import find_dup_groups
    papers=[{'key':'a','doi':'10.1000/a','title':'Acupuncture improves menopausal sleep'},
            {'key':'b','doi':'10.1000/b','title':'Acupuncture does not improve menopausal sleep'}]
    assert len(find_dup_groups(papers,fuzzy_threshold=.7))==2
