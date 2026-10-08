"""Immutable output generations; single-marker commit and verified projections.

No model/provider IO. Hashes provide byte identity, never native qualification.
Callers own semantic validation and exact bindings. See nvarc-output-lifecycle.md.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import hashlib
import os
from pathlib import Path
import re
import sys
import time
import traceback
import uuid

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, require

FORMAT = 'irisx/output-generation-v1'
SETS = {
    'paired-dfs-floor': {'p02-answers.json','p01-answers.json','p02-audit.json','p01-audit.json',
               'p02-candidate-pools.json','p01-candidate-pools.json','paired-summary.json','paired-task-timings.json'},
    'paired': {'interleaved-answers.json','deferred-answers.json','interleaved-audit.json','deferred-audit.json',
               'interleaved-candidate-pools.json','deferred-candidate-pools.json','paired-summary.json','paired-task-timings.json'},
    'public': {'submission.json', 'submission-audit.json', 'candidate-pools.json',
               'coverage.json', 'task-timings.json'},
    'native': {'native-evidence.json', 'submission-audit.json', 'submission.json', 'export-process.json'},
    'official': {'native-evidence.json', 'submission-audit.json', 'submission.json',
                 'export-process.json', 'official-summary.json'},
}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def outcomes(output_valid=False, notebook_exit='unknown', evidence_qualified=False):
    require(type(output_valid) is type(evidence_qualified) is bool and
            notebook_exit in {'unknown', 'success', 'failure'}, 'independent outcome types required')
    return dict(output_valid=output_valid, notebook_exit=notebook_exit,
                evidence_qualified=evidence_qualified, promotion=False)


def directory_sync(path):
    if os.name == 'nt':
        return 'unavailable-windows-api'
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP}:
                raise
            return 'unsupported'
        return 'observed-success-no-power-loss-claim'
    finally:
        os.close(descriptor)


def write_exclusive(path, body):
    with Path(path).open('xb') as stream:
        require(stream.write(body) == len(body), 'short output write')
        stream.flush()
        os.fsync(stream.fileno())


def atomic_bytes(path, body, *, observe=lambda *_: None):
    """Separate replacement API: does not relax generic write_new's contract."""
    path = Path(path)
    require(not path.is_symlink(), 'symlink projection forbidden')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    write_exclusive(temporary, body)
    observe('before-replace', path)
    os.replace(temporary, path)
    observe('after-replace', path)
    return directory_sync(path.parent)


def manifest_snapshot(root):
    """Validate the marker/path before opening any referenced manifest."""
    root = Path(root); marker_path = root/'output-commit.json'
    require(not marker_path.is_symlink(), 'regular commit marker required')
    marker = parse_json(marker_path.read_bytes())
    require(set(marker) == {'format', 'generation', 'manifest_sha256'} and
            marker['format'] == FORMAT and isinstance(marker['generation'], str) and
            re.fullmatch('[0-9a-f]{32}', marker['generation']), 'invalid generation marker')
    directory = root/'.output-generations'/marker['generation']
    require(not (root/'.output-generations').is_symlink() and not directory.is_symlink(),
            'regular confined generation required')
    manifest_path = directory/'manifest.json'
    require(not manifest_path.is_symlink(), 'regular manifest required')
    body = manifest_path.read_bytes()
    require(sha(body) == marker['manifest_sha256'], 'manifest hash differs')
    return marker, directory, parse_json(body)


