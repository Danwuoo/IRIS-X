"""Independent gate regressions with synthetic data and owned CPU children."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.test_nvarc_e10_screen import fixture
from tools import stage_nvarc_e10_screen as stage
from tools import nvarc_e10_screen as runtime
from tools import nvarc_calibration_gate as calibration
from tools.nvarc_native_multitask import write
from tools.nvarc_native_ttt_schedule import SOURCES,FUNCTIONS
from tools.nvarc_process_supervisor import supervise


class RuntimeGateTests(unittest.TestCase):
    def test_outer_supervisor_bounds_silent_child_without_reading_stdout(self):
        started=time.monotonic()
        result=supervise([sys.executable,'-c','import time;time.sleep(10)'],env=os.environ.copy(),cwd='.',
            started=started,total_seconds=.7,cleanup_seconds=.3)
        self.assertTrue(result['timed_out']);self.assertTrue(result['confirmed_stopped'])
        self.assertLess(time.monotonic()-started,.9)
        result=supervise([],env={},cwd='.',started=time.monotonic()-10,total_seconds=1,cleanup_seconds=.1)
        self.assertFalse(result['launched'])

    def test_closed_runtime_archive_rejects_unknown_and_known_structured_truth(self):
        screen,plans,payload=fixture()
        for relative in ('unrecognized.json','terminal.json'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'root';root.mkdir()
                for name,body in payload.items():
                    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
                write(root/relative,{'solutions':{'synthetic':[[[9]]]}})
                with self.assertRaises((RuntimeError,ValueError)):runtime.archive(root,Path(tmp)/'out.zip',100*1024**2)

    def test_nested_manifest_name_cannot_hide_uninventoried_file_from_external_pin(self):
        screen,plans,payload=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'package';result=stage.stage(root,screen,plans,payload)
            path=root/'runtime/unrecognized/package-manifest.json';path.parent.mkdir()
            write(path,{'solutions':{'synthetic':[[[9]]]}})
            with self.assertRaisesRegex(RuntimeError,'inventory differs'):
                stage.preflight(root,allow_fixture=True,expected_manifest_sha256=result['package_manifest_sha256'])

    def test_safe_partial_tail_and_uuid_temp_retained_without_marker_bypass(self):
        from tools.nvarc_runtime_archive import validate_members
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root/'screen.json',{'payload_sha256':{},'task_ids':['a']})
            path=root/'interleaved-r1/tasks/a/native/events.jsonl';path.parent.mkdir(parents=True)
            path.write_bytes(b'{"event":"synthetic"}\n'+b'{"event":"forward_reser')
            temporary=root/('interleaved-r1/submission.json.'+'a'*32+'.tmp');temporary.write_bytes(b'{"a":[')
            retained=[];self.assertIn(path,validate_members(root,interrupted=retained));self.assertEqual(len(retained),2)
            import zipfile
            target=root.parent/(root.name+'-retained.zip');runtime.archive(root,target,10000)
            extracted=root.parent/(root.name+'-extracted');extracted.mkdir()
            with zipfile.ZipFile(target) as stream:stream.extractall(extracted)
            validate_members(extracted)
            path.write_bytes(b'{"event":"synthetic"}\n'+b'{"soluti\\u006fns":[[[9]]')
            with self.assertRaisesRegex(RuntimeError,'evaluator marker'):validate_members(root)

    def test_closed_archive_worker_and_generation_identities(self):
        from tools.nvarc_runtime_archive import validate_members
        for name in ('workers/invented/result.json','interleaved-r1/.output-generations/invented/submission.json'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);write(root/'screen.json',{'payload_sha256':{},'task_ids':['a'],'workload_order':[]})
                path=root/name;path.parent.mkdir(parents=True);write(path,{})
                with self.assertRaisesRegex(RuntimeError,'unrecognized'):validate_members(root)

    def test_uncommitted_generation_partial_retains_bytes_but_active_corruption_rejects(self):
        from tools.nvarc_runtime_archive import validate_members
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root/'screen.json',{'payload_sha256':{},'task_ids':['a']})
            generation='a'*32;path=root/'interleaved-r1/.output-generations'/generation/'native-evidence.json'
            path.parent.mkdir(parents=True);path.write_bytes(b'[{"task_id":"a"')
            retained=[];validate_members(root,interrupted=retained);self.assertEqual(retained[0]['qualified'],False)
            write(root/'interleaved-r1/output-commit.json',{'generation':generation})
            with self.assertRaisesRegex(RuntimeError,'corrupted committed'):validate_members(root)

    def test_host_phase_exclusive_must_match_inclusive_observation(self):
        from tools.nvarc_public_eval import PhaseTelemetry
        value=PhaseTelemetry().snapshot();value['tests']={'0':{}};value['elapsed_host_seconds']=10;value['unscoped_host_seconds']=0
        for phase in ('preparation','training','reset','control','generation'):
            value['inclusive_host_seconds'][phase]=0;value['exclusive_host_seconds'][phase]=2
        with self.assertRaisesRegex(RuntimeError,'exclusive calibration'):calibration.verify_host_telemetry(value,1)

    def test_resource_freshness_is_bounded_and_nonfuture_at_admission(self):
        screen,_,_=fixture();now=1780000000.
        from datetime import datetime,timezone
        admission={'format':'irisx/stage4-free-gpu-resource-admission-v1','screen_id':screen['screen_id'],
            'paid_usd_ceiling':0,'quota_hours_available':100,'allocated_gpu_hours_per_quota_hour':2,
            'provider_session_seconds':18000,'private':True,'internet':False,'prior_sessions_reconciled':True,
            'rules_materials_review_ref':'synthetic no real admission'}
        for delta in (-3601,6,-1000000000,1000000000):
            admission['quota_observed_at']=datetime.fromtimestamp(now+delta,timezone.utc).isoformat()
            with self.subTest(delta=delta),self.assertRaisesRegex(RuntimeError,'observation must'):
                stage.validate_resource_admission(admission,screen,now_epoch=now)
        admission['quota_observed_at']=datetime.fromtimestamp(now-30,timezone.utc).isoformat()
        stage.validate_resource_admission(admission,screen,now_epoch=now)

    def test_zero_candidate_calibration_still_invokes_native_epoch_gate(self):
        ch={'a':{'train':[{'input':[[1]],'output':[[2]]}],'test':[{'input':[[3]]}]}}
        evidence=[{'task_id':'a','provenance':'native-model','receipt':{'status':'complete','launched':True,'returncode':0},
                   'checkpoint':{'tests':[{'attempts':[]}]}}]
        # This tests unconditional gate dispatch, not NumPy or native loading.
        with patch.dict(sys.modules, {'numpy': SimpleNamespace()}), \
             patch.object(calibration,'load_sources',return_value=(SimpleNamespace(),None,None)), \
             patch.object(calibration,'verify_native_training_gate',side_effect=RuntimeError('mandatory epoch')) as gate:
            with self.assertRaisesRegex(RuntimeError,'mandatory epoch'):
                calibration.require_task_gates('.',{},ch,evidence,None,['a'])
            self.assertEqual(gate.call_count,1)

    def test_exact_epoch_lr_token_construction_and_completion_closure(self):
        rates=[5e-5*(i/13 if i<13 else .5*(1+math.cos(math.pi*(i-13)/115))) for i in range(129)]
        rows=[{'input_ids_digest':str(i),'labels_digest':'l'+str(i),'input_tokens':9,'supervised_tokens':3} for i in range(128)]
        ledger={'forwards':[{**row,'completed':True,'loss':1.} for row in rows],
            'training_steps':[{'completed':True} for _ in rows],
            'optimizer_steps':[{'learning_rate':rates[i],'gradient_tensors':506,'gradient_norm_after_clip':.5,'completed':True} for i in range(128)],
            'optimizer_constructions':[{'completed':True}],'generation_calls':0,'teacher_calls':0}
        schedule={'source_sha256':SOURCES,'function_sha256':FUNCTIONS,'warmup_steps':13,'epoch_steps':128,'rates':rates}
        calibration.verify_epoch_ledger(ledger,schedule,{'source_learning_rates':rates},rows,506)
        for mode in ('lr','tokens','construction','completion'):
            bad=copy.deepcopy(ledger)
            if mode=='lr':bad['optimizer_steps'][20]['learning_rate']*=2
            if mode=='tokens':bad['forwards'][20]['input_tokens']+=1
            if mode=='construction':bad['optimizer_constructions']=[]
            if mode=='completion':bad['training_steps'][20]['completed']=False
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):
                calibration.verify_epoch_ledger(bad,schedule,{'source_learning_rates':rates},rows,506)


if __name__=='__main__':unittest.main()
