"""Opt-in concept search with observable budgets and separate official pages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import math
import time

from .mesh_lexicon import MeshIndex, normalize
from .query_plan import build_plan
from .institution_sources import route_sources, fetch_source
from .record_identity import deduplicate_records, record_aliases


def _record_key(paper: dict) -> str:
    aliases=record_aliases(paper)
    return aliases[0] if aliases else 'title:'


def _screen(paper: dict, groups: list[dict], expansion: str = 'none') -> dict:
    text=' '+normalize(' '.join([str(paper.get('title','')),str(paper.get('abstract','')),
                               ' '.join(paper.get('mesh_terms',[]))]))+' '
    matches=[]
    def matches_term(term):
        parts=re.findall(r'\w+\*?',term.casefold())
        if not parts:return False
        pattern=r'\b'+r'\s+'.join(re.escape(normalize(p.rstrip('*')))+(r'\w*' if p.endswith('*') else '') for p in parts)+r'\b'
        return re.search(pattern,text) is not None
    for g in groups:
        mapped_labels=[c['label'] for c in g['mesh_concepts']] if expansion!='none' else []
        if any(matches_term(t) for t in [*g['terms'],*mapped_labels]):matches.append(g['id'])
    missing=[g['id'] for g in groups if g['required'] and g['id'] not in matches]
    return {'matched_groups':matches,'missing_required_groups':missing,
            'topic_candidate':not missing,'method':'Conservative phrase matching, not scientific relevance adjudication'}


def run_research(spec: dict, index: MeshIndex | None = None, *, searcher=None,
                 registry: dict | None = None, source_fetcher=None,
                 max_queries: int = 6, limit: int = 32, patience: int = 2,
                 min_new: int = 1, max_sources: int = 3, timeout_seconds: float = 180,
                 source_cache: Path | None = None, expansion: str = 'none',
                 strategy: str = 'single', query_cache: Path | None = None,
                 cache_ttl: float = 86400, refresh_cache: bool = False,
                 reference_seeds: int = 0, reference_limit: int = 200, graph_fetcher=None,
                 max_result_slots: int | None = None, engine: str = 'pubmed') -> dict:
    integer_budgets=(max_queries,limit,patience,min_new,max_sources,reference_seeds,reference_limit)
    if any(type(v) is not int for v in integer_budgets):
        raise ValueError('Query, result, source and reference budgets must be integers')
    if (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float))
            or not math.isfinite(timeout_seconds)):
        raise ValueError('Time budget must be finite')
    if max_queries<1 or limit<1 or patience<1 or min_new<1 or max_sources<0 or timeout_seconds<=0:
        raise ValueError('Positive query/limit/patience/gain/time budgets and nonnegative source budget required')
    if not 0<=reference_seeds<=5 or not 1<=reference_limit<=500:
        raise ValueError('Reference seed budget must be 0..5; per-seed references 1..500')
    if max_result_slots is not None and (type(max_result_slots) is not int or max_result_slots<1):
        raise ValueError('Maximum result slots must be positive')
    if spec.get('domain','medicine')!='medicine':
        raise ValueError('Paper-query execution supports medicine only; use source-only mode for other domains')
    if searcher is None:
        from .search import run_search
        searcher=run_search
    if query_cache is not None:
        from .research_cache import CachedSearch
        searcher=CachedSearch(searcher,query_cache,ttl_seconds=cache_ttl,refresh=refresh_cache)
    source_fetcher=source_fetcher or fetch_source
    if strategy not in ('single','portfolio','legacy','adaptive'):
        raise ValueError('strategy must be single, portfolio, legacy, or adaptive')
    if strategy=='adaptive' and max_result_slots is None:max_result_slots=32
    plan=build_plan(spec,index,expansion=expansion,engine=engine)
    by_id={q['id']:q for q in plan['queries']}
    queue=[by_id[qid] for qid in plan['query_strategies'][strategy]]
    start=time.monotonic();records={};runs=[];stale=0;stop='query_queue_exhausted';spent=0
    for query in queue:
        if len(runs)>=max_queries:
            stop='query_budget';break
        slots_left=max_result_slots-spent if max_result_slots is not None else None
        if slots_left is not None and slots_left<=0:
            stop='result_slot_budget';break
        query_limit=min(limit,200,slots_left) if slots_left is not None else min(limit,200)
        if strategy=='adaptive' and not runs and min(max_queries,len(queue))>1:
            query_limit=min(query_limit,(slots_left+1)//2)
        remaining=timeout_seconds-(time.monotonic()-start)
        if remaining<=0:
            stop='time_budget';break
        t=time.monotonic()
        try:
            options=({'pubmed_sort':'relevance','pubmed_diagnostics':True} if engine=='pubmed'
                     else {'sort_by':'relevance'})
            result=searcher(query['query'],engine=engine,limit=query_limit,
                            engine_timeout=min(45,remaining),**options)
        except Exception as exc:
            result={'results':[],'engine_status':{engine:{'status':'error','message':type(exc).__name__}}}
        state=result.get('engine_status',{}).get(engine,{})
        success=state.get('status')=='ok'
        usable=state.get('status') in ('ok','partial')
        spent+=query_limit
        before={k for k,p in records.items() if p['screening']['topic_candidate'] and p.get('abstract')}
        incoming=[]
        for paper in result.get('results',[]) if usable else []:
            incoming.append({**paper,'query_ids':[query['id']]})
        combined=deduplicate_records([*records.values(),*incoming])
        records={}
        for paper in combined:
            key=_record_key(paper)
            if key=='title:':continue
            merged=dict(paper)
            merged['access']='partial_text' if merged.get('abstract') else 'metadata_only'
            merged['screening']=_screen(merged,plan['groups'],expansion)
            merged['evidence_verified']=False
            records[key]=merged
        after={k for k,p in records.items() if p['screening']['topic_candidate'] and p.get('abstract')}
        gain=max(0,len(after)-len(before))
        runs.append({'query_id':query['id'],'query':query['query'],'kind':query['kind'],
                     'upstream_sort':'relevance',
                     'requested_limit':query_limit,
                     'group_ids':query['group_ids'],'relaxed_optional_groups':query['relaxed_optional_groups'],
                     'status':state.get('status','error'),'engine_status':result.get('engine_status',{}),
                     'returned_count':len(result.get('results',[])),
                     'new_inspectable_topic_candidates':gain,'elapsed_seconds':round(time.monotonic()-t,3),
                     'cache':result.get('cache',{'state':'disabled'}),
                     'raw_response':result})
        # Network failures never advance the plateau counter. No inspectable
        # candidates means insufficient evidence, not a claim of saturation.
        if success:
            details=state.get('search_details',{})
            if strategy=='adaptive' and len(runs)==1 and details.get('truncated') is False:
                stop='untruncated_primary_results';break
            stale=stale+1 if gain<min_new else 0
            if after and stale>=patience:
                stop='candidate_gain_plateau';break
    reference_walks=[];citation_records={}
    if reference_seeds:
        from .research_graph import select_review_seeds,reference_candidates
        graph_fetcher=graph_fetcher or reference_candidates
        seeds=select_review_seeds(list(records.values()),plan['groups'],reference_seeds)
        for seed in seeds:
            remaining=timeout_seconds-(time.monotonic()-start)
            if remaining<=0:break
            try:
                walk=graph_fetcher(seed,limit=reference_limit,timeout=min(30,remaining))
            except Exception as exc:
                walk={'seed_doi':seed['doi'],'status':'error','results':[],
                      'error':type(exc).__name__,'requests':None}
            reference_walks.append(walk)
            incoming=[{**paper,'reference_seed_dois':[seed['doi']]} for paper in
                      (walk.get('results',[]) if walk.get('status') in ('ok','partial') else [])]
            combined=deduplicate_records([*citation_records.values(),*incoming])
            citation_records={}
            for paper in combined:
                key=_record_key(paper)
                if key=='title:':continue
                merged=dict(paper)
                merged['evidence_verified']=False
                merged['screening']=_screen(merged,plan['groups'],expansion)
                merged['access']='partial_text' if merged.get('abstract') else 'metadata_only'
                citation_records[key]=merged
    routed=route_sources(spec,registry,limit=max_sources) if max_sources else []
    source_results=[]
    for source in routed:
        remaining=timeout_seconds-(time.monotonic()-start)
        if remaining<=0:break
        source_results.append(source_fetcher(source,timeout=min(20,remaining),cache_dir=source_cache))
    count=sum(p['screening']['topic_candidate'] and bool(p.get('abstract')) for p in records.values())
    status='candidates_ready' if count else 'insufficient_candidates' if any(r['status'] in ('ok','partial') for r in runs) else 'retrieval_failed'
    return {'schema_version':1,'status':status,'original_question':spec['original_question'],
            'strategy':strategy,'expansion':expansion,
            'retrieval_work':{'live_search_calls':sum(r['cache']['state']!='hit' for r in runs),
                              'cache_hits':sum(r['cache']['state']=='hit' for r in runs)},
            'research_verified':False,'plan':plan,'query_runs':runs,'stop_reason':stop,
            'inspectable_candidate_count':count,'records':list(records.values()),
            'reference_walks':reference_walks,'citation_candidates':list(citation_records.values()),
            'reference_work':{'seed_budget':reference_seeds,'per_seed_limit':reference_limit,
                              'requests':sum(w.get('requests') or 0 for w in reference_walks),
                              'request_count_complete':all(w.get('requests') is not None for w in reference_walks)},
            'source_routes':routed,'institutional_sources':source_results,
            'sources_not_fetched':len(routed)-len(source_results),
            'budgets':{'max_queries':max_queries,'per_query_limit':limit,'patience':patience,
                       'requested_result_slots':spent,'max_result_slots':max_result_slots,
                       'scheduled_result_slots':min(min(max_queries,len(queue))*min(limit,200),max_result_slots) if max_result_slots is not None else min(max_queries,len(queue))*min(limit,200),
                       'minimum_new_candidates':min_new,'max_sources':max_sources,'time_seconds':timeout_seconds},
            'scheduler':'Explicit single/portfolio/legacy/adaptive policies with observable budgets; not a trained optimizer',
            'elapsed_seconds':round(time.monotonic()-start,3),
            'limitations':['Candidate novelty is not recall or independent-study coverage.',
                           'Phrase screening may miss relevant studies or admit unsuitable interventions; review retained records.',
                           'No abstracts never count as inspected effect evidence; no automatic clinical verdict.',
                           'Institutional listings and topic pages are separate from paper results and are not quality certification.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path)
    parser.add_argument('--mesh-index',type=Path)
    parser.add_argument('--engine',choices=['pubmed','europepmc'],default='pubmed')
    parser.add_argument('--registry',type=Path)
    parser.add_argument('--max-queries',type=int,default=6)
    parser.add_argument('--limit',type=int,default=32)
    parser.add_argument('--expansion',choices=['none','headings','full'],default='none')
    parser.add_argument('--strategy',choices=['single','portfolio','legacy','adaptive'],default='single')
    parser.add_argument('--max-result-slots',type=int)
    parser.add_argument('--query-cache',type=Path,help='Opt-in exact-query successful-response cache directory')
    parser.add_argument('--cache-ttl',type=float,default=86400)
    parser.add_argument('--refresh-cache',action='store_true')
    parser.add_argument('--reference-seeds',type=int,default=0)
    parser.add_argument('--reference-limit',type=int,default=200)
    parser.add_argument('--patience',type=int,default=2)
    parser.add_argument('--min-new',type=int,default=1)
    parser.add_argument('--max-sources',type=int,default=3)
    parser.add_argument('--time-budget',type=float,default=180)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--sources-only',action='store_true',help='Fetch routed official pages without PubMed queries')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    spec=json.loads(args.profile.read_text(encoding='utf-8-sig'))
    index=MeshIndex(args.mesh_index) if args.mesh_index and not args.sources_only else None
    registry=json.loads(args.registry.read_text(encoding='utf-8-sig')) if args.registry else None
    if args.sources_only:
        if args.max_sources<0 or args.time_budget<=0:
            parser.error('Source budget must be nonnegative and time budget positive')
        routed=route_sources(spec,registry,limit=args.max_sources)
        pages=[]
        start=time.monotonic()
        if not args.dry_run:
            for source in routed:
                remaining=args.time_budget-(time.monotonic()-start)
                if remaining<=0:break
                pages.append(fetch_source(source,timeout=min(20,remaining),
                             cache_dir=args.output.parent/'source_pages' if args.output else None))
        result={'status':'sources_ready' if args.dry_run or any(p.get('status')=='ok' for p in pages) else 'source_access_incomplete',
                'original_question':spec['original_question'],'source_routes':routed,
                'institutional_sources':pages,'executed':not args.dry_run,'research_verified':False}
    elif args.dry_run:
        result={'plan':build_plan(spec,index,expansion=args.expansion,engine=args.engine),'strategy':args.strategy,
                'source_routes':route_sources(spec,registry,limit=args.max_sources),'executed':False}
    else:
        result=run_research(spec,index,registry=registry,max_queries=args.max_queries,
                            limit=args.limit,patience=args.patience,min_new=args.min_new,
                            max_sources=args.max_sources,timeout_seconds=args.time_budget,
                            source_cache=args.output.parent/'source_pages' if args.output else None,
                            expansion=args.expansion,strategy=args.strategy,
                            query_cache=args.query_cache,cache_ttl=args.cache_ttl,refresh_cache=args.refresh_cache,
                            reference_seeds=args.reference_seeds,reference_limit=args.reference_limit,
                            max_result_slots=args.max_result_slots,engine=args.engine)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(args.output.resolve()),'status':result.get('status','plan_ready'),
                          'queries_executed':len(result.get('query_runs',[])),
                          'inspectable_candidates':result.get('inspectable_candidate_count',0)},ensure_ascii=False))
    else:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result.get('status')=='retrieval_failed' else 0


if __name__=='__main__':
    raise SystemExit(main())
