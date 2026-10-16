"""Source-fixed training numeric diagnostic publication, using the legacy run008 wire schema.

The consumed run006 transport and every earlier publication remain unchanged.
These local successor bytes retain the source-only, official-auth action gates.
Official local SDK calls remain bounded, write-once and review-gated. Decision0075 admits terminal monitoring and exact selected-output retrieval.
No automatic relaunch is supported.
"""
import argparse, ast, contextlib, hashlib, json, math, os, stat, subprocess, sys, time, types, zipfile
from pathlib import Path

# Acyclic local dependency pin. Compile source before any authentication or RPC.
COMMON_SOURCE_SHA256 = '833d6d1dfcd78224a0f7a214d611e6143383f9d3b0b38ae4d4b4c891f388950e'
_common_path=Path(__file__).absolute().with_name('operator_common.py')
if any(p.is_symlink() for p in (_common_path,*_common_path.parents)) or not stat.S_ISREG(_common_path.stat().st_mode):
    raise ValueError('unsafe_local_common_source')
with _common_path.open('rb') as _f:_common_raw=_f.read(1024**2+1)
if len(_common_raw)>1024**2 or hashlib.sha256(_common_raw).hexdigest()!=COMMON_SOURCE_SHA256:
    raise ValueError('local_common_source_pin')
_common=types.ModuleType('reviewed_rl_operator_common');_common.__file__=str(_common_path);_common.__package__=''
exec(compile(_common_raw,str(_common_path),'exec',dont_inherit=True,optimize=sys.flags.optimize),_common.__dict__)
globals().update({k:v for k,v in _common.__dict__.items() if not k.startswith('_')})

FORMAT='irisx/qwen14b-rlvr-run008-publication-contract-v1'
RUN_PURPOSE='training-only-numeric-diagnostic-v1'
V37_SAVED_SOURCE='dd849708ac6c13ccaba5341427b3f700b05123dd857999f41c24e192a7f7ea65'
V35_SAVED_SOURCE='778c014ccea8b0f376d06afeeeceb318e50b3bce926ef13a6da068c9b3d5d917'
OLD_SOURCE=None
DOCKER='gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f'
NON_CODE_PINS=['danielwuu/iris-x-public120-data-20261010/1','danielwuu/iris-x-learning-training-20261011/1','danielwuu/iris-arc-next-runtime/8','danielwuu/iris-arc-granite42-8b-offline/2','danielwuu/iris-arc-next-cu128-cp312-wheels/1','danielwuu/iris-arc-next-cpython312-offline/2','danielwuu/iris-arc-granite42-run003-adapter-20261009/1']
PINS=None
SCRIPT=Path(__file__).resolve()
OPERATOR_SOURCE_NAMES = ('config.py', 'native_auth.py', 'sdk-lock.json',
    'operator_common.py', 'rl_transport.py', 'rl_collect.py', 'launch.py',
    'bridge_client.py', 'protocol.py', 'native_config.py', 'sdk_worker.py',
    'win_runtime.py', 'win_supervisor.py', 'native_probe.py', 'verify_active_wire.py',
    'recovery_epoch.py', 'recovery_boot_probe.py', 'recovery_entry.py',
    'context_continuation.py', 'context-source-pins.json', 'preworker_disposition.py',
    'publication_state.py')

# Allocation comes from the independently hash-bound live local configuration.
# Historical code18/v35 evidence is validated separately and never relabelled.
CODE_PREDECESSOR=CODE_VERSION=NOTEBOOK_PREDECESSOR=INACTIVE_VERSION=ACTIVE_VERSION=None
RUN_PATH='/kaggle/working/irisx-qwen14b-numeric-diagnostic-20261016-run001'
SOURCE_PATH='/kaggle/working/irisx-qwen14b-numeric-diagnostic-20261016-source001'
ENVIRONMENT_PATH='/tmp/irisx-qwen14b-numeric-diagnostic-20261016-environment001'
FROZEN_TRANSPORT_SHA256='990f272eed0f243c9fff1a3d61f96a280c875e6bc8e31e5dfdb1aa4690b32eed'
RUN006_LINEAGE_HELPER_SHA='0e1dae66529831ae719da5bc0d36bf300a11bdc07734416bb9ff8490d1d77cfe'
V35_LINEAGE_HELPER_SHA='f3cc35d60fd5f5aaa173feeb824120ff6ed18fea6a8aaba0f3368a973215e2b8'
SNAPSHOT_COMMIT='e951604b829497e81bc6e18b32662ff050bd54db'
REMOTE_PREDECESSOR=None

def code_claim_name():return f'dataset-code-v{CODE_VERSION}'
def code_state(suffix):return publication_root()/(code_claim_name()+suffix)
def profile_versions():
    return {'code_predecessor':CODE_PREDECESSOR,'code':CODE_VERSION,
            'inactive_predecessor':NOTEBOOK_PREDECESSOR,'inactive':INACTIVE_VERSION,'active':ACTIVE_VERSION}


def rows(m):return {r['role']:r for r in m['notebooks']}
def row(m,role):return rows(m)[role]
def clock(epoch):return {'dispatch_epoch':epoch,'predispatch_epoch':epoch,'deadline_epoch':epoch+43200,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'outer_deadline_epoch':epoch+42180,'provider_timeout_seconds':42300}
def predecessor_proof(m,root):
    """Execute the exact frozen code18 validator, preserving all v33/v31 gates."""
    path=SCRIPT.parent.parent/'publication_run005/rl_transport.py'
    historical=load_source_module('run006_frozen_code18_history',path,FROZEN_TRANSPORT_SHA256)
    return historical.predecessor_proof(m,root)

def original_v35_dispatch_proof(m,root):
    """Replay authentic historical v35 dispatch; never assert runtime closure."""
    d=m['v35_original_dispatch_chain'];h=m['v35_launch_lineage_verifier']
    need(type(d)is dict and set(d)=={'path','bytes','sha256'} and type(h)is dict and set(h)=={'path','bytes','sha256'},'v35_lineage_descriptor_schema')
    relative(d['path']);relative(h['path'])
    need(Path(d['path']).name=='LAUNCH-LINEAGE.json','v35_lineage_document_name')
    need(h['sha256']==V35_LINEAGE_HELPER_SHA,'v35_lineage_verifier_review_pin')
    verified(root/d['path'],d['sha256'],d['bytes'],4*1024**2)
    verified(root/h['path'],h['sha256'],h['bytes'],1024**2)
    helper=load_source_module('reviewed_v35_lineage_'+h['sha256'],root/h['path'],h['sha256'],1024**2)
    proof=helper.verify((root/d['path']).parent,d['sha256'])
    need(type(proof)is dict and proof['format']=='irisx/run006-original-v35-launch-lineage-v1' and proof['status']=='ORIGINAL_DISPATCH_LINEAGE_VERIFIED_NO_RUNTIME_CLOSURE','v35_lineage_verified_result')
    need(proof['notebook_version']==35 and proof['code_version']==18 and proof['saved_source_sha256']==V35_SAVED_SOURCE,'v35_original_launch_identity')
    need(type(proof['original_epoch'])is int and proof['original_epoch']==1791871874 and type(proof['original_deadline'])is int and proof['original_deadline']==1791915074,'v35_original_launch_clock')
    need(proof['v35_original_dispatch_chain_verified'] is True and m['v35_original_dispatch_chain_verified'] is True,'v35_actual_dispatch_verification_required')
    need(all(proof[k] is False for k in ('runtime_or_model_closure_verified','physical_costs_known','manual_failure_root_cause_verified','scientific_result_verified')),'v35_launch_not_runtime_closure')
    need(proof['code18_publication_manifest_sha256']=='76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca' and proof['code18_assembly_inventory_sha256']=='de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0','v35_original_release_identity')
    need(proof['provider_calls']==0 and proof['model_or_GPU_calls']==0,'v35_local_replay_only')
    return proof

