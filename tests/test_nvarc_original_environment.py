"""The historical dependency binding must survive independently rehashed faults."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import acquire_nvarc_original_environment as evidence
from tools import stage_nvarc_original_environment as probe
from irisx.arc_nvarc_combined import atomic, sha
from irisx.errors import ValidationError


class OriginalEnvironmentEvidenceTests(unittest.TestCase):
    def fixture(self, root):
        files, source, index = [root / name for name in ('files', 'source', 'index')]
        files.mkdir(); source.mkdir(); index.mkdir()
        notebook = root / 'original.ipynb'
        atomic(notebook, {'metadata': {'language_info': {'version': '3.11.13'}, 'kaggle': {
            'dockerImageVersionId': 31090, 'dataSources': [{'sourceId': evidence.SCRIPT_VERSION}]}}})
        atomic(root / 'kernel-metadata.json', {'docker_image': evidence.DOCKER, 'kernel_sources': [evidence.REF]})
        manifest = root / 'trials/arc-agi-2-qwen35-nvarc/source-manifest.json'
        atomic(manifest, {'notebooks': {'qwen': {'sha256': sha(notebook)}}})
        patch_bytes = b'bound original decode patch\r\n'
        atomic(source / 'source.ipynb', {'cells': [{'cell_type': 'code', 'source':
            [f'patch = {patch_bytes!r}\n', '!patch --binary file patch\n']}]})
        atomic(source / 'provider-metadata.json', {'ref': evidence.REF, 'currentVersionNumber': 2,
            'dockerImage': evidence.DOCKER, 'isPrivate': False})
        atomic(source / 'acquisition.json', {'source_sha256': sha(source / 'source.ipynb'),
            'provider_metadata_sha256': sha(source / 'provider-metadata.json')})
        events = []
        for name in evidence.FILES:
            path = files / name; path.parent.mkdir(parents=True, exist_ok=True)
            if name == 'qwen3.patch':
                path.write_bytes(patch_bytes)
            elif name == 'unsloth/models/qwen3.py':
                path.write_text('raise RuntimeError("must never execute package source")\n'
                    'self.temp_O = torch.empty((bsz, 1, hidden_size), dtype=dtype)\n'
                    'A = flash_attn_func(Qnn, Knn, Vnn)\n', encoding='utf-8')
            else:
                package = name.split('-', 1)[0]; version = evidence.PACKAGES[package]
                path.write_text(f'Name: {package}\nVersion: {version}\n', encoding='utf-8')
            events.append({'file_name': name, 'state': 'retained', 'bytes': path.stat().st_size,
                'sha256': sha(path), 'download_host': 'www.kaggleusercontent.com',
                'path_kernel_version_ids': [evidence.SCRIPT_VERSION]})
        ledger = {'state': 'complete-exact-public-dependency-files', 'ref': evidence.REF,
            'version_number': 2, 'expected_script_version_id': evidence.SCRIPT_VERSION,
            'requests_reserved': 8, 'files_completed': 8, 'source_program_executions': 0,
            'model_calls': 0, 'paid_usd': 0, 'events': events}
        atomic(files / 'acquisition.json', ledger)
        atomic(index / 'partial-file-index.json', [{'path_kernel_version_ids': [evidence.SCRIPT_VERSION]}] * 100)
        atomic(index / 'public-installer.log', [{'data': 'Successfully installed ' + ' '.join(
            f'{name}-{version}' for name, version in evidence.PACKAGES.items())},
            {'data': 'Python 3.11.13'}, {'data': 'patching file /kaggle/working/unsloth/models/qwen3.py'}])
        atomic(index / 'acquisition.json', {'state': 'retained-public-dependency-index',
            'path_kernel_version_ids': [evidence.SCRIPT_VERSION],
            'file_index_sha256': sha(index / 'partial-file-index.json'),
            'log_sha256': sha(index / 'public-installer.log')})
        return files, source, index, notebook

    def test_complete_binding_never_executes_package_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); args = self.fixture(root)
            with patch.object(evidence, 'ROOT', root):
                result = evidence.verify(*args)
            self.assertEqual(result['distribution_versions']['transformers'], '4.55.4')
            self.assertTrue(result['literal_patch_matches_exact_output'])
            self.assertEqual(result['package_code_executions'], 0)
            self.assertFalse(result['full_environment_file_inventory_verified'])
            self.assertFalse(result['historical_cuda_numerical_parity'])

    def test_rehashed_wrong_script_or_distribution_is_rejected(self):
        for fault in ('script', 'version', 'decode'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); args = self.fixture(root); files = args[0]
                ledger = json.loads((files / 'acquisition.json').read_bytes())
                if fault == 'script':
                    ledger['events'][0]['path_kernel_version_ids'] = [evidence.SCRIPT_VERSION + 1]
                else:
                    name = 'peft-0.17.1.dist-info/METADATA' if fault == 'version' else 'unsloth/models/qwen3.py'
                    target = files / name
                    target.write_text('Name: peft\nVersion: 0.21.0\n' if fault == 'version' else 'A = new_backend(Q,K,V)\n', encoding='utf-8')
                    row = next(row for row in ledger['events'] if row['file_name'] == name)
                    row.update(bytes=target.stat().st_size, sha256=sha(target))
                atomic(files / 'acquisition.json', ledger)
                with patch.object(evidence, 'ROOT', root), self.assertRaises(ValidationError):
                    evidence.verify(*args)
    def test_rehashed_source_patch_and_extra_file_are_rejected(self):
        for fault in ('patch', 'extra'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); args = self.fixture(root); files, source = args[:2]
                if fault == 'patch':
                    atomic(source / 'source.ipynb', {'cells': [{'cell_type': 'code', 'source': ["patch = b'other'\n"]}]})
                    ledger = json.loads((source / 'acquisition.json').read_bytes())
                    ledger['source_sha256'] = sha(source / 'source.ipynb'); atomic(source / 'acquisition.json', ledger)
                else:
                    (files / 'unverified.py').write_text('pass\n', encoding='utf-8')
                with patch.object(evidence, 'ROOT', root), self.assertRaises(ValidationError):
                    evidence.verify(*args)


class OriginalEnvironmentProbeTests(unittest.TestCase):
    def test_private_cpu_transport_and_rehashed_gpu_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); tokenizer=root/'model';tokenizer.mkdir()
            for name in probe.TOKENIZER_FILES:
                atomic(tokenizer/name, {'test':name})
            atomic(root/'independent-verification.json', {'inventory':{name:{'bytes':(tokenizer/name).stat().st_size,
                'sha256':sha(tokenizer/name)} for name in probe.TOKENIZER_FILES}})
            proof=root/'proof.json';atomic(proof,{})
            package=root/'package'
            with patch.object(probe,'TOKENIZER',tokenizer), patch.object(probe,'BINDING',proof), patch.object(probe,'binding',return_value={}):
                observed=probe.stage(package,'nvarc-original-qwen3-environment-999')
                self.assertEqual(observed['model_calls'],0)
                self.assertEqual(observed['hardware'],'CPU only')
                meta_path=package/'kernel/kernel-metadata.json'
                meta=json.loads(meta_path.read_bytes());self.assertFalse(meta['enable_gpu'])
                self.assertFalse(meta['enable_internet']);self.assertEqual(meta['model_sources'],[])
                meta['enable_gpu']=True;atomic(meta_path,meta)
                summary_path=package/'stage-summary.json';summary=json.loads(summary_path.read_bytes())
                summary['inventory']['kernel/kernel-metadata.json']=sha(meta_path);atomic(summary_path,summary)
                with self.assertRaises(ValidationError):probe.preflight(package)


if __name__ == '__main__':
    unittest.main()
