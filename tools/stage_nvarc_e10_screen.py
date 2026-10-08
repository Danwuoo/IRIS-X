"""Build/preflight a new, offline, truth-free E10 development notebook.

No legacy run is rebound and no provider is contacted. Exact code-only native
materials, tokenizer/inventories, visible partition and original configuration
must be supplied; an absent handoff archive is never treated as evidence.
"""
from __future__ import annotations
import argparse
import ast
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, public_training_material, require, validate_challenges, write
from tools.nvarc_native_solve_runtime import SOURCE_HASHES, load_sources
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_native_multitask_render import worker as native_worker
from tools.nvarc_official_render import bridge, replace_once
from tools.nvarc_resource_attachment import attachment,validate_attachment
from tools.nvarc_notebook_controls import cli_handoff, render_download_cell

FORMAT = 'irisx/stage4-e10-runtime-screen-v1'
SCIENTIFIC_SCOPE = 'frozen public solver-visible development challenges only'
EXTERNAL_FILES = ('solver.py', 'arc_loader.py', 'arc_decoder.py', 'inspection_helpers.py',
                  'hardware_helpers.py', 'source-inventory.json', 'model-inventory.json')
LOCAL_FILES = ('tools/arc_kaggle_submission.py', 'tools/nvarc_native_solve_runtime.py',
    'tools/nvarc_native_multitask.py', 'tools/nvarc_native_submission.py', 'tools/nvarc_native_export.py',
    'tools/nvarc_output_lifecycle.py', 'tools/nvarc_allocation_transport.py',
    'tools/nvarc_public_eval.py', 'tools/nvarc_public_eval_parent.py', 'tools/nvarc_e10_screen.py',
    'tools/stage_nvarc_e10_screen.py', 'tools/nvarc_native_multitask_render.py',
    'tools/nvarc_official_render.py', 'tools/nvarc_original_native_ttt_worker.py',
    'tools/verify_nvarc_e10_screen.py', 'tools/nvarc_process_supervisor.py',
    'tools/nvarc_runtime_archive.py', 'tools/nvarc_calibration_gate.py','tools/nvarc_resource_attachment.py',
    'tools/nvarc_notebook_controls.py')
CONFIG_FIELDS = ('model_material_digest', 'versions', 'original_peft_parameters', 'original_training_arguments',
    'native_trainer_origins', 'native_checkpoint_flags', 'source_inferred_trainable_layout',
    'original_class_ast_sha256', 'solver_cell_sha256', 'source_inventory_digest',
    'model_instance_version_id', 'dependency_script_version_id', 'docker_image', 'model_sources')
BASELINE_CONFIG_DIGESTS = {
    'original_peft_parameters': 'sha256:76e215ea96ba8123fb19208e01cebca870316a26026f89528e63a4fa85359af0',
    'original_training_arguments': 'sha256:925369216c7087b7695f87f748e3a6f581f336f88c4dd5c524404e5db84c01ee',
    'native_checkpoint_flags': 'sha256:7292347b713dcd406d92cd6ab41f31ab964252bfeb23ae0727e38e1c144f6b71',
    'native_source_learning_rates': 'sha256:42e532114ebdb7cf20f9423848f051757958e40a4ac680ccc5c71c75b4d9d499'}
MODEL_MATERIAL_DIGEST = 'sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03'
NOTICE_FILES_SHA256 = {
    'LICENSE-Apache-2.0.txt':'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30',
    'NOTICE-native.txt':'c9e87523811159ebff4469484abab9ee1f368c563bc286d0b12bed142cc96955',
    'MODIFIED-SOURCE-ATTRIBUTION.txt':'c202a40c7bfed6233e3dd1088bdabaf86505ee81949672e069c67087f09ed9ef',
    'PROVENANCE.json':'aaa90d26c3d26f40cb4140e8b2d8f875a2265ee653fd707f0efbd4a82bad9c97'}
NATIVE_ATTRIBUTION = '''# Original portions/source flow: sorokin's Kaggle notebook
# arc2-qwen3-unsloth-flash-lora-batch4-queue, Version10, Apache-2.0.
# https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue
# IRIS-X changes: reviewed native preparation and bounded task/reset,
# verification, process supervision and host telemetry orchestration.
# See notices/NOTICE-native.txt and notices/LICENSE-Apache-2.0.txt.
# This attributes original portions and does not relicense the entire file.
'''


def material_files(contract):
    """Exact external payload slots; v1 historical material schema stays valid."""
    fields={'format','files_sha256','template_sha256','tokenizer_sha256','source_provenance'}
    v2=contract.get('format')=='irisx/native-code-material-contract-v2'
    require(set(contract)==fields|({'notices_sha256'} if v2 else set()) and
        contract['format'] in ('irisx/native-code-material-contract-v1','irisx/native-code-material-contract-v2') and
        set(contract['files_sha256'])==set(EXTERNAL_FILES) and
        (not v2 or contract['notices_sha256']==NOTICE_FILES_SHA256),'closed reviewed code-only material contract required')
    return EXTERNAL_FILES+tuple('notices/'+name for name in NOTICE_FILES_SHA256) if v2 else EXTERNAL_FILES


def native_notice_closure(contract,external):
    names=material_files(contract)
    if contract['format']=='irisx/native-code-material-contract-v1':return False
    require(all(name in external and hashlib.sha256(external[name]).hexdigest()==
        NOTICE_FILES_SHA256[name.removeprefix('notices/')] for name in names if name.startswith('notices/')),
        'exact native notebook license/notice/provenance payload required')
    return True


