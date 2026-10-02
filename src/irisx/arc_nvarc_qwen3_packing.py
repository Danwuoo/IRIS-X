"""Single-forward packed Qwen3 execution with explicit sample boundaries.

Dense SDPA is a small differential reference with quadratic mask memory.
FlashAttention-2 uses true varlen boundaries without a dense block mask.
Neither backend establishes the unknown historical NeMo/Unsloth numerics.
The Qwen3.5 hybrid port deliberately retains its segmented state executor.
"""
from __future__ import annotations

from .arc_nvarc_packing import validate_pack
from .canonical import digest_value
from .errors import ValidationError

TORCH_VARLEN = 'irisx_qwen3_torch_varlen'


def execution_slices(pack,maximum_input_tokens):
    """Partition a retained logical MFFD bin at whole-sample boundaries.

    Source placement, row order, labels, lineage and each complete sequence
    remain unchanged. Only the physical forward sizes change; gradients must
    accumulate before the one original global-token optimizer update.
    """
    validate_pack(pack)
    if type(maximum_input_tokens) is not int or maximum_input_tokens<2:
        raise ValidationError('positive whole-sample physical token ceiling required')
    groups=[];group=[];used=0
    for index,segment in enumerate(pack['segments']):
        length=segment['input_tokens']
        if length>maximum_input_tokens:
            raise ValidationError('whole source sequence exceeds physical token ceiling; truncation forbidden')
        if group and used+length>maximum_input_tokens:
            groups.append(group);group=[];used=0
        group.append(index);used+=length
    if group:groups.append(group)
    result=[];parent=digest_value(pack)
    tensor_keys=('input_ids','labels','position_ids','attention_mask')
    for indices in groups:
        piece={k:v for k,v in pack.items() if k not in {*tensor_keys,'segments','cu_seqlens','input_tokens','supervised_tokens'}}
        piece.update({key:[] for key in tensor_keys});piece.update(segments=[],cu_seqlens=[0])
        for index in indices:
            segment=pack['segments'][index];start,stop=segment['start'],segment['end'];offset=len(piece['input_ids'])
            for key in tensor_keys:piece[key].extend(pack[key][start:stop])
            piece['segments'].append({**segment,'start':offset,
                'valid_end':offset+segment['valid_end']-start,'end':offset+stop-start})
            piece['cu_seqlens'].append(offset+stop-start)
        piece.update(input_tokens=sum(s['input_tokens'] for s in piece['segments']),
            supervised_tokens=sum(s['supervised_tokens'] for s in piece['segments']),
            execution_slice={'logical_pack_digest':parent,'logical_segment_indices':indices,
                'maximum_physical_input_tokens':maximum_input_tokens})
        validate_pack(piece);result.append(piece)
    if sum(p['input_tokens'] for p in result)!=pack['input_tokens']:
        raise ValidationError('physical source coverage differs')
    return result


def register_torch_varlen():
    """Register the pinned PyTorch public varlen API; never fetch kernels."""
    from transformers import AttentionInterface, AttentionMaskInterface
    AttentionInterface.register(TORCH_VARLEN, torch_varlen_attention)
    # The packed executor supplies explicit cu_seqlens; constructing a flat
    # causal mask here would destroy sample isolation or force quadratic memory.
    AttentionMaskInterface.register(TORCH_VARLEN, lambda **kwargs: None)


def torch_varlen_attention(module, query, key, value, attention_mask, *, dropout=0.0,
                           scaling=None, cu_seq_lens_q=None, cu_seq_lens_k=None,
                           max_length_q=None, max_length_k=None, **kwargs):
    import torch
    from torch.nn.attention.varlen import varlen_attn
    if (query.device.type != 'cuda' or query.shape[0] != 1 or attention_mask is not None or
            dropout != 0 or module.sliding_window is not None or
            abs(scaling - query.shape[-1] ** -0.5) > 1e-12 or
            any(x is None for x in (cu_seq_lens_q, cu_seq_lens_k, max_length_q, max_length_k))):
        raise ValidationError('explicit causal zero-dropout packed CUDA varlen contract required')
    # PyTorch 2.10's public API has no enable_gqa argument. Explicit head repeat
    # keeps the Qwen grouped-query math with a version-independent signature.
    repeat = query.shape[1] // key.shape[1]
    if query.shape[1] != key.shape[1] * repeat:
        raise ValidationError('Qwen3 GQA head ratio differs')
    key = key.repeat_interleave(repeat, dim=1)
    value = value.repeat_interleave(repeat, dim=1)
    q, k, v = (x.transpose(1, 2).squeeze(0).contiguous() for x in (query, key, value))
    output = varlen_attn(q, k, v, cu_seq_lens_q, cu_seq_lens_k, max_length_q, max_length_k, is_causal=True)
    return output.unsqueeze(0), None


