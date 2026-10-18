"""CPU/source fixtures only: the owned wave, device and tiny state are mocked.

No official weights, CUDA workload, provider execution or effectiveness claim.
The fixture patches only the expected tensor inventory, never byte/hash checks.
"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.platform_requirements import requires_linux

from tools.arc2_goal_sprint_20261017.data import canonical, digest
from tools.arc2_goal_sprint_20261017.launch import write_new
from tools.nvarc_posttrain_20261017 import matched_controller as mc
from tests.test_nvarc_posttrain_controller import model_identity
from tests.test_nvarc_posttrain_package import closure as legacy_closure


def closure(**changes):
    return {**legacy_closure(), 'forced': False, 'reaped_identities': [], **changes}


def h(value):
    return hashlib.sha256(canonical(value)).hexdigest()


TENSORS = {'synthetic.cpu.weight': {'shape': [2], 'dtype': 'torch.float32'}}


def artifact(path, root):
    return {'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


def export_fixture(root, arm, *, values=(1., 2.)):
    name = next(iter(TENSORS)); data = struct.pack('<ff', *values)
    header = canonical({name: {'dtype': 'F32', 'shape': [2], 'data_offsets': [0, 8]}})
    header += b' ' * (-len(header) % 8)
    body = struct.pack('<Q', len(header)) + header + data
    state_hash = hashlib.sha256(name.encode() + b'(2,)' + data).hexdigest()
    directory = root / 'checkpoints' / arm; directory.mkdir(parents=True)
    (directory / 'trainable_state.safetensors').write_bytes(body)
    manifest = {'format': 'irisx/nvarc-compact-trainable-v1', 'base_identity': model_identity('2b'),
        'model_contract': mc._official_model_contract(), 'tokenizer_admission': mc._official_tokenizer_admission(),
        'trainable_contract': mc._official_trainable_contract(),
        'trainable_tensors': {name: {**TENSORS[name], 'sha256': hashlib.sha256(data).hexdigest()}},
        'origin': {'phase': 'pre_public', 'public_labels_used': False, 'public_ttt_applied': False,
            'source_identity': 'a' * 64, 'job_id': mc.JOB_ID, 'arm': arm},
        'state_sha256': state_hash, 'file': {'name': 'trainable_state.safetensors', 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}, 'optimizer_resumed': False, 'rng_resumed': False,
        'fresh_optimizer_required': True}
    save(directory / 'manifest.json', manifest)
    return {'status': 'complete', 'state_sha256': state_hash, 'checkpoint': {'root': str(directory),
        'manifest_sha256': artifact(directory / 'manifest.json', root)['sha256'], 'state_sha256': state_hash}}


def result_fixture(root, *, partial=False, scores=None):
    root.mkdir(parents=True, exist_ok=True)
    scores = scores or {arm: 8 for arm in mc.ARMS}
    ids = [f'p{i:02}' for i in range(16)]
    binding = {'source': {'training_manifest_sha256': mc.TRAINING_MANIFEST_SHA256},
               'split': {'synthetic_fixture': True}, 'family_lineage': {'synthetic_fixture': True}}
    pins = {field: h(binding[key]) for key, field in
            (('source', 'source_sha256'), ('split', 'split_sha256'), ('family_lineage', 'family_lineage_sha256'))}
    admission = {**pins, 'parents': [{'parent_id': f't{i:02}'} for i in range(16)]}
    protocol = {**pins, 'version': mc.WORKFLOW, 'arms': list(mc.ARMS), 'views': 2, 'ttt_steps': 0,
        'held_demo_index': 0, 'public_feedback_used': False, 'admission_sha256': h(admission),
        'development_parent_ids': ids, 'development_target_digest': {parent: digest([[1]]) for parent in ids}, 'training_parent_ids': [f't{i:02}' for i in range(16)]}
    artifacts = {}
    for name, value in [('matched-source-binding.json', binding), ('matched-admission.json', admission),
                        ('matched-protocol.json', protocol)]:
        save(root / name, value); artifacts[name] = artifact(root / name, root)
    exports = {arm: export_fixture(root, arm) for arm in mc.ARMS}
    capture = {'groups': [{'parent_id': 't00', 'status': 'complete', 'category': 'mixed'}],
               'status': 'synthetic_fixture'}
    capture['seal_sha256'] = h(capture)
    full = {'status': 'complete', 'anchor_restored': True, 'engine_poisoned': False, 'cleanup_errors': [],
        'capture': capture, 'collection': {}, 'state_sha256': {arm: ex['state_sha256'] for arm, ex in exports.items()},
        'arms': {arm: {'status': 'complete', 'after_sha256': ex['state_sha256']} for arm, ex in exports.items()}}
    save(root / 'matched-controls.json', full); artifacts['matched-controls.json'] = artifact(root / 'matched-controls.json', root)
    controls = {**full, 'capture': {k: v for k, v in capture.items() if k != 'groups'},
                'collection': {'distinct_mixed_parents': 1}}
    controls['capture']['group_count'] = 1
    evaluation = {'complete': not partial, 'full_requested_denominator': 16, 'requested_views': 2, 'arms': {}}
    for arm in mc.ARMS:
        rows = []
        for i, parent in enumerate(ids):
            complete = not (partial and arm == mc.ARMS[-1] and i == 15)
            row = {'parent_id': parent, 'target_digest': digest([[1]]), 'complete': complete, 'completed_views': 2 if complete else 0,
                'valid': complete, 'pass1': int(complete and i < scores[arm]), 'pass2': int(complete and i < scores[arm])}
            if complete:
                grid = [[1]] if i < scores[arm] else [[2]]
                raw = {'complete': True, 'views': [{'view': 0}, {'view': 1}], 'ranked_grids': [grid],
                    'candidates': [{'grid': grid}], 'ranked_candidate_indices': [0]}
                path = root / 'predictions' / arm / (parent + '.json'); save(path, raw)
                receipt = artifact(path, root); artifacts[receipt['path']] = receipt
                row.update(prediction_artifact=receipt, state_sha256=exports[arm]['state_sha256'],
                    verification={'verified': True, 'completed_views': 2, 'candidate_count': 1, 'result_sha256': h(raw)})
            rows.append(row)
        evaluation['arms'][arm] = {'complete': all(row['complete'] for row in rows), 'requested_parents': 16,
            'complete_parents': sum(row['complete'] for row in rows), 'records': rows,
            **{key: sum(int(row[key]) for row in rows) for key in ('pass1', 'pass2', 'valid')}}
    best = max(scores.values()); winners = [arm for arm in mc.ARMS if scores[arm] == best]
    selected = winners[0] if not partial and len(winners) == 1 and best > scores['anchor'] else 'anchor'
    report = {'format': 'irisx/nvarc-matched-workflow-v1', 'status': 'partial' if partial else 'complete',
        'complete': not partial, 'protocol_sha256': h(protocol), 'admission_sha256': h(admission),
        'full_requested_denominator': 16, 'public_inference_performed': False, 'public_scoring_performed': False,
        'public_answers_used': False, 'clean_generalization_claimed': False, 'source_identity': 'a' * 64,
        'job_id': mc.JOB_ID, 'arms': list(mc.ARMS), 'private_artifacts': artifacts, 'exports': exports,
        'controls': controls, 'evaluation': evaluation, 'anchor_restored': True, 'engine_poisoned': False,
        'cleanup_errors': [], 'selected_arm': selected, 'candidate_selected': selected != 'anchor',
        'returned_after_evaluation_deadline': False,
        'selection_label': 'provisional16-parent-mechanism-candidate' if selected != 'anchor' else 'retain-anchor'}
    result = {'mode': 'matched', 'job_id': mc.JOB_ID, 'source_identity': 'a' * 64,
        'workload_identity': mc.WORKLOAD, 'device_identity': 'synthetic-device', 'model_identity': model_identity('2b'),
        'completed': not partial, 'matched': report}
    persist_result(root, result)
    return result


def persist_result(root, result):
    save(root / 'matched-report.json', result['matched'])
    result['matched_report'] = artifact(root / 'matched-report.json', root)
    save(root / 'result.json', result)


class ProbabilityConsumerTests(unittest.TestCase):
    """Pure synthetic receipt validation, no Torch/model/accuracy claims."""
    def evidence(self):
        from tools.nvarc_posttrain_20261017 import probability_trace as pt
        trace = {'format': pt.TRACE_FORMAT, 'prompts': [[14], [14]], 'prompt_lengths': [1, 1],
            'batch_size': 2, 'padding_width': 1, 'max_new_tokens': 931, 'sample': True,
            'conventions': copy.deepcopy(pt.TRACE_CONVENTIONS), 'status': 'completed', 'error': None,
            'steps': [{'step': 0, 'selected_ids': [15, 15], 'selected_log_probs': [-0.1, -0.2],
                       'retained': [True, True], 'committed': True}],
            'completion_ids': [[15], [15]], 'completion_log_probs': [[-0.1], [-0.2]],
            'stops': ['completed', 'completed'],
            'work': {'generation_forward_attempts': 1, 'generation_input_tokens': 2,
                     'generation_row_token_slots': 2, 'generation_finished_row_token_slots': 0,
                     'generation_padding_tokens': 0, 'forward_calls': 1, 'sampled_tokens': 2}}
        trace['sha256'] = pt._sha(trace)
        rows = [{'input_ids': [14, 15], 'prompt_length': 1, 'completion_ids': [15],
                 'behavior_log_probs': [0.0, value], 'text': '<|im_end|>', 'completion_tokens': 1,
                 'stop': 'completed'} for value in [-0.1, -0.2]]
        raw = {'training_authorized': False, 'status': 'completed', 'trace': trace, 'rows': rows,
            'cached_replay': {'status': 'completed', 'steps': [{'step': 0, 'selected_ids': [15, 15],
                'behavior_log_probs': [-0.1, -0.2], 'cached_log_probs': [-0.1, -0.2], 'retained': [True, True]}]},
            'full_replay': [{'row_index': i, 'completion_ids': [15], 'behavior_log_probs': [value],
                             'full_log_probs': [value]} for i, value in enumerate([-0.1, -0.2])],
            'cached_max_abs_logp_gap': 0.0, 'full_max_abs_logp_gap': 0.0, 'full_metrics': {'tokens': 2}}
        return {'protocol': mc.PREFLIGHT, 'used_for_loss': False, 'full_pool_verification_still_required': True,
            **mc._official_preflight_config(), 'policy_before_sha256': 'a'*64, 'policy_after_sha256': 'a'*64,
            'engine_poisoned_after': False, 'prompt_ids_sha256': h([14]), 'status': 'completed', 'passed': True,
            'metrics': {'cached_max_abs_logp_gap': 0.0, 'full_max_abs_logp_gap': 0.0, 'full_path': {'tokens': 2}},
            'physical': {'optimizer_steps': 0, 'optimizer_attempts': 0}, 'probe': raw}

    def validate(self, root, evidence):
        name = 'matched-probability-preflight.json'; save(root/name, evidence)
        matched = {'anchor_policy_sha256': 'a'*64,
            'probability_preflight': {k: v for k, v in evidence.items() if k != 'probe'}}
        return mc._probability_preflight(matched, {'probability_preflight': mc.PREFLIGHT}, root,
                                        {name: artifact(root/name, root)})

    def test_complete_original_trace_and_vectors_pass_without_ml(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(self.validate(Path(temp), self.evidence()))

    def test_resealed_denominator_substitution_cannot_replace_sampled_trace(self):
        evidence = self.evidence()
        evidence['probe']['rows'][0]['behavior_log_probs'][1] -= 0.125
        evidence['probe']['full_replay'][0]['behavior_log_probs'][0] -= 0.125
        evidence['probe']['full_replay'][0]['full_log_probs'][0] -= 0.125
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'original trace'):
            self.validate(Path(temp), evidence)

    def test_resealed_truncated_full_replay_cannot_drop_unfavorable_tokens(self):
        evidence = self.evidence()
        evidence['probe']['full_replay'][0]['behavior_log_probs'] = []
        evidence['probe']['full_replay'][0]['full_log_probs'] = []
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'original sampled'):
            self.validate(Path(temp), evidence)

    def test_invalid_trace_commit_is_rejected_even_if_all_outer_hashes_change(self):
        from tools.nvarc_posttrain_20261017 import probability_trace as pt
        evidence = self.evidence(); trace = evidence['probe']['trace']
        trace['steps'][0]['committed'] = False; trace['sha256'] = pt._sha(trace)
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'commit'):
            self.validate(Path(temp), evidence)


class MatchedControllerTests(unittest.TestCase):
    def setUp(self):
        # The fixtures do not pretend to contain394 official model tensors.
        self.tensor_patch = patch.object(mc, '_official_tensor_contract', return_value=TENSORS)
        self.tensor_patch.start(); self.addCleanup(self.tensor_patch.stop)

    def config(self, root):
        now = time.time()
        return {'workflow': mc.WORKFLOW, 'started_epoch': now - 1, 'deadline_epoch': now - 1 + 43200,
            'parameters': {}, 'model_roots': {'2b': 'official-two'}, 'source_identity': 'a' * 64,
            'run_id': 'synthetic-matched', 'source_root': str(root), 'output_root': str(root / 'solver'),
            'input_root': str(root / 'input'), 'allowed_input_roots': [], 'runtime_env': {}, 'python': 'python',
            'training_root': 'train', 'training_manifest_path': 'manifest', 'public_path': 'solver-only'}

    def topology(self):
        return {'measured': True, 'device_count': 1, 'device_identity': 'synthetic-device',
            'hardware_partition_claimed': False, 'total_bytes': 24 * mc.GIB, 'free_bytes': 22 * mc.GIB}

    def dispatch(self, root, *, partial=False, proof=None):
        config = self.config(root)
        calls = []
        def execute(jobs, **kwargs):
            calls.append((jobs, kwargs))
            worker = Path(kwargs['output_root']) / mc.JOB_ID
            result = result_fixture(worker, partial=partial)
            result['matched'].update(screen_deadline_epoch=jobs[0]['training_deadline_epoch'],
                evaluation_deadline_epoch=kwargs['deadline_epoch'] - mc.STOP_SECONDS - mc.FINALIZATION_SECONDS)
            persist_result(worker, result)
            return {'completed': not partial, 'wall_seconds': 1., 'jobs': [{'job_id': mc.JOB_ID,
                'status': 'worker_failed' if partial else 'completed', 'closure_verified': True,
                'closure': proof or closure(), 'result': result}]}
        with patch.object(mc, 'check_dataset_separation'), patch.object(mc, 'progress'), \
                patch.object(mc.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(self.topology()))), \
                patch.object(mc.shutil, 'disk_usage', return_value=SimpleNamespace(free=4 * mc.GIB)), \
                patch.object(mc, 'run_wave', side_effect=execute):
            summary = mc.run(config)
        return config, summary, calls

    def validate(self, root, result):
        return mc.validate_result(result, root, source_identity='a' * 64, device_identity='synthetic-device')

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_exact_single_owned_official2b_path_and_deadline_reserves(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            config, summary, calls = self.dispatch(Path(temp))
            self.assertTrue(summary['completed']); self.assertEqual(len(calls), 1)
            jobs, args = calls[0]; self.assertEqual(len(jobs), 1)
            self.assertEqual((jobs[0]['job_id'], jobs[0]['variant'], jobs[0]['arm'], jobs[0]['mode']),
                             (mc.JOB_ID, '2b', 'S', 'matched'))
            self.assertEqual(jobs[0]['parameters'], {}); self.assertNotIn('checkpoint', jobs[0])
            plan = summary['phase_plan']
            self.assertEqual(args['deadline_epoch'], config['deadline_epoch'] - 180)
            self.assertEqual(plan['worker_deadline_epoch'], args['deadline_epoch'] - 45)
            self.assertEqual(jobs[0]['training_deadline_epoch'], plan['screen_deadline_epoch'])
            self.assertGreaterEqual(plan['heldout_reserve_seconds'], 3600)
            self.assertFalse(summary['public_inference_performed']); self.assertFalse(summary['automatic_following_run'])

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_partial_report_retains_full_denominator_and_anchor(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            _, summary, _ = self.dispatch(Path(temp), partial=True)
            self.assertFalse(summary['completed'])
            report = summary['workers'][0]['result']['matched']
            self.assertEqual(report['selected_arm'], 'anchor')
            for arm in report['evaluation']['arms'].values():
                self.assertEqual(arm['requested_parents'], 16); self.assertEqual(len(arm['records']), 16)

    def test_late_complete_views_are_incomplete_and_cannot_select(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); result = result_fixture(root)
            result['matched'].update(returned_after_evaluation_deadline=True, complete=False, status='partial')
            result['completed'] = False; persist_result(root, result)
            self.assertFalse(self.validate(root, result))
            result['matched'].update(complete=True, status='complete'); result['completed'] = True
            persist_result(root, result)
            with self.assertRaisesRegex(ValueError, 'completion differs'):
                self.validate(root, result)

    def test_only_unique_complete_strict_improvement_selects_candidate(self):
        cases = [({'anchor': 8, 'known_target_ce': 8, 'exact_positive_ce': 8, 'exact_centered_ddis': 8}, 'anchor'),
                 ({'anchor': 8, 'known_target_ce': 9, 'exact_positive_ce': 9, 'exact_centered_ddis': 8}, 'anchor'),
                 ({'anchor': 8, 'known_target_ce': 9, 'exact_positive_ce': 8, 'exact_centered_ddis': 8}, 'known_target_ce')]
        for scores, selected in cases:
            with tempfile.TemporaryDirectory() as temp, self.subTest(selected=selected):
                root = Path(temp); result = result_fixture(root, scores=scores)
                self.assertTrue(self.validate(root, result)); self.assertEqual(result['matched']['selected_arm'], selected)

    def test_rejects_fourb_unknown_overrides_resume_and_consumed_clocks_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = self.config(Path(temp))
            changes = [{'workflow': 'dual-posttrain-v1'}, {'model_roots': {'2b': 'two', '4b': 'four'}},
                {'model_roots': {'4b': 'four'}}, {'parameters': {'generation_tokens': 20}}, {'checkpoint': {}},
                {'started_epoch': float('nan')}, {'deadline_epoch': base['deadline_epoch'] + 1},
                {'started_epoch': time.time() - 43000, 'deadline_epoch': time.time() + 200}]
            with patch.object(mc, 'run_wave') as run:
                for change in changes:
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        mc.run({**base, **change})
                run.assert_not_called()

    def test_original_session_feasibility_is_not_quota_query(self):
        now = time.time()
        with self.assertRaisesRegex(ValueError, 'insufficient original-session'):
            mc.phase_plan({'started_epoch': now - 42000, 'deadline_epoch': now + 1200}, now)
        plan = mc.phase_plan({'started_epoch': now - 1, 'deadline_epoch': now - 1 + 43200}, now)
        self.assertFalse(plan['quota_hours_queried'])

    def test_per_device_memory_uses_actual_original2b_envelope_not_pooling(self):
        self.assertEqual(mc.HISTORICAL_2B_RESERVATION, 15679147213)
        mc._topology(self.topology())
        for change in ({'device_count': 4}, {'measured': False}, {'hardware_partition_claimed': True},
                       {'free_bytes': 19 * mc.GIB}, {'device_identity': 'MIG-synthetic'}, {'free_bytes': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                mc._topology({**self.topology(), **change})

    def test_disk_reserve_blocks_launch(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(mc, 'check_dataset_separation'), \
                patch.object(mc.shutil, 'disk_usage', return_value=SimpleNamespace(free=mc.GIB)), \
                patch.object(mc, 'run_wave') as run, patch.object(mc.subprocess, 'run') as topology:
            with self.assertRaisesRegex(ValueError, '3GiB'):
                mc.run(self.config(Path(temp)))
            run.assert_not_called(); topology.assert_not_called()

    def test_identity_status_and_completion_cannot_be_fabricated(self):
        mutations = [lambda r: r.update(mode='public'), lambda r: r.update(model_identity=model_identity('4b')),
            lambda r: r.update(workload_identity='wrong'), lambda r: r['matched'].update(public_answers_used=True),
            lambda r: r['matched']['evaluation']['arms']['anchor'].update(complete_parents=15),
            lambda r: r['matched']['exports'].pop('known_target_ce'),
            lambda r: r['matched'].update(selected_arm='exact_centered_ddis', candidate_selected=True),
            lambda r: r['matched']['evaluation']['arms']['anchor']['records'].pop()]
        for i, mutate in enumerate(mutations):
            with tempfile.TemporaryDirectory() as temp, self.subTest(case=i):
                root = Path(temp); result = result_fixture(root); mutate(result); persist_result(root, result)
                with self.assertRaises(ValueError):
                    self.validate(root, result)

    def test_raw_prediction_hash_and_verification_digest_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); result = result_fixture(root)
            row = result['matched']['evaluation']['arms']['anchor']['records'][0]
            row['verification']['result_sha256'] = 'e' * 64; persist_result(root, result)
            with self.assertRaisesRegex(ValueError, 'raw prediction'):
                self.validate(root, result)


    def test_exact_scores_target_binding_and_candidate_count_are_recomputed(self):
        for action in ('counts','false_miss','target','candidate_count'):
            with tempfile.TemporaryDirectory() as temp, self.subTest(action=action):
                root=Path(temp);result=result_fixture(root)
                report=result['matched']['evaluation']['arms']['anchor'];row=report['records'][0]
                if action=='counts':
                    row.update(pass1=0,pass2=0);report['pass1']-=1;report['pass2']-=1
                elif action=='false_miss':
                    row.update(pass1=0,pass2=0,valid=False);report['pass1']-=1;report['pass2']-=1;report['valid']-=1
                elif action=='target':row['target_digest']=digest([[9]])
                else:row['verification']['candidate_count']=2
                persist_result(root,result)
                with self.assertRaises(ValueError):self.validate(root,result)

    def test_different_report_phase_deadline_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); result = result_fixture(root)
            result['matched'].update(screen_deadline_epoch=10., evaluation_deadline_epoch=100.)
            persist_result(root, result)
            with self.assertRaisesRegex(ValueError, 'phase deadlines differ'):
                mc.validate_result(result, root, source_identity='a' * 64, device_identity='synthetic-device',
                    phase_deadlines={'screen_deadline_epoch': 11., 'worker_deadline_epoch': 100.})

    def test_full_captured_pool_seal_not_only_report_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); result = result_fixture(root)
            path = root / 'matched-controls.json'; full = json.loads(path.read_bytes())
            full['capture']['groups'][0]['parent_id'] = 'tampered'; save(path, full)
            result['matched']['private_artifacts'][path.name] = artifact(path, root); persist_result(root, result)
            with self.assertRaisesRegex(ValueError, 'captured pool seal'):
                self.validate(root, result)

    def test_checkpoint_body_manifest_origin_and_state_hash_checked(self):
        for action in ('body', 'origin', 'state'):
            with tempfile.TemporaryDirectory() as temp, self.subTest(action=action):
                root = Path(temp); result = result_fixture(root)
                export = result['matched']['exports']['anchor']; directory = root / 'checkpoints' / 'anchor'
                if action == 'body':
                    with (directory / 'trainable_state.safetensors').open('ab') as stream:
                        stream.write(b'evil')
                else:
                    manifest = json.loads((directory / 'manifest.json').read_bytes())
                    if action == 'origin': manifest['origin']['arm'] = 'exact_centered_ddis'
                    else: manifest['state_sha256'] = 'b' * 64; export['state_sha256'] = 'b' * 64; export['checkpoint']['state_sha256'] = 'b' * 64
                    save(directory / 'manifest.json', manifest)
                    export['checkpoint']['manifest_sha256'] = artifact(directory / 'manifest.json', root)['sha256']
                    persist_result(root, result)
                with self.assertRaises(ValueError): self.validate(root, result)


    def test_exact_model_trainable_and_tokenizer_contracts_cannot_be_changed(self):
        for kind in ('rotary','rslora','projection','tokenizer'):
            with tempfile.TemporaryDirectory() as temp, self.subTest(kind=kind):
                root=Path(temp);result=result_fixture(root);export=result['matched']['exports']['anchor']
                path=root/'checkpoints'/'anchor'/'manifest.json';manifest=json.loads(path.read_bytes())
                if kind=='rotary':manifest['model_contract']['rope_parameters']['rope_theta']=123
                elif kind=='rslora':manifest['trainable_contract']['use_rslora']=False
                elif kind=='projection':manifest['trainable_contract']['target_modules']=[]
                else:manifest['tokenizer_admission']={}
                save(path,manifest);export['checkpoint']['manifest_sha256']=artifact(path,root)['sha256'];persist_result(root,result)
                with self.assertRaises(ValueError):self.validate(root,result)

    @requires_linux('Late closure requires the Linux owned-process proof contract')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_late_closure_retains_all_work_without_claiming_session_completion(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config,_,_=self.dispatch(root)
            control=root/'control';control.mkdir();save(control/'owner-closure.json',closure())
            with patch.object(mc.time,'time',return_value=config['deadline_epoch']+1):
                terminal=mc.close_diagnostic(config,control,closure())
            self.assertFalse(terminal['completed']);self.assertFalse(terminal['finalization_within_original_session'])
            self.assertTrue(terminal['files']);self.assertEqual(terminal['status'],'CLOSED_DIAGNOSTIC')

    def test_tensor_finiteness_is_verified_without_torch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); export_fixture(root, 'anchor', values=(float('nan'), 1.))
            manifest = json.loads((root / 'checkpoints/anchor/manifest.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'nonfinite checkpoint'):
                mc._verify_tensor_file(root / 'checkpoints/anchor/trainable_state.safetensors', manifest)

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_normal_closure_binds_all_files_not_json_only(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config, _, _ = self.dispatch(root)
            output = Path(config['output_root']); (output / 'worker-extra.log').write_bytes(b'private log')
            (output / 'rng-state.pt').write_bytes(b'not deserialized')
            control = root / 'control'; control.mkdir(); save(control / 'owner-closure.json', closure())
            terminal = mc.close_diagnostic(config, control, closure())
            self.assertTrue(terminal['completed']); self.assertEqual(terminal['status'], 'CLOSED_DIAGNOSTIC')
            for arm in mc.ARMS:
                self.assertIn(f'matched-2b/{mc.JOB_ID}/checkpoints/{arm}/trainable_state.safetensors', terminal['files'])
            self.assertIn('worker-extra.log', terminal['files']); self.assertIn('rng-state.pt', terminal['files'])
            self.assertFalse(terminal['provider_terminal_verified']); self.assertIsNone(terminal['public_score'])
            self.assertFalse(terminal['generation_may_resume']); self.assertFalse((control / 'sealed').exists())

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_forced_parent_closure_or_nonzero_return_cannot_complete(self, _closed_proof):
        for change in ({'forced': True}, {'worker_returncode': 1}, {'returncode': 125}):
            with tempfile.TemporaryDirectory() as temp, self.subTest(change=change):
                root = Path(temp); config, _, _ = self.dispatch(root)
                control = root / 'control'; control.mkdir(); proof = closure(**change)
                save(control / 'owner-closure.json', proof)
                self.assertFalse(mc.close_diagnostic(config, control, proof)['completed'])

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_forced_worker_tree_cannot_make_complete_summary(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            _, summary, _ = self.dispatch(Path(temp), proof=closure(forced=True))
            self.assertFalse(summary['completed'])

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_missing_summary_is_closed_incomplete_not_false_success(self, _closed_proof):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = self.config(root); control = root / 'control'; control.mkdir()
            save(control / 'owner-closure.json', closure())
            result = mc.close_diagnostic(config, control, closure())
            self.assertFalse(result['completed']); self.assertEqual(result['files'], {})

    @requires_linux('Owned process-closure contract imports Linux signals and procfs support')
    @patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof')
    def test_closure_proof_and_persisted_result_tampering_rejected(self, _closed_proof):
        for action in ('proof', 'result', 'summary'):
            with tempfile.TemporaryDirectory() as temp, self.subTest(action=action):
                root = Path(temp); config, _, _ = self.dispatch(root); output = Path(config['output_root'])
                control = root / 'control'; control.mkdir(); save(control / 'owner-closure.json', closure())
                if action == 'proof': save(control / 'owner-closure.json', closure(forced=True))
                if action == 'result': save(output / 'matched-2b' / mc.JOB_ID / 'result.json', {'completed': True})
                if action == 'summary':
                    path = output / 'run-summary.json'; summary = json.loads(path.read_bytes())
                    summary['requested_models'] = ['2b', '4b']; save(path, summary)
                with self.assertRaises(ValueError): mc.close_diagnostic(config, control, closure())

    @requires_linux('Symlink creation requires native link support and privilege')
    def test_symlink_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / 'out'; output.mkdir(); outside = root / 'outside'; outside.write_bytes(b'x')
            (output / 'link').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'symlink'): mc._inventory(output)

    def test_inventory_caps_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp); (output / 'large.bin').write_bytes(b'abcd')
            with patch.object(mc, 'MAX_TOTAL', 3), self.assertRaisesRegex(ValueError, 'bounded complete'):
                mc._inventory(output)

    def test_controller_source_has_no_model_or_evaluator_execution_import(self):
        source = Path(mc.__file__).read_text()
        for forbidden in ('import torch', 'from .matched_workflow import', 'CompactEngine.load(', 'score.seal(', 'resource_probe('):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
