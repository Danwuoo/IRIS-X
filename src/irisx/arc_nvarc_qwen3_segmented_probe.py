"""Full-model segmented-GEMM packing gate; original thresholds, no optimizer."""
from __future__ import annotations
import copy
import gc
import json
from pathlib import Path
import time

from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_qwen3_packing import TORCH_VARLEN,packed_forward,packed_tensors,register_torch_varlen
from .arc_nvarc_qwen3_packing_diagnostic import ForwardBudget,TINY,ATOL,RTOL,ordered_rows,changed_rows
from .arc_nvarc_segmented_linear import segmented_linear
from .canonical import digest_value
from .errors import ValidationError

FORMAT='irisx/nvarc-original-qwen3-segmented-linear-probe-v1'


def schedule(rows):
    _,ordered=ordered_rows(rows);_,tiny_ordered=ordered_rows(TINY)
    result=[{'stage':'tiny-independent-gradients','input_tokens':len(row['input_ids']),
        'input_ids_digest':digest_value(row['input_ids'])} for row in TINY]
    def add(stage,ids):result.append({'stage':stage,'input_tokens':len(ids),'input_ids_digest':digest_value(ids)})
    add('tiny-packed-gradients',[x for row in tiny_ordered for x in row['input_ids']])
    for row in ordered:add('actual-independent-flash-sdpa',row['input_ids'])
    add('actual-packed-segmented',[x for row in ordered for x in row['input_ids']])
    _,altered=ordered_rows(changed_rows(rows))
    add('actual-packed-isolation',[x for row in altered for x in row['input_ids']])
    return result


class SegmentedBudget(ForwardBudget):
    def __init__(self,rows,plan,retain):
        super().__init__(rows,plan,retain);self.allowed=schedule(rows)


