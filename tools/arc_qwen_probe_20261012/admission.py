"""Exact source-pinned composite, no caller-supplied deployment allowlist."""
from __future__ import annotations
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import time
from .protocol import require,checked_json,file_sha

CONTRACT_SHA256='8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0'
DEPLOYMENT_ID='qwen3-14b-kaggle-v1-hf40c069-bf16-r8-c2048-first-probe-20261012'

def select_deployment(config):
    require(config.get('enabled') is True and config.get('reviewed_deployment_id')==DEPLOYMENT_ID,'source-pinned probe deployment required')
    c=checked_json(config['contract_path'],CONTRACT_SHA256)
    require(c['contract_id']==DEPLOYMENT_ID and c['probe_bounds']['public_solving_admitted'] is False,'composite identity differs')
    for k,v in (('context_limit',2048),('prompt_cap',1792),('output_cap',256),('tensor_parallel_size',1)):
        require(type(config.get(k,v)) is int and config.get(k,v)==v,'fixed composite '+k+' differs')
    require(config.get('precision','bf16-base-fp32-lora')=='bf16-base-fp32-lora','only exact BF16 probe admitted')
    return {'model_key':c['model_key'],'profile_id':c['profile_id'],'revision':c['hf_revision'],
            'public_solving_admitted':False,'admission_phase':'first-bounded-probe','composite_contract_sha256':CONTRACT_SHA256}

def _deadline(deadline):require(time.monotonic()<deadline,'immutable composite admission deadline expired')

def _root(path):
    p=Path(path).absolute();require(p.is_dir() and not any(q.is_symlink() for q in (p,*p.parents)),'regular separate material root required')
    return p

def _hash_before(path,deadline):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            _deadline(deadline);b=f.read(8*1024**2)
            if not b:break
            h.update(b)
    return h.hexdigest()

def _closed_files(root,entries,deadline,*,readonly=False):
    root=_root(root)
    require({p.name for p in root.iterdir()}==set(entries),'closed material inventory differs')
    if readonly:require(bool(os.statvfs(root).f_flag & os.ST_RDONLY),'weights/wheels must remain on readonly provider mount')
    for n,e in entries.items():
        require(Path(n).name==n,'unsafe contract member')
        p=root/n;require(p.is_file() and not p.is_symlink(),'regular material member required')
        require(p.stat().st_size==e.get('size_bytes',e.get('bytes')),'material byte size differs: '+n)
        if 'sha256' in e:require(_hash_before(p,deadline)==e['sha256'],'material SHA differs: '+n)
    return root

def _descriptor(root,c,key):
    e=c[key];p=root/e['path'];require(p.stat().st_size==e['bytes'],'descriptor length differs')
    return checked_json(p,e['sha256'],cap=2*1024**2)

def _pairs(items):
    r={}
    for k,v in items:require(k not in r,'duplicate JSON key');r[k]=v
    return r

def tensor_header(path):
    """Closed BF16 safetensors intervals and duplicate-key rejection."""
    size=path.stat().st_size
    with path.open('rb') as f:
        prefix=f.read(8);require(len(prefix)==8,'short safetensors prefix')
        n=struct.unpack('<Q',prefix)[0];require(1<=n<=min(64*1024**2,size-8),'safetensors header bound')
        raw=f.read(n);header=json.loads(raw,object_pairs_hook=_pairs)
    require(type(header) is dict,'safetensors object required')
    entries={};spans=[]
    for name,e in header.items():
        if name=='__metadata__':continue
        require(type(e) is dict and set(e)=={'dtype','shape','data_offsets'},'tensor metadata differs')
        shape=e['shape'];offsets=e['data_offsets'];require(e['dtype']=='BF16','all native weights must be BF16')
        require(type(shape) is list and shape and all(type(x) is int and x>0 for x in shape),'native tensor shape invalid')
        require(type(offsets) is list and len(offsets)==2 and all(type(x) is int for x in offsets),'native tensor offsets invalid')
        a,b=offsets;require(0<=a<b<=size-8-n and b-a==2*math.prod(shape),'native tensor payload span invalid')
        entries[name]={'shape':shape,'dtype':'BF16','elements':math.prod(shape)};spans.append((a,b))
    end=0
    for a,b in sorted(spans):require(a==end,'overlap/gap in native tensor payload');end=b
    require(entries and end==size-8-n,'incomplete native tensor payload')
    return entries

