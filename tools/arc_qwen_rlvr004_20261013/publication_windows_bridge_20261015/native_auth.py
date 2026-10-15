"""Windows official OAuth adapter; credentials never cross the bridge.

The runtime owns Windows identity, no-reparse handles and ACL validation. This
module reads only reviewed SDK sources and credential *metadata*. Credential
loading, access-token refresh and saving remain in the pinned official SDK.
"""
from contextlib import contextmanager
import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import sysconfig
import time

LOCK_SHA256 = '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d'
SOURCE_COUNT = 170
ACCOUNT = 'danielwuu'
FORBIDDEN_AUTH_ENV = frozenset(('KAGGLE_API_TOKEN', 'KAGGLE_USERNAME', 'KAGGLE_KEY',
    'KAGGLE_IAP_TOKEN', 'KAGGLE_ENV', 'KAGGLE_API_ENDPOINT', 'KAGGLE_API_ENVIRONMENT',
    'KAGGLE_KERNEL_RUN_TYPE', 'KAGGLE_DATA_PROXY_URL', 'KAGGLE_API_V1_TOKEN',
    'KAGGLE_CONFIG_DIR', 'PYTHONPATH', 'PYTHONHOME'))


class AuthGuardError(ValueError):
    pass


class AuthRefreshUnknown(RuntimeError):
    """One attempted refresh cannot safely be retried automatically."""


def need(condition, code):
    if not condition:
        raise AuthGuardError(code)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'sdk_lock_duplicate_key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda unused: need(False, 'sdk_lock_nonfinite'))


def verify_sdk(runtime, lock_path):
    """Verify the complete ORIGINAL source closure before any SDK import.

    runtime.read_source holds the runtime's no-reparse/owner checks while reading.
    No .pyc is trusted, including bytecode left by a previous installation.
    """
    runtime.verify_runtime()
    root = Path(runtime.sdk_root)
    need(root == Path(sysconfig.get_path('purelib')), 'official_sdk_sysconfig_root')
    raw = runtime.read_source(Path(lock_path), 1024 * 1024)
    need(hashlib.sha256(raw).hexdigest() == LOCK_SHA256, 'original_sdk_lock_changed')
    lock = _strict_json(raw)
    need(type(lock) is dict and set(lock) == {'format', 'distributions', 'sources'}, 'sdk_lock_schema')
    need(lock['format'] == 'irisx/run008-native-sdk-source-lock-v1', 'sdk_lock_schema')
    need(lock['distributions'] == {'kaggle': '2.2.4', 'kagglesdk': '0.1.37'}, 'sdk_lock_distributions')
    sources = lock['sources']
    need(type(sources) is dict and len(sources) == SOURCE_COUNT, 'sdk_source_count')
    need(not any(name.split('.')[0] in ('kaggle', 'kagglesdk') for name in sys.modules),
         'official_api_must_not_be_preimported')
    for name, version in lock['distributions'].items():
        distribution = importlib.metadata.distribution(name)
        need(distribution.version == version, 'sdk_distribution_version')
        need(Path(distribution.locate_file('')) == root, 'sdk_distribution_outside_bound_root')
    actual = {}
    for package in ('kaggle', 'kagglesdk'):
        package_root = root / package
        # The runtime checks directory ancestors, including package root, while
        # opening every source; unexpected sources fail even if never imported.
        for path in package_root.rglob('*.py'):
            relative = path.relative_to(root).as_posix()
            need(relative in sources, 'official_sdk_source_closure')
            content = runtime.read_source(path, 16 * 1024 * 1024)
            actual[relative] = hashlib.sha256(content).hexdigest()
    need(actual == sources, 'official_sdk_source_closure')
    return root, sources


