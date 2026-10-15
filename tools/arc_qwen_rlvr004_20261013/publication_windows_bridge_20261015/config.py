"""Hash-reviewed WSL owner binding for the Windows official SDK bridge.

Static loading checks only reviewed local configuration and runtime file metadata.
Actual interpreter isolation is checked separately, before the official SDK alone
loads credentials inside the selected native Windows account's existing store.
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

FORMAT = 'irisx/run008-windows-bridge-operator-config-v1'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
SAFE_INHERITED_ENV = frozenset(('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'REQUESTS_CA_BUNDLE',
    'SSL_CERT_FILE', 'SSL_CERT_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy', 'WSL_INTEROP'))
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
    interop_environment_sha256: dict


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
    windows_bridge: dict


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
    fields = {'venv_prefix', 'executable', 'python_version', 'sdk_root', 'home', 'requests_ca_bundle', 'interop_environment_sha256'}
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
                             tuple(version), sdk_root, home, ca, document['interop_environment_sha256'])
    verify_executable(runtime)
    requests_ca_guard(runtime, os.environ)
    interop_guard(runtime, os.environ)
    return runtime


def read_runtime(config_path, config_sha256):
    """Launcher-only static binding; the entry validates the full contract next."""
    need(is_sha(config_sha256), 'local_document_hash')
    document = read_json(config_path, config_sha256)
    config_schema(document)
    return load_runtime(document['runtime'])


def config_schema(document):
    fields = {'format', 'repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root',
              'gpu_stop_path', 'runtime', 'windows_bridge', 'username', 'publication_manifest_sha256', 'versions', 'remote_predecessor'}
    need(set(document) == fields and document['format'] == FORMAT, 'local_config_schema')
    need(document['username'] == 'danielwuu' and is_sha(document['publication_manifest_sha256']), 'local_config_identity')


def load(config_path, config_sha256, manifest_path, manifest_sha256, *, recovery=False):
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
                       document_sha256=config_sha256, publication_manifest_sha256=manifest_sha256,
                       windows_bridge=load_windows_bridge(document['windows_bridge'],versions, recovery=recovery))


def child_environment(runtime, inherited):
    need(inherited.get('HOME') == str(real_home()) == str(runtime.home), 'native_real_account_home_required')
    requests_ca_guard(runtime, inherited)
    interop_guard(runtime, inherited)
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
    interop_guard(runtime, os.environ)
    return {'format': 'irisx/run008-portable-posix-runtime-boundary-v1',
            'python_version': list(runtime.python_version), 'executable_sha256': runtime.executable_sha256,
            'real_account_home': True, 'credential_contents_inspected': False}


def credential_guard(config):
    """WSL checks runtime and native evidence only; no WSL credential store."""
    proof = runtime_guard(config.runtime)
    load_windows_bridge(config.windows_bridge, config.versions)
    return {**proof, 'format': 'irisx/windows-bridge-wsl-boundary-v1',
            'credential_contents_inspected': False, 'native_oauth_verified': False}


def interop_guard(runtime, inherited):
    selected = runtime.interop_environment_sha256
    need(type(selected) is dict and set(selected) == {'WSL_INTEROP'}
         and is_sha(selected['WSL_INTEROP']), 'reviewed_wsl_interop_required')
    value = inherited.get('WSL_INTEROP')
    need(type(value) is str and hashlib.sha256(value.encode()).hexdigest() == selected['WSL_INTEROP'],
         'wsl_interop_environment_changed')
    path = secure_path(value)
    need(str(path).startswith('/run/WSL/') and path.name.endswith('_interop')
         and stat.S_ISSOCK(path.stat().st_mode), 'wsl_interop_socket_required')
    need(not inherited.get('WSLENV'), 'unreviewed_cross_os_environment_mapping')


def load_windows_bridge(document, versions, *, recovery=False):
    """Bind public source/runtime metadata and genuine synthetic native evidence.

    This is a structural source/receipt check. Existing independent action review
    remains the authority; a JSON declaration never admits provider execution.
    """
    from pathlib import PureWindowsPath
    need(type(document) is dict and set(document) ==
         {'executable', 'supervisor', 'configuration', 'native_acceptance'}, 'windows_bridge_schema')
    for key in ('executable', 'supervisor', 'configuration'):
        row = document[key]
        need(type(row) is dict and set(row) == {'wsl_path', 'native_path', 'sha256'}
             and is_sha(row['sha256']), 'windows_bridge_file_binding')
        native = row['native_path']
        need(type(native) is str and len(native) <= 4096 and not any(ord(c)<32 for c in native),
             'windows_bridge_native_path')
        path = PureWindowsPath(native)
        need(path.is_absolute() and re.fullmatch('[A-Za-z]:',path.drive) is not None
             and native == str(path) and all(p not in ('','..','.') and ':' not in p
                 and not p.endswith(('.', ' ')) for p in path.parts[1:]), 'windows_bridge_native_path')
        expected = '/mnt/' + path.drive[0].lower() + '/' + '/'.join(path.parts[1:])
        need(row['wsl_path'] == expected, 'windows_bridge_exact_drive_mapping')
        raw = bounded_read(row['wsl_path'],128*1024**2)
        need(hashlib.sha256(raw).hexdigest() == row['sha256'], 'windows_bridge_file_bytes')
    need(type(recovery) is bool, 'windows_recovery_mode_type')
    native = read_json(document['configuration']['wsl_path'],document['configuration']['sha256'])
    expected_format = 'irisx/run008-windows-sdk-recovery-runtime-v1' if recovery else 'irisx/run008-windows-sdk-runtime-v1'
    need(native.get('format') == expected_format
         and native.get('account') == 'danielwuu' and native.get('versions') == dict(versions),
         'windows_bridge_native_configuration')
    native_sources = {'win_runtime.py', 'win_supervisor.py', 'protocol.py',
                      'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json'}
    if recovery:
        native_sources.add('recovery_boot_probe.py')
        recovery_stanza(native.get('recovery'))
    else:
        need('recovery' not in native, 'windows_recovery_mode_required')
    need(type(native.get('sources')) is dict and set(native['sources']) == native_sources,
         'windows_native_source_closure')
    for name in native_sources:
        row = native['sources'][name]
        need(type(row) is dict and set(row) == {'bytes', 'sha256'}
             and type(row['bytes']) is int and is_sha(row['sha256']), 'windows_native_source_descriptor')
        raw = bounded_read(Path(__file__).with_name(name), 1024**2)
        need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
             'windows_native_source_not_reviewed_sibling')
    need(native['runtime']['executable']['path'] == document['executable']['native_path']
         and native['runtime']['executable']['sha256'] == document['executable']['sha256'],
         'windows_bridge_native_executable_binding')
    supervisor = PureWindowsPath(document['supervisor']['native_path'])
    need(supervisor.name == 'win_supervisor.py' and str(supervisor.parent) == native['source_root']
         and native['sources']['win_supervisor.py']['sha256'] == document['supervisor']['sha256'],
         'windows_bridge_supervisor_binding')
    receipt = document['native_acceptance']
    need(type(receipt) is dict and set(receipt)=={'path','sha256'} and is_sha(receipt['sha256']),
         'windows_native_acceptance_binding')
    proof = read_json(receipt['path'],receipt['sha256'])
    need(proof.get('format')=='irisx/windows-native-probe-v1' and proof.get('ok') is True
         and proof.get('native_windows') is True and proof.get('network_used') is False
         and proof.get('real_auth_accessed') is False, 'windows_native_probe_incomplete')
    checks = proof.get('checks')
    need(type(checks) is dict and set(checks) == {'metadata','mutex','job_tree','deadline','pipe_eof',
         'supervisor_kill','parent_death','source_unchanged',
         'framed_operation_deadline','framed_official_rpc_deadline'}
         and all(type(r) is dict and r.get('ok') is True for r in checks.values()),
         'windows_native_probe_cases')
    sources = proof.get('source_sha256')
    need(type(sources) is dict and set(sources)=={'win_runtime.py','win_supervisor.py','native_probe.py','protocol.py'},
         'windows_native_probe_source_schema')
    for name in ('win_runtime.py','win_supervisor.py','protocol.py'):
        need(sources[name] == native['sources'][name]['sha256'], 'windows_native_probe_stale_source')
    probe = Path(__file__).with_name('native_probe.py')
    need(sources['native_probe.py'] == hashlib.sha256(bounded_read(probe,1024**2)).hexdigest(),
         'windows_native_probe_source_bytes')
    spec = native['runtime']
    version = spec['python_version']
    need(type(version) is list and len(version) == 3 and all(type(v) is int for v in version)
         and version[:2] == [3, 12] and 0 <= version[2] <= 99
         and is_sha(spec['executable']['sha256']) and is_sha(spec['base_executable']['sha256'])
         and is_sha(spec['pyvenv_cfg_sha256']), 'windows_native_probe_runtime_schema')
    need(proof.get('python_version') == '.'.join(str(v) for v in native['runtime']['python_version'])
         and proof.get('python_executable_sha256') == native['runtime']['executable']['sha256']
         and proof.get('python_base_executable_sha256') == native['runtime']['base_executable']['sha256']
         and proof.get('pyvenv_cfg_sha256') == native['runtime']['pyvenv_cfg_sha256'],
         'windows_native_probe_runtime')
    return dict(document)


def recovery_stanza(value):
    """Structural mode binding only; an epoch capability is separate admission."""
    fields = {'capability_sha256', 'reservation_sha256', 'challenge',
              'host_install_sha256', 'last_boot_utc', 'expires_epoch', 'allowed_operations'}
    need(type(value) is dict and set(value) == fields, 'windows_recovery_stanza_schema')
    need(all(is_sha(value[key]) for key in ('capability_sha256', 'reservation_sha256',
              'challenge', 'host_install_sha256')), 'windows_recovery_stanza_hash')
    need(type(value['last_boot_utc']) is str and 0 < len(value['last_boot_utc']) <= 64
         and value['last_boot_utc'].endswith('Z'), 'windows_recovery_boot_time')
    import math
    expiry = value['expires_epoch']
    need(type(expiry) in (int, float) and math.isfinite(expiry) and expiry > 0,
         'windows_recovery_expiry')
    need(value['allowed_operations'] == ['open', 'dataset', 'kernel', 'status', 'close'],
         'windows_recovery_operations')
    return dict(value)