def full_task_gate_ids(plan,challenges):
    """Final comparative qualification includes every actual task, empty pools too."""
    tasks=plan['task_order']
    require(isinstance(tasks,list) and tasks and len(tasks)==len(set(tasks)) and
        set(tasks)==set(challenges),'mandatory final gate must cover every actual task exactly once')
    return list(tasks)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_baseline(config, external, contract):
    require(config['model_material_digest'] == MODEL_MATERIAL_DIGEST and
        all(digest(config[key]) == expected for key, expected in BASELINE_CONFIG_DIGESTS.items()) and
        config['solver_cell_sha256'] == SOURCE_HASHES['solver.py'],
        'unchanged E10 SFT139/TTT128 baseline configuration required')
    names=material_files(contract)
    require(set(external)==set(names)|{'verified-tokenizer.json'} and
        all(hashlib.sha256(external[name]).hexdigest() == contract['files_sha256'][name] for name in EXTERNAL_FILES) and
        all(contract['files_sha256'][name] == expected for name, expected in SOURCE_HASHES.items()),
        'closed exact native code-only material contract differs')
    native_notice_closure(contract,external)
    require(digest(parse_json(external['model-inventory.json'])) == config['model_material_digest'] and
        digest(parse_json(external['source-inventory.json'])) == config['source_inventory_digest'] and
        hashlib.sha256(external['verified-tokenizer.json']).hexdigest() == contract['tokenizer_sha256'] and
        parse_json(external['model-inventory.json'])['tokenizer.json']['sha256'] == contract['tokenizer_sha256'],
        'native model/source/tokenizer identities differ')


def rendered_worker(*, source_root=ROOT):
    base = (Path(source_root)/'tools/nvarc_original_native_ttt_worker.py').read_bytes()
    # The tracked preparer predates the retained notebook's schedule extension.
    # Keep only its reviewed zero-work/preparation prefix, never its old run
    # body or main block. The renderer supplies the new finite native tail.
    anchor = b'    budget=EpochBudget(torch,model,trainer,rows,'
    require(base.count(anchor) == 1, 'one tracked native preparation boundary required')
    suffix = base[base.index(b"\n\nif __name__=='__main__':"):]
    base = base.split(anchor)[0]+b'    from nvarc_native_ttt_schedule import native_schedule\n'+suffix
    base = base.replace(b"FORMAT='irisx/nvarc-original-native-long-ttt-v1'",
                        b"FORMAT='irisx/nvarc-original-native-long-ttt-v2'")
    source = native_worker(base).decode()
    source = replace_once(source, "['inventory'][0]['uuid']", "['inventory'][spec['selected_gpu_index']]['uuid']")
    source = replace_once(source, "started=time.monotonic();budget=None", "started=time.monotonic();budget=None\n"
        "    import os,signal\n    from tools.nvarc_public_eval import install_owner_guard,PhaseTelemetry\n"
        "    install_owner_guard(int(os.environ['IRIS_NATIVE_PARENT_PID']),signal.SIGKILL)\n"
        "    telemetry=PhaseTelemetry()")
    source = replace_once(source, 'with zero_work_guard(torch,denied) as verify_guard:',
                          "with telemetry.scope('preparation'),zero_work_guard(torch,denied) as verify_guard:")
    source = replace_once(source, "mode=attempt['mode'];spec=plan['task_specs'][task_id]",
        "mode=attempt['mode'];spec=plan['task_specs'][task_id]\n"
        "    require(mode=='solve' and plan['owner_decision']=='Decision 0061' and "
        "plan['official_score_scope'] is False,'private Stage4 development solve only')")
    source = replace_once(source, '    budget=None;control=None;', '    adapter.telemetry=telemetry\n    budget=None;control=None;')
    source = replace_once(source, 'control=cache_controls(adapter);save(\'cache-control.json\',control)',
        "with telemetry.scope('control'): control=cache_controls(adapter)\n        save('cache-control.json',control)")
    start = source.index("            if mode=='fault-after-two-updates':")
    end = source.index('            start_training=', start)
    source = source[:start]+source[end:]
    source = replace_once(source, "with training_deadline(budget,task_deadline-spec['inference_reserve_seconds']):",
        "with telemetry.scope('training'),training_deadline(budget,task_deadline-spec['inference_reserve_seconds']):")
    old = """            adapter.generation_deadline=min(task_deadline,time.time()+spec['inference_seconds'])
            with torch.inference_mode():
                tests,failure=run_task_tests(challenges,task_id,lambda index:solve_test(challenges,task_id,index,
                    loader,solver,decoder,tokenizer,adapter,maximum_candidates=spec['maximum_candidate_sequences_per_test'],
                    emit=events.emit),checkpoint)"""
    new = """            from tools.nvarc_allocation_transport import AllocationClient,run_admitted_tests
            client=AllocationClient(int(os.environ['IRIS_ALLOCATION_FD']),binding)
            with torch.inference_mode():
                tests,failure=run_admitted_tests(challenges,task_id,lambda index,allocation,schedule:solve_test(
                    challenges,task_id,index,loader,solver,decoder,tokenizer,adapter,
                    maximum_candidates=spec['maximum_candidate_sequences_per_test'],emit=events.emit,
                    verification_schedule=schedule,test_allocation=allocation),checkpoint,adapter,client,
                    spec['verification_schedule'])"""
    source = replace_once(source, old, new)
    start = source.index("            set_peft_model_state_dict(model,defaults.copy(),adapter_name='default')", source.index('    finally:'))
    end = source.index('\n        except BaseException as error:', start)
    block = source[start:end]
    source = source[:start]+"            with telemetry.scope('reset'):\n"+'\n'.join('    '+line for line in block.splitlines())+source[end:]
    source = replace_once(source, "FastLanguageModel.for_inference(model);post_reset=reset_control(adapter,control);save('post-reset-control.json',post_reset)",
        "with telemetry.scope('control'):\n                    FastLanguageModel.for_inference(model)\n"
        "                    post_reset=reset_control(adapter,control)\n                save('post-reset-control.json',post_reset)")
    source = replace_once(source, "        save('result.json',result)",
        "        result['telemetry']=telemetry.snapshot()\n"
        "        try:\n            result['cuda_memory_observation']={'peak_allocated_bytes':torch.cuda.max_memory_allocated(),"
        "'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'scope':'per-process high water since model initialization; peaks not reset',"
        "'added_device_synchronizations':0}\n"
        "        except BaseException as error:\n            result['cuda_memory_observation']={'peak_allocated_bytes':None,'peak_reserved_bytes':None,"
        "'error_type':type(error).__name__,'message':str(error)[:500]}\n        save('result.json',result)")
    source=NATIVE_ATTRIBUTION+source
    compile(source, 'new-e10-native-worker', 'exec')
    return source.encode()


