"""Offline immutable full-input candidate for Decision 0059. No provider IO."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.nvarc_native_multitask import canonical,digest,write,require
from tools.nvarc_official_render import worker,bridge

FROZEN=ROOT/'.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-010/package-l4'
FROZEN_NOTEBOOK_SHA='0d1e82b8310b70e1633a0f4728fc4d4dce3fea7a636c08088def22b2e7f2cb6e'
FILES={'solver.py':'solver','arc_loader.py':'loader','arc_decoder.py':'decoder','inspection.py':'worker',
    'inspection_helpers.py':'helper','nvarc_native_ttt_budget.py':'budget','nvarc_native_ttt_schedule.py':'schedule',
    'hardware_helpers.py':'hardware','tools/arc_kaggle_submission.py':'exporter',
    'tools/nvarc_native_solve_runtime.py':'solve_runtime','tools/nvarc_native_multitask.py':'multitask',
    'tools/nvarc_native_submission.py':'bridge','tools/nvarc_native_export.py':'native_export',
    'tools/nvarc_official_adapter.py':'official_adapter','tools/nvarc_official_parent.py':'official_parent'}
PRODUCERS=('worker','helper','budget','schedule','solve_runtime','multitask','bridge','exporter')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_payloads():
    notebook=FROZEN/'kernel/notebook.ipynb'
    require(sha(notebook)==FROZEN_NOTEBOOK_SHA,'immutable saved native 010 notebook differs')
    source=''.join(json.loads(notebook.read_bytes())['cells'][0]['source'])
    values={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            name=node.targets[0].id
            if name in ('PAYLOADS','HASHES'):values[name]=ast.literal_eval(node.value)
    require(set(values)=={'PAYLOADS','HASHES'},'frozen exact payload envelope required')
    raw={k:base64.b64decode(v,validate=True) for k,v in values['PAYLOADS'].items()}
    require({k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}==values['HASHES'],'frozen native 010 payload differs')
    return raw


def construct(run_id, source_commit):
    require(re.fullmatch(r'nvarc-stage3-official-\d{3}',run_id),'distinct official candidate identity required')
    require(re.fullmatch(r'[0-9a-f]{40}',source_commit),'full source commit required')
    old=frozen_payloads();previous=json.loads(old['plan'])
    keys=set(FILES.values())-{'official_adapter','official_parent'}|{'source_inventory','model_inventory'}
    raw={key:old[key] for key in keys}
    raw['worker']=worker(raw['worker']);raw['bridge']=bridge(raw['bridge'])
    for key,name in [('official_adapter','nvarc_official_adapter.py'),('official_parent','nvarc_official_parent.py')]:
        raw[key]=(ROOT/'tools'/name).read_bytes()
    keep=('format','model_material_digest','versions','original_peft_parameters','original_training_arguments',
          'native_trainer_origins','native_checkpoint_flags','source_inferred_trainable_layout',
          'original_class_ast_sha256','solver_cell_sha256','source_inventory_digest','original_solve_source_sha256',
          'model_instance_version_id','dependency_script_version_id','docker_image','model_sources','competition_sources')
    candidate={key:previous[key] for key in keep}
    producers={key:hashlib.sha256(raw[key]).hexdigest() for key in PRODUCERS}
    candidate.update(run_id=run_id,kernel_id='danielwuu/'+run_id,source_commit=source_commit,
        approved=True,agent_execution_authorized=True,official_score_scope=True,
        controller_admission={'format':'irisx/stage3-official-cli-owner-authority-v1','decision':'0059',
            'owner_chat_id':'01a105f2-1643-74e0-845e-d31b426efb50',
            'owner_message_refs':['01a107db-1e37-7c82-aa63-24648f564e5e','01a107dd-3dbe-7760-9384-3db4e772d555'],
            'controller_acceptance_sha256':'272bedc7c3eea981ed3dc587bca2afb2e5e0d9b9c1d62e102999ea2b30208105',
            'maximum_formal_submissions':1,'paid_usd':0,'stage4':False},
        producer_files=producers,producer_sha256=digest(producers),native_source_learning_rates=previous['task_specs']['44f52bb0']['source_learning_rates'],
        runtime_input_policy='read all mounted arc-agi_test_challenges.json; never embed preview tasks or answers',
        parallel_workers=4,selected_gpu_indices=[0,1,2,3],pythonhashseed=0,
        maximum_paid_usd=0,maximum_teacher_calls=0,maximum_notebook_wall_seconds=42600,
        initial_preparation_seconds=600,packaging_reserve_seconds=1800,maximum_export_process_seconds=1800,
        export_verification_process='fresh-cpu-startup-hashseed-0',export_helper_sha256=hashlib.sha256(raw['native_export']).hexdigest(),
        kernel_execution_type='SAVE_AND_RUN',owner_editor_only=False,maximum_formal_submissions=1,
        resource_information_status='unavailable',reserved_quota_hours=None,quota_observed_at=None,
        quota_reservation_id=None,prior_sessions_reconciled=None,owner_editor_sessions_closed=None,
        resource_sufficiency_verified=False,strict_portable_gpu_gate=False,correctness_scored=False,
        method_deviations=['four fresh independent task processes on four L4s',
            'LPT public-cost ordering instead of original task ordering',
            'finite 180-second clock per actual test, four native view batches per test',
            'bounded 4096 generation/128 verifier forwards and 5 MiB physical inference tokens per test',
            'fresh seed-0 strict CPU export; no cross-version portability claim'],
        frozen_probe_run='nvarc-original-qwen3-native-multitask-010',
        frozen_probe_plan_digest=digest(previous))
    raw['candidate']=canonical(candidate)
    source="""import base64,hashlib,json,sys,time
