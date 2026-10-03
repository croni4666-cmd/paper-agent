"""Small, dependency-free helpers for bibliographic and retrieval identifiers."""
import re
from urllib.parse import urlsplit

_ARXIV = re.compile(r'(?:\d{4}\.\d{4,5}|[a-zA-Z][a-zA-Z.-]*/\d{7})(?:v\d+)?$')


def arxiv_id(value):
    value = str(value or '').strip()
    if value.lower().startswith('arxiv:'):
        value = value[6:]
    elif value.startswith(('http://', 'https://')):
        parsed = urlsplit(value)
        if parsed.hostname not in ('arxiv.org', 'www.arxiv.org'):
            return ''
        if not parsed.path.startswith(('/abs/', '/pdf/')):
            return ''
        value = parsed.path[5:].removesuffix('.pdf')
    return value if _ARXIV.fullmatch(value) else ''


def split_identifiers(paper):
    doi = str(paper.get('doi') or '').strip()
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi, flags=re.I)
    legacy = arxiv_id(doi) if doi.lower().startswith('arxiv:') else ''
    aid = arxiv_id(paper.get('arxiv_id')) or legacy
    if str(paper.get('archiveprefix') or paper.get('archivePrefix') or '').casefold() == 'arxiv':
        aid = aid or arxiv_id(paper.get('eprint'))
    aid = aid or arxiv_id(paper.get('url')) or arxiv_id(paper.get('pdf_url'))
    return ('' if legacy else doi), aid


def citation_url(paper):
    doi, aid = split_identifiers(paper)
    for name in ('oa_url', 'url'):
        url = str(paper.get(name) or '').strip()
        if url.startswith(('https://', 'http://')) and not re.search(r'doi\.org/arxiv:', url, re.I):
            return url
    return f'https://doi.org/{doi}' if doi else (f'https://arxiv.org/abs/{aid}' if aid else '')
