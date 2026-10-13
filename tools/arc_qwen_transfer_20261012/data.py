"""Pinned metadata split before source reads; demonstration-only native records.

Held-out answers are written to an escrow file, never retained in solver cases,
Trainer manifests or checkpoint provenance. Production excludes old panels and
independently bound PUBLIC120 ancestry/known variants without substitutions.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha1, sha256
import json
from pathlib import Path
from .protocol import PROTOCOL, require, digest, checked_json, file_sha
from . import arc_adaptation as aa
from tools.arc_qwen_portfolio_20261012.panel_contract import REAL_TRAIN_IDS, REAL_EVAL_IDS, INVENTORY_SHA256, inventory_path
from tools.arc_qwen_probe_20261012.data import DEVELOPMENT_SOURCES
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.grid_codec import grid_messages, encode_grid
from tools.arc_learning_agent_20261011.data import create_split_manifest, validate_records, _seal_record
from tools.arc_next_models import digest as native_digest
from src.irisx.arc_nvarc_data import known_variant_group, transform_grid

PUBLIC_EXCLUSIONS_SHA256='ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e'
EXCLUSION_FIELDS={'format','source','public_parent_ids','ancestor_ids','aliases','known_variant_groups'}


def load_inventory():
    raw=checked_json(inventory_path(),INVENTORY_SHA256)
    entries=tuple(aa.SourceEntry(Path(r['path']).stem,r['path'],r['git_blob_sha1'],r['bytes']) for r in raw['files'])
    return aa.SourceInventory(raw['repository'],raw['commit'],entries,aa.inventory_digest(raw['repository'],raw['commit'],entries))


def freeze_panels(inventory, exclusions):
    require(type(exclusions) is dict and set(exclusions)==EXCLUSION_FIELDS,'closed PUBLIC120 exclusion manifest required')
    require(exclusions['format']=='irisx/public120-transfer-exclusions-v1','PUBLIC120 exclusion format')
    require(type(exclusions['source']) is dict,'PUBLIC120 independently bound source required')
    for name in ('solver_manifest_sha256','challenges_sha256'):
        aa._hash(exclusions['source'].get(name),64,'PUBLIC120 '+name)
    for key in EXCLUSION_FIELDS-{'format','source'}:
        require(type(exclusions[key]) is list and all(type(x) is str and x for x in exclusions[key]),'invalid public exclusion values')
    public=tuple(sorted(set(exclusions['public_parent_ids']+exclusions['ancestor_ids']+exclusions['aliases'])))
    require(len(set(exclusions['public_parent_ids']))==120 and public,'full PUBLIC120 parents required')
    rule=aa.Exclusions(REAL_EVAL_IDS,tuple(s['task_id'] for s in DEVELOPMENT_SOURCES.values()),public)
    part=aa.partition_parents(inventory,REAL_TRAIN_IDS,rule,canary_count=16,holdout_count=32,seed=PROTOCOL['split_seed'])
    aa.assert_sprint_contract(part,inventory=inventory,archived_optimizer_ids=REAL_TRAIN_IDS,
        archived_regression_ids=REAL_EVAL_IDS,archived_exposed_ids=rule.old_exposed_ids,
        public120_exclusion_sha256=aa.digest(rule.public120_ids))
    rank=lambda values,purpose: sorted(values,key=lambda k:(digest([PROTOCOL['split_seed'],purpose,k]),k))
    result={'partition':part.to_artifact(),'partition_sha256':part.sha256,
        'train_ids':list(part.optimizer_ids),'dev_ids':list(part.canary_ids),'holdout_ids':list(part.holdout_ids),
        'ttt_dev_ids':rank(part.canary_ids,'ttt-dev')[:8],'ttt_holdout_ids':rank(part.holdout_ids,'ttt-holdout')[:8],
        'exclusions_sha256':digest(exclusions),'metadata_only_before_task_reads':True}
    result['representative_ttt_parent']=result['ttt_dev_ids'][0]
    result['plan_sha256']=digest(result)
    return part,result


def _lists(value):
    return json.loads(json.dumps(value))


def zero_context_messages(query):
    # A one-demo outer fold legitimately leaves a zero-context supervised pair.
    messages=grid_messages([{'input':[[0]],'output':[[0]]}],_lists(query))
    messages[-1]['content']='Query\nInput:\n'+encode_grid(_lists(query))+'\nOutput:'
    return messages


def _transform_spec(transform):
    sample=[[0,1,2],[3,4,5]]
    expected=_lists(transform.apply(sample))
    for rotation in range(4):
        for transpose in (False,True):
            spec={'rotation':rotation,'transpose':transpose,'colors':list(transform.palette)}
            if transform_grid(sample,spec)==expected:return spec
    raise ValueError('D4 native mapping unavailable')


def transforms(seed, count=8):
    require(type(count) is int and 1<=count<=8,'one to eight fixed D4 views')
    return tuple(aa.Transform(i,tuple(range(10)) if i==0 else aa.deterministic_palette(str(seed),i)) for i in range(count))


def _native_record(record,task_id,family_id,source_sha):
    demos=_lists([asdict(e) for e in record.prompt.examples]); query=_lists(record.prompt.query_input)
    result={'task_id':task_id,'split':'train','parent_ids':[task_id],'family_id':family_id,'kind':'grid',
        'messages':grid_messages(demos,query) if demos else zero_context_messages(query),
        'completion':encode_grid(_lists(record.target)),
        'provenance':{'objective':'demo-only-lodo','held_out_demo':record.withheld_demo_index,
            'visible_demo_indices':list(record.context_demo_indices),'augmentation':_transform_spec(record.transform),
            'augmentation_index':record.transform.d4,'source_task_sha256':source_sha,
            'transfer_record':record.to_artifact(),'transfer_record_sha256':record.sha256}}
    return _seal_record(result)


def _local_task(task_id,demos):
    # Local evidence identity only; official provenance remains in the case binding.
    raw={'train':deepcopy(demos)}; blob=aa.canonical_json(raw).encode('ascii')
    key=sha256(task_id.encode()).hexdigest()[:8]
    entry=aa.SourceEntry(key,'data/training/'+key+'.json',sha1(f'blob {len(blob)}\0'.encode()+blob).hexdigest(),len(blob))
    inv=aa.SourceInventory('task-local-demonstrations','0'*40,(entry,),aa.inventory_digest('task-local-demonstrations','0'*40,(entry,)))
    return aa.project_source_bytes(blob,inv,key)


def build_task_records(task_id,demos,*,augmentations=8,seed=0):
    require(type(task_id) is str and task_id,'task identity required')
    task=_local_task(task_id,demos)
    typed=aa.loo_records(task,transforms=transforms(seed,augmentations),purpose='ttt')
    records=[_native_record(r,task_id,'task-local:'+task_id,native_digest({'train':demos})) for r in typed]
    validate_task_records(records,task_id)
    return records


def validate_task_records(records,task_id):
    require(type(records) is list and records,'nonempty typed task records required')
    sources=set()
    for row in records:
        require(row.get('task_id')==task_id and row.get('parent_ids')==[task_id] and row.get('split')=='train','task record scope differs')
        require(row.get('record_id')==native_digest({k:v for k,v in row.items() if k!='record_id'}),'task record digest differs')
        art=row['provenance']['transfer_record']; lineage=aa.Lineage(**art['lineage'])
        prompt=aa.Prompt(tuple(aa.Example(**p) for p in art['prompt']['examples']),art['prompt']['query_input'])
        record=aa.SupervisedRecord(lineage,prompt,art['target'],art['withheld_demo_index'],tuple(art['context_demo_indices']),
            art['demo_count'],aa.Transform(**art['transform']),art['purpose'],art['partition_sha256'])
        require(record.purpose=='ttt' and record.sha256==row['provenance']['transfer_record_sha256'],'task record lineage differs')
        reconstructed=_native_record(record,task_id,'task-local:'+task_id,row['provenance']['source_task_sha256'])
        require(reconstructed==row,'task native prompt/target differs from typed source')
        sources.add(lineage.projection_sha256)
    require(len(sources)==1,'mixed task demonstration sources')
    return {'records_sha256':native_digest(records),'records':len(records),'source_projection_sha256':next(iter(sources))}


def solver_case(case):
    require(type(case) is dict and set(case)=={'case_id','parent_id','scope','demos','query_input','source'},'closed target-free case required')
    require(case['scope'] in ('dev','holdout'),'unknown panel scope')
    require(type(case['demos']) is list and case['demos'],'visible demos required')
    for demo in case['demos']:
        require(set(demo)=={'input','output'},'demo projection differs');aa.Example(**demo)
    aa.freeze_grid(case['query_input'])
    return deepcopy(case)


def _fixture(inventory):
    tasks={}
    for entry in inventory.entries:
        # Distinct deterministic content prevents false identity/variant collisions.
        cells=list(sha256(entry.task_id.encode()).digest())
        tasks[entry.task_id]={'train':[{'input':[[cells[(i*9+j)%32]%10 for j in range(3)] for _ in range(2)],
            'output':[[cells[(i*9+j+4)%32]%10 for j in range(3)] for _ in range(2)]} for i in range(3)]}
    return tasks


def build_dataset(config,output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False); inventory=load_inventory()
    fixture=config.get('tiny_cpu') is True
    if fixture:
        exclusions={'format':'irisx/public120-transfer-exclusions-v1','source':{'solver_manifest_sha256':'0'*64,'challenges_sha256':'0'*64},
            'public_parent_ids':['f%07x'%i for i in range(120)],'ancestor_ids':[],'aliases':[],'known_variant_groups':[]}
    else:
        require(config['public_exclusions_sha256']==PUBLIC_EXCLUSIONS_SHA256,'unreviewed PUBLIC120 exclusion pin')
        exclusions=checked_json(config['public_exclusions_path'],PUBLIC_EXCLUSIONS_SHA256)
    partition,plan=freeze_panels(inventory,exclusions)
    atomic_json(root/'frozen-plan.json',plan,exclusive=True)
    atomic_json(root/'source-inventory.json',inventory.to_artifact(),exclusive=True)
    selected=plan['train_ids']+plan['dev_ids']+plan['holdout_ids'];tasks={};typed={};receipts={}
    fixtures=_fixture(inventory) if fixture else None
    if not fixture:
        source=Path(config['training_root']).absolute()
        require(source.is_dir() and not any(p.is_symlink() for p in (source,*source.parents)),'regular source root required')
        require({p.name for p in source.iterdir()}=={e.task_id+'.json' for e in inventory.entries},'closed1000 source inventory required')
    old_ids=sorted(set(REAL_EVAL_IDS)|{r['task_id'] for r in DEVELOPMENT_SOURCES.values()})
    for key in selected+old_ids:
        if fixture:
            task=aa.project_demonstrations(fixtures[key],inventory,key)
        else:
            path=source/(key+'.json');require(path.is_file() and not path.is_symlink() and path.stat().st_size<=1024**2,'regular source file')
            task=aa.project_source_bytes(path.read_bytes(),inventory,key)
            receipts[key]={'git_blob_sha1':inventory.entry(key).git_blob_sha1,'bytes':path.stat().st_size,'sha256':file_sha(path)}
        typed[key]=task;tasks[key]={'train':_lists([asdict(e) for e in task.demos])}
    # Check variants only after metadata freeze. A collision fails this exact panel;
    # there is never a content/outcome-based replacement selection.
    seen={}; public_variants=set(exclusions['known_variant_groups'])
    old_variants={known_variant_group({**tasks[k],'test':[]}) for k in old_ids}
    for key in selected:
        task=tasks[key]
        group=known_variant_group({**task,'test':[]}); require(group not in public_variants,'PUBLIC120 known variant collision')
        require(group not in old_variants,'historically exposed known variant collision')
        scope='train' if key in plan['train_ids'] else 'dev' if key in plan['dev_ids'] else 'holdout'
        require(group not in seen or seen[group]==scope,'cross-partition known variant collision');seen[group]=scope
    cases=[];escrow={};visible={k:v for k,v in tasks.items() if k in plan['train_ids']}
    for scope in ('dev','holdout'):
        for key in plan[scope+'_ids']:
            demos=deepcopy(tasks[key]['train']);require(2<=len(demos)<=11,'fixed evaluation parents need1..10 visible demos; no replacement')
            target=demos.pop();cid=scope+':'+key
            cases.append(solver_case({'case_id':cid,'parent_id':key,'scope':scope,'demos':demos,'query_input':target['input'],
                'source':{'lineage':asdict(typed[key].lineage),'query_source_demo_index':len(demos),'visible_demo_indices':list(range(len(demos)))}}))
            escrow[cid]=target['output'];visible[key]={'train':demos}
    # Global manifest deliberately contains only visible evaluation demonstrations.
    manifest=create_split_manifest(visible,family_ids={k:k for k in visible},seed=PROTOCOL['seed'],
        fixed_splits={'train':plan['train_ids'],'dev':plan['dev_ids']+plan['holdout_ids']},
        source_identity={'kind':'pinned-official-training','partition_sha256':partition.sha256})
    require(set(k for k,v in manifest['tasks'].items() if v['split']=='train')==set(plan['train_ids']),'global32 demotion/identity change forbidden')
    records=[]
    for key in plan['train_ids']:
        for row in aa.loo_records(typed[key],transforms=transforms(PROTOCOL['seed']),purpose='optimizer',partition=partition):
            aa.validate_record(row,typed[key]);records.append(_native_record(row,key,key,manifest['tasks'][key]['task_sha256']))
    validate_records(records,manifest,())
    escrows={}
    for scope in ('dev','holdout'):
        escrow_path=root/(scope+'-target-escrow.json')
        atomic_json(escrow_path,{k:v for k,v in escrow.items() if k.startswith(scope+':')},exclusive=True)
        escrows[scope]={'path':str(escrow_path.absolute()),'sha256':file_sha(escrow_path)}
    dataset={'format':'irisx/true-arc-transfer-dataset-v1','plan':plan,'cases':cases,'records':records,'manifest':manifest,
        'escrow':escrows,'cpu_fixture_only':fixture,
        'source_receipts':receipts,'denominators':{'dev':16,'holdout':32,'ttt_dev':8,'ttt_holdout':8},
        'public_answers_read':False,'original_test_fields_retained':False}
    atomic_json(root/'solver-dataset.json',dataset,exclusive=True)
    return dataset


def open_targets(dataset,scope,seal):
    require(scope in ('dev','holdout'),'target scope')
    require(seal.get('sealed') is True and seal.get('scope')==scope,'matching prediction seal required')
    payload=checked_json(seal['path'],seal['file_sha256'],cap=16*1024**2)
    expected=[c['case_id'] for c in dataset['cases'] if c['scope']==scope]
    require(payload['case_ids']==expected and payload['plan_sha256']==dataset['plan']['plan_sha256'],'sealed case coverage differs')
    targets=checked_json(dataset['escrow'][scope]['path'],dataset['escrow'][scope]['sha256'])
    return {k:targets[k] for k in expected}


def pack_prompt(model,demos,query,*,task_id='packing'):
    """Choose full demonstrations on actual native template/token IDs, target-free."""
    from .prompt_budget import pack_demonstrations
    def messages(items,q):
        plain=[{'input':d['input'],'output':d['output']} for d in items]
        return grid_messages(plain,q) if plain else zero_context_messages(q)
    def render(items,q):
        return model.tokenizer.apply_chat_template(messages(items,q),tokenize=False,add_generation_prompt=True,enable_thinking=False)
    task={'task_id':task_id,'demonstrations':[{'demo_id':str(i),**deepcopy(d)} for i,d in enumerate(demos)],'query_input':deepcopy(query)}
    if not demos:
        msg=zero_context_messages(query);text,ids=model._prompt(msg)
        require(len(ids)<=3072,'zero-context prompt exceeds fixed cap')
        return msg,{'admitted':True,'selected_demo_ids':[],'prompt':text,'prompt_tokens':len(ids),
            'prompt_sha256':digest(text),'zero_context_training_only':True,'partial_grids_or_targets_truncated':False}
    receipt=pack_demonstrations(task,render=render,encode=lambda text:model.tokenizer.encode(text,add_special_tokens=False))
    if not receipt['admitted']:return None,receipt
    indices=[int(i) for i in receipt['selected_demo_ids']]
    msg=grid_messages([demos[i] for i in indices],query);text,ids=model._prompt(msg)
    require(text==receipt['prompt'] and len(ids)==receipt['prompt_tokens'],'native packed prompt IDs differ')
    return msg,receipt


def prepare_record(model,record):
    """Prepare packed native supervision from the immutable verified full LOO row."""
    require(record.get('record_id')==native_digest({k:v for k,v in record.items() if k!='record_id'}),'training row hash differs')
    art=record['provenance']['transfer_record'];lineage=aa.Lineage(**art['lineage'])
    typed=aa.SupervisedRecord(lineage,aa.Prompt(tuple(aa.Example(**e) for e in art['prompt']['examples']),art['prompt']['query_input']),
        art['target'],art['withheld_demo_index'],tuple(art['context_demo_indices']),art['demo_count'],
        aa.Transform(**art['transform']),art['purpose'],art['partition_sha256'])
    require(typed.sha256==record['provenance']['transfer_record_sha256'],'typed training row differs')
    require(_native_record(typed,record['task_id'],record['family_id'],record['provenance']['source_task_sha256'])==record,'native row differs from typed lineage')
    messages,packing=pack_prompt(model,_lists([asdict(e) for e in typed.prompt.examples]),_lists(typed.prompt.query_input),task_id=record['record_id'])
    require(messages is not None,'context: no whole training demonstration fits')
    prepared=model.prepare_completion(messages,record['completion'])
    require(prepared['completion_tokens']<=1024,'completion context: full target exceeds1024; never truncate')
    require(prepared['input_tokens']<=4096,'completion context exceeds4096')
    return prepared
