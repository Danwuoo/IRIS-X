"""Decision 0060: render two immutable owner-Editor public notebooks, offline only."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.nvarc_public_eval import FORMAT, RUNS, INPUT_SHA, sha, validate_plan
from tools.nvarc_native_multitask import canonical, digest, write, require
from tools.arc_kaggle_submission import parse_json, challenge_counts
from tools.stage_nvarc_official import frozen_payloads

INPUT = ROOT/'.irisx/stage3-public-eval-20261005-001/public-challenges.json'
WORKLOAD = ROOT/'.irisx/stage3-public-eval-20261005-001/notebook-workload-profile.json'
DECISION = ROOT/'docs/decisions/0060-save-two-public-evaluation-notebooks.md'
FILES = {'solver.py': 'solver', 'arc_loader.py': 'loader', 'arc_decoder.py': 'decoder',
    'inspection_helpers.py': 'helper', 'nvarc_native_ttt_budget.py': 'budget',
    'nvarc_native_ttt_schedule.py': 'schedule', 'hardware_helpers.py': 'hardware',
    'tools/nvarc_native_solve_runtime.py': 'solve_runtime',
    'tools/nvarc_native_multitask.py': 'multitask', 'tools/arc_kaggle_submission.py': 'exporter',
    'tools/nvarc_public_eval.py': 'public_core', 'tools/nvarc_public_eval_runtime.py': 'public_runtime',
    'tools/nvarc_public_eval_parent.py': 'public_parent',
    'source-inventory.json': 'source_inventory', 'model-inventory.json': 'model_inventory',
    'challenges.json': 'challenges', 'plan.json': 'plan'}


def construct(profile, source_commit):
    require(profile in RUNS and re.fullmatch('[0-9a-f]{40}', source_commit), 'exact profile/implementation commit required')
    old = frozen_payloads(); previous = parse_json(old['plan'])
    require(sha(INPUT) == INPUT_SHA and sha(WORKLOAD) == '12479915fd5bc81336c893315c67cd860932ddc51eb2f78d1b19b6ca0e1a5b52',
            'frozen public input/workload proof differs')
    challenges = parse_json(INPUT.read_bytes()); workload = parse_json(WORKLOAD.read_bytes())
    keys = {'solver', 'loader', 'decoder', 'helper', 'budget', 'schedule', 'hardware',
            'solve_runtime', 'multitask', 'exporter', 'source_inventory', 'model_inventory'}
    raw = {k: old[k] for k in sorted(keys)}; raw['challenges'] = INPUT.read_bytes()
    for key, name in [('public_core', 'nvarc_public_eval.py'), ('public_runtime', 'nvarc_public_eval_runtime.py'),
                      ('public_parent', 'nvarc_public_eval_parent.py')]:
        raw[key] = (ROOT/'tools'/name).read_bytes(); compile(raw[key], name, 'exec')
    retained = ('model_material_digest', 'versions', 'original_peft_parameters', 'original_training_arguments',
        'native_trainer_origins', 'native_checkpoint_flags', 'source_inferred_trainable_layout',
        'original_class_ast_sha256', 'solver_cell_sha256', 'model_instance_version_id', 'dependency_script_version_id',
        'docker_image', 'model_sources', 'competition_sources')
    plan = {k: previous[k] for k in retained}
    run = RUNS[profile]
    plan.update(format=FORMAT, run_id=run, kernel_id='danielwuu/'+run, profile=profile, source_commit=source_commit,
        owner_decision='Decision 0060', owner_decision_sha256=sha(DECISION), approved=True,
        owner_editor_only=True, agent_execution_authorized=False, kernel_execution_type='QUICK_SAVE',
        local_fixture=False, maximum_quick_saves=1, download_archive=run+'.zip',
        maximum_paid_usd=0, maximum_teacher_calls=0, parallel_workers=4, pythonhashseed=0,
        maximum_notebook_wall_seconds=3600 if profile == 'BASE-30' else 14400,
        startup_seconds=900, export_reserve_seconds=300, per_test_seconds=30,
        verification_reserve_seconds=10, task_training_seconds=0 if profile == 'BASE-30' else 1200,
        maximum_optimizer_steps=0 if profile == 'BASE-30' else 15360,
        maximum_training_input_tokens=0 if profile == 'BASE-30' else 30713088,
        maximum_generation_batches=4*172, maximum_generation_forwards=4096*172,
        maximum_verification_forwards=128*172, maximum_control_forwards=4*6+120*7,
        native_source_learning_rates=previous['task_specs']['44f52bb0']['source_learning_rates'],
        challenges_sha256=INPUT_SHA, challenges_digest=digest(challenges), task_counts=challenge_counts(challenges),
        task_materials=workload['tasks'], producer_sha256={k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
        actual_public_gpu_timing_measured=False, strict_portable_gpu_gate=False,
        correctness_scored=False, model_training_exposure='unresolved-public-development-measurement',
        resource_information_status='unavailable', reserved_quota_hours=None, quota_observed_at=None,
        quota_factor=None, quota_reservation_id=None, prior_sessions_reconciled=None,
        owner_editor_sessions_closed=None, resource_sufficiency_verified=False,
        no_competition_files_read=True, lightweight_evidence_is_native_gate=False)
    validate_plan(plan, challenges); raw['plan'] = canonical(plan)
    notebook = render(plan, raw)
    metadata = {'id': plan['kernel_id'], 'title': run, 'code_file': 'notebook.ipynb', 'language': 'python',
        'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True, 'enable_internet': False,
        'machine_shape': 'NvidiaL4', 'docker_image': plan['docker_image'], 'docker_image_pinning_type': 'original',
        'dataset_sources': [], 'kernel_sources': ['sorokin/pip-install-unsloth-flash-patch'],
        'competition_sources': plan['competition_sources'], 'model_sources': plan['model_sources']}
    return plan, raw, notebook, metadata


def render(plan, raw):
    source = '''import base64,hashlib,json,os,subprocess,sys,time,zlib
from pathlib import Path
START=time.monotonic()
'''
    source += 'PACKED='+repr({k: base64.b64encode(zlib.compress(v, 9)).decode() for k, v in raw.items()})+'\n'
    source += 'HASHES='+repr({k: hashlib.sha256(v).hexdigest() for k, v in raw.items()})+'\n'
    source += 'FILES='+repr(FILES)+'\n'
    source += '''raw={}
for key,value in PACKED.items():
    decoder=zlib.decompressobj()
    body=decoder.decompress(base64.b64decode(value,validate=True),8*1024**2)
    if not decoder.eof or decoder.unused_data or hashlib.sha256(body).hexdigest()!=HASHES[key]:
        raise RuntimeError('bounded exact public notebook payload differs: '+key)
    raw[key]=body
PLAN=json.loads(raw['plan']); RUN=PLAN['run_id']
work=Path('/kaggle/working')/RUN
if work.exists():
    raise RuntimeError('Run directory already exists; retained checkpoints will not be overwritten. Use the download cell for the prior run.')
work.mkdir()
for name,key in FILES.items():
    path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw[key])
(work/'tools/__init__.py').write_bytes(b'')
(work/'payload-bindings.json').write_text(json.dumps(HASHES,sort_keys=True),encoding='utf-8')
sys.path.insert(0,str(work))
from tools.nvarc_public_eval import ResultStore,write_archive
from tools.nvarc_native_multitask import digest,write
ResultStore(work,PLAN,json.loads(raw['challenges']))
print(json.dumps({'run_id':RUN,'profile':PLAN['profile'],'tasks':120,'tests':172,
    'session_limit_seconds':PLAN['maximum_notebook_wall_seconds'],'zip':PLAN['download_archive']}))
'''
    launch = '''# Fresh parent and all children start with PYTHONHASHSEED=0.
paths=[Path(p) for p in sys.path if Path(p).is_absolute() and Path(p).is_relative_to('/kaggle/usr/lib/notebooks')]
matches=[p for p in dict.fromkeys(paths) if (p/'qwen3.patch').is_file()]
destination=work.parent/PLAN['download_archive']
code=None
try:
    if len(paths)>32 or len(matches)!=1:
        raise RuntimeError('one exact original dependency notebook mount required')
    env=dict(os.environ,PYTHONHASHSEED='0',PYTHONPATH=str(work)+os.pathsep+str(matches[0]),
        PYTHONIOENCODING='utf-8',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        HF_DATASETS_OFFLINE='1',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true')
    command=[sys.executable,str(work/'tools/nvarc_public_eval_parent.py'),'--root',str(work),
        '--dependency',str(matches[0]),'--started',str(START),'--owner-pid',str(os.getpid())]
    process=subprocess.Popen(command,env=env,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,encoding='utf-8',errors='replace',start_new_session=True)
    # Stream progress. The parent enforces worker clocks and finalizes its ZIP.
    for line in process.stdout: print(line,end='',flush=True)
    code=process.wait()
except BaseException as error:
    if 'process' in globals() and process.poll() is None:
        import signal
        os.killpg(process.pid,signal.SIGTERM)
        try: process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=15)
    write(work/'terminal.json',{'run_id':RUN,'plan_digest':digest(PLAN),'outcome':'failed',
        'phase':'notebook-parent','error_type':type(error).__name__,'message':str(error)[:2000],
        'correctness_scored':False,'strict_portable_gpu_gate':False})
finally:
    if not destination.is_file():
        if not (work/'terminal.json').is_file():
            write(work/'terminal.json',{'run_id':RUN,'plan_digest':digest(PLAN),'outcome':'failed',
                'phase':'parent-exit','returncode':code,'correctness_scored':False,'strict_portable_gpu_gate':False})
        write_archive(work,destination,PLAN)
    from IPython.display import display,FileLink
    display(FileLink(str(destination)))
    print(json.dumps({'download':str(destination),'run_id':RUN}))
if code!=0: raise RuntimeError('Public evaluation failed; exact terminal/logs and committed outputs are in '+PLAN['download_archive'])
'''
    download = '''# 可單獨執行：只下載這份 notebook 的 ZIP，不啟動模型。
from pathlib import Path
from IPython.display import display,FileLink
RUN='''+repr(plan['run_id'])+'''
destination=Path('/kaggle/working')/(RUN+'.zip')
if not destination.is_file(): raise RuntimeError('ZIP 尚未產生；已保存的逐題檔案在 /kaggle/working/'+RUN)
display(FileLink(str(destination)))
print(str(destination))
'''
    for body in (source, launch, download): compile(body, 'public-notebook', 'exec')
    text = ('# ARC-AGI-2 public eval — '+plan['profile']+'\n\n'
        '固定 120 題／172 tests；SFT139；4 張 L4；Internet off。搜尋與八視角驗證共 30 秒/test。\n\n'
        +('不做 TTT；session 上限 60 分鐘。' if plan['profile']=='BASE-30' else '每題完整 128 步 TTT；session 上限 4 小時。')
        +'時限可能留下部分结果，缺項保留在分母內。公開答案不進入此 notebook，ZIP 下載後再於本地評分。\n\n'
        '點 Run All 開始一次執行；完成或報錯後可用最後一格下載 `'+plan['download_archive']+'`。\n')
    return {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': text.splitlines(keepends=True)}]+
            [{'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [],
              'source': body.splitlines(keepends=True)} for body in (source, launch, download)]}


def stage(package, profile, source_commit):
    package = Path(package); require(not package.exists(), 'new immutable public package required')
    plan, raw, notebook, metadata = construct(profile, source_commit)
    (package/'kernel').mkdir(parents=True)
    write(package/'plan.json', plan); write(package/'kernel/notebook.ipynb', notebook)
    write(package/'kernel/kernel-metadata.json', metadata)
    write(package/'stage-summary.json', {'run_id': plan['run_id'], 'plan_digest': digest(plan),
        'payload_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    package = Path(package)
    require(not package.is_symlink() and not any(p.is_symlink() for p in package.rglob('*')), 'regular package required')
    saved = parse_json((package/'plan.json').read_bytes())
    plan, raw, notebook, metadata = construct(saved['profile'], saved['source_commit'])
    saved_notebook = parse_json((package/'kernel/notebook.ipynb').read_bytes())
    # Original staged bytes may have a different literal dictionary order from
    # an earlier interpreter's hash seed. Preserve them while checking every
    # packed value and all surrounding executable source exactly. No saved
    # payload is executed or used as authoritative source for reconstruction.
    tree = ast.parse(''.join(saved_notebook['cells'][1]['source']))
    assignments = [n for n in tree.body if isinstance(n, ast.Assign) and
        any(isinstance(t, ast.Name) and t.id == 'PACKED' for t in n.targets)]
    require(len(assignments) == 1, 'one literal packed payload required')
    packed = ast.literal_eval(assignments[0].value)
    require(isinstance(packed, dict) and set(packed) == set(raw), 'closed packed payload keys required')
    notebook = render(plan, {k: raw[k] for k in packed})
    summary = parse_json((package/'stage-summary.json').read_bytes())
    require(saved == plan and saved_notebook == notebook and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes()) == metadata and
        summary == {'run_id': plan['run_id'], 'plan_digest': digest(plan),
            'payload_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
            'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*')
                          if p.is_file() and p.name != 'stage-summary.json'}}, 'exact closed public package differs')
    require(len(raw['challenges']) < 8*1024**2 and not any(k in raw for k in ('solutions', 'answers', 'scorer')),
            'pure public input without scorer/solutions required')
    return {'run_id': plan['run_id'], 'profile': plan['profile'], 'plan_digest': digest(plan),
        'notebook_sha256': sha(package/'kernel/notebook.ipynb'), 'offline_package_verified': True,
        'archive': plan['download_archive'], 'quick_save_only': True, 'external_calls': 0,
        'gpu_runtime_verified': False, 'strict_portable_gpu_gate': False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True); parser.add_argument('--profile', choices=RUNS)
    parser.add_argument('--source-commit'); args = parser.parse_args()
    result = stage(args.package, args.profile, args.source_commit) if args.action == 'stage' else preflight(args.package)
    print(json.dumps(result))


if __name__ == '__main__': main()
