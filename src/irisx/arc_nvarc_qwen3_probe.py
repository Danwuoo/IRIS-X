"""Bounded original-family Qwen3 packing/config probe, without generation."""
from __future__ import annotations

import copy
import gc
import hashlib
import json
from pathlib import Path
import time

from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_qwen3_packing import TORCH_VARLEN, packed_forward, register_torch_varlen
from .canonical import digest_value
from .errors import ValidationError


def run(plan, rows, compact, output):
    import torch
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from tokenizers import Tokenizer
    started = time.monotonic()
    device = torch.device('cuda:0')
    register_torch_varlen()
    if (plan['owner_decision'] != 'Decision 0054' or plan['maximum_generations'] != 0 or
            plan['maximum_optimizer_steps'] != 0 or plan['maximum_paid_usd'] != 0 or
            digest_value(rows) != plan['data_digest'] or len(rows) != 8):
        raise ValidationError('exact bounded original Qwen3 probe required')
    calls = tokens = 0
    events = []
    def retain(name, value):
        (output / name).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    def reserve(stage, n, input_tokens):
        nonlocal calls, tokens
        if (calls + n > plan['maximum_outer_forwards'] or tokens + input_tokens > plan['maximum_input_tokens'] or
                time.monotonic() - started > plan['maximum_worker_wall_seconds'] - 60):
            raise ValidationError('Qwen3 probe forward/token/time ceiling reached')
        calls += n
        tokens += input_tokens
        events.append({'stage': stage, 'reserved_forwards': n, 'reserved_input_tokens': input_tokens,
                       'cumulative_forwards': calls, 'cumulative_input_tokens': tokens})
        retain('worker-ledger.json', events)
    # An actual tiny CUDA backward is required for the native varlen path,
    # independently of the larger no-training original-weight forward probe.
    torch.manual_seed(731)
    config = Qwen3Config(vocab_size=16, hidden_size=64, intermediate_size=128,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        head_dim=16, max_position_embeddings=262144, rope_theta=5000000,
        attention_dropout=0.0, tie_word_embeddings=True, pad_token_id=13)
    config._attn_implementation = 'sdpa'
    reference = Qwen3ForCausalLM(config).to(device=device, dtype=torch.bfloat16).eval()
    packed = copy.deepcopy(reference)
    packed.config._attn_implementation = TORCH_VARLEN
    # These synthetic rows exercise unequal lengths and GQA; original corpus
    # rows are used only by the separate actual-weight probe below.
    tiny = [{'input_ids': [14,11,10,1,15,14,12,10,2,15], 'labels': [-100]*8+[2,15]},
            {'input_ids': [14,11,10,3,4,15,14,12,10,5,6,15], 'labels': [-100]*9+[5,6,15]}]
    layout = pack_sequences(tiny, capacity=128)[0]
    reserve('tiny-independent-gradients', 2, 22)
    expected_loss = torch.zeros((), device=device)
    expected_logits = []
    for row in tiny:
        logits = reference(torch.tensor([row['input_ids']], device=device), use_cache=False).logits
        expected_logits.append(logits.detach())
        expected_loss = expected_loss + torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1,16),
            torch.tensor(row['labels'][1:],device=device), ignore_index=-100, reduction='sum')
    expected_loss.div(layout['supervised_tokens']).backward()
    reserve('tiny-packed-gradients', 1, 22)
    actual = packed_forward(packed, layout, backend='torch-varlen-flash')
    actual['loss_sum'].div(actual['supervised_tokens']).backward()
    differences = []
    for (name, lhs), (_, rhs) in zip(packed.named_parameters(), reference.named_parameters()):
        if lhs.grad is None or rhs.grad is None or not torch.isfinite(lhs.grad).all():
            raise ValidationError('tiny native varlen gradient missing/nonfinite: '+name)
        torch.testing.assert_close(lhs.grad, rhs.grad, atol=0.006, rtol=0.06, msg=name)
        differences.append({'name':name,'max_absolute_error':float((lhs.grad.float()-rhs.grad.float()).abs().max())})
    for i, expected in enumerate(expected_logits):
        begin, end = actual['offsets'][i:i+2]
        torch.testing.assert_close(actual['logits'][:,begin:end], expected, atol=0.006, rtol=0.06)
    retain('tiny-gradient-differential.json', {'dtype':'bfloat16', 'gradient_tensors':differences,
        'packed_token_mean_loss':float(actual['loss_sum'].detach())/layout['supervised_tokens'],
        'independent_token_mean_loss':float(expected_loss.detach())/layout['supervised_tokens'],
        'atol':0.006,'rtol':0.06,'original_scale':False})
    del actual, reference, packed, expected_loss, expected_logits
    gc.collect(); torch.cuda.empty_cache()
    tokenizer = Tokenizer.from_file(str(compact / 'tokenizer.json'))
    if tokenizer.encode('<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>').ids != [14,11,10,1,2,15,14,12,10,3,4,15]:
        raise ValidationError('source WordLevel formatter encoding differs')
    model = Qwen3ForCausalLM.from_pretrained(compact, local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to(device).eval()
    if model.get_input_embeddings().weight.data_ptr() != model.get_output_embeddings().weight.data_ptr():
        raise ValidationError('source tied embeddings not preserved')
    retain('loaded-config.json', model.config.to_dict())
    pack = pack_sequences(rows, capacity=256000)[0]
    expected = []
    batch_tokens = sum(len(row['input_ids']) for row in rows)
    timings = []
    with torch.inference_mode():
        reserve('actual-weights-independent', 8, batch_tokens)
        torch.cuda.synchronize(); before = time.monotonic()
        for segment in pack['segments']:
            row = rows[segment['row_index']]
            expected.append(model(torch.tensor([row['input_ids']],device=device),use_cache=False).logits.cpu())
        torch.cuda.synchronize(); timings.append({'mode':'independent-sdpa','seconds':time.monotonic()-before})
        model.config._attn_implementation = TORCH_VARLEN
        reserve('actual-weights-packed', 1, batch_tokens)
        torch.cuda.synchronize(); before=time.monotonic()
        actual = packed_forward(model, pack, backend='torch-varlen-flash')
        torch.cuda.synchronize(); timings.append({'mode':'packed-native-varlen','seconds':time.monotonic()-before})
        max_errors = []
        for i, lhs in enumerate(expected):
            begin, end = actual['offsets'][i:i+2]
            rhs = actual['logits'][:,begin:end].cpu()
            max_errors.append(float((lhs.float()-rhs.float()).abs().max()))
            # BF16 reductions differ by kernel; retain measured errors and a
            # stated tolerance rather than claiming bitwise historical parity.
            torch.testing.assert_close(rhs, lhs, atol=0.25, rtol=0.03)
        retain('actual-weight-differential.json', {'max_absolute_logit_errors':max_errors,
            'packed_token_mean_loss':float(actual['loss_sum'])/actual['supervised_tokens'],
            'input_tokens':batch_tokens,'supervised_tokens':actual['supervised_tokens'],
            'atol':0.25,'rtol':0.03,'timings':timings,'timing_repetitions':1,
            'timing_scope':'inference forward only; one cold observation, not training throughput',
            'model_config':model.config.to_dict(),'no_generation':True})
        original = actual['logits'].cpu(); offsets=actual['offsets']; del actual
        changed = copy.deepcopy(rows)
        first_index = pack['segments'][0]['row_index']
        # Change an unlabelled public input token without changing labels.
        index = next(i for i,x in enumerate(changed[first_index]['input_ids']) if x<10 and changed[first_index]['labels'][i]==-100)
        changed[first_index]['input_ids'][index] = (changed[first_index]['input_ids'][index]+1)%10
        reserve('actual-weights-isolation',1,batch_tokens)
        altered=packed_forward(model,pack_sequences(changed,capacity=256000)[0],backend='torch-varlen-flash')
        tail=offsets[1]
        torch.testing.assert_close(altered['logits'][:,tail:].cpu(),original[:,tail:],atol=0,rtol=0)
        retain('isolation.json', {'unchanged_later_samples_bitwise_equal':True,'altered_row_index':first_index,
            'original_prefix_digest':digest_value(rows),'changed_prefix_digest':digest_value(changed)})
    result={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'outcome':'complete',
        'reserved_outer_forwards':calls,'reserved_input_tokens':tokens,
        'tiny_gradient_differential':True,'actual_qwen3_weight_forward_differential':True,
        'actual_qwen3_packed_isolation':True,'native_varlen_flash_verified':True,
        'model_material_digest':plan['model_material_digest'],'generation_calls':0,'optimizer_steps':0,
        'full_sft_completed':False,'historical_nemo_unsloth_parity':False,'contains_evaluator_truth':False,
        'cuda_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'worker_wall_seconds':time.monotonic()-started}
    retain('worker-result.json',result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('plan','samples','compact','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir()
    run(json.loads(args.plan.read_bytes()),json.loads(args.samples.read_bytes()),args.compact,args.output)
