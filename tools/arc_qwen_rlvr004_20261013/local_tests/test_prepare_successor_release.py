"""Source-only successor mechanics, exact inheritance and final approval gates."""
from pathlib import Path
import io
import json
import tempfile
import unittest
import zipfile

from tools.arc_qwen_rlvr004_20261013 import prepare_successor_release as build

REPO=Path(__file__).resolve().parents[3]
TOOL=REPO/'tools/arc_qwen_rlvr004_20261013'

def source_from_git():
    mapping=json.loads((TOOL/'runtime-path-map.json').read_bytes())
    return {name:(REPO/row['repository_path']).read_bytes() for name,row in mapping['files'].items()}

class SuccessorMechanics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.ordinary(REPO/'.irisx').mkdir(exist_ok=True)
        cls.old=source_from_git()
        cls.old_environment=(TOOL/'release/consumer-release/environment.json').read_bytes()

    def test_environment_only_three_namespace_paths_change(self):
        updated=json.loads(build.derive_environment(self.old_environment))
        original=json.loads(self.old_environment)
        changed={key for key in original['model_config'] if original['model_config'][key]!=updated['model_config'][key]}
        self.assertEqual(changed,{'contract_path','environment_lock_path','tokenizer_path'})
        self.assertEqual(updated['actual_environment'],original['actual_environment'])
        self.assertEqual(updated['native_identity_projection'],original['native_identity_projection'])
        for key in changed:self.assertIn('source005/runtime/',updated['model_config'][key])

    def test_changed_unreviewed_base_environment_rejected(self):
        with self.assertRaisesRegex(ValueError,'original reviewed environment'):
            build.derive_environment(self.old_environment+b'\n')

    def test_source_delta_and_normalized_pin_preserve257_baseline200(self):
        environment=build.derive_environment(self.old_environment)
        # Synthetic source-mechanics annotation only; never a reviewed repair.
        parent=self.old['owned_runtime/parent_scoring.py']+b'\n# synthetic source-only test annotation\n'
        files,archive,inventory,normal,source_sha=build.derive_source(self.old,parent,environment)
        self.assertEqual({n for n in files if files[n]!=self.old[n]},
                         {'owned_runtime/parent_scoring.py','owned_runtime/release.py'})
        self.assertEqual(sum(n.startswith('baseline/') for n in files),200)
        self.assertTrue(all(files[n]==self.old[n] for n in files if n.startswith('baseline/')))
        self.assertEqual(json.loads(inventory)['source_sha256'],source_sha)
        self.assertIn(normal.encode(),files['owned_runtime/release.py'])
        self.assertIn(build.sha(environment).encode(),files['owned_runtime/release.py'])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(len(z.namelist()),259)
            for item in z.infolist():
                self.assertEqual(item.date_time,(2026,10,12,0,0,0))
                self.assertEqual(z.read(item),files[item.filename])
        self.assertEqual(build.zip_blobs(files,stored=True),archive)

    def test_empty_repair_and_corrupt_release_self_pin_rejected(self):
        environment=build.derive_environment(self.old_environment)
        with self.assertRaisesRegex(ValueError,'nonempty'):
            build.derive_source(self.old,self.old['owned_runtime/parent_scoring.py'],environment)
        damaged=dict(self.old)
        damaged['owned_runtime/release.py']=damaged['owned_runtime/release.py'].replace(b'NORMALIZED_SOURCE_CONTRACT_SHA256',b'NOT_THE_SOURCE_CONTRACT_SHA256')
        with self.assertRaisesRegex(ValueError,'one normalized'):
            build.derive_source(damaged,self.old['owned_runtime/parent_scoring.py']+b'\n',environment)

    def test_final_mode_cannot_self_approve_or_create_output(self):
        with tempfile.TemporaryDirectory(dir=REPO/'.irisx',prefix='successor-final-guard-') as temporary:
            root=Path(temporary);output=root/'output'
            with self.assertRaisesRegex(ValueError,'independent reviews/proposal/collector'):
                build.assemble(base_root=root/'base',state_root=root/'state',evidence_root=root/'evidence',
                               parent_overlay=root/'overlay.py',parent_overlay_sha='a'*64,output_root=output,mode='final')
            self.assertFalse(output.exists())

    def test_missing_solver_namespace_review_is_blocked(self):
        with self.assertRaisesRegex(ValueError,'independent solver namespace proof'):
            build.dataset_namespace({},None,None)

    def test_unapproved_solver_review_cannot_open_dataset_references(self):
        base={'consumer-release/material_review.json':(TOOL/'release/consumer-release/material_review.json').read_bytes()}
        with tempfile.TemporaryDirectory(dir=REPO/'.irisx',prefix='solver-review-rejection-') as temporary:
            path=Path(temporary)/'review.json'
            raw=build.encoded({'format':'irisx/run005-solver-namespace-review-v1','status':'PENDING',
                               'path_substitutions':2,'reverse_byte_equality':True})
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'reviewed two-path'):
                build.dataset_namespace(base,path,build.sha(raw))

    def test_fake_pass_review_cannot_replace_original_solver_hash(self):
        base={'consumer-release/material_review.json':(TOOL/'release/consumer-release/material_review.json').read_bytes()}
        with tempfile.TemporaryDirectory(dir=REPO/'.irisx',prefix='solver-hash-rejection-') as temporary:
            root=Path(temporary);empty=root/'empty.json';empty.write_bytes(b'')
            ref={'path':str(empty),'bytes':0,'sha256':build.sha(b'')}
            raw=build.encoded({'format':'irisx/run005-solver-namespace-review-v1','status':'PASS',
                               'path_substitutions':2,'reverse_byte_equality':True,'old_solver':ref,'new_solver':ref})
            path=root/'review.json';path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'original reviewed target-free solver bytes'):
                build.dataset_namespace(base,path,build.sha(raw))

    def test_source_only_rebuild_does_not_need_operational_evidence(self):
        overlay=TOOL/'driver_path_repair/parent_scoring.py'
        self.assertTrue(overlay.is_file(),'tracked driver repair overlay is required for cold reconstruction')
        with tempfile.TemporaryDirectory(dir=REPO/'.irisx',prefix='successor-git-rebuild-') as temporary:
            output=Path(temporary)/'source'
            result=build.rebuild_source(repository_root=REPO,parent_overlay=overlay,
                                        parent_overlay_sha=build.sha(overlay.read_bytes()),output_root=output)
            self.assertEqual(result['status'],'EXACT_GIT_SOURCE_SUCCESSOR_REBUILT')
            self.assertFalse(result['operational_evidence_required'])
            self.assertEqual(build.sha((output/'source.zip').read_bytes()),result['source_archive_sha256'])
            mapping=json.loads((output/'runtime-path-map-run005.json').read_bytes())
            self.assertEqual(mapping['source_member_count'],259)
            self.assertEqual(mapping['files']['owned_runtime/parent_scoring.py']['repository_path'],overlay.relative_to(REPO).as_posix())
            self.assertEqual(build.sha((output/'release_run005.py').read_bytes()),mapping['files']['owned_runtime/release.py']['sha256'])
            retained=TOOL/'driver_path_repair'
            for generated,committed in (('SOURCE-FREEZE.json','SOURCE-FREEZE.json'),
                                        ('environment-run005.json','environment-run005.json'),
                                        ('runtime-path-map-run005.json','runtime-path-map-run005.json'),
                                        ('release_run005.py','release_run005.py')):
                self.assertEqual((output/generated).read_bytes(),(retained/committed).read_bytes())
            frozen=json.loads((retained/'SOURCE-FREEZE.json').read_bytes())
            self.assertEqual(build.sha((output/'source.zip').read_bytes()),frozen['source_archive_sha256'])

    def test_deployment_namespace_delta_keeps_family_and_other_helpers(self):
        declared=json.loads((TOOL/'release/notebook-release.json').read_bytes())['deployment']
        base={}
        for name in build.DEPLOYMENT_NAMES:
            raw=(TOOL/'support/deployment'/name).read_bytes()
            self.assertEqual({'bytes':len(raw),'sha256':build.sha(raw)},declared[name])
            base['code-payload/deployment/'+name]=raw
        wrapper=(TOOL/'support/assembly/verify_parent_wrappers.py').read_bytes()
        pinned=json.loads((TOOL/'release/publication-manifest.json').read_bytes())['parent_wrapper_verifier']
        self.assertEqual({'bytes':len(wrapper),'sha256':build.sha(wrapper)},{k:pinned[k] for k in ('bytes','sha256')})
        base['assembly/verify_parent_wrappers.py']=wrapper
        derived,wrappers=build.derive_deployment(base)
        self.assertEqual(derived['prepare_entry.py'],base['code-payload/deployment/prepare_entry.py'])
        self.assertEqual(derived['parent_entry.py'],base['code-payload/deployment/parent_entry.py'])
        self.assertIn(b"release.get('release_role')=='rlvr004'",derived['launch_notebook.py'])
        self.assertIn((build.DREF+'/18').encode(),derived['source_loader.py'])
        self.assertIn(build.RUN.encode(),derived['notebook_builder.py'])
        self.assertIn(build.SOURCE.encode(),derived['notebook_builder.py'])
        self.assertIn(build.ENVIRONMENT.encode(),wrappers)

    def test_zip_paths_reject_traversal_and_source_assembly_is_canonical(self):
        for name in ('../bad','/absolute','C:/bad','a\\b','a//b','a/./b'):
            with self.subTest(name=name),self.assertRaises(ValueError):build.relative(name)
        self.assertEqual(build.sha(build.zip_blobs(self.old,stored=True)),build.BASE_ARCHIVE)

if __name__=='__main__':unittest.main()
