from urllib.parse import urlparse, parse_qs
import pytest
from pa_cli import search

def test_full_crossref_abstract():
    abstract = '<jats:p>' + 'Evidence and limitations. ' * 60 + '</jats:p>'
    assert search._normalize_crossref({'abstract': abstract})['abstract'] == abstract

@pytest.mark.parametrize('dates,expected', [
    ({'published-online': {'date-parts': [[2024, 3]]}}, 2024),
    ({'published-print': {'date-parts': [[]]}, 'published-online': {'date-parts': [[2023]]}}, 2023),
    ({'published': {'date-parts': [[2022]]}}, 2022),
    ({'issued': {'date-parts': [[2025]]}}, 2025),
    ({'created': {'date-parts': [[2026]]}}, None),
    ({'published-print': {'date-parts': [['unknown']]}, 'issued': {'date-parts': [[2021]]}}, 2021),
])
def test_crossref_publication_year(dates, expected):
    assert search._normalize_crossref(dates)['year'] == expected

@pytest.mark.parametrize('lookup', [False, True])
def test_crossref_requests_all_publication_dates(monkeypatch, lookup):
    urls=[]
    def get(url, **kwargs):
        urls.append(url)
        return 200, {'message': {'items': [{'title':['A title'], 'issued': {'date-parts': [[2024]]}}]}}
    monkeypatch.setattr(search, 'http_get_json', get)
    result=search._crossref_lookup_title('A long research paper title') if lookup else search.search_crossref('research')
    fields=set(parse_qs(urlparse(urls[0]).query)['select'][0].split(','))
    assert {'published-print','published-online','published','issued'} <= fields
    assert (result if lookup else result[0])['year']==2024

def test_crossref_error_identifies_engine(monkeypatch):
    monkeypatch.setattr(search, 'http_get_json', lambda *a, **k: (503, {}))
    with pytest.raises(RuntimeError, match='Crossref'):
        search.search_crossref('research')
