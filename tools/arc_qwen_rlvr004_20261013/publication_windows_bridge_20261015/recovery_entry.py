"""Explicit same-namespace failed-open recovery; no automatic restart or retry.

validate is local evidence inspection only. prepare additionally collects one
fresh no-auth native boot observation and appends preparation under the existing
publisher lock. reconcile-read-only requires separately reviewed manual Restart
provenance, a post-restart binding review and original action admission. It can
only observe Dataset/kernel/status and close; no publication call is exposed.
Consumer-local descriptors are private inputs, never project credentials.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import ntpath
import os
import re
from pathlib import Path
import stat
import sys
import time
import types

TRANSPORT_SHA256 = 'f9a8a9cc0b43fb5f035452588832999e3de209324ff5a19abe20f46b6f77d721'
CORE_SHA256 = '2d7ecb31f7571a51382597a1fc5ddd75939b296794d7de28cef10cc06b2439dc'
CLIENT_SHA256 = '35cb7d2eb42d6e6a7d45ad44374d68bc36d1883eae36a55ab44f5bb98859a4ec'
READ_BRACKET = ['dataset', 'kernel', 'status', 'kernel', 'dataset']


def pinned_module(name, filename, expected):
    path = Path(__file__).absolute().with_name(filename)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('recovery_entry_linked_source')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1024**2:
        raise ValueError('recovery_entry_source_kind')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        raw = stream.read(1024**2 + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    if (identity(before) != identity(info) or identity(before) != identity(after)
            or identity(before) != identity(path.stat()) or len(raw) != before.st_size
            or hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('recovery_entry_source_hash')
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('recovery_entry_input_schema')


def materialize_binding(core, owner, reservation, binding_review, c):
    """Exclusive exact template derivation after consumption; never overwrites."""
    binding = core.strict_json(core.verified(binding_review))
    local = core.strict_json(core.verified(binding['local_configuration_template']))
    native = core.strict_json(core.verified(binding['native_configuration_template']))
    reservation_value = core.strict_json(core.verified(reservation))
    preparation = core.strict_json(core.verified(reservation_value['capability']['preparation']))
    review = core.strict_json(core.verified(preparation['review']))
    native = copy.deepcopy(native)
    native['format'] = 'irisx/run008-windows-sdk-recovery-runtime-v1'
    native['recovery'] = core.recovery_stanza(reservation)
    source = review['recovery_sources']['recovery_boot_probe.py']
    native['sources']['recovery_boot_probe.py'] = {'bytes': source['bytes'], 'sha256': source['sha256']}
    local = copy.deepcopy(local)
    output = binding['output_native_configuration_path']
    row = local['windows_bridge']['configuration']
    row['wsl_path'] = output
    row['native_path'] = ntpath.join(ntpath.dirname(row['native_path']), Path(output).name)
    row['sha256'] = core.sha(core.canonical(native))
    core.verify_generated_binding(reservation, native, local)
    # Review binds the paths; absence, symlink and overwrite checks stay active.
    native_descriptor = c['write_new'](output, core.canonical(native))
    local_descriptor = c['write_new'](binding['output_local_configuration_path'], core.canonical(local))
    if native_descriptor['sha256'] != row['sha256']:
        raise ValueError('recovery_generated_native_bytes')
    return native, local, local_descriptor


def bind_derived_configuration(core, config_module, c, reservation, native, local, descriptor, args):
    core.verify_generated_binding(reservation, native, local)
    prior = c['configured']()
    current = config_module.load(descriptor['path'], descriptor['sha256'],
                                 args.manifest, args.manifest_sha, recovery=True)
    # Only the independently reviewed exact native configuration overlay changes.
    for name in ('repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root',
                 'gpu_stop_path', 'runtime', 'versions', 'publication_manifest_sha256'):
        if getattr(current, name) != getattr(prior, name):
            raise ValueError('recovery_derived_owner_binding_changed')
    c['CONFIG'] = current
    return current


def execute(args, transport, core, client):
    transport.load_contract(args)
    c = vars(transport._common)
    document = core.strict_json(c['verified'](args.input, args.input_sha, cap=4*1024**2))
    if args.action in ('validate', 'prepare'):
        fields = ('inventory', 'review') if args.action == 'validate' else ('inventory', 'review', 'challenge', 'expires_epoch')
        exact(document, fields)
        with core.RecoveryOwner(c) as owner:
            if args.action == 'validate':
                frontier = core.validate_frontier(c['STATE'], document['inventory'], document['review'])
                return {'status': 'RECOVERY_FRONTIER_VALIDATED', 'provider_calls': 0,
                        'historical_unknown_changed': False, 'frontier': frontier}
            review = core.strict_json(core.verified(document['review']))
            before = client.observe_recovery_boot(c, review, document['challenge'])
            result = owner.prepare(document['inventory'], document['review'], before,
                challenge=document['challenge'], now_epoch=time.time(), expires_epoch=document['expires_epoch'])
            return {'status': 'RECOVERY_PREPARATION_SAVED', 'preparation': result,
                    'provider_calls': 0, 'manual_restart_executed': False}
    if args.action != 'reconcile-read-only':
        raise ValueError('recovery_entry_action')
    exact(document, ('preparation', 'restart', 'binding_review', 'session_nonce'))
    transport.execution_gate(args)
    transport.git_publication_gate(args)
    preparation = core.strict_json(core.verified(document['preparation']))
    review = core.strict_json(core.verified(preparation['review']))
    binding = core.strict_json(core.verified(document['binding_review']))
    if binding['local_configuration_template']['sha256'] != c['configured']().document_sha256:
        raise ValueError('recovery_current_template_not_reviewed')
    with core.RecoveryOwner(c) as owner:
        after = client.observe_recovery_boot(c, review, preparation['challenge'])
        capability = owner.capability(document['preparation'], after, document['restart'],
            binding_review_descriptor=document['binding_review'],
            calls=[{'operation': name, 'arguments': {}} for name in READ_BRACKET], now_epoch=time.time())
        reservation = owner.reserve(capability, session_nonce=document['session_nonce'],
                                     current_boot_descriptor=after, now_epoch=time.time())
        native, local, derived = materialize_binding(core, owner, reservation, document['binding_review'], c)
        config_module = sys.modules['reviewed_rl_local_config_' + c['CONFIG_SOURCE_SHA256']]
        configured = bind_derived_configuration(core, config_module, c, reservation, native, local, derived, args)
        connection = None
        try:
            connection = client.RecoveryBridgeClient(c, dict(configured.windows_bridge), owner, reservation, after)
            observations = {}
            for key, operation in (('dataset_before', 'dataset'), ('kernel_before', 'kernel'),
                                   ('status', 'status'), ('kernel_after', 'kernel'), ('dataset_after', 'dataset')):
                observations[key] = connection.call(operation, {})
            connection.close()
            result = owner.finalize(reservation, session_name=connection.session_name,
                receipt_bytes=connection.native_receipt_bytes, proxy_exit_status=connection.native_exit_status,
                observations=observations, now_epoch=time.time())
            return {'status': 'READ_ONLY_RECONCILIATION_CLOSED', 'eligibility': result,
                    'historical_unknown_changed': False, 'publication_attempted': False}
        finally:
            if connection is not None and not connection.closed and not connection.unknown:
                connection.close()


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument('action', choices=('validate', 'prepare', 'reconcile-read-only'))
    for name in ('manifest', 'manifest-sha', 'material', 'material-sha', 'review', 'review-sha',
                 'local-config', 'local-config-sha', 'input', 'input-sha'):
        result.add_argument('--' + name, required=True)
    return result


def main():
    args = parser().parse_args()
    try:
        transport = pinned_module('reviewed_recovery_transport', 'rl_transport.py', TRANSPORT_SHA256)
        core = pinned_module('reviewed_recovery_core', 'recovery_epoch.py', CORE_SHA256)
        client = pinned_module('reviewed_recovery_client', 'bridge_client.py', CLIENT_SHA256)
        result = execute(args, transport, core, client)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except BaseException as error:
        # Only the exact core error class's fixed token can leave this entry.
        code = 'recovery_evidence_or_execution_failed'
        if 'core' in locals() and type(error) is core.RecoveryError and re.fullmatch(r'recovery_[a-z0-9_]{1,100}', str(error)):
            code = str(error)
        print(json.dumps({'status': 'RECOVERY_BLOCKED', 'reason': code,
                          'automatic_retry_permitted': False}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
