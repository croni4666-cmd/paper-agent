"""Offline dispatch tests, real SQLite and PDF; transport is injected."""
import sys
import tempfile
import unittest
import json
import io
import time
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf
from pa_cli.evidence import build_index,build_packet,_hash
from pa_cli.jev import prepare_request,Price


def slow_transport_worker(pipe,payload,key,timeout):
    time.sleep(2)
    pipe.close()


class RecordingPipe:
    def send(self,result):
        self.result=result
    def close(self):
        pass


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.pdf=self.root/'p.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72,72),'Results\nEmployment increased.')
            doc.set_xml_metadata('''<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:RDF><rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:cc="http://creativecommons.org/ns#"><prism:doi>10.1234/study</prism:doi><cc:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/></rdf:Description></rdf:RDF></x:xmpmeta>''')
            doc.save(self.pdf)
        self.index=build_index(self.pdf)
        self.packet=build_packet(self.index,'employment')
        self.q={'support':{'type':'noul','instructions':'Supported?'}}
        self.now=datetime.now(timezone.utc)
        self.price=Price('jev-test','0.042',self.now,'https://typesafe.ai/pricing')
        self.response={'model':'jev-test','answers':{'support':{'type':'noul','noul':0.95}},'usage':{'input_tokens':80,'output_tokens':3}}
        self.calls=0

    def dispatch(self,**updates):
        from pa_cli.jev_dispatch import dispatch,Approval
        request=prepare_request(self.packet,self.q,'jev-test')
        approval=Approval('run-1',_hash(request),True,True,self.now+timedelta(minutes=5),
                          max_input_tokens=updates.get('max_input_tokens',200))
        def transport(payload,key,timeout):
            self.calls+=1
            return self.response
        args=dict(pdf=self.pdf,index=self.index,packet=self.packet,questions=self.q,
                  fetch_result={'doi':'10.1234/study','via_channel':'pmc','via_url':'https://europepmc.org/articles/PMC1?pdf=render'},
                  price=self.price,run_id='run-1',approval=approval,db_path=self.root/'dispatch.sqlite',
                  api_key='offline-test-key',estimated_input_tokens=100,rubric_version='v1',
                  data_class='public',transport=transport,max_input_tokens=200)
        args.update(updates)
        return dispatch(**args)

    def test_request_is_persisted_and_replayed_without_second_send(self):
        a=self.dispatch()
        b=self.dispatch()
        self.assertEqual(a['status'],'completed')
        self.assertEqual(a,b)
        self.assertEqual(self.calls,1)

    def test_unknown_holds_budget_and_halts_run_after_restart(self):
        def broken(*args):
            raise TimeoutError('secret text')
        result=self.dispatch(transport=broken)
        self.assertEqual(result['status'],'unknown')
        self.assertNotIn('secret text',str(result))
        self.assertEqual(self.dispatch()['status'],'unknown')
        self.q['support']['instructions']='Another request'
        with self.assertRaises(ValueError):
            self.dispatch()
        self.assertEqual(self.calls,0)

    def test_concurrent_duplicate_has_one_send(self):
        # Initialize schema before racing reservations (also exercised on every call).
        from pa_cli.jev_dispatch import Ledger
        Ledger(self.root/'dispatch.sqlite').close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.dispatch(),range(2)))
        self.assertEqual(self.calls,1)
        self.assertIn('completed',[r['status'] for r in results])

    def test_authorization_hash_and_expiry_are_checked_before_send(self):
        from pa_cli.jev_dispatch import Approval
        for approval in [None,Approval('run-1','wrong',True,True,self.now+timedelta(minutes=1)),
                         Approval('run-1',_hash(prepare_request(self.packet,self.q,'jev-test')),True,True,self.now-timedelta(seconds=1))]:
            with self.assertRaises(ValueError):
                self.dispatch(approval=approval)
        self.assertEqual(self.calls,0)

    def test_budget_caps_cannot_be_reset_by_reopening_run(self):
        self.dispatch()
        self.q['support']['instructions']='New question'
        with self.assertRaises(ValueError):
            self.dispatch(max_input_tokens=1000)

    def test_private_and_changed_artifact_never_send(self):
        with self.assertRaises(ValueError):
            self.dispatch(data_class='unpublished')
        self.pdf.write_bytes(self.pdf.read_bytes()+b'\n% changed')
        with self.assertRaises(ValueError):
            self.dispatch()
        self.assertEqual(self.calls,0)

    def test_actual_overrun_is_recorded_and_halts_run(self):
        self.response['usage']['input_tokens']=201
        result=self.dispatch()
        self.assertEqual(result['status'],'budget_overrun')
        self.q['support']['instructions']='new'
        with self.assertRaises(ValueError):
            self.dispatch()

    def test_malformed_answer_accounts_known_usage(self):
        self.response['answers']['support']['noul']=2
        result=self.dispatch()
        self.assertEqual(result['status'],'invalid_response')
        self.assertEqual(result['input_tokens'],80)

    def test_stale_price_rejected_before_send(self):
        stale=Price('jev-test','0.042',self.now-timedelta(days=8),'https://typesafe.ai/pricing')
        with self.assertRaises(ValueError):
            self.dispatch(price=stale)
        self.assertEqual(self.calls,0)

    def test_transport_serializes_fixed_request_and_rejects_redirect_handler(self):
        from pa_cli.jev_dispatch import _http_worker,ENDPOINT,_NoRedirect
        pipe=RecordingPipe()
        captured=[]
        class Opener:
            def open(inner,request,timeout):
                captured.append(request)
                return io.BytesIO(json.dumps(self.response).encode())
        with patch('pa_cli.jev_dispatch.urllib.request.build_opener',return_value=Opener()) as factory:
            _http_worker(pipe,{'model':'jev-test'},'secret-key',1)
        self.assertEqual(pipe.result[0],'ok')
        self.assertEqual(captured[0].full_url,ENDPOINT)
        self.assertEqual(captured[0].method,'POST')
        self.assertEqual(json.loads(captured[0].data),{'model':'jev-test'})
        self.assertTrue(any(isinstance(h,_NoRedirect) for h in factory.call_args.args))
        handler=next(h for h in factory.call_args.args if isinstance(h,_NoRedirect))
        self.assertIsNone(handler.redirect_request(captured[0],None,302,'redirect',{},'https://other.test'))

    def test_transport_large_or_error_response_does_not_leak(self):
        from pa_cli.jev_dispatch import _http_worker,MAX_RESPONSE
        for body in [b'x'*(MAX_RESPONSE+1),b'secret server error response']:
            pipe=RecordingPipe()
            class Opener:
                def open(inner,*args,**kwargs):
                    return io.BytesIO(body)
            with patch('pa_cli.jev_dispatch.urllib.request.build_opener',return_value=Opener()):
                _http_worker(pipe,{},'secret-key',1)
            self.assertEqual(pipe.result[0],'error')
            self.assertNotIn('secret',str(pipe.result))

    def test_transport_deadline_terminates_worker(self):
        from pa_cli.jev_dispatch import send_request
        start=time.monotonic()
        with patch('pa_cli.jev_dispatch._http_worker',slow_transport_worker):
            with self.assertRaises(TimeoutError):
                send_request({},'test-key',0.05)
        self.assertLess(time.monotonic()-start,1.5)

    def test_wrong_returned_model_halts_run(self):
        self.response['model']='unpriced-model'
        result=self.dispatch()
        self.assertEqual(result['status'],'model_price_unverified')
        self.q['support']['instructions']='new'
        with self.assertRaises(ValueError):
            self.dispatch()

    def test_critical_score_mass_overrides_high_confidence(self):
        self.q={'support':{'type':'score','criteria':['critical failure','acceptable']}}
        self.response['answers']['support']={'type':'score','score':0.95,'confidence':0.95,
            'legend':{'0':'critical failure','1':'acceptable'},'probabilities':{'0':0.05,'1':0.95}}
        result=self.dispatch(score_boundaries={'support':1},critical_score_levels={'support':[0]})
        self.assertEqual(result['routes']['support']['route'],'human_review')

    def test_uncertainty_only_queues_gpt_when_separately_authorized(self):
        self.response['answers']['support']['noul']=0.5
        result=self.dispatch(fallback_authorized=True)
        self.assertEqual(result['routes']['support']['route'],'gpt_review_pending')

    def test_expired_after_reservation_does_not_send(self):
        from pa_cli.jev_dispatch import Ledger,Approval
        original=Ledger.claim
        def delayed(ledger,*args):
            result=original(ledger,*args)
            time.sleep(1.1)
            return result
        approval=Approval('run-1',_hash(prepare_request(self.packet,self.q,'jev-test')),True,True,
                          datetime.now(timezone.utc)+timedelta(seconds=1),max_input_tokens=200)
        with patch.object(Ledger,'claim',delayed):
            result=self.dispatch(approval=approval)
        self.assertEqual(result['status'],'preflight_expired')
        self.assertEqual(self.calls,0)

    def test_quarantine_before_send_gate_does_not_send(self):
        from pa_cli.jev_dispatch import Ledger
        from pa_cli.jev_recovery import quarantine_request
        original = Ledger.claim
        def interrupted(ledger, *args):
            result = original(ledger, *args)
            quarantine_request(self.root/'dispatch.sqlite', 'run-1', args[2],
                               operator='op', evidence_reference='incident', interruption_confirmed=True)
            return result
        with patch.object(Ledger, 'claim', interrupted):
            result = self.dispatch()
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(self.calls, 0)

    def test_quarantine_during_transport_retains_late_result(self):
        from pa_cli.jev_recovery import quarantine_request
        import sqlite3
        def transport(*args):
            self.calls += 1
            with sqlite3.connect(self.root/'dispatch.sqlite') as conn:
                request_id = conn.execute('SELECT request_id FROM requests').fetchone()[0]
            conn.close()
            quarantine_request(self.root/'dispatch.sqlite', 'run-1', request_id,
                               operator='op', evidence_reference='incident', interruption_confirmed=True)
            return self.response
        result = self.dispatch(transport=transport)
        self.assertEqual(result['status'], 'late_result_review')
        self.assertEqual(self.calls, 1)
        self.assertEqual(result['routes']['support']['route'], 'human_review')

    def test_expiry_during_final_send_gate_does_not_send(self):
        from pa_cli.jev_dispatch import Ledger, Approval
        original = Ledger.begin_send
        def delayed(ledger, *args):
            result = original(ledger, *args)
            time.sleep(1.1)
            return result
        approval = Approval('run-1', _hash(prepare_request(self.packet, self.q, 'jev-test')), True, True,
                            datetime.now(timezone.utc)+timedelta(seconds=1), max_input_tokens=200)
        with patch.object(Ledger, 'begin_send', delayed):
            result = self.dispatch(approval=approval)
        self.assertEqual(result['status'], 'preflight_expired')
        self.assertEqual(self.calls, 0)


if __name__=='__main__':
    unittest.main()
