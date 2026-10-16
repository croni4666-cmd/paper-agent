"""Explicit batched reference discovery from reviews found by the user's query."""
from __future__ import annotations

import re
from urllib.parse import quote,urlencode

from .mesh_lexicon import normalize


def select_review_seeds(papers,groups,limit=3):
    def coverage(paper):
        title=' '+normalize(paper.get('title',''))+' '
        return sum(any(' '+normalize(t)+' ' in title for t in g['original_terms']) for g in groups if g.get('required',True))
    reviews=[p for p in papers if p.get('doi') and 'Review' in p.get('pub_types',[])]
    seen=set();selected=[]
    for paper in sorted(reviews,key=lambda p:-coverage(p)):
        doi=paper['doi'].lower()
        if doi not in seen:
            selected.append(paper);seen.add(doi)
            if len(selected)>=limit:break
    return selected if limit>0 else []


def reference_candidates(seed,limit=200,*,request=None,timeout=30):
    doi=seed.get('doi','').removeprefix('https://doi.org/')
    if not isinstance(limit,int) or not 1<=limit<=500:
        raise ValueError('Reference limit must be 1..500')
    if not re.fullmatch(r'10\.\d{4,9}/[^\s<>]+',doi):
        raise ValueError('A valid DOI seed is required')
    if request is None:
        from ._http import http_get_json
        request=http_get_json
    from .search import _normalize_openalex
    result={'seed_pmid':seed.get('pmid'),'seed_doi':doi,'results':[],
            'requests':0,'status':'error','research_verified':False}
    def get(url):
        result['requests']+=1
        try:return request(url,timeout=timeout)
        except Exception as exc:
            return 0,{'error':type(exc).__name__}
    status,source=get('https://api.openalex.org/works/doi:'+quote(doi,safe='/:'))
    if status!=200 or not isinstance(source,dict) or not isinstance(source.get('referenced_works'),list):
        result['http_status']=status
        return result
    raw=source['referenced_works']
    ids=[];invalid=0
    for value in raw:
        match=re.fullmatch(r'(?:https://openalex\.org/)?(W\d+)',str(value))
        if match:ids.append(match.group(1))
        else:invalid+=1
    ids=list(dict.fromkeys(ids));selected=ids[:limit]
    fetched={};errors=[]
    for start in range(0,len(selected),100):
        batch=selected[start:start+100]
        status,data=get('https://api.openalex.org/works?'+urlencode({'filter':'openalex_id:'+'|'.join(batch),'per-page':100}))
        if status!=200 or not isinstance(data,dict) or not isinstance(data.get('results'),list):
            errors.append({'batch_start':start,'http_status':status});continue
        for paper in data['results']:
            if not isinstance(paper,dict):continue
            wid=str(paper.get('id','')).rsplit('/',1)[-1]
            if wid in batch:
                try:
                    normalized=_normalize_openalex(paper)
                    if not (normalized.get('title') or normalized.get('doi') or normalized.get('pmid')):
                        raise ValueError('Missing document identity')
                except (TypeError,ValueError,AttributeError,KeyError):
                    errors.append({'openalex_id':wid,'error':'invalid_record'});continue
                normalized['evidence_verified']=False
                normalized['access']='partial_text' if normalized.get('abstract') else 'metadata_only'
                normalized['reference_seed_doi']=doi
                normalized['openalex_id']=wid
                fetched[wid]=normalized
    missing=[wid for wid in selected if wid not in fetched]
    result.update({'status':'partial' if errors or invalid or missing else 'ok',
                   'total_reference_ids':len(raw),'selected_reference_ids':len(selected),
                   'truncated':len(ids)>limit,'invalid_reference_ids':invalid,
                   'missing_reference_ids':missing,'errors':errors,
                   'results':[fetched[wid] for wid in selected if wid in fetched]})
    return result
