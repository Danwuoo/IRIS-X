"""Closed, source-bound native Windows configuration; never credential contents.

The supervisor/worker bootstrap must compile pinned win_runtime and this module
before calling load_runtime. All authentication remains behind OfficialSession.
This file changes no environment, permissions, profile, credential or TLS state.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path
import re
import sys
import sysconfig

FORMAT = 'irisx/run008-windows-sdk-runtime-v1'
SOURCE_NAMES = frozenset(('win_runtime.py', 'win_supervisor.py', 'protocol.py',
    'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json'))
VERSION_KEYS = frozenset(('code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'))
NETWORK_KEYS = frozenset(('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE', 'SSL_CERT_DIR'))
FORBIDDEN_KEYS = frozenset(('KAGGLE_API_TOKEN', 'KAGGLE_USERNAME', 'KAGGLE_KEY',
    'KAGGLE_IAP_TOKEN', 'KAGGLE_ENV', 'KAGGLE_API_ENDPOINT', 'KAGGLE_API_ENVIRONMENT',
    'KAGGLE_KERNEL_RUN_TYPE', 'KAGGLE_DATA_PROXY_URL', 'KAGGLE_API_V1_TOKEN',
    'KAGGLE_CONFIG_DIR', 'PYTHONPATH', 'PYTHONHOME', 'CURL_CA_BUNDLE',
    'REQUESTS_CLIENT_CERT', 'REQUESTS_CLIENT_KEY', 'REQUESTS_CERT', 'SSL_CLIENT_CERT',
    'SSL_CLIENT_KEY', 'SSLKEYLOGFILE', 'PYTHONHTTPSVERIFY', 'SSL_NO_VERIFY',
    'REQUESTS_VERIFY', 'REQUESTS_VERIFY_SSL', 'CURL_INSECURE'))


def need(value, code):
    if not value:
        raise ValueError(code)


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def native_path(value):
    need(type(value) is str and 3 <= len(value) <= 4096 and '\x00' not in value,
         'native_path_bounds')
    drive, tail = ntpath.splitdrive(value)
    need(re.fullmatch('[A-Za-z]:', drive) is not None and tail.startswith('\\')
         and '/' not in value and not any(c in tail for c in ':*?<>|\"') and ntpath.normpath(value) == value
         and all(part not in ('', '.', '..') and not part.endswith(('.', ' '))
                 for part in tail[1:].split('\\')), 'native_local_normal_path')
    return value


def same_path(left, right):
    return ntpath.normcase(native_path(str(left))) == ntpath.normcase(native_path(str(right)))


def strict_json(raw):
    need(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024, 'native_config_size')
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'native_duplicate_key')
            out[key] = value
        return out
    def finite(raw):
        value = float(raw)
        need(math.isfinite(value), 'native_nonfinite_json')
        return value
    try:
        doc = json.loads(raw, object_pairs_hook=pairs, parse_float=finite,
                         parse_constant=lambda _: need(False, 'native_nonfinite_json'))
    except (RecursionError, UnicodeError) as error:
        raise ValueError('native_json_invalid') from error
    need(type(doc) is dict, 'native_config_object')
    return doc


def validate_document(doc):
    need(type(doc) is dict and set(doc) == {'format', 'account', 'identity', 'runtime',
         'source_root', 'sources', 'versions', 'network_environment_sha256',
         'requests_ca_bundle'}, 'native_config_schema')
    need(doc['format'] == FORMAT and doc['account'] == 'danielwuu', 'native_config_identity')
    identity = doc['identity']
    need(type(identity) is dict and set(identity) == {'sid', 'profile'}, 'native_identity_schema')
    need(type(identity['sid']) is str and re.fullmatch(r'S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}', identity['sid']),
         'native_user_sid')
    native_path(identity['profile']); native_path(doc['source_root'])
    runtime = doc['runtime']
    need(type(runtime) is dict and set(runtime) == {'executable', 'base_executable', 'pyvenv_cfg_sha256', 'venv_prefix', 'sdk_root', 'python_version'},
         'native_runtime_schema')
    exe = runtime['executable']
    need(type(exe) is dict and set(exe) == {'path', 'sha256'} and is_sha(exe['sha256']), 'native_executable_schema')
    base = runtime['base_executable']
    need(type(base) is dict and set(base) == {'path', 'sha256'} and is_sha(base['sha256'])
         and is_sha(runtime['pyvenv_cfg_sha256']), 'native_base_runtime_binding')
    for value in (exe['path'], base['path'], runtime['venv_prefix'], runtime['sdk_root']):
        native_path(value)
    need(same_path(exe['path'], ntpath.join(runtime['venv_prefix'], 'Scripts', 'python.exe')),
         'native_venv_executable')
    need(same_path(runtime['sdk_root'], ntpath.join(runtime['venv_prefix'], 'Lib', 'site-packages')),
         'native_venv_sdk_root')
    version = runtime['python_version']
    need(type(version) is list and len(version) == 3 and all(type(x) is int for x in version)
         and version[:2] == [3, 12] and 0 <= version[2] <= 99, 'native_python_version')
    sources = doc['sources']
    need(type(sources) is dict and set(sources) == SOURCE_NAMES, 'native_source_closure')
    for row in sources.values():
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
             and 0 < row['bytes'] <= 1024 * 1024 and is_sha(row['sha256']), 'native_source_descriptor')
    versions = doc['versions']
    need(type(versions) is dict and set(versions) == VERSION_KEYS
         and all(type(v) is int and 0 < v <= 2**31 - 1 for v in versions.values()), 'native_version_schema')
    need(versions['code'] == versions['code_predecessor'] + 1
         and versions['inactive'] == versions['inactive_predecessor'] + 1
         and versions['active'] == versions['inactive'] + 1, 'native_successor_versions')
    env = doc['network_environment_sha256']
    need(type(env) is dict and set(env) <= NETWORK_KEYS and all(is_sha(v) for v in env.values()),
         'native_network_environment_schema')
    ca = doc['requests_ca_bundle']
    need(ca is None or type(ca) is dict and set(ca) == {'path', 'sha256'} and is_sha(ca['sha256']),
         'native_ca_schema')
    if ca is not None:
        native_path(ca['path'])
    return doc


class NativeRuntime:
    def __init__(self, document, config_path, config_sha256, win):
        self.document = validate_document(document)
        self.config_path, self.config_sha256, self.win = config_path, config_sha256, win
        self.source_root = Path(document['source_root'])
        self.sdk_root = Path(document['runtime']['sdk_root'])
        self.worker_path = self.source_root / 'sdk_worker.py'
        self.executable = document['runtime']['executable']['path']
        self.versions = dict(document['versions'])

    def read_source(self, path, cap):
        value = native_path(str(path))
        source = ntpath.normcase(value)
        root = ntpath.normcase(str(self.source_root))
        sdk = ntpath.normcase(str(self.sdk_root))
        reviewed = ntpath.dirname(source) == root and ntpath.basename(source) in SOURCE_NAMES
        sdk_member = source.startswith(sdk + '\\') and source.endswith('.py')
        need(reviewed or sdk_member, 'native_read_outside_source_inventory')
        return self.win.read_source(value, cap)

    def verify_sources(self):
        for name, row in self.document['sources'].items():
            raw = self.read_source(self.source_root / name, 1024 * 1024)
            need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
                 'native_bridge_source_bytes')

    def verify_runtime(self):
        need(os.name == 'nt' and sys.platform == 'win32', 'native_windows_required')
        need(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
             and sys.flags.ignore_environment == 1, 'native_isolated_runtime')
        spec = self.document['runtime']
        need(sys.implementation.name == 'cpython' and list(sys.version_info[:3]) == spec['python_version'],
             'native_python_identity')
        need(same_path(sys.executable, self.executable) and same_path(sys.prefix, spec['venv_prefix'])
             and not same_path(sys.prefix, sys.base_prefix), 'native_venv_identity')
        need(same_path(sysconfig.get_path('purelib'), self.sdk_root), 'native_purelib_identity')
        raw = self.win.read_source(self.executable, 128 * 1024 * 1024)
        need(hashlib.sha256(raw).hexdigest() == spec['executable']['sha256'], 'native_executable_bytes')
        base = spec['base_executable']
        need(same_path(getattr(sys, '_base_executable', ''), base['path']), 'native_base_executable_identity')
        raw = self.win.read_source(base['path'], 128 * 1024 * 1024)
        need(hashlib.sha256(raw).hexdigest() == base['sha256'], 'native_base_executable_bytes')
        raw = self.win.read_source(ntpath.join(spec['venv_prefix'], 'pyvenv.cfg'), 65536)
        need(hashlib.sha256(raw).hexdigest() == spec['pyvenv_cfg_sha256'], 'native_pyvenv_configuration_bytes')
        identity = self.win.current_identity()
        need(identity.sid == self.document['identity']['sid']
             and same_path(identity.profile, self.document['identity']['profile'])
             and same_path(os.environ.get('USERPROFILE', ''), identity.profile), 'native_account_profile')
        folded = {key.upper(): value for key, value in os.environ.items()}
        need(not FORBIDDEN_KEYS.intersection(folded), 'native_alternate_auth_or_tls_environment')
        actual = {key: hashlib.sha256(value.encode()).hexdigest()
                  for key, value in folded.items() if key in NETWORK_KEYS}
        need(actual == self.document['network_environment_sha256'], 'native_network_environment_changed')
        ca = self.document['requests_ca_bundle']
        if ca is None:
            need('REQUESTS_CA_BUNDLE' not in folded, 'native_unreviewed_ca')
        else:
            need(folded.get('REQUESTS_CA_BUNDLE') == ca['path'], 'native_ca_selector_changed')
            raw = self.win.read_source(ca['path'], 16 * 1024 * 1024)
            need(hashlib.sha256(raw).hexdigest() == ca['sha256'], 'native_ca_bytes_changed')
        self.verify_sources()
        return {'format': 'irisx/windows-sdk-runtime-boundary-v1', 'real_profile': True,
                'bridge_source_count': len(SOURCE_NAMES), 'credential_contents_inspected': False}

    @contextmanager
    def credential_guard(self, *, allow_write=False):
        need(type(allow_write) is bool, 'native_credential_guard_mode')
        self.verify_runtime()
        profile = Path(self.document['identity']['profile'])
        for name in ('kaggle.json', 'access_token', 'access_token.txt'):
            path = profile / '.kaggle' / name
            need(not os.path.lexists(path), 'native_alternate_auth_store')
        with self.win.private_file_guard(profile / '.kaggle' / 'credentials.json',
                expected_relative=r'.kaggle\credentials.json', allow_write=allow_write) as guard:
            yield guard


def load_runtime(config_path, config_sha256, *, supervisor=False):
    need(type(supervisor) is bool and is_sha(config_sha256), 'native_config_binding')
    win = sys.modules.get('win_runtime')
    need(win is not None, 'pinned_native_runtime_bootstrap_required')
    native_path(str(config_path))
    raw = win.read_source(config_path, 1024 * 1024)
    need(hashlib.sha256(raw).hexdigest() == config_sha256, 'native_config_bytes')
    runtime = NativeRuntime(strict_json(raw), str(config_path), config_sha256, win)
    runtime.verify_runtime()
    return runtime
