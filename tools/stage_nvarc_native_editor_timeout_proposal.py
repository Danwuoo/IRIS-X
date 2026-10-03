"""Inert local 008 timeout repair for review; contains no provider operations."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, sha
from irisx.canonical import digest_value
from tools import stage_nvarc_native_editor as predecessor

RUN = 'nvarc-original-qwen3-native-ttt-008'
AUTHORITY = 'UNAPPROVED local timeout-repair proposal'
CHANGES = {'run_id', 'kernel_id', 'approved', 'owner_decision',
    'maximum_notebook_wall_seconds', 'maximum_child_wall_seconds'}


def plan_for():
    plan = predecessor.plan_for()
    plan.update(run_id=RUN, kernel_id='danielwuu/' + RUN, approved=False,
        owner_decision=AUTHORITY, maximum_notebook_wall_seconds=3600,
        maximum_child_wall_seconds=3000)
    return plan


def notebook(plan, raw):
    candidate = predecessor.notebook(plan, raw)
    source = ''.join(candidate['cells'][0]['source'])
    anchor = "    (work/'editor-archive.py').write_bytes(raw['editor_archive'])"
    predecessor.require(source.count(anchor) == 1, 'exact retained-input proposal guard position required')
    source = source.replace(anchor, anchor + "\n    if plan['approved'] is not True:\n        raise RuntimeError('inert local proposal: new owner approval required before runtime work')")
    compile(source, 'inert-native-editor-timeout-proposal', 'exec')
    candidate['cells'][0]['source'] = source.splitlines(keepends=True)
    return candidate


def stage(package):
    predecessor.require(not package.exists(), 'new immutable local proposal path required')
    plan = plan_for(); raw = predecessor.raw_payloads(plan)
    (package / 'kernel').mkdir(parents=True)
    (package / 'plan.json').write_bytes(raw['plan'])
    atomic(package / 'kernel/notebook.ipynb', notebook(plan, raw))
    atomic(package / 'kernel/kernel-metadata.json', predecessor.metadata(plan))
    atomic(package / 'stage-summary.json', {'run_id': RUN, 'plan_digest': digest_value(plan),
        'approved': False, 'external_actions_authorized': False,
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan = json.loads((package / 'plan.json').read_bytes())
    summary = json.loads((package / 'stage-summary.json').read_bytes())
    predecessor.require(plan == plan_for() and plan['approved'] is False and
        summary['approved'] is False and summary['external_actions_authorized'] is False and
        digest_value(plan) == summary['plan_digest'], 'exact unapproved local proposal required')
    original = predecessor.plan_for(); old_raw = predecessor.raw_payloads(original)
    raw = predecessor.raw_payloads(plan)
    delta = {key for key in plan.keys() | original.keys() if plan.get(key) != original.get(key)}
    predecessor.require(delta == CHANGES and set(raw) == set(old_raw) and
        all(raw[key] == old_raw[key] for key in raw if key != 'plan'),
        'only identity/authority/time bounds may differ; all native payloads must remain byte-identical')
    predecessor.require(summary['inventory'] == {p.relative_to(package).as_posix(): sha(p)
        for p in package.rglob('*') if p.is_file() and p.name != 'stage-summary.json'} and
        json.loads((package / 'kernel/notebook.ipynb').read_bytes()) == notebook(plan, raw) and
        json.loads((package / 'kernel/kernel-metadata.json').read_bytes()) == predecessor.metadata(plan),
        'closed exact inert proposal package required')
    return {'run_id': RUN, 'plan_digest': summary['plan_digest'], 'offline_package_verified': True,
        'inert': True, 'approved': False, 'external_calls': 0, 'provider_operations_available': False,
        'parent_seconds': 3600, 'child_seconds': 3000, 'terminal_reserve_seconds': 120,
        'native_worker_and_material_payloads_byte_identical': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True); args = parser.parse_args()
    print(json.dumps(stage(args.package) if args.action == 'stage' else preflight(args.package)))
