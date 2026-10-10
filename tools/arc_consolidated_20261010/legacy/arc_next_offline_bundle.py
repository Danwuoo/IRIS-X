"""Hash-closed local Dataset inputs for the separately versioned offline pilot.

No network, installation, model import, provider call, or GPU operation exists
here. The notebook authenticates this module's bytes before importing it.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

FORMAT = 'irisx/arc-next-offline-runtime-dataset-v1'
DATA_FILES = ('train-demonstrations.json', 'training-manifest.json',
              'development-challenges.json', 'evaluator/development-solutions.json',
              'source-receipts.json', 'task-groups.json')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_file(root, member):
    root = Path(root)
    part = Path(member)
    if not isinstance(member, str) or not member or part.is_absolute() or '..' in part.parts or '\\' in member:
        raise ValueError('Safe relative Dataset member required')
    target = root / part
    if not target.is_file() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise ValueError('Regular non-symlink Dataset member required: ' + member)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Dataset member escaped its root')
    return target


def validate_reference(reference):
    if not isinstance(reference, str) or not re.fullmatch(r'danielwuu/[a-z0-9][a-z0-9-]+/[1-9][0-9]*', reference):
        raise ValueError('An exact owner/slug/numeric-version Dataset reference is required')
    return reference


def resolve_mount(reference, *, input_root='/kaggle/input', explicit_root=None):
    """No wildcard/latest discovery. Only explicit root or two known Kaggle layouts."""
    validate_reference(reference)
    owner, slug, version = reference.split('/')
    if explicit_root is not None:
        candidates = [Path(explicit_root)]
    else:
        parent = Path(input_root)
        candidates = [parent / 'datasets' / owner / slug, parent / slug]
    found = [p for p in candidates if p.is_dir()]
    if len(found) != 1:
        raise ValueError('Exactly one explicit Dataset mount is required: ' + reference)
    root = found[0]
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError('Dataset mount may not be a symlink')
    return root


def verify_runtime(root, expected_manifest_sha256):
    root = Path(root)
    path = safe_file(root, 'bundle-manifest.json')
    if not re.fullmatch('[0-9a-f]{64}', str(expected_manifest_sha256)) or sha_file(path) != expected_manifest_sha256:
        raise ValueError('Runtime Dataset manifest does not match the notebook pin')
    manifest = json.loads(path.read_bytes())
    if manifest.get('format') != FORMAT or not re.fullmatch('[0-9a-f]{40}', manifest.get('source_commit', '')):
        raise ValueError('Versioned runtime source identity required')
    entries = manifest.get('files')
    if not isinstance(entries, dict) or not entries:
        raise ValueError('Closed nonempty runtime file inventory required')
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('Runtime Dataset may not contain symlinks')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(entries) | {'bundle-manifest.json'}:
        raise ValueError('Runtime Dataset has missing or unexpected files')
    for name, entry in entries.items():
        file = safe_file(root, name)
        if file.stat().st_size != entry['bytes'] or sha_file(file) != entry['sha256']:
            raise ValueError('Runtime Dataset file changed: ' + name)
    if manifest.get('contains_model_weights') is not False or manifest.get('contains_wheels') is not False:
        raise ValueError('Code Dataset must remain independently versioned and lightweight')
    return manifest


def verify_runtime_training(inventory, root):
    """Validate training/challenge partition without semantically opening evaluator answers."""
    from tools.arc_next_materials import groups
    from tools.arc_next_training import load_training_material
    root = Path(root)
    expected = groups(inventory, training_count=32, development_count=4)
    if json.loads((root / 'task-groups.json').read_bytes()) != expected:
        raise ValueError('Pinned task-group selection differs')
    tasks, manifest = load_training_material(root / 'train-demonstrations.json', root / 'training-manifest.json')
    if set(manifest['task_partition']['train']) != set(expected['training_ids']) or set(manifest['task_partition']['dev']) != set(expected['development_ids']):
        raise ValueError('Training/development partition differs')
    challenges = {key: {'train': tasks[key]['train'][:-1], 'test': [{'input': tasks[key]['train'][-1]['input']}]} for key in expected['development_ids']}
    if json.loads((root / 'development-challenges.json').read_bytes()) != challenges:
        raise ValueError('Development challenges differ from source demonstrations')
    receipts = json.loads((root / 'source-receipts.json').read_bytes())
    if set(receipts) != set(expected['source_files']) or any(receipts[key]['git_blob_sha1'] != value['git_blob_sha1'] or receipts[key]['bytes'] != value['bytes'] or receipts[key].get('original_test_fields_retained') is not False for key,value in expected['source_files'].items()):
        raise ValueError('Source provenance or test-field exclusion differs')
    return {'status': 'verified-existing', 'network_calls': 0, 'training_tasks':len(expected['training_ids']),
            'development_tasks':len(expected['development_ids']), 'evaluator_answers_parsed':False}


def verify_inputs(runtime_root, model_root, wheels_root, pins, *, check_runtime=True):
    """Verify bytes independently of mount names; no remote fallback is possible."""
    if set(pins) != {'runtime', 'model', 'wheels'}:
        raise ValueError('Exactly three independent Dataset bindings required')
    for pin in pins.values():
        validate_reference(pin['reference'])
        if pin.get('private') is not True:
            raise ValueError('Private Dataset binding required')
    runtime = verify_runtime(runtime_root, pins['runtime']['manifest_sha256'])
    model_manifest = safe_file(model_root, 'irisx-model-material.json')
    wheel_manifest = safe_file(wheels_root, 'wheel-lock.json')
    if sha_file(model_manifest) != pins['model']['manifest_sha256'] or sha_file(wheel_manifest) != pins['wheels']['manifest_sha256']:
        raise ValueError('Model or wheel manifest differs from the exact Dataset version pin')
    from tools.arc_next_models import validate_material
    from tools.arc_next_offline_environment import validate_wheelhouse
    model = validate_material(model_root, 'granite-4.2-8b', model_manifest)
    inventory = json.loads((Path(runtime_root) / 'runtime/research/arc-next-line/training-source-inventory.json').read_bytes())
    training = verify_runtime_training(inventory, Path(runtime_root) / 'training')
    wheel_result = validate_wheelhouse(Path(runtime_root) / 'runtime/research/arc-next-line/model-source-lock.json', wheels_root, check_runtime=check_runtime)
    return {'format': 'irisx/arc-next-offline-input-check-v1', 'pins': pins,
            'source_commit': runtime['source_commit'], 'model': model,
            'training': training, 'wheelhouse': wheel_result,
            'network_calls': 0, 'gpu_runtime_verified': False}
