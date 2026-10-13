"""Actual safe CPU state replay. No model construction, CUDA use, or candidate imports."""
from collections import OrderedDict
import math
from .safe_io import EvidenceError, Root, need, integer, finite, is_sha, same, digest, sha, inspect_tensor_zip

STATE_KEYS = {'adapters','optimizer','optimizer_defaults','schedule_recipe','scheduler','rng','counters',
              'training_identity','policy_version','stage','sft_exposed','training_modes','source_sha256',
              'base_identity_sha256','structure_sha256','counter_policy'}
COUNTER_LIMITS = {'anchor_updates':256,'rl_updates':4,'control_updates':8192,'optimizer_steps':8192,
                  'scheduler_steps':8192,'backward_calls':256+256+8192,'sampler_cursor':10000000}

def torch_module():
    try:
        import torch
    except ImportError as exc:
        raise EvidenceError('safe tensor replay requires installed PyTorch; metadata is not tensor proof') from exc
    # Earlier versions have known weights-only deserialization vulnerabilities.
    major, minor = (int(x) for x in torch.__version__.split('+')[0].split('.')[:2])
    need((major, minor) >= (2, 6), 'safe tensor replay requires PyTorch >=2.6')
    return torch

def tree_descriptor(value, *, maximum_elements=128_000_000):
    torch = torch_module()
    budget = [0, 0]
    def walk(item, depth=0):
        budget[0] += 1
        need(depth <= 64 and budget[0] <= 2000000, 'tensor tree nesting/node limit')
        if type(item) is torch.Tensor:
            need(item.device.type == 'cpu' and item.layout == torch.strided and not item.is_quantized, 'unsupported tensor layout/device')
            budget[1] += item.numel()
            need(budget[1] <= maximum_elements, 'tensor element limit')
            need(bool(torch.isfinite(item).all()), 'nonfinite state tensor')
            v = item.detach().contiguous()
            return {'tensor':True,'dtype':str(v.dtype),'shape':list(v.shape),
                    'sha256':sha(v.reshape(-1).view(torch.uint8).numpy().tobytes())}
        if type(item) in (dict, OrderedDict):
            need(all(type(k) in (str,int) for k in item), 'unsupported tensor mapping key')
            need(len({str(k) for k in item}) == len(item), 'ambiguous stringified tensor keys')
            return {str(k):walk(v,depth+1) for k,v in sorted(item.items(),key=lambda kv:str(kv[0]))}
        if type(item) in (list,tuple):
            return [walk(v,depth+1) for v in item]
        need(item is None or type(item) in (str,bool,int,float), 'unsupported tensor pickle primitive/object')
        if type(item) is float:
            need(finite(item), 'nonfinite tensor primitive')
        return item
    return walk(value)

def tree_sha(value):
    return digest(tree_descriptor(value))

def adapter_sha(adapters):
    descriptors=tree_descriptor(adapters)
    return digest({name:{'dtype':row['dtype'],'shape':row['shape'],'elements':math.prod(row['shape']),'sha256':row['sha256']} for name,row in descriptors.items()})

def safe_load_state(path):
    inspect_tensor_zip(path)
    torch = torch_module()
    from torch.nested._internal.nested_tensor import _rebuild_njt, NestedTensor
    need(all(x is _rebuild_njt or x is NestedTensor for x in torch.serialization.get_safe_globals()), 'ambient custom pickle globals forbidden for offline tensor replay')
    # Explicitly never fall back, register globals, or disable weights-only.
    try:
        value = torch.load(path, map_location='cpu', weights_only=True)
    except Exception as exc:
        raise EvidenceError('restricted tensor decode rejected archive: ' + type(exc).__name__) from exc
    tree_descriptor(value)
    need(type(value) is dict and set(value) == STATE_KEYS, 'closed actual checkpoint state inventory')
    return value

def anchor_multiplier(step):
    if step < 4:
        return (step+1)/4
    progress = min(1., max(0., (step-4)/252))
    return .1 + .9 * .5 * (1 + math.cos(math.pi * progress))