def original_v37_dispatch_proof(m,root):
    """Replay exact consumed run006 dispatch without asserting GPU success."""
    d=m['run006_original_dispatch_chain'];h=m['run006_launch_lineage_verifier']
    need(type(d)is dict and set(d)=={'path','bytes','sha256'} and type(h)is dict and set(h)=={'path','bytes','sha256'},'v37_lineage_descriptor_schema')
    relative(d['path']);relative(h['path'])
    need(Path(d['path']).name=='LAUNCH-LINEAGE.json','v37_lineage_document_name')
    need(h['sha256']==RUN006_LINEAGE_HELPER_SHA,'v37_lineage_verifier_review_pin')
    verified(root/d['path'],d['sha256'],d['bytes'],4*1024**2)
    helper=load_source_module('reviewed_run006_lineage_'+h['sha256'],root/h['path'],h['sha256'],1024**2)
    proof=helper.verify((root/d['path']).parent,d['sha256'])
    need(type(proof)is dict and proof['format']=='irisx/run007-original-v37-launch-lineage-v1' and proof['status']=='ORIGINAL_DISPATCH_LINEAGE_VERIFIED_NO_RUNTIME_CLOSURE','v37_lineage_verified_result')
    need(proof['notebook_version']==37 and proof['code_version']==19 and proof['saved_source_sha256']==V37_SAVED_SOURCE,'v37_original_launch_identity')
    need(type(proof['original_epoch'])is int and proof['original_epoch']==1791901490 and type(proof['original_deadline'])is int and proof['original_deadline']==1791944690,'v37_original_launch_clock')
    need(proof['v37_original_dispatch_chain_verified'] is True and m['run006_original_dispatch_chain_verified'] is True,'v37_actual_dispatch_verification_required')
    need(all(proof[k] is False for k in ('runtime_or_model_closure_verified','scientific_result_verified','physical_costs_known','manual_failure_root_cause_verified')),'v37_launch_not_runtime_success')
    need(proof['code19_publication_manifest_sha256']=='7212b5c46f6c350617a4d3037788996d6e19fa349691b6b78a245d84898cfe62' and proof['code19_assembly_inventory_sha256']=='85a270c4fcacbe99c012b860fcd25f6b9d909df7c1aa17075c462a68c892277a','v37_original_release_identity')
    need(proof['provider_calls']==0 and proof['model_or_GPU_calls']==0,'v37_local_replay_only')
    return proof


