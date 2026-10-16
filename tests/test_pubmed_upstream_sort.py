from unittest.mock import patch
from urllib.parse import parse_qs,urlparse

import pytest

from pa_cli import search


def test_opt_in_pubmed_best_match_is_sent_upstream():
    urls=[]
    def get(url,**kwargs):
        urls.append(url)
        return 200,{'esearchresult':{'idlist':[]}}
    with patch.object(search,'http_get_json',side_effect=get),patch.object(search,'_pubmed_throttle'):
        result=search.run_search('menopause insomnia',engine='pubmed',pubmed_sort='relevance')
    assert result['engine_status']['pubmed']['status']=='ok'
    assert parse_qs(urlparse(urls[0]).query)['sort']==['relevance']


def test_default_pubmed_sort_is_unchanged():
    urls=[]
    def get(url,**kwargs):
        urls.append(url);return 200,{'esearchresult':{'idlist':[]}}
    with patch.object(search,'http_get_json',side_effect=get),patch.object(search,'_pubmed_throttle'):
        search.run_search('menopause insomnia',engine='pubmed')
    assert 'sort' not in parse_qs(urlparse(urls[0]).query)


def test_reject_invalid_upstream_sort_before_network():
    with patch.object(search,'http_get_json',side_effect=AssertionError('no request')):
        with pytest.raises(ValueError):search.search_pubmed('sleep',sort='anything')


def test_opt_in_diagnostics_preserve_translation_and_phrase_warnings_on_zero_hits():
    payload={'esearchresult':{'idlist':[], 'count':'0','retmax':'0','retstart':'0',
             'querytranslation':'"home environment"[MeSH Terms] AND insomnia[All Fields]',
             'warninglist':{'quotedphrasesnotfound':['Good Sleep Habit']}}}
    with patch.object(search,'http_get_json',return_value=(200,payload)),patch.object(search,'_pubmed_throttle'):
        result=search.run_search('alone insomnia',engine='pubmed',pubmed_diagnostics=True)
    details=result['engine_status']['pubmed']['search_details']
    assert details['query_translation']=='"home environment"[MeSH Terms] AND insomnia[All Fields]'
    assert details['warnings']['quotedphrasesnotfound']==['Good Sleep Habit']
    assert details['total_matches']==0
    assert details['truncated'] is False


def test_diagnostics_distinguish_result_truncation_from_zero_recall():
    payload={'esearchresult':{'idlist':['123'],'count':'159','retmax':'1','retstart':'0',
                             'querytranslation':'insomnia[Title/Abstract]'}}
    summary={'result':{'uids':['123'],'123':{'uid':'123','title':'Insomnia trial','pubdate':'2019'}}}
    with patch.object(search,'http_get_json',side_effect=[(200,payload),(200,summary)]),\
         patch.object(search,'_pubmed_throttle'),patch.object(search,'_fetch_pubmed_details',return_value={}):
        result=search.run_search('insomnia',engine='pubmed',limit=1,pubmed_diagnostics=True)
    details=result['engine_status']['pubmed']['search_details']
    assert details['total_matches']==159
    assert details['returned_ids']==1
    assert details['truncated'] is True
    assert result['results'][0]['pmid']=='123'


def test_pubmed_preserves_esearch_rank_when_esummary_returns_different_order():
    # ESummary metadata order is not the ranked ESearch identifier order.
    payload={'esearchresult':{'idlist':['2','1'],'count':'2'}}
    metadata={'result':{'uids':['1','2'],
              '1':{'uid':'1','title':'Lower-ranked study','pubdate':'2025'},
              '2':{'uid':'2','title':'Higher-ranked study','pubdate':'2019'}}}
    with patch.object(search,'http_get_json',side_effect=[(200,payload),(200,metadata)]),\
         patch.object(search,'_pubmed_throttle'),patch.object(search,'_fetch_pubmed_details',return_value={}):
        result=search.run_search('sleep',engine='pubmed',pubmed_sort='relevance')
    assert [r['pmid'] for r in result['results']]==['2','1']
