"""Explicit fictional provider/outer envelope around exact genuine tiny successor.
No model/provider execution; historical and new source bytes stay unchanged.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import zipfile
import validate_transfer_outputs as v
ROOT=Path(__file__).resolve().parents[2]
RETAINED_ROOT=ROOT/'cpu-owner-001'
RETAINED_SOURCE=ROOT/'cpu-source-freeze-001'
def make_synthetic_collector_fixture(destination,*,synthetic,template_release,owner_root=None,source_root=None):
    """Wrap actual owned tiny bytes in explicitly fictional provider/outer receipts.

    This tests only the offline envelope parser. Provider save/download/outer
    ownership are deliberately synthetic, not actual Kaggle execution evidence.
    Production entry rejects this before processing it.
    """
    retained_root=Path(owner_root or RETAINED_ROOT);retained_source=Path(source_root or RETAINED_SOURCE)
    if synthetic is not True:raise ValueError('explicit synthetic=True required')
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=False)
    release=Path(template_release);manifest=v.json_file(release/'publication-manifest.json')
    spec=next(n for n in manifest['notebooks'] if n['role']=='transfer002')
    shutil.copyfile(release/manifest['generation_call_policy']['path'],dest/manifest['generation_call_policy']['path'])
    manifest['synthetic']=True;manifest['fixture_qualification']='Fictional provider/outer envelope around unchanged actual tiny CPU evidence. No production claim.'
    source_mapping=v.source_identity(retained_source)
    inner=manifest['terminal_contract']['inner_request_source_identity'];inner['mapping']=source_mapping;inner['identity_sha256']=v.digest(source_mapping)
    payload=dest/'code-payload';payload.mkdir()
    with zipfile.ZipFile(payload/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in source_mapping:z.write(retained_source/name,name)
    code=next(d for d in manifest['datasets'] if d['role']=='code')
    code['upload_inventory']=[{'path':'source.zip','sha256':v.file_sha(payload/'source.zip'),'bytes':(payload/'source.zip').stat().st_size}]
    template=v.normalize_notebook(v.json_file(release/spec['path']));raw=v.canonical(template);(dest/spec['path']).write_bytes(raw);spec.update(sha256=v.raw_sha(raw),bytes=len(raw))
    terminal=v.json_file(retained_root/'terminal-receipt.json');epoch=terminal['predispatch_started_epoch']
    final=deepcopy(template);idx=spec['dispatch_epoch_patch']['cell_index'];final['cells'][idx]['source']=final['cells'][idx]['source'].replace('PREDISPATCH_EPOCH = None','PREDISPATCH_EPOCH = '+repr(epoch))
    final_path=dest/'finalized.ipynb';final_raw=v.canonical(final);final_path.write_bytes(final_raw);constants=v.notebook_constants(final)
    download=dest/'downloads';download.mkdir();prefix=Path(spec['output_root']).name;out=download/prefix;out.mkdir()
    shutil.copyfile(retained_root/'evidence.zip',out/'evidence.zip');shutil.copyfile(retained_root/'terminal-receipt.json',out/'terminal-receipt.json')
    launchroot=download/(prefix+'-launcher');launchroot.mkdir();remote_launcher=spec['output_root']+'-launcher'
    cfg={k.lower():constants[k] for k in ('MANUAL_START','ENABLE_MODEL','PROFILE','OUTPUT_ROOT','SOURCE_PARENT','INPUT_ROOT','CODE_ROOT','DATA_ROOT','TRAINING_ROOT')};cfg.update(session_seconds=43200,probe_seconds=43200,predispatch_epoch=epoch)
    cfg.update({k:constants[k.upper()] for k in ('execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds')})
    outer_request={'config':cfg,'pins':constants['PINS'],'started_epoch':epoch,'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'provider_deadline_epoch':epoch+42300,'launcher_root':remote_launcher,'loader_sha256':constants['EXPECTED_LOADER_SHA256'],'guard_sha256':constants['EXPECTED_GUARD_SHA256']}
    for name,row in manifest['terminal_contract']['outer_executable_files'].items():
        (launchroot/name).write_bytes((release/row['path']).read_bytes())
    outer_request['driver_sha256']=v.file_sha(launchroot/'bootstrap.py')
    with zipfile.ZipFile(retained_root/'evidence.zip') as z:actual_inner_launch=v.strict_json(z.read('owned-tree/launch.json'))
    worker=actual_inner_launch['coordinator_identity'];supervisor={**worker,'pid':worker['pid']+1000000,'birth':worker['birth']+1}
    proof={'format':'irisx/owned-process-closure-v1','root_identity':supervisor,'scope':'dedicated-subreaper-tree','ownership_complete':True,'closed':True,'owned_identities':[supervisor,worker],'remaining':[],'returncode':0,'worker_returncode':0,'forced':False,'reaped_identities':[supervisor,worker],'errors':[]}
    closure={'format':'irisx/learning-notebook-closure-v1','started_epoch':epoch,'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'completed_epoch':terminal['completed_epoch']+1,'within_absolute_deadline':True,'forced':False,'reason':None,'process_tree_proof':proof,'synthetic':True}
    def write(root,name,value):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v.canonical(value))
    write(launchroot,'request.json',outer_request);write(launchroot,'result.json',terminal);write(launchroot,'launcher-closure.json',closure)
    write(launchroot,'owned-tree/closure.json',proof)
    write(launchroot,'owned-tree/launch.json',{'supervisor_identity':supervisor,'worker_argv':['synthetic-python','-I','-B',remote_launcher+'/bootstrap.py',remote_launcher+'/request.json',v.file_sha(launchroot/'request.json')]})
    write(launchroot,'owned-tree/worker-launch.json',{'supervisor_identity':supervisor,'worker_identity':worker})
    write(launchroot,'owned-tree/supervisor-result.json',{'supervisor_identity':supervisor,'root_identity':worker,'closed':True,'ownership_complete':True,'remaining':[],'errors':[],'worker_returncode':0})
    write(dest,'publication-manifest.json',manifest);msha=v.file_sha(dest/'publication-manifest.json')
    clocks={'predispatch_epoch':epoch,'deadline_epoch':epoch+43200,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'outer_deadline_epoch':epoch+42180,'provider_timeout_seconds':42300}
    f={'synthetic':True,'manifest_sha256':msha,'finalized_sha256':v.raw_sha(final_raw),'template_sha256':spec['sha256'],**clocks};write(dest,'finalization.json',f)
    reference=spec['existing_notebook_reference']
    j={'synthetic':True,'role':'transfer002','manifest_sha256':msha,'source_sha256':v.raw_sha(final_raw),'reference':reference,'kernel_id':138123872,'expected_version':23,'save_calls':1,'dispatch_epoch':epoch+1,**clocks};write(dest,'launch-journal.json',j)
    saved={'path':str(final_path.absolute()),'bytes':len(final_raw),'sha256':v.raw_sha(final_raw)}
    l={'synthetic':True,'manifest_sha256':msha,'launch_journal_sha256':v.file_sha(dest/'launch-journal.json'),'finalization_sha256':v.file_sha(dest/'finalization.json'),'reference':reference,'kernel_id':138123872,'version':23,'submitted_source_sha256':v.raw_sha(final_raw),'saved_source':saved,'normalized_source_exact':True};write(dest,'launch-receipt.json',l)
    files=[];listed=[]
    for p in sorted(download.rglob('*')):
        if not p.is_file():continue
        n=p.relative_to(download).as_posix();files.append({'provider_path':n,'local_path':n,'version':23,'numeric_version':23,'bytes':p.stat().st_size,'sha256':v.file_sha(p),'http_status':200,'source_kind':'provider_download'});listed.append({'path':n,'bytes':p.stat().st_size,'size_source':'verified_numeric_download','numeric_version':23})
    if terminal.get('checkpoint_archive'):listed.append({'path':prefix+'/checkpoints.zip','bytes':terminal['checkpoint_archive']['bytes'],'size_source':'numeric_response_header_only','numeric_version':23})
    snap={'version':23,'status':'COMPLETE','source_sha256':saved['sha256'],'metadata_sha256':'0'*64}
    checkpoint={'path':prefix+'/checkpoints.zip','presence':'UNKNOWN','bytes':None,'body_consumed_bytes':0,'archive_bytes_verified':False}
    if terminal.get('checkpoint_archive'):checkpoint.update(presence='HTTP200_CONTENT_LENGTH_VERIFIED',bytes=terminal['checkpoint_archive']['bytes'],http_status=200,declared_sha256_unverified=terminal['checkpoint_archive']['sha256'],scope='numeric output request; Content-Length and successful response only')
    retrieval={'format':'irisx/transfer-selected-retrieval-v1','synthetic':True,'manifest_sha256':msha,'launch_receipt_sha256':v.file_sha(dest/'launch-receipt.json'),'reference':reference,'kernel_id':138123872,'numeric_output_version':23,'before':snap,'after':snap,'files':files,'provider_files':listed,'inventory_scope':'selected_outputs_only','whole_provider_inventory_verified':False,'provider_files_scope':'selected_numeric_byte_or_header_facts','checkpoint_downloaded':False,'checkpoint_metadata_only':checkpoint};write(dest,'retrieval-receipt.json',retrieval)
    return {'download_root':download,'manifest':dest/'publication-manifest.json','finalization':dest/'finalization.json','launch_journal':dest/'launch-journal.json','launch_receipt':dest/'launch-receipt.json','retrieval_receipt':retrieval,'finalized_notebook':final_path,'allow_synthetic':True}


def make_final_source_collector_fixture(destination,*,synthetic,template_release,source_root):
    """Entirely authored before-load failure; never relabel a genuine model run.

    The actual final manifest/template/source ZIP remain exact; only mocked
    execution/provider envelopes are authored, all with synthetic=True.
    """
    if synthetic is not True:raise ValueError('synthetic=True required')
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=False);owner=dest/'fictional-owner';owner.mkdir()
    release=Path(template_release);manifest=v.json_file(release/'publication-manifest.json');spec=next(n for n in manifest['notebooks'] if n['role']=='transfer002')
    mapping=manifest['terminal_contract']['inner_request_source_identity']['mapping']
    if v.source_identity(source_root)!=mapping:raise ValueError('final source tree must equal exact manifest mapping')
    epoch=1000000.;output=spec['output_root'];coordinator={'pid':901,'birth':9010,'session':900,'state':'Z'};supervisor={'pid':902,'birth':9020,'session':902,'state':'Z'};worker={'pid':903,'birth':9030,'session':902,'state':'Z'}
    request={'format':'irisx/true-arc-transfer-request-v1','synthetic':True,'config':{'tiny_cpu':True,'started_epoch':epoch,'maximum_seconds':1800},'source_identity':mapping,'output_root':output,'hard_deadline':10000.,'work_deadline':9940.}
    child={'source_identity_sha256':v.digest(mapping),'request_sha256':v.digest(request),'pending_work':{},'model_stopped':True,'child_cleanup_complete':True,'public_gold_opened':False,'physical_usage':dict.fromkeys(v.CAPS,0),'synthetic':True}
    proof={'format':'irisx/owned-process-closure-v1','root_identity':supervisor,'scope':'dedicated-subreaper-tree','ownership_complete':True,'closed':True,'owned_identities':[supervisor,worker],'remaining':[],'returncode':1,'worker_returncode':1,'forced':False,'reaped_identities':[supervisor,worker],'errors':[]}
    rows=[{'event':'opened','caps':v.CAPS,'index':0,'previous':'0'*64}];rows[0]['sha256']=v.digest(rows[0])
    objects={'request.json':request,'child-summary.json':child,'active-stage.json':{'stage':'native-load','status':'closed'},'checkpoint-assets-manifest.json':{'files':{},'bytes':0,'complete_store':False},
        'owned-tree/closure.json':proof,'owned-tree/worker-launch.json':{'supervisor_identity':supervisor,'worker_identity':worker},
        'owned-tree/supervisor-result.json':{'supervisor_identity':supervisor,'root_identity':worker,'closed':True,'ownership_complete':True,'remaining':[],'errors':[],'worker_returncode':1},
        'owned-tree/launch.json':{'coordinator_identity':coordinator,'worker_argv':['synthetic-python','/synthetic-final-source/'+v.PACKAGE+'child.py',output+'/request.json',v.digest(request)]}}
    members={n:v.canonical(value) for n,value in objects.items()};members['physical-work.jsonl']=v.canonical(rows[0])
    inventory={'format':'irisx/qwen14b-probe-archive-v1','files':{n:{'bytes':len(raw),'sha256':v.raw_sha(raw)} for n,raw in members.items()},'owned_process_closed':True,'public_score':None}
    with zipfile.ZipFile(owner/'evidence.zip','x',zipfile.ZIP_DEFLATED) as z:
        for n,raw in members.items():z.writestr(n,raw)
        z.writestr('archive-manifest.json',v.canonical(inventory))
    terminal={'format':'irisx/true-arc-transfer-owned-v1','status':'TRANSFER_FAILED','synthetic':True,'source_identity_sha256':v.digest(mapping),'child':child,'archive':{'sha256':v.file_sha(owner/'evidence.zip'),'bytes':(owner/'evidence.zip').stat().st_size,'files':len(members)+1},'closure_proof':proof,'owned_process_closed':True,'science_complete':False,'operational_success':False,
        'predispatch_started_epoch':epoch,'maximum_seconds':1800,'global_deadline_epoch':epoch+43200,'effective_deadline_epoch':epoch+1800,'completed_epoch':epoch+1,'within_probe_deadline':True,'within_absolute_deadline':True,'elapsed_seconds':1.,'work_reserve_seconds':60,'owner_stop_reserve_seconds':30}
    (owner/'terminal-receipt.json').write_bytes(v.canonical(terminal))
    args=make_synthetic_collector_fixture(dest/'envelope',synthetic=True,template_release=release,owner_root=owner,source_root=source_root)
    # Restore the exact final released manifest, whose source inventory matches
    # the entirely authored inner request. No manifest field is substituted.
    args['manifest']=release/'publication-manifest.json';msha=v.file_sha(args['manifest'])
    f=v.json_file(args['finalization']);f['manifest_sha256']=msha;f['template_sha256']=spec['sha256'];Path(args['finalization']).write_bytes(v.canonical(f))
    j=v.json_file(args['launch_journal']);j['manifest_sha256']=msha;Path(args['launch_journal']).write_bytes(v.canonical(j))
    l=v.json_file(args['launch_receipt']);l.update(manifest_sha256=msha,launch_journal_sha256=v.file_sha(args['launch_journal']),finalization_sha256=v.file_sha(args['finalization']));Path(args['launch_receipt']).write_bytes(v.canonical(l))
    r=args['retrieval_receipt'];r.update(manifest_sha256=msha,launch_receipt_sha256=v.file_sha(args['launch_receipt']));(dest/'envelope/retrieval-receipt.json').write_bytes(v.canonical(r))
    (dest/'SYNTHETIC-FIXTURE.json').write_bytes(v.canonical({'synthetic':True,'production_evidence':False,'uses_exact_final_manifest':True,'fixture':'Entirely fictional before-model failure, no genuine tiny source relabeling.','source_identity_sha256':v.digest(mapping),'manifest_sha256':msha}))
    return args
