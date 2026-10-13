"""Future independently pinned release/launch content. No live authority is minted.

Release bytes are immutable across runs; launch-envelope digest is delivered by
an authenticated outer collector per run. All file paths below are local only.
The current top-level validator has no admitted release anchor.
"""
import math,zipfile
from .safe_io import Root,need,same,digest,is_sha,integer,finite,relative,sha,inspect_tensor_zip


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
    names={'outer_notebook','operator','original_request','source_archive'}
    need(type(launch['files']) is dict and set(launch['files'])==names,'complete actual outer release files required')
    raw={}
    for name,ref in launch['files'].items():
        need(type(ref) is dict and set(ref)=={'path','file_sha256'},'closed launch member reference')
        relative(ref['path']);need(is_sha(ref['file_sha256']) and ext.file_sha(ref['path'],256*1024**2)==ref['file_sha256'],'actual outer bytes differ: '+name)
        raw[name]=ext.json(ref['path']) if name!='source_archive' else ref
    bootstrap=envelope['request'].get('bootstrap',{})
    for name in names:need(bootstrap.get(name,{}).get('file_sha256')==launch['files'][name]['file_sha256'],'runtime bootstrap differs from independently bound outer bytes')
    need(bootstrap.get('material_review',{}).get('file_sha256')==release['material_review_sha256'],'actual material review differs')
    operator=raw['operator'];owner=raw['original_request'];notebook=raw['outer_notebook']
    need(notebook.get('metadata',{}).get('owned_rl_release')=={'format':'owned-rl-outer-notebook-v1','operator_sha256':launch['files']['operator']['file_sha256']},'actual outer notebook/operator binding')
    need(operator.get('format')=='owned-rl-reviewed-operator-v1' and operator.get('raw_source_sha256')==source_sha256,'actual operator/source binding')
    for name in ('original_request','source_archive'):need(operator.get(name+'_sha256')==launch['files'][name]['file_sha256'],'actual operator raw member binding')
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
    sr=Root(source_root);policyname='independent-protocol-review/PROVISIONAL-DEFAULTS.json'
    need(sr.file_sha(policyname)==release['phase_policy_sha256'],'runtime source policy differs from independently reviewed phase policy')
    # Worker source reads these exact externally reviewed input bytes.
    need(type(launch['review_inputs']) is dict and set(launch['review_inputs'])=={'environment','phase_policy'},'independently bound actual review input paths required')
    for k in ('environment','phase_policy'):
        ref=cfg.get('environment_path' if k=='environment' else 'policy_path')
        need(type(ref) is str and ref and launch['review_inputs'][k]=={'path':ref,'file_sha256':release[k+'_sha256']},'actual configured review input bytes/path differ')
    return {'release':release,'documents':docs,'launch_sha256':launch_sha256,'independent_release_sha256':release_sha256}


def source_policy(plan,policy,policy_sha256):
    """Replay the exact current source builder without importing producer code."""
    c=policy['phase_constants']
    expected={'evidence_sha256':policy_sha256,'evidence_kind':'v25-source-bound-pending-review',
      'setup_seconds':float(c['common_setup_calibration_anchor_forecast_seconds']),'sweep_seconds':float(32*8*45+30),
      'control_step_seconds':float(c['control_step_forecast_seconds']),'persist_reload_seconds':float(c['arm_finalization_forecast_seconds']),
      'evaluation_seconds':float(c['ABC_reserve_seconds']),'public_seconds':float(c['selected_PUBLIC_reserve_seconds']),
      'failure_margin_seconds':float(c['future_reload_persistence_reserve_seconds']),'closure_seconds':float(c['cleanup_reserve_seconds'])}
    need(same(plan.get('forecast'),expected),'actual phase forecast differs from exact source-bound policy recipe')
    need(same(plan.get('anchor_schedule'),{'base_lr':2e-4,'warmup':4,'cosine_steps':256,'min_lr_ratio':.1}) and plan.get('comparison')=='intervention-package','actual anchor schedule/comparison differs')
    need(plan['inference']['max_new_tokens']==1024 and plan['shape']['max_sweeps']==4 and plan['shape']['max_control_updates']==8192,'production caps/schedule cannot shrink')


