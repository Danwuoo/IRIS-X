"""Exact code18/v34/v35 run005 successor; consumed run004 bytes preserved."""
import argparse, contextlib, hashlib, json, os, stat, sys, time, types, zipfile
from pathlib import Path

# Acyclic local dependency pin. Compile source before any authentication or RPC.
COMMON_SOURCE_SHA256='9c1385696c4edd3fe381d7c1d657aa805b9dcca2def6700148a40aa255db977a'
_common_path=Path(__file__).absolute().with_name('operator_common.py')
if any(p.is_symlink() for p in (_common_path,*_common_path.parents)) or not stat.S_ISREG(_common_path.stat().st_mode):
    raise ValueError('unsafe_local_common_source')
with _common_path.open('rb') as _f:_common_raw=_f.read(1024**2+1)
if len(_common_raw)>1024**2 or hashlib.sha256(_common_raw).hexdigest()!=COMMON_SOURCE_SHA256:
    raise ValueError('local_common_source_pin')
_common=types.ModuleType('reviewed_rl_operator_common');_common.__file__=str(_common_path);_common.__package__=''
exec(compile(_common_raw,str(_common_path),'exec',dont_inherit=True,optimize=sys.flags.optimize),_common.__dict__)
globals().update({k:v for k,v in _common.__dict__.items() if not k.startswith('_')})

FORMAT='irisx/qwen14b-rlvr-run005-publication-contract-v1'
OLD_SOURCE='e7747c8013a9149cf7331954fd583fd8770adb416b2881074c9875f94c3f7761'
DOCKER='gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f'
PINS=[DREF+'/18','danielwuu/iris-x-public120-data-20261010/1','danielwuu/iris-x-learning-training-20261011/1','danielwuu/iris-arc-next-runtime/8','danielwuu/iris-arc-granite42-8b-offline/2','danielwuu/iris-arc-next-cu128-cp312-wheels/1','danielwuu/iris-arc-next-cpython312-offline/2','danielwuu/iris-arc-granite42-run003-adapter-20261009/1']
SCRIPT=Path(__file__).resolve()

# These are this single reviewed successor's immutable identities. rlvr004 is
# the frozen method-family role; fresh manifest/state/source/run identities are
# mandatory, and these constants grant no provider authority.
CODE_PREDECESSOR=17
CODE_VERSION=18
NOTEBOOK_PREDECESSOR=33
INACTIVE_VERSION=34
ACTIVE_VERSION=35
RUN_PATH='/kaggle/working/irisx-qwen14b-rlvr-20261012-run005'
SOURCE_PATH='/kaggle/working/irisx-qwen14b-rlvr-20261012-source005'
ENVIRONMENT_PATH='/tmp/irisx-qwen14b-rlvr-20261012-environment005'
PREDECESSOR_SUBMITTED_SOURCE='a3bdc6b13870a0dcc6862a08b2ebbef6f07419e9147c1c989fb6a4403abba037'
PREDECESSOR_DIAGNOSTIC_SHA256='7e6161727accff39afaba37e75f1527db7a638098cbcb4f58d88e95fb7b0e8bc'
PREDECESSOR_RETRIEVAL_SHA256='8f7446f1182bdeacba86e982793222203b948ab4dac6831b712a786fa3c29042'
PREDECESSOR_ARCHIVE_SHA256='06825c68f991fd8e9b4f1a3cf76cf5e06fae18607918bf0840991f1a9a6591cd'
PREDECESSOR_EPOCH=1791866719
HISTORICAL_V31_SHA256='4ebd93a7377d759b02cca24e950eabf1f14d3ccc6e87df94d8f3a286974fabd7'

def code_claim_name():return f'dataset-code-v{CODE_VERSION}'
def code_state(suffix):return STATE/(code_claim_name()+suffix)
def profile_versions():
    return {'code_predecessor':CODE_PREDECESSOR,'code':CODE_VERSION,
            'inactive_predecessor':NOTEBOOK_PREDECESSOR,'inactive':INACTIVE_VERSION,'active':ACTIVE_VERSION}


