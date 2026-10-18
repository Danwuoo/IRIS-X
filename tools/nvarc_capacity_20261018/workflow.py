"""Bounded same-example/optimizer-budget capacity screen, with no PUBLIC run.

The train/dev panel admission is inherited unchanged. Every treatment gets a
fresh official initialization, the exact same serialized SFT sequence, a fresh
AdamW, and target-free generated held-demo evaluation. The trained baseline
control is distinct from the untouched dense anchor, which receives a separate
development evaluation before SFT and protects selection. Optional PUBLIC
execution elsewhere compares only the three post-SFT arms, not that untouched
anchor. This is not equal GPU wall/FLOPs or a clean generalization claim.
"""
from __future__ import annotations

import copy
import gc
import math
from pathlib import Path
import random
import shutil
import time

import torch

from tools.arc2_goal_sprint_20261017.data import canonical, digest, loo_example
from tools.arc2_goal_sprint_20261017.launch import require, write_new
from tools.arc2_goal_sprint_20261017.model import (
    PhaseDeadline, adapter_state, check_deadline, make_optimizer, state_digest,
)
from tools.arc2_goal_sprint_20261017.run import atomic_json
from tools.nvarc_posttrain_20261017 import matched_controls as mc, matched_workflow as mw
from tools.nvarc_posttrain_20261017.codec import encode_example
from tools.nvarc_posttrain_20261017.engine import CompactEngine
from tools.nvarc_posttrain_20261017.experiment import infer_query
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_posttrain_20261017.stability import verify_prediction

PROTOCOL = 'compact-capacity-same-budget-v1'
FORMAT = 'irisx/nvarc-capacity-comparison-v1'
TREATMENTS = ('baseline', 'depth32', 'moe4_top2')
DEFAULT_CONFIG = {'updates': 64, 'learning_rate': 2e-5, 'seed': 20261018,
    'adapter_seed': 731, 'context_tokens': 8192, 'generation_tokens': 931,
    'evaluation_seed': 20261018, 'views': 2, 'ttt_steps': 0,
    'training_wall_seconds': 900, 'evaluation_wall_seconds': 900}
SELECTION_RULE = ('All three treatments complete the identical 64-update SFT schedule and all 16 '
    'two-view no-TTT held-demo generations; select only a unique strict generated-exact '
    'pass2 improvement over both untouched dense anchor and trained dense control for a capacity arm. '
    'A unique best trained baseline can select only if it strictly beats the untouched anchor. '
    'Any tie, partial development run, error or late development-comparison completion retains initial_anchor.')


def prepare_panels(*args, **kwargs):
    kwargs.setdefault('probability_policy', FP32_BACKBONE_POLICY)
    return mw.prepare_panels(*args, **kwargs)


def validate_config(config=None):
    cfg = copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    require(type(cfg) is dict and set(cfg) == set(DEFAULT_CONFIG), 'exact capacity config schema required')
    for key, upper in (('updates', 64), ('context_tokens', 8192), ('generation_tokens', 931)):
        require(type(cfg[key]) is int and 1 <= cfg[key] <= upper, 'bounded positive ' + key + ' required')
    require(cfg['views'] == 2 and type(cfg['views']) is int and cfg['ttt_steps'] == 0,
            'fixed two-view no-TTT evaluation required')
    for key in ('seed', 'adapter_seed', 'evaluation_seed'):
        require(type(cfg[key]) is int and 0 <= cfg[key] < 2**63, 'bounded integer seed required')
    for key, upper in (('learning_rate', 1e-3), ('training_wall_seconds', 900), ('evaluation_wall_seconds', 900)):
        require(type(cfg[key]) in (int, float) and math.isfinite(cfg[key]) and 0 < cfg[key] <= upper,
                'positive finite bounded ' + key + ' required')
    return cfg