from pathlib import Path
"""+'PAYLOADS='+repr({k:base64.b64encode(v).decode() for k,v in raw.items()})+'\n'
    source+='HASHES='+repr({k:hashlib.sha256(v).hexdigest() for k,v in raw.items()})+'\n'
    source+='FILES='+repr(FILES)+'\n'
    source+="""START=time.monotonic()
raw={k:base64.b64decode(v,validate=True) for k,v in PAYLOADS.items()}
if {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}!=HASHES:
    raise RuntimeError('exact official candidate payload differs')
candidate=json.loads(raw['candidate'])
if candidate['approved'] is not True or candidate['official_score_scope'] is not True:
    raise RuntimeError('explicit single official score authority required')
work=Path('/kaggle/working')/candidate['run_id'];work.mkdir(exist_ok=False)
for name,key in FILES.items():
    path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw[key])
(work/'tools/__init__.py').write_bytes(b'')
(work/'candidate-plan.json').write_bytes(raw['candidate'])
(work/'payload-bindings.json').write_text(json.dumps(HASHES,sort_keys=True),encoding='utf-8')
sys.path.insert(0,str(work))
from tools.nvarc_official_parent import execute
summary=execute(work,candidate,raw,START)
print(json.dumps({'export_complete':True,'task_count':summary['output_counts']['task_count'],
    'test_count':summary['output_counts']['test_output_count'],'strict_portable_gpu_gate':False}))
"""
    compile(source,'official-notebook','exec')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.splitlines(keepends=True)}]}
    metadata=json.loads((FROZEN/'kernel/kernel-metadata.json').read_bytes())
    metadata.update(id=candidate['kernel_id'],title=run_id,docker_image_pinning_type='original',machine_shape='NvidiaL4')
    return candidate,raw,notebook,metadata


def stage(package,run_id,source_commit):
    require(not package.exists(),'new immutable official package directory required')
    retained=(ROOT/'.irisx/nvarc-original/runs').glob('nvarc-stage3-official-*/package-*/candidate-plan.json')
    require(not any(json.loads(p.read_bytes())['run_id']==run_id for p in retained),
            'retained official candidate identity cannot be restaged')
    candidate,raw,notebook,metadata=construct(run_id,source_commit)
    (package/'kernel').mkdir(parents=True)
    write(package/'candidate-plan.json',candidate);write(package/'kernel/notebook.ipynb',notebook)
    write(package/'kernel/kernel-metadata.json',metadata)
    wire=json.loads(canonical(notebook))
    for cell in wire['cells']:
        if cell['cell_type']=='code':cell['outputs']=[]
        if isinstance(cell['source'],list):cell['source']=''.join(cell['source'])
    write(package/'manifest.json',{'run_id':run_id,'candidate_digest':digest(candidate),
        'cli_wire_script_sha256':hashlib.sha256(json.dumps(wire).encode()).hexdigest(),
        'payload_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
        'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    require(not package.is_symlink() and not any(p.is_symlink() for p in package.rglob('*')),'regular immutable package required')
    saved=json.loads((package/'candidate-plan.json').read_bytes())
    candidate,raw,notebook,metadata=construct(saved['run_id'],saved['source_commit'])
    manifest=json.loads((package/'manifest.json').read_bytes())
    wire=json.loads(canonical(notebook))
    for cell in wire['cells']:
        if cell['cell_type']=='code':cell['outputs']=[]
        if isinstance(cell['source'],list):cell['source']=''.join(cell['source'])
    require(saved==candidate and json.loads((package/'kernel/notebook.ipynb').read_bytes())==notebook and
        json.loads((package/'kernel/kernel-metadata.json').read_bytes())==metadata and
        manifest=={'run_id':saved['run_id'],'candidate_digest':digest(candidate),
            'cli_wire_script_sha256':hashlib.sha256(json.dumps(wire).encode()).hexdigest(),
            'payload_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
            'inventory':{p.relative_to(package).as_posix():sha(p) for p in package.rglob('*') if p.is_file() and p.name!='manifest.json'}},
        'exact closed official package differs')
    return {'candidate_digest':digest(candidate),'run_id':saved['run_id'],'offline_package_verified':True,
            'official_score':None,'strict_portable_gpu_gate':False,'external_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['stage','preflight']);parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--run-id');parser.add_argument('--source-commit')
    args=parser.parse_args()
    result=stage(args.package,args.run_id,args.source_commit) if args.action=='stage' else preflight(args.package)
    print(json.dumps(result))


if __name__=='__main__':main()