def rows(m):return {r['role']:r for r in m['notebooks']}
def row(m,role):return rows(m)[role]
def clock(epoch):return {'dispatch_epoch':epoch,'predispatch_epoch':epoch,'deadline_epoch':epoch+43200,'global_deadline_epoch':epoch+43200,'execution_deadline_epoch':epoch+42000,'outer_deadline_epoch':epoch+42180,'provider_timeout_seconds':42300}
def predecessor_proof(m,root):
    """Bind actual v33 selected diagnostics and retain the distinct v31 history.

    Transport/process proofs do not grant authenticated model closure, a journal
    total, scientific admission, a PUBLIC score, or billing/VM attestation.
    Exact observed v33 report/receipt hashes prevent substituting a caller-made
    boolean report. The original epoch and failed evidence remain immutable.
    """
    import math
    d=m['predecessor_readiness'];relative(d['path'])
    proof=json.loads(verified(root/d['path'],d['sha256'],d['bytes']))
    need(d['notebook_version']==NOTEBOOK_PREDECESSOR and d['notebook_source_sha256']==OLD_SOURCE and d['provider_status']=='ERROR','predecessor_descriptor_identity')
    fields={'format','notebook_id','numeric_notebook_version','code_dataset_id','code_dataset_version','provider_status','saved_source_sha256','submitted_source_sha256','evidence','selected_outputs','historical_v31'}
    need(set(proof)==fields and proof['format']=='irisx/rlvr005-predecessor-evidence-v1','run005_predecessor_schema')
    need(proof['numeric_notebook_version']==NOTEBOOK_PREDECESSOR and proof['code_dataset_version']==CODE_PREDECESSOR and proof['notebook_id']==138123872 and proof['code_dataset_id']==12504696 and proof['provider_status']=='ERROR','verified_error_predecessor_required')
    need(proof['saved_source_sha256']==OLD_SOURCE and proof['submitted_source_sha256']==PREDECESSOR_SUBMITTED_SOURCE,'predecessor_distinct_saved_submitted')
    evidence=proof['evidence']
    names={'code_receipt','launch_receipt','launch_journal','finalization','launch_wire','saved_source','retrieval_receipt','terminal_diagnostic','terminal_checkpoint','evidence_archive','terminal_receipt','runtime_outer_closure','owned_result'}
    need(type(evidence)is dict and set(evidence)==names,'predecessor_exact_evidence')
    raw={}
    for name,desc in evidence.items():
        need(type(desc)is dict and set(desc)=={'path','bytes','sha256'},'predecessor_evidence_descriptor');relative(desc['path'])
        raw[name]=verified(root/desc['path'],desc['sha256'],desc['bytes'])
    need(evidence['saved_source']['sha256']==OLD_SOURCE and evidence['saved_source']['bytes']==21096,'predecessor_source_bytes')
    need(evidence['terminal_diagnostic']['sha256']==PREDECESSOR_DIAGNOSTIC_SHA256 and evidence['retrieval_receipt']['sha256']==PREDECESSOR_RETRIEVAL_SHA256,'exact_predecessor_diagnostic_review')
    need(evidence['evidence_archive']['sha256']==PREDECESSOR_ARCHIVE_SHA256 and evidence['evidence_archive']['bytes']==15908385,'exact_predecessor_archive')
    code=json.loads(raw['code_receipt']);launch=json.loads(raw['launch_receipt']);journal_=json.loads(raw['launch_journal']);final=json.loads(raw['finalization']);wire=json.loads(raw['launch_wire'])
    need(code['dataset_id']==12504696 and code['version']==CODE_PREDECESSOR and code['is_private'] is True and code['exact_byte_roundtrip'] is True,'predecessor_code_identity')
    need(launch['kernel_id']==138123872 and launch['reference']==REF and launch['version']==NOTEBOOK_PREDECESSOR and launch['role']=='rlvr004' and launch['normalized_source_exact'] is True,'predecessor_launch_identity')
    need(launch['submitted_source_sha256']==PREDECESSOR_SUBMITTED_SOURCE and launch['saved_source']['sha256']==OLD_SOURCE and launch['saved_source']['bytes']==21096,'predecessor_launch_sources')
    need(launch['launch_journal_sha256']==sha(raw['launch_journal']) and launch['finalization_sha256']==journal_['finalization_sha256']==sha(raw['finalization']) and journal_['wire_sha256']==sha(raw['launch_wire']),'predecessor_launch_hash_chain')
    need(journal_['save_calls']==1 and journal_['save_accepted'] is True and journal_['expected_version']==journal_['response_version']==NOTEBOOK_PREDECESSOR and journal_['source_sha256']==PREDECESSOR_SUBMITTED_SOURCE,'predecessor_single_dispatch')
    need(final['predispatch_epoch']==PREDECESSOR_EPOCH and all(final.get(k)==v for k,v in clock(PREDECESSOR_EPOCH).items()),'predecessor_original_clock')
    need(all(journal_.get(k)==final[k] for k in ('predispatch_epoch','deadline_epoch','global_deadline_epoch','execution_deadline_epoch','outer_deadline_epoch','provider_timeout_seconds')) and 0<=journal_['dispatch_epoch']-PREDECESSOR_EPOCH<=60,'predecessor_dispatch_clock')
    submitted=wire['text'].encode();need(sha(submitted)==final['finalized_sha256']==PREDECESSOR_SUBMITTED_SOURCE and source_normalize(submitted)==source_normalize(raw['saved_source']),'predecessor_documented_source_normalization')
    need(wire['id']==138123872 and wire['slug']==REF and wire['dataset_data_sources']==[DREF+'/'+str(CODE_PREDECESSOR),*PINS[1:]] and wire['model_data_sources']==[MODEL] and wire['competition_data_sources']==['arc-prize-2026-arc-agi-3'] and wire['kernel_data_sources']==[],'predecessor_original_wire_pins')
    need(wire['is_private'] is True and wire['enable_gpu'] is True and wire['enable_tpu'] is False and wire['enable_internet'] is False and wire['docker_image']==DOCKER and wire['machine_shape']=='NvidiaRtxPro6000' and wire['session_timeout_seconds']==42300 and wire['kernel_execution_type']==1,'predecessor_original_wire_settings')
    retrieval=json.loads(raw['retrieval_receipt']);diagnostic=json.loads(raw['terminal_diagnostic']);checkpoint=json.loads(raw['terminal_checkpoint'])
    need(retrieval['reference']==REF and retrieval['kernel_id']==138123872 and retrieval['numeric_output_version']==NOTEBOOK_PREDECESSOR and retrieval['checkpoint_numeric_version']==NOTEBOOK_PREDECESSOR and retrieval['launch_receipt_sha256']==sha(raw['launch_receipt']),'predecessor_retrieval_identity')
    need(retrieval['inventory_scope']=='selected_outputs_only' and retrieval['whole_provider_inventory_verified'] is False and retrieval['checkpoint_downloaded'] is False,'predecessor_selected_scope')
    for snap in (retrieval['before'],retrieval['after']):
        need(snap['version']==NOTEBOOK_PREDECESSOR and snap['source_sha256']==OLD_SOURCE and snap['status']=='ERROR' and snap['gpu_stop'] is False,'predecessor_terminal_source_bracket')
        need(type(snap['observed_epoch'])in (int,float) and math.isfinite(snap['observed_epoch']) and all(type(snap.get(k))is str and re.fullmatch('[a-f0-9]{64}',snap[k]) for k in ('metadata_before_sha256','metadata_sha256')),'predecessor_provider_observation')
    need(type(retrieval['collected_epoch'])in (int,float) and math.isfinite(retrieval['collected_epoch']) and PREDECESSOR_EPOCH<=retrieval['before']['observed_epoch']<=retrieval['after']['observed_epoch']<=retrieval['collected_epoch'],'predecessor_ordered_bracket')
    need(diagnostic['status']=='UNSEALED_SESSION_DIAGNOSTICS' and diagnostic['reason']=='SOURCE_BOUND_TERMINATED_SESSION_WITHOUT_AUTHENTICATED_JOURNAL_CLOSURE' and diagnostic['provider_status']=='ERROR' and diagnostic['numeric_output_version']==NOTEBOOK_PREDECESSOR,'predecessor_unsealed_diagnostic')
    need(all(diagnostic.get(k)is True for k in ('diagnostic_transport_integrity_verified','external_stage_process_closure_verified','runtime_worker_exited','runtime_worker_session_empty')),'predecessor_raw_process_proofs')
    false_flags=('terminal_validated','consumer_admitted','production_admitted','external_owner_envelope_verified','runtime_safe_closure','runtime_model_closure_verified','physical_costs_known','billing_verified','operational_success','public_goal_met','scientific_goal_met','goal_met','whole_provider_inventory_verified','independent_checkpoint_tensor_verification')
    need(all(diagnostic.get(k)is False for k in false_flags) and diagnostic['physical_costs'] is None and diagnostic['public_score'] is None and diagnostic['runtime_authenticated_request_sha256'] is None and diagnostic['runtime_authenticated_inner_closure'] is None and diagnostic['physical_journal_present_in_archive'] is False,'predecessor_no_invented_admission')
    need(checkpoint['diagnostic_receipt']['sha256']==sha(raw['terminal_diagnostic']) and checkpoint['predispatch_epoch']==PREDECESSOR_EPOCH and checkpoint['status']==diagnostic['status'] and checkpoint['public_score'] is None and checkpoint['operational_success'] is False,'predecessor_terminal_checkpoint')
    selected=proof['selected_outputs'];rows_={r['provider_path']:r for r in retrieval['files']}
    need(type(selected)is dict and len(rows_)==len(retrieval['files']) and set(selected)==set(rows_) and len(selected)<=12000,'predecessor_exact_selected_inventory')
    for name,desc in selected.items():
        relative(name);relative(desc['path']);r=rows_[name]
        need(type(desc)is dict and set(desc)=={'path','bytes','sha256'} and r['version']==r['numeric_version']==NOTEBOOK_PREDECESSOR and r['http_status']==200 and r['source_kind']=='provider_download' and r['bytes']==desc['bytes'] and r['sha256']==desc['sha256'],'predecessor_selected_numeric_binding')
        verified(root/desc['path'],desc['sha256'],desc['bytes'])
    prefix='irisx-qwen14b-rlvr-20261012-run004';outer=prefix+'-launcher'
    required={prefix+'.evidence.zip',prefix+'.evidence.zip.terminal.json'}
    required.update(prefix+'/'+name for name in ('owner-request.json','owner-clock.json','artifact-inventory.json','outer-closure.json','owned-result.json'))
    required.update(outer+'/'+name for name in ('outer.ipynb','original-request.json','operator.json','parent-private-scorer.json','preparation-request.json','preparation-receipt.json','installed-parent-request.json','interpreter-manifest.json','result.json'))
    for stage in ('preparation','installed-parent'):
        required.update(outer+'/'+stage+'/'+name for name in ('closure.json','owned-tree/launch.json','owned-tree/worker-launch.json','owned-tree/supervisor-result.json','owned-tree/closure.json'))
    need(required<=set(selected) and not set(retrieval['missing_paths'])&required,'predecessor_required_selected_complete')
    def selected_raw(name):
        desc=selected[name];return verified(root/desc['path'],desc['sha256'],desc['bytes'])
    mapping={'evidence_archive':prefix+'.evidence.zip','terminal_receipt':prefix+'.evidence.zip.terminal.json','runtime_outer_closure':prefix+'/outer-closure.json','owned_result':prefix+'/owned-result.json'}
    for name,path in mapping.items():need(raw[name]==selected_raw(path),'predecessor_metadata_selected_link')
    jit_names={'active-finalized.ipynb':'outer.ipynb','original-request.json':'original-request.json','operator.json':'operator.json','parent-private-scorer.json':'parent-private-scorer.json'}
    for name,tail in jit_names.items():
        actual=selected_raw(outer+'/'+tail);desc=final['documents'][name]
        need(sha(actual)==desc['sha256'] and len(actual)==desc['bytes'],'predecessor_jit_document_chain')
    runtime_outer=json.loads(raw['runtime_outer_closure']);owned=json.loads(raw['owned_result'])
    need(runtime_outer['safe_closure'] is False and runtime_outer['model_stopped'] is False and runtime_outer['inner_closure'] is None and runtime_outer['request_sha256'] is None and runtime_outer['journal']['closed'] is False and runtime_outer['worker_exited'] is True and runtime_outer['worker_session_empty'] is True,'predecessor_no_journal_model_closure')
    need(owned['status']=='stopped-incomplete' and owned['production_admitted'] is False and owned['PUBLIC_score'] is None and owned['parent_scoring_ref'] is None,'predecessor_no_public_result')
    archive=check_zip(root/evidence['evidence_archive']['path'],64*1024**2,12000)
    terminal=json.loads(raw['terminal_receipt'])
    need(len(archive)==22 and sum(r['bytes'] for r in archive.values())==15905139 and terminal['status']=='diagnostic' and terminal['archive_complete'] is True and terminal['model_closed'] is False and terminal['production_admitted'] is False,'predecessor_archive_diagnostic')
    need(terminal['archive']['sha256']==PREDECESSOR_ARCHIVE_SHA256 and terminal['archive']['bytes']==15908385 and terminal['archive']['members']==archive,'predecessor_terminal_zip_binding')
    for name in ('owner-request.json','owner-clock.json','artifact-inventory.json','outer-closure.json','owned-result.json'):
        desc=selected[prefix+'/'+name];need(archive.get(name)=={'bytes':desc['bytes'],'sha256':desc['sha256']},'predecessor_archive_compact_binding')
    need('physical-journal.jsonl' not in archive and 'physical-journal.jsonl.anchor' not in archive,'predecessor_journal_absence_not_cost_total')
    historical=proof['historical_v31'];relative(historical['path'])
    need(historical['sha256']==HISTORICAL_V31_SHA256 and historical['bytes']==6450,'historical_v31_exact_binding')
    old=json.loads(verified(root/historical['path'],historical['sha256'],historical['bytes']));old_root=(root/historical['path']).parent
    need(old['numeric_notebook_version']==31 and old['code_dataset_version']==16 and old['provider_status']=='ERROR' and old['terminal_validation_status']=='PARTIAL_INTEGRITY_VERIFIED_COLLECTION_BLOCKED' and old['operational_success'] is False and old['public_score'] is None,'historical_v31_not_relabelled')
    for desc in old['evidence'].values():
        relative(desc['path']);verified(old_root/desc['path'],desc['sha256'],desc['bytes'])
    return proof

