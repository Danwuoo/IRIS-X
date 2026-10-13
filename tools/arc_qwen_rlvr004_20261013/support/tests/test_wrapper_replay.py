"""Mutation replay of retained actual CPU proofs; no model or subprocess work."""
from pathlib import Path
import copy,json,shutil,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment'))
from launch_notebook import load_file
v=load_file('reviewed_wrapper_test',ROOT/'assembly/verify_parent_wrappers.py')
FIX=ROOT/'test-results/wrapper-raw-cpu-normal'

class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'case';shutil.copytree(FIX/'success',self.root)
        self.meta=json.loads((FIX/'FIXTURE.json').read_bytes())['cases']['success']
    def tearDown(self):self.tmp.cleanup()
    def check(self):return v.verify_stage(self.root/'installed-parent',expected_argv=self.meta['installed_parent_argv'],epoch=self.meta['epoch'],scope='synthetic-installed-parent')
    def edit(self,name,fn):
        p=self.root/'installed-parent'/name;d=json.loads(p.read_bytes());fn(d);p.write_text(json.dumps(d))
    def test_valid_actual_raw_proofs(self):self.assertTrue(self.check()['operational'])
    def test_missing_raw_each(self):
        for name in ('launch.json','worker-launch.json','supervisor-result.json','closure.json'):
            p=self.root/'installed-parent/owned-tree'/name;raw=p.read_bytes();p.unlink()
            with self.assertRaises((ValueError,OSError)):self.check()
            p.write_bytes(raw)
    def test_forged_summary(self):
        self.edit('closure.json',lambda d:d['proof'].update(worker_returncode=22))
        with self.assertRaisesRegex(ValueError,'raw closure'):self.check()
    def test_wrong_request_hash_argv(self):
        self.edit('owned-tree/launch.json',lambda d:d['worker_argv'].append('forged-request-sha'))
        with self.assertRaisesRegex(ValueError,'argv'):self.check()
    def test_wrong_supervisor_birth(self):
        self.edit('owned-tree/worker-launch.json',lambda d:d['supervisor_identity'].update(birth=1))
        with self.assertRaisesRegex(ValueError,'incarnation'):self.check()
    def test_wrong_worker_birth(self):
        self.edit('owned-tree/worker-launch.json',lambda d:d['worker_identity'].update(birth=1))
        with self.assertRaisesRegex(ValueError,'incarnation'):self.check()
    def test_both_clock_envelope_mutations(self):
        for offset in (-1,1):
            self.edit('closure.json',lambda d:d.update(deadline_epoch=self.meta['epoch']+42180+offset))
            with self.assertRaisesRegex(ValueError,'deadline'):self.check()
    def test_nonfinite_clock(self):
        self.edit('closure.json',lambda d:d.update(started_epoch=float('inf')))
        with self.assertRaises(ValueError):self.check()
    def test_reversed_interval(self):
        self.edit('closure.json',lambda d:d.update(started_epoch=d['completed_epoch']+1))
        with self.assertRaisesRegex(ValueError,'interval'):self.check()
    def test_false_deadline_claim(self):
        self.edit('closure.json',lambda d:d.update(completed_epoch=self.meta['epoch']+50000))
        with self.assertRaises(ValueError):self.check()
    def bothproofs(self,fn):
        self.edit('owned-tree/closure.json',fn);self.edit('closure.json',lambda d:fn(d['proof']))
    def test_residual_is_not_clean(self):
        self.bothproofs(lambda p:p.update(remaining=[p['root_identity']]))
        self.assertFalse(self.check()['closure_valid'])
    def test_error_is_not_clean(self):
        self.bothproofs(lambda p:p.update(errors=['unresolved owned member']))
        self.assertFalse(self.check()['closure_valid'])
    def test_forced_is_not_clean(self):
        self.bothproofs(lambda p:p.update(forced=True));self.edit('closure.json',lambda d:d.update(forced=True,reason='original-outer-deadline'))
        self.assertFalse(self.check()['closure_valid'])
    def test_reaped_foreign_incarnation(self):
        self.bothproofs(lambda p:p.update(reaped_identities=[dict(p['root_identity'],pid=99999999)]))
        with self.assertRaisesRegex(ValueError,'ownership'):self.check()
    def test_wrong_returncode_chain(self):
        self.bothproofs(lambda p:p.update(worker_returncode=9))
        with self.assertRaisesRegex(ValueError,'return-code'):self.check()
    def test_nonzero_can_be_clean(self):
        m=json.loads((FIX/'FIXTURE.json').read_bytes())['cases']['nonzero']
        result=v.verify_stage(FIX/'nonzero/installed-parent',expected_argv=m['installed_parent_argv'],epoch=m['epoch'],scope='synthetic-installed-parent')
        self.assertTrue(result['closure_valid']);self.assertFalse(result['operational']);self.assertEqual(result['worker_returncode'],7)
    def test_nested_real_birth_chain(self):
        m=self.meta
        a=v.verify_stage(self.root/'preparation',expected_argv=m['preparation_argv'],epoch=m['epoch'],scope='synthetic-preparation');b=self.check()
        self.assertEqual(v.identity(b['coordinator_identity']),v.identity(a['worker_identity']))
        self.assertLessEqual(v.identities(b['owned_identities']),v.identities(a['owned_identities']))
        self.assertLessEqual(a['started_monotonic'],b['started_monotonic']);self.assertLessEqual(b['completed_monotonic'],a['completed_monotonic'])


