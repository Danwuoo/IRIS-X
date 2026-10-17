"""Synthetic probe packaging/counts only; zero model or provider invocations."""
from tests.platform_requirements import requires_linux
import json
import copy
import contextlib
import io
import hashlib
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from tests.test_nvarc_e10_screen import fixture
from tools import stage_nvarc_e10_probe as stage
from tools.nvarc_native_multitask import canonical,digest,write
from tools.nvarc_native_solve_runtime import cache_controls
from tools import nvarc_resource_attachment as mounts
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,EXTERNAL_FILES


def _load_linux_runtime():
    global verify_observations, control_adapter, probe
    from tools.nvarc_e10_probe import verify_observations
    from tools.nvarc_e10_probe import control_adapter
    from tools import nvarc_e10_probe as probe

def probe_fixture():
    screen,plans,payload=fixture();plan=plans['interleaved-r1']
    config={key:plan[key] for key in CONFIG_FIELDS}
    config.update(native_source_learning_rates=plan['native_source_learning_rates'],versions={'torch':'2.8.0'})
    external={name:payload[name] for name in EXTERNAL_FILES};external['verified-tokenizer.json']=b'{}'
    return stage.construct('stage4-e10-probe-synthetic','0'*40,external,config,
        json.loads(payload['material-contract.json']),fixture=True)


class FakeTensor:
    def __init__(self,data):self.data=copy.deepcopy(data)
    @property
    def shape(self):
        result=[];row=self.data
        while isinstance(row,list):result.append(len(row));row=row[0] if row else None
        return tuple(result)
    def detach(self):return self
    def cpu(self):return self
    def float(self):return self
    def contiguous(self):return self
    def tolist(self):return copy.deepcopy(self.data)
    def unsqueeze(self,axis):assert axis==0;return FakeTensor([self.data])
    def expand(self,n,width):assert width==-1;return FakeTensor(self.data*n)
    def __getitem__(self,key):
        assert key==(slice(None),-1);return FakeTensor([row[-1] for row in self.data])


class FakeTorch:
    long=object();__version__='2.8.0+cu128'
    def __init__(self,peak=0):self.cuda=SimpleNamespace(max_memory_allocated=lambda:peak)
    def tensor(self,data,**_kwargs):return FakeTensor(data)
    def arange(self,n,**_kwargs):return FakeTensor(list(range(n)))
    def inference_mode(self):return contextlib.nullcontext()
    def isfinite(self,_value):return SimpleNamespace(all=lambda:SimpleNamespace(item=lambda:True))


class FakeEngine:
    peak=0
    def __init__(self,root,plan,_model,_dependency,rank):
        self.torch=FakeTorch(type(self).peak)
        class Model:
            device='synthetic-cpu'
            def __call__(self,input_ids,**_kwargs):
                rows,width=input_ids.shape
                return SimpleNamespace(logits=FakeTensor([[[0.]*16 for _ in range(width)] for _ in range(rows)]),past_key_values=object())
            def parameters(self):return [SimpleNamespace(grad=None)]
        self.model=Model();self.baseline={'synthetic':'detached-inventory'}
        warm=self.adapter(lambda *_args,**_kwargs:None);self.initial_control=cache_controls(warm)
        write(root/'workers'/str(rank)/'ready.json',{'rank':rank,'uuid':'synthetic-'+str(rank),
            'model_material_digest':plan['model_material_digest'],'baseline_digest':digest(self.baseline),
            'torch':self.torch.__version__,'initial_control_forwards':warm.completed})
    def inventory(self):return self.baseline
    def restore(self):pass
    def inference(self):pass


