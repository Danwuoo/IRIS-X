"""Synthetic, offline wrapper mutation tests. No provider/model/production claims.

Optional --counterexample-root replays the separately retained genuine CPU
counterexample without changing it. That fixture is never synthesized here.
"""
from pathlib import Path
import ast, copy, hashlib, json, sys, tempfile, types, unittest

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/'support/assembly/verify_parent_wrappers.py'
SUCCESSOR=HERE/'verify_parent_wrappers.py'
ORIGINAL_SHA='c97adede45574f79d22428afc23d2184dfd6d9c1a87ddfb288830374dddefc6c'
NAMESPACES=tuple(('irisx-qwen14b-rlvr-20261012-'+s+'004','irisx-qwen14b-rlvr-20261013-'+s+'008') for s in ('environment','run','source'))
def enc(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def original_bytes():
    raw=ORIGINAL.read_bytes()
    if sha(raw)!=ORIGINAL_SHA:raise ValueError('frozen original helper differs')
    for old,new in NAMESPACES:
        if raw.count(old.encode())!=1:raise ValueError('exact inherited namespace count')
        raw=raw.replace(old.encode(),new.encode())
    return raw

def load(path,raw=None):
    m=types.ModuleType('synthetic_wrapper_'+path.stem);m.__file__=str(path)
    exec(compile(path.read_bytes() if raw is None else raw,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(m))
    return m

def ident(pid,birth,session):return dict(pid=pid,birth=birth,session=session,state='S')

class Fixture:
    """Invented document fixture; topology matches the two-scope test condition."""
    def __init__(self,root,v):
        self.root=Path(root);self.v=v;self.epoch=1000
        self.a_coord=ident(1,1,1);self.a_sup=ident(2,2,2);self.a_worker=ident(3,3,2)
        self.b_sup=ident(20,15,20);self.b_worker=ident(21,16,20)
        self.model=ident(22,17,22);self.missing=[ident(23,18,22),ident(25,20,22)];self.common=ident(24,19,22)
        self.source='/kaggle/working/irisx-qwen14b-rlvr-20261013-source008/runtime'
        self.output='/kaggle/working/irisx-qwen14b-rlvr-20261013-run008';self.launcher=self.output+'-launcher'
        self.release={'source_sha256':'a'*64,'source_archive_sha256':'b'*64,'code_manifest_sha256':'c'*64,
                      'material_pins':{'data':{'reference':'fixture/data/1'},'training':{'reference':'fixture/training/1'}}}
        self.environment={'model_config':{'model_path':'/synthetic-model-never-opened'}}
        owner={'original_epoch':self.epoch};operator={'fixture':True}
        self.jit={k:self.write(n,d) for n,k,d in (
            ('outer.ipynb','active-finalized.ipynb',{'fixture':True}),('original-request.json','original-request.json',owner),
            ('operator.json','operator.json',operator),('parent-private-scorer.json','parent-private-scorer.json',{'fixture':True}))}
        ready={'source_root':self.source,'source_sha256':'a'*64,'source_archive_path':str(Path(self.source).parent/'source.zip'),
               'source_archive_sha256':'b'*64,'manifest_sha256':'c'*64}
        prep={'format':'irisx/rlvr-parent-preparation-request-v1','ready':ready,'release':self.release,
              'finalized':{'owner_request':owner,'operator':operator},'notebook_python_executable':'/synthetic/python',
              'output_root':self.output,'input_root':'/kaggle/input','epoch':self.epoch,'launcher_root':self.launcher,'environment_root':v.ENV}
        prep_raw=self.write('preparation-request.json',prep)
        paths={'outer_notebook_path':self.launcher+'/outer.ipynb','operator_path':self.launcher+'/operator.json',
               'material_review_path':str(Path(self.source).parent/'release/MATERIAL-REVIEW.json'),
               'source_archive_path':ready['source_archive_path'],'original_request_path':self.launcher+'/original-request.json',
               'parent_scorer_path':self.launcher+'/parent-private-scorer.json'}
        config={'fixture':False,'policy_path':self.source+'/design/MEASURED-POLICY.json',
                'environment_path':str(Path(self.source).parent/'release/REVIEWED-ENVIRONMENT.json'),
                'training_root':'/kaggle/input/datasets/fixture/training/data/training','public_solver_root':'/kaggle/input/datasets/fixture/data/solver',
                'model':self.environment['model_config']}
        parent_raw=self.write('installed-parent-request.json',{'format':'irisx/rlvr-installed-parent-request-v1','source_root':self.source,
            'output_root':self.output,'config':config,'paths':paths,'result_path':self.launcher+'/result.json','source_sha256':'a'*64})
        manifest={'members':{'python/bin/python3.12':{'sha256':'d'*64}}};manifest_raw=self.write('interpreter-manifest.json',manifest)
        # This explicit synthetic fixture changes only its isolated module's
        # interpreter-manifest pin. Production successor source pins are intact.
        v.INTERPRETER_MANIFEST=sha(manifest_raw)
        command=[v.ENV+'/environment-cp312-cu128/bin/python','-I','-B','-S',v.ENV+'/environment-cp312-cu128/offline-run.py']
        installed={'python_command':command,'installed_offline':True,'reused_environment':False,
                   'actual_environment_lock_path':v.ENV+'/environment-cp312-cu128/evidence/environment-lock.json',
                   'actual_environment_lock_sha256':'e'*64,'interpreter':{'manifest_sha256':v.INTERPRETER_MANIFEST,
                   'archive_sha256':v.INTERPRETER_ARCHIVE,'executable_sha256':'d'*64,'verified_member_count':1}}
        self.write('preparation-receipt.json',{'format':'irisx/rlvr-offline-preparation-receipt-v1','source_sha256':'a'*64,
            'source_acceptance':ready,'original_epoch':self.epoch,'installed_offline':True,'offline_environment':installed,
            'model_mount':config['model']['model_path'],'public_answers_opened':False,'model_loaded_by_preparation':False,
            'storage_plan':{},'disk_admission':{},'actual_disk_free_bytes':1})
        deployment=str(Path(self.source).parent/'deployment')
        self.argv_a=['/synthetic/python','-I','-B',deployment+'/prepare_entry.py',self.launcher+'/preparation-request.json',sha(prep_raw)]
        self.argv_b=command+[deployment+'/parent_entry.py',self.launcher+'/installed-parent-request.json',sha(parent_raw)]
        self.stage('preparation',self.a_coord,self.a_sup,self.a_worker,[self.a_sup,self.a_worker,self.b_sup,self.b_worker,self.model,self.common],self.argv_a,110,190,'entire-owned-preparation-and-runtime')
        self.stage('installed-parent',self.a_worker,self.b_sup,self.b_worker,[self.b_sup,self.b_worker,self.model,self.common,*self.missing],self.argv_b,120,180,'installed-parent-with-owned-model-child')
        clock={'format':'owned-rl-original-clock-v1','original_epoch':1000,'origin_monotonic':100.,'observed_epoch':1020.,
               'observed_monotonic':120.,'session_id':'synthetic-no-provider','fixture':False,
               'offsets':{'inner':42000.,'outer':42180.,'provider':42300.,'absolute':43200.}}
        self.outer={'schema':'owned-parent-supervision-v1','fixture':False,'launch_source_sha256':'a'*64,'output_root':self.output,
                    'worker_pid':22,'worker_incarnation':{'pid':22,'start_ticks':17,'session_id':22,'process_group':22},
                    'started_monotonic':125.,'exit_observed_monotonic':170.,'original_clock':clock,
                    'original_deadlines':{k:100.+n for k,n in clock['offsets'].items()},'launch_request_sha256':'f'*64,
                    'worker_exited':True,'worker_session_empty':True,'safe_closure':True,'model_stopped':True}
        self.owned={'format':'owned-rl-result-v1','fixture':False,'source_sha256':'a'*64,'clock':clock,
                    'status':'owned-mechanics-complete-PUBLIC-sealed'}
        self.terminal={'format':'owned-rl-evidence-terminal-v1','status':'complete','output_root':self.output,'mode':'runtime-reload-bound',
            'model_closed':True,'model_success_claim':False,'scientific_goal_met':False,'production_admitted':False,'archive_complete':True,
            'archive':{},'external_bodies':{},'independent_checkpoint_tensor_verification':False,'external_archive_sha256_independently_verified':False,
            'authorization':{},'started_monotonic':171.,'caps':{},'terminal_metadata_may_finish_after_absolute_deadline':True,
            'original_artifact_inventory':{},'retained_body_exceptions':{},'checkpoint_archive_observation':None,'finished_monotonic':175.}
        self.refresh_runtime()
    def write(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);raw=enc(value);p.write_bytes(raw);return raw
    def read(self,name):return json.loads((self.root/name).read_bytes())
    def edit(self,name,fn):
        d=self.read(name);fn(d);self.write(name,d)
    def stage(self,name,coord,sup,worker,rows,argv,start,end,scope):
        rows=sorted(rows,key=lambda x:(x['birth'],x['pid']))
        def proof(root,owned):return {'format':'irisx/owned-process-closure-v1','root_identity':root,'scope':'dedicated-subreaper-tree',
            'ownership_complete':True,'closed':True,'owned_identities':owned,'remaining':[],'returncode':0,'worker_returncode':0,
            'forced':False,'reaped_identities':[],'errors':[]}
        p=proof(sup,rows);s=proof(worker,[x for x in rows if x!=sup]);s.update(format='irisx/owned-supervisor-result-v1',supervisor_identity=sup)
        prefix=name+'/owned-tree/'
        self.write(prefix+'launch.json',{'format':'irisx/owned-process-launch-v1','supervisor_identity':sup,'coordinator_identity':coord,'worker_argv':argv,'scope':'dedicated-subreaper-tree'})
        self.write(prefix+'worker-launch.json',{'format':'irisx/owned-worker-launch-v1','worker_identity':worker,'supervisor_identity':sup,'parent_death_signal':9})
        self.write(prefix+'supervisor-result.json',s);self.write(prefix+'closure.json',p)
        self.write(name+'/closure.json',{'format':'irisx/rlvr-outer-process-closure-v1','scope':scope,'deadline_epoch':self.epoch+42180,
            'started_epoch':self.epoch+start-100,'started_monotonic':start,'completed_epoch':self.epoch+end-100,'completed_monotonic':end,
            'within_deadline':True,'forced':False,'reason':None,'proof':p,'log_bytes':0,'log_cap_bytes':8*1024**2,'VM_teardown_or_billing_claim':False})
        for n in ('stdout.txt','stderr.txt'):(self.root/name/n).write_bytes(b'')
    def proof_edit(self,stage,fn,supervisor=False):
        self.edit(stage+'/owned-tree/closure.json',fn)
        self.edit(stage+'/closure.json',lambda d:d.update(proof=self.read(stage+'/owned-tree/closure.json')))
        if supervisor:self.edit(stage+'/owned-tree/supervisor-result.json',fn)
    def remove_outer_observation(self,pid):
        self.proof_edit('preparation',lambda d:d.update(owned_identities=[x for x in d['owned_identities'] if x['pid']!=pid]),True)
    def refresh_runtime(self):
        self.outer_raw=enc(self.outer);self.owned['outer_closure_ref']={'path':self.output+'/outer-closure.json','file_sha256':sha(self.outer_raw)}
        self.owned_raw=enc(self.owned)
        self.terminal['authorization']={'kind':'live-owned-model-closure','output_root':self.output,
            'original_deadlines':self.outer['original_deadlines'],'original_clock':self.outer['original_clock'],'source_sha256':'a'*64,
            'owner_request_ref':{'path':self.output+'/owner-request.json','file_sha256':self.outer['launch_request_sha256']},
            'outer_closure_ref':self.owned['outer_closure_ref'],'worker_pid':self.outer['worker_pid'],'worker_exited':True,'worker_session_empty':True}
        self.terminal['archive']={'path':self.output+'.evidence.zip','members':{n:{'bytes':len(raw),'sha256':sha(raw)} for n,raw in [('outer-closure.json',self.outer_raw),('owned-result.json',self.owned_raw)]}}
        self.terminal_raw=enc(self.terminal);self.refresh_result()
    def refresh_result(self):
        self.write('result.json',{**self.owned,'terminal_export':{**self.terminal,'terminal_receipt':{
            'path':self.output+'.evidence.zip.terminal.json','sha256':sha(self.terminal_raw),'bytes':len(self.terminal_raw)}}})
    def kwargs(self):return dict(expected_jit=self.jit,notebook_release=self.release,reviewed_environment=self.environment,
        runtime_outer_raw=self.outer_raw,runtime_owned_result_raw=self.owned_raw,runtime_terminal_raw=self.terminal_raw)

class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-nested-wrapper-');self.addCleanup(self.tmp.cleanup)
        self.v=load(SUCCESSOR);self.f=Fixture(self.tmp.name,self.v)
    def check(self):return self.v.verify_wrappers(self.f.root,**self.f.kwargs())
    def reject(self,pattern=None):
        with self.assertRaisesRegex(ValueError,pattern or 'wrapper:'):self.check()
    def test_synthetic_two_missing_observations_pass(self):
        before={p.relative_to(self.f.root):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        d=self.check();self.assertTrue(d['closure_valid']);self.assertTrue(d['operational'])
        self.assertEqual(d['format'],'irisx/rlvr-parent-wrapper-verification-v2')
        self.assertFalse(d['model_closure_verified_by_this_helper'])
        x=d['nested_observation_difference'];self.assertFalse(x['full_cross_scope_observed_subset'])
        self.assertEqual([r['pid'] for r in x['installed_parent_only']],[23,25])
        self.assertEqual([r['pid'] for r in x['preparation_only']],[2,3])
        self.assertEqual(before,{p.relative_to(self.f.root):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
    def test_original_still_rejects_same_documents(self):
        old=load(ORIGINAL,original_bytes());old.INTERPRETER_MANIFEST=self.v.INTERPRETER_MANIFEST
        with self.assertRaisesRegex(ValueError,'complete nested owned-tree membership'):old.verify_wrappers(self.f.root,**self.f.kwargs())
    def test_no_difference_passes(self):
        def add(d):d['owned_identities']=sorted(d['owned_identities']+self.f.missing,key=lambda r:(r['birth'],r['pid']))
        self.f.proof_edit('preparation',add,True)
        self.assertTrue(self.check()['nested_observation_difference']['full_cross_scope_observed_subset'])
    def test_missing_each_spine_anchor(self):
        for pid in (20,21,22):
            with self.subTest(pid=pid):
                self.setUp();self.f.remove_outer_observation(pid)
                self.reject('spine|must also be observed')
    def test_descendant_needs_both_inner_witnesses(self):
        self.f.edit('installed-parent/owned-tree/supervisor-result.json',lambda d:d.update(owned_identities=[x for x in d['owned_identities'] if x['pid']!=23]))
        self.reject('both inner raw witnesses')
    def test_changed_common_session_not_ignored(self):
        def change(d):
            for r in d['owned_identities']:
                if r['pid']==24:r['session']=99
        self.f.proof_edit('preparation',change,True);self.reject('session disagreement')
    def test_one_sided_birth_or_session_mutation(self):
        for key in ('birth','session'):
            with self.subTest(key=key):
                self.setUp()
                def change(d):
                    for r in d['owned_identities']:
                        if r['pid']==23:r[key]+=100
                    d['owned_identities'].sort(key=lambda r:(r['birth'],r['pid']))
                self.f.edit('installed-parent/owned-tree/supervisor-result.json',change);self.reject('subreaper owned union')
    def test_pid_reuse_does_not_satisfy_runtime_anchor(self):
        def change(d):
            for r in d['owned_identities']:
                if r['pid']==22:r['birth']=14
            d['owned_identities'].sort(key=lambda r:(r['birth'],r['pid']))
        self.f.proof_edit('preparation',change,True);self.reject('must also be observed')
    def test_duplicate_incarnation_rejected(self):
        self.f.proof_edit('installed-parent',lambda d:d['owned_identities'].append(self.f.missing[0]));self.reject('duplicate incarnation')
    def test_wrong_coordinator_pid_birth_session(self):
        for key in ('pid','birth','session'):
            with self.subTest(key=key):
                self.setUp();self.f.edit('installed-parent/owned-tree/launch.json',lambda d:d['coordinator_identity'].update({key:1}))
                self.reject('coordinator incarnation|dedicated session')
    def test_nested_time_not_merely_overlap(self):
        self.f.edit('installed-parent/closure.json',lambda d:d.update(completed_monotonic=200,completed_epoch=1100));self.reject('nested stage interval')
    def test_forced_residual_errors_and_open_proofs(self):
        changes=(lambda d:d.update(forced=True),lambda d:d.update(remaining=[d['root_identity']]),lambda d:d.update(errors=['synthetic failure']),
                 lambda d:d.update(closed=False),lambda d:d.update(ownership_complete=False))
        for stage in ('preparation','installed-parent'):
            for n,change in enumerate(changes):
                with self.subTest(stage=stage,change=n):
                    self.setUp();self.f.proof_edit(stage,change);self.reject('two clean closures')
    def test_raw_summary_mismatch(self):
        self.f.edit('installed-parent/owned-tree/closure.json',lambda d:d.update(returncode=7));self.reject('raw closure equals')
    def test_inner_union_still_required(self):
        self.f.proof_edit('installed-parent',lambda d:d.update(owned_identities=[x for x in d['owned_identities'] if x['pid']!=23]));self.reject('subreaper owned union')
    def test_changed_deadline(self):
        self.f.edit('preparation/closure.json',lambda d:d.update(deadline_epoch=self.f.epoch+42181));self.reject('original outer deadline')
    def test_missing_raw_file(self):
        (self.f.root/'installed-parent/owned-tree/worker-launch.json').unlink()
        with self.assertRaises(FileNotFoundError):self.check()
    def test_changed_argv_jit_and_source(self):
        for target in ('argv','jit','source'):
            with self.subTest(target=target):
                self.setUp()
                if target=='argv':self.f.edit('installed-parent/owned-tree/launch.json',lambda d:d.update(worker_argv=['foreign']))
                elif target=='jit':self.f.write('operator.json',{'foreign':True})
                else:self.f.release['source_sha256']='e'*64
                self.reject()
    def test_runtime_checks_after_repaired_boundary(self):
        for target in ('birth','session','interval'):
            with self.subTest(target=target):
                self.setUp()
                if target=='birth':self.f.outer['worker_incarnation']['start_ticks']+=1
                elif target=='session':self.f.outer['worker_incarnation']['process_group']=1
                else:self.f.outer['started_monotonic']=0
                self.f.refresh_runtime();self.reject('runtime model-worker|runtime supervision')
    def test_rebound_runtime_incarnation_pid_must_match(self):
        self.f.outer['worker_incarnation']['pid']=999
        self.f.refresh_runtime();self.reject('strict runtime worker incarnation identity')
    def test_rebound_runtime_identity_requires_exact_ints(self):
        for field in ('worker_pid','pid','start_ticks','session_id','process_group'):
            for value in (True,False,22.0,'22',None,[],{}):
                with self.subTest(field=field,value=value):
                    self.setUp()
                    target=self.f.outer if field=='worker_pid' else self.f.outer['worker_incarnation']
                    target[field]=value;self.f.refresh_runtime()
                    self.reject('strict runtime worker incarnation identity')
    def test_missing_runtime_incarnation_integer_fields(self):
        for field in ('pid','start_ticks','session_id','process_group'):
            with self.subTest(field=field):
                self.setUp();self.f.outer['worker_incarnation'].pop(field);self.f.refresh_runtime()
                self.reject('strict runtime worker incarnation identity')
    def test_runtime_incarnation_must_be_dict(self):
        for value in (None,[],True):
            with self.subTest(value=value):
                self.setUp();self.f.outer['worker_incarnation']=value;self.f.refresh_runtime()
                self.reject('strict runtime worker incarnation identity')
    def test_terminal_checks_after_repaired_boundary(self):
        for target in ('source','claim','deadline','model','late'):
            with self.subTest(target=target):
                self.setUp()
                if target=='source':self.f.terminal['authorization']['source_sha256']='e'*64
                elif target=='claim':self.f.terminal['scientific_goal_met']=True
                elif target=='deadline':self.f.terminal['authorization']['original_deadlines']=dict(self.f.outer['original_deadlines'],outer=1)
                elif target=='model':self.f.terminal['model_closed']=False
                else:self.f.terminal['finished_monotonic']=181
                self.f.terminal_raw=enc(self.f.terminal);self.f.refresh_result();self.reject()
    def test_result_projection_after_repaired_boundary(self):
        self.f.edit('result.json',lambda d:d.update(unrelated=True));self.reject('exact owned-result projection')
    def test_clean_nonzero_is_separate_from_operational(self):
        for stage in ('preparation','installed-parent'):
            self.f.proof_edit(stage,lambda d:d.update(returncode=7,worker_returncode=7),True)
        d=self.check();self.assertTrue(d['closure_valid']);self.assertFalse(d['operational'])
    def test_supervisor_changed_after_stage_verification(self):
        a=self.v.verify_stage(self.f.root/'preparation',expected_argv=self.f.argv_a,epoch=1000,scope='entire-owned-preparation-and-runtime')
        b=self.v.verify_stage(self.f.root/'installed-parent',expected_argv=self.f.argv_b,epoch=1000,scope='installed-parent-with-owned-model-child')
        p=self.f.root/'installed-parent/owned-tree/supervisor-result.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'evidence changed'):self.v._nested_observations(self.f.root,a,b)

class SourcePreservationTests(unittest.TestCase):
    def test_all_original_functions_except_wrapper_byte_identical(self):
        old=original_bytes().decode();new=SUCCESSOR.read_text()
        a={n.name:ast.get_source_segment(old,n) for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}
        b={n.name:ast.get_source_segment(new,n) for n in ast.parse(new).body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(set(b)-set(a),{'_nested_observations'})
        for name in a.keys()-{'verify_wrappers'}:self.assertEqual(a[name],b[name],name)
    def test_all_original_wrapper_checks_preserved(self):
        a=next(n for n in ast.parse(original_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='verify_wrappers')
        b=next(n for n in ast.parse(SUCCESSOR.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='verify_wrappers')
        old_subset=next(n for n in a.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and any(isinstance(x,ast.Constant) and x.value=='complete nested owned-tree membership' for x in n.value.args))
        normalized=[]
        for node in b.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='observation_difference' for t in node.targets):
                normalized.append(old_subset);continue
            if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and any(isinstance(x,ast.Constant) and x.value in ('runtime model-worker incarnation must also be observed by preparation','strict runtime worker incarnation identity') for x in node.value.args):continue
            if isinstance(node,ast.Return):
                node=copy.deepcopy(node);pairs=[(k,v) for k,v in zip(node.value.keys,node.value.values) if not (isinstance(k,ast.Constant) and k.value=='nested_observation_difference')]
                node.value.keys=[k for k,v in pairs];node.value.values=[v for k,v in pairs]
                for k,v in pairs:
                    if isinstance(k,ast.Constant) and k.value=='format':self.assertEqual(v.value,'irisx/rlvr-parent-wrapper-verification-v2');v.value='irisx/rlvr-parent-wrapper-verification-v1'
            normalized.append(node)
        b.body=normalized;self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))
    def test_runtime_producer_is_exact_original(self):
        root=HERE.parents[2];p=root/'tools/arc_learning_agent_20261011/process_guard.py'
        self.assertEqual(sha(p.read_bytes()),'8bc66ac80499203bca9f583f0d5ea5ecc5d8a131a2aa267f661060fc69e0580c')


def retained_counterexample(root):
    """Read-only original CPU artifact replay; deliberately remains rejected."""
    root=Path(root);raw=(root/'RESULT.json').read_bytes()
    if sha(raw)!='46e0ca89ca58c3afadaf0cc1a7513138bddd92120bd5146324ac14d447499c2c':raise ValueError('exact retained CPU counterexample required')
    record=json.loads(raw);v=load(SUCCESSOR);case=record['cases'][0];path=root/'case-0'
    checked=[]
    for name,scope,key in [('preparation','synthetic-preparation','a'),('installed-parent','synthetic-installed-parent','b')]:
        launch=json.loads((path/name/'owned-tree/launch.json').read_bytes());closure=json.loads((path/name/'closure.json').read_bytes())
        stage=v.verify_stage(path/name,expected_argv=launch['worker_argv'],epoch=closure['deadline_epoch']-42180,scope=scope)
        if stage!=case['proofs'][key]:raise ValueError('retained stage evidence changed')
        checked.append(stage)
    try:v._nested_observations(path,*checked)
    except ValueError as exc:
        if str(exc)!='wrapper: nested-only observations require both inner raw witnesses':raise
    else:raise AssertionError('counterexample with coordinator-only observations must remain rejected')
    print('Retained genuine CPU counterexample: REJECT as required (two observations lack the second inner witness).')

if __name__=='__main__':
    if '--counterexample-root' in sys.argv:
        i=sys.argv.index('--counterexample-root');root=sys.argv[i+1];del sys.argv[i:i+2];retained_counterexample(root)
    unittest.main(verbosity=2)
