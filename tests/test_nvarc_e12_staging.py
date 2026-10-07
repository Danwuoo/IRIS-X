"""CPU-only E12 owner admission, inert notebook and immutable parent checks."""
import ast
import base64
import copy
import hashlib
import io
import json
import math
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from tools import nvarc_e12_admission as owner
from tools import nvarc_e12_entry as entry
from tools import nvarc_e12_cleanup as cleanup
from tools import stage_nvarc_e12_prefix_probe as stage
from tools.nvarc_native_multitask import canonical
from tests.test_nvarc_e11_owner_editor import fixture as historical_fixture


def fixture(root):
    plan = historical_fixture(root)
    plan.pop('e11_process_policy', None)
    plan.update(format='irisx/stage4-e12-prefix-probe-v1',
        run_id=owner.RUN_ID, screen_id=owner.RUN_ID,
        resource_budget_profile=owner.BUDGET_PROFILE, generation_budget_profile='native-prefix-stop-v10',
        expected_notebook_version=10, expected_previous_version=9,
        expected_previous_script_version_id=None, notebook_numeric_id=137327571,
        maximum_notebook_wall_seconds=3600, optimizer_steps=768,
        maximum_training_forwards=768, maximum_training_backwards=768,
        per_worker_training_steps=192, startup_seconds=900, maximum_training_seconds=1200,
        reset_reserve_seconds=360, finalization_reserve_seconds=300, maximum_worker_seconds=3060,
        cleanup_reserve_seconds=310, owner_editor_only=True, kernel_execution_type='INERT',
        e12_process_policy=dict(term_seconds=3290, kill_seconds=3299.8, stop_seconds=3300,
            final_seconds=3600, worker_cleanup_deadline_seconds=3299.8, requires_owned_group_absence=True),
        arm_contracts={arm: dict(experiment='prefix-stop-v10', arm_id=arm, training_updates=steps,
            schedule='interleaved', dfs_probability_floor=.2, dfs_max_score=-math.log(.2))
            for arm, steps in (('ttt64', 64), ('ttt128', 128))},
        arm_order={key: (['ttt64', 'ttt128'] if key in ('195c6913', 'a47bf94d') else ['ttt128', 'ttt64'])
            for key in plan['task_order']},
        **{key: False for key in stage.FALSE_FIELDS})
    plan['owner_editor_admission'] = owner.admission(plan)
    return plan


