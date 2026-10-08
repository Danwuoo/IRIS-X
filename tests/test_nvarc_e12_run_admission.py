"""Self-contained CPU tests. Frozen public-input plan is data, never authority.

The fixture is the verified immutable INERT001 plan (f8000ab7...). Tests derive
synthetic RUN admission observations and never authenticate them or run a model.
"""
import ast
import builtins
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import nvarc_e12_admission as admission
from tools import nvarc_e12_entry as entry
from tools import nvarc_e12_cleanup as cleanup
from tools import nvarc_e12_delivery_envelope as delivery
from tools import stage_nvarc_e12_prefix_probe as stage

FIXTURE = Path(__file__).parent / 'fixtures/e12/frozen-inert-001-plan.json'
FIXTURE_SHA256 = 'f8000ab7db2a40795e93ff7482ad17ffa7fc817057207da7a9aadd6266739349'


def snapshot(remaining=6000, *, now=None):
    now = time.time() if now is None else now
    stamp = datetime.fromtimestamp(now, timezone.utc)
    return dict(format='irisx/stage4-quota-observation-v1', provider='kaggle', account='danielwuu',
        observed_at=stamp.isoformat(), refresh_at=(stamp + timedelta(days=1)).isoformat(),
        primary_sha256='a' * 64, typed_projection_sha256='b' * 64,
        used_seconds=36000 - remaining, reserved_seconds=0, total_seconds=36000,
        remaining_free_seconds=remaining, pay_to_scale_enabled=False,
        duration_units='provider charged quota seconds', permission_granted=False)


def fixture(*, automatic=True, remaining=6000):
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    plan = admission.parse(raw)
    plan.update(run_id=admission.RUN_ID, screen_id=admission.RUN_ID,
        expected_notebook_version=11, expected_previous_version=10,
        source_commit='a' * 40, kernel_execution_type='RUN' if automatic else 'INERT',
        resource_budget_profile=admission.RUN_BUDGET_PROFILE if automatic else admission.BUDGET_PROFILE,
        owner_editor_only=not automatic, owner_editor_admission=None, resource_admission=None,
        **{key: automatic and key in admission.RUN_TRUE_FIELDS for key in admission.FALSE_FIELDS})
    if automatic:
        plan['resource_admission'] = admission.run_admission(plan, snapshot(remaining),
            admission.AUTHORIZATION_REF, quota_policy=admission.WAIVER_POLICY)
    else:
        plan['owner_editor_admission'] = admission.admission(plan)
    return plan


def payload(plan):
    raw = {name: (stage.ROOT / name).read_bytes() for name in stage.NEW_FILES}
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in raw.items()}
    plan['source_files_sha256'] = hashes.copy()
    plan['payload_sha256'] = hashes
    raw['plan.json'] = raw['screen.json'] = admission.canonical(plan)
    return raw


def write_runtime(root, plan):
    for name, body in payload(plan).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)