def read_materials(materials, contract_path, template_path, tokenizer_path):
    materials = Path(materials); contract = parse_json(Path(contract_path).read_bytes())
    names=material_files(contract)
    reject_truth(contract)
    require(sha(template_path) == contract['template_sha256'] and sha(tokenizer_path) == contract['tokenizer_sha256'],
            'exact original config/tokenizer contract differs')
    raw = {}
    for name in names:
        path = materials/name
        expected=contract['notices_sha256'][name.removeprefix('notices/')] if name.startswith('notices/') else contract['files_sha256'][name]
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(materials.resolve()) and
            sha(path) == expected, 'exact code-only material missing/differs: '+name)
        raw[name] = path.read_bytes()
    require(all(contract['files_sha256'][name] == expected for name, expected in SOURCE_HASHES.items()),
            'exact three code-only native source pins required')
    for name in ('solver.py', 'arc_loader.py', 'arc_decoder.py', 'inspection_helpers.py', 'hardware_helpers.py'):
        ast.parse(raw[name])
    template = parse_json(Path(template_path).read_bytes())
    require(all(key in template for key in CONFIG_FIELDS), 'complete original native configuration required')
    config = {key: template[key] for key in CONFIG_FIELDS}; reject_truth(config)
    rates = template.get('native_source_learning_rates', template.get('source_learning_rates'))
    if rates is None and template.get('task_specs'):
        rates = next(iter(template['task_specs'].values()))['source_learning_rates']
    require(isinstance(rates, list) and len(rates) == 129 and
        all(type(rate) in (int, float) and math.isfinite(rate) and rate >= 0 for rate in rates),
        'complete unchanged native 129-rate/128-step schedule required')
    config['native_source_learning_rates'] = rates
    require(config['model_material_digest'] == MODEL_MATERIAL_DIGEST and
        all(digest(config[key]) == expected for key, expected in BASELINE_CONFIG_DIGESTS.items()),
        'unchanged E10 SFT139/TTT128 baseline configuration required')
    model_inventory = parse_json(raw['model-inventory.json']); source_inventory = parse_json(raw['source-inventory.json'])
    require(digest(model_inventory) == config['model_material_digest'] and
        digest(source_inventory) == config['source_inventory_digest'] and
        model_inventory['tokenizer.json']['sha256'] == contract['tokenizer_sha256'] and
        config['solver_cell_sha256'] == SOURCE_HASHES['solver.py'], 'native model/source/tokenizer identities differ')
    raw['verified-tokenizer.json'] = Path(tokenizer_path).read_bytes()
    validate_baseline(config, raw, contract)
    return raw, config, contract


def task_materials(challenges, materials, tokenizer_path):
    import numpy as np
    from tokenizers import Tokenizer
    from types import SimpleNamespace
    loader, _, _ = load_sources(materials, SimpleNamespace(no_grad=lambda: lambda function: function), np)
    tok = Tokenizer.from_file(str(tokenizer_path))
    class Tokens:
        def encode(self, text): return tok.encode(text).ids
        def decode(self, ids): return tok.decode(ids, skip_special_tokens=False)
    return {key: public_training_material(loader, Tokens(), key, task) for key, task in challenges.items()}