def mock_profile(plan):
    owner.scope(plan)
    return {'profile_id': 'native-prefix-stop-v10'}


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.plan = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, confirmed=True):
        return owner.write_confirmation(self.root, self.plan, confirmed, 10.,
            now=lambda: 100., monotonic=lambda: 10.)

    def verify(self):
        return owner.verify_confirmation(self.root, self.plan, now=lambda: 101., monotonic=lambda: 11.)

    def test_four_hour_declarations_are_exclusive_and_not_resource_or_publication_attestations(self):
        value = self.write()
        self.assertEqual(value, self.verify())
        self.assertEqual(value['owner_declared_minimum_free_gpu_hours'], 4)
        for key in ('publication_authorized', 'agent_execution_authorized',
                    'quota_independently_verified', 'provider_editor_timeout_attested'):
            self.assertIs(value[key], False)
        self.assertIsNone(value['publication_authorization_ref'])
        with self.assertRaises(FileExistsError):
            self.write()

    def test_only_literal_true_writes_and_no_short_profile_is_accepted(self):
        for value in (False, None, 1, 'True', [], {}):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.write(value)
            self.assertFalse((self.root / owner.CONFIRMATION_FILE).exists())
        for key, value in (('maximum_notebook_wall_seconds', 2700),
                ('resource_budget_profile', 'owner-editor-45min-v9'), ('optimizer_steps', 512),
                ('publication_authorized', True), ('approved_for_owner_editor', True),
                ('agent_execution_authorized', True), ('per_worker_training_steps', 128)):
            changed = copy.deepcopy(self.plan); changed[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                owner.admission(changed)

    def test_plan_source_identity_typed_flags_and_four_hour_declaration_are_bound(self):
        original = self.write(); path = self.root / owner.CONFIRMATION_FILE
        for key, value in (('run_id', 'stage4-e11-probe-paired-dfs-floor-20261007-003'),
                ('source_commit', 'b' * 40), ('config_name', 'E11_CONFIRM_RUN_003'),
                ('owner_enabled_exact_run', 1), ('owner_declared_minimum_free_gpu_hours', 3),
                ('owner_declared_minimum_free_gpu_hours', 4.0),
                ('plan_digest', 'sha256:' + '0' * 64), ('publication_authorized', True)):
            changed = copy.deepcopy(original); changed[key] = value; path.write_bytes(canonical(changed))
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                self.verify()
        path.write_bytes(canonical(original)); changed = copy.deepcopy(self.plan)
        changed['arm_contracts']['ttt64']['training_updates'] = 63
        with self.assertRaises(RuntimeError):
            owner.verify_confirmation(self.root, changed, current=False)

    def test_stale_future_nonfinite_and_duplicate_confirmation_rejected(self):
        original = self.write(); path = self.root / owner.CONFIRMATION_FILE
        with self.assertRaises(RuntimeError):
            owner.verify_confirmation(self.root, self.plan, now=lambda: 3701., monotonic=lambda: 3611.)
        with self.assertRaises(RuntimeError):
            owner.verify_confirmation(self.root, self.plan, now=lambda: 99., monotonic=lambda: 9.)
        for tail in (b',"owner_enabled_exact_run":true}', b',"surplus":1e999}'):
            path.write_bytes(canonical(original)[:-1] + tail)
            with self.assertRaises((ValueError, RuntimeError)):
                self.verify()

    def test_required_admission_fails_before_runtime_when_confirmation_is_absent(self):
        with patch.object(stage, 'runtime_api', return_value=SimpleNamespace(profile_for_plan=mock_profile)):
            stage.validate_admission(self.plan)
        with patch.object(stage, 'runtime_api', side_effect=AssertionError('no runtime import before confirmation')):
            with self.assertRaises(RuntimeError):
                stage.validate_admission(self.plan, required=True, root=self.root)
        (self.root / 'plan.json').write_bytes(canonical(self.plan))
        import builtins
        original_import = builtins.__import__; imports = []
        def guarded(name, *args, **kwargs):
            imports.append(name)
            if name in ('tools.nvarc_e12_runtime', 'torch', 'numpy', 'unsloth', 'transformers'):
                raise AssertionError('runtime import before owner opt-in')
            return original_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=guarded), self.assertRaises(RuntimeError):
            entry.main(['--root', str(self.root), '--dependency', str(self.root)])
        self.assertNotIn('tools.nvarc_e12_runtime', imports)

    def test_admission_and_entry_have_only_standard_library_imports_before_gate(self):
        for filename in ('tools/nvarc_e12_admission.py', 'tools/nvarc_e12_entry.py'):
            tree = ast.parse((stage.ROOT / filename).read_bytes())
            names = {node.module.split('.')[0] for node in tree.body if isinstance(node, ast.ImportFrom)}
            names |= {alias.name.split('.')[0] for node in tree.body
                if isinstance(node, ast.Import) for alias in node.names}
            self.assertFalse(names & {'torch', 'numpy', 'tokenizers', 'unsloth', 'transformers', 'peft', 'tools'})


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.plan = fixture(self.root)
        self.raw = {name: (stage.ROOT / name).read_bytes() for name in (
            'tools/nvarc_e12_entry.py', 'tools/nvarc_e12_admission.py',
            'tools/stage_nvarc_e12_prefix_probe.py', 'tools/nvarc_e12_delivery_envelope.py')}
        self.plan['payload_sha256'] = {name: hashlib.sha256(body).hexdigest() for name, body in self.raw.items()}
        self.raw['plan.json'] = self.raw['screen.json'] = canonical(self.plan)
        self.notebook = stage.render(self.plan, self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_run_all_performs_no_import_setup_write_or_subprocess(self):
        env = {}
        with patch('builtins.__import__', side_effect=AssertionError('no imports before opt-in')), \
             patch('builtins.open', side_effect=AssertionError('no file access before opt-in')), \
             patch('sys.stdout', new=io.StringIO()) as output:
            for cell in self.notebook['cells'][1:]:
                exec(compile(''.join(cell['source']), 'default-inert-e12', 'exec'), env)
        self.assertIs(env[owner.CONFIG_NAME], False)
        self.assertIn('No run started', output.getvalue())
        self.assertNotIn('START', env); self.assertNotIn('PACKED', env)

    def test_stale_or_truthy_non_boolean_configuration_never_activates(self):
        for value in (None, False, 1, 'True'):
            env = {'E11_CONFIRM_RUN_003': True, owner.CONFIG_NAME: value}
            with patch('builtins.__import__', side_effect=AssertionError('no import')), \
                 patch('sys.stdout', new=io.StringIO()):
                for cell in self.notebook['cells'][2:]:
                    exec(compile(''.join(cell['source']), 'unconfirmed-e12', 'exec'), env)
            self.assertNotIn('START', env)

    def test_actual_embedded_bytes_compile_with_bound_runtime_hooks_and_stdout_capture(self):
        stage.verify_embedded_payload(self.notebook, self.raw)
        body = stage.embedded_body(self.notebook)
        packed = next(ast.literal_eval(node.value) for node in ast.parse(body).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'PACKED')
        self.assertEqual(set(packed), set(self.raw))
        for name, encoded in packed.items():
            decoded = zlib.decompress(base64.b64decode(encoded)); self.assertEqual(decoded, self.raw[name])
            if name.endswith('.py'):
                compile(decoded, name, 'exec')
        for hook in ("str(work / 'tools/nvarc_e12_entry.py')", 'from tools.nvarc_e12_runtime import finalize',
                'from tools.nvarc_e12_cleanup import supervise', "capture_path=work / 'coordinator-output.log'",
                "OMP_NUM_THREADS='2'", "MKL_NUM_THREADS='2'",
                'write_confirmation(work, screen, E12_CONFIRM_RUN_001, START)'):
            self.assertIn(hook, body)
        self.assertNotIn('from tools.nvarc_e11_paired_floor import finalize', body)
        download = ''.join(self.notebook['cells'][-1]['source'])
        self.assertIn('DOWNLOAD_RUN_ID=' + repr(owner.RUN_ID), download)
        self.assertIn('DOWNLOAD_PLAN_SHA256=' + repr(hashlib.sha256(canonical(self.plan)).hexdigest()), download)
        self.assertIn('DOWNLOAD_CHECKER_SHA256=' + repr(hashlib.sha256(
            self.raw['tools/nvarc_e12_delivery_envelope.py']).hexdigest()), download)
        self.assertIn("DOWNLOAD_RUN_ID+'-delivery.zip'", download)
        self.assertIn('verify_envelope(DOWNLOAD_PATH.parent', download)

    def test_mutated_embedded_bytes_duplicate_mapping_or_unconditional_setup_rejected(self):
        original = ''.join(self.notebook['cells'][2]['source'])
        encoded = base64.b64encode(zlib.compress(self.raw['tools/nvarc_e12_entry.py'], 9)).decode()
        for change in ('import os\n' + original,
                original.replace(encoded, base64.b64encode(zlib.compress(b'wrong', 9)).decode()),
                original.replace("PACKED={", "PACKED={'tools/nvarc_e12_entry.py':'wrong',", 1)):
            mutated = copy.deepcopy(self.notebook); mutated['cells'][2]['source'] = change.splitlines(keepends=True)
            with self.assertRaises(RuntimeError):
                stage.verify_embedded_payload(mutated, self.raw)
        mutated = copy.deepcopy(self.notebook)
        mutated['cells'][1]['source'] = stage.configuration_cell().replace(' = False', ' = True').splitlines(keepends=True)
        with self.assertRaises(RuntimeError):
            stage.verify_embedded_payload(mutated, self.raw)

    def test_readonly_download_rejects_changed_staged_checker_before_execution(self):
        directory = self.root / owner.RUN_ID / 'tools'; directory.mkdir(parents=True)
        source = self.raw['tools/nvarc_e12_delivery_envelope.py']
        checker = directory / 'nvarc_e12_delivery_envelope.py'
        checker.write_bytes(b'X' + source[1:])
        bundle = self.root / (owner.RUN_ID + '-delivery.zip'); bundle.write_bytes(b'untouched')
        body = stage.delivery_download_body(self.plan, self.raw).replace("'/kaggle/working'", repr(str(self.root)))
        before = {str(path): path.read_bytes() for path in (checker, bundle)}
        with self.assertRaisesRegex(RuntimeError, 'checker bytes differ'):
            exec(compile(body, 'read-only-e12-download', 'exec'), {})
        self.assertEqual(before, {str(path): path.read_bytes() for path in (checker, bundle)})

    def executed_body(self):
        body = stage.embedded_body(self.notebook)
        hook = "work = Path('/kaggle/working')"
        self.assertEqual(body.count(hook), 1)
        return body.replace(hook, 'work = Path(' + repr(str(self.root)) + ')', 1)

    def test_actual_execution_cell_retains_dependency_discovery_failure_before_launch(self):
        runtime = stage.runtime_api(); seen = []
        def finalized(root, observation, plan_sha256):
            seen.append((root, observation, plan_sha256))
            return dict(final_archive_created=False, finalization_qualified=False,
                delivery_bundle_created=False, coordinator_diagnostic_excerpt='literal failure diagnostic')
        display = SimpleNamespace(FileLink=lambda value: value, display=lambda value: None)
        with patch.object(sys, 'path', list(sys.path)), \
             patch.object(cleanup, 'supervise', side_effect=AssertionError('no process launch allowed')) as launch, \
             patch.object(runtime, 'finalize', side_effect=finalized), \
             patch.dict(sys.modules, {'IPython.display': display}), \
             patch('sys.stdout', new=io.StringIO()), \
             self.assertRaisesRegex(RuntimeError, 'incomplete or failed'):
            exec(compile(self.executed_body(), 'actual-e12-cell-discovery-failure', 'exec'),
                {owner.CONFIG_NAME: True})
        launch.assert_not_called(); self.assertEqual(len(seen), 1)
        root, observation, pin = seen[0]
        self.assertEqual(pin, hashlib.sha256(canonical(self.plan)).hexdigest())
        self.assertIs(observation['prelaunch_failed'], True)
        self.assertIs(observation['launch_attempted'], False)
        self.assertIs(observation['launch_failed'], False)
        self.assertIs(observation['launched'], False)
        self.assertIsNone(observation['coordinator_pid'])
        self.assertTrue(observation['output_capture']['written'])
        self.assertIn('one exact original offline dependency notebook mount required',
            (root / 'coordinator-output.log').read_text())

    def test_dispatched_supervisor_error_is_never_relabelled_as_no_launch(self):
        runtime = stage.runtime_api(); original_is_file = Path.is_file
        mount = '/kaggle/usr/lib/notebooks/literal-test-dependency'
        def is_file(path):
            return True if str(path) == mount + '/qwen3.patch' else original_is_file(path)
        with patch.object(sys, 'path', [*sys.path, mount]), \
             patch.object(Path, 'is_file', autospec=True, side_effect=is_file), \
             patch.object(cleanup, 'supervise', side_effect=RuntimeError('uncertain supervisor state')), \
             patch.object(cleanup, 'prelaunch_failure', side_effect=AssertionError('cannot fabricate no launch')) as failed, \
             patch.object(runtime, 'finalize') as finalizer, \
             self.assertRaisesRegex(RuntimeError, 'uncertain supervisor state'):
            exec(compile(self.executed_body(), 'actual-e12-supervisor-failure', 'exec'),
                {owner.CONFIG_NAME: True})
        failed.assert_not_called(); finalizer.assert_not_called()

    def test_missing_delivery_does_not_import_checker_or_create_files(self):
        body = stage.delivery_download_body(self.plan, self.raw).replace("'/kaggle/working'", repr(str(self.root)))
        before = set(self.root.rglob('*'))
        with patch('sys.stdout', new=io.StringIO()) as output:
            exec(compile(body, 'missing-e12-delivery', 'exec'), {})
        self.assertIn('No finalized delivery bundle', output.getvalue())
        self.assertEqual(before, set(self.root.rglob('*')))

    def test_disclosure_and_handoff_never_grant_publication_or_fabricate_quota(self):
        text = ''.join(self.notebook['cells'][0]['source'])
        for word in ('FlashAttention', '768 updates', '12 test', 'INTERLEAVED', '128-row',
                     '13-update warmup', '3600-second', '4 free GPU-hours', 'INTERNAL',
                     'pay-to-scale OFF', 'STOP THE EDITOR'):
            self.assertIn(word, text)
        handoff = stage.handoff(self.plan)
        self.assertEqual(handoff['kernel_execution_type'], 'INERT')
        for field in ('publication_authorized', 'agent_execution_authorized', 'runtime_authorized'):
            self.assertIs(handoff[field], False)
        self.assertEqual(handoff['planned_charged_gpu_seconds_ceiling'], 14400)
        self.assertIsNone(handoff['resource_admission'])
        self.assertIsNone(handoff['publication_authorization_ref'])


class FrozenTests(unittest.TestCase):
    def test_unpinned_parent_is_rejected_before_using_its_payload_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = dict(payload_sha256={'../outside': '0' * 64})
            for name in ('plan.json', 'screen.json'):
                (root / name).write_bytes(canonical(parent))
            read_paths = []; original = Path.read_bytes
            def observed(path):
                read_paths.append(path)
                return original(path)
            with patch.object(Path, 'read_bytes', autospec=True, side_effect=observed), \
                 self.assertRaisesRegex(RuntimeError, 'exact immutable v9'):
                stage.build_from_frozen(root / 'package', root, 'a' * 40)
            self.assertNotIn(root / '../outside', read_paths)

    def test_frozen_material_source_and_plan_digests_are_not_negotiable(self):
        payload = {'tools/old.py': b'pass\n', 'materials/task.json': b'{"rows":[]}'}
        parent = dict(source_commit=stage.FROZEN_SOURCE_COMMIT,
            source_files_sha256={'tools/old.py': hashlib.sha256(payload['tools/old.py']).hexdigest()},
            payload_sha256={name: hashlib.sha256(body).hexdigest() for name, body in payload.items()})
        pin = hashlib.sha256(canonical(parent)).hexdigest()
        with patch.object(stage, 'FROZEN_PLAN_SHA256', pin), patch.object(stage.historical, 'FILES', ('tools/old.py',)):
            stage._verify_frozen(parent, payload)
            changed = dict(payload, **{'materials/task.json': b'{"rows":[1]}'})
            with self.assertRaises(RuntimeError):
                stage._verify_frozen(parent, changed)
            changed = copy.deepcopy(parent); changed['source_commit'] = 'a' * 40
            with self.assertRaises(RuntimeError):
                stage._verify_frozen(changed, payload)
            with self.assertRaises(RuntimeError):
                stage._verify_frozen(parent, dict(payload, surplus=b'extra'))


if __name__ == '__main__':
    unittest.main()
