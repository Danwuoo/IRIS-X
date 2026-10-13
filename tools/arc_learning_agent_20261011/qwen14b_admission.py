"""Conditional exact-material/environment/measured-hardware admission.

No reviewed deployment is shipped. Adding one is a separately reviewed source
change, never a caller-supplied enabled=True or self-signed calibration receipt.
This code implements the future loading path without activating/downloads.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import importlib.util
import platform
import json
import math
import os
import time
import weakref
from pathlib import Path
from types import MappingProxyType
from .qwen14b_profiles import MODEL_KEY, MODEL_ID, REVISION, PROFILE_ID, VOCAB_SIZE, EOS_IDS, SMALL_FILES, HF_LICENSE_SHA256, require

REVIEWED_DEPLOYMENTS = MappingProxyType({})
_VERIFIED_LOADED_MODELS = weakref.WeakKeyDictionary()


def consume_load_evidence(model, tokenizer, config):
    evidence = _VERIFIED_LOADED_MODELS.pop(model, None)
    require(evidence is not None and evidence['tokenizer'] is tokenizer and
            evidence['reviewed_deployment_id'] == config.get('reviewed_deployment_id'),
            'pretrained model was not returned by this exact verified conditional loader')
    return evidence['identity'], evidence['hardware']
ENVIRONMENT = MappingProxyType({'torch':'2.8.0+cu128','transformers':'5.8.1','tokenizers':'0.22.2',
    'peft':'0.21.0','accelerate':'1.10.1','huggingface-hub':'1.32.0','safetensors':'0.8.0'})


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()


def checked_json(path, expected, cap=4*1024**2):
    path=Path(path)
    require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and 0<path.stat().st_size<=cap,
            'bounded regular reviewed JSON required')
    require(file_sha(path)==expected,'reviewed JSON digest mismatch')
    return json.loads(path.read_bytes())


def select_reviewed_deployment(config):
    require(config.get('enabled') is True,'Qwen14B pretrained loading is default-disabled')
    require(config.get('model_key')==MODEL_KEY and config.get('profile_id')==PROFILE_ID,'exact Qwen14B probe profile required')
    require(config.get('precision','bf16-base-fp32-lora')=='bf16-base-fp32-lora','FP8/quantized fallback is not admitted')
    require(type(config.get('tensor_parallel_size',1)) is int and config.get('tensor_parallel_size',1)==1,
            'four-L4/tensor-parallel execution is not admitted')
    for name, default, upper in (('context_limit',2048,2048),('prompt_cap',1792,1792),('output_cap',256,256)):
        require(type(config.get(name,default)) is int and 0<config.get(name,default)<=upper,'Qwen14B probe '+name+' exceeds admission')
    require(config.get('prompt_cap',1792)<config.get('context_limit',2048) and config.get('output_cap',256)<config.get('context_limit',2048),'probe context reservation differs')
    key=config.get('reviewed_deployment_id')
    from tools.arc_qwen_probe_20261012.admission import DEPLOYMENT_ID,select_deployment
    if key==DEPLOYMENT_ID:
        return select_deployment(config)
    require(type(key) is str and key in REVIEWED_DEPLOYMENTS,
            'Qwen14B production blocked: no exact-byte independently reviewed measured deployment is shipped')
    reviewed=dict(REVIEWED_DEPLOYMENTS[key])
    require(reviewed.get('profile_id')==PROFILE_ID and reviewed.get('model_key')==MODEL_KEY and
            reviewed.get('revision')==REVISION,'reviewed deployment identity differs')
    require(reviewed.get('public_solving_admitted') is False,'this short-context release is probe-only')
    require(reviewed.get('admission_phase') in ('first-bounded-probe','measured-repeat-probe'),'explicit first-probe or measured-repeat admission required')
    return reviewed


def validate_environment(config,reviewed):
    lock=checked_json(config['environment_lock_path'],reviewed['environment_lock_sha256'])
    versions=lock.get('versions',{})
    require(lock.get('format')=='irisx/qwen14b-environment-v1' and
            type(versions) is dict and all(versions.get(k)==v for k,v in ENVIRONMENT.items()) and
            lock.get('complete_transitive_lock') is True,'exact complete reviewed Qwen14B environment lock required')
    root=Path(config['environment_lock_path']).parent
    wheels=checked_json(root/'wheel-lock.json',lock.get('wheel_lock_sha256'))
    require(wheels.get('format')=='irisx/arc-next-offline-wheel-lock-v1' and
            wheels.get('all_transitive_wheels_materialized') is True and wheels.get('versions')==versions,
            'complete transitive offline wheel closure required')
    require(file_sha(root/'requirements.lock')==wheels.get('requirements_sha256'),'requirements lock bytes differ')
    entries=wheels.get('files')
    require(type(entries) is dict and entries and {e['name']:e['version'] for e in entries.values()}==versions,
            'wheel inventory does not cover installed dependency closure')
    from tools.arc_next_models import validate_wheel_platform
    for name,entry in entries.items():
        require(Path(name).name==name and name.endswith('.whl'),'bounded wheel member required')
        validate_wheel_platform(name)
        path=root/'wheels'/name
        require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and
                path.stat().st_size==entry['bytes'] and file_sha(path)==entry['sha256'],'staged wheel bytes differ')
        require(reviewed['wheel_sha256'].get(name)==entry['sha256'],'wheel absent from independently reviewed closure')
    require(set(reviewed['wheel_sha256'])==set(entries),'reviewed wheel inventory differs')
    require(platform.system()=='Linux' and platform.machine()=='x86_64' and
            lock.get('python')==wheels.get('python')==platform.python_version(),'exact reviewed Python platform required')
    actual={name:importlib.metadata.version(name) for name in versions}
    require(actual==versions,'actual environment versions differ')
    optional=('torchao','bitsandbytes','flash_attn','fla','causal_conv1d','vllm','unsloth')
    require(all(importlib.util.find_spec(name) is None for name in optional),'unreviewed optional backend or precision extension installed')
    require(all(os.environ.get(name)=='1' for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_DATASETS_OFFLINE')),
            'all offline flags required before native imports')
    return {'environment_lock_sha256':reviewed['environment_lock_sha256'],'actual_versions':actual,
            'wheel_lock_sha256':lock['wheel_lock_sha256'],'complete_transitive_lock_verified':True}


def validate_hardware(config,reviewed,torch,*,estimate=None):
    """Compare actual device to immutable reviewed measurement, not an estimate."""
    if reviewed.get('admission_phase') == 'first-bounded-probe':
        require(type(estimate) is dict and estimate.get('measured') is False and
                type(estimate.get('estimated_required_bytes')) is int and estimate['estimated_required_bytes']>0,
                'first probe requires conservative source-derived analytic memory bound')
        require(torch.cuda.is_available() and torch.cuda.device_count()==1,'only exact first-probe single CUDA device admitted')
        prop=torch.cuda.get_device_properties(0)
        hardware={'name':prop.name,'total_memory_bytes':prop.total_memory,'capability':list(torch.cuda.get_device_capability(0))}
        require(hardware==reviewed['hardware'] and torch.cuda.is_bf16_supported(),'first-probe hardware/BF16 differs')
        free,total=torch.cuda.mem_get_info(0);reserve=reviewed['free_memory_reserve_bytes']
        require(type(reserve) is int and reserve>=4*1024**3 and total==prop.total_memory and
                free>=estimate['estimated_required_bytes']+reserve,'first-probe analytic requirement plus reserve unavailable')
        return {**hardware,'estimate':estimate,'calibration_scope':'unmeasured-first-bounded-capability-probe',
                'g4_fit_measured':False,'memory_fit_guaranteed':False,'analytical_estimate_only':True,'measured_peak_allocated_bytes':None,
                'free_bytes_before_load':free,'reserve_bytes':reserve,'four_l4_tp_admitted':False,'fp8_admitted':False}
    require(reviewed.get('admission_phase')=='measured-repeat-probe','unknown hardware admission phase')
    calibration=checked_json(config['calibration_path'],reviewed['calibration_sha256'])
    require(calibration.get('format')=='irisx/qwen14b-measured-admission-v1' and
            calibration.get('model_manifest_sha256')==reviewed['model_manifest_sha256'] and
            calibration.get('environment_lock_sha256')==reviewed['environment_lock_sha256'] and
            calibration.get('profile_id')==PROFILE_ID and calibration.get('context_tokens')==2048 and
            calibration.get('rank')==8 and calibration.get('batch_size')==1 and
            calibration.get('precision')=='bf16-base-fp32-lora' and calibration.get('tensor_parallel_size')==1,
            'exact measured capability probe binding required')
    require(all(calibration.get(k) is True for k in ('finite_backward','optimizer_update','exact_reset','cached_full_parity',
            'owned_process_closed','independently_reviewed')),'incomplete strict native measured probe')
    peak=calibration.get('peak_allocated_bytes');throughput=calibration.get('tokens_per_second')
    require(type(peak) is int and peak>0 and type(throughput) in (int,float) and math.isfinite(throughput) and throughput>0,
            'actual positive finite measured peak/throughput required')
    require(torch.cuda.is_available() and torch.cuda.device_count()==1,'only exact measured single-device CUDA profile admitted')
    prop=torch.cuda.get_device_properties(0)
    hardware={'name':prop.name,'total_memory_bytes':prop.total_memory,'capability':list(torch.cuda.get_device_capability(0))}
    require(hardware==reviewed['hardware'] and calibration.get('hardware')==hardware,'actual hardware differs from exact reviewed profile')
    require(torch.cuda.is_bf16_supported(),'native BF16 support required')
    free,total=torch.cuda.mem_get_info(0)
    reserve=reviewed['free_memory_reserve_bytes']
    require(type(reserve) is int and reserve>=4*1024**3 and free>=peak+reserve and total==prop.total_memory,
            'measured peak plus explicit free-memory reserve unavailable')
    return {**hardware,'calibration_sha256':reviewed['calibration_sha256'],'measured_peak_allocated_bytes':peak,
            'free_bytes_before_load':free,'reserve_bytes':reserve,'g4_fit_measured':True,'four_l4_tp_admitted':False,'fp8_admitted':False}


def load_reviewed_pretrained(config):
    """Real dormant loader: all gates precede native weight-loading call."""
    reviewed=select_reviewed_deployment(config)
    if reviewed.get('composite_contract_sha256'):
        from tools.arc_qwen_probe_20261012.admission import load_composite
        model,tokenizer,identity,hardware=load_composite(config)
        _VERIFIED_LOADED_MODELS[model]={'tokenizer':tokenizer,'identity':identity,'hardware':hardware,
                                      'reviewed_deployment_id':config['reviewed_deployment_id']}
        return model,tokenizer,identity,hardware
    hard=config.get('_owned_probe_deadline')
    require(type(hard) in (int,float) and math.isfinite(hard) and 0<hard-time.monotonic()<=1800 and
            config.get('_owned_probe_supervisor_pid')==os.getppid() and
            config.get('_owned_probe_scope')=='qwen14b-capability-only',
            'pretrained load requires bounded owned-process capability launcher')
    environment=validate_environment(config,reviewed)
    from .qwen14b_contract import ReviewedAdmission, validate_local_material, resolve_native_eos_policy
    admission=ReviewedAdmission(model_key=MODEL_KEY,revision=REVISION,
        manifest_sha256=reviewed['model_manifest_sha256'],environment_versions=dict(ENVIRONMENT),
        context_limit=2048,max_new_tokens=256,tensor_parallel_size=1)
    root=Path(config['model_path'])
    require(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)), 'regular exact model material directory required')
    material,cfg,inventory=validate_local_material(root,config['model_manifest_path'],admission)
    require(all(material['files'].get(name,{}).get('sha256')==sha for name,sha in SMALL_FILES.items()),
            'this HF-revision profile requires exact HF small assets; provider/composite identity needs separate reviewed profile')
    require(material['files'].get('LICENSE',{}).get('sha256')==HF_LICENSE_SHA256,
            'exact separately anchored HF license material required')
    require(cfg.get('num_attention_heads')==40 and cfg.get('num_key_value_heads')==8 and cfg.get('head_dim')==128 and
            cfg.get('intermediate_size')==17408 and cfg.get('attention_bias') is False and
            cfg.get('tie_word_embeddings') is False,'exact conventional40-layer Qwen3 GQA dimensions required')
    require(not material.get('unused_source_keys') and len({v for v in json.loads((root/'model.safetensors.index.json').read_bytes())['weight_map'].values()})==8,
            'all eight Qwen14B shards and every source tensor required')
    require(all(v['dtype']=='BF16' for v in inventory.values()),'only exactly reviewed native BF16 Qwen14B source tensors admitted')
    import torch
    from .qwen14b_contract import memory_estimate
    estimate=memory_estimate(cfg,inventory,sequence_length=2048,adapter_rank=8,batch_size=1)
    hardware=validate_hardware(config,reviewed,torch,estimate=estimate)
    require(time.monotonic()<hard,'probe deadline expired before weight loading')
    from transformers import AutoTokenizer,Qwen3ForCausalLM
    tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True,trust_remote_code=False,use_fast=True)
    require(hashlib.sha256(tokenizer.get_chat_template().encode()).hexdigest()==material['template_sha256'],
            'exact reviewed native chat template differs')
    from .qwen14b_contract import canonical
    require(hashlib.sha256(canonical(tokenizer.get_vocab())).hexdigest()==material['vocabulary_sha256'],
            'exact reviewed vocabulary differs')
    policy=resolve_native_eos_policy(tokenizer,cfg,json.loads((root/'generation_config.json').read_bytes()),expected_ids=list(EOS_IDS))
    require(material['native_eos_ids']==list(EOS_IDS) and material['tokenizer_eos_id']==151645,
            'reviewed Qwen14B EOS policy differs')
    torch.cuda.reset_peak_memory_stats(0)
    model,info=Qwen3ForCausalLM.from_pretrained(str(root),local_files_only=True,trust_remote_code=False,
        dtype=torch.bfloat16,use_safetensors=True,attn_implementation='sdpa',device_map={'':'cuda:0'},
        low_cpu_mem_usage=True,output_loading_info=True)
    try:
        require(time.monotonic()<hard,'probe deadline expired during weight loading')
        require(type(model).__name__=='Qwen3ForCausalLM' and all(not info.get(k) for k in
                ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')),'exact native weight loading coverage failed')
        state=model.state_dict()
        require(set(state)==set(inventory) and all(list(state[n].shape)==item['shape'] and state[n].dtype==torch.bfloat16
                for n,item in inventory.items()),'exact loaded tensor inventory/shape/dtype differs')
        require(all(p.device.type=='cuda' and p.device.index==0 for p in model.parameters()),'unreviewed device placement')
        require(model.get_input_embeddings().weight.shape[0]==VOCAB_SIZE and model.get_output_embeddings().weight.shape[0]==VOCAB_SIZE,
                'all151936 full head rows required')
        model.requires_grad_(False);model.eval()
        identity={'format':'irisx/qwen14b-native-interface-v1','model_key':MODEL_KEY,'model_id':MODEL_ID,'revision':REVISION,
                  'profile_id':PROFILE_ID,'execution_mode':'native-qwen3-pretrained-probe','pretrained_weights_loaded':True,
                  'random_test_weights':False,'production_admitted':False,'probe_pretrained_admitted':True,
                  'public_solving_admitted':False,'model_manifest_sha256':reviewed['model_manifest_sha256'],
                  'reviewed_deployment_id':config['reviewed_deployment_id'],'full_vocabulary_rows':VOCAB_SIZE,
                  'base_precision':'bfloat16','environment':environment,'hardware_profile':reviewed['hardware'],
                  'admission_phase':reviewed['admission_phase'],'native_eos_policy':policy}
        _VERIFIED_LOADED_MODELS[model] = {'tokenizer':tokenizer,'identity':identity,'hardware':hardware,
                                         'reviewed_deployment_id':config['reviewed_deployment_id']}
        return model,tokenizer,identity,hardware
    except BaseException:
        del model
        raise
