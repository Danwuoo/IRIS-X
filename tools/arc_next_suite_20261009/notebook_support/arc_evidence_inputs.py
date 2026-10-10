"""Hash-bound notebook I/O only. The locked scientific runner is unchanged.

No execution, installation, network access or file mutation occurs on import.
All prior content is data; only the separately verified scientific runner acts.
"""
from pathlib import Path, PurePosixPath
import json
import os
import stat
import zipfile

REVISION = 'evidence-inputs-fix2-20261010'
REQUIRED = {'N9': ('N6',), 'N10': ('N6',), 'N11': ('N6',), 'N12': ('N7',),
            'N14': ('N6', 'N7', 'N9', 'N10', 'N11')}
MAX_FILES = 20000
MAX_BYTES = 250 * 1024 * 1024
MAX_METADATA = 4 * 1024 * 1024
MAX_DEPTH = 7
MAX_DIRECTORIES = 1024
MAX_ENTRIES = 12000
MAX_CANDIDATES = 128
MAX_ATTEMPTS = 1000
KAGGLE_INPUT_ROOT = Path('/kaggle/input')
VCS_METADATA_NAMES = frozenset({'.git', '.hg', '.svn'})
# Typed provider namespaces/known competition association are not prior evidence.
# This is path-scoped: an ordinary Dataset wrapper named competitions is allowed.
COMPETITION_SLUGS = frozenset({'arc-prize-2026-arc-agi-3'})


class InputError(ValueError):
    def __init__(self, reason, details):
        super().__init__(reason)
        self.reason = reason
        self.details = details


def safe_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink prior/output path forbidden: ' + str(path))
    return path


def metadata(path):
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size > MAX_METADATA:
        raise ValueError('Missing/oversized evidence metadata: ' + str(path))
    return json.loads(path.read_bytes())


def safe_name(name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or '..' in p.parts or '.' in p.parts or
            '\\' in name or ':' in name or p.as_posix() != name):
        raise ValueError('Unsafe evidence member: ' + name)
    return p


def preflight_directory(path):
    """Bound work before the frozen verifier hashes the entire closed artifact."""
    path = safe_path(path)
    if not path.is_dir():
        raise ValueError('Prior evidence directory missing')
    count = total = 0
    pending = [(path, 0)]
    while pending:
        parent, depth = pending.pop()
        if depth > 8:
            raise ValueError('Evidence directory nesting limit')
        for item in parent.iterdir():
            count += 1
            if count > MAX_FILES:
                raise ValueError('Evidence inventory count limit')
            mode = item.lstat().st_mode
            safe_name(item.relative_to(path).as_posix())
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError('Symlink/special evidence member forbidden')
            if stat.S_ISDIR(mode):
                pending.append((item, depth + 1))
            else:
                total += item.stat().st_size
                if total > MAX_BYTES:
                    raise ValueError('Evidence byte limit')
    inventory = metadata(path / 'final-inventory.json')
    if not isinstance(inventory.get('files'), dict):
        raise ValueError('Evidence file inventory required')
    for name in inventory['files']:
        safe_name(name)
    return path


def materialize(suite, path):
    """Reject symlinks before resolve(); delegate exact ZIP extraction to the runner."""
    path = safe_path(path)
    if path.is_dir():
        return preflight_directory(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Prior evidence file missing/oversized')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Prior archive inventory/size limit')
        for info in infos:
            safe_name(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not stat.S_ISREG(mode)):
                raise ValueError('Prior archive unsafe member')
    return preflight_directory(suite.materialize_prior(path))


