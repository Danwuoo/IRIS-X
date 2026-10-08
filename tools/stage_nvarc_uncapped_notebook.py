"""Build a genuinely new manual, private, uncapped QUICK_SAVE notebook offline."""
from __future__ import annotations
import argparse
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.nvarc_native_multitask import canonical,digest,require

RUN_ID='stage4-uncapped-20261008-001'
REF='danielwuu/stage4-uncapped-ttt128-20261008-3baff209a1'
SLUG=REF.split('/')[1]
CONFIG_NAME='CONFIRM_UNCAPPED_OWNER_RUN'
SAVE_AUTHORIZATION='Sentinel_430508333a308191b38745cab592170b'
SCIENCE_AUTHORIZATION='Sentinel_443db39890e881918ba30b72da871e0d'
FROZEN_PLAN_SHA256='45a833b265f85fae7de4a431aca0ecad25be47f9f08b448cb2b9a667db571981'
NEW_FILES=('tools/stage_nvarc_uncapped_notebook.py','tools/nvarc_uncapped_runtime.py',
    'tools/nvarc_uncapped_entry.py','tools/nvarc_uncapped_artifacts.py',
    'tools/nvarc_uncapped_inference.py','tools/nvarc_uncapped_source.py','tools/nvarc_uncapped_training.py','tools/nvarc_original_ast_binding.py')
RESOURCE_CAPS=('cleanup_reserve_seconds','finalization_reserve_seconds','generation_seconds',
    'inference_reserve_seconds','maximum_aggregate_host_rss_bytes','maximum_archive_uncompressed_bytes',
    'maximum_generation_forwards','maximum_inference_event_bytes','maximum_inference_input_tokens',
    'maximum_inference_ledger_bytes','maximum_notebook_wall_seconds','maximum_processed_sequences_per_test',
    'maximum_processed_sequences_total','maximum_training_seconds','maximum_verification_forwards',
    'maximum_worker_cuda_allocated_bytes','maximum_worker_host_rss_bytes','maximum_worker_seconds',
    'minimum_free_working_bytes','per_test_seconds','reset_reserve_seconds','startup_seconds',
    'verification_reserve_seconds','source_dfs_wall_seconds','archive_member_count_cap',
    'archive_member_bytes_cap','observer_row_cap','coordinator_capture_bytes_cap')
SCIENTIFIC=dict(training_updates_per_task=128,training_epochs=1,test_cases=6,searches_per_test=1,
    dfs_probability_floor=.2,verification_schedule='interleaved',source_views=16,source_batch_size=4,
    verification_views=8,grid_max_rows=30,grid_max_columns=30,answer_grammar_tokens=931,
    model_context_tokens=8192,displayed_guesses=2)


def sha(body):return hashlib.sha256(body).hexdigest()


