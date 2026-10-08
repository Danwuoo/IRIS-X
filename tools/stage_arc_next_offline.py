"""Stage separately versioned private offline runtime and default-inert notebook.

Packaging only. Dataset publication and QUICK_SAVE use a separate reviewed
transport; neither is an implicit side effect of these functions.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
from tools.arc_next_offline_bundle import FORMAT, DATA_FILES, canonical, sha_file, validate_reference, verify_runtime
from tools.stage_arc_next_notebook import REF, SLUG
RUNTIME_FILES = ('tools/arc_next_agent.py','tools/arc_next_models.py','tools/arc_next_training.py',
 'tools/arc_next_materials.py','tools/arc_next_environment.py','tools/arc_next_workflow.py',
 'tools/arc_next_report.py','tools/arc_kaggle_submission.py','tools/arc_next_offline_bundle.py',
 'tools/arc_next_offline_environment.py','tools/arc_next_offline_runtime.py','tools/arc_next_index_repair.py',
 'research/arc-next-line/training-source-inventory.json','research/arc-next-line/model-source-lock.json',
 'research/arc-next-line/licenses/granite-4.2-8b-LICENSE.txt',
 'research/arc-next-line/licenses/ARC-AGI-2-LICENSE.txt')
FLAGS = ('VERIFY_OFFLINE_INPUTS','INSTALL_OFFLINE_ENVIRONMENT','CHECK_CPU_IMPORTS',
         'RUN_CALIBRATION','ENABLE_TRAINING_PILOT','RUN_ARCHITECTURE_PILOT',
         'SCORE_DEVELOPMENT','EXPORT_REPORT')
PRESERVED_COMPETITION_SOURCES = ('arc-prize-2026-arc-agi-3',)


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


def stage_runtime(destination, source_commit, training_root):
    destination = Path(destination)
    if destination.exists(): raise ValueError('Fresh runtime Dataset stage required')
    import re
    if not re.fullmatch('[0-9a-f]{40}', source_commit): raise ValueError('Exact source commit required')
    from tools.arc_next_materials import verify_prepared_training
    inventory = json.loads((ROOT / 'research/arc-next-line/training-source-inventory.json').read_bytes())
    verify_prepared_training(inventory, training_root)
    raw = {}
    for name in RUNTIME_FILES:
        body = subprocess.check_output(['git','show',source_commit+':'+name], cwd=ROOT)
        if body != (ROOT / name).read_bytes(): raise ValueError('Committed runtime bytes differ: ' + name)
        raw['runtime/'+name] = body
    raw['runtime/tools/__init__.py'] = b'"""IRIS-X verified offline runtime package."""\n'
    for name in DATA_FILES: raw['training/'+name] = (Path(training_root)/name).read_bytes()
    raw['licenses/ARC-AGI-2-LICENSE.txt'] = (ROOT/'research/arc-next-line/licenses/ARC-AGI-2-LICENSE.txt').read_bytes()
    raw['NOTICE.txt'] = (
        'IRIS-X private offline runtime. IRIS-X code remains proprietary.\n'
        'Training materials derive from ARC Prize Foundation ARC-AGI-2 at f3283f727488ad98fe575ea6a5ac981e4a188e49, Apache-2.0.\n'
        'MODIFICATIONS: only 36 pinned public-training tasks were retained; original test fields were removed; training demonstrations were task-group split 32/4.\n'
        'Development questions and evaluator answers are derived only from held-out public-training demonstrations. No official evaluation answers are included.\n'
        'Granite and wheel distributions remain separate artifacts with their original licenses.\n').encode()
    for name, body in raw.items():
        path = destination/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    manifest = {'format':FORMAT,'source_commit':source_commit,'contains_model_weights':False,'contains_wheels':False,
                'model_key':'granite-4.2-8b','training_groups':32,'development_groups':4,
                'original_test_answers_retained':False,
                'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(raw.items())}}
    write(destination/'bundle-manifest.json', manifest)
    bound = sha_file(destination/'bundle-manifest.json')
    verify_runtime(destination, bound)
    return {'path':str(destination),'manifest_sha256':bound,'files':len(raw)+1,
            'bytes':sum(p.stat().st_size for p in destination.rglob('*') if p.is_file()),'source_commit':source_commit}


def notebook(pins):
    pins = json.loads(canonical(pins))
    for role in ('runtime','model','wheels'):
        validate_reference(pins[role]['reference'])
        if pins[role]['private'] is not True: raise ValueError('All Datasets must be private')
        if not re.fullmatch('[0-9a-f]{64}', pins[role]['manifest_sha256']): raise ValueError('Actual manifest SHA256 required')
    def code(s): return {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':s.splitlines(keepends=True)}
    def md(s): return {'cell_type':'markdown','metadata':{},'source':s.splitlines(keepends=True)}
    intro='''# IRIS-X：完整離線 G4 ARC 小模型試驗

此版本只讀三個已固定版本的 private Kaggle Datasets：Granite 權重、CUDA 12.8／Python 3.12 wheels、獨立版本的程式與 32+4 個 demonstration-only task。所有開關預設 False。安裝、驗證、訓練與推論都沒有網路下載步驟。

依你的明確指示，保留既有 ARC-AGI-3 比賽資料掛載。此 ARC-AGI-2 程式不讀取或使用該比賽資料；保留掛載沒有啟動 GPU、訓練或付費執行。

Granite 官方索引與 shard header 不一致；此材料保留官方原始索引與來源紀錄，只重建 shard 對應及位元組總數。權重、config、tokenizer 和完整詞彙表都不變。完整模型載入與 GPU 訓練仍未驗證。

訓練目標仍為一張 G4 RTX PRO 6000 Blackwell。Kaggle 此處只保存來源，GPU OFF、Internet OFF，沒有建立 VM、付费執行或正式提交。首次 GPU 訓練與四張 L4 部署仍須手動驗證。

手動順序：先 VERIFY_OFFLINE_INPUTS；再 INSTALL_OFFLINE_ENVIRONMENT；再 CHECK_CPU_IMPORTS；最後才依需求單獨選 smoke2 訓練、A/B/C、獨立評分或匯出。安裝到獨立 venv，無須修改 Kaggle 既有套件或重啟 kernel。目標必須 Linux x86_64、CPython 3.12、glibc ≥2.28。準備機下載與 Dataset 上傳已在此 notebook 之外完成。

在 G4 使用時，先把相同三個 Dataset 完整複製到當地；填入三個明確資料夾路徑。缺檔、hash／版本不同、Python ABI 不合即停止，不會連網補檔。停掉程序不代表停止 VM 計費。
'''
    config='''from pathlib import Path
VERIFY_OFFLINE_INPUTS = False
INSTALL_OFFLINE_ENVIRONMENT = False
CHECK_CPU_IMPORTS = False
RUN_CALIBRATION = False
ENABLE_TRAINING_PILOT = False
RUN_ARCHITECTURE_PILOT = False
SCORE_DEVELOPMENT = False
EXPORT_REPORT = False
RUNTIME_ROOT = None  # 非 Kaggle 主機填入完整資料夾；不要填下載 URL
MODEL_ROOT = None
WHEELS_ROOT = None
TRAINING_PROFILE = 'smoke2'
RUN_TAG = 'granite-offline-smoke2-001'
MAX_WALL_SECONDS = 1800
APPROVED_MAX_COST_USD = None
ESTIMATED_HOURLY_COST_USD = None
ADAPTER_PATH = None
BASE = (Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()) / 'iris-next-offline'
ENVIRONMENT = BASE / 'environment-cp312-cu128'
'''
    bootstrap='PINS = '+repr(pins)+'\nFLAGS = '+repr(FLAGS)+'''\nimport hashlib, json, re, sys
if any(type(globals()[f]) is not bool for f in FLAGS): raise ValueError('所有手動開關必須是 bool')
PHASES = ('VERIFY_OFFLINE_INPUTS','INSTALL_OFFLINE_ENVIRONMENT','CHECK_CPU_IMPORTS','RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT','SCORE_DEVELOPMENT','EXPORT_REPORT')
if sum(globals()[f] for f in PHASES) > 1: raise ValueError('每次只開一個 phase')
ACTIVE = any(globals()[f] for f in PHASES)
if ACTIVE:
    sys.dont_write_bytecode = True
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', RUN_TAG): raise ValueError('使用新的安全 RUN_TAG')
    def _root(role, explicit):
        owner, slug, version = PINS[role]['reference'].split('/')
        choices = [Path(explicit)] if explicit is not None else [Path('/kaggle/input/datasets') / owner / slug, Path('/kaggle/input') / slug]
        found = [p for p in choices if p.is_dir()]
        if len(found) != 1: raise ValueError('缺少或重複 Dataset mount: ' + role)
        return found[0]
    RUNTIME_ROOT = _root('runtime', RUNTIME_ROOT)
    MODEL_ROOT = _root('model', MODEL_ROOT)
    WHEELS_ROOT = _root('wheels', WHEELS_ROOT)
    _manifest = RUNTIME_ROOT / 'bundle-manifest.json'
    if hashlib.sha256(_manifest.read_bytes()).hexdigest() != PINS['runtime']['manifest_sha256']: raise ValueError('程式 Dataset 版本/hash 不符')
    _files = json.loads(_manifest.read_bytes())['files']
    for _name, _entry in _files.items():
        _p = RUNTIME_ROOT / _name
        if Path(_name).is_absolute() or '..' in Path(_name).parts or not _p.resolve().is_relative_to(RUNTIME_ROOT.resolve()) or _p.is_symlink() or any(q.is_symlink() for q in _p.parents): raise ValueError('非法 Dataset 路徑')
        if _p.stat().st_size != _entry['bytes'] or hashlib.sha256(_p.read_bytes()).hexdigest() != _entry['sha256']: raise ValueError('程式 Dataset 內容不同: ' + _name)
    _code = RUNTIME_ROOT / 'runtime'
    if 'tools' in sys.modules and any(Path(p).resolve() != (_code / 'tools').resolve() for p in getattr(sys.modules['tools'], '__path__', [])): raise RuntimeError('已有不同 tools package；請用乾淨 kernel 避免來源混用')
    sys.path.insert(0, str(_code))
    from tools.arc_next_offline_bundle import verify_runtime
    verify_runtime(RUNTIME_ROOT, PINS['runtime']['manifest_sha256'])
else:
    print('所有操作關閉；没有下載、安裝、模型載入、GPU 執行或輸出寫入。')
'''
    phase='''if ACTIVE:
    import subprocess
    from tools.arc_next_offline_runtime import launch_phase
    selected = next(f for f in PHASES if globals()[f])
    config = dict(runtime_root=str(RUNTIME_ROOT), model_root=str(MODEL_ROOT), wheels_root=str(WHEELS_ROOT),
        environment_dir=str(ENVIRONMENT), pins=PINS, run_tag=RUN_TAG, output_root=str(BASE),
        training_profile=TRAINING_PROFILE, enable_training_pilot=ENABLE_TRAINING_PILOT,
        max_wall_seconds=MAX_WALL_SECONDS, approved_max_cost_usd=APPROVED_MAX_COST_USD,
        estimated_hourly_cost_usd=ESTIMATED_HOURLY_COST_USD, adapter_path=ADAPTER_PATH)
    result = launch_phase(selected, config, enabled=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
'''
    return {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
            'language_info':{'name':'python'},'irisx_execution_mode':'QUICK_SAVE','irisx_offline_dataset_pins':pins,
            'irisx_preserved_competition_sources':list(PRESERVED_COMPETITION_SOURCES),
            'irisx_agent_execution_authorized':False},'cells':[md(intro),code(config),code(bootstrap),code(phase)]}


def stage_notebook(destination, pins):
    destination=Path(destination)
    if destination.exists(): raise ValueError('Fresh immutable offline notebook stage required')
    nb=notebook(pins)
    for cell in nb['cells']:
        if cell['cell_type']=='code':ast.parse(''.join(cell['source']))
    with tempfile.TemporaryDirectory() as d:
        script=Path(d)/'inert.py'; script.write_text('\n'.join(''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'))
        subprocess.run(['python',str(script)],cwd=d,check=True,capture_output=True)
        if set(Path(d).iterdir())!={script}:raise ValueError('Default offline notebook wrote files')
    write(destination/'notebook.ipynb',nb)
    write(destination/'kernel-metadata.json',{'id':REF,'title':SLUG,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
          'is_private':True,'enable_gpu':False,'enable_internet':False,'dataset_sources':[pins[k]['reference'] for k in ('runtime','model','wheels')],
          'competition_sources':list(PRESERVED_COMPETITION_SOURCES),'kernel_sources':[],'model_sources':[]})
    return {'notebook_sha256':sha_file(destination/'notebook.ipynb'),'all_defaults_inert':True,
            'execution_type':'QUICK_SAVE','gpu_executed':False,'pins':pins,'path':str(destination)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['runtime','notebook']);parser.add_argument('--destination',required=True)
    parser.add_argument('--source-commit');parser.add_argument('--training-root');parser.add_argument('--pins')
    args=parser.parse_args()
    result=stage_runtime(args.destination,args.source_commit,args.training_root) if args.action=='runtime' else stage_notebook(args.destination,json.loads(Path(args.pins).read_bytes()))
    print(json.dumps(result,indent=2))
