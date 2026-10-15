"""Hash-reviewed POSIX runtime binding, without SDK or credential side effects.

Static loading checks only reviewed local configuration and runtime file metadata.
Actual interpreter isolation is checked separately, before the official SDK alone
loads credentials from this account's real HOME/.kaggle store.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import sysconfig
from types import MappingProxyType

FORMAT = 'irisx/run008-portable-posix-operator-config-v1'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
SAFE_INHERITED_ENV = frozenset(('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'REQUESTS_CA_BUNDLE',
    'SSL_CERT_FILE', 'SSL_CERT_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy'))
CHILD_ENV = SAFE_INHERITED_ENV | {'HOME', 'PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED'}
FORBIDDEN_AUTH_ENV = frozenset(('KAGGLE_API_TOKEN', 'KAGGLE_USERNAME', 'KAGGLE_KEY',
    'KAGGLE_IAP_TOKEN', 'KAGGLE_ENV', 'KAGGLE_API_ENDPOINT', 'KAGGLE_API_ENVIRONMENT',
    'KAGGLE_KERNEL_RUN_TYPE', 'KAGGLE_DATA_PROXY_URL', 'KAGGLE_API_V1_TOKEN',
    'KAGGLE_CONFIG_DIR', 'PYTHONPATH', 'PYTHONHOME'))
FORBIDDEN_TLS_ENV = frozenset(('CURL_CA_BUNDLE', 'REQUESTS_CLIENT_CERT', 'REQUESTS_CLIENT_KEY',
    'REQUESTS_CERT', 'SSL_CLIENT_CERT', 'SSL_CLIENT_KEY', 'SSLKEYLOGFILE', 'PYTHONHTTPSVERIFY',
    'SSL_NO_VERIFY', 'REQUESTS_VERIFY', 'REQUESTS_VERIFY_SSL', 'CURL_INSECURE'))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def lexical_path(value):
    need(type(value) is str or isinstance(value, Path), 'local_path_type')
    need('\x00' not in str(value) and len(str(value)) <= 4096, 'local_path_bounds')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == str(value)
         and not str(path).startswith('//'), 'local_absolute_normal_path')
    return path


def secure_path(value):
    path = lexical_path(value)
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'local_path_symlink')
    return path


def inside(path, root):
    return path == root or root in path.parents


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def bounded_read(path, cap):
    """Reject special files before open; verify one bounded, stable file identity."""
    path = secure_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= cap, 'local_bounded_regular_file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        need(stat.S_ISREG(opened.st_mode) and identity(opened) == identity(before), 'local_file_identity_changed')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        current = path.lstat()
        need(len(raw) <= cap and len(raw) == before.st_size, 'local_bounded_regular_file')
        need(stat.S_ISREG(current.st_mode) and identity(after) == identity(before) == identity(current),
             'local_file_identity_changed')
    return raw


def read_json(path, expected_sha=None):
    raw = bounded_read(path, 4 * 1024**2)
    if expected_sha is not None:
        need(is_sha(expected_sha) and hashlib.sha256(raw).hexdigest() == expected_sha, 'local_document_hash')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'local_duplicate_json_key')
            result[key] = value
        return result
    def finite(value):
        number = float(value)
        need(math.isfinite(number), 'local_nonfinite_json')
        return number
    try:
        document = json.loads(raw, object_pairs_hook=pairs, parse_float=finite,
                              parse_constant=lambda _: need(False, 'local_nonfinite_json'))
    except (RecursionError, UnicodeError) as error:
        raise ValueError('local_invalid_json') from error
    need(type(document) is dict, 'local_document_object')
    return document


@dataclass(frozen=True)
class FileBinding:
    path: Path
    sha256: str


@dataclass(frozen=True)
class RuntimeBinding:
    venv_prefix: Path
    executable: Path
    executable_resolved: Path
    executable_sha256: str
    python_version: tuple
    sdk_root: Path
    home: Path
    requests_ca_bundle: object


@dataclass(frozen=True)
class LocalConfig:
    repository_root: Path
    candidate_root: Path
    scratch_root: Path
    state_root: Path
    evidence_root: Path
    gpu_stop_path: Path
    runtime: RuntimeBinding
    versions: dict
    document_sha256: str
    publication_manifest_sha256: str


def real_home():
    need(os.name == 'posix' and os.getuid() == os.geteuid(), 'local_posix_account_required')
    home = secure_path(pwd.getpwuid(os.getuid()).pw_dir)
    need(home.is_dir() and os.environ.get('HOME') == str(home) and Path.home() == home,
         'native_real_account_home_required')
    return home


def verify_executable(runtime):
    """Only the selected executable leaf may be a single, pinned symlink."""
    path = lexical_path(runtime.executable)
    need(all(not parent.is_symlink() for parent in path.parents), 'native_executable_parent_link')
    target = secure_path(runtime.executable_resolved)
    need(path.resolve(strict=True) == target, 'native_executable_resolved_identity')
    if path.is_symlink():
        raw_target = Path(os.readlink(path))
        direct = raw_target if raw_target.is_absolute() else path.parent / raw_target
        direct = Path(os.path.normpath(str(direct)))
        need(secure_path(direct) == target, 'native_executable_indirect_link')
    else:
        need(path == target, 'native_executable_resolved_identity')
    info = target.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_mode & 0o111, 'native_executable_regular_executable')
    need(is_sha(runtime.executable_sha256) and
         hashlib.sha256(bounded_read(target, 128 * 1024**2)).hexdigest() == runtime.executable_sha256,
         'native_executable_bytes')


def requests_ca_guard(runtime, environment):
    """A review may bind existing Requests trust, never select a different CA."""
    need(not any(key in environment for key in FORBIDDEN_TLS_ENV), 'alternate_tls_environment')
    value = environment.get('REQUESTS_CA_BUNDLE')
    binding = runtime.requests_ca_bundle
    if binding is None:
        need(value is None, 'native_requests_ca_inherited_mismatch')
        return
    need(value == str(binding.path), 'native_requests_ca_inherited_mismatch')
    need(hashlib.sha256(bounded_read(binding.path, 1024**2)).hexdigest() == binding.sha256,
         'native_requests_ca_bytes')


def load_runtime(document):
    need(os.name == 'posix', 'local_posix_runtime_required')
    fields = {'venv_prefix', 'executable', 'python_version', 'sdk_root', 'home', 'requests_ca_bundle'}
    need(type(document) is dict and set(document) == fields, 'native_runtime_schema')
    prefix = secure_path(document['venv_prefix'])
    need(prefix.is_dir(), 'native_venv_prefix_required')
    # Metadata only: no interpreter, SDK, authentication or provider is invoked.
    pyvenv = secure_path(prefix / 'pyvenv.cfg')
    info = pyvenv.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= 65536, 'native_venv_config_required')
    version = document['python_version']
    need(type(version) is list and len(version) == 3 and
         all(type(item) is int and 0 <= item <= 999 for item in version) and
         version[:2] == [3, 12], 'native_python312_exact_patch_required')
    executable = document['executable']
    need(type(executable) is dict and set(executable) == {'path', 'resolved_path', 'sha256'},
         'native_executable_schema')
    path = lexical_path(executable['path'])
    need(path.parent == prefix / 'bin' and path.name in ('python', 'python3', 'python3.12'),
         'native_venv_executable_required')
    sdk_root = secure_path(document['sdk_root'])
    need(sdk_root.is_dir() and sdk_root == prefix / 'lib/python3.12/site-packages', 'native_sdk_root_required')
    home = secure_path(document['home'])
    need(home == real_home(), 'native_real_account_home_required')
    ca = document['requests_ca_bundle']
    if ca is not None:
        need(type(ca) is dict and set(ca) == {'path', 'sha256'} and is_sha(ca['sha256']),
             'native_requests_ca_schema')
        ca = FileBinding(secure_path(ca['path']), ca['sha256'])
    runtime = RuntimeBinding(prefix, path, secure_path(executable['resolved_path']), executable['sha256'],
                             tuple(version), sdk_root, home, ca)
    verify_executable(runtime)
    requests_ca_guard(runtime, os.environ)
    return runtime


def read_runtime(config_path, config_sha256):
    """Launcher-only static binding; the entry validates the full contract next."""
    need(is_sha(config_sha256), 'local_document_hash')
    document = read_json(config_path, config_sha256)
    config_schema(document)
    return load_runtime(document['runtime'])


def config_schema(document):
    fields = {'format', 'repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root',
              'gpu_stop_path', 'runtime', 'username', 'publication_manifest_sha256', 'versions', 'remote_predecessor'}
    need(set(document) == fields and document['format'] == FORMAT, 'local_config_schema')
    need(document['username'] == 'danielwuu' and is_sha(document['publication_manifest_sha256']), 'local_config_identity')


def load(config_path, config_sha256, manifest_path, manifest_sha256):
    need(is_sha(config_sha256) and is_sha(manifest_sha256), 'local_document_hash')
    document = read_json(config_path, config_sha256)
    config_schema(document)
    need(document['publication_manifest_sha256'] == manifest_sha256, 'local_config_identity')
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
    runtime = load_runtime(document['runtime'])
    versions = document['versions']
    need(type(versions) is dict and set(versions) == {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'}, 'local_version_schema')
    need(all(type(value) is int and 0 < value <= 2**31 - 1 for value in versions.values()), 'local_version_integer')
    need(versions['code'] == versions['code_predecessor'] + 1 and versions['inactive'] == versions['inactive_predecessor'] + 1 and versions['active'] == versions['inactive'] + 1, 'local_successor_versions')
    dataset = manifest['datasets']; notebook_rows = manifest['notebooks']
    need(type(dataset) is list and len(dataset) == 1 and type(dataset[0]) is dict, 'local_dataset_identity')
    need(type(notebook_rows) is list and len(notebook_rows) == 2 and all(type(row) is dict for row in notebook_rows), 'local_notebook_roles')
    notebooks = {row['role']: row for row in notebook_rows}
    need(dataset[0]['reference'] == DREF and type(dataset[0]['id']) is int and dataset[0]['id'] == 12504696, 'local_dataset_identity')
    for key in ('expected_predecessor_version', 'expected_version'):
        need(type(dataset[0][key]) is int, 'local_manifest_version_integer')
    need(dataset[0]['expected_predecessor_version'] == versions['code_predecessor'] and dataset[0]['expected_version'] == versions['code'], 'local_manifest_code_versions')
    need(set(notebooks) == {'inactive', 'rlvr004'}, 'local_notebook_roles')
    for role, predecessor, version in (('inactive', 'inactive_predecessor', 'inactive'), ('rlvr004', 'inactive', 'active')):
        row = notebooks[role]
        need(type(row['existing_notebook_id']) is int and row['existing_notebook_id'] == 138123872 and row['existing_notebook_reference'] == REF, 'local_notebook_identity')
        need(type(row['expected_predecessor_version']) is int and type(row['expected_version']) is int, 'local_manifest_version_integer')
        need(row['expected_predecessor_version'] == versions[predecessor] and row['expected_version'] == versions[version], 'local_manifest_notebook_versions')
        need(type(row['dataset_sources']) is list and row['dataset_sources'] and row['dataset_sources'][0] == DREF + '/' + str(versions['code']), 'local_manifest_code_pin')
    predecessor = document['remote_predecessor']
    need(type(predecessor) is dict and set(predecessor) == {'code_version', 'notebook_version', 'notebook_source_sha256', 'provider_status', 'snapshot_sha256'}, 'local_remote_predecessor_schema')
    need(type(predecessor['code_version']) is int and type(predecessor['notebook_version']) is int, 'local_remote_predecessor_version_integer')
    need(predecessor['code_version'] == versions['code_predecessor'] and predecessor['notebook_version'] == versions['inactive_predecessor'], 'local_remote_predecessor_versions')
    need(is_sha(predecessor['snapshot_sha256']) and is_sha(predecessor['notebook_source_sha256']) and predecessor['notebook_source_sha256'] == notebooks['inactive']['predecessor_source_sha256'], 'local_remote_predecessor_source')
    need(predecessor['provider_status'] in ('COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'), 'local_remote_predecessor_not_terminal')
    return LocalConfig(**paths, runtime=runtime, versions=MappingProxyType(dict(versions)),
                       document_sha256=config_sha256, publication_manifest_sha256=manifest_sha256)


def child_environment(runtime, inherited):
    need(inherited.get('HOME') == str(real_home()) == str(runtime.home), 'native_real_account_home_required')
    requests_ca_guard(runtime, inherited)
    environment = {key: value for key, value in inherited.items() if key in SAFE_INHERITED_ENV}
    environment.update(HOME=str(runtime.home), PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0')
    return environment


def runtime_guard(runtime):
    """Validate this process without opening the official credential store."""
    need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1 and sys.flags.ignore_environment == 1,
         'native_isolated_source_execution_required')
    need(sys.implementation.name == 'cpython' and tuple(sys.version_info[:3]) == runtime.python_version,
         'native_python_version_mismatch')
    need(secure_path(sys.prefix) == runtime.venv_prefix and sys.prefix != sys.base_prefix,
         'native_bound_venv_required')
    need(lexical_path(sys.executable) == runtime.executable, 'native_bound_executable_required')
    verify_executable(runtime)
    need(secure_path(sysconfig.get_path('purelib')) == runtime.sdk_root, 'native_sysconfig_sdk_root_mismatch')
    need(runtime.home == real_home(), 'native_real_account_home_required')
    need(not any(key in os.environ for key in FORBIDDEN_AUTH_ENV) and set(os.environ) <= CHILD_ENV,
         'alternate_auth_or_import_environment')
    need(os.environ.get('PYTHONDONTWRITEBYTECODE') == '1' and os.environ.get('PYTHONHASHSEED') == '0',
         'native_source_environment_required')
    requests_ca_guard(runtime, os.environ)
    return {'format': 'irisx/run008-portable-posix-runtime-boundary-v1',
            'python_version': list(runtime.python_version), 'executable_sha256': runtime.executable_sha256,
            'real_account_home': True, 'credential_contents_inspected': False}


def credential_guard(config):
    """Only filesystem metadata: credentials are loaded exclusively by official API."""
    runtime = config.runtime
    proof = runtime_guard(runtime)
    store = secure_path(runtime.home / '.kaggle')
    info = store.stat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o022,
         'native_official_store_directory')
    for name in ('kaggle.json', 'access_token', 'access_token.txt'):
        alternate = store / name
        need(not alternate.exists() and not alternate.is_symlink(), 'alternate_credential_store_not_allowed')
    path = secure_path(store / 'credentials.json'); info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= 65536 and
         info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600, 'native_existing_oauth_store_mode')
    return {**proof, 'format': 'irisx/run008-portable-posix-auth-boundary-v1', 'existing_official_store': True}