def construct(screen_id, source_commit, challenges, partition, external, config, contract, materials,
              *, resource_admission=None, fixture=False, preprocessing_environment=None, session_seconds=10800,
              resource_check_current=True, rank_plan=None):
    require(re.fullmatch(r'stage4-e10-screen-[a-z0-9-]+', screen_id) and
            re.fullmatch('[0-9a-f]{40}', source_commit), 'new E10 screen identity/full source commit required')
    require(type(session_seconds) is int and session_seconds in (10800, 18000),
            'explicit reviewed three/five-hour planning envelope required')
    # Native strict replay's denominator order follows the serialized challenge
    # mapping. Preserve the separately frozen development/calibration order in
    # the workload, rather than losing it to canonical JSON key sorting.
    challenges = parse_json(canonical(challenges))
    counts = validate_challenges(challenges); reject_truth(partition)
    require(len(counts) == (2 if fixture else 24) and set(materials) == set(counts) and
        partition['challenges_digest'] == digest(challenges) and
        isinstance(partition['task_order'], list) and len(partition['task_order']) == len(counts) and
        set(partition['task_order']) == set(counts), 'exact frozen whole-task development partition required')
    development_order = partition['task_order']
    source_partition_digest = partition.get('source_partition_digest') if (
        partition.get('format') == 'irisx/e10-runtime-visible-partition-v1') else digest(partition)
    require(isinstance(source_partition_digest, str) and re.fullmatch('sha256:[0-9a-f]{64}', source_partition_digest),
            'exact private partition provenance digest required')
    partition = {'format': 'irisx/e10-runtime-visible-partition-v1',
        'source_partition_digest': source_partition_digest,
        'challenges_digest': digest(challenges), 'task_order': development_order,
        'visible_task_digests': {key: digest(task) for key, task in challenges.items()}}
    require(all(len(materials[key]['rows']) == 128 for key in counts), 'full native task epochs required')
    if fixture and preprocessing_environment is None:
        preprocessing_environment = {'python': 'synthetic', 'numpy': 'synthetic', 'tokenizers': 'synthetic'}
    require(isinstance(preprocessing_environment, dict) and set(preprocessing_environment) ==
        {'python', 'numpy', 'tokenizers'} and all(isinstance(value, str) and value for value in preprocessing_environment.values()),
        'explicit CPU source preprocessing version inventory required')
    common = {name: (ROOT/name).read_bytes() for name in LOCAL_FILES}
    if not fixture:
        require('verified-tokenizer.json' in external and
            hashlib.sha256(external['verified-tokenizer.json']).hexdigest() == contract['tokenizer_sha256'],
            'exact small tokenizer required for independent offline replay')
        validate_baseline(config, external, contract)
        if resource_admission is not None:
            require(native_notice_closure(contract,external),'native source license/notice closure required before runtime admission')
    common.update(external)
    common['tools/nvarc_native_submission.py'] = bridge(common['tools/nvarc_native_submission.py'])
    common['inspection.py'] = rendered_worker()
    for name in ('nvarc_native_ttt_budget.py', 'nvarc_native_ttt_schedule.py'):
        common[name] = (ROOT/'tools'/name).read_bytes()
    common['tools/__init__.py'] = b''
    producer_paths = {'worker': 'inspection.py', 'helper': 'inspection_helpers.py',
        'budget': 'nvarc_native_ttt_budget.py', 'schedule': 'nvarc_native_ttt_schedule.py',
        'solve_runtime': 'tools/nvarc_native_solve_runtime.py', 'multitask': 'tools/nvarc_native_multitask.py',
        'bridge': 'tools/nvarc_native_submission.py', 'exporter': 'tools/arc_kaggle_submission.py'}
    producers = {key: hashlib.sha256(common[name]).hexdigest() for key, name in producer_paths.items()}
    loads = [0.0]*4; ranks = {}
    def child_seconds(key):
        return math.ceil(120+100+sum(row['input_tokens'] for row in materials[key]['rows'])/800+30*counts[key]+60)
    for key in sorted(counts, key=lambda key: (-child_seconds(key), key)):
        rank = min(range(4), key=lambda rank: (loads[rank], rank))
        ranks[key] = rank; loads[rank] += child_seconds(key)
    if rank_plan is not None:
        require(set(rank_plan)=={'format','challenges_digest','task_child_seconds_digest','calibration_task_order','ranks'} and
            rank_plan['format']=='irisx/e10-fixed-public-cost-rank-plan-v1' and
            rank_plan['challenges_digest']==digest(challenges) and
            rank_plan['task_child_seconds_digest']==digest({key:child_seconds(key) for key in counts}) and
            rank_plan['calibration_task_order']==development_order[:min(6,len(counts))] and
            set(rank_plan['ranks'])==set(counts) and all(type(rank) is int and 0<=rank<4 for rank in rank_plan['ranks'].values()),
            'closed exact public-cost fixed-rank plan required')
        ranks=dict(rank_plan['ranks']);loads=[sum(child_seconds(key) for key in counts if ranks[key]==rank) for rank in range(4)]
    approved = resource_admission is not None and not fixture
    plans = {}; workload = []
    for schedule in ('interleaved', 'deferred'):
        for repeat in (1, 2):
            subrun = schedule+'-r'+str(repeat)
            specs = {}
            for key, count in counts.items():
                rows = materials[key]['rows']; tokens = sum(row['input_tokens'] for row in rows)
                training = math.ceil(100+tokens/800)
                specs[key] = {'test_count': count, 'training_forwards': 128, 'optimizer_steps': 128,
                    'training_input_tokens': tokens, 'training_supervised_tokens': sum(row['supervised_tokens'] for row in rows),
                    'maximum_sequence_tokens': max(row['input_tokens'] for row in rows),
                    'expected_rows_digest': digest(rows), 'texts_digest': digest(materials[key]['texts']),
                    'source_learning_rates': config['native_source_learning_rates'],
                    'inference_forward_limits': {'control': 7, 'generation': 4096*count, 'verification': 128*count},
                    'maximum_inference_input_tokens': 5*1024**2*count, 'maximum_candidate_sequences_per_test': 64,
                    'per_test_limits': {'generation': 4096, 'verification': 128, 'input_tokens': 5*1024**2},
                    'verification_schedule': schedule, 'selected_gpu_index': ranks[key],
                    'task_seconds': training+30*count, 'inference_seconds': 30*count,
                    'inference_reserve_seconds': 30*count, 'reset_reserve_seconds': 60,
                    'child_seconds': child_seconds(key), 'minimum_admission_seconds': child_seconds(key)}
                workload.append({'job_id': subrun+'-'+key, 'subrun': subrun, 'task_id': key, 'rank': ranks[key]})
            plan = copy.deepcopy(config)
            plan.update(format='irisx/nvarc-native-multitask-v1', run_id=screen_id+'-'+subrun,
                approved=approved, controller_admission=resource_admission, owner_decision='Decision 0061',
                source_commit=source_commit, official_score_scope=False, maximum_paid_usd=0, maximum_teacher_calls=0,
                pythonhashseed=0, task_order=list(counts), task_specs=specs,
                worker_attempts=[{'attempt_id': key, 'task_id': key, 'mode': 'solve'} for key in counts],
                challenges_digest=digest(challenges), producer_files=producers, producer_sha256=digest(producers),
                export_verification_process='fresh-cpu-startup-hashseed-0',
                export_helper_sha256=hashlib.sha256(common['tools/nvarc_native_export.py']).hexdigest(),
                output_lifecycle_sha256=hashlib.sha256(common['tools/nvarc_output_lifecycle.py']).hexdigest(),
                exposure='previously exposed public development; checkpoint training exposure unresolved',
                calibration_and_quality_pending=True, actual_gpu_timing_measured=False)
            plans[subrun] = plan
    calibration_keys = development_order[:min(6, len(counts))]
    calibration_ids = ['interleaved-r1-'+key for key in calibration_keys]
    workload.sort(key=lambda job: (job['job_id'] not in calibration_ids,
        calibration_ids.index(job['job_id']) if job['job_id'] in calibration_ids else 0,
        list(plans).index(job['subrun']), development_order.index(job['task_id'])))
    prefix=[sum(child_seconds(job['task_id']) for job in workload if job['rank']==rank and job['job_id'] in calibration_ids) for rank in range(4)]
    suffix=[sum(child_seconds(job['task_id']) for job in workload if job['rank']==rank and job['job_id'] not in calibration_ids) for rank in range(4)]
    screen = {'format': FORMAT, 'screen_id': screen_id, 'source_commit': source_commit,
        'resource_attachment':attachment(SCIENTIFIC_SCOPE),
        'source_config_digest': digest(config), 'material_contract_digest': digest(contract),
        'preprocessing_environment': preprocessing_environment,
        'preprocessing_qualification': 'CPU source/tokenizer preparation; every actual native GPU collator row must still match at runtime',
        'partition_digest': digest(partition), 'challenges_digest': digest(challenges),
        'tasks': len(counts), 'task_ids':list(counts), 'tests': sum(counts.values()), 'task_runs': 4*len(counts),
        'test_runs': 4*sum(counts.values()), 'arms': ['interleaved', 'deferred'], 'technical_repeats': 2,
        'parallel_workers': 4, 'calibration_subrun': 'interleaved-r1', 'calibration_jobs': calibration_ids,
        'workload_order': workload, 'workload_order_digest': digest(workload),
        'rank_plan':rank_plan,'task_child_seconds':{key:child_seconds(key) for key in counts},
        'calibration_prefix_lane_seconds':prefix,'post_calibration_suffix_lane_seconds':suffix,
        'barrier_aware_reserved_seconds':max(prefix)+max(suffix),
        'maximum_notebook_wall_seconds': session_seconds, 'startup_seconds': 900, 'packaging_reserve_seconds': 1500,
        'cleanup_reserve_seconds':120,'archive_reserve_seconds':180,
        'maximum_export_process_seconds': 300, 'minimum_free_working_bytes': 20*1024**3,
        'cpu_replay_budget_basis':'unmeasured hard allowance: 300s first-six gate and 300s per final all-task export; timeout refuses scientific qualification',
        'maximum_archive_uncompressed_bytes': 8*1024**3,
        'allocated_gpu_hours_upper_bound': 4*session_seconds/3600, 'paid_usd_ceiling': 0,
        'training_steps_upper_bound': 128*4*len(counts),
        'training_input_tokens_upper_bound': 4*sum(row['input_tokens'] for material in materials.values() for row in material['rows']),
        'generation_batches_upper_bound': 16*sum(counts.values()),
        'generation_forwards_upper_bound': 4*4096*sum(counts.values()),
        'verification_forwards_upper_bound': 4*128*sum(counts.values()),
        'processed_sequences_upper_bound': 4*64*sum(counts.values()),
        'inference_input_tokens_upper_bound': 4*5*1024**2*sum(counts.values()),
        'subrun_reserved_lane_seconds': loads, 'all_repeat_reserved_lane_seconds': [4*load for load in loads],
        'reservation_estimate_policy': '100s + demo tokens/800 per epoch, 120s fresh preparation, 60s reset, 30s per actual test; hard caps, not measured throughput',
        'approved_for_runtime': approved, 'resource_admission': resource_admission, 'local_fixture': fixture,
        'calibration_observation_gate_measured': False, 'correctness_scored': False,
        'promotion': False, 'official_submission': False, 'gpu_timing_attestation': False,
        'acceptance_reference': 'research/stage4-e10/inert-screen-plan.json; thresholds unchanged',
        'source_provenance': contract['source_provenance']}
    screen['native_notebook_notice_closure']=False if fixture else native_notice_closure(contract,external)
    screen['complete_dependency_license_closure']=False
    if approved: validate_resource_admission(resource_admission, screen,current=resource_check_current)
    payload = {**common, 'challenges.json': canonical(challenges),
               'task-material-index.json': canonical({key: digest(value) for key, value in materials.items()}),
               'partition.json': canonical(partition), 'material-contract.json': canonical(contract)}
    for key, material in materials.items(): payload['materials/'+key+'.json'] = canonical(material)
    for key, plan in plans.items():
        for name, body in common.items(): payload[key+'/'+name] = body
        payload[key+'/plan.json'] = canonical(plan); payload[key+'/challenges.json'] = canonical(challenges)
    screen['payload_sha256'] = {name: hashlib.sha256(body).hexdigest() for name, body in sorted(payload.items())}
    payload['screen.json'] = canonical(screen)
    require(all(len(body) < 8*1024**2 for body in payload.values()),
            'each exact screen payload must fit the bounded notebook decoder')
    return screen, plans, payload


