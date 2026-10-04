"""Synthetic-only controls for native source interfaces and inert packaging."""
import ast
from contextlib import contextmanager
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_native_solve_runtime as runtime
from tools import nvarc_native_solve_render as render
from tools import stage_nvarc_native_long_ttt as legacy
from tools import stage_nvarc_native_editor as editor
from tools import stage_nvarc_native_solve as stage
from tools import verify_nvarc_native_solve as reader
from tools import save_nvarc_native_solve as transport


class FakeTensor:
    def __init__(self, values, shape=None):
        self.values = copy.deepcopy(values)
        self.shape = shape or self._shape(values)
    @staticmethod
    def _shape(value):
        return [len(value)] + FakeTensor._shape(value[0]) if isinstance(value, list) and value else []
    def detach(self): return self
    def cpu(self): return self
    def float(self): return self
    def tolist(self): return copy.deepcopy(self.values)
    def unsqueeze(self, dimension):
        if dimension != 0: raise ValueError('fixture supports dimension zero')
        return FakeTensor([self.values])
    def expand(self, batch, _width): return FakeTensor(self.values * batch)
    def contiguous(self): return self
    def all(self): return self
    def item(self): return True


class FakeTorch:
    long = 'fixture-long'
    @staticmethod
    def arange(n, **_kwargs): return FakeTensor(list(range(n)))
    @staticmethod
    def isfinite(_tensor): return FakeTensor(True)
    @staticmethod
    def tensor(values, **_kwargs): return FakeTensor(values)
    @staticmethod
    def no_grad(): return lambda function: function


class FakeModel:
    device = 'fixture'
    def __init__(self, tuple_output=True):
        self.calls = []; self.tuple_output = tuple_output; self.cache = object()
    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        shape = kwargs['input_ids'].shape
        logits = FakeTensor(None, [shape[0], shape[1], 16])
        cache = self.cache if kwargs['use_cache'] else None
        return (logits, cache) if self.tuple_output else SimpleNamespace(logits=logits, past_key_values=cache)


def adapter(model=None, generation_limit=2):
    events = []
    value = runtime.SourceModel(model or FakeModel(), FakeTorch,
        lambda event, **details: events.append({'event': event, **details}),
        forward_limits={'control': 7, 'generation': generation_limit, 'verification': 2},
        input_token_limit=1000, generation_deadline=time.time()+60)
    return value, events


def visible():
    return {'fixture': {'train': [
        {'input': [[1,2],[3,4]], 'output': [[1,2],[3,4]]},
        {'input': [[5,6],[7,8]], 'output': [[5,6],[7,8]]}],
        'test': [{'input': [[1,2,3],[4,5,6]]}]}}


