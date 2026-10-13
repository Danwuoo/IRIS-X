"""Review-gated numeric29 RL evidence and independently authenticated consumer."""
import argparse, hashlib, importlib.util, json, math, stat, sys, time, types
from pathlib import Path

# Upstream-only pins keep collector -> transport -> common acyclic and source-only.
COMMON_SOURCE_SHA256='e1975b858f42e00e83bf73c221b03c8289ad6efd74cddf00107b85b5cdf13d4e'
TRANSPORT_SOURCE_SHA256='faa901638b73d980fdfb9cd174122ff45703e77225d7941398066bfd86cfae48'
_local_sources={}
for _name,_digest in [('operator_common.py',COMMON_SOURCE_SHA256),('rl_transport.py',TRANSPORT_SOURCE_SHA256)]:
    _path=Path(__file__).absolute().with_name(_name)
    if any(p.is_symlink() for p in (_path,*_path.parents)) or not stat.S_ISREG(_path.stat().st_mode):
        raise ValueError('unsafe_local_operator_source')
    with _path.open('rb') as _f:_raw=_f.read(1024**2+1)
    if len(_raw)>1024**2 or hashlib.sha256(_raw).hexdigest()!=_digest:
        raise ValueError('local_operator_source_pin')
    _local_sources[_name]=(_path,_raw)
_path,_raw=_local_sources['rl_transport.py']
transport=types.ModuleType('reviewed_rl_transport');transport.__file__=str(_path);transport.__package__=''
exec(compile(_raw,str(_path),'exec',dont_inherit=True,optimize=sys.flags.optimize),transport.__dict__)
_common=transport._common
globals().update({k:v for k,v in _common.__dict__.items() if not k.startswith('_')})
OUT=WORK/'publication/run-evidence'
DOWNLOADS=OUT/'downloads'
class IndexingPending(GuardError):pass

def bindings(args):
    m=transport.load_contract(args);review=transport.monitor_gate(args)
    launch_path=STATE/'notebook-rlvr002-receipt.json';journal_path=STATE/'notebook-rlvr002-journal.json';final_path=STATE/'finalization.json'
    l=obj(launch_path);j=obj(journal_path);f=obj(final_path)
    need(l['launch_journal_sha256']==file_sha(journal_path) and l['finalization_sha256']==file_sha(final_path),'launch_hash_chain')
    need(l['manifest_sha256']==j['manifest_sha256']==f['manifest_sha256']==args.manifest_sha and j['save_calls']==1 and j['expected_version']==l['version']==29 and j['kernel_id']==l['kernel_id']==138123872,'exact_launch_identity')
    need(l['reference']==j['reference']==REF and l['role']==j['role']=='rlvr002','launch_reference_role')
    need(j['material_approval_sha256']==args.material_sha and j['transport_review_sha256']==args.review_sha and j['monitor_review_sha256']==args.monitor_sha,'launch_review_hashes')
    need(l['git_publication_completed'] is False and l['git_commit'] is None,'honest_git_provenance')
    raw=verified(STATE/'active-finalized.ipynb',f['finalized_sha256']);n=transport.row(m,'rlvr002')
    template=verified(Path(args.manifest).resolve().parent/n['path'],f['template_sha256'])
    transport.check_finalization(m,args,f)
    need(sha(raw)==l['submitted_source_sha256']==j['source_sha256'],'source_launch_hash')
    saved=verified(l['saved_source']['path'],l['saved_source']['sha256'],l['saved_source']['bytes'])
    need(source_normalize(saved)==source_normalize(raw),'saved_source_normalization')
    need(all(j[k]==f[k] for k in ['predispatch_epoch','deadline_epoch','global_deadline_epoch','execution_deadline_epoch','outer_deadline_epoch','provider_timeout_seconds']),'clock_envelope_link')
    need(0<=j['dispatch_epoch']-f['predispatch_epoch']<=60,'dispatch_freshness')
    need(all(f.get(k)==v for k,v in transport.clock(f['predispatch_epoch']).items()),'absolute_clock_policy')
    need(j['claim_sha256']==file_sha(STATE/'notebook-rlvr002.claim.json'),'original_claim_binding')
    need(j['wire_sha256']==file_sha(STATE/'notebook-rlvr002-wire.json'),'launch_wire_hash')
    need(obj(STATE/'notebook-rlvr002-wire.json')==transport.kernel_wire(n,raw),'exact_wire_settings')
    need(l['model_sources_returned'] in MODEL_ALIASES,'exact_returned_model')
    transport.saved_settings(l['settings'],n,29)
    need(l['model_sources_returned']==l['settings'].get('modelDataSources'),'raw_model_receipt_link')
    return m,l,j,f


