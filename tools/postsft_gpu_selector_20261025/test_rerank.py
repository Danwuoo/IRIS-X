import copy
import json
from pathlib import Path
from rerank_candidates import select

def c(i,g,lp=-1.,eos=True,truncated=False):
    return {'draw_id':str(i),'view_id':'canonical','grid':g,'finished_eos':eos,
            'truncated':truncated,'sampled_logps':[lp,-0.1]}
p={'schema':'iris-fixed-candidate-pool/v1','pool_id':'synthetic-no-gold',
   'policy_sha256':'a'*64,'decoder_contract_sha256':'b'*64,
   'candidates':[c(0,[[1]],-.1),c(1,[[2]],-2),c(2,[[2]],-2),c(3,[[3]],-3,truncated=True)]}
assert select(p,'first')['selected'][0]['grid']==[[1]]
assert select(p,'vote')['selected'][0]['grid']==[[2]]
assert select(p,'mean_logp')['selected'][0]['grid']==[[1]]
r=select(p);assert (r['draws'],r['invalid_or_truncated_draws'],r['unique_valid_grids'],r['duplicate_valid_draws'])==(4,1,2,1)
assert r['oracle_score'] is None and not r['semantic_correctness_verified'] and r['new_model_calls']==0
q=copy.deepcopy(p);q['query_gold']=[[2]]
try: select(q); raise AssertionError('accepted gold')
except ValueError: pass
q=copy.deepcopy(p);q['candidates'][0]['reward']=1
try: select(q); raise AssertionError('accepted reward')
except ValueError: pass
q=copy.deepcopy(p);q['candidates'][1]['draw_id']='0'
try: select(q); raise AssertionError('accepted duplicate ID')
except ValueError: pass
q=copy.deepcopy(p);q['candidates'][0]['sampled_logps']=[float('nan')]
try: select(q); raise AssertionError('accepted NaN')
except ValueError: pass
q=copy.deepcopy(p);q['candidates']=[c(0,[[1],[2,3]])]
assert select(q)['selected']==[]
q=copy.deepcopy(p);q['candidates']=[c(0,[[2]]),c(1,[[1]])]
assert select(q,'vote')['selected'][0]['grid']==[[2]]
q=copy.deepcopy(p);q['candidates']=[c(0,[[2]],eos=False)]
assert select(q)['selected']==[]
try: select(p, slots=True); raise AssertionError('accepted boolean slots')
except ValueError: pass
Path(__file__).with_name('RERANK-CPU-RESULT.json').write_text(json.dumps({'passed':True,'synthetic_fixtures_only':True,'GPU_or_model_calls':0,'query_gold_read':False,'tested':['first/vote/logp ordering','draws vs unique and invalid accounting','unknown gold/reward field rejection','duplicate ID rejection','nonfinite logprob rejection','nonrectangular grid exclusion','stable ties','missingEOS exclusion','boolean slots rejected']},indent=2)+'\n')
print('PASS: fixed-pool CPU selectors; no model or gold')
