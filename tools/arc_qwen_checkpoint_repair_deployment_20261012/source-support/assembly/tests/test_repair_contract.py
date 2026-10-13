"""Generation-repair release regressions using exact emitted notebook code."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_release as builder
from exercise_notebook_config import exercise
CANDIDATE=Path(os.environ.get('QWEN_CANDIDATE',builder.ROOT/'release-candidate-001'))


class RepairContract(unittest.TestCase):
    def test_exact_emitted_run_cell_builds_full_outer_schema(self):
        with tempfile.TemporaryDirectory() as td:
            r=exercise(CANDIDATE,Path(td)/'fixture')
            self.assertEqual(r['status'],'PASS')
            self.assertTrue(r['exact_run_cell_executed'])
            self.assertEqual(r['request_config']['execution_cutoff_seconds'],42000)
            self.assertEqual(r['request_config']['outer_cutoff_seconds'],42180)
            self.assertEqual(r['request_config']['provider_runtime_seconds'],42300)
            self.assertEqual(r['request_config']['output_root'],'/kaggle/working/irisx-qwen14b-transfer-20261012-run003')
            self.assertEqual(r['request_config']['source_parent'],'/kaggle/working/irisx-qwen14b-transfer-20261012-source003')

    def test_all_final_descriptors_resolve_and_hash(self):
        self.assertEqual(builder.verify_descriptors(CANDIDATE)['status'],'PASS')

    def test_exact_version_roles_and_unchanged_material_pins(self):
        current=json.loads((CANDIDATE/'publication-manifest.json').read_bytes())
        prior=json.loads((builder.PRIOR_RELEASE/'publication-manifest.json').read_bytes())
        self.assertEqual(current['format'],'irisx/qwen14b-transfer-checkpoint-repair-publication-contract-v1')
        self.assertEqual((current['datasets'][0]['expected_predecessor_version'],current['datasets'][0]['expected_version']),(12,13))
        a,b=current['notebooks']
        self.assertEqual((a['role'],a['expected_predecessor_version'],a['expected_version']),('inactive',23,24))
        self.assertEqual((b['role'],b['expected_predecessor_version'],b['expected_version']),('transfer003',24,25))
        self.assertEqual(a['predecessor_source_sha256'],builder.PREDECESSOR_SOURCE)
        for spec in (a,b):
            self.assertEqual(spec['dataset_sources'][1:],prior['notebooks'][0]['dataset_sources'][1:])
            self.assertEqual(spec['model_sources'],prior['notebooks'][0]['model_sources'])
            self.assertEqual(spec['competition_sources'],prior['notebooks'][0]['competition_sources'])
            self.assertEqual(spec['docker_image'],prior['notebooks'][0]['docker_image'])
        self.assertEqual((CANDIDATE/'MATERIAL-ADDENDUM.json').read_bytes(),(builder.PRIOR_RELEASE/'MATERIAL-ADDENDUM.json').read_bytes())

    def test_misnamed_approval_descriptor_fails(self):
        manifest=json.loads((CANDIDATE/'publication-manifest.json').read_bytes())
        # The historic descriptor mismatch must fail before an alias is created.
        manifest['runtime_source_approval']={'path':'independent-runtime-approval.json','bytes':1,'sha256':'0'*64}
        original=builder.regular
        def read(path):
            if Path(path)==CANDIDATE/'publication-manifest.json':return builder.encoded(manifest)
            return original(path)
        with patch.object(builder,'regular',side_effect=read),self.assertRaises(FileNotFoundError):
            builder.verify_descriptors(CANDIDATE)

    def test_actual_build_emits_renamed_approval_descriptor(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-reviewed-assembly-') as td:
            root=Path(td);files,_=builder.collect()
            approval=root/'arbitrary-input-name.json'
            approval.write_text(json.dumps({'format':'irisx/independent-transfer-checkpoint-runtime-review-v1',
                'approved':True,'known_blockers':[],'synthetic_fixture_only':True,
                'source_identity_sha256':builder.sha(builder.canonical({n:builder.sha(raw) for n,raw in files.items() if Path(n).suffix in ('.py','.json','.jinja')})),
                'runtime_source_identity':{n:builder.sha(raw) for n,raw in files.items() if n.startswith(builder.RUNTIME_PREFIX) or n==builder.SHARED_CHECKPOINT}}))
            result=builder.build(root/'candidate',runtime_approval=approval)
            manifest=json.loads((root/'candidate/publication-manifest.json').read_bytes())
            row=manifest['runtime_source_approval']
            self.assertEqual(row['path'],'RUNTIME-SOURCE-APPROVAL.json')
            self.assertEqual((root/'candidate'/row['path']).read_bytes(),approval.read_bytes())
            self.assertFalse((root/'candidate'/approval.name).exists())
            self.assertEqual(builder.verify_descriptors(root/'candidate')['status'],'PASS')

    def test_inherited_tiny_is_qualified_and_caps_preserved(self):
        freeze=json.loads((CANDIDATE/'SOURCE-FREEZE.json').read_bytes())
        manifest=json.loads((CANDIDATE/'publication-manifest.json').read_bytes())
        self.assertEqual(freeze['genuine_tiny_inner_source_identity_sha256'],builder.GENUINE_TINY_INNER_IDENTITY_SHA)
        self.assertEqual(freeze['frozen_inner_source_identity_sha256'],builder.AUTHOR_INNER_IDENTITY_SHA)
        self.assertNotEqual(freeze['genuine_tiny_inner_source_identity_sha256'],freeze['frozen_inner_source_identity_sha256'])
        self.assertEqual(manifest['terminal_contract']['archive_caps']['evidence_expanded_bytes'],512*1024**2)
        self.assertEqual(manifest['terminal_contract']['archive_caps']['evidence_archive_bytes'],544*1024**2)
        self.assertEqual(manifest['upload_authorities'],['https://storage.googleapis.com:443','https://www.googleapis.com:443'])

    def test_policy_is_bound_to_exact_source_and_budget(self):
        policy=json.loads((CANDIDATE/'GENERATION-CALL-POLICY.json').read_bytes())
        manifest=json.loads((CANDIDATE/'code-payload/manifest.json').read_bytes())
        self.assertEqual(policy['source_sha256'],manifest['source_identity'][policy['source_member']])
        self.assertEqual(policy['runtime_policy_sha256'],builder.sha(builder.canonical(policy['runtime_policy'])))
        self.assertEqual((policy['generation_hard_seconds'],policy['generation_work_seconds'],policy['likelihood_hard_seconds'],policy['likelihood_work_seconds']),(180,175,120,115))


    def test_source_bound_checkpoint_policy_and_shared_baseline_delta(self):
        publication=json.loads((CANDIDATE/'publication-manifest.json').read_bytes())
        policy=json.loads((CANDIDATE/publication['checkpoint_policy']['path']).read_bytes())
        identities=json.loads((CANDIDATE/'code-payload/manifest.json').read_bytes())['source_identity']
        self.assertEqual(policy['format'],'irisx/transfer003-source-bound-checkpoint-policy-v1')
        self.assertEqual(set(policy['contracts']),{'global','ttt','fixture'})
        for key,updates in [('global',[0,64,256]),('ttt',[0,8,16]),('fixture',[0,1,2])]:
            self.assertEqual(policy['contracts'][key]['allowed_updates'],updates)
            self.assertIs(policy['contracts'][key]['fixture_only'],key=='fixture')
        self.assertEqual(set(policy['source_sha256']),{builder.RUNTIME_PREFIX+'checkpoint_policy.py',builder.RUNTIME_PREFIX+'protocol.py',builder.SHARED_CHECKPOINT})
        for name,digest in policy['source_sha256'].items():self.assertEqual(digest,identities[name])
        freeze=json.loads((CANDIDATE/'SOURCE-FREEZE.json').read_bytes())
        self.assertEqual(set(freeze['prior_changed']),builder.ALLOWED_CHANGED)
        self.assertEqual(set(freeze['prior_added']),builder.ALLOWED_ADDED)
        self.assertEqual(set(freeze['baseline_changed']),{builder.SHARED_CHECKPOINT})
        self.assertEqual((CANDIDATE/'GENERATION-CALL-POLICY.json').read_bytes(),(builder.PRIOR_RELEASE/'GENERATION-CALL-POLICY.json').read_bytes())

    def test_exact_roles_differ_only_two_switches_epoch_patch_only_one_assignment(self):
        inactive=json.loads((CANDIDATE/'iris-x-qwen14b-transfer-inactive.ipynb').read_bytes())
        active=json.loads((CANDIDATE/'iris-x-qwen14b-transfer-active-template.ipynb').read_bytes())
        normalized=copy.deepcopy(active)
        source=''.join(normalized['cells'][1]['source'])
        source=source.replace('MANUAL_START = True','MANUAL_START = False').replace('ENABLE_MODEL = True','ENABLE_MODEL = False')
        normalized['cells'][1]['source']=source.splitlines(keepends=True)
        self.assertEqual(normalized,inactive)
        patched=copy.deepcopy(active);before=''.join(active['cells'][1]['source'])
        after=before.replace('PREDISPATCH_EPOCH = None','PREDISPATCH_EPOCH = 2000000000')
        patched['cells'][1]['source']=after.splitlines(keepends=True)
        self.assertEqual(sum(a!=b for a,b in zip(before.splitlines(),after.splitlines())),1)
        self.assertEqual([i for i,(a,b) in enumerate(zip(active['cells'],patched['cells'])) if a!=b],[1])
        import ast
        left=ast.parse(before);right=ast.parse(after)
        changes=[(a,b) for a,b in zip(left.body,right.body) if ast.dump(a)!=ast.dump(b)]
        self.assertEqual(len(changes),1);self.assertEqual(changes[0][0].targets[0].id,'PREDISPATCH_EPOCH')
        self.assertIsNone(changes[0][0].value.value);self.assertEqual(changes[0][1].value.value,2000000000)

    def test_exact_material_model_and_runtime_pins_except_code_review_identity(self):
        old=json.loads((builder.PRIOR_RELEASE/'pins.json').read_bytes())
        current=json.loads((CANDIDATE/'pins.json').read_bytes())
        for value in (old,current):
            value.pop('code');value.pop('release')
        self.assertEqual(current,old)

    def test_predecessor_partial_and_checkpoint_header_scope_retained(self):
        predecessor=json.loads((CANDIDATE/'PREDECESSOR-EVIDENCE.json').read_bytes())
        self.assertEqual(predecessor['numeric_notebook_version'],23)
        self.assertEqual(predecessor['provider_status'],'COMPLETE')
        self.assertEqual(predecessor['runtime_status'],'TRANSFER_PARTIAL')
        self.assertFalse(predecessor['science_complete']);self.assertFalse(predecessor['operational_success'])
        self.assertFalse(predecessor['whole_provider_inventory_verified'])
        self.assertFalse(predecessor['checkpoint_archive_bytes_verified'])
        self.assertEqual(predecessor['checkpoint_metadata_only']['body_consumed_bytes'],0)
        self.assertEqual(builder.sha((CANDIDATE/'PREDECESSOR-DESCRIPTORS.json').read_bytes()),builder.PREDECESSOR_DESCRIPTORS_SHA)

if __name__=='__main__':unittest.main(verbosity=2)
