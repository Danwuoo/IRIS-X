"""CPU-only real shared-library and independent-consumer regression coverage."""
from pathlib import Path
import copy,importlib.util,json,os,shutil,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'source'))
import owned_runtime
spec=importlib.util.spec_from_file_location('owned_runtime.run007_test',HERE/'environment_v2.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
sys.path.insert(0,str(HERE.parent/'release/terminal-consumer'))
import consumer
cspec=importlib.util.spec_from_file_location('consumer.run007_test',HERE/'release_checks.py')
c=importlib.util.module_from_spec(cspec);cspec.loader.exec_module(c)


@unittest.skipUnless(sys.platform=='linux' and shutil.which('gcc'),'Linux /proc and C compiler required for actual loader tests')
class RealLoaderTests(unittest.TestCase):
    def fixture(self,case):
        args=[sys.executable,'-B']+(['-O'] if sys.flags.optimize else [])+[str(HERE/'fixture_runner.py'),case]
        completed=subprocess.run(args,capture_output=True,text=True,timeout=50,check=True)
        row=json.loads(completed.stdout);self.assertIs(row['fixture_only'],True)
        self.assertEqual(len(row['diagnostics']),1)
        return row
    def test_actual_owned_api_map_and_consumer(self):
        row=self.fixture('owned');self.assertTrue(row['accepted']);self.assertTrue(row['consumer_verified'])
        self.assertEqual(row['diagnostics'][0]['status'],'PASS')
        self.assertTrue(all(m['file_identity_verified'] for m in row['observation']['verified_mappings']))
    def test_actual_identical_fixed_driver_alias_and_consumer(self):
        row=self.fixture('alias');self.assertTrue(row['accepted']);self.assertTrue(row['consumer_verified'])
        self.assertTrue(any(m['location']=='fixed-driver-alias' for m in row['observation']['verified_mappings']))
    def test_actual_identical_versioned_alias_and_consumer(self):
        row=self.fixture('versioned_alias');self.assertTrue(row['accepted']);self.assertTrue(row['consumer_verified'])
    def test_actual_multi_component_vendor_backend_alias_and_consumer(self):
        row=self.fixture('multi_component_alias');self.assertTrue(row['accepted']);self.assertTrue(row['consumer_verified'])
        self.assertEqual(len(row['observation']['verified_libraries']),4)
        self.assertTrue(any(r['member']=='nvidia/cudnn/lib/libcudnn_engines_runtime_compiled.so.9' for r in row['observation']['verified_mappings']))
    def test_foreign_identical_bytes_outside_fixed_directories_rejected(self):
        row=self.fixture('foreign_exact');self.assertFalse(row['accepted']);self.assertIn('outside fixed',row['error']['message'])
        failed=[r for r in row['diagnostics'][0]['mapped_libraries'] if 'error' in r]
        self.assertEqual(len(failed),1);self.assertIsNotNone(failed[0]['sha256']);self.assertTrue(failed[0]['file_identity_verified'])
    def test_foreign_backend_bytes_rejected_and_digest_recorded(self):
        row=self.fixture('foreign_bytes');self.assertFalse(row['accepted']);self.assertIn('exact pinned wheel',row['error']['message'])
        failed=[r for r in row['diagnostics'][0]['mapped_libraries'] if 'error' in r]
        self.assertIsNotNone(failed[0]['sha256'])
    def test_deleted_actual_mapping_rejected(self):
        row=self.fixture('deleted');self.assertFalse(row['accepted']);self.assertIn('deleted',row['error']['message'])
        self.assertTrue(any('(deleted)' in r['path'] for r in row['diagnostics'][0]['mapped_libraries']))
    def test_mixed_exact_api_and_foreign_transitive_backend_rejected(self):
        row=self.fixture('mixed');self.assertFalse(row['accepted']);self.assertIn('exact pinned wheel',row['error']['message'])
        self.assertGreaterEqual(len(row['diagnostics'][0]['mapped_libraries']),3)
    def test_replaced_matching_path_does_not_hide_original_mapped_inode(self):
        row=self.fixture('replaced_inode');self.assertFalse(row['accepted']);self.assertIn('deleted',row['error']['message'])
    def test_tampered_actual_mapped_library_rejected(self):
        row=self.fixture('tampered_alias');self.assertFalse(row['accepted']);self.assertIn('exact pinned wheel',row['error']['message'])
    def test_tampered_installed_library_rejected_before_map_admission(self):
        row=self.fixture('installed_tampered');self.assertFalse(row['accepted']);self.assertIn('cuDNN file bound',row['error']['message'])
        self.assertEqual(row['diagnostics'][0]['stage'],'verify-complete-installed-wheel-set')
    def test_unknown_actual_backend_rejected(self):
        row=self.fixture('unknown_member');self.assertFalse(row['accepted']);self.assertIn('no exact pinned',row['error']['message'])
    def test_current_api_mismatch_still_rejected(self):
        row=self.fixture('api_mismatch');self.assertFalse(row['accepted']);self.assertIn('runtime differs',row['error']['message'])
        self.assertTrue(row['diagnostics'][0]['mapped_libraries'])
        self.assertTrue(all(r['sha256'] is not None and r['verified'] is False for r in row['diagnostics'][0]['mapped_libraries']))
    def test_independent_consumer_rejects_mapping_receipt_mutations(self):
        original=self.fixture('alias')['observation']
        for field,value in (('sha256','0'*64),('bytes',1),('inode',True),('file_identity_verified',1),
                            ('member','nvidia/cudnn/lib/libcudnn_unknown.so.9'),('path','/unapproved/libcudnn.so.9'),
                            ('location','anything')):
            with self.subTest(field=field):
                row=copy.deepcopy(original);alias=next(r for r in row['verified_mappings'] if r['location']=='fixed-driver-alias')
                alias[field]=value
                with self.assertRaises(ValueError):c._verify_cudnn_mapping_v2(row,row['verified_libraries'],row['mapped_library_paths'],{Path(row['verified_libraries'][0]['path']).parent})
        row=copy.deepcopy(original);row['verified_mappings'].pop()
        with self.assertRaises(ValueError):c._verify_cudnn_mapping_v2(row,row['verified_libraries'],row['mapped_library_paths'],{Path(row['verified_libraries'][0]['path']).parent})


class BoundaryTests(unittest.TestCase):
    def test_mapping_bounds_and_missing_map(self):
        for raw in ('','x'*(16*1024**2+1),'1-2 r-xp 0 bad 1 /x/libcudnn.so.9'):
            with self.assertRaises(ValueError):e._mapping_snapshot(raw)
    def test_inconsistent_kernel_identity_rejected(self):
        with self.assertRaises(ValueError):e._mapping_snapshot('1-2 r-xp 0 00:01 1 /x/libcudnn.so.9\n2-3 r-xp 0 00:01 2 /x/libcudnn.so.9')
    def test_nonfinite_and_bool_deadline_still_rejected(self):
        for value in (True,float('inf'),float('nan'),time.monotonic()-1):
            with self.assertRaises(ValueError):e._check_time(value)
    def test_alias_role_rejects_wrong_major_or_unversioned(self):
        self.assertNotEqual(e._library_key('libcudnn.so.8'),e._library_key('libcudnn.so.9'))
        for name in ('libcudnn.so','libcudnn.so.9.backup','other.so.9','libcudnn__ops.so.9','libcudnn_ops_.so.9'):
            with self.assertRaises(ValueError):e._library_key(name)
    @unittest.skipUnless(sys.platform=='linux','Linux kernel file identities required')
    def test_escaped_symlink_and_forged_inode_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'libcudnn.so.9';path.write_bytes(b'fixture-only')
            info=path.stat();device=f'{os.major(info.st_dev):x}:{os.minor(info.st_dev):x}'
            rows=[{'member':'nvidia/cudnn/lib/libcudnn.so.9','path':str(path),'sha256':e.file_sha(path),'bytes':info.st_size}]
            aliases={k:str(root) for k in e.ALIAS_DIRECTORIES}
            with self.assertRaisesRegex(ValueError,'kernel-mapped'):
                e._verified_mappings(f'1-2 r-xp 0 {device} {info.st_ino+1} {path}',rows,root,deadline=time.monotonic()+2,diagnostic={},alias_roots=aliases)
            with self.assertRaisesRegex(ValueError,'ambiguous'):
                e._verified_mappings(f'1-2 r-xp 0 {device} {info.st_ino} {root}/libcudnn\\040.so.9',rows,root,deadline=time.monotonic()+2,diagnostic={},alias_roots=aliases)
            link=root/'linked';link.mkdir();target=link/'libcudnn.so.9'
            try:target.symlink_to(path)
            except OSError:self.skipTest('host cannot create symlink fixture')
            with self.assertRaisesRegex(ValueError,'no-link'):
                e._verified_mappings(f'1-2 r-xp 0 {device} {info.st_ino} {target}',rows,root,deadline=time.monotonic()+2,diagnostic={},alias_roots=aliases)
    def test_source_owned_alias_policy_matches_existing_driver_policy(self):
        from owned_runtime.parent_scoring import TRUSTED_DRIVER_LIBRARY_DIRECTORIES
        self.assertEqual(e.ALIAS_DIRECTORIES,TRUSTED_DRIVER_LIBRARY_DIRECTORIES)
    def test_source_lock_policy_and_fullwheel_descriptor_unchanged(self):
        original_spec=importlib.util.spec_from_file_location('owned_runtime.original_environment_v2',HERE.parent/'source/owned_runtime/environment_v2.py')
        original=importlib.util.module_from_spec(original_spec);original_spec.loader.exec_module(original)
        self.assertEqual((e.POLICY,e.LOCK_SHA256,e.FORMAT,e.ENVIRONMENT_KEYS),(original.POLICY,original.LOCK_SHA256,original.FORMAT,original.ENVIRONMENT_KEYS))


if __name__=='__main__':unittest.main()
