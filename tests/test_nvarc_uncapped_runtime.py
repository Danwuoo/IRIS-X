"""CPU-only inert notebook/admission checks for the separate uncapped package."""
from tests.platform_requirements import requires_linux
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import stage_nvarc_uncapped_notebook as builder
from tools.nvarc_native_multitask import canonical, digest


def _load_linux_runtime():
    global runtime
    from tools import nvarc_uncapped_runtime as runtime

def minimal_plan():
    return dict(format=runtime.FORMAT,run_id=runtime.RUN_ID,screen_id=runtime.RUN_ID,
        kernel_execution_type='QUICK_SAVE',owner_editor_only=True,agent_execution_authorized=False,
        approved_for_runtime=False,resource_admission=None,paid_usd_ceiling=0,official_submission=False,
        resource_policy='no-program-capacity-or-time-caps',removed_resource_caps=list(builder.RESOURCE_CAPS),
        **{key:None for key in builder.RESOURCE_CAPS},scientific_contract=dict(builder.SCIENTIFIC),
        test_counts={'195c6913':2,'aa4ec2a5':1,'a47bf94d':1,'a25697e4':2},
        task_order=['195c6913','aa4ec2a5','a47bf94d','a25697e4'],payload_sha256={},
        scientific_design_confirmed=False)