def descriptor_at(root,d,cap=128*1024**2):
    relative(d['path']);return verified(root/d['path'],d['sha256'],d['bytes'],cap)

def contract(manifest, allow_preview=False):
    m=obj(manifest);root=Path(manifest).resolve().parent
    need(m['format']==FORMAT,'manifest_format')
    need(allow_preview or m['source_review_only'] is False and m.get('run_authorized') is True and m.get('release_runtime_finalized') is True,'unapproved_preview')
    need(m['candidate_git_published'] is False and m['git_gate_required'] is False and m['owner_published_stable_commit']=='08d6e1c7a7feae044fdd50e6d421b4a7340ea56a','git_provenance')
    verified(root/'SOURCE-FREEZE.json',m['source_freeze_sha256']);predecessor_proof(m,root)
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
        d=f['documents'][name];need(d['path']==str(STATE/name) and d['sha256']==sha(raw) and d['bytes']==len(raw),'finalization_descriptor')
        need(read(STATE/name,4*1024**2)==raw,'finalization_reconstruction')
    need(f['finalized_sha256']==sha(docs['active-finalized.ipynb']),'finalized_notebook_hash')
    return docs


def review_gate(path,digest,manifest_sha,material_sha,required):
    r=json.loads(verified(path,digest));need(r.get('local_config_sha256')==CONFIG.document_sha256,'local_review_config_binding');need(r['status']=='PASS' and r['publication_manifest_sha256']==manifest_sha and r['material_approval_sha256']==material_sha,'operator_review_binding')
    for p in required:need(r['operator_files'][p.name]==file_sha(p),'operator_bytes_not_reviewed')
    return r

