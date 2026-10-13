"""Source-owned runtime reload receipt mode; NEVER independent tensor verification."""
import math,struct
from .safe_io import Root,need,integer,finite,is_sha,digest,sha,same
from .tensor_checks import STATE_KEYS,COUNTER_LIMITS,anchor_multiplier,validate_adapter_descriptors,checkpoint_root

FORMAT='owned-rl-state-summary-v1'
OMITTABLE=('state.pt','adapter/adapter_model.safetensors')

def validate_tensor_tree(tree):
    nodes=[0]
    def walk(v,depth=0):
        nodes[0]+=1;need(depth<=64 and nodes[0]<=2000000,'compact state tree bound')
        if type(v) is dict:
            if v.get('tensor') is True:
                need(set(v)=={'tensor','dtype','shape','sha256'} and v['dtype'] in ('torch.float32','torch.float64','torch.float16','torch.bfloat16','torch.int64','torch.int32','torch.int16','torch.int8','torch.uint8','torch.bool') and type(v['shape']) is list and all(integer(n,0,100000000) for n in v['shape']) and math.prod(v['shape'])<=128000000 and is_sha(v['sha256']),'closed compact tensor descriptor')
            else:
                need(all(type(k) is str for k in v),'compact tree mapping keys')
                for x in v.values():walk(x,depth+1)
        elif type(v) is list:
            for x in v:walk(x,depth+1)
        else:need(v is None or type(v) in (str,bool,int,float) and (type(v) is not float or finite(v)),'compact tensor primitive type')
    walk(tree)