class GenerationStore:
    """One owner, immutable members, no newest-file scan or stale fallback."""
    def __init__(self, root, kind, bindings, *, observe=lambda *_: None,
                 now=time.monotonic, deadline=None):
        self.root, self.kind = Path(root), kind
        require(kind in SETS and isinstance(bindings, dict) and bindings.get('run_id'),
                'exact generation kind/run binding required')
        self.bindings = parse_json(canonical(bindings))
        self.observe, self.now, self.deadline = observe, now, deadline

    def boundary(self, stage, path):
        if self.deadline is not None and self.now() >= self.deadline:
            raise TimeoutError('output publication deadline at ' + stage)
        self.observe(stage, Path(path))

    @contextmanager
    def writer(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.output-writer.lock'
        write_exclusive(lock, canonical({'pid': os.getpid(), 'token': uuid.uuid4().hex,
                                        'bindings': self.bindings}))
        try:
            yield
        except BaseException as primary:
            try:
                lock.unlink()
            except BaseException as secondary:
                primary.add_note('writer lock cleanup failed: '+repr(secondary))
            raise
        else:
            lock.unlink()  # OS kill leaves it for explicit quiescent-owner cleanup.

    def publish(self, values, *, evidence_qualified=False):
        require(set(values) == SETS[self.kind], 'closed output file set required')
        bodies = {name: canonical(value) for name, value in values.items()}
        # Publication never marks a process successful or promotes a method.
        status = outcomes(True, 'unknown', evidence_qualified)
        with self.writer():
            if (self.root/'output-commit.json').exists():
                self.read()  # Never overwrite a foreign/corrupt committed store.
            base = self.root / '.output-generations'
            require(not base.is_symlink(), 'regular generation base required')
            base.mkdir(exist_ok=True)
            name = uuid.uuid4().hex
            directory = base / name
            directory.mkdir()
            for filename, body in sorted(bodies.items()):
                path = directory / filename
                self.boundary('before-member', path)
                write_exclusive(path, body)
                self.boundary('after-member', path)
            members = {n: {'bytes': len(b), 'sha256': sha(b)} for n, b in sorted(bodies.items())}
            require(all((directory/n).read_bytes() == b for n, b in bodies.items()),
                    'generation readback differs')
            durability = {'file_fsync': 'completed-before-commit',
                'member_directory_fsync_before_manifest': directory_sync(directory),
                'power_loss_verified': False, 'replace_scope': 'single-path-same-filesystem'}
            manifest = dict(format=FORMAT, generation=name, kind=self.kind, bindings=self.bindings,
                            members=members, outcomes=status, durability=durability)
            self.boundary('before-manifest', directory)
            write_exclusive(directory/'manifest.json', canonical(manifest))
            directory_sync(directory)
            directory_sync(base)
            marker = dict(format=FORMAT, generation=name, manifest_sha256=sha(canonical(manifest)))
            self.boundary('before-commit', directory)
            atomic_bytes(self.root/'output-commit.json', canonical(marker), observe=self.boundary)
            self.boundary('after-commit', directory)
            # A post-commit failure must not make the generation disappear.
            loaded, verified = self.read()
            self._project(loaded, verified)
            return loaded

    def read(self):
        """Read marker once; verify closed immutable inventory and exact bindings."""
        marker, directory, manifest = manifest_snapshot(self.root)
        require(set(manifest) == {'format', 'generation', 'kind', 'bindings', 'members', 'outcomes', 'durability'} and
                manifest['format'] == FORMAT and manifest['generation'] == marker['generation'] and
                manifest['kind'] == self.kind and manifest['bindings'] == self.bindings,
                'stale/foreign generation binding')
        require(set(manifest['members']) == SETS[self.kind] and
                {p.name for p in directory.iterdir()} == SETS[self.kind] | {'manifest.json'},
                'generation inventory differs')
        status = manifest['outcomes']
        require(status == outcomes(True, 'unknown', status['evidence_qualified']),
                'generation cannot assert notebook exit or promotion')
        durability = manifest['durability']
        require(set(durability) == {'file_fsync', 'member_directory_fsync_before_manifest',
                                   'power_loss_verified', 'replace_scope'} and
                durability['file_fsync'] == 'completed-before-commit' and durability['power_loss_verified'] is False and
                durability['replace_scope'] == 'single-path-same-filesystem' and
                durability['member_directory_fsync_before_manifest'] in {
                    'unavailable-windows-api', 'unsupported', 'observed-success-no-power-loss-claim'},
                'unverified durability claim forbidden')
        bodies = {}
        for filename, item in manifest['members'].items():
            path = directory/filename
            require(path.is_file() and not path.is_symlink() and
                    set(item) == {'bytes', 'sha256'} and type(item['bytes']) is int,
                    'regular digest-bound member required')
            body = path.read_bytes()
            require(len(body) == item['bytes'] and sha(body) == item['sha256'], 'member hash differs: '+filename)
            parse_json(body)
            bodies[filename] = body
        return manifest, bodies

    def _project(self, manifest, bodies):
        # All root files are replaceable compatibility projections. The marker
        # makes a partially updated set invalid, even when submission is legal.
        ordered=sorted(set(bodies)-{'submission.json'})
        if 'submission.json' in bodies:ordered.append('submission.json')
        for name in ordered:
            self.boundary('before-projection', self.root/name)
            atomic_bytes(self.root/name, bodies[name], observe=self.boundary)
            self.boundary('after-projection', self.root/name)
        self.boundary('before-projection-marker', self.root)
        atomic_bytes(self.root/'output-projection.json', canonical({
            'format': FORMAT, 'generation': manifest['generation'],
            'manifest_sha256': sha(canonical(manifest))}), observe=self.boundary)

    def verify_projection(self):
        manifest, bodies = self.read()
        expected = {'format': FORMAT, 'generation': manifest['generation'],
                    'manifest_sha256': sha(canonical(manifest))}
        path = self.root/'output-projection.json'
        require(not path.is_symlink() and parse_json(path.read_bytes()) == expected,
                'root projection marker differs')
        require(all(not (self.root/n).is_symlink() and (self.root/n).read_bytes() == b
                    for n, b in bodies.items()), 'mixed/stale root projection')
        return manifest

    def recover(self, validate):
        """Caller must rerun semantic/source gates before any projection repair."""
        with self.writer():
            manifest, bodies = self.read()
            validate(manifest, {n: parse_json(b) for n, b in bodies.items()})
            self._project(manifest, bodies)
            return manifest


def diagnostic(error, phase):
    value = {'phase': phase, 'type': type(error).__name__, 'message': str(error)[:2400],
             'traceback': ''.join(traceback.format_exception(error))[-12000:]}
    if hasattr(error, 'cleanup_report'): value['cleanup'] = error.cleanup_report
    return value


def cleanup_workers(resources, stop, *, primary=None, drains=()):
    """Attempt each bounded stop/close independently; drain only stopped producers.

    The caller supplies a finite stop function. A successful stop call alone is
    insufficient: poll must confirm exit. Never replace an active exception.
    Without one, raise the first cleanup error after attempting all resources.
    """
    report = {'workers': [], 'secondary_errors': [], 'all_producers_stopped': True,
              'drain_status': 'not-requested'}
    errors = []
    def failed(error, phase):
        errors.append(error); report['secondary_errors'].append(diagnostic(error, phase))
    for item in resources:
        identity = str(item['identity']); process = item.get('process')
        row = {'identity': identity, 'pid': None if process is None else process.pid,
               'stop_attempted': process is not None, 'returncode': None,
               'stop_confirmed': None, 'streams': {}}
        report['workers'].append(row)
        if process is not None:
            try: stop(process)
            except BaseException as error: failed(error, 'stop:'+identity)
            try:
                row['returncode'] = process.poll()
                row['stop_confirmed'] = row['returncode'] is not None
                if not row['stop_confirmed']:
                    failed(RuntimeError('producer exit unconfirmed: '+identity), 'poll:'+identity)
            except BaseException as error: failed(error, 'poll:'+identity)
            if row['stop_confirmed'] is not True: report['all_producers_stopped'] = False
        for name, stream in item.get('streams', {}).items():
            if stream is None: continue
            row['streams'][name] = {'close_attempted': True, 'closed': None}
            try: stream.close()
            except BaseException as error: failed(error, 'close:'+identity+':'+name)
            try:
                row['streams'][name]['closed'] = stream.closed
                if not stream.closed: failed(RuntimeError('stream close unconfirmed'), 'closed:'+identity+':'+name)
            except BaseException as error: failed(error, 'closed:'+identity+':'+name)
    drains = list(drains)
    if drains:
        report['drain_status'] = 'attempted' if report['all_producers_stopped'] else 'skipped-unconfirmed-producers'
        if report['all_producers_stopped']:
            for identity, action in drains:
                try: action()
                except BaseException as error: failed(error, 'drain:'+str(identity))
    target = primary if primary is not None else errors[0] if errors else None
    if target is not None:
        target.cleanup_report = report
        # Add compact notes; the structured diagnostic retains every failure.
        for value in report['secondary_errors']:
            target.add_note('cleanup secondary '+value['phase']+': '+value['type']+': '+value['message'])
    if primary is None and errors: raise target
    return report


def terminal_attempt(value, action, *, phase='terminal-logger', stderr=None):
    """One disk attempt; report secondary error without replacing primary."""
    try:
        action()
        return True
    except BaseException as error:
        value.setdefault('secondary_errors', []).append(diagnostic(error, phase))
        value.update(notebook_exit='failure', promotion=False)
        try:
            target = sys.stderr if stderr is None else stderr
            target.write(canonical(value).decode()+'\n')
            target.flush()
        except BaseException as fallback:
            value['secondary_errors'].append(diagnostic(fallback, phase+'-stderr'))
        return False
