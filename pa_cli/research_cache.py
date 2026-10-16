"""Opt-in exact-response research cache; failures and other depths are never reused."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

PROTOCOL = 'public-search-metadata-v4-exact-depth-1'


class CachedSearch:
    def __init__(self, searcher, directory: Path, *, ttl_seconds: float = 86400,
                 refresh: bool = False, clock=time.time):
        if not math.isfinite(ttl_seconds) or ttl_seconds<=0:
            raise ValueError('Cache TTL must be positive and finite')
        self.searcher=searcher
        self.directory=Path(directory)
        self.ttl_seconds=ttl_seconds
        self.refresh=refresh
        self.clock=clock

    @staticmethod
    def _valid(response, engine='pubmed'):
        if not isinstance(response,dict) or not isinstance(response.get('results'),list):return False
        engines=response.get('engine_status')
        state=engines.get(engine) if isinstance(engines,dict) else None
        return (isinstance(state,dict) and state.get('status')=='ok'
                and all(isinstance(paper,dict) for paper in response['results']))

    def __call__(self, query, **kwargs):
        # Preserve actual query text and every result-affecting option. A
        # transport deadline cannot change which cached document set was asked.
        request={'protocol':PROTOCOL,'query':query,
                 'options':{k:v for k,v in kwargs.items() if k!='engine_timeout'}}
        encoded=json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        key=hashlib.sha256(encoded.encode('utf-8')).hexdigest()
        path=self.directory/(key+'.json')
        now=self.clock()
        if not self.refresh:
            try:
                entry=json.loads(path.read_text(encoding='utf-8'))
                stamp=entry['retrieved_at']
                if (entry.get('request')==request and isinstance(stamp,(int,float))
                        and 0<=now-stamp<self.ttl_seconds and self._valid(entry.get('response'),kwargs.get('engine','pubmed'))):
                    result=deepcopy(entry['response'])
                    result['cache']={'state':'hit','key':key,'retrieved_at':stamp,'read_at':now}
                    return result
            except (OSError,ValueError,KeyError,TypeError):
                pass
        result=self.searcher(query,**kwargs)
        if not isinstance(result,dict):return result
        result=deepcopy(result)
        state='refresh' if self.refresh else 'miss'
        if self._valid(result,kwargs.get('engine','pubmed')):
            temporary=None
            try:
                self.directory.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.directory,
                                                  prefix='.query-',suffix='.tmp',delete=False) as stream:
                    temporary=Path(stream.name)
                    json.dump({'request':request,'retrieved_at':now,'response':result},stream,ensure_ascii=False)
                os.replace(temporary,path)
            except (OSError,ValueError,TypeError):
                state='write_error'
            finally:
                if temporary and temporary.exists():
                    try:temporary.unlink()
                    except OSError:pass
        else:
            state='not_cacheable'
        result['cache']={'state':state,'key':key,'retrieved_at':now,'read_at':now}
        return result