def validate_adapter_descriptors(adapters,synthetic):
    need(type(adapters) is dict and adapters,'complete adapter descriptor map')
    prefixes={name.rsplit('.lora_',1)[0] for name in adapters}
    need(set(adapters)=={prefix+'.lora_'+kind+'.default.weight' for prefix in prefixes for kind in ('A','B')},'both A/B matrices per projection required')
    for prefix in prefixes:
        a,b=(adapters[prefix+'.lora_'+kind+'.default.weight'] for kind in ('A','B'))
        need(a['dtype']==b['dtype']=='torch.float32' and len(a['shape'])==len(b['shape'])==2 and a['shape'][0]==b['shape'][1]==8,'exact FP32 rank8 matrix pair')
    if not synthetic:
        expected={}
        dimensions={'q_proj':(5120,5120),'k_proj':(5120,1024),'v_proj':(5120,1024),'o_proj':(5120,5120),'gate_proj':(5120,17408),'up_proj':(5120,17408),'down_proj':(17408,5120)}
        for layer in range(40):
            for projection,(input_dim,output_dim) in dimensions.items():
                stem=f'base_model.model.model.layers.{layer}.'+('self_attn.' if projection in ('q_proj','k_proj','v_proj','o_proj') else 'mlp.')+projection
                expected[stem+'.lora_A.default.weight']=[8,input_dim]
                expected[stem+'.lora_B.default.weight']=[output_dim,8]
        need(set(adapters)==set(expected) and all(adapters[n]['shape']==shape for n,shape in expected.items()),'full14B40-layer seven-projection actual adapter coverage differs')


