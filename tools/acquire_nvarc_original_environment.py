"""Acquire small exact-version public dependency files without executing them."""
from __future__ import annotations

import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, sha
from irisx.errors import ValidationError

REF = 'sorokin/pip-install-unsloth-flash-patch'
VERSION = 2
SCRIPT_VERSION = 272622465
DOCKER = 'gcr.io/kaggle-private-byod/python@sha256:320043e14c68293f1c946585b9257123385205a58af4b94b17d31868cae4e868'
PACKAGES = {'unsloth': '2025.9.7', 'unsloth_zoo': '2025.9.9',
            'transformers': '4.55.4', 'peft': '0.17.1', 'torch': '2.8.0', 'flash_attn': '2.8.2'}
FILES = ['qwen3.patch', 'unsloth/models/qwen3.py'] + [
    f'{name}-{version}.dist-info/METADATA' for name, version in PACKAGES.items()]
LIMIT = 2 * 1024**2


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def collect(folder):
    from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest
    from tools.execute_nvarc_overnight_sft import client_for, token
    require(not folder.exists(), 'new immutable exact dependency material identity required')
    folder.mkdir(parents=True)
    ledger = {'owner_decision': 'Decision 0054', 'ref': REF, 'version_number': VERSION,
              'expected_script_version_id': SCRIPT_VERSION, 'maximum_file_requests': len(FILES),
              'maximum_file_bytes': LIMIT, 'maximum_wall_seconds': 1200, 'requests_reserved': 0,
              'files_completed': 0, 'source_program_executions': 0, 'model_calls': 0,
              'paid_usd': 0, 'state': 'exact-public-dependency-acquisition', 'events': []}
    atomic(folder / 'acquisition.json', ledger)
    started = time.monotonic()
    try:
        with client_for(token()) as client:
            for name in FILES:
                require(time.monotonic() - started < 1200, 'dependency acquisition wall ceiling reached')
                event = {'file_name': name, 'state': 'reserved'}
                ledger['events'].append(event)
                ledger['requests_reserved'] += 1
                atomic(folder / 'acquisition.json', ledger)
                request = ApiDownloadKernelOutputRequest()
                request.owner_slug = 'sorokin'
                request.kernel_slug = 'pip-install-unsloth-flash-patch'
                request.version_number = VERSION
                request.file_path = name
                response = client.kernels.kernels_api_client.download_kernel_output(request)
                with response:
                    parts = urlsplit(response.url)
                    ids = [int(v) for v in re.findall(r'/(?:kf|kernels)/([0-9]+)/', parts.path)]
                    require(response.status_code == 200 and parts.scheme == 'https' and
                            parts.hostname == 'www.kaggleusercontent.com' and ids == [SCRIPT_VERSION],
                            'exact original dependency script-version download binding required')
                    declared = response.headers.get('Content-Length')
                    require(declared is None or int(declared) <= LIMIT, 'dependency file byte ceiling reached')
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        require(len(body) <= LIMIT and time.monotonic() - started < 1200,
                                'dependency body byte/wall ceiling reached')
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
                event.update(state='retained', bytes=len(body), sha256=sha(path),
                             download_host=parts.hostname, path_kernel_version_ids=ids)
                ledger['files_completed'] += 1
                atomic(folder / 'acquisition.json', ledger)
        ledger.update(state='complete-exact-public-dependency-files', wall_seconds=round(time.monotonic()-started, 3))
        atomic(folder / 'acquisition.json', ledger)
        return {k: ledger[k] for k in ('state', 'requests_reserved', 'files_completed', 'model_calls')}
    except BaseException as error:
        ledger.update(state='failed-retained-no-repeat', error_type=type(error).__name__,
                      http_status=getattr(getattr(error, 'response', None), 'status_code', None))
        atomic(folder / 'acquisition.json', ledger)
        raise ValidationError('exact public dependency acquisition failed; retained identity cannot be reused') from None


