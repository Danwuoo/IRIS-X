"""Bounded public-evaluation checkpoints/archives. No model, truth or provider IO."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import os
import sys
import zipfile
import time
import errno
from contextlib import contextmanager

from tools.nvarc_native_multitask import canonical, digest, write, require
from tools.arc_kaggle_submission import (challenge_counts, grid, grid as legal_grid,
    build_submission, parse_json)

FORMAT = 'irisx/nvarc-public-eval-v1'
INPUT_SHA = 'e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8'
RUNS = {'BASE-30': 'nvarc-public-base30-001', 'TTT128-30': 'nvarc-public-ttt128-30-001'}
ARCHIVE_LIMIT = 512 * 1024**2
TASK_FILES = {'checkpoint.json', 'result.json', 'training-ledger.json', 'prepared-rows.json',
    'preparation.json', 'native-schedule.json', 'baseline-inventory.json', 'trained-inventory.json',
    'reset-inventory.json', 'post-reset-control.json'}
WORKER_FILES = {'ready.json', 'process.json', 'job.json', 'done.json', 'load-telemetry.json'}


class MailboxReader:
    """One read per poll; bounded Windows access deferral, never a model retry.

    CRT reads can report only EACCES for a sharing/delete-pending conflict.
    An ACL denial is indistinguishable until it persists: fifth denied read
    fails closed. Callers keep their exit/deadline checks between attempts.
    JSON and identity validation deliberately happen outside this class.
    """
    MAX_ATTEMPTS = 5

    def __init__(self, *, read_bytes=Path.read_bytes, windows=os.name == 'nt', observe=None):
        self.read_bytes, self.windows, self.observe = read_bytes, windows, observe
        self.pending = {}; self.deferred_reads = 0; self.recovered_paths = 0

    def read(self, path, *, required=False):
        path = Path(path)
        if path in self.pending and self.pending[path][0] >= self.MAX_ATTEMPTS:
            raise self.pending[path][1]
        try:
            body = self.read_bytes(path)
        except FileNotFoundError as error:
            if not required and path not in self.pending:
                return None
            return self._defer(path, error)
        except PermissionError as error:
            if not (self.windows and error.errno == errno.EACCES and
                    getattr(error, 'winerror', None) in (None, 5, 32, 33)):
                raise
            return self._defer(path, error)
        if self.pending.pop(path, None) is not None:
            self.recovered_paths += 1
            if self.observe: self.observe('mailbox-read-recovered', path=path)
        return body

    def _defer(self, path, error):
        count = self.pending.get(path, (0, None))[0] + 1
        self.pending[path] = (count, error); self.deferred_reads += 1
        exhausted = count >= self.MAX_ATTEMPTS
        if self.observe:
            self.observe('mailbox-read-exhausted' if exhausted else 'mailbox-read-deferred',
                path=path, attempts=count, error_type=type(error).__name__,
                errno=error.errno, winerror=getattr(error, 'winerror', None))
        if exhausted:
            error.add_note('mailbox remained unreadable after five bounded read attempts')
            raise error
        return None

    def final_read(self, path, *, required=False, pause=time.sleep):
        """After producer termination only: at most four .2s deferred waits."""
        while True:
            body = self.read(path, required=required)
            if body is not None or Path(path) not in self.pending:
                return body
            pause(.2)


class PhaseTelemetry:
    """In-memory host clocks; no IO, device synchronization or solver decisions.

    Inclusive scopes may nest. Exclusive time is charged to the innermost
    phase, so it can be added within ONE collector (never across workers).
    Detail scopes only run when explicitly enabled and retain the parent phase.
    """
    PHASES = ('generation', 'verification', 'parse_dedup', 'ranking', 'training',
              'reset', 'load', 'export', 'control', 'preparation')

    def __init__(self, *, clock=time.monotonic, detailed=False):
        require(type(detailed) is bool, 'explicit boolean profiling switch required')
        self.clock, self.detailed = clock, detailed
        self.started = clock(); self.stack = []; self.last = self.started
        self.inclusive = {}; self.exclusive = {}; self.details = {}; self.events = []
        self.tests = {}

    def _charge(self, stamp):
        require(math.isfinite(stamp) and stamp >= self.last, 'monotonic finite host clock required')
        if self.stack:
            phase = self.stack[-1]['phase']
            self.exclusive[phase] = self.exclusive.get(phase, 0.0) + stamp-self.last
        self.last = stamp

    @contextmanager
    def scope(self, phase):
        require(phase in self.PHASES, 'known telemetry phase required')
        begin = self.clock(); self._charge(begin)
        frame = {'phase': phase}; self.stack.append(frame)
        self.inclusive.setdefault(phase, 0.0)
        try:
            yield
        except BaseException as error:
            self.events.append({'event': 'phase_exception', 'phase': phase,
                                'type': type(error).__name__})
            raise
        finally:
            end = self.clock(); self._charge(end)
            require(self.stack.pop() is frame, 'balanced host timing scope required')
            self.inclusive[phase] += end-begin

    @contextmanager
    def detail(self, name):
        # No additional clock read at all in the default per-forward hot path.
        if not self.detailed:
            yield
            return
        begin = self.clock()
        try:
            yield
        finally:
            self.details[name] = self.details.get(name, 0.0) + self.clock()-begin

    def begin_test(self, index, generation_deadline, verification_deadline):
        row = {'counters': {k: 0 for k in ('raw_returned', 'processed', 'invalid',
            'duplicate', 'parsed_unique', 'verification_started', 'partial_verified',
            'full_verified', 'ranked', 'votes_ranked')}, 'sequences': [], 'verifications': [],
            'forward_reservations': None, 'forward_completions': None,
            'reserved_physical_input_tokens': None, 'completed_physical_input_tokens': None,
            'cooperative_deadlines': {'clock': 'time.time epoch seconds',
                'generation': generation_deadline, 'verification': verification_deadline,
                'preemption': False, 'in_flight_may_overrun': True,
                'latest_generation_return': None, 'latest_verification_return': None,
                'generation_return_after_deadline': None, 'verification_return_after_deadline': None},
            'parent_hard_watchdog': None, 'termination_reason': 'interrupted_pending'}
        require(str(index) not in self.tests, 'one telemetry lifecycle per test required')
        self.tests[str(index)] = row
        return row

    def snapshot(self):
        require(not self.stack, 'close scopes before telemetry snapshot')
        elapsed = self.clock()-self.started
        return {'format': 'irisx/nvarc-host-telemetry-v1',
            'clock': 'time.monotonic host wall seconds',
            'gpu_kernel_seconds': None, 'gpu_timing_semantics':
                'asynchronous host wall; includes existing guards/readbacks/synchronization/IO where inside scope',
            'added_device_synchronizations': 0, 'per_token_telemetry_writes': 0,
            'detailed_profiling': self.detailed, 'elapsed_host_seconds': elapsed,
            'inclusive_host_seconds': {p: self.inclusive.get(p) for p in self.PHASES},
            'exclusive_host_seconds': {p: self.exclusive.get(p, 0.0) if p in self.inclusive else None
                                       for p in self.PHASES},
            'unscoped_host_seconds': max(0.0, elapsed-sum(self.exclusive.values())),
            'detail_inclusive_host_seconds': dict(self.details) if self.detailed else None,
            'aggregation': 'exclusive phases plus unscoped partition this collector; inclusive/detail scopes overlap; worker sums are not parent wall',
            'unobserved_phase_policy': 'null; absent scope is not measured zero',
            'training_forwards': None, 'tests': self.tests, 'events': list(self.events)}


def install_owner_guard(expected_pid, signal_number):
    """Linux parent-death signal, with both sides of the startup race checked.

    https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html
    """
    import ctypes
    require(sys.platform == 'linux' and expected_pid > 0 and os.getppid() == expected_pid,
            'live expected Linux owner required')
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    require(libc.prctl(1, signal_number, 0, 0, 0) == 0 and os.getppid() == expected_pid,
            'parent-death guard failed or owner already exited')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_plan(plan, challenges, *, allow_fixture=False):
    counts = challenge_counts(challenges)
    require(plan['format'] == FORMAT and plan['profile'] in RUNS and
        plan['run_id'] == RUNS[plan['profile']], 'exact public profile/run required')
    require(plan['approved'] is True and plan['owner_editor_only'] is True and
        plan['kernel_execution_type'] == 'QUICK_SAVE' and plan['owner_decision'] == 'Decision 0060' and
        plan['agent_execution_authorized'] is False, 'owner save-only envelope required')
    require(plan['maximum_paid_usd'] == plan['maximum_teacher_calls'] == 0 and
        plan['parallel_workers'] == 4 and plan['per_test_seconds'] == 30,
        'fixed free four-worker public scope required')
    require(plan['challenges_digest'] == digest(challenges) and
        plan['task_counts'] == counts and set(plan['task_materials']) == set(counts),
        'complete exact public input binding required')
    require(plan['maximum_notebook_wall_seconds'] == (3600 if plan['profile'] == 'BASE-30' else 14400) and
        plan['startup_seconds'] == 900 and plan['export_reserve_seconds'] == 300,
        'fixed finite session required')
    if not allow_fixture:
        require(plan.get('local_fixture') is False and len(counts) == 120 and sum(counts.values()) == 172 and
            plan['challenges_sha256'] == INPUT_SHA, 'standard 120-task/172-test public set required')
    return counts


def task_binding(plan, challenges, key):
    require(key in challenges, 'known public task required')
    return {'run_id': plan['run_id'], 'profile': plan['profile'], 'plan_digest': digest(plan),
            'challenges_digest': plan['challenges_digest'], 'task_id': key,
            'task_digest': digest(challenges[key]), 'model_material_digest': plan['model_material_digest']}


def empty_tests(count, reason='not_executed'):
    return [{'test_index': i, 'attempts': [], 'ranked_grids': [], 'status': 'not_executed',
             'termination_reason': reason, 'missing_attempts': 2} for i in range(count)]


def validate_record(plan, challenges, record):
    def truth_free(value):
        if isinstance(value, dict):
            require(not {'expected_output', 'expected_outputs', 'solutions', 'evaluator_truth',
                'ground_truth', 'answer_key', 'exact_match', 'official_score', 'diagnostic_label',
                'answer_rank', 'stratum', 'pass_at_1', 'pass_at_2', 'candidate_oracle',
                'oracle', 'evaluator_label', 'route_label'}.intersection(value),
                'evaluator fields forbidden in public predictions')
            for child in value.values(): truth_free(child)
        elif isinstance(value, list):
            for child in value: truth_free(child)
    truth_free(record)
    key = record['binding']['task_id']
    require(record['binding'] == task_binding(plan, challenges, key), 'foreign task/profile checkpoint')
    require(len(record['tests']) == len(challenges[key]['test']), 'all task tests required')
    for index, test in enumerate(record['tests']):
        require(type(test['test_index']) is int and test['test_index'] == index and test['attempts'] == test['ranked_grids'][:2] and
            test['missing_attempts'] == max(0, 2-len(test['attempts'])), 'ordered complete test binding differs')
        pool = [legal_grid(g) for g in test['ranked_grids']]
        require(len(pool) == len({digest(g) for g in pool}) <= 64, 'bounded unique candidate pool required')
        if pool:
            require(record['baseline_verified'] is True and
                (plan['profile'] == 'BASE-30' or record['training_complete'] is True and
                 record['training_steps'] == 128), 'qualified task state required before candidates')
            proof = test['candidate_evidence']
            require(set(proof) == {digest(g) for g in pool}, 'pool/verifier closure differs')
            for candidate in proof.values():
                require(len(candidate['scores']) == len(candidate['rows']) == 8 and
                    len({r['source_view'] for r in candidate['rows']}) == 8 and
                    all(type(s) in (int, float) and math.isfinite(s) and s >= 0 for s in candidate['scores']),
                    'all eight finite actual verifier views required')
                require([r['score'] for r in candidate['rows']] == candidate['scores'] and
                    all(r['source_view'].startswith(key+'_'+str(index)+'.') and
                        re.fullmatch(r'sha256:[0-9a-f]{64}', r['query_digest']) and
                        re.fullmatch(r'sha256:[0-9a-f]{64}', r['answer_digest']) for r in candidate['rows']),
                    'actual source verifier binding differs')
    return key


class ResultStore:
    def __init__(self, root, plan, challenges, *, allow_fixture=False):
        self.root, self.plan, self.challenges = Path(root), plan, challenges
        self.counts = validate_plan(plan, challenges, allow_fixture=allow_fixture)
        self.records = {}; self.flush()

    def commit(self, record):
        key = validate_record(self.plan, self.challenges, record)
        if key in self.records:
            for old, new in zip(self.records[key]['tests'], record['tests']):
                if old['ranked_grids']:
                    require(new['ranked_grids'] == old['ranked_grids'] and
                        new['candidate_evidence'] == old['candidate_evidence'], 'committed candidate cannot disappear or change')
        self.records[key] = parse_json(canonical(record))
        self.flush()

    def flush(self):
        exported = []
        for key, record in sorted(self.records.items()):
            tests = []
            for t in record['tests']:
                attempts = t['attempts']
                tests.append({'test_index': t['test_index'], 'attempts': attempts,
                    'status': ('complete' if len(attempts) == 2 else 'missing-candidate')
                              if t['status'] != 'not_executed' else 'not_executed'})
            exported.append({'task_id': key, 'tests': tests})
        submission, audit = build_submission(self.challenges, exported)
        write(self.root/'submission.json', submission); write(self.root/'submission-audit.json', audit)
        write(self.root/'candidate-pools.json', {'format': FORMAT, 'run_id': self.plan['run_id'],
            'plan_digest': digest(self.plan), 'records': self.records})
        rows = []
        for key, count in sorted(self.counts.items()):
            rec = self.records.get(key)
            for i in range(count):
                test = None if rec is None else rec['tests'][i]
                rows.append({'task_id': key, 'test_index': i, 'model_candidates': 0 if test is None else len(test['ranked_grids']),
                    'status': 'not_executed' if test is None else test['status'],
                    'termination_reason': 'not_executed' if test is None else test['termination_reason']})
        write(self.root/'coverage.json', {'tasks': len(self.counts), 'tests': len(rows), 'rows': rows,
            'tests_with_model_candidates': sum(r['model_candidates'] > 0 for r in rows),
            'tests_not_executed': sum(r['status'] == 'not_executed' for r in rows),
            'correctness_scored': False, 'strict_portable_gpu_gate': False})
        write(self.root/'task-timings.json', {k: r.get('timings', {}) for k, r in self.records.items()})


def write_archive(root, destination, plan):
    """Whitelist diagnostics; never walk model weights or compiler caches into ZIP."""
    root, destination = Path(root), Path(destination)
    require(destination.name == plan['run_id']+'.zip' and not destination.exists(), 'new run-named ZIP required')
    selected = [p for p in root.iterdir() if p.is_file() and p.suffix in {'.json', '.jsonl', '.py'}]
    selected += [p for p in (root/'tools').glob('*.py') if p.is_file()]
    selected += [p for p in (root/'tasks').glob('*/*') if p.name in TASK_FILES and p.is_file()]
    selected += [p for p in (root/'workers').glob('*/*') if p.name in WORKER_FILES and p.is_file()]
    # Bound log retention independently of the on-disk worker logs.
    logs = list((root/'workers').glob('*/*.log')) + list(root.glob('*.log'))
    for p in sorted(logs):
        require(not p.is_symlink(), 'regular worker log required')
        with p.open('rb') as stream:
            stream.seek(max(0, p.stat().st_size-2*1024**2)); body = stream.read()
        target = root/(('parent' if p.parent == root else p.parent.name)+'-'+p.name+'.tail.json')
        write(target, {'original_bytes': p.stat().st_size, 'retained_tail_utf8': body.decode('utf-8', 'replace')})
        selected.append(target)
    members = []
    for path in sorted(set(selected)):
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'regular confined archive path required')
        members.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    require(sum(r['bytes'] for r in members) < ARCHIVE_LIMIT, 'bounded public diagnostics archive required')
    manifest = {'format': FORMAT, 'run_id': plan['run_id'], 'plan_digest': digest(plan), 'members': members,
                'contains_evaluator_truth': False, 'correctness_scored': False}
    temporary = destination.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', canonical(manifest))
        for item in members: archive.write(root/item['path'], item['path'])
    read_archive(temporary, expected_run=plan['run_id'])
    temporary.rename(destination)
    return destination


def read_archive(path, *, expected_run=None):
    with zipfile.ZipFile(path) as archive:
        info = archive.infolist(); names = [r.filename for r in info]
        require(len(names) == len(set(names)) <= 4096 and
            sum(r.file_size for r in info) <= ARCHIVE_LIMIT and
            all(not r.is_dir() and not r.filename.startswith('/') and '\\' not in r.filename and
                '..' not in Path(r.filename).parts and ':' not in r.filename and
                (r.external_attr >> 16) & 0o170000 != 0o120000 for r in info), 'safe bounded ZIP inventory required')
        manifest = parse_json(archive.read('manifest.json'))
        require(manifest['format'] == FORMAT and (expected_run is None or manifest['run_id'] == expected_run),
                'public archive identity differs')
        require(manifest['run_id'] in RUNS.values() and manifest['contains_evaluator_truth'] is False,
                'public truth-free archive required')
        rows = manifest['members']
        require(len(rows) == len({r['path'] for r in rows}) and set(names) == {'manifest.json'}|{r['path'] for r in rows},
                'closed complete manifest required')
        result = {}
        for row in rows:
            body = archive.read(row['path'])
            require(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'],
                    'ZIP member digest differs')
            result[row['path']] = body
        return manifest, result
