"""Finite same-weight Flash/one-sequence-varlen/packed numerical diagnosis.

Every outer forward is reserved by the actual model call hook. Full BF16
logits (losslessly represented as little-endian FP32) and sampled layer states
are retained before numerical gates. No optimizer, generation or teacher runs.
"""
from __future__ import annotations

import copy
import gc
import json
from pathlib import Path
import time

from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_qwen3_packing import TORCH_VARLEN, packed_forward, register_torch_varlen
from .canonical import digest_value
from .errors import ValidationError

FORMAT = 'irisx/nvarc-original-qwen3-packing-diagnostic-v1'
ATOL, RTOL = 0.25, 0.03
TINY = [{'input_ids':[14,11,10,1,15,14,12,10,2,15], 'labels':[-100]*8+[2,15]},
        {'input_ids':[14,11,10,3,4,15,14,12,10,5,6,15], 'labels':[-100]*9+[5,6,15]}]


def ordered_rows(rows):
    layout = pack_sequences(rows, capacity=256000)[0]
    return layout, [rows[s['row_index']] for s in layout['segments']]


def changed_rows(rows):
    result = copy.deepcopy(rows)
    layout, _ = ordered_rows(rows)
    index = layout['segments'][0]['row_index']
    position = next(i for i,x in enumerate(result[index]['input_ids'])
                    if x < 10 and result[index]['labels'][i] == -100)
    result[index]['input_ids'][position] = (result[index]['input_ids'][position]+1)%10
    return result


def schedule(rows):
    """Reconstruct the actual unpadded, ordered inputs for every allowed call."""
    _, ordered = ordered_rows(rows)
    _, tiny_ordered = ordered_rows(TINY)
    result = []
    def add(stage, ids):
        result.append({'stage':stage, 'input_tokens':len(ids), 'input_ids_digest':digest_value(ids)})
    for row in TINY: add('tiny-independent-gradients', row['input_ids'])
    add('tiny-packed-gradients', [x for r in tiny_ordered for x in r['input_ids']])
    for stage in ('actual-independent-flash-sdpa', 'actual-single-varlen'):
        for row in ordered: add(stage, row['input_ids'])
    add('actual-packed-varlen', [x for r in ordered for x in r['input_ids']])
    _, changed = ordered_rows(changed_rows(rows))
    add('actual-packed-isolation', [x for r in changed for x in r['input_ids']])
    return result


class ForwardBudget:
    """Actual model entry guard, independently testable without importing ML."""
    def __init__(self, rows, plan, retain):
        self.allowed = schedule(rows)
        self.plan, self.retain = plan, retain
        self.events, self.active = [], None
        self.started = time.monotonic()

    def perform(self, stage, operation):
        if self.active is not None: raise ValidationError('nested outer forward scope')
        before = len(self.events)
        self.active = stage
        try:
            result = operation()
            if len(self.events) != before+1: raise ValidationError('exactly one guarded forward required')
            return result
        finally:
            self.active = None

    def guard_call(self, module, args, kwargs, original):
        if type(module).__name__ != 'Qwen3ForCausalLM': return original(module,*args,**kwargs)
        ids = kwargs.get('input_ids', args[0] if args else None)
        if self.active is None or ids is None or len(self.events) >= len(self.allowed):
            raise ValidationError('unreserved outer forward blocked')
        array = ids.tolist()
        if len(array) != 1: raise ValidationError('single physical packed batch required')
        expected = self.allowed[len(self.events)]
        if self.active != expected['stage'] or digest_value(array[0]) != expected['input_ids_digest']:
            raise ValidationError('actual outer forward input/order differs')
        calls = len(self.events)+1
        tokens = sum(e['input_tokens'] for e in self.events)+len(array[0])
        if (calls > self.plan['maximum_outer_forwards'] or tokens > self.plan['maximum_input_tokens'] or
                time.monotonic()-self.started > self.plan['maximum_worker_wall_seconds']-60):
            raise ValidationError('actual forward/token/time ceiling reached')
        event = {**expected, 'cumulative_forwards':calls, 'cumulative_input_tokens':tokens, 'completed':False}
        self.events.append(event)
        self.retain('worker-ledger.json', self.events)
        result = original(module,*args,**kwargs)
        event['completed'] = True
        self.retain('worker-ledger.json', self.events)
        return result