def model_admission(root,envelope,proof,environment):
    row=root.json('session-admission.json');native=row.get('native_identity',{});actual=row.get('actual_environment')
    need(row.get('format')=='owned-session-admission-v1' and row.get('consumed') is True and row.get('scope')=='source-admitted-pretrained-session','actual consumed production Session required')
    need(row.get('pid')==envelope['outer']['worker_pid'] and row.get('source_sha256')==proof['source_sha256'] and row.get('plan_sha256')==proof['plan_sha256'] and row.get('owner_request_sha256')==root.file_sha('owner-request.json') and same(row.get('clock'),envelope['clock']),'session actual owner/source/clock/plan identity')
    need(environment.get('format')=='owned-rl-reviewed-environment-v1' and same(actual,environment.get('actual_environment')) and same(envelope['request']['config'].get('model'),environment.get('model_config')),'actual package/hardware/model config differs from independently reviewed environment')
    projection=environment.get('native_identity_projection');required={'model_key','profile_id','material_addendum_sha256','pretrained_weights_loaded','probe_pretrained_admitted'}
    need(type(projection) is dict and required<=set(projection) and all(same(native.get(k),v) for k,v in projection.items()),'actual authenticated native identity differs from reviewed model/weights')
    need(native.get('pretrained_weights_loaded') is True and native.get('probe_pretrained_admitted') is True and not native.get('random_test_weights') and native.get('base_precision')=='bfloat16','actual pretrained BF16 native model missing')
    need(same(row.get('actual_topology'),dict(hidden_size=5120,num_hidden_layers=40,vocab_size=151936,num_attention_heads=40,num_key_value_heads=8,context_limit=4096,prompt_cap=3072,output_cap=1024)),'actual14B/context topology differs')
    need(type(actual) is dict and actual.get('device_count')==1 and len(actual.get('devices',[]))==1 and actual['devices'][0].get('index')==0 and integer(actual['devices'][0].get('total_memory_bytes'),1,1024**4),'actual admitted single CUDA device required')
    params=row.get('peft_parameters');need(type(params) is dict and len(params)==560,'actual complete40-layer seven-projection LoRA inventory')
    for name,p in params.items():need(p.get('dtype')=='torch.float32' and p.get('device')=='cuda:0' and p.get('elements')==math.prod(p.get('shape',[])),'actual FP32 CUDA PEFT inventory')
    from .tensor_checks import validate_adapter_descriptors
    validate_adapter_descriptors(params,False)
    for cp in proof['checkpoints'].values():
        need(cp['base_identity_sha256']==digest(native)==row.get('trainer_base_identity_sha256') and cp['structure_sha256']==row.get('trainer_structure_sha256'),'actual admission native/base/structure differs from persisted states')
    need(is_sha(row.get('calibration_sha256')),'owned actual calibration identity missing')
    return {'native_identity_sha256':digest(native),'environment_sha256':digest(actual),'session_pid':row['pid']}


def session_receipt(root,envelope,proof,*,synthetic):
    row=root.json('session-admission.json');native=row.get('native_identity')
    need(type(native) is dict and row.get('consumed') is True and row.get('pid')==envelope['outer']['worker_pid'],'actual owned native session identity required')
    need(row.get('source_sha256')==proof['source_sha256'] and row.get('plan_sha256')==proof['plan_sha256'] and row.get('owner_request_sha256')==root.file_sha('owner-request.json') and same(row.get('clock'),envelope['clock']),'actual Session owner/source/plan/clock differs')
    for cp in proof['checkpoints'].values():need(cp['base_identity_sha256']==digest(native)==row.get('trainer_base_identity_sha256') and cp['structure_sha256']==row.get('trainer_structure_sha256'),'native Session differs from actual checkpoint base/structure')
    actual=row.get('actual_environment');need(type(actual) is dict and set(actual)=={'python_version','torch_version','transformers_version','peft_version','tokenizers_version','cuda_version','cudnn_version','device_count','devices'},'complete observed package/device environment')
    need(all(type(actual[k]) is str and actual[k] for k in ('python_version','torch_version','transformers_version','peft_version','tokenizers_version')),'actual package versions missing')
    from .tensor_checks import validate_adapter_descriptors
    params=row.get('peft_parameters');validate_adapter_descriptors(params,synthetic)
    for name,p in params.items():need(p.get('elements')==math.prod(p['shape']) and p.get('device')==('cpu' if synthetic else 'cuda:0'),'actual PEFT device/parameter count differs')
    if synthetic:need(native.get('random_test_weights') is True and native.get('pretrained_weights_loaded') is False and row.get('scope')=='native-tiny-CPU-fixture','tiny source cannot claim native pretrained efficacy')
    for label in ('base','A','B','C'):
        summary=root.json('experiment/checkpoints/'+label+'/state-summary.json');adapters=summary['state_tree']['adapters']
        need(set(params)==set(adapters) and all(params[n]['shape']==adapters[n]['shape'] and params[n]['dtype']==adapters[n]['dtype'] for n in params),'actual PEFT inventory differs from persisted checkpoint descriptors')
    return {'native_identity_sha256':digest(native),'environment_sha256':digest(actual),'session_pid':row['pid']}
