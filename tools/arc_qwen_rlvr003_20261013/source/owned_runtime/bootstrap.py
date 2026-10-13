"""Concrete checked-outer bootstrap for the separately reviewed assembly.

Trust starts with the independently reviewed outer notebook/operator and the
authenticated original owner request, not a Boolean in a runtime request. The
notebook pins the complete operator bytes; the operator pins the complete raw
source inventory, source-only ZIP, material-review bytes and original request.
An independent offline validator must bind the *published* notebook/operator/
review hashes to its own review. This module checks that descriptor and its
actual files; self-consistent locally supplied files do NOT establish independent
approval. In particular, the normalized source hash is only self-consistency.

The topology is deliberately acyclic: no source constant attempts to hash an
outer notebook which itself hashes those complete source bytes. Production's
final source, policy and environment bindings remain closed in release.py.
There are no signing keys, credentials, network calls or provider operations.
The process registries and exact source callsites prevent JSON admission and
ordinary confused-deputy calls; they are not a sandbox against arbitrary Python
reflection, same-UID memory mutation, or replacement of trusted source.
"""
from __future__ import annotations

from copy import deepcopy
import importlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types
import weakref
import zipfile

from . import ROOT
from .release import canonical, need, sha, inventory, source_digest, verify_inventory

PRODUCTION_SCOPE = 'production-rl-abc'
SYNTHETIC_SCOPE = 'synthetic-bootstrap-test-only'
ROLE = 'rl-abc'
_CONTEXTS = weakref.WeakKeyDictionary()
_CHILD_ISSUED = set()
_MAX_DOCUMENT = 16 * 1024**2
_MAX_ARCHIVE = 256 * 1024**2
_FILES = ('outer_notebook', 'operator', 'material_review', 'source_archive', 'original_request')


class VerifiedOuterContext:
    """Non-serializable, process-local result of checking actual outer files."""
    __slots__ = ('__weakref__',)

    def __new__(cls, *args, **kwargs):
        raise TypeError('a source-owned checked outer bootstrap context is required')

    def __reduce__(self):
        raise TypeError('checked outer authority cannot be serialized')

    def __copy__(self):
        raise TypeError('checked outer authority cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('checked outer authority cannot be copied')


def _require_caller(module_name, names):
    """Verify the caller of our caller against the actual source-owned function."""
    frame = sys._getframe(2)
    module = importlib.import_module(module_name)
    path = ROOT / (module_name.replace('.', '/') + '.py')
    need(Path(module.__file__).resolve() == path.resolve(), 'canonical bootstrap callsite module required')
    code = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    compiled = {v.co_name: v for v in code.co_consts if isinstance(v, types.CodeType)}
    need(any(frame.f_code is getattr(module, name).__code__ and
             frame.f_globals is vars(module) and frame.f_code == compiled.get(name)
             for name in names), 'exact source-owned ' + module_name + ' callsite required')


def _json(raw, label):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key in ' + label)
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite ' + label)))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid JSON ' + label) from exc