def source_bytes(commit):
    require(re.fullmatch('[0-9a-f]{40}',commit or ''),'full committed uncapped source identity required')
    result={}
    for name in NEW_FILES:
        body=subprocess.run(['git','show',commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout
        require(body==(ROOT/name).read_bytes(),'committed uncapped source differs: '+name)
        ast.parse(body,filename=name);result[name]=body
    return result


def construct_values(parent,raw,commit,science_confirmation=None):
    require(science_confirmation in (None,SCIENCE_AUTHORIZATION),'exact owner single-search confirmation required')
    require(parent['run_id']=='stage4-e13-search-budget-20261008-001' and
        parent['source_commit']=='23018f6aaaba81ca7281c2893a1c4b92c45576be' and
        sha(canonical(parent))==FROZEN_PLAN_SHA256,'exact immutable failed E13 parent required')
    require(set(raw)==set(parent['payload_sha256']) and
        all(sha(body)==parent['payload_sha256'][name] for name,body in raw.items()),'preserve exact frozen source/material bytes')
    raw=dict(raw)
    plan=copy.deepcopy(parent)
    for key in ('arm_order','arm_order_rule','arm_contracts','per_arm_caps','e13_process_policy',
        'paired_resource_proposal','owner_editor_admission','raw_returned_policy','processed_sequence_policy'):
        plan.pop(key,None)
    plan.update(format='irisx/stage4-uncapped-owner-editor-v1',run_id=RUN_ID,screen_id=RUN_ID,
        source_commit=commit,notebook_ref=REF,notebook_numeric_id=None,expected_notebook_version=1,
        expected_previous_version=None,expected_previous_script_version_id=None,
        kernel_execution_type='QUICK_SAVE',owner_editor_only=True,agent_execution_authorized=False,
        approved_for_runtime=False,approved_for_owner_editor=True,publication_authorized=True,
        resource_admission=None,resource_policy='no-program-capacity-or-time-caps',
        removed_resource_caps=list(RESOURCE_CAPS),**{key:None for key in RESOURCE_CAPS},
        scientific_contract=dict(SCIENTIFIC),scientific_design_confirmed=science_confirmation is not None,
        scientific_design_confirmation=science_confirmation,save_authorization_ref=SAVE_AUTHORIZATION,
        generation_budget_profile='native-single-uncapped-search',resource_budget_profile='owner-manual-no-program-caps',
        test_executions=6,training_reuse='one native TTT128 epoch per task followed by one uncapped search per test',
        scientific_factor='single search to native completion; removes resource ceilings, retains source p=.2 and finite output grammar',
        cache_policy='fresh uncapped adapter and cache state; each of the original four batches starts with uncached prefill',
        rng_policy='original task training and source-view randomization; no redundant identical second arm',
        training_token_cap_policy='exact original128 public rows and token digests are scientific identity checks',
        qualification_policy='CPU structure/hash proof; no independent native-logit numerical replay or correctness claim',
        output_policy='full streamed hash-chain and ZIP64 truth-free evidence; no artificial byte or duration cap',
        source_replay_policy='pinned source bytes preserved; exact audited AST removal of the sole DFS wall-clock while condition',
        physical_limits_warning='Machine RAM/VRAM/disk and Kaggle quota/session limits remain. Full disk/OOM/provider termination may prevent completion or archive creation.',
        numerical_replay='retained input/NLL receipts and structural verification; native logits are not independently replayed')
    plan['lineage']['uncapped_parent']=dict(run_id=parent['run_id'],plan_sha256=sha(canonical(parent)),
        source_commit=parent['source_commit'],notebook_ref=parent['notebook_ref'],notebook_version=12,
        immutable=True,authority_inherited=False)
    plan['lineage']['experiment']='distinct new owner-only uncapped notebook, not another old-notebook version'
    raw['frozen-e13-plan.json']=canonical(parent)
    raw.update(source_bytes(commit))
    plan['source_files_sha256'].update({name:sha(raw[name]) for name in NEW_FILES})
    plan['payload_sha256']={name:sha(body) for name,body in sorted(raw.items())}
    from tools.nvarc_uncapped_runtime import verify_plan
    verify_plan(plan)
    raw['plan.json']=raw['screen.json']=canonical(plan)
    return plan,raw


def construct(frozen_root,commit,science_confirmation=None):
    frozen_root=Path(frozen_root);parent=json.loads((frozen_root/'plan.json').read_bytes())
    raw={name:(frozen_root/name).read_bytes() for name in parent['payload_sha256']}
    return construct_values(parent,raw,commit,science_confirmation)


def metadata(plan):
    return dict(id=REF,title=SLUG,code_file='notebook.ipynb',language='python',kernel_type='notebook',
        is_private=True,enable_gpu=True,enable_internet=False,machine_shape='NvidiaL4',dataset_sources=[],
        competition_sources=['arc-prize-2026-arc-agi-2'],kernel_sources=['sorokin/pip-install-unsloth-flash-patch/2'],
        model_sources=['sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'],
        docker_image=plan['docker_image'],docker_image_pinning_type='original')


def render(plan,raw):
    pin=sha(canonical(plan));packed={name:base64.b64encode(zlib.compress(body,9)).decode() for name,body in sorted(raw.items())}
    hashes={name:sha(body) for name,body in sorted(raw.items())}
    body='''import base64,hashlib,json,os,sys,zlib
from pathlib import Path
'''
    body+='PACKED='+repr(packed)+'\nHASHES='+repr(hashes)+'\nEXPECTED_PLAN_SHA256='+repr(pin)+'\n'
    body+='''screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'],validate=True)))
if hashlib.sha256(zlib.decompress(base64.b64decode(PACKED['screen.json']))).hexdigest()!=EXPECTED_PLAN_SHA256:
    raise RuntimeError('exact uncapped plan differs')
if not screen['scientific_design_confirmed']:
    raise RuntimeError('experimental design has not been approved; do not run this draft')
if screen['kernel_execution_type']!='QUICK_SAVE' or screen['agent_execution_authorized'] is not False:
    raise RuntimeError('manual QuickSave-only package required')
work=Path('/kaggle/working')/screen['run_id']
if work.exists():raise RuntimeError('one new immutable owner runtime directory required; do not rerun')
work.mkdir()
for name,packed in PACKED.items():
    raw=zlib.decompress(base64.b64decode(packed,validate=True))
    if hashlib.sha256(raw).hexdigest()!=HASHES[name]:raise RuntimeError('exact payload differs: '+name)
    path=work/name
    if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(work.resolve()):
        raise RuntimeError('unsafe payload path')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
sys.path.insert(0,str(work))
from tools.nvarc_uncapped_runtime import verify_runtime,write_confirmation
from tools.nvarc_uncapped_artifacts import supervise,atomic_json,stream_archive,full_diagnostic
verify_runtime(work,EXPECTED_PLAN_SHA256)
write_confirmation(work,screen,CONFIRM_UNCAPPED_OWNER_RUN)
paths=[Path(path) for path in sys.path if Path(path).is_absolute() and Path(path).is_relative_to('/kaggle/usr/lib/notebooks')]
matches=[path for path in dict.fromkeys(paths) if (path/'qwen3.patch').is_file()]
if len(matches)!=1:raise RuntimeError('one exact original offline dependency notebook mount required')
env=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(work),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    HF_DATASETS_OFFLINE='1',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',
    TOKENIZERS_PARALLELISM='false',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true')
command=[sys.executable,str(work/'tools/nvarc_uncapped_entry.py'),'--root',str(work),'--dependency',str(matches[0]),
    '--owner-pid',str(os.getpid()),'--expected-plan-sha256',EXPECTED_PLAN_SHA256]
observation=supervise(command,cwd=work,env=env,capture_path=work/'coordinator-output.log')
atomic_json(work/'outer-supervision.json',observation)
if observation.get('confirmed_stopped') is not True:raise RuntimeError('process stop unconfirmed; do not archive live evidence')
destination=work.parent/(screen['run_id']+'.zip')
try:
    archive_receipt=stream_archive(work,destination)
    atomic_json(work.parent/(screen['run_id']+'-archive-receipt.json'),archive_receipt)
except BaseException as error:
    print(full_diagnostic(error,'archive-finalization'))
    raise
from IPython.display import FileLink,display
display(FileLink(str(destination)))
print('Full evidence archived. STOP THE EDITOR SESSION after downloading. Platform limits still apply.')
if observation.get('success') is not True or observation.get('returncode')!=0 or observation.get('errors'):
    raise RuntimeError('runtime or supervision failed; the archive retains the available full diagnostics')
'''
    code=lambda text:dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=text.splitlines(keepends=True))
    guard="if type(globals().get('CONFIRM_UNCAPPED_OWNER_RUN')) is not bool or CONFIRM_UNCAPPED_OWNER_RUN is not True:\n    print('Saved only. Set the visible confirmation to True yourself only after reviewing all warnings.')\nelse:\n"
    guarded=guard+''.join('    '+line if line.strip() else line for line in body.splitlines(keepends=True))
    config='''# MANUAL OWNER START ONLY. Saving this notebook never starts a run.
# Setting True declares: paid scaling is OFF, you checked current free quota,
# and you accept that no program runtime, search, RAM or output-byte ceiling exists.
# Real machine/platform limits can stop work; full disk/OOM can prevent final export.
# Keep this False unless you personally intend to start now. Stop the session afterward.
CONFIRM_UNCAPPED_OWNER_RUN = False
'''
    disclosure='''# New uncapped TTT128 notebook (manual QUICK_SAVE)

This is a NEW private notebook. It is saved without execution. The default confirmation is False; the assistant has no run authorization.

Program-imposed search/training/startup/watchdog, forward/input-token/candidate, telemetry/log, memory-reservation and archive limits are removed. Logs are streamed without silent truncation and archives use ZIP64. This does not make resources infinite: Kaggle session/quota limits and actual RAM/VRAM/disk capacity still apply. Long search may exhaust free quota or disk; a provider kill or full disk may prevent a final archive. Partial files and explicit failures remain; do not assume completion.

The scientific method still has a finite workload: the same four exposed public tasks/six tests, one original 128-row/128-update TTT epoch per task (512 total), then one search per test. Original p=.2, INTERLEAVED verification, 16 source views, eight verifier views, grid/token grammar, 8192 model context and two displayed guesses remain. Removing 120/240-second caps means this is not a timed paired comparison.

Same pinned Qwen3-4B SFT139, original Torch/Unsloth/FlashAttention dependency mount and offline setup. Private, Internet OFF, paid spending USD 0, pay-to-scale OFF. No quota bypass, cloud migration, official submission, hidden answers, scoring or promotion. Exact provenance and grammar checks remain.

You must manually inspect current free quota and keep paid scaling OFF before starting. No resource sufficiency is promised. Set the configuration True, run once, download the complete evidence if available, then STOP THE EDITOR SESSION.
'''
    nb=dict(nbformat=4,nbformat_minor=5,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3'),
        language_info=dict(name='python'),irisx_execution_mode='QUICK_SAVE',irisx_new_notebook=True),
        cells=[dict(cell_type='markdown',metadata={},source=disclosure.splitlines(keepends=True)),code(config),code(guarded)])
    for cell in nb['cells'][1:]:compile(''.join(cell['source']),'uncapped-notebook','exec')
    return nb