def validate_resource_admission(value, screen, *, current=True, now_epoch=None):
    from datetime import datetime
    require(isinstance(value, dict) and set(value) == {'format', 'screen_id', 'paid_usd_ceiling',
        'quota_hours_available', 'allocated_gpu_hours_per_quota_hour', 'quota_observed_at', 'provider_session_seconds',
        'private', 'internet', 'prior_sessions_reconciled', 'rules_materials_review_ref'} and
        value['format'] == 'irisx/stage4-free-gpu-resource-admission-v1' and value['screen_id'] == screen['screen_id'] and
        type(value['paid_usd_ceiling']) is int and value['paid_usd_ceiling'] == 0 and
        value['private'] is True and value['internet'] is False and value['prior_sessions_reconciled'] is True and
        isinstance(value['rules_materials_review_ref'], str) and bool(value['rules_materials_review_ref']) and
        all(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] > 0
            for key in ('quota_hours_available', 'allocated_gpu_hours_per_quota_hour', 'provider_session_seconds')) and
        value['quota_hours_available'] >= screen['allocated_gpu_hours_upper_bound']/value['allocated_gpu_hours_per_quota_hour'] and
        value['provider_session_seconds'] >= screen['maximum_notebook_wall_seconds'],
        'current finite free quota/session/materials admission required')
    require(datetime.fromisoformat(value['quota_observed_at'].replace('Z', '+00:00')).utcoffset() is not None,
            'timezone-qualified current quota observation required')
    if current:
        import time
        stamp=datetime.fromisoformat(value['quota_observed_at'].replace('Z','+00:00')).timestamp()
        age=(time.time() if now_epoch is None else now_epoch)-stamp
        require(-5<=age<=3600,'quota observation must be no more than one hour old and at most five seconds future at runtime admission')
    require('task_child_seconds' in screen and set(screen['task_child_seconds'])==set(screen['task_ids']),
            'exact calibration barrier cost closure required')
    prefix=[sum(screen['task_child_seconds'][job['task_id']] for job in screen['workload_order']
        if job['rank']==rank and job['job_id'] in screen['calibration_jobs']) for rank in range(4)]
    suffix=[sum(screen['task_child_seconds'][job['task_id']] for job in screen['workload_order']
        if job['rank']==rank and job['job_id'] not in screen['calibration_jobs']) for rank in range(4)]
    require(screen['calibration_prefix_lane_seconds']==prefix and screen['post_calibration_suffix_lane_seconds']==suffix and
        screen['barrier_aware_reserved_seconds']==max(prefix)+max(suffix) and max(prefix)+max(suffix) <=
        screen['maximum_notebook_wall_seconds']-screen['startup_seconds']-screen['packaging_reserve_seconds']-300,
        'calibration barrier reservations plus replay exceed bounded session')


