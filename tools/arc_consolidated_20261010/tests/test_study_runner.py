"""Explicitly synthetic controller evidence. No tokenizer assets, torch or GPU."""
from dataclasses import asdict
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from tools.arc_consolidated_20261010 import arc_object_ir as ir, assets, model_provider as mp, stages
from tools.arc_consolidated_20261010.ledger import BindingMismatch, Ledger, digest
from tools.arc_consolidated_20261010.study_runner import _feedback, run_model_studies
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory

ENV = 'e' * 64
PLAN = {'steps': [{'op': 'flip_horizontal'}]}


def tasks():
    return [{'task_id': tid, 'demos': [{'input': [[1, 2]], 'output': [[2, 1]]}]} for tid in assets.ENGINEERING_IDS]


def fixture():
    plans = [row['plan'] for row in assets.load_legacy('arc_typed_ir').grammar_candidates()[:64]]
    pool = stages.freeze_base_inventory(plans, ir.compile_plan)
    coverage = {'tasks': [{'task_id': task['task_id'], 'demo_fit': i < 2,
        'results': [{'candidate_id': row['candidate_id'], 'status': 'mismatch', 'known': True,
                     'all_demos_fit': False} for row in pool['candidates']]} for i, task in enumerate(tasks())]}
    return pool, coverage


def make_ledger(directory, mode='synthetic-test-only'):
    limits = {'physical_calls':80, 'cpu_checks':6000, 'unknown_calls':100,
              'prompt_tokens':80*6144, 'output_tokens':80*2048, 'model_seconds':80*120,
              'load_seconds':1000, 'wall_seconds':500, 'unknown_model_calls':80}
    study = mp.build_study_plan(tasks(), grammar={'version':ir.IR_VERSION,'contract':ir.plan_contract()}, environment_sha256=ENV)
    bindings = {'source':digest('synthetic-controller-source'), 'task':assets.digest(tasks()),
                'model':study.model_sha256, 'prompt':study.prompt_template_sha256,
                'sampling':assets.digest(asdict(study.sampling)), 'budget':digest(limits),
                'mode':digest(mode), 'environment':ENV}
    return Ledger(Path(directory)/'ledger', bindings, limits)


class SyntheticBackend:
    def __init__(self, ledger, *, overflow=False, fail=False, token=1):
        self.ledger, self.overflow, self.fail, self.token = ledger, overflow, fail, token
        self.calls, self.trace = [], []
        self.loaded = False

    def encode(self, messages):
        self.trace.append('encode')
        payload = json.loads(messages[1]['content'])
        parent = payload.get('parent') or {}
        if self.overflow and payload.get('memory') and parent.get('plan') == PLAN:
            return [self.token] * 6145
        return [self.token, 2, 3]

    def ensure_model_loaded(self):
        self.loaded = True
        self.trace.append('load')

    def generate(self, prepared, *, deadline_monotonic):
        self.assert_reserved = self.ledger.operation('model/'+prepared.request.spec.call_id)['status']
        if self.assert_reserved != 'reserved' or not self.loaded:
            raise AssertionError('dispatch before durable reservation/load')
        self.calls.append(prepared)
        if self.fail and len(self.calls) == 1:
            raise RuntimeError('synthetic unknown physical response')
        return {'request_sha256':prepared.sha256, 'model_sha256':prepared.request.model_sha256,
                'environment_sha256':ENV, 'text':json.dumps(PLAN), 'prompt_tokens':prepared.prompt_tokens,
                'output_tokens':1, 'output_token_ids':[7], 'finish_reason':'stop'}

    def close(self):
        self.loaded = False
        self.trace.append('close')
        return {'model_released':True,'descendants_stopped':True,'owned_descendants':[]}