class ReviewedSdkFinder(importlib.abc.MetaPathFinder):
    """Recheck pinned bytes at import and compile them directly."""
    def __init__(self, root, sources, runtime):
        self.root, self.sources, self.runtime = root, sources, runtime

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in ('kaggle', 'kagglesdk'):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        need(spec is not None and spec.origin is not None, 'official_sdk_import_missing')
        source = Path(spec.origin)
        need(source.is_relative_to(self.root), 'official_sdk_import_outside_bound_root')
        digest = self.sources.get(source.relative_to(self.root).as_posix())
        need(digest is not None, 'official_sdk_unpinned_import')
        raw = self.runtime.read_source(source, 16 * 1024 * 1024)
        need(hashlib.sha256(raw).hexdigest() == digest, 'official_sdk_import_hash')
        class SourceOnly(importlib.machinery.SourceFileLoader):
            def get_code(self, unused):
                return compile(raw, str(source), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
        spec.loader = SourceOnly(fullname, str(source))
        return spec


class OfficialSession:
    """One dedicated worker; every uncertain refresh permanently latches it.

    refresh_exchange.intent(metadata) must return only after WSL durably claims
    the attempt and writes refresh_intent. accepted(metadata) must wait for the
    durable refresh_accepted ACK. Both are permitted before default kaggle import.
    """
    def __init__(self, runtime, refresh_exchange, bound_sdk_client, *, lock_path=None):
        self.runtime, self.exchange, self.bind_client = runtime, refresh_exchange, bound_sdk_client
        self.lock_path = lock_path or Path(__file__).with_name('sdk-lock.json')
        self.client = self.api = self.finder = None
        self.originals = []
        self.refreshing = self.save_completed = self.uncertain = False
        self.refresh_credential = None
        self.next_renew = 0
        self.prepared = self.ready = False

    def check(self):
        if self.uncertain:
            raise AuthRefreshUnknown('official_existing_credential_refresh_unknown')

    def prepare(self):
        need(not self.prepared, 'auth_already_prepared')
        self.runtime.verify_runtime()
        need(not FORBIDDEN_AUTH_ENV.intersection(os.environ), 'alternate_auth_environment')
        with self.runtime.credential_guard():
            pass
        root, sources = verify_sdk(self.runtime, self.lock_path)
        self.finder = ReviewedSdkFinder(root, sources, self.runtime)
        self.prepared = True
        return {'sdk_source_count': SOURCE_COUNT, 'sdk_lock_sha256': LOCK_SHA256,
                'account': ACCOUNT, 'existing_official_store': True}

    def protocol_ready(self):
        need(self.prepared and not self.ready, 'source_verification_before_protocol_ready')
        self.exchange.check_ready()
        self.ready = True

    def _patch(self, owner, name, value):
        # Retain classmethod descriptors rather than their bound-method view.
        old = vars(owner).get(name, getattr(owner, name))
        self.originals.append((owner, name, old))
        setattr(owner, name, value)

    def _install(self, Client, Credentials):
        original_enter = Client.__enter__
        def enter(client):
            self.check()
            result = original_enter(client)
            if not getattr(client, '_irisx_bound', False):
                try:
                    self.bind_client(client, self)
                except BaseException:
                    client.__exit__(None, None, None)
                    raise
                client._irisx_bound = True
            return result
        self._patch(Client, '__enter__', enter)

        original_load = Credentials.load
        def load(cls, client, file_path=None):
            self.check()
            need(file_path is None, 'alternate_credential_path')
            with self.runtime.credential_guard():
                creds = original_load(client=client)
                need(creds is not None and creds.get_username() == ACCOUNT, 'native_auth_account')
                return creds
        self._patch(Credentials, 'load', classmethod(load))

        def expired(creds):
            expiry = creds._access_token_expiration
            return not expiry or time.time() + 300 >= expiry.timestamp()
        self._patch(Credentials, 'access_token_has_expired', expired)

        original_save = Credentials.save
        def save(creds, *args, **kwargs):
            need(self.refreshing and creds is self.refresh_credential and not args and not kwargs,
                 'unclaimed_credential_save')
            need(not self.save_completed, 'credential_save_resend_forbidden')
            with self.runtime.credential_guard(allow_write=True):
                result = original_save(creds)
            with self.runtime.credential_guard(allow_write=True):
                pass
            self.save_completed = True
            return result
        self._patch(Credentials, 'save', save)

        original_refresh = Credentials.refresh_access_token
        def refresh(creds):
            self.check()
            need(not self.refreshing, 'nested_credential_refresh')
            need(creds.get_username() == ACCOUNT, 'native_auth_account')
            expiry = creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
            need(type(expiry) in (int, float) and math.isfinite(expiry) and expiry >= 0,
                 'auth_expiration_invalid')
            metadata = {'account': ACCOUNT, 'old_expiration_epoch': expiry}
            metadata['refresh_id'] = hashlib.sha256(canonical(metadata)).hexdigest()
            # Any pipe/save/ACL ambiguity is terminal, including a swallowed
            # exception in kaggle.__init__. No second GenerateAccessToken occurs.
            try:
                with self.runtime.credential_guard(allow_write=True):
                    self.exchange.intent(metadata)
                    self.refreshing = True
                    self.refresh_credential = creds
                    self.save_completed = False
                    result = original_refresh(creds)
                need(self.save_completed, 'official_credential_save_not_completed')
                with self.runtime.credential_guard():
                    pass
                new_expiry = creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
                need(type(new_expiry) in (int, float) and math.isfinite(new_expiry)
                     and new_expiry > time.time() + 300, 'refreshed_credential_expiration_invalid')
                self.exchange.accepted({'refresh_id': metadata['refresh_id'],
                    'new_expiration_epoch': new_expiry, 'official_save_completed': True,
                    'credential_acl_verified': True})
                return result
            except BaseException:
                self.uncertain = True
                raise AuthRefreshUnknown('official_existing_credential_refresh_unknown') from None
            finally:
                self.refreshing = False
                self.refresh_credential = None
        self._patch(Credentials, 'refresh_access_token', refresh)

        def forbidden(*args, **kwargs):
            raise AuthGuardError('credential_delete_or_revoke_not_authorized')
        self._patch(Credentials, 'delete', forbidden)
        self._patch(Credentials, 'revoke_token', forbidden)

    def open(self):
        need(self.prepared and self.ready, 'protocol_ready_before_sdk_auth')
        self.check()
        sys.meta_path.insert(0, self.finder)
        try:
            from kagglesdk import KaggleClient, KaggleCredentials, KaggleOAuth
            self._install(KaggleClient, KaggleCredentials)
            def no_login(*args, **kwargs):
                raise AuthGuardError('new_oauth_login_not_authorized')
            self._patch(KaggleOAuth, 'authenticate', no_login)
            # Official load/save wrappers hold the appropriate handles. Holding
            # a read-only target handle across import would prohibit the SDK's
            # legitimate in-place refresh save on Windows.
            import kaggle
            self.check()  # kaggle.__init__ swallows authentication exceptions.
            self.api = kaggle.api
            self._account()
            self.client = self.api.build_kaggle_client()
            self.client.__enter__()
            self._download_response(self.client)
            self.next_renew = time.monotonic() + 300
            return self.client
        except BaseException:
            self.close()
            raise

    def _account(self):
        self.check()
        need(self.api.get_config_value('username') == ACCOUNT, 'native_api_account')
        need(self.api.get_config_value('auth_method') == 'OAUTH', 'native_official_oauth_required')

    @staticmethod
    def _download_response(client):
        from kagglesdk.common.types.http_redirect import HttpRedirect
        original = client.http_client()._prepare_response
        def prepare(kind, response):
            if kind is HttpRedirect and 200 <= response.status_code < 400:
                return response
            return original(kind, response)
        client.http_client()._prepare_response = prepare

    def renew_if_due(self):
        self.check()
        if time.monotonic() < self.next_renew:
            return self.client
        need(self.api._authenticate_with_oauth_creds() is True, 'native_oauth_renew_failed')
        self._account()
        replacement = self.api.build_kaggle_client()
        try:
            replacement.__enter__()
            self._download_response(replacement)
        except BaseException:
            replacement.__exit__(None, None, None)
            raise
        old, self.client = self.client, replacement
        old.__exit__(None, None, None)
        self.next_renew = time.monotonic() + 300
        return self.client

    def close(self):
        try:
            if self.client is not None:
                self.client.__exit__(None, None, None)
                self.client = None
        finally:
            for owner, name, original in reversed(self.originals):
                setattr(owner, name, original)
            self.originals.clear()
            if self.finder is not None and self.finder in sys.meta_path:
                sys.meta_path.remove(self.finder)


@contextmanager
def isolate_sdk_output():
    """Reserve duplicate binary IPC handles, then sink both raw SDK streams.

    The dedicated worker never stores SDK stdout/stderr or exception messages.
    Returning duplicate handles also prevents C-level writes to fd 1/2 from
    entering the framed protocol. The caller owns the returned pipe handles.
    """
    reader = os.fdopen(os.dup(sys.stdin.fileno()), 'rb', buffering=0)
    writer = os.fdopen(os.dup(sys.stdout.fileno()), 'wb', buffering=0)
    saved_out, saved_err = os.dup(1), os.dup(2)
    sink = open(os.devnull, 'wb', buffering=0)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
        yield reader, writer
    finally:
        reader.close()
        writer.close()
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        sink.close()
