"""Build/verify one new private, source-only G4 training notebook package."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
SLUG='iris-arc2-g4-agent-pilot-20261008-6deaf904'
REF='danielwuu/'+SLUG
RUN_ID='arc-next-g4-manual-20261008-001'
SOURCE_FILES=('tools/arc_next_agent.py','tools/arc_next_models.py','tools/arc_next_training.py',
 'tools/arc_next_materials.py','tools/arc_next_environment.py','tools/arc_next_workflow.py',
 'tools/arc_kaggle_submission.py','research/arc-next-line/training-source-inventory.json',
 'research/arc-next-line/model-source-lock.json',
 'research/arc-next-line/licenses/granite-4.2-8b-LICENSE.txt',
 'research/arc-next-line/licenses/seed-coder-8b-reasoning-LICENSE.txt')
FLAGS=('PREPARE_ENVIRONMENT','PREPARE_PUBLIC_MATERIALS','RUN_CALIBRATION',
 'ENABLE_TRAINING_PILOT','RUN_ARCHITECTURE_PILOT','SCORE_DEVELOPMENT','EXPORT_REPORT','ALLOW_QWEN_HYBRID')


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value)+b'\n')

def notebook(plan,raw):
    def code(s):return {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':s.splitlines(keepends=True)}
    def md(s):return {'cell_type':'markdown','metadata':{},'source':s.splitlines(keepends=True)}
    config='''from pathlib import Path
# 所有動作預設關閉。每次只選一個 phase；請在你自己已選定的訓練環境手動執行。
PREPARE_ENVIRONMENT = False       # 下載固定版本與完整相依 wheel，離線 hash 安裝；完成後重啟 kernel
PREPARE_PUBLIC_MATERIALS = False  # 只下載指定模型及固定 public-training demos；需要網路
RUN_CALIBRATION = False          # 單一模型、真實 LoRA；smoke2 先驗證，再另選 pilot16 / pilot128
ENABLE_TRAINING_PILOT = False    # pilot16 / pilot128 的第二道手動開關
RUN_ARCHITECTURE_PILOT = False   # 同權重 A/B/C；不會自動接在訓練之後
SCORE_DEVELOPMENT = False       # 求解程序停止後，獨立讀取 public-training dev answers；只產生彙總
EXPORT_REPORT = False           # 只包裝已完成或失敗的本機證據；不自動上傳
ALLOW_QWEN_HYBRID = False        # 第二候選的明確架構選擇，不會自動換模型
MODEL_KEY = 'granite-4.2-8b'      # 第二 qwen3.5-9b；第三 seed-coder-8b-reasoning
TRAINING_PROFILE = 'smoke2'      # smoke2 / pilot16 / pilot128
RUN_TAG = 'granite-smoke2-001'   # 每次新實驗使用新的名稱，禁止覆寫或隱式續跑
MAX_WALL_SECONDS = 1800
APPROVED_MAX_COST_USD = None     # 填入你接受的本次程序預算；不代表雲端帳單上限
ESTIMATED_HOURLY_COST_USD = None # 填入你的地區、VM、磁碟等目前全包時薪估計
ADAPTER_PATH = None             # None=原始 base；訓練後另填已驗證的 adapter 目錄作配對比較
BASE = (Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()) / 'iris-next-manual'
MATERIALS = BASE / 'materials'
ENVIRONMENT = BASE / 'environment'
MODEL_PATH = MATERIALS / MODEL_KEY
DATA_PATH = MATERIALS / 'arc-training'
OUTPUT_PATH = BASE / RUN_TAG
'''
    intro='''# IRIS-X：G4 小模型訓練與 ARC-AGI-2 架構試驗

這是新的 private QUICK_SAVE，沒有執行。訓練目標為 Google Cloud g4-standard-48：一張 RTX PRO 6000 Blackwell（96 GB 等級）、48 vCPU、180 GiB RAM。正式提交仍是離線 L4 ×4；此 notebook 不會提交、建立 VM、開啟付費硬體或處理憑證。

先跑 smoke2 確认原生 tokenizer／BF16／LoRA／梯度／安全匯出與重載；再手動選 pilot16 或 pilot128 作真實 demonstration-only SFT。A/B/C 分別是 direct-grid、程式提案加示例驗證、再加失敗回饋修復。訓練與架構測量分開開啟，沒有自动全模型 sweep 或 RL。

前次 uncapped 完成 512 updates／六個 tests，41 個不同候選，但 top-1／top-2／pool oracle 仍各 1/6。因此本線測試提案品質；沒有宣稱新架構已提升準確率。AVO、Duck、Prime 的 ARC-AGI-3 成績不能代替本案的 ARC-AGI-2 證據。

## 手動順序
1. 選定你要使用的付費 G4 環境。Kaggle QUICK_SAVE 僅保存來源，不保證 G4 權限。可匯出此 notebook；不要借用 ARC-AGI-3 限定硬體。
2. 在新的 Linux x86_64 Python 3.11/3.12 環境，單獨開啟 PREPARE_ENVIRONMENT，執行後重啟 kernel 並關閉開關。
3. 單獨開啟 PREPARE_PUBLIC_MATERIALS。會下載一個指定的官方模型（約 18–33 GB）及固定的 36 個 public-training task demonstrations；預留模型、wheels、cache、adapter 與輸出磁碟空間。完成後關閉開關。也可在非 GPU 準備機先完成，再複製完整 materials/environment 資料夾。
4. 填好費用欄位，單獨開啟 RUN_CALIBRATION，以 smoke2 開始。之後要跑 pilot16/128，改新 RUN_TAG 並另開 ENABLE_TRAINING_PILOT。
5. 要測試架構，另改新 RUN_TAG、關閉 RUN_CALIBRATION、開啟 RUN_ARCHITECTURE_PILOT。先 ADAPTER_PATH=None 跑 base，再另外指定訓練 adapter 跑同一組 A/B/C。
6. 匯出並下載證據。程序 timeout 不會停止 VM 帳單：最後由你停止 VM／Editor session。

開啟材料準備需要 Internet；訓練、推論與正式 L4 提交只讀本機固定材料並強制 offline。這份 notebook 保持預設 Internet OFF，避免誤把準備需求帶入提交。
'''
    flags=repr(FLAGS)
    packed={n:base64.b64encode(zlib.compress(b,9)).decode() for n,b in sorted(raw.items())}
    hashes={n:sha(b) for n,b in sorted(raw.items())}
    bootstrap='''import json, hashlib, sys, base64, zlib, re
for _flag in FLAGS:
    if type(globals()[_flag]) is not bool: raise ValueError('所有手動開關必須是 bool，不能是字串')
_phase_flags = [PREPARE_ENVIRONMENT, PREPARE_PUBLIC_MATERIALS, RUN_CALIBRATION, RUN_ARCHITECTURE_PILOT, SCORE_DEVELOPMENT]
if sum(_phase_flags) > 1: raise ValueError('每次只開啟一個準備／訓練／架構 phase')
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', RUN_TAG): raise ValueError('RUN_TAG 必須是安全且新的名稱')
ACTIVE = any(_phase_flags) or EXPORT_REPORT
if ACTIVE:
    CODE = BASE / ('code-' + SOURCE_DIGEST[:16])
    for name, encoded in PACKED.items():
        body = zlib.decompress(base64.b64decode(encoded, validate=True))
        if hashlib.sha256(body).hexdigest() != HASHES[name]: raise ValueError('內嵌來源 hash 不符')
        target = CODE / name
        if target.is_symlink() or any(p.is_symlink() for p in target.parents): raise ValueError('來源路徑不可是 symlink')
        if not target.resolve().is_relative_to(CODE.resolve()): raise ValueError('非法來源路徑')
        if target.exists():
            if target.read_bytes() != body: raise ValueError('已存在來源不同，請勿覆寫')
        else:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(body)
    if 'tools' in sys.modules and any(Path(p).resolve() != (CODE / 'tools').resolve() for p in getattr(sys.modules['tools'], '__path__', [])):
        raise RuntimeError('已載入其他 tools package；請重啟 kernel，不可混用來源')
    sys.path.insert(0, str(CODE))
else:
    print('僅保存來源。所有操作關閉：沒有下載、安裝、模型載入、GPU 執行或輸出寫入。')
'''
    bootstrap='FLAGS='+flags+'\nPACKED='+repr(packed)+'\nHASHES='+repr(hashes)+'\nSOURCE_DIGEST='+repr(plan['source_digest'])+'\n'+bootstrap
    environment='''if PREPARE_ENVIRONMENT:
    from tools.arc_next_environment import prepare_environment
    print(prepare_environment(CODE / 'research/arc-next-line/model-source-lock.json', ENVIRONMENT, enabled=True, install=True))
    print('先重啟 kernel，再將 PREPARE_ENVIRONMENT 改回 False。既有不相容的可選套件會讓 pip check 明確失敗。')
'''
    materials='''if PREPARE_PUBLIC_MATERIALS:
    from tools.arc_next_materials import materialize_model, materialize_training
    inventory = json.loads((CODE / 'research/arc-next-line/training-source-inventory.json').read_bytes())
    print(materialize_training(inventory, DATA_PATH, enabled=True, training_count=32, development_count=4))
    print(materialize_model(MODEL_KEY, MODEL_PATH, enabled=True))
'''
    training='''if RUN_CALIBRATION:
    from tools.arc_next_training import CalibrationConfig, RunBudget, PROFILES, preflight, run_calibration
    if TRAINING_PROFILE not in PROFILES: raise ValueError('未知訓練 profile')
    steps = PROFILES[TRAINING_PROFILE]
    budget = RunBudget(max_optimizer_steps=steps, max_input_tokens=steps * 4096,
        max_supervised_tokens=steps * 4096, max_sequence_tokens=4096,
        max_eval_input_tokens=32768, max_eval_rows=4, max_wall_seconds=MAX_WALL_SECONDS)
    config = CalibrationConfig(model_path=str(MODEL_PATH), model_key=MODEL_KEY,
        training_tasks_path=str(DATA_PATH / 'train-demonstrations.json'),
        training_manifest_path=str(DATA_PATH / 'training-manifest.json'),
        environment_lock_path=str(ENVIRONMENT / 'environment-lock.json'),
        model_manifest_path=str(MODEL_PATH / 'irisx-model-material.json'),
        output_dir=str(OUTPUT_PATH), enabled=True, profile=TRAINING_PROFILE,
        enable_pilot=ENABLE_TRAINING_PILOT, allow_experimental_qwen=ALLOW_QWEN_HYBRID,
        budget=budget, approved_max_cost_usd=APPROVED_MAX_COST_USD,
        estimated_hourly_cost_usd=ESTIMATED_HOURLY_COST_USD, seed=1008)
    print(json.dumps(preflight(config), ensure_ascii=False, indent=2))
    print(json.dumps(run_calibration(config), ensure_ascii=False, indent=2))
    print('程序已返回不等於 VM 停止計費。請檢查 result/watchdog receipt，下載後停止 VM。')
'''
    architecture='''if RUN_ARCHITECTURE_PILOT:
    from tools.arc_next_workflow import ArchitectureConfig, run_architecture
    config = ArchitectureConfig(model_path=str(MODEL_PATH), model_key=MODEL_KEY,
        material_manifest_path=str(MODEL_PATH / 'irisx-model-material.json'),
        environment_lock_path=str(ENVIRONMENT / 'environment-lock.json'),
        challenges_path=str(DATA_PATH / 'development-challenges.json'),
        output_dir=str(OUTPUT_PATH), adapter_path=ADAPTER_PATH, enabled=True,
        allow_experimental_qwen=ALLOW_QWEN_HYBRID, maximum_wall_seconds=MAX_WALL_SECONDS,
        approved_max_cost_usd=APPROVED_MAX_COST_USD,
        estimated_hourly_cost_usd=ESTIMATED_HOURLY_COST_USD)
    print(json.dumps(run_architecture(config), ensure_ascii=False, indent=2))
    print('A/B/C 只使用 challenge。尚未開啟 development answers，也未取得官方分數。')
'''
    scoring='''if SCORE_DEVELOPMENT:
    from tools.arc_next_report import score_development
    target = OUTPUT_PATH.parent / (OUTPUT_PATH.name + '-development-aggregate.json')
    if target.exists(): raise ValueError('已存在評估彙總，禁止覆寫')
    aggregate = score_development(OUTPUT_PATH, DATA_PATH)
    target.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + '\\n')
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
'''
    export='''if EXPORT_REPORT:
    from tools.arc_next_report import export_report
    from IPython.display import display, FileLink
    exported = export_report(OUTPUT_PATH)
    display(FileLink(str(exported['archive'])))
    print(json.dumps(exported, ensure_ascii=False, indent=2))
    print('下載後請停止 VM／session。adapter 權重留在獨立資料夾，需與 manifest 一起保存，不會自動上傳。')
'''
    closing='''## 訓練 artifact → 離線 L4 ×4

保留 base 的官方 revision／shard hashes、完整 tokenizer/template、LoRA safetensors／adapter config、環境 wheel lock、程式與資料 split manifest。先在一張 L4 上實測最長 prompt 的 BF16 峰值與 adapter 重載一致性，再以四個獨立 replica 分派 task。4 ×24 GB 不會自動變成單一卡的 96 GB。

不要把 Blackwell 編譯快取／NVFP4-only kernel 帶到 Ada L4。首次資格確認不使用量化；之後若改 INT4，另外量測精度與 kernel 支援。正式 offline notebook 還要通過四個 distinct L4 UUID、完整 test denominator、12 小時內輸出保留、失敗復原與 submission.json schema。此處不會自動上傳模型、建立 Kaggle Dataset 或 Submit to Competition。

四個 held-out public-training task 僅是工程 screen，不是120個 public-evaluation benchmark，更不是官方隱藏分數。模型選擇須看實際驗證結果；第一順位 Granite 不是先驗勝出結論。完整 NeMo、RL、learned verifier 與 fresh-fold LODO 尚未執行。
'''
    cells=[md(intro),code(config),code(bootstrap),md('## 1. 環境（手動、需要網路，無 GPU 訓練）'),code(environment),
           md('## 2. 固定 public materials（與運算分離）'),code(materials),
           md('## 3. 真實 bounded LoRA 訓練／dev NLL／匯出重載'),code(training),
           md('## 4. 固定權重 A/B/C 架構比較'),code(architecture),
           md('## 5. 獨立 development 評分與 matched-cost prefixes'),code(scoring),
           md('## 6. 結果下載'),code(export),md(closing)]
    return {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
       'language_info':{'name':'python'},'irisx_source_commit':plan['source_commit'],
       'irisx_execution_mode':'QUICK_SAVE','irisx_training_machine':'g4-standard-48',
       'irisx_submission_machine':'four NVIDIA L4','irisx_agent_execution_authorized':False},'cells':cells}


def stage(destination,source_commit):
    destination=Path(destination)
    if destination.exists():raise ValueError('Fresh immutable package directory required')
    if not re.fullmatch('[0-9a-f]{40}',source_commit):raise ValueError('Full committed source identity required')
    raw={}
    for name in SOURCE_FILES+('tools/arc_next_report.py',):
        body=subprocess.check_output(['git','show',source_commit+':'+name],cwd=ROOT)
        if body!=(ROOT/name).read_bytes():raise ValueError('Committed code differs: '+name)
        raw[name]=body
    raw['tools/__init__.py']=b'"""IRIS-X manual notebook runtime package."""\n'
    plan={'format':'irisx/arc-next-manual-notebook-v1','run_id':RUN_ID,'ref':REF,'source_commit':source_commit,
      'source_digest':sha(canonical({n:sha(b) for n,b in sorted(raw.items())})),
      'agent_execution_authorized':False,'execution_type':'QUICK_SAVE','private':True,
      'training_target':'g4-standard-48-one-RTX-PRO-6000','submission_target':'four-L4-offline',
      'source_only_save_hardware':'CPU','runtime_host_selection':'owner-manual; not provisioned or allocated by save',
      'official_submission_authorized':False,'all_flags_default_false':list(FLAGS),'payload_sha256':{n:sha(b) for n,b in sorted(raw.items())}}
    meta={'id':REF,'title':SLUG,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
      'is_private':True,'enable_gpu':False,'enable_internet':False,'dataset_sources':[],
      'competition_sources':[],'kernel_sources':[],'model_sources':[]}
    files={'runtime/'+n:b for n,b in raw.items()}
    files.update({'plan.json':canonical(plan),'kernel/notebook.ipynb':canonical(notebook(plan,raw)),
                  'kernel/kernel-metadata.json':canonical(meta)})
    for name,body in files.items():p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    write(destination/'package-manifest.json',{'format':'irisx/arc-next-notebook-package-v1','files':{n:sha(b) for n,b in sorted(files.items())}})
    return preflight(destination)


def preflight(destination):
    destination=Path(destination);manifest=json.loads((destination/'package-manifest.json').read_bytes())
    if any(p.is_symlink() for p in destination.rglob('*')):raise ValueError('No package symlinks')
    actual={p.relative_to(destination).as_posix():sha(p.read_bytes()) for p in destination.rglob('*') if p.is_file() and p.name!='package-manifest.json'}
    if actual!=manifest['files']:raise ValueError('Closed notebook package differs')
    plan=json.loads((destination/'plan.json').read_bytes())
    if plan.get('ref')!=REF or plan.get('run_id')!=RUN_ID or plan.get('execution_type')!='QUICK_SAVE' or plan.get('private') is not True or plan.get('agent_execution_authorized') is not False:
        raise ValueError('Exact private source-only plan required')
    meta=json.loads((destination/'kernel/kernel-metadata.json').read_bytes())
    expected_meta={'id':REF,'title':SLUG,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':False,'enable_internet':False,'dataset_sources':[],'competition_sources':[],'kernel_sources':[],'model_sources':[]}
    if canonical(meta)!=canonical(expected_meta):raise ValueError('Exact private CPU offline mount-free save metadata required')
    raw={n:(destination/'runtime'/n).read_bytes() for n in plan['payload_sha256']}
    if plan['source_digest']!=sha(canonical({n:sha(b) for n,b in sorted(raw.items())})):raise ValueError('Source digest does not bind payload')
    if set(raw)!=set(SOURCE_FILES)|{'tools/arc_next_report.py','tools/__init__.py'}:raise ValueError('Exact runtime allowlist required')
    if raw['tools/__init__.py']!=b'"""IRIS-X manual notebook runtime package."""\n':raise ValueError('Exact synthetic package marker required')
    for name in SOURCE_FILES+('tools/arc_next_report.py',):
        committed=subprocess.check_output(['git','show',plan['source_commit']+':'+name],cwd=ROOT)
        if committed!=raw[name] or (ROOT/name).read_bytes()!=raw[name]:raise ValueError('Payload differs from audited committed source: '+name)
    if {n:sha(b) for n,b in raw.items()}!=plan['payload_sha256']:raise ValueError('Runtime source hashes differ')
    nb=json.loads((destination/'kernel/notebook.ipynb').read_bytes())
    if nb!=notebook(plan,raw):raise ValueError('Exact notebook rendering differs')
    for cell in nb['cells']:
        if cell['cell_type']=='code':
            ast.parse(''.join(cell['source']))
            if cell['outputs'] or cell['execution_count'] is not None:raise ValueError('Notebook must remain unexecuted')
    with tempfile.TemporaryDirectory() as d:
        script=Path(d)/'inert.py';script.write_text('\n'.join(''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'))
        result=subprocess.run(['python',str(script)],cwd=d,capture_output=True,text=True)
        if result.returncode!=0 or set(Path(d).iterdir())!={script}:raise ValueError('Default notebook is not inert: '+result.stderr)
    return {'format':'irisx/arc-next-notebook-preflight-v1','ref':REF,'source_commit':plan['source_commit'],
      'notebook_sha256':sha((destination/'kernel/notebook.ipynb').read_bytes()),'source_digest':plan['source_digest'],
      'package_manifest_sha256':sha((destination/'package-manifest.json').read_bytes()),
      'default_all_cells_inert':True,'gpu_executed':False,'provider_calls':0,'mode':'QUICK_SAVE'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','preflight']);p.add_argument('--package',required=True);p.add_argument('--source-commit')
    a=p.parse_args();print(json.dumps(stage(a.package,a.source_commit) if a.action=='stage' else preflight(a.package),indent=2))
