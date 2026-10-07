"""Offline, immutable four-task native TTT resource calibration packaging.

Default output is inert. Distinct explicit owner-Editor and one-run admissions
cannot be combined. Provider operations remain outside this offline builder.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, require, validate_challenges, write
from tools.stage_nvarc_e10_screen import (CONFIG_FIELDS, read_materials, task_materials,
    validate_baseline, material_files, native_notice_closure, render as render_base, sha)
from tools.stage_nvarc_e10_probe import FILES as PROBE_FILES, UNAVAILABLE_RESOURCE_FIELDS
from tools.nvarc_resource_attachment import attachment, validate_attachment
from tools.nvarc_dependency_readproof import PROOF_FILE, VERSIONED_REF, bind_contract, read_contract
from tools.nvarc_notebook_controls import cli_handoff

FORMAT = 'irisx/stage4-e10-native-ttt-resource-probe-v1'
RUN_ID = 'stage4-e10-probe-ttt-20261006-001'
NOTEBOOK = 'danielwuu/stage4-e10-probe-20261006-001'
ADMISSION = 'irisx/stage4-native-ttt-probe-owner-editor-admission-v1'
RUN_ADMISSION = 'irisx/stage4-native-ttt-probe-single-run-admission-v1'
SCOPE = 'frozen public solver-visible development challenges only'
FROZEN_PLAN_SHA256 = '88d5c2420a13fd0c13807b8c59c0734764491620edaf256719028a41b224bc38'
FROZEN_CHALLENGES_SHA256 = 'b346c4958c9d4be369d62695ff0e8e490f6914922153f23f302b5698e4aaca25'
TASKS = ('195c6913', 'aa4ec2a5', 'a47bf94d', 'a25697e4')
COSTS = ((442624, 220160, 3458), (408320, 203008, 3198),
         (373632, 185664, 2922), (364416, 181056, 2868))
ROW_DIGESTS = ('2560a6998b99c866516593acb865610aa5d5c84dab55077691334e67c2c4e7dd',
    'ab78ffab52637be202d69521f215869f0c97e23572443ac5c74e429c50b50bb2',
    '93790369380691e105cb60a519082145b8887899cafd7c49f3e051d7a115ec1c',
    'd94cada0e88448834e53854157477f838636b474913f007128537d020d73f7aa')
TEXT_DIGESTS = ('e6b63b2a13de69a5f0e3a1c9b281a6223ae9cc663a5c9cad5fecac8e32d69dc2',
    'db95d52b5c70649959d441781bc9e617492ae88e1dedca4c12144ca201b3774d',
    '347c168c376ce7d27fcd987f9d363de13b5b7e524434dd3664951b71d61f82ba',
    '983222c70508689ee6bf97886c7a559c98e459dbd59b73f74b3296dc514e2a5c')
FILES = tuple(sorted(set(PROBE_FILES) | {'tools/stage_nvarc_e10_ttt_probe.py',
    'tools/nvarc_e10_ttt_probe.py'}))
BOUNDS = {'parallel_workers':4, 'maximum_notebook_wall_seconds':3600, 'startup_seconds':900,
    'maximum_worker_seconds':2100, 'maximum_training_seconds':1800, 'reset_reserve_seconds':180,
    'finalization_reserve_seconds':600, 'cleanup_reserve_seconds':600,
    'maximum_training_forwards':512, 'maximum_training_backwards':512, 'optimizer_steps':512,
    'maximum_training_input_tokens':1588992, 'maximum_training_supervised_tokens':789888,
    'maximum_control_forwards':28, 'maximum_control_input_tokens':672,
    'per_worker_training_steps':128, 'per_worker_forwards':7, 'per_worker_physical_input_tokens':168,
    'generations':0, 'paid_usd_ceiling':0}


def select(frozen_plan, challenges):
    require(sha_bytes(canonical(frozen_plan)) == FROZEN_PLAN_SHA256 and
        sha_bytes(canonical(challenges)) == FROZEN_CHALLENGES_SHA256,
        'exact already-frozen exposed development plan/challenges required')
    validate_challenges(challenges)
    specs = frozen_plan['task_specs']
    require(set(specs) == set(challenges) and len(specs) == 24,
        'complete preexisting 24-task public token metadata required')
    order = sorted(specs, key=lambda key: (-specs[key]['training_input_tokens'], key))[:4]
    require(order == list(TASKS), 'four highest preexisting input-token tasks required')
    return {key: {name: specs[key][name] for name in ('training_input_tokens',
        'training_supervised_tokens', 'maximum_sequence_tokens', 'expected_rows_digest', 'texts_digest')}
        for key in order}


def sha_bytes(body): return hashlib.sha256(body).hexdigest()


def frozen_specs():
    return {key:dict(zip(('training_input_tokens','training_supervised_tokens','maximum_sequence_tokens'),costs),
        expected_rows_digest='sha256:'+rows,texts_digest='sha256:'+texts)
        for key,costs,rows,texts in zip(TASKS,COSTS,ROW_DIGESTS,TEXT_DIGESTS)}


def validate_admission(plan, *, required=False):
    admitted = plan.get('owner_editor_admission') is not None
    automatic = plan.get('resource_admission') is not None
    if automatic:
        value = plan['resource_admission']
        require(not admitted and plan.get('approved_for_owner_editor') is False and plan.get('owner_editor_only') is False and
            plan.get('approved_for_runtime') is plan.get('agent_execution_authorized') is True and
            plan.get('kernel_execution_type') == 'SAVE_AND_RUN_ALL', 'distinct approved automatic execution admission required')
        require(type(value) is dict and set(value) == {'format','run_id','owner_instruction_ref','notebook_ref',
            'notebook_numeric_id','expected_notebook_version','kernel_execution_type','provider_session_seconds',
            'private','internet','paid_usd_ceiling','charged_quota_seconds_reserved','quota_snapshot_sha256',
            'quota_observed_at','remaining_free_seconds','provider_reserved_seconds','monitor_after_submission'} and
            value['format'] == RUN_ADMISSION and value['run_id'] == RUN_ID and value['notebook_ref'] == NOTEBOOK and
            value['kernel_execution_type'] == 'SAVE_AND_RUN_ALL' and value['private'] is True and
            value['internet'] is value['monitor_after_submission'] is False and
            all(type(value[k]) is int and value[k] == v for k,v in (('notebook_numeric_id',137327571),
                ('expected_notebook_version',4),('provider_session_seconds',3600),('paid_usd_ceiling',0),
                ('charged_quota_seconds_reserved',14400))) and
            all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in
                ('remaining_free_seconds','provider_reserved_seconds')) and
            value['remaining_free_seconds'] >= 14400 and value['provider_reserved_seconds'] == 0 and
            type(value['owner_instruction_ref']) is str and bool(value['owner_instruction_ref'].strip()) and
            type(value['quota_snapshot_sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['quota_snapshot_sha256']) and
            type(value['quota_observed_at']) is str and datetime.fromisoformat(value['quota_observed_at']).utcoffset() is not None,
            'one exact private free bounded RUN and sufficient observed quota required')
        require(plan.get('notebook_ref') == NOTEBOOK and type(plan.get('notebook_numeric_id')) is int and
            plan['notebook_numeric_id'] == 137327571 and type(plan.get('expected_notebook_version')) is int and
            plan['expected_notebook_version'] == 4, 'one existing notebook version-four RUN required')
        return
    require(plan.get('approved_for_runtime') is False and plan.get('agent_execution_authorized') is False and
        plan.get('resource_admission') is None and plan.get('approved_for_owner_editor') is admitted and
        plan.get('owner_editor_only') is True and
        plan.get('kernel_execution_type') == ('QUICK_SAVE' if admitted else 'INERT') and
        (not required or admitted), 'explicit owner-Editor approval required; automatic execution prohibited')
    require(plan.get('notebook_ref') == NOTEBOOK and plan.get('notebook_numeric_id') == 137327571 and
        type(plan.get('notebook_numeric_id')) is type(plan.get('expected_notebook_version')) is int and
        plan.get('expected_notebook_version') == 4, 'one exact existing notebook version-four save required')
    if admitted:
        value = plan['owner_editor_admission']
        require(type(value) is dict and set(value) == {'format','run_id','owner_instruction_ref',
            'notebook_ref','notebook_numeric_id','expected_notebook_version','kernel_execution_type',
            'agent_execution_authorized'} and value == {'format':ADMISSION, 'run_id':RUN_ID,
            'owner_instruction_ref':value.get('owner_instruction_ref'), 'notebook_ref':NOTEBOOK,
            'notebook_numeric_id':137327571, 'expected_notebook_version':4,
            'kernel_execution_type':'QUICK_SAVE', 'agent_execution_authorized':False} and
            type(value['notebook_numeric_id']) is type(value['expected_notebook_version']) is int and
            value['agent_execution_authorized'] is False and
            type(value['owner_instruction_ref']) is str and bool(value['owner_instruction_ref'].strip()),
            'exact user-approved calibration save admission required')


def construct(source_commit, external, config, contract, challenges, specs, materials,
              dependency_readproof, *, owner_editor_admission=None, resource_admission=None, preprocessing_environment=None):
    require(re.fullmatch('[0-9a-f]{40}', source_commit), 'full implementation commit required')
    validate_baseline(config, external, contract)
    require(native_notice_closure(contract, external), 'native source notice closure required')
    bind_contract(dependency_readproof, parse_json(external['source-inventory.json']))
    require(config['dependency_script_version_id'] == dependency_readproof['script_version_id'],
        'unchanged v2 dependency and five-file selected-byte proof required')
    require(set(challenges) == set(specs) == set(materials) == set(TASKS), 'exact four selected tasks required')
    require(specs == frozen_specs(), 'unchanged frozen task row/text/cost metadata required')
    require(all(type(specs[key][field]) is int for key in TASKS for field in
        ('training_input_tokens','training_supervised_tokens','maximum_sequence_tokens')), 'integer frozen token costs required')
    validate_challenges(challenges)
    for key, costs in zip(TASKS, COSTS):
        material = materials[key]; rows = material['rows']; spec = specs[key]
        require(len(rows) == len(material['texts']) == 128 and digest(rows) == spec['expected_rows_digest'] and
            digest(material['texts']) == spec['texts_digest'] and
            (sum(r['input_tokens'] for r in rows), sum(r['supervised_tokens'] for r in rows),
             max(r['input_tokens'] for r in rows)) == costs == tuple(spec[k] for k in
                ('training_input_tokens','training_supervised_tokens','maximum_sequence_tokens')),
            'exact frozen native texts, row multiset and token costs required: '+key)
    require(type(preprocessing_environment) is dict and set(preprocessing_environment) ==
        {'python','numpy','tokenizers'}, 'explicit CPU preprocessing versions required')
    raw = {name:(ROOT/name).read_bytes() for name in FILES}; raw.update(external)
    for name in ('nvarc_native_ttt_budget.py','nvarc_native_ttt_schedule.py'):
        raw[name] = (ROOT/'tools'/name).read_bytes()
    raw['tools/__init__.py'] = b''
    raw[PROOF_FILE] = canonical(dependency_readproof)
    raw['challenges.json'] = canonical(challenges)
    for key in TASKS: raw['materials/'+key+'.json'] = canonical(materials[key])
    admitted = owner_editor_admission is not None
    automatic = resource_admission is not None
    plan = {**config, 'format':FORMAT, 'screen_id':RUN_ID, 'run_id':RUN_ID,
        'source_commit':source_commit, **BOUNDS, 'task_order':list(TASKS), 'task_ids':list(TASKS),
        'task_specs':specs, 'worker_ids':['0','1','2','3'], 'runtime_torch_version':'2.8.0+cu128',
        'selection':'descending preexisting training_input_tokens only; task_id tie break',
        'frozen_source_plan_sha256':FROZEN_PLAN_SHA256,
        'frozen_source_challenges_sha256':FROZEN_CHALLENGES_SHA256,
        'challenges_digest':digest(challenges), 'material_contract_digest':digest(contract),
        'preprocessing_environment':preprocessing_environment,
        'approved_for_runtime':automatic, 'resource_admission':resource_admission, 'local_fixture':False,
        'approved_for_owner_editor':admitted, 'owner_editor_only':not automatic,
        'agent_execution_authorized':automatic, 'owner_editor_admission':owner_editor_admission,
        'kernel_execution_type':'SAVE_AND_RUN_ALL' if automatic else ('QUICK_SAVE' if admitted else 'INERT'),
        'notebook_ref':NOTEBOOK, 'notebook_numeric_id':137327571, 'expected_notebook_version':4,
        'resource_information_status':'unavailable', 'resource_sufficiency_verified':False,
        'resource_information':{key:None for key in UNAVAILABLE_RESOURCE_FIELDS},
        'provider_timeout_enforcement_observed':False, 'manual_editor_timeout_attested':False,
        'resource_attachment':attachment(SCOPE), 'maximum_worker_host_rss_bytes':16*1024**3,
        'maximum_aggregate_host_rss_bytes':64*1024**3, 'maximum_worker_cuda_allocated_bytes':24*1024**3,
        'minimum_free_working_bytes':10*1024**3, 'maximum_archive_uncompressed_bytes':1024**3,
        'correctness_scored':False, 'promotion':False, 'official_submission':False,
        'generation_paths_enabled':False, 'full_screen_feasibility_established':False,
        'exposure':'already exposed public development; model training exposure unresolved',
        'historical_planning_only':{'native_ttt_008_training_seconds':862,
            'native_ttt_008_parent_seconds':1068, 'native_ttt_008_training_input_tokens':955392,
            'native_ttt_008_cuda_gb_approximate':13.9, 'four_worker_throughput_claim':False},
        'source_provenance':contract['source_provenance'], 'native_notebook_notice_closure':True,
        'complete_dependency_license_closure':False, 'dependency_readproof_digest':digest(dependency_readproof),
        'declared_dependency_source':VERSIONED_REF, 'provider_resolved_dependency_version_verified':False,
        'platform_parent_startup_attested':False,
        'payload_sha256':{name:sha_bytes(body) for name,body in sorted(raw.items())}}
    validate_admission(plan)
    raw.update({'plan.json':canonical(plan), 'screen.json':canonical(plan), 'material-contract.json':canonical(contract)})
    return plan, raw


def verify_runtime(root, *, require_approved=False):
    root = Path(root); plan = parse_json((root/'plan.json').read_bytes())
    require(plan.get('format') == FORMAT and plan.get('run_id') == plan.get('screen_id') == RUN_ID and
        plan == parse_json((root/'screen.json').read_bytes()), 'exact TTT resource-only plan required')
    validate_admission(plan, required=require_approved)
    require(all(type(plan.get(k)) is int and plan[k] == v for k,v in BOUNDS.items()) and
        plan['task_order'] == list(TASKS) and plan['worker_ids'] == ['0','1','2','3'] and
        plan['runtime_torch_version'] == '2.8.0+cu128' and plan['local_fixture'] is False and
        plan['task_specs'] == frozen_specs() and
        all(plan[k] is False for k in ('correctness_scored','promotion','official_submission',
            'generation_paths_enabled','full_screen_feasibility_established')),
        'unchanged four complete epochs, 512 updates, 28 controls, zero generation bounds required')
    validate_attachment(plan['resource_attachment'], SCOPE)
    for name, expected in plan['payload_sha256'].items():
        path = root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path) == expected,
            'immutable TTT resource payload differs: '+name)
    contract = parse_json((root/'material-contract.json').read_bytes())
    require(digest(contract) == plan['material_contract_digest'], 'material contract binding differs')
    external = {name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json'] = (root/'verified-tokenizer.json').read_bytes()
    validate_baseline(plan, external, contract)
    require(native_notice_closure(contract, external), 'native source notice closure required')
    proof = read_contract(root/PROOF_FILE); bind_contract(proof, parse_json(external['source-inventory.json']))
    require(digest(proof) == plan['dependency_readproof_digest'] and
        proof['script_version_id'] == plan['dependency_script_version_id'], 'pinned v2 read-proof differs')
    return plan


def render(plan, raw):
    notebook = render_base(plan, raw, entrypoint='tools/nvarc_e10_probe.py', description=[
        'Private native SFT139 resource calibration: four complete 128-step epochs on four L4s.\n',
        '1,588,992 training input tokens; 789,888 supervised tokens; 28 synthetic control forwards.\n',
        '60-minute internal cap; no generation, ARC score, candidate comparison or promotion.\n'])
    body = ''.join(notebook['cells'][1]['source'])
    old = "str(work/'tools/nvarc_probe_bootstrap.py'),'--root'"
    require(body.count(old) == 1, 'exact bootstrap render hook required')
    body = body.replace(old, "str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'")
    body = body.replace('from tools.nvarc_probe_bootstrap import finalize',
        'from tools.nvarc_e10_ttt_probe import finalize')
    body = body.replace("if code!=0 or observation['timed_out'] or not observation['confirmed_stopped']:",
        "if code!=0 or observation['timed_out'] or not observation['confirmed_stopped'] or not diagnostics.get('final_archive_created'):")
    compile(body, 'native-ttt-probe-notebook', 'exec')
    notebook['cells'][1]['source'] = body.splitlines(keepends=True)
    return notebook


def metadata(plan):
    return {'id':NOTEBOOK, 'title':NOTEBOOK.split('/')[1], 'code_file':'notebook.ipynb', 'language':'python',
        'kernel_type':'notebook', 'is_private':True, 'enable_gpu':True, 'enable_internet':False,
        'machine_shape':'NvidiaL4', 'docker_image':plan['docker_image'], 'docker_image_pinning_type':'original',
        'dataset_sources':[], 'kernel_sources':[VERSIONED_REF],
        'competition_sources':plan['resource_attachment']['competition_sources'], 'model_sources':plan['model_sources']}


def stage(package, plan, raw):
    package = Path(package); require(not package.exists(), 'new immutable TTT probe package required')
    (package/'kernel').mkdir(parents=True)
    for name, body in raw.items():
        path = package/'runtime'/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    write(package/'kernel/notebook.ipynb', render(plan, raw))
    write(package/'kernel/kernel-metadata.json', metadata(plan))
    write(package/'cli-handoff.json', cli_handoff(plan) if plan['approved_for_owner_editor'] or plan['approved_for_runtime'] else {
        'format':'irisx/ttt-probe-inert-handoff-v1', 'run_id':RUN_ID, 'execute_commands':False,
        'approval_pending':True, 'kernel_execution_type':'INERT'})
    write(package/'package-manifest.json', {'format':'irisx/e10-ttt-probe-package-v1', 'plan_digest':digest(plan),
        'files_sha256':{p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob('*')) if p.is_file()}})
    return preflight(package)


def preflight(package, *, expected_manifest_sha256=None):
    package = Path(package); manifest = parse_json((package/'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (package,*package.rglob('*'))) and
        manifest['files_sha256'] == {p.relative_to(package).as_posix():sha(p) for p in package.rglob('*')
            if p.is_file() and p.name != 'package-manifest.json'}, 'closed immutable package inventory differs')
    if expected_manifest_sha256 is not None:
        require(sha(package/'package-manifest.json') == expected_manifest_sha256, 'independent package pin differs')
    root = package/'runtime'; plan = verify_runtime(root)
    contract = parse_json((root/'material-contract.json').read_bytes())
    external = {name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json'] = (root/'verified-tokenizer.json').read_bytes()
    config = {key:plan[key] for key in (*CONFIG_FIELDS,'native_source_learning_rates')}
    expected,raw = construct(plan['source_commit'],external,config,contract,
        parse_json((root/'challenges.json').read_bytes()), plan['task_specs'],
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in TASKS},read_contract(root/PROOF_FILE),
        owner_editor_admission=plan['owner_editor_admission'], resource_admission=plan['resource_admission'],
        preprocessing_environment=plan['preprocessing_environment'])
    require(plan == expected and manifest['plan_digest'] == digest(plan) and
        set(manifest['files_sha256']) == {'runtime/'+name for name in raw} |
            {'kernel/notebook.ipynb','kernel/kernel-metadata.json','cli-handoff.json'} and
        all((root/name).read_bytes() == body for name,body in raw.items()) and
        parse_json((package/'kernel/notebook.ipynb').read_bytes()) == render(plan,raw) and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes()) == metadata(plan),
        'exact reconstruction of TTT plan, source, materials and notebook required')
    require(parse_json((package/'cli-handoff.json').read_bytes()) == (cli_handoff(plan) if plan['approved_for_owner_editor'] or plan['approved_for_runtime'] else {
        'format':'irisx/ttt-probe-inert-handoff-v1', 'run_id':RUN_ID, 'execute_commands':False,
        'approval_pending':True, 'kernel_execution_type':'INERT'}), 'exact owner-only or inert transport handoff required')
    return {'run_id':RUN_ID, 'plan_digest':digest(plan), 'package_manifest_sha256':sha(package/'package-manifest.json'),
        'offline_package_verified':True, 'approved_for_owner_editor':plan['approved_for_owner_editor'],
        'agent_execution_authorized':plan['agent_execution_authorized'], 'new_model_calls':0, 'planned_training_updates':512,
        'planned_control_forwards':28, 'generations':0, 'gpu_probe_run':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('stage','preflight')); parser.add_argument('--package',type=Path,required=True)
    for name in ('materials','material-contract','template','tokenizer','frozen-plan','challenges',
                 'dependency-readproof','owner-editor-admission','resource-admission'): parser.add_argument('--'+name,type=Path)
    parser.add_argument('--source-commit'); parser.add_argument('--expected-manifest-sha256')
    args = parser.parse_args()
    if args.action == 'preflight': value = preflight(args.package,expected_manifest_sha256=args.expected_manifest_sha256)
    else:
        require(__import__('os').environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
            'fresh seed-zero CPU preprocessing required')
        for name in FILES:
            require(subprocess.run(['git','show',args.source_commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout ==
                (ROOT/name).read_bytes(), 'exact committed implementation required: '+name)
        challenges = parse_json(args.challenges.read_bytes()); specs = select(parse_json(args.frozen_plan.read_bytes()),challenges)
        challenges = {key:challenges[key] for key in TASKS}
        external,config,contract = read_materials(args.materials,args.material_contract,args.template,args.tokenizer)
        materials = task_materials(challenges,args.materials,args.tokenizer)
        import platform, numpy, tokenizers
        plan,raw = construct(args.source_commit,external,config,contract,challenges,specs,materials,
            read_contract(args.dependency_readproof),
            owner_editor_admission=parse_json(args.owner_editor_admission.read_bytes()) if args.owner_editor_admission else None,
            resource_admission=parse_json(args.resource_admission.read_bytes()) if args.resource_admission else None,
            preprocessing_environment={'python':platform.python_version(),'numpy':numpy.__version__,'tokenizers':tokenizers.__version__})
        value = stage(args.package,plan,raw)
    print(json.dumps(value))


if __name__ == '__main__': main()
