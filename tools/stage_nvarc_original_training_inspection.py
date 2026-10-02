"""Native original Trainer inspection, gated on the completed cache probe."""
from __future__ import annotations
import argparse
from array import array
import ast
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, sha
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.acquire_nvarc_original_environment import DOCKER, REF, PACKAGES
from tools.audit_nvarc_original_training_environment import EXTRA, GROUPS
from tools.nvarc_original_training_inspection_worker import FORMAT, PARAMETERS
from tools.stage_nvarc_original_unsloth_probe import inventory, MATERIAL, MODEL_REF, verify_archive as verify_native

MATERIALS = ROOT / '.irisx/nvarc-original/materials'
MANIFESTS = ROOT / '.irisx/nvarc-original/manifests'
VIEWS = MATERIALS / 'original-inspection-views-20261002-002'
WORKER = ROOT / 'tools/nvarc_original_training_inspection_worker.py'
ENVIRONMENT = MANIFESTS / 'original-training-environment-20261002-002/result.json'
POLICY = MANIFESTS / 'original-ttt-policy-20261002-003/result.json'
ENVIRONMENT_SHA = 'bf0f748811d96c110152ab0f38e203a080e3252b7e05b6772441d281520b368a'
POLICY_SHA = '3a061806fd40202a4494ce5f35a46d3b6be8b8018990487f59d8167df83ae31f'
VIEWS_SHA = '88ee3161a7f82eb051ae846161a6cfd2d9ebdbfa145b0d84cb3d52098763b134'


def require(value, message):
    if not value: raise ValidationError(message)


def source_inventory():
    require(sha(ENVIRONMENT) == ENVIRONMENT_SHA and sha(POLICY) == POLICY_SHA,
        'exact complete original training source audits required')
    groups = {**GROUPS,
        'qwen3-original-training-source-20261002-001': ['torch/optim/adam.py', 'torch/optim/adamw.py',
            'unsloth/trainer.py', 'unsloth/models/llama.py'],
        'qwen3-original-training-source-20261002-002': ['unsloth/models/loader.py'],
        'qwen3-original-training-rl-patches-20261002-001': ['unsloth/models/__init__.py', 'unsloth/models/rl.py']}
    result = {}
    for group, names in groups.items():
        folder = MATERIALS / group
        ledger = json.loads((folder / 'acquisition.json').read_bytes())
        require(ledger['state'] == 'complete-exact-public-dependency-files' and ledger['version_number'] == 2 and
            ledger['expected_script_version_id'] == 272622465 and ledger['requests_reserved'] == ledger['files_completed'] == len(names) and
            [row['file_name'] for row in ledger['events']] == names,
            'closed exact dependency source acquisition required')
        for row in ledger['events']:
            name = row['file_name']; path = folder / name
            require(name not in result and row['state'] == 'retained' and row['path_kernel_version_ids'] == [272622465] and
                row['download_host'] == 'www.kaggleusercontent.com' and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'exact original dependency file binding differs')
            result[name] = {'bytes': row['bytes'], 'sha256': row['sha256']}
    require(len(result) == 37, 'all thirty-seven source/metadata files required')
    return result


def views():
    require(sha(VIEWS / 'result.json') == VIEWS_SHA, 'exact complete original text material required')
    proof = json.loads((VIEWS / 'result.json').read_bytes())
    require({p.name for p in VIEWS.iterdir() if p.is_file()} == set(proof['inventory']) | {'result.json'},
        'closed source-view inventory required')
    for name, row in proof['inventory'].items():
        require((VIEWS / name).stat().st_size == row['bytes'] and sha(VIEWS / name) == row['sha256'],
            'frozen source-view bytes differ')
    text_bytes = gzip.decompress((VIEWS / 'texts.json.gz').read_bytes())
    texts = json.loads(text_bytes)
    rows = json.loads((VIEWS / 'expected-rows.json').read_bytes())
    mask_path = MANIFESTS / 'original-ttt-loss-20261002-001/result.json'
    require(sha(mask_path) == proof['source_mask_proof_sha256'] and rows == json.loads(mask_path.read_bytes())['rows'] and
        len(text_bytes) == proof['uncompressed_text_bytes'] <= 4 * 1024**2 and len(texts) == len(rows) == proof['view_count'] == 128 and
        digest_value(texts) == proof['texts_digest'] and proof['input_tokens'] == sum(row['input_tokens'] for row in rows) == 955392 and
        proof['supervised_tokens'] == sum(row['supervised_tokens'] for row in rows) == 476160 and
        proof['maximum_sequence_length'] == max(row['input_tokens'] for row in rows) == 7464 and
        all(hashlib.sha256(row['text'].encode()).hexdigest() == expected['original_text_sha256']
            for row, expected in zip(texts, rows)), 'all complete original view/text/label bindings required')
    return proof