class NativeSolveControlTests(unittest.TestCase):
    def test_admission_requires_explicit_editor_clearance_and_finite_reserved_quota(self):
        run = 'nvarc-original-qwen3-native-solve-001'
        value = {'format':'irisx/controller-gpu-admission-v1','run_id':run,
            'control_sha256':stage.CONTROL_SHA,'source_commit':stage.BASE_COMMIT,'maximum_paid_usd':0,
            'prior_sessions_reconciled':True,'quota_reservation_id':'synthetic-reservation',
            'reserved_quota_hours':2.5,'quota_observed_at':'2026-10-04T04:30:00Z',
            'local_resource_admission':True,'ui_operator':'user','private':True,'internet':False,
            'owner_editor_sessions_closed':True,'owner_clearance_ref':'synthetic-owner-evidence',
            'l4_quota_multiplier':2}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'admission.json';path.write_text(json.dumps(value))
            self.assertEqual(stage.admission_for(path,run)[0],value)
            for delta in ({'owner_editor_sessions_closed':False},{'owner_clearance_ref':''},
                          {'reserved_quota_hours':float('inf')},{'reserved_quota_hours':2},
                          {'internet':True},{'l4_quota_multiplier':4},
                          {'quota_observed_at':'2026-10-04T04:30:00'}):
                path.write_text(json.dumps({**value,**delta}))
                with self.subTest(delta=delta),self.assertRaises((RuntimeError,ValueError)):
                    stage.admission_for(path,run)

    def test_offline_stager_roundtrip_is_inert_and_rejects_changed_payload(self):
        old_plan={'run_id':'nvarc-original-qwen3-native-ttt-008','source_rows_digest':'synthetic',
            'source_learning_rates':[0.]*129,'parent_ids':['fixture'],'exposure_tags':['synthetic'],
            'competition_sources':['arc-prize-2026-arc-agi-2'],'model_sources':['synthetic-model']}
        source=legacy.portable_worker().decode().replace("plan['owner_decision']=='Decision 0054'",
                                                        "plan['owner_decision']=='Decision 0056'")
        raw={'plan':b'{}','worker':source.encode(),'source_inventory':b'{}','model_inventory':b'{}',
             'helper':b'# fixture','solver':b'# fixture','schedule':b'# fixture',
             'budget':b'# fixture','hardware':b'# fixture','texts_gzip':b'fixture',
             'expected_rows':b'[]','editor_archive':editor.ARCHIVE.read_bytes()}
        bodies={'solver.py':b'# fixture','arc_loader.py':b'# fixture','arc_decoder.py':b'# fixture'}
        def inputs(): return copy.deepcopy(old_plan),copy.deepcopy(raw),json.dumps(visible()).encode(),copy.deepcopy(bodies)
        with tempfile.TemporaryDirectory() as temp,patch.object(stage,'frozen_inputs',side_effect=inputs):
            package=Path(temp)/'package'
            result=stage.stage(package,'nvarc-original-qwen3-native-solve-001')
            self.assertFalse(result['approved_for_runtime'])
            self.assertEqual(result['model_calls'],0)
            self.assertEqual(stage.preflight(package),result)
            notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
            parent=''.join(notebook['cells'][0]['source'])
            work=Path(temp)/'work';work.mkdir()
            parent=parent.replace("Path('/kaggle/working')",'Path('+repr(str(work))+')')
            with patch('sys.stdout',new_callable=io.StringIO),self.assertRaisesRegex(RuntimeError,'inert package'):
                exec(compile(parent,'inert-stage-fixture','exec'),{})
            proof=reader.verify(work/'結果.zip',package)
            self.assertFalse(proof['trained_solve_gate'])
            self.assertEqual(proof['outcome'],'failed-before-pipeline-result')
            extra=package/'kernel/stage-summary.json';extra.write_text('{}')
            with self.assertRaises(RuntimeError):stage.preflight(package)
            extra.unlink()
            with (package/'kernel/notebook.ipynb').open('ab') as stream:stream.write(b' ')
            with self.assertRaises(RuntimeError):stage.preflight(package)

    def test_optimizer_zero_grad_failure_does_not_skip_state_and_reference_cleanup(self):
        actions=[]
        def failed_zero(**_kwargs):
            actions.append('optimizer-zero');raise RuntimeError('synthetic-zero-failure')
        optimizer=SimpleNamespace(zero_grad=failed_zero,state={'tensor':'retained'})
        budget=SimpleNamespace(optimizer=optimizer)
        trainer=SimpleNamespace(optimizer=optimizer,lr_scheduler=object(),
            accelerator=SimpleNamespace(_optimizers=[optimizer],_schedulers=[object()]))
        model=SimpleNamespace(zero_grad=lambda **_k:actions.append('model-zero'))
        with self.assertRaisesRegex(RuntimeError,'synthetic-zero-failure'):
            runtime.discard_optimizer_state(model,trainer,budget)
        self.assertEqual(actions,['model-zero','optimizer-zero'])
        self.assertEqual(optimizer.state,{})
        self.assertIsNone(budget.optimizer);self.assertIsNone(trainer.optimizer)
        self.assertIsNone(trainer.lr_scheduler)
        self.assertEqual(trainer.accelerator._optimizers,[])
        self.assertEqual(trainer.accelerator._schedulers,[])

    def test_no_cache_model_output_may_omit_cache_attribute(self):
        class Model(FakeModel):
            def __call__(self,**kwargs):
                return SimpleNamespace(logits=super().__call__(**kwargs)[0])
        wrapped,_=adapter(Model())
        with wrapped.scope('generation'):
            self.assertIsNone(wrapped(input_ids=FakeTensor([[1]]*4),use_cache=False).past_key_values)
        with wrapped.scope('generation'),self.assertRaisesRegex(RuntimeError,'cache result missing'):
            wrapped(input_ids=FakeTensor([[1]]*4),use_cache=True)

    def test_physical_token_and_deadline_stops_leave_no_new_reservation(self):
        for reason in ('input_token_limit','inference_deadline'):
            wrapped,_=adapter()
            if reason=='input_token_limit':wrapped.input_token_limit=3
            else:wrapped.generation_deadline=0
            with wrapped.scope('generation'),self.assertRaises(runtime.InferenceLimitReached) as error:
                wrapped(input_ids=FakeTensor([[1]]*4),use_cache=True)
            self.assertEqual(error.exception.reason,reason)
            self.assertEqual(wrapped.reserved['generation'],0)
            self.assertIsNone(wrapped.active)

    def test_cached_position_ranges_must_match_four_source_rows(self):
        for positions in ([[1,3]]*4,[[1],[1],[2],[1]]):
            wrapped,_=adapter();length=len(positions[0])
            with wrapped.scope('generation'),self.assertRaisesRegex(RuntimeError,'contiguous'):
                wrapped(input_ids=FakeTensor([[1]*length]*4),position_ids=FakeTensor(positions),
                        past_key_values=object(),use_cache=True)

    def test_no_call_outside_phase_and_no_boolean_limits(self):
        wrapped, _ = adapter()
        with self.assertRaisesRegex(RuntimeError, 'unreserved'):
            wrapped(input_ids=FakeTensor([[0]]*4), use_cache=True)
        with self.assertRaises(RuntimeError):
            runtime.SourceModel(FakeModel(), FakeTorch, lambda *_a, **_k: None,
                forward_limits={'control': True, 'generation': 2, 'verification': 2},
                input_token_limit=100, generation_deadline=1)

    def test_explicit_prefill_positions_and_tuple_identity(self):
        model = FakeModel(); wrapped, events = adapter(model)
        with wrapped.scope('generation'):
            value = wrapped(input_ids=FakeTensor([[1,2,3]]*4), use_cache=True)
        self.assertEqual(model.calls[0]['position_ids'].tolist(), [[0,1,2]]*4)
        self.assertIs(value.past_key_values, model.cache)
        self.assertEqual(wrapped.input_tokens, 12)
        self.assertEqual([e['event'] for e in events], ['forward_reserved', 'forward_completed'])

    def test_model_output_and_cached_explicit_positions(self):
        model = FakeModel(False); wrapped, _ = adapter(model)
        with wrapped.scope('generation'):
            result = wrapped(input_ids=FakeTensor([[1]]*4), position_ids=FakeTensor([[12]]*4),
                             past_key_values=object(), use_cache=True)
        self.assertIs(result.past_key_values, model.cache)

    def test_cached_missing_positions_rejected_before_model_entry(self):
        model = FakeModel(); wrapped, _ = adapter(model)
        with wrapped.scope('generation'), self.assertRaisesRegex(RuntimeError, 'explicit'):
            wrapped(input_ids=FakeTensor([[1]]*4), past_key_values=object(), use_cache=True)
        self.assertEqual(model.calls, [])

    def test_inference_bound_keeps_separate_control_reservation(self):
        wrapped, _ = adapter(generation_limit=1)
        with wrapped.scope('generation'):
            wrapped(input_ids=FakeTensor([[1]]*4), use_cache=True)
            with self.assertRaisesRegex(RuntimeError, 'ceiling'):
                wrapped(input_ids=FakeTensor([[1]]*4), use_cache=True)
        with wrapped.scope('control'):
            wrapped(input_ids=FakeTensor([[1]]*4), use_cache=True)
        self.assertEqual(wrapped.reserved, {'control': 1, 'generation': 1, 'verification': 0})

    def test_failed_model_entry_stays_reserved_not_completed(self):
        model = FakeModel(); wrapped, events = adapter(model)
        with wrapped.scope('generation'):
            with patch.object(FakeModel, '__call__', side_effect=ValueError('fixture failure')):
                with self.assertRaises(ValueError):
                    wrapped(input_ids=FakeTensor([[1]]*4), use_cache=True)
        self.assertEqual(wrapped.reserved['generation'], 1)
        self.assertEqual(wrapped.completed['generation'], 0)
        self.assertEqual(len(events), 1)

    def test_only_four_view_shapes_and_legal_prefill_positions(self):
        for values, kwargs in (([[1]], {}), ([[1]]*4, {'position_ids': FakeTensor([[1]]*4)})):
            wrapped, _ = adapter()
            with wrapped.scope('generation'), self.assertRaises(RuntimeError):
                wrapped(input_ids=FakeTensor(values), use_cache=True, **kwargs)

    def test_known_finite_vocabulary_controls_do_not_claim_full_parity(self):
        rows = [[9.0]+[0.0]*15 for _ in range(4)]
        result = runtime.compare_vectors(rows, rows)
        self.assertTrue(result['gate_passed']); self.assertFalse(result['full_numerical_parity_claim'])
        changed = [[0.0,9.0]+[0.0]*14 for _ in range(4)]
        self.assertFalse(runtime.compare_vectors(rows, changed)['gate_passed'])

    def test_source_batch_partition_and_denominator(self):
        keys = [f'fixture_0.{i:02}' for i in range(16)]
        result = runtime.source_batches(keys)
        self.assertEqual(result[0], [keys[0],keys[1],keys[4],keys[5]])
        self.assertEqual(len({key for batch in result for key in batch}), 16)
        with self.assertRaises(RuntimeError): runtime.source_batches(keys[:-1])

    def test_visible_rejects_truth_illegal_grids_or_unplanned_test_count(self):
        self.assertEqual(runtime.validate_visible(visible()), 'fixture')
        wrong = visible(); wrong['fixture']['test'][0]['output'] = [[1]]
        with self.assertRaises(RuntimeError): runtime.validate_visible(wrong)
        wrong = visible(); wrong['fixture']['test'] *= 2
        with self.assertRaises(RuntimeError): runtime.validate_visible(wrong)
        with self.assertRaises(RuntimeError): runtime.grid_key([[True]])

    def test_worker_derivation_compiles_and_does_not_reuse008_identity(self):
        source = legacy.portable_worker().decode().replace("plan['owner_decision']=='Decision 0054'",
                                                          "plan['owner_decision']=='Decision 0056'")
        generated = render.worker(source).decode()
        self.assertIn(render.FORMAT, generated)
        self.assertIn("plan['maximum_generations']==4", generated)
        self.assertIn('finally:', generated)
        self.assertNotIn("plan['owner_decision']=='Decision 0056'", generated)
        tree = ast.parse(generated)
        emit = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'emit')
        with tempfile.TemporaryDirectory() as temp:
            namespace = {'output': Path(temp), 'time': time, 'started': time.monotonic(), 'json': json}
            exec(compile(ast.Module(body=[emit], type_ignores=[]), 'synthetic-emitter', 'exec'), namespace)
            namespace['emit']('synthetic', value=1)
            namespace['emit']('synthetic', value=2)
            body = (Path(temp)/'solve-events.jsonl').read_bytes()
            self.assertTrue(body.endswith(b'\n'))
            self.assertEqual([json.loads(line)['value'] for line in body.splitlines()], [1,2])

    def test_inert_parent_stops_before_runtime_and_retains_archive(self):
        plan = {'run_id': 'nvarc-original-qwen3-native-solve-001', 'approved': False,
                'controller_admission_sha256': None}
        raw = {'plan': json.dumps(plan).encode(), 'source_inventory': b'{}',
               'model_inventory': b'{}', 'schedule': b'# fixture', 'editor_archive': editor.ARCHIVE.read_bytes()}
        source = render.parent(editor.render(plan, raw))
        with tempfile.TemporaryDirectory() as temp:
            source = source.replace("Path('/kaggle/working')", 'Path('+repr(temp)+')')
            with patch('sys.stdout', new_callable=io.StringIO), self.assertRaisesRegex(RuntimeError, 'inert package'):
                exec(compile(source, 'inert-parent-fixture', 'exec'), {})
            self.assertTrue((Path(temp)/'結果.zip').is_file())
            terminal = json.loads((Path(temp)/plan['run_id']/'terminal.json').read_bytes())
            self.assertEqual(terminal['model_forwards'], 0)
            self.assertEqual(terminal['generations'], 0)

    def test_admitted_render_passes_manual_gate_and_download_never_runs_model(self):
        plan={'run_id':'nvarc-original-qwen3-native-solve-001','approved':True,
              'controller_admission_sha256':'synthetic-controller-binding'}
        raw={'plan':json.dumps(plan).encode(),'source_inventory':b'{}','model_inventory':b'{}',
             'schedule':b'# fixture','editor_archive':editor.ARCHIVE.read_bytes()}
        source=render.parent(editor.render(plan,raw))
        with tempfile.TemporaryDirectory() as temp:
            source=source.replace("Path('/kaggle/working')",'Path('+repr(temp)+')')
            with patch('sys.stdout',new_callable=io.StringIO),patch('sys.version_info',(3,12,0)), \
                    self.assertRaisesRegex(RuntimeError,'original Python version'):
                exec(compile(source,'admitted-parent-fixture','exec'),{})
            download=stage.download_cell(plan).replace("Path('/kaggle/working/結果.zip')",'Path('+repr(str(Path(temp)/'結果.zip'))+')')
            with patch('sys.stdout',new_callable=io.StringIO):
                exec(compile(download,'standalone-download-fixture','exec'),{})
            tree=ast.parse(download)
            imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)]
            self.assertNotIn('torch',imports)

    def test_save_fields_are_quick_save_only_with_exact_manual_envelope(self):
        run='nvarc-original-qwen3-native-solve-001'
        plan={'run_id':run,'format':render.FORMAT,'owner_decision':'dots-control-kit-v1.2.0',
            'owner_execution_instruction_ref':stage.OWNER_RUN_INSTRUCTION,'approved':True,
            'maximum_notebook_wall_seconds':3600,'maximum_child_wall_seconds':3000,
            'controller_admission_sha256':'synthetic','agent_execution_authorized':False,
            'save_helper_status_calls':0,'owner_editor_only':True,'kernel_execution_type':'QUICK_SAVE'}
        metadata={'id':'danielwuu/'+run,'title':run,'is_private':True,'enable_internet':False,
            'enable_gpu':True,'dataset_sources':[],'competition_sources':['arc-prize-2026-arc-agi-2'],
            'kernel_sources':['synthetic'],'model_sources':['synthetic'],'docker_image':'synthetic'}
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp);(package/'kernel').mkdir()
            (package/'kernel/kernel-metadata.json').write_text(json.dumps(metadata))
            (package/'kernel/notebook.ipynb').write_text(json.dumps({'cells':[
                {'cell_type':'code','execution_count':None,'outputs':[],'source':['pass\n']}]}))
            (package/'plan.json').write_text(json.dumps(plan))
            fields=transport.request_fields(package)
            self.assertEqual(fields['kernel_execution_type'],'QUICK_SAVE')
            self.assertEqual(fields['machine_shape'],'NvidiaL4')
            for delta in ({'kernel_execution_type':'SAVE_AND_RUN_ALL'}, {'approved':False},
                          {'agent_execution_authorized':True},{'owner_editor_only':False}):
                (package/'plan.json').write_text(json.dumps({**plan,**delta}))
                with self.subTest(delta=delta),self.assertRaises(AssertionError):
                    transport.request_fields(package)


