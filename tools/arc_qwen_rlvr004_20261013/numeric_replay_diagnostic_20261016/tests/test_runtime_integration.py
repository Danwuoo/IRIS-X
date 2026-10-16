"""Offline source/controller and real CPU tensor control-flow checks; never GPU proof."""
from __future__ import annotations
import ast
from contextlib import contextmanager, nullcontext
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
TOOL = PACKAGE.parent
REPOSITORY = TOOL.parents[1]
_runtime_tmp = tempfile.TemporaryDirectory(prefix='irisx-numeric-runtime-')
RUNTIME = Path(_runtime_tmp.name) / 'runtime'
# Reconstruct only the public, exactly pinned source map. No private fixture/data.
for name, row in json.loads((TOOL/'runtime-path-map.json').read_bytes())['files'].items():
    raw=(REPOSITORY/row['repository_path']).read_bytes()
    if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
        raise RuntimeError('public source mapping differs: '+name)
    target=RUNTIME/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
for source in (PACKAGE/'runtime').rglob('*.py'):
    target=RUNTIME/source.relative_to(PACKAGE/'runtime');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(source.read_bytes())
# Sibling probe tests intentionally load historical helpers. Test this exact
# reconstructed successor, independent of unittest discovery/import order.
for name in tuple(sys.modules):
    if name.split('.')[0] in ('owned_runtime','rl_session','experiment_flow'):
        del sys.modules[name]
sys.path[:0]=[str(RUNTIME),str(RUNTIME/'baseline'),str(RUNTIME/'baseline/src')]
from experiment_flow import flow
from experiment_flow.contracts import ExperimentPlan, FixtureShape, Forecast, canonical
from experiment_flow.tests.test_flow import Clock, Dataset, Panel, GATE
from experiment_flow.controlled_batched import BatchedAdapter
from owned_runtime.release import source_freeze
from owned_runtime.ledger import DurablePhysicalLedger, Limits, phase_kind


class DiagnosticAdapter(BatchedAdapter):
    """Explicit controlled adapter; fabricated outcomes are not native evidence."""
    def update(self,batch,*,gate_json,deadline):
        self.update_calls+=1;self.pending=None
        self._op('causal-replay',1.)
        self._op('numeric-shadow-forward',1.)
        self.events[-1]['input_tokens']=17
        self._op('restore',1.)
        complete=self.branch!='shadow-incomplete'
        if self.branch=='partial-update-error':
            from experiment_flow.contracts import RecoverableWorkError
            error=RecoverableWorkError('controlled shadow failure',batch=batch)
            error.update_report={'status':'update-failed','optimizer_committed':False,
                'optimizer_dispatched':False,'replays':[{} for _ in range(64)],
                'numeric_shadow':{'complete':False,'status':'incomplete','rows':[{'partial':True}]}}
            raise error
        return {'status':'intentionally-no-update' if complete else 'numeric-diagnostic-incomplete-no-update',
            'optimizer_committed':False,'optimizer_dispatched':False,
            'replays':[{} for _ in range(64)],'numeric_shadow_complete':complete,
            'numeric_shadow':{'complete':complete,'status':'complete' if complete else 'incomplete','model_forward_calls':1},
            'original_numeric_gate':{'admitted':self.branch!='numeric-fail','failures':[] if self.branch!='numeric-fail' else ['original-gap']},
            'rollback':{'restored':True,'logical_counters_restored':True}}


