"""Full archive-reader regressions with explicitly synthetic downstream candidates.

Only package admission/construction and candidate replay are substituted. Real
ZIP closure, hashes, prepared-token/epoch recount, event chains, receipts, cache
and reset inputs, parent counters and final qualification run through verify().
These fixtures cannot pass the unmodified inert-package admission path and are
never evidence of GPU execution, trained model output or ARC correctness.
"""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from array import array
import sys
import base64
import subprocess
import time

from tools import verify_nvarc_native_multitask as verifier
from tools import stage_nvarc_native_multitask as stage
from tools.nvarc_native_multitask import canonical,digest
from tools.nvarc_native_submission import task_binding,read_task_evidence
from tools.nvarc_native_solve_runtime import CONTROL_PREFIXES,compare_vectors


class ArchiveQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tokenizers import Tokenizer
        cls.plan,cls.raw,_,_=stage.construct('nvarc-original-qwen3-native-multitask-994')
        cls.plan=copy.deepcopy(cls.plan);cls.plan['approved']=True
        cls.raw=dict(cls.raw,plan=canonical(cls.plan))
        cls.material=json.loads(gzip.decompress(cls.raw['task_materials_gzip']))
        cls.tokenizer=Tokenizer.from_file(str(stage.MODEL/'model/tokenizer.json'))
        cls.challenges=json.loads(cls.raw['challenges'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='iris-native-archive-fixture-')
        self.directory=Path(self.temp.name);self.content={}
        self.receipts=[{'task_id':a['task_id'],'attempt_id':a['attempt_id'],
            'status':'failed' if a['mode']=='fault-after-two-updates' else 'complete',
            'returncode':1 if a['mode']=='fault-after-two-updates' else 0,
            'launched':True,'reset_inferred':False,'reserved_seconds':1000}
            for a in self.plan['worker_attempts']]
        self.put('plan.json',self.plan)
        self.put('payload-bindings.json',{k:hashlib.sha256(v).hexdigest() for k,v in self.raw.items()})
        for name,key in stage.FILES.items():self.content[name]=self.raw[key]
        self.put('hardware.json',{'torch':'2.8.0+cu128','cuda':'12.8','inventory':[
            {'uuid':'GPU-synthetic-'+str(i),'name':'NVIDIA L4','bf16':True} for i in range(4)]})
        self.put('model-verification.json',{'all_ten_files_verified':True,'model_material_digest':self.plan['model_material_digest']})
        self.put('source-verification.json',{'inventory':json.loads(self.raw['source_inventory'])})
        for attempt in self.plan['worker_attempts']:self.worker(attempt)

    def tearDown(self):self.temp.cleanup()
    def put(self,name,value):self.content[name]=canonical(value)
    def get(self,name):return json.loads(self.content[name])

    def worker(self,attempt):
        task=attempt['task_id'];mode=attempt['mode'];prefix='tasks/'+attempt['attempt_id']+'/native/'
        spec=self.plan['task_specs'][task];binding=task_binding(self.plan,self.challenges,task)
        binding['attempt_id']=attempt['attempt_id']
        baseline=[dict(row,finite=True,sha256='0'*64) for row in self.plan['native_adapter_topology']]
        changed=copy.deepcopy(baseline);changed[0]['sha256']='1'*64
        self.put(prefix+'hardware.json',{'device_uuid':'GPU-synthetic-0'})
        for name,value in [('baseline-inventory',baseline),('reset-inventory',baseline),
            ('pre-reset-inventory',baseline if mode=='baseline-only' else changed)]:self.put(prefix+name+'.json',value)
        if mode!='baseline-only':
            material=self.material[task];rows=[];values=[]
            for wanted,text in zip(material['rows'],material['texts']):
                ids=self.tokenizer.encode(text['text']).ids;labels=[-100]*len(ids)
                starts=[i for i,t in enumerate(ids) if t in (11,12)];ends=[i for i,t in enumerate(ids) if t==15]
                for j,(start,end) in enumerate(zip(starts,ends)):
                    if j%2:labels[start+2:end+1]=ids[start+2:end+1]
                rows.append(dict(wanted,retained_byte_offset=len(values)*2,retained_token_bytes=len(ids)*4,
                    source_input_ids_equal=True,source_labels_equal=True,collator_preserved_input_ids=True))
                values.extend(ids+labels)
            packed=array('h',values)
            if sys.byteorder!='little':packed.byteswap()
            self.content[prefix+'prepared-tokens.i16le']=packed.tobytes();self.put(prefix+'prepared-rows.json',rows)
            self.put(prefix+'preparation.json',{'trainer_origins':self.plan['native_trainer_origins'],
                'checkpoint_flags':self.plan['native_checkpoint_flags'],'prepared_rows_digest':digest(rows),'blocked_attempts':0})
            used=material['rows'] if mode=='solve' else material['rows'][:2]
            self.put(prefix+'training-ledger.json',{'forwards':[dict(r,completed=True) for r in used],
                'training_steps':[{'completed':True} for _ in used],
                'optimizer_steps':[{'completed':True,'learning_rate':spec['source_learning_rates'][i],
                    'gradient_tensors':506,'gradient_norm_after_clip':.5} for i,_ in enumerate(used)]})
            self.put(prefix+'native-schedule.json',{'epoch_steps':128,'warmup_steps':13,
                'maximum_reference_ulp_distance':0,'rates':spec['source_learning_rates']})
            if mode=='solve':
                self.put(prefix+'trained-inventory.json',changed)
                self.put(prefix+'optimizer-state.json',[{'step':128,'finite':True,'parameter_dtype':'torch.bfloat16'}]*506)
        vector=[[10.]+[0.]*15 for _ in range(4)]
        comparisons={k:compare_vectors(vector,vector) for k in ('deep','sibling_after_deep')}
        events=[]
        def emit(event,**kw):events.append({'event':event,**kw})
        inputs=[(CONTROL_PREFIXES,False,0),([[0]]*4,True,9),([[1]]*4,True,10),([[2]]*4,True,9),
            ([r+[0,1] for r in CONTROL_PREFIXES],False,0),([r+[2] for r in CONTROL_PREFIXES],False,0),
            (CONTROL_PREFIXES,False,0)]
        for i,(ids,cached,start) in enumerate(inputs,1):
            emit('forward_reserved',call_id=i,phase='control',batch_shape=[4,len(ids[0])],
                physical_input_tokens=4*len(ids[0]),cached=cached,position_start=start,
                position_end=start+len(ids[0])-1,input_ids_digest=digest(ids))
            emit('forward_completed',call_id=i,phase='control',output_contract='model-output-logits-cache')
            if i==6:emit('cache_control_result',comparisons=comparisons,baseline_prefill=vector,
                deep_cached=vector,sibling_cached=vector,deep_reference=vector,sibling_reference=vector)
        self.put_events(prefix,events,binding)
        self.put(prefix+'cache-control.json',{'comparisons':comparisons,'baseline_prefill':vector,'model_calls':6,
            'synthetic_tokens_only':True,'full_numerical_parity_claim':False})
        self.put(prefix+'post-reset-control.json',{'prefill':vector,'prefill_bitwise_equal':True,
            'synthetic_tokens_only':True,'additional_model_calls':1})
        tests=[{'test_index':i,'ranked_grids':[[[1]]],'native_complete':True} for i in range(spec['test_count'])] if mode=='solve' else []
        if mode=='solve':
            self.put(prefix+'checkpoint.json',{'binding':binding,'tests':tests,'event_count':len(events),
                'event_head':json.loads(self.content[prefix+'events.jsonl'].splitlines()[-1])['digest']})
        self.put(prefix+'result.json',{'binding':binding,'mode':mode,'outcome':'failed' if mode=='fault-after-two-updates' else 'complete',
            'failures':[{'phase':'pipeline','error_type':'RuntimeError','error_message':'planned isolation fault after two native updates'}]
                if mode=='fault-after-two-updates' else [],'training_complete':mode=='solve',
            'all_saved_tensors_restored':True,'post_reset_control_verified':True,'optimizer_discarded':True,
            'inference_forwards_reserved':{'control':7,'generation':0,'verification':0},
            'inference_forwards_completed':{'control':7,'generation':0,'verification':0},
            'inference_input_tokens_by_phase':{'control':168,'generation':0,'verification':0},
            'tests':tests,'contains_evaluator_truth':False,'correctness_scored':False,'teacher_calls':0,'paid_usd':0,
            'worker_wall_seconds':1,'training_wall_seconds':.5 if mode=='solve' else None})

    def put_events(self,prefix,events,binding):
        head=digest(binding);rows=[]
        for i,event in enumerate(events):
            row={**binding,**{k:v for k,v in event.items() if k not in binding and k not in {'sequence','previous','digest'}},
                'sequence':i,'previous':head};row['digest']=digest(row);head=row['digest'];rows.append(row)
        self.content[prefix+'events.jsonl']=b''.join(canonical(r)+b'\n' for r in rows)

    @staticmethod
    def candidate_fixture(challenges,plan,evidence,directory,tokenizer):
        # Substitute only downstream solver replay, outside this lifecycle test.
        assert len(evidence)==len(challenges)
        submission={}
        for item in evidence:
            tests=item['checkpoint']['tests'];assert len(tests)==len(challenges[item['task_id']]['test'])
            submission[item['task_id']]=[{'attempt_1':[[1]],'attempt_2':[[1]]} for _ in tests]
        return submission,{'fixture_kind':'synthetic-candidate-substitution','model_attempt_slots_missing':0,
            'task_count':len(challenges),'test_output_count':sum(len(t['test']) for t in challenges.values())}

    def archive(self):
        self.put('worker-receipts.json',self.receipts)
        counters=dict(model_forwards=0,model_forwards_reserved=0,optimizer_steps=0,optimizer_steps_reserved=0,generations=0)
        for attempt in self.plan['worker_attempts']:
            prefix='tasks/'+attempt['attempt_id']+'/native/'
            if prefix+'training-ledger.json' in self.content:
                ledger=self.get(prefix+'training-ledger.json')
                for kind,key in [('forwards','model_forwards'),('optimizer_steps','optimizer_steps')]:
                    counters[key]+=sum(r['completed'] for r in ledger[kind]);counters[key+'_reserved']+=len(ledger[kind])
            if prefix+'events.jsonl' in self.content:
                events=[json.loads(line) for line in self.content[prefix+'events.jsonl'].splitlines()]
                counters['model_forwards_reserved']+=sum(e['event']=='forward_reserved' for e in events)
                counters['model_forwards']+=sum(e['event']=='forward_completed' for e in events)
        self.put('terminal.json',dict(run_id=self.plan['run_id'],outcome='failed',phase='terminal',wall_seconds=1,
            worker_receipts_digest=digest(self.receipts),contains_evaluator_truth=False,**counters))
        for name,body in self.content.items():
            path=self.directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        evidence=read_task_evidence(self.directory,self.plan,self.challenges,self.receipts)
        submission,audit=self.candidate_fixture(self.challenges,self.plan,evidence,self.directory,None)
        self.put('native-evidence.json',evidence);self.put('submission.json',submission);self.put('submission-audit.json',audit)
        path=self.directory/'synthetic-result.zip'
        manifest={'run_id':self.plan['run_id'],'plan_digest':digest(self.plan),'members':[
            {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()} for name,body in self.content.items()]}
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as stream:
            for name,body in self.content.items():stream.writestr(name,body)
            stream.writestr('manifest.json',canonical(manifest))
        return path

    def verify(self):
        path=self.archive()
        with patch.object(verifier,'preflight',return_value={'run_id':self.plan['run_id']}),\
             patch.object(verifier,'construct',return_value=(self.plan,self.raw,None,None)),\
             patch.object(verifier,'build_native_submission',side_effect=self.candidate_fixture):
            return verifier.verify(path,self.directory/'inert-package-not-created')

    def test_complete_controls_and_only_expected_fault_qualify_full_reader(self):
        proof=self.verify()
        self.assertTrue(proof['gpu_validation_gate']);self.assertEqual(proof['parent_outcome'],'failed')
        self.assertTrue(proof['all_expected_attempts_gate']);self.assertTrue(all(p['cache_reset_gate'] for p in proof['attempts']))
        # Without the explicit test substitutions, no authorized package exists.
        with self.assertRaises(Exception):verifier.verify(self.directory/'synthetic-result.zip',self.directory/'inert-package-not-created')

    def test_fourth_nonzero_or_terminated_after_result_never_passes(self):
        original=copy.deepcopy(self.receipts[3])
        for status,code in [('failed',1),('worker_crash',-9),('timeout',None),('interrupted_pending',None),('failed',0)]:
            with self.subTest(status=status,code=code):
                self.receipts[3]=dict(original,status=status,returncode=code);proof=self.verify()
                self.assertFalse(proof['gpu_validation_gate']);self.assertFalse(proof['all_expected_attempts_gate'])
                self.assertTrue(proof['isolation_baseline_gate']);self.assertTrue(proof['attempts'][3]['cache_reset_gate'])
                self.assertTrue(proof['nonempty_all_tests']);self.assertEqual(proof['test_output_count'],3)

    def test_actual_fourth_process_exit_or_termination_after_durable_artifacts(self):
        from irisx.arc_nvarc_combined import _launch_worker,_reap
        prefix='tasks/baseline-after-fault/native/'
        payload=self.directory/'fourth-payload.json'
        payload.write_text(json.dumps({name:base64.b64encode(self.content[prefix+name]).decode()
            for name in ('reset-inventory.json','post-reset-control.json','result.json')}))
        script=("import base64,json,os,pathlib,sys,time\n"
            "out=pathlib.Path(sys.argv[2]);out.mkdir()\n"
            "for name,value in json.loads(pathlib.Path(sys.argv[1]).read_bytes()).items():\n"
            " with (out/name).open('wb') as stream:\n"
            "  stream.write(base64.b64decode(value));stream.flush();os.fsync(stream.fileno())\n"
            "(out/'artifacts-written').write_text('synthetic CPU fixture')\n"
            "if sys.argv[3]=='nonzero':raise SystemExit(3)\n"
            "time.sleep(30)\n")
        for fate in ('nonzero','terminated'):
            with self.subTest(fate=fate):
                target=self.directory/fate
                process,job=_launch_worker([sys.executable,'-c',script,str(payload),str(target),fate],cwd=None,env=None)
                try:
                    deadline=time.monotonic()+3
                    while not (target/'artifacts-written').exists() and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue((target/'artifacts-written').is_file())
                    for name in ('reset-inventory.json','post-reset-control.json','result.json'):
                        self.assertEqual(self.content[prefix+name],(target/name).read_bytes())
                    if fate=='nonzero':
                        code=process.wait(timeout=3);self.assertEqual(3,code)
                        _reap(process,job,1,1);job=None
                        self.receipts[3].update(status='failed',returncode=code)
                    else:
                        self.assertIsNone(process.poll())
                        _reap(process,job,1,1);job=None
                        self.assertNotEqual(0,process.returncode)
                        self.receipts[3].update(status='timeout',returncode=None)
                    proof=self.verify()
                    self.assertFalse(proof['gpu_validation_gate']);self.assertTrue(proof['isolation_baseline_gate'])
                    self.assertTrue(proof['attempts'][3]['cache_reset_gate']);self.assertTrue(proof['nonempty_all_tests'])
                finally:
                    if job is not None or process.poll() is None:_reap(process,job,1,1)
                    process.stdout.close();process.stderr.close()

    def test_fourth_failed_result_with_full_artifacts_is_diagnostic_only(self):
        prefix='tasks/baseline-after-fault/native/';result=self.get(prefix+'result.json')
        result.update(outcome='failed',failures=[{'phase':'cleanup','error_type':'RuntimeError','error_message':'synthetic cleanup failure'}])
        self.put(prefix+'result.json',result);self.receipts[3].update(status='failed',returncode=1)
        proof=self.verify();self.assertFalse(proof['gpu_validation_gate']);self.assertTrue(proof['isolation_baseline_gate'])

    def test_each_reset_requires_seventh_completed_call_even_with_true_flags(self):
        for attempt in self.plan['worker_attempts']:
            with self.subTest(attempt=attempt['attempt_id']):
                original=copy.deepcopy(self.content);prefix='tasks/'+attempt['attempt_id']+'/native/'
                events=[json.loads(line) for line in self.content[prefix+'events.jsonl'].splitlines()]
                events=[e for e in events if e.get('call_id')!=7]
                self.put_events(prefix,events,self.get(prefix+'result.json')['binding'])
                result=self.get(prefix+'result.json');result['inference_forwards_reserved']['control']=6
                result['inference_forwards_completed']['control']=6;result['inference_input_tokens_by_phase']['control']=132
                self.put(prefix+'result.json',result)
                if prefix+'checkpoint.json' in self.content:
                    cp=self.get(prefix+'checkpoint.json');cp.update(event_count=len(events),event_head=json.loads(self.content[prefix+'events.jsonl'].splitlines()[-1])['digest']);self.put(prefix+'checkpoint.json',cp)
                proof=self.verify();self.assertFalse(proof['gpu_validation_gate'])
                target=next(p for p in proof['attempts'] if p['attempt_id']==attempt['attempt_id'])
                self.assertTrue(target['cache_observed']);self.assertFalse(target['reset_call_observed'])
                self.content=original

    def test_reserved_reset_without_completion_cannot_qualify(self):
        prefix='tasks/baseline-after-fault/native/'
        events=[json.loads(line) for line in self.content[prefix+'events.jsonl'].splitlines()]
        events=[e for e in events if not (e['event']=='forward_completed' and e['call_id']==7)]
        self.put_events(prefix,events,self.get(prefix+'result.json')['binding'])
        result=self.get(prefix+'result.json');result['inference_forwards_completed']['control']=6;self.put(prefix+'result.json',result)
        self.assertFalse(self.verify()['gpu_validation_gate'])

    def test_cache_metadata_cannot_replace_complete_six_call_transcript(self):
        prefix='tasks/baseline-after-fault/native/';cache=self.get(prefix+'cache-control.json');cache['model_calls']=5
        self.put(prefix+'cache-control.json',cache)
        with self.assertRaisesRegex(RuntimeError,'six-call'):self.verify()

    def test_fourth_unexecuted_or_missing_result_never_passes(self):
        self.receipts[3].update(status='not_executed',returncode=None,launched=False)
        for name in list(self.content):
            if name.startswith('tasks/baseline-after-fault/'):del self.content[name]
        proof=self.verify();self.assertFalse(proof['gpu_validation_gate']);self.assertEqual(proof['test_output_count'],3)

    def test_fourth_complete_receipt_without_worker_result_is_not_qualified(self):
        del self.content['tasks/baseline-after-fault/native/result.json']
        proof=self.verify();self.assertFalse(proof['gpu_validation_gate']);self.assertFalse(proof['all_expected_attempts_gate'])

    def test_complete_result_with_uncleared_optimizer_does_not_qualify(self):
        prefix='tasks/baseline-after-fault/native/';result=self.get(prefix+'result.json')
        result['optimizer_discarded']=False;self.put(prefix+'result.json',result)
        proof=self.verify();self.assertFalse(proof['gpu_validation_gate']);self.assertTrue(proof['isolation_baseline_gate'])

    def test_reset_call_count_metadata_and_prefill_binding_are_checked(self):
        prefix='tasks/baseline-after-fault/native/';post=self.get(prefix+'post-reset-control.json')
        post['additional_model_calls']=0;self.put(prefix+'post-reset-control.json',post)
        with self.assertRaisesRegex(RuntimeError,'one-call'):self.verify()

    def test_wrong_mode_and_forged_success_receipt_fail_closed(self):
        prefix='tasks/baseline-after-fault/native/';result=self.get(prefix+'result.json');result['mode']='solve'
        self.put(prefix+'result.json',result)
        with self.assertRaisesRegex(RuntimeError,'child failure'):self.verify()
        result['mode']='baseline-only';self.put(prefix+'result.json',result);self.receipts[3]['returncode']=1
        with self.assertRaisesRegex(RuntimeError,'successful process exit'):self.verify()

    def test_fault_is_only_the_exact_two_update_normal_exception(self):
        prefix='tasks/fault-first/native/';result=self.get(prefix+'result.json')
        result['failures'][0]['error_message']='unexpected runtime failure';self.put(prefix+'result.json',result)
        proof=self.verify();self.assertFalse(proof['gpu_validation_gate']);self.assertFalse(proof['expected_injected_failure_observed'])

    def test_fault_signal_exit_is_not_the_expected_python_exception(self):
        self.receipts[2]['returncode']=-9;proof=self.verify()
        self.assertFalse(proof['gpu_validation_gate']);self.assertFalse(proof['expected_injected_failure_observed'])
