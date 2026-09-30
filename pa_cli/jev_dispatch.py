"""M4 explicit-consent dispatch and persistent per-run budgets.

No calls occur on import. Live transport requires a caller-provided API key and
fresh approval of the exact minimized payload and configured estimated caps.
"""
from __future__ import annotations

import json
import math
import multiprocessing as mp
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from .evidence import _hash
from .jev import Budget, SCHEMA_VERSION, prepare_request, validate_response, route_answer
from .provenance import inspect_artifact
from .shadow import _check_packet

ENDPOINT='https://api.typesafe.ai/v1/systemone'
APP_ID=1346458452
MAX_RESPONSE=1024*1024


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)


@dataclass(frozen=True)
class Approval:
    run_id: str
    reviewed_request_hash: str
    upload_authorized: bool
    estimated_cost_risk_accepted: bool
    expires_at: datetime
    max_papers: int=25
    max_input_tokens: int=100000
    max_cost_usd: str='0.01'
    pilot_approval_attested: bool=False
    retry_of: str | None=None


class Ledger:
    """Separate dispatch DB, never the human sample pool or M3 synthetic DB."""
    def __init__(self,path):
        self.conn=sqlite3.connect(str(path),timeout=10)
        try:
            app=self.conn.execute('PRAGMA application_id').fetchone()[0]
            tables=self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if (tables or app) and app!=APP_ID:
                raise ValueError('use a dedicated Jev dispatch database')
            self.conn.execute('PRAGMA foreign_keys=ON')
            self.conn.executescript(f'''
                PRAGMA application_id={APP_ID};
                CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, config TEXT NOT NULL, halted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),
                    snapshot TEXT NOT NULL,tokens INTEGER NOT NULL,status TEXT NOT NULL,result TEXT);
                CREATE TABLE IF NOT EXISTS events(event_id INTEGER PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(request_id),
                    created_at TEXT NOT NULL,status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS retry_links(
                    child_request_id TEXT PRIMARY KEY REFERENCES requests(request_id),
                    parent_request_id TEXT NOT NULL UNIQUE REFERENCES requests(request_id));
                CREATE TRIGGER IF NOT EXISTS retry_links_no_update BEFORE UPDATE ON retry_links BEGIN
                    SELECT RAISE(ABORT,'immutable retry link'); END;
                CREATE TRIGGER IF NOT EXISTS retry_links_no_delete BEFORE DELETE ON retry_links BEGIN
                    SELECT RAISE(ABORT,'immutable retry link'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN
                    SELECT RAISE(ABORT,'append-only event'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN
                    SELECT RAISE(ABORT,'append-only event'); END;
            ''')
            self.conn.commit()
        except Exception:
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def event(self,request_id,status):
        self.conn.execute('INSERT INTO events(request_id,created_at,status) VALUES(?,?,?)',
                          (request_id,datetime.now(timezone.utc).isoformat(),status))

    def claim(self,run_id,config,request_id,snapshot,tokens):
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            run=self.conn.execute('SELECT config,halted FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if run and run[0]!=_json(config):
                raise ValueError('run limits/price are immutable; cannot reset an existing run')
            if not run:
                self.conn.execute('INSERT INTO runs(run_id,config) VALUES(?,?)',(run_id,_json(config)))
            row=self.conn.execute('SELECT status,result FROM requests WHERE request_id=?',(request_id,)).fetchone()
            if row:
                return json.loads(row[1]) if row[1] else {'request_id':request_id,'status':'unknown','reason':'pending_or_interrupted; no automatic retry'}
            if run and run[1]:
                raise ValueError('run halted after unknown outcome or overrun')
            parent_id = snapshot.get('retry_of')
            if parent_id is not None:
                parent = self.conn.execute('SELECT run_id,status,snapshot FROM requests WHERE request_id=?',
                                           (parent_id,)).fetchone()
                if (not parent or parent[0] != run_id
                        or parent[1] not in ('invalid_response', 'usage_reconciled', 'preflight_expired')):
                    raise ValueError('retry requires a settled eligible parent in the same run')
                prior_snapshot = json.loads(parent[2])
                if any(prior_snapshot.get(key) != snapshot.get(key) for key in
                       ('request', 'packet_hash', 'rubric_version', 'routing_policy')):
                    raise ValueError('retry must preserve the parent payload and evaluation policy')
            count,committed,pending=self.conn.execute(
                "SELECT count(*),coalesce(sum(tokens),0),coalesce(sum(status='pending'),0) FROM requests WHERE run_id=?",(run_id,)).fetchone()
            if pending:
                raise ValueError('run has an unresolved reservation; wait or resolve manually')
            if (count>=config['max_papers'] or committed+tokens>config['max_input_tokens']
                    or Decimal(config['rate'])*(committed+tokens)>Decimal(config['max_cost_usd'])):
                raise ValueError('run budget exhausted')
            self.conn.execute('INSERT INTO requests VALUES(?,?,?,?,?,NULL)',
                              (request_id,run_id,_json(snapshot),tokens,'pending'))
            if parent_id is not None:
                self.conn.execute('INSERT INTO retry_links VALUES(?,?)', (request_id, parent_id))
                self.event(request_id, _json({'event': 'explicit_linked_retry', 'retry_of': parent_id}))
            self.event(request_id,'reserved_before_dispatch')
        return None

    def begin_send(self, request_id):
        """Final local send gate; quarantine is not cancellation of in-flight HTTP."""
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            row = self.conn.execute(
                'SELECT q.status,q.result,r.halted FROM requests q JOIN runs r ON q.run_id=r.run_id WHERE q.request_id=?',
                (request_id,)).fetchone()
            if row is None:
                raise ValueError('request not found')
            if row[0] != 'pending' or row[2]:
                return json.loads(row[1]) if row[1] else {
                    'request_id': request_id, 'status': 'unknown', 'reason': 'run_halted_before_send'}
            self.event(request_id, 'dispatch_started')
        return None

    def settle(self,request_id,result,actual_tokens=None,halt=False):
        if actual_tokens is not None and (type(actual_tokens) is not int or actual_tokens < 0):
            raise ValueError('invalid actual usage')
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            row=self.conn.execute('SELECT run_id,tokens,status,result FROM requests WHERE request_id=?',(request_id,)).fetchone()
            previous = json.loads(row[3]) if row and row[3] else {}
            reconciled_interruption = (row and row[2] == 'usage_reconciled'
                                      and previous.get('reconciliation', {}).get('previous_status') == 'interrupted')
            if not row or (row[2] not in ('pending', 'interrupted') and not reconciled_interruption):
                raise ValueError('request is not pending')
            tokens=row[1] if actual_tokens is None else actual_tokens
            if row[2] == 'interrupted' or reconciled_interruption:
                if reconciled_interruption:
                    reservation = previous['reconciliation']['previous_accounted_tokens']
                    tokens = max(row[1], reservation if actual_tokens is None else actual_tokens)
                late = dict(event='late_result_after_quarantine', previous_status=row[2],
                            previous_accounted_tokens=row[1], reported_input_tokens=actual_tokens,
                            retained_input_tokens=tokens, observed_status=result['status'])
                if reconciled_interruption:
                    late['prior_reconciliation'] = previous['reconciliation']
                    result['prior_reconciliation'] = previous['reconciliation']
                result.update(status='late_result_review', late_result=late,
                              automatic_decision_allowed=False, run_halted=True,
                              accounted_input_tokens=tokens)
                result.pop('input_cost_usd', None)
                result['routes'] = {name: {'route': 'human_review', 'automatic_decision_allowed': False}
                                    for name in result.get('routes', {})}
                self.conn.execute('UPDATE runs SET halted=1 WHERE run_id=?', (row[0],))
                self.conn.execute('UPDATE requests SET tokens=?,status=?,result=? WHERE request_id=?',
                                  (tokens, result['status'], _json(result), request_id))
                self.event(request_id, _json(late))
                return result
            overrun=actual_tokens is not None and actual_tokens>row[1]
            if overrun:
                result['status']='budget_overrun'
                result['routes']={name:{'route':'human_review','automatic_decision_allowed':False}
                                  for name in result.get('routes',{})}
            if halt or overrun or actual_tokens is None:
                self.conn.execute('UPDATE runs SET halted=1 WHERE run_id=?',(row[0],))
            self.conn.execute('UPDATE requests SET tokens=?,status=?,result=? WHERE request_id=?',
                              (tokens,result['status'],_json(result),request_id))
            self.event(request_id,result['status'])
        return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def _http_worker(pipe,payload,key,timeout):
    try:
        request=urllib.request.Request(ENDPOINT,data=_json(payload).encode('utf-8'),
                    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
        with opener.open(request,timeout=timeout) as response:
            body=response.read(MAX_RESPONSE+1)
        if len(body)>MAX_RESPONSE:
            raise ValueError('response_size_limit')
        pipe.send(('ok',json.loads(body)))
    except Exception as exc:
        # Do not return server bodies, URLs, keys, or exception text.
        pipe.send(('error',type(exc).__name__))
    finally:
        pipe.close()


def send_request(payload,api_key,timeout=30):
    """One POST, fixed TLS origin, no redirects/proxy/retry; bounded worker life."""
    if not isinstance(api_key,str) or not api_key.strip() or any(c in api_key for c in '\r\n'):
        raise ValueError('valid explicit API key required')
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=120:
        raise ValueError('timeout must be 0..120 seconds')
    ctx=mp.get_context('spawn')
    reader,writer=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_http_worker,args=(writer,payload,api_key,timeout),daemon=True)
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout):
            raise TimeoutError('provider_deadline')
        status,value=reader.recv()
        if status!='ok':
            raise RuntimeError('provider_request_failed')
        return value
    finally:
        reader.close()
        writer.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(2)


