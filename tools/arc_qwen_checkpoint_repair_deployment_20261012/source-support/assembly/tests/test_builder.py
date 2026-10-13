"""No-model release-builder policy tests. Approval documents here are synthetic fixtures."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_release as builder


class BuilderPolicies(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='transfer-assembly-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_zip_reproducible_exact_and_relative(self):
        files={'b.txt':b'b','a/a.py':b'pass\n'}
        builder.zip_files(self.root/'one.zip',files)
        builder.zip_files(self.root/'two.zip',dict(reversed(list(files.items()))))
        self.assertEqual((self.root/'one.zip').read_bytes(),(self.root/'two.zip').read_bytes())
        with zipfile.ZipFile(self.root/'one.zip') as z:
            self.assertEqual(z.namelist(),sorted(files))
            self.assertTrue(all(i.date_time==(2026,10,12,0,0,0) for i in z.infolist()))
        with self.assertRaises(FileExistsError):builder.zip_files(self.root/'one.zip',files)

    def test_unsafe_names_denied(self):
        for name in ('','/absolute','../parent','a/../b','a//b','a/./b','a\\b','a:b','a\nb'):
            with self.subTest(name=name),self.assertRaises(ValueError):builder.safe_name(name)

    def test_single_link_regular_and_no_symlink(self):
        p=self.root/'a';p.write_bytes(b'a')
        self.assertEqual(builder.regular(p),b'a')
        link=self.root/'link';link.symlink_to(p)
        with self.assertRaisesRegex(ValueError,'symlink'):builder.regular(link)
        hard=self.root/'hard';os.link(p,hard)
        with self.assertRaisesRegex(ValueError,'single-link'):builder.regular(p)

    def test_approval_requires_exact_complete_runtime_source_and_explicit_true(self):
        files={builder.RUNTIME_PREFIX+'x.py':b'x=1\n',builder.RUNTIME_PREFIX+'README.md':b'fixture',
               'tools/baseline.py':b'pass\n',builder.SHARED_CHECKPOINT:b'fixture_checkpoint=True\n'}
        identity={k:builder.sha(v) for k,v in files.items() if k.startswith(builder.RUNTIME_PREFIX) or k==builder.SHARED_CHECKPOINT}
        p=self.root/'fixture-approval.json'
        for approval in ({'runtime_source_identity':identity},{'approved':1,'runtime_source_identity':identity},
                         {'approved':True,'runtime_source_identity':{}},
                         {'approved':True,'runtime_source_identity':{**identity,builder.RUNTIME_PREFIX+'extra.py':'0'*64}}):
            p.write_text(json.dumps(approval))
            with self.assertRaises(ValueError):builder.approval_check(p,files)
        p.write_text(json.dumps({'format':'irisx/independent-transfer-checkpoint-runtime-review-v1','approved':True,'known_blockers':[],'runtime_source_identity':identity,'source_identity_sha256':builder.sha(builder.canonical({n:builder.sha(raw) for n,raw in files.items() if Path(n).suffix in ('.py','.json','.jinja')})),'synthetic_fixture_only':True}))
        row,raw=builder.approval_check(p,files)
        self.assertEqual(row['path'],'RUNTIME-SOURCE-APPROVAL.json')
        self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest())
        changed={**files,builder.RUNTIME_PREFIX+'x.py':b'x=2\n'}
        with self.assertRaisesRegex(ValueError,'exact runtime bytes'):builder.approval_check(p,changed)
        shared_changed={**files,builder.SHARED_CHECKPOINT:b'fixture_checkpoint=False\n'}
        with self.assertRaisesRegex(ValueError,'exact runtime bytes'):builder.approval_check(p,shared_changed)

    def test_closed_baseline_and_staged_runtime_collection(self):
        files,baseline=builder.collect()
        self.assertEqual(len(baseline),175)
        self.assertEqual({n for n in baseline if builder.sha(files[n])!=baseline[n]},{builder.SHARED_CHECKPOINT})
        self.assertEqual(builder.sha(files[builder.EXCLUSIONS]),builder.EXCLUSIONS_SHA)
        self.assertLessEqual(sum(map(len,files.values())),16*1024**2)
        self.assertNotIn('tests/test_transfer_runtime.py',files)
        self.assertTrue(all(n.endswith(('.py','.json','.md','.jinja','.txt')) or n in baseline for n in files))

    def test_new_candidate_destination_cannot_reuse_or_overlap(self):
        with self.assertRaisesRegex(ValueError,'fresh unlinked'):builder.build(self.root)
        with self.assertRaisesRegex(ValueError,'overlaps source'):builder.build(builder.WORK/'never-create-test-output')
        with self.assertRaisesRegex(ValueError,'overlaps source'):builder.build(builder.HERE/'never-create-test-output')
        self.assertFalse((builder.WORK/'never-create-test-output').exists())


if __name__=='__main__':unittest.main(verbosity=2)