def verify_runtime_tree(root, *, allow_fixture=False, require_approved=True, current_resource=True):
    root = Path(root); screen = parse_json((root/'screen.json').read_bytes())
    require(screen['format'] == FORMAT and (not screen['local_fixture'] or allow_fixture) and
        type(screen['approved_for_runtime']) is bool and
        (not require_approved or screen['approved_for_runtime']) and
        (not screen['local_fixture'] or screen['approved_for_runtime'] is False),
        'approved distinct real development screen required')
    for name, expected in screen['payload_sha256'].items():
        path = root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path) == expected,
                'immutable screen payload differs: '+name)
    validate_attachment(screen['resource_attachment'],SCIENTIFIC_SCOPE)
    challenges = parse_json((root/'challenges.json').read_bytes())
    plans = {key: parse_json((root/key/'plan.json').read_bytes()) for key in ('interleaved-r1', 'interleaved-r2', 'deferred-r1', 'deferred-r2')}
    require(screen['challenges_digest'] == digest(challenges) and screen['workload_order_digest'] == digest(screen['workload_order']),
            'screen input/workload binding differs')
    if screen['approved_for_runtime']:
        contract=parse_json((root/'material-contract.json').read_bytes())
        external={name:(root/name).read_bytes() for name in material_files(contract)}
        require(screen['native_notebook_notice_closure'] is True and native_notice_closure(contract,external),
            'admitted screen requires exact native source notice closure')
        validate_resource_admission(screen['resource_admission'], screen,current=current_resource)
    return screen, plans, challenges