class FlowTests(unittest.TestCase):
    def run_case(self,branch='mixed'):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        clock=Clock();shape=FixtureShape(anchor_updates=256,parents=32,group_size=8,dev_cases=16,
            holdout_cases=32,max_sweeps=4,max_control_updates=8192,batch_parents=8)
        forecast=Forecast('f'*64,'controlled-fixture',1.,1.,1.,1.,1.,1.,1.,1.)
        plan=ExperimentPlan(source_freeze(),forecast,clock(),GATE,shape=shape,output_cap=1024)
        backend=DiagnosticAdapter(clock,branch,generation_seconds=.01,save_cost=.01)
        dataset=Dataset(shape);panel=Panel(shape);panel.plan_sha256="d"*64
        result=flow.run_training_numeric_diagnostic(backend,dataset,panel,plan,Path(temporary.name)/'run',clock=clock)
        return result,backend,dataset
    def test_first64_then_no_control_or_evaluation(self):
        result,backend,dataset=self.run_case()
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_COMPLETE,result.get('error'))
        self.assertTrue(result['diagnostic_complete'])
        self.assertEqual(result['original_planned_attempts'],256)
        self.assertEqual(result['requested_attempts'],64)
        self.assertEqual(result['unrequested_original_panel_attempts'],192)
        self.assertEqual(len(backend.batches),1);self.assertEqual(backend.update_calls,1)
        self.assertEqual(backend.predictions,0);self.assertEqual(dataset.opened,[])
        self.assertEqual(result['arms']['A']['updates']['anchor_updates'],256)
        self.assertEqual(result['arms']['B']['updates']['rl_updates'],0)
        self.assertEqual(result['arms']['B']['updates']['control_updates'],0)
        self.assertEqual(result['arms']['A']['adapter_sha256'],result['arms']['B']['adapter_sha256'])
        self.assertFalse(result['comparison_complete']);self.assertIsNone(result['comparison'])
        for name in ('dev_selection','holdout','public'):self.assertIsNone(result[name])
        for name in ('C','dev','PUBLIC','holdout'):self.assertEqual(result['stage_status'][name],'not-requested-by-diagnostic')
        self.assertEqual([x['status'] for x in result['audit_batches'][1:]],['not-requested-by-diagnostic']*3)
        self.assertEqual(result['full_panel_audit']['summary']['not_reached'],192)
        self.assertEqual(result['metering_bridge']['known_forward_input_tokens'],17)
        ref=result['numeric_shadow_ref'];raw=Path(ref['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ref['file_sha256'])
        audit=json.loads(Path(result['audit_batches'][0]['path']).read_bytes())
        self.assertEqual(audit['update']['numeric_shadow_ref'],ref)
        self.assertNotIn('numeric_shadow',audit['update'])
    def test_original_numeric_failure_can_complete_diagnostic(self):
        result,_,_=self.run_case('numeric-fail')
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_COMPLETE,result.get('error'))
        audit=json.loads(Path(result['audit_batches'][0]['path']).read_bytes())
        self.assertFalse(audit['update']['original_numeric_gate']['admitted'])
    def test_zero_signal_is_incomplete_no_fake_replay_or_extra_batch(self):
        result,backend,dataset=self.run_case('zero')
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_INCOMPLETE)
        self.assertFalse(result['diagnostic_complete']);self.assertEqual(backend.update_calls,0)
        self.assertEqual(len(backend.batches),1);self.assertEqual(dataset.opened,[])
        self.assertNotIn('numeric_shadow_ref',result)
    def test_shadow_partial_is_retained_and_incomplete(self):
        result,backend,_=self.run_case('shadow-incomplete')
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_INCOMPLETE)
        self.assertFalse(json.loads(Path(result['numeric_shadow_ref']['path']).read_bytes())['complete'])
        self.assertEqual(len(backend.batches),1)
    def test_update_failure_retains_audit_physical_costs_and_stops(self):
        result,backend,dataset=self.run_case('partial-update-error')
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_INCOMPLETE)
        self.assertEqual(len(backend.batches),1);self.assertEqual(dataset.opened,[])
        audit=json.loads(Path(result['audit_batches'][0]['path']).read_bytes())
        self.assertEqual(audit['update']['status'],'update-failed')
        self.assertGreater(result['metering_bridge']['event_count'],256)
    def test_bad_cleanup_never_completes(self):
        result,_,_=self.run_case('bad-close')
        self.assertEqual(result['status'],flow.NUMERIC_DIAGNOSTIC_INCOMPLETE)
        self.assertFalse(result['diagnostic_complete'])