def training_schedule(prepared, config=None):
    """Materialize before any model work; mutation/treatment-conditioned data denied."""
    cfg = validate_config(config)
    mw._validate_prepared(prepared)
    ids = prepared['protocol']['training_parent_ids']
    rng, schedule = random.Random(cfg['seed']), []
    while len(schedule) < cfg['updates']:
        order = list(ids); rng.shuffle(order)
        for parent in order:
            demos, query, target = loo_example(prepared['training'][parent], rng, augment=True)
            example = encode_example(demos, query, target, context=cfg['context_tokens'],
                                     generation=cfg['generation_tokens'], loss_mode='final')
            schedule.append({'step': len(schedule), 'parent_id': parent,
                'training_task_sha256': mc._sha(prepared['training'][parent]),
                'example': example, 'example_sha256': mc._sha(example)})
            if len(schedule) == cfg['updates']:
                break
    return schedule


def select_treatment(treatments, anchor, *, complete):
    if not complete or set(treatments) != set(TREATMENTS) or not anchor['complete']:
        return 'initial_anchor'
    require(all(treatments[t]['complete'] and treatments[t]['evaluation']['complete'] for t in TREATMENTS),
            'all declared treatments must be complete before selection')
    scores = {t: treatments[t]['evaluation']['pass2'] for t in TREATMENTS}
    require(all(type(v) is int and 0 <= v <= 16 for v in scores.values()), 'full-panel integer scores required')
    best = max(scores.values()); winners = [t for t in TREATMENTS if scores[t] == best]
    return winners[0] if len(winners) == 1 and best > anchor['pass2'] else 'initial_anchor'


def parameter_accounting(engine):
    """Observed resident counts plus explicitly approximate active-parameter proxy."""
    total = sum(p.numel() for p in engine.model.parameters())
    trainable = sum(p.numel() for p in engine.model.parameters() if p.requires_grad)
    admitted = engine.contract.get('capacity_v2', {}).get('accounting')
    if admitted is not None:
        require(admitted['total_resident_parameters'] == total and admitted['trainable_parameters'] == trainable,
                'live capacity accounting differs')
        return {'resident_parameters': total, 'trainable_parameters': trainable,
            'resident_parameter_bytes': sum(p.numel() * p.element_size() for p in engine.model.parameters()),
            'active_parameters_per_token_proxy': admitted['potentially_active_parameters_per_token'],
            'active_parameter_proxy_measured_flops': False, 'architecture_accounting': admitted}
    # One top-k mixture evaluates only k experts per token. This proxy ignores
    # imbalance, capacity/padding, routing, attention quadratic terms and LoRA.
    inactive = 0
    for module in engine.model.modules():
        experts = getattr(module, 'experts', None)
        top_k = getattr(module, 'top_k', None)
        if isinstance(experts, torch.nn.ModuleList) and type(top_k) is int and 0 < top_k <= len(experts):
            counts = [sum(p.numel() for p in expert.parameters()) for expert in experts]
            require(len(set(counts)) == 1, 'equal expert shapes required for active parameter proxy')
            inactive += (len(experts) - top_k) * counts[0]
    return {'resident_parameters': total, 'trainable_parameters': trainable,
        'resident_parameter_bytes': sum(p.numel() * p.element_size() for p in engine.model.parameters()),
        'active_parameters_per_token_proxy': total - inactive,
        'active_parameter_proxy_measured_flops': False}


def _summarize_evaluation(cell):
    rows = cell['records']; done = [row for row in rows if row['complete']]
    cell.update(completed_parents=len(done), complete=len(done) == cell['full_requested_denominator'],
        observed_pass1=sum(row['pass1'] or 0 for row in rows), observed_pass2=sum(row['pass2'] or 0 for row in rows))
    for metric in ('pass1', 'pass2'):
        cell[metric] = cell['observed_' + metric] if cell['complete'] else None