def validate_state(state, *, label, anchor_updates, expected_source_sha256, synthetic):
    torch = torch_module()
    need(label in ('base','A','B','C',*(f'B-batch-{i}' for i in range(4))), 'known checkpoint role')
    c = state['counters']
    need(type(c) is dict and set(c) == set(COUNTER_LIMITS), 'closed state counters')
    need(all(integer(c[k],0,v) for k,v in COUNTER_LIMITS.items()), 'integer bounded counters')
    stage = {'base':'anchor','A':'anchor','B':'rl','C':'control'}['B' if label.startswith('B-batch-') else label]
    need(state['stage'] == stage, 'checkpoint stage differs')
    need(c['anchor_updates'] == (0 if label=='base' else anchor_updates), 'same-session anchor count differs')
    need(c['optimizer_steps'] == c['scheduler_steps'] == c[stage+'_updates'], 'stage optimizer/scheduler count differs')
    need(c['sampler_cursor'] == c['anchor_updates']+c['control_updates'] == len(state['sft_exposed']), 'committed sampler/exposure count differs')
    need(c['backward_calls'] >= c['anchor_updates'] + c['control_updates'] + c['rl_updates'], 'backward count cannot cover commits')
    need((label=='B' or label.startswith('B-batch-')) or c['rl_updates']==0, 'RL updates in wrong branch')
    need(label in ('C',) or c['control_updates']==0, 'control updates in wrong branch')
    need(state['source_sha256'] == expected_source_sha256, 'actual checkpoint core source differs')
    need(is_sha(state['base_identity_sha256']) and is_sha(state['structure_sha256']), 'actual base/structure identity required')
    need(type(state['policy_version']) is str and state['policy_version'].startswith(stage+':'), 'actual policy version/stage differs')
    recipes = {'anchor':'tiny-anchor-constant-2e4-v1' if synthetic and anchor_updates==1 else 'historical-anchor-2e4-w4-c256-min01-v1',
               'rl':'rl-constant-1e6-v1','control':'control-constant-2e4-v1'}
    need(state['schedule_recipe'] == recipes[stage], 'actual source-owned schedule recipe differs')
    base_lr = 1e-6 if stage=='rl' else 2e-4
    count = c['optimizer_steps']
    lr = base_lr * (anchor_multiplier(count) if state['schedule_recipe'].startswith('historical-') else 1.)
    opt, sched = state['optimizer'], state['scheduler']
    need(type(opt) is dict and set(opt)=={'state','param_groups'}, 'closed optimizer state inventory')
    groups = opt['param_groups']
    need(type(groups) is list and len(groups)==1, 'one fixed optimizer parameter group')
    params = groups[0]['params']
    need(type(params) is list and params == list(range(len(state['adapters']))), 'exact optimizer adapter parameter order')
    need(sched.get('last_epoch') == count and type(sched.get('last_epoch')) is int and type(sched.get('_step_count')) is int and sched.get('_step_count')==count+1,
         'actual scheduler counters differ')
    need(same(sched.get('base_lrs'),[base_lr]) and same(sched.get('_last_lr'),[lr]) and sched.get('lr_lambdas')==[None], 'actual scheduler rates/callable state differs')
    need(sched.get('_is_initial') is False and sched.get('_get_lr_called_within_step') is False, 'unsettled scheduler boundary')
    expected_defaults={'lr':base_lr,'betas':[.9,.999],'eps':1e-8,'weight_decay':0.,'amsgrad':False,
                       'maximize':False,'foreach':False,'capturable':False,'differentiable':False,'fused':None}
    for key, value in expected_defaults.items():
        need(same(state['optimizer_defaults'].get(key),value), 'optimizer defaults differ: '+key)
        need(same(groups[0].get(key),lr if key=='lr' else value), 'optimizer group differs: '+key)
    need(same(groups[0].get('initial_lr'),base_lr), 'optimizer base rate differs')
    adapters=state['adapters']
    need(type(adapters) is dict and adapters and all(type(v) is torch.Tensor and v.dtype==torch.float32 and v.ndim==2 for v in adapters.values()), 'actual FP32 adapter matrices required')
    projections={n.split('.')[-4] for n in adapters}
    need(projections=={'q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'}, 'seven projection adapter inventory')
    need(all('.lora_A.default.weight' in n or '.lora_B.default.weight' in n for n in adapters), 'unknown adapter parameter')
    validate_adapter_descriptors(tree_descriptor(adapters),synthetic)
    adam=opt['state']
    need(set(adam)==(set(params) if count else set()), 'actual Adam parameter state coverage')
    for parameter, value in zip(params, adapters.values()):
        if not count:
            break
        row=adam[parameter]
        need(set(row)=={'step','exp_avg','exp_avg_sq'}, 'closed actual Adam tensors')
        need(type(row['step']) is torch.Tensor and row['step'].numel()==1 and float(row['step'])==count, 'actual Adam step differs')
        for name in ('exp_avg','exp_avg_sq'):
            need(type(row[name]) is torch.Tensor and row[name].shape==value.shape and row[name].dtype==value.dtype, 'actual Adam moment shape/dtype')
    need(type(state['rng']) is dict and set(state['rng'])=={'python','numpy','torch','cuda'}, 'actual complete RNG package')
    need(type(state['rng']['torch']) is torch.Tensor and state['rng']['torch'].dtype==torch.uint8, 'actual Torch RNG bytes')
    need(type(state['training_modes']) is dict and state['training_modes'] and all(type(v) is bool for v in state['training_modes'].values()), 'actual module mode inventory')
    need(same(state['counter_policy'],{'id':'rl-fixed-disjoint-batches-v2','anchor_max':256,'rl_max':4,'control_max':8192,'batches_max':4,'batch_slots':64,'planned_attempts':256}), 'counter policy differs')
    return {'state_sha256':tree_sha(state),'adapter_sha256':adapter_sha(adapters),'counts':c,
            'schedule_recipe':state['schedule_recipe'],'policy_version':state['policy_version'],
            'base_identity_sha256':state['base_identity_sha256'],'structure_sha256':state['structure_sha256'],
            'training_identity':state['training_identity'],'sft_exposed':state['sft_exposed']}

def checkpoint_root(root,label):
    from pathlib import PurePosixPath
    allowed={'base','A','B','C',*(f'B-batch-{i}' for i in range(4))}
    need(label in allowed,'canonical checkpoint label required')
    proof=root.json(label+'-checkpoint-proof.json')
    path=proof.get('checkpoint_path');need(type(path) is str,'actual checkpoint path required')
    parsed=PurePosixPath(path);stored=parsed.name
    need(parsed.is_absolute() and parsed.parent.name=='checkpoints' and stored in allowed,
         'canonical stored checkpoint path required')
    need(stored==label or label=='B' and stored.startswith('B-batch-'), 'unexpected checkpoint alias')
    return Root(root.member('checkpoints/'+stored+'/manifest.json').parent)


