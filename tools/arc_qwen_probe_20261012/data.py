"""Six source-authored train families with target-free query prompt construction."""
from __future__ import annotations
from copy import deepcopy
import time
from pathlib import Path
from .protocol import PROTOCOL, require, digest, checked_json
from tools.arc_learning_agent_20261011.data import create_split_manifest,build_records,verified_program_record,validate_records
from tools.arc_learning_agent_20261011.grid_codec import grid_messages,program_messages,encode_grid,validate_grid
from tools.arc_learning_agent_20261011.program_tools import verify_program,execute_queries
from tools.arc_learning_agent_20261011.budget import atomic_json

PROGRAMS={
 'identity':'def transform(grid):\n    return grid',
 'reverse-columns':'def transform(grid):\n    return [row[::-1] for row in grid]',
 'transpose':'def transform(grid):\n    return [[grid[r][c] for r in range(len(grid))] for c in range(len(grid[0]))]',
 'reverse-rows':'def transform(grid):\n    return grid[::-1]',
 'recolor-one-two':'def transform(grid):\n    return [[2 if x == 1 else x for x in row] for row in grid]',
 'repeat-columns':'def transform(grid):\n    return [[x for x in row for repeat in range(2)] for row in grid]',
}

def reference(family,grid):
    """Authored formulas only, never generated source or host exec."""
    if family=='identity': return deepcopy(grid)
    if family=='reverse-columns': return [list(reversed(r)) for r in grid]
    if family=='transpose': return [list(row) for row in zip(*grid)]
    if family=='reverse-rows': return deepcopy(list(reversed(grid)))
    if family=='recolor-one-two': return [[2 if c==1 else c for c in row] for row in grid]
    if family=='repeat-columns': return [[c for c in row for _ in range(2)] for row in grid]
    raise ValueError('unknown authored family')

def authored_specs():
    grids=[[[1,2],[3,4]],[[0,5,6]],[[7],[1],[8]],[[9,1,0],[2,3,5]]]
    query=[[5,6,7,1],[8,9,0,4],[1,3,2,6]]
    return {f:{'train':[{'input':deepcopy(g),'output':reference(f,g)} for g in grids],
               'query':deepcopy(query),'target':reference(f,query)} for f in PROTOCOL['train_families']}

DEVELOPMENT_SHA256='18c9a0877aa0c093e7177c1e11f41c01c5ac2356833efa2d99c2110869e8b7e3'
DEVELOPMENT_SOURCES={'training-dev:b1948b0a': {'ancestor_ids': ['b1948b0a'], 'held_out_demo_index': 2, 'kind': 'exact-split-manifest', 'parent_ids': ['b1948b0a'], 'split': 'dev', 'task_id': 'b1948b0a', 'task_sha256': '8607a930c28150f561c29f3f469cef7a684b0a990f39f408aa340ff7f880c2f4', 'visible_demo_indices': [0, 1]}, 'training-dev:e9c9d9a1': {'ancestor_ids': ['e9c9d9a1'], 'held_out_demo_index': 2, 'kind': 'exact-split-manifest', 'parent_ids': ['e9c9d9a1'], 'split': 'dev', 'task_id': 'e9c9d9a1', 'task_sha256': '4be0fee59cf725f0dac82f6d3bc1e2fb3838d72fc13c1b56ace261d4dd651fb3', 'visible_demo_indices': [0, 1]}, 'training-dev:53b68214': {'ancestor_ids': ['53b68214'], 'held_out_demo_index': 2, 'kind': 'exact-split-manifest', 'parent_ids': ['53b68214'], 'split': 'dev', 'task_id': '53b68214', 'task_sha256': 'e64843bee893afd160ee1e2b0d15192b06b10a39143414c1b19e31041e73b484', 'visible_demo_indices': [0, 1]}, 'training-dev:cce03e0d': {'ancestor_ids': ['cce03e0d'], 'held_out_demo_index': 2, 'kind': 'exact-split-manifest', 'parent_ids': ['cce03e0d'], 'split': 'dev', 'task_id': 'cce03e0d', 'task_sha256': 'fd109521292be36bdcbdcb6c204363ee79dc59fdb8524a9f69c5f66ad49e700a', 'visible_demo_indices': [0, 1]}}

