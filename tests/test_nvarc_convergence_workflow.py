"""Persisted real tiny-Qwen convergence/evaluation; no official/GPU claim."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

MISSING=[n for n in ('torch','transformers','peft','pydantic','tokenizers','safetensors') if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_controls import scripted_groups
    from tests.test_nvarc_matched_workflow import corpus
    from tests.test_nvarc_convergence import configuration
    from tools.nvarc_posttrain_20261017 import convergence as cv, convergence_workflow as cw, matched_controls as mc
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, state_digest


@unittest.skipIf(bool(MISSING),'Optional compact dependencies absent: '+','.join(MISSING))
class ConvergenceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temp=tempfile.TemporaryDirectory(); args=corpus(Path(cls.temp.name))
        cls.prepared=cw.prepare_panels(*args[:4],**args[4])

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def flow(self,root,engine=None,**changes):
        now=time.time()
        return cw.run_workflow(engine or tiny_engine(),copy.deepcopy(self.prepared),
            output=root,source_identity='a'*64,deadline=now+180,training_deadline=now+120,
            config=configuration(),evaluation={**cw.DEFAULT_EVALUATION,'ttt_steps':1},**changes)

    def test_summary_excludes_maximum_shaped_raw_vectors_without_truncating_evidence(self):
        # Repeated references avoid allocating an unnecessary 7M distinct floats;
        # dimensions are the full physical protocol bound, not a tiny fixture.
        vector = [-2.123456789012345] * 8192
        rows = [{'sample_id': 'row', 'replay_log_probs': vector}] * 64
        windows = [{'window_id': str(index), 'capture': {'seal_sha256': 'a'*64,
            'lineage': {'policy_sha256': 'b'*64}}, 'preflight': {'passed': True},
            'verification': {'rows': rows, 'observed_rows': 64, 'verified_rows': 64,
                'max_logp_gap': 0.0, 'failed_row': {'sample_id': 'failed',
                    'max_abs_logp_gap': .1, 'replay_log_probs': vector}}} for index in range(13)]
        result = {'states': {'anchor': {'weight': torch.zeros(1)}}, 'windows': windows}
        summary = cw._json_training(result, {})
        self.assertLess(len(cw.canonical(summary)), 32*1024)
        self.assertNotIn('rows', summary['windows'][0]['verification'])
        self.assertNotIn('replay_log_probs', summary['windows'][0]['verification']['failed_row'])
        self.assertEqual(len(result['windows']), 13)
        self.assertEqual(len(result['windows'][0]['verification']['rows']), 64)
        self.assertEqual(len(result['windows'][0]['verification']['rows'][0]['replay_log_probs']), 8192)
        self.assertEqual(result['windows'][0]['verification']['failed_row']['replay_log_probs'], vector)

    def test_maximum_raw_numeric_shapes_fit_window_artifact_budget(self):
        # Finite float32 values can have long decimal representations even when
        # all probability gaps are zero. This is serialization, not GPU proof.
        value=-1.234567860607578e-35; prompt=7261; completion=931
        row={'input_ids':[15]*8192, 'behavior_log_probs':[0.0]*prompt+[value]*completion,
            'completion_ids':[15]*completion, 'text':'9'*completion}
        head={key:[[[value]*16]]*2 for key in
            ('actual_logits','fp32_same_hidden_logits','legacy_same_hidden_logits')}
        full={key:[[[value]*16]*completion] for key in head}
        raw={'capture':{'groups':[{'prompt_ids':[15]*prompt,'rows':[row]*8}]*8},
            'verification':{'rows':[{'replay_log_probs':[0.0]*prompt+[value]*completion}]*64},
            'preflight':{'probe':{'logit_evidence':[head]*(2*completion)+[full]*6}}}
        size=len(cw.canonical(raw))
        self.assertGreater(size,16*1024**2)
        self.assertLess(size+4*1024**2,cw.WINDOW_EVIDENCE_LIMIT_BYTES)
        self.assertLess(13*cw.WINDOW_EVIDENCE_LIMIT_BYTES,1024**3)

    def test_declared_probability_policy_must_match_engine_before_output(self):
        engine = tiny_engine(probability_policy='fp32-compact-head-v1')
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)/'must-not-exist'
            with self.assertRaisesRegex(ValueError, 'declared numerical policy'):
                self.flow(output, engine)
            self.assertFalse(output.exists())
            self.assertEqual(engine.optimizer_attempts, 0)

    def test_real_five_checkpoints_full_denominators_paired_ttt_and_reload(self):
        engine=tiny_engine(); before=mc.full_policy_sha256(engine)
        original=cw.adapt_task; seen=[]
        def adapt(engine,task,cfg,**kwargs):
            parent=kwargs['task_id']
            self.assertEqual(task,{'train':self.prepared['development'][parent]['train'][1:]})
            seen.append(parent)
            return original(engine,task,cfg,**kwargs)
        with tempfile.TemporaryDirectory() as root, patch('torch.multinomial',side_effect=scripted_groups([[1,0]*4]*26)), \
                patch.object(cw,'adapt_task',side_effect=adapt):
            report=self.flow(root,engine)
            self.assertEqual(report['status'],'complete'); self.assertTrue(report['complete'])
            self.assertTrue(report['anchor_restored']); self.assertFalse(report['public_answers_used'])
            self.assertEqual(report['training']['physical']['optimizer_steps'],16)
            self.assertEqual(report['physical']['optimizer_steps'],96)
            self.assertEqual(len(seen),80)
            self.assertEqual(before,mc.full_policy_sha256(engine))
            self.assertEqual(json.loads((Path(root)/'report.json').read_bytes()),report)
            for arm in cv.ARMS:
                self.assertEqual(report['exports'][arm]['status'],'complete')
                self.assertTrue(report['paired_ttt'][arm]['complete'])
                self.assertEqual(sum(report['paired_ttt'][arm][k] for k in ('wins','losses','ties')),16)
                for name,cell in report['evaluation'][arm].items():
                    self.assertEqual(cell['full_requested_denominator'],16)
                    self.assertEqual(cell['completed_parents'],16)
                    self.assertEqual(len(cell['records']),16)
                    self.assertEqual(cell['pass2'],sum(r['pass2'] for r in cell['records']))
                    for row in cell['records']:
                        self.assertEqual(row['starting_state_sha256'],report['exports'][arm]['checkpoint']['state_sha256'])
                        self.assertEqual(row['reset_state_sha256'],row['starting_state_sha256'])
                        prediction=json.loads((Path(root)/row['prediction_artifact']['path']).read_bytes())
                        self.assertEqual(len(prediction['views']),2)
                        self.assertIn('token_evidence',prediction['views'][0])
                        if name=='ttt':
                            self.assertTrue(row['functional_reset']['verified'])
                            self.assertFalse(row['adaptation']['held_target_used_for_gradient'])
                fresh=tiny_engine(); saved=report['exports'][arm]['checkpoint']
                fresh.load_checkpoint({'root':saved['root'],'manifest_sha256':saved['manifest_sha256']})
                self.assertEqual(state_digest(adapter_state(fresh.model)),saved['state_sha256'])
            for artifact in report['private_artifacts'].values():
                self.assertTrue((Path(root)/artifact['path']).is_file())
            self.assertEqual(len(list((Path(root)/'windows').glob('*.json'))),13)
            protocol=json.loads((Path(root)/'protocol.json').read_bytes())
            self.assertEqual(protocol['requested_view_generations'],320)
            self.assertEqual(protocol['maximum_ttt_optimizer_attempts'],80)
            self.assertIn('noTTT',protocol['selection_rule'])
            self.assertFalse(report['equal_compute_claimed']); self.assertFalse(report['efficacy_claimed'])

    def test_preflight_failure_retains_all_unknown_development_rows_and_evidence(self):
        engine=tiny_engine(); real=engine.completion_logps
        def mismatch(ids,n):
            value=real(ids,n).clone();value[n]+=.25;return value
        with tempfile.TemporaryDirectory() as root,patch.object(engine,'completion_logps',side_effect=mismatch):
            with self.assertRaisesRegex(ValueError,'preflight failed') as caught:
                self.flow(root,engine)
            report=caught.exception.convergence_workflow_result
            self.assertEqual(report['status'],'failed');self.assertTrue(report['anchor_restored'])
            self.assertEqual(report['physical']['optimizer_attempts'],0)
            self.assertFalse(report['candidate_selected'])
            for arm in report['evaluation'].values():
                for cell in arm.values():
                    self.assertIsNone(cell['pass2']);self.assertEqual(cell['full_requested_denominator'],16)
                    self.assertTrue(all(r['status']=='not_executed' and r['pass2'] is None for r in cell['records']))
            raw=json.loads((Path(root)/'windows/shared-anchor.json').read_bytes())
            self.assertAlmostEqual(raw['preflight']['probe']['full_max_abs_logp_gap'],.25,places=5)
            self.assertFalse(raw['preflight']['passed'])
            self.assertEqual(json.loads((Path(root)/'report.json').read_bytes()),report)

    def test_heldout_failure_does_not_shrink_denominators_or_select_partial_winner(self):
        with tempfile.TemporaryDirectory() as root,patch.object(cw,'infer_query',side_effect=PhaseDeadline('test cutoff')):
            report=self.flow(root)
            self.assertEqual(report['status'],'partial');self.assertFalse(report['candidate_selected'])
            self.assertEqual(report['selected_arm'],'anchor')
            self.assertEqual(report['evaluation']['anchor']['no_ttt']['records'][0]['status'],'deadline')
            for arm in report['evaluation'].values():
                for cell in arm.values():
                    self.assertEqual(len(cell['records']),16);self.assertIsNone(cell['pass2'])
            self.assertTrue(report['anchor_restored'])

    def test_final_report_persistence_crossing_deadline_cannot_retain_selection(self):
        now=time.time(); clock=[now]; original=cw.atomic_json
        def write(path,value):
            original(path,value)
            if Path(path).name=='report.json' and value.get('status')=='complete':
                clock[0]=value['deadline_epoch']+1
        with tempfile.TemporaryDirectory() as root,patch.object(cw.time,'time',side_effect=lambda:clock[0]), \
                patch.object(cw,'atomic_json',side_effect=write):
            report=self.flow(root)
            self.assertEqual(report['status'],'partial');self.assertFalse(report['complete'])
            self.assertFalse(report['candidate_selected']);self.assertEqual(report['selected_arm'],'anchor')
            self.assertEqual(report['selection_label'],'retain-anchor')
            self.assertTrue(report['returned_after_deadline'])
            self.assertEqual(report['stop_reason'],'deadline_during_final_report_persistence')
            self.assertEqual(json.loads((Path(root)/'report.json').read_bytes()),report)

    def test_functional_reset_drift_denies_paired_causal_completion(self):
        engine=tiny_engine();original=engine.nll;calls=0
        def nll(example):
            nonlocal calls
            calls+=1;value=original(example)
            return value+1 if calls==2 else value
        with tempfile.TemporaryDirectory() as root,patch.object(engine,'nll',side_effect=nll):
            with self.assertRaisesRegex(ValueError,'probe drift') as caught:self.flow(root,engine)
            report=caught.exception.convergence_workflow_result
            row=report['evaluation']['anchor']['ttt']['records'][0]
            self.assertFalse(row['complete']);self.assertEqual(row['status'],'failed_functional_reset')
            self.assertFalse(row['functional_reset']['verified'])
            self.assertFalse(report['candidate_selected']);self.assertTrue(report['anchor_restored'])
            self.assertIsNone(report['evaluation']['anchor']['ttt']['pass2'])

    def test_functional_reset_execution_failure_keeps_scores_observed_not_complete(self):
        for nonfinite in (False,True):
            with self.subTest(nonfinite=nonfinite):
                engine=tiny_engine(); original=engine.nll; calls=[0]
                def nll(example):
                    calls[0]+=1
                    if calls[0]==2:
                        if nonfinite:return float('nan')
                        raise RuntimeError('injected functional reset forward failure')
                    return original(example)
                with tempfile.TemporaryDirectory() as root,patch.object(engine,'nll',side_effect=nll):
                    with self.assertRaises((RuntimeError,ValueError)) as caught:self.flow(root,engine)
                    report=caught.exception.convergence_workflow_result
                    row=report['evaluation']['anchor']['ttt']['records'][0]
                    self.assertFalse(row['complete'])
                    self.assertEqual(row['status'],'failed_functional_reset')
                    self.assertFalse(row['functional_reset']['verified'])
                    self.assertIsNone(row['functional_reset']['nll_restored'])
                    self.assertIsInstance(row['pass2'],int)
                    self.assertIsNone(report['evaluation']['anchor']['ttt']['pass2'])
                    self.assertFalse(report['candidate_selected'])
                    self.assertEqual(report['selection_label'],'retain-anchor')
                    self.assertEqual(json.loads((Path(root)/'report.json').read_bytes()),report)

    def test_exact_source_pin_and_empty_output_required_before_training(self):
        prepared=copy.deepcopy(self.prepared)
        prepared['development'][next(iter(prepared['development']))]['train'][0]['output']=[[9]]
        with tempfile.TemporaryDirectory() as root:
            now=time.time()
            with patch.object(cv,'run_training') as train:
                with self.assertRaises(ValueError):
                    cw.run_workflow(tiny_engine(),prepared,deadline=now+20,training_deadline=now+10,
                        output=root,source_identity='a'*64,config=configuration())
                train.assert_not_called()
            (Path(root)/'prior-evidence.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'empty'):
                self.flow(root)

if __name__=='__main__':unittest.main()
