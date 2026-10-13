"""Model-free owned preparation, followed by the exact installed parent entry."""
from pathlib import Path
import json, os, shutil, sys, time
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import types
def _source_module(name):
    path=HERE/(name+'.py');module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module
_source_module('source_loader')
from source_loader import read_regular,parse,digest,need,clean_path,encoded,source_import_paths
_source_module('launch_notebook')
from launch_notebook import load_file,run_bounded


def resolve(reference,input_root):
    owner,slug,version=reference.split('/')
    base=clean_path(input_root)
    present=[p for p in (base/slug,base/'datasets'/owner/slug) if p.is_dir()]
    need(len(present)==1,'one retained Dataset mount required: '+reference)
    return clean_path(present[0])


def verify_target_free_materials(release,input_root):
    pins=release['material_pins']
    data=resolve(pins['data']['reference'],input_root)
    raw=read_regular(data/'public-data-material.json',2*1024**2)
    need(digest(raw)==pins['data']['manifest_sha256'],'public material metadata pin')
    doc=parse(raw)
    need(doc['format']=='irisx/public120-data-material-v1' and doc['reference']==pins['data']['reference'] and doc['role_manifests']==pins['data']['role_manifests'],'public data role identity')
    # Evaluator path is derived lexically and not statted, resolved or opened.
    training=resolve(pins['training']['reference'],input_root)
    raw=read_regular(training/'manifest.json',2*1024**2)
    need(digest(raw)==pins['training']['manifest_sha256'],'training manifest hash')
    manifest=parse(raw)
    need(manifest['format']=='irisx/learning-training-material-v1' and manifest['reference']==pins['training']['reference'] and manifest['tasks']==1000 and manifest['public_evaluation_files']==0,'clean1000 training material')
    from source_loader import _actual_files,safe_name
    need(len(manifest['files'])<=1100 and sum(v['bytes'] for v in manifest['files'].values())<=32*1024**2,'training inventory limits')
    need(_actual_files(training)==set(manifest['files'])|{'manifest.json'},'exact training inventory')
    for name,row in manifest['files'].items():
        safe_name(name);raw=read_regular(training/name,2*1024**2)
        need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'training file byte pin')
    return data,training


