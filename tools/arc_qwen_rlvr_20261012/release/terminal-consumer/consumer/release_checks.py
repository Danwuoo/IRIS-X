"""Future independently pinned release/launch content. No live authority is minted.

Release bytes are immutable across runs; launch-envelope digest is delivered by
an authenticated outer collector per run. All file paths below are local only.
The current top-level validator has no admitted release anchor.
"""
import math,zipfile
from .safe_io import Root,need,same,digest,canonical,is_sha,integer,finite,relative,sha,inspect_tensor_zip


def checked_document(root,name,expected):
    need(is_sha(expected) and root.file_sha(name)==expected,'independent release document bytes differ: '+name)
    return root.json(name)


def release_binding(root,source_root,envelope,*,release_root,release_sha256,launch_sha256,source_sha256,inventory_sha256):
    ext=Root(release_root)
    release=checked_document(ext,'release.json',release_sha256)
    fields={'format','source_sha256','material_review_sha256','environment_sha256','phase_policy_sha256','owner_protocol_sha256'}
    need(set(release)==fields and release['format']=='owned-rl-independent-release-v1','closed independently reviewed release schema')
    need(release['source_sha256']==source_sha256,'independent release source differs')
    docs={k:checked_document(ext,k+'.json',release[k+'_sha256']) for k in ('material_review','environment','phase_policy','owner_protocol')}
    launch=checked_document(ext,'launch.json',launch_sha256)
    need(set(launch)=={'format','release_sha256','files','owner_request_sha256','owner_clock_sha256','artifact_inventory_sha256','review_inputs','checkpoint_archive_observation_sha256'} and launch['format']=='owned-rl-independent-launch-v1','closed authenticated per-run launch schema')
    need(launch['release_sha256']==release_sha256 and launch['owner_request_sha256']==root.file_sha('owner-request.json') and launch['owner_clock_sha256']==root.file_sha('owner-clock.json') and launch['artifact_inventory_sha256']==inventory_sha256,'fresh launch owner/clock/artifact binding differs')
    names={'outer_notebook','operator','original_request','source_archive','parent_scorer'}
    need(type(launch['files']) is dict and set(launch['files'])==names,'complete actual outer release files required')
    raw={}
    for name,ref in launch['files'].items():
        need(type(ref) is dict and set(ref)=={'path','file_sha256'},'closed launch member reference')
        relative(ref['path']);need(is_sha(ref['file_sha256']) and ext.file_sha(ref['path'],256*1024**2)==ref['file_sha256'],'actual outer bytes differ: '+name)
        raw[name]=ext.json(ref['path']) if name!='source_archive' else ref
    bootstrap=envelope['request'].get('bootstrap',{})
    for name in names:
        actual=bootstrap.get('parent_scorer_sha256') if name=='parent_scorer' else bootstrap.get(name,{}).get('file_sha256')
        need(actual==launch['files'][name]['file_sha256'],'runtime bootstrap differs from independently bound outer bytes')
    need(bootstrap.get('material_review',{}).get('file_sha256')==release['material_review_sha256'],'actual material review differs')
    operator=raw['operator'];owner=raw['original_request'];notebook=raw['outer_notebook']
    need(notebook.get('metadata',{}).get('owned_rl_release')=={'format':'owned-rl-outer-notebook-v1','operator_sha256':launch['files']['operator']['file_sha256']},'actual outer notebook/operator binding')
    need(operator.get('format')=='owned-rl-reviewed-operator-v2' and operator.get('raw_source_sha256')==source_sha256,'actual operator/source binding')
    for name in ('original_request','source_archive','parent_scorer'):need(operator.get(name+'_sha256')==launch['files'][name]['file_sha256'],'actual operator raw member binding')
    need(operator.get('material_review_sha256')==release['material_review_sha256'],'actual operator material review binding')
    policy=docs['owner_protocol']
    need(policy.get('format')=='owned-rl-reviewed-owner-protocol-v1' and policy.get('scope')=='production-rl-abc' and policy.get('role')=='rl-abc','reviewed owner protocol')
    need(owner.get('format')=='owned-rl-original-owner-request-v1' and set(owner)=={'format','scope','role','original_epoch','request_id','owner_id','instruction'},'actual original owner request schema')
    for k in ('scope','role'):need(owner[k]==operator.get(k)==policy[k]==bootstrap.get(k),'actual owner scope/role differs')
    need(finite(owner['original_epoch']) and owner['original_epoch']==envelope['clock']['original_epoch']==operator.get('original_epoch')==bootstrap.get('original_epoch'),'original authenticated owner epoch cannot reset')
    need(owner['request_id']==operator.get('original_request_id')==bootstrap.get('original_request_id') and owner['owner_id']==operator.get('owner_id')==bootstrap.get('owner_id'),'actual authenticated owner identity differs')
    need(all(type(owner[k]) is str and owner[k] for k in ('request_id','owner_id','instruction')),'actual owner instruction missing')
    archive=ext.member(raw['source_archive']['path']);inspect_tensor_zip(archive,maximum_bytes=256*1024**2,maximum_members=10000)
    with zipfile.ZipFile(archive) as z:
        need(set(z.namelist())==set(envelope['source']['files']),'actual outer source ZIP complete inventory differs')
        for name,h in envelope['source']['files'].items():need(sha(z.read(name))==h,'outer ZIP actual source bytes differ')
    cfg=envelope['request']['config']
    need(cfg.get('fixture') is False and 'failure_fixture' not in cfg,'production model request fixture contamination')
    sr=Root(source_root);policyname='design/MEASURED-POLICY.json'
    need(sr.file_sha(policyname)==release['phase_policy_sha256'],'runtime source policy differs from independently reviewed phase policy')
    # Worker source reads these exact externally reviewed input bytes.
    need(type(launch['review_inputs']) is dict and set(launch['review_inputs'])=={'environment','phase_policy'},'independently bound actual review input paths required')
    for k in ('environment','phase_policy'):
        ref=cfg.get('environment_path' if k=='environment' else 'policy_path')
        need(type(ref) is str and ref and launch['review_inputs'][k]=={'path':ref,'file_sha256':release[k+'_sha256']},'actual configured review input bytes/path differ')
    return {'release':release,'documents':docs,'launch_sha256':launch_sha256,'independent_release_sha256':release_sha256}