class SourceBoundaryTests(unittest.TestCase):
    def test_shadow_hard_deadline_intersects_original_batch_and_phase_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=DurablePhysicalLedger('cpu',1000.,lambda error:None,
                Path(directory)/'physical.jsonl',auth_key=b'k'*32,clock=lambda:100.)
            self.addCleanup(ledger.release)
            with ledger.work('numeric-shadow',110.) as outer:
                self.assertEqual(outer['hard_deadline'],110.)
                with ledger.work('numeric-shadow-forward',105.) as event:
                    self.assertEqual(event['hard_deadline'],105.)
                    self.assertEqual(event['soft_deadline'],105.)
            with ledger.work('numeric-shadow-forward',900.) as event:
                self.assertEqual(event['hard_deadline'],130.)
                self.assertEqual(event['soft_deadline'],125.)
            with ledger.work('causal-replay',105.) as event:
                self.assertEqual(event['hard_deadline'],220.)
            self.assertTrue(ledger.summary()['integrity_ok'])
            ledger.closed=True

    def test_watchdog_new_kind_is_narrow(self):
        limits=Limits().validate()
        self.assertEqual(phase_kind('numeric-shadow-forward'),'numeric-shadow-forward')
        self.assertEqual(limits.for_kind('numeric-shadow-forward'),(25.,30.))
        self.assertEqual(phase_kind('numeric-shadow'),'operation')
        self.assertEqual(limits.for_kind('operation'),(115.,120.))
        self.assertEqual(limits.for_kind('generation'),(175.,180.))
        self.assertEqual(limits.for_kind('native-load'),(1795.,1800.))
        self.assertEqual(phase_kind('causal-replay'),'operation')
        self.assertEqual(phase_kind('sample-forward'),'generation')
        supervisor=(TOOL/'source/owned_runtime/supervisor.py').read_text()
        self.assertIn("limits.for_kind(phase_kind(event['phase']))",supervisor)
    def test_owned_worker_never_constructs_public_bridge(self):
        text=(PACKAGE/'runtime/owned_runtime/worker.py').read_text()
        self.assertNotIn('PublicSuccessorBridge',text)
        self.assertIn("request.get('run_purpose')==NUMERIC_DIAGNOSTIC_PURPOSE",text)
        self.assertIn('result=run_training_numeric_diagnostic(',text)
    def test_runner_requires_safe_capability_and_has_no_scorer_or_tensor_export(self):
        tree=ast.parse((PACKAGE/'runtime/owned_runtime/runner.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_owned')
        calls={n.func.id if isinstance(n.func,ast.Name) else n.func.attr for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))}
        self.assertIn('export_diagnostic_evidence',calls)
        self.assertIn('verify_closed_capability',calls)
        for name in ('score_parent_public','score_closed_public','export_checkpoint_zip','export_evidence_only'):self.assertNotIn(name,calls)
        self.assertIn('owned.capability is not None',ast.unparse(fn))
        self.assertIn("closed.get('safe_closure') is True",ast.unparse(fn))
        self.assertIn("closed.get('model_stopped') is True",ast.unparse(fn))
        self.assertIn("'run_purpose': NUMERIC_DIAGNOSTIC_PURPOSE",ast.unparse(fn))
    def test_source_inventory_captures_new_module_and_no_release_overlay(self):
        self.assertFalse((PACKAGE/'runtime/owned_runtime/release.py').exists())
        # The probe can be absent while its separate author is still working.
        source=(PACKAGE/'runtime/rl_session/numeric_shadow.py')
        if source.exists():self.assertIn('rl_session/numeric_shadow.py',dict(source_freeze().files))
    def test_original_abc_function_preserved_byte_for_byte(self):
        old=(TOOL/'source/experiment_flow/flow.py').read_bytes()
        self.assertTrue((PACKAGE/'runtime/experiment_flow/flow.py').read_bytes().startswith(old))


try:
    import torch
except ImportError:
    torch=None


