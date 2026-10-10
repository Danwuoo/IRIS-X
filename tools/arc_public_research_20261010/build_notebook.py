"""Build a small default-inert notebook pinned to separate code/data Datasets."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from .offline_bootstrap import PINS as MODEL_PINS

ROOT=Path(__file__).resolve().parent
TITLE='IRIS-X PUBLIC120 Research 20261010'
REFERENCE='danielwuu/iris-x-public120-research-20261010'

def build(pins):
    if set(pins)!={'code','data'}:raise ValueError('exact code/data pins required')
    for row in pins.values():
        if len(row['manifest_sha256'])!=64:raise ValueError('unfrozen manifest')
    markdown='''# IRIS-X PUBLIC120：公開研究評分\n\n此 notebook 使用專案原有 ARC-AGI-2 scorer，固定公開120題／167個測試輸入。資料已有開發曝光，並非未觸碰確認集。這是研究硬體上的推論；competition_gpu_equivalent=false，官方競賽分數為null。\n\n## 執行\n1. 保留7個已固定版本的私有 Dataset。Internet 關閉。模型路徑為既有 G4 RTX PRO 6000 Blackwell／48CPU；GPU真實整合須由此次手動run建立，CPU合約測試不保證GPU結果。\n2. 全新kernel：將 MANUAL_START=True，若要模型比較同時 ENABLE_MODEL=True；PROFILE保持PUBLIC120，RESUME=False。OUTPUT_ROOT每次選全新名稱。預設兩個開關皆False，因此Run All不讀Dataset、不安裝、不推論。\n3. Run All一次。先做128個控制，再完成兩種CPU排名，各題各64候選；模型共最多240calls，一次載入。每個policy只將新鮮demo-fit計畫執行query，凍結預測並停止模型後，獨立CPU scorer才讀公開答案。\n4. 不需重新執行舊FULL 47,720枚舉。沒有coverage cache，也不要求舊8題witness gate；舊notebook保留原合約。\n\n## 預算與輸出\n固定最多17,064次CPU驗證、4workers、240model calls、7200秒整個session；包含bootstrap、tokenizer、搜尋、query、評分與封存。單次模型120秒、prompt6144/output2048/context8192。每個VM200000gas、256MiB、2CPU秒／3wall秒。預算耗盡保留缺失分母；unknown不能自動重試。Partial run不能resume，請保留證據並用新OUTPUT_ROOT重跑。\n\nraw／strict使用相同有限5965計畫支援與prompt／seed，strict只限制native token合法路徑，這不是無限制程式生成。uniform／shape_palette_v1保留每個候選正支持；沒有注入已知witness或gold特徵。\n\n主輸出為研究summary、四個sealed prediction pools、scorer報告、ledger與evidence ZIP。下載ZIP及其同run post-seal-closure.json和最後ledger/journal.jsonl；最後兩者完成於ZIP封存後，須一併保存。不要只截取最後一行，也不要把synthetic測試當實際分數。\n\n模型及所有owned子程序停止才允許score；若停止／封存證據不完整會標記SCORING_BLOCKED，而不是偽造0分。評分沿用exact-grid pass@1/pass@2、167-test全分母與120-task補充指標。adapter驗證但不使用，沒有訓練。\n'''
    config="""MANUAL_START = False
ENABLE_MODEL = False
PROFILE = 'PUBLIC120'
RESUME = False
OUTPUT_ROOT = 'irisx-public120-20261010-run001'
SOURCE_PARENT = '.irisx-public120-source'
INPUT_ROOT = '/kaggle/input'
CODE_ROOT = None
DATA_ROOT = None
MODEL_CONFIG = None
SESSION_SECONDS = 7200
"""
    loader= (ROOT/'source_loader.py').read_text()
    source = loader+'\n\nPUBLIC_PINS = '+repr(json.loads(json.dumps(pins,sort_keys=True)))+'\n'
    source += """
