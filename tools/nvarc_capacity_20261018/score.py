"""Separate protected CPU scoring for immutable three-arm capacity predictions.

This command never generates predictions, changes development selection or
manufactures provider receipts. Supply a genuinely externally reconciled exact
notebook/version terminal record and its independently retained SHA256. All
source, both process closures, checkpoint and prediction bindings are checked
BEFORE the first evaluator file is opened. Incomplete recipes may receive only
explicitly partial, full-denominator post-hoc diagnostics, never a completed
scored comparison. No provider signature or hidden/official accuracy is claimed.

CLI (paths are retained local artifacts, not downloads performed here)::

    python -I EXACT_SOURCE/tools/nvarc_capacity_20261018/score.py \
      --attempt-root RETRIEVED_ATTEMPT --source-root EXACT_SOURCE \
      --public-challenges PINNED_SOLVER/public-challenges.json \
      --evaluator-root PROTECTED_EVALUATOR \
      --terminal-evidence EXTERNAL_TERMINAL.json --terminal-sha256 SHA256 \
      --notebook-id NOTEBOOK_ID --version EXACT_VERSION --output NEW_OUTPUT

The terminal JSON schema is TERMINAL_KEYS below. `prediction_seals` and
`pools_sha256` map all three treatment names to their exact file SHA256 values.
`source_capsule_manifest_sha256` is the uploaded capsule manifest pin in the
bootstrap handoff; `source_identity` is the distinct canonical runtime Python
source-snapshot identity. The receipt must come from actual external provider
readback, not the worker/controller/bootstrap, and is an observer attestation,
not a cryptographic provider signature. This module has no receipt constructor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

# Explicit script use works under -I without an installed project or ambient PYTHONPATH.
# Only this reviewed file's repository root is admitted before source verification.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.nvarc_capacity_20261018'

from tools.arc2_goal_sprint_20261017.data import canonical, digest
from tools.arc2_goal_sprint_20261017.launch import (
    EVALUATOR_MANIFEST_SHA256, SCORER_SHA256, SOLVER_MANIFEST_SHA256,
    regular, require, sha, verify_inventory, write_new,
)
from tools.nvarc_posttrain_20261017.score import closure_structure, validate_pool_inventory
from .controller import source_identity, verify_source
from .public import TREATMENTS, validate_solver_payload, verify_public_artifacts

FORMAT = 'irisx/capacity-public-evaluation-v1'
TERMINAL_FORMAT = 'irisx/capacity-provider-terminal-v1'
TERMINAL_KEYS = {'format', 'provider', 'notebook_id', 'version', 'status', 'run_id', 'manual_session_id',
    'verified_terminal_epoch', 'source_verified', 'outputs_verified', 'evidence_origin',
    'source_capsule_manifest_sha256', 'source_identity', 'closed_result_sha256', 'handoff_sha256',
    'isolation_sha256', 'prediction_seals', 'pools_sha256'}
TERMINAL_STATES = {'COMPLETE', 'ERROR', 'CANCELLED', 'CANCEL_ACKNOWLEDGED'}
MAX_JSON_BYTES = 64 * 1024**2
MAX_TOTAL_BYTES = 2 * 1024**3


def _is_sha(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def _json(path):
    path = regular(path)
    require(path.stat().st_size <= MAX_JSON_BYTES, 'bounded regular evidence JSON required')
    return json.loads(path.read_bytes())


def _artifact(root, relative, entry):
    require(type(relative) is str and relative and not Path(relative).is_absolute()
            and '..' not in Path(relative).parts, 'safe relative evidence path required')
    require(type(entry) is dict and type(entry.get('bytes')) is int and 0 <= entry['bytes'] <= MAX_TOTAL_BYTES
            and _is_sha(entry.get('sha256')), 'bounded exact artifact byte/hash pin required')
    path = regular(Path(root) / relative)
    require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'bound evidence bytes or SHA differ')
    return path


def _closed(proof):
    # These PIDs belong to the original provider host. Inspecting evaluator
    # /proc would be meaningless (and can collide with unrelated local PIDs).
    # Fresh source-side checks were performed by controller/bootstrap; the
    # independently reconciled terminal record now binds those exact proofs.
    expected = {'format', 'root_identity', 'scope', 'ownership_complete', 'closed',
                'owned_identities', 'remaining', 'returncode', 'worker_returncode',
                'forced', 'reaped_identities', 'errors'}
    require(type(proof) is dict and set(proof) == expected and type(proof['forced']) is bool,
            'exact source-side owned-process closure proof schema required')
    closure_structure(proof)
    require(all(row['pid'] > 0 and bool(row['state']) for row in proof['owned_identities']),
            'positive source-side process incarnations required')
    reaped = proof['reaped_identities']
    require(type(reaped) is list and all(type(row) is dict and row in proof['owned_identities'] for row in reaped)
            and len({(row['pid'], row['birth']) for row in reaped}) == len(reaped),
            'exact source-side reaped incarnation subset required')
    return proof['returncode'] == proof['worker_returncode'] == 0 and not proof['forced']


def verify_terminal(attempt_root, terminal_path, terminal_sha256, *, notebook_id, version, source_root, public_path):
    """Answer-free admission, preserving distinct capsule and runtime identities."""
    require(type(notebook_id) is int and notebook_id > 0 and type(version) is int and version > 0,
            'independently reconciled exact positive notebook ID/version required')
    require(_is_sha(terminal_sha256) and sha(regular(terminal_path)) == terminal_sha256,
            'independently retained external terminal SHA differs')
    terminal = _json(terminal_path)
    require(type(terminal) is dict and set(terminal) == TERMINAL_KEYS and terminal['format'] == TERMINAL_FORMAT
            and terminal['provider'] == 'kaggle' and terminal['evidence_origin'] == 'external-provider-readback'
            and type(terminal['notebook_id']) is int and terminal['notebook_id'] == notebook_id
            and type(terminal['version']) is int and terminal['version'] == version
            and terminal['status'] in TERMINAL_STATES and terminal['source_verified'] is True
            and terminal['outputs_verified'] is True
            and all(type(terminal[key]) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}', terminal[key])
                    for key in ('run_id', 'manual_session_id')), 'exact external provider terminal/source/output readback required')
    require(all(_is_sha(terminal[key]) for key in ('source_capsule_manifest_sha256', 'source_identity',
            'closed_result_sha256', 'handoff_sha256', 'isolation_sha256'))
            and all(type(terminal[key]) is dict and set(terminal[key]) == set(TREATMENTS)
                    and all(_is_sha(v) for v in terminal[key].values()) for key in ('prediction_seals', 'pools_sha256')),
            'complete distinct source/closure/three-arm terminal hash bindings required')
    stamp = terminal['verified_terminal_epoch']
    require(type(stamp) in (int, float) and math.isfinite(stamp) and 0 < stamp <= time.time(),
            'finite observed external terminal epoch required')
    attempt = Path(attempt_root).absolute(); root = attempt / 'solver'
    handoff_path = attempt / 'control/external-evaluator-handoff.json'
    require(sha(regular(handoff_path)) == terminal['handoff_sha256'], 'external handoff changed')
    handoff = _json(handoff_path)
    require(handoff.get('format') == 'irisx/capacity-external-evaluator-handoff-v1'
            and handoff.get('source_manifest_sha256') == terminal['source_capsule_manifest_sha256']
            and handoff.get('source_capsule_manifest_sha256') == terminal['source_capsule_manifest_sha256']
            and handoff.get('source_identity') == terminal['source_identity']
            and handoff.get('run_id') == terminal['run_id'] and handoff.get('manual_session_id') == terminal['manual_session_id']
            and handoff.get('closed_result_sha256') == terminal['closed_result_sha256']
            and handoff.get('original_scorer_sha256') == SCORER_SHA256
            and handoff.get('generation_may_resume') is False and handoff.get('provider_terminal_verified') is False
            and handoff.get('public_scoring_performed') is False and handoff.get('scorer_dispatched') is False
            and handoff.get('inherited_exposure_qualified') is True
            and handoff.get('clean_generalization_claimed') is False,
            'genuine capacity bootstrap handoff with unchanged scorer and explicit non-provider status required')
    outer_path = regular(attempt / 'control/owner-closure.json')
    require(sha(outer_path) == handoff['outer_owner_closure_sha256'], 'outer ownership closure hash differs')
    outer_proof = _json(outer_path)
    outer_normal = _closed(outer_proof)
    isolation_path = regular(attempt / 'isolation.json')
    require(sha(isolation_path) == terminal['isolation_sha256'], 'externally bound solver-isolation evidence differs')
    isolation = _json(isolation_path)
    from tools.nvarc_capacity_20261018.isolation import validate_receipt
    validate_receipt(isolation)
    closed_path = regular(root / 'closed-result.json')
    require(sha(closed_path) == terminal['closed_result_sha256'], 'externally bound closed controller result changed')
    closed = _json(closed_path)
    require(closed.get('format') == 'irisx/nvarc-capacity-local-closure-v1'
            and closed.get('source_identity') == terminal['source_identity']
            and closed.get('comparison_complete') is True and closed.get('public_diagnostics_requested') is True
            and closed.get('public_scoring_performed') is False and closed.get('provider_execution_claimed') is False
            and closed.get('closure', {}).get('closed') is True,
            'complete frozen development comparison and closed answer-free PUBLIC output required')
    worker_proof = closed['closure']['proof']; worker_normal = _closed(worker_proof)
    require(worker_proof['root_identity'] != outer_proof['root_identity'],
            'distinct source-side worker and outer controller closure identities required')
    snapshot_path = regular(root / 'source-manifest.json'); snapshot = _json(snapshot_path)
    require(source_identity(snapshot) == terminal['source_identity'], 'runtime source snapshot identity differs')
    verify_source(source_root, snapshot, terminal['source_identity'])
    require(sha(regular(Path(source_root) / 'tools/arc_offline_evaluation.py')) == SCORER_SHA256,
            'unchanged original scorer source required')
    require(type(closed.get('artifacts')) is dict and bool(closed['artifacts']), 'complete closed worker artifact inventory required')
    total = 0
    for name, entry in closed['artifacts'].items():
        _artifact(root, name, entry); total += entry['bytes']
    require(total <= MAX_TOTAL_BYTES and total == closed.get('total_artifact_bytes'), 'closed artifact total differs')
    actual_worker_files = {p.relative_to(root).as_posix() for p in (root / 'worker').rglob('*') if p.is_file()}
    require(actual_worker_files == set(closed['artifacts']), 'closed worker inventory changed or incomplete')
    frozen_path = root / 'worker/frozen-selection.json'; frozen = _json(frozen_path)
    comparison_path = root / 'worker/comparison/report.json'; comparison = _json(comparison_path)
    require(sha(regular(comparison_path)) == frozen['comparison_report_sha256']
            and comparison.get('complete') is True and comparison.get('source_identity') == terminal['source_identity']
            and comparison.get('protocol_sha256') == frozen['protocol_sha256']
            and comparison.get('selected_treatment') == frozen['selected_treatment'] == closed['selected_treatment']
            and frozen['source_identity'] == terminal['source_identity'], 'frozen development selection changed')
    require(set(closed.get('prediction_seals', {})) == set(TREATMENTS), 'all three immutable prediction seals required')
    verify_inventory(Path(public_path).parent, SOLVER_MANIFEST_SHA256)
    public = _json(public_path); validate_solver_payload(public)
    source_manifest_file_sha = sha(snapshot_path)
    pools, verifications, seals, pool_paths = {}, {}, {}, {}
    for treatment in TREATMENTS:
        entry = closed['prediction_seals'][treatment]
        relative = 'prediction-seals/' + treatment + '.json'
        require(entry.get('path') == relative and entry['sha256'] == terminal['prediction_seals'][treatment]
                and handoff.get('prediction_seals', {}).get(treatment) == {key: entry[key] for key in ('path', 'bytes', 'sha256')},
                'exact per-arm external seal binding required')
        seal_path = _artifact(root, relative, entry); seal = _json(seal_path)
        body = {k: v for k, v in seal.items() if k != 'seal_sha256'}
        require(seal.get('format') == 'irisx/capacity-local-prediction-seal-v1' and seal.get('treatment') == treatment
                and seal.get('seal_sha256') == hashlib.sha256(canonical(body)).hexdigest() == entry['seal_sha256']
                and seal.get('source_identity') == terminal['source_identity']
                and seal.get('source_manifest_sha256') == source_manifest_file_sha
                and seal.get('worker_closure_proof') == worker_proof
                and seal.get('worker_closure_sha256') == hashlib.sha256(canonical(worker_proof)).hexdigest()
                and seal.get('frozen_selection') == frozen
                and seal.get('frozen_selection_file_sha256') == sha(regular(frozen_path))
                and seal.get('comparison_report_sha256') == frozen['comparison_report_sha256'],
                'seal source/process/frozen-selection identities differ')
        sealed_epoch = seal.get('sealed_epoch')
        started, deadline = seal.get('original_started_epoch'), seal.get('original_session_deadline_epoch')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (sealed_epoch, started, deadline))
                and 0 < started <= sealed_epoch <= stamp and deadline == started + 43200,
                'original session/seal/external-terminal chronology required')
        require(seal.get('full_requested_tasks') == 120 and seal.get('full_requested_queries') == 167
                and seal.get('requested_views_per_query') == 2 and seal.get('public_scoring_performed') is False
                and seal.get('provider_terminal_verified') is False
                and seal.get('legacy_scorer_compatibility_claimed') is False,
                'full120/167 two-view distinct capacity seal required')
        arm_root = root / 'worker/public' / treatment
        expected_files = {p.relative_to(root).as_posix() for p in arm_root.iterdir() if p.is_file()}
        require(type(seal.get('files')) is dict and set(seal['files']) == expected_files,
                'sealed arm file inventory differs')
        for name, item in seal['files'].items():
            require(name.startswith('worker/public/' + treatment + '/') and closed['artifacts'].get(name) == item,
                    'per-arm/closed artifact binding differs')
            _artifact(root, name, item)
        checkpoint = comparison['treatments'][treatment]['checkpoint']
        pin = {key: checkpoint[key] for key in ('root', 'manifest_sha256', 'state_sha256')}
        require(seal.get('checkpoint_pin') == pin, 'sealed trained checkpoint identity differs')
        verified = verify_public_artifacts(arm_root, solver_payload=public, frozen_selection=frozen,
            checkpoint_pin=pin, treatment=treatment, checkpoint_root=root / 'worker/comparison/checkpoints' / treatment)
        require(seal.get('verification') == verified and seal.get('complete') == entry.get('complete') == verified['complete']
                and seal.get('completed_views') == verified['completed_views'], 'sealed independent reconstruction differs')
        pool_path = regular(arm_root / 'pools.json')
        require(sha(pool_path) == terminal['pools_sha256'][treatment], 'externally reconciled prediction pool changed')
        pool = _json(pool_path); validate_pool_inventory(pool)
        pools[treatment], verifications[treatment], seals[treatment], pool_paths[treatment] = pool, verified, seal, pool_path
    complete = (all(v['complete'] and v['completed_views'] == 334 for v in verifications.values())
                and closed.get('complete') is True and handoff.get('complete') is True
                and outer_normal and worker_normal and terminal['status'] == 'COMPLETE')
    return {'terminal': terminal, 'terminal_sha256': terminal_sha256, 'public': public, 'pools': pools,
        'pool_paths': pool_paths, 'verifications': verifications, 'seals': seals, 'frozen_selection': frozen,
        'source_manifest_file_sha256': source_manifest_file_sha, 'complete': complete,
        'closed_result_path': closed_path, 'handoff_path': handoff_path}


def score(attempt_root, evaluator_root, public_path, source_root, terminal_path, terminal_sha256,
          *, notebook_id, version, output):
    """Use unchanged actual scorer for all3×120/167; answers stay evaluator-side."""
    admitted = verify_terminal(attempt_root, terminal_path, terminal_sha256,
        notebook_id=notebook_id, version=version, source_root=source_root, public_path=public_path)
    # No evaluator path has been resolved, statted, read or inventoried above.
    # abspath is lexical only, including normalization of '..'. Reject overlap
    # before even output.exists(): a forbidden output could be evaluator-side.
    output = Path(os.path.abspath(output))
    evaluator_root = Path(os.path.abspath(evaluator_root))
    protected_roots = (Path(os.path.abspath(attempt_root)), Path(os.path.abspath(source_root)),
                       evaluator_root, Path(os.path.abspath(public_path)).parent)
    require(all(not output.is_relative_to(root) and not root.is_relative_to(output)
                for root in protected_roots),
            'evaluator output must be lexically disjoint from all protected input roots')
    require(not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)),
            'new regular evaluator output destination required')
    verify_inventory(evaluator_root, EVALUATOR_MANIFEST_SHA256)
    source_root = Path(source_root).absolute()
    sys.path.insert(0, str(source_root / 'src'))
    from tools import arc_offline_evaluation as scorer
    require(Path(scorer.__file__).resolve() == (source_root / 'tools/arc_offline_evaluation.py').resolve()
            and sha(regular(scorer.__file__)) == SCORER_SHA256, 'imported original scorer identity differs')
    challenges, solutions, reference = scorer.load_pinned_reference(evaluator_root / 'upstream', evaluator_root / 'provenance.json')
    require(challenges == admitted['public'], 'protected reference differs from exact solver-only input projection')
    evaluations = {}
    for treatment in TREATMENTS:
        evaluations[treatment] = scorer.evaluate(challenges, solutions, admitted['pools'][treatment])
        metrics = evaluations[treatment]['development_metrics']
        require(metrics['tasks'] == 120 and metrics['tests'] == 167
                and metrics['metrics']['pass_at_2']['denominator'] == 167, 'all-arm full120/167 scoring denominator required')
    del solutions
    paired = {t: {**scorer.paired(evaluations['baseline'], evaluations[t]), 'post_hoc_diagnostic_only': True,
                  'selects_treatment': False} for t in TREATMENTS if t != 'baseline'}
    terminal = admitted['terminal']; frozen = admitted['frozen_selection']
    summary = {'format': FORMAT, 'measurement': 'inherited-exposure-qualified PUBLIC developmental diagnosis',
        'tasks_per_treatment': 120, 'queries_per_treatment': 167, 'requested_treatments': list(TREATMENTS),
        'comparison_complete': admitted['complete'], 'partial_diagnostic': not admitted['complete'],
        'selection_frozen_before_public': True, 'selected_treatment': frozen['selected_treatment'],
        'comparison_report_sha256': frozen['comparison_report_sha256'], 'selection_changed': False,
        'source_capsule_manifest_sha256': terminal['source_capsule_manifest_sha256'],
        'source_identity': terminal['source_identity'], 'runtime_source_manifest_sha256': admitted['source_manifest_file_sha256'],
        'provider_notebook_id': notebook_id, 'provider_version': version, 'provider_status': terminal['status'],
        'provider_terminal_evidence_sha256': terminal_sha256, 'provider_signature_claimed': False,
        'source_host_processes_rechecked_on_evaluator': False,
        'closure_basis': 'exact source-side worker and outer proofs independently bound to external terminal readback',
        'prediction_seal_sha256': terminal['prediction_seals'], 'pools_sha256': terminal['pools_sha256'],
        'scorer_sha256': SCORER_SHA256, 'solver_manifest_sha256': SOLVER_MANIFEST_SHA256,
        'evaluator_manifest_sha256': EVALUATOR_MANIFEST_SHA256, 'reference': reference,
        'treatments': {t: {'inference_complete': admitted['verifications'][t]['complete'],
            'completed_views': admitted['verifications'][t]['completed_views'], 'requested_views': 334,
            'development_metrics': evaluations[t]['development_metrics']} for t in TREATMENTS},
        'paired_vs_baseline': paired, 'post_hoc_diagnostic_only': True, 'public_used_for_selection': False,
        'generation_may_resume': False, 'inherited_exposure_qualified': True, 'clean_generalization_claimed': False,
        'capacity_gain_claimed': False, 'official_score': None, 'hidden_score': None,
        'limits': ['All arms retain120tasks/167queries, including empty/failed/unexecuted queries.',
            'Any missing requested view or incomplete execution makes this a partial diagnostic, not a completed comparison.',
            'Paired PUBLIC differences are post-hoc exposure-qualified diagnostics, not a new selection rule.',
            'The untouched anchor has held-demo evaluation only, not matched-view PUBLIC scoring; paired results cannot measure absolute PUBLIC gain over the original pretrained model.',
            'External observer evidence binds actual provider readback; it is not a provider cryptographic signature.']}
    for treatment in TREATMENTS:
        for name, entry in admitted['seals'][treatment]['files'].items():
            _artifact(Path(attempt_root) / 'solver', name, entry)
        require(sha(admitted['pool_paths'][treatment]) == terminal['pools_sha256'][treatment], 'sealed predictions changed during scoring')
    require(sha(admitted['closed_result_path']) == terminal['closed_result_sha256']
            and sha(admitted['handoff_path']) == terminal['handoff_sha256']
            and sha(regular(terminal_path)) == terminal_sha256, 'closure or provider evidence changed during scoring')
    output.mkdir(parents=True, exist_ok=False)
    for treatment, evaluation in evaluations.items():
        write_new(output / (treatment + '-evaluation.json'), evaluation)
    write_new(output / 'public-summary.json', summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('attempt-root', 'source-root', 'public-challenges', 'evaluator-root', 'terminal-evidence', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--terminal-sha256', required=True)
    parser.add_argument('--notebook-id', type=int, required=True)
    parser.add_argument('--version', type=int, required=True)
    args = parser.parse_args(argv)
    result = score(args.attempt_root, args.evaluator_root, args.public_challenges, args.source_root,
                   args.terminal_evidence, args.terminal_sha256, notebook_id=args.notebook_id, version=args.version,
                   output=args.output)
    print(json.dumps({'output': str(args.output), 'comparison_complete': result['comparison_complete'],
        'partial_diagnostic': result['partial_diagnostic'], 'selected_treatment': result['selected_treatment'],
        'pass_at_2': {t: result['treatments'][t]['development_metrics']['metrics']['pass_at_2'] for t in TREATMENTS}}, sort_keys=True))
    return 0 if result['comparison_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