def validate_environment(config,c,deadline):
    root=Path(config['contract_path']).absolute().parent
    e=_descriptor(root,c,'environment')
    require(Path(config['environment_lock_path']).absolute()==root/c['environment']['path'],'exact descriptor path required')
    require(platform.python_version()==e['python'] and platform.system()=='Linux' and platform.machine()=='x86_64','exact runtime platform required')
    require(sys.prefix!=sys.base_prefix,'isolated installed environment required')
    require(file_sha(sys.executable)==e['interpreter']['executable_sha256'],'exact interpreter executable differs')
    require(all(os.environ.get(k)==v for k,v in e['offline_flags'].items()),'offline flags missing')
    import socket
    require(getattr(socket,'_irisx_offline_guard',False),'production offline socket guard missing')
    from tools import arc_next_offline_environment as installer
    prefix=Path(sys.prefix)
    require((prefix/'offline-run.py').read_text()==installer._LAUNCHER,'production offline launcher bytes differ')
    require((prefix/'lib/python3.12/site-packages/sitecustomize.py').read_text()==installer.NETWORK_GUARD,'production network guard bytes differ')
    wroot=_root(config['wheel_root_path']);require(bool(os.statvfs(wroot).f_flag & os.ST_RDONLY),'readonly original wheel mount required')
    require(_hash_before(wroot/'wheel-lock.json',deadline)==e['prepared_wheel_lock']['sha256'],'original prepared wheel-lock changed')
    require(_hash_before(wroot/'requirements.lock',deadline)==e['requirements_lock']['sha256'],'original requirements changed')
    _closed_files(wroot/'wheels',e['wheel_files'],deadline,readonly=True)
    versions={n:importlib.metadata.version(n) for n in e['versions']}
    require(versions==e['versions'],'exact52 installed versions differ')
    origins={}
    for n in versions:
        distribution=importlib.metadata.distribution(n)
        p=Path(distribution.locate_file('')).resolve();require(p.is_relative_to(prefix.resolve()),'distribution outside isolated runtime: '+n)
        origins[n]=str(p)
    require(all(importlib.util.find_spec(n) is None for n in e['optional_backend_modules_absent']),'optional backend present')
    for name in ('torch','transformers','tokenizers','peft','accelerate','safetensors','huggingface_hub'):
        spec=importlib.util.find_spec(name)
        require(spec is not None and spec.origin and Path(spec.origin).resolve().is_relative_to(prefix.resolve()),'native module origin outside isolated runtime: '+name)
    return {'environment_lock_sha256':c['environment']['sha256'],'actual_versions':versions,'python':platform.python_version(),
            'distribution_origins':origins,'complete_transitive_lock_verified':True,'wheel_root_separate':True}