class Process:
    pid=123456
    def __init__(self,code=0):self.code=code
    def poll(self):return self.code


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class ProbeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)/'root';self.root.mkdir()
        self.plan,raw=probe_fixture()
        for name,body in raw.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    def tearDown(self):self.temporary.cleanup()
    def worker(self,rank=0,peak=0):
        (self.root/'workers'/str(rank)).mkdir(parents=True,exist_ok=True)
        FakeEngine.peak=peak
        with patch.object(probe,'NativeEngine',FakeEngine),patch.object(probe,'install_owner_guard'), \
             patch.object(probe,'require_worker_receipt'):
            return probe.worker(self.root,Path('synthetic-dependency'),Path('synthetic-model'),rank,time.time()+30,os.getpid())
    def coordinator(self,*,launch=None,write_fn=None,archive_fn=None):
        def normal(command,**_kwargs):
            rank=int(command[command.index('--rank')+1]);return Process(self.worker(rank))
        def proof(*_args):write(self.root/probe.RECEIPT_FILE,{'synthetic':'no dependency imported'})
        with patch.object(stage,'verify_runtime',return_value=self.plan), \
             patch.object(probe,'verify_before_prepare',side_effect=proof), \
             patch.object(probe,'verify_mount',return_value={'competition_files_opened':0}), \
             patch.object(probe,'prepare',return_value=(Path('synthetic-model'),[{'uuid':'synthetic-'+str(i)} for i in range(4)])), \
             patch.object(probe.subprocess,'Popen',side_effect=launch or normal), \
             patch.object(probe,'stop_process'),patch.object(probe,'archive',side_effect=archive_fn) as archive, \
             patch.object(probe,'write',side_effect=write_fn or write), \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=probe.execute(self.root,Path('synthetic-dependency'),time.monotonic())
        return code,archive
    def test_fake_source_adapter_worker_and_independent_parent_replay(self):
        self.assertEqual(self.worker(),0)
        result=probe.verify_worker_result(self.root,self.plan,0,'synthetic-0')
        self.assertEqual(self.plan['versions']['torch'],'2.8.0')
        self.assertEqual(json.loads((self.root/'workers/0/ready.json').read_bytes())['torch'],'2.8.0+cu128')
        self.assertEqual(result['accounting']['completed_forwards'],7)
        self.assertEqual(result['accounting']['reserved_physical_input_tokens'],168)
        self.assertEqual(result['scientific_task_runs'],0)
    def test_parent_accepts_four_exact_fake_control_receipts(self):
        code,archive=self.coordinator();self.assertEqual(code,0);archive.assert_called_once()
        terminal=json.loads((self.root/'terminal.json').read_bytes())
        self.assertEqual(len(terminal['results']),4);self.assertEqual(terminal['outcome'],'complete')
    def cache_launch(self,command,**_kwargs):
        rank=int(command[command.index('--rank')+1]);code=self.worker(rank)
        cache=self.root/'workers'/str(rank)/'unsloth_compiled_cache';cache.mkdir()
        (cache/'UnslothAlignPropTrainer.py').write_text('raise AssertionError("literal cache must not execute")\n')
        return Process(code)
    def test_real_archive_retains_all_four_fake_worker_evidence_without_generated_cache(self):
        real_archive=probe.archive
        code,call=self.coordinator(launch=self.cache_launch,archive_fn=real_archive)
        self.assertEqual(code,0);call.assert_called_once()
        with zipfile.ZipFile(self.root.parent/(self.plan['screen_id']+'.zip')) as stream:
            self.assertFalse(any('unsloth_compiled_cache' in name for name in stream.namelist()))
            terminal=json.loads(stream.read('terminal.json'))
            self.assertEqual(terminal['outcome'],'complete');self.assertEqual(len(terminal['results']),4)
            self.assertTrue(terminal['cleanup']['all_producers_stopped'])
            self.assertNotIn('diagnostic-only.json',stream.namelist())
            for rank in range(4):
                for name in ('ready.json','result.json','events.jsonl','stdout.log','stderr.log','launch-reservation.json'):
                    relative=f'workers/{rank}/{name}'
                    self.assertEqual(stream.read(relative),(self.root/relative).read_bytes())
    def test_unknown_neighbor_still_fails_real_archive_and_preserves_diagnostic_only_fallback(self):
        from tools.nvarc_probe_bootstrap import finalize
        original=self.root;self.root=self.root.parent/self.plan['screen_id'];original.rename(self.root)
        def launch(command,**kwargs):
            process=self.cache_launch(command,**kwargs)
            (self.root/'workers/0/unrecognized.py').write_text('literal unknown neighbor')
            return process
        code,call=self.coordinator(launch=launch,archive_fn=probe.archive)
        self.assertEqual(code,1);call.assert_called_once()
        destination=self.root.parent/(self.plan['screen_id']+'.zip');self.assertFalse(destination.exists())
        terminal=json.loads((self.root/'terminal.json').read_bytes())
        self.assertEqual(terminal['outcome'],'failed');self.assertEqual(len(terminal['results']),4)
        self.assertEqual(terminal['errors'][-1]['phase'],'probe-archive')
        self.assertIn('workers/0/unrecognized.py',terminal['errors'][-1]['message'])
        (self.root/'coordinator-output.log').write_text('literal CPU-only caught archive failure')
        observation={'returncode':code,'confirmed_stopped':True,'timed_out':False}
        result=finalize(self.root,observation,hashlib.sha256((self.root/'screen.json').read_bytes()).hexdigest())
        self.assertTrue(result['diagnostic_only_archive_created'])
        with zipfile.ZipFile(destination) as stream:
            marker=json.loads(stream.read('diagnostic-only.json'))
            self.assertFalse(marker['complete_runtime_evidence']);self.assertFalse(marker['candidate_qualification'])
            self.assertFalse(any(name.startswith('workers/') for name in stream.namelist()))
            self.assertEqual(json.loads(stream.read('terminal.json')),terminal)
    def test_cache_does_not_bypass_unconfirmed_producer_stop(self):
        failure=RuntimeError('literal unconfirmed producer stop')
        failure.cleanup_report={'all_producers_stopped':False}
        with patch.object(probe,'cleanup_workers',side_effect=failure):
            code,call=self.coordinator(launch=self.cache_launch,archive_fn=probe.archive)
        self.assertEqual(code,1);call.assert_not_called()
        self.assertFalse((self.root.parent/(self.plan['screen_id']+'.zip')).exists())
    def test_parent_rejects_wrong_binding_zero_controls_and_forbidden_work(self):
        def launch(command,**_kwargs):
            rank=int(command[command.index('--rank')+1]);self.worker(rank)
            path=self.root/'workers'/str(rank)/'result.json';result=json.loads(path.read_bytes())
            result['binding']['rank']=999;result['accounting']['completed_forwards']=0;result['scientific_task_runs']=99
            write(path,result);return Process()
        code,archive=self.coordinator(launch=launch);self.assertEqual(code,1);archive.assert_called_once()
        self.assertEqual(json.loads((self.root/'terminal.json').read_bytes())['outcome'],'failed')
    def test_independent_wrong_ready_cache_reset_and_counter_rejections(self):
        self.worker();directory=self.root/'workers/0'
        for name,mutate in [('ready.json',lambda v:v.update(uuid='unassigned')),
            ('ready.json',lambda v:v.update(rank=False)),
            ('result.json',lambda v:v.update(optimizer_steps=1)),
            ('result.json',lambda v:v['binding'].update(rank=False)),
            ('result.json',lambda v:v['post_reset_control'].update(additional_model_calls=True)),
            ('result.json',lambda v:(v['telemetry']['inclusive_host_seconds'].update(generation=123),
                v['telemetry']['exclusive_host_seconds'].update(generation=0))),
            ('result.json',lambda v:v['telemetry']['inclusive_host_seconds'].update(
                load=v['telemetry']['elapsed_host_seconds']+2)),
            ('result.json',lambda v:v['post_reset_control']['prefill'][0].__setitem__(0,9)),
            ('result.json',lambda v:v.update(reset_inventory_digest='sha256:'+'0'*64))]:
            path=directory/name;original=path.read_bytes();value=json.loads(original);mutate(value);write(path,value)
            with self.assertRaises(RuntimeError):probe.verify_worker_result(self.root,self.plan,0,'synthetic-0')
            path.write_bytes(original)
        (directory/'ready.json').unlink()
        with self.assertRaises(FileNotFoundError):probe.verify_worker_result(self.root,self.plan,0,'synthetic-0')
    def test_rehashed_wrong_physical_control_sequence_is_rejected(self):
        self.worker();path=self.root/'workers/0/events.jsonl'
        rows=[json.loads(line) for line in path.read_bytes().splitlines()]
        rows[0]['batch_shape']=[4,8]
        head=digest(probe.probe_binding(self.plan,0))
        for row in rows:
            row['previous']=head;row['digest']=digest({k:v for k,v in row.items() if k!='digest'});head=row['digest']
        path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
        with self.assertRaisesRegex(RuntimeError,'forward/token/cache/position'):
            probe.verify_worker_result(self.root,self.plan,0,'synthetic-0')
    def test_worker_memory_rejection_preserves_structured_failure_after_seven_calls(self):
        self.assertEqual(self.worker(peak=self.plan['maximum_worker_cuda_allocated_bytes']+1),1)
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['outcome'],'failed');self.assertEqual(result['accounting']['completed_forwards'],7)
        self.assertIn('memory cap',result['errors'][0]['message'])
    def test_terminal_write_failure_archives_and_retains_fallback(self):
        def failing(path,value):
            if Path(path).name=='terminal.json':raise OSError('synthetic disk fault')
            write(path,value)
        code,archive=self.coordinator(write_fn=failing);self.assertEqual(code,1);archive.assert_called_once()
        value=json.loads((self.root/'terminal-fallback.json').read_bytes())
        self.assertEqual(value['outcome'],'failed');self.assertEqual(value['secondary_errors'][0]['phase'],'probe-terminal')


