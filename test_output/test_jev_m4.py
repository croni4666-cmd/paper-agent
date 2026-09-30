"""Offline API-contract and budget tests; never calls Jev."""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class JevTests(unittest.TestCase):
    def setUp(self):
        self.questions = {'support': {'type':'noul','instructions':'Is the claim supported?'}}
        self.now = datetime(2026, 9, 26, tzinfo=timezone.utc)

    def response(self, answer):
        return {'model':'jev-version-test','answers':{'support':answer},
                'usage':{'input_tokens':100,'output_tokens':5}}

    def validate(self, answer, questions=None):
        from pa_cli.jev import validate_response
        return validate_response(self.response(answer), questions or self.questions)

    def test_noul_uses_actual_api_field(self):
        result = self.validate({'type':'noul','noul':0.96})
        self.assertEqual(result['answers']['support']['p_yes'], 0.96)
        with self.assertRaises(ValueError):
            self.validate({'type':'noul','p_yes':0.96})

    def test_choice_selection_must_match_distribution(self):
        q = {'support':{'type':'choice','criteria':{'yes':'support','no':'no support'}}}
        a = {'type':'choice','choice':'no','confidence':0.95,'probabilities':{'yes':0.95,'no':0.05}}
        with self.assertRaises(ValueError):
            self.validate(a,q)
        a['choice']='yes'
        self.assertEqual(self.validate(a,q)['answers']['support']['choice'],'yes')

    def test_score_validates_expected_value_and_legend(self):
        q={'support':{'type':'score','criteria':['low','medium','high']}}
        a={'type':'score','score':1.7,'confidence':0.8,'legend':{'0':'low','1':'medium','2':'high'},
           'probabilities':{'0':0.1,'1':0.1,'2':0.8}}
        self.assertAlmostEqual(self.validate(a,q)['answers']['support']['score'],1.7)
        a['score']=2
        with self.assertRaises(ValueError):
            self.validate(a,q)

    def test_nonfinite_or_wrong_usage_rejected(self):
        from pa_cli.jev import validate_response
        for value in [float('nan'),float('inf'),-0.1,True]:
            with self.assertRaises(ValueError):
                self.validate({'type':'noul','noul':value})
        response=self.response({'type':'noul','noul':0.9})
        response['usage']['input_tokens']=True
        with self.assertRaises(ValueError):
            validate_response(response,self.questions)

    def test_missing_named_answer_rejected(self):
        from pa_cli.jev import validate_response
        r=self.response({'type':'noul','noul':0.9})
        r['answers']={}
        with self.assertRaises(ValueError):
            validate_response(r,self.questions)

    def test_routing_is_suggestions_only_and_requires_escalation_consent(self):
        from pa_cli.jev import route_answer
        self.assertEqual(route_answer({'type':'noul','p_yes':0.95})['route'],'triage_suggestion')
        self.assertEqual(route_answer({'type':'noul','p_yes':0.5})['route'],'human_review')
        self.assertEqual(route_answer({'type':'noul','p_yes':0.5}, fallback_authorized=True)['route'],'gpt_review_pending')
        self.assertEqual(route_answer({'type':'noul','p_yes':0.99}, high_stakes=True)['route'],'human_review')

    def test_score_routes_probability_mass_at_action_boundary(self):
        from pa_cli.jev import route_answer
        a={'type':'score','score':1.7,'probabilities':{'0':0.1,'1':0.1,'2':0.8}}
        self.assertEqual(route_answer(a,score_boundary=2)['route'],'human_review')
        self.assertEqual(route_answer(a)['route'],'human_review')

    def test_budget_reserves_unknown_and_reconciles_known_usage(self):
        from pa_cli.jev import Budget, Price
        price=Price('jev-test','0.042',self.now,'https://typesafe.ai/pricing')
        budget=Budget(price,max_papers=2,max_input_tokens=200,max_cost_usd='0.01',now=self.now)
        budget.reserve('a',100)
        budget.mark_unknown('a')
        budget.reserve('b',100)
        with self.assertRaises(ValueError):
            budget.reserve('c',1)
        budget.reconcile('b',50)
        self.assertEqual(budget.input_tokens_committed,150)
        with self.assertRaises(ValueError):
            budget.reserve('a',100)

    def test_stale_price_and_actual_overrun_halt_budget(self):
        from pa_cli.jev import Budget, Price
        old=Price('jev-test','0.042',self.now-timedelta(days=8),'https://typesafe.ai/pricing')
        with self.assertRaises(ValueError):
            Budget(old,now=self.now)
        price=Price('jev-test','0.042',self.now,'https://typesafe.ai/pricing')
        b=Budget(price,max_input_tokens=100,now=self.now)
        b.reserve('a',100)
        b.reconcile('a',101)
        self.assertTrue(b.halted)
        with self.assertRaises(ValueError):
            b.reserve('b',1)

    def test_request_state_omits_local_metadata(self):
        from pa_cli.jev import prepare_request
        from pa_cli.evidence import _hash
        packet={'artifact_sha256':'a'*64,'evidence':[{'evidence_id':'b'*64,'text':'Quoted passage','page':1}],
                'local_path':'private/project/paper.pdf','author':'Private Author'}
        packet['packet_hash']=_hash(packet)
        request=prepare_request(packet,self.questions,'jev-test')
        self.assertNotIn('Private Author',str(request))
        self.assertNotIn('local_path',str(request))
        self.assertEqual(request['state']['passages'][0]['text'],'Quoted passage')

    def test_dry_run_accounts_usage_and_keeps_unknown_reserved(self):
        from pa_cli.jev import dry_run, Budget, Price
        from pa_cli.evidence import _hash
        packet={'evidence':[{'evidence_id':'e1','text':'employment increased'}]}
        packet['packet_hash']=_hash(packet)
        budget=Budget(Price('jev-test','0.042',self.now,'https://typesafe.ai/pricing'),now=self.now)
        result=dry_run(packet,self.questions,'jev-test',self.response({'type':'noul','noul':0.95}),
                       budget=budget,estimated_input_tokens=200,rubric_version='v1')
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['routes']['support']['route'],'triage_suggestion')
        self.assertEqual(budget.input_tokens_committed,100)
        unknown=dry_run(packet,self.questions,'jev-test',None,
                        budget=budget,estimated_input_tokens=200,rubric_version='v2')
        self.assertEqual(unknown['status'],'unknown')
        self.assertEqual(budget.input_tokens_committed,300)

    def test_model_price_mismatch_is_rejected_before_reservation(self):
        from pa_cli.jev import dry_run, Budget, Price
        budget=Budget(Price('jev-priced','0.042',self.now,'https://typesafe.ai/pricing'),now=self.now)
        with self.assertRaises(ValueError):
            dry_run({},self.questions,'other-model',None,budget=budget,estimated_input_tokens=100,rubric_version='v1')
        self.assertEqual(budget.input_tokens_committed,0)

    def test_question_description_must_follow_api_types(self):
        from pa_cli.jev import validate_response
        for questions in [
            {'support':{'type':'noul','instructions':42}},
            {'support':{'type':'choice','criteria':{'yes':True,'no':'no'}}},
            {'support':{'type':'score','criteria':['low',42]}},
        ]:
            with self.assertRaises(ValueError):
                validate_response(self.response({'type':'noul','noul':0.9}),questions)


if __name__=='__main__':
    unittest.main()
