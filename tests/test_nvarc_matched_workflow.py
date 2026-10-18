"""Synthetic source admission and actual tiny-engine numerical integration.

No official weights, GPU, provider write or measured2B accuracy is exercised.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from tests.platform_requirements import requires_linux

MISSING = [name for name in ('torch', 'transformers', 'peft', 'pydantic', 'tokenizers', 'safetensors')
           if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_controls import scripted_groups
    from tools.nvarc_posttrain_20261017 import matched_workflow as mw
    from tools.nvarc_posttrain_20261017 import matched_controls as mc
    from tools.arc2_goal_sprint_20261017.data import canonical, digest
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, state_digest
    from tools.nvarc_posttrain_20261017.engine import FatalUpdateError


def task(index):
    return {'train': [{'input': [[0, 1, 2, 3] + [(index >> i) & 1 for i in range(12)] + [4, 4]], 'output': [[2]]},
                      {'input': [[5, 6]], 'output': [[7]]}]}


def corpus(root):
    training = {f't{i:04}': task(i) for i in range(800)}
    development = {f'd{i:04}': task(1000 + i) for i in range(200)}
    public = {f'p{i:04}': {**task(2000 + i), 'test': [{'input': [[9]]}] * (2 if i < 47 else 1)} for i in range(120)}
    source = root / 'training'; source.mkdir()
    files = {}
    for parent, value in {**training, **development}.items():
        # Deliberately unusable test-output fields prove this fixture only
        # admits original demonstrations, never training-file test solutions.
        raw = canonical({**value, 'test': [{'input': [[8]], 'output': 'FORBIDDEN-UNUSED'}]})
        (source / (parent + '.json')).write_bytes(raw)
        files['data/training/' + parent + '.json'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    manifest = {'files': files, 'upstream': {'fixed_splits': {'train': list(training), 'dev': list(development)}}}
    manifest_path = root / 'manifest.json'; manifest_path.write_bytes(canonical(manifest))
    pin = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    split = {'training_manifest_sha256': pin, 'training_tasks': 800, 'dev_tasks': 200,
        'train_ids_digest': digest(sorted(training)), 'dev_ids_digest': digest(sorted(development)),
        'public_digest': digest(public), 'training_test_fields_used': False, 'excluded_task_ids': []}
    kwargs = {'training_root': source, 'training_manifest_path': manifest_path, 'expected_training_manifest_sha256': pin}
    return training, development, public, split, kwargs


@unittest.skipIf(bool(MISSING), 'Optional compact dependencies missing: ' + ', '.join(MISSING))
class MatchedWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory()
        cls.args = corpus(Path(cls.temp.name))
        cls.prepared = mw.prepare_panels(*cls.args[:4], **cls.args[4])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def cfg(self):
        return {**mc.DEFAULT_CONFIG, 'context_tokens': 96, 'generation_tokens': 2, 'max_groups': 1,
                'target_mixed_groups': 1, 'microbatch': 8, 'learning_rate': 1e-3}

    def run_flow(self, root, engine=None, **kwargs):
        now = time.time()
        options = {'deadline':now+120, 'screen_deadline':now+90, **kwargs}
        from tools.nvarc_posttrain_20261017.precision_contract import LEGACY_POLICY
        engine = engine or tiny_engine()
        prepared = self.prepared if engine.probability_policy == LEGACY_POLICY else mw.prepare_panels(
            *self.args[:4], **self.args[4], probability_policy=engine.probability_policy)
        return mw.run_workflow(engine, copy.deepcopy(prepared), output=root, audit=Mock(),
            source_identity='a' * 64, job_id='2b-S', config=self.cfg(), **options)


    def test_pure_controller_contracts_equal_real_engine_admission(self):
        from tools.nvarc_posttrain_20261017 import matched_controller as controller
        from tools.nvarc_posttrain_20261017.engine import model_contract, validate_tokenizer
        from tests.test_nvarc_posttrain_engine import tokenizer_fixture
        expected=controller._official_model_contract()
        actual=model_contract({**expected,'architectures':['Qwen3ForCausalLM'],
            'use_sliding_window':False,'sliding_window':None},variant='2b')
        self.assertEqual(actual,expected)
        self.assertEqual(validate_tokenizer(tokenizer_fixture()),controller._official_tokenizer_admission())

    def test_actual_source_bytes_and_fixed_panels_are_independent(self):
        prepared = self.prepared
        protocol = prepared['protocol']
        self.assertEqual(len(prepared['training']), 16); self.assertEqual(len(prepared['development']), 16)
        self.assertEqual(len(protocol['excluded_previous_panel']), 24)
        self.assertEqual(len(protocol['excluded_stability_panel']), 32)
        self.assertFalse(set(protocol['development_parent_ids']) & set(protocol['excluded_previous_panel'] + protocol['excluded_stability_panel']))
        self.assertFalse(set(protocol['development_variant_groups'].values()) & set(protocol['excluded_development_variant_groups']))
        self.assertFalse(prepared['source_binding']['family_lineage']['true_generator_lineage_available'])
        self.assertTrue(all(set(t) == {'train'} for t in prepared['training'].values()))
        again = mw.prepare_panels(*(dict(reversed(list(value.items()))) if i < 3 else value
                                  for i, value in enumerate(self.args[:4])), **self.args[4])
        self.assertEqual(prepared, again)

    def test_source_substitution_and_public_answers_fail_before_model_work(self):
        train, dev, public, split = copy.deepcopy(self.args[:4])
        train[next(iter(train))]['train'][0]['output'] = [[9]]
        with self.assertRaisesRegex(ValueError, 'mapping differs'):
            mw.prepare_panels(train, dev, public, split, **self.args[4])
        public[next(iter(public))]['test'][0]['output'] = [[1]]
        split['public_digest'] = digest(public)
        with self.assertRaisesRegex(ValueError, 'answer-free'):
            mw.prepare_panels(self.args[0], dev, public, split, **self.args[4])

    def test_panel_pin_mutation_is_rejected_before_collection(self):
        altered = copy.deepcopy(self.prepared); altered['protocol']['development_parent_ids'].reverse()
        with tempfile.TemporaryDirectory() as temp, patch.object(mc, 'run_matched_controls') as collect:
            with self.assertRaisesRegex(ValueError, 'pinned panel'):
                mw.run_workflow(tiny_engine(), altered, output=temp, audit=Mock(), deadline=time.time()+60,
                    screen_deadline=time.time()+30, source_identity='a'*64, job_id='2b-S', config=self.cfg())
            collect.assert_not_called()

    def test_actual_tiny_generation_updates_exports_and_full_denominator(self):
        engine = tiny_engine(); before = mc.full_policy_sha256(engine)
        with tempfile.TemporaryDirectory() as temp, patch('torch.multinomial', side_effect=scripted_groups([[1, 0]*4]*2)):
            root = Path(temp)
            report = self.run_flow(root, engine)
            self.assertTrue(report['complete']); self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['full_requested_denominator'], 16)
            self.assertTrue(report['anchor_restored']); self.assertFalse(report['engine_poisoned'])
            self.assertEqual(mc.full_policy_sha256(engine), before)
            self.assertTrue(report['ddis_signal_evidence'])
            self.assertEqual(report['physical']['optimizer_steps'], 3)
            self.assertEqual(report['controls']['collection']['categories'], {'mixed': 1})
            self.assertEqual(report['controls']['collection']['distinct_mixed_parents'], 1)
            self.assertNotIn('groups', report['controls']['capture'])
            full = json.loads((root/'matched-controls.json').read_bytes())
            self.assertEqual(len(full['capture']['groups']), 1); self.assertNotIn('states', full)
            self.assertEqual(json.loads((root/'matched-report.json').read_bytes()), report)
            self.assertLess((root/'matched-report.json').stat().st_size, 4*1024**2)
            for arm in mc.ARMS:
                rows = report['evaluation']['arms'][arm]
                self.assertTrue(rows['complete']); self.assertEqual(rows['complete_parents'], 16)
                self.assertEqual(rows['pass2'], sum(r['pass2'] for r in rows['records']))
                saved = report['exports'][arm]['checkpoint']
                self.assertEqual(report['exports'][arm]['status'], 'complete')
                clone = tiny_engine(); clone.load_checkpoint({'root': saved['root'], 'manifest_sha256': saved['manifest_sha256']})
                self.assertEqual(state_digest(adapter_state(clone.model)), saved['state_sha256'])
                for record in rows['records']:
                    self.assertEqual(record['completed_views'], 2); self.assertTrue(record['verification']['verified'])
                    self.assertEqual(record['anchor_reset_sha256'], report['anchor_state_sha256'])
                    path = root/record['prediction_artifact']['path']
                    prediction = json.loads(path.read_bytes())
                    parent = record['parent_id']; task = self.prepared['development'][parent]
                    mw.verify_prediction(prediction, {'train': task['train'][1:]}, task['train'][0]['input'],
                        {'context_tokens':96,'generation_tokens':2,'evaluation_seed':mw.EVALUATION_SEED}, task_id=parent, views=2)
                    self.assertNotIn('prediction', record)
            self.assertFalse(report['public_inference_performed']); self.assertFalse(report['clean_generalization_claimed'])

    def test_no_mixed_groups_remains_explicit_ddis_non_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch('torch.multinomial', side_effect=scripted_groups([[0]*8]*2)):
            report = self.run_flow(temp)
        self.assertTrue(report['complete']); self.assertFalse(report['ddis_signal_evidence'])
        self.assertEqual(report['ddis_signal_status'], 'no_usable_mixed_update_non_evidence')
        self.assertFalse(report['controls']['arms']['exact_centered_ddis']['updated'])
        self.assertEqual(report['exports']['anchor']['state_sha256'], report['exports']['exact_centered_ddis']['state_sha256'])
        self.assertNotEqual(report['selected_arm'], 'exact_centered_ddis')

    def test_real_preflight_repeats_first_seeded_batch_without_using_it_for_loss(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.run_flow(temp)
            root = Path(temp)
            evidence = json.loads((root/'matched-probability-preflight.json').read_bytes())
            full = json.loads((root/'matched-controls.json').read_bytes())
        self.assertTrue(evidence['passed'])
        self.assertFalse(evidence['used_for_loss'])
        self.assertTrue(evidence['full_pool_verification_still_required'])
        self.assertEqual(evidence['policy_before_sha256'], evidence['policy_after_sha256'])
        self.assertEqual(evidence['parent_id'], full['capture']['groups'][0]['parent_id'])
        for probed, captured in zip(evidence['probe']['rows'], full['capture']['groups'][0]['rows']):
            self.assertEqual(probed['input_ids'], captured['input_ids'])
            self.assertEqual(probed['behavior_log_probs'], captured['behavior_log_probs'])
        self.assertEqual(full['collection']['trajectories_retained'], 8)
        self.assertEqual(evidence['physical']['optimizer_attempts'], 0)
        for key in report['physical']:
            self.assertEqual(report['physical'][key], evidence['physical'][key] + full['physical'][key]
                + sum(arm['physical'][key] for arm in report['evaluation']['arms'].values()))

    def test_stable_grad_forward_failure_is_retained_before_collection(self):
        from tools.nvarc_posttrain_20261017 import probability_probe as pp
        from tools.nvarc_posttrain_20261017.precision_contract import FP32_HEAD_POLICY
        engine = tiny_engine(dtype=torch.bfloat16, probability_policy=FP32_HEAD_POLICY)
        original = pp._additional_full
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs['mode'] == 'train_grad' and result['status'] == 'completed':
                result['rows'][0]['full_log_probs'][0] += .1
                behavior = [v for row in result['rows'] for v in row['behavior_log_probs']]
                replay = [v for row in result['rows'] for v in row['full_log_probs']]
                result['metrics'] = pp._metrics(behavior, replay)
            return result
        with tempfile.TemporaryDirectory() as temp, patch.object(pp, '_additional_full', side_effect=changed), \
                patch.object(mc, 'run_matched_controls') as collection:
            with self.assertRaisesRegex(ValueError, 'probability preflight failed'):
                self.run_flow(temp, engine)
            evidence = json.loads((Path(temp)/'matched-probability-preflight.json').read_bytes())
            report = json.loads((Path(temp)/'matched-report.json').read_bytes())
        collection.assert_not_called()
        self.assertFalse(evidence['passed'])
        self.assertEqual(evidence['tolerance'], .05)
        self.assertGreater(evidence['metrics']['additional_paths']['train_grad']['max_abs_logp_gap'], .05)
        self.assertEqual(engine.optimizer_steps, 0)
        self.assertIsNone(report['controls'])
        self.assertTrue(report['anchor_restored'])

    def test_failed_preflight_persists_measured_drift_before_any_pool_or_update(self):
        engine = tiny_engine(); original = engine.completion_logps
        def mismatch(ids, prompt_length):
            values = original(ids, prompt_length).clone(); values[prompt_length] += 0.25
            return values
        with tempfile.TemporaryDirectory() as temp, patch.object(engine, 'completion_logps', side_effect=mismatch), \
                patch.object(mc, 'run_matched_controls') as collect:
            with self.assertRaisesRegex(ValueError, 'probability preflight failed'):
                self.run_flow(temp, engine)
            collect.assert_not_called()
            root = Path(temp)
            report = json.loads((root/'matched-report.json').read_bytes())
            evidence = json.loads((root/'matched-probability-preflight.json').read_bytes())
            self.assertFalse((root/'matched-controls.json').exists())
            self.assertFalse((root/'checkpoints').exists())
        self.assertIsNone(report['controls'])
        self.assertFalse(report['complete']); self.assertFalse(evidence['passed'])
        self.assertAlmostEqual(evidence['metrics']['full_max_abs_logp_gap'], 0.25, places=5)
        self.assertLess(evidence['metrics']['cached_max_abs_logp_gap'], 1e-5)
        self.assertEqual(report['physical']['optimizer_attempts'], 0)
        self.assertTrue(report['anchor_restored'])
        self.assertTrue(all(r['status'] == 'not_executed' for arm in report['evaluation']['arms'].values()
                            for r in arm['records']))

    def test_preflight_deadline_preserves_unknown_measurements_and_all_denominators(self):
        from tools.nvarc_posttrain_20261017 import probability_probe as pp
        with tempfile.TemporaryDirectory() as temp, patch.object(pp, 'check_deadline', side_effect=PhaseDeadline('fixture')), \
                patch.object(mc, 'run_matched_controls') as collect:
            report = self.run_flow(temp)
            collect.assert_not_called()
            evidence = json.loads((Path(temp)/'matched-probability-preflight.json').read_bytes())
        self.assertEqual(report['status'], 'partial'); self.assertFalse(report['complete'])
        self.assertEqual(evidence['status'], 'deadline'); self.assertFalse(evidence['passed'])
        self.assertIsNone(evidence['metrics']['full_max_abs_logp_gap'])
        self.assertIsNone(evidence['metrics']['cached_max_abs_logp_gap'])
        self.assertEqual([len(a['records']) for a in report['evaluation']['arms'].values()], [16]*4)

    def test_collection_deadline_retains_all_denominators_and_available_anchor(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(mc, 'check_deadline', side_effect=PhaseDeadline('fixture')):
            report = self.run_flow(temp)
        self.assertFalse(report['complete']); self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['controls']['status'], 'deadline')
        self.assertTrue(report['evaluation']['arms']['anchor']['complete'])
        self.assertEqual(report['selected_arm'], 'anchor'); self.assertFalse(report['candidate_selected'])
        self.assertEqual([len(a['records']) for a in report['evaluation']['arms'].values()], [16]*4)

    def test_partial_generated_views_cannot_select_candidate(self):
        original = mw.infer_query
        calls = []
        def partial(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                return {'ranked_grids': [], 'candidates': [], 'ranked_candidate_indices': [], 'views': [],
                        'ranking':'votes-descending-mean-own-view-nll-tie-v1', 'complete':False}
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as temp, patch.object(mw, 'infer_query', side_effect=partial):
            report = self.run_flow(temp)
        self.assertFalse(report['complete']); self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['evaluation']['arms']['anchor']['complete_parents'], 1)
        self.assertEqual(report['full_requested_denominator'], 16); self.assertFalse(report['candidate_selected'])

    def test_numerical_failure_preserves_receipt_and_poison_without_more_exports(self):
        engine = tiny_engine()
        def fail(*args, **kwargs):
            engine._fatal_update = True
            raise FatalUpdateError('synthetic poison')
        with tempfile.TemporaryDirectory() as temp, patch.object(engine, 'generate', side_effect=fail):
            with self.assertRaises(FatalUpdateError): self.run_flow(temp, engine)
            report = json.loads((Path(temp)/'matched-report.json').read_bytes())
            self.assertEqual(report['status'], 'failed'); self.assertTrue(report['engine_poisoned'])
            self.assertFalse(report['complete']); self.assertFalse(report['candidate_selected'])
            self.assertTrue((Path(temp)/'matched-probability-preflight.json').is_file())
            self.assertFalse((Path(temp)/'matched-controls.json').exists())
            self.assertFalse((Path(temp)/'checkpoints').exists())
        self.assertTrue(engine._fatal_update)

    def test_export_failure_is_not_callable_success(self):
        engine = tiny_engine()
        with tempfile.TemporaryDirectory() as temp, patch.object(engine, 'save_checkpoint', side_effect=OSError('disk fixture')):
            with self.assertRaises(OSError): self.run_flow(temp, engine)
            report = json.loads((Path(temp)/'matched-report.json').read_bytes())
        self.assertEqual(report['exports']['anchor']['status'], 'failed')
        self.assertFalse(report['complete']); self.assertTrue(report['anchor_restored'])
        self.assertEqual(report['physical']['optimizer_attempts'], engine.optimizer_attempts)

    def test_storage_admission_fails_before_collection(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(mw.shutil, 'disk_usage', return_value=Mock(free=0)), \
                patch.object(mc, 'run_matched_controls') as collect:
            with self.assertRaisesRegex(ValueError, 'disk reserve'): self.run_flow(temp)
            collect.assert_not_called()

    def test_all64_groups_and512_trajectories_reach_real_export_and_generation(self):
        cfg = {**self.cfg(), 'max_groups':64, 'target_mixed_groups':8}
        with tempfile.TemporaryDirectory() as temp, patch('torch.multinomial', side_effect=scripted_groups([[0]*8]*65)), \
                patch.object(self,'cfg',return_value=cfg):
            report = self.run_flow(temp)
            full = json.loads((Path(temp)/'matched-controls.json').read_bytes())
        self.assertTrue(report['complete']); self.assertEqual(len(full['capture']['groups']),64)
        self.assertEqual(report['controls']['collection']['trajectories_retained'],512)
        self.assertEqual(report['controls']['collection']['categories'],{'all_wrong':64})
        self.assertFalse(report['ddis_signal_evidence'])
        self.assertEqual(report['evaluation']['arms']['exact_centered_ddis']['complete_parents'],16)

    def test_final_sync_failure_denies_success_despite_finished_exports_and_predictions(self):
        engine = tiny_engine(); sync = engine.sync
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def failed_final_sync():
                if len(list((root/'predictions').glob('*/*.json'))) == 64:
                    raise RuntimeError('synthetic final synchronization failure')
                return sync()
            with patch.object(engine,'sync',side_effect=failed_final_sync):
                with self.assertRaisesRegex(RuntimeError,'synchronization'):
                    self.run_flow(temp,engine)
            report=json.loads((root/'matched-report.json').read_bytes())
        self.assertEqual(report['status'],'failed');self.assertFalse(report['complete'])
        self.assertTrue(report['engine_poisoned']);self.assertFalse(report['candidate_selected'])
        self.assertEqual(report['selection_label'],'retain-anchor')
        self.assertTrue(report['evaluation']['complete'])
        self.assertTrue(all(e['status']=='complete' for e in report['exports'].values()))
        self.assertGreater(report['physical']['model_forward_attempts'],0)

    def test_only_final_sync_crossing_deadline_preserves_work_but_denies_selection(self):
        engine=tiny_engine();sync=engine.sync;real_time=time.time;offset=[0.]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def late_sync():
                sync()
                if len(list((root/'predictions').glob('*/*.json'))) == 64:
                    offset[0]=200.
            with patch.object(engine,'sync',side_effect=late_sync), \
                    patch.object(mw.time,'time',side_effect=lambda:real_time()+offset[0]):
                report=self.run_flow(temp,engine)
            self.assertEqual(json.loads((root/'matched-report.json').read_bytes()),report)
        self.assertFalse(report['complete']);self.assertEqual(report['status'],'partial')
        self.assertTrue(report['returned_after_evaluation_deadline'])
        self.assertEqual(report['stop_reason'],'deadline_during_final_synchronous_cleanup')
        self.assertTrue(report['evaluation']['complete']);self.assertTrue(report['anchor_restored'])
        self.assertFalse(report['engine_poisoned']);self.assertFalse(report['candidate_selected'])
        self.assertEqual(report['selection_label'],'retain-anchor')
        self.assertTrue(all(e['status']=='complete' for e in report['exports'].values()))
        self.assertGreater(report['report_persistence']['completed_writes_before_this'],0)

    @requires_linux('Complete closure roundtrip imports the Linux owned-process proof contract')
    def test_real_safe_exports_and_raw_receipts_pass_persisted_controller_and_closure(self):
        # Only admission dimensions/manifest pin and external process liveness
        # are synthetic. Every control, generated prediction, safe tensor byte,
        # content hash, record denominator and closure inventory remains real.
        from tools.nvarc_posttrain_20261017 import matched_controller as controller
        from tests.test_nvarc_matched_controller import closure, persist_result, save, artifact
        from tools.nvarc_posttrain_20261017.precision_contract import FP32_HEAD_POLICY
        engine=tiny_engine(rank=64,dtype=torch.bfloat16,probability_policy=FP32_HEAD_POLICY)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);output=root/'solver';worker=output/'matched-2b'/'2b-S';worker.mkdir(parents=True)
            start=time.time()-1
            cfg={'output_root':str(output),'source_identity':'a'*64,'run_id':'synthetic-matched',
                 'started_epoch':start,'deadline_epoch':start+43200}
            plan=controller.phase_plan(cfg,time.time())
            report=self.run_flow(worker,engine,deadline=plan['worker_deadline_epoch'],screen_deadline=plan['screen_deadline_epoch'])
            result={'mode':'matched','job_id':'2b-S','source_identity':'a'*64,'workload_identity':mw.PROTOCOL,
                'device_identity':'synthetic-device','model_identity':engine.base_identity,'completed':report['complete'],
                'matched':report}
            persist_result(worker,result)
            proof=closure();row={'job_id':'2b-S','status':'completed','closure_verified':True,'closure':proof,'result':result}
            wave={'jobs':[row],'completed':True,'wall_seconds':report['wall_seconds']}
            summary={'format':'irisx/nvarc-matched-controller-v1','run_id':'synthetic-matched','source_identity':'a'*64,
                'workflow':mw.PROTOCOL,'workload_identity':mw.PROTOCOL,'requested_models':['2b'],
                'requested_parents_per_arm':16,'arms':list(mc.ARMS),'matched_views':2,'completed':True,
                'public_inference_performed':False,'public_scoring_performed':False,'workers':[row],'phase_plan':plan,
                'architecture_expansion_tested':False,'automatic_following_run':False,
                'training_or_ensemble_selected_for_public':False,'clean_generalization_claimed':False,
                'public_score':None,'official_score':None}
            save(output/'matched-2b-wave.json',wave);save(output/'run-summary.json',summary);save(output/'phase-plan.json',plan)
            save(output/'topology.json',{'measured':True,'device_count':1,'device_identity':'synthetic-device',
                'hardware_partition_claimed':False,'total_bytes':24*1024**3,'free_bytes':22*1024**3})
            control=root/'control';control.mkdir();save(control/'owner-closure.json',proof)
            with patch.object(controller,'_official_tensor_contract',return_value=engine.trainable_inventory['tensors']), \
                    patch.object(controller,'_official_model_contract',return_value=engine.contract), \
                    patch.object(controller,'_official_preflight_config',return_value={
                        'microbatch':8,'generation_tokens':2,'seed':0,'tolerance':0.05}), \
                    patch.object(controller,'model_bound',return_value=True), \
                    patch.object(controller,'TRAINING_MANIFEST_SHA256',self.args[4]['expected_training_manifest_sha256']), \
                    patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof'):
                self.assertTrue(controller.validate_result(result,worker,source_identity='a'*64,device_identity='synthetic-device'))
                terminal=controller.close_diagnostic(cfg,control,proof)
                self.assertTrue(terminal['completed'])
                self.assertEqual(sum(name.endswith('.safetensors') for name in terminal['files']),4)
                self.assertEqual(sum('/predictions/' in name for name in terminal['files']),64)
                self.assertFalse(terminal['provider_terminal_verified']);self.assertIsNone(terminal['public_score'])
                # Re-seal a modified replay vector but retain its old numeric
                # summary. The independent CPU consumer must recompute the gap.
                probe_path=worker/'matched-probability-preflight.json'
                original_probe=probe_path.read_bytes()
                altered_probe=json.loads(original_probe)
                altered_probe['probe']['full_replay'][0]['full_log_probs'][0] += 0.25
                save(probe_path,altered_probe)
                changed_probe=copy.deepcopy(result)
                changed_probe['matched']['private_artifacts'][probe_path.name]=artifact(probe_path,worker)
                persist_result(worker,changed_probe)
                with self.assertRaisesRegex(ValueError,'gap summary differs|full16 logits do not bind'):
                    controller.validate_result(changed_probe,worker,source_identity='a'*64,device_identity='synthetic-device')
                probe_path.write_bytes(original_probe);persist_result(worker,result)
                # Exact reviewer reproduction: alter a real correct row and its
                # aggregates while leaving prediction, target and all artifacts.
                changed=copy.deepcopy(result)
                scored=changed['matched']['evaluation']['arms']['known_target_ce']
                correct=next(row for row in scored['records'] if row['pass1'] == 1)
                correct.update(pass1=0,pass2=0,valid=False)
                scored['pass1']-=1;scored['pass2']-=1;scored['valid']-=1
                persist_result(worker,changed)
                with self.assertRaisesRegex(ValueError,'generated exact counts'):
                    controller.validate_result(changed,worker,source_identity='a'*64,device_identity='synthetic-device')
                persist_result(worker,result)
                path=worker/'checkpoints'/'known_target_ce'/'trainable_state.safetensors'
                raw=path.read_bytes();path.write_bytes(raw[:-4])
                with self.assertRaises(ValueError):
                    controller.validate_result(result,worker,source_identity='a'*64,device_identity='synthetic-device')

    def test_real_worker_branch_with_mocked_offline_gpu_orchestration_and_tiny_math(self):
        # Hardware, official-model loading and corpus loading are honest mocks;
        # collection, all losses, generation, checkpoints and worker dispatch
        # are real CPU execution. This is not a2B/GPU acceptance receipt.
        from tools.nvarc_posttrain_20261017 import worker
        engine = tiny_engine(); now = time.time()
        actual = mw.run_workflow
        def small(*args, **kwargs):
            return actual(*args, **kwargs, config=self.cfg())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = {'job_id':'2b-S','arm':'S','mode':'matched','variant':'2b','seed':0,'parameters':{},
                'source_identity':'a'*64,'workload_identity':mw.PROTOCOL,'device_identity':'synthetic',
                'model_root':'synthetic-only','output_dir':str(root),'ready_path':str(root/'ready.json'),
                'training_root':str(self.args[4]['training_root']),
                'training_manifest_path':str(self.args[4]['training_manifest_path']),
                'public_path':'synthetic-solver/public-challenges.json',
                'deadline_epoch':now+120,'training_deadline_epoch':now+90}
            with patch.object(worker,'topology',return_value={'device_identity':'synthetic'}), \
                    patch.object(worker,'verify_model',return_value={'synthetic':True}), \
                    patch.object(worker,'verify_inventory'), patch.object(worker,'load_data',return_value=self.args[:4]), \
                    patch.object(worker.CompactEngine,'load',return_value=engine), patch.object(worker,'wait_release'), \
                    patch.object(worker.torch.cuda,'set_per_process_memory_fraction'), \
                    patch.object(worker.torch.cuda,'max_memory_allocated',return_value=0), \
                    patch.object(worker.torch.cuda,'max_memory_reserved',return_value=0), \
                    patch.object(mw,'prepare_panels',return_value=copy.deepcopy(self.prepared)), \
                    patch.object(mw,'run_workflow',side_effect=small), patch.object(worker,'run_public') as public:
                result = worker.run(cfg)
            public.assert_not_called()
            self.assertTrue(result['completed']); self.assertTrue(result['matched']['complete'])
            self.assertEqual(result['matched_report']['sha256'],hashlib.sha256((root/'matched-report.json').read_bytes()).hexdigest())
            self.assertEqual(json.loads((root/'result.json').read_bytes()), result)
            self.assertLess((root/'result.json').stat().st_size,4*1024**2)

    def test_real_convergence_shared_worker_dispatch_preserves_owned_paths(self):
        from tools.nvarc_posttrain_20261017 import worker, convergence_workflow as cw
        from tests.test_nvarc_convergence import configuration
        from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
        engine = tiny_engine(dtype=torch.bfloat16, probability_policy=FP32_BACKBONE_POLICY)
        now = time.time(); actual = cw.run_workflow; actual_prepare = cw.prepare_panels
        def prepare(*args, **kwargs):
            return actual_prepare(*args, **kwargs, expected_training_manifest_sha256=self.args[4]['expected_training_manifest_sha256'])
        def small(*args, **kwargs):
            return actual(*args, **kwargs, config=configuration(),
                          evaluation={**cw.DEFAULT_EVALUATION, 'ttt_steps': 1})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = {'job_id':'2b-S','arm':'S','mode':'convergence','variant':'2b','seed':0,'parameters':{},
                'source_identity':'a'*64,'workload_identity':cw.PROTOCOL,'device_identity':'synthetic',
                'model_root':'synthetic-only','output_dir':str(root),'ready_path':str(root/'ready.json'),
                'training_root':str(self.args[4]['training_root']),
                'training_manifest_path':str(self.args[4]['training_manifest_path']),
                'public_path':'synthetic-solver/public-challenges.json',
                'deadline_epoch':now+180,'training_deadline_epoch':now+120}
            with patch.object(worker,'topology',return_value={'device_identity':'synthetic'}), \
                    patch.object(worker,'verify_model',return_value={'synthetic':True}), \
                    patch.object(worker,'verify_inventory'), patch.object(worker,'load_data',return_value=self.args[:4]), \
                    patch.object(worker.CompactEngine,'load',return_value=engine) as load, patch.object(worker,'wait_release'), \
                    patch.object(worker.torch.cuda,'set_per_process_memory_fraction'), \
                    patch.object(worker.torch.cuda,'max_memory_allocated',return_value=0), \
                    patch.object(worker.torch.cuda,'max_memory_reserved',return_value=0), \
                    patch.object(cw,'prepare_panels',side_effect=prepare), \
                    patch.object(cw,'run_workflow',side_effect=small), patch.object(worker,'run_public') as public:
                result = worker.run(cfg)
            public.assert_not_called()
            self.assertEqual(load.call_args.kwargs['probability_policy'], FP32_BACKBONE_POLICY)
            self.assertTrue(result['completed']); self.assertTrue(result['convergence']['complete'])
            self.assertEqual(result['convergence_report']['path'], 'convergence/report.json')
            self.assertEqual(result['convergence_report']['sha256'],
                             hashlib.sha256((root/'convergence/report.json').read_bytes()).hexdigest())
            self.assertEqual(json.loads((root/'result.json').read_bytes()), result)
            self.assertEqual(len(result['convergence']['exports']), 5)
            self.assertEqual(result['convergence']['evaluation']['anchor']['no_ttt']['full_requested_denominator'], 16)
            self.assertLess((root/'result.json').stat().st_size, 4*1024**2)

    def test_bootstrap_exact2b_mount_preserves_old_dual_and_stability_mounts(self):
        from tools.nvarc_posttrain_20261017 import bootstrap as boot
        from tools.nvarc_posttrain_20261017.materials import model_pin
        for workflow, variants in ((mw.PROTOCOL, ['2b']), ('compact-convergence-screen-v1', ['2b']),
                                   ('paired-ttt-stability-v1',['2b','4b']),
                                   ('dual-posttrain-v1',['2b','4b'])):
            with tempfile.TemporaryDirectory() as temp, self.subTest(workflow=workflow):
                root=Path(temp); now=time.time()-1
                request={'workflow':workflow,'started_epoch':now,'session_deadline_epoch':now+43200,
                    'evaluation_mode':'external-cpu','working_root':str(root/'work'),'runtime_root':str(root/'runtime'),
                    'run_id':'synthetic','solver_dataset':'owner/solver/1','source_dataset':'owner/source/1',
                    'source_manifest_sha256':'a'*64,'input_root':str(root/'input')}
                manifest={'workflow':workflow,'model_sources':[model_pin(v)['model_source'] for v in variants],
                    'transport':{'filename':'source.tar.gz'}}
                mounts=[]
                def model(input_root,variant):
                    mounts.append(variant); return root/variant, {'fixture':variant}
                with patch.object(boot.offline,'remaining'), patch.object(boot,'verify_source',return_value=manifest), \
                        patch.object(boot.offline,'resolve_dataset',side_effect=lambda base,ref:root/ref.split('/')[1]), \
                        patch.object(boot.offline,'solver_projection',return_value=root/'solver'), \
                        patch.object(boot,'verify_inventory'), patch.object(boot.offline,'exact_files'), \
                        patch.object(boot,'check_dataset_separation'), patch.object(boot,'resolve_model',side_effect=model), \
                        patch.object(boot.offline,'install',return_value=('python',{},{})), \
                        patch.object(boot,'protected_launch',side_effect=lambda cfg,*args:cfg):
                    result=boot.bootstrap(request)
                self.assertEqual(mounts,variants);self.assertEqual(set(result['model_roots']),set(variants))
                self.assertEqual(result['workflow'],workflow)


if __name__ == '__main__': unittest.main()