def verify_candidate(suite, path, run_id, allow_blocked=False):
    root = materialize(suite, path)
    suite.verify_final_inventory(root)
    if (root / 'blocked.json').is_file():
        receipt = metadata(root / 'blocked.json')
        files = metadata(root / 'final-inventory.json')['files']
        if (not allow_blocked or run_id not in ('N9', 'N10', 'N11') or
                set(files) != {'blocked.json'} or receipt.get('run_id') != run_id or
                receipt.get('suite_revision') != suite.SUITE_REVISION or
                receipt.get('source_lock_sha256') != suite.file_sha(suite.ROOT / 'source-lock.json') or
                receipt.get('status') != 'blocked' or receipt.get('reason') != 'admission-threshold-not-met' or
                type(receipt.get('generate_calls')) is not int or receipt.get('generate_calls') != 0 or
                type(receipt.get('training_calls')) is not int or receipt.get('training_calls') != 0):
            raise ValueError('Only verified admission-threshold BLOCKED evidence can enter N14')
        identity = {'run_id': run_id, 'blocked_sha256': suite.file_sha(root / 'blocked.json')}
    else:
        manifest, report, receipt = suite.verified_prior(root, run_id)
        if report.get('search_ledger_complete') is not True:
            raise ValueError('Prerequisite search ledger incomplete')
        identity = dict(receipt)
        identity['source_lock_sha256'] = manifest['core']['source_lock_sha256']
    identity['final_inventory_sha256'] = suite.file_sha(root / 'final-inventory.json')
    return root, identity


def candidate_run(suite, path):
    """Read only bounded identity metadata before full validation of relevant runs."""
    path = safe_path(path)
    if path.is_dir():
        if (path / 'manifest.json').is_file():
            return metadata(path / 'manifest.json').get('core', {}).get('run_id')
        if (path / 'blocked.json').is_file():
            return metadata(path / 'blocked.json').get('run_id')
        return None
    if path.stat().st_size > MAX_BYTES:
        return None
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Prior archive inventory/size limit')
        for name in ('manifest.json', 'blocked.json'):
            try:
                info = archive.getinfo(name)
            except KeyError:
                continue
            if info.file_size > MAX_METADATA:
                raise ValueError('Oversized prior identity metadata')
            value = json.loads(archive.read(info))
            return value.get('core', {}).get('run_id') if name == 'manifest.json' else value.get('run_id')
    return None


def scan_candidates(search_roots, excluded_roots=(), excluded_names=()):
    """Bounded filename scan; never recursively enumerate the five large asset trees."""
    excluded = {safe_path(p) for p in excluded_roots if p}
    competition_roots = {KAGGLE_INPUT_ROOT / 'competitions', *[KAGGLE_INPUT_ROOT / slug for slug in COMPETITION_SLUGS]}
    def competition_path(path):
        normalized = Path(os.path.abspath(path))
        return any(normalized.is_relative_to(root) for root in competition_roots)
    names = set(excluded_names) | VCS_METADATA_NAMES
    skipped = []
    candidates = []
    visited = set()
    directories = entries = 0
    pending = [(safe_path(p), 0) for p in search_roots]
    while pending:
        directory, depth = pending.pop(0)
        if directory in visited:
            continue
        if directory in excluded or directory.name in names or competition_path(directory):
            skipped.append(str(directory))
            continue
        visited.add(directory)
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise InputError('invalid-prior-search-root', {'path': str(directory)})
        directories += 1
        if directories > MAX_DIRECTORIES:
            raise InputError('prior-discovery-limit', {'limit': 'directories'})
        children = []
        with os.scandir(directory) as stream:
            for entry in stream:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise InputError('prior-discovery-limit', {'limit': 'entries'})
                children.append(entry)
        byname = {e.name: e for e in children}
        # Only a recognizable evidence inventory closes a subtree. Dataset wrappers
        # may legitimately contain their own manifest/report alongside N6/N7 folders.
        closed = False
        if 'final-inventory.json' in byname:
            try:
                closed = metadata(directory / 'final-inventory.json').get('format') == 'irisx/nextphase-final-inventory-v1'
            except Exception:
                pass
        if {'manifest.json', 'blocked.json', 'final-inventory.json', 'report.json'} & set(byname):
            candidates.append(directory)
        if not closed:
            for entry in sorted(children, key=lambda e: e.name):
                p = Path(entry.path)
                if p in excluded or entry.name in names or competition_path(p):
                    skipped.append(str(p))
                    continue
                if entry.is_symlink():
                    # A symlink may hide a second matching identity, so never silently follow/ignore it.
                    raise InputError('unsafe-prior-discovery-path', {'path': str(p), 'reason': 'symlink'})
                if entry.is_dir(follow_symlinks=False):
                    if p in excluded or entry.name in names or competition_path(p):
                        continue
                    if depth >= MAX_DEPTH:
                        raise InputError('prior-discovery-limit', {'limit': 'depth', 'path': str(p)})
                    pending.append((p, depth + 1))
                elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith('.zip'):
                    if entry.stat(follow_symlinks=False).st_size <= MAX_BYTES:
                        candidates.append(p)
        if len(candidates) > MAX_CANDIDATES:
            raise InputError('prior-discovery-limit', {'limit': 'candidates'})
    return sorted(set(candidates)), {'directories': directories, 'entries': entries, 'candidates': len(candidates), 'excluded_paths': sorted(set(skipped))}