def source_policy(plan,policy,policy_sha256,*,source_root):
    """Recompute measured disjoint-batch forecast from byte-pinned cost evidence."""
    sr=Root(source_root)
    need(policy_sha256=='3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda'
         and sr.file_sha('design/MEASURED-POLICY.json')==policy_sha256 and same(sr.json('design/MEASURED-POLICY.json'),policy),
         'independently frozen new scientific policy bytes required')
    expected_cost='ae7dbc7584fe9f54db0444f54c72fed8ac2b56031d74f1e0d18f46bb38c8b1f2'
    need(sr.file_sha('design/COST-EVIDENCE.json')==expected_cost==policy['evidence_sha256'],'measured cost evidence bytes differ')
    costs=sr.json('design/COST-EVIDENCE.json');r=policy['reserves_seconds'];c=policy['cost_model']
    sample=c['rollout_factor']*costs['public']['observed_generation_metrics']['elapsed_seconds']['sum']/costs['public']['views']
    expected={'evidence_sha256':expected_cost,'evidence_kind':'v25-source-bound-pending-review',
      'setup_seconds':float(r['common_setup_calibration_anchor']),
      'sweep_seconds':64*(sample+c['replay_forecast_per_trajectory_seconds'])+c['batch_bookkeeping_seconds'],
      'control_step_seconds':float(c['control_step_forecast_seconds']),'persist_reload_seconds':float(r['B_finalization']),
      'evaluation_seconds':float(r['paired_ABC']),'public_seconds':float(r['selected_PUBLIC']),
      'failure_margin_seconds':float(r['future_common_reload_persistence']),'closure_seconds':float(r['closure'])}
    need(same(plan.get('forecast'),expected),'source measured phase forecast recipe differs')
    need(plan.get('measured_policy_sha256')==policy_sha256 and plan.get('batch_semantics')=='disjoint-fixed-prefix',
         'exact measured batch policy identity differs')