def packed_tensors(pack, device):
    import torch
    validate_pack(pack)
    ids, labels, positions, offsets = [], [], [], [0]
    for segment in pack['segments']:
        start, stop = segment['start'], segment['valid_end']
        ids.extend(pack['input_ids'][start:stop])
        labels.extend(pack['labels'][start:stop])
        positions.extend(range(stop - start))
        offsets.append(len(ids))
    return {'input_ids': torch.tensor([ids], dtype=torch.long, device=device),
        'labels': torch.tensor([labels], dtype=torch.long, device=device),
        'position_ids': torch.tensor([positions], dtype=torch.long, device=device),
        'cu_seqlens': torch.tensor(offsets, dtype=torch.int32, device=device),
        'offsets': offsets, 'max_seqlen': max(b - a for a, b in zip(offsets, offsets[1:]))}


def dense_mask(offsets, device, dtype, maximum_tokens=8192):
    import torch
    size = offsets[-1]
    if size > maximum_tokens:
        raise ValidationError('quadratic dense reference exceeds its token ceiling')
    mask = torch.full((size, size), float('-inf'), dtype=dtype, device=device)
    for start, stop in zip(offsets, offsets[1:]):
        mask[start:stop, start:stop] = torch.triu(
            torch.full((stop - start, stop - start), float('-inf'), dtype=dtype, device=device), diagonal=1)
    return mask[None, None]


def packed_forward(model, pack, *, backend='dense-sdpa-reference', maximum_dense_tokens=8192, device=None):
    import torch
    if model.config.model_type != 'qwen3' or model.config.vocab_size != 16 or model.config.attention_dropout != 0:
        raise ValidationError('zero-dropout compact original-family Qwen3 required')
    impl = model.config._attn_implementation
    # An idle CPU-offloaded FSDP shard does not identify the compute device.
    # Distributed callers must provide the explicit rank-local input device.
    tensors = packed_tensors(pack, next(model.parameters()).device if device is None else device)
    common = {'input_ids': tensors['input_ids'], 'position_ids': tensors['position_ids'], 'use_cache': False}
    if backend == 'dense-sdpa-reference':
        if impl != 'sdpa':
            raise ValidationError('dense reference requires explicit SDPA, without fallback')
        mask = dense_mask(tensors['offsets'], tensors['input_ids'].device, next(model.parameters()).dtype,
                          maximum_tokens=maximum_dense_tokens)
        common['attention_mask'] = {'full_attention': mask}
    elif backend in {'flash-attention-2-varlen', 'torch-varlen-flash'}:
        expected = 'flash_attention_2' if backend == 'flash-attention-2-varlen' else TORCH_VARLEN
        if impl != expected or tensors['input_ids'].device.type != 'cuda':
            raise ValidationError('varlen requires explicitly configured CUDA backend')
        common.update(attention_mask={'full_attention': None}, cu_seq_lens_q=tensors['cu_seqlens'],
            cu_seq_lens_k=tensors['cu_seqlens'], max_length_q=tensors['max_seqlen'],
            max_length_k=tensors['max_seqlen'])
    else:
        raise ValidationError('unknown packed Qwen3 backend')
    logits = model(**common).logits
    # First labels at every sample are ignored before causal shifting. Thus no
    # loss term predicts the next sample's first token from the preceding one.
    shifted = tensors['labels'][:, 1:]
    supervised = int((shifted != -100).sum())
    if supervised != pack['supervised_tokens'] or supervised == 0:
        raise ValidationError('packed supervision boundary differs')
    loss_sum = torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 16),
        shifted.reshape(-1), ignore_index=-100, reduction='sum')
    return {'logits': logits, 'loss_sum': loss_sum, 'supervised_tokens': supervised,
        'offsets': tensors['offsets'], 'physical_input_tokens': tensors['offsets'][-1],
        'logical_padded_tokens': len(pack['input_ids']), 'backend': backend,
        'outer_model_forwards': 1}
