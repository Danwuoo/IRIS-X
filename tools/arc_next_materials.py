"""Explicit owner-only public material preparation; imports are inert.

Only pinned official public training tasks and model artifacts are downloaded.
The training source is split by task identity before any labels are inspected.
No Kaggle, GCP, billing, credential, or submission operation is implemented.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ARC_COMMIT = 'f3283f727488ad98fe575ea6a5ac981e4a188e49'
SPLIT_SEED = 'irisx-arc-next-training-groups-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('A fresh material destination is required: ' + str(path))
    path.write_bytes(canonical(value) + b'\n')


def groups(inventory, *, training_count=32, development_count=4):
    if inventory.get('commit') != ARC_COMMIT or inventory.get('evaluation_paths_included') is not False:
        raise ValueError('Pinned public training-only inventory required')
    files = inventory.get('files')
    if not isinstance(files, list) or len(files) != 1000:
        raise ValueError('Complete pinned 1000-task training inventory required')
    by_id = {}
    for item in files:
        path = item['path']
        if not re.fullmatch(r'data/training/[0-9a-f]{8}\.json', path):
            raise ValueError('Only official training paths are eligible')
        task_id = Path(path).stem
        if task_id in by_id or not re.fullmatch('[0-9a-f]{40}', item['git_blob_sha1']):
            raise ValueError('Duplicate identity or invalid blob binding')
        by_id[task_id] = item
    ranked = sorted(by_id, key=lambda value: hashlib.sha256((SPLIT_SEED + value).encode()).hexdigest())
    if type(training_count) is not int or not 2 <= training_count <= 800:
        raise ValueError('training_count must be 2..800')
    if type(development_count) is not int or not 1 <= development_count <= 200:
        raise ValueError('development_count must be 1..200')
    return {'format': 'irisx/arc-next-task-groups-v1', 'seed': SPLIT_SEED,
            'source_commit': ARC_COMMIT, 'inventory_sha256': digest(inventory),
            'training_ids': ranked[:training_count],
            'development_ids': ranked[800:800 + development_count],
            'unused_training_ids': ranked[training_count:800],
            'unused_development_ids': ranked[800 + development_count:],
            'split_before_label_read': True,
            'source_files': {key: by_id[key] for key in ranked[:training_count] + ranked[800:800 + development_count]}}


def grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30 or
            type(value[0]) is not list or not 1 <= len(value[0]) <= 30 or
            any(type(row) is not list or len(row) != len(value[0]) or
                any(type(cell) is not int or not 0 <= cell <= 9 for cell in row) for row in value)):
        raise ValueError('Legal ARC grid required')
    return [row[:] for row in value]


def sanitize_source(body, expected):
    if len(body) != expected['bytes']:
        raise ValueError('Pinned source size differs')
    blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    if blob != expected['git_blob_sha1']:
        raise ValueError('Pinned upstream Git blob differs')
    task = json.loads(body)
    if type(task) is not dict or set(task) != {'train', 'test'}:
        raise ValueError('Official task envelope differs')
    # Deliberately do not inspect or retain any original test fields.
    rows = task['train']
    if type(rows) is not list or len(rows) < 2:
        raise ValueError('At least two demonstration pairs required; no automatic replacement task')
    demos = []
    for row in rows:
        if type(row) is not dict or set(row) != {'input', 'output'}:
            raise ValueError('Demonstration schema differs')
        demos.append({'input': grid(row['input']), 'output': grid(row['output'])})
    return {'train': demos}, {'git_blob_sha1': blob, 'sha256': hashlib.sha256(body).hexdigest(),
                             'bytes': len(body), 'original_test_fields_retained': False}


def materialize_training(inventory, destination, *, enabled=False,
                         training_count=32, development_count=4, fetch=None):
    if enabled is not True:
        return {'status': 'disabled', 'network_calls': 0}
    destination = Path(destination)
    selection = groups(inventory, training_count=training_count, development_count=development_count)
    if destination.exists():
        return verify_prepared_training(inventory, destination, training_count=training_count, development_count=development_count)
    # Network code is deliberately isolated from all solver/trainer entry points.
    if fetch is None:
        from urllib.request import urlopen
        def fetch(url):
            with urlopen(url, timeout=60) as response:
                return response.read()
    train, challenges, solutions, receipts = {}, {}, {}, {}
    for task_id, item in selection['source_files'].items():
        url = f'https://raw.githubusercontent.com/arcprize/ARC-AGI-2/{ARC_COMMIT}/' + item['path']
        body = fetch(url)
        demos, receipts[task_id] = sanitize_source(body, item)
        train[task_id] = demos
        if task_id in selection['development_ids']:
            # A development test is the final TRAINING demonstration of a
            # different task group. No original public-evaluation or test truth.
            challenges[task_id] = {'train': demos['train'][:-1],
                                  'test': [{'input': demos['train'][-1]['input']}]}
            solutions[task_id] = [demos['train'][-1]['output']]
    destination.mkdir(parents=True)
    write_json(destination / 'task-groups.json', selection)
    write_json(destination / 'train-demonstrations.json', train)
    write_json(destination / 'development-challenges.json', challenges)
    write_json(destination / 'evaluator' / 'development-solutions.json', solutions)
    write_json(destination / 'source-receipts.json', receipts)
    from tools.arc_next_training import write_training_manifest
    write_training_manifest(destination / 'train-demonstrations.json',
                            selection['training_ids'] + selection['development_ids'],
                            destination / 'training-manifest.json', source_revision=ARC_COMMIT,
                            train_task_ids=selection['training_ids'], dev_task_ids=selection['development_ids'])
    return {'status': 'prepared', 'training_tasks': len(selection['training_ids']), 'development_tasks': len(challenges),
            'source_commit': ARC_COMMIT, 'material_sha256': digest(receipts),
            'development_is': 'held-out public-training task demonstrations; not ARC-AGI-2 public evaluation',
            'source_test_answers_retained': False}


def verify_prepared_training(inventory,destination,*,training_count=32,development_count=4):
    destination=Path(destination)
    expected=groups(inventory,training_count=training_count,development_count=development_count)
    if json.loads((destination/'task-groups.json').read_bytes())!=expected:
        raise ValueError('Existing data split differs; use a separate fresh material directory')
    from tools.arc_next_training import load_training_material
    tasks,manifest=load_training_material(destination/'train-demonstrations.json',destination/'training-manifest.json')
    if set(manifest['task_partition']['train'])!=set(expected['training_ids']) or set(manifest['task_partition']['dev'])!=set(expected['development_ids']):
        raise ValueError('Existing training partition differs')
    challenges={key:{'train':tasks[key]['train'][:-1],'test':[{'input':tasks[key]['train'][-1]['input']}]} for key in expected['development_ids']}
    solutions={key:[tasks[key]['train'][-1]['output']] for key in expected['development_ids']}
    if json.loads((destination/'development-challenges.json').read_bytes())!=challenges or json.loads((destination/'evaluator/development-solutions.json').read_bytes())!=solutions:
        raise ValueError('Existing derived development files differ')
    receipts=json.loads((destination/'source-receipts.json').read_bytes())
    if set(receipts)!=set(expected['source_files']) or any(receipts[key]['git_blob_sha1']!=v['git_blob_sha1'] or receipts[key]['bytes']!=v['bytes'] for key,v in expected['source_files'].items()):
        raise ValueError('Existing source provenance differs')
    return {'status':'verified-existing','network_calls':0,'training_tasks':len(expected['training_ids']),'development_tasks':len(expected['development_ids'])}


def materialize_model(model_key, destination, *, enabled=False):
    if type(enabled) is not bool:raise ValueError('Boolean owner preparation switch required')
    if enabled is not True:
        return {'status': 'disabled', 'network_calls': 0, 'model_downloaded': False}
    from tools.arc_next_models import MODEL_CANDIDATES, PINNED_FILES, write_material_manifest, validate_material
    from huggingface_hub import snapshot_download
    model = MODEL_CANDIDATES[model_key]
    destination = Path(destination)
    intent={'model_key':model_key,'repository':model['repository'],'revision':model['revision'],
            'expected_files':PINNED_FILES[model_key]}
    intent_path=destination/'irisx-download-intent.json'
    if destination.exists():
        if (destination/'irisx-model-material.json').is_file():
            validate_material(destination,model_key,destination/'irisx-model-material.json')
            return {'status':'verified-existing','model_key':model_key,'network_calls':0,'model_downloaded':False}
        if not intent_path.is_file() or json.loads(intent_path.read_bytes())!=intent:
            raise ValueError('Existing model directory lacks the exact same download intent; use a fresh directory')
    else:
        destination.mkdir(parents=True);write_json(intent_path,intent)
    # A failed public transfer may resume only its exact pinned download intent.
    # Completed verified materials never get overwritten or changed by this helper.
    snapshot_download(repo_id=model['repository'], revision=model['revision'],
                      local_dir=str(destination), token=False,
                      allow_patterns=list(PINNED_FILES[model_key]),
                      ignore_patterns=['optimizer*', 'training_args*', '*.bin', '*.pt', '*.pth'])
    source_root=Path(__file__).resolve().parents[1]/'research/arc-next-line'
    source_lock=json.loads((source_root/'model-source-lock.json').read_bytes())
    candidate=next(c for c in source_lock['candidates'] if c['model_key']==model_key)
    for item in candidate.get('supplemental_artifacts',[]):
        if item['path']!='LICENSE':raise ValueError('Unknown supplemental artifact')
        body=(source_root/'licenses'/(model_key+'-LICENSE.txt')).read_bytes()
        if len(body)!=item['size'] or hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise ValueError('Pinned bundled license differs')
        target=destination/'LICENSE'
        if target.exists():
            if target.read_bytes()!=body:raise ValueError('Existing source license differs')
        else:target.write_bytes(body)
    write_material_manifest(destination, model_key, destination / 'irisx-model-material.json')
    validate_material(destination,model_key,destination/'irisx-model-material.json')
    return {'status': 'prepared', 'model_key': model_key, 'manifest': str(destination / 'irisx-model-material.json'),
            'revision': model['revision'], 'model_downloaded': True}