def run_workflow(engine_factory, prepared, *, deadline, output, source_identity,
                 config=None, audit=lambda *args, **kwargs: None):
    """Load/train/export/evaluate/dispose each treatment serially.

    The factory must return a fresh CapacityEngine per treatment. Reduced config
    is allowed only for explicitly tiny fixtures; official knobs are frozen.
    All interrupted cells retain 16 rows and unknown final pass1/pass2 values.
    The external controller, not this callable, proves owned process closure.
    """
    cfg = validate_config(config)
    require(mc._is_sha(source_identity), 'source identity SHA256 required')
    require(type(deadline) in (int, float) and math.isfinite(deadline) and time.time() < deadline,
            'finite unconsumed original deadline required')
    mw._validate_prepared(prepared)
    require(prepared['protocol'].get('probability_policy') == FP32_BACKBONE_POLICY,
            'capacity comparison requires predeclared FP32-backbone policy')
    prepared = copy.deepcopy(prepared)
    schedule = training_schedule(prepared, cfg)
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), 'new empty capacity destination required')
    output.mkdir(parents=True, exist_ok=True)
    ids = prepared['protocol']['development_parent_ids']
    protocol = {'version': PROTOCOL, 'treatments': list(TREATMENTS), 'config': cfg,
        'source_identity': source_identity, 'panel_pins': prepared['pins'],
        'training_schedule_sha256': mc._sha(schedule), 'probability_policy': FP32_BACKBONE_POLICY,
        'optimizer': {'kind': 'torch.optim.AdamW', 'learning_rate': cfg['learning_rate'],
            'weight_decay': 0.01, 'betas': [0.9, 0.999], 'eps': 1e-8, 'fresh_per_treatment': True},
        'training_data_control': 'identical pre-serialized augmented training LOO examples and order',
        'full_requested_denominator': 16, 'development_parent_ids': ids,
        'development_target_digests': prepared['protocol']['development_target_digest'],
        'selection_rule': SELECTION_RULE, 'fixture_config': cfg != DEFAULT_CONFIG,
        'baseline_definition': 'original dense architecture after the same SFT budget; not untouched anchor',
        'public_inference_performed': False, 'public_answers_used': False,
        'public_integration_boundary': 'Separate post-selection only: sealed full120-task/167-query predictions, '
            'stopped owned solver and unchanged answer-separated evaluator; not scheduled by this screen.',
        'initial_weight_cleanliness_claimed': False, 'equal_compute_claimed': False}
    artifacts = {}
    for name, value in (('protocol.json', protocol), ('source-panel-protocol.json', prepared['protocol']),
            ('source-binding.json', prepared['source_binding']), ('panel-admission.json', prepared['admission']),
            ('training-panel.json', prepared['training']), ('development-panel.json', prepared['development']),
            ('training-schedule.json', schedule)):
        write_new(output / name, value); artifacts[name] = mw._file(output / name, output)
    treatments = {}
    for treatment in TREATMENTS:
        treatments[treatment] = {'status': 'not_executed', 'complete': False,
            'training': {'requested_updates': cfg['updates'], 'attempted_updates': 0, 'accepted_updates': 0,
                         'completed': False, 'records': []},
            'checkpoint': None, 'evaluation': {'complete': False, 'full_requested_denominator': 16,
                'completed_parents': 0, 'pass1': None, 'pass2': None, 'observed_pass1': 0, 'observed_pass2': 0,
                'records': [{'parent_id': p, 'status': 'not_executed', 'complete': False, 'pass1': None, 'pass2': None,
                    'target_digest': protocol['development_target_digests'][p]} for p in ids]}}
    report = {'format': FORMAT, 'status': 'running', 'complete': False, 'source_identity': source_identity,
        'protocol_sha256': mc._sha(protocol), 'treatments': treatments, 'selected_treatment': 'initial_anchor',
        'candidate_selected': False, 'private_artifacts': artifacts, 'full_requested_denominator': 16,
        'deadline_epoch': deadline, 'owned_process_closure_verified': False, 'public_scoring_performed': False,
        'public_inference_performed': False, 'public_answers_used': False, 'efficacy_claimed': False,
        'capacity_gain_claimed': False, 'clean_generalization_claimed': False, 'equal_compute_claimed': False,
        'anchor': {'complete': False, 'full_requested_denominator': 16, 'completed_parents': 0,
            'pass1': None, 'pass2': None, 'observed_pass1': 0, 'observed_pass2': 0,
            'records': [{'parent_id': p, 'status': 'not_executed', 'complete': False, 'pass1': None, 'pass2': None,
                'target_digest': protocol['development_target_digests'][p]} for p in ids]},
        'limits': ['Small inherited-exposure train-derived held-demo panel, not clean/general/official accuracy.',
            'Same examples and optimizer budget do not establish equal GPU wall or FLOPs.',
            'Engine counters begin after construction; source loading and initial architecture-parity probes are included in load wall/memory, not these counters.',
            'No PUBLIC inference or evaluator feedback is used for selection.',
            'Standalone completion is not an owned-process/source-closure receipt.']}
    started = time.monotonic(); identity = None; variant = None; inherited_identity = None

    def persist():
        require(len(canonical(report)) <= 4 * 1024**2, 'capacity summary exceeds4MiB bound')
        atomic_json(output / 'report.json', report)

    persist()
    try:
        for treatment in TREATMENTS:
            check_deadline(deadline)
            cell = treatments[treatment]; cell['status'] = 'loading'; persist()
            engine = optimizer = meter = None
            arm_started = time.monotonic()
            try:
                from .model import CapacityEngine
                if torch.cuda.is_initialized():
                    torch.cuda.reset_peak_memory_stats()
                engine = engine_factory(treatment)
                require(type(engine) is CapacityEngine and getattr(engine, 'treatment', None) == treatment,
                        'fresh explicitly named capacity engine required')
                engine._checkpoint_admission()
                require(engine.probability_policy == FP32_BACKBONE_POLICY and not engine._fatal_update,
                        'healthy FP32-backbone engine required')
                require(not any(getattr(engine, k) for k in mc.COUNTERS), 'unused capacity engine required')
                actual_variant = engine.contract['variant']
                if identity is None:
                    identity, variant = engine.base_identity, actual_variant
                    inherited_identity = engine.contract['capacity_v2']['inherited_source_and_adapter_sha256']
                require(engine.base_identity == identity and actual_variant == variant
                        and engine.contract['capacity_v2']['inherited_source_and_adapter_sha256'] == inherited_identity
                        and engine.adapter_seed == cfg['adapter_seed'] and engine.generator.initial_seed() == cfg['seed'],
                        'same admitted original model identity and fixture status required')
                require(actual_variant == 'tiny' or cfg == DEFAULT_CONFIG, 'official comparison settings are frozen')
                engine.sync()
                cell['load_peak_memory'] = {'gpu_measured': engine.device.type == 'cuda',
                    'allocated_bytes': torch.cuda.max_memory_allocated(engine.device) if engine.device.type == 'cuda' else None,
                    'reserved_bytes': torch.cuda.max_memory_reserved(engine.device) if engine.device.type == 'cuda' else None}
                if engine.device.type == 'cuda':
                    torch.cuda.reset_peak_memory_stats(engine.device)
                cell.update(status='training', loading_wall_seconds=time.monotonic() - arm_started,
                    model_contract=engine.contract, trainable_contract=engine.trainable_inventory,
                    capacity_receipt=engine.contract.get('capacity_v2'),
                    initial_function_receipt=getattr(engine, 'initial_function_receipt', None),
                    base_identity=engine.base_identity,
                    parameter_accounting=parameter_accounting(engine),
                    initial_trainable_state_sha256=state_digest(adapter_state(engine.model)))
                state_bytes = cell['parameter_accounting']['trainable_parameters'] * 4
                require(shutil.disk_usage(output).free >= state_bytes + 32 * 1024**2,
                        'checkpoint and bounded evidence disk reserve unavailable')
                meter = mc._Meter(engine); before = meter.snapshot()
                from .model import probability_admission
                probe_started = time.monotonic(); probe_before = meter.snapshot()
                probe = probability_admission(engine, schedule[0]['example']['prompt_ids'],
                    deadline=min(deadline, time.time() + 120), max_new_tokens=min(32, cfg['generation_tokens'], cfg['context_tokens'] - len(schedule[0]['example']['prompt_ids'])))
                probe_path = output / 'probability' / (treatment + '.json')
                probe_path.parent.mkdir(parents=True, exist_ok=True); write_new(probe_path, probe)
                probe_artifact = mw._file(probe_path, output); artifacts[probe_artifact['path']] = probe_artifact
                cell['probability_admission'] = {'passed': probe['passed'], 'artifact': probe_artifact,
                    'tolerance': probe['tolerance'], 'wall_seconds': time.monotonic() - probe_started,
                    'physical': mc._delta(meter.snapshot(), probe_before), 'optimizer_updates': 0}
                persist()
                if not probe['passed'] and (probe.get('error') or {}).get('type') == 'PhaseDeadline':
                    raise PhaseDeadline('capacity probability admission reached deadline')
                require(probe['passed'], 'capacity sampled/full numerical admission failed before optimizer')
                if treatment == 'baseline':
                    anchor_started = time.monotonic(); anchor_before = meter.snapshot()
                    anchor_deadline = min(deadline, time.time() + cfg['evaluation_wall_seconds'])
                    params = {**cfg, 'retain_token_evidence': True}
                    report['anchor']['initial_state_sha256'] = cell['initial_trainable_state_sha256']
                    report['anchor']['base_identity'] = engine.base_identity
                    report['anchor']['reconstruction'] = 'Exact original source plus declared adapter seed; no mutable anchor checkpoint.'
                    try:
                        for row in report['anchor']['records']:
                            check_deadline(anchor_deadline)
                            parent = row['parent_id']; row['status'] = 'running'
                            demos, query, target = loo_example(prepared['development'][parent], random.Random(0),
                                                              augment=False, held_index=0)
                            prediction = infer_query(engine, {'train': demos}, query, params,
                                task_id=parent, views=cfg['views'], deadline=anchor_deadline)
                            verification = verify_prediction(prediction, {'train': demos}, query, params,
                                task_id=parent, views=cfg['views'])
                            path = output / 'predictions' / 'initial_anchor' / (parent + '.json')
                            path.parent.mkdir(parents=True, exist_ok=True); write_new(path, prediction)
                            artifact = mw._file(path, output); artifacts[artifact['path']] = artifact
                            ranked = prediction['ranked_grids']
                            row.update(status='complete' if prediction['complete'] else 'partial',
                                complete=prediction['complete'], pass1=int(bool(ranked) and ranked[0] == target),
                                pass2=int(target in ranked), prediction_artifact=artifact, verification=verification)
                            _summarize_evaluation(report['anchor']); persist()
                            if not prediction['complete']:
                                raise PhaseDeadline('incomplete untouched anchor generations')
                        require(state_digest(adapter_state(engine.model)) == cell['initial_trainable_state_sha256'],
                                'untouched anchor evaluation mutated initial state')
                    finally:
                        engine.sync(); _summarize_evaluation(report['anchor'])
                        report['anchor']['physical'] = mc._delta(meter.snapshot(), anchor_before)
                        report['anchor']['wall_seconds'] = time.monotonic() - anchor_started
                        persist()
                    check_deadline(anchor_deadline)
                train_before = meter.snapshot(); train_started = time.monotonic()
                # Each arm has the same finite train/eval time cap, not a claim
                # that measured elapsed work is equal. Original deadline wins.
                train_deadline = min(deadline - min(60, cfg['evaluation_wall_seconds']),
                                     time.time() + cfg['training_wall_seconds'])
                cell['training']['deadline_epoch'] = train_deadline
                optimizer = make_optimizer(engine.model, cfg['learning_rate'])
                try:
                    for record in schedule:
                        check_deadline(train_deadline)
                        require(mc._sha(record['example']) == record['example_sha256'], 'immutable example schedule changed')
                        cell['training']['attempted_updates'] += 1
                        update = engine.sft_step(copy.deepcopy(record['example']), optimizer, deadline=train_deadline)
                        cell['training']['accepted_updates'] += int(update['updated'])
                        cell['training']['records'].append({k: v for k, v in record.items() if k != 'example'} | update |
                            {'router_gradient_norms': copy.deepcopy(getattr(engine, 'last_router_gradient_norms', {}))})
                        audit('capacity_sft_step', treatment=treatment, step=record['step'], **update)
                        persist()
                    require(cell['training']['accepted_updates'] == cfg['updates'], 'all fixed SFT updates must commit')
                    cell['training']['completed'] = True
                finally:
                    optimizer.zero_grad(set_to_none=True); optimizer = None
                    engine.sync()
                    cell['training']['physical'] = mc._delta(meter.snapshot(), train_before)
                    cell['training']['wall_seconds'] = time.monotonic() - train_started
                check_deadline(train_deadline)
                check_deadline(deadline)
                checkpoint = engine.save_checkpoint(output / 'checkpoints' / treatment, origin={
                    'phase': 'pre_public', 'public_ttt_applied': False, 'public_labels_used': False,
                    'workflow': PROTOCOL, 'treatment': treatment, 'source_identity': source_identity,
                    'protocol_sha256': report['protocol_sha256'], 'training_schedule_sha256': protocol['training_schedule_sha256'],
                    'selected': False})
                cell['checkpoint'] = checkpoint
                for name in ('manifest.json', 'trainable_state.safetensors'):
                    path = Path(checkpoint['root']) / name
                    artifacts[path.relative_to(output).as_posix()] = mw._file(path, output)
                eval_started = time.monotonic(); eval_before = meter.snapshot()
                eval_deadline = min(deadline, time.time() + cfg['evaluation_wall_seconds'])
                cell.update(status='evaluating'); cell['evaluation']['deadline_epoch'] = eval_deadline
                params = {**cfg, 'retain_token_evidence': True}
                try:
                    for row in cell['evaluation']['records']:
                        check_deadline(eval_deadline)
                        parent = row['parent_id']; row['status'] = 'running'
                        demos, query, target = loo_example(prepared['development'][parent], random.Random(0),
                                                          augment=False, held_index=0)
                        prediction = infer_query(engine, {'train': demos}, query, params,
                            task_id=parent, views=cfg['views'], deadline=eval_deadline)
                        verification = verify_prediction(prediction, {'train': demos}, query, params,
                            task_id=parent, views=cfg['views'])
                        path = output / 'predictions' / treatment / (parent + '.json')
                        path.parent.mkdir(parents=True, exist_ok=True); write_new(path, prediction)
                        artifact = mw._file(path, output); artifacts[artifact['path']] = artifact
                        ranked = prediction['ranked_grids']
                        row.update(status='complete' if prediction['complete'] else 'partial',
                            complete=prediction['complete'], pass1=int(bool(ranked) and ranked[0] == target),
                            pass2=int(target in ranked), prediction_artifact=artifact, verification=verification)
                        _summarize_evaluation(cell['evaluation']); persist()
                        if not prediction['complete']:
                            raise PhaseDeadline('incomplete fixed held-demo generations')
                    require(state_digest(adapter_state(engine.model)) == checkpoint['state_sha256'],
                            'no-TTT evaluation changed exported trainable state')
                    cell['evaluation']['exported_state_unchanged'] = True
                finally:
                    engine.sync(); _summarize_evaluation(cell['evaluation'])
                    cell['evaluation']['physical'] = mc._delta(meter.snapshot(), eval_before)
                    cell['evaluation']['wall_seconds'] = time.monotonic() - eval_started
                check_deadline(eval_deadline)
                check_deadline(deadline)
                cell.update(status='complete', complete=True)
            except BaseException as error:
                cell.update(status='partial' if isinstance(error, PhaseDeadline) else 'failed',
                            complete=False, error=type(error).__name__)
                raise
            finally:
                if optimizer is not None:
                    optimizer.zero_grad(set_to_none=True)
                if engine is not None:
                    if meter is not None:
                        cell['physical'] = mc._delta(meter.snapshot(), before); meter.close()
                        cell['physical_counter_scope'] = 'after successful engine construction; includes numerical gate, training and generated evaluation; excludes initial architecture probes retained in loading wall/memory'
                        account = cell['parameter_accounting']
                        train_tokens = cell['training'].get('physical', {}).get('model_input_tokens', 0)
                        infer_tokens = cell['evaluation'].get('physical', {}).get('model_input_tokens', 0)
                        cell['approximate_flops'] = {
                            'training_dense_equivalent_proxy': 6 * account['active_parameters_per_token_proxy'] * train_tokens,
                            'inference_linear_proxy': 2 * account['active_parameters_per_token_proxy'] * infer_tokens,
                            'measured': False, 'basis': '6P*T train / 2P*T inference active-parameter proxies; '
                                'not actual FLOPs; ignores attention quadratic work, activation recomputation, routing, '
                                'LoRA-vs-full-backprop differences, cache and expert imbalance'}
                    if callable(getattr(engine, 'dispatch_receipt', None)):
                        cell['expert_dispatch'] = engine.dispatch_receipt()
                    cell['engine_poisoned'] = bool(engine._fatal_update)
                    cell['peak_memory'] = {'gpu_measured': engine.device.type == 'cuda',
                        'allocated_bytes': max(cell.get('load_peak_memory', {}).get('allocated_bytes') or 0,
                            torch.cuda.max_memory_allocated(engine.device)) if engine.device.type == 'cuda' else None,
                        'reserved_bytes': max(cell.get('load_peak_memory', {}).get('reserved_bytes') or 0,
                            torch.cuda.max_memory_reserved(engine.device)) if engine.device.type == 'cuda' else None,
                        'scope': 'maximum of model-load and resident train/eval allocator peaks; not whole-device process memory'}
                    if engine._fatal_update:
                        cell.update(status='failed', complete=False)
                cell['wall_seconds'] = time.monotonic() - arm_started
                _summarize_evaluation(cell['evaluation']); persist()
                optimizer = engine = meter = None; gc.collect()
                if torch.cuda.is_initialized():
                    torch.cuda.empty_cache()
        require(all(cell['complete'] for cell in treatments.values()), 'all fixed treatments required')
        report.update(status='complete', complete=True)
        report['selected_treatment'] = select_treatment(treatments, report['anchor'], complete=True)
        report['candidate_selected'] = report['selected_treatment'] != 'initial_anchor'
    except PhaseDeadline:
        report.update(status='partial', complete=False, stop_reason='original_or_treatment_deadline')
    except BaseException as error:
        report.update(status='failed', complete=False, error=type(error).__name__)
        error.capacity_workflow_result = report
        raise
    finally:
        report['wall_seconds'] = time.monotonic() - started
        report['returned_after_deadline'] = time.time() >= deadline
        if report['returned_after_deadline']:
            report.update(status='partial' if report['status'] != 'failed' else 'failed', complete=False)
        if not report['complete']:
            report.update(selected_treatment='initial_anchor', candidate_selected=False)
        persist()
        if time.time() >= deadline and not report['returned_after_deadline']:
            report.update(status='partial', complete=False, returned_after_deadline=True,
                          selected_treatment='initial_anchor', candidate_selected=False)
            persist()
    return report