def render(screen, payload, *, entrypoint='tools/nvarc_e10_screen.py', description=None):
    probe = entrypoint == 'tools/nvarc_e10_probe.py'
    body = '''import base64,hashlib,json,os,signal,subprocess,sys,time,zlib
from pathlib import Path
START=time.monotonic()
'''
    body += 'PACKED='+repr({key: base64.b64encode(zlib.compress(value, 9)).decode() for key, value in sorted(payload.items())})+'\n'
    body += 'HASHES='+repr({key: hashlib.sha256(value).hexdigest() for key, value in sorted(payload.items())})+'\n'
    body += 'ENTRYPOINT='+repr(entrypoint)+'\n'
    body += '''screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'])))
if screen['approved_for_runtime'] is not True or screen['local_fixture'] is not False:
    raise RuntimeError('inert E10 package: current free resource/materials admission required')
work=Path('/kaggle/working')/screen['screen_id']
if work.exists(): raise RuntimeError('new immutable E10 runtime directory required')
work.mkdir()
for name,packed in PACKED.items():
    decoder=zlib.decompressobj();raw=decoder.decompress(base64.b64decode(packed,validate=True),8*1024**2)
    if not decoder.eof or decoder.unused_data or hashlib.sha256(raw).hexdigest()!=HASHES[name]:
        raise RuntimeError('exact bounded E10 payload differs: '+name)
    path=work/name
    if not path.resolve().is_relative_to(work.resolve()): raise RuntimeError('confined E10 payload required')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
paths=[Path(path) for path in sys.path if Path(path).is_absolute() and Path(path).is_relative_to('/kaggle/usr/lib/notebooks')]
matches=[path for path in dict.fromkeys(paths) if (path/'qwen3.patch').is_file()]
if len(paths)>32 or len(matches)!=1: raise RuntimeError('one exact original offline dependency notebook mount required')
env=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(work),
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHONIOENCODING='utf-8')
command=[sys.executable,str(work/ENTRYPOINT),'--root',str(work),'--dependency',str(matches[0]),
    '--started',str(START),'--owner-pid',str(os.getpid())]
sys.path.insert(0,str(work))
from tools.nvarc_process_supervisor import supervise
observation=supervise(command,env=env,cwd=work,started=START,
    total_seconds=screen['maximum_notebook_wall_seconds'],cleanup_seconds=screen.get('cleanup_reserve_seconds',120))
code=observation['returncode']
print(json.dumps({'outer_supervision':observation,'run_id':screen['screen_id']}),flush=True)
destination=work.parent/(screen['screen_id']+'.zip')
from IPython.display import display,FileLink
if destination.is_file(): display(FileLink(str(destination)))
if code!=0 or observation['timed_out'] or not observation['confirmed_stopped']:
    raise RuntimeError('E10 screen incomplete or failed; retain exact terminal and evidence')
'''
    if probe:
        body = body.replace("if screen['approved_for_runtime'] is not True or screen['local_fixture'] is not False:",
            """owner_editor=(screen.get('approved_for_owner_editor') is True and screen.get('owner_editor_only') is True
    and screen.get('agent_execution_authorized') is False and screen.get('kernel_execution_type')=='QUICK_SAVE')
if (screen['approved_for_runtime'] is not True and not owner_editor) or screen['local_fixture'] is not False:""")
        body = body.replace("command=[sys.executable,str(work/ENTRYPOINT)",
            "command=[sys.executable,str(work/'tools/nvarc_probe_bootstrap.py')")
        body = body.replace("cleanup_seconds=screen.get('cleanup_reserve_seconds',120))",
            "cleanup_seconds=screen.get('cleanup_reserve_seconds',120),capture_path=work/'coordinator-output.log')")
        body = body.replace("code=observation['returncode']", """code=observation['returncode']
from tools.nvarc_probe_bootstrap import finalize
diagnostics=finalize(work,observation,HASHES['screen.json'])
excerpt=diagnostics.pop('coordinator_diagnostic_excerpt')
if excerpt: print('Bounded coordinator diagnostic tail:\\n'+excerpt,flush=True)
print(json.dumps({'probe_diagnostics':diagnostics},ensure_ascii=False),flush=True)""")
    compile(body, 'offline-e10-screen-notebook', 'exec')
    return {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': description or ['Private E10 development screen.\n',
            'Visible demonstrations/test inputs only. Two schedules × two technical repeats.\n',
            'No official submission, evaluator answers, paid execution or quality claim.\n']},
            {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': body.splitlines(keepends=True)},
            {'cell_type': 'markdown', 'metadata': {}, 'source': [
                'Download an already finalized exact-run ZIP independently of the main cell.\n',
                'No archive creation or recovery. Failed-run evidence remains downloadable; native evidence, exit and promotion need separate review.\n']},
            render_download_cell(screen)]}


def stage(package, screen, plans, payload):
    package = Path(package); require(not package.exists(), 'new immutable E10 package directory required')
    (package/'runtime').mkdir(parents=True); (package/'kernel').mkdir()
    for name, body in payload.items():
        path = package/'runtime'/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    write(package/'kernel/notebook.ipynb', render(screen, payload))
    exemplar = next(iter(plans.values()))
    metadata = {'id': 'danielwuu/'+screen['screen_id'], 'title': screen['screen_id'], 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'machine_shape': 'NvidiaL4', 'docker_image': exemplar['docker_image'], 'docker_image_pinning_type': 'original',
        'dataset_sources': [], 'kernel_sources': ['sorokin/pip-install-unsloth-flash-patch'],
        'competition_sources': screen['resource_attachment']['competition_sources'], 'model_sources': exemplar['model_sources']}
    write(package/'kernel/kernel-metadata.json', metadata)
    write(package/'cli-handoff.json', cli_handoff(screen))
    write(package/'package-manifest.json', {'format': 'irisx/e10-package-manifest-v1', 'screen_digest': digest(screen),
        'files_sha256': {path.relative_to(package).as_posix(): sha(path) for path in sorted(package.rglob('*')) if path.is_file()}})
    return preflight(package, allow_fixture=screen['local_fixture'])