def model_admission(root,envelope,proof,environment):
    row=root.json('session-admission.json');native=row.get('native_identity',{});actual=row.get('actual_environment')
    need(row.get('format')=='owned-session-admission-v1' and row.get('consumed') is True and row.get('scope')=='source-admitted-pretrained-session','actual consumed production Session required')
    need(row.get('pid')==envelope['outer']['worker_pid'] and row.get('source_sha256')==proof['source_sha256'] and row.get('plan_sha256')==proof['plan_sha256'] and row.get('owner_request_sha256')==root.file_sha('owner-request.json') and same(row.get('clock'),envelope['clock']),'session actual owner/source/clock/plan identity')
    need(environment.get('format')=='owned-rl-reviewed-environment-v2' and same({k:v for k,v in actual.items() if k!='cudnn_version'},environment.get('actual_environment')) and same(envelope['request']['config'].get('model'),environment.get('model_config')),'actual package/hardware/model config differs from independently reviewed environment')
    verify_cudnn_receipt(row,environment,proof['events'])
    projection=environment.get('native_identity_projection');required={'model_key','profile_id','material_addendum_sha256','pretrained_weights_loaded','probe_pretrained_admitted'}
    need(type(projection) is dict and required<=set(projection) and all(same(native.get(k),v) for k,v in projection.items()),'actual authenticated native identity differs from reviewed model/weights')
    need(native.get('pretrained_weights_loaded') is True and native.get('probe_pretrained_admitted') is True and not native.get('random_test_weights') and native.get('base_precision')=='bfloat16','actual pretrained BF16 native model missing')
    need(same(row.get('actual_topology'),dict(hidden_size=5120,num_hidden_layers=40,vocab_size=151936,num_attention_heads=40,num_key_value_heads=8,context_limit=4096,prompt_cap=3072,output_cap=1024)),'actual14B/context topology differs')
    need(type(actual) is dict and actual.get('device_count')==1 and len(actual.get('devices',[]))==1 and actual['devices'][0].get('index')==0 and integer(actual['devices'][0].get('total_memory_bytes'),1,1024**4),'actual admitted single CUDA device required')
    params=row.get('peft_parameters');need(type(params) is dict and len(params)==560,'actual complete40-layer seven-projection LoRA inventory')
    for name,p in params.items():need(p.get('dtype')=='torch.float32' and p.get('device')=='cuda:0' and p.get('elements')==math.prod(p.get('shape',[])),'actual FP32 CUDA PEFT inventory')
    from .tensor_checks import validate_adapter_descriptors
    validate_adapter_descriptors(params,False)
    admission_hash_domains(row,proof['checkpoints'],synthetic=False,require_projection=True)
    need(is_sha(row.get('calibration_sha256')),'owned actual calibration identity missing')
    return {'native_identity_sha256':digest(native),'environment_sha256':digest(actual),'session_pid':row['pid']}


