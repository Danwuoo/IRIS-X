"""Offline E10 package/scheduler fixtures; fake children never invoke a model."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import nvarc_e10_screen as runtime
from tools import stage_nvarc_e10_screen as stage
from tools import verify_nvarc_e10_screen as verifier
from tools.nvarc_native_multitask import canonical, digest, write


def fixture():
    data = {'a': {'train': [{'input': [[1]], 'output': [[2]]}], 'test': [{'input': [[3]]}, {'input': [[4]]}]},
            'b': {'train': [{'input': [[5]], 'output': [[6]]}], 'test': [{'input': [[7]]}]}}
    config = {key: 'synthetic' for key in stage.CONFIG_FIELDS}
    config.update(versions={}, original_peft_parameters={}, original_training_arguments={},
        native_trainer_origins=[], native_checkpoint_flags=[], source_inferred_trainable_layout={},
        model_sources=['synthetic/no-model/transformers/fixture/1'], docker_image='synthetic-no-GPU',
        native_source_learning_rates=[.001]*129)
    external = {name: b'pass\n' if name.endswith('.py') else b'{}' for name in stage.EXTERNAL_FILES}
    external['verified-tokenizer.json'] = b'{}'
    materials = {key: {'texts': [{'key': key+'.r'+str(index), 'text': 'synthetic-demo-only'} for index in range(128)],
        'rows': [{'row': index, 'input_tokens': 8, 'supervised_tokens': 4} for index in range(128)]} for key in data}
    partition = {'challenges_digest': digest(data), 'task_order': list(data),
                 'exposure': 'synthetic fixture only; no ARC metric'}
    contract = {'source_provenance': 'synthetic fixture; no native material claims'}
    return stage.construct('stage4-e10-screen-synthetic', '0'*40, data, partition, external, config,
                           contract, materials, fixture=True)


FAKE_CHILD = '''import argparse,json,os,time
from pathlib import Path
from tools.nvarc_allocation_transport import AllocationClient
from tools.nvarc_native_submission import task_binding
from tools.nvarc_native_multitask import write
parser=argparse.ArgumentParser()
for name in ('plan','model','dependency','solver','texts','rows','output'):parser.add_argument('--'+name)
args=parser.parse_args();out=Path(args.output);out.mkdir()
root=Path(args.plan).parent;plan=json.loads(Path(args.plan).read_bytes());ch=json.loads((root/'challenges.json').read_bytes())
task=out.parent.name
if os.environ.get('IRIS_E10_FAKE_FAIL')==task: raise RuntimeError('synthetic calibration process failure')
client=AllocationClient(int(os.environ['IRIS_ALLOCATION_FD']),task_binding(plan,ch,task))
for index in range(len(ch[task]['test'])): client.request(index)
write(out/'result.json',{'training_complete':True,'all_saved_tensors_restored':True,
    'post_reset_control_verified':True,'optimizer_discarded':True,'telemetry':{'gpu_kernel_seconds':None}})
'''


class ScreenPackageTests(unittest.TestCase):
    def test_coordinator_startup_does_not_import_unverified_dependency_sitecustomize(self):
        screen,_plans,payload=fixture();source=''.join(stage.render(screen,payload)['cells'][1]['source'])
        assignment=next(node for node in ast.parse(source).body if isinstance(node,ast.Assign) and
            any(isinstance(target,ast.Name) and target.id=='env' for target in node.targets))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';root.mkdir();dependency=Path(tmp)/'unverified';dependency.mkdir()
            marker=Path(tmp)/'unexpected-startup-import'
            (dependency/'sitecustomize.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n')
            namespace={'os':os,'work':root,'matches':[dependency]}
            exec(compile(ast.Module(body=[assignment],type_ignores=[]),'notebook-env','exec'),namespace)
            self.assertEqual(namespace['env']['PYTHONPATH'],str(root))
            child=subprocess.run([sys.executable,'-c','print("stdlib startup only")'],env=namespace['env'],
                cwd=root,capture_output=True,text=True,timeout=10,check=True)
            self.assertIn('stdlib startup only',child.stdout);self.assertFalse(marker.exists())

    def test_rehashed_screen_metadata_cannot_omit_resource_competition(self):
        screen,plans,payload=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            package=Path(tmp)/'package';stage.stage(package,screen,plans,payload)
            path=package/'kernel/kernel-metadata.json';value=json.loads(path.read_bytes())
            value['competition_sources']=[];write(path,value)
            index=package/'package-manifest.json';manifest=json.loads(index.read_bytes())
            manifest['files_sha256']['kernel/kernel-metadata.json']=hashlib.sha256(path.read_bytes()).hexdigest();write(index,manifest)
            with self.assertRaisesRegex(RuntimeError,'exact private offline development metadata'):
                stage.preflight(package,allow_fixture=True)

    def test_closed_inert_notebook_package_and_exact_full_test_bounds(self):
        screen, plans, payload = fixture()
        self.assertEqual((screen['tasks'], screen['tests'], screen['task_runs'], screen['test_runs']), (2, 3, 8, 12))
        self.assertEqual(screen['training_steps_upper_bound'], 1024)
        self.assertEqual(screen['generation_forwards_upper_bound'], 12*4096)
        self.assertEqual(screen['processed_sequences_upper_bound'], 12*64)
        self.assertFalse(screen['approved_for_runtime'])
        self.assertEqual(screen['calibration_jobs'], ['interleaved-r1-a', 'interleaved-r1-b'])
        for key in ('a', 'b'):
            specs = [copy.deepcopy(plan['task_specs'][key]) for plan in plans.values()]
            for spec in specs: spec.pop('verification_schedule')
            self.assertTrue(all(spec == specs[0] for spec in specs))
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)/'package'; result = stage.stage(package, screen, plans, payload)
            self.assertTrue(result['offline_package_verified']); self.assertFalse(result['real_gpu_screen_run'])
            self.assertEqual(stage.preflight(package, allow_fixture=True,
                expected_manifest_sha256=result['package_manifest_sha256']), result)
            with self.assertRaisesRegex(RuntimeError, 'approved distinct'):
                stage.verify_runtime_tree(package/'runtime')
            metadata = json.loads((package/'kernel/kernel-metadata.json').read_bytes())
            self.assertTrue(metadata['is_private']); self.assertFalse(metadata['enable_internet'])
            self.assertEqual(metadata['competition_sources'], ['arc-prize-2026-arc-agi-2'])
            self.assertEqual(screen['resource_attachment']['scientific_input_scope'],
                'frozen public solver-visible development challenges only')
            notebook = json.loads((package/'kernel/notebook.ipynb').read_bytes())
            source = ''.join(notebook['cells'][1]['source']); ast.parse(source)
            self.assertNotIn('kaggle competitions submit', source)
            self.assertIn('PYTHONHASHSEED', source); self.assertIn('IRIS_NATIVE_PARENT_PID', payload['tools/nvarc_e10_screen.py'].decode())

    def test_native_render_has_one_main_new_admission_and_original_full_epoch_gates(self):
        source = stage.rendered_worker().decode(); tree = ast.parse(source)
        mains = [node for node in tree.body if isinstance(node, ast.If) and '__name__' in ast.unparse(node.test)]
        self.assertEqual(len(mains), 1)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        text = ast.unparse(function)
        self.assertIn('run_admitted_tests', text); self.assertIn('IRIS_ALLOCATION_FD', text)
        self.assertIn('expected_rows_digest', text); self.assertIn('post_reset_control_verified', text)
        self.assertNotIn('training-result.json', text); self.assertNotIn('fault-after-two-updates', text)
        self.assertIn("spec['selected_gpu_index']", text)
        self.assertIn("telemetry.scope('training')", text)
        self.assertIn("telemetry.scope('reset')", text)

    def test_frozen_development_order_survives_canonical_mapping_sort(self):
        screen, plans, payload = fixture()
        data = json.loads(payload['challenges.json']); partition = json.loads(payload['partition.json'])
        partition['task_order'] = ['b', 'a']
        config = {key: plans['interleaved-r1'][key] for key in stage.CONFIG_FIELDS}
        config['native_source_learning_rates'] = plans['interleaved-r1']['native_source_learning_rates']
        external = {name: payload[name] for name in stage.EXTERNAL_FILES}
        materials = {key: json.loads(payload['materials/'+key+'.json']) for key in data}
        altered, new_plans, _ = stage.construct(screen['screen_id'], screen['source_commit'], data, partition,
            external, config, json.loads(payload['material-contract.json']), materials, fixture=True)
        self.assertEqual(altered['calibration_jobs'], ['interleaved-r1-b', 'interleaved-r1-a'])
        self.assertTrue(all(plan['task_order'] == ['a', 'b'] for plan in new_plans.values()))

    def test_rehashed_metadata_source_budget_and_package_mutations_rejected(self):
        for mode in ('metadata', 'source', 'budget', 'notebook', 'pin'):
            screen, plans, payload = fixture()
            with tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp)/'package'; result = stage.stage(package, screen, plans, payload)
                if mode == 'metadata':
                    path = package/'kernel/kernel-metadata.json'; value = json.loads(path.read_bytes())
                    value['enable_internet'] = True; write(path, value)
                if mode == 'source':
                    path = package/'runtime/deferred-r1/tools/nvarc_allocation_transport.py'; path.write_bytes(path.read_bytes()+b'\n# tampered\n')
                if mode == 'budget':
                    path = package/'runtime/screen.json'; value = json.loads(path.read_bytes())
                    value['maximum_notebook_wall_seconds'] += 30; write(path, value)
                if mode == 'notebook':
                    path = package/'kernel/notebook.ipynb'; value = json.loads(path.read_bytes())
                    value['cells'][1]['source'].append('print("tampered")\n'); write(path, value)
                manifest = json.loads((package/'package-manifest.json').read_bytes())
                manifest['files_sha256'] = {path.relative_to(package).as_posix(): stage.sha(path)
                    for path in package.rglob('*') if path.is_file() and path.name != 'package-manifest.json'}
                if mode == 'pin': manifest['format'] = 'changed'
                write(package/'package-manifest.json', manifest)
                with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, 'differs|planning envelope required'):
                    stage.preflight(package, allow_fixture=True, expected_manifest_sha256=
                        result['package_manifest_sha256'] if mode == 'pin' else None)

    def test_missing_reviewed_materials_are_not_replaced_with_raw_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); contract = {'format': 'irisx/native-code-material-contract-v1',
                'files_sha256': {name: '0'*64 for name in stage.EXTERNAL_FILES},
                'template_sha256': stage.sha(__file__), 'tokenizer_sha256': stage.sha(__file__),
                'source_provenance': 'synthetic missing material test'}
            write(root/'contract.json', contract)
            with self.assertRaisesRegex(RuntimeError, 'material missing/differs: solver.py'):
                stage.read_materials(root, root/'contract.json', Path(__file__), Path(__file__))

    def test_five_hour_plan_and_quota_units_preserve_hard_resource_gate(self):
        screen, plans, payload = fixture()
        five = copy.deepcopy(screen)
        five.update(maximum_notebook_wall_seconds=18000, allocated_gpu_hours_upper_bound=20)
        admission = {'format': 'irisx/stage4-free-gpu-resource-admission-v1', 'screen_id': five['screen_id'],
            'paid_usd_ceiling': 0, 'quota_hours_available': 10, 'allocated_gpu_hours_per_quota_hour': 2,
            'quota_observed_at': '2026-10-06T08:00:00+00:00', 'provider_session_seconds': 18000,
            'private': True, 'internet': False, 'prior_sessions_reconciled': True,
            'rules_materials_review_ref': 'synthetic resource arithmetic only; no real admission'}
        stage.validate_resource_admission(admission, five,current=False)
        self.assertEqual(18000-five['startup_seconds']-five['packaging_reserve_seconds']-300,15300)
        with self.assertRaisesRegex(RuntimeError, 'quota/session'):
            stage.validate_resource_admission({**admission,'quota_hours_available':9.99}, five,current=False)
        three = copy.deepcopy(five); three.update(maximum_notebook_wall_seconds=10800,allocated_gpu_hours_upper_bound=12)
        three['task_child_seconds']={key:10000 for key in three['task_ids']}
        three['calibration_prefix_lane_seconds']=[sum(10000 for job in three['workload_order'] if job['rank']==rank and job['job_id'] in three['calibration_jobs']) for rank in range(4)]
        three['post_calibration_suffix_lane_seconds']=[sum(10000 for job in three['workload_order'] if job['rank']==rank and job['job_id'] not in three['calibration_jobs']) for rank in range(4)]
        three['barrier_aware_reserved_seconds']=max(three['calibration_prefix_lane_seconds'])+max(three['post_calibration_suffix_lane_seconds'])
        with self.assertRaisesRegex(RuntimeError, 'reservations'):
            stage.validate_resource_admission(admission, three,current=False)


@unittest.skipUnless(os.name == 'posix', 'POSIX fake task process scheduler')
class ScreenProcessTests(unittest.TestCase):
    def prepare(self, directory):
        screen, plans, payload = fixture(); root = Path(directory)
        for name, body in payload.items():
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        data = json.loads(payload['challenges.json']); hardware = [{'uuid': 'synthetic-'+str(rank)} for rank in range(4)]
        return screen, plans, root, data, hardware

    def launcher(self, command, **kwargs):
        # This test executes the fixed fake script above, never inspection.py.
        return subprocess.Popen([sys.executable, '-c', FAKE_CHILD, *command[2:]], **kwargs)

    def test_fake_process_full_screen_calibration_precedes_every_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            screen, plans, root, data, hardware = self.prepare(tmp); calls = []
            def calibration(key, receipt_hash):
                calls.append(key)
                self.assertEqual(key, 'interleaved-r1')
                self.assertFalse((root/'deferred-r1/tasks').exists())
                self.assertEqual(len(json.loads((root/key/'caller-admissions.json').read_bytes())['ledger']), 3)
            result = runtime.run_jobs(root, screen, plans, data, Path('synthetic-model'),
                Path(__file__).resolve().parents[1], hardware, runtime.time.monotonic(),
                launch=self.launcher, calibration_check=calibration)
            self.assertEqual(result['finished_task_runs'], 8); self.assertEqual(calls, ['interleaved-r1'])
            self.assertTrue(result['cleanup']['all_producers_stopped']); self.assertTrue(result['calibration_observation_gate'])
            ledger = [json.loads(line) for line in (root/'execution-ledger.jsonl').read_bytes().splitlines()]
            gate = next(index for index, row in enumerate(ledger) if row['event'] == 'calibration-observation-gate')
            self.assertTrue(all(index > gate for index, row in enumerate(ledger)
                if row.get('job_id', '').startswith('deferred-')))
            self.assertTrue(all(len(json.loads((root/key/'caller-admissions.json').read_bytes())['ledger']) == 3 for key in plans))

    def test_fake_calibration_process_failure_refuses_candidate_and_stops_sibling(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, IRIS_E10_FAKE_FAIL='a'):
            screen, plans, root, data, hardware = self.prepare(tmp)
            with self.assertRaisesRegex(RuntimeError, 'calibration native process failed'):
                runtime.run_jobs(root, screen, plans, data, Path('synthetic-model'),
                    Path(__file__).resolve().parents[1], hardware, runtime.time.monotonic(),
                    launch=self.launcher, calibration_check=lambda *_args: self.fail('gate must not run'))
            self.assertFalse((root/'deferred-r1/tasks').exists())
            self.assertTrue((root/'caller-receipt-bindings.json').is_file())

    def test_missing_independent_calibration_replay_never_dispatches_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            screen, plans, root, data, hardware = self.prepare(tmp)
            with self.assertRaisesRegex(RuntimeError, 'independent calibration replay'):
                runtime.run_jobs(root, screen, plans, data, Path('synthetic-model'),
                    Path(__file__).resolve().parents[1], hardware, runtime.time.monotonic(), launch=self.launcher)
            self.assertFalse((root/'deferred-r1/tasks').exists())

    def test_launch_failure_preserves_reservation_and_final_caller_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            screen, plans, root, data, hardware = self.prepare(tmp)
            def denied(*_args, **_kwargs): raise OSError('synthetic Popen failure')
            with self.assertRaisesRegex(OSError, 'synthetic Popen'):
                runtime.run_jobs(root, screen, plans, data, Path('synthetic-model'),
                    Path(__file__).resolve().parents[1], hardware, runtime.time.monotonic(), launch=denied)
            receipts = json.loads((root/'interleaved-r1/worker-receipts.json').read_bytes())
            self.assertEqual(sum(receipt['launched'] for receipt in receipts), 1)
            self.assertTrue((root/'caller-receipt-bindings.json').is_file())

    def test_independent_replay_orchestrator_uses_external_pins_read_only_cpu_and_full_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp); screen, plans, payload = fixture()
            package = location/'package'; staged = stage.stage(package, screen, plans, payload)
            screen, plans, root, data, hardware = self.prepare(location/'retained')
            runtime.run_jobs(root, screen, plans, data, Path('synthetic-model'),
                Path(__file__).resolve().parents[1], hardware, runtime.time.monotonic(),
                launch=self.launcher, calibration_check=lambda *_args: None)
            write(root/'terminal.json', {'screen_id': screen['screen_id'], 'screen_digest': digest(screen),
                'outcome': 'synthetic-fixture-only', 'correctness_scored': False,
                'promotion': False, 'official_submission': False})
            caller = json.loads((root/'caller-receipt-bindings.json').read_bytes()); calls = []
            def replay(command, **kwargs):
                # Fixed fake subprocess result tests orchestration, never DFS/NLL replay.
                calls.append(command)
                self.assertIn('--validate-only', command)
                self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
                key = Path(command[command.index('--root')+1]).name
                requested=[command[i+1] for i,arg in enumerate(command) if arg=='--require-task-gates']
                self.assertEqual(requested,plans[key]['task_order'])
                if len(calls)<=4:self.assertIn('--verify-committed',command)
                context={'strict_replay_validated': True,
                    'committed_projection_verified': True, 'output_published': False, 'new_model_calls': 0,
                    'cpu_only': True, 'caller_admission_receipt_sha256': caller['receipt_sha256'][key]}
                if '--require-task-gates' in command:
                    context['mandatory_task_gates']={command[i+1]:{'synthetic':True} for i,arg in enumerate(command) if arg=='--require-task-gates'}
                else:self.assertIn('--verify-committed',command)
                return SimpleNamespace(stdout=canonical(context))
            from types import SimpleNamespace
            real_preflight = stage.preflight
            with patch.object(verifier, 'preflight', side_effect=lambda package, **kwargs:
                    real_preflight(package, allow_fixture=True, **kwargs)), \
                 patch.object(verifier, 'verify_runtime_tree', return_value=(screen, plans, data)):
                result = verifier.verify(package, root, staged['package_manifest_sha256'],
                    stage.sha(root/'caller-receipt-bindings.json'), run=replay)
                self.assertEqual((result['actual_test_count'], result['planned_test_runs'], len(calls)), (3, 12, 5))
                self.assertFalse(result['correctness_scored']); self.assertFalse(result['gpu_timing_attestation'])
                def missing(command,**kwargs):
                    value=replay(command,**kwargs);context=json.loads(value.stdout)
                    context['mandatory_task_gates'].pop(plans['interleaved-r1']['task_order'][-1])
                    return SimpleNamespace(stdout=canonical(context))
                with self.assertRaisesRegex(RuntimeError,'fresh independent CPU replay result differs'):
                    verifier.verify(package,root,staged['package_manifest_sha256'],
                        stage.sha(root/'caller-receipt-bindings.json'),run=missing)
                with self.assertRaisesRegex(RuntimeError, 'caller receipt binding bytes differ'):
                    verifier.verify(package, root, staged['package_manifest_sha256'], '0'*64, run=replay)


if __name__ == '__main__': unittest.main()