class WrapperIntegrationFixtureTests(WrapperTests):
    """Synthetic document binding around real kernel proofs; no production claim."""
    def setUp(self):
        super().setUp()
        self.epoch=self.meta['epoch'];source='/kaggle/working/irisx-qwen14b-rlvr-20261012-source004/runtime';output='/kaggle/working/irisx-qwen14b-rlvr-20261012-run004';launcher=output+'-launcher';env=v.ENV
        self.source=source;self.output=output;self.launcher=launcher
        self.release={'source_sha256':'a'*64,'source_archive_sha256':'b'*64,'code_manifest_sha256':'c'*64,'material_pins':{'data':{'reference':'fixture/data/1'},'training':{'reference':'fixture/training/1'}}}
        self.environment={'model_config':{'model_path':'/fixture-model'}}
        def write(name,value):
            b=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode();(self.root/name).write_bytes(b);return b
        self.write=write
        owner={'original_epoch':self.epoch};operator={'fixture':True}
        self.jit={'active-finalized.ipynb':write('outer.ipynb',{'fixture':True}),'original-request.json':write('original-request.json',owner),'operator.json':write('operator.json',operator),'parent-private-scorer.json':write('parent-private-scorer.json',{'fixture':True})}
        ready={'source_root':source,'source_sha256':'a'*64,'source_archive_sha256':'b'*64,'manifest_sha256':'c'*64,'source_archive_path':str(Path(source).parent/'source.zip')}
        prep={'format':'irisx/rlvr-parent-preparation-request-v1','ready':ready,'release':self.release,'finalized':{'owner_request':owner,'operator':operator},'notebook_python_executable':'/fixture/python','output_root':output,'input_root':'/kaggle/input','epoch':self.epoch,'launcher_root':launcher,'environment_root':env}
        prep_raw=write('preparation-request.json',prep)
        paths={'outer_notebook_path':launcher+'/outer.ipynb','operator_path':launcher+'/operator.json','material_review_path':str(Path(source).parent/'release/MATERIAL-REVIEW.json'),'source_archive_path':ready['source_archive_path'],'original_request_path':launcher+'/original-request.json','parent_scorer_path':launcher+'/parent-private-scorer.json'}
        config={'fixture':False,'policy_path':source+'/design/MEASURED-POLICY.json','environment_path':str(Path(source).parent/'release/REVIEWED-ENVIRONMENT.json'),'training_root':'/kaggle/input/datasets/fixture/training/data/training','public_solver_root':'/kaggle/input/datasets/fixture/data/solver','model':self.environment['model_config']}
        parent={'format':'irisx/rlvr-installed-parent-request-v1','source_root':source,'output_root':output,'config':config,'paths':paths,'result_path':launcher+'/result.json','source_sha256':'a'*64}
        parent_raw=write('installed-parent-request.json',parent)
        manifest={'members':{'python/bin/python3.12':{'sha256':'d'*64}}};manifest_raw=write('interpreter-manifest.json',manifest)
        self.saved_manifest=v.INTERPRETER_MANIFEST;v.INTERPRETER_MANIFEST=v.sha(manifest_raw)
        command=[env+'/environment-cp312-cu128/bin/python','-I','-B','-S',env+'/environment-cp312-cu128/offline-run.py']
        installed={'python_command':command,'installed_offline':True,'reused_environment':False,'actual_environment_lock_path':env+'/environment-cp312-cu128/evidence/environment-lock.json','actual_environment_lock_sha256':'f'*64,'interpreter':{'manifest_sha256':v.INTERPRETER_MANIFEST,'archive_sha256':v.INTERPRETER_ARCHIVE,'executable_sha256':'d'*64,'verified_member_count':1}}
        write('preparation-receipt.json',{'format':'irisx/rlvr-offline-preparation-receipt-v1','source_sha256':'a'*64,'source_acceptance':ready,'original_epoch':self.epoch,'installed_offline':True,'offline_environment':installed,'model_mount':'/fixture-model','public_answers_opened':False,'model_loaded_by_preparation':False,'storage_plan':{},'disk_admission':{},'actual_disk_free_bytes':1})
        write('result.json',{'status':'owned-mechanics-complete-PUBLIC-sealed','terminal_export':{'status':'complete'}})
        for stage,scope,argv in [('preparation','entire-owned-preparation-and-runtime',['/fixture/python','-I','-B',str(Path(source).parent/'deployment/prepare_entry.py'),launcher+'/preparation-request.json',v.sha(prep_raw)]),('installed-parent','installed-parent-with-owned-model-child',command+[str(Path(source).parent/'deployment/parent_entry.py'),launcher+'/installed-parent-request.json',v.sha(parent_raw)])]:
            path=self.root/stage/'owned-tree/launch.json';d=json.loads(path.read_bytes());d['worker_argv']=argv;path.write_text(json.dumps(d))
            path=self.root/stage/'closure.json';d=json.loads(path.read_bytes());d['scope']=scope;path.write_text(json.dumps(d))
        # Synthetic model-child observation supplements the real two-stage kernel
        # fixture only for document/API checks; no model was loaded or observed.
        child={'pid':99999999,'birth':99999999,'session':99999999,'state':'R'}
        for stage in ('preparation','installed-parent'):
            for name in ('owned-tree/closure.json','owned-tree/supervisor-result.json'):
                p=self.root/stage/name;d=json.loads(p.read_bytes());d['owned_identities'].append(child);d['owned_identities'].sort(key=lambda r:(r['birth'],r['pid']));p.write_text(json.dumps(d))
            p=self.root/stage/'closure.json';d=json.loads(p.read_bytes());d['proof']=json.loads((self.root/stage/'owned-tree/closure.json').read_bytes());p.write_text(json.dumps(d))
        c=json.loads((self.root/'installed-parent/closure.json').read_bytes());clock={'original_epoch':self.epoch}
        outer={'schema':'owned-parent-supervision-v1','fixture':False,'launch_source_sha256':'a'*64,'output_root':output,'worker_pid':child['pid'],'worker_incarnation':{'pid':child['pid'],'start_ticks':child['birth'],'session_id':child['session'],'process_group':child['session']},'started_monotonic':c['started_monotonic'],'exit_observed_monotonic':c['completed_monotonic'],'original_clock':clock}
        self.runtime_outer_raw=json.dumps(outer).encode()
        owned={'format':'owned-rl-result-v1','fixture':False,'source_sha256':'a'*64,'clock':clock,'outer_closure_ref':{'path':output+'/outer-closure.json','file_sha256':v.sha(self.runtime_outer_raw)},'status':'owned-mechanics-complete-PUBLIC-sealed'}
        self.runtime_owned_result_raw=json.dumps(owned).encode()
        terminal={'status':'complete','original_clock':clock,'source_sha256':'a'*64,'archive_complete':True,'output_root':output,'archive':{'members':{n:{'bytes':len(raw),'sha256':v.sha(raw)} for n,raw in [('outer-closure.json',self.runtime_outer_raw),('owned-result.json',self.runtime_owned_result_raw)]}}}
        self.runtime_terminal_raw=json.dumps(terminal).encode()
        write('result.json',{**owned,'terminal_export':{**terminal,'terminal_receipt':{'path':output+'.evidence.zip.terminal.json','sha256':v.sha(self.runtime_terminal_raw),'bytes':len(self.runtime_terminal_raw)}}})
    def tearDown(self):v.INTERPRETER_MANIFEST=self.saved_manifest;super().tearDown()
    def integration(self):return v.verify_wrappers(self.root,expected_jit=self.jit,notebook_release=self.release,reviewed_environment=self.environment,runtime_outer_raw=self.runtime_outer_raw,runtime_owned_result_raw=self.runtime_owned_result_raw,runtime_terminal_raw=self.runtime_terminal_raw)
    # Inherited stage-only tests use the original synthetic argv; disable their discovery.
    def test_integration_synthetic_document_chain(self):self.assertTrue(self.integration()['operational'])
    def test_integration_partial_comparison_can_close_operationally(self):
        owned=json.loads(self.runtime_owned_result_raw);owned['status']='owned-mechanics-partial-comparison-PUBLIC-sealed';self.runtime_owned_result_raw=json.dumps(owned).encode()
        terminal=json.loads(self.runtime_terminal_raw);terminal['archive']['members']['owned-result.json']={'bytes':len(self.runtime_owned_result_raw),'sha256':v.sha(self.runtime_owned_result_raw)};self.runtime_terminal_raw=json.dumps(terminal).encode()
        self.write('result.json',{**owned,'terminal_export':{**terminal,'terminal_receipt':{'path':self.output+'.evidence.zip.terminal.json','sha256':v.sha(self.runtime_terminal_raw),'bytes':len(self.runtime_terminal_raw)}}})
        result=self.integration();self.assertTrue(result['operational']);self.assertNotIn('comparison_complete',result)
    def test_integration_jit_mutation(self):
        self.write('operator.json',{'forged':True})
        with self.assertRaisesRegex(ValueError,'JIT'):self.integration()
    def test_integration_source_mutation(self):
        d=json.loads((self.root/'installed-parent-request.json').read_bytes());d['source_sha256']='0'*64;self.write('installed-parent-request.json',d)
        with self.assertRaisesRegex(ValueError,'source identity'):self.integration()
    def test_integration_child_evaluator_leak(self):
        d=json.loads((self.root/'installed-parent-request.json').read_bytes());d['config']['model']['evaluator_root']='/private';self.write('installed-parent-request.json',d)
        with self.assertRaisesRegex(ValueError,'model inputs'):self.integration()
    def test_integration_interpreter_mutation(self):
        d=json.loads((self.root/'preparation-receipt.json').read_bytes());d['offline_environment']['interpreter']['executable_sha256']='0'*64;self.write('preparation-receipt.json',d)
        with self.assertRaisesRegex(ValueError,'interpreter identity'):self.integration()
    def test_integration_unrelated_parent_result(self):
        d=json.loads((self.root/'result.json').read_bytes());d['source_sha256']='0'*64;self.write('result.json',d)
        with self.assertRaisesRegex(ValueError,'projection'):self.integration()
    def test_integration_terminal_projection_mutation(self):
        d=json.loads((self.root/'result.json').read_bytes());d['terminal_export']['terminal_receipt']['sha256']='0'*64;self.write('result.json',d)
        with self.assertRaisesRegex(ValueError,'terminal projection'):self.integration()
    def test_integration_runtime_interval_mutation(self):
        d=json.loads(self.runtime_outer_raw);d['started_monotonic']=0;self.runtime_outer_raw=json.dumps(d).encode()
        with self.assertRaisesRegex(ValueError,'interval'):self.integration()
    def test_integration_runtime_session_mutation(self):
        d=json.loads(self.runtime_outer_raw);d['worker_incarnation']['process_group']=1;self.runtime_outer_raw=json.dumps(d).encode()
        with self.assertRaisesRegex(ValueError,'session'):self.integration()
    def test_integration_request_hash_mutation(self):
        d=json.loads((self.root/'preparation-request.json').read_bytes());d['notebook_python_executable']='/fixture/other';self.write('preparation-request.json',d)
        with self.assertRaisesRegex(ValueError,'argv'):self.integration()

for _name in list(vars(WrapperTests)):
    if _name.startswith('test_'):setattr(WrapperIntegrationFixtureTests,_name,None)

if __name__=='__main__':unittest.main()