def validate_checkpoint(root, label, *, anchor_updates, expected_core_source_sha256, synthetic):
    sub=checkpoint_root(root,label)
    manifest=sub.json('manifest.json')
    need(manifest.get('format')=='rl-owned-same-source-state-v1', 'checkpoint manifest format')
    need(set(manifest.get('files',{}))==set(sub.inventory())-{'manifest.json'}, 'exact checkpoint file inventory')
    for name, h in manifest['files'].items():
        need(is_sha(h) and sub.file_sha(name)==h, 'checkpoint file bytes differ: '+name)
    need({'state.pt','adapter/adapter_model.safetensors','adapter/adapter_config.json'} <= set(manifest['files']), 'required actual checkpoint assets')
    config=sub.json('adapter/adapter_config.json')
    need(config.get('r')==8 and config.get('lora_alpha')==16 and config.get('lora_dropout')==0. and config.get('bias')=='none' and config.get('peft_type')=='LORA' and config.get('use_dora') is False and config.get('use_rslora') is False, 'source-fixed rank8 alpha16 zero-dropout PEFT recipe')
    state=safe_load_state(sub.member('state.pt'))
    need(all(v.shape[0 if '.lora_A.' in n else 1]==8 for n,v in state['adapters'].items()), 'actual rank8 adapter tensors')
    replay=validate_state(state,label=label,anchor_updates=anchor_updates,expected_source_sha256=expected_core_source_sha256,synthetic=synthetic)
    need(manifest['state_sha256']==replay['state_sha256'] and same(manifest['counts'],replay['counts']), 'manifest/actual tensor state differs')
    need(manifest['source_sha256']==expected_core_source_sha256 and manifest['policy_version']==state['policy_version'], 'manifest source/policy differs')
    need(manifest.get('physical_ledger_imported_as_state') is False, 'physical cost cannot be restored/refunded')
    try:
        from safetensors.torch import load_file
        saved=load_file(str(sub.member('adapter/adapter_model.safetensors')),device='cpu')
    except Exception as exc:
        raise EvidenceError('safe adapter tensor decode failed') from exc
    actual={n.replace('.default.weight','.weight'):v for n,v in state['adapters'].items()}
    need(tree_sha(saved)==tree_sha(actual), 'actual safetensors/state adapter mismatch')
    proof=root.json(label+'-checkpoint-proof.json')
    need(proof['manifest_file_sha256']==sub.file_sha('manifest.json') and proof['adapter_sha256']==replay['adapter_sha256'], 'checkpoint proof bytes/adapter differ')
    need(same(proof['save'],manifest) and same(proof['updates'],replay['counts']), 'save proof/counters differ')
    reload=proof['reload']
    need(reload.get('state_sha256')==replay['state_sha256'] and all(reload.get(k) is True for k in ('reload_verified','safetensors_verified','same_source','physical_ledger_preserved')), 'reload state proof differs')
    need(proof['policy_identity']['adapter_sha256']==replay['adapter_sha256'] and proof['policy_identity']['policy_version']==state['policy_version'] and proof['policy_identity']['source_sha256']==expected_core_source_sha256, 'checkpoint policy identity differs')
    if 'state-summary.json' in manifest['files']:
        summary=sub.json('state-summary.json')
        need(same(summary.get('state_tree'),tree_descriptor(state)) and summary.get('state_sha256')==replay['state_sha256'] and summary.get('adapter_sha256')==replay['adapter_sha256'],'compact metadata differs from independent actual tensor bytes')
        need(summary.get('optimizer_parameter_names')==list(state['adapters']),'compact optimizer order differs from actual saved state')
        steps={str(k):float(v['step']) for k,v in state['optimizer']['state'].items()}
        need(same(summary.get('optimizer_step_values'),steps),'compact Adam scalars differ from independently decoded tensors')
        need(reload.get('state_summary_verified') is True and reload.get('state_summary_file_sha256')==manifest['files']['state-summary.json'],'compact actual restored metadata parity missing')
    from .prediction_checks import reference
    from pathlib import PurePosixPath
    original=str(PurePosixPath(proof['checkpoint_path']).parent.parent)
    need(same(reference(root,proof.get('manifest_ref'),original),manifest),'mandatory checkpoint manifest copy/reference differs')
    need(same(reference(root,proof.get('state_summary_ref'),original),sub.json('state-summary.json')),'mandatory checkpoint summary copy/reference differs')
    replay['independent_checkpoint_tensor_verification']=True
    replay['verification_scope']='full-materialized-safe-tensor-replay'
    return replay