def verify_cudnn_receipt(row,environment,events):
    """Runtime-bound observed wheel/library proof; never infer prior cuDNN scalar."""
    from pathlib import PurePosixPath
    policy={'mode':'pinned-wheel-mapped-library-current-observation-v1','prior_runtime_integer_observed':False,
        'distribution':'nvidia-cudnn-cu12','distribution_version':'9.10.2.21',
        'wheel_name':'nvidia_cudnn_cu12-9.10.2.21-py3-none-manylinux_2_27_x86_64.whl',
        'wheel_bytes':706758467,'wheel_sha256':'949452be657fa16687d0930933f032835951ef0892b37d2d53824d1a84dc97a8',
        'library_member':'nvidia/cudnn/lib/libcudnn.so.9','library_api':'size_t cudnnGetVersion(void)'}
    need(same(environment.get('cudnn_policy'),policy),'exact source-owned cuDNN library policy differs')
    observed=row.get('environment_verification')
    need(type(observed) is dict and observed.get('format')=='owned-rl-cudnn-current-library-observation-v1'
         and observed.get('prior_runtime_integer_observed') is False,'cuDNN current observation required without invented prior scalar')
    for key in ('distribution','distribution_version','wheel_sha256','wheel_bytes'):
        need(same(observed.get(key),policy[key]),'observed cuDNN exact wheel identity differs: '+key)
    value=observed.get('torch_cudnn_version')
    need(integer(value,1,2**31) and value==observed.get('library_cudnn_version')==row['actual_environment']['cudnn_version']
         and observed.get('ctypes_signature')==policy['library_api'],'actual current cuDNN version/ABI differs')
    need(observed.get('all_observed_cudnn_mappings_verified') is True and observed.get('full_installed_vendor_library_set_verified') is True
         and observed.get('source_of_version')=='current-process-observation; not an inferred v25 scalar','complete observed cuDNN provenance required')
    libraries=observed.get('verified_libraries');mapped=observed.get('mapped_library_paths')
    need(type(libraries) is list and 0<len(libraries)<=32 and type(mapped) is list and mapped,'complete bounded cuDNN library receipt')
    paths=set();members=set();parents=set()
    for library in libraries:
        need(set(library)=={'member','path','bytes','sha256'} and is_sha(library['sha256']) and integer(library['bytes'],1,2*policy['wheel_bytes']),
             'closed observed cuDNN library hash/length')
        path=PurePosixPath(library['path']);member=PurePosixPath(library['member'])
        need(path.is_absolute() and member.parent.as_posix()=='nvidia/cudnn/lib' and path.name==member.name
             and 'site-packages' in path.parts and path.name.startswith('libcudnn') and '.so' in path.name,
             'cuDNN verified installed member/path differs')
        need(library['path'] not in paths and library['member'] not in members,'duplicate cuDNN library receipt')
        paths.add(library['path']);members.add(library['member']);parents.add(path.parent)
    need(policy['library_member'] in members and len(parents)==1 and len(set(mapped))==len(mapped) and set(mapped)<=paths,
         'mapped cuDNN backend outside exact verified library set')
    need(any(PurePosixPath(p).name=='libcudnn.so.9' for p in mapped),'actual cuDNN API library mapping absent')
    actual=[e for e in events.values() if e['phase']=='environment-admission']
    need(len(actual)==1 and actual[0]['dispatched'] and actual[0]['status']=='complete'
         and actual[0].get('reserved_cost')==actual[0].get('actual_cost')=={'environment_verifications':1},
         'actual metered cuDNN/environment admission missing')


