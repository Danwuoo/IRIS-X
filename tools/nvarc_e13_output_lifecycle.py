"""Closed E13 output generation set using the unchanged atomic writer protocol.

Historical E10/E11/E12 file sets stay frozen. This copy admits only the eight E13
pilot members and binds every read to its single immutable generation marker.
"""
from contextlib import contextmanager
import os
import re
from pathlib import Path
import time
import uuid
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical,digest,require
from tools.nvarc_output_lifecycle import (FORMAT,sha,outcomes,directory_sync,write_exclusive,atomic_bytes,manifest_snapshot)

SETS={'e13-search-budget-pilot':{'search120-answers.json','search240-answers.json','search120-audit.json','search240-audit.json',
    'search120-candidate-pools.json','search240-candidate-pools.json','paired-summary.json','paired-task-timings.json'}}

class GenerationStore:
    """One owner, immutable members, no newest-file scan or stale fallback."""
    def __init__(self, root, kind, bindings, *, observe=lambda *_: None,
                 now=time.monotonic, deadline=None):
        self.root, self.kind = Path(root), kind
        from tools.nvarc_e13_admission import RUN_ID, read_plan, verify_execution
        require(kind in SETS and type(bindings) is dict and
            set(bindings) == {'run_id', 'plan_digest', 'challenges_digest'} and bindings['run_id'] == RUN_ID and
            all(type(bindings[k]) is str and re.fullmatch('sha256:[0-9a-f]{64}', bindings[k])
                for k in ('plan_digest', 'challenges_digest')), 'exact E13 generation kind/run/digest binding required')
        plan = read_plan(self.root)
        verify_execution(self.root, plan)
        require(digest(plan) == bindings['plan_digest'] and plan['challenges_digest'] == bindings['challenges_digest'],
            'output generation must bind admitted exact plan/challenges')
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