def output_paths(m):
    t=m['terminal_contract'];prefix=Path(transport.row(m,'rlvr002')['output_root']).name;outer=prefix+'-launcher'
    caps={t['terminal_path']:16*1024**2,t['evidence_path']:t['archive_caps']['evidence_archive_bytes']}
    required=set(caps)
    for name,cap in {'owner-request.json':4*1024**2,'owner-clock.json':1024**2,'artifact-inventory.json':16*1024**2,'outer-closure.json':4*1024**2,'owned-result.json':4*1024**2}.items():
        caps[prefix+'/'+name]=cap;required.add(prefix+'/'+name)
    for name in ['outer.ipynb','original-request.json','operator.json','parent-private-scorer.json','preparation-request.json','preparation-receipt.json','installed-parent-request.json','interpreter-manifest.json','result.json']:
        caps[outer+'/'+name]=4*1024**2;required.add(outer+'/'+name)
    caps[outer+'/startup-failure.json']=64*1024
    for stage in ('preparation','installed-parent'):
        caps[outer+'/'+stage+'/startup-failure.json']=64*1024
        for name in ['closure.json','owned-tree/launch.json','owned-tree/worker-launch.json','owned-tree/supervisor-result.json','owned-tree/closure.json']:
            caps[outer+'/'+stage+'/'+name]=4*1024**2;required.add(outer+'/'+stage+'/'+name)
        for name in ('stdout.txt','stderr.txt'):caps[outer+'/'+stage+'/'+name]=8*1024**2
    return prefix,outer,caps,required

def failure_paths(prefix):
    return {prefix+'/'+name:cap for name,cap in {'owned-result.json':16*1024**2,'owner-request.json':4*1024**2,'owner-clock.json':1024**2,'outer-closure.json':1024**2,'inner-closure.json':1024**2,'worker.stdout.log':8*1024**2,'worker.stderr.log':8*1024**2,'experiment/result.json':2*1024**3,'physical-journal.jsonl':8192*400000,'physical-journal.jsonl.anchor':1024**2}.items()}

def poll(provider,m,l):
    provider.ensure_read_auth();snap,_,_=transport.bracket(provider,29,l['saved_source']['sha256'],transport.row(m,'rlvr002'))
    print(json.dumps({'event':'provider_observation',**snap}),flush=True);return snap

def downloaded_bytes():
    total=0
    if DOWNLOADS.exists():
        for p in DOWNLOADS.rglob('*'):
            secure_path(p);mode=p.stat().st_mode;need(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'download_tree_special')
            if stat.S_ISREG(mode):total+=p.stat().st_size
    return total

def fetch_selected(provider,name,cap,aggregate_cap,expected_sha=None,expected_bytes=None):
    relative(name);need(type(cap)is int and cap>=0,'download_cap_type')
    dest=secure_path(DOWNLOADS/name);receipt_path=secure_path(OUT/'download-receipts'/(sha(name.encode())+'.json'))
    if receipt_path.exists():
        row=obj(receipt_path);need(row['provider_path']==name and row['version']==row['numeric_version']==29 and row['http_status']==200 and row['source_kind']=='provider_download','selected_cache_binding')
        need(dest.stat().st_size==row['bytes']<=cap and file_sha(dest)==row['sha256'],'selected_cache_hash')
        need((expected_sha is None or row['sha256']==expected_sha) and (expected_bytes is None or row['bytes']==expected_bytes),'expected_cache_binding');return row
    need(not dest.exists(),'download_without_receipt')
    need(downloaded_bytes()+cap<=aggregate_cap,'selected_download_aggregate')
    d=binary_get(provider.output(name),dest,cap,expected_sha,expected_bytes)
    row={'provider_path':name,'local_path':name,'version':29,'numeric_version':29,'bytes':d['bytes'],'sha256':d['sha256'],'http_status':200,'source_kind':'provider_download'}
    write_new(receipt_path,row);return row

def checkpoint_observation(provider,m,terminal):
    """Numeric successful header presence is independent of source-local hashes."""
    local=terminal.get('checkpoint_archive_observation')
    default={'filename':'checkpoints.zip','present':None,'byte_length':None,'transport_observation':'UNKNOWN','body_materialized':False,'independently_sha256_verified':False,'observed_sha256':None}
    if local is None:return None
    need(type(local)is dict and local.get('present') is True,'checkpoint_declaration_schema')
    size=local.get('byte_length');cap=m['terminal_contract']['archive_caps']['checkpoint_archive_bytes']
    need(type(size)is int and 0<size<=cap,'checkpoint_declared_size')
    need(local.get('filename')=='checkpoints.zip' and local.get('body_materialized') is False and local.get('independently_sha256_verified') is False and local.get('observed_sha256') is None,'checkpoint_no_body_claim')
    try:r=binary_metadata(provider.output(m['terminal_contract']['checkpoint_path']),size,cap)
    except Exception as e:
        if getattr(getattr(e,'response',None),'status_code',None)!=404:raise
        return {**default,'transport_observation':'PENDING_HTTP404','http_status':404}
    need(r['http_status']==200 and r['bytes']==size and r['body_consumed_bytes']==0,'header_only_response')
    return {'filename':'checkpoints.zip','present':True,'byte_length':size,'transport_observation':'HTTP200_CONTENT_LENGTH_VERIFIED','body_materialized':False,'independently_sha256_verified':False,'observed_sha256':None}

