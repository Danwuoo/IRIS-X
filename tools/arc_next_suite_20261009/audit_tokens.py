"""Exact pinned tokenizer audit. Visible challenges only; no query gold/weights."""
from pathlib import Path
import os,sys,importlib.metadata,json,hashlib
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'src'))
import arc_suite as s
from transformers import AutoTokenizer
assets=Path(sys.argv[1]).resolve()
assert s.file_sha(assets/'irisx-model-material.json')==s.EXPECTED_PINS['model']['manifest_sha256']
material=s.read(assets/'irisx-model-material.json');files={r['path']:r for r in material['files']};used=('tokenizer.json','tokenizer_config.json','chat_template.jinja','special_tokens_map.json')
for name in used:assert s.file_sha(assets/name)==files[name]['sha256']
versions={n:importlib.metadata.version(n) for n in ('transformers','tokenizers','Jinja2')}
assert versions=={'transformers':'5.8.1','tokenizers':'0.22.2','Jinja2':'3.1.6'}
t=AutoTokenizer.from_pretrained(str(assets),local_files_only=True,trust_remote_code=False)
assert s.digest(t.get_vocab())=='bba08239637b434c5ce2d7aa763b0b83abe14efc2b948c579d45d7e114740c76'
original=s.read(ROOT/'src/solver-manifest-reference.json');ch=s.read(ROOT/'src/solver-challenges-reference.json')
policies=['direct_grid','detailed_contract','host_toolbox','host_python','typed_ir','proposal_pool','generic_static','precise_static','raw_grid','raw_plus_objects','redacted_demo','true_demo','independent_roots','best_first_memory']
prompts={};tasks=original['core']['tuning_ids'][:40]
for tid in tasks:
 assert s.digest(s.task(ch[tid]))==original['challenge_sha256'][tid]
 prompts[tid]={}
 for policy in policies:
  r=s.render_initial(ch[tid],policy,t)
  prompts[tid][policy]={k:r[k] for k in ('prompt_tokens','input_token_ids_sha256','rendered_text_sha256','messages_sha256')}
  prompts[tid][policy].update(challenge_sha256=s.digest(ch[tid]),context_excluded=r['prompt_tokens']>6144)
summary={p:{'engineering8_min':min(prompts[x][p]['prompt_tokens'] for x in tasks[:8]),'engineering8_max':max(prompts[x][p]['prompt_tokens'] for x in tasks[:8]),'engineering8_excluded':[x for x in tasks[:8] if prompts[x][p]['context_excluded']], 'consolidation32_min':min(prompts[x][p]['prompt_tokens'] for x in tasks[8:40]),'consolidation32_max':max(prompts[x][p]['prompt_tokens'] for x in tasks[8:40]),'consolidation32_excluded':[x for x in tasks[8:40] if prompts[x][p]['context_excluded']]} for p in policies}
audit={'format':'irisx/nextphase-visible-token-audit-v1','gold_read':False,'weights_loaded':False,'gpu_used':False,'versions':versions,
       'base_manifest_sha256':s.EXPECTED_PINS['model']['manifest_sha256'],'tokenizer_files':{n:files[n] for n in used},'prompts':prompts,'summary':summary,
       'max_prompt_tokens':6144,'max_new_tokens':2048,'max_context_tokens':8192,'overflow_policy':'Retain exact raw tasks; exclude oversize prompts from fixed denominators, never drop or truncate task.'}
(ROOT/'src/visible-token-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(summary,indent=2))