def load_composite(config):
    select_deployment(config)
    deadline=config.get('_owned_probe_deadline')
    require(type(deadline) in (int,float) and math.isfinite(deadline) and 0<deadline-time.monotonic()<=1800 and
            config.get('_owned_probe_supervisor_pid')==os.getppid() and config.get('_owned_probe_scope')=='qwen14b-capability-only',
            'bounded owned1800s loader required')
    c=checked_json(config['contract_path'],CONTRACT_SHA256);cr=Path(config['contract_path']).absolute().parent
    environment=validate_environment(config,c,deadline)
    weights=_root(config['model_path']);overlay=_root(config['tokenizer_path'])
    require(weights!=overlay and not weights.is_relative_to(overlay) and not overlay.is_relative_to(weights),'two disjoint weight/tokenizer roots required')
    require(weights.is_relative_to('/kaggle/input'),'weights must stay on original provider mount')
    _closed_files(weights,c['provider_files'],deadline,readonly=True)
    _closed_files(overlay,c['overlay_files'],deadline)
    expected=_descriptor(cr,c,'expected_tensor_inventory')['tensors']
    index=checked_json(weights/'model.safetensors.index.json',c['provider_files']['model.safetensors.index.json']['sha256'])
    require(index['weight_map']=={n:e['shard'] for n,e in expected.items()} and index['metadata']['total_size']==c['weight_payload_bytes'],'exact443tensor index differs')
    inventory={}
    for name in sorted({e['shard'] for e in expected.values()}):
        _deadline(deadline);part=tensor_header(weights/name)
        require(not set(part)&set(inventory),'duplicate native tensor across shards')
        require(part=={n:{k:v for k,v in e.items() if k!='shard'} for n,e in expected.items() if e['shard']==name},'native tensor header inventory differs')
        inventory.update(part)
    cfg=checked_json(overlay/'config.json',c['overlay_files']['config.json']['sha256'])
    gen=checked_json(overlay/'generation_config.json',c['overlay_files']['generation_config.json']['sha256'])
    require(not cfg.get('auto_map'),'remote configuration denied')
    import torch
    from transformers import AutoTokenizer,Qwen3Config,GenerationConfig,Qwen3ForCausalLM
    h=_descriptor(cr,c,'hardware')
    require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported(),'exact singleBF16 GPU required')
    prop=torch.cuda.get_device_properties(0)
    actual={'name':prop.name,'total_memory_bytes':prop.total_memory,'capability':list(torch.cuda.get_device_capability(0))}
    require(actual==h['hardware'] and torch.version.cuda==h['torch_cuda'],'exact hardware/CUDA differs')
    driver=subprocess.run(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],capture_output=True,text=True,
                          check=True,timeout=min(10,max(.001,deadline-time.monotonic())))
    require(driver.stdout.strip()==h['driver_version'],'exact GPU driver differs')
    from tools.arc_learning_agent_20261011.qwen14b_contract import memory_estimate,canonical,resolve_native_eos_policy
    estimate=memory_estimate(cfg,inventory,sequence_length=2048,adapter_rank=8,batch_size=1)
    require(estimate['estimated_required_bytes']==h['memory_estimate']['estimated_required_bytes'],'source-derived analytical estimate differs')
    free,total=torch.cuda.mem_get_info(0)
    require(total==prop.total_memory and free>=estimate['estimated_required_bytes']+h['free_memory_reserve_bytes'],'analytic estimate plus reserve unavailable')
    with torch.device('meta'):meta=Qwen3ForCausalLM(Qwen3Config.from_dict(cfg))
    require({n:list(t.shape) for n,t in meta.state_dict().items()}=={n:e['shape'] for n,e in inventory.items()},'rebuilt native meta inventory differs')
    del meta
    tokenizer=AutoTokenizer.from_pretrained(str(overlay),local_files_only=True,trust_remote_code=False,use_fast=True)
    require(hashlib.sha256(tokenizer.get_chat_template().encode()).hexdigest()==c['template_sha256'] and
            hashlib.sha256(canonical(tokenizer.get_vocab())).hexdigest()==c['vocabulary_sha256'],'native overlay tokenizer identity differs')
    policy=resolve_native_eos_policy(tokenizer,cfg,gen,expected_ids=c['native_eos_ids'])
    _deadline(deadline);model=None
    try:
        torch.cuda.reset_peak_memory_stats(0)
        model,info=Qwen3ForCausalLM.from_pretrained(str(weights),config=Qwen3Config.from_dict(cfg),generation_config=GenerationConfig.from_dict(gen),
            local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,use_safetensors=True,attn_implementation='sdpa',
            device_map={'':'cuda:0'},low_cpu_mem_usage=True,output_loading_info=True)
        _deadline(deadline)
        require(type(model).__name__=='Qwen3ForCausalLM' and all(not info.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')),'native loading info incomplete')
        state=model.state_dict()
        require(set(state)==set(inventory) and all(list(state[n].shape)==e['shape'] and state[n].dtype==torch.bfloat16 and state[n].device.type=='cuda' and state[n].device.index==0 for n,e in inventory.items()),'loaded native tensor inventory/placement differs')
        require(model.get_input_embeddings().weight.shape[0]==model.get_output_embeddings().weight.shape[0]==151936,'full native151936 heads required')
        model.requires_grad_(False);model.eval()
        hardware={**actual,'torch_cuda':torch.version.cuda,'driver_version':driver.stdout.strip(),
            'visible_device_count':1,'bf16_supported':True,'free_bytes_before_load':free,'estimate':estimate,'cache_atol':h['cache_atol'],'cache_rtol':h['cache_rtol'],
            'g4_fit_measured':False,'four_l4_tp_admitted':False,'fp8_admitted':False,'load_peak_allocated_bytes':torch.cuda.max_memory_allocated(0)}
        identity={'format':'irisx/qwen14b-native-interface-v1','model_key':c['model_key'],'model_id':c['model_id'],'revision':c['hf_revision'],
            'profile_id':c['profile_id'],'execution_mode':'native-qwen3-pretrained-composite-probe','pretrained_weights_loaded':True,
            'random_test_weights':False,'production_admitted':False,'probe_pretrained_admitted':True,'public_solving_admitted':False,
            'model_manifest_sha256':CONTRACT_SHA256,'reviewed_deployment_id':DEPLOYMENT_ID,'full_vocabulary_rows':151936,
            'base_precision':'bfloat16','environment':environment,'hardware_profile':actual,'native_eos_policy':policy,
            'admission_phase':'first-bounded-probe','all_eight_weight_sha256_verified':True,'provider_snapshot_identical_to_hf':False,
            'separate_weights_and_hf_overlay':True,'material_contract_sha256':CONTRACT_SHA256,
            'verified_tensor_count':len(inventory),'verified_tensor_elements':sum(e['elements'] for e in inventory.values()),
            'provider_weight_index_sha256':c['provider_files']['model.safetensors.index.json']['sha256'],
            'verified_weight_shards':{n:{'bytes':e['size_bytes'],'sha256':e['sha256']} for n,e in c['provider_files'].items() if e['role']=='base-weight'},
            'verified_overlay_files':{n:{'bytes':e['size_bytes'],'sha256':e['sha256']} for n,e in c['overlay_files'].items()},
            'overlay_template_sha256':c['template_sha256'],'overlay_vocabulary_sha256':c['vocabulary_sha256']}
        return model,tokenizer,identity,hardware
    except BaseException:
        if model is not None:del model
        import gc
        gc.collect();torch.cuda.empty_cache()
        raise
