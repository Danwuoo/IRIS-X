"""Trusted, data-only materialization. Never called by the model/generation role.

Only published pinned evaluation files are read. No answers are printed, copied
to source code, or put in the solver asset. Original bytes remain evaluator-only.
"""
from __future__ import annotations

import argparse
import base64
import subprocess
from pathlib import Path
import sys

if __package__ in (None, ''):
    _root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(_root), str(_root / 'src')]

from tools.arc_offline_evaluation import load_pinned_reference, content_identity
from tools.arc_kaggle_submission import parse_json, require
from tools.arc_public_research_20261010.public_data import (
    COMMIT, REPOSITORY, PROVENANCE_SHA256, LICENSE_SHA256, EXPOSURE,
    SOLVER_FORMAT, EVALUATOR_FORMAT, read_regular, write_new, inventory,
    separated, safe_path, sha256, load_solver_tasks, canonical, verify_upstream_inventory, git_object_sha)

NOTICE = ('ARC-AGI-2 public evaluation tasks, arcprize/ARC-AGI-2, commit ' + COMMIT +
          '. Original source is Apache-2.0; LICENSE is retained. Solver projection removes '
          'only test outputs. Evaluator retains original source bytes. '
          'Public development data with known project exposure, not a fresh holdout.\n')


def _write_assets(source_root, provenance_path, output_root, challenges, reference, *, evidence_mode, upstream_inventory=None):
    """Internal data-only writer. Synthetic fixtures explicitly carry their mode."""
    source_root, output_root = separated(source_root, output_root)
    require(not output_root.exists(), 'new data-build identity required')
    if evidence_mode == 'public-development':
        official_files = verify_upstream_inventory(upstream_inventory)
    else:
        require(evidence_mode == 'synthetic-test-only', 'explicit materialization role required')
        official_files = None
        upstream_inventory = {'format': 'irisx/synthetic-fixture-inventory-v1', 'complete_official_pinned_set': False}
    source = {'repository': REPOSITORY, 'commit': COMMIT,
              'provenance_sha256': sha256(read_regular(provenance_path)),
              'license_sha256': sha256(read_regular(source_root / 'LICENSE')),
              'evaluation_inventory_sha256': sha256(canonical(upstream_inventory) + b'\n')}
    identity = content_identity(challenges)
    require(identity['tasks'] == 120 and identity['tests'] == 167, 'complete PUBLIC120 shape required')
    solver, evaluator = output_root / 'solver', output_root / 'evaluator'
    solver.mkdir(parents=True); evaluator.mkdir()
    for role_root in (solver, evaluator):
        write_new(role_root / 'LICENSE', read_regular(source_root / 'LICENSE'), raw=True)
        write_new(role_root / 'NOTICE', NOTICE.encode(), raw=True)
    write_new(solver / 'public-challenges.json', challenges)
    write_new(evaluator / 'provenance.json', read_regular(provenance_path), raw=True)
    write_new(evaluator / 'upstream-inventory.json', upstream_inventory)
    provenance = parse_json(read_regular(provenance_path))['payload']
    rows = sorted((r for r in provenance['files'] if r['path'].startswith('data/evaluation/')),
                  key=lambda row: row['path'])
    require(len(rows) == 120 and len({r['path'] for r in rows}) == 120, 'complete unique source inventory required')
    if official_files is not None:
        require({r['path'] for r in rows} == set(official_files), 'provenance is not the complete official evaluation tree')
    for row in rows:
        name = row['path']
        require(name.count('/') == 2 and name.startswith('data/evaluation/') and name.endswith('.json')
                and Path(name).stem in challenges, 'evaluation source member required')
        raw = read_regular(source_root / name, row['content_digest'].removeprefix('sha256:'))
        require(len(raw) == row['byte_size'], 'source size differs')
        if official_files is not None:
            require(git_object_sha('blob', raw) == official_files[name], 'source differs from official Git blob')
        write_new(evaluator / 'upstream' / name, raw, raw=True)
    bindings = {}
    for role, role_root, format_id in (('solver', solver, SOLVER_FORMAT), ('evaluator', evaluator, EVALUATOR_FORMAT)):
        manifest = {'format': format_id, 'profile': 'PUBLIC120', 'evidence_mode': evidence_mode,
                    'source': source, 'identity': identity, 'files': inventory(role_root),
                    'exposure': EXPOSURE, 'complete_official_pinned_set': evidence_mode == 'public-development',
                    'projection_notice': NOTICE.strip()}
        bindings[role + '_manifest_sha256'] = write_new(role_root / 'manifest.json', manifest)['sha256']
    load_solver_tasks(solver, bindings['solver_manifest_sha256'])
    return {'profile': 'PUBLIC120', 'tasks': 120, 'queries': 167,
            'source_commit': COMMIT, 'evidence_mode': evidence_mode,
            'complete_official_pinned_set': evidence_mode == 'public-development',
            'challenges_digest': reference['challenges_digest'], **bindings,
            'solver_root': str(solver), 'evaluator_root': str(evaluator),
            'raw_answers_printed': False, 'scoring_performed': False}


def _git_inventory(source_root):
    def read(kind, name):
        result = subprocess.run(['git', '-C', str(source_root), 'cat-file', kind, name],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        require(len(result.stdout) < 256 * 1024, 'bounded Git metadata required')
        return result.stdout
    objects = {'commit': read('commit', COMMIT), 'root': read('tree', COMMIT + '^{tree}'),
               'data': read('tree', COMMIT + ':data'), 'evaluation': read('tree', COMMIT + ':data/evaluation')}
    from tools.arc_public_research_20261010.public_data import _git_tree
    value = {'format': 'irisx/pinned-public-evaluation-git-inventory-v1', 'commit': COMMIT,
             'objects': {key: base64.b64encode(raw).decode('ascii') for key, raw in objects.items()},
             'files': {'data/evaluation/' + name: row['sha1'] for name, row in _git_tree(objects['evaluation']).items()}}
    verify_upstream_inventory(value)
    return value


def prepare_public_assets(source_root, provenance_path, output_root):
    """Verify retained provenance, all 120 original files, exact counts and license."""
    source_root, output_root = separated(source_root, output_root)
    safe_path(provenance_path)
    read_regular(provenance_path, PROVENANCE_SHA256)
    read_regular(source_root / 'LICENSE', LICENSE_SHA256)
    upstream_inventory = _git_inventory(source_root)
    # Existing evaluator API validates task schemas and every original file hash.
    challenges, answers, reference = load_pinned_reference(source_root, provenance_path)
    del answers  # No scoring, summary, content logging, or answer-dependent selection.
    return _write_assets(source_root, provenance_path, output_root, challenges, reference,
                         evidence_mode='public-development', upstream_inventory=upstream_inventory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--provenance', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    result = prepare_public_assets(Path(args.source_root), Path(args.provenance), Path(args.output_root))
    from tools.arc_public_research_20261010.public_data import canonical
    sys.stdout.buffer.write(canonical(result) + b'\n')


if __name__ == '__main__':
    main()