def replay_state_summary(summary,*,label,anchor_updates,expected_core_source_sha256,synthetic):
    need(set(summary)=={'format','state_sha256','adapter_sha256','state_tree','optimizer_step_values','optimizer_parameter_names','cleared_gradients'} and summary['format']==FORMAT and summary['cleared_gradients'] is True,'complete source-owned compact state summary required')
    tree=summary['state_tree'];validate_tensor_tree(tree)
    need(type(tree) is dict and set(tree)==STATE_KEYS and digest(tree)==summary['state_sha256'],'complete compact state fingerprint differs')
    c=tree['counters'];need(type(c) is dict and set(c)==set(COUNTER_LIMITS) and all(integer(c[k],0,n) for k,n in COUNTER_LIMITS.items()),'strict compact counters')
    stage={'base':'anchor','A':'anchor','B':'rl','C':'control'}['B' if label.startswith('B-batch-') else label]
    need(tree['stage']==stage and c['anchor_updates']==(0 if label=='base' else anchor_updates),'compact branch/anchor count')
    need(c['optimizer_steps']==c['scheduler_steps']==c[stage+'_updates'],'compact optimizer/scheduler/branch count')
    need(c['sampler_cursor']==c['anchor_updates']+c['control_updates']==len(tree['sft_exposed']),'compact sampler/committed exposure count')
    need(c['backward_calls']>=c['anchor_updates']+c['control_updates']+c['rl_updates'],'compact backward count cannot cover commits')
    need((label=='B' or label.startswith('B-batch-')) or c['rl_updates']==0,'RL count in wrong branch');need(label=='C' or c['control_updates']==0,'SFT control count in wrong branch')
    need(tree['source_sha256']==expected_core_source_sha256 and is_sha(tree['base_identity_sha256']) and is_sha(tree['structure_sha256']),'compact exact source/base/model identity')
    need(type(tree['policy_version']) is str and tree['policy_version'].startswith(stage+':'),'compact policy identity')
    recipe={'anchor':'tiny-anchor-constant-2e4-v1' if synthetic and anchor_updates==1 else 'historical-anchor-2e4-w4-c256-min01-v1','rl':'rl-constant-1e6-v1','control':'control-constant-2e4-v1'}[stage]
    need(tree['schedule_recipe']==recipe,'compact source-owned schedule recipe differs')
    count=c['optimizer_steps'];base=1e-6 if stage=='rl' else 2e-4;lr=base*(anchor_multiplier(count) if recipe.startswith('historical-') else 1.)
    opt,scheduler=tree['optimizer'],tree['scheduler'];need(set(opt)=={'state','param_groups'} and len(opt['param_groups'])==1,'complete compact optimizer package')
    group=opt['param_groups'][0];adapters=tree['adapters'];need(adapters and group['params']==list(range(len(adapters))),'compact optimizer parameter coverage')
    need(type(scheduler.get('last_epoch')) is int and scheduler['last_epoch']==count and type(scheduler.get('_step_count')) is int and scheduler['_step_count']==count+1,'compact scheduler actual counters')
    need(same(scheduler.get('base_lrs'),[base]) and same(scheduler.get('_last_lr'),[lr]) and scheduler.get('lr_lambdas')==[None] and scheduler.get('_is_initial') is False and scheduler.get('_get_lr_called_within_step') is False,'compact actual rate/settled callable-free schedule')
    defaults={'lr':base,'betas':[.9,.999],'eps':1e-8,'weight_decay':0.,'amsgrad':False,'maximize':False,'foreach':False,'capturable':False,'differentiable':False,'fused':None}
    for k,v in defaults.items():need(same(tree['optimizer_defaults'].get(k),v) and same(group.get(k),lr if k=='lr' else v),'compact Adam defaults/rate differ: '+k)
    need(same(group.get('initial_lr'),base),'compact optimizer initial rate')
    for name,t in adapters.items():
        need(t.get('tensor') is True and t['dtype']=='torch.float32' and len(t['shape'])==2 and ('.lora_A.default.weight' in name or '.lora_B.default.weight' in name) and t['shape'][0 if '.lora_A.' in name else 1]==8,'compact actual FP32 rank8 adapter descriptor')
    need({n.split('.')[-4] for n in adapters}=={'q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'},'compact seven-projection inventory')
    validate_adapter_descriptors(adapters,synthetic)
    adapter_hash=digest({n:{'shape':t['shape'],'dtype':t['dtype'],'elements':math.prod(t['shape']),'sha256':t['sha256']} for n,t in sorted(adapters.items())})
    need(adapter_hash==summary['adapter_sha256'],'compact adapter fingerprint differs')
    adam=opt['state'];steps=summary['optimizer_step_values'];expected={str(i) for i in group['params']} if count else set()
    need(set(adam)==set(steps)==expected,'compact Adam state and actual scalar-step inventory')
    names=summary['optimizer_parameter_names']
    need(type(names) is list and len(names)==len(set(names)) and set(names)==set(adapters),'compact exact original optimizer parameter order')
    for key,row in adam.items():
        need(set(row)=={'step','exp_avg','exp_avg_sq'} and finite(steps[key]) and steps[key]==count,'compact actual Adam scalar step')
        need(row['step']=={'tensor':True,'dtype':'torch.float32','shape':[],'sha256':sha(struct.pack('<f',float(count)))},'compact step scalar descriptor differs')
        for name in ('exp_avg','exp_avg_sq'):need(row[name]['dtype']=='torch.float32' and row[name]['shape']==adapters[names[int(key)]]['shape'],'compact Adam moment shape/dtype')
        need(row['exp_avg']['shape']==row['exp_avg_sq']['shape'],'compact Adam moment pair differs')
    need(set(tree['rng'])=={'python','numpy','torch','cuda'} and tree['rng']['torch'].get('dtype')=='torch.uint8','complete compact RNG package')
    need(type(tree['training_modes']) is dict and tree['training_modes'] and all(type(v) is bool for v in tree['training_modes'].values()),'compact actual module mode package')
    need(same(tree['counter_policy'],{'id':'rl-fixed-disjoint-batches-v2','anchor_max':256,'rl_max':4,'control_max':8192,'batches_max':4,'batch_slots':64,'planned_attempts':256}),'compact bounded counter policy')
    return {'state_sha256':summary['state_sha256'],'adapter_sha256':summary['adapter_sha256'],'counts':c,'schedule_recipe':recipe,'policy_version':tree['policy_version'],
            'base_identity_sha256':tree['base_identity_sha256'],'structure_sha256':tree['structure_sha256'],'training_identity':tree['training_identity'],'sft_exposed':tree['sft_exposed'],
            'independent_checkpoint_tensor_verification':False,'verification_scope':'runtime-reload-bound-metadata','runtime_reported_tensor_hashes_verified_against_bytes':False}