def discover_priors(suite, run_id, explicit=None, search_roots=('/kaggle/input',), excluded_roots=(), expected_evidence=None):
    required = REQUIRED.get(run_id, ())
    explicit = explicit or {}
    if set(explicit) - set(required):
        raise InputError('unexpected-prior-override', {'keys': sorted(set(explicit) - set(required))})
    report = {'helper_revision': REVISION, 'required': list(required), 'search_roots': [str(p) for p in search_roots],
              'selected': {}, 'rejected': [], 'missing': []}
    if not required:
        report['scan'] = {'directories': 0, 'entries': 0, 'candidates': 0}
        return {}, report
    paths = {}
    unresolved = []
    for required_run in required:
        if explicit.get(required_run) is None:
            unresolved.append(required_run)
            continue
        try:
            root, identity = verify_candidate(suite, explicit[required_run], required_run, run_id == 'N14')
        except Exception as exc:
            raise InputError('invalid-prerequisite', {'run_id': required_run, 'override': str(explicit[required_run]), 'error': str(exc)}) from exc
        paths[required_run] = str(root)
        report['selected'][required_run] = {'method': 'explicit-override', 'path': str(explicit[required_run]), 'identity': identity}
    if not unresolved:
        report['scan'] = {'directories': 0, 'entries': 0, 'candidates': 0}
        return paths, report
    excluded_names = [p['reference'].split('/')[1] for p in suite.EXPECTED_PINS.values()]
    candidates, report['scan'] = scan_candidates(search_roots, excluded_roots, excluded_names)
    matches = {r: {} for r in unresolved}
    for candidate in candidates:
        try:
            claimed_run = candidate_run(suite, candidate)
            if claimed_run not in unresolved:
                if claimed_run is None:
                    report['rejected'].append({'path': str(candidate), 'reason': 'no-run-identity-or-report-only'})
                continue
            root, identity = verify_candidate(suite, candidate, claimed_run, run_id == 'N14')
            key = suite.digest(identity)
            matches[claimed_run].setdefault(key, {'identity': identity, 'copies': []})['copies'].append((candidate, root))
        except Exception as exc:
            report['rejected'].append({'path': str(candidate), 'reason': str(exc)[:1200]})
    for required_run in unresolved:
        found = matches[required_run]
        if len(found) > 1:
            raise InputError('ambiguous-prerequisite', {'run_id': required_run, 'valid_identities': [
                {'identity': x['identity'], 'paths': [str(p) for p, _ in x['copies']]} for _, x in sorted(found.items())],
                'action': 'Set PRIOR_RESULTS for this run to the intended complete evidence root or ZIP.'})
        if not found:
            report['missing'].append(required_run)
            continue
        match = next(iter(found.values()))
        expected = (expected_evidence or {}).get(required_run, {}).get('final_inventory_sha256')
        if expected and match['identity']['final_inventory_sha256'] != expected:
            raise InputError('prerequisite-evidence-pin-mismatch', {'run_id': required_run, 'expected': expected,
                'observed': match['identity']['final_inventory_sha256'], 'action': 'Use the attached reviewed evidence or an intentional PRIOR_RESULTS override.'})
        # Byte-identical closed evidence has one identity. Prefer its directory deterministically.
        copies = sorted(match['copies'], key=lambda pair: (not pair[0].is_dir(), str(pair[0])))
        candidate, root = copies[0]
        paths[required_run] = str(root)
        report['selected'][required_run] = {'method': 'verified-discovery', 'path': str(candidate),
            'identical_copies': [str(p) for p, _ in copies], 'identity': match['identity'],
            'evidence_pin_verified': bool(expected)}
    return paths, report


