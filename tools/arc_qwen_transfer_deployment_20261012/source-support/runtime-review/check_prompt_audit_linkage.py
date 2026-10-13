"""Independent linkage/content-shape review of existing tokenizer-only receipt.

Does not rerun tokenizer counts and does not load neural code or evaluation gold.
"""
import ast,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_public_research_20261010.public_data import load_solver_tasks
from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def clazz(path,name):
    tree=ast.parse(path.read_text());return ast.dump(next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name),include_attributes=False)
p=ROOT/'prompt-audit/PUBLIC-PROMPT-AUDIT.json';a=json.loads(p.read_bytes())
require(sha(p)=='ffa990d0e4addaa9f00b60460a2c339eb1c6212b91c92f4854af90eb8046d6b4','audit identity')
for name,pin in a['tokenizer_files'].items():require(sha(ROOT/'worktree/materials/qwen14b/hf-overlay'/name)==pin,'tokenizer file changed:'+name)
for rel,pin in a['source_files'].items():
    if rel.endswith('/decoder.py'):
        prior=ROOT/'runtime-review/frozen-worktree-v2'/rel
        require(sha(prior)==pin,'audited decoder bytes unavailable')
        require(clazz(prior,'TransferPromptContract')==clazz(ROOT/'worktree'/rel,'TransferPromptContract'),'native prompt contract changed')
    else:require(sha(ROOT/'worktree'/rel)==pin,'packing source changed:'+rel)
loaded=load_solver_tasks((ROOT/'materials/public120-solver/solver').absolute(),'549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f')
expected=[]
for parent,queries in sorted(loaded['query_inputs'].items()):
    for index,q in enumerate(queries):
        for op in (0,1):expected.append((parent,index,op))
require([(r['parent_id'],r['test_index'],r['transform_d4']) for r in a['rows']]==expected,'exact334 orderedqueryview coverage')
for r in a['rows']:
    task=loaded['demos_tasks'][r['parent_id']];query=loaded['query_inputs'][r['parent_id']][r['test_index']]
    q=Transform(r['transform_d4']).apply(query)
    require(r['query_shape']==[len(q),len(q[0])],'transformedshape')
    n=len(task['demos']);selected=[int(i) for i in r['selected_demo_ids']]
    require(selected and selected==sorted(set(selected)) and all(0<=i<n for i in selected),'invalid complete-demo selection')
    require(r['omitted_demo_ids']==[str(i) for i in range(n) if i not in selected],'omission coverage')
    require(r['admitted'] is True and 0<r['prompt_tokens']<=3072,'admission bounds')
require(max(r['prompt_tokens'] for r in a['rows'])==a['maximum_prompt_tokens']==3069,'maximumcount')
require(sum(bool(r['omitted_demo_ids']) for r in a['rows'])==a['demos_omitted_views']==90,'omittedviewcount')
report={'status':'PASS_LINKAGE_AND_COVERAGE','audit_sha256':sha(p),'ordered_views':334,'public_tasks':120,'query_inputs':167,
        'actual_tokenizer_count_reexecuted':False,'tokenizer_and_packing_source_pins_verified':True,
        'native_prompt_contract_ast_unchanged_after_tiny_calibration_only_edit':True,
        'claimed_max_prompt_tokens':3069,'claimed_admitted_views':334,'claimed_omitted_demo_views':90,
        'gold_files_opened':0,'model_calls':0,'qualification':'Verifies exact asset/code linkage and334 row identities; original32s tokenizer execution supplies token counts. Does not establish GPUfit or accuracy.'}
(ROOT/'runtime-review/prompt-audit-linkage-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