def run(plan, rows, compact, output):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from tokenizers import Tokenizer
    if (plan['format'] != FORMAT or plan['owner_decision'] != 'Decision 0054' or
            plan['maximum_generations'] != 0 or plan['maximum_optimizer_steps'] != 0 or
            plan['maximum_teacher_calls'] != 0 or plan['maximum_paid_usd'] != 0 or
            digest_value(rows) != plan['data_digest'] or len(rows) != 8 or
            plan['forward_schedule'] != schedule(rows) or plan['atol'] != ATOL or plan['rtol'] != RTOL):
        raise ValidationError('exact finite original packing diagnostic required')
    started = time.monotonic(); device = torch.device('cuda:0')
    def retain(name, value):
        (output/name).write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    vectors = {}
    def binary(name, tensor):
        value = tensor.detach().float().cpu().contiguous()
        if not torch.isfinite(value).all(): raise ValidationError('nonfinite retained numerical vector')
        path = name+'.f32le'; raw = value.numpy().astype('<f4',copy=False).tobytes()
        (output/path).write_bytes(raw)
        vectors[name] = {'path':path, 'shape':list(value.shape), 'dtype':'float32-le'}
        retain('vectors.json', vectors)
        return value
    budget = ForwardBudget(rows,plan,retain)
    original_call = torch.nn.Module._call_impl
    def guarded(module,*args,**kwargs): return budget.guard_call(module,args,kwargs,original_call)
    torch.nn.Module._call_impl = guarded
    try:
        register_torch_varlen(); torch.manual_seed(731)
        config = Qwen3Config(vocab_size=16,hidden_size=64,intermediate_size=128,num_hidden_layers=2,
            num_attention_heads=4,num_key_value_heads=2,head_dim=16,max_position_embeddings=262144,
            rope_theta=5000000,attention_dropout=0.0,tie_word_embeddings=True,pad_token_id=13)
        config._attn_implementation = 'sdpa'
        reference = Qwen3ForCausalLM(config).to(device=device,dtype=torch.bfloat16).eval()
        packed = copy.deepcopy(reference); packed.config._attn_implementation = TORCH_VARLEN
        tiny_layout = pack_sequences(TINY,capacity=128)[0]
        expected_loss = torch.zeros((),device=device); expected_logits = []
        # Force the same documented Flash backend, excluding cuDNN/math fallback.
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            for row in TINY:
                logits = budget.perform('tiny-independent-gradients',lambda:
                    reference(torch.tensor([row['input_ids']],device=device),use_cache=False).logits)
                expected_logits.append(logits.detach())
                expected_loss = expected_loss+torch.nn.functional.cross_entropy(logits[:,:-1].float().reshape(-1,16),
                    torch.tensor(row['labels'][1:],device=device),ignore_index=-100,reduction='sum')
        expected_loss.div(tiny_layout['supervised_tokens']).backward()
        actual = budget.perform('tiny-packed-gradients',lambda:
            packed_forward(packed,tiny_layout,backend='torch-varlen-flash'))
        actual['loss_sum'].div(actual['supervised_tokens']).backward()
        differences = []
        for (name,lhs), (_,rhs) in zip(packed.named_parameters(),reference.named_parameters()):
            if lhs.grad is None or rhs.grad is None or not torch.isfinite(lhs.grad).all():
                raise ValidationError('tiny native varlen gradient missing/nonfinite: '+name)
            torch.testing.assert_close(lhs.grad,rhs.grad,atol=0.006,rtol=0.06,msg=name)
            differences.append({'name':name,'max_absolute_error':float((lhs.grad.float()-rhs.grad.float()).abs().max())})
        for i,expected in enumerate(expected_logits):
            begin,end = actual['offsets'][i:i+2]
            torch.testing.assert_close(actual['logits'][:,begin:end],expected,atol=0.006,rtol=0.06)
        retain('tiny-gradient-differential.json',{'dtype':'bfloat16','gradient_tensors':differences,
            'packed_token_mean_loss':float(actual['loss_sum'].detach())/tiny_layout['supervised_tokens'],
            'independent_token_mean_loss':float(expected_loss.detach())/tiny_layout['supervised_tokens'],
            'atol':0.006,'rtol':0.06,'original_scale':False})
        del actual,reference,packed,expected_loss,expected_logits
        gc.collect(); torch.cuda.empty_cache()
        tokenizer = Tokenizer.from_file(str(compact/'tokenizer.json'))
        if tokenizer.encode('<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>').ids != [14,11,10,1,2,15,14,12,10,3,4,15]:
            raise ValidationError('source WordLevel formatter encoding differs')
        model = Qwen3ForCausalLM.from_pretrained(compact,local_files_only=True,dtype=torch.bfloat16,
            attn_implementation='sdpa').to(device).eval()
        if model.get_input_embeddings().weight.data_ptr() != model.get_output_embeddings().weight.data_ptr():
            raise ValidationError('source tied embeddings differ')
        retain('loaded-config.json',model.config.to_dict())
        layout, ordered = ordered_rows(rows)
        offsets = [0]
        for row in ordered: offsets.append(offsets[-1]+len(row['input_ids']))
        # Three fixed token locations per whole source row; no extra model call.
        sampled = [[0,len(row['input_ids'])//2,len(row['input_ids'])-1] for row in ordered]
        retain('sampled-states-policy.json',{'row_indices':[s['row_index'] for s in layout['segments']],
            'local_token_positions':sampled,'layers':['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm'],
            'shape':[38,8,3,2560],'no_additional_forward':True})
        captures = {}; positions = []
        def capture(name):
            def hook(module,args,value):
                if isinstance(value,tuple): value = value[0]
                captures[name] = value[:,positions].detach().float().cpu()
            return hook
        hooks = [model.model.embed_tokens.register_forward_hook(capture('embed_tokens')),
                 model.model.norm.register_forward_hook(capture('norm'))]
        hooks.extend(layer.register_forward_hook(capture(f'layer-{i}')) for i,layer in enumerate(model.model.layers))
        layers = ['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm']
        modes = {}; timings = []
        def saved_states(): return torch.stack([captures[name][0] for name in layers])
        with torch.inference_mode():
            for mode in ('independent-flash-sdpa','single-varlen'):
                logits_list,states_list = [],[]
                model.config._attn_implementation = 'sdpa' if mode.startswith('independent') else TORCH_VARLEN
                torch.cuda.synchronize(); before = time.monotonic()
                for index,row in enumerate(ordered):
                    positions = sampled[index]
                    if mode.startswith('independent'):
                        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                            logits = budget.perform('actual-'+mode,lambda:
                                model(torch.tensor([row['input_ids']],device=device),use_cache=False).logits)
                    else:
                        result = budget.perform('actual-'+mode,lambda:
                            packed_forward(model,pack_sequences([row],capacity=256000)[0],backend='torch-varlen-flash'))
                        logits = result['logits']; del result
                    logits_list.append(logits.cpu()); states_list.append(saved_states())
                    # Persist each completed row even if a later call fails.
                    binary(mode+'-logits',torch.cat(logits_list,dim=1))
                    binary(mode+'-states',torch.stack(states_list,dim=1))
                    del logits
                torch.cuda.synchronize(); timings.append({'mode':mode,'seconds':time.monotonic()-before})
                modes[mode] = torch.cat(logits_list,dim=1).float()
            positions = [offsets[i]+p for i,ps in enumerate(sampled) for p in ps]
            torch.cuda.synchronize(); before = time.monotonic()
            actual = budget.perform('actual-packed-varlen',lambda:packed_forward(model,layout,backend='torch-varlen-flash'))
            torch.cuda.synchronize(); timings.append({'mode':'packed-varlen','seconds':time.monotonic()-before})
            modes['packed-varlen'] = binary('packed-varlen-logits',actual['logits'])
            binary('packed-varlen-states',saved_states().reshape(38,8,3,2560))
            loss = float(actual['loss_sum'])/actual['supervised_tokens']; del actual
            # Retain all mismatches before checking the unchanged original gate.
            report = {'atol':ATOL,'rtol':RTOL,'offsets':offsets,'timings':timings,
                'packed_token_mean_loss':loss,'comparisons':{},'all_logits_retained':True,
                'timing_scope':'cold forward with diagnostic hooks and output retention; not training throughput'}
            for reference_mode,actual_mode in [('independent-flash-sdpa','single-varlen'),
                    ('single-varlen','packed-varlen'),('independent-flash-sdpa','packed-varlen')]:
                measurements = []
                for start,stop in zip(offsets,offsets[1:]):
                    lhs = modes[reference_mode][:,start:stop]; rhs = modes[actual_mode][:,start:stop]
                    error = (rhs-lhs).abs(); bad = error > ATOL+RTOL*lhs.abs()
                    measurements.append({'max_absolute_error':float(error.max()),'outside_tolerance':int(bad.sum()),
                        'elements':lhs.numel(),'argmax_disagreements':int((lhs.argmax(-1)!=rhs.argmax(-1)).sum())})
                report['comparisons'][actual_mode+'-vs-'+reference_mode] = measurements
            retain('actual-weight-differential.json',report)
            positions = []  # Isolation needs full logits, without additional sampled state bytes.
            for hook in hooks: hook.remove()
            altered = budget.perform('actual-packed-isolation',lambda:packed_forward(model,
                pack_sequences(changed_rows(rows),capacity=256000)[0],backend='torch-varlen-flash'))
            changed_logits = binary('isolation-logits',altered['logits'])
            isolated = torch.equal(changed_logits[:,offsets[1]:],modes['packed-varlen'][:,offsets[1]:])
            retain('isolation.json',{'unchanged_later_samples_bitwise_equal':isolated,
                'original_prefix_digest':digest_value(rows),'changed_prefix_digest':digest_value(changed_rows(rows))})
            primary = report['comparisons']['packed-varlen-vs-independent-flash-sdpa']
            if not isolated or any(row['outside_tolerance'] for row in primary):
                raise ValidationError('original fixed packed numerical/isolation gate rejected; full diagnostics retained')
        result = {'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':'complete',
            'reserved_outer_forwards':len(budget.events),'reserved_input_tokens':sum(e['input_tokens'] for e in budget.events),
            'actual_qwen3_weight_forward_differential':True,'actual_qwen3_packed_isolation':True,
            'tiny_gradient_differential':True,'native_varlen_flash_verified':True,
            'model_material_digest':plan['model_material_digest'],'generation_calls':0,'optimizer_steps':0,
            'full_sft_completed':False,'historical_nemo_unsloth_parity':False,'contains_evaluator_truth':False,
            'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'worker_wall_seconds':time.monotonic()-started}
        retain('worker-result.json',result)
        return result
    finally:
        torch.nn.Module._call_impl = original_call


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('plan','samples','compact','output'): parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args(); args.output.mkdir()
    run(json.loads(args.plan.read_bytes()),json.loads(args.samples.read_bytes()),args.compact,args.output)
