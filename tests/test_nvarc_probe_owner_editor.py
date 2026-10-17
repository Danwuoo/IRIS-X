"""Offline manual-v2 identity/admission tests; no SDK, credentials or provider IO."""
from tests.platform_requirements import requires_linux
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_nvarc_e10_screen import fixture
from tools import stage_nvarc_e10_probe as stage
from tools import nvarc_notebook_controls as controls
from tools import stage4_execution_ledger as ledger
from tools.nvarc_native_multitask import canonical,digest
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,EXTERNAL_FILES


def manual_admission():
    return {'format':stage.OWNER_EDITOR_ADMISSION,'probe_id':stage.OWNER_EDITOR_RUN,
        'owner_instruction_ref':'offline test: owner requests same-notebook v2 and manual execution',
        'notebook_ref':stage.OWNER_EDITOR_NOTEBOOK,'notebook_numeric_id':stage.OWNER_EDITOR_NOTEBOOK_ID,
        'expected_notebook_version':2,'kernel_execution_type':'QUICK_SAVE','agent_execution_authorized':False}


def manual_fixture(**overrides):
    _,plans,payload=fixture();original=plans['interleaved-r1']
    config={key:original[key] for key in CONFIG_FIELDS}
    config['native_source_learning_rates']=original['native_source_learning_rates']
    external={name:payload[name] for name in EXTERNAL_FILES};external['verified-tokenizer.json']=b'{}'
    options={'fixture':True,'notebook_ref':stage.OWNER_EDITOR_NOTEBOOK,'owner_editor_admission':manual_admission()}
    options.update(overrides)
    return stage.construct(stage.OWNER_EDITOR_RUN,'0'*40,external,config,
        json.loads(payload['material-contract.json']),**options)


def rehash(package,plan=None):
    manifest_path=package/'package-manifest.json';manifest=json.loads(manifest_path.read_bytes())
    if plan is not None:
        for name in ('plan.json','screen.json'):(package/'runtime'/name).write_bytes(canonical(plan))
        manifest['plan_digest']=digest(plan)
    manifest['files_sha256']={p.relative_to(package).as_posix():stage.sha(p)
        for p in package.rglob('*') if p.is_file() and p!=manifest_path}
    manifest_path.write_bytes(canonical(manifest))


