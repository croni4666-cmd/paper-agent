"""Public Europe PMC core search. No credentials, expansion, or automatic retry."""
import re
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urlencode

BASE = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
_lock = threading.Lock()
_last_request = 0.0


class _ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        self.parts.append(' ')

    def handle_endtag(self, tag):
        self.parts.append(' ')


def _text(value):
    parser = _ArticleText()
    parser.feed(str(value or ''))
    parser.close()
    return ' '.join(''.join(parser.parts).split())


def _normalize(r):
    upstream = str(r.get('source') or '')
    identifier = str(r.get('id') or '')
    pmid = str(r.get('pmid') or (identifier if upstream == 'MED' else ''))
    pmcid = str(r.get('pmcid') or '').upper()
    if not re.fullmatch(r'PMC\d+', pmcid):
        pmcid = ''
    year = str(r.get('pubYear') or '')
    oa = r.get('isOpenAccess') == 'Y'
    author_list = (r.get('authorList') or {}).get('author', [])
    journal = (r.get('journalInfo') or {}).get('journal', {})
    count = str(r.get('citedByCount') or '0')
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '',
                 str(r.get('doi') or '').strip(), flags=re.I).lower()
    return {'title': _text(r.get('title')), 'doi': doi,
            'pmid': pmid if pmid.isdigit() else '', 'pmcid': pmcid,
            'europepmc_id': identifier, 'upstream_source': upstream,
            'source': 'europepmc', 'year': int(year) if re.fullmatch(r'\d{4}', year) else None,
            'authors': [a['fullName'] for a in author_list if isinstance(a, dict) and a.get('fullName')],
            'venue': journal.get('title') or '', 'abstract': _text(r.get('abstractText')),
            'cited_by_count': int(count) if count.isdigit() else 0,
            'publication_types': (r.get('pubTypeList') or {}).get('pubType', []),
            'pub_types': (r.get('pubTypeList') or {}).get('pubType', []),
            'mesh_terms': [m['descriptorName'] for m in (r.get('meshHeadingList') or {}).get('meshHeading', [])
                           if isinstance(m, dict) and m.get('descriptorName')],
            'license': r.get('license') or '', 'is_oa': oa,
            'url': f'https://europepmc.org/article/{upstream}/{identifier}',
            'oa_url': f'https://europepmc.org/articles/{pmcid}' if oa and pmcid else '',
            'fulltext_xml_url': f'{BASE}/{pmcid}/fullTextXML' if oa and pmcid else ''}


def search_europepmc(query, year_min=None, year_max=None, limit=50):
    from .search import http_get_json, _require_search_json
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Europe PMC requires a nonempty query')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Europe PMC limit must be 1..1000')
    for year in (year_min, year_max):
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError('Invalid publication year')
    if year_min and year_max and year_min > year_max:
        raise ValueError('Publication year range is reversed')
    if year_min or year_max:
        query = f'({query}) AND FIRST_PDATE:[{year_min or 1:04}-01-01 TO {year_max or 9999:04}-12-31]'
    params = {'query': query, 'format': 'json', 'resultType': 'core',
              'pageSize': limit, 'synonym': 'false'}
    global _last_request
    with _lock:
        # Conservative local pacing, not a claim about the provider's quota.
        time.sleep(max(0, 1.0 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
    status, data = http_get_json(BASE + '/search?' + urlencode(params), timeout=30)
    data = _require_search_json(status, data, 'Europe PMC', 'search')
    results = data.get('resultList')
    rows = results.get('result') if isinstance(results, dict) else None
    count = data.get('hitCount')
    if (type(count) is not int or count < 0 or not isinstance(rows, list)
            or any(not isinstance(r, dict) for r in rows)
            or (count > 0 and not rows) or count < len(rows)):
        raise ValueError('Europe PMC returned invalid result structure')
    normalized = []
    for r in rows[:limit]:
        try:
            p = _normalize(r)
            if not (p['title'] or p['pmid'] or p['doi']):
                raise ValueError('Missing identity')
            normalized.append(p)
        except (TypeError, ValueError, AttributeError, KeyError):
            normalized.append({'error': 'europepmc_invalid_record'})
    return normalized