def preflight(package, *, allow_fixture=False, expected_manifest_sha256=None):
    package = Path(package); manifest = parse_json((package/'package-manifest.json').read_bytes())
    if expected_manifest_sha256 is not None:
        require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256) and
            sha(package/'package-manifest.json') == expected_manifest_sha256,
            'independently retained immutable package binding differs')
    require(not package.is_symlink() and not any(path.is_symlink() for path in package.rglob('*')) and
        manifest['files_sha256'] == {path.relative_to(package).as_posix(): sha(path) for path in package.rglob('*')
            if path.is_file() and path.relative_to(package).as_posix() != 'package-manifest.json'}, 'closed immutable E10 package inventory differs')
    screen, plans, _ = verify_runtime_tree(package/'runtime', allow_fixture=allow_fixture, require_approved=False,current_resource=False)
    payload = {name: (package/'runtime'/name).read_bytes() for name in screen['payload_sha256']}
    payload['screen.json'] = canonical(screen)
    config = {key: next(iter(plans.values()))[key] for key in CONFIG_FIELDS}
    config['native_source_learning_rates'] = next(iter(plans.values()))['native_source_learning_rates']
    contract=parse_json((package/'runtime/material-contract.json').read_bytes())
    external = {name: (package/'runtime'/name).read_bytes() for name in (EXTERNAL_FILES if screen['local_fixture'] else material_files(contract))}
    if (package/'runtime/verified-tokenizer.json').is_file():
        external['verified-tokenizer.json'] = (package/'runtime/verified-tokenizer.json').read_bytes()
    expected_screen, expected_plans, expected_payload = construct(screen['screen_id'], screen['source_commit'],
        parse_json((package/'runtime/challenges.json').read_bytes()),
        parse_json((package/'runtime/partition.json').read_bytes()), external, config,
        parse_json((package/'runtime/material-contract.json').read_bytes()),
        {key: parse_json((package/'runtime/materials'/ (key+'.json')).read_bytes())
            for key in parse_json((package/'runtime/task-material-index.json').read_bytes())},
        resource_admission=screen['resource_admission'], fixture=screen['local_fixture'],
        preprocessing_environment=screen['preprocessing_environment'], session_seconds=screen['maximum_notebook_wall_seconds'],
        resource_check_current=False,rank_plan=screen['rank_plan'])
    closed_names = {'runtime/'+name for name in expected_payload} | {
        'kernel/notebook.ipynb', 'kernel/kernel-metadata.json', 'cli-handoff.json'}
    require(set(manifest['files_sha256']) == closed_names, 'exact closed E10 package membership differs')
    require(parse_json((package/'cli-handoff.json').read_bytes()) == cli_handoff(screen),
            'exact offline E10 CLI provider-cap handoff differs')
    require(screen == expected_screen and plans == expected_plans and payload == expected_payload,
            'source/config/budget/workload reconstruction differs')
    require(parse_json((package/'kernel/notebook.ipynb').read_bytes()) == render(screen, payload) and
        manifest['screen_digest'] == digest(screen), 'exact offline E10 notebook reconstruction differs')
    exemplar = next(iter(plans.values()))
    require(parse_json((package/'kernel/kernel-metadata.json').read_bytes()) == {
        'id': 'danielwuu/'+screen['screen_id'], 'title': screen['screen_id'], 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'machine_shape': 'NvidiaL4', 'docker_image': exemplar['docker_image'], 'docker_image_pinning_type': 'original',
        'dataset_sources': [], 'kernel_sources': ['sorokin/pip-install-unsloth-flash-patch'],
        'competition_sources': attachment(SCIENTIFIC_SCOPE)['competition_sources'], 'model_sources': exemplar['model_sources']},
        'exact private offline development metadata differs')
    return {'screen_id': screen['screen_id'], 'screen_digest': digest(screen),
        'package_manifest_sha256': sha(package/'package-manifest.json'),
        'offline_package_verified': True, 'approved_for_runtime': screen['approved_for_runtime'],
        'tasks': screen['tasks'], 'tests': screen['tests'], 'task_runs': screen['task_runs'],
        'external_calls': 0, 'real_gpu_screen_run': False, 'quality_gain_measured': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True)
    for name in ('materials', 'material-contract', 'template', 'tokenizer', 'challenges', 'partition', 'resource-admission','rank-plan'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--screen-id'); parser.add_argument('--source-commit')
    parser.add_argument('--session-seconds', type=int, choices=(10800, 18000), default=10800)
    parser.add_argument('--expected-manifest-sha256'); args = parser.parse_args()
    if args.action == 'preflight': result = preflight(args.package, expected_manifest_sha256=args.expected_manifest_sha256)
    else:
        require(re.fullmatch('[0-9a-f]{40}', args.source_commit or ''), 'exact implementation commit required')
        for name in LOCAL_FILES+('tools/nvarc_native_ttt_budget.py', 'tools/nvarc_native_ttt_schedule.py'):
            committed = subprocess.run(['git', 'show', args.source_commit+':'+name], cwd=ROOT,
                                       capture_output=True, check=True).stdout
            require(committed == (ROOT/name).read_bytes(), 'freeze requires exact committed implementation: '+name)
        raw, config, contract = read_materials(args.materials, args.material_contract, args.template, args.tokenizer)
        challenges = parse_json(args.challenges.read_bytes()); partition = parse_json(args.partition.read_bytes())
        materials = task_materials(challenges, args.materials, args.tokenizer)
        import numpy as np
        import tokenizers
        preprocessing = {'python': sys.version.split()[0], 'numpy': np.__version__, 'tokenizers': tokenizers.__version__}
        admission = parse_json(args.resource_admission.read_bytes()) if args.resource_admission else None
        screen, plans, payload = construct(args.screen_id, args.source_commit, challenges, partition, raw, config, contract,
                                           materials, resource_admission=admission, preprocessing_environment=preprocessing,
                                           session_seconds=args.session_seconds,rank_plan=parse_json(args.rank_plan.read_bytes()) if args.rank_plan else None)
        result = stage(args.package, screen, plans, payload)
    print(json.dumps(result))


if __name__ == '__main__': main()
