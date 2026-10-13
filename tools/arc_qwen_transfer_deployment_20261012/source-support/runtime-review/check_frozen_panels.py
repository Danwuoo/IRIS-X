"""Read-only independent metadata replay; reads no training tasks/evaluator gold."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import data as d
from tools.arc_public_research_20261010.public_data import load_solver_tasks
from src.irisx.arc_nvarc_data import known_variant_group

def require(ok,text):
    if not ok:raise ValueError(text)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
panel=ROOT/'panel-freeze'
ex=json.loads((panel/'public120-exclusions.json').read_bytes())
frozen=json.loads((panel/'frozen-panel-plan.json').read_bytes())
require(sha(panel/'public120-exclusions.json')=='ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e','changed exclusion bytes')
require(sha(panel/'frozen-panel-plan.json')=='8138168e1c8206977efaab20243ac66e04fe5d0cf5d375252b7cca68feefa17a','changed panel bytes')
solver=ROOT/'materials/public120-solver/solver'
loaded=load_solver_tasks(solver.absolute(),ex['source']['solver_manifest_sha256'])
require(sha(solver/'public-challenges.json')==ex['source']['challenges_sha256'],'challenge binding')
require(sha(ROOT/'materials/public120-solver/RETRIEVAL-RECEIPT.json')==ex['source']['retrieval_receipt_sha256'],'retrieval binding')
require(sha(ROOT/'worktree/src/irisx/arc_nvarc_data.py')==ex['source']['variant_implementation_sha256'],'variant source binding')
challenges=loaded['challenges'];ids=sorted(challenges)
require(len(ids)==120 and sum(len(t['test']) for t in challenges.values())==167,'exact public denominator')
require(all(set(q)=={'input'} for t in challenges.values() for q in t['test']),'gold present in solver')
require(ex['public_parent_ids']==ids and ex['ancestor_ids']==ids and ex['aliases']==[],'complete source identities')
variants=sorted({known_variant_group({'train':t['train'],'test':[]}) for t in challenges.values()})
require(variants==ex['known_variant_groups'],'demo-only known variants exact')
inventory=d.load_inventory();part,replay=d.freeze_panels(inventory,ex)
require(json.loads(json.dumps(replay))==frozen,'deterministic metadata panel replay differs')
sets=[set(replay[k]) for k in ('train_ids','dev_ids','holdout_ids')]
require([len(s) for s in sets]==[32,16,32],'panel denominator')
require(not any(a&b for i,a in enumerate(sets) for b in sets[i+1:]),'cross panel overlap')
require(sets[0]==set(d.REAL_TRAIN_IDS),'original32 changed')
excluded=set(ex['public_parent_ids']+ex['ancestor_ids']+ex['aliases'])|set(d.REAL_EVAL_IDS)|{r['task_id'] for r in d.DEVELOPMENT_SOURCES.values()}
require(not set.union(*sets)&excluded,'explicit excluded identity selected')
for prefix,parent in [('ttt_dev_ids','dev_ids'),('ttt_holdout_ids','holdout_ids')]:
    require(len(replay[prefix])==8 and set(replay[prefix])<=set(replay[parent]),'fixed8 subset scope')
report={'status':'PASS_METADATA_ONLY','approved_for_content_admission':True,'training_tasks_read':0,'evaluator_files_read':0,
        'public_test_gold_read':0,'public_solver_parents':120,'public_test_inputs':167,'known_variant_groups':len(variants),
        'panels':{k:len(replay[k]) for k in ('train_ids','dev_ids','holdout_ids','ttt_dev_ids','ttt_holdout_ids')},
        'exclusions_sha256':sha(panel/'public120-exclusions.json'),'frozen_plan_sha256':sha(panel/'frozen-panel-plan.json'),
        'plan_sha256':replay['plan_sha256'],'qualification':'Content/variant collision checks against actual training bytes remain runtime admission; no semantic or pretraining-cleanliness claim.'}
(ROOT/'runtime-review/panel-metadata-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