_PUBLIC_READY = None
if type(MANUAL_START) is not bool or type(ENABLE_MODEL) is not bool or type(RESUME) is not bool:
    raise ValueError('Manual/model/resume switches must be exact Booleans')
if PROFILE != 'PUBLIC120':
    raise ValueError('Only the frozen PUBLIC120 profile is available')
if type(SESSION_SECONDS) is not int or not 124 <= SESSION_SECONDS <= 7200:
    raise ValueError('Session budget must be an integer within 124..7200 seconds')
if MANUAL_START:
    import time as _public_time
    _PUBLIC_STARTED = _public_time.monotonic()
    _public_config = {} if MODEL_CONFIG is None else MODEL_CONFIG
    _PUBLIC_READY = load_reviewed_source(pins=PUBLIC_PINS,input_root=INPUT_ROOT,
        code_root=CODE_ROOT,data_root=DATA_ROOT,source_parent=SOURCE_PARENT,
        output_root=OUTPUT_ROOT,model_config=_public_config,resume=RESUME)
"""
    run="""if MANUAL_START:
    import json as _public_json
    from tools.arc_public_research_20261010.runner import run as _public_run
    _public_elapsed = _public_time.monotonic() - _PUBLIC_STARTED
    _public_result = _public_run(output_root=_PUBLIC_READY['output_root'],
        solver_root=_PUBLIC_READY['solver_root'],evaluator_root=_PUBLIC_READY['evaluator_root'],
        solver_manifest_sha256=_PUBLIC_READY['solver_manifest_sha256'],
        evaluator_manifest_sha256=_PUBLIC_READY['evaluator_manifest_sha256'],
        enable_model=ENABLE_MODEL,model_config=MODEL_CONFIG,resume=RESUME,
        session_seconds=SESSION_SECONDS,entry_wall_seconds=_public_elapsed,
        entry_provenance=_PUBLIC_READY['entry_provenance'])
    _public_report = _public_result.get('report', {})
    _public_costs = _public_report.get('accounting', {}).get('charged', {})
    _public_visible = {'run_id':_public_result.get('session_id'), 'profile':'PUBLIC120',
        'status':_public_result.get('status'), 'model_status':_public_report.get('model', {}).get('status'),
        'scoring_status':_public_report.get('scoring', {}).get('status'),
        'physical_calls':_public_costs.get('physical_calls'), 'cpu_checks':_public_costs.get('cpu_checks'),
        'archive':_public_result.get('archive'), 'output_root':_public_result.get('output_root'),
        'closure':_PUBLIC_READY['output_root']+'/post-seal-closure.json',
        'summary_path':_PUBLIC_READY['output_root']+'/summary.json',
        'wall_seconds':_public_report.get('elapsed_seconds'), 'competition_gpu_equivalent':False,
        'source_transport_mode':_PUBLIC_READY['source_transport_mode'],
        'source_archive_bytes_verified':_PUBLIC_READY['source_archive_bytes_verified']}
    _public_text = _public_json.dumps(_public_visible,sort_keys=True,ensure_ascii=False)
    if len(_public_text.encode('utf-8')) > 8192:
        raise ValueError('Unexpectedly large terminal summary; full evidence remains on disk')
    print(_public_text)
else:
    print('PUBLIC120 is disabled. Set MANUAL_START=True to begin the bounded research run.')
"""
    cells=[]
    for kind,text in [('markdown',markdown),('code',config),('code',source),('code',run)]:
        c={'cell_type':kind,'metadata':{},'source':text.splitlines(keepends=True)}
        if kind=='code':c.update(execution_count=None,outputs=[])
        cells.append(c)
    return {'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12.13'}},'nbformat':4,'nbformat_minor':5}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pins',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    nb=build(json.loads(Path(a.pins).read_bytes()));raw=(json.dumps(nb,ensure_ascii=False,indent=2)+'\n').encode()
    Path(a.output).write_bytes(raw);print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'reference':REFERENCE}))
