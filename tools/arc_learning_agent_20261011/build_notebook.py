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


def build_stable(pins):
    """Unpublished default-inert successor with the actual pre-loader supervisor."""
    notebook = build(pins)
    notebook['cells'][0]['source'] = '''# IRIS X 效果門檻與穩定訓練研究候選

此候選尚未發布或執行新的 GPU session。code 來源使用本交付包的 local candidate 身分，並非已存在的 Kaggle Dataset；其餘既有資料、模型與離線環境 pins 保留。發布與正式執行需另外核准、完成實際掛載核對。

流程包括穩定語義 sample ID、completion token 加權累積、暖身與衰減、固定 train dev 面板、base early best final 同預算自回歸比較、完整 optimizer scheduler RNG 回復，以及獨立 frozen base 程式分支。TTT 必須改善留出 demo 的實際生成行為，不能只靠 NLL 下降啟用。

只有兩個預先宣告簡單控制都正確，且至少一題留出 dev 正確、所有比較與 native receipt 完整，才允許 public 推論。這個最低門檻不保證 public 50 分。未達門檻時保留 EFFECTIVENESS_BLOCKED、實際運算紀錄與封存，不讀 public 評分答案。

一次最多 43200 秒，包含載入、安裝、訓練、TTT、推論、評分與清理。獨立 pre-loader supervisor 與原有各層資源保護保留。正式執行必須提供單次 pre-dispatch epoch，不能藉重新填時間延長同一 session。此候選預設 MANUAL_START=False、ENABLE_MODEL=False。

完整 8B 模型、替代大模型、4×L4 與 FP8 效果均未在此候選執行。精度 probe 另行明確啟用，不能把微型 Linear probe 當成整個模型 FP8 訓練驗證。
'''.splitlines(keepends=True)
    config = ''.join(notebook['cells'][1]['source'])
    config = config.replace("PROFILE = 'LEARNING_AGENT12H'", "PROFILE = 'LEARNING_AGENT_STABLE12H'")
    config = config.replace("'irisx-learning-agent-20261011-run001'", "'irisx-stable-learning-candidate001'")
    config = config.replace("'.irisx-learning-agent-source'", "'.irisx-stable-learning-source'")
    notebook['cells'][1]['source'] = config.splitlines(keepends=True)
    loader = (ROOT / 'source_loader.py').read_text()
    guard = (ROOT / 'process_guard.py').read_text()
    setup = (ROOT / 'deployment/preloader.py').read_text()
    setup += '\nLEARNING_PINS = ' + repr(pins) + '\nLOADER_SOURCE = ' + repr(loader)
    setup += '\nGUARD_SOURCE = ' + repr(guard)
    setup += '\nLOADER_SHA256 = ' + repr(hashlib.sha256(loader.encode()).hexdigest())
    setup += '\nGUARD_SHA256 = ' + repr(hashlib.sha256(guard.encode()).hexdigest()) + '\n'
    notebook['cells'][2]['source'] = setup.splitlines(keepends=True)
    notebook['cells'][3]['source'] = '''if MANUAL_START:
    import json as _launch_json
    _learning_result = launch_reviewed_notebook(pins=LEARNING_PINS,
        config={'manual_start':MANUAL_START,'enable_model':ENABLE_MODEL,'profile':PROFILE,
                'session_seconds':SESSION_SECONDS,'predispatch_epoch':PREDISPATCH_EPOCH,
                'output_root':OUTPUT_ROOT,'source_parent':SOURCE_PARENT,'input_root':INPUT_ROOT,
                'code_root':CODE_ROOT,'data_root':DATA_ROOT,'training_root':TRAINING_ROOT,
                'model_config':MODEL_CONFIG,'seed':SEED},
        loader_source=LOADER_SOURCE,guard_source=GUARD_SOURCE,
        expected_loader_sha256=LOADER_SHA256,expected_guard_sha256=GUARD_SHA256)
    print(_launch_json.dumps({'status':_learning_result['status'],'run_id':_learning_result['run_id'],
        'score_status':_learning_result.get('score_status'),
        'notebook_owner_closure':_learning_result.get('notebook_owner_closure')},sort_keys=True))
else:
    print('Stable learning candidate disabled. No inputs, model or evaluator opened.')
'''.splitlines(keepends=True)
    return notebook
