"""Search failures must not masquerade as successful empty retrieval."""
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pa_cli import search
from pa_cli.cli import main


@pytest.mark.parametrize('engine', ['pubmed', 'openalex', 'clinicaltrials'])
@pytest.mark.parametrize('status,payload,expected', [
    (0, {'error': 'connection refused: secret=do-not-echo'}, 'error'),
    (503, {}, 'error'),
    (429, {}, 'rate_limited'),
    (200, {'error': 'invalid_json_response'}, 'error'),
])
def test_upstream_failure_is_not_success(engine, status, payload, expected):
    with patch.object(search, 'http_get_json', return_value=(status, payload)), \
            patch.object(search, '_pubmed_throttle'):
        result = search.run_search('insomnia', engine=engine, limit=1)
    state = result['engine_status'][engine]
    assert state['status'] == expected
    assert result['results'] == []
    assert 'do-not-echo' not in state.get('message', '')


@pytest.mark.parametrize('engine,payload', [
    ('pubmed', {'esearchresult': {'idlist': [], 'count': '0'}}),
    ('openalex', {'results': []}),
    ('clinicaltrials', {'studies': []}),
])
def test_valid_zero_hits_remain_success(engine, payload):
    with patch.object(search, 'http_get_json', return_value=(200, payload)), \
            patch.object(search, '_pubmed_throttle'):
        result = search.run_search('no matching study', engine=engine)
    assert result['engine_status'][engine] == {'status': 'ok', 'count': 0}


@pytest.mark.parametrize('engine,payload', [
    ('pubmed', {}), ('pubmed', {'esearchresult': {'idlist': 'bad'}}),
    ('openalex', {}), ('openalex', {'results': 'bad'}),
    ('clinicaltrials', {'studies': 'bad'}),
])
def test_invalid_response_schema_is_error(engine, payload):
    with patch.object(search, 'http_get_json', return_value=(200, payload)), \
            patch.object(search, '_pubmed_throttle'):
        result = search.run_search('insomnia', engine=engine)
    assert result['engine_status'][engine]['status'] == 'error'


@pytest.mark.parametrize('status,payload', [(0, {}), (503, {}), (200, {'error': 'bad'})])
def test_pubmed_summary_failure_is_not_empty_success(status, payload):
    responses = [(200, {'esearchresult': {'idlist': ['123']}}), (status, payload)]
    with patch.object(search, 'http_get_json', side_effect=responses), \
            patch.object(search, '_pubmed_throttle'), \
            patch.object(search, '_fetch_pubmed_details', return_value={}):
        result = search.run_search('insomnia', engine='pubmed')
    assert result['engine_status']['pubmed']['status'] == 'error'


def test_pubmed_optional_abstract_failure_preserves_metadata():
    responses = [(200, {'esearchresult': {'idlist': ['123']}}),
                 (200, {'result': {'uids': ['123'], '123': {
                     'uid': '123', 'title': 'Usable record', 'pubdate': '2025'}}})]
    with patch.object(search, 'http_get_json', side_effect=responses), \
            patch.object(search, '_pubmed_throttle'), \
            patch.object(search, '_fetch_pubmed_details', return_value={}):
        result = search.run_search('insomnia', engine='pubmed')
    assert result['engine_status']['pubmed'] == {'status': 'ok', 'count': 1}
    assert result['results'][0]['title'] == 'Usable record'


def test_one_failed_engine_does_not_discard_other_engine():
    def respond(url, **kwargs):
        if 'openalex' in url:
            return 503, {}
        return 200, {'esearchresult': {'idlist': [], 'count': '0'}}
    with patch.object(search, 'http_get_json', side_effect=respond), \
            patch.object(search, '_pubmed_throttle'):
        result = search.run_search('insomnia', engine='pubmed,openalex')
    assert result['engine_status']['pubmed']['status'] == 'ok'
    assert result['engine_status']['openalex']['status'] == 'error'


def test_cli_fails_when_every_engine_failed_but_keeps_diagnostics():
    with patch.object(search, 'http_get_json', return_value=(503, {})):
        result = CliRunner().invoke(main, ['search', 'insomnia', '--engine', 'openalex', '--quiet'])
    assert result.exit_code == 2
    assert 'engine_status' in result.output
    assert 'error' in result.output


def test_cli_valid_zero_hits_exits_successfully():
    with patch.object(search, 'http_get_json', return_value=(200, {'results': []})):
        result = CliRunner().invoke(main, ['search', 'unlikely term', '--engine', 'openalex', '--quiet'])
    assert result.exit_code == 0
