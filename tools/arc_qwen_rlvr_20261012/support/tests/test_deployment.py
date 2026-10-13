"""No-model fixtures for exact mount layouts, inert notebooks and acyclic JIT."""
from pathlib import Path
import copy,importlib.util,io,json,os,py_compile,shutil,sys,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'deployment'))
import source_loader as l
import notebook_builder as nb
spec=importlib.util.spec_from_file_location('finalize_rlvr',ROOT/'assembly/finalize.py');fin=importlib.util.module_from_spec(spec);spec.loader.exec_module(fin)


def fixture(root,layout='archive'):
    root.mkdir()
    files={'owned_runtime/a.py':b'x = 1\n','baseline/LICENSE':b'fixture only\n'}
    auxiliary={'NOTICE.txt':b'No model fixture\n','deployment/a.py':b'y = 2\n'}
    archive=l.zip_source(files)
    row=lambda b:{'bytes':len(b),'sha256':l.digest(b)}
    manifest={'format':l.FORMAT,'reference':'danielwuu/iris-x-learning-agent-code-20261011/14',
        'source':{'archive':{'name':'source.zip',**row(archive)},'source_sha256':l.digest(json.dumps(sorted((n,l.digest(b)) for n,b in files.items()),sort_keys=True,separators=(',',':')).encode()),
        'files':{n:row(b) for n,b in files.items()}},'auxiliary_files':{n:row(b) for n,b in auxiliary.items()}}
    raw=l.encoded(manifest);(root/'manifest.json').write_bytes(raw)
    for n,b in auxiliary.items():p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    if layout=='archive':(root/'source.zip').write_bytes(archive)
    else:
        for n,b in files.items():p=root/('source' if layout=='directory' else '')/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'manifest_sha256':l.digest(raw),'archive_sha256':l.digest(archive)},files


class DeploymentTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_all_exact_mount_layouts(self):
        for layout in ('archive','directory','root'):
            code=self.root/layout;pins,files=fixture(code,layout)
            result=l.load_release(str(code),str(self.root/(layout+'-out')),**pins)
            self.assertEqual(result['source_members'],2);self.assertFalse(result['model_imported'])
            self.assertEqual((Path(result['source_archive_path'])).read_bytes(),l.zip_source(files))
    def test_no_unknown_file(self):
        code=self.root/'code';pins,_=fixture(code);(code/'unknown').write_bytes(b'')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_reject_mixed_archive_extraction(self):
        code=self.root/'code';pins,_=fixture(code);(code/'source').mkdir();(code/'source/x').write_bytes(b'x')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_source_mutation(self):
        code=self.root/'code';pins,_=fixture(code,'directory');(code/'source/owned_runtime/a.py').write_bytes(b'x = 2\n')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_auxiliary_mutation(self):
        code=self.root/'code';pins,_=fixture(code);(code/'deployment/a.py').write_bytes(b'y = 3\n')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_notice_mutation(self):
        code=self.root/'code';pins,_=fixture(code);(code/'NOTICE.txt').write_bytes(b'license changed')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_manifest_mutation(self):
        code=self.root/'code';pins,_=fixture(code);(code/'manifest.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_no_output_reuse(self):
        code=self.root/'code';pins,_=fixture(code);out=self.root/'out';out.mkdir()
        with self.assertRaises(ValueError):l.load_release(str(code),str(out),**pins)
    def test_no_source_input_overlap(self):
        code=self.root/'code';pins,_=fixture(code)
        with self.assertRaises(ValueError):l.load_release(str(code),str(code/'out'),**pins)
    def test_no_source_symlink(self):
        code=self.root/'code';pins,_=fixture(code,'directory');p=code/'source/owned_runtime/a.py';p.unlink();p.symlink_to(code/'deployment/a.py')
        with self.assertRaises(ValueError):l.inspect_release(str(code),**pins)
    def test_no_symlink_parent(self):
        code=self.root/'code';pins,_=fixture(code);link=self.root/'linked';link.symlink_to(code,target_is_directory=True)
        with self.assertRaises(ValueError):l.inspect_release(str(link),**pins)
    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):l.parse(b'{"a":1,"a":2}')
    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):l.parse(b'{"a":NaN}')
    def test_unsafe_paths_rejected(self):
        for value in ('../x','a/../b','/x','a//b','a\\b','a\x00b'):
            with self.assertRaises(ValueError):l.safe_name(value)
    def test_templates_entire_execution_inert(self):
        loader=(ROOT/'deployment/source_loader.py').read_text()
        for kind in ('inactive','active-template'):
            notebook=nb.build({'fixture_only':True},loader,kind=kind);scope={}
            with patch('builtins.open',side_effect=AssertionError('unexpected filesystem access')):
                for cell in notebook['cells']:
                    if cell['cell_type']=='code':exec(compile(''.join(cell['source']),'<fixture-notebook>','exec'),scope)
            self.assertEqual(scope['RESULT']['status'],'INACTIVE_NO_EXECUTION');self.assertIsNone(scope['PREDISPATCH_EPOCH'])
    def test_manual_switch_cannot_enable_template(self):
        notebook=nb.build({'fixture_only':True},'fixture',kind='active-template');scope={}
        for cell in notebook['cells'][:-1]:
            if cell['cell_type']=='code':exec(''.join(cell['source']),scope)
        scope.update(MANUAL_START=True,ENABLE_MODEL=True)
        with self.assertRaisesRegex(ValueError,'JIT'):exec(''.join(notebook['cells'][-1]['source']),scope)
    def candidate(self):
        candidate=self.root/'candidate';payload=candidate/'code-payload/deployment';payload.mkdir(parents=True)
        for name in ('notebook_builder.py','source_loader.py'):shutil.copy2(ROOT/'deployment'/name,payload/name)
        release={'production_admitted':True,'release_role':'rlvr001','source_sha256':'1'*64,'source_archive_sha256':'2'*64,
            'material_review_sha256':'3'*64,'scorer_pins_sha256':'4'*64,'data_mount_layout':'datasets-owner-slug',
            'deployment':{n:{'sha256':l.digest((payload/n).read_bytes())} for n in ('notebook_builder.py','source_loader.py')},
            'original_owner_request':{'owner_id':'synthetic-fixture-owner','request_id':'synthetic-fixture-request','instruction':'Synthetic JIT byte fixture only, not real production authority.'},
            'material_pins':{'data':{'reference':'danielwuu/iris-x-public120-data-20261010/1','role_manifests':{'evaluator':'5'*64}}}}
        (candidate/'notebook-release.json').write_bytes(l.encoded(release));return candidate,release
    def test_jit_determinism_and_chain(self):
        root,release=self.candidate();a=fin.finalize(root,1234567890);b=fin.finalize(root,1234567890)
        self.assertEqual(a,b);self.assertEqual(set(a),{'active-finalized.ipynb','original-request.json','operator.json','parent-private-scorer.json'})
        op=json.loads(a['operator.json']);self.assertEqual(op['parent_scorer_sha256'],l.digest(a['parent-private-scorer.json']))
        self.assertEqual(op['original_request_sha256'],l.digest(a['original-request.json']))
        self.assertEqual(json.loads(a['active-finalized.ipynb'])['metadata']['owned_rl_release']['operator_sha256'],l.digest(a['operator.json']))
    def test_jit_rejects_unadmitted_source(self):
        root,release=self.candidate();release['production_admitted']=False;(root/'notebook-release.json').write_bytes(l.encoded(release))
        with self.assertRaisesRegex(ValueError,'admitted'):fin.finalize(root,123)
    def test_jit_rejects_noninteger_or_missing_epoch(self):
        root,_=self.candidate()
        for value in (None,True,0,-1,1.5,float('nan'),float('inf')):
            with self.assertRaises(ValueError):fin.finalize(root,value)
    def test_dynamic_loader_ignores_valid_poisoned_pyc(self):
        from launch_notebook import load_file
        p=self.root/'module.py';p.write_text("VALUE='BAD'\n");stamp=p.stat().st_mtime_ns
        py_compile.compile(str(p),doraise=True)
        p.write_text("VALUE='YES'\n");os.utime(p,ns=(stamp,stamp))
        self.assertEqual(load_file('source_only_cache_test',p).VALUE,'YES')
    def test_source_import_paths_rejects_bytecode(self):
        p=self.root/'source';p.mkdir();(p/'__pycache__').mkdir()
        with self.assertRaisesRegex(ValueError,'bytecode'):l.source_import_paths(p)
    def test_finalizer_ignores_valid_poisoned_builder_cache(self):
        root,_=self.candidate();p=root/'code-payload/deployment/notebook_builder.py';raw=p.read_bytes();stamp=p.stat().st_mtime_ns
        evil=b"raise RuntimeError('POISONED CACHE')\n";p.write_bytes(evil+b'#'*(len(raw)-len(evil)));os.utime(p,ns=(stamp,stamp));py_compile.compile(str(p),doraise=True)
        p.write_bytes(raw);os.utime(p,ns=(stamp,stamp))
        self.assertIn('active-finalized.ipynb',fin.finalize(root,123))
    def test_jit_helper_bytes_changed(self):
        root,_=self.candidate();(root/'code-payload/deployment/notebook_builder.py').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'builder'):fin.finalize(root,123)

if __name__=='__main__':unittest.main()
