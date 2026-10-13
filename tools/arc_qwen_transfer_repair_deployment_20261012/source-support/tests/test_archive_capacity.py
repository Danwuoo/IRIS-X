"""Real source exporter at384MiB expanded, with unchanged safety boundaries.

All inputs are generated schema-shaped CPU fixtures, not predictions or model
results. Hard links keep local disk usage modest; the ZIP writes/reads every byte
of every regular member independently and validates SHA256 and CRC32.
"""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'worktree'),str(ROOT/'worktree'/'src')]
from tools.arc_qwen_transfer_20261012 import runner
from tools.arc_qwen_transfer_20261012.protocol import canonical

class ArchiveCapacity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'author-evidence'/('archive-capacity-'+str(time.time_ns()));cls.base.mkdir()
        cls.proof=json.loads((ROOT/'cpu-owner-001/terminal-receipt.json').read_bytes())['closure_proof']
        cls.initial_free=shutil.disk_usage(cls.base).free
        if cls.initial_free<4*1024**3+1024**3:raise RuntimeError('capacity fixture requires4GiB retained disk reserve')
        trace={'input_tokens':1,'attention_mask_tokens':4096,'position_start':4095,'position_end':4095,
            'cache_before':4095,'cache_after':4096,'use_cache':True,'started_monotonic':1000.0,
            'completed_monotonic':1000.05,'deadline_monotonic':1175.0,'late':False,'finite_full_head':True}
        payload={'format':'irisx/synthetic-native-receipt-size-fixture-v1','synthetic':True,
            'forward_trace':[trace for _ in range(1024)],'output_token_ids':[1]*1024,'output_tokens':1024,'padding':''}
        target=512*1024;base=canonical(payload);payload['padding']='x'*(target-len(base))
        cls.blob=canonical(payload)
        assert len(cls.blob)==target
        cls.template=cls.base/'schema-shaped-512k.json';cls.template.write_bytes(cls.blob)
        cls.template_sha=hashlib.sha256(cls.blob).hexdigest();cls.receipt={'synthetic_only':True,'checks':{},'fixture_root':str(cls.base)}
    @classmethod
    def tearDownClass(cls):
        cls.receipt.update(free_bytes_before=cls.initial_free,free_bytes_after=shutil.disk_usage(cls.base).free,
            generation_hard_seconds=180,total_capacity_bytes=runner.MAX_TOTAL_BYTES,
            ordinary_member_bytes=runner.MAX_FILE_BYTES,diagnostic_member_bytes=runner.MAX_DIAGNOSTIC_BYTES,
            retained_disk_reserve_at_least4GiB=shutil.disk_usage(cls.base).free>=4*1024**3)
        (ROOT/'author-evidence/archive-capacity-receipt.json').write_text(json.dumps(cls.receipt,sort_keys=True,indent=2)+'\n')
    def linked_root(self,name,count):
        root=self.base/name;root.mkdir()
        for i in range(count):os.link(self.template,root/('%04d-native.json'%i))
        return root
    def test_01_actual384mib_exporter_hash_crc_readback(self):
        root=self.linked_root('expanded384mib',768);began=time.monotonic()
        with patch.object(runner,'MAX_TOTAL_BYTES',256*1024**2):
            with self.assertRaisesRegex(ValueError,'archive bound'):runner._output_inventory(root)
        result=runner.archive_closed(root,self.proof,deadline=time.monotonic()+180)
        with zipfile.ZipFile(root/'evidence.zip') as z:
            self.assertIsNone(z.testzip());self.assertEqual(len(z.namelist()),769)
            manifest=json.loads(z.read('archive-manifest.json'))
            expanded=0
            for info in z.infolist():
                digest=hashlib.sha256()
                with z.open(info) as src:
                    while block:=src.read(1024**2):digest.update(block);expanded+=len(block)
                if info.filename!='archive-manifest.json':
                    self.assertEqual(digest.hexdigest(),self.template_sha)
                    self.assertEqual(manifest['files'][info.filename]['sha256'],digest.hexdigest())
                    self.assertEqual(manifest['files'][info.filename]['bytes'],512*1024)
            self.assertGreater(expanded,384*1024**2);self.assertLess(expanded,512*1024**2)
        self.assertEqual(result['sha256'],runner.file_sha(root/'evidence.zip'))
        before=result['sha256']
        with self.assertRaisesRegex(ValueError,'consumed'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertEqual(runner.file_sha(root/'evidence.zip'),before)
        self.receipt['checks']['384MiB_actual_export']={'passed':True,'result':result,'expanded_bytes_including_manifest':expanded,
            'regular_members':768,'crc_all_members_verified':True,'sha256_all_members_verified':True,
            'old256MiB_policy_rejects_same_members':True,'repeat_identity_refused_without_overwrite':True,
            'elapsed_seconds':time.monotonic()-began}
    def test_02_above512_rejects_before_archive(self):
        root=self.linked_root('expanded528mib',1056)
        with self.assertRaisesRegex(ValueError,'archive bound'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertFalse((root/'archive-manifest.json').exists());self.assertFalse((root/'evidence.zip').exists())
        self.assertEqual(len(list(root.iterdir())),1056)
        self.receipt['checks']['528MiB_rejected']={'passed':True,'source_members_preserved':1056,'partial_archive_created':False}
    def test_03_manifest_inclusive512_boundary(self):
        root=self.linked_root('expanded512mib',1024)
        with self.assertRaisesRegex(ValueError,'manifest-inclusive'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertFalse((root/'archive-manifest.json').exists());self.assertFalse((root/'evidence.zip').exists())
        self.receipt['checks']['512MiB_plus_manifest_rejected']={'passed':True}
    def test_04_ordinary_and_diagnostic_member_caps_unchanged(self):
        for name,member,limit in [('ordinary','ordinary.json',16*1024**2),('diagnostic','full-diagnostics.json',64*1024**2)]:
            root=self.base/name;root.mkdir();path=root/member
            with path.open('wb') as out:out.truncate(limit+1)
            with self.assertRaisesRegex(ValueError,'member byte ceiling'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
            self.assertFalse((root/'evidence.zip').exists());self.assertEqual(path.stat().st_size,limit+1)
        self.receipt['checks']['member_caps_unchanged']={'passed':True,'ordinary':16*1024**2,'diagnostic':64*1024**2}
    def test_05_collision_preserves_existing_zip(self):
        root=self.linked_root('zip-collision',1);(root/'evidence.zip').write_bytes(b'original sentinel')
        with self.assertRaises(FileExistsError):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertEqual((root/'evidence.zip').read_bytes(),b'original sentinel')
        self.receipt['checks']['existing_zip_collision']={'passed':True,'existing_bytes_preserved':True}
    def test_06_expired_export_preserves_partial_and_refuses_reuse(self):
        root=self.linked_root('expired-deadline',1)
        with self.assertRaisesRegex(ValueError,'export deadline'):runner.archive_closed(root,self.proof,deadline=time.monotonic()-1)
        self.assertTrue((root/'archive-manifest.json').exists());self.assertTrue((root/'evidence.zip').exists())
        old=(root/'evidence.zip').read_bytes()
        with self.assertRaisesRegex(ValueError,'consumed'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertEqual((root/'evidence.zip').read_bytes(),old)
        self.assertEqual(runner.file_sha(root/'0000-native.json'),self.template_sha)
        self.receipt['checks']['expired_export']={'passed':True,'partial_evidence_preserved_not_reported_success':True,
            'closed_zip_handle':True,'retry_same_identity_refused':True,'original_input_preserved':True}
    def test_07_manifest_counts_towards12000_limit(self):
        root=self.base/'filecount12000';root.mkdir()
        for i in range(12000):(root/('%05d.json'%i)).write_bytes(b'{}\n')
        with self.assertRaisesRegex(ValueError,'manifest-inclusive'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        self.assertFalse((root/'evidence.zip').exists());self.assertEqual(len(list(root.iterdir())),12000)
        self.receipt['checks']['12000_inputs_plus_manifest_rejected']={'passed':True}
    def test_08_symlink_and_live_owner_still_reject(self):
        root=self.base/'symlink';root.mkdir();(root/'link.json').symlink_to(self.template)
        with self.assertRaisesRegex(ValueError,'symlink'):runner.archive_closed(root,self.proof,deadline=time.monotonic()+60)
        proof={**self.proof,'closed':False}
        with self.assertRaisesRegex(ValueError,'closure proof'):runner.archive_closed(root,proof,deadline=time.monotonic()+60)
        self.receipt['checks']['unsafe_entries_and_unclosed_owner_rejected']={'passed':True}
if __name__=='__main__':unittest.main(verbosity=2)