def configure_local(args):
    _common.configure(args.local_config,args.local_config_sha,args.manifest,args.manifest_sha)
    globals().update({k:v for k,v in _common.__dict__.items() if not k.startswith('_')})
    need(dict(CONFIG.versions)==profile_versions(),'run005_config_versions')
    need(STATE==CONFIG.scratch_root/'state-run005' and CONFIG.evidence_root==CONFIG.scratch_root/'evidence-run005','run005_fresh_state_namespace')
    need(PINS[0]==DREF+'/'+str(CODE_VERSION),'run005_code_pin_profile')

def load_contract(args):
    configure_local(args)
    verified(args.manifest,args.manifest_sha);m=contract(args.manifest)
    material=json.loads(verified(args.material,args.material_sha))
    need(material['status']=='APPROVED' and material['scope']['publication_manifest']['sha256']==args.manifest_sha,'material_approval')
    approved={(n['role'],n['sha256']) for n in material['approved_notebooks']}
    need(all((n['role'],n['sha256']) in approved for n in m['notebooks']),'approved_notebooks')
    review_gate(args.review,args.review_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py')])
    return m

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

def dataset_check(provider,version):
    d=provider.dataset();need(d.id==12504696 and d.ref==DREF and d.is_private is True and d.current_version_number==version,'dataset_predecessor_identity')
    need(version in (CODE_PREDECESSOR,CODE_VERSION),'dataset_check_exact_successor_versions')
    need(d.title=='IRIS-X Learning Agent Code 20261011' and d.license_name=='Other (specified in description)' and getattr(d,'owner_ref','danielwuu')=='danielwuu','dataset_title_license_owner')
    versions=[v.version_number for v in d.versions]
    need(len(versions)==len(set(versions)) and all(type(v)is int and 1<=v<=version for v in versions),'invalid_dataset_version_history')
    full=set(versions)==set(range(1,version+1))
    need(full or versions==list(range(version,version-10,-1)),'unexpected_dataset_history_window')
    baseline=STATE/'historical-code-v7-inventory.json';historical=[]
    pinned={1:'9a8b5f698c942407b74cc5b16e0ad1d77dd2ac4a6800f991c8bd9f9584353a1b',2:'402aebb539a8163ed516d2e2915c75f5b7a16c56e1d244ac99088f62a2f2e6b9',3:'8c1b22bd9b676ad2a10f31ee820ed4d1732f04dca9d0a81835fdc456c6bd318d',4:'dc87ea2368b0ce1b750b3572327d57adc670474a8c511a485c43704b62c3e01f',5:'54fbc4f2d6543cc82255fdd71113ffce44ca88aab83442f1ac9d80abbe52e255',6:'8db523abc333759e431e396146e991564523aa2d2daac30374a384f86023dcac'}
    for old in (1,2,3,4,5,6,7):
        # Numeric7 is sampled before this successor's code write, then strictly rechecked.
        if old in versions and not (old==7 and version==CODE_PREDECESSOR):continue
        files=provider.list_files(dataset=True,version=old);need(bool(files),'historical_numeric_inventory_empty')
        digest=sha(canonical(files))
        if old in pinned:need(digest==pinned[old],'historical_numeric_version_inventory_changed')
        elif baseline.exists():
            proof=obj(baseline);need(proof['numeric_version']==7 and proof['dataset_id']==12504696 and proof['inventory_sha256']==digest and proof['files_inventory']==files,'numeric7_baseline_changed')
        else:
            need(version==CODE_PREDECESSOR and not (code_state('.claim.json')).exists(),'numeric7_baseline_must_precede_mutation')
            write_new(baseline,{'dataset_id':12504696,'numeric_version':7,'captured_while_current_version':CODE_PREDECESSOR,'inventory_sha256':digest,'files_inventory':files,'payload_bytes_rehashed':False})
        proof={'numeric_version':old,'files':len(files),'bytes_listed':sum(files.values()),'inventory_sha256':digest,'payload_bytes_rehashed':False,'scope':'Official numeric historical file-name/size inventory only; no historical payload byte claim.'}
        historical.append(proof);event('historical-retention',{'dataset_id':12504696,**proof,'files_inventory':files})
    after=provider.dataset();need(after.id==d.id and after.ref==d.ref and after.is_private is True and after.current_version_number==version and [v.version_number for v in after.versions]==versions and after.title==d.title and after.license_name==d.license_name and getattr(after,'owner_ref','danielwuu')==getattr(d,'owner_ref','danielwuu'),'dataset_history_bracket_changed')
    return {'id':d.id,'ref':d.ref,'version':version,'private':True,'license_name':d.license_name,'title':d.title,'owner_ref':getattr(d,'owner_ref',None),'versions':versions,'history_metadata_scope':'complete' if full else 'exact_latest_ten_plus_numeric_historical_inventory','older_version_metadata_proof':historical}


def predecessor(provider,m,role):
    n=row(m,role);expected=n['predecessor_source_sha256']
    if role=='rlvr004':
        rec=obj(STATE/'notebook-inactive-receipt.json');need(rec['version']==INACTIVE_VERSION and rec['status']=='COMPLETE','inactive_not_complete');expected=rec['saved_source']['sha256']
    snapshot,_,_=bracket(provider,n['expected_predecessor_version'],expected,n=row(m,'inactive') if role=='rlvr004' else None)
    need(snapshot['status']==('COMPLETE' if role=='rlvr004' else 'ERROR') and not snapshot['gpu_stop'],'predecessor_status_mismatch')
    return snapshot

def update_code(provider,m,args):
    no_gpu_stop();d=m['datasets'][0];dataset_check(provider,CODE_PREDECESSOR);predecessor(provider,m,'inactive')
    payload=Path(args.manifest).resolve().parent/d['transport_archive']['path'];verified(payload,d['transport_archive']['sha256'],d['transport_archive']['bytes'])
    name=code_claim_name();j={'manifest_sha256':args.manifest_sha,'stage':'claimed','init_calls':0,'put_calls':0,'version_calls':0,'payload_sha256':file_sha(payload),'expected_version':CODE_VERSION,'expected_predecessor_version':CODE_PREDECESSOR}
    c=claim(name,j);j['claim_sha256']=c['sha256'];journal(name,j)
    j.update(stage='init_intent',init_calls=1);journal(name,j);u=provider.start_upload(payload)
    need(bool(u.token) and bool(u.create_url),'upload_init_incomplete')
    origin=urlparse(u.create_url);safe_origin={'scheme':origin.scheme,'hostname':origin.hostname,'port':origin.port or 443,'path_class':'absolute' if origin.path.startswith('/') else 'other','path_segments':len([x for x in origin.path.split('/') if x]),'query_present':bool(origin.query),'token_or_signed_url_persisted':False,'official_init_response':True,'payload_sha256':j['payload_sha256']}
    authority=event('official-staging-authority',safe_origin);j.update(stage='init_accepted_ram_only',authority_metadata_sha256=authority['sha256']);journal(name,j)
    safe_url(u.create_url,upload=True)
    no_gpu_stop();j.update(stage='put_intent',put_calls=1);journal(name,j);upload_once(u.create_url,payload)
    j['stage']='put_accepted';journal(name,j)
    dataset_check(provider,CODE_PREDECESSOR);no_gpu_stop();j.update(stage='version_intent',version_calls=1);journal(name,j)
    r=provider.version(u.token,d['version_notes']);del u
    event('version-response',r.to_dict())
    need(not r.error and r.ref==DREF,'version_response_error');j['stage']='version_accepted';j['response']=r.to_dict();journal(name,j)
    return {'status':'VERSION_ACCEPTED_READBACK_REQUIRED','version':CODE_VERSION}

def expected_layout(m,actual):
    for name,rows_ in m['datasets'][0]['expected_readback_layouts'].items():
        rows_map={r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in rows_}
        if actual==rows_map:return name,rows_map
    raise GuardError('dataset_layout_mismatch')

def verify_code(provider,m,args,per_file=False):
    j=obj(code_state('-journal.json'));need(j['manifest_sha256']==args.manifest_sha and j['version_calls']==1,'no_version_write_to_reconcile')
    need(j['expected_version']==CODE_VERSION and j['expected_predecessor_version']==CODE_PREDECESSOR,'run005_code_journal_versions')
    need(j['claim_sha256']==file_sha(code_state('.claim.json')),'code_claim_binding')
    before=dataset_check(provider,CODE_VERSION);event('code-before',before)
    out=secure_path(STATE/f'code-v{CODE_VERSION}-readback');out.mkdir(exist_ok=True);payload=secure_path(out/'payload');actual={};archive=None
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

def execution_gate(args, *, monitor=False):
    """A supplied exact review admits actions; no future review hash is in code."""
    if monitor:
        review=monitor_gate(args)
        permitted={'activate','verify-run','poll','collect','watch'}
    else:
        review=review_gate(args.review,args.review_sha,args.manifest_sha,args.material_sha,[SCRIPT,SCRIPT.with_name('operator_common.py')])
        permitted={'readiness','update-code','verify-code','verify-code-files','save-inactive','verify-inactive','activate','verify-run','poll'}
    actions=review.get('allowed_actions')
    need(review.get('provider_execution_admitted') is True,'provider_execution_not_reviewed')
    need(review.get('synthetic_test_only') is False,'synthetic_review_cannot_admit_provider_execution')
    need(type(actions)is list and all(type(action)is str for action in actions) and len(actions)==len(set(actions)) and set(actions)<=permitted,'invalid_review_action_scope')
    need(args.action in actions,'provider_action_not_reviewed')
    return review

def run_prerequisites(m,args):
    monitor_gate(args)
    code=obj(code_state('-receipt.json'));inactive=obj(STATE/'notebook-inactive-receipt.json')
    need(code['dataset_id']==12504696 and code['version']==CODE_VERSION and code['is_private'] is True and inactive['kernel_id']==138123872 and inactive['version']==INACTIVE_VERSION,'run005_prerequisite_versions')
    need(code['exact_byte_roundtrip'] is True and code['manifest_sha256']==args.manifest_sha and inactive['manifest_sha256']==args.manifest_sha and inactive['status']=='COMPLETE','publication_readbacks_required')
    need(args.mount and args.mount_sha and args.audit and args.audit_sha,'mount_audit_required')
    mount=json.loads(verified(args.mount,args.mount_sha));audit=json.loads(verified(args.audit,args.audit_sha))
    need(mount['status']=='PASS' and mount['publication_manifest_sha256']==args.manifest_sha and mount['code_dataset_version']==CODE_VERSION and mount['model_calls']==0 and mount['owned_tree_closed'] is True and mount['code_receipt_sha256']==file_sha(code_state('-receipt.json')),'actual_mount_gate')
    need(audit['status']=='PASS' and audit['publication_manifest_sha256']==args.manifest_sha and audit['code_receipt_sha256']==file_sha(code_state('-receipt.json')) and audit['inactive_receipt_sha256']==file_sha(STATE/'notebook-inactive-receipt.json') and audit['mount_receipt_sha256']==args.mount_sha,'persisted_audit_gate')
    return {'mount_receipt_sha256':args.mount_sha,'persisted_audit_sha256':args.audit_sha,'monitor_review_sha256':args.monitor_sha,'code_receipt_sha256':file_sha(code_state('-receipt.json')),'inactive_receipt_sha256':file_sha(STATE/'notebook-inactive-receipt.json')}

def kernel_wire(n,raw):
    return {'id':138123872,'slug':REF,'new_title':n['title'],'text':raw.decode(),'language':'python','kernel_type':'notebook','dataset_data_sources':PINS,'model_data_sources':[MODEL],'competition_data_sources':['arc-prize-2026-arc-agi-3'],'kernel_data_sources':[],'is_private':True,'enable_gpu':n['enable_gpu'],'enable_tpu':False,'enable_internet':False,'docker_image':DOCKER,'kernel_execution_type':n['save_version_value'],'session_timeout_seconds':n['session_timeout_seconds'],'machine_shape':n['machine_shape']}

def save(provider,m,args,role):
    no_gpu_stop();n=row(m,role);active=role=='rlvr004'
    code=obj(code_state('-receipt.json'));need(code['dataset_id']==12504696 and code['version']==CODE_VERSION and code['is_private'] is True and code['manifest_sha256']==args.manifest_sha and code['exact_byte_roundtrip'] is True,'verified_code_required');dataset_check(provider,CODE_VERSION)
    gates=run_prerequisites(m,args) if active else {}
    pre=predecessor(provider,m,role);no_gpu_stop();name='notebook-'+role
    j={'role':role,'reference':REF,'kernel_id':138123872,'expected_version':n['expected_version'],'manifest_sha256':args.manifest_sha,'material_approval_sha256':args.material_sha,'transport_review_sha256':args.review_sha,'save_calls':0,'stage':'claimed','predecessor':pre,'git_publication_completed':False,'git_commit':None,**gates}
    c=claim(name,j);j['claim_sha256']=c['sha256'];journal(name,j)
    raw=verified(Path(args.manifest).resolve().parent/n['path'],n['sha256'],n['bytes'])
    if active:
        epoch=int(time.time());documents=finalized_documents(m,args.manifest,epoch)
        entries={name:write_new(STATE/name,data) for name,data in documents.items()}
        raw=documents['active-finalized.ipynb']
        final={'format':'irisx/rlvr-finalization-v1','manifest_sha256':args.manifest_sha,'template_sha256':n['sha256'],'finalized_sha256':sha(raw),'documents':entries,'finalizer_sha256':m['jit']['entry']['sha256'],**clock(epoch)}
        f=write_new(STATE/'finalization.json',final);j.update(clock(epoch));j['finalization_sha256']=f['sha256']
    else:j.update(dispatch_epoch=None,deadline_epoch=None,provider_timeout_seconds=None)
    wire=kernel_wire(n,raw);w=write_new(STATE/(name+'-wire.json'),wire)
    j.update(stage='save_intent',save_calls=1,source_sha256=sha(raw),wire_sha256=w['sha256'],dispatch_sample_epoch=time.time())
    if active:j['dispatch_epoch']=j['dispatch_sample_epoch']
    journal(name,j)
    if active:need(0<=time.time()-j['predispatch_epoch']<=60,'stale_epoch_no_send')
    no_gpu_stop();r=provider.save(wire)
    event(name+'-response',r.to_dict())
    if r.error:
        classification,message=classify(None,r.error)
        event('save-response-error',{'classification':classification,'message':message,'role':role})
        if classification=='GPU_UNAVAILABLE_STOP' and not STOP.exists():write_new(STOP,{'classification':classification,'message':message,'time_epoch':time.time()})
        raise ProviderReportedError(clean_message(r.error))
    need(r.kernel_id==138123872 and r.ref in (REF,'/code/'+REF) and r.version_number==n['expected_version'] and not r.invalid_dataset_sources and not r.invalid_model_sources and not r.invalid_competition_sources and not r.invalid_kernel_sources,'save_response_identity')
    j.update(stage='save_accepted',save_accepted=True,response_version=r.version_number,accepted_epoch=time.time());journal(name,j)
    return {'status':'SAVE_ACCEPTED','version':r.version_number,'role':role}

def verify_notebook(provider,m,args,role):
    name='notebook-'+role;n=row(m,role);j=obj(STATE/(name+'-journal.json'))
    need(j['expected_version']==n['expected_version'] and j['manifest_sha256']==args.manifest_sha and j['save_calls']==1 and j['claim_sha256']==file_sha(STATE/(name+'.claim.json')) and j['git_publication_completed'] is False and j['git_commit'] is None,'launch_journal_binding')
    raw=read(STATE/'active-finalized.ipynb') if role=='rlvr004' else read(Path(args.manifest).resolve().parent/n['path'])
    need(sha(raw)==j['source_sha256'],'submitted_source_binding')
    if role=='rlvr004':
        f=obj(STATE/'finalization.json');need(file_sha(STATE/'finalization.json')==j['finalization_sha256'] and f['finalized_sha256']==sha(raw) and f['manifest_sha256']==args.manifest_sha,'finalization_binding')
        check_finalization(m,args,f)
        need(all(j.get(k)==v for k,v in clock(f['predispatch_epoch']).items() if k!='dispatch_epoch') and 0<=j['dispatch_epoch']-f['predispatch_epoch']<=60,'launch_clock_binding')
    snap,saved,meta=bracket(provider,n['expected_version'],n=n)
    need(source_normalize(saved)==source_normalize(raw),'provider_source_normalization')
    if role=='inactive':need(snap['status']=='COMPLETE','inactive_not_complete')
    source_path=STATE/(name+'-saved.ipynb')
    if source_path.exists():need(read(source_path)==saved,'saved_source_changed_after_receipt')
    else:write_new(source_path,saved)
    result={'manifest_sha256':args.manifest_sha,'reference':REF,'kernel_id':138123872,'version':n['expected_version'],'status':snap['status'],'role':role,'submitted_source_sha256':sha(raw),'saved_source':descriptor(source_path),'normalized_source_exact':True,'model_sources_returned':meta.model_data_sources,'dataset_sources_returned':meta.dataset_data_sources,'settings':meta.to_dict(),'launch_journal_sha256':file_sha(STATE/(name+'-journal.json')),'finalization_sha256':file_sha(STATE/'finalization.json') if role=='rlvr004' else None,'predecessor':j['predecessor'],'snapshot':snap,'git_publication_completed':False,'git_commit':None}
    dest=STATE/(name+'-receipt.json')
    if dest.exists():
        prior=obj(dest);need(prior['saved_source']==result['saved_source'] and prior['launch_journal_sha256']==result['launch_journal_sha256'],'receipt_reconciliation_changed');event(name+'-observation',result)
    else:write_new(dest,result)
    return result

def parser():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['validate','readiness','update-code','verify-code','verify-code-files','save-inactive','verify-inactive','activate','verify-run','poll'])
    for x in ('manifest','manifest-sha','material','material-sha','review','review-sha','local-config','local-config-sha'):p.add_argument('--'+x,required=True)
    for x in ('monitor-review','monitor-sha','mount','mount-sha','audit','audit-sha','consumer-root'):p.add_argument('--'+x)
    return p

