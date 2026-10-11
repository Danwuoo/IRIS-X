"""Build one inert offline notebook for the complete twelve-hour research cycle."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(pins):
    if set(pins) != {'code', 'data', 'training'}:
        raise ValueError('three exact code/public/training pins required')
    for role in pins:
        if len(pins[role]['manifest_sha256']) != 64:
            raise ValueError('unfrozen manifest')
    markdown = '''# IRIS-X：訓練＋完整 agent，單次12小時研究流程

一個共享Granite8B底模：乾淨global LoRA SFT → training-only留出demo驗證的程式／修復軌跡SFT → 每題獨立demo-only TTT → 可逆grid views＋程式執行／回饋修復＋共同8-view likelihood排序。三個輸出視角共用物理運算：global_grid、task_ttt、full_agent。

主要研究目標沿用專案PUBLIC120 micro pass@2 ≥50%，即84/167；task-macro和整題成功率另報。不能保證一次達50。公開資料已有開發曝光，這不是官方競賽4×L4推論或未接觸holdout。沒有將public答案用於訓練或solver選擇。

## 執行前
此版本為本地準備的發布候選，尚未發佈新Dataset或執行8B GPU訓練。code/training的預定version1 reference必須先經獨立發布／readback核對，不能把預定名稱當作已存在資產。

保留三個釘選code/public-data/training Dataset及既有5個離線model/runtime/wheels/interpreter/adapter來源。G4 RTX PRO6000研究路徑、Internet關閉。舊run003 adapter只由既有bootstrap驗證，這輪從原始base建立新的global LoRA。

1. 所有開關預設False；Run All預設不讀input、不安裝、不訓練。
2. 核准新GPU執行後，MANUAL_START=True、ENABLE_MODEL=True、PROFILE固定LEARNING_AGENT12H，OUTPUT_ROOT全新名稱。
3. 一次Run All。從第一個active cell持久化43,200秒deadline，setup/loading/training/TTT/inference/scoring/export都計時。若預先提交者有dispatch epoch可填PREDISPATCH_EPOCH，使provider排程時間亦計入。無此值時不聲稱涵蓋看不到的provider啟動時間。
4. controls與資料合約先過，才安裝／載入模型。各stage有父程序watchdog，保留closure/export時間。已完成的checkpoint保留最新2份；不重用已封存prediction目錄。

## 輸出
summary.json、worker/training-admission.json、實際optimizer/token/模型成本、每題typed evidence、三組sealed predictions、獨立public scorer報告、archives/evidence-*.zip、post-seal-closure.json。
worker/trained-global-adapter與worker/checkpoints另存，不在evidence ZIP重複大型權重。缺失／超context／budget耗盡保留完整120題167tests分母。scoring必須等model及owned descendants全部停止。

CPU tiny真實神經訓練／adapter reset、native tokenizer、VM以及synthetic end-to-end測試只能證明工程合約。實際8B G4訓練throughput、VRAM峰值和正確率仍待這個未執行的GPU流程建立。
'''
    config = """MANUAL_START = False
ENABLE_MODEL = False
PROFILE = 'LEARNING_AGENT12H'
SESSION_SECONDS = 43200
PREDISPATCH_EPOCH = None
OUTPUT_ROOT = 'irisx-learning-agent-20261011-run001'
SOURCE_PARENT = '.irisx-learning-agent-source'
INPUT_ROOT = '/kaggle/input'
CODE_ROOT = None
DATA_ROOT = None
TRAINING_ROOT = None
MODEL_CONFIG = None
SEED = 0
"""
    loader = (ROOT / 'source_loader.py').read_text()
    setup = loader + '\n\nLEARNING_PINS = ' + repr(pins) + '\n' + """
_LEARNING_READY = None
if type(MANUAL_START) is not bool or type(ENABLE_MODEL) is not bool:
    raise ValueError('Exact Boolean switches required')
if PROFILE != 'LEARNING_AGENT12H' or type(SESSION_SECONDS) is not int or SESSION_SECONDS != 43200:
    raise ValueError('Frozen learning profile and <=12h session required')
if MANUAL_START:
    import time as _learning_time
    _LEARNING_STARTED = _learning_time.time() if PREDISPATCH_EPOCH is None else PREDISPATCH_EPOCH
    _LEARNING_READY = load_reviewed_learning_source(pins=LEARNING_PINS,input_root=INPUT_ROOT,
        code_root=CODE_ROOT,data_root=DATA_ROOT,training_root=TRAINING_ROOT,
        source_parent=SOURCE_PARENT,output_root=OUTPUT_ROOT,
        model_config={} if MODEL_CONFIG is None else MODEL_CONFIG,resume=False)
"""
    run = """if MANUAL_START:
    import json as _learning_json
    from tools.arc_learning_agent_20261011.session import run_session as _learning_run
    _learning_result = _learning_run(_LEARNING_READY['output_root'],
        solver_root=_LEARNING_READY['solver_root'],evaluator_root=_LEARNING_READY['evaluator_root'],
        solver_manifest_sha256=_LEARNING_READY['solver_manifest_sha256'],
        evaluator_manifest_sha256=_LEARNING_READY['evaluator_manifest_sha256'],
        training_root=_LEARNING_READY['training_root'],enable_model=ENABLE_MODEL,
        bootstrap_config=MODEL_CONFIG,started_epoch=_LEARNING_STARTED,
        config={'session_seconds':SESSION_SECONDS,'seed':SEED,'predispatch_clock':PREDISPATCH_EPOCH is not None})
    _learning_text = _learning_json.dumps(_learning_result,sort_keys=True,ensure_ascii=False)
    if len(_learning_text.encode())>16384:
        _learning_text = _learning_json.dumps({'status':_learning_result['status'],'run_id':_learning_result['run_id'],
            'output_root':OUTPUT_ROOT,'summary':'summary.json','closure':'post-seal-closure.json'})
    print(_learning_text)
else:
    print('Learning-agent disabled. Review the run guide before enabling a new session.')
"""
    cells = []
    for kind, value in [('markdown', markdown), ('code', config), ('code', setup), ('code', run)]:
        cell = {'cell_type': kind, 'metadata': {}, 'source': value.splitlines(keepends=True)}
        if kind == 'code': cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {'cells': cells, 'metadata': {'kernelspec': {'name': 'python3', 'display_name': 'Python3', 'language': 'python'},
                                       'language_info': {'name': 'python', 'version': '3.12'}},
            'nbformat': 4, 'nbformat_minor': 5}


def write_notebook(pins, output):
    raw = (json.dumps(build(pins), ensure_ascii=False, indent=2) + '\n').encode()
    Path(output).write_bytes(raw)
    return {'path': str(output), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
