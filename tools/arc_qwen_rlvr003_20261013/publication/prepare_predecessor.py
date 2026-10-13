"""Local byte-bound v29 handoff. No provider, model, or scorer calls."""
from pathlib import Path
import hashlib,json
BASE=Path('/workspace/scratch/3c2b2502fb1e')
OLD=BASE/'portfolio63-rl-bootstrap-repair-20261013'
OUT=Path(__file__).resolve().parent/'PREDECESSOR-DESCRIPTORS.json'
def desc(p):
    p=p.absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('symlink')
    raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def obj(p):return json.loads(p.read_bytes())
audit=OLD/'independent-operator-review/V29-FAILED-TERMINAL-AUDIT.json'
assert desc(audit)['sha256']=='a643c622e47376fe64ec2d41318258bc59039bfaa2a86120ad243d188be27c2e'
a=obj(audit)
p=OLD/'publication';e=p/'run-evidence';d=e/'downloads';run='irisx-qwen14b-rlvr-20261012-run002'
paths={
 'failed_terminal_audit':audit,
 'frozen_wrapper_replay':OLD/'independent-operator-review/V29-FROZEN-TERMINAL-BLOCKER-REPLAY-FINAL.json',
 'separate_consumer_replay':OLD/'independent-operator-review/V29-SEPARATE-CONSUMER-DIAGNOSTIC-REPLAY.json',
 'admission_audit':OLD/'independent-operator-review/V29-ADMISSION-AUDIT.json',
 'code_receipt':p/'state/dataset-code-v15-receipt.json',
 'launch_receipt':p/'state/notebook-rlvr002-receipt.json',
 'saved_source':p/'state/notebook-rlvr002-saved.ipynb',
 'terminal_checkpoint':e/'V29-TERMINAL-COST-CHECKPOINT.json',
 'terminal_index':e/'V29-TERMINAL-EVIDENCE-INDEX.json',
 'terminal_blocker':e/'WATCH-BLOCKER.json',
 'retrieval_receipt':e/'retrieval-1791853000626474890.json',
 'terminal_receipt':d/(run+'.evidence.zip.terminal.json'),
 'evidence_archive':d/(run+'.evidence.zip'),
 'runtime_outer_closure':d/run/'outer-closure.json',
 'owned_result':d/run/'owned-result.json',
}
evidence={k:desc(v) for k,v in paths.items()}
assert evidence['saved_source']['sha256']==a['saved_source_sha256']=='5ca3ce3f2774f1a962767e49ff1cbabb64656157bc0ea977e30e65923dbfed6c'
assert a['status']=='PASS_QUALIFIED_FAILED_TERMINAL_INTEGRITY' and a['provider_status']=='ERROR' and a['notebook_version']==29
for k in ('runtime_model_closure_verified','runtime_safe_closure','physical_costs_known','consumer_admitted','goal_met','terminal_validated'):assert a[k] is False
r={'format':'irisx/rlvr003-predecessor-evidence-v1','notebook_id':138123872,'numeric_notebook_version':29,'code_dataset_id':12504696,'code_dataset_version':15,'provider_status':'ERROR','saved_source_sha256':a['saved_source_sha256'],'runtime_status':'stopped-incomplete','terminal_status':'diagnostic','terminal_validation_status':'BLOCKED_FROZEN_WRAPPER_AND_UNSEALED_SESSION','selected_files_verified':33,'required_files_missing':0,'archive_members_verified':22,'diagnostic_archive_integrity_verified':True,'external_stage_process_closure_verified':True,'runtime_worker_exited':True,'runtime_worker_session_empty':True,'runtime_worker_returncode':1,'runtime_safe_closure':False,'runtime_model_closure_verified':False,'physical_journal_exists_in_sealed_archive':False,'terminal_validated':False,'consumer_admitted':False,'owned_closure_verified':False,'physical_costs_known':False,'billing_verified':False,'operational_success':False,'goal_met':False,'public_score':None,'whole_provider_inventory_verified':False,'checkpoint_archive_bytes_verified':False,'separate_checkpoint_presence':'UNKNOWN','diagnosis':{'runtime_error':a['runtime_error'],'frozen_wrapper_error':{'type':'KeyError','message':'original_clock'},'consumer_rejection':'owner request byte binding differs','failure_stage':'real-data construction before authenticated model session','source_linked':True},'evidence':evidence,'qualification':'Both deployment process stages terminated cleanly with return1. The runtime model/session journal did not seal, so model closure and physical cost remain unverified. Source-linked data-loader failure, frozen wrapper schema blocker, and separate consumer rejection remain distinct. Historical diagnostic integrity does not admit production or authorize another dispatch.'}
raw=(json.dumps(r,sort_keys=True,indent=2)+'\n').encode()
with OUT.open('xb') as f:f.write(raw)
print(json.dumps(desc(OUT)))
