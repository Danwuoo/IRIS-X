"""Full real-model fusion training, checkpoints and frozen generated development.

The complete panel is frozen before model work. Only no-TTT generated exact
results can select a provisional train-derived candidate; this entrypoint has
no PUBLIC generation, scorer, TTT, remote action, or architecture extension.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path
import random
import shutil
import time
from tools.arc2_goal_sprint_20261017.data import canonical, digest, loo_example
from tools.arc2_goal_sprint_20261017.launch import write_new
from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, state_digest
from tools.arc2_goal_sprint_20261017.run import atomic_json
from tools.nvarc_posttrain_20261017 import convergence as cv, matched_controls as mc, matched_workflow as mw
from tools.nvarc_posttrain_20261017.experiment import infer_query
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_posttrain_20261017.stability import verify_prediction
from .contracts import (ARMS, DEFAULT_CONFIG, LOSS_CONTRACT, PROTOCOL, SELECTION_RULE,
                        physical_bounds, require, sha, validate_config)
from .panels import validate_prepared
from .training import run_training

MAX_GROUP_BYTES = 8 * 1024**2
MAX_PREFLIGHT_BYTES = 32 * 1024**2


def group_evidence_limit(cfg):
    # Two aligned probability vectors, token IDs and lineage per eight rows.
    # The limit is enforced at every write, not merely estimated for disk.
    return min(MAX_GROUP_BYTES, 65536 + 8 * cfg['context_tokens'] * 80)


def json_training(value):
    return {**{k: v for k, v in value.items() if k != 'states'},
            'state_sha256': {arm: state_digest(state) for arm, state in value.get('states', {}).items()}}


def select_arm(evaluation, *, complete):
    if not complete: return 'anchor'
    require(set(evaluation) == set(ARMS) and all(v['complete'] for v in evaluation.values()),
            'all full development panels required before selection')
    counts = {a: evaluation[a]['pass2'] for a in ARMS}
    require(all(type(x) is int and 0 <= x <= evaluation['anchor']['full_requested_denominator'] for x in counts.values()),
            'full-denominator integer exact counts required')
    best = max(counts.values()); winners = [a for a, n in counts.items() if n == best]
    return winners[0] if len(winners) == 1 and best > counts['anchor'] else 'anchor'


def summarize(cell):
    rows = cell['records']; cell['completed_parents'] = sum(bool(r['complete']) for r in rows)
    cell['complete'] = cell['completed_parents'] == cell['full_requested_denominator']
    for metric in ('pass1', 'pass2'):
        cell['observed_' + metric] = sum(r[metric] or 0 for r in rows)
        cell[metric] = cell['observed_' + metric] if cell['complete'] else None


def run_workflow(engine, prepared, *, deadline, training_deadline, output, source_identity,
                 config=None, audit=lambda *args, **kwargs: None):
    cfg = validate_config(config); validate_prepared(prepared)
    require(mc._is_sha(source_identity), 'independently pinned source identity required')
    require(all(type(v) in (int, float) and math.isfinite(v) for v in (deadline, training_deadline))
            and time.time() < training_deadline < deadline, 'original finite training/evaluation/closure deadlines required')
    require(engine.probability_policy == prepared['protocol']['probability_policy'] == FP32_BACKBONE_POLICY,
            'matching fixed FP32-backbone panel and engine required')
    if engine.contract['variant'] != 'tiny':
        require(cfg == DEFAULT_CONFIG and len(prepared['training']) == 64 and len(prepared['development']) == 96,
                'fixed official fusion recipe and full64/96 panels required')
    output = Path(output)
    require(not output.exists(), 'new immutable workflow destination required')
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'regular workflow path required')
    prepared = copy.deepcopy(prepared); ids = prepared['protocol']['development_parent_ids']; denominator = len(ids)
    anchor = adapter_state(engine.model); anchor_sha = state_digest(anchor); mode = engine.model.training
    hash_cost = {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.0}
    policy_sha = mc.full_policy_sha256(engine, hash_cost); bytes_per_state = sum(v.numel()*v.element_size() for v in anchor.values())
    # Evidence upper bound plus three exports and one staging serialization. The
    # small-fixture reserve is not an official disk-feasibility claim.
    evidence_limit = 2*cfg['updates']*group_evidence_limit(cfg) + MAX_PREFLIGHT_BYTES + 32*1024**2
    required = 4*bytes_per_state + evidence_limit
    require(shutil.disk_usage(output.parent).free >= required, 'checkpoint and bounded complete evidence reserve unavailable')
    output.mkdir(parents=True); (output/'groups').mkdir()
    protocol = {'version': PROTOCOL, 'config': cfg, 'arms': list(ARMS), 'panel_pins': prepared['pins'],
        'source_identity': source_identity, 'loss_contract': LOSS_CONTRACT, 'bounds': physical_bounds(cfg),
        'development_parent_ids': ids, 'full_requested_denominator': denominator,
        'development_target_digests': prepared['protocol']['development_target_digest'],
        'probability_policy': FP32_BACKBONE_POLICY, 'selection_rule': SELECTION_RULE,
        'requested_view_generations': len(ARMS)*denominator*2, 'ttt_steps': 0,
        'public_feedback_used': False, 'equal_compute_claimed': False, 'initial_weight_cleanliness_claimed': False}
    artifacts = {}
    for name, value in (('protocol.json', protocol), ('prepared-panels.json', prepared)):
        write_new(output/name, value); artifacts[name] = mw._file(output/name, output)
    cells = {arm: {'complete': False, 'full_requested_denominator': denominator, 'completed_parents': 0,
        'pass1': None, 'pass2': None, 'observed_pass1': 0, 'observed_pass2': 0,
        'records': [{'parent_id': p, 'status': 'not_executed', 'complete': False, 'pass1': None, 'pass2': None,
            'target_digest': protocol['development_target_digests'][p]} for p in ids]} for arm in ARMS}
    report = {'format': 'irisx/efficient-fusion-workflow-v1', 'status': 'running', 'complete': False,
        'source_identity': source_identity, 'protocol_sha256': sha(protocol), 'training': None,
        'anchor_state_sha256': anchor_sha, 'anchor_policy_sha256': policy_sha, 'workflow_hash_cost': hash_cost,
        'engine_contract': engine.contract, 'trainable_contract': engine.trainable_inventory,
        'tokenizer_admission': engine.tokenizer_admission, 'base_identity': engine.base_identity,
        'probability_execution': engine.probability_execution_receipt(),
        'exports': {arm: {'status': 'not_executed'} for arm in ARMS}, 'evaluation': cells,
        'selected_arm': 'anchor', 'candidate_selected': False, 'selection_label': 'retain-anchor',
        'private_artifacts': artifacts, 'deadline_epoch': deadline, 'training_deadline_epoch': training_deadline,
        'anchor_restored': False, 'owned_process_closure_verified': False,
        'public_inference_performed': False, 'public_answers_used': False, 'public_scoring_performed': False,
        'ttt_performed': False, 'equal_compute_claimed': False, 'efficacy_claimed': False,
        'clean_generalization_claimed': False, 'full_requested_denominator': denominator,
        'disk_admission': {'required_bytes': required, 'trainable_state_bytes': bytes_per_state,
                           'maximum_evidence_bytes': evidence_limit},
        'limits': ['Known prior local panels excluded; unknown inherited model exposure is not removed.',
                   'Matching prompts and optimizer slots is not equal GPU wall/FLOPs.',
                   'Only closed independently verified results may qualify as a completed experiment.']}
    def persist():
        require(len(canonical(report)) <= 8*1024**2, 'bounded fusion summary required')
        atomic_json(output/'report.json', report)
    def persist_group(value):
        require(len(canonical(value)) <= group_evidence_limit(cfg), 'complete group exceeds declared evidence bound')
        path = output/'groups'/f"{value['slot']:03}.json"; atomic_json(path, value)
        artifacts[path.relative_to(output).as_posix()] = mw._file(path, output)
    def persist_gradient(value):
        require(len(canonical(value)) <= group_evidence_limit(cfg), 'gradient evidence exceeds declared bound')
        path = output/'gradients'/f"{value['slot']:03}.json"; path.parent.mkdir(exist_ok=True)
        atomic_json(path, value); artifacts[path.relative_to(output).as_posix()] = mw._file(path, output)
    def persist_probe(value):
        require(len(canonical(value)) <= MAX_PREFLIGHT_BYTES, 'complete preflight exceeds evidence bound')
        path = output/'probability-preflight.json'; atomic_json(path, value)
        artifacts[path.name] = mw._file(path, output)
    def persist_training(value): report.update(training=json_training(value)); persist()
    meter = mc._Meter(engine); before = meter.snapshot(); started = time.monotonic(); primary = None
    try:
        persist()
        trained = run_training(engine, prepared, deadline=training_deadline, config=cfg,
            persist=persist_training, persist_group=persist_group, persist_probe=persist_probe, persist_gradient=persist_gradient)
        require(trained['anchor_restored'] and not engine._fatal_update, 'healthy restored training anchor required')
        if trained['status'] != 'complete': raise PhaseDeadline('declared multiupdate training incomplete')
        params = {**cfg, 'retain_token_evidence': True}
        for arm in ARMS:
            check_deadline(deadline); state = trained['states'][arm]; state_sha = state_digest(state)
            cv.reset(engine, state, state_sha)
            checkpoint = engine.save_checkpoint(output/'checkpoints'/arm, origin={'phase': 'pre_public',
                'public_ttt_applied': False, 'public_labels_used': False, 'workflow': PROTOCOL,
                'arm': arm, 'source_identity': source_identity, 'protocol_sha256': report['protocol_sha256'],
                'selected': False, 'optimizer_slots': 0 if arm == 'anchor' else cfg['updates']})
            require(checkpoint['state_sha256'] == state_sha, 'saved state differs')
            report['exports'][arm] = {'status': 'complete', 'checkpoint': checkpoint}; persist()
            phase_before, phase_start = meter.snapshot(), time.monotonic()
            try:
                for row in cells[arm]['records']:
                    check_deadline(deadline); parent = row['parent_id']; row['status'] = 'running'; persist()
                    task = prepared['development'][parent]
                    demos, query, target = loo_example(task, random.Random(0), augment=False, held_index=0)
                    prediction = infer_query(engine, {'train': demos}, query, params, task_id=parent, views=2, deadline=deadline)
                    verification = verify_prediction(prediction, {'train': demos}, query, params, task_id=parent, views=2)
                    path = output/'predictions'/arm/(parent+'.json'); path.parent.mkdir(parents=True, exist_ok=True)
                    write_new(path, prediction); artifact = mw._file(path, output); artifacts[artifact['path']] = artifact
                    ranked = prediction['ranked_grids']
                    row.update(status='complete' if prediction['complete'] else 'partial', complete=prediction['complete'],
                        pass1=int(bool(ranked) and ranked[0] == target), pass2=int(target in ranked),
                        prediction_artifact=artifact, verification=verification, state_sha256=state_sha)
                    summarize(cells[arm]); persist(); audit('fusion_held_parent', arm=arm, parent_id=parent, complete=row['complete'])
                    if not prediction['complete']: raise PhaseDeadline('incomplete predeclared fixed development views')
                require(state_digest(adapter_state(engine.model)) == state_sha, 'no-TTT inference changed trainables')
            finally:
                engine.sync(); cells[arm].update(physical=mc._delta(meter.snapshot(), phase_before),
                                                  wall_seconds=time.monotonic()-phase_start)
                summarize(cells[arm]); persist()
            cv.reset(engine, anchor, anchor_sha)
        check_deadline(deadline)
        report.update(status='complete', complete=True)
        report['selected_arm'] = select_arm(cells, complete=True)
        report['candidate_selected'] = report['selected_arm'] != 'anchor'
        report['selection_label'] = 'provisional-train-derived-candidate' if report['candidate_selected'] else 'retain-anchor'
    except PhaseDeadline as error:
        primary = error; report.update(status='partial', complete=False, stop_reason=str(error))
    except BaseException as error:
        primary = error; report.update(status='failed', complete=False, error={'type': type(error).__name__, 'message': str(error)[:1024]})
        error.fusion_workflow_result = report; raise
    finally:
        try:
            cv.reset(engine, anchor, anchor_sha)
            require(mc.full_policy_sha256(engine, hash_cost) == policy_sha, 'full entry policy not restored after workflow')
            engine.model.train(mode); engine.sync(); report['anchor_restored'] = True
        except BaseException as error:
            engine._fatal_update = True; report.update(status='failed', complete=False, restoration_error=type(error).__name__)
            if primary is None or isinstance(primary, PhaseDeadline): error.fusion_workflow_result = report; raise
        finally:
            report.update(physical=mc._delta(meter.snapshot(), before), wall_seconds=time.monotonic()-started,
                engine_poisoned=bool(engine._fatal_update), returned_after_deadline=time.time() >= deadline)
            report['peak_memory'] = {'gpu_measured': engine.device.type == 'cuda', 'allocated_bytes': None, 'reserved_bytes': None}
            if engine.device.type == 'cuda':
                import torch
                report['peak_memory'].update(allocated_bytes=torch.cuda.max_memory_allocated(engine.device),
                                              reserved_bytes=torch.cuda.max_memory_reserved(engine.device))
            meter.close()
            if report['returned_after_deadline'] or engine._fatal_update or report['status'] != 'complete':
                report.update(complete=False, candidate_selected=False, selected_arm='anchor', selection_label='retain-anchor')
                if report['status'] == 'complete': report['status'] = 'partial'
            persist()
            if time.time() >= deadline and not report['returned_after_deadline']:
                report.update(status='partial' if report['status'] == 'complete' else report['status'],
                    complete=False, candidate_selected=False, selected_arm='anchor', selection_label='retain-anchor', returned_after_deadline=True)
                persist()
    return report