class ResourceAttachmentTests(unittest.TestCase):
    def test_exact_metadata_omitted_or_extra_competition_rejected_even_with_rehashed_manifest(self):
        for sources in ([],['unrelated'],[mounts.COMPETITION_SOURCE,'unrelated']):
            with tempfile.TemporaryDirectory() as tmp:
                plan,raw=probe_fixture();package=Path(tmp)/'package';stage.stage(package,plan,raw)
                path=package/'kernel/kernel-metadata.json';metadata=json.loads(path.read_bytes())
                self.assertEqual(metadata['competition_sources'],[mounts.COMPETITION_SOURCE])
                metadata['competition_sources']=sources;write(path,metadata)
                index=package/'package-manifest.json';manifest=json.loads(index.read_bytes())
                manifest['files_sha256']['kernel/kernel-metadata.json']=hashlib.sha256(path.read_bytes()).hexdigest();write(index,manifest)
                with self.assertRaisesRegex(RuntimeError,'exact private offline probe metadata'):
                    stage.preflight(package)
    def test_mount_inspection_never_lists_or_opens_competition_members(self):
        plan={'resource_attachment':mounts.attachment(stage.SCIENTIFIC_SCOPE)}
        with patch.object(Path,'is_dir',return_value=True),patch.object(Path,'is_symlink',return_value=False), \
             patch.object(Path,'open',side_effect=AssertionError('competition file opened')), \
             patch.object(Path,'iterdir',side_effect=AssertionError('competition members listed')):
            value=mounts.verify_mount(plan,stage.SCIENTIFIC_SCOPE)
        self.assertEqual(value['competition_files_opened'],0);self.assertFalse(value['competition_directory_members_listed'])
    def test_missing_wrong_extra_and_solution_reads_policy_rejected(self):
        value=mounts.attachment(stage.SCIENTIFIC_SCOPE)
        for change in ({'competition_sources':[]},{'competition_sources':['unrelated']},
            {'competition_sources':[mounts.COMPETITION_SOURCE,'unrelated']},{'competition_mount':'/unbound'},
            {'competition_files_allowed':['synthetic-forbidden-member']},{'scientific_input_scope':'hidden inputs'}):
            with self.assertRaisesRegex(RuntimeError,'exact resource-only'):
                mounts.validate_attachment({**value,**change},stage.SCIENTIFIC_SCOPE)
        with patch.object(Path,'is_dir',return_value=False),patch.object(Path,'is_symlink',return_value=False), \
             self.assertRaisesRegex(RuntimeError,'exact four-L4'):
            mounts.verify_mount({'resource_attachment':value},stage.SCIENTIFIC_SCOPE)