def _sha_value(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _read(path, *, maximum=_MAX_DOCUMENT):
    """Read one bounded ordinary file, rejecting aliases and mutation while read."""
    need(type(path) in (str, Path) or isinstance(path, Path), 'explicit raw file path required')
    raw_path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (raw_path, *raw_path.parents)), 'outer file symlink forbidden')
    resolved = raw_path.resolve(strict=True)
    fd = os.open(resolved, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum, 'bounded regular outer file required')
        chunks, total = [], 0
        while True:
            block = os.read(fd, min(1024**2, maximum + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            need(total <= maximum, 'outer file byte cap exceeded')
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
             total == before.st_size, 'outer file changed during verification')
        current = resolved.stat(follow_symlinks=False)
        need((current.st_dev, current.st_ino) == (before.st_dev, before.st_ino) and stat.S_ISREG(current.st_mode),
             'outer file replaced during verification')
        raw = b''.join(chunks)
    finally:
        os.close(fd)
    return raw, {'path': str(resolved), 'file_sha256': sha(raw)}


def _source_archive(raw, files):
    """Check complete raw source bytes without extraction or executable loading."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            need(0 < len(members) <= 10000 and len(members) == len(files), 'exact source-only ZIP inventory required')
            seen, total = set(), 0
            for member in members:
                name = member.filename
                p = PurePosixPath(name)
                need(name and not p.is_absolute() and '\\' not in name and '\x00' not in name and
                     all(part not in ('', '.', '..') for part in name.split('/')) and
                     name == p.as_posix(), 'unsafe source ZIP member path')
                need(name not in seen and name in files and not member.is_dir(), 'unknown/duplicate source ZIP member')
                seen.add(name)
                mode = member.external_attr >> 16
                need(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not member.flag_bits & 1,
                     'source ZIP member must be regular and unencrypted')
                need(member.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsupported source ZIP compression')
                need(p.suffix.lower() not in ('.pt', '.pth', '.bin', '.safetensors', '.pkl', '.pickle', '.zip'),
                     'source-only ZIP cannot contain tensor/evaluator/nested archives')
                total += member.file_size
                need(total <= _MAX_ARCHIVE, 'source ZIP expanded byte cap exceeded')
                need(sha(archive.read(member)) == files[name], 'raw source ZIP bytes differ: ' + name)
            need(seen == set(files), 'source ZIP missing members')
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError('invalid source-only ZIP') from exc


def _checked_files(paths, *, scope):
    need(type(paths) is dict and set(paths) == set(_FILES), 'exact outer raw file descriptors required')
    raw, refs = {}, {}
    for name in _FILES:
        raw[name], refs[name] = _read(paths[name], maximum=_MAX_ARCHIVE if name == 'source_archive' else _MAX_DOCUMENT)
    need(len({r['path'] for r in refs.values()}) == len(_FILES), 'distinct outer files required')
    notebook = _json(raw['outer_notebook'], 'outer notebook')
    need(type(notebook) is dict and notebook.get('nbformat') == 4 and type(notebook.get('cells')) is list,
         'actual version-four outer notebook required')
    need(type(notebook.get('metadata')) is dict, 'outer notebook metadata required')
    notebook_binding = notebook['metadata'].get('owned_rl_release')
    need(type(notebook_binding) is dict and set(notebook_binding) == {'format', 'operator_sha256'} and
         notebook_binding['format'] == 'owned-rl-outer-notebook-v1' and
         notebook_binding['operator_sha256'] == refs['operator']['file_sha256'],
         'outer notebook must pin complete raw operator bytes')
    operator = _json(raw['operator'], 'reviewed operator')
    fields = {'format', 'scope', 'role', 'raw_source_sha256', 'source_archive_sha256',
              'material_review_sha256', 'original_request_sha256', 'original_epoch', 'original_request_id', 'owner_id'}
    need(type(operator) is dict and ((set(operator) == fields and operator['format'] == 'owned-rl-reviewed-operator-v1') or
         (set(operator) == fields | {'parent_scorer_sha256'} and operator['format'] == 'owned-rl-reviewed-operator-v2' and
          _sha_value(operator['parent_scorer_sha256']))),
         'closed reviewed operator binding required')
    need(operator['scope'] == scope and operator['role'] == ROLE, 'reviewed operator scope/role differs')
    files = inventory()
    need(_sha_value(operator['raw_source_sha256']) and operator['raw_source_sha256'] == source_digest(files),
         'reviewed operator full raw source identity differs')
    for name in ('source_archive', 'material_review', 'original_request'):
        need(operator[name + '_sha256'] == refs[name]['file_sha256'], 'reviewed operator raw ' + name + ' bytes differ')
    _source_archive(raw['source_archive'], files)
    owner = _json(raw['original_request'], 'original owner request')
    owner_fields = {'format', 'scope', 'role', 'original_epoch', 'request_id', 'owner_id', 'instruction'}
    need(type(owner) is dict and set(owner) == owner_fields and owner['format'] == 'owned-rl-original-owner-request-v1',
         'closed original owner request required')
    need(owner['scope'] == scope and owner['role'] == ROLE, 'original owner request scope/role differs')
    need(type(owner['original_epoch']) in (int, float) and math.isfinite(owner['original_epoch']) and owner['original_epoch'] > 0 and
         type(operator['original_epoch']) in (int, float) and operator['original_epoch'] == owner['original_epoch'],
         'original owner epoch differs')
    for key in ('request_id', 'owner_id', 'instruction'):
        need(type(owner[key]) is str and 0 < len(owner[key]) <= (65536 if key == 'instruction' else 256),
             'bounded original owner ' + key + ' required')
    need(operator['original_request_id'] == owner['request_id'] and operator['owner_id'] == owner['owner_id'],
         'original owner request identity differs')
    receipt = {'format': 'owned-rl-checked-bootstrap-v1', 'scope': scope, 'role': ROLE,
               'raw_source_sha256': source_digest(files), 'original_epoch': owner['original_epoch'],
               'original_request_id': owner['request_id'], 'owner_id': owner['owner_id'], **refs}
    if 'parent_scorer_sha256' in operator:
        # Hash only. Evaluator paths/material stay in the parent-private descriptor.
        receipt['parent_scorer_sha256'] = operator['parent_scorer_sha256']
    return receipt, files


def _verify_context(paths, *, scope):
    _require_caller('owned_runtime.bootstrap',
                    ('reviewed_bootstrap',) if scope == PRODUCTION_SCOPE else ('synthetic_bootstrap_context', 'synthetic_scoring_bootstrap'))
    receipt, files = _checked_files(paths, scope=scope)
    context = object.__new__(VerifiedOuterContext)
    _CONTEXTS[context] = {'pid': os.getpid(), 'receipt': receipt, 'sources': files, 'parent_issued': False}
    return context


def _context(context):
    need(type(context) is VerifiedOuterContext and context in _CONTEXTS, 'live typed checked outer context required; JSON is not authority')
    entry = _CONTEXTS[context]
    need(entry['pid'] == os.getpid(), 'checked outer context cannot cross processes')
    verify_inventory(entry['sources'])
    _recheck_refs(entry['receipt'])
    return entry


def _recheck_refs(receipt):
    for name in _FILES:
        _, ref = _read(receipt[name]['path'], maximum=_MAX_ARCHIVE if name == 'source_archive' else _MAX_DOCUMENT)
        need(ref == receipt[name], 'checked outer raw bytes changed: ' + name)


def context_receipt(context):
    """Evidence only: serializing this record never serializes its authority."""
    return deepcopy(_context(context)['receipt'])


def reviewed_bootstrap(config, output, *, outer_notebook_path, operator_path,
                       material_review_path, source_archive_path, original_request_path, parent_scorer_path=None):
    """Canonical production assembly entrypoint; release.py still enforces pins.

    The operator must authenticate and independently review these exact outer
    files before calling this function. The offline validator independently
    authenticates that published chain. A caller's asserted review flag, supplied
    digest or original-request prose is never independent approval.
    """
    need(type(config) is dict and config.get('fixture') is False, 'production assembly requires exact nonfixture config')
    paths = dict(outer_notebook=outer_notebook_path, operator=operator_path, material_review=material_review_path,
                 source_archive=source_archive_path, original_request=original_request_path)
    context = _verify_context(paths, scope=PRODUCTION_SCOPE)
    if parent_scorer_path is not None:
        from .parent_scoring import bind_parent_scorer
        bind_parent_scorer(context, parent_scorer_path, config=config)
    from .runner import run_owned
    return run_owned(config, output, original_epoch=_CONTEXTS[context]['receipt']['original_epoch'], external_context=context)


def synthetic_scoring_bootstrap(config, output, *, outer_notebook_path, operator_path,
                                material_review_path, source_archive_path, original_request_path, parent_scorer_path):
    """Same parent-only scorer orchestration on explicitly synthetic tiny material.

    This fixture cannot authorize production or change its unfilled release pins.
    """
    need(type(config) is dict and config.get('fixture') is True, 'synthetic assembly requires fixture config')
    paths = dict(outer_notebook=outer_notebook_path, operator=operator_path, material_review=material_review_path,
                 source_archive=source_archive_path, original_request=original_request_path)
    context = _verify_context(paths, scope=SYNTHETIC_SCOPE)
    from .parent_scoring import bind_parent_scorer
    bind_parent_scorer(context, parent_scorer_path, config=config)
    from .runner import run_owned
    return run_owned(config, output, original_epoch=_CONTEXTS[context]['receipt']['original_epoch'], external_context=context)


def synthetic_bootstrap_context(*, outer_notebook_path, operator_path,
                                material_review_path, source_archive_path, original_request_path):
    """Explicit offline fixture issuer; its scope can never pass production."""
    paths = dict(outer_notebook=outer_notebook_path, operator=operator_path, material_review=material_review_path,
                 source_archive=source_archive_path, original_request=original_request_path)
    return _verify_context(paths, scope=SYNTHETIC_SCOPE)


def _request_binding(receipt, *, request_path, request_sha256, sources, plan_sha256, clock, request=None):
    from .clock import OriginalClock
    from .planning import build_plan
    need(type(clock) is OriginalClock, 'original source-owned clock required')
    clock.check_mapping()
    fixture = receipt['scope'] == SYNTHETIC_SCOPE
    need(clock.fixture is fixture and clock.original_epoch == receipt['original_epoch'], 'original clock/scope differs from checked owner request')
    need(verify_inventory(sources) == receipt['raw_source_sha256'], 'checked bootstrap source differs')
    raw, ref = _read(request_path, maximum=1024**2)
    need(_sha_value(request_sha256) and ref['file_sha256'] == request_sha256, 'actual runner request byte identity differs')
    current = _json(raw, 'runner request')
    need(request is None or type(request) is dict and canonical(request) == canonical(current), 'parsed worker request differs from authenticated raw request')
    need(type(current) is dict and current.get('format') == 'owned-rl-worker-request-v1' and
         type(current.get('config')) is dict and current['config'].get('fixture') is fixture and
         current.get('scope') == receipt['scope'], 'runner request scope/config differs')
    need(current.get('sources') == sources and current.get('clock') == clock.receipt() and
         current.get('bootstrap') == receipt and current.get('plan_sha256') == plan_sha256,
         'runner request source/clock/plan/outer binding differs')
    need(build_plan(clock, fixture=fixture).sha256 == plan_sha256, 'canonical source-owned plan differs')
    return {'request_path': ref['path'], 'request_sha256': request_sha256, 'plan_sha256': plan_sha256,
            'clock': clock.receipt(), 'raw_source_sha256': receipt['raw_source_sha256'],
            'scope': receipt['scope'], 'bootstrap': deepcopy(receipt), 'sources': dict(sources)}


def _issue_release(binding, phase):
    _require_caller('owned_runtime.bootstrap', ('issue_parent_release', 'reverify_child_release', 'issue_synthetic_release'))
    from .release import ExternalReleaseCapability, _EXTERNAL_RELEASES
    need(phase in ('launch', 'session'), 'known external release phase required')
    cap = object.__new__(ExternalReleaseCapability)
    _EXTERNAL_RELEASES[id(cap)] = {**binding, 'capability': cap, 'phase': phase, 'pid': os.getpid()}
    return cap


def issue_parent_release(context, *, request_path, request_sha256, sources, plan_sha256, clock):
    """Bind the canonical runner's checked context to its exact written request."""
    _require_caller('owned_runtime.runner', ('run_owned',))
    entry = _context(context)
    need(not entry['parent_issued'], 'outer context parent issuance already consumed')
    entry['parent_issued'] = True
    need(entry['receipt']['scope'] == PRODUCTION_SCOPE, 'synthetic context can never issue a production release')
    binding = _request_binding(entry['receipt'], request_path=request_path, request_sha256=request_sha256,
                               sources=sources, plan_sha256=plan_sha256, clock=clock)
    return _issue_release(binding, 'launch')


def reverify_child_release(request_path, request_sha256, *, request, sources, plan_sha256, clock):
    """Recheck actual outer/source bytes inside the authenticated owned worker."""
    _require_caller('owned_runtime.worker', ('main',))
    need(type(request) is dict and type(request.get('bootstrap')) is dict, 'checked parent bootstrap descriptor required')
    given = request['bootstrap']
    need(given.get('scope') == PRODUCTION_SCOPE and all(type(given.get(name)) is dict and
         set(given[name]) == {'path', 'file_sha256'} for name in _FILES), 'production parent raw descriptors required')
    receipt, actual_sources = _checked_files({name: given[name]['path'] for name in _FILES}, scope=PRODUCTION_SCOPE)
    need(receipt == given and actual_sources == sources, 'parent/child checked outer descriptor differs')
    binding = _request_binding(receipt, request_path=request_path, request_sha256=request_sha256,
                               sources=sources, plan_sha256=plan_sha256, clock=clock, request=request)
    identity = (os.getpid(), request_sha256, 'session')
    need(identity not in _CHILD_ISSUED, 'same authenticated child request cannot issue another session release')
    _CHILD_ISSUED.add(identity)
    return _issue_release(binding, 'session')


def issue_synthetic_release(context, *, request_path, request_sha256, sources, plan_sha256, clock, phase='launch'):
    """Offline fixture of identical byte/request checks; never production authority."""
    entry = _context(context)
    need(entry['receipt']['scope'] == SYNTHETIC_SCOPE, 'fixture issuer accepts only explicitly synthetic checked context')
    need(not entry['parent_issued'], 'synthetic context issuance already consumed')
    entry['parent_issued'] = True
    binding = _request_binding(entry['receipt'], request_path=request_path, request_sha256=request_sha256,
                               sources=sources, plan_sha256=plan_sha256, clock=clock)
    return _issue_release(binding, phase)


def _consume(capability, *, sources, phase, request_sha256, plan_sha256, clock, scope):
    from .release import ExternalReleaseCapability, _EXTERNAL_RELEASES
    need(type(capability) is ExternalReleaseCapability, 'live typed external release capability required; JSON is not authority')
    entry = _EXTERNAL_RELEASES.pop(id(capability), None)
    need(entry is not None and entry['capability'] is capability, 'fresh one-use external release capability required')
    need(entry['pid'] == os.getpid(), 'external release capability cannot cross processes')
    need(entry['scope'] == scope, 'synthetic capability can never authorize production')
    need(entry['phase'] == phase and phase in ('launch', 'session'), 'external release actual phase differs')
    clock.check_mapping()
    need(entry['request_sha256'] == request_sha256 and entry['plan_sha256'] == plan_sha256 and
         entry['clock'] == clock.receipt() and entry['sources'] == sources,
         'external release request/plan/original-clock/source binding differs')
    need(verify_inventory(sources) == entry['raw_source_sha256'], 'external release full raw source differs')
    _, current = _read(entry['request_path'], maximum=1024**2)
    need(current['file_sha256'] == request_sha256, 'actual runner request changed before phase consumption')
    _recheck_refs(entry['bootstrap'])
    return {key: deepcopy(value) for key, value in entry.items() if key != 'capability'}


def consume_external_release(capability, *, sources, phase, request_sha256, plan_sha256, clock):
    """Actual production-phase gate. No argument can enable synthetic admission."""
    need(phase in ('launch', 'session'), 'known external release phase required')
    _require_caller('owned_runtime.supervisor' if phase == 'launch' else 'owned_runtime.factory',
                    ('register_launch',) if phase == 'launch' else ('_construct',))
    return _consume(capability, sources=sources, phase=phase, request_sha256=request_sha256,
                    plan_sha256=plan_sha256, clock=clock, scope=PRODUCTION_SCOPE)


def consume_synthetic_release(capability, *, sources, phase, request_sha256, plan_sha256, clock):
    """Only verifies the explicitly synthetic offline mechanics fixture."""
    return _consume(capability, sources=sources, phase=phase, request_sha256=request_sha256,
                    plan_sha256=plan_sha256, clock=clock, scope=SYNTHETIC_SCOPE)
