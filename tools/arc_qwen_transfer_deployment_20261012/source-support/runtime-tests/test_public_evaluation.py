"""Explicit synthetic120/167 fixtures; no model dependencies or real gold data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.arc_qwen_transfer_20261012 import public_evaluation as pe
from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
from tools.arc_public_research_20261010.prepare_public_assets import _write_assets
from tools.arc_public_research_20261010.public_data import canonical, write_new, sha256, COMMIT, REPOSITORY
from tools.arc_offline_evaluation import load_pinned_reference
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_learning_agent_20261011.grid_codec import encode_grid, grid_messages
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof, _read_process, _identity
from irisx.artifacts import make_artifact


def native_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def assets(root):
    source = root / 'source'; source.mkdir()
    write_new(source / 'LICENSE', b'Explicit synthetic test fixture; no real ARC answers.\n', raw=True)
    rows = []
    for n in range(120):
        name = 'data/evaluation/%08x.json' % n
        task = {'train': [{'input': [[1, 2]], 'output': [[2, 3]]}],
                'test': [{'input': [[n % 10, i]], 'output': [[(n + i) % 10, (n + i + 1) % 10]]}
                         for i in range(2 if n < 47 else 1)]}
        raw = canonical(task) + b'\n'; write_new(source / name, raw, raw=True)
        rows.append({'path': name, 'byte_size': len(raw), 'content_digest': 'sha256:' + sha256(raw)})
    provenance = make_artifact('irisx/arc-source-provenance', 'synthetic-public-fixture', '1.0.0',
                               {'repository': REPOSITORY, 'commit': COMMIT, 'files': rows})
    prov = source / 'provenance.json'; write_new(prov, provenance)
    challenges, solutions, reference = load_pinned_reference(source, prov)
    result = _write_assets(source, prov, root / 'assets', challenges, reference, evidence_mode='synthetic-test-only')
    return result, challenges, solutions


class PublicEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='transfer-public-test-')
        cls.root = Path(cls.temp.name)
        cls.assets, cls.challenges, cls.solutions = assets(cls.root)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def fixture(self, *, omit_last=False, shuffle=False, extra_answer=False, bad_grid=False):
        root = Path(tempfile.mkdtemp(dir=self.root)); owner = root / 'owner'; owner.mkdir()
        config = {'tiny_cpu': True, 'test_public_evaluation_fixture': True,
                  'public_solver_root': self.assets['solver_root'],
                  'public_solver_manifest_sha256': self.assets['solver_manifest_sha256']}
        request = {'format': 'irisx/transfer-public-fixture-request-v1', 'config': config,
                   'output_root': str(owner), 'source_identity': pe.source_identity()}
        request_path = owner / 'request.json'; write_new(request_path, request)
        request_sha = sha256(request_path.read_bytes())
        guard = OwnedProcessGuard.spawn([sys.executable, '-I', '-B', '-S', str(Path(pe.__file__).resolve()),
            '--fixture-owner', str(request_path), request_sha], evidence_dir=owner / 'owned-tree',
            stdout=-3, stderr=-3, cwd=owner)
        deadline = time.monotonic() + 10
        while guard.poll() is None and time.monotonic() < deadline: time.sleep(.01)
        proof = guard.closed_proof()
        if not proof['closed']: proof = guard.stop()
        verify_closed_proof(proof)
        self.assertEqual(proof['worker_returncode'], 0)
        ledger = WorkLedger(owner / 'physical-work.jsonl')
        artifact = {'format': pe.ARTIFACT_FORMAT, 'solver_manifest_sha256': self.assets['solver_manifest_sha256'],
                    'method': {'candidate_id': 'sft2', 'role': 'global_sft', 'checkpoint_manifest_sha256': 'a' * 64, 'adapter_sha256': 'b' * 64},
                    'predictions': {}, 'case_receipts': [], 'case_count': 0, 'test_answers_read': False,
                    'physical_pending': {}, 'plan_sha256': 'c' * 64}
        for key, task in sorted(self.challenges.items()):
            artifact['predictions'][key] = []
            for index, query in enumerate(task['test']):
                if omit_last and key == '00000077':
                    artifact['predictions'][key].append({'attempt_1': None, 'attempt_2': None}); continue
                answer = self.solutions[key][index]
                case = {'parent_id': key, 'test_index': index, 'input_sha256': pe.digest(query['input']), 'generations': []}
                for d4 in (0, 1):
                    event = key + '-' + str(index) + '-' + str(d4)
                    text = encode_grid([list(row) for row in Transform(d4).apply(answer)])
                    ids = [ord(x) for x in text] + [151645]
                    amounts = {'generation_calls': 1, 'input_tokens': 10, 'output_tokens': len(ids)}
                    ledger.reserve(event, amounts); ledger.complete(event, amounts)
                    receipt = {'physical_event_id': event, 'text': text, 'output_token_ids': ids,
                               'output_sha256': native_hash(ids), 'native_eos_ids': [151645],
                               'adapter_fingerprint': 'd' * 64, 'adapter_state_sha256': 'b' * 64, 'adapter_execution_mode': 'trained', 'dispatched': True, 'model_forward_started': True,
                               'forward_input_tokens': 10, 'output_tokens': len(ids), 'tiny_cpu': True,
                               'valid': True, 'finish_reason': 'eos'}
                    path = owner / 'generations' / (event + '.json')
                    transform = Transform(d4)
                    demos = [{k: [list(row) for row in transform.apply(d[k])] for k in ('input', 'output')} for d in task['train']]
                    q = [list(row) for row in transform.apply(query['input'])]
                    messages = grid_messages(demos, q)
                    prompt = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n' for m in messages)
                    prompt += '<|im_start|>assistant\n<think>\n\n</think>\n\n'
                    receipt.update(rendered_prompt_sha256=sha256(prompt.encode()), input_tokens=10)
                    packing = {'format': 'irisx/whole-demonstration-packing-v1', 'task_id': 'public:' + key + ':' + str(index),
                               'admitted': True, 'selected_demo_ids': ['0'], 'omitted_demo_ids': [], 'withheld_demo_id': None,
                               'query_targets_used': False, 'partial_grids_or_targets_truncated': False,
                               'context_limit': 4096, 'output_cap': 1024, 'prompt': prompt, 'prompt_sha256': native_hash(prompt), 'prompt_tokens': 10}
                    write_new(path.with_suffix('.packing.json'), packing)
                    bound = write_new(path, receipt)
                    case['generations'].append({'transform_d4': d4, 'inverse_applied': True,
                        'prediction': deepcopy(answer), 'dispatched': True, 'physical_event_id': event,
                        'receipt_sha256': bound['sha256'], 'receipt_path': str(path)})
                artifact['predictions'][key].append({'attempt_1': deepcopy(answer), 'attempt_2': None})
                artifact['case_receipts'].append(case)
        artifact['case_count'] = len(artifact['case_receipts'])
        if shuffle:
            artifact['predictions']['00000000'].reverse()
        if extra_answer:
            artifact['predictions']['00000000'][0]['attempt_3'] = [[1]]
        if bad_grid:
            artifact['predictions']['00000000'][0]['attempt_1'] = [[True, 1]]
        artifact_path = owner / 'public-predictions.json'; write_new(artifact_path, artifact)
        branch = {'status': 'PUBLIC_PARTIAL' if omit_last else 'PUBLIC_PREDICTIONS_SEALED',
                  'solver_manifest_sha256': self.assets['solver_manifest_sha256'],
                  'artifact_path': str(artifact_path), 'artifact_sha256': sha256(artifact_path.read_bytes()),
                  'method': artifact['method'], 'cases': artifact['case_count'],
                  'actual_generation_calls': artifact['case_count'] * 2}
        result = {'status': 'TRANSFER_PARTIAL' if omit_last else 'TRANSFER_COMPLETE',
                  'request_sha256': request_sha, 'source_identity_sha256': pe.digest(request['source_identity']),
                  'model_stopped': True, 'pending_work': {}, 'physical_pending': {}, 'public_branch': branch,
                  'physical_usage': ledger.used, 'elapsed_seconds': 1, 'production_model': False,
                  'runtime_evidence': {}, 'model_identity': {'synthetic_test_only': True}}
        result_path = owner / 'child-summary.json'; write_new(result_path, result)
        return {'root': root, 'owner': owner, 'request': request, 'result': result, 'artifact': artifact,
                'request_path': request_path, 'result_path': result_path, 'proof': proof}

    def seal(self, fixture):
        return pe.seal_predictions(fixture['root'] / 'seal', solver_root=self.assets['solver_root'],
            solver_manifest_sha256=self.assets['solver_manifest_sha256'], evaluator_manifest_sha256=self.assets['evaluator_manifest_sha256'],
            request_path=fixture['request_path'], result_path=fixture['result_path'], owner_proof=fixture['proof'])

    def score(self, fixture, seal):
        return pe.evaluate_sealed(fixture['root'] / 'seal', seal['sha256'], solver_root=self.assets['solver_root'],
            evaluator_root=self.assets['evaluator_root'], output_root=fixture['root'] / 'score', deadline=time.monotonic() + 60)

    def test_complete_synthetic_120_167_stopped_owner_real_cpu_scorer(self):
        fixture = self.fixture(); seal = self.seal(fixture); result = self.score(fixture, seal)
        self.assertEqual(result['status'], 'PUBLIC_EVALUATION_COMPLETE', result)
        self.assertEqual(result['development_metrics']['metrics']['pass_at_1']['numerator'], 167)
        self.assertEqual(result['development_metrics']['metrics']['pass_at_2']['denominator'], 167)
        self.assertEqual(result['development_metrics']['metrics']['tasks_all_tests_pass_at_2']['numerator'], 120)
        self.assertFalse(result['goal_met']); self.assertFalse(result['eligible_complete_production_public_measurement'])
        self.assertIsNone(result['official_score'])

    def test_partial_retains_full_denominator_and_cannot_claim_goal(self):
        fixture = self.fixture(omit_last=True); result = self.score(fixture, self.seal(fixture))
        self.assertEqual(result['status'], 'PUBLIC_EVALUATION_PARTIAL', result)
        metric = result['development_metrics']['metrics']['pass_at_2']
        self.assertEqual((metric['numerator'], metric['denominator']), (166, 167))
        self.assertFalse(result['goal_met'])

    def test_shuffled_test_answers_fail(self):
        with self.assertRaisesRegex(ValueError, 'top-two answers differ'): self.seal(self.fixture(shuffle=True))

    def test_extra_answer_rejected(self):
        with self.assertRaisesRegex(ValueError, 'top-two answer schema'): self.seal(self.fixture(extra_answer=True))

    def test_boolean_grid_rejected(self):
        with self.assertRaises(ValueError): self.seal(self.fixture(bad_grid=True))

    def test_omitted_test_slot_rejected(self):
        fixture = self.fixture(); artifact = fixture['artifact']; artifact['predictions']['00000000'].pop()
        events, _ = pe._ledger((fixture['owner'] / 'physical-work.jsonl').read_bytes())
        with self.assertRaisesRegex(ValueError, 'omitted or extra test'):
            pe.make_pool(self.challenges, artifact, read=lambda p: Path(p).read_bytes(), events=events,
                         run_id='fixture', elapsed_seconds=1, tiny=True)

    def test_live_owner_proof_rejected(self):
        fixture = self.fixture(); current = _identity(_read_process(__import__('os').getpid()))
        fixture['proof']['owned_identities'].append(current)
        with self.assertRaisesRegex(ValueError, 'still present'): self.seal(fixture)

    def test_wrong_source_rejected_before_gold_open(self):
        fixture = self.fixture(); seal = self.seal(fixture)
        reads = []; original = pe.read_regular
        def track(path, *args, **kwargs):
            reads.append(str(path)); return original(path, *args, **kwargs)
        request = {'prediction_root': str(fixture['root'] / 'seal'), 'seal_sha256': seal['sha256'],
                   'solver_root': self.assets['solver_root'], 'evaluator_root': self.assets['evaluator_root'],
                   'output_root': str(fixture['root'] / 'score')}
        with patch.object(pe, 'source_identity', return_value={}), patch.object(pe, 'read_regular', side_effect=track):
            with self.assertRaisesRegex(ValueError, 'executable source'): pe._score_after_seal(request)
        self.assertFalse(any(p.startswith(self.assets['evaluator_root']) for p in reads))

    def test_tampered_prediction_seal_rejected_before_gold_open(self):
        fixture = self.fixture(); seal = self.seal(fixture)
        path = fixture['root'] / 'seal' / 'pool.json'; path.write_text('{}')
        with self.assertRaises(ValueError): self.score(fixture, seal)
        self.assertFalse((fixture['root'] / 'score').exists())

    def test_failed_owner_never_promoted_by_provider_complete(self):
        fixture = self.fixture(); fixture['proof']['worker_returncode'] = 2
        fixture['result']['provider_status'] = 'COMPLETE'
        fixture['result_path'].write_bytes(canonical(fixture['result']) + b'\n')
        with self.assertRaisesRegex(ValueError, 'failed or forced'): self.seal(fixture)

    def test_frozen_base_role_requires_native_disabled_adapter_mode(self):
        fixture = self.fixture(); artifact = fixture['artifact']
        artifact['method'].update(candidate_id='base', role='frozen_base')
        for case in artifact['case_receipts']:
            for compact in case['generations']:
                path = Path(compact['receipt_path']); receipt = json.loads(path.read_bytes())
                receipt['adapter_execution_mode'] = 'base'
                path.write_bytes(canonical(receipt) + b'\n'); compact['receipt_sha256'] = sha256(path.read_bytes())
        events, _ = pe._ledger((fixture['owner'] / 'physical-work.jsonl').read_bytes())
        _, coverage = pe.make_pool(self.challenges, artifact, read=lambda p: Path(p).read_bytes(), events=events,
                                  run_id='fixture-base', elapsed_seconds=1, tiny=True)
        self.assertTrue(coverage['complete_coverage'])
        artifact['method']['role'] = 'global_sft'
        with self.assertRaisesRegex(ValueError, 'role differs'):
            pe.make_pool(self.challenges, artifact, read=lambda p: Path(p).read_bytes(), events=events,
                         run_id='fixture-base', elapsed_seconds=1, tiny=True)

    def test_full_90_percent_goal_is_151_and_production_only(self):
        metrics = {'tasks': 120, 'tests': 167, 'metrics': {'pass_at_2': {'numerator': 150, 'denominator': 167}}}
        self.assertFalse(pe.goal_met(True, metrics))
        metrics['metrics']['pass_at_2']['numerator'] = 151
        self.assertTrue(pe.goal_met(True, metrics))
        self.assertFalse(pe.goal_met(False, metrics))
        metrics['metrics']['pass_at_2']['denominator'] = 166
        self.assertFalse(pe.goal_met(True, metrics))

    def test_native_receipt_cannot_be_shuffled_between_queries(self):
        fixture = self.fixture(); artifact = fixture['artifact']
        first, second = artifact['case_receipts'][:2]
        first['generations'], second['generations'] = second['generations'], first['generations']
        events, _ = pe._ledger((fixture['owner'] / 'physical-work.jsonl').read_bytes())
        with self.assertRaisesRegex(ValueError, 'query packing'):
            pe.make_pool(self.challenges, artifact, read=lambda p: Path(p).read_bytes(), events=events,
                         run_id='fixture', elapsed_seconds=1, tiny=True)

    def test_extra_evaluator_answer_rejected(self):
        fixture = self.fixture(); seal = self.seal(fixture)
        original = load_pinned_reference
        def extra(*args):
            challenges, solutions, reference = original(*args)
            solutions['00000000'].append([[0]])
            return challenges, solutions, reference
        request = {'prediction_root': str(fixture['root'] / 'seal'), 'seal_sha256': seal['sha256'],
                   'solver_root': self.assets['solver_root'], 'evaluator_root': self.assets['evaluator_root'],
                   'output_root': str(fixture['root'] / 'score')}
        with patch('tools.arc_offline_evaluation.load_pinned_reference', side_effect=extra):
            with self.assertRaisesRegex(ValueError, 'answer query denominator'): pe._score_after_seal(request)

    def test_fresh_seal_directory_under_real_owner_layout(self):
        fixture = self.fixture()
        seal = pe.seal_predictions(fixture['owner'] / 'public-prediction-seal', solver_root=self.assets['solver_root'],
            solver_manifest_sha256=self.assets['solver_manifest_sha256'], evaluator_manifest_sha256=self.assets['evaluator_manifest_sha256'],
            request_path=fixture['request_path'], result_path=fixture['result_path'], owner_proof=fixture['proof'])
        self.assertTrue(Path(seal['path']).is_file())

    def test_real_run_public_artifact_to_stopped_seal_and_cpu_scorer(self):
        from types import SimpleNamespace
        from tools.arc_qwen_transfer_20261012.experiment import run_public
        fixture = self.fixture(); owner = fixture['owner']
        # Fresh explicit fake-native seam drives the real run_public implementation.
        # It uses no test gold: every completion is the constant grid zero.
        ledger_path = owner / 'physical-work.jsonl'
        ledger_path.unlink()
        ledger = WorkLedger(ledger_path)
        class NativeFixture:
            def __init__(self): self.tokenizer = self; self.count = 0
            def apply_chat_template(self, messages, **kwargs):
                return ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n' for m in messages) + '<|im_start|>assistant\n<think>\n\n</think>\n\n'
            def encode(self, text, **kwargs): return [ord(c) for c in text]
            def _prompt(self, messages):
                text = self.apply_chat_template(messages); return text, self.encode(text)
            def generate(self, messages, **kwargs):
                prompt, prompt_ids = self._prompt(messages); self.count += 1
                event = 'runtime-fixture-' + str(self.count)
                amounts = {'generation_calls': 1, 'input_tokens': len(prompt_ids) + 1, 'output_tokens': 2}
                ledger.reserve(event, amounts); ledger.complete(event, amounts)
                return {'physical_event_id': event, 'text': '0', 'output_token_ids': [48, 151645],
                        'output_sha256': native_hash([48, 151645]), 'native_eos_ids': [151645],
                        'adapter_fingerprint': 'd' * 64, 'adapter_state_sha256': 'b' * 64, 'adapter_execution_mode': 'trained',
                        'dispatched': True, 'model_forward_started': True, 'forward_input_tokens': len(prompt_ids) + 1,
                        'input_tokens': len(prompt_ids), 'output_tokens': 2, 'tiny_cpu': True, 'valid': True,
                        'finish_reason': 'eos', 'rendered_prompt_sha256': sha256(prompt.encode())}
        session = SimpleNamespace(model=NativeFixture(), ledger=ledger)
        checkpoint = {'manifest_sha256': 'a' * 64, 'adapter_sha256': 'b' * 64}
        selection = {'candidate_id': 'sft2', 'selection_sha256': 'c' * 64}
        write_new(owner / 'experiment' / 'public-selection.json', selection)
        with patch('tools.arc_qwen_transfer_20261012.experiment.forecast', return_value={}), \
             patch('tools.arc_qwen_transfer_20261012.experiment.admission', return_value={'admitted': True}):
            branch = run_public(session, fixture['request']['config'], selection, checkpoint, owner / 'experiment' / 'public',
                time.monotonic() + 30, {}, records=[], provenance={}, return_checkpoint=checkpoint)
        fixture['result'].update(public_branch=branch, physical_usage=ledger.used)
        fixture['result_path'].write_bytes(canonical(fixture['result']) + b'\n')
        summary = self.score(fixture, self.seal(fixture))
        self.assertEqual(summary['status'], 'PUBLIC_EVALUATION_COMPLETE', summary)
        self.assertEqual(summary['generation_calls'], 334)
        self.assertEqual(summary['observed_queries'], 167)
        self.assertEqual(summary['development_metrics']['metrics']['pass_at_2']['denominator'], 167)
        self.assertFalse(summary['goal_met'])

    def test_production_runtime_schema_normalizes_only_decoder_identity(self):
        # Schema seam only: this cannot score production assets or establish GPU execution.
        identity = {'model_key': 'qwen3-14b', 'model_id': 'Qwen/Qwen3-14B',
                    'revision': '40c069824f4251a91eefaf281ebe4c544efd3e18',
                    'profile_id': 'qwen3-14b-native-bf16-r8-c4096-transfer-v1',
                    'execution_mode': 'native-qwen3-pretrained-c4096-transfer',
                    'pretrained_weights_loaded': True, 'random_test_weights': False,
                    'full_vocabulary_rows': 151936, 'base_precision': 'bfloat16',
                    'all_eight_weight_sha256_verified': True, 'verified_tensor_count': 443,
                    'verified_tensor_elements': 14768307200, 'context_limit': 4096,
                    'prompt_cap': 3072, 'output_cap': 1024, 'environment': {'fixture_schema_only': True}}
        checkpoint = {'format': 'irisx/qwen-branch-safe-checkpoint-v1', 'update': 64, 'adapter_sha256': 'b' * 64,
                      'binding': {'precision': 'bf16-base-fp32-lora', 'rank': 8, 'alpha': 16,
                                  'source': {'fixture.py': 'c' * 64}, 'config': {'objective_cycle': ['grid']}}}
        cp_raw = canonical(checkpoint) + b'\n'; cp_sha = sha256(cp_raw)
        method = {'candidate_id': 'sft64', 'role': 'global_sft', 'checkpoint_manifest_sha256': cp_sha, 'adapter_sha256': 'b' * 64}
        main = {'candidate_id': 'sft64', 'selection_uses_holdout_targets': False,
                'rankings': [{'candidate_id': key, 'update': update, 'exact': score, 'shape': score, 'valid': score, 'denominator': 16}
                             for key, update, score in [('sft64', 64, 3), ('sft256', 256, 2), ('base', 0, 1)]],
                'checkpoint': {'manifest_sha256': cp_sha, 'adapter_sha256': 'b' * 64}}
        main['selection_sha256'] = pe.digest(main)
        docs = {'checkpoint': cp_raw, 'main': canonical(main) + b'\n'}
        def ref(name, value=None):
            if value is not None: docs[name] = canonical(value) + b'\n'
            return {'path': name, 'sha256': sha256(docs[name])}
        evidence = {'checkpoint_manifest': ref('checkpoint'),
                    'model_admission': ref('admission', {'identity': identity, 'hardware': {'visible_device_count': 1, 'bf16_supported': True, 'fp8_admitted': False, 'four_l4_tp_admitted': False}}),
                    'calibration': ref('calibration', {'status': 'complete', 'completed_lengths': [128, 512, 2048, 4096],
                        'full_context_measured': True, 'cpu_fixture_only': False, 'full_state_restoration_verified': True}),
                    'frozen_selection': ref('selection', {'method': method, 'query_targets_used': False,
                        'selected_before_public_queries': True, 'selection_sha256': main['selection_sha256'], 'main_selection': ref('main')})}
        result = {'model_identity': {**identity, 'decoder_policy': {}, 'decoder_policy_sha256': 'd' * 64},
                  'production_model': True, 'runtime_evidence': evidence, '_source_identity': {'fixture.py': 'c' * 64}}
        self.assertTrue(pe._runtime(result, {'method': method}, docs.__getitem__, tiny=False))
        result['model_identity']['output_cap'] = 256
        with self.assertRaisesRegex(ValueError, 'identity differs'): pe._runtime(result, {'method': method}, docs.__getitem__, tiny=False)

    def test_evaluator_root_in_child_config_forbidden(self):
        with self.assertRaisesRegex(ValueError, 'configuration forbidden'):
            pe._no_evaluator_config({'public_evaluator_root': '/tmp/evaluator'})


if __name__ == '__main__': unittest.main()