def verify_blocked_attempt(suite, output, run_id):
    output = preflight_directory(output)
    suite.verify_final_inventory(output)
    inventory = metadata(output / 'final-inventory.json')
    value = metadata(output / 'blocked.json')
    if (set(inventory['files']) != {'blocked.json'} or value.get('status') != 'blocked' or
            value.get('run_id') != run_id or value.get('suite_revision') != suite.SUITE_REVISION or
            value.get('source_lock_sha256') != suite.file_sha(suite.ROOT / 'source-lock.json') or
            type(value.get('generate_calls')) is not int or value.get('generate_calls') != 0 or
            type(value.get('training_calls')) is not int or value.get('training_calls') != 0):
        raise ValueError('Retry requires a verified terminal zero-call BLOCKED receipt; preserve this attempt')
    return {'output': str(output), 'blocked_sha256': suite.file_sha(output / 'blocked.json'),
            'final_inventory_sha256': suite.file_sha(output / 'final-inventory.json')}


def allocate_output_root(suite, base, run_id):
    """Only zero-call terminal blocks permit a new attempt. Never resume model work."""
    base = safe_path(base)
    history = []
    identity = suite.experiment_identity(run_id)
    attempts = base / 'attempts'
    if attempts.exists():
        safe_path(attempts)
        names = sorted(p.name for p in attempts.iterdir())
        if any(not (len(n) == 12 and n.startswith('attempt-') and n[8:].isdigit()) for n in names):
            raise ValueError('Unexpected retry namespace; preserve and inspect it')
        numbers = [int(n[8:]) for n in names]
        if numbers != list(range(2, len(numbers) + 2)):
            raise ValueError('Retry history gap; preserve and inspect it')
    else:
        numbers = []
    for number in range(1, MAX_ATTEMPTS + 1):
        output_root = base / 'runs' if number == 1 else attempts / ('attempt-%04d' % number) / 'runs'
        output = safe_path(output_root / identity)
        archive = safe_path(output.with_name(output.name + '-evidence.zip'))
        journal = safe_path(base / 'orchestration' / ('attempt-%04d-inputs.json' % number))
        if output.exists():
            history.append(verify_blocked_attempt(suite, output, run_id))
            continue
        if archive.exists() or journal.exists() or any(n >= number for n in numbers):
            raise ValueError('Incomplete/orphaned attempt namespace; preserve and inspect it')
        return output_root, journal, history
    raise ValueError('Retry namespace limit; preserve all previous attempts')


def asset_roots(suite, run_id, explicit):
    required = () if run_id == 'N13' else ('runtime',) if run_id == 'N5' else tuple(suite.EXPECTED_PINS)
    roots = {}
    for role in required:
        owner, slug, _ = suite.EXPECTED_PINS[role]['reference'].split('/')
        choices = [Path(explicit[role])] if explicit.get(role) else [Path('/kaggle/input/datasets') / owner / slug, Path('/kaggle/input') / slug]
        found = [safe_path(p) for p in choices if p.is_dir()]
        if len(found) != 1:
            raise ValueError('Exactly one pinned Dataset mount required: ' + role)
        roots[role] = found[0]
    return roots