def load_development(config):
    if config.get('training_root'):
        from tools.arc_next_materials import groups,sanitize_source
        from tools.arc_next_models import digest as legacy_digest
        from .protocol import file_sha
        import json
        inventory_path=Path(__file__).resolve().parents[2]/'research/arc-next-line/training-source-inventory.json'
        require(file_sha(inventory_path)=='53fc35f54fa1b8a29403c5ede3e3880e8588c40c75a4a5783692a9a13a3e95cb','official training inventory differs')
        inventory=json.loads(inventory_path.read_bytes());fixed=groups(inventory,training_count=800,development_count=200)
        root=Path(config['training_root']).absolute()
        require(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),'regular training root required')
        entries={Path(e['path']).stem:e for e in inventory['files']}
        require({p.name for p in root.iterdir()}=={k+'.json' for k in entries},'closed1000-task training inventory required')
        cases=[]
        for case_id,source in DEVELOPMENT_SOURCES.items():
            key=source['task_id'];require(key in fixed['development_ids'],'exposed case outside official dev split')
            path=root/(key+'.json');require(path.is_file() and not path.is_symlink() and path.stat().st_size<=1024**2,'bounded official task required')
            task,_=sanitize_source(path.read_bytes(),entries[key])
            require(legacy_digest(task)==source['task_sha256'],'fixed development task content differs')
            demos=task['train'];cases.append({'case_id':case_id,'source':deepcopy(source),'demos':demos[:-1],'query_input':demos[-1]['input'],'target':demos[-1]['output']})
        panel={'format':'irisx/qwen14b-exposed-development-v1','exposure':'previously-exposed-v9-development','public_answers_used':False,'source_panel_sha256':'dc681c6c82c848bbaa362b7f179ef5bd1d9796e31addb246bd03b0044570c712','cases':cases}
        require(digest(panel)==DEVELOPMENT_SHA256,'reconstructed exact exposed panel differs')
    else:
        require(config.get('tiny_cpu') is True,'production needs independently pinned official training mount')
        require(config['development_panel_sha256']==DEVELOPMENT_SHA256,'fixed development panel digest differs')
        panel=checked_json(config['development_panel_path'],DEVELOPMENT_SHA256)
    require(panel['cases'] and [c['case_id'] for c in panel['cases']]==list(DEVELOPMENT_SOURCES),'fixed exposed case ordering differs')
    return panel

def build_dataset(development,output,deadline,ledger):
    """Only the six authored train parents can enter either optimizer branch."""
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    specs=authored_specs(); tasks={};families={};fixed={'train':[],'dev':[]}
    for f,s in specs.items():
        key='probe-authored:'+f; tasks[key]={'train':s['train']};families[key]=key;fixed['train'].append(key)
    for c in development['cases']:
        key='probe-exposed:'+c['case_id'];tasks[key]={'train':deepcopy(c['demos'])+[{'input':c['query_input'],'output':c['target']}]}
        families[key]=key;fixed['dev'].append(key)
    manifest=create_split_manifest(tasks,family_ids=families,fixed_splits=fixed)
    require(all(manifest['tasks'][k]['split']=='train' for k in fixed['train']),'authored training family collided with exposed dev lineage')
    records=[r for r in build_records(tasks,manifest,augmentations=1,seed=PROTOCOL['seed']) if r['split']=='train']
    proofs=[];cases=[]
    for f,s in specs.items():
        key='probe-authored:'+f;require(time.monotonic()<deadline,'dataset verifier deadline')
        from .experiment import _vm
        proof=_vm(ledger,'reference-'+f+'-demos',lambda:verify_program(PROGRAMS[f],s['train'],out/'reference-vm',f+'-demos',deadline=deadline))
        require(proof['all_demos_fit'],'authored witness failed real bounded VM: '+f)
        query=_vm(ledger,'reference-'+f+'-query',lambda:execute_queries(proof,[s['query']],out/'reference-vm',f+'-query',deadline=deadline))
        require(query['results'][0]['output']==s['target'],'authored formula and bounded VM disagree: '+f)
        # Known training query appears as input only; no evaluation target enters this record.
        task={'train':deepcopy(s['train']),'test':[{'input':deepcopy(s['train'][0]['input'])}]}
        record=verified_program_record(key,task,PROGRAMS[f],proof,manifest)
        records.append(record);proofs.append({'family':f,'proof':proof,'query':query})
        cases.append({'case_id':'train-control:'+f,'scope':'authored_train_control','family':f,
            'demos':deepcopy(s['train'][1:]),'query_input':deepcopy(s['train'][0]['input']),
            'target':deepcopy(s['train'][0]['output']),'program_reference':PROGRAMS[f]})
        cases.append({'case_id':'authored-disjoint:'+f,'scope':'authored_disjoint_query','family':f,
            'demos':deepcopy(s['train']),'query_input':deepcopy(s['query']),
            'target':deepcopy(s['target']),'program_reference':PROGRAMS[f]})
    for c in development['cases']: cases.append({**deepcopy(c),'scope':'exposed_development','family':None,'program_reference':None})
    admission=validate_records(records,manifest,())
    require(all(r['split']=='train' and r['task_id'] in fixed['train'] for r in records),'only authored train lineage admitted')
    train_queries={digest(p['input']) for s in specs.values() for p in s['train']}
    require(all(digest(s['query']) not in train_queries for s in specs.values()),'authored query input overlaps any train input')
    result={'format':'irisx/qwen14b-probe-dataset-v1','manifest':manifest,'records':records,'cases':cases,
        'admission':admission,'reference_proofs':proofs,'denominators':{'authored_train_control':6,'authored_disjoint_query':6,'exposed_development':4},
        'record_counts':{'grid':24,'program':6},'public_answers_used':False,
        'confirmation_targets_used':False,'authored_queries_are_same_family':True}
    atomic_json(out/'dataset.json',result,exclusive=True)
    return result
