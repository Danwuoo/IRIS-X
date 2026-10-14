"""Explicit native paths, versions and unchanged official wrapper boundary.

Configuration loading has no authentication or provider effects. The launcher
uses the existing wrapper-owned environment; official SDK owns credential I/O.
"""
from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType

FORMAT = 'irisx/run008-native-operator-config-v1'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
WRAPPER_SHA256 = '46134808e2705d45d70bdc9aadd26a1e1863628d3d045a32a507efa56616b4bc'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def secure_path(value):
    need(type(value) in (str, Path) or isinstance(value, Path), 'local_path_type')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == str(value), 'local_absolute_normal_path')
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'local_path_symlink')
    return path


def inside(path, root):
    return path == root or root in path.parents


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_json(path, expected_sha=None):
    path = secure_path(path)
    need(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= 4 * 1024**2, 'local_bounded_config')
    raw = path.read_bytes()
    if expected_sha is not None:
        need(is_sha(expected_sha) and hashlib.sha256(raw).hexdigest() == expected_sha, 'local_document_hash')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'local_duplicate_json_key')
            result[key] = value
        return result
    document = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'local_nonfinite_json'))
    need(type(document) is dict, 'local_document_object')
    return document


@dataclass(frozen=True)
class LocalConfig:
    repository_root: Path
    candidate_root: Path
    scratch_root: Path
    state_root: Path
    evidence_root: Path
    gpu_stop_path: Path
    native_wrapper: Path
    versions: dict
    document_sha256: str
    publication_manifest_sha256: str