def strict_object(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate_json_key');result[key]=value
        return result
    def finite(token):
        value=float(token);need(math.isfinite(value),'nonfinite_json');return value
    result=json.loads(raw,object_pairs_hook=pairs,parse_float=finite,parse_constant=lambda _:need(False,'nonfinite_json'))
    need(type(result)is dict,'json_object_required');return result

def current_predecessor_proof(m,root):
    """Bind a new official live readback, preserving the original v35 lineage."""
    d=m['current_predecessor_observation'];relative(d['path'])
    need(set(d)=={'path','bytes','sha256'} and d['sha256']==REMOTE_PREDECESSOR['snapshot_sha256'],'current_observation_descriptor')
    proof=strict_object(verified(root/d['path'],d['sha256'],d['bytes'],4*1024**2));base=(root/d['path']).parent
    if proof.get('format')=='irisx/run008-native-current-predecessor-observation-v1':
        closed=proof['closed_files'];evidence=proof['evidence']
        need(type(closed)is dict and type(evidence)is dict and 0<len(closed)<=12000,'current_closed_inventory')
        raw={}
        for name,desc in evidence.items():
            need(type(desc)is dict and set(desc)=={'path','bytes','sha256'},'current_evidence_descriptor');relative(desc['path'])
            need(closed.get(desc['path'])=={'bytes':desc['bytes'],'sha256':desc['sha256']},'current_evidence_inventory_link')
            raw[name]=verified(base/desc['path'],desc['sha256'],desc['bytes'],4*1024**2)
        need(len({desc['path'] for desc in evidence.values()})==len(evidence),'current_duplicate_evidence_path')
        actual=set()
        for path in secure_path(base).rglob('*'):
            secure_path(path);need(path.is_dir() or stat.S_ISREG(path.stat().st_mode),'current_special_entry')
            if path.is_file():actual.add(path.relative_to(base).as_posix())
        need(actual==set(closed)|{Path(d['path']).name},'current_closed_directory')
        for name,row_ in closed.items():
            relative(name);verified(base/name,row_['sha256'],row_['bytes'],4*1024**2)
        need({'saved_source','notebook_before','notebook_after','dataset_before','dataset_after'}<=set(raw),'current_required_raw_readbacks')
        before=strict_object(raw['notebook_before']);after=strict_object(raw['notebook_after'])
        dataset_before=strict_object(raw['dataset_before']);dataset_after=strict_object(raw['dataset_after']);saved=raw['saved_source']
    else:
        need(proof.get('format')=='irisx/run008-live-predecessor-observation-v1','current_observation_schema')
        before=strict_object(verified(base/'metadata-before.json',proof['metadata_before_sha256'],cap=4*1024**2))
        after=strict_object(verified(base/'metadata-after.json',proof['metadata_after_sha256'],cap=4*1024**2))
        dataset_before=strict_object(verified(base/'dataset.json',proof['dataset_metadata_sha256'],cap=4*1024**2))
        dataset_after=strict_object(verified(base/'dataset-after.json',proof['dataset_after_sha256'],cap=4*1024**2))
        status=strict_object(verified(base/'status.json',proof['status_sha256'],cap=65536))
        need(status['status']==proof['provider_status'],'current_status_evidence')
        saved=verified(base/'saved_source.ipynb',proof['saved_source_sha256'],cap=4*1024**2)
    need(proof['code_version']==CODE_PREDECESSOR and proof['notebook_version']==NOTEBOOK_PREDECESSOR and proof['saved_source_sha256']==OLD_SOURCE,'current_observation_identity')
    need(proof['provider_status']==REMOTE_PREDECESSOR['provider_status'] and proof['provider_status'] in TERMINAL and proof.get('gpu_unavailable_stop',False) is False,'current_terminal_not_gpu_stop')
    need(type(proof['observed_epoch'])in (int,float) and math.isfinite(proof['observed_epoch']) and proof['observed_epoch']>0,'current_observation_epoch')
    need(all(proof[k] is False for k in ('runtime_closure_verified','manual_failure_root_cause_verified','manual_editor_session_mapping_verified','scientific_result_verified','physical_costs_known')),'current_no_invented_runtime_proof')
    need(sha(saved)==OLD_SOURCE,'current_saved_source')
    prior_pins=[DREF+'/'+str(CODE_PREDECESSOR),*NON_CODE_PINS]
    for meta in (before,after):
        need(meta['id']==138123872 and meta['ref']==REF and meta['currentVersionNumber']==NOTEBOOK_PREDECESSOR and meta['isPrivate'] is True,'current_raw_notebook_identity')
        need(meta['enableGpu'] is True and meta.get('enableInternet',False) is False and meta.get('enableTpu',False) is False and meta['dockerImage']==DOCKER and meta['machineShape']=='NvidiaRtxPro6000' and meta['modelDataSources'] in MODEL_ALIASES and not meta.get('kernelDataSources'),'current_raw_settings')
        need(sorted(meta['datasetDataSources'])==sorted('/'.join(x.split('/')[:2]) for x in prior_pins) and meta['competitionDataSources']==['arc-prize-2026-arc-agi-3'],'current_raw_mount_identities')
    for meta in (dataset_before,dataset_after):
        need(meta['id']==12504696 and meta['ref']==DREF and meta['currentVersionNumber']==CODE_PREDECESSOR and meta['isPrivate'] is True,'current_raw_dataset_identity')
    if CODE_PREDECESSOR==18 and NOTEBOOK_PREDECESSOR==35:
        cfg=config(saved)
        need(OLD_SOURCE==V35_SAVED_SOURCE and cfg['PREDISPATCH_EPOCH']==1791871874 and cfg['OUTPUT_ROOT']=='/kaggle/working/irisx-qwen14b-rlvr-20261012-run005' and cfg['SOURCE_PARENT']=='/kaggle/working/irisx-qwen14b-rlvr-20261012-source005','current_original_v35_source_clock')
        need(cfg['SESSION_SECONDS']==43200 and cfg['EXECUTION_CUTOFF_SECONDS']==42000 and cfg['OUTER_CUTOFF_SECONDS']==42180 and cfg['PROVIDER_RUNTIME_SECONDS']==42300,'current_original_v35_limits')
    elif CODE_PREDECESSOR==19 and NOTEBOOK_PREDECESSOR==37:
        cfg=config(saved)
        need(OLD_SOURCE==V37_SAVED_SOURCE and cfg['PREDISPATCH_EPOCH']==1791901490 and cfg['OUTPUT_ROOT']=='/kaggle/working/irisx-qwen14b-rlvr-20261013-run006' and cfg['SOURCE_PARENT']=='/kaggle/working/irisx-qwen14b-rlvr-20261013-source006','current_original_v37_source_clock')
        need(cfg['SESSION_SECONDS']==43200 and cfg['EXECUTION_CUTOFF_SECONDS']==42000 and cfg['OUTER_CUTOFF_SECONDS']==42180 and cfg['PROVIDER_RUNTIME_SECONDS']==42300,'current_original_v37_limits')
    a=m['owner_session_stop_attestation'];relative(a['path'])
    owner=strict_object(verified(root/a['path'],a['sha256'],a['bytes'],65536))
    diagnostic_owner_scope(owner)
    return proof


def diagnostic_owner_scope(owner):
    """One immutable training-only purpose; original scorer counts are reference only."""
    need(owner.get('format') == 'irisx/numeric-diagnostic-owner-direction-v1'
         and owner.get('owner_id') == 'danielwuu', 'current_owner_direction_identity')
    need(owner.get('run_purpose') == RUN_PURPOSE and owner.get('training_only') is True
         and owner.get('rl_optimizer_commit_authorized') is False
         and owner.get('later_B_C_dev_holdout_PUBLIC_authorized') is False, 'fixed_diagnostic_owner_scope')
    need(owner.get('one_accepted_run_per_distinct_reviewed_candidate') is True
         and owner.get('continuous_monitoring_authorized') is True
         and owner.get('result_retrieval_authorized') is True, 'current_owner_one_submit_scope')
    need(owner.get('session_limit_seconds') == 43200 and owner.get('original_public_task_count') == 120
         and owner.get('original_public_query_denominator') == 167, 'original_clock_reference_scorer_scope')
    for key in ('gpu_quota_query_authorized', 'new_resource_or_paid_provisioning_authorized',
                'official_competition_submission_authorized', 'legal_agreement_acceptance_authorized',
                'credential_or_permission_changes_authorized_by_this_file', 'runtime_or_scientific_success_claim'):
        need(owner.get(key) is False, 'current_owner_resource_science_scope: ' + key)


def descriptor_at(root,d,cap=128*1024**2):
    relative(d['path']);return verified(root/d['path'],d['sha256'],d['bytes'],cap)

def contract(manifest, allow_preview=False):
    m=obj(manifest);root=Path(manifest).resolve().parent
    need(m['format']==FORMAT,'manifest_format')
    need(m.get('run_purpose')==RUN_PURPOSE,'fixed_diagnostic_manifest_purpose')
    need(allow_preview or m['source_review_only'] is False and m.get('run_authorized') is True and m.get('release_runtime_finalized') is True,'unapproved_preview')
    need(m['candidate_git_published'] is False and m['git_gate_required'] is False and m['owner_published_stable_commit']==SNAPSHOT_COMMIT,'git_provenance')
    scope=m.get('local_reconstruction',{})
    need(scope.get('stop_after_submit_readback') is False and scope.get('provider_monitoring_authorized') is True,'owner_stop_after_submit_scope')
    verified(root/'SOURCE-FREEZE.json',m['source_freeze_sha256']);predecessor_proof(m,root)
    current_predecessor_proof(m,root);original_v35_dispatch_proof(m,root);original_v37_dispatch_proof(m,root)
    descriptor_at(root,m['parent_wrapper_verifier'])
    need(m['upload_authorities']==['https://storage.googleapis.com:443','https://www.googleapis.com:443'],'source_bound_upload_authorities')
    need(len(m['datasets'])==1 and set(rows(m))=={'inactive','rlvr004'},'exact_publication_scope')
    d=m['datasets'][0];need(d['id']==12504696 and d['reference']==DREF and d['expected_predecessor_version']==CODE_PREDECESSOR and d['expected_version']==CODE_VERSION and d['is_private'] is True and d['new_only'] is False and d.get('delete_old_versions') is False,'dataset_identity_version')
    inv={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in d['upload_inventory']}
    need({'NOTICE.txt','manifest.json','source.zip'}<=set(inv) and len(inv)==len(d['upload_inventory'])<=2000,'upload_inventory')
    for name,v in inv.items():relative(name);verified(root/d['payload_root']/name,v['sha256'],v['bytes'])
    a=d['transport_archive'];descriptor_at(root,a);need(check_zip(root/a['path'],128*1024**2,2000,{'source.zip'})==inv,'closed_upload_zip')
    jit=m['jit'];need(jit['format']=='irisx/rlvr-pure-finalizer-contract-v1' and jit['maximum_dispatch_age_seconds']==60,'jit_contract')
    need(set(jit['output_documents'])=={'active-finalized.ipynb','original-request.json','operator.json','parent-private-scorer.json'},'closed_jit_outputs')
    descriptor_at(root,jit['entry']);need({d['path'] for d in jit['dependencies']}=={'notebook-release.json','code-payload/deployment/notebook_builder.py','code-payload/deployment/source_loader.py'} and len(jit['dependencies'])==3,'closed_jit_input_dependencies')
    for dd in jit['dependencies']:descriptor_at(root,dd)
    terminal=m['terminal_contract'];caps=terminal['archive_caps']
    need(caps['evidence_expanded_bytes']==5*1024**3 and caps['evidence_archive_bytes']==5*1024**3+16*1024**2 and caps['checkpoint_archive_bytes']==4*1024**3 and caps['members']==12000 and caps['json_bytes']==2*1024**3 and caps['journal_bytes']==3276800000 and caps['free_disk_reserve_bytes']==4*1024**3,'rl_source_storage_bounds')
    storage=terminal['storage'];expected_saved=2*5*1024**3+16*1024**2+2*4*1024**3+128*1024**2
    need(storage['saved_auxiliary_allowance_bytes']==128*1024**2 and storage['saved_working_upper_bytes']==expected_saved and storage['provider_saved_output_limit_bytes']==20000000000 and storage['saved_limit_headroom_bytes']==20000000000-expected_saved,'reviewed_saved_output_bound')
    need(storage['environment_root']==ENVIRONMENT_PATH and storage['environment_saved'] is False and storage['co_resident_peak_plus_reserve_bytes']==expected_saved+4*1024**3,'temporary_environment_storage_policy')
    need(terminal['inventory_scope']=='selected_outputs_only' and terminal['checkpoint_default_mode']=='header-only' and terminal['zip64'] is True,'rl_collection_scope')
    need(terminal['evidence_path']==Path(RUN_PATH).name+'.evidence.zip' and terminal['terminal_path']==terminal['evidence_path']+'.terminal.json' and terminal['checkpoint_path']==Path(RUN_PATH).name+'/checkpoints.zip','rl_output_paths')
    consumer=m['consumer_contract'];need(consumer['format']=='irisx/rlvr-independent-consumer-contract-v1','consumer_contract')
    for key in ('release','material_review','environment','phase_policy','owner_protocol','source_archive'):descriptor_at(root,consumer[key])
    relative(consumer['source_root'])
    need(consumer['source_sha256']==m['runtime_source_sha256'] and re.fullmatch('[0-9a-f]{64}',consumer['dataset_sha256']) is not None,'consumer_source_dataset_pins')
    for role in ('inactive','rlvr004'):
        n=row(m,role);active=role=='rlvr004'
        need(n['existing_notebook_id']==138123872 and n['existing_notebook_reference']==REF,'notebook_identity')
        need(n['expected_version']==(ACTIVE_VERSION if active else INACTIVE_VERSION) and n['expected_predecessor_version']==(INACTIVE_VERSION if active else NOTEBOOK_PREDECESSOR),'notebook_version')
        need(n['save_version_value']==(1 if active else 3) and n['save_mode']==('RUN' if active else 'QUICK_SAVE'),'save_mode')
        need(n['dataset_sources']==PINS and n['model_sources']==[MODEL] and n['competition_sources']==['arc-prize-2026-arc-agi-3'],'pinned_input_sources')
        need(n['is_private'] is True and n['enable_gpu'] is active and n['enable_tpu'] is False and n['enable_internet'] is False and n['docker_image']==DOCKER,'private_accelerator_settings')
        need(n['machine_shape']==('NvidiaRtxPro6000' if active else None) and n['session_timeout_seconds']==(42300 if active else None),'machine_timeout')
        need(n['title']=='IRIS-X Learning Agent 20261011' and n['language']=='python' and n['kernel_type']=='notebook','notebook_schema')
        if active:need(allow_preview or n['run_authorized'] is True,'active_not_authorized')
        else:need(n['run_authorized'] is False and n['predecessor_source_sha256']==OLD_SOURCE,'inactive_predecessor')
        raw=descriptor_at(root,n);c=config(raw)
        expected={'MANUAL_START':False,'ENABLE_MODEL':False,'PROFILE':'QWEN14B_RLVR12H','PREDISPATCH_EPOCH':None,'SESSION_SECONDS':43200,'PROBE_SECONDS':43200,'EXECUTION_CUTOFF_SECONDS':42000,'OUTER_CUTOFF_SECONDS':42180,'PROVIDER_RUNTIME_SECONDS':42300,'OUTPUT_ROOT':RUN_PATH,'SOURCE_PARENT':SOURCE_PATH,'NOTEBOOK_KIND':'active-template' if active else 'inactive'}
        need(all(c.get(k)==v and type(c.get(k))is type(v) for k,v in expected.items()),'inert_template_config')
        need(n['output_root']==c['OUTPUT_ROOT'] and n['source_parent']==c['SOURCE_PARENT'],'namespace_binding')
    return m

def finalized_documents(m,manifest,epoch):
    """Pure reviewed reconstruction; never patch an old active source."""
    need(type(epoch)is int and epoch>0,'fresh_integer_epoch')
    root=Path(manifest).resolve().parent;jit=m['jit'];path=root/jit['entry']['path']
    descriptor_at(root,jit['entry'])
    for d in jit['dependencies']:descriptor_at(root,d)
    module=load_source_module('reviewed_rlvr_jit_'+jit['entry']['sha256'],path,jit['entry']['sha256'])
    result=module.finalize(root,epoch)
    need(type(result)is dict and set(result)==set(jit['output_documents']) and all(type(v)is bytes and len(v)<=4*1024**2 for v in result.values()),'finalizer_closed_return')
    cfg=config(result['active-finalized.ipynb'])
    need(cfg['MANUAL_START'] is True and cfg['ENABLE_MODEL'] is True and cfg['PREDISPATCH_EPOCH']==epoch and cfg['NOTEBOOK_KIND']=='active-finalized','finalizer_explicit_admission')
    owner=json.loads(result['original-request.json']);operator=json.loads(result['operator.json']);notebook=json.loads(result['active-finalized.ipynb']);parent=json.loads(result['parent-private-scorer.json'])
    need(owner['format']=='owned-rl-original-owner-request-v1' and owner['scope']=='production-rl-abc' and owner['role']=='rl-abc' and owner['original_epoch']==epoch,'owner_request_contract')
    need(operator['format']=='owned-rl-reviewed-operator-v2' and operator['original_epoch']==epoch and operator['raw_source_sha256']==m['runtime_source_sha256'],'runtime_operator_binding')
    need(operator['source_archive_sha256']==m['consumer_contract']['source_archive']['sha256'] and operator['material_review_sha256']==m['consumer_contract']['material_review']['sha256'],'runtime_operator_release_pins')
    need(operator['original_request_sha256']==sha(result['original-request.json']) and operator['parent_scorer_sha256']==sha(result['parent-private-scorer.json']),'finalized_document_chain')
    need(notebook['metadata']['owned_rl_release']=={'format':'owned-rl-outer-notebook-v1','operator_sha256':sha(result['operator.json'])},'finalized_notebook_operator_binding')
    need(parent['original_request_sha256']==sha(result['original-request.json']) and parent['raw_source_sha256']==m['runtime_source_sha256'],'parent_private_source_owner')
    return result

def check_finalization(m,args,f):
    need(f['manifest_sha256']==args.manifest_sha and f['format']=='irisx/rlvr-finalization-v1','finalization_manifest')
    docs=finalized_documents(m,args.manifest,f['predispatch_epoch'])
    need(set(f['documents'])==set(docs),'finalization_documents')
    for name,raw in docs.items():
        d=f['documents'][name];need(d['path']==str(publication_root()/name) and d['sha256']==sha(raw) and d['bytes']==len(raw),'finalization_descriptor')
        need(read(publication_root()/name,4*1024**2)==raw,'finalization_reconstruction')
    need(f['finalized_sha256']==sha(docs['active-finalized.ipynb']),'finalized_notebook_hash')
    return docs


def review_gate(path,digest,manifest_sha,material_sha,required):
    r=json.loads(verified(path,digest));need(r.get('local_config_sha256')==CONFIG.document_sha256,'local_review_config_binding');need(r['status']=='PASS' and r['publication_manifest_sha256']==manifest_sha and r['material_approval_sha256']==material_sha,'operator_review_binding')
    need(type(r.get('operator_files')) is dict and set(OPERATOR_SOURCE_NAMES) <= set(r['operator_files']), 'complete_bridge_operator_review_required')
    for p in [*required, *(SCRIPT.with_name(name) for name in OPERATOR_SOURCE_NAMES)]:need(r['operator_files'][p.name]==file_sha(p),'operator_bytes_not_reviewed')
    return r

def configure_local(args):
    global CODE_PREDECESSOR,CODE_VERSION,NOTEBOOK_PREDECESSOR,INACTIVE_VERSION,ACTIVE_VERSION,PINS,OLD_SOURCE,REMOTE_PREDECESSOR
    _common.configure(args.local_config,args.local_config_sha,args.manifest,args.manifest_sha)
    globals().update({k:v for k,v in _common.__dict__.items() if not k.startswith('_')})
    need(CONFIG.runtime is not None,'reviewed_posix_runtime_required')
    need(STATE==CONFIG.scratch_root/'state-run008' and CONFIG.evidence_root==CONFIG.scratch_root/'evidence-run008','run008_fresh_state_namespace')
    versions=dict(CONFIG.versions)
    CODE_PREDECESSOR,CODE_VERSION,NOTEBOOK_PREDECESSOR,INACTIVE_VERSION,ACTIVE_VERSION=(versions[k] for k in ('code_predecessor','code','inactive_predecessor','inactive','active'))
    need(CODE_PREDECESSOR>=20 and NOTEBOOK_PREDECESSOR>=39,'live_allocation_precedes_consumed_run006')
    PINS=[DREF+'/'+str(CODE_VERSION),*NON_CODE_PINS]
    document=obj(args.local_config)
    REMOTE_PREDECESSOR=document['remote_predecessor']
    OLD_SOURCE=REMOTE_PREDECESSOR['notebook_source_sha256']
    if CODE_PREDECESSOR==20 and NOTEBOOK_PREDECESSOR==39:
        need(OLD_SOURCE=='a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9','original_v39_source_mismatch')

def load_contract(args):
    configure_local(args)
    verified(args.manifest,args.manifest_sha);m=contract(args.manifest)
    material=json.loads(verified(args.material,args.material_sha))
    need(material['status']=='APPROVED' and material['scope']['publication_manifest']['sha256']==args.manifest_sha,'material_approval')
    approved={(n['role'],n['sha256']) for n in material['approved_notebooks']}
    need(all((n['role'],n['sha256']) in approved for n in m['notebooks']),'approved_notebooks')
    review_gate(args.review,args.review_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py')])
    _common.bind_action_review(args.review,args.review_sha)
    publication_guard()
    return m

def publication_preflight(m,args):
    """Check future static dependencies now, without provider, claims or a clock.

    Epoch 1 is only an in-memory deterministic finalizer exercise. None of its
    four outputs is persisted, reviewed for dispatch, or passed to a consumer.
    Numeric readback, mount, inactive, audit and real active-wire gates still
    require their own subsequently observed receipts.
    """
    review=monitor_gate(args)
    root=secure_path(args.consumer_root)
    pins=obj(root/'CONSUMER-OPERATOR.json')
    contract_=m['consumer_contract']
    expected={'source_sha256':contract_['source_sha256'],
        'source_archive_sha256':contract_['source_archive']['sha256'],
        'release_sha256':contract_['release']['sha256'],
        'policy_sha256':contract_['phase_policy']['sha256']}
    need(all(pins.get(key)==value for key,value in expected.items()),'preflight_consumer_release_chain')
    entry=verified(root/'reviewed_entry.py',review['consumer_files']['reviewed_entry.py'])
    tree=ast.parse(entry)
    assignments=[node for node in tree.body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='REVIEWED_OPERATOR_PINS_SHA256'
                for target in node.targets)]
    need(len(assignments)==1 and ast.literal_eval(assignments[0].value)==file_sha(root/'CONSUMER-OPERATOR.json'),
         'preflight_reviewed_entry_operator_pin')
    collector=verified(SCRIPT.with_name('rl_collect.py'),pins['collector_entry_sha256'])
    compiled=compile(collector,str(SCRIPT.with_name('rl_collect.py')),'exec',dont_inherit=True,optimize=sys.flags.optimize)
    need(any(isinstance(code,types.CodeType) and code.co_name=='validate_received'
             for code in compiled.co_consts),'preflight_collector_callsite_present')
    documents=finalized_documents(m,args.manifest,1)
    protocol=load_source_module('reviewed_preflight_protocol',SCRIPT.with_name('protocol.py'),
                               review['operator_files']['protocol.py'])
    upload=m['datasets'][0]['transport_archive']
    protocol.validate_request('start_upload',{'name':Path(upload['path']).name,
        'bytes':upload['bytes'],'sha256':upload['sha256']})
    inactive=row(m,'inactive')
    inactive_raw=descriptor_at(Path(args.manifest).absolute().parent,inactive)
    wire_hashes={}
    for role,raw in (('inactive',inactive_raw),('rlvr004',documents['active-finalized.ipynb'])):
        wire=kernel_wire(row(m,role),raw)
        protocol.validate_request('save',{'wire':wire})
        protocol.canonical({'wire':wire})
        wire_hashes[role]=sha(canonical(wire))
    # Retain only bounded hashes, never synthetic owner/scorer/operator bytes.
    return {'status':'OFFLINE_PUBLICATION_CLOSURE_PASS','provider_calls':0,'state_writes':0,
        **(publication_paths() if STATE is not None else {}),
        'production_dispatch_admitted':False,'actual_epoch_reserved':False,'synthetic_epoch':1,
        'publication_manifest_sha256':args.manifest_sha,'collector_sha256':pins['collector_entry_sha256'],
        'consumer_entry_sha256':sha(entry),'synthetic_finalizer_documents':
            {name:{'bytes':len(raw),'sha256':sha(raw)} for name,raw in sorted(documents.items())},
        'static_wire_sha256':wire_hashes,
        'genuine_numeric_mount_inactive_audit_active_wire_still_required':True}

def settings(meta,n):
    need(meta.id==138123872 and meta.ref==REF and meta.is_private is True,'returned_notebook_identity')
    need(meta.title==n['title'] and meta.language==n['language'] and meta.kernel_type==n['kernel_type'] and meta.kernel_data_sources in (None,[]),'returned_title_type_kernel_sources')
    need(meta.enable_gpu==n['enable_gpu'] and not meta.enable_tpu and not meta.enable_internet,'returned_accelerators')
    need(meta.model_data_sources in MODEL_ALIASES,'returned_model_identity')
    need(sorted(meta.dataset_data_sources)==sorted('/'.join(x.split('/')[:2]) for x in PINS),'returned_dataset_identities')
    need(meta.competition_data_sources==n['competition_sources'] and meta.docker_image==DOCKER,'returned_docker_competition')
    need(meta.machine_shape==('NvidiaRtxPro6000' if n['enable_gpu'] else 'None'),'returned_machine_shape')

def saved_settings(meta,n,version):
    need(meta.get('id')==138123872 and meta.get('ref')==REF and meta.get('currentVersionNumber')==version and meta.get('isPrivate') is True,'saved_metadata_identity')
    need(meta.get('title')==n['title'] and meta.get('language')==n['language'] and meta.get('kernelType')==n['kernel_type'] and meta.get('kernelDataSources') in (None,[]),'saved_metadata_title_type_kernel_sources')
    need(meta.get('enableGpu',False) is n['enable_gpu'] and not meta.get('enableTpu',False) and not meta.get('enableInternet',False),'saved_metadata_accelerators')
    need(meta.get('modelDataSources') in MODEL_ALIASES,'saved_metadata_model')
    need(sorted(meta.get('datasetDataSources',[]))==sorted('/'.join(x.split('/')[:2]) for x in PINS),'saved_metadata_datasets')
    need(meta.get('competitionDataSources')==n['competition_sources'] and meta.get('dockerImage')==DOCKER,'saved_metadata_docker_competition')
    need(meta.get('machineShape')==('NvidiaRtxPro6000' if n['enable_gpu'] else 'None'),'saved_metadata_machine')


def bracket(provider,version,expected_sha=None,n=None):
    before=provider.kernel();status=provider.status();after=provider.kernel()
    need(before.metadata.ref==after.metadata.ref==REF and before.metadata.is_private is True and after.metadata.is_private is True,'bracket_identity_privacy')
    need(before.metadata.id==after.metadata.id==138123872 and before.metadata.current_version_number==after.metadata.current_version_number==version,'saved_version_changed')
    raw=before.blob.source.encode();need(raw==after.blob.source.encode() and len(raw)<=1024**2,'saved_source_changed')
    if expected_sha:need(sha(raw)==expected_sha,'saved_source_identity')
    if n:settings(before.metadata,n);settings(after.metadata,n)
    classification,_=classify(None,status.failure_message)
    if classification=='GPU_UNAVAILABLE_STOP':
        if not STOP.exists():write_new(STOP,{'classification':classification,'message':clean_message(status.failure_message),'observed_epoch':time.time(),'version':version})
    prefix=f'bracket-v{version}-{time.time_ns()}'
    a=event(prefix+'-before',before.metadata.to_dict());b=event(prefix+'-after',after.metadata.to_dict())
    event(prefix+'-status',{'status':status.status.name,'failure_message':clean_message(status.failure_message)})
    return {'version':version,'status':status.status.name,'source_sha256':sha(raw),'metadata_sha256':b['sha256'],'metadata_before_sha256':a['sha256'],'observed_epoch':time.time(),'gpu_stop':classification=='GPU_UNAVAILABLE_STOP'},raw,after.metadata

def historical_retention_roots():
    """Read each admitted round's own allocation; never relabel its captures."""
    result=[]
    for entry in getattr(CONFIG,'publication_history',()):
        descriptor_=entry['manifest']
        manifest=strict_object(verified(descriptor_['path'],descriptor_['sha256'],descriptor_['bytes'],4*1024**2))
        datasets=manifest.get('datasets')
        need(type(datasets)is list and len(datasets)==1,'historical_retention_dataset_schema')
        dataset=datasets[0];predecessor_=dataset.get('expected_predecessor_version');code=dataset.get('expected_version')
        need(type(predecessor_)is int and type(code)is int and 20<=predecessor_<code<=CODE_PREDECESSOR
             and code==predecessor_+1 and dataset.get('id')==12504696 and dataset.get('reference')==DREF,
             'historical_retention_allocation')
        result.append((secure_path(entry['root']),predecessor_))
    return result

def retained_inventory_matches(proof,old,captured,digest,files):
    return (type(proof.get('numeric_version'))is int and proof['numeric_version']==old
        and type(proof.get('dataset_id'))is int and proof['dataset_id']==12504696
        and type(proof.get('captured_while_current_version'))is int
        and proof['captured_while_current_version']==captured
        and proof.get('inventory_sha256')==digest and proof.get('files_inventory')==files
        and proof.get('payload_bytes_rehashed') is False)

def dataset_check(provider,version, *, capture_prewrite=False, metadata_only=False):
    """Preserve old versions including the one falling out of the latest-ten view."""
    d=provider.dataset();need(d.id==12504696 and d.ref==DREF and d.is_private is True and d.current_version_number==version,'dataset_predecessor_identity')
    need(version in (CODE_PREDECESSOR,CODE_VERSION),'dataset_check_exact_successor_versions')
    need(d.title=='IRIS-X Learning Agent Code 20261011' and d.license_name=='Other (specified in description)' and getattr(d,'owner_ref','danielwuu')=='danielwuu','dataset_title_license_owner')
    versions=[v.version_number for v in d.versions]
    need(len(versions)==len(set(versions)) and all(type(v)is int and 1<=v<=version for v in versions),'invalid_dataset_version_history')
    full=set(versions)==set(range(1,version+1))
    need(full or versions==list(range(version,max(0,version-10),-1)),'unexpected_dataset_history_window')
    need(type(capture_prewrite)is bool and type(metadata_only)is bool and not (capture_prewrite and metadata_only),'history_check_mode')
    if capture_prewrite:need(version==CODE_PREDECESSOR and not code_state('.claim.json').exists(),'history_capture_only_before_claim')
    pinned={1:'9a8b5f698c942407b74cc5b16e0ad1d77dd2ac4a6800f991c8bd9f9584353a1b',2:'402aebb539a8163ed516d2e2915c75f5b7a16c56e1d244ac99088f62a2f2e6b9',3:'8c1b22bd9b676ad2a10f31ee820ed4d1732f04dca9d0a81835fdc456c6bd318d',4:'dc87ea2368b0ce1b750b3572327d57adc670474a8c511a485c43704b62c3e01f',5:'54fbc4f2d6543cc82255fdd71113ffce44ca88aab83442f1ac9d80abbe52e255',6:'8db523abc333759e431e396146e991564523aa2d2daac30374a384f86023dcac',7:'55ee43dcab68f291aa517ad823c58993c8ec813a520173e09676598ae9dcda79'}
    historical=[]
    prior_roots=[] if metadata_only else historical_retention_roots()
    # The successor latest-ten window begins at predecessor-8. Capture through
    # predecessor-9 before mutation, including the version that will disappear.
    for old in (() if metadata_only else range(1,max(7,CODE_PREDECESSOR-9)+1)):
        files=provider.list_files(dataset=True,version=old);need(bool(files),'historical_numeric_inventory_empty')
        digest=sha(canonical(files))
        if old in pinned:need(digest==pinned[old],'historical_numeric_version_inventory_changed')
        else:
            for prior_root,captured in prior_roots:
                prior=prior_root/f'historical-code-v{old}-inventory.json'
                if old<=max(7,captured-9):
                    need(prior.is_file(),'prior_historical_baseline_missing')
                    need(retained_inventory_matches(obj(prior),old,captured,digest,files),
                         'prior_historical_baseline_changed')
            baseline=publication_root()/f'historical-code-v{old}-inventory.json'
            if baseline.exists():
                proof=obj(baseline);need(retained_inventory_matches(proof,old,CODE_PREDECESSOR,digest,files),'historical_baseline_changed')
            else:
                need(capture_prewrite and version==CODE_PREDECESSOR and not code_state('.claim.json').exists(),'historical_baseline_missing_prewrite_required')
                write_new(baseline,{'dataset_id':12504696,'numeric_version':old,'captured_while_current_version':CODE_PREDECESSOR,'inventory_sha256':digest,'files_inventory':files,'payload_bytes_rehashed':False})
        proof={'numeric_version':old,'files':len(files),'bytes_listed':sum(files.values()),'inventory_sha256':digest,'payload_bytes_rehashed':False,'scope':'Official numeric historical file-name/size inventory only; no historical payload byte claim.'}
        historical.append(proof);event('historical-retention',{'dataset_id':12504696,**proof,'files_inventory':files})
    after=provider.dataset();need(after.id==d.id and after.ref==d.ref and after.is_private is True and after.current_version_number==version and [v.version_number for v in after.versions]==versions and after.title==d.title and after.license_name==d.license_name and getattr(after,'owner_ref','danielwuu')==getattr(d,'owner_ref','danielwuu'),'dataset_history_bracket_changed')
    return {'id':d.id,'ref':d.ref,'version':version,'private':True,'license_name':d.license_name,'title':d.title,'owner_ref':getattr(d,'owner_ref',None),'versions':versions,'history_metadata_scope':('complete_metadata_only' if full else 'exact_latest_ten_metadata_only') if metadata_only else ('complete' if full else 'exact_latest_ten_plus_numeric_historical_inventory'),'older_version_metadata_proof':historical,'retention_check_complete':not metadata_only,'prewrite_capture_mode':capture_prewrite}


def predecessor(provider,m,role):
    n=row(m,role);expected=n['predecessor_source_sha256']
    status_expected=REMOTE_PREDECESSOR['provider_status']
    if role=='rlvr004':
        rec=obj(publication_root()/'notebook-inactive-receipt.json')
        need(rec['version']==INACTIVE_VERSION and rec['status']=='COMPLETE','inactive_not_complete')
        expected=rec['saved_source']['sha256'];status_expected='COMPLETE'
    snapshot,_,_=bracket(provider,n['expected_predecessor_version'],expected,n=row(m,'inactive') if role=='rlvr004' else None)
    need(snapshot['status']==status_expected and snapshot['status'] in TERMINAL and not snapshot['gpu_stop'],'predecessor_status_mismatch')
    return snapshot

def update_code(provider,m,args):
    no_gpu_stop();d=m['datasets'][0];dataset_check(provider,CODE_PREDECESSOR,capture_prewrite=True);predecessor(provider,m,'inactive')
    payload=Path(args.manifest).resolve().parent/d['transport_archive']['path'];verified(payload,d['transport_archive']['sha256'],d['transport_archive']['bytes'])
    name=code_claim_name();j={'manifest_sha256':args.manifest_sha,'stage':'claimed','init_calls':0,'put_calls':0,'version_calls':0,'payload_sha256':file_sha(payload),'expected_version':CODE_VERSION,'expected_predecessor_version':CODE_PREDECESSOR}
    c=publication_claim(name,j);j['claim_sha256']=c['sha256'];publication_journal(name,j)
    j.update(stage='init_intent',init_calls=1);publication_journal(name,j);u=provider.start_upload(payload)
    need(type(u.handle)is str and bool(u.handle) and type(u.origin)is dict,'upload_init_incomplete')
    safe_origin=u.origin
    need(safe_origin['payload_sha256']==j['payload_sha256'] and safe_origin['official_init_response'] is True
         and safe_origin['token_or_signed_url_persisted'] is False,'bridge_upload_authority_binding')
    authority=event('official-staging-authority',safe_origin);j.update(stage='init_accepted_ram_only',authority_metadata_sha256=authority['sha256']);publication_journal(name,j)
    no_gpu_stop();j.update(stage='put_intent',put_calls=1);publication_journal(name,j);provider.upload_once(u.handle,payload)
    j['stage']='put_accepted';publication_journal(name,j)
    dataset_check(provider,CODE_PREDECESSOR);no_gpu_stop();j.update(stage='version_intent',version_calls=1);publication_journal(name,j)
    r=provider.version(u.handle,d['version_notes']);del u
    event('version-response',r.to_dict())
    need(not r.error and r.ref==DREF,'version_response_error');j['stage']='version_accepted';j['response']=r.to_dict();publication_journal(name,j)
    return {'status':'VERSION_ACCEPTED_READBACK_REQUIRED','version':CODE_VERSION}

def expected_layout(m,actual):
    for name,rows_ in m['datasets'][0]['expected_readback_layouts'].items():
        rows_map={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in rows_}
        if actual==rows_map:return name,rows_map
    raise GuardError('dataset_layout_mismatch')

def verify_code(provider,m,args,per_file=False):
    j=obj(code_state('-journal.json'));need(j['manifest_sha256']==args.manifest_sha and j['version_calls']==1,'no_version_write_to_reconcile')
    need(j['expected_version']==CODE_VERSION and j['expected_predecessor_version']==CODE_PREDECESSOR,'run008_code_journal_versions')
    need(j['claim_sha256']==file_sha(code_state('.claim.json')),'code_claim_binding')
    before=dataset_check(provider,CODE_VERSION);event('code-before',before)
    out=secure_path(publication_root()/f'code-v{CODE_VERSION}-readback');out.mkdir(exist_ok=True);payload=secure_path(out/'payload');actual={};archive=None
    if per_file:
        listed=provider.list_files(dataset=True,version=CODE_VERSION);expected=None;layout=None
        for name,rr in m['datasets'][0]['expected_readback_layouts'].items():
            if {r['path']:r['bytes'] for r in rr}==listed:layout=name;expected={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in rr};break
        need(expected is not None,'listed_dataset_layout_mismatch');event('code-list-before',listed)
        for name,v in expected.items():
            relative(name);dest=payload/name
            if dest.exists():verified(dest,v['sha256'],v['bytes'])
            else:
                desc=binary_get(provider.dataset_download(name,version=CONFIG.versions['code']),dest,v['bytes'],v['sha256'],v['bytes']);event('code-file',{'numeric_version':CODE_VERSION,'raw':True,'provider_path':name,'http_status':200,**desc})
            actual[name]=v
        need(provider.list_files(dataset=True,version=CODE_VERSION)==listed,'provider_inventory_changed')
    else:
        p=out/'provider.zip'
        if p.exists():
            old=obj(out/'archive-download.json');verified(p,old['sha256'],old['bytes'])
        else:
            archive=binary_get(provider.dataset_download(version=CONFIG.versions['code']),p,64*1024**2);write_new(out/'archive-download.json',archive)
        actual=check_zip(p,128*1024**2,3000,{'source.zip'});layout,expected=expected_layout(m,actual);archive=descriptor(p)
        with zipfile.ZipFile(p) as z:
            for name,v in actual.items():
                dest=secure_path(payload/name)
                if dest.exists():verified(dest,v['sha256'],v['bytes']);continue
                write_new(dest,z.read(name))
    after=dataset_check(provider,CODE_VERSION);need(before==after,'dataset_metadata_changed');event('code-after',after)
    secure_path(payload);local={}
    for p in payload.rglob('*'):
        secure_path(p);mode=p.stat().st_mode
        need(stat.S_ISREG(mode) or stat.S_ISDIR(mode),'readback_special_entry')
        if stat.S_ISREG(mode):local[p.relative_to(payload).as_posix()]={'bytes':p.stat().st_size,'sha256':file_sha(p)}
    need(local==actual,'readback_extra_or_missing_files')
    result={'status':f'VERIFIED_CODE_V{CODE_VERSION}','manifest_sha256':args.manifest_sha,'publication_manifest_sha256':args.manifest_sha,'dataset_id':12504696,'version':CODE_VERSION,'is_private':True,'exact_byte_roundtrip':True,'layout':layout,'payload_root':str(payload),'files':len(actual),'bytes':sum(x['bytes'] for x in actual.values()),'inventory_sha256':sha(canonical(actual)),'provider_archive_verified':not per_file,'archive_sha256':None if per_file else archive['sha256'],'readback_method':'numeric_per_file' if per_file else 'numeric_whole_archive','journal_sha256':file_sha(code_state('-journal.json')),'claim_sha256':j['claim_sha256'],'before':before,'after':after}
    p=code_state('-receipt.json')
    if p.exists():need(obj(p)==result,'existing_code_receipt_differs')
    else:write_new(p,result)
    return result

def monitor_gate(args):
    need(args.monitor_review and args.monitor_sha and args.consumer_root,'monitor_consumer_review_required')
    r=review_gate(args.monitor_review,args.monitor_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py'),SCRIPT.with_name('rl_collect.py')])
    root=secure_path(args.consumer_root);files=r['consumer_files']
    need({'reviewed_entry.py','CONSUMER-INVENTORY.json','CONSUMER-OPERATOR.json'}<=set(files),'external_consumer_closure')
    for name,digest in files.items():relative(name);verified(root/name,digest)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*.py') if '__pycache__' not in p.parts and 'tests' not in p.relative_to(root).parts}
    need(actual=={name for name in files if name.endswith('.py')},'consumer_no_unreviewed_python')
    pins=obj(root/'CONSUMER-OPERATOR.json');need(pins['collector_entry_sha256']==file_sha(SCRIPT.with_name('rl_collect.py')) and pins['helper_inventory_sha256']==file_sha(root/'CONSUMER-INVENTORY.json'),'consumer_collector_closure_link')
    return r

def git_publication_gate(args,review=None):
    """Require reviewed remote publication and the exact committed local code."""
    if review is None:
        review=review_gate(args.review,args.review_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py')])
    commit=review.get('candidate_git_commit')
    need(review.get('candidate_git_remote_verified') is True and type(commit)is str and re.fullmatch('[a-f0-9]{40}',commit) is not None,'review_git_publication_required')
    repository=secure_path(CONFIG.repository_root)
    for name in OPERATOR_SOURCE_NAMES:
        path=secure_path(SCRIPT.with_name(name));relative_path=path.relative_to(repository).as_posix()
        need(':' not in relative_path and '\\' not in relative_path,'git_operator_relative_path')
        result=subprocess.run(['git','-C',str(repository),'show',commit+':'+relative_path],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
        need(result.returncode==0 and len(result.stdout)<=1024**2 and sha(result.stdout)==file_sha(path),'git_operator_bytes_not_committed')
    return commit


def execution_gate(args, *, monitor=False):
    """The reviewed action list cannot enlarge the current one-submit scope."""
    need(type(monitor)is bool,'monitor_flag_type')
    review=review_gate(args.review,args.review_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py')])
    permitted={'poll','collect','watch','readiness','update-code','verify-code','verify-code-files','save-inactive','verify-inactive','prepare-active','activate','verify-run','reconcile-read-only'}
    need((args.action in {'poll','collect','watch'}) is monitor,'wrong_execution_role')
    actions=review.get('allowed_actions')
    need(review.get('provider_execution_admitted') is True,'provider_execution_not_reviewed')
    need(review.get('synthetic_test_only') is False,'synthetic_review_cannot_admit_provider_execution')
    need(type(actions)is list and all(type(action)is str for action in actions) and len(actions)==len(set(actions)) and set(actions)<=permitted,'invalid_review_action_scope')
    need(args.action in actions,'provider_action_not_reviewed')
    if args.action in ('update-code','save-inactive','activate'):
        git_publication_gate(args,review)
    return review

def run_prerequisites(m,args):
    """Review exact source, private readbacks and CPU mount; no watcher readiness."""
    monitor_gate(args)
    code=obj(code_state('-receipt.json'));inactive=obj(publication_root()/'notebook-inactive-receipt.json')
    need(code['dataset_id']==12504696 and code['version']==CODE_VERSION and code['is_private'] is True and inactive['kernel_id']==138123872 and inactive['version']==INACTIVE_VERSION,'run008_prerequisite_versions')
    need(code['exact_byte_roundtrip'] is True and code['manifest_sha256']==args.manifest_sha and inactive['manifest_sha256']==args.manifest_sha and inactive['status']=='COMPLETE','publication_readbacks_required')
    need(args.mount and args.mount_sha and args.audit and args.audit_sha,'mount_audit_required')
    mount=json.loads(verified(args.mount,args.mount_sha));audit=json.loads(verified(args.audit,args.audit_sha))
    need(mount['status']=='PASS' and mount['publication_manifest_sha256']==args.manifest_sha and mount['code_dataset_version']==CODE_VERSION and mount['model_calls']==0 and mount['owned_tree_closed'] is True and mount['code_receipt_sha256']==file_sha(code_state('-receipt.json')),'actual_mount_gate')
    need(audit['status']=='PASS' and audit['publication_manifest_sha256']==args.manifest_sha and audit['code_receipt_sha256']==file_sha(code_state('-receipt.json')) and audit['inactive_receipt_sha256']==file_sha(publication_root()/'notebook-inactive-receipt.json') and audit['mount_receipt_sha256']==args.mount_sha,'persisted_audit_gate')
    return {'mount_receipt_sha256':args.mount_sha,'persisted_audit_sha256':args.audit_sha,'monitor_review_sha256':args.monitor_sha,'code_receipt_sha256':file_sha(code_state('-receipt.json')),'inactive_receipt_sha256':file_sha(publication_root()/'notebook-inactive-receipt.json')}

def kernel_wire(n,raw):
    return {'id':138123872,'slug':REF,'new_title':n['title'],'text':raw.decode(),'language':'python','kernel_type':'notebook','dataset_data_sources':PINS,'model_data_sources':[MODEL],'competition_data_sources':['arc-prize-2026-arc-agi-3'],'kernel_data_sources':[],'is_private':True,'enable_gpu':n['enable_gpu'],'enable_tpu':False,'enable_internet':False,'docker_image':DOCKER,'kernel_execution_type':n['save_version_value'],'session_timeout_seconds':n['session_timeout_seconds'],'machine_shape':n['machine_shape']}

def save(provider,m,args,role):
    no_gpu_stop();n=row(m,role);active=role=='rlvr004'
    review=json.loads(verified(args.review,args.review_sha))
    git_commit=git_publication_gate(args,review);git_verified=True
    code=obj(code_state('-receipt.json'));need(code['dataset_id']==12504696 and code['version']==CODE_VERSION and code['is_private'] is True and code['manifest_sha256']==args.manifest_sha and code['exact_byte_roundtrip'] is True,'verified_code_required');dataset_check(provider,CODE_VERSION)
    gates=run_prerequisites(m,args) if active else {}
    pre=predecessor(provider,m,role);no_gpu_stop();name='notebook-'+role
    j={'role':role,'reference':REF,'kernel_id':138123872,'expected_version':n['expected_version'],'manifest_sha256':args.manifest_sha,'material_approval_sha256':args.material_sha,'transport_review_sha256':args.review_sha,'save_calls':0,'stage':'claimed','predecessor':pre,'git_publication_completed':git_verified,'git_commit':git_commit if git_verified else None,'stop_after_submit_readback':False,'provider_monitoring_authorized':True,**gates}
    c=publication_claim(name,j);j['claim_sha256']=c['sha256'];publication_journal(name,j)
    raw=verified(Path(args.manifest).resolve().parent/n['path'],n['sha256'],n['bytes'])
    if active:
        epoch=int(time.time());documents=finalized_documents(m,args.manifest,epoch)
        entries={name:write_new(publication_root()/name,data) for name,data in documents.items()}
        raw=documents['active-finalized.ipynb']
        final={'format':'irisx/rlvr-finalization-v1','manifest_sha256':args.manifest_sha,'template_sha256':n['sha256'],'finalized_sha256':sha(raw),'documents':entries,'finalizer_sha256':m['jit']['entry']['sha256'],**clock(epoch)}
        f=write_new(publication_root()/'finalization.json',final);j.update(clock(epoch));j['finalization_sha256']=f['sha256']
    else:j.update(dispatch_epoch=None,deadline_epoch=None,provider_timeout_seconds=None)
    wire=kernel_wire(n,raw);w=write_new(publication_root()/(name+'-wire.json'),wire)
    j.update(stage='wire_prepared' if active else 'save_intent',save_calls=0 if active else 1,source_sha256=sha(raw),wire_sha256=w['sha256'])
    publication_journal(name,j)
    if active:
        return {'status':'ACTIVE_PREPARED_REVIEW_REQUIRED','version':ACTIVE_VERSION,'wire_sha256':w['sha256'],'finalization_sha256':j['finalization_sha256'],'predispatch_epoch':j['predispatch_epoch'],'maximum_dispatch_age_seconds':60}
    no_gpu_stop();r=provider.save(wire)
    event(name+'-response',r.to_dict())
    if r.error:
        classification,message=classify(None,r.error)
        event('save-response-error',{'classification':classification,'message':message,'role':role})
        if classification=='GPU_UNAVAILABLE_STOP' and not STOP.exists():write_new(STOP,{'classification':classification,'message':message,'time_epoch':time.time()})
        raise ProviderReportedError(clean_message(r.error))
    need(r.kernel_id==138123872 and r.ref in (REF,'/code/'+REF) and r.version_number==n['expected_version'] and not r.invalid_dataset_sources and not r.invalid_model_sources and not r.invalid_competition_sources and not r.invalid_kernel_sources,'save_response_identity')
    j.update(stage='save_accepted',save_accepted=True,response_version=r.version_number,accepted_epoch=time.time());publication_journal(name,j)
    if active:
        # One immediate source/settings/status bracket; terminal monitoring is a
        # separately reviewed collector action and never resends this RUN.
        return verify_notebook(provider,m,args,role)
    return {'status':'SAVE_ACCEPTED','version':r.version_number,'role':role}

def active_review_gate(m,args):
    """Independent review binds the real JIT bytes; stale epochs cannot dispatch."""
    need(args.active_review and args.active_review_sha,'active_wire_review_required')
    review=strict_object(verified(args.active_review,args.active_review_sha,cap=1024**2))
    journal_path=publication_root()/'notebook-rlvr004-journal.json';j=obj(journal_path)
    f=obj(publication_root()/'finalization.json');wire=obj(publication_root()/'notebook-rlvr004-wire.json')
    need(review.get('format')=='irisx/run008-active-wire-review-v1' and review.get('status')=='PASS' and review.get('synthetic_test_only') is False,'active_wire_review_admission')
    bindings={'publication_manifest_sha256':args.manifest_sha,'material_approval_sha256':args.material_sha,'transport_review_sha256':args.review_sha,'local_config_sha256':args.local_config_sha,'wire_sha256':file_sha(publication_root()/'notebook-rlvr004-wire.json'),'finalization_sha256':file_sha(publication_root()/'finalization.json'),'finalized_source_sha256':file_sha(publication_root()/'active-finalized.ipynb'),'prepared_journal_sha256':file_sha(journal_path),'predispatch_epoch':f['predispatch_epoch'],'numeric_notebook_version':ACTIVE_VERSION}
    need(all(review.get(k)==v for k,v in bindings.items()),'active_review_exact_bindings')
    need(j['stage']=='wire_prepared' and j['save_calls']==0 and j['expected_version']==ACTIVE_VERSION and j['manifest_sha256']==args.manifest_sha and j['claim_sha256']==file_sha(publication_root()/'notebook-rlvr004.claim.json'),'prepared_run_claim')
    check_finalization(m,args,f)
    need(wire==kernel_wire(row(m,'rlvr004'),read(publication_root()/'active-finalized.ipynb')) and j['source_sha256']==bindings['finalized_source_sha256'] and j['wire_sha256']==bindings['wire_sha256'] and j['finalization_sha256']==bindings['finalization_sha256'],'prepared_run_exact_wire')
    need(0<=time.time()-f['predispatch_epoch']<=60,'stale_epoch_no_send')
    return j,wire


def activate(provider,m,args):
    no_gpu_stop();j,wire=active_review_gate(m,args)
    git_publication_gate(args);run_prerequisites(m,args)
    dataset_check(provider,CODE_VERSION,metadata_only=True);predecessor(provider,m,'rlvr004')
    # Recheck after the last network read and before durable intent; no JIT rebuild.
    j,wire=active_review_gate(m,args);no_gpu_stop()
    j.update(stage='save_intent',save_calls=1,dispatch_sample_epoch=time.time(),dispatch_epoch=time.time(),active_wire_review_sha256=args.active_review_sha)
    publication_journal('notebook-rlvr004',j)
    need(0<=time.time()-j['predispatch_epoch']<=60,'stale_epoch_no_send')
    r=provider.save(wire)
    if r.error:raise ProviderReportedError(clean_message(r.error))
    need(r.kernel_id==138123872 and r.ref in (REF,'/code/'+REF) and r.version_number==ACTIVE_VERSION and not r.invalid_dataset_sources and not r.invalid_model_sources and not r.invalid_competition_sources and not r.invalid_kernel_sources,'save_response_identity')
    j.update(stage='save_accepted',save_accepted=True,response_version=r.version_number,accepted_epoch=time.time())
    publication_journal('notebook-rlvr004',j)
    return verify_notebook(provider,m,args,'rlvr004')


def verify_notebook(provider,m,args,role):
    name='notebook-'+role;n=row(m,role);j=obj(publication_root()/(name+'-journal.json'))
    # One initial read intent; later reconciliation references it without another RUN.
    if role=='rlvr004':
        intent={'manifest_sha256':args.manifest_sha,'numeric_notebook_version':ACTIVE_VERSION,'launch_claim_sha256':file_sha(publication_root()/'notebook-rlvr004.claim.json'),'action':'initial_post_submit_readback'}
        path=publication_root()/'active-readback.claim.json'
        if path.exists():need(obj(path)==intent,'initial_readback_claim_changed')
        else:publication_claim('active-readback',intent)
    need(j['expected_version']==n['expected_version'] and j['manifest_sha256']==args.manifest_sha and j['save_calls']==1 and j['claim_sha256']==file_sha(publication_root()/(name+'.claim.json')),'launch_journal_binding')
    raw=read(publication_root()/'active-finalized.ipynb') if role=='rlvr004' else read(Path(args.manifest).resolve().parent/n['path'])
    need(sha(raw)==j['source_sha256'],'submitted_source_binding')
    if role=='rlvr004':
        f=obj(publication_root()/'finalization.json');need(file_sha(publication_root()/'finalization.json')==j['finalization_sha256'] and f['finalized_sha256']==sha(raw) and f['manifest_sha256']==args.manifest_sha,'finalization_binding')
        check_finalization(m,args,f)
        need(all(j.get(k)==v for k,v in clock(f['predispatch_epoch']).items() if k!='dispatch_epoch') and 0<=j['dispatch_epoch']-f['predispatch_epoch']<=60,'launch_clock_binding')
    snap,saved,meta=bracket(provider,n['expected_version'],n=n)
    need(source_normalize(saved)==source_normalize(raw),'provider_source_normalization')
    if role=='inactive':need(snap['status']=='COMPLETE','inactive_not_complete')
    source_path=publication_root()/(name+'-saved.ipynb')
    if source_path.exists():need(read(source_path)==saved,'saved_source_changed_after_receipt')
    else:write_new(source_path,saved)
    result={'manifest_sha256':args.manifest_sha,'reference':REF,'kernel_id':138123872,'version':n['expected_version'],'status':snap['status'],'role':role,'submitted_source_sha256':sha(raw),'saved_source':descriptor(source_path),'normalized_source_exact':True,'provider_acceptance_reconciled':j.get('stage')=='save_intent','single_post_submit_readback':False,'model_sources_returned':meta.model_data_sources,'dataset_sources_returned':meta.dataset_data_sources,'settings':meta.to_dict(),'launch_journal_sha256':file_sha(publication_root()/(name+'-journal.json')),'finalization_sha256':file_sha(publication_root()/'finalization.json') if role=='rlvr004' else None,'predecessor':j['predecessor'],'snapshot':snap,'git_publication_completed':j['git_publication_completed'],'git_commit':j['git_commit'],'stop_after_submit_readback':False,'provider_monitoring_authorized':True}
    dest=publication_root()/(name+'-receipt.json')
    if dest.exists():
        prior=obj(dest);need(prior['saved_source']==result['saved_source'] and prior['launch_journal_sha256']==result['launch_journal_sha256'],'receipt_reconciliation_changed');event(name+'-observation',result)
    else:write_new(dest,result)
    return result

def parser():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['validate','validate-publication','readiness','update-code','verify-code','verify-code-files','save-inactive','verify-inactive','prepare-active','activate','verify-run'])
    for x in ('manifest','manifest-sha','material','material-sha','review','review-sha','local-config','local-config-sha'):p.add_argument('--'+x,required=True)
    for x in ('monitor-review','monitor-sha','mount','mount-sha','audit','audit-sha','consumer-root','active-review','active-review-sha'):p.add_argument('--'+x)
    return p

def main():
    a=parser().parse_args();provider=None
    try:
        m=load_contract(a)
        if a.action=='validate':print(json.dumps({'status':'LOCAL_CONTRACT_PASS','provider_calls':0,**publication_paths()}));return 0
        if a.action=='validate-publication':print(json.dumps(publication_preflight(m,a)));return 0
        execution_gate(a)
        if a.action in ('update-code','save-inactive','prepare-active','activate'):
            publication_preflight(m,a)
        if a.action=='activate':active_review_gate(m,a)
        if a.action in ('update-code','save-inactive','activate'):no_gpu_stop()
        with lock():
            provider=Provider()
            if a.action=='readiness':result={'dataset':dataset_check(provider,CODE_PREDECESSOR,metadata_only=True),'predecessor':predecessor(provider,m,'inactive')}
            elif a.action=='update-code':result=update_code(provider,m,a)
            elif a.action in ('verify-code','verify-code-files'):result=verify_code(provider,m,a,a.action.endswith('files'))
            elif a.action in ('save-inactive','prepare-active'):result=save(provider,m,a,'inactive' if a.action=='save-inactive' else 'rlvr004')
            elif a.action=='activate':result=activate(provider,m,a)
            elif a.action in ('verify-inactive','verify-run'):result=verify_notebook(provider,m,a,'inactive' if a.action=='verify-inactive' else 'rlvr004')
            else:raise GuardError('unsupported_one_submit_action')
            print(json.dumps(result));return 0
    except Exception as e:print(json.dumps(failure(e,a.action)));return 2
    finally:
        if provider:provider.close()
if __name__=='__main__':raise SystemExit(main())
