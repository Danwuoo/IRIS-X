"""Independent retained-byte replay of actual native CPU main and TTT runs."""
from pathlib import Path
import json,hashlib,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012.public_evaluation import _ledger
from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
from tools.arc_learning_agent_20261011.grid_codec import decode_grid
sha=lambda b:hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_bytes())
def require(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 root=ROOT/'native-transfer-1791808915341057591';term=load(root/'terminal-receipt.json');proof=load(root/'owned-tree/closure.json');verify_closed_proof(proof)
 require(proof['closed'] and not proof['forced'] and not proof['remaining'] and proof['worker_returncode']==0,'actual owned closure')
 require(term['status']=='TRANSFER_COMPLETE' and term['operational_success'] and not term['goal_met'] if 'goal_met' in term else term['status']=='TRANSFER_COMPLETE' and term['operational_success'],'fixture terminal')
 request=load(root/'request.json');copy=ROOT/'native-test-source-20261012-1241'
 # Retrospective receipt consistency only: the original live coordinator is gone.
 # Do not bypass or relabel the stricter contemporaneous public-scoring owner gate.
 launch=load(root/'owned-tree/launch.json');worker=load(root/'owned-tree/worker-launch.json')
 require(launch['supervisor_identity']==worker['supervisor_identity']==proof['root_identity'],'retained supervisor identity')
 require(worker['worker_identity'] in proof['owned_identities'],'retained child identity')
 require(launch['worker_argv'][-3:]==[str(copy/'tools/arc_qwen_transfer_20261012/child.py'),str(root/'request.json'),sha((root/'request.json').read_bytes())],'retained exact source/request argv')
 for path,h in request['source_identity'].items():require(sha((copy/path).read_bytes())==h,'native source copy '+path)
 for key in ['archive','checkpoint_archive']:
  art=term[key];require(sha(Path(art['path']).read_bytes())==art['sha256'],'archive checksum')
  with zipfile.ZipFile(art['path']) as z:
   require(z.testzip() is None,'archive CRC');require(len(z.namelist())==art['files'],'archive member count')
   manifest=load(root/('archive-manifest.json' if key=='archive' else 'checkpoint-assets-manifest.json'))
   for name,entry in manifest['files'].items():require(sha(z.read(name))==entry['sha256'] and len(z.read(name))==entry['bytes'],'archive member '+name)
 events,totals=_ledger((root/'physical-work.jsonl').read_bytes())
 require(totals==term['child']['physical_usage'],'main physical totals')
 require(totals['training_steps']==4 and totals['generation_calls']==230,'calibration-inclusive actual work')
 n=0;event_ids=set()
 for scope,expected_methods,count in [('dev',{'base','sft1','sft2'},16),('holdout',{'base','selected_sft'},32)]:
  seal=load(root/'experiment'/f'{scope}-prediction-seal.json');payload=load(Path(seal['path']))
  require(sha(Path(seal['path']).read_bytes())==seal['file_sha256'],'seal hash')
  require(set(payload['methods'])==expected_methods and len(payload['case_ids'])==count,'fixed main scope')
  for method,rows in payload['methods'].items():
   require(len(rows)==count and all(r['complete'] for r in rows),'full main denominator')
   for row in rows:
    require([g['transform_d4'] for g in row['generations']]==[0,1],'actual two transforms')
    for generation in row['generations']:
     receipt=load(Path(generation['receipt_path']));require(sha(Path(generation['receipt_path']).read_bytes())==generation['receipt_sha256'],'native receipt hash')
     eid=receipt['physical_event_id'];require(eid==generation['physical_event_id'] and eid in events and eid not in event_ids,'unique physical main dispatch');event_ids.add(eid)
     require(receipt['dispatched'] and receipt['full_vocabulary_rows']==151936,'actual full-head dispatch')
     if receipt['valid']:
      grid=[list(x) for x in Transform(generation['transform_d4']).inverse().apply(decode_grid(receipt['text']))]
      require(grid==generation['prediction'],'actual native inverse')
     n+=1
 require(n==224,'224 primary generations')
 for update in [1,2]:
  reload=load(root/'experiment'/f'fresh-reload-{update}.json');require(reload['fresh_backend_reload_verified'] and reload['loaded']['complete_training_state'] and reload['loaded']['physical_ledger_untouched'],'fresh reload receipt')
 cal=load(root/'calibration/calibration.json');require(cal['completed_lengths']==[128,512] and not cal['full_context_measured'] and cal['cpu_fixture_only'],'honest shortened calibration')
 report={'main':{'root':str(root),'evidence_sha256':term['archive']['sha256'],'source_files_checked':len(request['source_identity']),'actual_main_generations':n,'total_physical':totals,'owned_closed_without_forcing':True,'retrospective_launch_binding_verified':True,'contemporaneous_public_scoring_reperformed':False,'fresh_reloads':2,'fixture_only':True}}
 root=ROOT/'native-ttt-1791809444730656889';res=load(root/'result.json');case=root/'experiment/ttt/d93c6891';out=res['result'];events,totals=_ledger((root/'physical-work.jsonl').read_bytes())
 require(totals==res['physical_usage'],'TTT physical totals');require(out['physical_usage']['training_steps']==48 and out['physical_usage']['generation_calls']==12 and out['physical_usage']['scoring_forwards']==6,'complete native TTT cost')
 global_hash=out['candidate_state_hashes']['ttt0'][0];require(out['candidate_state_hashes']['ttt0']==[global_hash]*3,'all independent starts selected SFT')
 ids=set()
 for branch in ['fold-0','fold-1','full-demo']:
  for update in [8,16]:
   train=load(case/f'{branch}-train-{update}.json');require(train['optimizer_steps']==8 and train['total_steps']==update,'TTT fresh update count')
   require([u['adam_step'] for u in train['updates']]==list(range(update-7,update+1)),'actual fresh Adam branch steps')
   eid=train['physical_event_id'];require(eid in events and eid not in ids,'charged unique TTT training');ids.add(eid)
   require(events[eid]['amounts']['training_steps']==8,'exact charged branch cost')
   if update==8:require(train['adapter_before_sha256']==global_hash,'actual selected-SFT branch initialization')
  reset=load(case/f'{branch}-reset.json');require(reset['adapter_sha256']==global_hash and all(reset[k] for k in ['caller_rng_restored','gradients_cleared','optimizer_cleared','scheduler_cleared']),'full branch reset')
 inputs=load(case/'selector-inputs.json')
 for candidate in inputs['candidates']:
  require(len(candidate['folds'])==2 and len(candidate['query_predictions'])==2,'complete candidate evidence')
  for fold in candidate['folds']:require(fold['heldout_demo_id'] not in fold['adaptation_demo_ids'] and fold['heldout_demo_id'] not in fold['conditioning_demo_ids'],'held demo excluded')
 representative=out['representative_checkpoint'];require(sha((Path(representative['path'])/'manifest.json').read_bytes())==representative['manifest_sha256'],'representative persisted checkpoint')
 require(load(root/'prepared4096.json')['input_tokens']==4096,'native 4096 preparation (not forward)')
 report['ttt']={'root':str(root),'result_sha256':sha((root/'result.json').read_bytes()),'actual_cost':out['physical_usage'],'full_independent_refits':3,'fresh_adam_steps_verified':True,'full_resets_verified':True,'fixture_only':True}
 report['status']='passed';report['limitations']=['CPU tiny random weights only; no 14B/GPU efficacy','4096 prepared input only; no 4096 native backward','Owner main ran frozen source; later changes require focused source/delta tests']
 (ROOT/'runtime-review/actual-receipts-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
