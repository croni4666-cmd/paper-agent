"""M4 offline Jev contract, routing and budget primitives.

Schema checked against https://api.typesafe.ai/openapi.json on 2026-09-26.
No transport is shipped here: estimated tokens cannot enforce vendor billing.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from threading import RLock

from .evidence import _hash

SCHEMA_VERSION = 'jev-openapi-0.2.0-2026-09-26'


def _finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def _prob(value):
    if not _finite(value) or not 0 <= value <= 1:
        raise ValueError('invalid probability')
    return float(value)


def _questions(questions):
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 20:
        raise ValueError('one to twenty named questions required')
    for name, q in questions.items():
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or not isinstance(q, dict):
            raise ValueError('invalid named question')
        if set(q) - {'type','criteria','instructions'}:
            raise ValueError('unsupported question fields')
        kind, criteria = q.get('type'), q.get('criteria')
        descriptions=[q.get('instructions')]
        if kind == 'noul':
            if criteria is not None and (not isinstance(criteria, dict) or set(criteria)-{'true','false'}):
                raise ValueError('invalid noul criteria')
            descriptions.extend((criteria or {}).values())
        elif kind == 'choice':
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 20 or any(not isinstance(k,str) or not k for k in criteria):
                raise ValueError('choice needs distinct named alternatives')
            descriptions.extend(criteria.values())
        elif kind == 'score':
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 20 or any(c is None for c in criteria):
                raise ValueError('score needs ordered non-null criteria')
            descriptions.extend(criteria)
        else:
            raise ValueError('unsupported answer type')
        if any(v is not None and not isinstance(v,(str,dict,list)) for v in descriptions):
            raise ValueError('question descriptions must be text, object, list or permitted null')
    # Reject non-JSON objects/NaN and constrain the local rubric envelope.
    if len(json.dumps(questions, allow_nan=False).encode()) > 16000:
        raise ValueError('question envelope too large')


def prepare_request(packet, questions, model):
    """Construct a minimal payload only; never grants dispatch authorization."""
    _questions(questions)
    if not isinstance(model, str) or not 1 <= len(model) <= 100:
        raise ValueError('explicit model required')
    if packet.get('packet_hash') != _hash({k:v for k,v in packet.items() if k != 'packet_hash'}):
        raise ValueError('packet integrity mismatch')
    evidence = packet.get('evidence')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 6:
        raise ValueError('one to six passages required')
    passages=[]
    for item in evidence:
        if not isinstance(item.get('text'),str) or not item['text'].strip() or not isinstance(item.get('evidence_id'),str):
            raise ValueError('invalid evidence passage')
        passages.append({'id':item['evidence_id'],'text':item['text']})
    result={'model':model,'questions':questions,'state':{'passages':passages}}
    encoded=json.dumps(result,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode('utf-8'))>32000:
        raise ValueError('request envelope too large')
    return json.loads(encoded)


def _distribution(raw, keys):
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise ValueError('probability keys do not match criteria')
    values={k:_prob(v) for k,v in raw.items()}
    if abs(sum(values.values())-1)>1e-4:
        raise ValueError('probabilities do not sum to one')
    return values


def validate_response(response, questions):
    """Normalize official fields; fail closed on missing, inconsistent answers."""
    _questions(questions)
    try:
        model=response['model']
        if not isinstance(model,str) or not 1 <= len(model) <= 200:
            raise ValueError('missing returned model')
        usage=response['usage']
        for key in ('input_tokens','output_tokens'):
            if type(usage[key]) is not int or usage[key]<0:
                raise ValueError('invalid token usage')
        answers=response['answers']
        if not isinstance(answers,dict) or set(answers)!=set(questions):
            raise ValueError('answer names do not match questions')
        normalized={}
        for name,q in questions.items():
            a=answers[name]
            kind=q['type']
            if a['type']!=kind:
                raise ValueError('answer type mismatch')
            if kind=='noul':
                normalized[name]={'type':kind,'p_yes':_prob(a['noul'])}
                continue
            confidence=_prob(a['confidence'])
            keys=q['criteria'] if kind=='choice' else [str(i) for i in range(len(q['criteria']))]
            probs=_distribution(a['probabilities'],keys)
            if kind=='choice':
                selected=a['choice']
                if selected not in probs or probs[selected] < max(probs.values()):
                    raise ValueError('selected choice contradicts probabilities')
                normalized[name]={'type':kind,'choice':selected,'probabilities':probs,'confidence':confidence}
            else:
                legend={str(i):c for i,c in enumerate(q['criteria'])}
                if a['legend']!=legend:
                    raise ValueError('score legend differs from requested rubric')
                expected=sum(int(k)*p for k,p in probs.items())
                if not _finite(a['score']) or abs(a['score']-expected)>1e-3:
                    raise ValueError('score differs from expected value')
                normalized[name]={'type':kind,'score':expected,'probabilities':probs,
                                  'legend':legend,'confidence':confidence}
        return {'model':model,'answers':normalized,
                'usage':{k:usage[k] for k in ('input_tokens','output_tokens')},
                'schema_version':SCHEMA_VERSION}
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('malformed Jev response') from exc


def route_answer(answer, *, score_boundary=None, fallback_authorized=False,
                 high_stakes=False, conflicting_evidence=False):
    """Route already validated answers. Never approves claims or excludes papers."""
    high=False
    try:
        if answer['type']=='noul':
            p=_prob(answer['p_yes'])
            high=p>=0.9 or p<=0.1
        elif answer['type']=='choice':
            probs=sorted((_prob(p) for p in answer['probabilities'].values()),reverse=True)
            high=len(probs)>=2 and probs[0]>=0.9 and probs[0]-probs[1]>=0.2
        elif answer['type']=='score' and _finite(score_boundary):
            probs=answer['probabilities']
            levels=[int(k) for k in probs]
            if min(levels)<score_boundary<=max(levels):
                mass=sum(_prob(p) for k,p in probs.items() if int(k)>=score_boundary)
                high=mass>=0.9 or mass<=0.1
    except (KeyError,TypeError,ValueError):
        return {'route':'human_review','automatic_decision_allowed':False}
    if high_stakes or conflicting_evidence:
        route='human_review'
    elif high:
        route='triage_suggestion'
    else:
        route='gpt_review_pending' if fallback_authorized else 'human_review'
    return {'route':route,'automatic_decision_allowed':False}


@dataclass(frozen=True)
class Price:
    model: str
    usd_per_million_input: str
    checked_at: datetime
    source_url: str


class Budget:
    """Single-process dry-run reservations, not a vendor hard billing cap.

    Unknown usage remains reserved. No retries. Persistence and transport wiring
    must be implemented before paid dispatch. Caller estimates are not token counts.
    """
    def __init__(self, price, *, max_papers=25, max_input_tokens=100000,
                 max_cost_usd='0.01', now=None):
        self._lock=RLock()
        self.price=price
        now=now or datetime.now(timezone.utc)
        if (not isinstance(price.checked_at,datetime) or price.checked_at.tzinfo is None
                or not timedelta(0)<=now-price.checked_at<=timedelta(days=7)):
            raise ValueError('missing, future or stale price timestamp')
        if not price.model or not price.source_url.startswith('https://'):
            raise ValueError('model and price source required')
        try:
            self.rate=Decimal(str(price.usd_per_million_input))/Decimal(1000000)
            self.max_cost=Decimal(str(max_cost_usd))
        except InvalidOperation as exc:
            raise ValueError('invalid cost configuration') from exc
        if not self.rate.is_finite() or self.rate<=0 or not self.max_cost.is_finite() or self.max_cost<=0:
            raise ValueError('positive finite prices and cap required')
        if type(max_papers) is not int or max_papers<=0 or type(max_input_tokens) is not int or max_input_tokens<=0:
            raise ValueError('positive run limits required')
        self.max_papers=max_papers
        self.max_tokens=max_input_tokens
        self.records={}
        self.halted=False

    @property
    def input_tokens_committed(self):
        with self._lock:
            return sum(r['tokens'] for r in self.records.values())

    @property
    def cost_committed(self):
        return self.rate*self.input_tokens_committed

    def reserve(self, request_id, estimated_input_tokens):
        with self._lock:
            if not isinstance(request_id,str) or not request_id or request_id in self.records:
                raise ValueError('request ID must be new and nonempty; no automatic retry')
            if type(estimated_input_tokens) is not int or estimated_input_tokens<=0:
                raise ValueError('positive input token estimate required')
            total=self.input_tokens_committed+estimated_input_tokens
            if self.halted or len(self.records)>=self.max_papers or total>self.max_tokens or self.rate*total>self.max_cost:
                raise ValueError('run budget exhausted or halted')
            self.records[request_id]={'tokens':estimated_input_tokens,'status':'reserved'}

    def mark_unknown(self, request_id):
        with self._lock:
            if self.records[request_id]['status']!='reserved':
                raise ValueError('reservation is not pending')
            self.records[request_id]['status']='unknown'

    def reconcile(self, request_id, actual_input_tokens):
        with self._lock:
            if type(actual_input_tokens) is not int or actual_input_tokens<0:
                raise ValueError('invalid actual input usage')
            record=self.records[request_id]
            if record['status']!='reserved':
                raise ValueError('only pending reservations can be reconciled')
            overrun=actual_input_tokens>record['tokens']
            record.update(tokens=actual_input_tokens,status='reconciled')
            self.halted= self.halted or overrun or self.input_tokens_committed>self.max_tokens or self.cost_committed>self.max_cost


def dry_run(packet, questions, model, fixture_response, *, budget,
            estimated_input_tokens, rubric_version, score_boundaries=None,
            fallback_authorized=False, high_stakes=False, conflicting_evidence=False):
    """Exercise the adapter with supplied synthetic data. Does not call a provider.

    This deliberately cannot be used to dispatch paid requests. M3 provenance,
    passage privacy review, persistent reservations and consent are still needed
    before adding network transport. No key is accepted or loaded.
    """
    if model != budget.price.model:
        raise ValueError('price model does not match requested model')
    if not isinstance(rubric_version,str) or not rubric_version.strip():
        raise ValueError('explicit rubric version required')
    request=prepare_request(packet,questions,model)
    request_id=_hash([SCHEMA_VERSION,request,packet['packet_hash'],rubric_version])
    budget.reserve(request_id,estimated_input_tokens)
    common={'request_id':request_id,'requested_model':model,'rubric_version':rubric_version,
            'packet_hash':packet['packet_hash'],'synthetic':True,'external_upload_allowed':False}
    if fixture_response is None:
        budget.mark_unknown(request_id)
        return {**common,'status':'unknown','routes':{name:{'route':'human_review'} for name in questions}}
    # Even an invalid answer may have consumed tokens. Account for known usage
    # before validating answer content; otherwise retain the full reservation.
    try:
        usage=fixture_response['usage']['input_tokens']
        if type(usage) is not int or usage<0:
            raise ValueError('invalid usage')
    except (KeyError,TypeError,ValueError):
        budget.mark_unknown(request_id)
        return {**common,'status':'unknown','routes':{name:{'route':'human_review'} for name in questions}}
    budget.reconcile(request_id,usage)
    try:
        response=validate_response(fixture_response,questions)
    except ValueError:
        return {**common,'status':'invalid_response','routes':{name:{'route':'human_review'} for name in questions}}
    boundaries=score_boundaries or {}
    routes={name:route_answer(answer,score_boundary=boundaries.get(name),
                             fallback_authorized=fallback_authorized,
                             high_stakes=high_stakes or budget.halted,
                             conflicting_evidence=conflicting_evidence)
            for name,answer in response['answers'].items()}
    return {**common,'status':'budget_overrun' if budget.halted else 'completed',
            'response':response,'routes':routes,
            'input_cost_usd':str(budget.rate*usage)}
