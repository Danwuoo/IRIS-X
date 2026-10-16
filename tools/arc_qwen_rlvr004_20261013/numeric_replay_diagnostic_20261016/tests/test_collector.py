"""Offline collector fixtures with real unchanged ZIP/terminal verification.

Provider and external wrapper authority are explicit test doubles. Synthetic
metadata never grants launch, native closure, numerical or scientific authority.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

HERE=Path(__file__).resolve().parents[1]
TOOL=HERE.parent
PATH=HERE/'publication/rl_collect.py'
HELPERS=TOOL/'release/terminal-consumer'

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def need(ok,code):
    if not ok: raise ValueError(code)
def load():
    m=types.ModuleType('numeric_collector_test');m.__file__=str(PATH)
    exec(compile(PATH.read_bytes(),str(PATH),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(m))
    m.need=need;m.sha=sha;m.canonical=canonical;m.re=re;m.TERMINAL={'COMPLETE','ERROR','CANCELLED'}
    m.read=lambda p,cap=4*1024**2: Path(p).read_bytes()
    m.file_sha=lambda p:sha(Path(p).read_bytes())
    def verified(p,digest,bytes_=None,cap=4*1024**2):
        raw=Path(p).read_bytes();need(len(raw)<=cap and sha(raw)==digest,'fixture_verified')
        if bytes_ is not None:need(len(raw)==bytes_,'fixture_bytes')
        return raw
    m.verified=verified;m.obj=lambda p,cap=4*1024**2:json.loads(m.read(p,cap))
    m.secure_path=lambda p:Path(p)
    m.relative=lambda p:need(type(p)is str and p and not p.startswith('/') and '..' not in Path(p).parts,'fixture_relative')
    return m


def complete_documents(m):
    model={k:True for k in ('closed','future_operations_blocked','model_references_released','device_synchronized','model_stopped','ledger_settled')}
    model['fatal_native_state']=None
    outer={'safe_closure':True,'model_stopped':True,'worker_exited':True,'worker_session_empty':True,
           'worker_returncode':0,'inner_closure':{'status':'complete','model_closure':model}}
    owned={'format':'owned-rl-result-v1','status':m.NUMERIC_COMPLETE,'run_purpose':m.NUMERIC_PURPOSE,
           'scope':'training-only-numeric-diagnostic','fixture':False,'diagnostic_complete':True,
           'terminal_error':None,'source_integrity_error':None,'PUBLIC_score':None,'parent_scoring_ref':None,
           'checkpoint_export':None}
    owned.update({k:False for k in ('production_admitted','comparison_complete','public_benchmark_evidence_eligible','scientific_goal_met','ARC_or_14B_efficacy_claim')})
    arm={'adapter_sha256':'a'*64,'updates':{'anchor_updates':256,'rl_updates':0,'control_updates':0}}
    flow={'format':'owned-training-numeric-diagnostic-v1','run_purpose':m.NUMERIC_PURPOSE,
          'status':m.NUMERIC_COMPLETE,'diagnostic_complete':True,'production_admitted':False,
          'ARC_or_PUBLIC_efficacy_claim':False,'comparison_complete':False,'no_C_dev_holdout_PUBLIC':True,
          'TTT':False,'dev_selection':None,'holdout':None,'public':None,'comparison':None,
          'original_planned_attempts':256,'requested_attempts':64,'unrequested_original_panel_attempts':192,
          'arms':{'A':deepcopy(arm),'B':deepcopy(arm)},
          'stage_status':{k:'not-requested-by-diagnostic' for k in ('C','dev','holdout','PUBLIC')}}
    replays=[{'parent_id':'p'+str(i//8),'trajectory_id':'trajectory'+str(i),
        'original_token_replay':True,'training_mode':True,'log_pi':[-1.],'log_mu':[-1.1],
        'nonforced_tokens':{'tokens':1,'max_abs_gap':.1,'p95_abs_gap':.1,'unclipped_fraction':1.,'clipped_tokens':0}}
        for i in range(64)]
    gate={'admitted':False,'failures':['original-gap'],'gate':{
        'maximum_absolute_gap':.20,'minimum_unclipped_fraction':1.,'maximum_replay_seconds':30.,
        'maximum_peak_bytes':72*1024**3,'fixture_only':False,'maximum_p95_gap':.05,
        'maximum_reserved_bytes':80*1024**3,'maximum_batch_replay_backward_seconds':600.},
        'per_trajectory':deepcopy(replays),'per_parent_ids':['p'+str(i) for i in range(8)]}
    update={'status':'intentionally-no-update','optimizer_dispatched':False,'optimizer_committed':False,
            'rollback':{'restored':True},'within_original_batch_deadline':True,'numeric_shadow_complete':True,
            'replays':replays,'original_numeric_gate':deepcopy(gate),'numerical_gate':deepcopy(gate)}
    shadow={'schema':'numeric-shadow-training-only-v1','complete':True,'status':'complete','state_preserved':True,
            'optimizer_commit_allowed':False,'gate_inputs_replaced':False,'model_forward_calls':8,'head_projection_calls':0}
    wrappers={'closure_valid':True,'operational':True,'runtime_tree_link_checked':True,
              'terminal_status':'diagnostic','model_closure_verified_by_this_helper':False}
    return owned,flow,update,shadow,outer,wrappers


class CompletionTests(unittest.TestCase):
    def setUp(self):self.m=load();self.docs=complete_documents(self.m)
    def test_original_failed_gate_can_complete_diagnostic_without_passing_gate(self):
        self.assertTrue(self.m.numeric_completion(*self.docs))
        self.assertFalse(self.docs[2]['original_numeric_gate']['admitted'])
    def test_gate_pass_still_no_commit(self):
        for key in ('original_numeric_gate','numerical_gate'):self.docs[2][key].update(admitted=True,failures=[])
        self.assertTrue(self.m.numeric_completion(*self.docs))
        self.docs[2]['optimizer_committed']=True
        with self.assertRaises(ValueError):self.m.numeric_completion(*self.docs)
    def test_each_closure_flag_and_exact_returncode(self):
        for key in self.docs[4]['inner_closure']['model_closure']:
            rows=deepcopy(self.docs)
            rows[4]['inner_closure']['model_closure'][key]=False if key!='fatal_native_state' else 'unknown'
            with self.subTest(key=key),self.assertRaises(ValueError):self.m.numeric_completion(*rows)
        for value in (False,0.,1,None):
            rows=deepcopy(self.docs);rows[4]['worker_returncode']=value
            with self.subTest(returncode=value),self.assertRaises(ValueError):self.m.numeric_completion(*rows)
    def test_false_scope_and_counts_rejected(self):
        changes=[(1,'TTT',True),(1,'public',{}),(1,'no_C_dev_holdout_PUBLIC',False),
                 (1,'requested_attempts',True),(1,'requested_attempts',64.),(1,'original_planned_attempts',64),
                 (2,'optimizer_dispatched',True),(2,'within_original_batch_deadline',False),
                 (2,'replays',[{}]*63),(3,'state_preserved',False),(3,'model_forward_calls',9),
                 (3,'model_forward_calls',True),(3,'head_projection_calls',1),(3,'gate_inputs_replaced',True)]
        for index,key,value in changes:
            rows=deepcopy(self.docs);rows[index][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.m.numeric_completion(*rows)
    def test_missing_shadow_schema_and_empty_gate_rejected(self):
        for mode in ('schema','empty_gate','non_dictionary_replay'):
            rows=deepcopy(self.docs)
            if mode=='schema':rows[3].pop('schema')
            elif mode=='empty_gate':rows[2]['original_numeric_gate']=rows[2]['numerical_gate']={}
            else:
                rows[2]['replays']=[None]*64
                rows[2]['original_numeric_gate']['per_trajectory']=rows[2]['numerical_gate']['per_trajectory']=[None]*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.m.numeric_completion(*rows)
    def test_finite_json_parser_rejects_overflow_and_constants(self):
        for raw in (b'{"x":1e999}',b'{"x":-1e999}',b'{"x":NaN}',b'{"x":Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):self.m.strict_json(raw)

    def test_original_gate_replacement_and_adapter_change_rejected(self):
        self.docs[2]['numerical_gate']['admitted']=True
        with self.assertRaises(ValueError):self.m.numeric_completion(*self.docs)
        self.docs=complete_documents(self.m);self.docs[1]['arms']['B']['adapter_sha256']='b'*64
        with self.assertRaises(ValueError):self.m.numeric_completion(*self.docs)
    def test_incomplete_does_not_invent_missing_reports(self):
        owned=self.docs[0];owned['status']=self.m.NUMERIC_INCOMPLETE;owned['diagnostic_complete']=False
        self.assertFalse(self.m.numeric_completion(owned,None,None,None,{},{}))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=load();m=self.m;m.DOWNLOADS=self.root/'downloads';m.DOWNLOADS.mkdir()
        self.prefix='irisx-qwen14b-numeric-diagnostic-20261016-run001';self.outer=self.prefix+'-launcher'
        self.remote='/kaggle/working/'+self.prefix;self.source='/kaggle/working/irisx-qwen14b-numeric-diagnostic-20261016-source001'
        self.pub=self.root/'publication';self.pub.mkdir();m.publication_root=lambda:self.pub
        self.launch={'saved_source':{'sha256':'b'*64}}
        (self.pub/'notebook-rlvr004-receipt.json').write_bytes(canonical(self.launch))
        self.jit={k:canonical({'synthetic':k}) for k in ('active-finalized.ipynb','operator.json','original-request.json','parent-private-scorer.json')}
        self.inputs={'source.zip':b'synthetic opaque source bytes','MATERIAL-REVIEW.json':b'{}'}
        for name,raw in self.inputs.items():(self.root/name).write_bytes(raw)
        files={'source.py':'c'*64};source_sha=sha(json.dumps(sorted(files.items()),sort_keys=True,separators=(',',':')).encode())
        self.contract={'source_sha256':source_sha,
            'material_review':{'path':'MATERIAL-REVIEW.json','sha256':sha(self.inputs['MATERIAL-REVIEW.json'])},
            'source_archive':{'path':'source.zip','sha256':sha(self.inputs['source.zip'])}}
        self.manifest={'consumer_contract':self.contract,'runtime_source_sha256':source_sha,
            'terminal_contract':{'evidence_path':self.prefix+'.evidence.zip','terminal_path':self.prefix+'.evidence.zip.terminal.json'}}
        helper_files={n:sha((HELPERS/n).read_bytes()) for n in ('consumer/safe_io.py','streaming_zip.py','terminal.py')}
        m.transport=types.SimpleNamespace(ACTIVE_VERSION=45,monitor_gate=lambda args:{'consumer_files':helper_files},
            check_finalization=lambda *args:self.jit,row=lambda *args:{'source_parent':self.source},
            descriptor_at=lambda root,d:(root/d['path']).read_bytes())
        self.args=types.SimpleNamespace(manifest=str(self.root/'publication-manifest.json'),manifest_sha='d'*64,consumer_root=str(HELPERS))
        self.f={'predispatch_epoch':1000}
        snap={'version':45,'status':'COMPLETE','source_sha256':'b'*64,'gpu_stop':False,
              'metadata_before_sha256':'e'*64,'metadata_sha256':'f'*64,'observed_epoch':1100}
        self.receipt={'numeric_output_version':45,'manifest_sha256':'d'*64,
            'launch_receipt_sha256':m.file_sha(self.pub/'notebook-rlvr004-receipt.json'),
            'before':snap,'after':{**snap,'observed_epoch':1110},'collected_epoch':1120,'checkpoint_archive_observation':None}
        owned,flow,update,shadow,outer,wrappers=complete_documents(m)
        clock={'fixture':False,'original_epoch':1000,'origin_monotonic':1.}
        outer['original_clock']=clock
        self.members={}
        def add(name,value):
            raw=canonical(value);self.members[name]=raw
            return {'path':self.remote+'/'+name,'file_sha256':sha(raw)}
        shadow_ref=add('experiment/numeric-shadow.json',shadow);flow['numeric_shadow_ref']=shadow_ref;update['numeric_shadow_ref']=shadow_ref
        flow['batch_schedule']=[['p'+str(i*8+j) for j in range(8)] for i in range(4)]
        flow['audit_sweeps']=[]
        for index,parents in enumerate(flow['batch_schedule']):
            status='intentionally-no-update' if index==0 else 'not-requested-by-diagnostic'
            batch={'planned_attempts':64,'parent_ids':parents,'rows':[
                {'parent_id':parent,'slot':slot,'trajectory':None,'reward':None,'eligible':False,
                 'status':'not-reached','reason':'not-requested-by-diagnostic'} for parent in parents for slot in range(8)]}
            summary={'planned_attempts':64,'not_reached':0 if index==0 else 64}
            audit={'batch_index':index,'parent_ids':parents,'batch':batch,'summary':summary,
                   'update':update if index==0 else None,'status':status}
            ref=add(f'experiment/audit/sweep-{index}.json',audit)
            flow['audit_sweeps'].append({**ref,'batch_index':index,'parent_ids':parents,'summary':summary,
                'status':status,'update_status':update['status'] if index==0 else None,'durability_ref':None})
        flow['audit_batches']=deepcopy(flow['audit_sweeps'])
        flow_ref=add('experiment/result.json',flow);owned['result_ref']=flow_ref;outer['inner_closure']['result_ref']=flow_ref
        mapping={'outer_notebook':('outer_notebook.raw',self.jit['active-finalized.ipynb'],self.remote+'-launcher/outer.ipynb'),
            'operator':('operator.raw',self.jit['operator.json'],self.remote+'-launcher/operator.json'),
            'original_request':('original_request.raw',self.jit['original-request.json'],self.remote+'-launcher/original-request.json'),
            'parent_scorer':('parent_scorer.raw',self.jit['parent-private-scorer.json'],self.remote+'-launcher/parent-private-scorer.json'),
            'material_review':('material_review.raw',self.inputs['MATERIAL-REVIEW.json'],self.source+'/release/MATERIAL-REVIEW.json'),
            'source_archive':('source_archive.zip',self.inputs['source.zip'],self.source+'/source.zip')}
        bootstrap={'original_epoch':1000,'raw_source_sha256':source_sha,'scope':'production-rl-abc','role':'rl-abc'}
        lineage={'format':'owned-rl-parent-lineage-copies-v1','all_original_bytes_retained':True,'independent_approval_claim':False,'files':{}}
        for key,(name,raw,path) in mapping.items():
            self.members['parent-lineage/'+name]=raw
            if key=='parent_scorer':bootstrap['parent_scorer_sha256']=sha(raw)
            else:bootstrap[key]={'path':path,'file_sha256':sha(raw)}
            lineage['files'][key]={'bytes':len(raw),'matches_original_binding':True,'original':{'path':path,'file_sha256':sha(raw)},'retained':{'path':self.remote+'/parent-lineage/'+name,'file_sha256':sha(raw)}}
        owner={'format':'owned-rl-worker-request-v1','run_purpose':m.NUMERIC_PURPOSE,'scope':'production-rl-abc',
            'config':{'fixture':False},'output_root':self.remote,'clock':clock,'sources':files,'bootstrap':bootstrap}
        for name,value in (('owner-request.json',owner),('owner-clock.json',clock),('outer-closure.json',outer),('owned-result.json',owned),
                           ('artifact-inventory.json',{}),('release-source-inventory.json',{'files':files,'source_sha256':source_sha}),('parent-lineage/index.json',lineage)):
            add(name,value)
        self.wrappers=wrappers;self.outer_doc=outer
        self.materialize()
    def materialize(self):
        root=self.m.DOWNLOADS/self.prefix;root.mkdir(exist_ok=True)
        for name in ('owner-request.json','owner-clock.json','outer-closure.json','owned-result.json','artifact-inventory.json'):(root/name).write_bytes(self.members[name])
        archive=self.m.DOWNLOADS/self.manifest['terminal_contract']['evidence_path']
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
            for name,raw in self.members.items():
                info=zipfile.ZipInfo(name,(2026,10,16,0,0,0));info.external_attr=0o100600<<16;z.writestr(info,raw)
        with self.m.diagnostic_archive_helpers(self.args) as (t,z):
            actual=z.verify_evidence_zip(archive)
            actual['path']=self.remote+'.evidence.zip'
            terminal={'format':'owned-rl-evidence-terminal-v1','status':'diagnostic','archive_complete':True,
                'mode':'runtime-reload-bound','caps':t.CAPS,'model_closed':False,'checkpoint_archive_observation':None,
                'authorization':{'source_sha256':self.contract['source_sha256'],
                    'owner_request_ref':{'file_sha256':sha(self.members['owner-request.json'])},
                    'outer_closure_ref':{'file_sha256':sha(self.members['outer-closure.json'])},
                    'worker_exited':True,'worker_session_empty':True,'kind':'live-owned-process-termination',
                    'original_clock':{'origin_monotonic':1.},'original_deadlines':{'absolute':5000.}},
                'started_monotonic':20.,'finished_monotonic':21.,'terminal_metadata_may_finish_after_absolute_deadline':True,
                'archive':actual,'original_artifact_inventory':actual['members']['artifact-inventory.json']}
            terminal.update({k:False for k in ('scientific_goal_met','production_admitted','model_success_claim','independent_checkpoint_tensor_verification','external_archive_sha256_independently_verified')})
        terminal_path=self.m.DOWNLOADS/self.manifest['terminal_contract']['terminal_path'];terminal_path.write_bytes(canonical(terminal))
        self.terminal=terminal;self.present={p.name:{'sha256':self.m.file_sha(p),'bytes':p.stat().st_size} for p in (archive,terminal_path)}
    def verify(self):
        return self.m.numeric_session_diagnostic(self.manifest,self.args,self.f,self.receipt,self.terminal,self.present,self.prefix,self.outer,self.wrappers)
    def test_real_stored_archive_terminal_and_numeric_references(self):
        result=self.verify();self.assertEqual(result['status'],'NUMERIC_DIAGNOSTIC_COMPLETE')
        self.assertTrue(result['engineering_diagnostic_complete']);self.assertFalse(result['terminal_export_model_closed'])
        self.assertFalse(result['consumer_admitted']);self.assertIsNone(result['public_score']);self.assertFalse(result['billing_verified'])
        self.assertEqual(result['numeric_shadow_artifact']['sha256'],sha(self.members['experiment/numeric-shadow.json']))
    def test_changed_report_bytes_with_rebuilt_transport_still_fail_internal_reference(self):
        self.members['experiment/numeric-shadow.json']=canonical({'complete':True});self.materialize()
        with self.assertRaisesRegex(ValueError,'artifact_hash_reference'):self.verify()
    def test_changed_compact_owned_bytes_with_unchanged_archive_rejected(self):
        p=self.m.DOWNLOADS/self.prefix/'owned-result.json';v=json.loads(p.read_bytes());v['diagnostic_complete']=False;p.write_bytes(canonical(v))
        with self.assertRaisesRegex(ValueError,'compact_byte_link'):self.verify()
    def test_original_source_clock_and_provider_bracket_enforced(self):
        self.receipt['after']['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'provider_bracket'):self.verify()
    def test_report_path_cannot_escape_fixed_member(self):
        v=json.loads(self.members['owned-result.json']);v['result_ref']['path']=self.remote+'/other/result.json';self.members['owned-result.json']=canonical(v);self.materialize()
        with self.assertRaises(ValueError):self.verify()
    def test_checkpoint_or_benchmark_claim_rejected(self):
        self.terminal['checkpoint_archive_observation']={'present':True}
        with self.assertRaisesRegex(ValueError,'no_checkpoint'):self.verify()
    def test_source_bound_explicit_gpu_stop_preserved(self):
        self.members['child-driver-resolution.json']=canonical({'format':'owned-rl-child-driver-resolution-v1','status':'failed',
            'stage':'observe-cuda-visibility','native_model_loaded':False,'full_native_admission_still_required':True,
            'GPU_fit_or_throughput_claim':False,'cuda_visibility':{'cuda_available':False,'device_count':0}})
        self.materialize();self.assertTrue(self.verify()['source_bound_gpu_unavailable'])
    def test_complete_collect_writes_distinct_engineering_terminal_without_consumer(self):
        m=self.m;m.OUT=self.root/'out';m.OUT.mkdir();m.STOP=self.root/'STOP.json';m.REF='synthetic/reference'
        t=self.manifest['terminal_contract'];t['archive_caps']={'evidence_archive_bytes':1024**2};t['checkpoint_path']=self.prefix+'/checkpoints.zip'
        names=[t['terminal_path'],t['evidence_path']]
        for name in ('owner-request.json','owner-clock.json','outer-closure.json','owned-result.json','artifact-inventory.json'):
            names.append(self.prefix+'/'+name)
        caps={name:1024**2 for name in names}
        m.output_paths=lambda manifest:(self.prefix,self.outer,caps,set(names))
        m.collect_preowned_failure=lambda *args:(None,[],[])
        m.fetch_selected=lambda provider,name,*args:{'provider_path':name,'bytes':(m.DOWNLOADS/name).stat().st_size,'sha256':m.file_sha(m.DOWNLOADS/name)}
        m.checkpoint_observation=lambda *args:None
        m.poll=lambda *args:self.receipt['after']
        m.wrapper_gate=lambda *args:self.wrappers
        m.event=lambda *args:None
        def write_new(path,value):
            raw=value if type(value)is bytes else canonical(value)
            with Path(path).open('xb') as stream:stream.write(raw)
            return {'path':str(path),'bytes':len(raw),'sha256':sha(raw)}
        m.write_new=write_new;m.descriptor=lambda path:{'path':str(path),'bytes':path.stat().st_size,'sha256':m.file_sha(path)}
        def forbidden(*args,**kwargs):raise AssertionError('scientific consumer must never execute')
        m.assemble_consumer_envelope=m.validate_received=m.validation_gate=forbidden
        provider=types.SimpleNamespace(ensure_read_auth=lambda:None)
        result=m.collect(provider,self.manifest,self.launch,{'dispatch_epoch':1001},self.f,self.args,self.receipt['before'])
        self.assertEqual(result['status'],'NUMERIC_DIAGNOSTIC_COMPLETE')
        self.assertTrue((m.OUT/'TERMINAL-DIAGNOSTIC.json').is_file())
        self.assertFalse((m.OUT/'AUTHENTICATED-COLLECTION.json').exists())
        self.assertFalse(result['consumer_admitted'])

    def replace_flow(self,flow):
        raw=canonical(flow);self.members['experiment/result.json']=raw
        ref={'path':self.remote+'/experiment/result.json','file_sha256':sha(raw)}
        owned=json.loads(self.members['owned-result.json']);owned['result_ref']=ref;self.members['owned-result.json']=canonical(owned)
        outer=json.loads(self.members['outer-closure.json']);outer['inner_closure']['result_ref']=ref;self.members['outer-closure.json']=canonical(outer)
        self.materialize()
    def test_later_batch_work_rejected_even_after_all_transport_hashes_rebound(self):
        name='experiment/audit/sweep-1.json';audit=json.loads(self.members[name]);audit.update(status='updated',update={'optimizer_committed':True})
        self.members[name]=canonical(audit);flow=json.loads(self.members['experiment/result.json'])
        flow['audit_sweeps'][1].update(file_sha256=sha(self.members[name]),status='updated',update_status='updated')
        flow['audit_batches']=deepcopy(flow['audit_sweeps']);self.replace_flow(flow)
        with self.assertRaisesRegex(ValueError,'later_batches_not_requested'):self.verify()
    def test_duplicate_later_index_rejected_after_rebinding(self):
        flow=json.loads(self.members['experiment/result.json']);flow['audit_sweeps'][2]['batch_index']=1
        flow['audit_batches']=deepcopy(flow['audit_sweeps']);self.replace_flow(flow)
        with self.assertRaisesRegex(ValueError,'audit_index_order'):self.verify()
    def test_later_unrequested_slot_cannot_hide_a_trajectory(self):
        name='experiment/audit/sweep-3.json';audit=json.loads(self.members[name]);audit['batch']['rows'][0]['trajectory']={'dispatched':True}
        self.members[name]=canonical(audit);flow=json.loads(self.members['experiment/result.json'])
        flow['audit_sweeps'][3]['file_sha256']=sha(self.members[name]);flow['audit_batches']=deepcopy(flow['audit_sweeps']);self.replace_flow(flow)
        with self.assertRaisesRegex(ValueError,'unrequested_slot_has_no_work'):self.verify()

    def test_no_science_consumer_call_is_reachable_from_diagnostic_branch(self):
        tree=ast.parse(PATH.read_bytes());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect')
        calls={n.func.id for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(calls & {'assemble_consumer_envelope','validate_received','validation_gate'})

if __name__=='__main__':unittest.main()
