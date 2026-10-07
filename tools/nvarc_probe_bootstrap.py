"""Standard-library-only probe entry and bounded post-stop failure diagnostics.

This never retries a model or qualifies evidence. A fallback ZIP is explicitly
diagnostic-only; an existing runtime ZIP is never changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import sys
import traceback
import zipfile

OUTPUT_FILE = 'coordinator-output.log'
FAILURE_FILE = 'bootstrap-failure.json'
MAX_OUTPUT_BYTES = 64 * 1024


def _write_new(path, value):
    body = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with Path(path).open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())


def _read(path, limit):
    path = Path(path)
    if any(p.is_symlink() for p in path.parents):
        raise RuntimeError('diagnostics cannot follow directory symlinks')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise RuntimeError('bounded regular diagnostic file required: ' + path.name)
        body = stream.read(limit + 1)
        if len(body) != before.st_size:
            raise RuntimeError('diagnostic file size changed: ' + path.name)
        return body


def _truth_free(value):
    if isinstance(value, dict):
        forbidden = {'expected_output', 'expected_outputs', 'evaluator_truth', 'solutions',
            'correct_output', 'correct_outputs', 'exact_match', 'official_score'}
        if forbidden.intersection(value) or any(value.get(key, False) is not False
                for key in ('contains_evaluator_truth', 'correctness_scored')):
            raise RuntimeError('evaluator marker forbidden in diagnostic JSON')
        for child in value.values():
            _truth_free(child)
    elif isinstance(value, list):
        for child in value:
            _truth_free(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    entry = args.root / 'tools/nvarc_e10_probe.py'
    sys.argv = [str(entry), '--root', str(args.root), *remaining]
    try:
        runpy.run_path(str(entry), run_name='__main__')
    except BaseException as error:
        if isinstance(error, SystemExit) and (error.code is None or type(error.code) is int and error.code == 0):
            return 0
        # SystemExit can follow a retained coordinator failure. Do not label
        # every nonzero exit as a startup error or infer a scientific outcome.
        value = {'format': 'irisx/probe-entry-failure-v1', 'run_id': args.root.name,
            'phase': 'supervised-entrypoint', 'outcome': 'failed',
            'type': type(error).__name__, 'message': str(error)[:2400],
            'traceback': ''.join(traceback.format_exception(error))[-12000:],
            'correctness_scored': False, 'promotion': False}
        try:
            _write_new(args.root / FAILURE_FILE, value)
        except BaseException as secondary:
            error.add_note('Failed to retain entry diagnostic: ' + repr(secondary)[:500])
        raise
    return 0


def finalize(root, observation, expected_plan_sha256):
    """Called after supervision, never from a producer or with an active pipe.

    A fallback contains only bounded plans/diagnostics, not reconstructed model
    evidence. An entry failure before the durable coordinator admission marker,
    or an explicit terminal cleanup receipt, is required in addition to stop.
    """
    root = Path(root)
    result = {'diagnostic_only_archive_created': False, 'diagnostic_errors': []}
    destination = root.parent / (root.name + '.zip')
    try:
        _write_new(root / 'outer-supervision.json', observation)
    except BaseException as error:
        result['diagnostic_errors'].append(type(error).__name__ + ': ' + str(error)[:500])
    excerpt = ''
    try:
        body = _read(root / OUTPUT_FILE, MAX_OUTPUT_BYTES)
        excerpt = body[-12000:].decode('utf-8', errors='replace')
    except BaseException as error:
        result['diagnostic_errors'].append(type(error).__name__ + ': ' + str(error)[:500])
    terminal = None
    for name in ('terminal.json', 'terminal-fallback.json'):
        try:
            terminal = json.loads(_read(root / name, 1024 * 1024))
            errors = terminal.get('errors', []) + terminal.get('secondary_errors', [])
            if errors:
                excerpt = json.dumps(errors, ensure_ascii=False)[-12000:]
            break
        except FileNotFoundError:
            continue
        except BaseException as error:
            result['diagnostic_errors'].append(type(error).__name__ + ': ' + str(error)[:500])
    result['coordinator_diagnostic_excerpt'] = excerpt
    result['existing_archive_preserved'] = destination.exists()
    if destination.exists():
        return result
    failed = observation.get('returncode') != 0 or observation.get('timed_out') or not observation.get('confirmed_stopped')
    cleanup = terminal.get('cleanup') if isinstance(terminal, dict) else None
    startup_only = ((root / FAILURE_FILE).is_file() and
        not (root / 'coordinator-admitted.json').exists() and not (root / 'workers').exists())
    stopped = (startup_only or
        isinstance(cleanup, dict) and cleanup.get('all_producers_stopped') is True)
    if not failed or observation.get('confirmed_stopped') is not True or not stopped:
        result['fallback_refused'] = 'failure and confirmed coordinator/producer stop required'
        return result
    try:
        screen = _read(root / 'screen.json', 8 * 1024 * 1024)
        if hashlib.sha256(screen).hexdigest() != expected_plan_sha256 or json.loads(screen)['screen_id'] != root.name:
            raise RuntimeError('exact immutable probe screen required for diagnostic ZIP')
        members = {'screen.json': screen}
        for name, limit in ((FAILURE_FILE, 32 * 1024), ('outer-supervision.json', 16 * 1024),
                (OUTPUT_FILE, MAX_OUTPUT_BYTES), ('terminal.json', 1024 * 1024),
                ('terminal-fallback.json', 1024 * 1024), ('dependency-readproof-receipt.json', 16 * 1024)):
            try:
                body = _read(root / name, limit)
                if name.endswith('.json'):
                    _truth_free(json.loads(body))
                members[name] = body
            except FileNotFoundError:
                pass
            except (OSError, ValueError, RuntimeError) as error:
                result['diagnostic_errors'].append(name + ': ' + str(error)[:500])
        members['diagnostic-only.json'] = json.dumps({
            'format': 'irisx/probe-diagnostic-only-v1', 'run_id': root.name,
            'outcome': 'failed', 'complete_runtime_evidence': False,
            'candidate_qualification': False, 'promotion': False,
            'reason': 'no finalized runtime archive; bounded post-stop diagnostics only'},
            sort_keys=True, separators=(',', ':')).encode()
        temporary = destination.with_suffix('.diagnostic.zip.tmp')
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in sorted(members.items()):
                archive.writestr(name, body)
        # Hard-link is a no-replace publication; never replace an existing ZIP.
        os.link(temporary, destination)
        temporary.unlink()
        result['diagnostic_only_archive_created'] = True
    except BaseException as error:
        result['diagnostic_errors'].append(type(error).__name__ + ': ' + str(error)[:500])
    return result


if __name__ == '__main__':
    raise SystemExit(main())