class NativeFailureAccountingTests(unittest.TestCase):
    def test_reader_rejects_negative_tokens_invalid_shapes_and_completion_before_reservation(self):
        plan={'inference_forward_limits':{'control':7,'generation':2,'verification':2},
            'maximum_control_input_tokens':168,'maximum_inference_input_tokens':100}
        entry={'event':'forward_reserved','call_id':1,'phase':'generation','batch_shape':[4,2],
            'physical_input_tokens':8,'cached':False,'position_start':0,'position_end':1}
        done={'event':'forward_completed','call_id':1,'phase':'generation','output_contract':'tuple-logits-cache'}
        self.assertEqual(reader.validate_inference_events([entry,done],plan)[2]['generation'],1)
        for delta in ({'physical_input_tokens':-1},{'batch_shape':[True,2]},{'position_end':8192},
                      {'call_id':True},{'phase':'unknown'}):
            with self.subTest(delta=delta),self.assertRaises(RuntimeError):
                reader.validate_inference_events([{**entry,**delta},done],plan)
        with self.assertRaises(RuntimeError):reader.validate_inference_events([done,entry],plan)

    def test_sparse_source_rows_and_malformed_rows(self):
        self.assertEqual(runtime.source_result_rows([]), {})
        self.assertEqual(runtime.source_result_rows([(2, []), (0, [])]), {2: [], 0: []})
        for rows in (None, [(True, [])], [(4, [])], [(0, []), (0, [])], [(0, ())], [[0]]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                runtime.source_result_rows(rows)

    def test_failure_outcomes_require_exact_evidence_and_cannot_mask_process_failure(self):
        error={'phase':'post_reset_control','error_type':'RuntimeError','error_message':'synthetic'}
        result={'outcome':'failed','failures':[error]}
        self.assertEqual(reader.qualified_outcome({'outcome':'failed'},result,{'failures':[error]}),'failed')
        for terminal, evidence in (({'outcome':'complete'},{'failures':[error]}),({'outcome':'failed'},None)):
            with self.assertRaises(RuntimeError):reader.qualified_outcome(terminal,result,evidence)
        for outcome in ('complete','inconclusive'):
            self.assertEqual(reader.qualified_outcome({'outcome':'failed'},
                {'outcome':outcome,'failures':[]},None),'failed')
            with self.assertRaises(RuntimeError):reader.qualified_outcome({'outcome':'complete'},
                {'outcome':outcome,'failures':[error]},{'failures':[error]})
        with self.assertRaises(RuntimeError):reader.qualified_outcome({'outcome':'complete'},
            {'outcome':'unknown','failures':[]},None)

    def test_sparse_coverage_rejects_reduced_attempt_denominator(self):
        row={'batch_index':0,'attempted_views':4,'returned_row_ids':[0,2],
            'absent_rows':2,'explicit_empty_rows':0,'rows_with_sequences':2,'empty_rows':2}
        result={'generation_batch_coverage':[row],'completed_generation_batches':1,
            'reserved_generation_batches':1,'attempted_source_views':4,'completed_source_views':4,
            'unfinished_source_views':0,'source_views_without_sequences':2}
        reader.validate_batch_coverage(result)
        for change in ({'attempted_source_views':2},{'source_views_without_sequences':0}):
            with self.assertRaises(RuntimeError):reader.validate_batch_coverage({**result,**change})
        wrong=copy.deepcopy(result);wrong['generation_batch_coverage'][0]['returned_row_ids']=[0,0]
        with self.assertRaises(RuntimeError):reader.validate_batch_coverage(wrong)

    def _finalizer(self, fail_phases=(), primary=False, nonempty=True):
        node=ast.parse('def worker():\n'+render.TAIL).body[0]
        original=next(n for n in node.body if isinstance(n,ast.Try))
        body=[ast.Raise(exc=ast.Call(func=ast.Name(id='RuntimeError',ctx=ast.Load()),
                args=[ast.Constant(value='synthetic primary')],keywords=[]),cause=None)] if primary else [ast.Pass()]
        # Execute the actual exception handler/finalizer and trailing rethrow.
        test_try=ast.Try(body=body,handlers=original.handlers,orelse=[],finalbody=original.finalbody)
        tail=node.body[node.body.index(original)+1:]
        program=ast.fix_missing_locations(ast.Module(body=[test_try]+tail,type_ignores=[]))
        saved={};attempts=[]
        def maybe(phase):
            attempts.append(phase)
            if phase in fail_phases:raise RuntimeError('synthetic '+phase)
        def release():maybe('optimizer_cleanup')
        def restore(*_a,**_kw):maybe('adapter_restoration')
        def control(*_a):maybe('post_reset_control');return {'prefill_bitwise_equal':True}
        trainer=SimpleNamespace(optimizer=None,lr_scheduler=None,
            accelerator=SimpleNamespace(_optimizers=[],_schedulers=[]))
        ns={'release_optimizer':release,'set_peft_model_state_dict':restore,'model':object(),'defaults':{},
            'tensor_inventory':lambda *_a:[],'get_peft_model_state_dict':lambda *_a,**_k:{},'baseline':[],
            'require':runtime.require,'save':lambda name,value:saved.update({name:copy.deepcopy(value)}),
            'reset_verified':False,'control':{},'FastLanguageModel':SimpleNamespace(for_inference=lambda m:m),
            'reset_control':control,'adapter':SimpleNamespace(reserved={},completed={},input_tokens=0,input_by_phase={}),
            'failures':[],'pending_error':None,'solve':{'outcome':'complete' if nonempty else 'inconclusive'},
            'post_reset':None,'plan':{'run_id':'synthetic'},'digest':lambda _p:'synthetic','training_complete':True,
            'trainer':trainer,'elapsed':1,'started':time.monotonic(),'time':time,'budget':None,
            'torch':SimpleNamespace(cuda=SimpleNamespace(max_memory_allocated=lambda:0,max_memory_reserved=lambda:0))}
        ns['model'] = SimpleNamespace(parameters=lambda: [])
        if fail_phases or primary:
            with self.assertRaises(RuntimeError):exec(compile(program,'exact-finalizer-fixture','exec'),ns)
        else:exec(compile(program,'exact-finalizer-fixture','exec'),ns)
        return saved,attempts

    def test_post_reset_failure_is_saved_and_failed(self):
        saved,attempts=self._finalizer(('post_reset_control',))
        result=saved['pipeline-result.json']
        self.assertEqual(result['outcome'],'failed')
        self.assertTrue(result['all_saved_tensors_restored'])
        self.assertFalse(result['post_reset_control_verified'])
        self.assertEqual(saved['pipeline-failure.json']['failures'],result['failures'])
        self.assertEqual(attempts,['optimizer_cleanup','adapter_restoration','post_reset_control'])

    def test_optimizer_failure_still_attempts_restoration_and_control(self):
        saved,attempts=self._finalizer(('optimizer_cleanup',))
        self.assertEqual(saved['pipeline-result.json']['outcome'],'failed')
        self.assertTrue(saved['pipeline-result.json']['all_saved_tensors_restored'])
        self.assertEqual(attempts,['optimizer_cleanup','adapter_restoration','post_reset_control'])

    def test_restoration_failure_retains_primary_and_all_cleanup_failures(self):
        saved,attempts=self._finalizer(('optimizer_cleanup','adapter_restoration'),primary=True)
        result=saved['pipeline-result.json']
        self.assertEqual([row['phase'] for row in result['failures']],
                         ['pipeline','optimizer_cleanup','adapter_restoration'])
        self.assertFalse(result['all_saved_tensors_restored'])
        self.assertFalse(result['post_reset_control_verified'])
        self.assertNotIn('post_reset_control',attempts)

    def test_success_and_valid_empty_solve_keep_distinct_outcomes(self):
        for nonempty in (True,False):
            saved,_=self._finalizer(nonempty=nonempty)
            self.assertEqual(saved['pipeline-result.json']['outcome'],'complete' if nonempty else 'inconclusive')
            self.assertEqual(saved['pipeline-result.json']['failures'],[])
            self.assertNotIn('pipeline-failure.json',saved)


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional exact-source NumPy fixture dependency unavailable')
class OriginalSourceSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(os.environ.get('IRIS_NATIVE_CODE_ONLY_DIR',
            str(Path(__file__).resolve().parents[1]/'.irisx/native-code-source')))
        if not all((cls.directory/name).is_file() for name in runtime.SOURCE_HASHES):
            raise unittest.SkipTest('explicit hash-bound code-only source fixture not installed')
        import numpy as np
        cls.loader, cls.solver, cls.decoder = runtime.load_sources(cls.directory, FakeTorch, np)

    def test_no_truth_loader_or_upstream_convenience_score_exposed(self):
        self.assertFalse(hasattr(self.loader.ArcDataset, 'load_replies'))
        self.assertFalse(hasattr(self.loader.ArcDataset, 'validate_submission'))
        self.assertFalse(hasattr(self.decoder, 'ArcDecoder'))
        self.assertFalse(hasattr(self.solver, 'worker'))

    def test_real_source_augmentation_inverse_and_rank_with_fixture_candidates(self):
        self._fixture(nonempty=True)

    def test_empty_real_source_ranking_is_inconclusive(self):
        self._fixture(nonempty=False)

    def test_exact_dfs_uniform_logits_returns_no_rows_and_counts_all_views(self):
        self._exact_dfs_fixture(partial=False)

    def test_exact_dfs_partial_eos_rows_do_not_drop_attempted_views(self):
        self._exact_dfs_fixture(partial=True)

    def _exact_dfs_fixture(self, partial):
        import numpy as np
        import re
        class Array:
            def __init__(self,x):self.value=np.asarray(x)
            @property
            def shape(self):return self.value.shape
            def size(self,n):return self.value.shape[n]
            def view(self,*shape):return Array(self.value.reshape(*shape))
            def __getitem__(self,key):return Array(self.value[key])
            def __sub__(self,other):return Array(self.value-other.value)
            def float(self):return self
            def cpu(self):return self
            def item(self):return self.value.item()
            def log_softmax(self,axis):
                x=self.value-self.value.max(axis=axis,keepdims=True)
                return Array(x-np.log(np.exp(x).sum(axis=axis,keepdims=True)))
        class Torch:
            long='long';float32='float32'
            @staticmethod
            def tensor(x,**_kwargs):return Array(x)
            @staticmethod
            def no_grad():return lambda function:function
        class Fixture:
            device='fixture';generation_deadline=time.time()+60
            def __init__(self):self.calls=0
            @contextmanager
            def scope(self,phase):yield
            def __call__(self,input_ids,**_kwargs):
                self.calls+=1
                logits=np.zeros((*input_ids.shape,16))
                if partial:logits[[0,2],:,15]=20.
                return SimpleNamespace(logits=Array(logits),past_key_values=object())
        class Tokens:
            def encode(self,text):
                vocab={'<|im_start|>':14,'<|im_end|>':15,'user':11,'assistant':12,'\n':10}
                return [vocab[t] if t in vocab else int(t) for t in
                    re.findall(r'<\|im_start\|>|<\|im_end\|>|user|assistant|\n|[0-9]',text)]
            def decode(self,tokens):return ''.join('\n' if t==10 else str(t) for t in tokens)
        loader,solver,decoder=runtime.load_sources(self.directory,Torch,np)
        fixture=Fixture()
        source_rows=solver.inference_turbo_dfs(fixture,[[1,2]]*4,931,-np.log(.2),fixture.generation_deadline)
        self.assertEqual([row[0] for row in source_rows],[0,2] if partial else [])
        fixture=Fixture()
        result=runtime.solve_visible(visible(),loader,solver,decoder,Tokens(),fixture,task_started=time.time())
        self.assertEqual(fixture.calls,4)
        self.assertEqual(result['outcome'],'inconclusive')
        self.assertEqual(result['completed_generation_batches'],4)
        self.assertEqual(result['attempted_source_views'],16)
        self.assertEqual(result['source_views_without_sequences'],8 if partial else 16)
        self.assertEqual(result['invalid_parsed_candidates'],8 if partial else 0)
        self.assertEqual(result['ranked_grids'],[])
        self.assertEqual(result['missing_attempts'],2)
        reader.validate_batch_coverage(result)

    def test_sparse_valid_fixture_candidates_can_complete_without_full_row_return(self):
        self._fixture(nonempty=True, sparse=True)

    def test_source_binding_rejects_changed_code_before_loading(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            for name in runtime.SOURCE_HASHES:(path/name).write_bytes((self.directory/name).read_bytes())
            (path/'solver.py').write_bytes((path/'solver.py').read_bytes()+b'\n')
            with self.assertRaisesRegex(RuntimeError,'exact original code cell differs'):
                runtime.load_sources(path,FakeTorch,np)

    def test_bounded_generation_stop_preserves_verified_candidates_as_inconclusive(self):
        self._fixture(nonempty=True,stop_phase='generation')

    def test_bounded_verification_stop_preserves_prior_candidate_votes_as_inconclusive(self):
        self._fixture(nonempty=True,stop_phase='verification')

    def test_multiple_candidates_source_votes_likelihood_and_inverse_recompute(self):
        import re
        class Tokens:
            def encode(self,text):
                vocab={'<|im_start|>':14,'<|im_end|>':15,'user':11,'assistant':12,'\n':10}
                return [vocab[t] if t in vocab else int(t) for t in
                    re.findall(r'<\|im_start\|>|<\|im_end\|>|user|assistant|\n|[0-9]',text)]
            def decode(self,tokens):return ''.join('\n' if t==10 else str(t) for t in tokens)
        tokenizer=Tokens();formatter=self.loader.QwenFormatter(tokenizer)
        puzzle=self.loader.ArcDataset(queries=visible(),keys=['fixture']).split_multi_replies()
        state=self.loader.np.random.get_state()
        try:
            views=puzzle.augment(n=2,seed=2).cut_to_len(formatter=formatter,name='input',max_len=8192-931)
        finally:self.loader.np.random.set_state(state)
        batches=runtime.source_batches(views.keys);batch_calls=[];verification=[]
        canonical=[visible()['fixture']['test'][0]['input'],[[9]]]
        def infer(*_args):
            index=len(batch_calls);batch_calls.append(index);result=[]
            for row,key in enumerate(batches[index]):
                choices=canonical if index==row==0 else canonical[:1]
                result.append((row,[(.1,tokenizer.encode(formatter.fmt_reply([
                    puzzle.forward_mod(self.loader.np.asarray(g),key).tolist()]))) for g in choices]))
            return result
        def scores(*_args):
            value=2. if len(verification)<2 else .1
            verification.append(value);return [value]*4
        class Adapter:
            generation_deadline=time.time()+60
            @contextmanager
            def scope(self,_phase):yield
        events=[]
        result=runtime.solve_visible(visible(),self.loader,SimpleNamespace(inference_turbo_dfs=infer,
            calc_scores=scores),self.decoder,tokenizer,Adapter(),task_started=time.time(),
            emit=lambda event,**details:events.append({'event':event,**details}))
        self.assertEqual(result['raw_candidates'],17);self.assertEqual(len(verification),4)
        self.assertEqual(result['ranked_grids'],canonical)  # 16 votes - 2 NLL beats 1 vote - .1 NLL.
        raw={'loader':(self.directory/'arc_loader.py').read_bytes(),'decoder':(self.directory/'arc_decoder.py').read_bytes()}
        reader.validate_solve_evidence(result,events,raw)
        wrong=copy.deepcopy(result);wrong['ranked_grids'].reverse();wrong['attempts'].reverse()
        with self.assertRaisesRegex(RuntimeError,'ranking differs'):reader.validate_solve_evidence(wrong,events,raw)

    def _fixture(self, nonempty, sparse=False, stop_phase=None):
        class Tokens:
            def encode(self, text):
                import re
                vocabulary={'<|im_start|>':14,'<|im_end|>':15,'user':11,'assistant':12,'\n':10}
                return [vocabulary[t] if t in vocabulary else int(t)
                    for t in re.findall(r'<\|im_start\|>|<\|im_end\|>|user|assistant|\n|[0-9]', text)]
            def decode(self, tokens): return ''.join('\n' if t==10 else str(t) for t in tokens)
        class FixtureAdapter:
            generation_deadline=time.time()+60
            @contextmanager
            def scope(self, _phase): yield
        calls=[]
        def infer(_model, prefixes, _max_tokens, _score, _deadline):
            if stop_phase=='generation' and calls.count('generation')==1:
                raise runtime.InferenceLimitReached('forward_limit')
            result=[]
            for index, prefix in enumerate(prefixes):
                if sparse and index not in (0,2):continue
                user=max(i for i,value in enumerate(prefix) if value==11)
                end=prefix.index(15,user)
                result.append((index,[(.1,prefix[user+2:end]+[15])] if nonempty else []))
            if stop_phase=='verification':
                # First candidate can be verified; a distinct second grid reaches the ceiling.
                result[1]=(1,[(.1,[0,15])])
            calls.append('generation');return result
        def scores(queries, answers, _tokenizer, _model):
            if stop_phase=='verification' and calls.count('verification')==2:
                raise runtime.InferenceLimitReached('forward_limit')
            self.assertEqual((len(queries),len(answers)),(4,4));calls.append('verification');return [1.]*4
        solver=SimpleNamespace(inference_turbo_dfs=infer,calc_scores=scores)
        events=[]
        result=runtime.solve_visible(visible(),self.loader,solver,self.decoder,Tokens(),FixtureAdapter(),
            task_started=time.time(),emit=lambda event,**details:events.append({'event':event,**details}))
        self.assertEqual(calls.count('generation'),1 if stop_phase else 4)
        self.assertEqual(result['outcome'],'complete' if nonempty and not stop_phase else 'inconclusive')
        self.assertFalse(result['correctness_scored'])
        if nonempty:
            self.assertEqual(calls.count('verification'),2)  # one unique grid, eight source views
            self.assertEqual(result['ranked_grids'],[visible()['fixture']['test'][0]['input']])
            self.assertEqual(result['raw_candidates'],2 if stop_phase=='verification' else 4 if stop_phase else 8 if sparse else 16)
            self.assertEqual(result['source_views_without_sequences'],4 if stop_phase=='generation' else 8 if sparse else 0)
            if stop_phase=='generation':
                self.assertEqual(result['attempted_source_views'],8)
                self.assertEqual(result['completed_source_views'],4)
                self.assertEqual(result['unfinished_source_views'],4)
        reader.validate_batch_coverage(result)
        raw={'loader':(self.directory/'arc_loader.py').read_bytes(),'decoder':(self.directory/'arc_decoder.py').read_bytes()}
        reader.validate_solve_evidence(result,events,raw)
        if nonempty:
            wrong=copy.deepcopy(result);wrong['ranked_grids']=[[[9]]]
            with self.assertRaisesRegex(RuntimeError,'ranking differs'):
                reader.validate_solve_evidence(wrong,events,raw)
            wrong=copy.deepcopy(events)
            next(row for row in wrong if row['event']=='candidate_ranked')['source_tokens']=[9,15]
            with self.assertRaises(RuntimeError):reader.validate_solve_evidence(result,wrong,raw)


if __name__ == '__main__':
    unittest.main()
