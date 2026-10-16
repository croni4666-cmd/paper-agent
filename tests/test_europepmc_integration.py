import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from pa_cli import search
from pa_cli.query_plan import build_plan
from pa_cli.research_search import run_research
from pa_cli.research_cache import CachedSearch


def payload(rows=(), count=None):
    return {'hitCount': len(rows) if count is None else count,
            'resultList': {'result': list(rows)}}


def row(**extra):
    return {'id': '123', 'source': 'MED', 'pmid': '123', 'pmcid': 'PMC456',
            'doi': '10.1000/ABC', 'title': 'Menopause sleep therapy',
            'pubYear': '2025', 'abstractText': '<h4>Results</h4><p>A &amp; B</p>',
            'isOpenAccess': 'Y', 'inEPMC': 'Y', 'license': 'CC BY',
            'pubTypeList': {'pubType': ['Journal Article']}, **extra}


def spec():
    return {'original_question': 'menopause sleep', 'groups': [
        {'id': 'population', 'terms': ['menopause']},
        {'id': 'sleep', 'terms': ['sleep', 'insomnia']}]}


def test_public_search_preserves_core_fields_and_request_contract():
    with patch.object(search, 'http_get_json', return_value=(200, payload([row()]))) as get:
        result = search.run_search('TITLE_ABS:menopause', engine='europepmc', limit=5,
                                   year_min=2020, year_max=2025)
    assert result['engine_status']['europepmc'] == {'status': 'ok', 'count': 1}
    p = result['results'][0]
    assert (p['pmid'], p['pmcid'], p['doi'], p['year']) == ('123', 'PMC456', '10.1000/abc', 2025)
    assert p['source'] == 'europepmc' and p['upstream_source'] == 'MED'
    assert p['abstract'] == 'Results A & B' and p['license'] == 'CC BY'
    assert p['fulltext_xml_url'].endswith('/PMC456/fullTextXML')
    q = parse_qs(urlparse(get.call_args.args[0]).query)
    assert q['synonym'] == ['false'] and q['resultType'] == ['core'] and q['pageSize'] == ['5']
    assert 'FIRST_PDATE:[2020-01-01 TO 2025-12-31]' in q['query'][0]


@pytest.mark.parametrize('code,data,state', [(429, {}, 'rate_limited'), (0, {}, 'error'),
    (200, {}, 'error'), (200, {'hitCount': 1, 'resultList': {'result': 'bad'}}, 'error'),
    (200, payload(), 'ok'), (200, payload([], count=4), 'error')])
def test_errors_are_not_zero_hit_success(code, data, state):
    with patch.object(search, 'http_get_json', return_value=(code, data)):
        r = search.run_search('sleep', engine='europepmc', limit=5)
    assert r['engine_status']['europepmc']['status'] == state


def test_non_oa_and_preprints_not_mislabeled():
    r = row(source='PPR', id='PPR123', pmid='', pmcid='', isOpenAccess='N',
            pubYear='', pubTypeList={'pubType': ['Preprint']})
    with patch.object(search, 'http_get_json', return_value=(200, payload([r]))):
        p = search.run_search('sleep', engine='europepmc')['results'][0]
    assert p['is_oa'] is False and p['fulltext_xml_url'] == ''
    assert p['year'] is None and p['publication_types'] == ['Preprint']


@pytest.mark.parametrize('reverse', [False, True])
def test_cross_engine_pmid_dedup_even_when_only_one_has_doi(reverse):
    p = {'pmid': '123', 'title': 'Menopause sleep therapy', 'source': 'pubmed'}
    with patch.object(search, 'http_get_json', return_value=(200, payload([row()]))), \
            patch.object(search, 'search_pubmed', return_value=[p]):
        r = search.run_search('sleep', engine='europepmc,pubmed' if reverse else 'pubmed,europepmc')
    assert len(r['results']) == 1
    assert set(r['results'][0]['found_by']) == {'europepmc', 'pubmed'}
    assert r['results'][0]['doi'] == '10.1000/abc'
    assert r['results'][0]['fulltext_xml_url']


