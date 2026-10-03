"""Decision 0056: exact approved envelope for the reviewed 008 timeout repair."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, read, sha
from irisx.canonical import digest_value
from tools import stage_nvarc_native_editor_timeout_proposal as proposal

RUN = proposal.RUN
AUTHORITY = 'Decision 0056'
PROPOSAL = ROOT / '.irisx/nvarc-original/runs' / RUN / 'proposal-001'
PROPOSAL_DIGEST = 'sha256:ccc7640aeecf42bacaaf671b9bc384d9c47bc470dd1b0986452c5e6e8449dc66'
require = proposal.predecessor.require


def plan_for():
    checked = proposal.preflight(PROPOSAL)
    require(checked['plan_digest'] == PROPOSAL_DIGEST and checked['approved'] is False,
        'exact retained reviewed 008 proposal required')
    plan = read(PROPOSAL / 'plan.json')
    plan.update(approved=True, owner_decision=AUTHORITY, approved_proposal_plan_digest=PROPOSAL_DIGEST)
    return plan


def raw_payloads(plan):
    raw = proposal.predecessor.raw_payloads(plan)
    source = raw['worker'].decode('utf-8')
    anchor = "plan['owner_decision']=='Decision 0055'"
    require(source.count(anchor) == 1, 'exact 007 worker approval guard required')
    source = source.replace(anchor, "plan['owner_decision']=='Decision 0056'")
    compile(source, 'approved-native-008-worker', 'exec')
    raw['worker'] = source.encode()
    return raw


def stage(package):
    require(not package.exists(), 'new immutable approved 008 package required')
    plan = plan_for(); raw = raw_payloads(plan)
    (package / 'kernel').mkdir(parents=True)
    (package / 'plan.json').write_bytes(raw['plan'])
    atomic(package / 'kernel/notebook.ipynb', proposal.notebook(plan, raw))
    atomic(package / 'kernel/kernel-metadata.json', proposal.predecessor.metadata(plan))
    atomic(package / 'stage-summary.json', {'run_id': RUN, 'plan_digest': digest_value(plan),
        'approved_proposal_plan_digest': PROPOSAL_DIGEST,
        'payload_sha256': {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan = read(package / 'plan.json'); summary = read(package / 'stage-summary.json')
    require(plan == plan_for() and digest_value(plan) == summary['plan_digest'] and
        summary['approved_proposal_plan_digest'] == PROPOSAL_DIGEST,
        'exact owner-approved 008 timeout envelope required')
    original = read(PROPOSAL / 'plan.json')
    require({key for key in plan.keys() | original.keys() if plan.get(key) != original.get(key)} ==
        {'approved', 'owner_decision', 'approved_proposal_plan_digest'},
        'only the reviewed proposal approval envelope may differ')
    raw = raw_payloads(plan); old_raw = proposal.predecessor.raw_payloads(original)
    require(set(raw) == set(old_raw) and all(raw[key] == old_raw[key] for key in raw
        if key not in {'plan', 'worker'}) and raw['worker'] == old_raw['worker'].replace(
            b"plan['owner_decision']=='Decision 0055'", b"plan['owner_decision']=='Decision 0056'"),
        'native workload/material bytes must remain unchanged except the exact owner-decision guard')
    require(summary['inventory'] == {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*')
        if p.is_file() and p.name != 'stage-summary.json'} and
        read(package / 'kernel/notebook.ipynb') == proposal.notebook(plan, raw) and
        read(package / 'kernel/kernel-metadata.json') == proposal.predecessor.metadata(plan) and
        summary['payload_sha256'] == {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'closed exact approved 008 source/material/download package required')
    return {'run_id': RUN, 'owner_decision': AUTHORITY, 'plan_digest': summary['plan_digest'],
        'offline_package_verified': True, 'external_calls': 0, 'execution_type': 'QUICK_SAVE',
        'owner_editor_only': True, 'maximum_notebook_wall_seconds': 3600,
        'maximum_child_wall_seconds': 3000, 'maximum_optimizer_steps': 128,
        'source_input_tokens': 955392, 'download_archive': '結果.zip',
        'approved_proposal_plan_digest': PROPOSAL_DIGEST}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True); args = parser.parse_args()
    print(json.dumps(stage(args.package) if args.action == 'stage' else preflight(args.package), ensure_ascii=True))