def prepare(request):
    ready=request['ready'];release=request['release'];epoch=request['epoch']
    need(request['format']=='irisx/rlvr-parent-preparation-request-v1' and release['production_admitted'] is True,'reviewed production preparation required')
    need(type(epoch) is int and epoch==request['finalized']['owner_request']['original_epoch'],'single original epoch')
    need(time.time()<epoch+42000-1800,'original setup/closure allowance exhausted')
    source=clean_path(ready['source_root']);baseline=source/'baseline'
    source_import_paths(source)
    from owned_runtime.release import inventory,source_digest,check_production_pins
    policy=source/'design/MEASURED-POLICY.json';environment=source.parent/'release/REVIEWED-ENVIRONMENT.json'
    need(source_digest(inventory())==ready['source_sha256']==release['source_sha256'],'complete source inventory changed')
    check_production_pins(inventory(),policy_path=policy,environment_path=environment)
    from owned_runtime.parent_scoring import worker_environment
    from tools.arc_qwen_transfer_deployment_20261012.bootstrap import resolve_datasets,discover_model,nonmodel_input_roots,prepare_environment
    roots=resolve_datasets(request['input_root'])
    data,training=verify_target_free_materials(release,request['input_root'])
    contract=baseline/'materials/qwen14b/material-contract.json'
    model_root=discover_model(request['input_root'],contract,excluded=nonmodel_input_roots(request['input_root'],release['dataset_references']))
    # Co-resident storage demand is issued by the reviewed source storage planner.
    from owned_runtime.storage import storage_plan,before_session
    storage=storage_plan()
    # Phase-specific source admission; installer separately checks actual /tmp
    # expansion on its backing filesystem. Full caps are descriptive, not free-space demand.
    disk_admission=before_session(Path(request['launcher_root']),fixture=False)
    prepare_request={'environment_root':request['environment_root'],'execution_deadline_epoch':epoch+42000,
        'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'provider_deadline_epoch':epoch+42300,
        'started_epoch':epoch}
    installed=prepare_environment(prepare_request,baseline,roots)
    interpreter_manifest=read_regular(Path(roots['interpreter'])/'interpreter-manifest.json',4*1024**2)
    need(digest(interpreter_manifest)==installed['interpreter']['manifest_sha256'],'installed interpreter manifest lineage')
    (Path(request['launcher_root'])/'interpreter-manifest.json').write_bytes(interpreter_manifest)
    need(time.time()<epoch+42000,'original inner deadline reached during setup')
    from tools.arc_qwen_transfer_20261012.model_profile import MODEL_KEY,PROFILE_ID,DEPLOYMENT_ID,MATERIAL_ADDENDUM_SHA256
    config={'fixture':False,'policy_path':str(policy),'environment_path':str(environment),'training_root':str(training/'data/training'),
        'public_solver_root':str(data/'solver'),'model':{'enabled':True,'model_key':MODEL_KEY,'profile_id':PROFILE_ID,
        'reviewed_deployment_id':DEPLOYMENT_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,
        'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'tensor_parallel_size':1,'precision':'bf16-base-fp32-lora','seed':1917,
        'model_path':model_root,'tokenizer_path':str(contract.parent/'hf-overlay'),'wheel_root_path':roots['wheels'],
        'contract_path':str(contract),'environment_lock_path':str(contract.parent/'environment-lock.json')}}
    expected=parse(read_regular(environment,2*1024**2));need(expected['model_config']==config['model'],'exact reviewed model material paths differ')
    from owned_runtime.public_bridge import EVALUATOR_MANIFEST_SHA256,SCORER_PINS_SHA256
    launcher=Path(request['launcher_root']);owner_raw=read_regular(launcher/'original-request.json',128*1024);owner=parse(owner_raw)
    descriptor={'format':'owned-rl-parent-scorer-material-v1','scope':'production-rl-abc','role':'rl-abc',
        'owner_id':owner['owner_id'],'original_request_id':owner['request_id'],'original_request_sha256':digest(owner_raw),
        'raw_source_sha256':ready['source_sha256'],'evaluator_root':str(data/'evaluator'),
        'evaluator_manifest_sha256':EVALUATOR_MANIFEST_SHA256,'scorer_pins_sha256':SCORER_PINS_SHA256}
    raw=encoded(descriptor)
    need(digest(raw)==request['finalized']['operator']['parent_scorer_sha256'],'resolved parent-private descriptor differs from reviewed JIT hash')
    private=launcher/'parent-private-scorer.json'
    with private.open('xb') as stream:stream.write(raw)
    parent_request={'format':'irisx/rlvr-installed-parent-request-v1','source_root':str(source),'output_root':request['output_root'],'config':config,
        'paths':{'outer_notebook_path':str(launcher/'outer.ipynb'),'operator_path':str(launcher/'operator.json'),
        'material_review_path':str(source.parent/'release/MATERIAL-REVIEW.json'),'source_archive_path':ready['source_archive_path'],
        'original_request_path':str(launcher/'original-request.json'),'parent_scorer_path':str(private)},
        'result_path':str(launcher/'result.json'),'source_sha256':ready['source_sha256']}
    path=launcher/'installed-parent-request.json';path.write_bytes(encoded(parent_request))
    receipt={'format':'irisx/rlvr-offline-preparation-receipt-v1','source_sha256':ready['source_sha256'],'source_acceptance':ready,
        'original_epoch':epoch,'installed_offline':True,'offline_environment':installed,'model_mount':model_root,
        'public_answers_opened':False,'model_loaded_by_preparation':False,'storage_plan':storage,'disk_admission':disk_admission,'actual_disk_free_bytes':shutil.disk_usage(source.parent).free}
    (launcher/'preparation-receipt.json').write_bytes(encoded(receipt))
    guard=load_file('rlvr_installed_parent_guard',baseline/'tools/arc_learning_agent_20261011/process_guard.py')
    run_bounded(installed['python_command']+[str(HERE/'parent_entry.py'),str(path),digest(path.read_bytes())],guard_module=guard,
        directory=launcher/'installed-parent',deadline_epoch=epoch+42180,env=worker_environment(fixture=False),scope='installed-parent-with-owned-model-child')


def main():
    need(len(sys.argv)==3,'exact preparation request and byte hash required')
    raw=read_regular(Path(sys.argv[1]),2*1024**2);need(digest(raw)==sys.argv[2],'preparation request bytes differ')
    prepare(parse(raw))

if __name__=='__main__':main()
