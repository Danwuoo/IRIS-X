"""Separated fixed panels, official-training-only loads and optional train admission.

No downloads, provider calls, model imports, or reads occur at import time. Raw
official tasks are never packaged here. Original ARC test fields are discarded.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import time

from .panel_contract import (FORMAT, SEED, TRAIN_FAMILIES, HELDOUT_FAMILIES,
    CANARY_FAMILIES, DENOMINATORS, REAL_EVAL_IDS, REAL_TRAIN_IDS,
    canary_case_ids, preregister_panels, validate_preregistration, solver_case)
from tools.arc_qwen_probe_20261012.protocol import digest, require
from tools.arc_qwen_probe_20261012.data import (
    authored_specs, reference as trained_reference, PROGRAMS, DEVELOPMENT_SOURCES)
from tools.arc_learning_agent_20261011.grid_codec import validate_grid
from tools.arc_learning_agent_20261011.data import (
    create_split_manifest, build_records, build_task_records, verified_program_record, validate_records)
from tools.arc_next_models import digest as task_digest
from src.irisx.arc_nvarc_data import known_variant_group


def reference(family, grid):
    """Independent authored formulas. Never execute generated source on the host."""
    validate_grid(grid)
    if family in TRAIN_FAMILIES:
        result = trained_reference(family, grid)
    elif family == 'pad-zero-border':
        result = [[0] * (len(grid[0]) + 2)] + [[0] + row[:] + [0] for row in grid] + [[0] * (len(grid[0]) + 2)]
    elif family == 'tile-2x2':
        result = [row + row for row in grid] * 2
    elif family == 'shift-right-zero':
        result = [[0] + row[:-1] for row in grid]
    elif family == 'mask-main-diagonal':
        result = [[0 if r == c else x for c, x in enumerate(row)] for r, row in enumerate(grid)]
    elif family == 'crop-inner':
        result = [row[1:-1] for row in grid[1:-1]]
    elif family == 'append-zero-row':
        result = deepcopy(grid) + [[0] * len(grid[0])]
    elif family == 'checkerboard-mask':
        result = [[x if (r + c) % 2 == 0 else 0 for c, x in enumerate(row)] for r, row in enumerate(grid)]
    else:
        raise ValueError('unknown authored transform family')
    return deepcopy(validate_grid(result))


def _grid(key, height, width):
    """Stable SHA256 counter generator, independent of Python random versions."""
    colors = []
    for counter in range((height * width + 31) // 32):
        colors.extend(b % 10 for b in hashlib.sha256(f'{SEED}:{key}:{counter}'.encode()).digest())
    return [colors[r * width:(r + 1) * width] for r in range(height)]


def _authored_task(family, index, scope):
    key = f'{scope}:{family}:{index:02d}'
    demos = []
    for demo, (height, width) in enumerate(((3, 4), (4, 5), (5, 3))):
        grid = _grid(f'{key}:demo:{demo}', height, width)
        demos.append({'input': grid, 'output': reference(family, grid)})
    query = _grid(key + ':query', 4 + index, 4)
    return {'train': demos}, query, reference(family, query)


def _metadata(task_id, family, task, *, kind, role, fixture=False):
    family_id = ('authored-family:' + family) if kind == 'authored' else ('official-parent:' + task_id)
    ancestors = sorted({task_id, family_id}) if kind == 'authored' else [task_id]
    return {'task_id': task_id, 'family_id': family_id, 'parent_ids': [task_id],
        'ancestor_ids': ancestors, 'task_sha256': task_digest(task),
        'variant_group': known_variant_group({**task, 'test': []}),
        'pair_sha256': [task_digest(pair) for pair in task['train']],
        'kind': kind, 'role': role, 'cpu_fixture_only': fixture,
        'original_test_fields_retained': False}


def _case(case_id, scope, family, task, query, source, *, held_out=None):
    demos = deepcopy(task['train'])
    visible = list(range(len(demos)))
    if held_out is not None:
        visible.remove(held_out)
        demos.pop(held_out)
    result = {'case_id': case_id, 'scope': scope, 'family': family, 'demos': demos,
        'query_input': deepcopy(query), 'source': {**deepcopy(source),
            'held_out_demo_index': held_out, 'visible_demo_indices': visible,
            'query_sha256': digest(query)}}
    return solver_case(result)


def _check_root(training_root, inventory):
    root = Path(training_root).absolute()
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
            'regular independently mounted official training root required')
    forbidden = re.compile(r'(?:public[-_]?120|evaluation|(?:^|[-_])eval(?:$|[-_])|answers|solutions)', re.I)
    require(not any(forbidden.search(part) for part in root.parts), 'public/evaluation/answer path forbidden')
    names = {Path(e['path']).name for e in inventory['files']}
    require({p.name for p in root.iterdir()} == names, 'closed pinned 1000-task official training inventory required')
    return root


def load_official_panels(training_root, preregistration=None):
    """Select IDs before reading labels; verify exact upstream blob bytes at runtime."""
    from .panel_contract import inventory_path, INVENTORY_SHA256
    from tools.arc_qwen_probe_20261012.protocol import checked_json
    from tools.arc_next_materials import sanitize_source
    plan = validate_preregistration(preregistration) if preregistration is not None else preregister_panels()
    inventory = checked_json(inventory_path(), INVENTORY_SHA256)
    root = _check_root(training_root, inventory)
    entries = {Path(item['path']).stem: item for item in inventory['files']}
    selected = list(REAL_EVAL_IDS) + list(REAL_TRAIN_IDS)
    # All four exposed parents are retained solely for the historical regression/training manifest.
    selected += [s['task_id'] for s in DEVELOPMENT_SOURCES.values()]
    tasks, receipts = {}, {}
    for key in selected:
        path = root / (key + '.json')
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 ** 2,
                'bounded regular official training task required')
        tasks[key], receipts[key] = sanitize_source(path.read_bytes(), entries[key])
        receipts[key]['sanitized_task_sha256'] = task_digest(tasks[key])
    return {'tasks': tasks, 'receipts': receipts, 'preregistration': plan,
            'cpu_fixture_only': False, 'source_root_verified': True, 'official_training_root': str(root)}


def _fixture_sources():
    """Synthetic tests only. These outputs are never claimed as genuine ARC gold."""
    tasks = {}
    for key in list(REAL_EVAL_IDS) + list(REAL_TRAIN_IDS):
        pairs = []
        for index in range(3):
            grid = _grid(f'fixture:{key}:{index}', 3 + index, 4)
            pairs.append({'input': grid, 'output': deepcopy(grid)})
        tasks[key] = {'train': pairs}
    return {'tasks': tasks, 'receipts': {}, 'preregistration': preregister_panels(),
            'cpu_fixture_only': True, 'source_root_verified': False}


def _fixture_development():
    cases = []
    for case_id, original in DEVELOPMENT_SOURCES.items():
        grids = [_grid(f'fixture:{case_id}:{i}', 3 + i, 4) for i in range(3)]
        pairs = [{'input': g, 'output': deepcopy(g)} for g in grids]
        cases.append({'case_id': case_id, 'source': deepcopy(original), 'demos': pairs[:-1],
                      'query_input': grids[-1], 'target': deepcopy(grids[-1])})
    return {'cases': cases, 'cpu_fixture_only': True}


def _validate_development(development, *, fixture):
    require(type(development) is dict and type(development.get('cases')) is list, 'historical development panel required')
    require([c['case_id'] for c in development['cases']] == list(DEVELOPMENT_SOURCES), 'closed historical development IDs required')
    if not fixture:
        for case in development['cases']:
            expected = DEVELOPMENT_SOURCES[case['case_id']]
            require(case['source'] == expected, 'historical source ancestry changed')
            task = {'train': deepcopy(case['demos']) + [{'input': case['query_input'], 'output': case['target']}]}
            require(task_digest(task) == expected['task_sha256'], 'historical source task content changed')


def _assemble(development, loaded):
    fixture = loaded['cpu_fixture_only']
    _validate_development(development, fixture=fixture)
    plan = validate_preregistration(loaded['preregistration'])
    solver, escrow, canaries, registry = [], {}, {}, {}
    train_tasks, families = {}, {}

    def add(case, target):
        require(case['case_id'] not in escrow and case['case_id'] not in canaries, 'duplicate case ID')
        solver.append(case)
        (canaries if case['scope'] == 'canary' else escrow)[case['case_id']] = deepcopy(validate_grid(target))

    for family, spec in authored_specs().items():
        task_id = 'probe-authored:' + family
        task = {'train': deepcopy(spec['train'])}
        source = _metadata(task_id, family, task, kind='authored', role='optimizer_train')
        registry[task_id] = source
        train_tasks[task_id], families[task_id] = task, task_id
        add(_case('train-control:' + family, 'seen_regression', family, task,
                  task['train'][0]['input'], source, held_out=0), task['train'][0]['output'])
        add(_case('authored-disjoint:' + family, 'seen_regression', family, task, spec['query'], source), spec['target'])
    for old in development['cases']:
        raw_id = old['source']['task_id']
        task_id = ('fixture:' if fixture else '') + raw_id
        task = {'train': deepcopy(old['demos']) + [{'input': old['query_input'], 'output': old['target']}]}
        source = _metadata(task_id, None, task, kind='fixture' if fixture else 'official-training',
                           role='seen_regression', fixture=fixture)
        registry[task_id] = source
        if old['case_id'] == 'training-dev:b1948b0a':
            add(_case(old['case_id'], 'seen_regression', None, task, old['query_input'], source,
                      held_out=len(task['train']) - 1), old['target'])

    for scope, prefix, family_list in (
            ('same_family_query', 'same-family', TRAIN_FAMILIES),
            ('heldout_family', 'heldout-family', HELDOUT_FAMILIES),
            ('canary', 'canary', CANARY_FAMILIES)):
        for family in family_list:
            for index in range(2):
                case_id = f'{prefix}:{family}:{index:02d}'
                task, query, target = _authored_task(family, index, scope)
                task_id = 'portfolio-authored:' + case_id
                source = _metadata(task_id, family, task, kind='authored', role=scope)
                registry[task_id] = source
                add(_case(case_id, scope, family, task, query, source), target)

    real_training_tasks = {}
    require(set(REAL_EVAL_IDS) | set(REAL_TRAIN_IDS) <= set(loaded['tasks']), 'fixed real source parents missing')
    for role, ids in (('real_arc_holdout', REAL_EVAL_IDS), ('real_optimizer_candidate', REAL_TRAIN_IDS)):
        for raw_id in ids:
            task_id = ('fixture:' if fixture else '') + raw_id
            task = deepcopy(loaded['tasks'][raw_id])
            source = _metadata(task_id, None, task, kind='fixture' if fixture else 'official-training', role=role, fixture=fixture)
            registry[task_id] = source
            if role == 'real_arc_holdout':
                last = len(task['train']) - 1
                add(_case('real-arc:' + raw_id, role, None, task, task['train'][last]['input'], source, held_out=last),
                    task['train'][last]['output'])
            else:
                real_training_tasks[task_id] = task
    _check_separation(registry)
    dataset = {'format': FORMAT, 'preregistration': plan, 'solver_cases': solver,
        'target_escrow': escrow, 'canary_targets': canaries, 'source_registry': registry,
        'denominators': deepcopy(DENOMINATORS), 'cpu_fixture_only': fixture,
        'official_source_receipts': deepcopy(loaded['receipts']), 'real_training_tasks': real_training_tasks,
        'official_training_root': loaded.get('official_training_root'),
        'public_answers_used': False, 'original_test_fields_retained': False,
        'phase_two_enabled': False, 'pretraining_cleanliness_claimed': False,
        'freshness': plan['freshness'], 'records': [], 'manifest': None}
    dataset['dataset_sha256'] = digest(dataset)
    validate_dataset(dataset)
    return dataset


def _check_separation(registry):
    require(type(registry) is dict and registry, 'source registry required')
    stores = {'task_sha256': {}, 'variant_group': {}, 'ancestor_ids': {}, 'pair_sha256': {}}
    # Same-family queries share the trained transformation by explicit design.
    def partition(role):
        return 'train-family' if role in ('optimizer_train', 'same_family_query') else role
    for task_id, source in registry.items():
        require(source['task_id'] == task_id and source['parent_ids'] == [task_id], 'changed or unknown parent')
        expected = sorted({task_id, source['family_id']}) if source['kind'] == 'authored' else [task_id]
        require(source['ancestor_ids'] == expected, 'mutated or unknown ancestry')
        role = partition(source['role'])
        for field, store in stores.items():
            values = source[field] if field in ('ancestor_ids', 'pair_sha256') else [source[field]]
            for value in values:
                require(value not in store or store[value] == role, 'cross-split content/variant/ancestor overlap')
                store[value] = role
    require(set(TRAIN_FAMILIES).isdisjoint(HELDOUT_FAMILIES) and set(CANARY_FAMILIES).isdisjoint(TRAIN_FAMILIES + HELDOUT_FAMILIES),
            'transform-family partitions overlap')


def validate_dataset(dataset):
    require(dataset.get('format') == FORMAT, 'portfolio dataset format required')
    require(dataset.get('dataset_sha256') == digest({k: v for k, v in dataset.items() if k != 'dataset_sha256'}), 'dataset digest changed')
    plan = validate_preregistration(dataset['preregistration'])
    fixture = dataset['cpu_fixture_only']
    require(type(fixture) is bool, 'explicit fixture flag required')
    require(dataset['denominators'] == DENOMINATORS, 'fixed denominators changed')
    cases = dataset['solver_cases']
    ids = [c['case_id'] for c in cases]
    require(len(ids) == len(set(ids)) == sum(DENOMINATORS.values()), 'complete fixed panel required')
    require(dict(Counter(c['scope'] for c in cases)) == DENOMINATORS, 'scope denominator differs')
    expected_ids = (['train-control:' + f for f in TRAIN_FAMILIES] + ['authored-disjoint:' + f for f in TRAIN_FAMILIES]
        + ['training-dev:b1948b0a'] + plan['same_family_case_ids'] + plan['heldout_case_ids']
        + canary_case_ids() + ['real-arc:' + key for key in REAL_EVAL_IDS])
    require(set(ids) == set(expected_ids), 'unknown or replaced panel case')
    require(set(dataset['canary_targets']) == set(canary_case_ids()), 'canary target coverage differs')
    require(set(dataset['target_escrow']) == set(ids) - set(canary_case_ids()), 'escrow target coverage differs')
    old_inputs = {digest(pair['input']) for spec in authored_specs().values() for pair in spec['train']}
    fresh_queries = [digest(case['query_input']) for case in cases if case['scope'] in ('same_family_query', 'heldout_family', 'canary')]
    require(not old_inputs.intersection(fresh_queries) and len(fresh_queries) == len(set(fresh_queries)),
            'fresh authored query overlaps an old training input or another fresh query')
    expected_registry = {'probe-authored:' + family for family in TRAIN_FAMILIES}
    expected_registry.update('portfolio-authored:' + case_id for case_id in
        plan['same_family_case_ids'] + plan['heldout_case_ids'] + canary_case_ids())
    expected_registry.update(('fixture:' if fixture else '') + key for key in
        list(REAL_EVAL_IDS) + list(REAL_TRAIN_IDS) + plan['excluded_exposed_ids'])
    require(set(dataset['source_registry']) == expected_registry, 'unknown or missing registered task')
    _check_separation(dataset['source_registry'])
    for case in cases:
        solver_case(case)
        source = case['source']
        metadata = {k: v for k, v in source.items() if k not in ('held_out_demo_index', 'visible_demo_indices', 'query_sha256')}
        require(metadata == dataset['source_registry'].get(source['task_id']), 'case source/ancestry changed or unknown')
        require(source['query_sha256'] == digest(case['query_input']), 'query input changed')
        target = (dataset['canary_targets'] if case['scope'] == 'canary' else dataset['target_escrow'])[case['case_id']]
        validate_grid(target)
        task = {'train': deepcopy(case['demos'])}
        held = source['held_out_demo_index']
        if held is not None:
            require(type(held) is int and 0 <= held <= len(task['train']), 'held-out demo index changed')
            task['train'].insert(held, {'input': deepcopy(case['query_input']), 'output': deepcopy(target)})
        require(source['visible_demo_indices'] == [i for i in range(len(task['train'])) if i != held], 'visible demo indices changed')
        require(task_digest(task) == source['task_sha256'], 'complete source example changed')
        require(known_variant_group({**task, 'test': []}) == source['variant_group'], 'source variant binding changed')
        require([task_digest(pair) for pair in task['train']] == source['pair_sha256'], 'source pair binding changed')
        if case['scope'] == 'real_arc_holdout':
            require(source['task_id'] == ('fixture:' if fixture else '') + case['case_id'].split(':', 1)[1], 'ARC case parent changed')
            require(source['role'] == 'real_arc_holdout', 'ARC holdout role changed')
        if case['scope'] in ('same_family_query', 'heldout_family', 'canary'):
            expected_families = {'same_family_query': TRAIN_FAMILIES, 'heldout_family': HELDOUT_FAMILIES, 'canary': CANARY_FAMILIES}[case['scope']]
            require(case['family'] in expected_families and source['family_id'] == 'authored-family:' + case['family'], 'authored family changed')
            index = int(case['case_id'].rsplit(':', 1)[1])
            expected_task, query, expected_target = _authored_task(case['family'], index, case['scope'])
            require(task == expected_task and query == case['query_input'] and target == expected_target, 'fixed authored example changed')
            require(metadata == _metadata('portfolio-authored:' + case['case_id'], case['family'], expected_task,
                    kind='authored', role=case['scope']), 'authored source ownership changed')
        elif case['scope'] == 'seen_regression' and case['family'] in TRAIN_FAMILIES:
            spec = authored_specs()[case['family']]
            expected_task = {'train': spec['train']}
            require(metadata == _metadata('probe-authored:' + case['family'], case['family'], expected_task,
                    kind='authored', role='optimizer_train'), 'seen authored source changed')
            expected_query = spec['query'] if case['case_id'].startswith('authored-disjoint:') else spec['train'][0]['input']
            require(case['query_input'] == expected_query and target == reference(case['family'], expected_query), 'seen authored example changed')
    require(set(dataset['real_training_tasks']) == {('fixture:' if fixture else '') + key for key in REAL_TRAIN_IDS}, 'real training candidate IDs changed')
    for task_id, task in dataset['real_training_tasks'].items():
        source = dataset['source_registry'][task_id]
        require(source['role'] == 'real_optimizer_candidate' and task_digest(task) == source['task_sha256'], 'training source changed')
    if not fixture:
        # Re-read the pinned source, rather than trusting a caller-rehashed
        # sanitized hash. No raw task bytes are copied into this package.
        trusted = load_official_panels(dataset['official_training_root'], plan)
        require(dataset['official_source_receipts'] == trusted['receipts'], 'official receipt binding changed')
        for task_id, task in trusted['tasks'].items():
            role = 'real_arc_holdout' if task_id in REAL_EVAL_IDS else (
                'real_optimizer_candidate' if task_id in REAL_TRAIN_IDS else 'seen_regression')
            require(dataset['source_registry'][task_id] == _metadata(task_id, None, task,
                    kind='official-training', role=role), 'official source content/ownership differs from pinned blob')
    else:
        trusted = _fixture_sources()
        for raw_id, task in trusted['tasks'].items():
            task_id = 'fixture:' + raw_id
            role = 'real_arc_holdout' if raw_id in REAL_EVAL_IDS else 'real_optimizer_candidate'
            require(dataset['source_registry'][task_id] == _metadata(task_id, None, task,
                    kind='fixture', role=role, fixture=True), 'synthetic fixture source mutated')
    if dataset['records']:
        validate_records(dataset['records'], dataset['manifest'], ())
        approved = {'probe-authored:' + family for family in TRAIN_FAMILIES}
        require(all(r['split'] == 'train' and r['task_id'] in approved for r in dataset['records']), 'evaluation/canary parent entered initial optimizer')
    return {'case_count': len(ids), 'denominators': deepcopy(DENOMINATORS), 'cpu_fixture_only': fixture,
            'records': len(dataset['records']), 'cross_split_known_duplicates': 0}


def build_panel_fixture():
    """Cheap deterministic fixture; never pretends to load official task gold."""
    return _assemble(_fixture_development(), _fixture_sources())


def build_dataset(development, output, deadline, ledger, *, training_root=None, tiny_cpu=False):
    """First release: six authored training parents, separated fixed 63-case panel."""
    from tools.arc_learning_agent_20261011.program_tools import verify_program
    from tools.arc_learning_agent_20261011.budget import atomic_json
    require(type(tiny_cpu) is bool, 'explicit fixture mode required')
    require(training_root is not None or tiny_cpu, 'production requires pinned official training mount')
    loaded = load_official_panels(training_root) if training_root is not None else _fixture_sources()
    if development is None:
        require(tiny_cpu and training_root is None, 'production historical regression panel required')
        development = _fixture_development()
    dataset = _assemble(development, loaded)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    tasks, families, fixed = {}, {}, {'train': [], 'dev': []}
    for family, spec in authored_specs().items():
        key = 'probe-authored:' + family
        tasks[key] = {'train': spec['train']}
        families[key] = key
        fixed['train'].append(key)
    for case in development['cases']:
        key = 'probe-exposed:' + case['case_id']
        tasks[key] = {'train': deepcopy(case['demos']) + [{'input': case['query_input'], 'output': case['target']}]}
        families[key] = key
        fixed['dev'].append(key)
    manifest = create_split_manifest(tasks, family_ids=families, fixed_splits=fixed)
    require(all(manifest['tasks'][key]['split'] == 'train' for key in fixed['train']), 'authored optimizer source demoted by overlap')
    records = [r for r in build_records(tasks, manifest, augmentations=1, seed=1917) if r['split'] == 'train']
    proofs = []
    for family in TRAIN_FAMILIES:
        require(time.monotonic() < deadline, 'dataset reference verification deadline')
        key = 'probe-authored:' + family
        proof = _vm(ledger, 'portfolio-reference-' + family,
            lambda: verify_program(PROGRAMS[family], tasks[key]['train'], out / 'reference-vm', family, deadline=deadline))
        require(proof['all_demos_fit'], 'authored program witness failed bounded verifier')
        # Explicitly preserve the prior six input-only program query prompts.
        prompt_task = {'train': deepcopy(tasks[key]['train']),
                       'test': [{'input': deepcopy(tasks[key]['train'][0]['input'])}]}
        records.append(verified_program_record(key, prompt_task, PROGRAMS[family], proof, manifest))
        proofs.append({'family': family, 'proof': proof})
    dataset.update(records=records, manifest=manifest, reference_proofs=proofs,
                   record_counts=dict(Counter(r['kind'] for r in records)))
    dataset['dataset_sha256'] = digest({k: v for k, v in dataset.items() if k != 'dataset_sha256'})
    validate_dataset(dataset)
    # Separate persisted objects: generation never needs the escrow file.
    atomic_json(out / 'solver-cases.json', dataset['solver_cases'], exclusive=True)
    atomic_json(out / 'target-escrow.json', {'targets': dataset['target_escrow'], 'dataset_sha256': dataset['dataset_sha256']}, exclusive=True)
    atomic_json(out / 'canary-targets.json', dataset['canary_targets'], exclusive=True)
    atomic_json(out / 'preregistration.json', dataset['preregistration'], exclusive=True)
    return dataset


def _vm(ledger, event, operation):
    ledger.reserve(event, {'cpu_checks': 1, 'gas': 200000})
    try:
        result = operation()
        ledger.complete(event, {'cpu_checks': int(result.get('receipt', result).get('dispatched', 0)),
                                'gas': result['gas_charged']})
        return result
    except BaseException as exc:
        if event in ledger.pending:
            ledger.unknown(event, type(exc).__name__)
        raise


def open_target_escrow(dataset, prediction_seal):
    """Release heldout targets only after a complete canonical prediction artifact.

    This is an ordering guard, not an OS security boundary. Callers must not pass
    dataset/escrow to candidate generation, portfolio selection or feasibility.
    """
    import json
    from tools.arc_qwen_probe_20261012.protocol import file_sha
    validate_dataset(dataset)
    seal = prediction_seal
    require(type(seal) is dict and seal.get('sealed') is True, 'sealed prediction receipt required')
    require(seal.get('case_ids') == [case['case_id'] for case in dataset['solver_cases']], 'complete ordered case denominator must be sealed')
    require(type(seal.get('prediction_sha256')) is str and re.fullmatch('[0-9a-f]{64}', seal['prediction_sha256']), 'prediction digest required')
    require('payload' in seal and digest(seal['payload']) == seal['prediction_sha256'], 'sealed prediction payload changed')
    _validate_prediction_payload(dataset, seal['payload'])
    path = Path(seal.get('artifact_path', '')).absolute()
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'regular persisted prediction artifact required')
    require(path.stat().st_size <= 64 * 1024 ** 2, 'bounded prediction artifact required')
    require(file_sha(path) == seal.get('artifact_sha256'), 'persisted prediction artifact digest changed')
    require(json.loads(path.read_bytes()) == seal['payload'], 'persisted predictions differ from sealed payload')
    return deepcopy(dataset['target_escrow'])


def _validate_prediction_payload(dataset, payload):
    from .selection import verify_selection_seal, source_digest
    from .protocol import PROTOCOL
    from tools.arc_learning_agent_20261011.grid_codec import decode_grid, grid_messages, encode_grid
    expected = {'format', 'case_ids', 'candidate_order', 'denominators',
                'candidate_predictions', 'selection', 'heldout_targets_accessed'}
    require(type(payload) is dict and set(payload) == expected, 'complete closed prediction payload required')
    cases = dataset['solver_cases']
    ids = [case['case_id'] for case in cases]
    candidates = ['base', 'grid8', 'grid16', 'program8', 'program16']
    require(payload['format'] == 'irisx/qwen-all-candidate-predictions-v1' and
            payload['case_ids'] == ids and payload['candidate_order'] == candidates and
            payload['denominators'] == DENOMINATORS and payload['heldout_targets_accessed'] is False,
            'fixed prediction payload identity/denominators differ')
    observations = payload['candidate_predictions']
    require(type(observations) is dict and set(observations) == set(candidates), 'all five checkpoint observations required')
    indexed = {}
    for candidate in candidates:
        observation = observations[candidate]
        require(type(observation) is dict and observation.get('candidate_id') == candidate and
                type(observation.get('complete')) is bool and observation.get('heldout_targets_accessed') is False,
                'closed candidate identity and pre-score state required')
        checkpoint = observation.get('checkpoint')
        require(type(checkpoint) is dict and type(checkpoint.get('available')) is bool and
                checkpoint.get('candidate_id') == candidate, 'sealed checkpoint slot identity required')
        if checkpoint['available']:
            require(set(checkpoint) == {'available', 'candidate_id', 'manifest_sha256', 'state_sha256',
                'adapter_sha256', 'branch_id', 'update'}, 'closed persisted checkpoint identity required')
            update = 0 if candidate == 'base' else int(candidate[-2:] if candidate.endswith('16') else candidate[-1])
            branch = 'program_lora' if candidate.startswith('program') else 'grid_lora'
            require(checkpoint['update'] == update and checkpoint['branch_id'] == branch, 'checkpoint branch/update slot differs')
            for key in ('manifest_sha256', 'state_sha256', 'adapter_sha256'):
                require(type(checkpoint[key]) is str and re.fullmatch('[0-9a-f]{64}', checkpoint[key]), 'checkpoint digest required')
        else:
            require(set(checkpoint) == {'available', 'candidate_id', 'manifest_sha256'} and
                    checkpoint['manifest_sha256'] == digest({'checkpoint': candidate, 'omitted': True}),
                    'explicit immutable checkpoint omission identity required')
        rows = observation.get('rows')
        require(type(rows) is list and [row.get('case_id') for row in rows] == ids,
                'complete ordered checkpoint by case prediction rows required')
        indexed[candidate] = dict(zip(ids, rows))
        for case, row in zip(cases, rows):
            require(row.get('scope') == case['scope'] and type(row.get('row_complete')) is bool,
                    'prediction scope/completion changed')
            require(type(row.get('program_all_demos_fit')) is bool, 'explicit program demo-fit state required')
            if not checkpoint['available']:
                require(row.get('grid_prediction') is None and row.get('program_prediction') is None and
                        row['row_complete'] is False, 'unavailable checkpoint cannot supply predictions')
            for kind in ('grid', 'program'):
                require(kind + '_prediction' in row and type(row.get(kind + '_generation')) is dict,
                        'both representation predictions or omission placeholders required')
                if row[kind + '_prediction'] is not None:
                    validate_grid(row[kind + '_prediction'])
            generation = row['grid_generation']
            predicted = None
            if generation.get('valid') is True:
                try:
                    predicted = decode_grid(generation.get('text'))
                except ValueError:
                    pass
            require(predicted == row['grid_prediction'], 'sealed grid prediction differs from generation')
    selection = payload['selection']
    require(type(selection) is dict and type(selection.get('selection_sha256')) is str, 'selection seal required')
    selected = verify_selection_seal(selection, selection['selection_sha256'], digest(PROTOCOL))
    decisions = selected['decisions']
    require({decision['task_id'] for decision in decisions} == set(ids) and len(decisions) == len(ids),
            'all fixed task portfolio decisions required before escrow')
    by_id = {case['case_id']: case for case in cases}
    for decision in decisions:
        case = by_id[decision['task_id']]
        require(decision['inputs']['task'] == {'task_id': case['case_id'], 'demos': case['demos'],
                'query_input': case['query_input']}, 'selection task differs from registered solver case')
        for candidate in decision['inputs']['candidates']:
            row = indexed[candidate['candidate_id']][case['case_id']]
            require(candidate['checkpoint_sha256'] == observations[candidate['candidate_id']]['checkpoint']['manifest_sha256'],
                    'selection checkpoint differs from sealed candidate identity')
            query = candidate['query']
            prediction = query['output'] if query is not None and query['status'] == 'valid' else None
            require(prediction == row['program_prediction'], 'program selection differs from sealed prediction')
            if candidate['generation_status'] == 'valid':
                require(row['program_generation'].get('valid') is True and
                        candidate['source_sha256'] == source_digest(row['program_generation']['text']),
                        'selection source differs from sealed generation')
    for ranking in selected['rankings']:
        require(ranking['approved_canary_ids'] == sorted(canary_case_ids()) and ranking['minimum_canaries'] == 8,
                'complete fixed eight-canary ranking required')
        branch = ranking['branch']
        expected_rows = []
        for update in (0, 8, 16):
            candidate = 'base' if update == 0 else branch + str(update)
            for case_id in sorted(canary_case_ids()):
                row = indexed[candidate][case_id]
                case = by_id[case_id]
                target = dataset['canary_targets'][case_id]
                item = {'branch': branch, 'scope': 'canary', 'case_id': case_id, 'checkpoint_update': update}
                if branch == 'grid':
                    prediction = row['grid_prediction']
                    score = row.get('canary_grid_score')
                    nll = None
                    if score and score.get('valid') is True:
                        nll = {k: score[k] for k in ('nll_sum', 'token_count', 'example_sha256')}
                        require(nll['example_sha256'] == digest({'messages': grid_messages(case['demos'], case['query_input']),
                            'completion': encode_grid(target)}), 'canary NLL example binding changed')
                    item.update(grid_exact=prediction == target,
                        grid_shape_correct=prediction is not None and (len(prediction), len(prediction[0])) == (len(target), len(target[0])),
                        grid_valid=prediction is not None, grid_nll=nll)
                else:
                    item.update(program_exact=row['program_prediction'] == target,
                        program_all_demos_fit=row['program_all_demos_fit'], program_valid_query=row['program_prediction'] is not None)
                expected_rows.append(item)
        require(ranking['input_rows'] == expected_rows, 'canary ranking differs from sealed predictions/scores')


def prepare_real_training(dataset, *, witnesses=()):
    """Optional phase-two data only; does not enable training or create witnesses.

    A witness is {task_id, source, proof}: proof must be a real persisted bounded
    verifier result on exactly this training parent's demonstrations. Candidate
    generation must receive this parent only. Demo fit is not independent proof
    of a correct transformation and is explicitly not called a gold program.
    """
    validate_dataset(dataset)
    tasks = deepcopy(dataset['real_training_tasks'])
    fixed = {'train': list(tasks), 'dev': []}
    # Dev anchors enforce known-variant separation in the existing training API.
    for case in dataset['solver_cases']:
        if case['scope'] not in ('canary', 'heldout_family', 'real_arc_holdout'):
            continue
        task_id = case['source']['task_id']
        task = {'train': deepcopy(case['demos'])}
        # Visible demonstrations suffice for dev anchors. No heldout target is
        # opened to prepare training; full-task duplicates were checked above.
        tasks[task_id] = task
        fixed['dev'].append(task_id)
    families = {key: dataset['source_registry'][key]['family_id'] for key in tasks}
    manifest = create_split_manifest(tasks, family_ids=families, fixed_splits=fixed)
    require(not manifest['train_to_dev_component_demotions'], 'real training parent overlaps canary/heldout; no replacements allowed')
    records = []
    for key in fixed['train']:
        # A heldout task may have one visible demo. Do not generate dev records
        # at all, and never reconstruct its missing pair from the target escrow.
        for record in build_task_records(key, tasks[key]['train'], augmentations=1, seed=1917):
            record['family_id'] = manifest['tasks'][key]['family_id']
            record['record_id'] = task_digest({k: v for k, v in record.items() if k != 'record_id'})
            records.append(record)
    for witness in witnesses:
        require(type(witness) is dict and set(witness) == {'task_id', 'source', 'proof'}, 'closed candidate witness required')
        key = witness['task_id']
        require(key in fixed['train'], 'program candidate from unknown/canary/evaluation parent')
        records.append(verified_program_record(key, tasks[key], witness['source'], witness['proof'], manifest))
    admission = validate_records(records, manifest, ())
    return {'enabled': False, 'records': records, 'manifest': manifest, 'admission': admission,
            'parent_ids': fixed['train'], 'parent_denominator': 32,
            'record_counts': dict(Counter(r['kind'] for r in records)),
            'program_target_policy': 'candidate-derived demo-fit only; no reference gold',
            'requires_source_bound_budget_plan': True, 'cpu_fixture_only': dataset['cpu_fixture_only']}