def validate_checkpoint_metadata(root,label,*,anchor_updates,expected_core_source_sha256,synthetic):
    sub=checkpoint_root(root,label);manifest=sub.json('manifest.json');files=manifest.get('files',{})
    need(manifest.get('format')=='rl-owned-same-source-state-v1' and {'state.pt','adapter/adapter_model.safetensors','adapter/adapter_config.json','state-summary.json'}<=set(files),'complete checkpoint manifest including compact state summary')
    actual=sub.inventory();need(set(actual)-{'manifest.json'}<=set(files),'unknown materialized checkpoint artifact')
    for name,h in files.items():
        need(is_sha(h),'declared checkpoint file hash')
        if name in actual:need(actual[name]==h,'materialized checkpoint metadata bytes differ: '+name)
        else:need(name in OMITTABLE,'required compact checkpoint evidence missing: '+name)
    summary=sub.json('state-summary.json');replay=replay_state_summary(summary,label=label,anchor_updates=anchor_updates,expected_core_source_sha256=expected_core_source_sha256,synthetic=synthetic)
    need(manifest.get('state_sha256')==replay['state_sha256'] and manifest.get('source_sha256')==expected_core_source_sha256 and manifest.get('policy_version')==replay['policy_version'] and same(manifest.get('counts'),replay['counts']),'compact manifest/state metadata projection')
    need(manifest.get('physical_ledger_imported_as_state') is False,'compact state cannot restore physical costs')
    config=sub.json('adapter/adapter_config.json');need(config.get('r')==8 and config.get('lora_alpha')==16 and config.get('lora_dropout')==0. and config.get('bias')=='none' and config.get('peft_type')=='LORA' and config.get('use_dora') is False and config.get('use_rslora') is False,'compact PEFT recipe')
    proof=root.json(label+'-checkpoint-proof.json');need(proof.get('manifest_file_sha256')==sub.file_sha('manifest.json') and proof.get('adapter_sha256')==replay['adapter_sha256'] and same(proof.get('save'),manifest) and same(proof.get('updates'),replay['counts']),'complete source-bound compact save proof')
    reload=proof.get('reload',{})
    need(reload.get('state_sha256')==replay['state_sha256'] and all(reload.get(k) is True for k in ('reload_verified','safetensors_verified','same_source','physical_ledger_preserved','state_summary_verified')) and reload.get('state_summary_file_sha256')==files['state-summary.json'],'actual same-source compact reload/parity proof required')
    identity=proof.get('policy_identity',{})
    need(identity.get('source_sha256')==expected_core_source_sha256 and identity.get('adapter_sha256')==replay['adapter_sha256'] and identity.get('policy_version')==replay['policy_version'],'compact saved/reloaded policy identity differs')
    from .prediction_checks import reference
    from pathlib import PurePosixPath
    original=str(PurePosixPath(proof['checkpoint_path']).parent.parent)
    need(same(reference(root,proof.get('manifest_ref'),original),manifest),'mandatory checkpoint manifest copy/reference differs')
    need(same(reference(root,proof.get('state_summary_ref'),original),sub.json('state-summary.json')),'mandatory checkpoint summary copy/reference differs')
    replay['unmaterialized_assets']=[n for n in files if n not in actual]
    return replay
