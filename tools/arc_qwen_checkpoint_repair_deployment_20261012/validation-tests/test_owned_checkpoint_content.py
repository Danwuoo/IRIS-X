"""Exact final-source actual tiny main/failure plus explicit negative copies.

Production labels25/code13 in surrounding envelopes are fictional. Real owned
CPU bytes stay unchanged. No old source/old run is ever called final execution.
"""
from copy import deepcopy
import json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
VALIDATION=Path(__file__).resolve().parents[1]/'validation';ROOT=VALIDATION.parent
sys.path[:0]=[str(VALIDATION),str(Path(__file__).parent)]
import validate_transfer_outputs as v
from successor_fixture_helpers import make_synthetic_collector_fixture,release_path,source_for_release,source_for_mapping
SOURCE=ROOT/'final-source-freeze-001'
MAIN=ROOT/'evidence/owned-final-fixture-main';FAILURE=ROOT/'evidence/owned-final-fixture-before-load'
class Archive:
    def __init__(self,members):self.members=members
    def read(self,name):return self.members[name]
    def json(self,name):return v.strict_json(self.read(name))
    def put(self,name,value):self.members[name]=v.canonical(value)
class ActualFinalContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (MAIN/'terminal-receipt.json').is_file():raise unittest.SkipTest('actual final-source owned tiny main is pending')
        with zipfile.ZipFile(MAIN/'evidence.zip') as z:cls.members={n:z.read(n) for n in z.namelist()}
        cls.request=v.strict_json(cls.members['request.json']);cls.mapping=cls.request['source_identity']
        cls.source_root=source_for_mapping(cls.mapping);cls.source=v.SourceSnapshot(cls.source_root,cls.mapping)
    @classmethod
    def tearDownClass(cls):cls.source.close()
    def test_exact_genuine_final_tiny_main(self):
        result=v.validate_content(MAIN,self.mapping,source_root=self.source_root,allow_synthetic=True)
        self.assertTrue(result['valid']);self.assertTrue(result['synthetic']);self.assertEqual(result['status'],'TRANSFER_COMPLETE')
        self.assertFalse(result['science_complete']);self.assertFalse(result['operational_success']);self.assertFalse(result['goal_met'])
        self.assertEqual(result['source_identity_sha256'],v.digest(self.mapping));self.assertTrue(result['checkpoints']['schedule_config_records_source_identity_verified'])
        self.assertEqual(result['checkpoints']['global_checkpoint_count'],3)
    def test_actual_final_tiny_checkpoint_archive_bytes(self):
        result=v.validate_content(MAIN,self.mapping,source_root=self.source_root,allow_synthetic=True,verify_checkpoint_bytes=True)
        self.assertTrue(result['checkpoints']['verified_archive_bytes'])
    def test_production_rejects_genuine_tiny_main(self):
        with self.assertRaisesRegex(ValueError,'synthetic'):v.validate_content(MAIN,self.mapping,source_root=self.source_root)
    def test_no_target_escrow_json_read(self):
        original=v.ClosedArchive.json
        def checked(obj,name):
            if 'target-escrow' in name or '/upstream/data/evaluation/' in name:raise AssertionError('target opened')
            return original(obj,name)
        v.ClosedArchive.json=checked
        try:self.assertTrue(v.validate_content(MAIN,self.mapping,source_root=self.source_root,allow_synthetic=True)['valid'])
        finally:v.ClosedArchive.json=original
    def checkpoint_mutation(self,mutate,*,cid='sft1',expect=None):
        a=Archive(deepcopy(self.members));receipts=a.json('experiment/checkpoint-receipts.json');saved=receipts[cid]
        prefix='experiment/checkpoint-metadata/'+cid+'/';original=v.local_reference(saved['path'],self.request['output_root'])
        manifest=a.json(prefix+'manifest.json')['payload'];resume=a.json(prefix+'resume/state.json')['payload'];inference=a.json(prefix+'inference/adapter_model.safetensors.index.json')['payload']
        mutate(manifest,resume,inference,saved)
        # Fully rehash the explicitly corrupt metadata, source wrapper copies,
        # saved receipts and asset inventory. Semantic checks must still fail.
        manifest['binding_sha256']=v.native_digest(manifest['binding'])
        inference['binding']=deepcopy(manifest['binding']);inference['binding_sha256']=manifest['binding_sha256']
        resume['handle']['identity_sha256']=v.native_digest({k:manifest['binding'][k] for k in ('model','config','source')})
        inventory=a.json('checkpoint-assets-manifest.json')
        def raw(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
        def put(filename,value):
            data=raw(value);sha=v.raw_sha(data)
            inventory['files'][original+'/'+filename]={'bytes':len(data),'sha256':sha}
            a.put(prefix+filename,{'source_path':saved['path']+'/'+filename,'source_sha256':sha,'payload':value})
            return {'bytes':len(data),'sha256':sha}
        manifest['files']['resume/state.json']=put('resume/state.json',resume)
        manifest['files']['inference/adapter_model.safetensors.index.json']=put('inference/adapter_model.safetensors.index.json',inference)
        saved['inference_manifest_sha256']=manifest['files']['inference/adapter_model.safetensors.index.json']['sha256']
        manifest['payload_file_bytes']=sum(x['bytes'] for x in manifest['files'].values())
        saved['manifest_sha256']=put('manifest.json',manifest)['sha256']
        inventory['bytes']=sum(x['bytes'] for x in inventory['files'].values());a.put('checkpoint-assets-manifest.json',inventory);a.put('experiment/checkpoint-receipts.json',receipts)
        # Every full-state reload is re-bound as well, so stale hashes cannot
        # explain away the expected semantic rejection.
        reload=a.json('experiment/fresh-reload-'+str(saved['update'])+'.json');reload['loaded']['manifest_sha256']=saved['manifest_sha256'];a.put('experiment/fresh-reload-'+str(saved['update'])+'.json',reload)
        with self.assertRaisesRegex(ValueError,expect or '.'):
            v.validate_checkpoints(MAIN,a,self.request,self.source,complete=True)
    def test_rehashed_checkpoint_schedule_wrong(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding']['checkpoint_schedule'].__setitem__('allowed_updates',[0,8,16]),expect='schedule')
    def test_rehashed_missing_schedule(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding'].pop('checkpoint_schedule'))
    def test_rehashed_source_subset(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding'].__setitem__('source',{v.PACKAGE+'protocol.py':self.mapping[v.PACKAGE+'protocol.py']}),expect='source')
    def test_rehashed_config_changed(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding']['config'].__setitem__('learning_rate',.9),expect='identity|config')
    def test_rehashed_records_reordered(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding']['record_ids'].reverse(),expect='record')
    def test_rehashed_record_digest_changed(self):self.checkpoint_mutation(lambda m,r,i,s:m['binding'].__setitem__('records_sha256','a'*64),expect='identity|record')
    def test_rehashed_manifest_update(self):self.checkpoint_mutation(lambda m,r,i,s:m.__setitem__('update',16),expect='update')
    def test_rehashed_inference_update(self):self.checkpoint_mutation(lambda m,r,i,s:i.__setitem__('update',16),expect='update')
    def test_partial_checkpoint_prefix(self):
        a=Archive(deepcopy(self.members));receipts=a.json('experiment/checkpoint-receipts.json')
        a.put('experiment/checkpoint-receipts.json',{'base':receipts['base']})
        inventory=a.json('checkpoint-assets-manifest.json');inventory['complete_store']=False
        keep=v.local_reference(receipts['base']['path'],self.request['output_root'])+'/'
        inventory['files']={n:r for n,r in inventory['files'].items() if '/update-' not in n or n.startswith(keep)}
        inventory['bytes']=sum(r['bytes'] for r in inventory['files'].values());a.put('checkpoint-assets-manifest.json',inventory)
        result=v.validate_checkpoints(MAIN,a,self.request,self.source,complete=False)
        self.assertEqual(result['global_checkpoint_count'],1)
    def test_partial_cannot_skip_base_checkpoint(self):
        a=Archive(deepcopy(self.members));receipts=a.json('experiment/checkpoint-receipts.json');receipts.pop('base');a.put('experiment/checkpoint-receipts.json',receipts)
        with self.assertRaisesRegex(ValueError,'prefix'):v.validate_checkpoints(MAIN,a,self.request,self.source,complete=False)
    def test_deleted_inference_compact_metadata(self):
        a=Archive(deepcopy(self.members));a.members.pop('experiment/checkpoint-metadata/sft1/inference/adapter_model.safetensors.index.json')
        with self.assertRaises((ValueError,KeyError)):v.validate_checkpoints(MAIN,a,self.request,self.source,complete=True)
    def test_exact_active25_synthetic_complete_envelope(self):
        release=release_path()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            args=make_synthetic_collector_fixture(Path(temp)/'envelope',synthetic=True,template_release=release,owner_root=MAIN,source_root=self.source_root)
            result=v.validate_outputs(**args);self.assertEqual(result['version'],25);self.assertEqual(result['status'],'TRANSFER_COMPLETE');self.assertTrue(result['synthetic']);self.assertFalse(result['goal_met'])
            self.assertEqual(result['separate_checkpoint_presence'],'HTTP200_CONTENT_LENGTH_VERIFIED');self.assertFalse(result['checkpoint_archive_bytes_verified'])
            with self.assertRaisesRegex(ValueError,'synthetic'):v.validate_outputs(**{**args,'allow_synthetic':False})

class ActualFinalFailure(unittest.TestCase):
    def test_exact_active25_synthetic_actual_failure_envelope(self):
        if not (FAILURE/'terminal-receipt.json').is_file():self.skipTest('actual final-source owned before-load failure is pending')
        release=release_path()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            args=make_synthetic_collector_fixture(Path(temp)/'envelope',synthetic=True,template_release=release,owner_root=FAILURE,source_root=source_for_release(release))
            result=v.validate_outputs(**args);self.assertTrue(result['valid']);self.assertEqual(result['status'],'TRANSFER_FAILED');self.assertEqual(result['version'],25)
            self.assertFalse(result['operational_success']);self.assertFalse(result['science_complete']);self.assertFalse(result['goal_met'])
            self.assertEqual(result['checkpoints']['global_checkpoint_count'],0)
            self.assertFalse(result['checkpoints']['metadata_and_reload_receipts_verified'])
            self.assertEqual(result['separate_checkpoint_presence'],'UNKNOWN')

class HistoricalSeparation(unittest.TestCase):
    def test_old23_contract_rejected(self):
        release=ROOT.parent/'portfolio63-transfer-repair-20261012/release-candidate-002'
        if not release.is_dir():self.skipTest('old release omitted')
        m=v.json_file(release/'publication-manifest.json')
        with self.assertRaisesRegex(ValueError,'publication contract'):v.validate_launch(m,v.digest(m),{},{},{},None,release)
    def test_prior23_proof_unchanged(self):
        path=ROOT/'publication/PREDECESSOR-DESCRIPTORS.json'
        if not path.is_file():self.skipTest('predecessor descriptor omitted')
        self.assertEqual(v.file_sha(path),'ef9e66cc2473306c6a54e2dc930dfdd9a9096433b7fb8810287501a6067d5b6b')
        doc=v.json_file(path);self.assertEqual(doc['provider_status'],'COMPLETE');self.assertEqual(doc['runtime_status'],'TRANSFER_PARTIAL');self.assertFalse(doc['goal_met'])
    def test_precap_cpu_not_newsource(self):
        old=ROOT.parent/'portfolio63-transfer-repair-20261012';source=old/'cpu-source-freeze-001';owner=old/'cpu-owner-001'
        if not owner.is_dir():self.skipTest('historical CPU control omitted')
        with self.assertRaisesRegex(ValueError,'512MiB'):v.validate_content(owner,v.source_identity(source),source_root=source,allow_synthetic=True)
if __name__=='__main__':unittest.main()
