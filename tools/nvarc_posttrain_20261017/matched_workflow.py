"""Admitted train-only matched-loss screen plus genuine held-demo generation.

This is a one-update mechanism/direction screen, not an optimized RAFT/DAPO or
RLVE recipe. Known-variant strata are syntactic, not generator lineage. No PUBLIC
prediction or evaluator is called; original training-file test fields are unused.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time

import torch

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import canonical, digest, loo_example
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, regular, require, sha, write_new
from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, restore_state, state_digest
from tools.arc2_goal_sprint_20261017.run import atomic_json
from . import matched_controls as controls
from .engine import CompactEngine, FatalUpdateError
from .precision_contract import LEGACY_POLICY, FP32_HEAD_POLICY, admit_policy
from .experiment import infer_query, panel_ids
from .stability import select_panel as stability_panel, verify_prediction

PROTOCOL = 'compact-matched-controls-v1'
FORMAT = 'irisx/nvarc-matched-workflow-v1'
PARENTS = 16
VIEWS = 2
EVALUATION_SEED = 20261018
PREFLIGHT = 'first-seeded-microbatch-cached-and-full-v1'


def _sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _groups(tasks):
    cache, result = {}, {}
    for parent, task in tasks.items():
        key = _sha({'train': task['train']})
        if key not in cache:
            cache[key] = known_variant_group({'train': task['train'], 'test': []})
        result[parent] = cache[key]
    return result


def _choose(tasks, groups, purpose, excluded=()):
    unavailable = set(excluded)
    chosen = []
    for parent in sorted(tasks, key=lambda p: hashlib.sha256((PROTOCOL + ':' + purpose + ':' + p).encode()).hexdigest()):
        pairs = tasks[parent]['train']
        if not 2 <= len(pairs) <= 32 or groups[parent] in unavailable:
            continue
        # A repeated held input in retained demonstrations is not an independent
        # held-demo test, even if a different target happens to be supplied.
        if any(pair['input'] == pairs[0]['input'] for pair in pairs[1:]):
            continue
        chosen.append(parent); unavailable.add(groups[parent])
        if len(chosen) == PARENTS:
            return chosen
    raise ValueError('insufficient independent known-variant groups for fixed ' + purpose + ' panel')


def prepare_panels(training, development, public, split, *, training_root, training_manifest_path,
                   expected_training_manifest_sha256=TRAINING_MANIFEST_SHA256,
                   probability_policy=LEGACY_POLICY):
    """Independently bind exact source bytes and recompute fixed panel exclusions.

    load_data must already have admitted the original corpus. This second check
    ties the mappings to actual raw training files without using their test data.
    The injectable manifest pin permits synthetic offline fixtures; the worker
    always supplies the immutable production default.
    """
    admit_policy(probability_policy)
    body = regular(training_manifest_path).read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_training_manifest_sha256
            == split.get('training_manifest_sha256'), 'independently pinned training source required')
    manifest = json.loads(body)
    fixed = manifest['upstream']['fixed_splits']
    require(len(training) == 800 and len(development) == 200 and len(public) == 120
            and sum(len(t['test']) for t in public.values()) == 167,
            'original admitted800/200 and solver120/167 partitions required')
    require(len(fixed['train']) == 800 and len(fixed['dev']) == 200
            and set(training) == set(fixed['train']) and set(development) == set(fixed['dev']),
            'this screen requires unchanged historical800/200 train/dev partition')
    require(set(training).isdisjoint(development) and set(training).isdisjoint(public)
            and set(development).isdisjoint(public), 'train/dev/PUBLIC parent overlap forbidden')
    require(split.get('training_test_fields_used') is False
            and split.get('train_ids_digest') == digest(sorted(training))
            and split.get('dev_ids_digest') == digest(sorted(development))
            and split.get('public_digest') == digest(public), 'admitted split receipt differs')
    for task in public.values():
        require(set(task) == {'train', 'test'} and all(set(q) == {'input'} for q in task['test']),
                'PUBLIC projection must remain answer-free and exclusion-only')
    tasks = {**training, **development}
    require(all(set(t) == {'train'} for t in tasks.values()), 'only original training demonstrations admitted')
    source_files = {}
    root = Path(training_root)
    require({p.stem for p in root.glob('*.json')} == set(tasks), 'exact admitted training file inventory required')
    for parent, task in sorted(tasks.items()):
        name = 'data/training/' + parent + '.json'
        row = manifest['files'][name]
        raw = regular(root / (parent + '.json')).read_bytes()
        require(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
                'source training bytes differ')
        require(json.loads(raw)['train'] == task['train'], 'admitted demonstration mapping differs from source')
        source_files[name] = {'bytes': len(raw), 'sha256': row['sha256']}
    groups = {name: _groups(data) for name, data in (('train', training), ('dev', development), ('public', public))}
    sets = {name: set(value.values()) for name, value in groups.items()}
    require(sets['train'].isdisjoint(sets['dev']) and sets['train'].isdisjoint(sets['public'])
            and sets['dev'].isdisjoint(sets['public']), 'known-variant overlap across partitions forbidden')
    previous = panel_ids(development, 24)
    stability, excluded_previous = stability_panel(development)
    require(set(previous) == set(excluded_previous), 'historical panel protocol changed')
    unavailable = {groups['dev'][parent] for parent in previous + stability}
    train_ids = _choose(training, groups['train'], 'train')
    dev_ids = _choose(development, groups['dev'], 'dev', unavailable)
    lineage = {'kind': 'syntactic-known-D4-color-demo-shuffle-strata-v1',
        'true_generator_lineage_available': False, 'semantic_family_independence_claimed': False,
        'groups': groups,
        'family_definition': 'known-variant:' + '<demonstration-only known_variant_group sha256>',
        'priority_interpretation': 'one parent per selected group; family priority degenerates to parent/group difficulty'}
    source = {'training_manifest_sha256': expected_training_manifest_sha256, 'files': source_files}
    split_binding = {'receipt': split, 'fixed_splits': fixed,
        'partition_ids': {name: sorted(data) for name, data in (('train', training), ('dev', development), ('public', public))},
        'known_variant_partition_sha256': _sha(groups), 'public_use': 'input/demonstration exclusion only'}
    family = lambda group: 'known-variant:' + group
    admission = {'format': controls.ADMISSION_FORMAT, 'source_sha256': _sha(source),
        'split_sha256': _sha(split_binding), 'family_lineage_sha256': _sha(lineage),
        'parents': [{'parent_id': parent, 'task_sha256': _sha(training[parent]),
            'variant_group': groups['train'][parent], 'family_id': family(groups['train'][parent]), 'held_index': 0}
            for parent in train_ids],
        'excluded': {'parent_ids': sorted(set(development) | set(public)),
            'variant_groups': sorted(sets['dev'] | sets['public']),
            'family_ids': sorted(family(group) for group in sets['dev'] | sets['public'])}}
    selected_train = {p: copy.deepcopy(training[p]) for p in train_ids}
    controls.admit_panel(selected_train, admission, expected_admission_sha256=_sha(admission))
    protocol = {'version': PROTOCOL, 'training_parent_ids': train_ids, 'development_parent_ids': dev_ids,
        'development_task_sha256': {p: _sha(development[p]) for p in dev_ids},
        'development_target_digest': {p: digest(development[p]['train'][0]['output']) for p in dev_ids},
        'development_variant_groups': {p: groups['dev'][p] for p in dev_ids},
        'excluded_previous_panel': previous, 'excluded_stability_panel': stability,
        'excluded_development_variant_groups': sorted(unavailable),
        'admission_sha256': _sha(admission), 'source_sha256': _sha(source),
        'split_sha256': _sha(split_binding), 'family_lineage_sha256': _sha(lineage),
        'arms': list(controls.ARMS), 'held_demo_index': 0, 'ttt_steps': 0, 'views': VIEWS,
        'evaluation_seed': EVALUATION_SEED, 'probability_preflight': PREFLIGHT,
        'selection_metric': 'generated-held-demo-exact-pass2',
        'selection_rule': 'all four arms complete; strictly higher pass2 than anchor; ties retain anchor',
        'initial_weight_cleanliness_claimed': False, 'public_feedback_used': False,
        'scientific_scope': 'one-update natural-parent mechanism screen, not optimized training or RLVE/DAPO/RAFT reproduction'}
    if probability_policy != LEGACY_POLICY:
        protocol['probability_policy'] = probability_policy
    binding = {'source': source, 'split': split_binding, 'family_lineage': lineage}
    return {'training': selected_train, 'development': {p: copy.deepcopy(development[p]) for p in dev_ids},
        'admission': admission, 'protocol': protocol, 'source_binding': binding,
        'pins': {'admission_sha256': _sha(admission), 'protocol_sha256': _sha(protocol), 'source_binding_sha256': _sha(binding)}}


def _validate_prepared(prepared):
    protocol, admission, binding, pins = (prepared[k] for k in ('protocol', 'admission', 'source_binding', 'pins'))
    require(pins == {'admission_sha256': _sha(admission), 'protocol_sha256': _sha(protocol),
                     'source_binding_sha256': _sha(binding)}, 'pinned panel payload changed before collection')
    require(protocol['version'] == PROTOCOL and protocol['arms'] == list(controls.ARMS)
            and protocol['held_demo_index'] == 0 and protocol['ttt_steps'] == 0 and protocol['views'] == VIEWS
            and protocol['evaluation_seed'] == EVALUATION_SEED
            and protocol.get('probability_preflight') == PREFLIGHT, 'fixed heldout protocol differs')
    require(protocol['admission_sha256'] == pins['admission_sha256']
            and len(prepared['training']) == PARENTS and len(prepared['development']) == PARENTS
            and set(protocol['training_parent_ids']) == set(prepared['training'])
            and set(protocol['development_parent_ids']) == set(prepared['development']), 'exact fixed panels required')
    for key, field in (('source_sha256', 'source'), ('split_sha256', 'split'), ('family_lineage_sha256', 'family_lineage')):
        require(protocol[key] == admission[key] == _sha(binding[field]), 'bound source/split/family evidence differs')
    controls.admit_panel(prepared['training'], admission, expected_admission_sha256=pins['admission_sha256'])
    for parent, task in prepared['development'].items():
        require(set(task) == {'train'} and len(task['train']) >= 2
                and _sha(task) == protocol['development_task_sha256'][parent]
                and digest(task['train'][0]['output']) == protocol['development_target_digest'][parent],
                'fixed development task or held-target digest differs')
    require(set(prepared['training']).isdisjoint(prepared['development']), 'heldout parent overlap forbidden')


def _json_controls(screen):
    # Tensor values only ever pass through the engine's exact safetensors format.
    return {**{k: v for k, v in screen.items() if k != 'states'},
        'state_sha256': {arm: state_digest(state) for arm, state in screen.get('states', {}).items()}}


def _file(path, root):
    return {'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(regular(path))}


def run_workflow(engine, prepared, *, deadline, screen_deadline, output, audit, source_identity, job_id, config=None):
    """Run real collection/updates, export named states, generate all heldouts.

    Every arm/task begins with the official anchor and returns to it. Partial
    attempts remain in all four 16-parent denominators. Nondeadline numerical or
    export errors persist a failed receipt and propagate; poison is never reset.
    """
    started = time.monotonic()
    require(isinstance(engine, CompactEngine) and engine.contract['variant'] in {'2b', 'tiny'},
            'official2B or explicitly synthetic tiny CompactEngine required')
    cfg = controls._config(config)
    require(engine.contract['variant'] == 'tiny' or cfg == controls.DEFAULT_CONFIG,
            'official2B mechanism settings are frozen')
    require(all(type(t) in (int, float) and math.isfinite(t) for t in (deadline, screen_deadline))
            and screen_deadline < deadline, 'finite screen deadline and heldout/closure reserve required')
    require(controls._is_sha(source_identity) and job_id == '2b-S', 'owned source/job identity required')
    _validate_prepared(prepared)
    require(prepared['protocol'].get('probability_policy', LEGACY_POLICY) == engine.probability_policy,
            'declared numerical policy differs from actual engine')
    engine._checkpoint_admission()
    prepared = copy.deepcopy(prepared)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name, key in (('matched-protocol.json', 'protocol'), ('matched-admission.json', 'admission'),
                      ('matched-source-binding.json', 'source_binding')):
        write_new(output / name, prepared[key]); artifacts[name] = _file(output / name, output)
    protocol = prepared['protocol']; anchor = adapter_state(engine.model); anchor_sha = state_digest(anchor)
    hash_cost = {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.}
    policy_sha = controls.full_policy_sha256(engine, hash_cost)
    trainable_bytes = sum(t.numel() * t.element_size() for t in anchor.values())
    disk_required = 5 * trainable_bytes + 1024**3
    free_disk = shutil.disk_usage(output).free
    require(free_disk >= disk_required, 'four checkpoints plus staging and evidence disk reserve unavailable')
    meter = controls._Meter(engine); before = meter.snapshot()
    ids = protocol['development_parent_ids']
    evaluation = {'complete': False, 'requested_parents': PARENTS, 'full_requested_denominator': PARENTS,
        'requested_views': VIEWS, 'ttt_steps': 0, 'metric': 'generated-held-demo-exact-pass2', 'arms': {}}
    for arm in controls.ARMS:
        evaluation['arms'][arm] = {'complete': False, 'requested_parents': PARENTS, 'complete_parents': 0,
            'pass1': 0, 'pass2': 0, 'valid': 0, 'records': [{'parent_id': parent, 'status': 'not_executed',
                'complete': False, 'pass1': 0, 'pass2': 0, 'valid': False, 'completed_views': 0,
                'target_digest': protocol['development_target_digest'][parent]} for parent in ids]}
    report = {'format': FORMAT, 'status': 'running', 'complete': False, 'protocol_sha256': prepared['pins']['protocol_sha256'],
        'admission_sha256': prepared['pins']['admission_sha256'], 'anchor_state_sha256': anchor_sha,
        'anchor_policy_sha256': policy_sha, 'full_requested_denominator': PARENTS, 'arms': list(controls.ARMS),
        'evaluation': evaluation, 'controls': None, 'probability_preflight': None,
        'exports': {arm: {'status': 'not_executed'} for arm in controls.ARMS},
        'selected_arm': 'anchor', 'candidate_selected': False, 'anchor_restored': False,
        'engine_poisoned': bool(engine._fatal_update), 'cleanup_errors': [], 'hash_cost': hash_cost,
        'screen_deadline_epoch': screen_deadline, 'evaluation_deadline_epoch': deadline,
        'returned_after_evaluation_deadline': False,
        'private_artifacts': artifacts, 'source_identity': source_identity, 'job_id': job_id,
        'disk_admission': {'free_bytes': free_disk, 'required_bytes': disk_required, 'trainable_bytes': trainable_bytes,
                           'basis': 'four exports plus one staged state and1GiB retained evidence reserve'},
        'public_inference_performed': False, 'public_scoring_performed': False,
        'public_answers_used': False, 'clean_generalization_claimed': False, 'equal_compute_claimed': False,
        'ttt_factor': 'not combined; independent ready0/32 stability workflow',
        'scientific_scope': protocol['scientific_scope'], 'initial_weight_cleanliness_claimed': False,
        'limitations': ['16 held-demo parents are not a clean generalization or goal claim.',
            'A single optimizer update measures a direction, not adequate recipe optimization.',
            'Syntactic source groups are not generator families; adaptive family priority reduces to parent/group difficulty.',
            'Target/positiveCE mainly differ in example weighting; no full RLVE, RAFT or DAPO reproduction.',
            'Counters include attempted/failed work but are not FLOPs or checkpoint recomputation counts.',
            'No uniform-only control was run; adaptive sampling efficiency has not been established.']}
    screen = None; error = None

    screen_saved = False
    persistence_calls, persistence_seconds = 0, 0.

    def persist():
        nonlocal screen_saved, persistence_calls, persistence_seconds
        persistence_started = time.monotonic()
        if screen is not None and not screen_saved:
            evidence = _json_controls(screen)
            write_new(output / 'matched-controls.json', evidence)
            artifacts['matched-controls.json'] = _file(output / 'matched-controls.json', output)
            capture = evidence['capture']
            report['controls'] = {**evidence, 'capture': {**{k: v for k, v in capture.items() if k != 'groups'},
                                                        'group_count': len(capture['groups'])}}
            report['controls']['collection']['distinct_mixed_parents'] = len({g['parent_id'] for g in capture['groups']
                                                        if g['status'] == 'complete' and g['category'] == 'mixed'})
            screen_saved = True
        report['report_persistence'] = {'completed_writes_before_this': persistence_calls,
            'wall_seconds_before_this': persistence_seconds, 'maximum_report_bytes': 4 * 1024**2,
            'current_atomic_write_excluded_from_own_timing': True}
        require(len(canonical(report)) <= 4 * 1024**2, 'owned matched receipt exceeds bounded4MiB')
        atomic_json(output / 'matched-report.json', report)
        persistence_calls += 1
        persistence_seconds += time.monotonic() - persistence_started

    def reset(state, expected):
        restore_state(engine.model, state)
        for parameter in engine.parameters:
            parameter.grad = None
        require(state_digest(adapter_state(engine.model)) == expected, 'exact named-state reset differs')

    def summarize():
        for arm in controls.ARMS:
            result = evaluation['arms'][arm]
            rows = result['records']
            result.update(complete_parents=sum(r['complete'] for r in rows),
                          pass1=sum(r['pass1'] for r in rows), pass2=sum(r['pass2'] for r in rows),
                          valid=sum(r['valid'] for r in rows))
            result['complete'] = result['complete_parents'] == PARENTS
        evaluation['complete'] = all(v['complete'] for v in evaluation['arms'].values())

    persist()
    try:
        # Reproduce the first actual collection dispatch before paying for the
        # rest of the pool. The separate seeded generator leaves collection's
        # draws untouched. This is diagnostic work, never extra training data.
        from .probability_probe import probe
        panel = controls.admit_panel(prepared['training'], prepared['admission'],
            expected_admission_sha256=prepared['pins']['admission_sha256'])
        parent, allocation = controls._Chooser(panel, cfg['seed']).choose()
        example, _ = controls._example(prepared['training'][parent], panel[parent], cfg)
        probe_before, probe_started = meter.snapshot(), time.monotonic()
        raw_probe = None
        try:
            raw_probe = probe(engine, example['prompt_ids'], count=cfg['microbatch'],
                max_new_tokens=cfg['generation_tokens'], deadline=screen_deadline, seed=cfg['seed'])
        except BaseException as caught:
            raw_probe = getattr(caught, 'probability_probe_result', None)
            raise
        finally:
            if raw_probe is not None:
                after_policy = controls.full_policy_sha256(engine, hash_cost)
                tolerance = 0.05 if engine.base_dtype == torch.bfloat16 else 1e-5
                metrics = {key: raw_probe.get(key) for key in ('cached_max_abs_logp_gap', 'full_max_abs_logp_gap')}
                metrics['full_path'] = raw_probe.get('full_metrics')
                gaps = [metrics.get(k) for k in ('cached_max_abs_logp_gap', 'full_max_abs_logp_gap')]
                passed = (raw_probe.get('status') == 'completed' and after_policy == policy_sha
                    and len(raw_probe.get('rows', [])) == len(raw_probe.get('full_replay', [])) == cfg['microbatch']
                    and raw_probe.get('cached_replay', {}).get('status') == 'completed'
                    and 0 < len(raw_probe['cached_replay']['steps']) == len(raw_probe['trace']['steps'])
                    and raw_probe['full_metrics']['tokens'] == sum(r['completion_tokens'] for r in raw_probe['rows'])
                    and raw_probe.get('training_authorized') is False
                    and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= tolerance for v in gaps)
                    and not engine._fatal_update)
                if engine.probability_policy == FP32_HEAD_POLICY:
                    from .precision_contract import stable_probe_admission
                    metrics['additional_paths'], additional_passed = stable_probe_admission(
                        raw_probe, tolerance=tolerance, count=cfg['microbatch'])
                    passed = passed and additional_passed
                evidence = {'format': 'irisx/nvarc-matched-probability-preflight-v1',
                    'protocol': PREFLIGHT, 'parent_id': parent, 'allocation': allocation,
                    'seed': cfg['seed'], 'microbatch': cfg['microbatch'],
                    'prompt_ids_sha256': _sha(example['prompt_ids']),
                    'generation_tokens': cfg['generation_tokens'], 'tolerance': tolerance,
                    'policy_before_sha256': policy_sha, 'policy_after_sha256': after_policy,
                    'engine_poisoned_after': bool(engine._fatal_update),
                    'status': raw_probe.get('status'), 'passed': passed, 'metrics': metrics,
                    'physical': controls._delta(meter.snapshot(), probe_before),
                    'wall_seconds': time.monotonic() - probe_started, 'probe': raw_probe,
                    'used_for_loss': False, 'full_pool_verification_still_required': True}
                if engine.probability_policy != LEGACY_POLICY:
                    evidence['probability_policy'] = engine.probability_policy
                write_new(output / 'matched-probability-preflight.json', evidence)
                artifacts['matched-probability-preflight.json'] = _file(output / 'matched-probability-preflight.json', output)
                report['probability_preflight'] = {k: v for k, v in evidence.items() if k != 'probe'}
                persist()  # Preserve failed measurements before admission.
        if engine._fatal_update:
            raise FatalUpdateError('probability preflight poisoned engine; no collection or update')
        if raw_probe.get('status') == 'deadline':
            raise PhaseDeadline('original screen deadline during probability preflight')
        require(report['probability_preflight']['passed'],
                'probability preflight failed; cached/full paths are not admitted; no collection or update')
        try:
            screen = controls.run_matched_controls(engine, prepared['training'], prepared['admission'],
                expected_admission_sha256=prepared['pins']['admission_sha256'], deadline=screen_deadline, config=cfg)
        except BaseException as caught:
            screen = getattr(caught, 'matched_controls_result', None)
            raise
        persist()
        require(screen.get('anchor_restored') is True and not screen.get('engine_poisoned')
                and not engine._fatal_update, 'restored nonpoisoned screen required before evaluation')
        params = {'context_tokens': cfg['context_tokens'], 'generation_tokens': cfg['generation_tokens'],
                  'evaluation_seed': EVALUATION_SEED, 'retain_token_evidence': True}
        for arm in controls.ARMS:
            state = screen['states'].get(arm)
            if state is None:
                continue
            state_sha = state_digest(state)
            try:
                check_deadline(deadline)
                reset(anchor, anchor_sha); reset(state, state_sha)
                report['exports'][arm] = {'status': 'pending', 'state_sha256': state_sha}
                checkpoint = engine.save_checkpoint(output / 'checkpoints' / arm, origin={
                    'phase': 'pre_public', 'public_ttt_applied': False, 'public_labels_used': False,
                    'workflow': PROTOCOL, 'treatment': arm, 'arm': arm, 'source_identity': source_identity, 'job_id': job_id,
                    'protocol_sha256': report['protocol_sha256'],
                    'admission_sha256': report['admission_sha256'], 'capture_sha256': screen['capture']['seal_sha256'],
                    'one_update_mechanism_screen': True, 'selected': False})
                require(checkpoint['state_sha256'] == state_sha, 'exported named trainables differ')
                report['exports'][arm].update(status='complete', checkpoint=checkpoint)
            except BaseException as caught:
                report['exports'][arm].update(status='deadline' if isinstance(caught, PhaseDeadline) else 'failed',
                                              error=type(caught).__name__)
                raise
            finally:
                reset(anchor, anchor_sha); persist()
            arm_before, arm_started = meter.snapshot(), time.monotonic()
            try:
                for record in evaluation['arms'][arm]['records']:
                    parent = record['parent_id']; task = prepared['development'][parent]
                    record['target_digest'] = digest(task['train'][0]['output'])
                    task_before, task_started = meter.snapshot(), time.monotonic()
                    try:
                        check_deadline(deadline)
                        reset(anchor, anchor_sha); reset(state, state_sha)
                        demos, query, target = loo_example(task, random.Random(0), augment=False, held_index=0)
                        demo_task = {'train': demos}
                        prediction = infer_query(engine, demo_task, query, params, task_id=parent, views=VIEWS, deadline=deadline)
                        verified = verify_prediction(prediction, demo_task, query, params, task_id=parent, views=VIEWS)
                        require(state_digest(adapter_state(engine.model)) == state_sha, 'noTTT inference changed trainables')
                        ranked = prediction['ranked_grids']
                        prediction_path = output / 'predictions' / arm / (parent + '.json')
                        prediction_path.parent.mkdir(parents=True, exist_ok=True)
                        write_new(prediction_path, prediction)
                        prediction_artifact = _file(prediction_path, output)
                        artifacts[prediction_artifact['path']] = prediction_artifact
                        record.update(prediction_artifact=prediction_artifact, verification=verified, complete=prediction['complete'],
                            completed_views=verified['completed_views'], pass1=int(bool(ranked) and ranked[0] == target),
                            pass2=int(target in ranked), valid=bool(ranked), state_sha256=state_sha,
                            status='complete' if prediction['complete'] else 'partial')
                        if not prediction['complete']:
                            raise PhaseDeadline('incomplete fixed heldout views')
                    except BaseException as caught:
                        if record['status'] == 'not_executed':
                            record['status'] = 'deadline' if isinstance(caught, PhaseDeadline) else 'failed'
                        record['error'] = type(caught).__name__
                        raise
                    finally:
                        reset(anchor, anchor_sha)
                        record['anchor_reset_sha256'] = anchor_sha
                        record['physical'] = controls._delta(meter.snapshot(), task_before)
                        record['wall_seconds'] = time.monotonic() - task_started
                        summarize(); persist()
                    audit('matched_heldout_parent', arm=arm, parent_id=parent, complete=record['complete'], pass2=record['pass2'])
            finally:
                reset(anchor, anchor_sha)
                evaluation['arms'][arm]['physical'] = controls._delta(meter.snapshot(), arm_before)
                evaluation['arms'][arm]['wall_seconds'] = time.monotonic() - arm_started
                summarize(); persist()
        all_arms = screen['status'] == 'complete' and all(screen['arms'][a].get('status') == 'complete' for a in controls.ARMS)
        report['returned_after_evaluation_deadline'] = time.time() >= deadline
        report['complete'] = (all_arms and evaluation['complete'] and not report['returned_after_evaluation_deadline']
                              and all(e['status'] == 'complete' for e in report['exports'].values()))
        report['status'] = 'complete' if report['complete'] else 'partial'
        report['ddis_signal_evidence'] = screen['arms']['exact_centered_ddis'].get('updated') is True
        report['ddis_signal_status'] = 'actual_mixed_group_update' if report['ddis_signal_evidence'] else 'no_usable_mixed_update_non_evidence'
        if report['complete']:
            counts = {arm: evaluation['arms'][arm]['pass2'] for arm in controls.ARMS}
            best = max(counts.values())
            winners = [arm for arm in controls.ARMS if counts[arm] == best]
            # A tie between updating arms also keeps anchor: no outcome-based
            # secondary metric/learning-rate choice is introduced after the fact.
            if len(winners) == 1 and best > counts['anchor']:
                report.update(selected_arm=winners[0], candidate_selected=True)
        report['selection_label'] = 'provisional16-parent-mechanism-candidate' if report['candidate_selected'] else 'retain-anchor'
    except PhaseDeadline as caught:
        error = caught
        report.update(status='partial', stop_reason='original_phase_deadline',
                      returned_after_evaluation_deadline=time.time() >= deadline)
    except BaseException as caught:
        error = caught
        report.update(status='failed', error=type(caught).__name__)
        caught.matched_workflow_result = report
        raise
    finally:
        try:
            reset(anchor, anchor_sha)
            require(controls.full_policy_sha256(engine, hash_cost) == policy_sha, 'full official anchor policy not restored')
            report['anchor_restored'] = True
            engine.sync()
        except BaseException as caught:
            engine._fatal_update = True
            report.update(status='failed', complete=False, anchor_restored=False, candidate_selected=False, selected_arm='anchor')
            report['cleanup_errors'].append({'action': 'restore_and_sync', 'error': type(caught).__name__,
                                           'primary_error': type(error).__name__ if error else None})
            caught.matched_workflow_result = report
            if error is None or isinstance(error, PhaseDeadline):
                raise
        finally:
            report['engine_poisoned'] = bool(engine._fatal_update)
            report['returned_after_evaluation_deadline'] = time.time() >= deadline
            if report['status'] == 'complete' and report['returned_after_evaluation_deadline']:
                report.update(status='partial', stop_reason='deadline_during_final_synchronous_cleanup')
            if report['status'] != 'complete' or report['engine_poisoned']:
                report.update(complete=False, candidate_selected=False, selected_arm='anchor', selection_label='retain-anchor')
            summarize()
            report['physical'] = controls._delta(meter.snapshot(), before)
            report['wall_seconds'] = time.monotonic() - started
            screen_hash = (screen or {}).get('hash_cost', {'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.})
            report['full_policy_hash_work'] = {'workflow': dict(hash_cost), 'controls': dict(screen_hash),
                'total': {key: hash_cost[key] + screen_hash[key] for key in hash_cost},
                'scope': 'full-policy streaming hashes; checkpoint/adapter/file hash cost remains in measured wall and export bytes'}
            report['peak_memory'] = {'gpu_measured': engine.device.type == 'cuda',
                'allocated_bytes': torch.cuda.max_memory_allocated(engine.device) if engine.device.type == 'cuda' else None,
                'reserved_bytes': torch.cuda.max_memory_reserved(engine.device) if engine.device.type == 'cuda' else None}
            meter.close(); persist()
            # A bounded atomic report write can itself cross the phase cutoff.
            # Preserve completed model work, but correct timing/selection claims
            # in one final write rather than treating persistence as zero-cost.
            if time.time() >= deadline and not report['returned_after_evaluation_deadline']:
                report['returned_after_evaluation_deadline'] = True
                if report['status'] == 'complete':
                    report.update(status='partial', stop_reason='deadline_during_final_report_persistence')
                report.update(complete=False, candidate_selected=False, selected_arm='anchor', selection_label='retain-anchor')
                persist()
    return report