def stage(package,frozen_root,commit,science_confirmation=None):
    package=Path(package);require(not package.exists(),'new immutable package directory required')
    plan,raw=construct(frozen_root,commit,science_confirmation)
    files={'runtime/'+name:body for name,body in raw.items()}
    files.update({'kernel/notebook.ipynb':canonical(render(plan,raw)),
        'kernel/kernel-metadata.json':canonical(metadata(plan))})
    for name,body in files.items():
        path=package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    manifest=dict(format='irisx/new-uncapped-quicksave-package-v1',run_id=RUN_ID,ref=REF,
        files_sha256={name:sha(body) for name,body in sorted(files.items())})
    (package/'package-manifest.json').write_bytes(canonical(manifest))
    return preflight(package,publication=False)


def preflight(package,*,publication=True):
    package=Path(package);manifest=json.loads((package/'package-manifest.json').read_bytes())
    files={p.relative_to(package).as_posix():p.read_bytes() for p in package.rglob('*') if p.is_file() and p.name!='package-manifest.json'}
    require(not any(p.is_symlink() for p in (package,*package.parents,*package.rglob('*'))),'regular package only')
    require(manifest['files_sha256']=={name:sha(body) for name,body in sorted(files.items())},'closed exact package differs')
    plan=json.loads(files['runtime/plan.json'])
    from tools.nvarc_uncapped_runtime import verify_runtime
    verify_runtime(package/'runtime',sha(files['runtime/plan.json']))
    require(source_bytes(plan['source_commit'])=={name:files['runtime/'+name] for name in NEW_FILES},'committed active source differs')
    raw={name.removeprefix('runtime/'):body for name,body in files.items() if name.startswith('runtime/')}
    parent=json.loads(raw['frozen-e13-plan.json'])
    expected_plan,expected_raw=construct_values(parent,{name:raw[name] for name in parent['payload_sha256']},plan['source_commit'],plan['scientific_design_confirmation'])
    require(plan==expected_plan and raw==expected_raw,'exact frozen material plus declared uncapped transformation differs')
    require(files['kernel/notebook.ipynb']==canonical(render(plan,raw)) and
        files['kernel/kernel-metadata.json']==canonical(metadata(plan)),'exact notebook/metadata rendering differs')
    if publication:require(plan['scientific_design_confirmed'] is True and bool(plan['scientific_design_confirmation']),
        'owner scientific-design confirmation still pending')
    # Default execution must be genuinely inert, not merely an execution-type field.
    namespace={}
    for cell in json.loads(files['kernel/notebook.ipynb'])['cells'][1:]:exec(compile(''.join(cell['source']),'inert-check','exec'),namespace)
    require(namespace[CONFIG_NAME] is False and not any(key in namespace for key in ('work','command','screen','PACKED')),
        'default cells unexpectedly entered setup/runtime')
    return dict(run_id=RUN_ID,ref=REF,package_manifest_sha256=sha(canonical(manifest)),plan_sha256=sha(raw['plan.json']),
        notebook_sha256=sha(files['kernel/notebook.ipynb']),offline_package_verified=True,
        scientific_design_confirmed=plan['scientific_design_confirmed'],kernel_execution_type='QUICK_SAVE',
        agent_execution_authorized=False,provider_calls=0,model_calls=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('stage','preflight'))
    p.add_argument('--package',type=Path,required=True);p.add_argument('--frozen-runtime',type=Path)
    p.add_argument('--source-commit');p.add_argument('--science-confirmation')
    args=p.parse_args()
    result=stage(args.package,args.frozen_runtime,args.source_commit,args.science_confirmation) if args.action=='stage' else preflight(args.package)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
