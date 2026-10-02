"""Actual published 4B/rank-256 adapter topology and reset, zero forwards."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.acquire_nvarc_qwen3_sft import DEFAULT
from tools.verify_nvarc_qwen3_sft import verified_inventory,CHAT,IDS
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_complete_ttt import complete_config
from irisx.arc_nvarc_training import TaskLocalAdapter
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def inspect(folder,output):
    import torch
    import transformers
    import peft
    from peft import get_peft_model_state_dict
    from tokenizers import Tokenizer
    from transformers import Qwen3ForCausalLM
    if output.exists() or transformers.__version__!='4.53.3' or peft.__version__!='0.21.0':
        raise ValidationError('new exact published-runtime adapter observation required')
    proof=json.loads((folder/'independent-verification.json').read_bytes())
    if digest_value(verified_inventory(folder))!=proof['material_digest']:
        raise ValidationError('independently byte-verified original SFT material required')
    if Tokenizer.from_file(str(folder/'model/tokenizer.json')).encode(CHAT).ids!=IDS:
        raise ValidationError('explicit source WordLevel role encoding differs')
    output.mkdir(parents=True);started=time.monotonic();torch.set_num_threads(2)
    atomic(output/'ledger.json',{'owner_decision':'Decision 0054','run_id':output.name,
        'material_digest':proof['material_digest'],'model_loads_reserved':1,'maximum_wall_seconds':600,
        'maximum_outer_forwards':0,'maximum_training_tokens':0,'maximum_optimizer_steps':0,
        'maximum_generations':0,'maximum_paid_usd':0,'manual_reset_probe_perturbations':1})
    forwards=0
    try:
        base=Qwen3ForCausalLM.from_pretrained(folder/'model',local_files_only=True,
            torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval()
        if base.get_input_embeddings().weight.data_ptr()==base.get_output_embeddings().weight.data_ptr():
            raise ValidationError('published untied base weights were silently tied')
        def reject_forward(module,args):
            nonlocal forwards
            forwards+=1;raise ValidationError('zero-forward adapter topology envelope exceeded')
        hook=base.register_forward_pre_hook(reject_forward)
        config=complete_config()['adaptation'];config['optimizer_state_device']='cpu'
        adapter=TaskLocalAdapter(base,config)
        if len(adapter.targets)!=254:raise ValidationError('all nine original projection kinds across 36 layers required')
        trainable=Counter()
        for parameter in adapter.model.parameters():
            if parameter.requires_grad:trainable[str(parameter.dtype)]+=parameter.numel()
        def state():
            records={}
            for name,tensor in get_peft_model_state_dict(adapter.model).items():
                value=tensor.detach().cpu().contiguous()
                if not bool(torch.isfinite(value).all()):raise ValidationError('nonfinite actual adapter state')
                records[name]={'shape':list(value.shape),'dtype':str(value.dtype),
                    'sha256':hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest()}
            return records
        initial=state()
        with torch.no_grad():
            first=next(p for p in adapter.model.parameters() if p.requires_grad)
            first.reshape(-1)[0].add_(1)
        changed=state()
        if changed==initial:raise ValidationError('adapter reset negative control did not perturb state')
        adapter.reset();restored=state()
        if restored!=initial or forwards!=0:raise ValidationError('exact actual 4B adapter reset/zero-forward gate failed')
        hook.remove()
        result={'format':'irisx/nvarc-published-qwen3-adapter-material-v1','run_id':output.name,
            'outcome':'complete','model_material_digest':proof['material_digest'],
            'transformers_version':transformers.__version__,'peft_version':peft.__version__,'torch_version':torch.__version__,
            'base_device':'cpu','base_dtype':'bfloat16','embedding_head_tied':False,
            'num_hidden_layers':36,'adapter_rank':256,'adapter_alpha':32,'use_rslora':True,
            'adapter_targets':adapter.targets,'adapter_target_count':len(adapter.targets),
            'trainable_parameters_by_dtype':dict(trainable),'trainable_parameter_count':sum(trainable.values()),
            'adapter_state_tensors':initial,'adapter_state_digest':digest_value(initial),
            'manual_parameter_perturbations':1,'reset_state_bitwise_verified':True,
            'outer_forwards_observed':forwards,'optimizer_steps':0,'training_tokens':0,'generations':0,
            'long_task_epoch_completed':False,'historical_unsloth_parity':False,'correctness_scored':False,
            'wall_seconds':time.monotonic()-started,'maximum_paid_usd':0}
        atomic(output/'result.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in {'adapter_state_tensors','adapter_targets'}}),flush=True)
    except BaseException as error:
        atomic(output/'failure.json',{'state':'retained-failure','error_type':type(error).__name__,
            'message':str(error)[:1200],'outer_forwards_observed':forwards});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,default=DEFAULT)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    if args.worker:inspect(args.folder,args.output)
    else:
        subprocess.run([sys.executable,str(Path(__file__)), '--folder',str(args.folder),
            '--output',str(args.output),'--worker'],check=True,timeout=600)
