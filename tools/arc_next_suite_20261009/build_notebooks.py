"""Build exactly ten inert, compressed-source Kaggle notebooks and manifests."""
from pathlib import Path
import base64,hashlib,json,zlib
ROOT=Path(__file__).parent;SRC=ROOT/'src'
lock=json.loads((SRC/'source-lock.json').read_text());design=json.loads((SRC/'DESIGN-FROZEN.json').read_text())
files={n:(SRC/n).read_text() for n in lock['files']};files['source-lock.json']=(SRC/'source-lock.json').read_text()
hashes={n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}
raw=json.dumps(files,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();packed=zlib.compress(raw,9);payload=base64.b64encode(packed).decode()
import sys;sys.path.insert(0,str(SRC));import arc_suite
pins=arc_suite.EXPECTED_PINS
notebooks=[]
for spec in design['runs']:
 run=spec['id'];number=run[1:];filename=f'IRIS-X-{run}-{spec["slug"].removeprefix("iris-x-"+run.lower()+"-")}-20261009.ipynb'
 prereqs={'N9':['N6'],'N10':['N6'],'N11':['N6'],'N12':['N7'],'N14':['N6','N7','N9','N10','N11']}.get(run,[])
 intro=f'''# IRIS-X {run} · {spec['question']}

修正版 {arc_suite.SUITE_REVISION}：修正 runtime8 原始 N1 manifest 與衍生 FIX1 reference 混用。使用新 output/source 目錄；舊版 evidence 不會自動升級成新 gate 收據。實驗 tasks、prompts、seeds 與 budgets 不變。

這是十份分階段實驗之一。預設停用，儲存為 private inactive QUICK_SAVE。沒有啟動 GPU、訓練、付費執行或競賽 submission。

## 要檢驗的假說
{spec['hypothesis']}

- Arms: {', '.join(spec['arms'])}
- 固定 tasks: {spec['tasks']}；model calls 上限: {spec['max_model_calls']}
- 生成 tokens 上限: {spec['max_model_calls']*2048:,}；prompt tokens 上限: {spec['max_model_calls']*6144:,}
- 每 call 最多2048新 tokens／6144prompt／8192context；不截斷 demonstrations、query 或修復 source
- {spec['gate']}
- Go/no-go: {spec['go_no_go']}

## 研究範圍
N4 的61份程式只有45份可 parse、0份通過原 bounded language。這份 suite 先分開 language admission 和 semantic reasoning，再測 representation、feedback、memory 和 search。V2仍是 gas-bounded AST interpreter；只新增受限 while、list methods 等，模型程式從不送入 Python exec/eval。

N5–N12使用原8題已曝光工程題；N14使用原 tuning[8:40] 的32題，這32題已被N3測過，和設計8題不重疊，仍不是新 holdout。136題 confirmation完全不使用。上限相同不代表實際compute相同。N9完整object view在工程題33067df9、N14候選object policy在a096bf4d超過prompt cap；這些exclusion保留在分母，不補題。N13只產生verified synthetic F/G/P/R資料，不訓練或聲稱SFT提升。

## 手動執行
1. 保持目前固定Dataset版本與Internet關閉。N5/N13為CPU-only，不需要CUDA、模型或G4；其他實驗需要既有已验证的G4環境：1×96GB-class RTX PRO6000 Blackwell、48CPUs、host RAM≥170GiB，原CPython3.12/cu128離線包。4×L4 deployment 尚未在本suite實测。
2. 必要時填入實際Dataset mount和PRIOR_RESULTS。前置證據可用本suite輸出的evidence ZIP，或完整解壓資料夾。所需prior runs: {', '.join(prereqs) if prereqs else '無'}。不要刪除或修改seal、report、final-inventory等metadata。
3. 願意開始此輪運算時才將 MANUAL_START 改成 True。前置gate失敗會在安裝或載入模型前產生BLOCKED收據，不能跳過gate。
4. 看IRIS-SUITE heartbeat與逐record進度，結尾必須有EXPERIMENT-FINISHED或EXPERIMENT-BLOCKED。下載所列evidence ZIP；未完成、context exclusion、late、unknown work都保留固定分母。
5. 不覆寫／重抽相同run identity；先保存結果。controller上限{'600 CPU replay' if run=='N5' else '1200 CPU curriculum' if run=='N13' else '32400' if run=='N14' else '9600'}秒；generation120秒為cooperative，並非整個VM硬停止。初始化驗證／interpreter preparation／seal／score／export及清理可能超時。
6. 程式不會停止VM計費。完成後自行停止VM。沒有新增授權GPU/training或自動發布資料。

SOURCE-LOCK: {hashes['source-lock.json']}
'''
 config=f'''from pathlib import Path
MANUAL_START = False
RUN_ID = {run!r}
RUNTIME_ROOT = MODEL_ROOT = WHEELS_ROOT = INTERPRETER_ROOT = ADAPTER_ROOT = None
PRIOR_RESULTS = {repr({r:None for r in prereqs})}
BASE = (Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()) / {'iris-nextphase-'+run.lower()+'-'+arc_suite.SUITE_REVISION!r}
'''
 data='PINS = '+repr(pins)+'\nFILE_HASHES = '+repr(hashes)+'\nPACKED_SOURCE_SHA256 = '+repr(hashlib.sha256(packed).hexdigest())+'\nUNPACKED_SOURCE_BYTES = '+str(len(raw))+'\nPACKED_SOURCE_BASE64 = '+repr(payload)+'\n'
 execute='''import base64, hashlib, importlib.util, importlib.machinery, json, zlib
if type(MANUAL_START) is not bool:
    raise ValueError('Explicit Boolean manual switch required')
if not MANUAL_START:
    print('INACTIVE: '+RUN_ID+' saved. No installation, writes, model load, generation, training, dataset export or submission occurred.')
else:
    packed=base64.b64decode(PACKED_SOURCE_BASE64,validate=True)
    if hashlib.sha256(packed).hexdigest()!=PACKED_SOURCE_SHA256:raise ValueError('Embedded compressed source changed')
    decoder=zlib.decompressobj();raw=decoder.decompress(packed,UNPACKED_SOURCE_BYTES+1)
    if len(raw)!=UNPACKED_SOURCE_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Embedded source size/stream differs')
    files=json.loads(raw)
    if set(files)!=set(FILE_HASHES):raise ValueError('Closed embedded source inventory differs')
    for name,value in files.items():
        if Path(name).name!=name or hashlib.sha256(value.encode()).hexdigest()!=FILE_HASHES[name]:raise ValueError('Embedded source hash/path differs')
    def root(role,explicit):
        owner,slug,version=PINS[role]['reference'].split('/')
        choices=[Path(explicit)] if explicit else [Path('/kaggle/input/datasets')/owner/slug,Path('/kaggle/input')/slug]
        found=[p for p in choices if p.is_dir()]
        if len(found)!=1:raise ValueError('Exactly one pinned Dataset mount required: '+role)
        return found[0].absolute()
    required=[] if RUN_ID=='N13' else ['runtime'] if RUN_ID=='N5' else list(PINS)
    roots={role:root(role,globals()[role.upper()+'_ROOT']) for role in required}
    BASE=BASE.absolute()
    if any(p.is_symlink() for p in (BASE,*BASE.parents)) or any(BASE.resolve().is_relative_to(p.resolve()) for p in roots.values()):raise ValueError('Output must be non-symlink and outside every input')
    source=BASE/'source'
    if source.is_symlink():raise ValueError('Symlink source directory forbidden')
    source.mkdir(parents=True,exist_ok=True)
    for name,value in files.items():
        path=source/name
        if path.is_symlink():raise ValueError('Symlink source forbidden')
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=FILE_HASHES[name]:raise ValueError('Existing source differs')
        else:
            with path.open('xb') as stream:stream.write(value.encode())
    entry=files['arc_suite.py'].encode();name='iris_suite_entry_'+FILE_HASHES['arc_suite.py']
    class VerifiedLoader(importlib.machinery.SourceFileLoader):
        def get_code(self,fullname):return self.source_to_code(entry,str(source/'arc_suite.py'))
    spec=importlib.util.spec_from_file_location(name,source/'arc_suite.py',loader=VerifiedLoader(name,str(source/'arc_suite.py')))
    suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
    cfg={'output_root':str(BASE/'runs')}
    if RUN_ID!='N13':cfg['runtime_root']=str(roots['runtime'])
    if RUN_ID not in ('N5','N13'):
        cfg.update({role+'_root':str(path) for role,path in roots.items()})
        cfg.update(interpreter_dir=str(BASE/'cpython312'),environment_dir=str(BASE/'environment-cp312-cu128'),pins=PINS)
    result=suite.launch(cfg,RUN_ID,enabled=True,prior_paths={key:value for key,value in PRIOR_RESULTS.items() if value is not None})
    print(json.dumps(result,ensure_ascii=False,indent=2))
'''
 def cell(kind,source,index):
  result={'cell_type':kind,'metadata':{},'source':source.splitlines(keepends=True),'id':run.lower()+'-'+str(index)}
  if kind=='code':result.update(execution_count=None,outputs=[])
  return result
 nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python3','language':'python','name':'python3'},'language_info':{'name':'python'},
     'irisx_run_id':run,'irisx_suite_revision':arc_suite.SUITE_REVISION,'irisx_execution_mode':'QUICK_SAVE','irisx_agent_execution_authorized':False,'irisx_gpu_validation_performed':False,
     'irisx_manual_start':False,'irisx_source_lock_sha256':hashes['source-lock.json'],'irisx_offline_dataset_pins':pins,
     'irisx_max_generate_calls':spec['max_model_calls'],'irisx_prior_runs':prereqs},'cells':[cell('markdown',intro,0),cell('code',config,1),cell('code',data,2),cell('code',execute,3)]}
 path=ROOT/'notebooks'/filename;path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n')
 title=f'IRIS-X {run} '+spec['slug'].removeprefix('iris-x-'+run.lower()+'-').replace('-',' ').title()
 publication={'run_id':run,'owner':'danielwuu','title':title,'slug':spec['slug'],'reference':'danielwuu/'+spec['slug'],
      'notebook':str(path.resolve()),'filename':filename,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,
      'private':True,'mode':'QUICK_SAVE','kernel_execution_type':3,'enable_gpu':False,'enable_tpu':False,'enable_internet':False,'manual_start':False,
      'gpu_execution_authorized':False,'training_authorized':False,'competition_submission_authorized':False,'language':'python','notebook_type':'notebook',
      'competition_sources':['arc-prize-2026-arc-agi-3'] if run=='N6' else [],'competition_metadata_preserved_only':True,'competition_data_used':False,
      'dataset_sources':[v['reference'] for v in pins.values()],'dataset_pins':pins,'runtime_dataset_upload_required':False,
      'max_generate_calls':spec['max_model_calls'],'max_generated_tokens':spec['max_model_calls']*2048,'max_prompt_tokens':spec['max_model_calls']*6144,
      'prerequisites':prereqs,'source_lock_sha256':hashes['source-lock.json'],'new_notebook_do_not_overwrite_previous':False,'update_existing_reviewed_notebook':True,'preserve_previous_provider_version':True,'suite_revision':arc_suite.SUITE_REVISION}
 (ROOT/'publication'/(run+'.json')).write_text(json.dumps(publication,indent=2)+'\n');notebooks.append(publication)
manifest={'format':'irisx/exact-ten-publication-v1','count':10,'source_lock_sha256':hashes['source-lock.json'],'design_sha256':hashes['DESIGN-FROZEN.json'],
          'total_model_call_ceiling':sum(x['max_generate_calls'] for x in notebooks),'gpu_execution_performed':False,'training_performed':False,
          'publication_status':'requires_separate_independent_release','suite_revision':arc_suite.SUITE_REVISION,'notebooks':notebooks}
(ROOT/'publication-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'notebooks':len(notebooks),'compressed_source_bytes':len(packed),'uncompressed_source_bytes':len(raw),'total_notebook_bytes':sum(x['bytes'] for x in notebooks)},indent=2))

# Notebook-only input handling remains separately pinned from scientific sources.
import runpy
runpy.run_path(str(ROOT/'build_input_repair.py'),run_name='__main__')