class SyntheticVerifier:
    def __init__(self):
        self.calls = {}

    def __call__(self, task, plan, *, scope, call_id):
        key = scope, call_id
        identity = assets.digest([task,plan])
        if key in self.calls and self.calls[key] != identity:
            raise AssertionError('callback identity changed')
        self.calls[key] = identity
        return {'status':'fit','known':True,'all_demos_fit':True,'gas':1,
                'demos':[{'match':True} for _ in task['demos']],
                'evidence_mode':'synthetic-test-only'}


class StudyRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool, cls.coverage = fixture()

    def run_study(self, ledger, backend, verifier, session_id):
        return run_model_studies(tasks(),self.pool,self.coverage,ledger,session_id=session_id,
            model_config={'environment_sha256':ENV},evidence_mode='synthetic-test-only',
            backend_factory=lambda:backend,verify_callback=verifier)

    def test_unknown_feedback_never_becomes_invalid_plan(self):
        root = mp.FrozenRoot('root','a'*64,'b'*64,'c'*64,None,'unknown')
        for status in ('unknown','missing','unavailable','excluded_token_budget','excluded_missing_root'):
            with self.subTest(status=status):
                result = _feedback(tasks()[0],root,{'status':status})
                self.assertEqual(result['status'],'unknown')
                self.assertEqual(result['demo_matches'],[None])

    def test_fixed80_shared_once_pair_admission_and_search(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend, verifier = SyntheticBackend(ledger), SyntheticVerifier()
            with ledger.session(session_seconds=100):
                result = self.run_study(ledger,backend,verifier,'first')
                self.assertEqual(result.get('error'),None)
                self.assertEqual(result['status'],'complete')
                self.assertEqual(len(result['rows']),80)
                self.assertEqual(len(backend.calls),80)
                self.assertEqual(ledger.summary()['charged']['physical_calls'],80)
                self.assertEqual(result['owner_accounting']['load_count'],1)
                self.assertEqual(len(result['initial_token_audit']),80)
                self.assertGreaterEqual(backend.trace.index('load'),80)
                self.assertEqual(len(result['actual_pair_admission']),32)
                self.assertEqual(result['search']['planned'],4608)
                self.assertEqual(len(result['search']['physical_search']),72)
                self.assertEqual(sum(r['planned'] for r in result['search']['physical_search']),4608)
                self.assertLessEqual(sum(k[0]=='search' for k in verifier.calls),4608)
                self.assertEqual(result['arm_attribution']['roots']['planned'],16)
                self.assertEqual(result['arm_attribution']['feedback_true']['planned'],32)
                self.assertEqual(result['arm_attribution']['feedback_true']['known_output_tokens'],32)
                self.assertEqual(len(result['search']['actual_search_curves']),9)
                self.assertTrue(all(len(c['success_at_expansions'])==64 and c['task_denominator']==8
                                    for c in result['search']['actual_search_curves']))
                self.assertTrue(result['stop_ack']['model_owner_stopped'])

    def test_pair_overflow_excludes_both_and_preserves80(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend = SyntheticBackend(ledger,overflow=True)
            with ledger.session(session_seconds=100):
                result = self.run_study(ledger,backend,SyntheticVerifier(),'overflow')
                self.assertNotIn('error',result)
                self.assertEqual(len(result['rows']),80)
                self.assertEqual(len(backend.calls),48)
                memory = [row for row in result['rows'] if row['stage']=='memory']
                self.assertEqual(len(memory),32)
                self.assertTrue(all(row['status']=='excluded_token_budget' for row in memory))
                self.assertTrue(all(not r['truncated'] for r in result['actual_pair_admission']))

    def test_resume_cached_responses_no_generation_or_second_model_load(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend, verifier = SyntheticBackend(ledger), SyntheticVerifier()
            with ledger.session(session_seconds=100):
                first = self.run_study(ledger,backend,verifier,'first')
                self.assertEqual(first['status'],'complete')
            resumed = make_ledger(directory)
            second_backend = SyntheticBackend(resumed)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed,second_backend,verifier,'second')
                self.assertNotIn('error',result)
                self.assertEqual(len(second_backend.calls),0)
                self.assertEqual(result['owner_accounting']['load_count'],0)
                self.assertTrue(all(row['cache_reused'] for row in result['rows']))
                self.assertEqual(resumed.summary()['charged']['physical_calls'],80)
                self.assertEqual(resumed.summary()['charged']['unknown_model_calls'],0)

    def test_unknown_model_is_not_redispatched_on_resume(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend = SyntheticBackend(ledger,fail=True)
            with ledger.session(session_seconds=100):
                first = self.run_study(ledger,backend,SyntheticVerifier(),'failed')
                self.assertEqual(len(backend.calls),74)
                self.assertEqual(first['rows'][0]['status'],'unknown')
                failed_id = backend.calls[0].request.spec.call_id
                failure = ledger.operation('model/' + failed_id)
                self.assertFalse(ledger.summary()['reservation_overrun'])
                self.assertEqual(failure['usage']['output_tokens'], failure['budget']['output_tokens'])
                self.assertEqual(failure['usage']['model_seconds'], failure['budget']['model_seconds'])
                self.assertGreaterEqual(ledger.get_response('model/' + failed_id)['observed_model_seconds'], 0)
            resumed = make_ledger(directory)
            second_backend = SyntheticBackend(resumed)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed,second_backend,SyntheticVerifier(),'resume')
                self.assertNotIn(failed_id,[c.request.spec.call_id for c in second_backend.calls])
                self.assertEqual(result['rows'][0]['status'],'unknown')
                self.assertEqual(result['status'],'partial')
                self.assertEqual(resumed.summary()['charged']['physical_calls'],74)
                self.assertEqual(resumed.summary()['charged']['unknown_model_calls'],1)
                self.assertTrue(result['stop_ack']['model_owner_stopped'])

    def test_failed_generation_time_overrun_is_charged_and_stops_following_calls(self):
        class SlowFailure(SyntheticBackend):
            def generate(self, prepared, *, deadline_monotonic):
                self.calls.append(prepared)
                time.sleep(.05)
                raise RuntimeError('synthetic generation exceeded its .02 second reservation')
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend = SlowFailure(ledger)
            with ledger.session(session_seconds=100), patch.object(mp, 'MAX_MODEL_SECONDS', .02):
                result = self.run_study(ledger, backend, SyntheticVerifier(), 'slow-failure')
                self.assertEqual(result['error']['type'], 'BudgetExceeded')
                self.assertEqual(len(backend.calls), 1)
                self.assertEqual(result['rows'][0]['status'], 'unknown')
                operation_id = 'model/' + backend.calls[0].request.spec.call_id
                failure = ledger.operation(operation_id)
                response = ledger.get_response(operation_id)
                self.assertGreaterEqual(response['observed_model_seconds'], .04)
                self.assertEqual(failure['budget']['model_seconds'], .02)
                self.assertEqual(failure['usage']['model_seconds'], response['observed_model_seconds'])
                self.assertEqual(failure['usage']['output_tokens'], 2048)
                self.assertEqual(failure['usage']['prompt_tokens'], failure['budget']['prompt_tokens'])
                self.assertEqual(ledger.summary()['charged']['physical_calls'], 1)
                self.assertTrue(ledger.summary()['reservation_overrun'])
                self.assertTrue(result['stop_ack']['model_owner_stopped'])
            resumed = make_ledger(directory)
            second = SyntheticBackend(resumed)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed, second, SyntheticVerifier(), 'after-overrun')
                self.assertEqual(result['error']['type'], 'BudgetExceeded')
                self.assertEqual(second.calls, [])
                self.assertEqual(resumed.summary()['charged']['physical_calls'], 1)

    def test_saved_failed_response_replays_elapsed_overrun_before_new_generation(self):
        class SlowFailure(SyntheticBackend):
            def generate(self, prepared, *, deadline_monotonic):
                self.calls.append(prepared)
                time.sleep(.05)
                raise RuntimeError('synthetic delayed failure')
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            backend = SlowFailure(ledger)
            finish = ledger.finish
            def interrupt_finish(call_id, *args, **kwargs):
                if call_id.startswith('model/'):
                    raise RuntimeError('synthetic interruption after error receipt fsync')
                return finish(call_id, *args, **kwargs)
            with ledger.session(session_seconds=100), patch.object(mp, 'MAX_MODEL_SECONDS', .02), \
                    patch.object(ledger, 'finish', side_effect=interrupt_finish):
                result = self.run_study(ledger, backend, SyntheticVerifier(), 'interrupted-finish')
                self.assertEqual(len(backend.calls), 1)
                operation_id = 'model/' + backend.calls[0].request.spec.call_id
                self.assertEqual(ledger.operation(operation_id)['status'], 'responded')
                self.assertFalse(ledger.summary()['reservation_overrun'])
            resumed = make_ledger(directory)
            second = SyntheticBackend(resumed)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed, second, SyntheticVerifier(), 'finish-recovery')
                self.assertEqual(result['error']['type'], 'BudgetExceeded')
                self.assertEqual(second.calls, [])
                self.assertTrue(resumed.summary()['reservation_overrun'])
                self.assertGreaterEqual(resumed.summary()['charged']['model_seconds'], .04)
                self.assertEqual(resumed.summary()['charged']['physical_calls'], 1)

    def test_constructor_failure_does_not_claim_stop_ack(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            def fail():
                raise RuntimeError('synthetic constructor failed')
            with ledger.session(session_seconds=100):
                result = run_model_studies(tasks(),self.pool,self.coverage,ledger,session_id='badinit',
                    model_config={'environment_sha256':ENV},evidence_mode='synthetic-test-only',
                    backend_factory=fail,verify_callback=SyntheticVerifier())
                self.assertFalse(result['stop_ack']['model_owner_stopped'])
                self.assertEqual(ledger.summary()['charged']['physical_calls'],0)

    def test_previous_interrupted_owner_withholds_global_stop(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            with ledger.session(session_seconds=100):
                ledger.reserve('overhead','owner/interrupted',{'physical_calls':0})
            resumed = make_ledger(directory)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed,SyntheticBackend(resumed),SyntheticVerifier(),'after-crash')
                self.assertFalse(result['stop_ack']['model_owner_stopped'])
                self.assertTrue(result['stop_ack']['current_owner_stopped'])
                self.assertIn('owner/interrupted',result['stop_ack']['prior_uncertain_operations'])

    def test_cached_native_token_mutation_fails_before_model_load(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory)
            with ledger.session(session_seconds=100):
                first = self.run_study(ledger,SyntheticBackend(ledger),SyntheticVerifier(),'first')
                self.assertEqual(first['status'],'complete')
            resumed = make_ledger(directory)
            backend = SyntheticBackend(resumed,token=9)
            with resumed.session(session_seconds=100):
                result = self.run_study(resumed,backend,SyntheticVerifier(),'changed-tokenizer')
                self.assertEqual(result['error']['type'],'BindingMismatch')
                self.assertEqual(backend.calls,[])
                self.assertEqual(result['owner_accounting']['load_count'],0)

    def test_production_rejects_factory_before_any_mount_access(self):
        with self.assertRaisesRegex(ValueError,'cannot inject'):
            run_model_studies(tasks(),self.pool,self.coverage,None,session_id='forbidden',
                model_config={'environment_sha256':ENV},backend_factory=lambda:None,
                evidence_mode='production',verify_callback=SyntheticVerifier())

    def test_synthetic_mode_cannot_cross_production_ledger(self):
        with TemporaryDirectory() as directory:
            ledger = make_ledger(directory,mode='production')
            with ledger.session(session_seconds=100),self.assertRaises(BindingMismatch):
                self.run_study(ledger,SyntheticBackend(ledger),SyntheticVerifier(),'wrong')


if __name__ == '__main__':
    unittest.main()