def test_query_compiler_and_research_do_not_send_pubmed_syntax():
    calls = []
    def runner(q, **kw):
        calls.append((q, kw))
        return {'results': [], 'engine_status': {'europepmc': {'status': 'ok', 'count': 0}}}
    r = run_research(spec(), engine='europepmc', searcher=runner, max_sources=0)
    assert len(calls) == 1 and calls[0][1]['engine'] == 'europepmc'
    assert 'pubmed_sort' not in calls[0][1]
    assert 'TITLE_ABS:"menopause"' in calls[0][0] and '[Title/Abstract]' not in calls[0][0]
    assert r['plan']['queries'][0]['engine'] == 'europepmc'
    assert r['status'] == 'insufficient_candidates'


def test_cache_separates_engines(tmp_path):
    calls = []
    def runner(q, **kw):
        calls.append(kw['engine'])
        return {'results': [], 'engine_status': {kw['engine']: {'status': 'ok', 'count': 0}}}
    c = CachedSearch(runner, tmp_path)
    assert c('sleep', engine='europepmc')['cache']['state'] == 'miss'
    assert c('sleep', engine='europepmc')['cache']['state'] == 'hit'
    assert c('sleep', engine='pubmed')['cache']['state'] == 'miss'
    assert calls == ['europepmc', 'pubmed']


def test_expansion_unsupported_explicitly():
    with pytest.raises(ValueError, match='expansion'):
        build_plan(spec(), engine='europepmc', expansion='full')


def test_exported_core_fixture_is_normalized_without_field_loss():
    path = Path(__file__).parent / 'fixtures/europepmc_core_prior.json'
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    with patch.object(search, 'http_get_json', return_value=(200, data)):
        r = search.run_search('prior frozen query', engine='europepmc', limit=5)
    assert r['engine_status']['europepmc']['status'] == 'ok'
    assert len(r['results']) == 5 and all(p['abstract'] and p['pmid'] for p in r['results'])


def test_later_identifier_bridge_collapses_two_earlier_records():
    rows = [{'title': 'Same study', 'doi': 'https://doi.org/10.1000/ABC'},
            {'title': 'Same study translated', 'pmid': '123'},
            {'title': 'Same study', 'doi': '10.1000/abc', 'pmid': '123'}]
    with patch.object(search, 'search_pubmed', return_value=rows):
        r = search.run_search('sleep', engine='pubmed')
    assert len(r['results']) == 1 and r['results'][0]['pmid'] == '123'


def test_bad_record_is_partial_and_not_cached(tmp_path):
    data = payload([row(), {'source': 'PPR', 'id': 'PPR123'}])
    with patch.object(search, 'http_get_json', return_value=(200, data)):
        r = CachedSearch(search.run_search, tmp_path)('sleep', engine='europepmc')
    assert r['engine_status']['europepmc']['status'] == 'partial'
    assert r['cache']['state'] == 'not_cacheable' and len(r['results']) == 1


def test_review_types_reach_existing_reference_seed_selector():
    from pa_cli.research_graph import select_review_seeds
    with patch.object(search, 'http_get_json', return_value=(200, payload([
            row(pubTypeList={'pubType': ['Review']})]))):
        r = search.run_search('sleep', engine='europepmc')
    groups = build_plan(spec(), expansion='none')['groups']
    assert len(select_review_seeds(r['results'], groups)) == 1


def test_explicit_health_probe_recognizes_optional_engine():
    from pa_cli.engine_probe import probe_search_engines
    report = probe_search_engines('sleep', engines=('europepmc',), runner=lambda *a,**k: {
        'by_engine': {'europepmc': 0}, 'engine_status': {'europepmc': {'status':'ok','count':0}}})
    assert report['engines'][0]['status'] == 'ok'