class OwnerEditorIdentityTests(unittest.TestCase):
    def test_same_notebook_new_runtime_and_archive_reconstruct_exactly(self):
        plan,raw=manual_fixture()
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'package';result=stage.stage(package,plan,raw)
            stage.preflight(package,expected_manifest_sha256=result['package_manifest_sha256'])
            meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
            self.assertEqual(meta['id'],stage.OWNER_EDITOR_NOTEBOOK)
            self.assertEqual(meta['title'],'stage4-e10-probe-20261006-001')
            self.assertEqual(plan['screen_id'],stage.OWNER_EDITOR_RUN)
            self.assertEqual(plan['run_id'],stage.OWNER_EDITOR_RUN)
            handoff=json.loads((package/'cli-handoff.json').read_bytes())
            self.assertEqual(handoff['save_request_target'],{'id':137327571,
                'slug':stage.OWNER_EDITOR_NOTEBOOK,'new_title':'stage4-e10-probe-20261006-001',
                'kernel_execution_type':'QUICK_SAVE'})
            self.assertEqual(handoff['expected_notebook_version'],2)
            self.assertIsNone(handoff['kernel_push_argv']);self.assertFalse(handoff['execute_commands'])
            self.assertFalse(handoff['agent_execution_authorized'])
            self.assertEqual(handoff['provider_session_timeout_seconds'],1800)
            self.assertEqual(handoff['internal_watchdog_seconds'],1800)
            self.assertFalse(handoff['manual_editor_timeout_attested'])
            self.assertFalse(handoff['provider_timeout_enforcement_observed'])
            self.assertFalse(handoff['resource_sufficiency_verified'])
            notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
            download=''.join(notebook['cells'][-1]['source'])
            self.assertIn('DOWNLOAD_RUN_ID='+repr(stage.OWNER_EDITOR_RUN),download)
            self.assertIn("DOWNLOAD_RUN_ID+'.zip'",download)
            self.assertFalse(plan['approved_for_runtime'])

    def test_rehashed_coupled_metadata_or_autorun_handoff_cannot_bypass_reconstruction(self):
        for mutation in ('coupled-id','coupled-title','push-command','save-and-run','wrong-numeric-target'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                plan,raw=manual_fixture();package=Path(temp)/'package';stage.stage(package,plan,raw)
                target=package/('kernel/kernel-metadata.json' if mutation.startswith('coupled') else 'cli-handoff.json')
                value=json.loads(target.read_bytes())
                if mutation=='coupled-id':value['id']='danielwuu/'+stage.OWNER_EDITOR_RUN
                elif mutation=='coupled-title':value['title']=stage.OWNER_EDITOR_RUN
                elif mutation=='push-command':value['kernel_push_argv']=['kaggle','kernels','push','-p','kernel']
                elif mutation=='save-and-run':value['kernel_execution_type']='SAVE_AND_RUN_ALL'
                else:value['save_request_target']['id']+=1
                target.write_bytes(canonical(value));rehash(package)
                with self.assertRaisesRegex(RuntimeError,'differs'):stage.preflight(package)

    def test_manual_target_is_exact_and_automatic_admission_cannot_be_reused(self):
        for key,bad in [('notebook_ref','danielwuu/'+stage.OWNER_EDITOR_RUN),('notebook_numeric_id',1),
            ('expected_notebook_version',3),('expected_notebook_version',True),
            ('kernel_execution_type','SAVE_AND_RUN_ALL'),('agent_execution_authorized',True),
            ('owner_instruction_ref','')]:
            with self.subTest(key=key):
                admission=manual_admission();admission[key]=bad
                with self.assertRaisesRegex(RuntimeError,'admission'):manual_fixture(owner_editor_admission=admission)
        with self.assertRaisesRegex(RuntimeError,'reuse automatic'):manual_fixture(resource_admission={})
        with self.assertRaisesRegex(RuntimeError,'separate notebook'):manual_fixture(owner_editor_admission=None)


class OwnerEditorVersionThreeTests(unittest.TestCase):
    def construct(self, *, version=3, run_id='stage4-e10-probe-20261006-003'):
        _,plans,payload=fixture();original=plans['interleaved-r1']
        config={key:original[key] for key in CONFIG_FIELDS}
        config['native_source_learning_rates']=original['native_source_learning_rates']
        external={name:payload[name] for name in EXTERNAL_FILES};external['verified-tokenizer.json']=b'{}'
        admission=manual_admission();admission.update(probe_id=run_id,expected_notebook_version=version)
        return stage.construct(run_id,'0'*40,external,config,json.loads(payload['material-contract.json']),
            fixture=True,notebook_ref=stage.OWNER_EDITOR_NOTEBOOK,owner_editor_admission=admission)
    def test_third_version_preserves_notebook_and_distinct_run_identity(self):
        plan,raw=self.construct()
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'package';stage.stage(package,plan,raw);stage.preflight(package)
            meta=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
            handoff=json.loads((package/'cli-handoff.json').read_bytes())
            self.assertEqual(meta['id'],'danielwuu/stage4-e10-probe-20261006-001')
            self.assertEqual(plan['run_id'],'stage4-e10-probe-20261006-003')
            self.assertEqual(handoff['expected_notebook_version'],3)
            self.assertEqual(handoff['kernel_execution_type'],'QUICK_SAVE')
            self.assertFalse(plan['agent_execution_authorized'])
            self.assertFalse(plan['approved_for_runtime'])
            self.assertEqual(plan['maximum_forwards'],28)
    def test_only_reviewed_run_version_pairings_are_admitted(self):
        for version,run in [(2,'stage4-e10-probe-20261006-003'),(4,'stage4-e10-probe-20261006-003'),
                            (3,'stage4-e10-probe-20261006-004'),(True,'stage4-e10-probe-20261006-003')]:
            with self.subTest(version=version,run=run),self.assertRaises(RuntimeError):
                self.construct(version=version,run_id=run)


class OwnerEditorAdmissionTests(unittest.TestCase):
    def test_manual_facts_stay_unavailable_and_are_not_automatic_ledger_inputs(self):
        plan,raw=manual_fixture()
        self.assertEqual(plan['resource_information'],{key:None for key in stage.UNAVAILABLE_RESOURCE_FIELDS})
        self.assertIsNone(plan['resource_admission'])
        with self.assertRaisesRegex(ValueError,'closed Stage 4 plan'):ledger.validate_plan(plan)
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'package';stage.stage(package,plan,raw)
            # Distinct execution contexts: neither automated admission nor an
            # unapproved synthetic fixture may enter owner model execution.
            with self.assertRaisesRegex(RuntimeError,'admitted'):stage.verify_runtime(package/'runtime',require_approved=True)
            with self.assertRaisesRegex(RuntimeError,'fixtures'):stage.verify_runtime(package/'runtime',require_owner_editor=True)
            with self.assertRaisesRegex(RuntimeError,'one explicit'):stage.verify_runtime(package/'runtime',require_approved=True,require_owner_editor=True)
            # Even a real-owner approval flag cannot pass the automatic gate.
            real=copy.deepcopy(plan);real.update(local_fixture=False,approved_for_owner_editor=True)
            rehash(package,real)
            with self.assertRaisesRegex(RuntimeError,'admitted'):stage.verify_runtime(package/'runtime',require_approved=True)

    def test_fabricated_current_quota_session_timeout_or_auto_permission_rejected(self):
        for key,bad in [('quota_hours_available',12),('quota_observed_at','2026-10-06T12:51:21Z'),
            ('historical_sessions_terminal_verified',True),('owner_editor_sessions_closed',True),
            ('provider_reserved_seconds',0),('campaign_pending_actions',0)]:
            with self.subTest(key=key):
                plan,_=manual_fixture();plan['resource_information'][key]=bad
                with self.assertRaisesRegex(RuntimeError,'invent'):stage.validate_owner_editor(plan)
        for key,bad in [('approved_for_runtime',True),('agent_execution_authorized',True),
            ('provider_timeout_enforcement_observed',True),('manual_editor_timeout_attested',True),
            ('resource_sufficiency_verified',True),('maximum_forwards',29),('maximum_notebook_wall_seconds',3600),
            ('generations',1),('optimizer_steps',1),('scientific_task_runs',1),('parallel_workers',2)]:
            with self.subTest(key=key):
                plan,_=manual_fixture();plan[key]=bad
                with self.assertRaises(RuntimeError):stage.validate_owner_editor(plan)
                with self.assertRaises(RuntimeError):controls.provider_cap_fields(plan)

    def test_real_manual_admission_still_requires_source_proof_and_notice_closure(self):
        with patch.object(stage,'validate_baseline'),patch.object(stage,'native_notice_closure',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'notice closure'):manual_fixture(fixture=False)
        with patch.object(stage,'validate_baseline'),patch.object(stage,'native_notice_closure',return_value=True):
            with self.assertRaisesRegex(RuntimeError,'selected-byte read-proof'):manual_fixture(fixture=False)

    def test_manual_plan_tampering_is_rejected_even_with_fresh_manifest_hashes(self):
        plan,raw=manual_fixture()
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'package';stage.stage(package,plan,raw)
            plan['resource_information']['quota_observed_at']='2026-10-06T13:30:00Z'
            rehash(package,plan)
            with self.assertRaisesRegex(RuntimeError,'invent'):stage.preflight(package)

    @requires_linux('Actual Linux owned-process cleanup uses killpg/procfs or imports the resource-bound runtime')
    def test_automatic_admission_freshness_remains_strict(self):
        from tests.test_nvarc_e10_probe import CurrentResourceAdmissionTests
        admission=CurrentResourceAdmissionTests().admission();plan={'screen_id':admission['probe_id']}
        admission['quota_observed_at']='2000-01-01T00:00:00Z'
        with self.assertRaisesRegex(RuntimeError,'current within one hour'):stage.validate_resource(admission,plan,current=True)
        stage.validate_resource(admission,plan,current=False)
        with self.assertRaisesRegex(RuntimeError,'finite free'):stage.validate_resource(manual_admission(),plan,current=False)


if __name__=='__main__':unittest.main()
