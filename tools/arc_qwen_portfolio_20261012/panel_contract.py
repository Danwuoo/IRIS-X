"""Preregistered, target-blind panel membership. Importing performs no I/O."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

from tools.arc_qwen_probe_20261012.protocol import checked_json, digest, require
from tools.arc_qwen_probe_20261012.data import DEVELOPMENT_SOURCES, PROGRAMS

FORMAT = 'irisx/qwen14b-portfolio-panels-v1'
SEED = 'irisx-qwen-portfolio-20261012-panels-v1'
INVENTORY_SHA256 = '53fc35f54fa1b8a29403c5ede3e3880e8588c40c75a4a5783692a9a13a3e95cb'
SOURCE_COMMIT = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'
TRAIN_FAMILIES = tuple(PROGRAMS)
HELDOUT_FAMILIES = ('pad-zero-border', 'tile-2x2', 'shift-right-zero')
CANARY_FAMILIES = ('mask-main-diagonal', 'crop-inner', 'append-zero-row', 'checkerboard-mask')
DENOMINATORS = {'seen_regression': 13, 'same_family_query': 12,
                'heldout_family': 6, 'canary': 8, 'real_arc_holdout': 24}
SOLVER_FIELDS = {'case_id', 'scope', 'family', 'demos', 'query_input', 'source'}
SOURCE_FIELDS = {'task_id', 'family_id', 'parent_ids', 'ancestor_ids', 'task_sha256',
                 'variant_group', 'pair_sha256', 'kind', 'role', 'cpu_fixture_only',
                 'original_test_fields_retained', 'held_out_demo_index',
                 'visible_demo_indices', 'query_sha256'}
REAL_EVAL_IDS = ('93b581b8', '5587a8d0', '42f14c03', '94414823', '9edfc990', 'e0fb7511',
    'e619ca6e', '31adaf00', '045e512c', 'd017b73f', '8d510a79', '90347967', 'cad67732',
    'e6721834', 'b25e450b', '91413438', 'd23f8c26', '770cc55f', '22425bda', '48d8fb45',
    '49d1d64f', '36d67576', '0a1d4ef5', '575b1a71')
REAL_TRAIN_IDS = ('15663ba9', 'd94c3b52', '810b9b61', '2ccd9fef', '5d588b4d', '5833af48',
    'ac6f9922', '0ca9ddb6', '4c5c2cf0', 'feca6190', 'dc2aa30b', '54d9e175', '12eac192',
    '58c02a16', '98cf29f8', 'cfb2ce5a', '72ca375d', '3979b1a8', 'b8cdaf2b', 'c64f1187',
    'af726779', '9def23fe', 'cd3c21df', 'f0afb749', '662c240a', 'a8610ef7', 'bc4146bd',
    '963e52fc', '8e1813be', '9841fdad', 'f28a3cbb', '1b59e163')


def inventory_path():
    return Path(__file__).resolve().parents[2] / 'research/arc-next-line/training-source-inventory.json'


def canary_case_ids():
    return [f'canary:{family}:{index:02d}' for family in CANARY_FAMILIES for index in range(2)]


def preregister_panels(path=None):
    """Read inventory metadata only: no task bytes, model outputs, or target lengths."""
    from tools.arc_next_materials import groups
    inventory = checked_json(path or inventory_path(), INVENTORY_SHA256)
    fixed = groups(inventory, training_count=800, development_count=200)
    exposed = {source['task_id'] for source in DEVELOPMENT_SOURCES.values()}
    rank = lambda ids: sorted(ids, key=lambda key: hashlib.sha256((SEED + ':' + key).encode()).hexdigest())
    evaluation = rank(set(fixed['development_ids']) - exposed)[:24]
    training = rank(fixed['training_ids'])[:32]
    require(evaluation == list(REAL_EVAL_IDS) and training == list(REAL_TRAIN_IDS), 'preregistered ARC IDs differ')
    selected = set(evaluation + training)
    result = {'format': FORMAT, 'seed': SEED, 'inventory_sha256': INVENTORY_SHA256,
        'source_repository': 'arcprize/ARC-AGI-2', 'source_commit': SOURCE_COMMIT,
        'source_url': inventory['source_url'], 'split_before_task_read': True,
        'historical_split_preserved': True, 'real_evaluation_ids': evaluation,
        'real_training_ids': training, 'excluded_exposed_ids': sorted(exposed),
        'source_entries': {Path(item['path']).stem: deepcopy(item) for item in inventory['files']
                           if Path(item['path']).stem in selected},
        'denominators': deepcopy(DENOMINATORS), 'canary_case_ids': canary_case_ids(),
        'same_family_case_ids': [f'same-family:{family}:{i:02d}' for family in TRAIN_FAMILIES for i in range(2)],
        'heldout_case_ids': [f'heldout-family:{family}:{i:02d}' for family in HELDOUT_FAMILIES for i in range(2)],
        'selection_policy': 'fixed SHA256 rank; no substitutions, outcome filters or target-length filters',
        'freshness': 'authored from fixed hashes without selecting on v18 outputs; no pretraining-cleanliness claim',
        'independence_limit': 'declared transforms/parents plus known D4/color/demo-order variants; not semantic proof',
        'real_arc_family_independence_claimed': False,
        'stage_two': {'enabled_by_default': False, 'parents': 32,
                      'program_targets': 'candidate-derived persisted all-demo-fit proofs only; no gold programs'}}
    result['preregistration_sha256'] = digest(result)
    return result


def validate_preregistration(value):
    require(value == preregister_panels(), 'unknown or mutated panel preregistration')
    return value


def solver_case(case):
    """Closed projection, never pass an escrow-bearing dataset to generation."""
    require(type(case) is dict and set(case) == SOLVER_FIELDS, 'closed target-free solver case required')
    require(type(case['source']) is dict and set(case['source']) == SOURCE_FIELDS,
            'closed target-free source metadata required')
    source = case['source']
    for field in ('case_id', 'scope'):
        require(type(case[field]) is str and 0 < len(case[field]) <= 256, 'bounded case label required')
    require(case['family'] is None or type(case['family']) is str and 0 < len(case['family']) <= 128, 'bounded family label required')
    for field in ('task_id', 'family_id', 'kind', 'role'):
        require(type(source[field]) is str and 0 < len(source[field]) <= 256, 'bounded source label required')
    for field in ('parent_ids', 'ancestor_ids'):
        require(type(source[field]) is list and 1 <= len(source[field]) <= 8 and
                all(type(x) is str and 0 < len(x) <= 256 for x in source[field]), 'bounded lineage IDs required')
    for field in ('task_sha256', 'variant_group', 'query_sha256'):
        require(type(source[field]) is str and re.fullmatch('[0-9a-f]{64}', source[field]), 'source digest required')
    require(type(source['pair_sha256']) is list and 1 <= len(source['pair_sha256']) <= 100 and
            all(type(x) is str and re.fullmatch('[0-9a-f]{64}', x) for x in source['pair_sha256']), 'bounded pair digests required')
    held = source['held_out_demo_index']
    require(held is None or type(held) is int and 0 <= held < 100, 'valid heldout index required')
    require(type(source['visible_demo_indices']) is list and 1 <= len(source['visible_demo_indices']) <= 100 and
            all(type(i) is int and 0 <= i < 100 for i in source['visible_demo_indices']), 'bounded visible indices required')
    require(type(source['cpu_fixture_only']) is bool and source['original_test_fields_retained'] is False,
            'explicit sanitized source flags required')
    from tools.arc_learning_agent_20261011.grid_codec import validate_task
    validate_task({'train': case['demos'], 'test': [{'input': case['query_input']}]})
    require(case['scope'] in DENOMINATORS, 'unknown panel scope')
    return deepcopy(case)


def context_eligibility(cases, native_model, *, grid_output_cap=256, program_output_cap=256,
                        context_limit=2048):
    """Prompt-only eligibility, identical across branches; never inspect escrow.

    Every fixed case remains in the denominator. A representation either reserves
    its complete fixed output budget or is wholly excluded; no truncation.
    """
    from tools.arc_learning_agent_20261011.grid_codec import grid_messages, program_messages
    for cap in (grid_output_cap, program_output_cap, context_limit):
        require(type(cap) is int and cap > 0, 'positive integer token bounds required')
    rows = []
    for raw in cases:
        case = solver_case(raw)
        task = {'train': case['demos'], 'test': [{'input': case['query_input']}]}
        representations = {}
        for kind, messages, cap in (
                ('grid', grid_messages(case['demos'], case['query_input']), grid_output_cap),
                ('program', program_messages(task), program_output_cap)):
            try:
                _, ids = native_model._prompt(messages)
                count = len(ids)
                eligible = count + cap <= context_limit
                reason = None if eligible else 'whole-example prompt plus fixed output reservation exceeds context'
            except ValueError as exc:
                if not any(word in str(exc).lower() for word in ('context', 'prompt', 'length')):
                    raise
                count, eligible, reason = None, False, str(exc)
            representations[kind] = {'prompt_tokens': count, 'output_cap': cap,
                                      'eligible': eligible, 'exclusion_reason': reason}
        rows.append({'case_id': case['case_id'], 'scope': case['scope'], 'representations': representations})
    return {'format': 'irisx/portfolio-prompt-only-eligibility-v1', 'rows': rows,
            'fixed_denominator': len(rows), 'target_inspected': False, 'truncation': False,
            'selection_or_replacement_allowed': False,
            'excluded_case_ids': {kind: [r['case_id'] for r in rows if not r['representations'][kind]['eligible']]
                                  for kind in ('grid', 'program')}}
