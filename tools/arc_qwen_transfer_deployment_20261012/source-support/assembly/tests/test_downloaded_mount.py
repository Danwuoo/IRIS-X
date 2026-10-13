"""Synthetic local-code mount exercise; no publication or actual download claim."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
PREVIEW=Path(os.environ.get('QWEN_CANDIDATE',HERE.parent/'preview-006'))
spec=importlib.util.spec_from_file_location('mount_acceptance',HERE/'accept_downloaded_mount.py')
mount=importlib.util.module_from_spec(spec);spec.loader.exec_module(mount)


class DownloadedMountFixture(unittest.TestCase):
    def test_synthetic_candidate_actual_embedded_loader_owned_and_zero_model(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-only-mount-') as td:
            root=Path(td);candidate=root/'synthetic-candidate';candidate.mkdir()
            manifest=json.loads((PREVIEW/'publication-manifest.json').read_bytes())
            # A fixture envelope only. It is never published or retained as source approval.
            manifest['source_review_only']=False
            manifest['synthetic_fixture_only']=True
            (candidate/'publication-manifest.json').write_text(json.dumps(manifest))
            notebook=next(n for n in manifest['notebooks'] if n['role']=='inactive')['path']
            shutil.copyfile(PREVIEW/notebook,candidate/notebook)
            (candidate/'expected-launcher').mkdir()
            shutil.copyfile(PREVIEW/'expected-launcher/owned_process_guard.py',candidate/'expected-launcher/owned_process_guard.py')
            receipt=root/'synthetic-code-receipt.json';receipt.write_text('{"synthetic_fixture_only":true}')
            result=mount.accept(candidate,PREVIEW/'code-payload',receipt,root/'acceptance')
            self.assertEqual(result['status'],'PASS')
            body=json.loads(Path(result['path']).read_bytes())
            self.assertTrue(body['owned_tree_closed'])
            self.assertEqual(body['model_calls'],0)
            self.assertEqual(body['worker_result']['source_transport_mode'],'verified-archive')
            self.assertTrue(body['worker_result']['synthetic_non_code_metadata_only'])
            self.assertFalse(body['process_tree_proof']['forced'])
            self.assertEqual(body['code_receipt_sha256'],mount.sha(receipt.read_bytes()))

    def test_preview_envelope_is_blocked_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-preview-gate-') as td:
            root=Path(td);receipt=root/'fixture.json';receipt.write_text('{}')
            preview=root/'preview';preview.mkdir()
            manifest=json.loads((PREVIEW/'publication-manifest.json').read_bytes());manifest['source_review_only']=True
            (preview/'publication-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'reviewed source required'):
                mount.accept(preview,PREVIEW/'code-payload',receipt,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main(verbosity=2)
