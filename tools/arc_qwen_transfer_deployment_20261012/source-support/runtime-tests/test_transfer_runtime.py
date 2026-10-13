"""Offline contracts and adversarial tests for true-ARC transfer runtime."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools.arc_qwen_transfer_20261012 import data,experiment,science_profiles as sp
from tools.arc_qwen_transfer_20261012.protocol import PROTOCOL,digest,validate_config
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json

class RuntimeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.dataset=data.build_dataset({'tiny_cpu':True},cls.root/'dataset')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_frozen_split_counts_and_separation(self):
        p=self.dataset['plan'];self.assertEqual([len(p[k]) for k in ('train_ids','dev_ids','holdout_ids','ttt_dev_ids','ttt_holdout_ids')],[32,16,32,8,8])
        self.assertEqual(len(set(p['train_ids']+p['dev_ids']+p['holdout_ids'])),80)
        self.assertEqual(set(p['train_ids']),set(data.REAL_TRAIN_IDS))
    def test_closed_solver_case(self):
        c=copy.deepcopy(self.dataset['cases'][0]);c['target']=[[1]]
        with self.assertRaises(ValueError):data.solver_case(c)
    def test_native_global_records_reconstruct(self):
        data.validate_records(self.dataset['records'],self.dataset['manifest'],())
        self.assertEqual({r['task_id'] for r in self.dataset['records']},set(data.REAL_TRAIN_IDS))
        self.assertTrue(all(r['provenance']['augmentation']['colors'][0]==0 for r in self.dataset['records']))
    def test_single_visible_pair_task_supervision(self):
        rows=data.build_task_records('one',[{'input':[[1]],'output':[[2]]}])
        self.assertEqual(len(rows),8);data.validate_task_records(rows,'one')
        self.assertTrue(all(r['provenance']['visible_demo_indices']==[] for r in rows))
        self.assertNotIn('Demonstration 1',rows[0]['messages'][-1]['content'])
    def test_tampered_task_message_rejected(self):
        rows=data.build_task_records('one',[{'input':[[1]],'output':[[2]]}]);rows[0]['messages'][-1]['content']='target leak'
        from tools.arc_next_models import digest as nd
        rows[0]['record_id']=nd({k:v for k,v in rows[0].items() if k!='record_id'})
        with self.assertRaises(ValueError):data.validate_task_records(rows,'one')
    def test_escrows_separate_and_dev_does_not_open_holdout(self):
        d=self.dataset;self.assertNotEqual(d['escrow']['dev']['path'],d['escrow']['holdout']['path'])
        out=Path(tempfile.mkdtemp())
        rows=[experiment._empty(c,'none') for c in d['cases'] if c['scope']=='dev']
        seal=experiment.seal_scope(out,'dev',d,{'base':rows})
        original=data.checked_json
        def guarded(path,*args,**kw):
            self.assertNotEqual(str(path),d['escrow']['holdout']['path']);return original(path,*args,**kw)
        with patch.object(data,'checked_json',side_effect=guarded):self.assertEqual(len(data.open_targets(d,'dev',seal)),16)
        with self.assertRaises(ValueError):data.open_targets(d,'holdout',seal)
    def test_missing_case_denominator_cannot_seal(self):
        rows=[experiment._empty(c,'none') for c in self.dataset['cases'] if c['scope']=='dev'][:-1]
        with self.assertRaises(ValueError):experiment.seal_scope(Path(tempfile.mkdtemp()),'dev',self.dataset,{'base':rows})
    def test_ttt_full_fold_and_refit_counts(self):
        p=self.dataset['plan'];r=sp.counts(self.dataset['cases'],p['ttt_dev_ids']+p['ttt_holdout_ids'])
        self.assertEqual(r['parents'],16);self.assertEqual(r['demonstrations'],32)
        self.assertEqual(r['training_updates'],16*(32+16));self.assertEqual(r['generation_calls'],3*32+6*16)
        self.assertEqual(r['fold_scores'],96);self.assertEqual(r['full_demo_retrains'],16)
    def test_per_call_and_session_cost_gates(self):
        ledger=WorkLedger(Path(tempfile.mkdtemp())/'ledger.jsonl')
        stats={'training_seconds_per_step':1,'prefill_seconds_per_input':.001,'decode_seconds_per_call':1,'full_seconds_per_input':.001}
        e=sp.forecast(stats,updates=0,generations=1)
        a=sp.admission(e,ledger,time.monotonic()+43200)
        self.assertFalse(a['admitted']);self.assertEqual(a['reason'],'native-per-call-deadline-exceeded')
    def test_calibration_stats_not_aliased(self):
        ledger=WorkLedger(Path(tempfile.mkdtemp())/'ledger.jsonl')
        c={'completed_lengths':[128,512,2048,4096],'full_state_restoration_verified':True,'behavioral_cache_admitted':True,
            'measurements':{'training_seconds_per_step':.001,'prefill_seconds_per_input':.00001,'decode_seconds_per_call':.001,'full_seconds_per_input':.00001}}
        a=sp.decide(None,self.dataset,c,ledger,time.monotonic()+43200,tiny=True);a['measurements']['backend_load_seconds']=30
        self.assertNotIn('backend_load_seconds',c['measurements'])
    def test_failclosed_config(self):
        base={'enabled':True,'started_epoch':time.time(),'model':{},'training_root':'/tmp/train','public_exclusions_path':'/tmp/ex','public_exclusions_sha256':'a'*64}
        validate_config(base)
        with self.assertRaises(ValueError):validate_config({**base,'test_skip_ttt':True})
        with self.assertRaises(ValueError):validate_config({**base,'started_epoch':float('nan')})
    def test_context_integrity_errors_not_exclusions(self):
        with patch.object(experiment,'prepare_record',side_effect=ValueError('completion tokenizer identity changed')):
            with self.assertRaisesRegex(ValueError,'identity changed'):experiment._native_admission(None,self.dataset['records'][:1],data.REAL_TRAIN_IDS)
    def test_score_keeps_first_answer_order_and_denominators(self):
        root=Path(tempfile.mkdtemp());d=self.dataset;targets={}
        for scope in ('dev','holdout'):
            targets.update(json.loads(Path(d['escrow'][scope]['path']).read_text()))
        methods={};report={}
        for scope in ('dev','holdout'):
            cases=[c for c in d['cases'] if c['scope']==scope]
            base=[{**experiment._empty(c,'fixture'),'answers':[[[0]]],'complete':True} for c in cases]
            selected=[{**experiment._empty(c,'fixture'),'answers':[[[0]],targets[c['case_id']]],'complete':True} for c in cases]
            methods={'base':base,'selected_sft':selected}
            report[scope+'_seal']=experiment.seal_scope(root,scope,d,methods)
        chosen=set(d['plan']['ttt_dev_ids']+d['plan']['ttt_holdout_ids'])
        ttt={'status':'TTT_NOT_RUN','rows':[experiment._empty(c,'not admitted') for c in d['cases'] if c['parent_id'] in chosen]}
        path=root/'ttt.json';atomic_json(path,ttt,exclusive=True)
        report.update(ttt_predictions_path=str(path),ttt_predictions_sha256=data.file_sha(path))
        with patch('tools.arc_learning_agent_20261011.process_guard.verify_closed_proof'):
            scored=experiment.score_closed(d,report,{'closed':True})
        for scope,n in (('dev',16),('holdout',32)):
            row=scored['scopes'][scope]['selected_sft']
            self.assertEqual((row['denominator'],row['pass_at_1_count'],row['pass_at_2_count']),(n,0,n))
            t=scored['scopes'][scope]['selected_ttt_subset']
            self.assertEqual((t['denominator'],t['status'],t['abstentions']),(8,'TTT_NOT_RUN',8))
    def test_public_selection_includes_base_without_changing_main_selector(self):
        root=Path(tempfile.mkdtemp());d=self.dataset;targets=json.loads(Path(d['escrow']['dev']['path']).read_text())
        cases=[c for c in d['cases'] if c['scope']=='dev'];methods={}
        for name in ('base','sft64','sft256'):
            methods[name]=[{**experiment._empty(c,'fixture'),'answers':[targets[c['case_id']]] if name=='base' else [],'complete':True} for c in cases]
        seal=experiment.seal_scope(root,'dev',d,methods)
        self.assertEqual(experiment.select_sft(d,seal,[64,256])['candidate_id'],'sft64')
        self.assertEqual(experiment.select_sft(d,seal,[64,256],include_base=True)['candidate_id'],'base')
    def test_stream_export_deadline_and_operational_failures(self):
        import zipfile
        from tools.arc_qwen_transfer_20261012.runner import _zip_member,operational_success
        root=Path(tempfile.mkdtemp());f=root/'data';f.write_bytes(b'fixture')
        with zipfile.ZipFile(root/'out.zip','w') as z:
            with self.assertRaisesRegex(ValueError,'deadline'):
                _zip_member(z,f,'data',data.file_sha(f),time.monotonic()-1)
        for error in ('public_evaluation_error','main_scoring_error','archive_error'):
            self.assertFalse(operational_success({'science_complete':True,error:'blocked'},{'operational_success':True}))
        self.assertTrue(operational_success({'science_complete':True},{'operational_success':True}))
    def test_fixture_defaults_and_actual_reservation_cap(self):
        c=validate_config({'enabled':True,'tiny_cpu':True,'test_fixture_dataset':True,'started_epoch':time.time()})
        self.assertEqual((c['test_checkpoint_updates'],c['test_generation_cap']),([1,2],4))
        stats={'training_seconds_per_step':0,'prefill_seconds_per_input':0,'decode_seconds_per_call':0,'full_seconds_per_input':0}
        e=sp.forecast(stats,updates=0,generations=1,tiny=True,generation_cap=1024)
        ledger=WorkLedger(Path(tempfile.mkdtemp())/'ledger.jsonl')
        a=sp.admission(e,ledger,time.monotonic()+100,tiny=True)
        self.assertEqual(a['reservation_slack_input_tokens'],sum(3072+i for i in range(1024))+4096)
    def test_wilson_bounds(self):
        self.assertAlmostEqual(experiment._wilson(0,32)[0],0);self.assertLess(experiment._wilson(0,32)[1],.11)
        self.assertAlmostEqual(experiment._wilson(32,32)[1],1)

if __name__=='__main__':unittest.main()