class ProbeTests(unittest.TestCase):
    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_actual_source_adapter_positive_contract_with_closed_control_scope(self):
        _load_linux_runtime()
        from types import SimpleNamespace
        from tools.nvarc_public_eval import PhaseTelemetry
        adapter=control_adapter(SimpleNamespace(device='synthetic-cpu'),SimpleNamespace(),lambda *_args,**_kwargs:None,PhaseTelemetry())
        with adapter.scope('control'):self.assertEqual(adapter.active,'control')
        for phase in ('generation','verification'):
            with self.assertRaisesRegex(RuntimeError,'probe cannot enter'):
                with adapter.scope(phase):pass

    def test_inert_closed_probe_package_has_zero_scientific_task_runs(self):
        screen,plans,payload=fixture();plan=plans['interleaved-r1']
        config={key:plan[key] for key in CONFIG_FIELDS};config['native_source_learning_rates']=plan['native_source_learning_rates']
        external={name:payload[name] for name in EXTERNAL_FILES};external['verified-tokenizer.json']=b'{}'
        probe,raw=stage.construct('stage4-e10-probe-synthetic','0'*40,external,config,
            json.loads(payload['material-contract.json']),fixture=True)
        self.assertEqual((probe['maximum_forwards'],probe['maximum_physical_input_tokens'],probe['scientific_task_runs']),(28,672,0))
        self.assertEqual(probe['optimizer_steps'],0);self.assertEqual(probe['generations'],0)
        self.assertEqual(probe['worker_ids'],['0','1','2','3'])
        with tempfile.TemporaryDirectory() as tmp:
            result=stage.stage(Path(tmp)/'package',probe,raw)
            self.assertFalse(result['approved_for_runtime']);self.assertFalse(result['gpu_probe_run'])
            stage.preflight(Path(tmp)/'package',expected_manifest_sha256=result['package_manifest_sha256'])
            with self.assertRaisesRegex(RuntimeError,'admitted'):
                stage.verify_runtime(Path(tmp)/'package/runtime',require_approved=True)

    @requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
    def test_source_cache_and_reset_token_ceilings(self):
        _load_linux_runtime()
        events=[]
        for index,width in enumerate((9,1,1,1,11,10,9),1):
            events.extend([{'event':'forward_reserved','call_id':index,'phase':'control','physical_input_tokens':4*width},
                           {'event':'forward_completed','call_id':index,'phase':'control'}])
        self.assertEqual(verify_observations(events),{'reserved_forwards':7,'completed_forwards':7,'reserved_physical_input_tokens':168})
        with self.assertRaisesRegex(RuntimeError,'ceilings'):
            verify_observations(events+[{'event':'forward_reserved','call_id':8,'phase':'control','physical_input_tokens':4}])
        with self.assertRaisesRegex(RuntimeError,'ceilings'):
            verify_observations([{'event':'forward_reserved','call_id':1,'phase':'generation','physical_input_tokens':4}])