def validate_routing_policy(questions, score_boundaries=None, critical_score_levels=None,
                            fallback_authorized=False):
    """Validate the same local routing policy in preflight and actual dispatch."""
    critical_score_levels = {} if critical_score_levels is None else critical_score_levels
    score_boundaries = {} if score_boundaries is None else score_boundaries
    if (type(fallback_authorized) is not bool or not isinstance(score_boundaries, dict)
            or not isinstance(critical_score_levels, dict)):
        raise ValueError('routing maps and explicit fallback boolean required')
    for name, levels in critical_score_levels.items():
        q = questions.get(name, {})
        if (q.get('type') != 'score' or not isinstance(levels, list)
                or any(type(level) is not int or not 0 <= level < len(q['criteria']) for level in levels)):
            raise ValueError('invalid critical score levels')
    for name, boundary in score_boundaries.items():
        q = questions.get(name, {})
        if (q.get('type') != 'score' or type(boundary) not in (int, float)
                or not math.isfinite(boundary) or not 0 < boundary <= len(q['criteria']) - 1):
            raise ValueError('invalid score action boundary')
    return {'score_boundaries': score_boundaries, 'critical_score_levels': critical_score_levels,
            'fallback_authorized': fallback_authorized}


def dispatch(*,pdf,index,packet,questions,fetch_result,price,run_id,approval,db_path,
             api_key,estimated_input_tokens,rubric_version,data_class='unknown',
             expected_title=None,max_papers=25,max_input_tokens=100000,max_cost_usd='0.01',
             transport=None,timeout=30,score_boundaries=None,high_stakes=False,
             conflicting_evidence=False,critical_score_levels=None,fallback_authorized=False,retry_of=None):
    """Explicit opt-in API used by the approval CLI. Injected transport is synthetic.

    Approval must be created by the trusted caller only after the user reviews
    the exact payload and caps. This dataclass is not an authentication mechanism.
    """
    now=datetime.now(timezone.utc)
    if retry_of is not None and (not isinstance(retry_of, str) or not retry_of.strip() or len(retry_of)>200):
        raise ValueError('bounded parent request ID required')
    budget=Budget(price,max_papers=max_papers,max_input_tokens=max_input_tokens,max_cost_usd=max_cost_usd,now=now)
    if not isinstance(run_id,str) or not run_id.strip() or not isinstance(rubric_version,str) or not rubric_version.strip():
        raise ValueError('run ID and rubric version required')
    if type(estimated_input_tokens) is not int or estimated_input_tokens<=0:
        raise ValueError('positive token estimate required')
    if not isinstance(api_key,str) or not api_key.strip() or '\r' in api_key or '\n' in api_key:
        raise ValueError('explicit API key required')
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=120:
        raise ValueError('invalid timeout')
    if Path(pdf).resolve()==Path(db_path).resolve():
        raise ValueError('database cannot be source PDF')
    index,packet,questions=json.loads(_json([index,packet,questions]))
    _check_packet(index,packet)
    request=prepare_request(packet,questions,price.model)
    routing_policy=validate_routing_policy(questions,score_boundaries,critical_score_levels,fallback_authorized)
    critical_score_levels=routing_policy['critical_score_levels']
    score_boundaries=routing_policy['score_boundaries']
    if (not isinstance(approval,Approval) or approval.upload_authorized is not True
            or approval.estimated_cost_risk_accepted is not True or approval.run_id!=run_id
            or approval.reviewed_request_hash!=_hash(request)
            or approval.retry_of!=retry_of
            or not isinstance(approval.expires_at,datetime) or approval.expires_at.tzinfo is None
            or not timedelta(0)<approval.expires_at-now<=timedelta(minutes=15)
            or approval.max_papers!=max_papers or approval.max_input_tokens!=max_input_tokens
            or str(approval.max_cost_usd)!=str(max_cost_usd)):
        raise ValueError('fresh authorization of exact payload and estimated caps required')
    source=fetch_result.get('via_channel','').removeprefix('cache:')
    provenance=inspect_artifact(pdf,fetch_result['doi'],source,fetch_result.get('via_url'),
                                expected_title=expected_title,data_class=data_class)
    if (provenance['artifact_sha256']!=index['artifact_sha256']
            or not provenance['external_evaluation_candidate']
            or packet.get('status')!='ready_for_local_review' or packet.get('missing_sections')
            or any(p['status']!='text_extracted' for p in index['pages'])
            or high_stakes or conflicting_evidence):
        raise ValueError('artifact, provenance, extraction or human-review gate failed')
    synthetic=transport is not None
    mode='injected-test-transport' if synthetic else 'typesafe-fixed-https'
    request_id=_hash([SCHEMA_VERSION,request,packet['packet_hash'],rubric_version,mode,routing_policy])
    if retry_of is not None:
        request_id=_hash([request_id, 'explicit_retry', retry_of])
    config={'model':price.model,'rate':str(budget.rate),'checked_at':price.checked_at.isoformat(),
            'price_source':price.source_url,'max_papers':max_papers,'max_input_tokens':max_input_tokens,
            'max_cost_usd':str(max_cost_usd),'mode':mode}
    snapshot={'request':request,'packet_hash':packet['packet_hash'],'provenance':provenance,
              'rubric_version':rubric_version,'approval_expires':approval.expires_at.isoformat(),
              'approved_request_hash':approval.reviewed_request_hash,'config':config,'routing_policy':routing_policy,
              'pilot_approval_attested':approval.pilot_approval_attested is True, 'retry_of':retry_of}
    ledger=Ledger(db_path)
    try:
        prior=ledger.claim(run_id,config,request_id,snapshot,estimated_input_tokens)
        if prior is not None:
            return prior
        base={'request_id':request_id,'requested_model':price.model,'synthetic':synthetic,
              'automatic_decision_allowed':False}
        if retry_of is not None:
            base['retry_of']=retry_of
        stopped = ledger.begin_send(request_id)
        if stopped is not None:
            return stopped
        send_time=datetime.now(timezone.utc)
        if (send_time>=approval.expires_at
                or not timedelta(0)<=send_time-price.checked_at<=timedelta(days=7)):
            return ledger.settle(request_id,{**base,'status':'preflight_expired'},0)
        try:
            raw=(transport or send_request)(request,api_key,timeout)
        except Exception as exc:
            return ledger.settle(request_id,{**base,'status':'unknown','error_type':type(exc).__name__})
        try:
            actual=raw['usage']['input_tokens']
            if type(actual) is not int or actual<0:
                raise ValueError('invalid usage')
        except (KeyError,TypeError,ValueError):
            return ledger.settle(request_id,{**base,'status':'unknown','reason':'usage_unavailable'})
        base.update(input_tokens=actual,input_cost_usd=str(budget.rate*actual))
        try:
            response=validate_response(raw,questions)
        except ValueError:
            return ledger.settle(request_id,{**base,'status':'invalid_response'},actual)
        if response['model']!=price.model:
            return ledger.settle(request_id,{**base,'status':'model_price_unverified',
                                             'returned_model':response['model']},actual,halt=True)
        routes={name:route_answer(answer,score_boundary=score_boundaries.get(name),
                                 fallback_authorized=fallback_authorized,
                                 high_stakes=any(answer.get('probabilities',{}).get(str(level),0)>0
                                                 for level in critical_score_levels.get(name,[])))
                for name,answer in response['answers'].items()}
        return ledger.settle(request_id,{**base,'status':'completed','response':response,'routes':routes},actual)
    finally:
        ledger.close()