def main():
    a=parser().parse_args();provider=None
    try:
        m=load_contract(a)
        if a.action=='validate':print(json.dumps({'status':'LOCAL_CONTRACT_PASS','provider_calls':0}));return 0
        execution_gate(a)
        if a.action in ('activate','verify-run','poll'):execution_gate(a,monitor=True)
        if a.action in ('update-code','save-inactive','activate'):no_gpu_stop()
        with lock():
            provider=Provider()
            if a.action=='readiness':result={'dataset':dataset_check(provider,CODE_PREDECESSOR),'predecessor':predecessor(provider,m,'inactive')}
            elif a.action=='update-code':result=update_code(provider,m,a)
            elif a.action in ('verify-code','verify-code-files'):result=verify_code(provider,m,a,a.action.endswith('files'))
            elif a.action in ('save-inactive','activate'):result=save(provider,m,a,'inactive' if a.action=='save-inactive' else 'rlvr004')
            elif a.action in ('verify-inactive','verify-run'):result=verify_notebook(provider,m,a,'inactive' if a.action=='verify-inactive' else 'rlvr004')
            else:
                r=obj(STATE/'notebook-rlvr004-receipt.json');result,_,_=bracket(provider,ACTIVE_VERSION,r['saved_source']['sha256'],row(m,'rlvr004'))
            print(json.dumps(result));return 0
    except Exception as e:print(json.dumps(failure(e,a.action)));return 2
    finally:
        if provider:provider.close()
if __name__=='__main__':raise SystemExit(main())