def launch_notebook(suite, base, run_id, *, prior_results=None, prior_search_roots=('/kaggle/input',), explicit_roots=None, prior_dataset_pin=None):
    """Manual-start caller only. Missing gates block before asset/install/model access."""
    explicit_roots = explicit_roots or {}
    base = suite._safe_output(safe_path(base), [p for p in explicit_roots.values() if p] + list(prior_search_roots))
    output_root, journal, history = allocate_output_root(suite, base, run_id)
    suite.verify_sources()
    suite.require_security_release()
    try:
        paths, discovery = discover_priors(suite, run_id, prior_results, prior_search_roots, explicit_roots.values(), (prior_dataset_pin or {}).get('sources'))
        gate = suite.resolve_gate(run_id, paths)
    except InputError as exc:
        paths = {}
        discovery = {'helper_revision': REVISION, 'error': exc.details}
        gate = {'status': 'blocked', 'reason': exc.reason, 'details': exc.details}
    except Exception as exc:
        paths = {}
        discovery = {'helper_revision': REVISION, 'error': str(exc)}
        gate = {'status': 'blocked', 'reason': 'invalid-prerequisite', 'error': {'type': type(exc).__name__, 'message': str(exc)[:2000]}}
    roots = {}
    if gate['status'] == 'passed':
        try:
            roots = asset_roots(suite, run_id, explicit_roots)
        except Exception as exc:
            gate = {'status': 'blocked', 'reason': 'missing-or-invalid-asset-mount',
                    'error': {'type': type(exc).__name__, 'message': str(exc)[:2000]}}
        if roots:
            suite._safe_output(base, list(roots.values()) + list(paths.values()))
    log = {'format': 'irisx/notebook-input-receipt-v1', 'helper_revision': REVISION,
        'helper_sha256': suite.file_sha(__file__), 'run_id': run_id, 'source_lock_sha256': suite.file_sha(suite.ROOT / 'source-lock.json'),
        'output_root': str(output_root), 'declared_prior_dataset_pin': prior_dataset_pin, 'wrapper_manifest_runtime_verified': False, 'preserved_blocked_attempts': history, 'discovery': discovery, 'gate': gate}
    suite.write(journal, log)
    suite.progress('PREREQUISITE-DISCOVERY', **log)
    if gate['status'] == 'blocked':
        output = output_root / suite.experiment_identity(run_id)
        output.mkdir(parents=True, exist_ok=False)
        receipt = {**gate, 'run_id': run_id, 'suite_revision': suite.SUITE_REVISION,
            'source_lock_sha256': suite.file_sha(suite.ROOT / 'source-lock.json'), 'generate_calls': 0, 'training_calls': 0,
            'input_receipt': str(journal), 'input_receipt_sha256': suite.file_sha(journal),
            'next_step': 'Attach complete prerequisite evidence as a private Kaggle input; ZIP or auto-extracted folders are discovered automatically. Keep PRIOR_RESULTS=None entries unless selecting an explicit override.',
            'expected_runs': list(REQUIRED.get(run_id, ())), 'searched_roots': [str(p) for p in prior_search_roots]}
        suite.write(output / 'blocked.json', receipt)
        archive = suite.finalize(output)
        suite.progress('EXPERIMENT-BLOCKED', **receipt, archive=archive)
        return {**receipt, 'archive': archive, 'output': str(output)}
    cfg = {'output_root': str(output_root)}
    if run_id != 'N13':
        cfg['runtime_root'] = str(roots['runtime'])
    if run_id not in ('N5', 'N13'):
        cfg.update({role + '_root': str(path) for role, path in roots.items()})
        cfg.update(interpreter_dir=str(base / 'cpython312'), environment_dir=str(base / 'environment-cp312-cu128'), pins=suite.EXPECTED_PINS)
    result = suite.launch(cfg, run_id, enabled=True, prior_paths=paths)
    return {**result, 'input_receipt': str(journal), 'input_receipt_sha256': suite.file_sha(journal)}
