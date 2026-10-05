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
WORKER_FILES = {'ready.json', 'process.json', 'job.json', 'done.json'}


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
                'ground_truth', 'answer_key', 'exact_match', 'official_score'}.intersection(value),
                'evaluator fields forbidden in public predictions')
            for child in value.values(): truth_free(child)
        elif isinstance(value, list):
            for child in value: truth_free(child)
    truth_free(record)
    key = record['binding']['task_id']
    require(record['binding'] == task_binding(plan, challenges, key), 'foreign task/profile checkpoint')
    require(len(record['tests']) == len(challenges[key]['test']), 'all task tests required')
    for index, test in enumerate(record['tests']):
        require(test['test_index'] == index and test['attempts'] == test['ranked_grids'][:2] and
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