class CurrentResourceAdmissionTests(unittest.TestCase):
    def admission(self):
        from datetime import datetime,timezone
        return {'format':'irisx/stage4-native-probe-resource-admission-v2',
            'probe_id':'stage4-e10-probe-synthetic','paid_usd_ceiling':0,
            'quota_hours_available':3.,'allocated_gpu_hours_per_quota_hour':1.,
            'quota_observed_at':datetime.now(timezone.utc).isoformat(),
            'provider_session_seconds':1800,'private':True,'internet':False,
            'rules_materials_review_ref':'bounded synthetic probe approval and exact dependency proof',
            'current_resource_reconciliation':{'quota_snapshot_sha256':'a'*64,
                'provider_reserved_seconds':0.,'campaign_pending_actions':0,
                'historical_sessions_terminal_verified':False,
                'scope':'current-provider-quota-and-local-campaign-only'}}
    def test_current_occupancy_does_not_claim_historical_terminal_states(self):
        value=self.admission();stage.validate_resource(value,{'screen_id':value['probe_id']})
        self.assertFalse(value['current_resource_reconciliation']['historical_sessions_terminal_verified'])
    def test_pending_reserved_opaque_and_fabricated_historical_claims_rejected(self):
        for key,bad in [('provider_reserved_seconds',1),('provider_reserved_seconds',False),
            ('campaign_pending_actions',1),('campaign_pending_actions',False),
            ('historical_sessions_terminal_verified',True),('quota_snapshot_sha256','x'),
            ('scope','all historical sessions complete')]:
            with self.subTest(key=key,bad=bad):
                value=self.admission();value['current_resource_reconciliation'][key]=bad
                with self.assertRaises(RuntimeError):stage.validate_resource(value,{'screen_id':value['probe_id']})
        value=self.admission();value['prior_sessions_reconciled']=True
        with self.assertRaises(RuntimeError):stage.validate_resource(value,{'screen_id':value['probe_id']})


if __name__=='__main__':unittest.main()
