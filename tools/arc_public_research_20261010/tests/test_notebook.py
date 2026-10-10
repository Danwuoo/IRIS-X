"""Synthetic portable loader and default-inert notebook acceptance."""
import hashlib, io, json, os, stat, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock
from tools.arc_public_research_20261010.source_loader import load_reviewed_source
from tools.arc_public_research_20261010.build_notebook import build

def sha(raw):return hashlib.sha256(raw).hexdigest()
def raw(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='public-loader-');self.root=Path(self.temp.name)
        self.code=self.root/'inputs'/'code';self.data=self.root/'inputs'/'data'
        self.code.mkdir(parents=True);self.data.mkdir()
        self.contents={'tools/__init__.py':b'','tools/example.py':b'VALUE=1\n'}
        self.make()
    def tearDown(self):self.temp.cleanup()
    def make(self,members=None):
        target=self.code/'source.zip'
        with zipfile.ZipFile(target,'w') as z:
            for name,value in (members or self.contents).items():
                info=zipfile.ZipInfo(name);info.external_attr=(stat.S_IFREG|0o644)<<16;z.writestr(info,value)
        manifest={'format':'irisx/public120-code-material-v1','reference':'owner/code/1',
                  'files':{k:{'sha256':sha(v),'bytes':len(v)} for k,v in self.contents.items()},
                  'source_identity':{k:sha(v) for k,v in self.contents.items()},
                  'archive':{'name':'source.zip','sha256':sha(target.read_bytes()),'bytes':target.stat().st_size}}
        (self.code/'manifest.json').write_bytes(raw(manifest))
        roles={'solver':'a'*64,'evaluator':'b'*64}
        (self.data/'public-data-material.json').write_bytes(raw({'format':'irisx/public120-data-material-v1','reference':'owner/data/1','role_manifests':roles}))
        self.pins={'code':{'reference':'owner/code/1','manifest_sha256':sha((self.code/'manifest.json').read_bytes()),'archive_sha256':manifest['archive']['sha256']},
                   'data':{'reference':'owner/data/1','manifest_sha256':sha((self.data/'public-data-material.json').read_bytes()),'role_manifests':roles}}
        self.kw=dict(pins=self.pins,input_root=str(self.root/'inputs'),code_root=str(self.code),data_root=str(self.data),source_parent=str(self.root/'source'),output_root=str(self.root/'output'),model_config={})
    def invoke(self,**changes):
        before=list(sys.path);bytecode=sys.dont_write_bytecode
        try:
            with mock.patch.dict(sys.modules):
                for k in list(sys.modules):
                    if k=='tools' or k.startswith('tools.') or k=='irisx' or k.startswith('irisx.'):sys.modules.pop(k)
                return load_reviewed_source(**(self.kw|changes))
        finally:sys.path[:]=before;sys.dont_write_bytecode=bytecode
    def test_exact_extract_and_repeat_no_evaluator_members_read(self):
        value=self.invoke();source=Path(value['source_root'])
        self.assertEqual((source/'tools/example.py').read_bytes(),self.contents['tools/example.py'])
        self.assertEqual(self.invoke(),value)
        self.assertFalse((self.data/'evaluator').exists())
    def test_exact_extracted_root_and_directory(self):
        for prefix in ('','source'):
            with self.subTest(prefix=prefix):
                self.make()
                base=self.code/prefix
                for name,value in self.contents.items():
                    target=base/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
                (self.code/'source.zip').unlink()
                result=self.invoke(source_parent=str(self.root/('extract-'+(prefix or 'root'))))
                self.assertFalse(result['source_archive_bytes_verified'])
                self.assertTrue(result['source_transport_mode'].startswith('verified-extracted-source'))
                import shutil
                shutil.rmtree(base/'tools')
                if prefix:base.rmdir()
    def test_ambiguous_archive_and_extracted_rejected(self):
        (self.code/'tools').mkdir();(self.code/'tools'/'__init__.py').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.invoke()
    def test_extracted_corruption_and_extra_rejected(self):
        for name,value in self.contents.items():
            target=self.code/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
        (self.code/'source.zip').unlink();(self.code/'tools/example.py').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'integrity'):self.invoke()
        (self.code/'tools/example.py').write_bytes(self.contents['tools/example.py']);(self.code/'unexpected').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'inventory'):self.invoke()
    def test_modified_existing_source_rejected(self):
        value=self.invoke();(Path(value['source_root'])/'tools/example.py').write_text('modified')
        with self.assertRaisesRegex(ValueError,'bytes differ'):self.invoke()
    def test_extra_existing_source_rejected(self):
        value=self.invoke();(Path(value['source_root'])/'extra').write_text('x')
        with self.assertRaisesRegex(ValueError,'inventory differs'):self.invoke()
    def test_input_overlap_precedes_any_path_inspection(self):
        for field,value in [('source_parent',str(self.root/'inputs')),('output_root',str(self.code/'bad'))]:
            with self.subTest(field=field),mock.patch.object(Path,'is_symlink',side_effect=AssertionError('inspection')):
                with self.assertRaisesRegex(ValueError,'overlaps'):self.invoke(**{field:value})
    def test_environment_overlap_precedes_inspection(self):
        with mock.patch.object(Path,'is_symlink',side_effect=AssertionError('inspection')):
            with self.assertRaisesRegex(ValueError,'overlap'):self.invoke(source_parent=str(self.root/'output-environment'))
    def test_source_output_overlap(self):
        with self.assertRaisesRegex(ValueError,'overlap'):self.invoke(output_root=str(self.root/'source'/'nested'))
    def test_traversal_and_double_slash_alias(self):
        with self.assertRaises(ValueError):self.invoke(output_root=str(self.root/'x/../out'))
        with self.assertRaisesRegex(ValueError,'overlap'):self.invoke(output_root='/'+str(self.code))
    def test_source_parent_symlink(self):
        (self.root/'linked').symlink_to(self.root/'inputs',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):self.invoke(source_parent=str(self.root/'linked'))
    def test_archive_extra_and_traversal_fail(self):
        for name in ['extra.py','../escape','/absolute']:
            self.make(self.contents|{name:b'x'})
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'archive members'):self.invoke()
    def test_archive_member_hash_differs(self):
        self.make(self.contents|{'tools/example.py':b'wrong'})
        with self.assertRaisesRegex(ValueError,'integrity'):self.invoke()
    def test_manifest_hash_and_notebook_archive_pin(self):
        self.pins['code']['manifest_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'manifest hash'):self.invoke()
        self.make();self.pins['code']['archive_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'archive differs'):self.invoke()
    def test_dataset_autodiscovery_only_exact_layouts(self):
        (self.root/'inputs'/'code').rename(self.root/'inputs'/'other')
        with self.assertRaisesRegex(ValueError,'exactly one'):self.invoke(code_root=None)
    def test_conflicting_import_rejected(self):
        with self.assertRaisesRegex(ValueError,'conflicting imported'):load_reviewed_source(**self.kw)

class NotebookTests(unittest.TestCase):
    def test_default_all_cells_inert(self):
        pins={'code':{'manifest_sha256':'a'*64},'data':{'manifest_sha256':'b'*64}}
        notebook=build(pins);namespace={}
        with mock.patch('builtins.open',side_effect=AssertionError('file open')),mock.patch.object(Path,'open',side_effect=AssertionError('Path.open')),mock.patch('os.mkdir',side_effect=AssertionError('mkdir')),mock.patch('builtins.print'):
            for cell in notebook['cells']:
                if cell['cell_type']=='code':exec(compile(''.join(cell['source']),'<notebook>','exec'),namespace)
        self.assertFalse(namespace['MANUAL_START']);self.assertFalse(namespace['ENABLE_MODEL'])
        self.assertIsNone(namespace['_PUBLIC_READY'])
        self.assertEqual(namespace['PROFILE'],'PUBLIC120')
    def test_builder_independent_of_pin_key_insertion_order(self):
        pins={'code':{'reference':'a/b/1','manifest_sha256':'a'*64,'archive_sha256':'c'*64},
              'data':{'reference':'a/c/1','manifest_sha256':'b'*64,'role_manifests':{'solver':'d'*64,'evaluator':'e'*64}}}
        shuffled=json.loads(json.dumps(pins,sort_keys=True))
        self.assertEqual(build(pins),build(shuffled))
    def test_manual_and_budget_values_strict(self):
        nb=build({'code':{'manifest_sha256':'a'*64},'data':{'manifest_sha256':'b'*64}})
        for key,value in [('MANUAL_START',1),('ENABLE_MODEL','yes'),('SESSION_SECONDS',7201),('PROFILE','FULL')]:
            ns={};exec(''.join(nb['cells'][1]['source']),ns);ns[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):exec(''.join(nb['cells'][2]['source']),ns)

if __name__=='__main__':unittest.main()