@unittest.skipUnless(torch is not None,'real CPU tensor tests require local torch environment')
class SessionHookTests(unittest.TestCase):
    def run_update(self,*,admitted=True,shadow_complete=True,state_preserved=True,raise_shadow=False):
        """Execute actual successor method body, real tensors/backward, controlled ownership."""
        tree=ast.parse((PACKAGE/'runtime/rl_session/runtime.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Session')
        method=deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_update_impl'))
        namespace={'__package__':'rl_session','torch':torch,'deepcopy':deepcopy,'time':time,
                   'canonical':canonical,'need':lambda ok,msg:None if ok else (_ for _ in ()).throw(ValueError(msg))}
        gate=types.SimpleNamespace(maximum_batch_replay_backward_seconds=600.)
        namespace['production_numeric_gate']=lambda:gate
        namespace['cumulative_batch_deadline']=lambda gate,deadline,started,fixture: min(deadline,started+600.)
        namespace['rl_math']=types.SimpleNamespace(reward_groups=lambda *a:(torch.tensor([1.]*8+[0.]*56),torch.tensor([8]*64),[{'successes':7,'eligible':8,'total':8,'mixed':True}]))
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-source-update-method>','exec'),namespace)
        events=[];parameters=[torch.tensor([.3,.4],requires_grad=True) for _ in range(64)]
        class Ledger:
            @contextmanager
            def work(self,phase,deadline):
                event={'event_id':len(events),'phase':phase};events.append(event)
                try:yield event
                finally:event['seconds']=.001
        class Owner:
            fixture=False;stage='rl';policy_version='p';_generation_epoch=3;fatal_error=None
            device=torch.device('cpu');_lock=nullcontext();_phase_deadline=time.monotonic()+1000
            ledger=Ledger();counters={'rl_updates':0,'backward_calls':0};_rl_stop_reason=None
            def _check_live(self):pass
            def _deadline(self,d):pass
            def _check_batch(self,b):pass
            def snapshot(self,*a,**k):return {'saved_backward':self.counters['backward_calls']}
            def release_snapshot(self,h):self.released=True
            def replay(self,t,**kw):
                self.replays=getattr(self,'replays',0)+1
                return types.SimpleNamespace(log_pi=parameters[t['trajectory_id']],log_mu=parameters[t['trajectory_id']].detach().clone(),diagnostic={'seconds':0.})
            def _mode(self,value):return nullcontext()
            def numerical_admission(self,replays,gate):return {'admitted':admitted,'failures':[] if admitted else ['gap']}
            def restore(self,h,**k):
                self.restored=True;self.counters['backward_calls']=h['saved_backward']
                return {'restored':True,'logical_counters_restored':True,'physical_events_preserved':len(events)}
            def _finish_batch(self,b,status):return {'status':status}
            def _commit(self,*a):raise AssertionError('diagnostic must never commit')
        owner=Owner();owner.ledger.events=events;owner.counters={'rl_updates':0,'backward_calls':0}
        owner.optimizer=types.SimpleNamespace(zero_grad=lambda **k:[setattr(p,'grad',None) for p in parameters])
        batch={'rows':[{'eligible':True,'reward':1 if i<7 else 0,'parent_id':str(i//8),'status':'eligible',
                        'trajectory':{'trajectory_id':i,'original_ids':[1,2,3],'dispatched_forwards':1}} for i in range(64)],
               'policy_version':'p','generation_epoch':3,'closed':True,'planned_attempts':64,'batch_index':0,
               'parent_ids':[str(i) for i in range(8)],'session_planned_attempts':256,'all_slots_reached':True,'id':'batch'}
        def shadow(actor,b,replays,*,deadline):
            self.assertEqual(len(replays),64);self.assertEqual(actor.replays,64)
            self.assertEqual(actor.counters['backward_calls'],8)
            self.assertEqual(sum(p.grad is not None for p in parameters),8)
            events.append({'event_id':len(events),'phase':'numeric-shadow-forward','dispatched':True})
            if raise_shadow:raise ValueError('controlled shadow failure')
            return {'complete':shadow_complete,'state_preserved':state_preserved,
                    'status':'complete' if shadow_complete else 'incomplete'}
        fake=types.ModuleType('rl_session.numeric_shadow');fake.run_numeric_shadow=shadow
        with patch.dict(sys.modules,{'rl_session.numeric_shadow':fake}):
            try:result=namespace['_update_impl'](owner,batch,gate=gate,deadline=time.monotonic()+1000)
            except Exception as error:result=error
        return result,owner,events,parameters
    def test_both_numeric_gate_outcomes_execute64_replays8_real_backwards_then_restore(self):
        for admitted in (True,False):
            with self.subTest(admitted=admitted):
                result,owner,events,parameters=self.run_update(admitted=admitted)
                self.assertIsInstance(result,dict,str(result))
                self.assertEqual(result['status'],'intentionally-no-update')
                self.assertFalse(result['optimizer_committed']);self.assertFalse(result['optimizer_dispatched'])
                self.assertEqual(result['original_numeric_gate']['admitted'],admitted)
                self.assertEqual(result['numerical_gate'],result['original_numeric_gate'])
                self.assertEqual(result['backward_calls'],8);self.assertEqual(owner.counters['backward_calls'],0)
                self.assertEqual(len(events),9);self.assertTrue(owner.restored);self.assertTrue(owner.released)
                self.assertTrue(all(p.grad is None for p in parameters))
    def test_incomplete_shadow_still_restores_and_never_commits(self):
        result,owner,events,_=self.run_update(shadow_complete=False)
        self.assertEqual(result['status'],'numeric-diagnostic-incomplete-no-update')
        self.assertTrue(owner.restored);self.assertEqual(len(events),9)
    def test_unpreserved_shadow_never_claims_completion(self):
        result,owner,_,_=self.run_update(state_preserved=False)
        self.assertEqual(result['status'],'numeric-diagnostic-incomplete-no-update')
        self.assertFalse(result['numeric_shadow_complete']);self.assertTrue(owner.restored)
    def test_exception_preserves_failure_report_and_physical_events(self):
        result,owner,events,_=self.run_update(raise_shadow=True)
        self.assertIsInstance(result,ValueError)
        self.assertEqual(result.update_report['status'],'update-failed')
        self.assertFalse(result.update_report['optimizer_committed'])
        self.assertTrue(owner.restored);self.assertTrue(owner.released);self.assertEqual(len(events),9)


if __name__=='__main__':unittest.main()
