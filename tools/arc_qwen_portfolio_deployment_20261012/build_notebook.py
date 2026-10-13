"""Deterministic output-free four-cell notebook; inactive is always the default."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PACKAGE=Path(__file__).resolve().parent


def build(pins, *, active=False):
    config=f'''# Only this cell differs between inactive and active publication.
MANUAL_START = {active!r}
ENABLE_MODEL = {active!r}
PROFILE = "QWEN14B_PORTFOLIO12H"
SESSION_SECONDS = 43200
PROBE_SECONDS = 43200
PREDISPATCH_EPOCH = None
OUTPUT_ROOT = "/kaggle/working/irisx-qwen14b-portfolio-20261012-run001"
SOURCE_PARENT = "/kaggle/working/irisx-qwen14b-portfolio-20261012-source001"
INPUT_ROOT = "/kaggle/input"
CODE_ROOT = None
DATA_ROOT = None
TRAINING_ROOT = None
'''
    loader=(PACKAGE/'source_loader.py').read_text();guard=(PACKAGE.parent/'arc_learning_agent_20261011/process_guard.py').read_text()
    preloader=(PACKAGE/'preloader.py').read_text()
    embedded='import json\nPINS = json.loads('+repr(json.dumps(pins,sort_keys=True,separators=(',',':')))+')\n'
    embedded+='LOADER_SOURCE = '+repr(loader)+'\nGUARD_SOURCE = '+repr(guard)+'\n'
    embedded+='EXPECTED_LOADER_SHA256 = '+repr(hashlib.sha256(loader.encode()).hexdigest())+'\n'
    embedded+='EXPECTED_GUARD_SHA256 = '+repr(hashlib.sha256(guard.encode()).hexdigest())+'\n'
    embedded+='PRELOADER_SOURCE = '+repr(preloader)+'\n'
    embedded+="exec(compile(PRELOADER_SOURCE, '<reviewed-qwen-preloader>', 'exec'))\n"
    run='''RESULT = launch_reviewed_qwen_notebook(pins=PINS, config={
    'manual_start':MANUAL_START,'enable_model':ENABLE_MODEL,'profile':PROFILE,
    'session_seconds':SESSION_SECONDS,'probe_seconds':PROBE_SECONDS,'predispatch_epoch':PREDISPATCH_EPOCH,
    'output_root':OUTPUT_ROOT,'source_parent':SOURCE_PARENT,'input_root':INPUT_ROOT,
    'code_root':CODE_ROOT,'data_root':DATA_ROOT,'training_root':TRAINING_ROOT},
    loader_source=LOADER_SOURCE,guard_source=GUARD_SOURCE,
    expected_loader_sha256=EXPECTED_LOADER_SHA256,expected_guard_sha256=EXPECTED_GUARD_SHA256)
print(json.dumps({'status':RESULT['status'],'operational_success':RESULT.get('operational_success',False),'science_complete':RESULT.get('science_complete',False),'public_score':None,'public_solving_admitted':False},sort_keys=True))
'''
    def cell(kind,source):
        c={'cell_type':kind,'metadata':{},'source':source.splitlines(keepends=True)}
        if kind=='code':c.update(execution_count=None,outputs=[])
        return c
    title='''# Qwen3-14B 預註冊 checkpoint portfolio 手跑實驗

預設不執行。掛載本次精確 code Dataset、官方 Qwen3-14B model/1 與既有離線環境材料後，將下一格 MANUAL_START 與 ENABLE_MODEL 都設為 True，再執行全部。
PREDISPATCH_EPOCH 保持 None：首次啟動當下記錄一次時鐘，含安裝、雜湊、模型載入、訓練、評估、封存，最多12小時。不要複用先前 v17/v18 epoch。每次新實驗請使用新的 OUTPUT_ROOT/SOURCE_PARENT；舊目錄存在即拒絕覆寫，重跑不會重設原目錄時鐘。

固定63題：13舊回歸、12新網格同族、6新轉換族、8不進訓練的 canary、24固定官方 ARC training-source 留出題。PUBLIC120 不在本次評分範圍。BF16 base、FP32 rank8/alpha16 LoRA、context2048；FP8/4L4 尚未實測。
兩個獨立訓練分支各16更新，保存 base/8/16。Grid/program 輸出上限皆256，與先前64/128不同。每個 checkpoint 分片落盤後清潔重載再生成。多題 canary 以分支自身指標排名；program portfolio 固定 base→8→16，只用 demonstrations 驗證，最多兩個不同預測。所有選答先封存，再開啟留出答案評分。
原本6訓練轉換族仍是第一輪控制。新族與真 ARC 結果是轉移測試；預留32個真 ARC 訓練父題的 API 未啟用，不冒充已擴大訓練。

結束下載：輸出目錄中的 evidence.zip、terminal-receipt.json、checkpoints.zip，以及同名前綴加 -launcher 的完整目錄和實際 notebook。evidence.zip 包含選答/評分/成本/流程證據；checkpoints.zip 另存真正 adapter 與完整邏輯訓練狀態，可能約1.6GiB。失敗/部分完成也請保留全部已寫檔案。模型結果必須看 PORTFOLIO_COMPLETE 與逐題指標，不能只看 Kaggle COMPLETE。
'''
    notebook={'cells':[cell('markdown',title),cell('code',config),cell('code',embedded),cell('code',run)],
        'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                    'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
    for c in notebook['cells']:
        if c['cell_type']=='code':compile(''.join(c['source']),'<qwen-notebook>','exec')
    return notebook