def load(config_path, config_sha256, manifest_path, manifest_sha256):
    need(os.name == 'posix', 'local_posix_runtime_required')
    document = read_json(config_path, config_sha256)
    fields = {'format', 'repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root', 'gpu_stop_path',
              'native_wrapper', 'username', 'publication_manifest_sha256', 'versions', 'remote_predecessor'}
    need(set(document) == fields and document['format'] == FORMAT, 'local_config_schema')
    need(document['username'] == 'danielwuu' and document['publication_manifest_sha256'] == manifest_sha256, 'local_config_identity')
    manifest = read_json(manifest_path, manifest_sha256)
    paths = {key: secure_path(document[key]) for key in ('repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root', 'gpu_stop_path')}
    repository = paths['repository_root']; scratch = paths['scratch_root']
    need(repository.is_dir() and (repository / '.git').exists(), 'local_repository_required')
    need(secure_path(manifest_path).parent == paths['candidate_root'] and paths['candidate_root'].is_dir(), 'local_candidate_manifest_root')
    # Existing source is tracked; operational state must be ignored or outside it.
    if inside(scratch, repository):
        need(inside(scratch, repository / '.irisx') and scratch != repository / '.irisx', 'local_ignored_scratch_required')
    need(scratch != repository and not inside(repository, scratch), 'local_scratch_repository_overlap')
    for key in ('state_root', 'evidence_root', 'gpu_stop_path'):
        need(inside(paths[key], scratch) and paths[key] != scratch, 'local_state_outside_reviewed_scratch')
    need(paths['state_root'] != paths['evidence_root'] and not inside(paths['state_root'], paths['evidence_root']) and not inside(paths['evidence_root'], paths['state_root']), 'local_state_evidence_overlap')
    wrapper = document['native_wrapper']
    need(type(wrapper) is dict and set(wrapper) == {'path', 'sha256'}, 'native_wrapper_schema')
    native_wrapper = secure_path(wrapper['path'])
    need(native_wrapper == repository.parent/'kaggle_setup/kaggle.sh' and wrapper['sha256'] == WRAPPER_SHA256, 'native_wrapper_identity')
    need(native_wrapper.is_file() and native_wrapper.stat().st_size <= 65536 and hashlib.sha256(native_wrapper.read_bytes()).hexdigest() == WRAPPER_SHA256, 'native_wrapper_bytes')
    versions = document['versions']
    need(type(versions) is dict and set(versions) == {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'}, 'local_version_schema')
    need(all(type(value) is int and value > 0 for value in versions.values()), 'local_version_integer')
    need(versions['code'] == versions['code_predecessor'] + 1 and versions['inactive'] == versions['inactive_predecessor'] + 1 and versions['active'] == versions['inactive'] + 1, 'local_successor_versions')
    dataset = manifest['datasets']; notebooks = {row['role']: row for row in manifest['notebooks']}
    need(len(dataset) == 1 and dataset[0]['reference'] == DREF and dataset[0]['id'] == 12504696, 'local_dataset_identity')
    need(dataset[0]['expected_predecessor_version'] == versions['code_predecessor'] and dataset[0]['expected_version'] == versions['code'], 'local_manifest_code_versions')
    need(set(notebooks) == {'inactive', 'rlvr004'}, 'local_notebook_roles')
    for role, predecessor, version in (('inactive', 'inactive_predecessor', 'inactive'), ('rlvr004', 'inactive', 'active')):
        row = notebooks[role]
        need(row['existing_notebook_id'] == 138123872 and row['existing_notebook_reference'] == REF, 'local_notebook_identity')
        need(row['expected_predecessor_version'] == versions[predecessor] and row['expected_version'] == versions[version], 'local_manifest_notebook_versions')
        need(row['dataset_sources'][0] == DREF + '/' + str(versions['code']), 'local_manifest_code_pin')
    predecessor = document['remote_predecessor']
    need(type(predecessor) is dict and set(predecessor) == {'code_version', 'notebook_version', 'notebook_source_sha256', 'provider_status', 'snapshot_sha256'}, 'local_remote_predecessor_schema')
    need(predecessor['code_version'] == versions['code_predecessor'] and predecessor['notebook_version'] == versions['inactive_predecessor'], 'local_remote_predecessor_versions')
    need(is_sha(predecessor['snapshot_sha256']) and is_sha(predecessor['notebook_source_sha256']) and predecessor['notebook_source_sha256'] == notebooks['inactive']['predecessor_source_sha256'], 'local_remote_predecessor_source')
    need(predecessor['provider_status'] in ('COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'), 'local_remote_predecessor_not_terminal')
    return LocalConfig(**paths, native_wrapper=native_wrapper, versions=MappingProxyType(dict(versions)),
                       document_sha256=config_sha256, publication_manifest_sha256=manifest_sha256)



def credential_guard(config):
    """Only filesystem metadata: credentials are loaded exclusively by official API."""
    import sys
    base=config.native_wrapper.parent
    need(sys.flags.isolated==1 and sys.flags.dont_write_bytecode==1,'native_isolated_source_execution_required')
    need(Path(sys.prefix)==base/'venv','existing_native_venv_required')
    home=secure_path(base/'home');store=secure_path(home/'.kaggle')
    need(Path.home()==home and os.environ.get('HOME')==str(home) and os.environ.get('KAGGLE_CONFIG_DIR')==str(store), 'native_wrapper_environment_required')
    need(config.native_wrapper==config.repository_root.parent/'kaggle_setup/kaggle.sh' and hashlib.sha256(config.native_wrapper.read_bytes()).hexdigest()==WRAPPER_SHA256,'native_wrapper_bytes')
    forbidden={'KAGGLE_API_TOKEN','KAGGLE_USERNAME','KAGGLE_KEY','KAGGLE_IAP_TOKEN','KAGGLE_ENV','KAGGLE_API_ENDPOINT','KAGGLE_API_ENVIRONMENT','KAGGLE_KERNEL_RUN_TYPE','KAGGLE_DATA_PROXY_URL','KAGGLE_API_V1_TOKEN','PYTHONPATH','PYTHONHOME'}
    need(not any(os.environ.get(key) for key in forbidden),'alternate_auth_or_import_environment')
    for name in ('kaggle.json','access_token','access_token.txt'):
        need(not (store/name).exists(),'alternate_credential_store_not_allowed')
    path=secure_path(store/'credentials.json');info=path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=65536 and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600,'native_existing_oauth_store_mode')
    return {'format':'irisx/run008-native-auth-boundary-v1','wrapper_sha256':WRAPPER_SHA256,'existing_official_store':True,'credential_contents_inspected':False}