def run(plan,rows,compact,output):
    import torch
    from tokenizers import Tokenizer
    from torch.nn.attention import SDPBackend,sdpa_kernel
    from transformers import Qwen3Config,Qwen3ForCausalLM
    if (plan['format']!=FORMAT or plan['owner_decision']!='Decision 0054' or
            plan['forward_schedule']!=schedule(rows) or len(rows)!=8 or digest_value(rows)!=plan['data_digest'] or
            plan['atol']!=ATOL or plan['rtol']!=RTOL or plan['tiny_gradient_backwards']!=2 or
            any(type(plan[k]) is not int or plan[k]!=0 for k in
                ('maximum_optimizer_steps','maximum_generations','maximum_teacher_calls','maximum_paid_usd')) or
            torch.__version__!='2.10.0+cu128'):
        raise ValidationError('exact finite original-threshold segmented-linear probe required')
    started=time.monotonic();device=torch.device('cuda:0');vectors={};backwards=[];active_backward=None
    def retain(name,value):(output/name).write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    def binary(name,value):
        tensor=value.detach().float().cpu().contiguous()
        if not torch.isfinite(tensor).all():raise ValidationError('finite retained segmented vector required')
        path=name+'.f32le';(output/path).write_bytes(tensor.numpy().astype('<f4',copy=False).tobytes())
        vectors[name]={'path':path,'shape':list(tensor.shape),'dtype':'float32-le'};retain('vectors.json',vectors)
        return tensor
    budget=SegmentedBudget(rows,plan,retain);original_call=torch.nn.Module._call_impl
    original_backward,original_grad=torch.autograd.backward,torch.autograd.grad
    original_optimizer=torch.optim.Optimizer.__init__
    def call(module,*args,**kwargs):return budget.guard_call(module,args,kwargs,original_call)
    def backward(tensors,*args,**kwargs):
        values=(tensors,) if isinstance(tensors,torch.Tensor) else tuple(tensors)
        expected=('tiny-independent','tiny-packed')
        if (active_backward is None or len(backwards)>=2 or len(values)!=1 or values[0] is not active_backward[1] or
                active_backward[0]!=expected[len(backwards)]):raise ValidationError('unreserved backward blocked')
        event={'stage':active_backward[0],'completed':False};backwards.append(event);retain('backward-ledger.json',backwards)
        result=original_backward(tensors,*args,**kwargs);event['completed']=True;retain('backward-ledger.json',backwards)
        return result
    def blocked(*args,**kwargs):raise ValidationError('optimizer construction/autograd.grad blocked in inference probe')
    def perform_backward(stage,loss):
        nonlocal active_backward
        active_backward=(stage,loss)
        try:loss.backward()
        finally:active_backward=None
    torch.nn.Module._call_impl=call;torch.autograd.backward=backward;torch.autograd.grad=blocked
    torch.optim.Optimizer.__init__=blocked;hooks=[]
    try:
        register_torch_varlen();torch.manual_seed(731)
        config=Qwen3Config(vocab_size=16,hidden_size=64,intermediate_size=128,num_hidden_layers=2,
            num_attention_heads=4,num_key_value_heads=2,head_dim=16,max_position_embeddings=262144,
            rope_theta=5000000,attention_dropout=0.0,tie_word_embeddings=True,pad_token_id=13)
        config._attn_implementation='sdpa';reference=Qwen3ForCausalLM(config).to(device=device,dtype=torch.bfloat16).eval()
        packed=copy.deepcopy(reference);packed.config._attn_implementation=TORCH_VARLEN
        tiny=pack_sequences(TINY,capacity=128)[0];reference_logits=[];loss=torch.zeros((),device=device)
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            for row in TINY:
                logits=budget.perform('tiny-independent-gradients',lambda:reference(
                    input_ids=torch.tensor([row['input_ids']],device=device),use_cache=False).logits)
                reference_logits.append(logits.detach());loss=loss+torch.nn.functional.cross_entropy(
                    logits[:,:-1].float().reshape(-1,16),torch.tensor(row['labels'][1:],device=device),
                    ignore_index=-100,reduction='sum')
        perform_backward('tiny-independent',loss/tiny['supervised_tokens'])
        with segmented_linear(packed,packed_tensors(tiny,device)['offsets'],maximum_invocations_per_module=1) as policy:
            actual=budget.perform('tiny-packed-gradients',lambda:packed_forward(packed,tiny,backend='torch-varlen-flash'))
            perform_backward('tiny-packed',actual['loss_sum']/actual['supervised_tokens'])
        retain('tiny-linear-policy.json',policy);gradient_rows=[];gradient_pass=True
        for i,((name,lhs),(_,rhs)) in enumerate(zip(reference.named_parameters(),packed.named_parameters())):
            if lhs.grad is None or rhs.grad is None:raise ValidationError('all tiny gradients required: '+name)
            a=binary('tiny-reference-gradient-'+str(i),lhs.grad);b=binary('tiny-packed-gradient-'+str(i),rhs.grad)
            passed=bool(torch.all((a-b).abs()<=0.006+0.06*a.abs()));gradient_pass=gradient_pass and passed
            gradient_rows.append({'name':name,'shape':list(a.shape),'reference_vector':'tiny-reference-gradient-'+str(i),
                'packed_vector':'tiny-packed-gradient-'+str(i),'within_fixed_tolerance':passed})
        a=binary('tiny-reference-logits',torch.cat(reference_logits,dim=1));b=binary('tiny-packed-logits',actual['logits'])
        tiny_logits_pass=bool(torch.all((a-b).abs()<=0.006+0.06*a.abs()))
        retain('tiny-gradient-differential.json',{'gradients':gradient_rows,'atol':0.006,'rtol':0.06,
            'all_gradients_passed':gradient_pass,'all_logits_passed':tiny_logits_pass,'original_scale':False})
        del actual,reference,packed,loss,logits,reference_logits;gc.collect();torch.cuda.empty_cache()
        tokenizer=Tokenizer.from_file(str(compact/'tokenizer.json'))
        if tokenizer.encode('<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>').ids!=[14,11,10,1,2,15,14,12,10,3,4,15]:
            raise ValidationError('exact source WordLevel chat formatter required')
        model=Qwen3ForCausalLM.from_pretrained(compact,local_files_only=True,dtype=torch.bfloat16,
            attn_implementation='sdpa').to(device).eval()
        if len(model.model.layers)!=36 or model.get_input_embeddings().weight.data_ptr()!=model.get_output_embeddings().weight.data_ptr():
            raise ValidationError('complete unchanged tied original-family model required')
        retain('loaded-config.json',model.config.to_dict())
        layout,ordered=ordered_rows(rows);offsets=packed_tensors(layout,device)['offsets'];positions=[];captures={}
        layers=['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm']
        local_positions=[[0,len(row['input_ids'])//2,len(row['input_ids'])-1] for row in ordered]
        def capture(name):
            def hook(module,args,value):
                if isinstance(value,tuple):value=value[0]
                captures[name]=value[:,positions].detach().float().cpu()
            return hook
        hooks=[model.model.embed_tokens.register_forward_hook(capture('embed_tokens')),
            model.model.norm.register_forward_hook(capture('norm'))]
        hooks.extend(layer.register_forward_hook(capture(f'layer-{i}')) for i,layer in enumerate(model.model.layers))
        retain('sampled-states-policy.json',{'layers':layers,'local_positions':local_positions,'offsets':offsets,
            'shape':[38,8,3,2560],'no_additional_forward':True})
        timings=[];independent=[];states=[]
        with torch.inference_mode():
            torch.cuda.synchronize();before=time.monotonic()
            for i,row in enumerate(ordered):
                positions=local_positions[i]
                with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                    logits=budget.perform('actual-independent-flash-sdpa',lambda:model(
                        input_ids=torch.tensor([row['input_ids']],device=device),use_cache=False).logits)
                independent.append(logits.cpu());states.append(torch.stack([captures[name][0] for name in layers]))
                binary('independent-logits',torch.cat(independent,dim=1))
                binary('independent-states',torch.stack(states,dim=1))
            torch.cuda.synchronize();timings.append({'mode':'independent-flash-sdpa','seconds':time.monotonic()-before})
            model.config._attn_implementation=TORCH_VARLEN
            positions=[offsets[i]+position for i,ps in enumerate(local_positions) for position in ps]
            torch.cuda.synchronize();before=time.monotonic()
            with segmented_linear(model,offsets,maximum_invocations_per_module=1) as policy:
                actual=budget.perform('actual-packed-segmented',lambda:packed_forward(model,layout,backend='torch-varlen-flash'))
            torch.cuda.synchronize();timings.append({'mode':'packed-segmented','seconds':time.monotonic()-before})
            retain('full-linear-policy.json',policy)
            wanted=torch.cat(independent,dim=1).float();got=binary('packed-logits',actual['logits'])
            binary('packed-states',torch.stack([captures[name][0].reshape(8,3,-1) for name in layers]))
            numeric_pass=bool(torch.all((got-wanted).abs()<=ATOL+RTOL*wanted.abs()))
            changed=pack_sequences(changed_rows(rows),capacity=256000)[0]
            with segmented_linear(model,offsets,maximum_invocations_per_module=1) as isolation_policy:
                altered=budget.perform('actual-packed-isolation',lambda:packed_forward(model,changed,backend='torch-varlen-flash'))
            retain('isolation-linear-policy.json',isolation_policy);changed_logits=binary('isolation-logits',altered['logits'])
            isolated=torch.equal(changed_logits[:,offsets[1]:],got[:,offsets[1]:])
        result={'format':FORMAT,'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':'complete',
            'actual_outer_forwards':len(budget.events),'actual_input_tokens':sum(row['input_tokens'] for row in budget.events),
            'actual_backwards':len(backwards),'tiny_gradients_passed':gradient_pass,'tiny_logits_passed':tiny_logits_pass,
            'whole_model_fixed_numerical_gate_passed':numeric_pass,'later_samples_bitwise_isolated':isolated,
            'native_varlen_gpu_differential_observed':gradient_pass and tiny_logits_pass and numeric_pass and isolated,
            'decoder_layers_executed':36,'weights_modified':False,'stored_and_compute_dtype':'bfloat16',
            'optimizer_steps':0,'generation_calls':0,'teacher_calls':0,'full_sft_completed':False,'historical_nemo_unsloth_parity':False,
            'correctness_scored':False,'contains_evaluator_truth':False,'timings':timings,'worker_wall_seconds':time.monotonic()-started}
        retain('worker-result.json',result);return result
    finally:
        for hook in hooks:hook.remove()
        torch.nn.Module._call_impl=original_call;torch.autograd.backward=original_backward;torch.autograd.grad=original_grad
        torch.optim.Optimizer.__init__=original_optimizer


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    for name in ('plan','samples','compact','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    run(json.loads(args.plan.read_bytes()),json.loads(args.samples.read_bytes()),args.compact,args.output)