class AdmissionTests(unittest.TestCase):
    def test_default_conservative_policy_and_explicit_small_quota_waiver(self):
        plan = fixture()
        with self.assertRaisesRegex(RuntimeError, 'four-GPU-hour'):
            admission.run_admission(plan, snapshot(), admission.AUTHORIZATION_REF)
        value = admission.run_admission(plan, snapshot(14400), admission.AUTHORIZATION_REF)
        self.assertEqual(value['quota_policy'], admission.CONSERVATIVE_POLICY)
        self.assertFalse(value['conservative_reservation_waived'])
        self.assertTrue(value['quota_rate_is_conservative_planning_assumption'])
        self.assertFalse(value['quota_rate_independently_verified'])
        self.assertEqual(plan['resource_admission']['quota_policy'], admission.WAIVER_POLICY)
        self.assertEqual(plan['optimizer_steps'], 768)
        self.assertEqual(plan['test_executions'], 12)
        self.assertEqual(plan['maximum_notebook_wall_seconds'], 3600)

    def test_snapshot_projection_and_freshness_reject_unsafe_facts(self):
        for field, bad in [('account', 'someoneelse'), ('pay_to_scale_enabled', True),
                ('permission_granted', True), ('reserved_seconds', 1), ('remaining_free_seconds', 0),
                ('remaining_free_seconds', True), ('used_seconds', float('nan')),
                ('primary_sha256', 'unknown'), ('total_seconds', 1)]:
            value = snapshot(); value[field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises((RuntimeError, ValueError)):
                admission.validate_resource_snapshot(value)
        stale = snapshot(now=time.time() - 901)
        with self.assertRaisesRegex(RuntimeError, '900'):
            admission.validate_resource_snapshot(stale)
        admission.validate_resource_snapshot(stale, current=False)
        with self.assertRaises(RuntimeError):
            admission.run_admission(fixture(), snapshot(), 'another-owner-message', quota_policy=admission.WAIVER_POLICY)

    def test_scope_and_admission_are_closed_and_typed(self):
        original = fixture()
        for field, bad in [('optimizer_steps', 384), ('source_commit', 'b' * 40),
                ('dependency_readproof_digest', 'sha256:' + 'c' * 64), ('generation_seconds', 60),
                ('agent_execution_authorized', 1), ('owner_editor_only', True)]:
            plan = copy.deepcopy(original); plan[field] = bad
            with self.subTest(field=field), self.assertRaises((RuntimeError, ValueError)):
                admission.validate_plan(plan)
        plan = copy.deepcopy(original); plan['resource_admission']['extra'] = True
        with self.assertRaises(RuntimeError): admission.validate_plan(plan)
        with self.assertRaises(RuntimeError): admission.write_run_start('/unused', fixture(automatic=False), time.monotonic())
        with self.assertRaises(RuntimeError): admission.declarations(original)

    def test_receipt_has_actual_clocks_without_invented_owner_or_runtime_quota(self):
        plan = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = admission.write_run_start(root, plan, 10., now=lambda: 100., monotonic=lambda: 10.)
            self.assertFalse(value['owner_edited_notebook_config'])
            self.assertFalse(value['owner_minimum_four_hour_declaration'])
            self.assertFalse(value['quota_current_at_runtime'])
            self.assertEqual(admission.verify_execution(root, plan, now=lambda: 101., monotonic=lambda: 11.), value)
            with self.assertRaises(FileExistsError):
                admission.write_run_start(root, plan, 10., now=lambda: 100., monotonic=lambda: 10.)
            with self.assertRaises(RuntimeError):
                admission.verify_execution(root, plan, now=lambda: 3701., monotonic=lambda: 3611.)
            changed = dict(value, owner_edited_notebook_config=True)
            with self.assertRaises(RuntimeError): admission.verify_start_value(changed, plan, current=False)
            with self.assertRaises(ValueError): delivery.verify_start_value(changed, plan, current=False)
            self.assertEqual(delivery.verify_start_value(value, plan, current=False), value)

    def test_runtime_uses_historical_submission_observation_after_queue(self):
        plan = fixture(); resource = plan['resource_admission']
        resource['resource_snapshot'] = snapshot(now=time.time() - 7200)
        plan['resource_admission'] = admission.run_admission(plan, resource['resource_snapshot'],
            admission.AUTHORIZATION_REF, quota_policy=admission.WAIVER_POLICY, current=False)
        admission.validate_plan(plan)
        with self.assertRaises(RuntimeError): admission.validate_plan(plan, current_resource=True)
        with tempfile.TemporaryDirectory() as temporary:
            admission.write_run_start(temporary, plan, time.monotonic())
            admission.verify_execution(temporary, plan)


class EntryAndOutputTests(unittest.TestCase):
    def test_tampered_runtime_never_imports_before_source_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = fixture(); write_runtime(root, plan)
            admission.write_run_start(root, plan, time.monotonic())
            (root / 'tools/nvarc_e12_runtime.py').write_text('raise AssertionError("runtime import tripwire")\n')
            imported = []; original = builtins.__import__
            def observe(name, *args, **kwargs):
                imported.append(name)
                if name == 'tools' or name in ('tools.nvarc_e12_runtime', 'torch', 'numpy'):
                    raise AssertionError('runtime import before source check')
                return original(name, *args, **kwargs)
            with patch('builtins.__import__', side_effect=observe), self.assertRaisesRegex(RuntimeError, 'payload differs'):
                entry.main(['--root', str(root), '--dependency', str(root),
                    '--expected-plan-sha256', admission.digest(plan).removeprefix('sha256:')])
            self.assertNotIn('tools', imported)

    def test_self_consistently_rehashed_plan_rejected_by_independent_expected_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = fixture(); write_runtime(root, plan)
            pin = admission.digest(plan).removeprefix('sha256:')
            source = root / 'tools/nvarc_e12_runtime.py'
            source.write_text('raise AssertionError("rehashed source import tripwire")\n')
            changed = hashlib.sha256(source.read_bytes()).hexdigest()
            plan['payload_sha256']['tools/nvarc_e12_runtime.py'] = changed
            plan['source_files_sha256']['tools/nvarc_e12_runtime.py'] = changed
            for name in ('plan.json', 'screen.json'): (root / name).write_bytes(admission.canonical(plan))
            admission.write_run_start(root, plan, time.monotonic())
            with self.assertRaisesRegex(RuntimeError, 'independently supplied'):
                entry.main(['--root', str(root), '--dependency', str(root), '--expected-plan-sha256', pin])
            with self.assertRaisesRegex(RuntimeError, 'independently supplied notebook'):
                stage.verify_runtime(root, require_approved=True, expected_plan_sha256=pin)

    def test_absent_receipt_duplicate_plan_and_symlink_fail_before_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = fixture(); write_runtime(root, plan)
            with self.assertRaises(FileNotFoundError): entry.main(['--root', str(root), '--dependency', str(root),
                    '--expected-plan-sha256', admission.digest(plan).removeprefix('sha256:')])
            path = root / 'plan.json'; path.write_bytes(b'{"run_id":"x","run_id":"y"}')
            with self.assertRaisesRegex(RuntimeError, 'duplicate'): admission.read_plan(root)
            path.unlink(); path.symlink_to(root / 'screen.json')
            with self.assertRaisesRegex(RuntimeError, 'no-follow'): admission.read_plan(root)

    def test_output_store_rejects_foreign_or_unadmitted_run(self):
        from tools.nvarc_e12_output_lifecycle import GenerationStore
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = fixture(); write_runtime(root, plan)
            bindings = dict(run_id=admission.RUN_ID, plan_digest=admission.digest(plan), challenges_digest=plan['challenges_digest'])
            with self.assertRaises(FileNotFoundError): GenerationStore(root, 'e12-prefix-pilot', bindings)
            admission.write_run_start(root, plan, time.monotonic())
            GenerationStore(root, 'e12-prefix-pilot', bindings)
            with self.assertRaises(RuntimeError): GenerationStore(root, 'e12-prefix-pilot', dict(bindings, run_id='foreign'))
            with self.assertRaises(RuntimeError): GenerationStore(root, 'e12-prefix-pilot', dict(bindings, plan_digest='sha256:' + 'b' * 64))


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.plan = fixture(); self.raw = payload(self.plan)
        self.notebook = stage.render(self.plan, self.raw)

    def test_automatic_branch_embeds_exact_sources_without_owner_config(self):
        stage.verify_embedded_payload(self.notebook, self.raw)
        body = stage.embedded_body(self.notebook)
        self.assertEqual(len(self.notebook['cells']), 3)
        self.assertIn('write_run_start(work,screen,START)', body)
        self.assertNotIn('write_confirmation', body)
        self.assertNotIn('E12_CONFIRM_RUN', body)
        self.assertIn("'--expected-plan-sha256'," + repr(admission.digest(self.plan).removeprefix('sha256:')), body)
        self.assertNotIn('STOP THE EDITOR', ''.join(self.notebook['cells'][-1]['source']))
        self.assertEqual(stage.handoff(self.plan)['kernel_execution_type'], 'RUN')
        self.assertFalse(stage.handoff(self.plan)['owner_config_required'])

    def test_inert_default_still_has_zero_setup_imports_and_false_configuration(self):
        plan = fixture(automatic=False); notebook = stage.render(plan, payload(plan)); environment = {}
        with patch('builtins.__import__', side_effect=AssertionError('INERT import')), patch('sys.stdout', new=io.StringIO()):
            for cell in notebook['cells'][1:]: exec(compile(''.join(cell['source']), 'inert', 'exec'), environment)
        self.assertIs(environment[admission.CONFIG_NAME], False)
        self.assertNotIn('START', environment)

    def test_actual_admission_failure_reaches_prelaunch_diagnostic_finalizer(self):
        runtime = stage.runtime_api(); seen = []
        def finalized(root, observation, plan_sha256):
            seen.append((root, observation, plan_sha256))
            return dict(coordinator_diagnostic_excerpt='', final_archive_created=False,
                finalization_qualified=False, delivery_bundle_created=False)
        with tempfile.TemporaryDirectory() as temporary:
            body = stage.embedded_body(self.notebook).replace("Path('/kaggle/working')", 'Path(' + repr(temporary) + ')')
            with patch.object(sys_path := __import__('sys'), 'path', list(sys_path.path)), \
                 patch.object(admission, 'write_run_start', side_effect=RuntimeError('admission-tripwire')), \
                 patch.object(runtime, 'finalize', side_effect=finalized), \
                 patch('IPython.display.display'), patch('sys.stdout', new=io.StringIO()), \
                 self.assertRaisesRegex(RuntimeError, 'E12 calibration incomplete'):
                exec(compile(body, 'actual-run003-admission-failure', 'exec'), {})
            self.assertEqual(len(seen), 1)
            root, observation, _ = seen[0]
            self.assertFalse(observation['launched'])
            self.assertTrue(observation['confirmed_stopped'])
            self.assertIn('admission-tripwire', (root / 'coordinator-output.log').read_text())
            self.assertFalse((root / admission.CONFIRMATION_FILE).exists())

    def test_delivery_gate_rejects_missing_or_fake_automatic_receipt(self):
        delivery.validate_plan(self.plan, admission.RUN_ID)
        with self.assertRaisesRegex(ValueError, 'honest start receipt'):
            delivery.validate_runtime_artifacts({}, self.plan)
        changed = copy.deepcopy(self.plan); changed['agent_execution_authorized'] = False
        with self.assertRaises(ValueError): delivery.validate_plan(changed, admission.RUN_ID)
        changed = copy.deepcopy(self.notebook); changed['metadata']['irisx_execution_mode'] = 'INERT'
        with self.assertRaises(RuntimeError): stage.verify_embedded_payload(changed, self.raw)


if __name__ == '__main__': unittest.main()