def wrapper_gate(m,args,f,outer,prefix):
    """Raw archived PID/birth/argv/request/source/clock closure, never summary flags."""
    root=Path(args.manifest).resolve().parent;descriptor_=m['parent_wrapper_verifier']
    path=root/descriptor_['path'];transport.descriptor_at(root,descriptor_)
    helper=load_source_module('reviewed_rl_parent_wrappers_'+descriptor_['sha256'],path,descriptor_['sha256'])
    documents=transport.check_finalization(m,args,f)
    notebook_descriptor=next(d for d in m['jit']['dependencies'] if d['path']=='notebook-release.json')
    notebook_release=json.loads(transport.descriptor_at(root,notebook_descriptor))
    environment=json.loads(transport.descriptor_at(root,m['consumer_contract']['environment']))
    result=helper.verify_wrappers(DOWNLOADS/outer,expected_jit=documents,
        notebook_release=notebook_release,reviewed_environment=environment,
        runtime_outer_raw=read(DOWNLOADS/prefix/'outer-closure.json',4*1024**2),
        runtime_owned_result_raw=read(DOWNLOADS/prefix/'owned-result.json',4*1024**2),
        runtime_terminal_raw=read(DOWNLOADS/m['terminal_contract']['terminal_path'],16*1024**2))
    need(result['closure_valid'] is True and type(result['operational'])is bool and result['runtime_tree_link_checked'] is True,'invalid_raw_wrapper_proof')
    need(result['source_sha256']==m['runtime_source_sha256'] and result['original_epoch']==f['predispatch_epoch'] and result['outer_deadline_epoch']==f['outer_deadline_epoch'],'raw_wrapper_source_clock')
    return result

