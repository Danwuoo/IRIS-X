"""Apply the separately pinned notebook-only input repair to N9–N14."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).parent
helper=(ROOT/'notebook_support/arc_evidence_inputs.py').read_text()
helper_sha=hashlib.sha256(helper.encode()).hexdigest()
entry=(ROOT/'notebook_support/notebook_entry.py').read_text()
pin=json.loads((ROOT/'docs/PREREQUISITE-DATASET-PIN.json').read_text())
manifest=json.loads((ROOT/'publication-manifest.json').read_text())
byid={x['run_id']:x for x in manifest['notebooks']}
revision='evidence-inputs-fix2-20261010'
for run in ('N9','N10','N11','N12','N13','N14'):
 row=byid[run];path=ROOT/'notebooks'/row['filename'];nb=json.loads(path.read_text())
 def replace(index,text):nb['cells'][index]['source']=text.splitlines(keepends=True)
 intro=''.join(nb['cells'][0]['source']).split('\n## 自動前置證據修正')[0]
 intro=intro.replace('必要時填入實際Dataset mount和PRIOR_RESULTS。','必要時填入實際Dataset mount。PRIOR_RESULTS 可保持 None，自動尋找前置證據。')
 intro=intro.replace('使用新 output/source 目錄；舊版 evidence 不會自動升級成新 gate 收據。','保留科學 source lock 與 run identity；不會將不相容 evidence 升級成新 gate 收據。')
 intro+='''\n## 自動前置證據修正 · evidence-inputs-fix2-20261010

- 本修正不再掃描 Kaggle competitions 掛載與 .git/.hg/.svn metadata；搜尋深度／數量上限不變。一般 Dataset 的多層 evidence 與同名 wrapper 仍會完整檢查。
- 保持 PRIOR_RESULTS 的 None 即可。自動在 /kaggle/input 的有限深度內尋找完整 ZIP 或 Kaggle 自動解壓後的多層資料夾；不需手打 ZIP 路徑。
- N9–N11 已掛載完整 N6；N12 已掛載完整 N7。N14 仍須等 N9、N10、N11 真實完成結果，沒有跳過 gate。N13 不讀前置資料也不碰模型。
- 每份證據都先驗證 run/source-lock、完整 inventory、seal、完成與停止狀態。ZIP 與相同解壓副本會合併；不同有效結果會停止並要求明確選擇。PRIOR_RESULTS 保留作有意識的完整證據路徑 override。
- 缺少或不合格前置資料會在安裝／模型前輸出零 calls 的 BLOCKED 收據，列出預期 runs 與搜尋位置。
- 只有完整驗證為零 calls 的 terminal BLOCKED 才能重試。重新執行會使用 attempts/attempt-0002 等新目錄，保留前次 ZIP／收據；complete、partial、已開始或不明狀態不會自動重跑。
- 科學 source lock 仍是 29172a035efc7704cd3f60e663a714a7570c18f636fdca32304be94d02689d50。新增 helper 為獨立 hash-bound notebook I/O，不改 tasks、prompts、seeds、budgets 或 gates。
'''
 replace(0,intro)
 config=''.join(nb['cells'][1]['source']).split('\n# NOTEBOOK INPUT REPAIR')[0]
 config+='\n# NOTEBOOK INPUT REPAIR: None keeps verified automatic discovery enabled.\nPRIOR_SEARCH_ROOTS = [Path("/kaggle/input")]\n'
 replace(1,config)
 data=''.join(nb['cells'][2]['source']).split('\n# NOTEBOOK INPUT HELPER')[0]
 usepin=pin if run!='N13' else None
 data+='\n# NOTEBOOK INPUT HELPER: separately pinned, outside the immutable scientific source lock.\n'
 data+='NOTEBOOK_INPUT_HELPER_SHA256 = '+repr(helper_sha)+'\nNOTEBOOK_INPUT_HELPER_SOURCE = '+repr(helper)+'\nPRIOR_DATASET_PIN = '+repr(usepin)+'\n'
 replace(2,data);replace(3,entry)
 nb['metadata'].update(irisx_notebook_input_revision=revision,irisx_notebook_input_helper_sha256=helper_sha,
   irisx_prior_dataset_pin=usepin,irisx_auto_prior_discovery=True,irisx_blocked_only_retry=True)
 path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n')
 row.update(notebook=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,
   notebook_input_revision=revision,notebook_input_helper_sha256=helper_sha,prior_dataset_pin=usepin,
   runtime_dataset_upload_required=False,prerequisite_dataset_upload_required=False,
   competition_sources=['arc-prize-2026-arc-agi-3'] if run=='N9' else [])
 row['dataset_sources']=[x['reference'] for x in row['dataset_pins'].values()]+([pin['reference']] if usepin else [])
 (ROOT/'publication'/(run+'.json')).write_text(json.dumps(row,indent=2)+'\n')
manifest.update(notebook_input_revision=revision,notebook_input_helper_sha256=helper_sha,
  updated_runs=['N9','N10','N11','N12','N13','N14'],unchanged_runs=['N5','N6','N7','N8'])
(ROOT/'publication-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'input_revision':revision,'helper_sha256':helper_sha,'updated_runs':manifest['updated_runs']}))
