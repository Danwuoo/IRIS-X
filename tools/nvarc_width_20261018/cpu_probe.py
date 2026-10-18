"""Bounded actual official-weight CPU component proof, never ARC/full-model evidence.

No downloads, no full-model allocation, no tensor export. Official checkpoint
files are verified once, selected layer bytes are independently hashed, and native
PEFT initialization follows the full meta-model target traversal. Children are
CPU/thread/RSS/wall bounded; existing immutable model files are read in place.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
MODEL=None

def write_json(path,data):
    Path(path).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')

def tensor_sha(t):
    return hashlib.sha256(t.detach().contiguous().view(dtype=torch.uint8).numpy().tobytes()).hexdigest()

def state_sha(module,frozen_only=False):
    h=hashlib.sha256()
    for name,p in sorted(module.named_parameters()):
        if frozen_only and p.requires_grad: continue
        h.update(name.encode());h.update(tensor_sha(p).encode())
    return h.hexdigest()

def stats(t):
    return {'norm':float(t.detach().norm()),'nonzero':int(t.detach().count_nonzero()),'finite':bool(torch.isfinite(t).all())}

def gap(a,b):
    return {'max_absolute':float((a-b).abs().max()),'relative_l2':float((a-b).norm()/a.norm().clamp_min(1e-30)),
        'finite':bool(torch.isfinite(b).all()),'bitwise_equal':bool(torch.equal(a,b))}

def build_block(index, receipt):
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from peft import LoraConfig, get_peft_model
    from tools.nvarc_posttrain_20261017.engine import PROJECTIONS, model_contract
    raw = json.loads((MODEL / 'config.json').read_text())
    config = Qwen3Config(**raw)
    config._attn_implementation = 'sdpa'
    receipt['official_model_contract'] = model_contract(config, variant='2b')
    # No actual full-model weights are allocated. Keeping all native target names
    # means PEFT's own CPU RNG draws follow the complete official traversal.
    with torch.device('meta'):
        skeleton = Qwen3ForCausalLM(config).to(dtype=torch.bfloat16)
    block = skeleton.model.layers[index]
    with (MODEL / 'model.safetensors').open('rb') as f:
        hsize = struct.unpack('<Q', f.read(8))[0]
        header = json.loads(f.read(hsize))
        receipt['header_sha256'] = hashlib.sha256(json.dumps(header, sort_keys=True).encode()).hexdigest()
        selected = {}
        provenance = []
        prefix = f'model.layers.{index}.'
        for name, meta in header.items():
            if not name.startswith(prefix):
                continue
            assert meta['dtype'] == 'BF16'
            lo, hi = meta['data_offsets']
            assert hi-lo == math.prod(meta['shape']) * 2
            f.seek(8+hsize+lo)
            data = bytearray(f.read(hi-lo))
            assert len(data) == hi-lo
            tensor = torch.frombuffer(data, dtype=torch.bfloat16).reshape(meta['shape']).clone()
            selected[name[len(prefix):]] = tensor
            provenance.append({'name': name, **meta, 'absolute_start': 8+hsize+lo,
                               'source_bytes_sha256': hashlib.sha256(data).hexdigest()})
            del data
        block.load_state_dict(selected, strict=True, assign=True)
        del selected
    receipt['tensor_provenance'] = provenance
    receipt['real_source_parameters'] = sum(p.numel() for p in block.parameters())
    assert sum(p.numel() for p in skeleton.parameters() if p.device.type != 'meta') == receipt['real_source_parameters']
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(731)
        skeleton = get_peft_model(skeleton, LoraConfig(r=64, lora_alpha=16, lora_dropout=0.,
            use_rslora=True, bias='none', task_type='CAUSAL_LM', target_modules=list(PROJECTIONS),
            modules_to_save=['embed_tokens', 'lm_head']))
    block = skeleton.get_base_model().model.layers[index]
    # Same CompactEngine ordering: promote trainables first, then all BF16 base.
    for p in block.parameters():
        if p.requires_grad:
            p.data = p.data.float()
    block.float().eval()
    receipt['adapter_initialization'] = {
        'seed': 731, 'r': 64, 'alpha': 16, 'use_rslora': True, 'scaling': 2.,
        'native_get_peft_model': True, 'full_native_target_traversal_on_meta_skeleton': True,
        'all_real_parameters_fp32': all(p.dtype == torch.float32 for p in block.parameters()),
        'all_A_exactly_BF16_representable': all(torch.equal(p, p.bfloat16().float()) for n,p in block.named_parameters() if 'lora_A' in n),
        'all_B_zero': all(not bool(p.count_nonzero()) for n,p in block.named_parameters() if 'lora_B' in n),
        'same_seed_as_official_load_engine_default': True,
        'cpu_stream_not_claimed_bitwise_equal_to_cuda_initialization': True,
        'A_sha256': {n: tensor_sha(p) for n,p in block.named_parameters() if 'lora_A' in n}}
    assert receipt['adapter_initialization']['all_A_exactly_BF16_representable']
    assert receipt['adapter_initialization']['all_B_zero']
    assert all(p.device.type == 'cpu' for p in block.parameters())
    del skeleton
    return block, config


def probe(index,r):
    from tools.nvarc_width_20261018.expansion import widen_mlp,replica_indices,WIDTH
    from tools.nvarc_posttrain_20261017.precision import full_precision_compute
    from transformers.models.qwen3.modeling_qwen3 import Qwen3RotaryEmbedding
    block,config=build_block(index,r)
    mlp=block.mlp
    g=torch.Generator(device='cpu').manual_seed(20261018)
    x=(torch.randn((1,24,config.hidden_size),generator=g)*.2).requires_grad_()
    target=torch.randn(x.shape,generator=g)*.1
    positions=torch.arange(x.shape[1]).unsqueeze(0)
    rope=Qwen3RotaryEmbedding(config);position_embeddings=rope(x,positions)
    mask=torch.full((1,1,x.shape[1],x.shape[1]),float('-inf')).triu(1)
    def forward_block():
        return block(x,attention_mask=mask,position_ids=positions,position_embeddings=position_embeddings,use_cache=False)
    with torch.no_grad(),full_precision_compute('cpu'):
        base=mlp(x).detach();base_block=forward_block().detach()
    with full_precision_compute('cpu'):
        reference_input_grad=torch.autograd.grad((mlp(x)-target).square().mean(),x)[0].detach()
    r['expansion']=widen_mlp(mlp,WIDTH,layer_index=index)
    r['native_and_adapter_initialization_proofs_separate']=True
    index_map,_=replica_indices(6144,8192,index)
    with torch.no_grad(),full_precision_compute('cpu'):
        initial=mlp(x);initial_block=forward_block()
    with full_precision_compute('cpu'):
        expanded_input_grad=torch.autograd.grad((mlp(x)-target).square().mean(),x)[0].detach()
    r['FP32_input_gradient_gap']=gap(reference_input_grad,expanded_input_grad)
    assert r['FP32_input_gradient_gap']['max_absolute']<1e-6 and r['FP32_input_gradient_gap']['relative_l2']<1e-5
    r['FP32_mlp_gap']=gap(base,initial);r['FP32_residual_block_gap']=gap(base_block,initial_block)
    assert r['FP32_mlp_gap']['max_absolute']<1e-4
    r['residual_hidden_drift_descriptive_not_logit_admission']=True
    r['full_model_logit_1e_minus4_gate_executed']=False
    # Hidden-state magnitude is not logit units; final-layer synthetic residual
    # may be large. Preserve/report it, never use it to waive the full logit gate.
    # A counterfactual numerical diagnostic only, not a permitted runtime policy.
    # Compute native MLP with re-quantized paired matrices without changing source.
    import torch.nn.functional as F
    with torch.no_grad(),full_precision_compute('cpu'):
        q=lambda m: m.base_layer.weight.bfloat16().float()
        re=F.linear(F.silu(F.linear(x,q(mlp.gate_proj)))*F.linear(x,q(mlp.up_proj)),q(mlp.down_proj))
        r['BF16_requantized_then_FP32_mlp_gap_NOT_ADMITTED']=gap(base,re)
    r['resident_parameters']=sum(p.numel() for p in mlp.parameters())
    r['trainable_parameters']=sum(p.numel() for p in mlp.parameters() if p.requires_grad)
    r['frozen_sha256_before']=state_sha(mlp,True)
    optimizer=torch.optim.AdamW([p for p in mlp.parameters() if p.requires_grad],lr=2e-5,weight_decay=.01)
    r['steps']=[]
    for step in range(2):
        optimizer.zero_grad(set_to_none=True);x.grad=None
        with full_precision_compute('cpu'):
            out=mlp(x);loss=(out-target).square().mean();loss.backward()
        gradients={name:stats(p.grad) for name,p in mlp.named_parameters() if p.requires_grad}
        assert all(v['finite'] for v in gradients.values()) and torch.isfinite(x.grad).all()
        assert all(p.grad is None for p in mlp.parameters() if not p.requires_grad)
        bg=mlp.gate_proj.lora_B['default'].weight.grad
        differential=bg[index_map]-bg[6144:]
        dg=stats(differential)
        assert dg['finite'] and dg['norm']>0 and bool((differential.norm(dim=1)>0).all())
        row={'step':step,'loss':float(loss.detach()),'gradients':gradients,
             'antisymmetric_gate_B_direction_gradient':dg,
             'all2048_gate_replica_gradient_rows_distinct':True}
        optimizer.step()
        b=mlp.gate_proj.lora_B['default'].weight.detach()
        row['gate_B_replica_update_difference']=stats(b[index_map]-b[6144:])
        row['all2048_gate_replica_update_rows_distinct']=bool(((b[index_map]-b[6144:]).norm(dim=1)>0).all())
        assert row['all2048_gate_replica_update_rows_distinct']
        assert all(bool(torch.isfinite(p).all()) for p in mlp.parameters())
        r['steps'].append(row)
    first,second=(row['gradients'] for row in r['steps'])
    assert all(v['norm']==0 for k,v in first.items() if '.lora_A.' in k)
    assert all(v['norm']>0 for k,v in first.items() if '.lora_B.' in k)
    assert all(v['norm']>0 for k,v in second.items() if '.lora_A.' in k)
    assert state_sha(mlp,True)==r['frozen_sha256_before']
    r['frozen_weights_unchanged_after_two_AdamW_updates']=True
    r['input']={'shape':list(x.shape),'seed':20261018,'scale':.2,'sha256':tensor_sha(x),'synthetic_not_ARC':True}
    r['full_model_forward_or_scoring_performed']=False
    r['GPU_or_capability_validation_claimed']=False

def main():
    global torch,MODEL
    p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--layer',type=int)
    a=p.parse_args();MODEL=a.model_dir.resolve()
    if a.layer is not None:
        resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(120,125))
        resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**2,4*1024**2))
        start=time.monotonic();r={'format':'irisx/official-width-component-cpu-v1','original_layer':a.layer,'success':False}
        try:
            import torch,peft,transformers
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            r['versions']={'torch':torch.__version__,'peft':peft.__version__,'transformers':transformers.__version__}
            probe(a.layer,r);r['success']=True
        except BaseException as e:
            r['error']={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
        r['wall_seconds']=time.monotonic()-start;r['peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        write_json(a.output,r);print(json.dumps({k:r[k] for k in ('success','original_layer','wall_seconds','peak_RSS_bytes')},sort_keys=True),flush=True)
        return 0 if r['success'] else 1
    from tools.nvarc_posttrain_20261017.materials import verify_model
    identity=verify_model(MODEL,'2b')
    a.output.mkdir(parents=True,exist_ok=False)
    r={'format':'irisx/official-width-component-suite-v1','verified_original_model_identity':identity,
       'source_git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ('tools/nvarc_width_20261018/model.py','tools/nvarc_width_20261018/expansion.py','tools/nvarc_width_20261018/cpu_probe.py')},
       'no_remote_actions':True,'no_full_model_allocation':True,'no_tensor_exports':True,'cases':[]}
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
    for index in (6,13,20,27):
        with (a.output/f'layer{index}.log').open('w') as log:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--model-dir',str(MODEL),
                '--output',str(a.output/f'layer{index}.json'),'--layer',str(index)],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=240)
        row=json.loads((a.output/f'layer{index}.json').read_text())
        r['cases'].append({'layer':index,'success':row['success'],'exit_code':result.returncode,
                         'wall_seconds':row['wall_seconds'],'peak_RSS_bytes':row['peak_RSS_bytes']})
        write_json(a.output/'suite.json',r)
        print(json.dumps(r['cases'][-1]),flush=True)
        if result.returncode: return 1
    r['all_cases_passed']=True;write_json(a.output/'suite.json',r)
    return 0

if __name__=='__main__':sys.exit(main())