class UncappedRuntimeTests(unittest.TestCase):
    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_caps_none_but_scientific_bounds_remain(self):
        _load_linux_runtime()
        plan=minimal_plan();self.assertIs(runtime.verify_plan(plan),plan)
        for key in builder.RESOURCE_CAPS:
            changed=copy.deepcopy(plan);changed[key]=999999999
            with self.assertRaises(RuntimeError):runtime.verify_plan(changed)
        for key in ('training_updates_per_task','source_views','answer_grammar_tokens','model_context_tokens'):
            changed=copy.deepcopy(plan);changed['scientific_contract'][key]+=1
            with self.assertRaises(RuntimeError):runtime.verify_plan(changed)

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_default_notebook_cells_do_no_setup(self):
        _load_linux_runtime()
        plan=minimal_plan();raw={'plan.json':canonical(plan),'screen.json':canonical(plan)}
        notebook=builder.render(plan,raw);namespace={}
        with patch('subprocess.Popen',side_effect=AssertionError('must remain inert')):
            for cell in notebook['cells'][1:]:exec(''.join(cell['source']),namespace)
        self.assertIs(namespace[builder.CONFIG_NAME],False)
        self.assertNotIn('work',namespace);self.assertNotIn('PACKED',namespace)
        self.assertTrue(all(c.get('outputs',[])==[] for c in notebook['cells']))
        source=''.join(notebook['cells'][2]['source']);self.assertNotIn('timeout=',source)
        self.assertNotIn('sessionTimeoutSeconds',source)
        self.assertIn("observation.get('success') is not True",source)
        # The final notebook guard rejects a zero-return coordinator whose
        # logging or worker-registry supervision did not succeed.
        guard=ast.parse(source).body[0].orelse[-1]
        self.assertIsInstance(guard,ast.If)
        for observation in (dict(returncode=0,success=False,errors=[]),dict(returncode=0,success=True,errors=['capture'])):
            with self.assertRaises(RuntimeError):exec(compile(ast.Module(body=[guard],type_ignores=[]),'final-guard','exec'),dict(observation=observation))

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_notebook_payload_rendering_is_order_independent(self):
        _load_linux_runtime()
        plan=minimal_plan();raw={'plan.json':canonical(plan),'screen.json':canonical(plan),'a.py':b'pass'}
        self.assertEqual(builder.render(plan,raw),builder.render(plan,dict(reversed(list(raw.items())))))

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_confirmed_execution_rejects_pending_science_and_tampered_payload(self):
        _load_linux_runtime()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);plan=minimal_plan();raw=canonical(plan)
            (root/'plan.json').write_bytes(raw);(root/'screen.json').write_bytes(raw)
            pin=hashlib.sha256(raw).hexdigest()
            self.assertEqual(runtime.verify_runtime(root,pin),plan)
            with self.assertRaisesRegex(RuntimeError,'experimental design'):
                runtime.verify_runtime(root,pin,confirmed=True)
            with self.assertRaisesRegex(RuntimeError,'plan pin'):
                runtime.verify_runtime(root,'0'*64)
            with self.assertRaises(RuntimeError):runtime.write_confirmation(root,plan,False)

    def test_no_watchdog_or_subprocess_timeout_in_active_runtime(self):
        source=Path('tools/nvarc_uncapped_runtime.py').read_text();tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                self.assertNotIn('timeout',{kw.arg for kw in node.keywords})
        self.assertNotIn('time.time()<deadline',source)
        self.assertNotIn('time.monotonic() < end',source)
        self.assertIn('budget.installed()',source)
        self.assertNotIn('training_deadline(',source)

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_retained_control_replay_reaches_complete_seventh_call(self):
        _load_linux_runtime()
        from tools.nvarc_uncapped_artifacts import StreamEvents,atomic_json
        bound=dict(rank=0,probe_id=runtime.RUN_ID)
        vector=[[float(i) for i in range(16)] for _ in range(4)]
        reset=dict(prefill_bitwise_equal=True,prefill=vector,synthetic_tokens_only=True,additional_model_calls=1)
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            with StreamEvents(directory/'events.jsonl',bound) as events:
                for call,(width,cached,start) in enumerate(((9,False,0),(1,True,9),(1,True,10),(1,True,9),
                        (11,False,0),(10,False,0),(9,False,0)),1):
                    if call==7:
                        events.emit('cache_control_result',baseline_prefill=vector,deep_reference=vector,deep_cached=vector,
                            sibling_reference=vector,sibling_cached=vector,comparisons={
                                'deep':runtime.compare_vectors(vector,vector),
                                'sibling_after_deep':runtime.compare_vectors(vector,vector)})
                    events.emit('forward_reserved',call_id=call,phase='control',batch_shape=[4,width],
                        physical_input_tokens=4*width,cached=cached,position_start=start,position_end=start+width-1)
                    events.emit('forward_completed',call_id=call,phase='control',output_contract='tuple-logits-cache')
            atomic_json(directory/'post-reset-control.json',reset)
            counts=dict(reserved_forwards=7,completed_forwards=7,reserved_physical_input_tokens=168)
            self.assertEqual(runtime.verify_controls(directory,dict(controls=counts,post_reset_control=reset),bound),counts)

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_partial_training_counts_completed_updates_without_claiming_epoch(self):
        _load_linux_runtime()
        from types import SimpleNamespace
        self.assertEqual(runtime.completed_training_updates(None),0)
        budget=SimpleNamespace(state={'optimizer_steps':[{'completed':True} for _ in range(7)]+[{'completed':False}]})
        self.assertEqual(runtime.completed_training_updates(budget),7)
        budget.state['optimizer_steps']=[{'completed':True} for _ in range(128)]
        self.assertEqual(runtime.completed_training_updates(budget),128)

    @requires_linux('Native Trainer hook module imports POSIX resource-bound epoch runtime')
    def test_training_derivative_changes_only_message_slice_and_retains_full_error(self):
        from tools import nvarc_uncapped_training as full
        from tests import test_nvarc_e12_training as fixture
        original=Path('tools/nvarc_e12_training.py').read_text()
        self.assertEqual(ast.dump(ast.parse(Path(full.__file__).read_text())),
            ast.dump(ast.parse(original.replace('str(error)[:1000]','str(error)'))))
        fixture._load_linux_runtime()
        hooks=fixture.HookTests();hooks.setUp()
        try:
            with patch.object(fixture,'native',full):
                engine,trainer,budget=hooks.setup('ttt128')
                message='uncropped-'+('x'*9000)
                with hooks.environment(engine):
                    with self.assertRaisesRegex(RuntimeError,'uncropped'),budget.installed():
                        raise RuntimeError(message)
                self.assertEqual(budget.native_errors[0]['message'],message)
                self.assertEqual(hooks.saved['native-hook-status.json']['errors'][0]['message'],message)
                engine,trainer,budget,moments,trace=hooks.run_arm('ttt128')
                self.assertEqual(trainer.update_calls,128);self.assertEqual(len(trace['steps']),128)
                self.assertTrue(trace['complete'])
        finally:hooks.tearDown()

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_transition_failure_retains_full_message_and_traceback(self):
        _load_linux_runtime()
        from types import SimpleNamespace
        from tools.nvarc_uncapped_artifacts import read_json
        message='transition-'+('y'*9000)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary);engine=SimpleNamespace(model=object())
            with patch.object(runtime.native_epoch,'forward_observation',side_effect=RuntimeError(message)):
                with self.assertRaisesRegex(RuntimeError,'transition'):
                    runtime.inference_transition(engine,None,output,{},'trained')
            receipt=read_json(output/'trained-inference-transition.json')
            self.assertEqual(receipt['errors'][0]['message'],message)
            self.assertIn(message,receipt['errors'][0]['traceback'])
            self.assertEqual(receipt['status'],'failed')

    def test_new_notebook_metadata_has_no_old_numeric_identity(self):
        meta=builder.metadata(dict(docker_image='pinned-example'))
        self.assertEqual(meta['id'],builder.REF);self.assertEqual(meta['title'],builder.SLUG)
        self.assertTrue(meta['is_private']);self.assertFalse(meta['enable_internet'])
        self.assertNotIn('137327571',json.dumps(meta));self.assertNotIn('session_timeout_seconds',meta)
        self.assertEqual(meta['kernel_sources'],['sorokin/pip-install-unsloth-flash-patch/2'])


if __name__=='__main__':unittest.main()