def prerequisite():
    folder = ROOT / '.irisx/nvarc-original/runs/nvarc-original-qwen3-unsloth-probe-003'
    archive = folder / 'execution-final/retrieved/gpu-preflight-result.zip'
    ledger = json.loads((folder / 'execution-final/execution-ledger.json').read_bytes())
    require(ledger['accepted'] is True and ledger['terminal_observed'] is True and ledger['retrieval_reserved'] == 1 and
        ledger['events'][-1].get('outcome') == 'retrieved' and archive.is_file(),
        'completed and once-retrieved original explicit-position GPU prerequisite required')
    proof = verify_native(archive, folder / 'package-l4')
    require(proof['outcome'] == 'complete' and proof['completed_outer_forwards'] == 4 and
        proof['reserved_outer_forwards'] == 4 and proof['reserved_input_tokens'] == 26 and
        proof['four_bf16_l4_hardware_observed'] is True and proof['exact_original_model_material_observed'] is True,
        'complete original model prefill/cache prerequisite required')
    return {'run_id': proof['run_id'], 'archive_sha256': sha(archive), 'plan_digest': proof['plan_digest'],
        'comparisons': proof['comparisons']}


def trainable_layout(config, rank):
    hidden = config['hidden_size']; q = config['num_attention_heads'] * config['head_dim']
    kv = config['num_key_value_heads'] * config['head_dim']; intermediate = config['intermediate_size']
    projections = {'q_proj': (hidden, q), 'k_proj': (hidden, kv), 'v_proj': (hidden, kv),
        'o_proj': (q, hidden), 'gate_proj': (hidden, intermediate), 'up_proj': (hidden, intermediate),
        'down_proj': (intermediate, hidden)}
    result = {}
    for layer in range(config['num_hidden_layers']):
        for name, (inputs, outputs) in projections.items():
            branch = 'self_attn' if name in ('q_proj', 'k_proj', 'v_proj', 'o_proj') else 'mlp'
            prefix = f'base_model.model.model.layers.{layer}.{branch}.{name}'
            result[prefix + '.lora_A.default.weight'] = [rank, inputs]
            result[prefix + '.lora_B.default.weight'] = [outputs, rank]
    result['base_model.model.model.embed_tokens.modules_to_save.default.weight'] = [config['vocab_size'], hidden]
    result['base_model.model.lm_head.modules_to_save.default.weight'] = [config['vocab_size'], hidden]
    return result


def plan_for(run):
    require(re.fullmatch(r'nvarc-original-qwen3-training-inspect-\d{3}', run), 'distinct finite native inspection identity required')
    native = prerequisite(); view = views(); policy = json.loads(POLICY.read_bytes())
    source = source_inventory()
    config_path = MATERIALS / 'qwen3-published-sft139-20261002-001/model/config.json'
    require(sha(config_path) == inventory()['config.json']['sha256'], 'exact published original topology configuration required')
    layout = trainable_layout(json.loads(config_path.read_bytes()), policy['peft_parameters']['r'])
    require(sum(math.prod(shape) for shape in layout.values()) == PARAMETERS, 'complete source-inferred trainable layout required')
    return {'format': FORMAT, 'approved': True, 'owner_decision': 'Decision 0054', 'run_id': run,
        'kernel_id': 'danielwuu/' + run, 'maximum_notebook_wall_seconds': 1200, 'maximum_child_wall_seconds': 900,
        'maximum_outer_forwards': 0, 'maximum_optimizer_steps': 0, 'maximum_generations': 0,
        'maximum_teacher_calls': 0, 'maximum_paid_usd': 0, 'competition_files_opened': 0,
        'docker_image': DOCKER, 'dependency_ref': REF, 'dependency_script_version_id': 272622465,
        'model_material_digest': MATERIAL, 'model_sources': [MODEL_REF], 'model_instance_version_id': 627758,
        'competition_sources': ['arc-prize-2026-arc-agi-2'],
        'hardware_gate': 'four distinct BF16 L4s; one sequential rank-zero inspection worker',
        'versions': {**PACKAGES, **EXTRA}, 'source_inventory_digest': digest_value(source),
        'training_environment_proof_sha256': ENVIRONMENT_SHA, 'training_policy_proof_sha256': POLICY_SHA,
        'views_proof_sha256': VIEWS_SHA, 'original_unsloth_gpu_prerequisite_verified': True,
        'native_gpu_prerequisite': native, 'original_peft_parameters': policy['peft_parameters'],
        'source_inferred_trainable_layout': layout,
        'original_training_arguments': policy['training_arguments'], 'solver_cell_sha256': view['solver_cell_sha256'],
        'original_class_ast_sha256': view['original_class_ast_sha256'], 'source_rows_digest': view['source_rows_digest'],
        'source_bundle_digest': view['source_bundle_digest'], 'uncompressed_text_bytes': view['uncompressed_text_bytes'],
        'texts_digest': view['texts_digest'], 'source_view_count': 128, 'source_input_tokens': 955392,
        'source_supervised_tokens': 476160, 'source_maximum_sequence_length': 7464,
        'parent_ids': view['parent_ids'], 'exposure_tags': view['exposure_tags'],
        'full_long_ttt_completed': False, 'correctness_scored': False, 'retain_export': False,
        'scope': 'native source adapter topology/BF16/reset/Trainer preparation; zero forward/backward/optimizer work'}