def assemble_consumer_envelope(m,args,f,receipt,terminal,archive_row,terminal_row,prefix,outer,checkpoint):
    """Authenticate downloaded compact identities against the sealed runtime ZIP and JIT."""
    contract=m['consumer_contract'];root=Path(args.manifest).resolve().parent
    owner_path=DOWNLOADS/prefix/'owner-request.json';clock_path=DOWNLOADS/prefix/'owner-clock.json';inventory_path=DOWNLOADS/prefix/'artifact-inventory.json';closure_path=DOWNLOADS/prefix/'outer-closure.json'
    members=terminal['archive']['members']
    for path in (owner_path,clock_path,inventory_path,closure_path):
        need(members.get(path.name)=={'bytes':path.stat().st_size,'sha256':file_sha(path)},'compact_original_matches_sealed_archive')
    owner=obj(owner_path,4*1024**2);clock_doc=obj(clock_path);inventory_sha=file_sha(inventory_path)
    need(clock_doc['original_epoch']==f['predispatch_epoch'],'runtime_original_epoch')
    b=owner['bootstrap'];jit=obj(STATE/'operator.json')
    need(b['original_epoch']==f['predispatch_epoch'] and b['raw_source_sha256']==contract['source_sha256'],'runtime_bootstrap_identity')
    for key in ('original_request_sha256','parent_scorer_sha256'):
        # The bootstrap records original_request as a file reference, while operator records its digest.
        observed=b['original_request']['file_sha256'] if key=='original_request_sha256' else b[key]
        need(observed==jit[key],'runtime_bootstrap_jit_link')
    release_root=OUT/'consumer-release';secure_path(release_root);release_root.mkdir(exist_ok=True)
    def retain(name,raw):
        path=release_root/name
        if path.exists():need(read(path,256*1024**2)==raw,'existing_consumer_release_changed')
        else:write_new(path,raw)
    for key in ('release','material_review','environment','phase_policy','owner_protocol'):
        retain(key+'.json',transport.descriptor_at(root,contract[key]))
    mapped={'outer_notebook':('outer-notebook.ipynb','active-finalized.ipynb'),'operator':('operator.json','operator.json'),'original_request':('original-request.json','original-request.json'),'parent_scorer':('parent-scorer.json','parent-private-scorer.json')};refs={}
    for key,(name,local) in mapped.items():
        raw=read(STATE/local,4*1024**2);retain(name,raw);refs[key]={'path':name,'file_sha256':sha(raw)}
    raw=transport.descriptor_at(root,contract['source_archive']);retain('source.zip',raw);refs['source_archive']={'path':'source.zip','file_sha256':sha(raw)}
    review_inputs={key:{'path':contract['review_input_paths'][key],'file_sha256':contract[key]['sha256']} for key in ('environment','phase_policy')}
    need(owner['config']['environment_path']==review_inputs['environment']['path'] and owner['config']['policy_path']==review_inputs['phase_policy']['path'],'actual_review_paths')
    observation_sha=None if checkpoint is None else sha(json.dumps(checkpoint,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    launch={'format':'owned-rl-independent-launch-v1','release_sha256':contract['release']['sha256'],'files':refs,'owner_request_sha256':file_sha(owner_path),'owner_clock_sha256':file_sha(clock_path),'artifact_inventory_sha256':inventory_sha,'review_inputs':review_inputs,'checkpoint_archive_observation_sha256':observation_sha}
    retain('launch.json',canonical(launch))
    collection={'format':'owned-rl-batched-authenticated-collection-v1','source_sha256':contract['source_sha256'],'source_archive_sha256':contract['source_archive']['sha256'],'policy_sha256':contract['phase_policy']['sha256'],'release_sha256':contract['release']['sha256'],'launch_sha256':file_sha(release_root/'launch.json'),'artifact_inventory_sha256':inventory_sha,'dataset_sha256':contract['dataset_sha256'],'archive_sha256':archive_row['sha256'],'terminal_sha256':terminal_row['sha256'],'owner_request_sha256':file_sha(owner_path),'outer_closure_sha256':file_sha(closure_path),'checkpoint_archive_observation':checkpoint}
    p=OUT/'AUTHENTICATED-COLLECTION.json';write_new(p,collection)
    return p,release_root

def validate_received(m,args,collection_path,release_root,archive_path,terminal_path):
    """This exact source callsite is externally pinned by consumer operator JSON."""
    review=transport.monitor_gate(args)
    root=secure_path(args.consumer_root);path=root/'reviewed_entry.py'
    entry=load_source_module('reviewed_rl_terminal_entry',path,review['consumer_files']['reviewed_entry.py'])
    context=entry.receive_authenticated_collection(collection_path,file_sha(collection_path),operator_pins_path=root/'CONSUMER-OPERATOR.json')
    return entry.validate_reviewed(context,archive_path=archive_path,terminal_path=terminal_path,output_root=OUT/'validated-evidence',source_root=Path(args.manifest).resolve().parent/m['consumer_contract']['source_root'],release_root=release_root)

def validation_gate(result,provider_status,wrapper_verified,wrapper_operational=True):
    need(provider_status in TERMINAL,'provider_terminal_required')
    need(wrapper_verified is True and type(wrapper_operational)is bool,'invalid_raw_wrapper_blocks_all_admission')
    if result.get('status')=='STOPPED_INCOMPLETE':
        need(result.get('diagnostic_evidence_valid') is True and result.get('authenticated_collection_verified') is True and result.get('release_content_binding_valid') is True and result.get('external_owner_envelope_verified') is True,'authenticated_diagnostic_only')
        need(result.get('production_admitted') is False and result.get('public_goal_met') is False and result.get('scientific_goal_met') is False,'diagnostic_no_success')
        return {**result,'provider_status':provider_status,'operational_complete':False,'operational_success':False,'comparison_complete':False,'compute_matched':False,'comparison_eligible':False,'public_benchmark_evidence_eligible':False,'verified_public_threshold_reached':False,'public_goal_met':False,'goal_met':False,'automatic_retry':False}
    need(result.get('evidence_valid') is True and result.get('authenticated_collection_verified') is True and result.get('external_owner_envelope_verified') is True and result.get('production_admitted') is True,'unverified_production_content')
    need(result.get('status')=='REVIEWED_PRODUCTION_CONTENT_COMPLETE','consumer_status')
    fields=('operational_complete','comparison_complete','compute_matched','comparison_eligible','public_benchmark_evidence_eligible','public_goal_met','scientific_goal_met')
    need(all(type(result.get(k))is bool for k in fields),'consumer_boolean_axes')
    need(result['comparison_eligible']==(result['comparison_complete'] and result['compute_matched']),'paired_axis_conflation')
    public=result.get('public',{});metric=public.get('micro_pass_at_2',{})
    eligible=result['public_benchmark_evidence_eligible']
    if eligible:need(public.get('status')=='SEALED_SCORER_ROWS_REPLAYED' and public.get('scorer_rows_complete') is True and type(metric.get('denominator'))is int and metric['denominator']==167 and type(metric.get('numerator'))is int and 0<=metric['numerator']<=167 and type(metric.get('value')) in (int,float) and math.isfinite(metric['value']) and abs(metric['value']-metric['numerator']/167)<=1e-12,'original_public_metric')
    threshold=eligible and metric['numerator']>=151
    need(result['public_goal_met']==result['scientific_goal_met']==threshold,'scientific_goal_evidence')
    goal=threshold and wrapper_verified
    operational=provider_status=='COMPLETE' and wrapper_verified and wrapper_operational and result['operational_complete']
    # Scientific threshold survives a later provider ERROR when all original proofs are valid.
    return {**result,'provider_status':provider_status,'provider_operational_success':provider_status=='COMPLETE','operational_complete':operational,'operational_success':operational,'verified_public_threshold_reached':goal,'public_goal_met':goal,'goal_met':goal,'automatic_retry':False}
def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate_diagnostic_json_key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(GuardError('nonfinite_diagnostic_json')))

PREOWNED_STAGES={'source-guard-import','source-import-policy','parent-environment-import','parent-environment-policy'}

def preowned_failure_binding(m,args,f,before,diagnostic,outer):
    """Exact trusted-source diagnostic attribution; never a closure capability."""
    expected_keys={'format','status','stage','exception_type','safe_message','frames','observed_epoch','observed_monotonic','original_epoch','deadline_epoch','source_sha256','request_sha256','dispatch_state','proof_available','proof_verified','clean_owned_closure_verified','closure_authority','model_or_GPU_execution_claim','environment_values_recorded','operational_success','VM_teardown_or_billing_claim'}
    need(type(diagnostic)is dict and set(diagnostic)==expected_keys,'closed_startup_diagnostic')
    need(before['status']=='ERROR' and before['version']==29 and before['gpu_stop'] is False,'preowned_error_only')
    need(diagnostic['format']=='irisx/rlvr-parent-startup-failure-v1' and diagnostic['status']=='FAILED' and diagnostic['stage'] in PREOWNED_STAGES and diagnostic['dispatch_state']=='not-dispatched','preowned_stage_only')
    flags=('proof_available','proof_verified','clean_owned_closure_verified','closure_authority','model_or_GPU_execution_claim','environment_values_recorded','operational_success','VM_teardown_or_billing_claim')
    need(all(diagnostic[k] is False for k in flags),'diagnostic_cannot_assert_proof')
    epoch=f['predispatch_epoch']
    need(type(before['observed_epoch']) in (int,float) and math.isfinite(before['observed_epoch']),'finite_provider_observation')
    for key in ('observed_epoch','observed_monotonic','original_epoch','deadline_epoch'):
        need(type(diagnostic[key]) in (int,float) and math.isfinite(diagnostic[key]),'finite_startup_time')
    need(diagnostic['original_epoch']==epoch and diagnostic['deadline_epoch']==f['outer_deadline_epoch']==epoch+42180 and epoch<=diagnostic['observed_epoch']<=min(before['observed_epoch'],epoch+42180) and diagnostic['observed_monotonic']>=0,'startup_original_clock')
    need(diagnostic['source_sha256']==m['runtime_source_sha256'],'startup_source_identity')
    need(type(diagnostic['exception_type'])is str and 0<len(diagnostic['exception_type'])<=128 and type(diagnostic['safe_message'])is str and len(diagnostic['safe_message'])<=512,'bounded_diagnostic_text')
    need(type(diagnostic['frames'])is list and len(diagnostic['frames'])<=32,'bounded_diagnostic_frames')
    for frame in diagnostic['frames']:
        need(type(frame)is dict and set(frame)=={'file','function','line'} and all(type(frame[k])is str and len(frame[k])<=128 for k in ('file','function')) and type(frame['line'])is int and frame['line']>0,'diagnostic_frame_schema')
    docs=transport.check_finalization(m,args,f)
    for name,key in (('outer.ipynb','active-finalized.ipynb'),('original-request.json','original-request.json'),('operator.json','operator.json')):
        need(read(DOWNLOADS/outer/name,4*1024**2)==docs[key],'preowned_exact_jit_documents')
    prep_raw=read(DOWNLOADS/outer/'preparation-request.json',4*1024**2)
    need(diagnostic['request_sha256']==sha(prep_raw),'diagnostic_request_bytes')
    prep=strict_json(prep_raw)
    need(type(prep)is dict and set(prep)=={'format','ready','release','finalized','notebook_python_executable','output_root','input_root','epoch','launcher_root','environment_root'} and prep['format']=='irisx/rlvr-parent-preparation-request-v1','preparation_request_schema')
    root=Path(args.manifest).resolve().parent
    d=next(d for d in m['jit']['dependencies'] if d['path']=='notebook-release.json')
    release=strict_json(transport.descriptor_at(root,d));owner=strict_json(docs['original-request.json']);operator=strict_json(docs['operator.json'])
    need(prep['release']==release and prep['finalized']=={'owner_request':owner,'operator':operator} and owner['original_epoch']==epoch,'preowned_reviewed_release_jit')
    n=transport.row(m,'rlvr002');source=n['source_parent']+'/runtime'
    need(prep['epoch']==epoch and prep['output_root']==n['output_root'] and prep['input_root']=='/kaggle/input' and prep['launcher_root']==n['output_root']+'-launcher' and prep['environment_root']==m['terminal_contract']['storage']['environment_root'],'preowned_paths_epoch')
    ready=prep['ready']
    need(ready['source_root']==source and ready['source_sha256']==release['source_sha256']==m['runtime_source_sha256'] and ready['source_archive_path']==n['source_parent']+'/source.zip' and ready['source_archive_sha256']==release['source_archive_sha256'] and ready['manifest_sha256']==release['code_manifest_sha256'],'preowned_complete_source_lineage')
    python=prep['notebook_python_executable'];need(type(python)is str and python.startswith('/') and '..' not in Path(python).parts,'preowned_observed_interpreter')
    return {'stage':diagnostic['stage'],'exception_type':diagnostic['exception_type'],'request_sha256':diagnostic['request_sha256'],'diagnostic_source_bound':True,'source_sha256':m['runtime_source_sha256'],'original_epoch':epoch,'dispatch_state':'not-dispatched','owned_closure_verified':False,'physical_costs_known':False,'billing_verified':False}


def collect_preowned_failure(provider,m,l,j,f,args,before,prefix,outer,caps,required,aggregate):
    """One small ERROR-only frontier read can close a known pre-owned failure."""
    if before['status']!='ERROR':return None,[],[]
    name=outer+'/startup-failure.json';rows_=[];missing=[]
    def fetch(name):
        try:rows_.append(fetch_selected(provider,name,caps[name],aggregate))
        except Exception as e:
            if getattr(getattr(e,'response',None),'status_code',None)!=404:raise
            missing.append(name)
    fetch(name)
    if missing:return None,rows_,missing
    diagnostic=strict_json(read(DOWNLOADS/name,65536))
    if not (type(diagnostic)is dict and diagnostic.get('format')=='irisx/rlvr-parent-startup-failure-v1' and diagnostic.get('stage') in PREOWNED_STAGES and diagnostic.get('dispatch_state')=='not-dispatched'):
        return None,rows_,missing
    for tail in ('outer.ipynb','original-request.json','operator.json','preparation-request.json'):fetch(outer+'/'+tail)
    if missing:return None,rows_,missing
    bound=preowned_failure_binding(m,args,f,before,diagnostic,outer)
    after=poll(provider,m,l)
    need(after['version']==before['version']==29 and after['status']==before['status']=='ERROR' and after['source_sha256']==before['source_sha256']==l['saved_source']['sha256'] and after['gpu_stop'] is False,'preowned_terminal_source_bracket')
    need(type(after['observed_epoch']) in (int,float) and math.isfinite(after['observed_epoch']) and before['observed_epoch']<=after['observed_epoch'],'ordered_preowned_collection_bracket')
    attempted={r['provider_path'] for r in rows_}|set(missing)
    unattempted=sorted((set(caps)|set(failure_paths(prefix)))-attempted)
    receipt={'format':'irisx/rlvr-selected-retrieval-v1','manifest_sha256':args.manifest_sha,'reference':REF,'kernel_id':138123872,'numeric_output_version':29,'launch_receipt_sha256':file_sha(STATE/'notebook-rlvr002-receipt.json'),'before':before,'after':after,'files':rows_,'inventory_scope':'selected_outputs_only','whole_provider_inventory_verified':False,'missing_paths':missing,'unattempted_paths':unattempted,'required_paths_unattempted':sorted(required-attempted),'checkpoint_downloaded':False,'checkpoint_archive_observation':None,'checkpoint_provider_path':m['terminal_contract']['checkpoint_path'],'checkpoint_numeric_version':29,'separate_checkpoint_presence':'UNKNOWN','collected_epoch':time.time(),'collection_scope':'source_bound_preowned_failure_frontier','diagnostic_binding':bound}
    rp=OUT/f'retrieval-{time.time_ns()}.json';write_new(rp,receipt)
    result={'status':'INCOMPLETE_DIAGNOSTIC_EVIDENCE','reason':'SOURCE_BOUND_PRE_OWNED_STARTUP_FAILURE','provider_status':'ERROR','missing':missing,'unattempted_paths':unattempted,'required_paths_unattempted':receipt['required_paths_unattempted'],'retrieval_receipt':descriptor(rp),'diagnostic_binding':bound,'terminal_validated':False,'consumer_admitted':False,'production_admitted':False,'scientific_evidence_eligible':False,'science_complete':False,'operational_complete':False,'comparison_complete':False,'comparison_eligible':False,'compute_matched':False,'public_benchmark_evidence_eligible':False,'verified_public_threshold_reached':False,'provider_operational_success':False,'owned_closure_verified':False,'physical_costs_known':False,'billing_verified':False,'operational_success':False,'public_score':None,'public_goal_met':False,'scientific_goal_met':False,'goal_met':False,'automatic_retry':False,'whole_provider_inventory_verified':False,'separate_checkpoint_presence':'UNKNOWN','qualification':'A source-linked pre-owned diagnostic ends further missing-output polling. Unattempted outputs and runtime costs/closure remain unknown; no remote OS or VM-teardown attestation.'}
    event('preowned-incomplete-outputs',result);write_new(OUT/'TERMINAL-BLOCKER.json',result)
    return result,rows_,missing


def collect(provider,m,l,j,f,args,before=None,final_incomplete=False):
    provider.ensure_read_auth();before=before or poll(provider,m,l)
    need(before['status'] in TERMINAL and before['gpu_stop'] is False,'provider_not_terminal')
    prefix,outer,caps,required=output_paths(m);t=m['terminal_contract'];aggregate=t['archive_caps']['evidence_archive_bytes']+256*1024**2
    early,rows_,missing=collect_preowned_failure(provider,m,l,j,f,args,before,prefix,outer,caps,required,aggregate)
    if early is not None:return early
    terminal=None;prefetched={r['provider_path'] for r in rows_}|set(missing)
    for name,cap in caps.items():
        if name in prefetched:continue
        expected_sha=expected_bytes=None
        if name==t['evidence_path'] and terminal is not None and terminal.get('archive_complete') is True:
            a=terminal['archive'];need(a['path']=='/kaggle/working/'+name,'terminal_evidence_path')
            expected_sha=a['sha256'];expected_bytes=a['bytes']
            need(type(expected_bytes)is int and 0<expected_bytes<=cap and type(expected_sha)is str and re.fullmatch('[0-9a-f]{64}',expected_sha),'terminal_archive_descriptor')
        try:
            rr=fetch_selected(provider,name,cap,aggregate,expected_sha,expected_bytes);rows_.append(rr)
            if name==t['terminal_path']:terminal=obj(DOWNLOADS/name,16*1024**2)
        except Exception as e:
            if getattr(getattr(e,'response',None),'status_code',None)!=404:raise
            missing.append(name)
    present={r['provider_path']:r for r in rows_}
    if t['evidence_path'] not in present:
        for name,cap in failure_paths(prefix).items():
            if name in present:continue
            try:rows_.append(fetch_selected(provider,name,cap,aggregate))
            except Exception as e:
                if getattr(getattr(e,'response',None),'status_code',None)!=404:raise
                missing.append(name)
    need(sum(r['bytes'] for r in rows_)<=aggregate,'selected_aggregate')
    cp=checkpoint_observation(provider,m,terminal) if terminal is not None else None
    after=poll(provider,m,l);need(before['status']==after['status'] and after['gpu_stop'] is False,'terminal_collection_bracket')
    receipt={'format':'irisx/rlvr-selected-retrieval-v1','manifest_sha256':args.manifest_sha,'reference':REF,'kernel_id':138123872,'numeric_output_version':29,'launch_receipt_sha256':file_sha(STATE/'notebook-rlvr002-receipt.json'),'before':before,'after':after,'files':rows_,'inventory_scope':'selected_outputs_only','whole_provider_inventory_verified':False,'missing_paths':sorted(set(missing)),'checkpoint_downloaded':False,'checkpoint_archive_observation':cp,'checkpoint_provider_path':t['checkpoint_path'],'checkpoint_numeric_version':29,'collected_epoch':time.time()}
    rp=OUT/f'retrieval-{time.time_ns()}.json';write_new(rp,receipt)
    absent=sorted(required-{r['provider_path'] for r in rows_})
    if cp is not None and cp['transport_observation']=='PENDING_HTTP404':absent.append(t['checkpoint_path'])
    if absent:
        result={'status':'INCOMPLETE_DIAGNOSTIC_EVIDENCE','provider_status':before['status'],'missing':absent,'retrieval_receipt':descriptor(rp),'terminal_validated':False,'operational_success':False,'goal_met':False,'automatic_retry':False}
        event('incomplete-outputs',result)
        if final_incomplete:write_new(OUT/'TERMINAL-BLOCKER.json',result);return result
        raise IndexingPending('selected_numeric_outputs_pending_or_missing')
    need(terminal is not None and terminal.get('archive_complete') is True,'terminal_archive_incomplete')
    wrappers=wrapper_gate(m,args,f,outer,prefix)
    collection_path,release_root=assemble_consumer_envelope(m,args,f,receipt,terminal,present[t['evidence_path']],present[t['terminal_path']],prefix,outer,cp)
    report=validate_received(m,args,collection_path,release_root,DOWNLOADS/t['evidence_path'],DOWNLOADS/t['terminal_path'])
    raw=write_new(OUT/'TERMINAL-CONSUMER-RAW.json',report)
    report=validation_gate(report,before['status'],wrappers['closure_valid'],wrappers['operational'])
    report.update(separate_checkpoint_presence='UNKNOWN' if cp is None else cp['transport_observation'],inventory_scope='selected_outputs_only',whole_provider_inventory_verified=False,checkpoint_archive_observation=cp,independent_checkpoint_tensor_verification=False,raw_consumer_result=raw,deployment_closures=wrappers)
    write_new(OUT/'RETRIEVAL-RECEIPT.json',receipt);write_new(OUT/'TERMINAL-VALIDATION.json',report)
    checkpoint={'status':'TERMINAL_EVIDENCE_VERIFIED','provider_status':before['status'],'operational_success':report['operational_success'],'comparison_complete':report['comparison_complete'],'compute_matched':report['compute_matched'],'comparison_eligible':report['comparison_eligible'],'public_benchmark_evidence_eligible':report['public_benchmark_evidence_eligible'],'goal_met':report['goal_met'],'public_goal_met':report['public_goal_met'],'validation':descriptor(OUT/'TERMINAL-VALIDATION.json'),'retrieval':descriptor(OUT/'RETRIEVAL-RECEIPT.json'),'dispatch_epoch':j['dispatch_epoch'],'predispatch_epoch':f['predispatch_epoch'],'last_observed_terminal_epoch':after['observed_epoch'],'observed_dispatch_to_terminal_seconds':after['observed_epoch']-j['dispatch_epoch'],'timing_scope':'Observed wall includes queue, status lag and collection; billing unverified.','provider_vm_or_billing_state_verified':False,'automatic_retry':False,'inventory_scope':'selected_outputs_only','whole_provider_inventory_verified':False,'checkpoint_archive_observation':cp,'independent_checkpoint_tensor_verification':False}
    write_new(OUT/'TERMINAL-CHECKPOINT.json',checkpoint);return checkpoint

def retry_delay(result,count):
    need(result['classification']=='TRANSIENT','non_transient_no_retry')
    return max(min(300,30*2**min(count-1,4)),result.get('retry_after_seconds') or 0)

def watch(provider,m,l,j,f,args):
    failures={'poll':0,'collect':0};terminal_seen=None
    while True:
        try:
            snap=poll(provider,m,l);failures['poll']=0
        except Exception as e:
            r=failure(e,'poll')
            if r['sprint_stop'] or r['classification']!='TRANSIENT':write_new(OUT/'WATCH-BLOCKER.json',r);return 2
            failures['poll']+=1;print(json.dumps(r),flush=True);time.sleep(retry_delay(r,failures['poll']));continue
        if snap['gpu_stop']:
            write_new(OUT/'WATCH-BLOCKER.json',{'status':'GPU_UNAVAILABLE_STOP','snapshot':snap,'automatic_retry':False});return 3
        if snap['status'] not in TERMINAL:
            if time.time()>f['deadline_epoch']:event('deadline-status-unproven',{'snapshot':snap,'original_deadline_epoch':f['deadline_epoch'],'no_relaunch':True})
            time.sleep(60);continue
        if terminal_seen is None:terminal_seen=time.monotonic()
        try:
            result=collect(provider,m,l,j,f,args,snap,final_incomplete=time.monotonic()-terminal_seen>=600)
            print(json.dumps(result),flush=True)
            return 0 if result['status']=='TERMINAL_EVIDENCE_VERIFIED' else 4
        except IndexingPending:
            failures['collect']+=1;time.sleep(min(120,15*2**min(failures['collect']-1,3)))
        except Exception as e:
            r=failure(e,'collect')
            # Scientific verification errors are terminal blockers, never another RUN.
            if type(e).__name__ in ('ValidationError','EvidenceError') or isinstance(e,ValueError):
                r['classification']='TERMINAL_VERIFICATION_BLOCKED';r['message']=clean_message(str(e))
            if r['sprint_stop'] or r['classification']!='TRANSIENT':write_new(OUT/'WATCH-BLOCKER.json',r);print(json.dumps(r),flush=True);return 2
            failures['collect']+=1;print(json.dumps(r),flush=True);time.sleep(retry_delay(r,failures['collect']))

def main():
    p=transport.parser();p._actions[1].choices=['poll','collect','watch']
    args=p.parse_args();provider=None
    try:
        m,l,j,f=bindings(args)
        transport.execution_gate(args,monitor=True)
        secure_path(OUT);OUT.mkdir(parents=True,exist_ok=True)
        need(not (OUT/'TERMINAL-CHECKPOINT.json').exists(),'terminal_already_collected')
        with lock('collector'):
            provider=Provider()
            if args.action=='poll':print(json.dumps(poll(provider,m,l)));return 0
            if args.action=='collect':print(json.dumps(collect(provider,m,l,j,f,args)));return 0
            return watch(provider,m,l,j,f,args)
    except Exception as e:
        r=failure(e,args.action)
        if type(e).__name__ in ('ValidationError','EvidenceError') or isinstance(e,ValueError):r['message']=clean_message(str(e));r['classification']='TERMINAL_VERIFICATION_BLOCKED'
        print(json.dumps(r));return 2
    finally:
        if provider:provider.close()
if __name__=='__main__':raise SystemExit(main())