def session_receipt(root,envelope,proof,*,synthetic):
    row=root.json('session-admission.json');native=row.get('native_identity')
    need(type(native) is dict and row.get('consumed') is True and row.get('pid')==envelope['outer']['worker_pid'],'actual owned native session identity required')
    need(row.get('source_sha256')==proof['source_sha256'] and row.get('plan_sha256')==proof['plan_sha256'] and row.get('owner_request_sha256')==root.file_sha('owner-request.json') and same(row.get('clock'),envelope['clock']),'actual Session owner/source/plan/clock differs')
    identity_check=admission_hash_domains(row,proof['checkpoints'],synthetic=synthetic,require_projection=proof.get('structural_projection_required',False))
    actual=row.get('actual_environment');need(type(actual) is dict and set(actual)=={'python_version','torch_version','transformers_version','peft_version','tokenizers_version','cuda_version','cudnn_version','device_count','devices'},'complete observed package/device environment')
    need(all(type(actual[k]) is str and actual[k] for k in ('python_version','torch_version','transformers_version','peft_version','tokenizers_version')),'actual package versions missing')
    from .tensor_checks import validate_adapter_descriptors
    params=row.get('peft_parameters');validate_adapter_descriptors(params,synthetic)
    for name,p in params.items():need(p.get('elements')==math.prod(p['shape']) and p.get('device')==('cpu' if synthetic else 'cuda:0'),'actual PEFT device/parameter count differs')
    if synthetic:need(native.get('random_test_weights') is True and native.get('pretrained_weights_loaded') is False and row.get('scope')=='native-tiny-CPU-fixture','tiny source cannot claim native pretrained efficacy')
    for label in ('base','A','B','C'):
        from .tensor_checks import checkpoint_root
        summary=checkpoint_root(Root(root.path/'experiment'),label).json('state-summary.json');adapters=summary['state_tree']['adapters']
        need(set(params)==set(adapters) and all(params[n]['shape']==adapters[n]['shape'] and params[n]['dtype']==adapters[n]['dtype'] for n in params),'actual PEFT inventory differs from persisted checkpoint descriptors')
    return {'native_identity_sha256':digest(native),'environment_sha256':digest(actual),'session_pid':row['pid'],**identity_check}


ADMISSION_CANONICALIZATION={'admission':'json-sort-keys-compact-allow_nan_false-utf8-ascii-escaped-final-newline','checkpoint':'json-sort-keys-compact-allow_nan_false-utf8-ascii-escaped-no-newline'}

def admission_hash_domains(row,checkpoints,*,synthetic,require_projection):
    native=row['native_identity'];core=digest(native);admission=sha(canonical(native)+b'\n')
    need(row.get('trainer_base_identity_sha256')==admission and all(cp['base_identity_sha256']==core for cp in checkpoints.values()),'actual emitted native identity differs in its source-defined canonical domain')
    structures={cp['structure_sha256'] for cp in checkpoints.values()}
    need(len(structures)==1 and all(is_sha(h) for h in structures) and is_sha(row.get('trainer_structure_sha256')),'complete same-session checkpoint structural commitments required')
    raw=row.get('structural_projection')
    if raw is None:
        need(synthetic and not require_projection,'raw structural projection/canonicalization bridge required before production')
        return {'independent_admission_structure_cross_domain_verification':False,'structural_bridge_status':'UNAVAILABLE_RAW_PROJECTION_NOT_EMITTED','production_structural_admission_eligible':False,'process_local_callable_ids_portable':False,'admission_native_identity_sha256':admission,'checkpoint_native_identity_sha256':core}
    need(type(raw) is dict and set(raw)=={'native_config','checkpoint_functions','config','attention','checkpointing','recipe','scalars','trainer_config'},'closed actual native structural projection')
    need(same(row.get('canonicalization'),ADMISSION_CANONICALIZATION),'explicit source-defined canonicalization identifiers required')
    need(sha(canonical(raw)+b'\n')==row['trainer_structure_sha256'] and digest(raw)==next(iter(structures))==row.get('checkpoint_structure_sha256') and row.get('checkpoint_base_identity_sha256')==core,'actual raw structure does not bridge both canonicalization domains')
    need(raw['checkpointing'] is True and type(raw['checkpoint_functions']) is dict and raw['checkpoint_functions'],'actual checkpointing structure required')
    for value in raw['checkpoint_functions'].values():need(set(value)=={'function','kwargs'} and integer(value['function'],1,2**64-1) and value['kwargs']=={'use_reentrant':False},'same-process nonreentrant checkpoint callable projection')
    return {'independent_admission_structure_cross_domain_verification':True,'structural_bridge_status':'ACTUAL_RAW_PROJECTION_VERIFIED','production_structural_admission_eligible':True,'process_local_callable_ids_portable':False,'admission_native_identity_sha256':admission,'checkpoint_native_identity_sha256':core}
