"""pa_cli.citations — Forward + backward citation walk via OpenAlex.

Implements [P1-1] (ROADMAP.md):

  forward  →  papers that cite the given DOI   (via filter=cites:W<id>)
  backward →  papers that the given DOI cites (via referenced_works[])

OpenAlex API:
  - Look up DOI: GET /works/doi:<doi> → {id: "https://openalex.org/W<id>", referenced_works[], ...}
  - Forward: GET /works?filter=cites:W<id>&cursor=<cursor>&per-page=<n>
    Cursor-paginated; meta.next_cursor drives the loop.
  - Backward: each entry in referenced_works[] is "https://openalex.org/W<id>".
    Reference metadata is batched in groups of at most 100, bounded by --limit.

Note (verified 2026-07-04): OpenAlex `cites` filter accepts ONLY OpenAlex IDs
(W-prefixed), NOT DOIs in any form. Direct DOI URL in filter returns 0 results.

Limits & safety:
  - default cap: 100 forward, 50 backward (per --limit flag override)
  - per-page=200 max for forward (OpenAlex hard cap); default 50 per page
  - 30s timeout per request
  - explicit error/partial states, bounded pages, and repeated-cursor detection
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Optional, Any
from urllib.parse import quote

from .search import http_get_json, _normalize_openalex


log = logging.getLogger(__name__)


OPENALEX_BASE = "https://api.openalex.org"


def _api_key_suffix(sep: str = "&") -> str:
    """Append OPENALEX_API_KEY to URL if set in env (free tier: 1 RPS without, faster with).

    sep: '&' when URL already has '?', '?' otherwise.
    """
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        return f"{sep}api_key={quote(key, safe='')}"
    return ""


def _strip_openalex_url(oa_url: str) -> str:
    """Convert 'https://openalex.org/W123' to 'W123' (for filter=)."""
    return oa_url.replace("https://openalex.org/", "")


def _validate_limit(limit):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Citation limit must be an integer from 1 to 1000')


def _request(url):
    from .search import _require_search_json
    status,data=http_get_json(url,timeout=30)
    return _require_search_json(status,data,'OpenAlex','citation retrieval')


def get_work_by_doi(doi: str) -> Optional[dict]:
    from .record_identity import canonical_doi
    import re
    doi=canonical_doi(doi)
    if not re.fullmatch(r'10\.\d{4,9}/[^\s<>]+',doi):
        raise ValueError('A valid DOI is required')
    url=f"{OPENALEX_BASE}/works/doi:{quote(doi,safe='/:')}{_api_key_suffix('?')}"
    status,data=http_get_json(url,timeout=30)
    if status==404:return None
    from .search import _require_search_json
    data=_require_search_json(status,data,'OpenAlex','source lookup')
    if not isinstance(data.get('id'),str) or not data['id'].startswith('https://openalex.org/W'):
        raise ValueError('Invalid source work identity')
    return data


def _finish(diagnostics,results,errors,truncated):
    if diagnostics is not None:
        diagnostics.update(status='partial' if errors and results else 'error' if errors else 'ok',
                           errors=errors,truncated=bool(truncated),complete=not errors and not truncated)
    return results


def _normalise_record(raw):
    if not isinstance(raw,dict):raise ValueError('Invalid record')
    p=_normalize_openalex(raw)
    if not (p.get('title') or p.get('doi') or p.get('pmid')):raise ValueError('Missing identity')
    p['openalex_id']=str(raw.get('id') or '').rsplit('/',1)[-1]
    return p


def get_citing(doi: str, limit: int = 100, per_page: int = 50, *, diagnostics=None, _source=None) -> List[Dict]:
    _validate_limit(limit)
    if type(per_page) is not int or not 1 <= per_page <= 200:raise ValueError('Invalid citation page size')
    work=_source if _source is not None else get_work_by_doi(doi)
    if work is None:raise ValueError('Source DOI not found')
    import re
    short_id=_strip_openalex_url(work['id'])
    if not re.fullmatch(r'W\d+',short_id):raise ValueError('Invalid source work identity')
    results=[];errors=[];cursor='*';seen_cursors=set();seen_records=set();leftover=False
    page_size=min(per_page,limit)
    max_pages=(limit+page_size-1)//page_size+2
    for _ in range(max_pages):
        if not cursor or len(results)>=limit:break
        if cursor in seen_cursors:
            errors.append({'error':'repeated_cursor'});break
        seen_cursors.add(cursor)
        url=(f"{OPENALEX_BASE}/works?filter=cites:{short_id}&per-page={page_size}"
             f"&cursor={quote(cursor,safe='')}{_api_key_suffix('&')}")
        try:
            data=_request(url)
            if not isinstance(data.get('results'),list) or not isinstance(data.get('meta'),dict):
                raise ValueError('Invalid citation page')
        except Exception:
            errors.append({'error':'citation_page_failed'});break
        raw_rows=data['results']
        for i,raw in enumerate(raw_rows):
            try:
                paper=_normalise_record(raw)
                key=paper.get('openalex_id') or paper.get('doi') or paper.get('pmid') or paper['title']
                if key in seen_records:continue
                seen_records.add(key);results.append(paper)
            except (ValueError,TypeError,AttributeError,KeyError):
                errors.append({'error':'invalid_citation_record'});continue
            if len(results)>=limit:
                leftover=i<len(raw_rows)-1;break
        cursor=data['meta'].get('next_cursor')
        if cursor is not None and not isinstance(cursor,str):
            errors.append({'error':'invalid_cursor'});break
    return _finish(diagnostics,results,errors,bool(cursor) or leftover)


def get_referenced(doi: str, limit: int = 50, *, diagnostics=None, _source=None) -> List[Dict]:
    _validate_limit(limit)
    work=_source if _source is not None else get_work_by_doi(doi)
    if work is None:raise ValueError('Source DOI not found')
    refs=work.get('referenced_works')
    if not isinstance(refs,list):raise ValueError('Invalid reference list')
    import re
    from urllib.parse import urlencode
    ids=[];errors=[]
    for value in refs:
        wid=_strip_openalex_url(str(value))
        if not re.fullmatch(r'W\d+',wid):errors.append({'error':'invalid_reference_id'})
        elif wid not in ids:ids.append(wid)
    selected=ids[:limit];fetched={}
    for start in range(0,len(selected),100):
        batch=selected[start:start+100]
        try:
            data=_request(OPENALEX_BASE+'/works?'+urlencode({'filter':'openalex_id:'+'|'.join(batch),'per-page':100})+_api_key_suffix('&'))
            if not isinstance(data.get('results'),list):raise ValueError('Invalid reference batch')
        except Exception:
            errors.append({'error':'reference_batch_failed'});continue
        for raw in data['results']:
            try:
                paper=_normalise_record(raw);wid=paper['openalex_id']
                if wid in batch:fetched[wid]=paper
            except (ValueError,TypeError,AttributeError,KeyError):
                errors.append({'error':'invalid_reference_record'})
    missing=[wid for wid in selected if wid not in fetched]
    if missing:errors.append({'error':'missing_reference_metadata','count':len(missing)})
    return _finish(diagnostics,[fetched[wid] for wid in selected if wid in fetched],errors,len(ids)>limit)


def citation_walk(doi: str, direction: str = 'forward', limit: int = 100) -> dict:
    if direction not in ('forward','backward'):
        return {'status':'error','error':'unknown_direction','available':['forward','backward']}
    try:
        _validate_limit(limit)
        source=get_work_by_doi(doi)
        if source is None:return {'status':'error','error':'doi_not_found','doi':doi}
        src_meta=_normalise_record(source)
        details={}
        func=get_citing if direction=='forward' else get_referenced
        papers=func(doi,limit=limit,diagnostics=details,_source=source)
        result={'doi':doi,'direction':direction,'source_work':src_meta,'results':papers,'count':len(papers),**details}
        if details.get('status')=='error':result['error']='citation_retrieval_failed'
        return result
    except Exception:
        return {'doi':doi,'direction':direction,'status':'error','error':'citation_retrieval_failed',
                'results':[],'count':0,'complete':False}
