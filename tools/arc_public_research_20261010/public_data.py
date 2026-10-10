"""Truth-free PUBLIC120 asset loading; no evaluator files are opened here.

Manifest hashes are external pins, not secrets. This is a trusted-dataflow
boundary, not filesystem secrecy against another process running as this UID.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

from tools.arc_kaggle_submission import challenge_counts, parse_json, require
from tools.arc_offline_evaluation import content_identity

REPOSITORY = 'https://github.com/arcprize/ARC-AGI-2.git'
COMMIT = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'
PROVENANCE_SHA256 = 'f581e41ccb10f2def2c8ff438619ec51e3fb9c2d42b17900e5e49e30e9cda1e5'
LICENSE_SHA256 = '8360699be7ffadd4b460e4287c1f7d0ada282518ee8e375fff603b1b3ecbb43f'
SOLVER_FORMAT = 'irisx/public120-solver-asset-v1'
EVALUATOR_FORMAT = 'irisx/public120-evaluator-asset-v1'
POLICIES = ('raw', 'strict', 'uniform', 'shape')
EXPOSURE = {'project_public_evaluation_exposure': 'known', 'model_pretraining_exposure': 'unknown',
            'fresh_holdout': False}
MAX_FILE_BYTES = 16 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def hash_value(value):
    return sha256(canonical(value))


def hash_string(value):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), 'exact SHA-256 required')
    return value


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute path without traversal required')
    for part in (*reversed(path.parents), path):
        require(not part.is_symlink(), 'symlink path prohibited')
    return path


def separated(*paths):
    paths = [safe_path(p) for p in paths]
    for i, left in enumerate(paths):
        for right in paths[i + 1:]:
            require(left != right and left not in right.parents and right not in left.parents,
                    'source, solver, evaluator, and output paths must be disjoint')
    return paths


def read_regular(path, expected=None, limit=MAX_FILE_BYTES):
    path = safe_path(path)
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= limit,
            'bounded regular file required: ' + path.name)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and len(raw) <= limit and
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'file changed while reading')
    finally:
        os.close(fd)
    if expected is not None:
        require(sha256(raw) == hash_string(expected), 'bound file digest differs: ' + path.name)
    return raw


def write_new(path, value, *, raw=False):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = value if raw else canonical(value) + b'\n'
    require(type(body) is bytes, 'bytes required')
    partial = path.with_name(path.name + '.partial')
    require(not path.exists() and not partial.exists(), 'immutable output identity consumed')
    with partial.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    os.rename(partial, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'sha256': sha256(body), 'bytes': len(body)}


def inventory(root, *, exclude=()):
    root = safe_path(root)
    require(root.is_dir(), 'asset directory required')
    output = {}
    for path in sorted(root.rglob('*')):
        safe_path(path)
        if path.is_dir():
            continue
        name = path.relative_to(root).as_posix()
        require(not name.endswith(('.partial', '.lock')), 'interrupted artifact prohibited')
        if name in exclude:
            continue
        raw = read_regular(path)
        output[name] = {'sha256': sha256(raw), 'bytes': len(raw)}
    return output


def verify_inventory(root, expected, *, exclude=()):
    require(type(expected) is dict and expected, 'nonempty closed inventory required')
    for name, row in expected.items():
        require(type(name) is str and not PurePosixPath(name).is_absolute() and '\\' not in name
                and all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe inventory member')
        require(type(row) is dict and set(row) == {'sha256', 'bytes'} and
                type(row['bytes']) is int and 0 <= row['bytes'] <= MAX_FILE_BYTES, 'file binding schema differs')
        hash_string(row['sha256'])
    require(inventory(root, exclude=exclude) == expected, 'closed inventory changed, missing, or extra')


def validate_manifest(value, *, role):
    require(type(value) is dict and set(value) == {'format', 'profile', 'evidence_mode', 'source',
            'identity', 'files', 'exposure', 'complete_official_pinned_set', 'projection_notice'},
            'public asset manifest schema differs')
    require(value['format'] == (SOLVER_FORMAT if role == 'solver' else EVALUATOR_FORMAT), 'asset role differs')
    require(value['profile'] == 'PUBLIC120' and value['evidence_mode'] in ('public-development', 'synthetic-test-only'),
            'PUBLIC120 profile required')
    require(type(value['source']) is dict and set(value['source']) == {'repository', 'commit',
            'provenance_sha256', 'license_sha256', 'evaluation_inventory_sha256'}, 'source binding schema differs')
    hash_string(value['source']['evaluation_inventory_sha256'])
    require({k: v for k, v in value['source'].items() if k != 'evaluation_inventory_sha256'} ==
            {'repository': REPOSITORY, 'commit': COMMIT, 'provenance_sha256': PROVENANCE_SHA256,
             'license_sha256': LICENSE_SHA256} or value['evidence_mode'] == 'synthetic-test-only',
            'canonical public source pin differs')
    require(value['identity']['tasks'] == 120 and value['identity']['tests'] == 167,
            'canonical 120-task/167-query denominator required')
    require(value['exposure'] == EXPOSURE and
            value['complete_official_pinned_set'] is (value['evidence_mode'] == 'public-development'),
            'source completeness/exposure labels differ')
    require(type(value['projection_notice']) is str and value['projection_notice'], 'projection attribution required')
    return value


def load_solver_tasks(root, manifest_sha256):
    """Validate every solver byte and return demo-only tasks plus separate inputs."""
    root = safe_path(root)
    manifest = validate_manifest(parse_json(read_regular(root / 'manifest.json', manifest_sha256)), role='solver')
    require(set(manifest['files']) == {'public-challenges.json', 'LICENSE', 'NOTICE'}, 'solver asset file roles differ')
    verify_inventory(root, manifest['files'], exclude=('manifest.json',))
    challenges = parse_json(read_regular(root / 'public-challenges.json', manifest['files']['public-challenges.json']['sha256']))
    counts = challenge_counts(challenges)
    identity = content_identity(challenges)
    require(identity == manifest['identity'] and len(counts) == 120 and sum(counts.values()) == 167,
            'challenge identities or denominator differ')
    require(sha256(read_regular(root / 'LICENSE')) == manifest['source']['license_sha256'], 'license binding differs')
    demos = {key: {'task_id': key, 'demos': task['train']} for key, task in sorted(challenges.items())}
    inputs = {key: [pair['input'] for pair in task['test']] for key, task in sorted(challenges.items())}
    # Separate copies prevent a consumer from mutating another projection by alias.
    return parse_json(canonical({'manifest': manifest, 'manifest_sha256': manifest_sha256,
        'challenges': challenges, 'demos_tasks': demos, 'query_inputs': inputs, 'identity': identity}))


def git_object_sha(kind, raw):
    return hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def _git_tree(raw):
    rows, pos = {}, 0
    while pos < len(raw):
        end = raw.index(b' ', pos); mode = raw[pos:end].decode('ascii'); pos = end + 1
        end = raw.index(b'\0', pos); name = raw[pos:end].decode('utf-8'); pos = end + 1
        require(name not in rows and '/' not in name and name not in ('', '.', '..') and
                pos + 20 <= len(raw), 'invalid/duplicate Git tree entry')
        rows[name] = {'mode': mode, 'sha1': raw[pos:pos + 20].hex()}; pos += 20
    return rows


def verify_upstream_inventory(value):
    """Verify Git's content-addressed commit/tree chain without reading answers."""
    import base64
    require(type(value) is dict and set(value) == {'format', 'commit', 'objects', 'files'} and
            value['format'] == 'irisx/pinned-public-evaluation-git-inventory-v1' and value['commit'] == COMMIT,
            'authoritative pinned Git inventory required')
    require(type(value['objects']) is dict and set(value['objects']) == {'commit', 'root', 'data', 'evaluation'},
            'complete commit/tree chain required')
    raw = {key: base64.b64decode(encoded, validate=True) for key, encoded in value['objects'].items()}
    require(git_object_sha('commit', raw['commit']) == COMMIT, 'pinned commit object differs')
    first = raw['commit'].split(b'\n', 1)[0]
    require(first.startswith(b'tree ') and len(first) == 45, 'commit tree required')
    require(git_object_sha('tree', raw['root']) == first[5:].decode('ascii'), 'root tree differs')
    root = _git_tree(raw['root']); data_tree = _git_tree(raw['data']); evaluation = _git_tree(raw['evaluation'])
    require(root['data']['mode'] == '40000' and git_object_sha('tree', raw['data']) == root['data']['sha1'] and
            data_tree['evaluation']['mode'] == '40000' and
            git_object_sha('tree', raw['evaluation']) == data_tree['evaluation']['sha1'], 'evaluation tree chain differs')
    require(len(evaluation) == 120 and all(row['mode'] == '100644' and name.endswith('.json') for name, row in evaluation.items()),
            'entire authoritative evaluation tree must contain exactly 120 regular JSON tasks')
    expected = {'data/evaluation/' + name: row['sha1'] for name, row in evaluation.items()}
    require(value['files'] == expected, 'complete official filename/blob inventory differs')
    return expected