def payloads_for(plan):
    return {'plan': canonical_bytes(plan, newline=True), 'source_inventory': canonical_bytes(source_inventory(), newline=True),
        'model_inventory': canonical_bytes(inventory(), newline=True), 'texts_gzip': (VIEWS / 'texts.json.gz').read_bytes(),
        'expected_rows': (VIEWS / 'expected-rows.json').read_bytes(), 'solver': (VIEWS / 'solver.py').read_bytes(),
        'worker': WORKER.read_bytes()}


def render(run, payloads, hashes):
    source = (ROOT / 'tools/nvarc_original_training_inspection.py.tmpl').read_text(encoding='utf-8')
    for key, value in {'__RUN__': json.dumps(run), '__PAYLOADS__': json.dumps(payloads), '__HASHES__': json.dumps(hashes),
        '__HARDWARE_HELPER__': (ROOT / 'src/irisx/arc_nvarc_hardware.py').read_text(encoding='utf-8')}.items():
        source = source.replace(key, value)
    compile(source, 'native-training-inspection', 'exec')
    return source


def stage(package, run):
    require(not package.exists(), 'new immutable native inspection package required')
    plan = plan_for(run)  # No partial package or execution journal before all prerequisites exist.
    raw = payloads_for(plan)
    hashes = {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()}
    (package / 'kernel').mkdir(parents=True)
    (package / 'plan.json').write_bytes(raw['plan'])
    atomic(package / 'kernel/notebook.ipynb', {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [],
            'source': render(run, {key: base64.b64encode(value).decode() for key, value in raw.items()}, hashes).splitlines(keepends=True)}]})
    atomic(package / 'kernel/kernel-metadata.json', {'id': plan['kernel_id'], 'title': run, 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True,
        'enable_internet': False, 'docker_image': DOCKER, 'dataset_sources': [], 'kernel_sources': [REF],
        'competition_sources': plan['competition_sources'], 'model_sources': plan['model_sources']})
    atomic(package / 'stage-summary.json', {'run_id': run, 'plan_digest': digest_value(plan), 'payload_sha256': hashes,
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan = json.loads((package / 'plan.json').read_bytes()); summary = json.loads((package / 'stage-summary.json').read_bytes())
    require(plan == plan_for(plan['run_id']) and digest_value(plan) == summary['plan_digest'] and
        {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file() and p.name != 'stage-summary.json'} == summary['inventory'],
        'closed immutable native inspection plan/package differs')
    source = ''.join(json.loads((package / 'kernel/notebook.ipynb').read_bytes())['cells'][0]['source'])
    values = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(source).body if isinstance(n, ast.Assign) and
        len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('RUN', 'PAYLOADS', 'HASHES')}
    raw = {key: base64.b64decode(value, validate=True) for key, value in values['PAYLOADS'].items()}
    require(raw == payloads_for(plan) and values['HASHES'] == summary['payload_sha256'] ==
        {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()} and values['RUN'] == plan['run_id'] and
        source == render(values['RUN'], values['PAYLOADS'], values['HASHES']), 'exact native parent/worker/source bytes differ')
    meta = json.loads((package / 'kernel/kernel-metadata.json').read_bytes())
    require(meta == {'id': plan['kernel_id'], 'title': plan['run_id'], 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'docker_image': DOCKER, 'dataset_sources': [], 'kernel_sources': [REF],
        'competition_sources': plan['competition_sources'], 'model_sources': [MODEL_REF]}, 'exact private original transport required')
    return {'run_id': plan['run_id'], 'plan_digest': summary['plan_digest'], 'offline_package_verified': True,
        'external_calls': 0, 'maximum_outer_forwards': 0, 'maximum_optimizer_steps': 0}


def verify(path, package):
    checked = preflight(package); plan = json.loads((package / 'plan.json').read_bytes())
    content = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and sum(row.file_size for row in archive.infolist()) <= 16 * 1024**2,
            'closed bounded native inspection archive required')
        manifest = json.loads(archive.read('manifest.json'))
        require(manifest['run_id'] == plan['run_id'] and manifest['plan_digest'] == checked['plan_digest'] and
            len(manifest['members']) == len({row['path'] for row in manifest['members']}) and
            set(names) == {row['path'] for row in manifest['members']} | {'manifest.json'}, 'exact native archive members/plan required')
        for row in manifest['members']:
            body = archive.read(row['path'])
            require(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'], 'native archive member differs')
            content[row['path']] = body
    def read(name): return json.loads(content[name])
    raw = payloads_for(plan)
    require(read('plan.json') == plan and read('payload-bindings.json') ==
        {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()}, 'returned exact native payload differs')
    terminal = read('terminal.json')
    require(terminal['outcome'] in {'complete', 'failed'} and terminal['run_id'] == plan['run_id'] and terminal['contains_evaluator_truth'] is False and
        type(terminal['wall_seconds']) in (int, float) and math.isfinite(terminal['wall_seconds']) and
        0 <= terminal['wall_seconds'] <= 1200 and all(type(terminal[key]) is int and terminal[key] == 0
            for key in ('model_forwards', 'optimizer_steps', 'generations', 'teacher_calls', 'paid_usd')), 'native terminal cost differs')
    result = {'run_id': plan['run_id'], 'outcome': terminal['outcome'], 'terminal': terminal,
        'archive_sha256': sha(path), 'plan_digest': checked['plan_digest'], 'source_long_ttt_prerequisite_qualified': False,
        'model_forwards': 0, 'optimizer_steps': 0, 'generations': 0, 'teacher_calls': 0,
        'full_long_ttt_completed': False, 'correctness_scored': False}
    if terminal['outcome'] == 'complete':
        hardware = read('hardware.json'); gpu = hardware['inventory']
        require(len(gpu) == len({row['uuid'] for row in gpu}) == 4 and all(row['name'] == 'NVIDIA L4' and row['bf16'] is True for row in gpu) and
            hardware['torch'] == '2.8.0+cu128' and hardware['cuda'] == '12.8' and
            read('source-verification.json')['inventory'] == source_inventory() and
            read('model-verification.json')['all_ten_files_verified'] is True and
            read('model-verification.json')['model_material_digest'] == MATERIAL,
            'complete native hardware/material/source envelope required')
        require(content['inspection.py'] == raw['worker'] and content['solver.py'] == raw['solver'] and
            content['expected-rows.json'] == raw['expected_rows'] and content['texts.json'] == gzip.decompress(raw['texts_gzip']),
            'complete native trusted worker/data bytes required')
        observation = read('native/native-inspection.json'); rows = read('native/prepared-rows.json')
        expected_rows = json.loads(raw['expected_rows'])
        require(observation['format'] == FORMAT and observation['versions'] == plan['versions'] and
            observation['optimizer_created'] is False and all(type(observation[key]) is int and observation[key] == 0 for key in
                ('model_forwards', 'optimizer_steps', 'generation_calls', 'teacher_calls', 'prohibited_attempts')) and
            observation['contains_evaluator_truth'] is False and observation['full_long_ttt_completed'] is False and
            observation['prepared_rows_digest'] == digest_value(rows) and len(rows) == 128,
            'complete native observation/cost/prepared-row schema differs')
        require(all(type(row['value']) is bool for row in observation['gradient_checkpoint_flags']) and
            len({row['module'] for row in observation['gradient_checkpoint_flags']}) == len(observation['gradient_checkpoint_flags']),
            'distinct native checkpoint-module flags required')
        before, after = observation['trainable_before_trainer'], observation['trainable_after_trainer']
        require(all(type(row['elements']) is int and row['elements'] > 0 and
            row['elements'] == math.prod(row['shape']) for row in before + after) and
            len({row['name'] for row in before}) == len(before) and len({row['name'] for row in after}) == len(after) and
            observation['trainable_parameters'] == sum(row['elements'] for row in before) and
            read('native/adapter-topology.json')['trainable'] == before, 'actual native trainable topology differs')
        equal = True
        tokens = content['native/prepared-tokens.i16le']; offset = 0
        require(sum(row['input_tokens'] for row in expected_rows) == plan['source_input_tokens'] and
            sum(row['supervised_tokens'] for row in expected_rows) == plan['source_supervised_tokens'] and
            max(row['input_tokens'] for row in expected_rows) == plan['source_maximum_sequence_length'],
            'fixed complete source-view counts differ')
        for index, (row, expected) in enumerate(zip(rows, expected_rows)):
            count = row['input_tokens']; size = row['retained_token_bytes']
            require(type(count) is int and 0 < count <= 8192 and type(size) is int and size == 4 * count and
                type(row['retained_byte_offset']) is int and row['retained_byte_offset'] == offset and offset + size <= len(tokens),
                'closed bounded native input/label vector slices required')
            values = array('h'); values.frombytes(tokens[offset:offset + size])
            if sys.byteorder != 'little': values.byteswap()
            ids, labels = list(values[:count]), list(values[count:]); offset += size
            require(all(0 <= value < 16 for value in ids) and all(value == -100 or 0 <= value < 16 for value in labels) and
                digest_value(ids) == row['input_ids_digest'] and digest_value(labels) == row['labels_digest'] and
                type(row['supervised_tokens']) is int and sum(value >= 0 for value in labels[1:]) == row['supervised_tokens'],
                'native raw vectors contradict retained input/label/count hashes')
            require(row['row'] == index and all(type(row[key]) is bool for key in
                ('collator_preserved_input_ids', 'source_input_ids_equal', 'source_labels_equal')) and
                row['source_input_ids_equal'] == (row['input_ids_digest'] == expected['input_ids_digest']) and
                row['source_labels_equal'] == (row['labels_digest'] == expected['labels_digest']), 'native source-row diagnostic differs')
            equal = (equal and row['collator_preserved_input_ids'] and row['source_input_ids_equal'] and row['source_labels_equal'] and
                row['input_tokens'] == expected['input_tokens'] and row['supervised_tokens'] == expected['supervised_tokens'])
        require(offset == len(tokens), 'native token vectors must have no unreferenced suffix')
        require(observation['every_source_input_and_label_equal'] == all(row['collator_preserved_input_ids'] and
            row['source_input_ids_equal'] and row['source_labels_equal'] for row in rows), 'native summary contradicts retained row evidence')
        baseline, reset = read('native/baseline-inventory.json'), read('native/reset-inventory.json')
        require(baseline == reset and len({row['name'] for row in baseline}) == len(baseline) and
            len(baseline) >= len(before) and all(re.fullmatch(r'[0-9a-f]{64}', row['sha256']) and
                math.prod(row['shape']) == row['elements'] and row['finite'] is True for row in baseline) and
            read('native/reset-observation.json')['all_saved_tensors_restored'] is True and
            read('native/reset-observation.json')['independent_detached_storage_observed'] is True,
            'every saved tensor must retain and reset its exact detached baseline')
        require(read('native/guard-state.json') == {'installed_before_unsloth_import': True,
            'module_call_paths_blocked': ['__call__', '_wrapped_call_impl', '_call_impl'],
            'optimizer_construction_blocked': True, 'backward_and_step_blocked': True} and
            'native/prohibited-attempts.json' not in content, 'complete native inspection must have no blocked work attempts')
        for origin in observation['trainer_origins']:
            if 'retained_file' in origin:
                body = content['native/' + origin['retained_file']]
                require(len(body) == origin['bytes'] and hashlib.sha256(body).hexdigest() == origin['sha256'], 'retained native Trainer class source differs')
        qualified = (before == after and {row['name']: row['shape'] for row in before} == plan['source_inferred_trainable_layout'] and
            sum(row['elements'] for row in before) == PARAMETERS and
            all(row['dtype'] == 'torch.bfloat16' for row in before) and equal and
            observation['prepared_argument_lengths'].get('max_length') == 8192)
        result.update(source_long_ttt_prerequisite_qualified=qualified, trainable_parameters=observation['trainable_parameters'],
            every_source_input_and_label_equal=equal, prepared_argument_lengths=observation['prepared_argument_lengths'],
            actual_checkpoint_flags=observation['gradient_checkpoint_flags'],
            source_trainable_dtype_policy_observed=sorted({row['dtype'] for row in before}),
            all_saved_tensors_reset_verified=True, native_trainer_origins=observation['trainer_origins'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('stage', 'preflight', 'verify'))
    parser.add_argument('--package', type=Path, required=True); parser.add_argument('--run-id')
    parser.add_argument('--archive', type=Path); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'stage': result = stage(args.package, args.run_id)
    elif args.action == 'preflight': result = preflight(args.package)
    else:
        require(args.output is not None and not args.output.exists(), 'new independent native inspection proof required')
        result = verify(args.archive, args.package); atomic(args.output, result)
    print(json.dumps(result))