def verify(folder, source, index, notebook):
    ledger = json.loads((folder / 'acquisition.json').read_bytes())
    require(ledger['state'] == 'complete-exact-public-dependency-files' and
            ledger['ref'] == REF and type(ledger['version_number']) is int and ledger['version_number'] == VERSION and
            ledger['expected_script_version_id'] == SCRIPT_VERSION and
            ledger['requests_reserved'] == ledger['files_completed'] == len(FILES) and
            ledger['source_program_executions'] == ledger['model_calls'] == ledger['paid_usd'] == 0,
            'closed zero-execution exact dependency acquisition required')
    events = ledger['events']
    require(len(events) == len(FILES) and [event['file_name'] for event in events] == FILES,
            'closed ordered exact dependency files required')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    require(actual == set(FILES) | {'acquisition.json'}, 'closed dependency file inventory differs')
    inventory = {}
    for event in events:
        path = folder / event['file_name']
        require(not path.is_symlink() and path.stat().st_size <= LIMIT and event['state'] == 'retained' and
                path.stat().st_size == event['bytes'] and sha(path) == event['sha256'] and
                event['download_host'] == 'www.kaggleusercontent.com' and
                event['path_kernel_version_ids'] == [SCRIPT_VERSION], 'exact dependency file binding differs')
        inventory[event['file_name']] = {'bytes': event['bytes'], 'sha256': event['sha256']}
    provider = json.loads((source / 'provider-metadata.json').read_bytes())
    acquisition = json.loads((source / 'acquisition.json').read_bytes())
    require(provider['ref'] == REF and provider['currentVersionNumber'] == VERSION and
            provider['dockerImage'] == DOCKER and provider['isPrivate'] is False and
            acquisition['source_sha256'] == sha(source / 'source.ipynb') and
            acquisition['provider_metadata_sha256'] == sha(source / 'provider-metadata.json'),
            'exact acquired public source/version/Docker binding differs')
    original = json.loads(notebook.read_bytes())
    original_metadata = json.loads((notebook.parent / 'kernel-metadata.json').read_bytes())
    manifest = json.loads((ROOT / 'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
    require(sha(notebook) == manifest['notebooks']['qwen']['sha256'], 'frozen original Qwen notebook bytes differ')
    kaggle = original['metadata']['kaggle']
    require(original['metadata']['language_info']['version'] == '3.11.13' and
            kaggle['dockerImageVersionId'] == 31090 and original_metadata['docker_image'] == DOCKER and
            original_metadata['kernel_sources'] == [REF] and
            any(row.get('sourceId') == SCRIPT_VERSION for row in kaggle['dataSources']),
            'original Qwen notebook dependency version/Docker binding differs')
    public = json.loads((source / 'source.ipynb').read_bytes())
    cells = [''.join(row.get('source', [])) for row in public['cells'] if row.get('cell_type') == 'code']
    # Parse only the ordinary literal patch cell; never run installer or package code.
    patches = []
    for cell in cells:
        if cell.startswith('patch = b'):
            module = ast.parse(cell.split('\n!patch ', 1)[0])
            patches.extend(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                           and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'patch')
    require(len(patches) == 1 and isinstance(patches[0], bytes) and patches[0] == (folder / 'qwen3.patch').read_bytes(),
            'installer literal patch and exact output patch bytes differ')
    patched = (folder / 'unsloth/models/qwen3.py').read_text(encoding='utf-8')
    require('self.temp_O = torch.empty((bsz, 1, hidden_size)' in patched and
            'A = flash_attn_func(Qnn, Knn, Vnn)' in patched, 'original Qwen3 decode patch not present')
    versions = {}
    for name, version in PACKAGES.items():
        metadata = BytesParser().parsebytes((folder / f'{name}-{version}.dist-info/METADATA').read_bytes())
        require(metadata['Name'].lower().replace('-', '_') == name and metadata['Version'] == version,
                'exact output distribution metadata version differs')
        versions[name] = version
    read_index = json.loads((index / 'acquisition.json').read_bytes())
    rows = json.loads((index / 'partial-file-index.json').read_bytes())
    require(read_index['state'] == 'retained-public-dependency-index' and
            read_index['path_kernel_version_ids'] == [SCRIPT_VERSION] and
            read_index['file_index_sha256'] == sha(index / 'partial-file-index.json') and
            read_index['log_sha256'] == sha(index / 'public-installer.log') and len(rows) == 100 and
            all(row['path_kernel_version_ids'] == [SCRIPT_VERSION] for row in rows),
            'original dependency public output-index/log binding differs')
    log = json.loads((index / 'public-installer.log').read_text(encoding='utf-8'))
    success = [row['data'] for row in log if 'Successfully installed ' in row.get('data', '')]
    require(all(any(f'{name.replace("_", "-")}-{version}' in line or f'{name}-{version}' in line
                    for line in success) for name, version in versions.items()) and
            any('Python 3.11.13' in row.get('data', '') for row in log) and
            any('patching file /kaggle/working/unsloth/models/qwen3.py' in row.get('data', '') for row in log),
            'exact dependency installer completion/version/patch log differs')
    return {'format': 'irisx/nvarc-original-notebook-dependency-binding-v1', 'outcome': 'complete',
            'ref': REF, 'kernel_version': VERSION, 'script_version_id': SCRIPT_VERSION,
            'original_notebook_sha256': sha(notebook), 'source_sha256': sha(source / 'source.ipynb'),
            'original_kernel_metadata_sha256': sha(notebook.parent / 'kernel-metadata.json'),
            'provider_metadata_sha256': sha(source / 'provider-metadata.json'), 'docker_image': DOCKER,
            'python_version': '3.11.13', 'distribution_versions': versions, 'inventory': inventory,
            'acquisition_sha256': sha(folder / 'acquisition.json'),
            'index_acquisition_sha256': sha(index / 'acquisition.json'),
            'installer_log_sha256': sha(index / 'public-installer.log'),
            'literal_patch_matches_exact_output': True, 'patched_decode_observed': True,
            'generated_program_executions': 0, 'package_code_executions': 0, 'model_calls': 0,
            'full_environment_file_inventory_verified': False, 'historical_cuda_numerical_parity': False,
            'nemo_revision': None, 'megatron_revision': None,
            'proof_scope': 'original notebook binds exact dependency version; eight small output files and installer observations, not a reproduced full runtime'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    collect_parser = sub.add_parser('collect'); collect_parser.add_argument('--folder', type=Path, required=True)
    check = sub.add_parser('verify')
    for name in ('folder', 'source', 'index', 'notebook', 'output'):
        check.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'collect':
        result = collect(args.folder)
    else:
        require(not args.output.exists(), 'new independent dependency binding result required')
        result = verify(args.folder, args.source, args.index, args.notebook); atomic(args.output, result)
    print(json.dumps(result))
