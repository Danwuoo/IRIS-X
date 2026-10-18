"""Real closed tiny-Qwen artifacts plus adversarial independent CPU consumers.

Fixture contracts are explicit and cannot enter production validate_result,
run or close_diagnostic. No official weights, CUDA, network or score claims.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

from tools.arc2_goal_sprint_20261017.data import canonical
from tools.nvarc_posttrain_20261017 import convergence_controller as ctl
from tools.nvarc_posttrain_20261017.concurrency import run_wave
from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
from tools.nvarc_posttrain_20261017.score import closure_structure

MISSING = [name for name in ('torch', 'transformers', 'peft', 'pydantic', 'tokenizers', 'safetensors')
           if importlib.util.find_spec(name) is None]
ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


def artifact(path, root):
    return {'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture_worker(path):
    """Executed through actual dedicated-subreaper ownership, never GPU dispatch."""
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_workflow import corpus
    from tests.test_nvarc_convergence import configuration
    from tools.nvarc_posttrain_20261017 import convergence_workflow as workflow
    torch.set_num_threads(1)
    cfg = json.loads(path.read_bytes()); source = Path(cfg['fixture_source']); source.mkdir()
    args = corpus(source)
    prepared = workflow.prepare_panels(*args[:4], **args[4], probability_policy=ctl.FP32_HEAD_POLICY)
    engine = tiny_engine(dtype=torch.bfloat16, probability_policy=ctl.FP32_HEAD_POLICY)
    output = Path(cfg['output_dir'])
    save(Path(cfg['ready_path']), {'job_id': ctl.JOB_ID, 'ready': True})
    while not Path(cfg['release_path']).exists():
        if time.time() >= cfg['deadline_epoch']:
            raise TimeoutError('fixture release deadline')
        time.sleep(.01)
    report = workflow.run_workflow(engine, prepared, output=output/'convergence',
        source_identity=cfg['source_identity'], deadline=cfg['deadline_epoch'],
        training_deadline=cfg['training_deadline_epoch'], config=configuration(),
        evaluation={**workflow.DEFAULT_EVALUATION, 'ttt_steps': 1})
    result = {key: cfg[key] for key in ('mode', 'job_id', 'source_identity', 'device_identity', 'workload_identity')}
    result.update(model_identity=engine.base_identity, completed=report['complete'], convergence=report,
                  convergence_report=artifact(output/'convergence/report.json', output))
    save(output/'result.json', result)


class PureControllerTests(unittest.TestCase):
    def test_control_plane_imports_without_ml(self):
        code = "import sys; from tools.nvarc_posttrain_20261017 import convergence_controller; assert not any(n in sys.modules for n in ('torch','transformers','peft'))"
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_session_and_finite_active_phase_bound(self):
        now = 2000000000.
        cfg = {'started_epoch': now-100, 'deadline_epoch': now-100+43200}
        plan = ctl.phase_plan(cfg, now)
        self.assertEqual(plan['active_deadline_epoch'], now+7200)
        self.assertLessEqual(plan['wave_deadline_epoch']-now, 7200)
        self.assertGreaterEqual(plan['worker_deadline_epoch']-plan['screen_deadline_epoch'], 3600)
        self.assertEqual(plan['original_started_epoch'], cfg['started_epoch'])
        for bad in ({**cfg, 'deadline_epoch': now+999999}, {**cfg, 'started_epoch': float('nan')}):
            with self.assertRaises(ValueError):
                ctl.phase_plan(bad, now)
        with self.assertRaises(ValueError):
            ctl.phase_plan(cfg, cfg['deadline_epoch']-100)

    def test_production_rejects_fixture_depth_and_other_model_before_execution(self):
        for changes in ({'model_roots': {'2b': 'x', '4b': 'y'}}, {'capacity': 'identity-depth32'}, {'parameters': {'ttt_steps': 1}}, {'resume': 'x'}):
            cfg = {'workflow': ctl.WORKFLOW, 'model_roots': {'2b': 'unused'}, 'parameters': {}, **changes}
            with self.assertRaisesRegex(ValueError, 'fixed fresh official'):
                ctl.run(cfg)
        self.assertEqual(ctl._bounds(ctl.DEFAULT_CONFIG)['collection_windows'], 13)
        self.assertEqual(ctl._bounds(ctl.DEFAULT_CONFIG)['training_optimizer_attempts'], 16)
        self.assertEqual(ctl._bounds(ctl.DEFAULT_CONFIG)['training_trajectory_slots'], 832)


@unittest.skipIf(bool(MISSING) or sys.platform != 'linux', 'Actual closed tiny CPU fixture needs Linux and optional ML dependencies: '+','.join(MISSING))
class ClosedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from tests.test_nvarc_posttrain_engine import tiny_engine
        from tests.test_nvarc_convergence import configuration
        from tools.nvarc_posttrain_20261017 import convergence_workflow as workflow
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name); now = time.time()
        cls.source = cls.base/'source'
        job = {'job_id': ctl.JOB_ID, 'variant': '2b', 'arm': 'S', 'mode': 'convergence', 'seed': 7321,
            'source_identity': 'a'*64, 'workload_identity': ctl.WORKLOAD, 'device_identity': 'explicit-cpu-fixture',
            'fixture_source': str(cls.source), 'training_deadline_epoch': now+300}
        cls.wave = run_wave([job], python=sys.executable, source_root=str(ROOT), output_root=str(cls.base/'wave'),
            worker_module='tests.test_nvarc_convergence_controller', deadline_epoch=now+480,
            common_env={'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'},
            load_timeout_seconds=120, stop_timeout_seconds=5, finalization_reserve_seconds=10)
        cls.worker_root = cls.base/'wave'/ctl.JOB_ID
        if not cls.wave['completed']:
            raise AssertionError('actual CPU worker did not complete: '+str(cls.wave)+'\n'+(cls.worker_root/'worker.log').read_text()[-6000:])
        cls.report = json.loads((cls.worker_root/'convergence/report.json').read_bytes())
        cls.result = json.loads((cls.worker_root/'result.json').read_bytes())
        # Independently construct the tiny numerical contract, never derive the
        # expected tensor inventory/model schema from the untrusted export.
        engine = tiny_engine(dtype=torch.bfloat16, probability_policy=ctl.FP32_HEAD_POLICY)
        cls.contracts = ctl._Contracts(hashlib.sha256((cls.source/'manifest.json').read_bytes()).hexdigest(),
            copy.deepcopy(engine.contract), copy.deepcopy(engine.trainable_inventory),
            copy.deepcopy(engine.tokenizer_admission), configuration(),
            {**workflow.DEFAULT_EVALUATION, 'ttt_steps': 1}, .05)
        cls.model_identity = copy.deepcopy(engine.base_identity)
        del engine

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.local = tempfile.TemporaryDirectory()
        self.root = Path(self.local.name)/'convergence'
        shutil.copytree(self.worker_root/'convergence', self.root)
        self.report = copy.deepcopy(type(self).report)
        for arm in ctl.ARMS:
            self.report['exports'][arm]['checkpoint']['root'] = str(self.root/'checkpoints'/arm)
        save(self.root/'report.json', self.report)

    def tearDown(self):
        self.local.cleanup()

    def validate(self):
        return ctl._validate_report(self.report, self.root, source_identity='a'*64,
            model_identity=self.model_identity, contracts=self.contracts, training_root=self.source/'training', training_manifest_path=self.source/'manifest.json')

    def repin(self, name, body):
        save(self.root/name, body)
        self.report['private_artifacts'][name] = artifact(self.root/name, self.root)

    def change_window(self, index, mutate):
        compact = self.report['training']['windows'][index]; name = compact['artifact']['path']
        window = json.loads((self.root/name).read_bytes()); mutate(window)
        self.repin(name, window)
        summary = {k: v for k, v in window.items() if k not in ('capture', 'preflight', 'verification')}
        verification = window['verification']
        summary['verification'] = {k: v for k, v in verification.items() if k not in ('rows', 'failed_row')}
        summary['verification']['failed_row'] = None if not verification.get('failed_row') else {k: v for k, v in verification['failed_row'].items() if k != 'replay_log_probs'}
        summary.update(capture_sha256=window['capture']['seal_sha256'], policy_sha256=window['capture']['lineage']['policy_sha256'],
            preflight_passed=(window.get('preflight') or {}).get('passed'), artifact=self.report['private_artifacts'][name])
        self.report['training']['windows'][index] = summary
        return window

    def test_actual_owned_closed_fixture_reconstructs_every_window_export_and_paired_view(self):
        row = self.wave['jobs'][0]
        self.assertTrue(row['closure_verified']); self.assertTrue(ctl.shared._normal_closure(row))
        closure_structure(row['closure']); self.assertTrue(verify_closed_proof(row['closure']))
        self.assertEqual(json.loads((self.worker_root/'ownership/closure.json').read_bytes()), row['closure'])
        self.assertTrue(self.validate())
        self.assertEqual(len(self.report['training']['windows']), 13)
        self.assertEqual(sum(len(cell['records']) for arm in self.report['evaluation'].values() for cell in arm.values()), 160)
        self.assertEqual(sum(r['verification']['completed_views'] for a in self.report['evaluation'].values() for c in a.values() for r in c['records']), 320)
        self.assertFalse(self.report['candidate_selected'])

    def test_closed_fixture_proof_cannot_impersonate_production_worker_invocation(self):
        with self.assertRaisesRegex(ValueError, 'different worker invocation'):
            ctl._closed_worker(self.wave['jobs'][0], self.worker_root, {'python': sys.executable}, {}, 'explicit-cpu-fixture')

    def test_actual_fixture_never_passes_production_model_contract(self):
        with self.assertRaisesRegex(ValueError, 'official baseline2B'):
            ctl.validate_result(self.result, self.worker_root, source_identity='a'*64, device_identity='explicit-cpu-fixture')

    def test_resealed_forged_exact_score_rejected(self):
        row = self.report['evaluation']['anchor']['no_ttt']['records'][0]
        row['pass2'] = 1-row['pass2']
        with self.assertRaisesRegex(ValueError, 'exact scores'):
            self.validate()

    def test_raw_ranking_cannot_be_relabelled_with_new_hash(self):
        row = self.report['evaluation']['anchor']['no_ttt']['records'][0]
        name = row['prediction_artifact']['path']; raw = json.loads((self.root/name).read_bytes())
        raw['ranked_grids'] = [[[9]]]
        self.repin(name, raw); row['prediction_artifact'] = self.report['private_artifacts'][name]
        row['verification']['result_sha256'] = ctl._h(raw)
        with self.assertRaisesRegex(ValueError, 'ranking'):
            self.validate()

    def test_raw_view_prompt_substitution_rejected(self):
        row = self.report['evaluation']['finite_hybrid']['ttt']['records'][0]
        name = row['prediction_artifact']['path']; raw = json.loads((self.root/name).read_bytes())
        raw['views'][0]['token_evidence']['prompt_ids'][0] = 0
        self.repin(name, raw); row['prediction_artifact'] = self.report['private_artifacts'][name]
        row['verification']['result_sha256'] = ctl._h(raw)
        with self.assertRaisesRegex(ValueError, 'prompt/completion'):
            self.validate()

    def test_resealed_wrong_held_target_digest_rejected(self):
        protocol = json.loads((self.root/'protocol.json').read_bytes())
        protocol['development_target_digests'][protocol['development_parent_ids'][0]] = 'sha256:'+'f'*64
        self.repin('protocol.json', protocol); self.report['protocol_sha256'] = ctl._h(protocol)
        with self.assertRaisesRegex(ValueError, 'target/prompt'):
            self.validate()

    def test_changed_original_training_source_bytes_rejected(self):
        parent = json.loads((self.root/'training-panel.json').read_bytes()).keys().__iter__().__next__()
        path = self.source/'training'/(parent+'.json'); original = path.read_bytes()
        try:
            path.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError, 'pinned original training bytes'):
                self.validate()
        finally:
            path.write_bytes(original)

    def test_original_full_pool_denominator_substitution_rejected_after_reseal(self):
        def mutate(window):
            row = window['verification']['rows'][0]
            row['replay_log_probs'][row['prompt_length']] += .25
            window['verification']['max_logp_gap'] = .25
        self.change_window(0, mutate)
        with self.assertRaisesRegex(ValueError, 'replay continued|gap summary|pool admission'):
            self.validate()

    def test_successful_pool_vectors_cannot_be_omitted(self):
        self.change_window(0, lambda w: w['verification'].pop('rows'))
        with self.assertRaisesRegex(ValueError, 'gap summary'):
            self.validate()

    def test_stable_train_gradient_raw_logits_are_independently_checked(self):
        def mutate(window):
            raw = window['preflight']['probe']
            item = next(v for v in raw['logit_evidence'] if v['stage'] == 'full_train_grad')
            item['actual_logits'][0][0][0] += 1.
        self.change_window(0, mutate)
        with self.assertRaisesRegex(ValueError, 'stable probe admission'):
            self.validate()

    def test_later_arm_slot_cannot_reuse_shared_old_pool(self):
        slot = self.report['training']['arms']['known_target_ce']['slots'][1]
        slot['window_id'] = 'shared-anchor'
        with self.assertRaisesRegex(ValueError, 'stale, foreign'):
            self.validate()

    def test_modified_tensor_bytes_fail_even_when_manifest_file_pin_is_renewed(self):
        arm = 'known_target_ce'; path = self.root/'checkpoints'/arm/'trainable_state.safetensors'
        raw = bytearray(path.read_bytes()); raw[-4:] = struct.pack('<f', 99.)
        path.write_bytes(raw)
        manifest_path = path.parent/'manifest.json'; manifest = json.loads(manifest_path.read_bytes())
        manifest['file'] = {'name': path.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        save(manifest_path, manifest)
        self.report['exports'][arm]['checkpoint']['manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'tensor SHA'):
            self.validate()

    def test_checkpoint_probability_policy_cannot_be_downgraded(self):
        arm = 'anchor'; path = self.root/'checkpoints'/arm/'manifest.json'; manifest = json.loads(path.read_bytes())
        manifest['trainable_contract'].pop('probability_policy')
        save(path, manifest); self.report['exports'][arm]['checkpoint']['manifest_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'stable baseline'):
            self.validate()

    def test_no_ttt_mutation_and_fake_functional_reset_rejected(self):
        row = self.report['evaluation']['anchor']['no_ttt']['records'][0]
        row['ending_state_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'noTTT generation'):
            self.validate()
        row['ending_state_sha256'] = row['starting_state_sha256']
        reset = self.report['evaluation']['anchor']['ttt']['records'][0]['functional_reset']
        reset['nll_restored'] += 1
        with self.assertRaisesRegex(ValueError, 'functional reset'):
            self.validate()

    def test_partial_unknown_score_denominator_cannot_select_false_winner(self):
        arm = 'finite_hybrid'; cell = self.report['evaluation'][arm]['ttt']; row = cell['records'][-1]
        row['complete'] = False; row['status'] = 'failed_functional_reset'
        cell.update(complete=False, completed_parents=15, pass1=None, pass2=None)
        self.report['paired_ttt'].pop(arm)
        self.report.update(complete=False, status='partial', selected_arm='anchor', candidate_selected=False, selection_label='retain-anchor')
        self.assertFalse(self.validate())
        self.report.update(selected_arm='finite_hybrid', candidate_selected=True, selection_label='provisional-small-panel-candidate')
        with self.assertRaisesRegex(ValueError, 'unique strict'):
            self.validate()
        self.report.update(selected_arm='anchor', candidate_selected=False, selection_label='retain-anchor')
        cell['pass2'] = 0
        with self.assertRaisesRegex(ValueError, 'partial full-panel'):
            self.validate()

    def test_missing_row_never_shrinks_denominator(self):
        self.report['evaluation']['anchor']['no_ttt']['records'].pop()
        with self.assertRaisesRegex(ValueError, 'parent denominator'):
            self.validate()

    def test_resealed_extra_projection_attempts_cannot_disappear(self):
        self.report['training']['physical']['diagnostic_head_projection_attempts'] -= 1
        with self.assertRaisesRegex(ValueError, 'head projection charges'):
            self.validate()

    def test_changed_deadline_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, 'deadline binding'):
            ctl._validate_report(self.report, self.root, source_identity='a'*64, model_identity=self.model_identity,
                contracts=self.contracts, training_root=self.source/'training',
                phase_deadlines={'screen_deadline_epoch': self.report['training_deadline_epoch']+1,
                                 'worker_deadline_epoch': self.report['deadline_epoch']})

    def _partial_last_ttt(self, *, entered_adaptation=False):
        arm = 'finite_hybrid'; cell = self.report['evaluation'][arm]['ttt']; old = cell['records'][-1]
        name = old['prediction_artifact']['path']; (self.root/name).unlink()
        self.report['private_artifacts'].pop(name)
        counters = {k: 0 for k in ctl.COUNTERS}
        if entered_adaptation:
            # Entering sft_step is charged even if its optimizer commit never ran.
            counters['forward_calls'] = counters['model_forward_attempts'] = 1
        for key in ('optimizer_attempts', 'optimizer_steps'):
            self.report['physical'][key] -= old['physical'][key]
        row = {'parent_id': old['parent_id'], 'target_digest': old['target_digest'],
            'complete': False, 'status': 'deadline', 'pass1': None, 'pass2': None,
            'physical': counters, 'reset_state_sha256': old['reset_state_sha256']}
        if entered_adaptation:
            row.update(starting_state_sha256=old['starting_state_sha256'], adaptation={
                'data': 'demonstrations-only', 'optimizer_resumed': False, 'held_target_used_for_gradient': False,
                'requested_steps': 1, 'attempts': 1, 'steps': 0, 'all_requested_complete': False})
        cell['records'][-1] = row
        cell.update(complete=False, completed_parents=15, pass1=None, pass2=None,
            observed_pass1=cell['observed_pass1']-old['pass1'], observed_pass2=cell['observed_pass2']-old['pass2'])
        self.report['paired_ttt'].pop(arm)
        self.report.update(complete=False, status='partial', selected_arm='anchor', candidate_selected=False,
                           selection_label='retain-anchor')

    def test_deadline_before_start_keeps_unknown_row_without_fake_state(self):
        self._partial_last_ttt()
        self.assertFalse(self.validate())
        row = self.report['evaluation']['finite_hybrid']['ttt']['records'][-1]
        row['pass2'] = 0
        with self.assertRaisesRegex(ValueError, 'unknown, not measured zero'):
            self.validate()

    def test_adaptation_entry_without_optimizer_commit_is_valid_partial(self):
        self._partial_last_ttt(entered_adaptation=True)
        self.assertFalse(self.validate())

    def test_nonfinite_or_raised_functional_reset_keeps_observed_score_but_no_winner(self):
        cell = self.report['evaluation']['finite_hybrid']['ttt']; row = cell['records'][-1]
        row.update(complete=False, status='failed_functional_reset')
        row['functional_reset'].update(verified=False, nll_restored=None, tolerance=None)
        cell.update(complete=False, completed_parents=15, pass1=None, pass2=None)
        self.report['paired_ttt'].pop('finite_hybrid')
        self.report.update(complete=False, status='failed', selected_arm='anchor', candidate_selected=False,
                           selection_label='retain-anchor')
        self.assertFalse(self.validate())

    def test_foreign_probe_prompt_resealed_with_consistent_trace_is_rejected(self):
        from tools.nvarc_posttrain_20261017.probability_trace import _sha
        def mutate(window):
            raw = window['preflight']['probe']; trace = raw['trace']
            for prompt, row in zip(trace['prompts'], raw['rows']):
                prompt[0] = 0; row['input_ids'][0] = 0
            trace['sha256'] = _sha(trace)
        self.change_window(0, mutate)
        with self.assertRaisesRegex(ValueError, 'seeded first admitted'):
            self.validate()

    def test_probe_seed_and_model_context_cannot_be_relabelled(self):
        self.change_window(0, lambda w: w['preflight']['probe'].update(seed=99))
        with self.assertRaisesRegex(ValueError, 'probe seed/count'):
            self.validate()

    def test_objective_weights_must_rederive_from_original_exact_groups(self):
        slot = self.report['training']['arms']['known_target_ce']['slots'][0]
        slot['prompt_weights'][0]['weight'] = .01
        with self.assertRaisesRegex(ValueError, 'objective loss weights'):
            self.validate()

    def test_manifest_source_pin_cannot_be_self_asserted(self):
        manifest = self.source/'manifest.json'; body = manifest.read_bytes()
        try:
            manifest.write_bytes(body+b' ')
            with self.assertRaisesRegex(ValueError, 'immutable training manifest bytes'):
                self.validate()
        finally:
            manifest.write_bytes(body)

    def test_symlink_and_unpinned_file_bytes_rejected(self):
        path = self.root/'training-panel.json'; body = path.read_bytes()
        path.write_bytes(body+b' ')
        with self.assertRaisesRegex(ValueError, 'artifact bytes'):
            self.validate()
        path.unlink(); path.symlink_to(self.worker_root/'convergence/training-panel.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.validate()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--config':
        fixture_worker(Path(sys.argv[2]))
    else:
        unittest.main()
