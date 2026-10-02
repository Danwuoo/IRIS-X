"""First-layer shape/reduction/GQA localization; no whole-model qualification."""
from __future__ import annotations
from contextlib import contextmanager
import gc
import json
from pathlib import Path
import time
from types import MethodType

from .arc_nvarc_packing import pack_sequences
from .arc_nvarc_qwen3_packing import (TORCH_VARLEN, TORCH_VARLEN_GQA, packed_forward,
    register_torch_varlen, register_torch_varlen_gqa)
from .arc_nvarc_qwen3_packing_diagnostic import ForwardBudget, ordered_rows
from .canonical import digest_value
from .errors import ValidationError

FORMAT = 'irisx/nvarc-original-qwen3-first-layer-operators-v1'
MODES = ('independent-flash-sdpa', 'independent-fp32-linear', 'packed-repeat',
    'packed-repeat-no-reduced', 'packed-native-gqa', 'packed-native-gqa-no-reduced', 'packed-fp32-linear')
OPERATORS = ('embedding', 'input-norm', 'q-projection', 'k-projection', 'v-projection',
    'q-norm', 'k-norm', 'attention-before-o-projection', 'o-projection', 'post-attention-norm',
    'gate-projection', 'up-projection', 'product-before-down-projection', 'down-projection',
    'layer-0-output', 'final-norm')


def schedule(rows):
    _, ordered = ordered_rows(rows)
    flat = [token for row in ordered for token in row['input_ids']]
    result = []
    for mode in MODES:
        inputs = [row['input_ids'] for row in ordered] if mode.startswith('independent') else [flat]
        result.extend({'stage': mode, 'input_tokens': len(ids), 'input_ids_digest': digest_value(ids)} for ids in inputs)
    return result


class OperatorBudget(ForwardBudget):
    def __init__(self, rows, plan, retain):
        super().__init__(rows, plan, retain)
        self.allowed = schedule(rows)


@contextmanager
def precision_mode(model, torch, mode):
    """Restore all diagnostic compute settings/methods even after failure."""
    reduced = torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction
    precision = torch.get_float32_matmul_precision()
    methods = []
    fp32 = 'fp32-linear' in mode
    try:
        torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = not ('no-reduced' in mode or fp32)
        if fp32:
            torch.set_float32_matmul_precision('highest')
            for module in model.modules():
                if isinstance(module, torch.nn.Linear):
                    methods.append((module, 'forward' in module.__dict__, module.__dict__.get('forward')))
                    def linear(self, value):
                        bias = None if self.bias is None else self.bias.float()
                        return torch.nn.functional.linear(value.float(), self.weight.float(), bias).to(value.dtype)
                    module.forward = MethodType(linear, module)
        yield {'bf16_reduced_precision_reduction': torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
            'float32_matmul_precision': torch.get_float32_matmul_precision(),
            'linear_compute': 'float32 with output cast to input dtype' if fp32 else 'stored bfloat16',
            'rewritten_linear_modules': len(methods)}
    finally:
        for module, existed, method in methods:
            if existed: module.forward = method
            else: del module.forward
        torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = reduced
        torch.set_float32_matmul_precision(precision)


def parameter_layout(config):
    """Exact unchanged named-parameter subset; tied head has no duplicate entry."""
    hidden = config['hidden_size']; head = config['head_dim']; intermediate = config['intermediate_size']
    result = {'model.embed_tokens.weight': [config['vocab_size'], hidden], 'model.norm.weight': [hidden]}
    base = 'model.layers.0.'
    for name in ('input_layernorm', 'post_attention_layernorm'): result[base + name + '.weight'] = [hidden]
    for name, shape in {'q_proj': [config['num_attention_heads'] * head, hidden],
            'k_proj': [config['num_key_value_heads'] * head, hidden],
            'v_proj': [config['num_key_value_heads'] * head, hidden],
            'o_proj': [hidden, config['num_attention_heads'] * head],
            'q_norm': [head], 'k_norm': [head]}.items():
        result[base + 'self_attn.' + name + '.weight'] = shape
    for name, shape in {'gate_proj': [intermediate, hidden], 'up_proj': [intermediate, hidden],
            'down_proj': [hidden, intermediate]}.items(): result[base + 'mlp.' + name + '.weight'] = shape
    return result


class OperatorCapture:
    """Hooks select fixed tokens without another model call or changed output."""
    def __init__(self, model):
        self.positions = []; self.values = {}; self.hooks = []
        layer = model.model.layers[0]
        modules = {'embedding': model.model.embed_tokens, 'input-norm': layer.input_layernorm,
            'q-projection': layer.self_attn.q_proj, 'k-projection': layer.self_attn.k_proj,
            'v-projection': layer.self_attn.v_proj, 'q-norm': layer.self_attn.q_norm, 'k-norm': layer.self_attn.k_norm,
            'o-projection': layer.self_attn.o_proj, 'post-attention-norm': layer.post_attention_layernorm,
            'gate-projection': layer.mlp.gate_proj, 'up-projection': layer.mlp.up_proj,
            'down-projection': layer.mlp.down_proj, 'layer-0-output': layer, 'final-norm': model.model.norm}
        for name, module in modules.items():
            self.hooks.append(module.register_forward_hook(
                lambda module, args, value, name=name: self.capture(name, value)))
        for name, module in [('attention-before-o-projection', layer.self_attn.o_proj),
                ('product-before-down-projection', layer.mlp.down_proj)]:
            self.hooks.append(module.register_forward_pre_hook(
                lambda module, args, name=name: self.capture(name, args[0])))

    def capture(self, name, value):
        if isinstance(value, tuple): value = value[0]
        if value.shape[0] != 1: raise ValidationError('one physical batch required for fixed operator capture')
        self.values[name] = value[:, self.positions].detach().float().cpu().reshape(len(self.positions), -1)

    def remove(self):
        for hook in self.hooks: hook.remove()
        self.hooks.clear()


def run(plan, rows, compact, output):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from transformers import Qwen3ForCausalLM
    if (plan['format'] != FORMAT or plan['owner_decision'] != 'Decision 0054' or
            plan['maximum_generations'] != 0 or plan['maximum_optimizer_steps'] != 0 or
            plan['maximum_teacher_calls'] != 0 or plan['maximum_paid_usd'] != 0 or
            plan['forward_schedule'] != schedule(rows) or len(rows) != 8 or
            digest_value(rows) != plan['data_digest'] or plan['retained_decoder_layers'] != [0] or
            torch.__version__ != '2.10.0+cu128'):
        raise ValidationError('exact bounded one-layer operator diagnostic required')
    started = time.monotonic(); device = torch.device('cuda:0')
    def retain(name, value):
        (output / name).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    vectors = {}
    def binary(name, value):
        tensor = value.detach().float().cpu().contiguous()
        if not torch.isfinite(tensor).all(): raise ValidationError('nonfinite first-layer diagnostic vector')
        path = name + '.f32le'
        (output / path).write_bytes(tensor.numpy().astype('<f4', copy=False).tobytes())
        vectors[name] = {'path': path, 'shape': list(tensor.shape), 'dtype': 'float32-le'}
        retain('vectors.json', vectors)
        return tensor
    budget = OperatorBudget(rows, plan, retain)
    original = torch.nn.Module._call_impl
    def guarded(module, *args, **kwargs): return budget.guard_call(module, args, kwargs, original)
    torch.nn.Module._call_impl = guarded
    capture = None
    try:
        register_torch_varlen(); register_torch_varlen_gqa()
        model = Qwen3ForCausalLM.from_pretrained(compact, local_files_only=True,
            dtype=torch.bfloat16, attn_implementation='sdpa').to(device).eval()
        if len(model.model.layers) != 36 or model.config.hidden_size != 2560 or not model.config.tie_word_embeddings:
            raise ValidationError('exact original compact base architecture required')
        loaded_config = model.config.to_dict()
        retain('original-loaded-config.json', loaded_config)
        # This is explicitly a one-layer diagnostic model, never a 4B solver.
        del model.model.layers[1:]
        model.config.num_hidden_layers = 1
        model.config.layer_types = model.config.layer_types[:1]
        gc.collect(); torch.cuda.empty_cache()
        retained = [{'name': name, 'shape': list(p.shape), 'dtype': str(p.dtype)} for name, p in model.named_parameters()]
        if ({row['name']: row['shape'] for row in retained} != parameter_layout(loaded_config) or
                any(row['dtype'] != 'torch.bfloat16' for row in retained)):
            raise ValidationError('exact original first-layer parameter subset differs')
        retain('retained-model-subset.json', {'original_decoder_layers': 36, 'retained_decoder_layers': [0],
            'parameters': retained, 'whole_model': False, 'weights_modified': False})
        capture = OperatorCapture(model)
        layout, ordered = ordered_rows(rows)
        offsets = [0]
        for row in ordered: offsets.append(offsets[-1] + len(row['input_ids']))
        samples = [[0, len(row['input_ids']) // 2, len(row['input_ids']) - 1] for row in ordered]
        retain('capture-policy.json', {'operators': list(OPERATORS), 'local_positions': samples,
            'offsets': offsets, 'whole_model_qualification': False, 'additional_forwards_from_hooks': 0})
        modes = {}; settings = {}; times = []
        with torch.inference_mode():
            for mode in MODES:
                model.config._attn_implementation = ('sdpa' if mode.startswith('independent') else
                    TORCH_VARLEN_GQA if 'native-gqa' in mode else TORCH_VARLEN)
                capture.values.clear(); logits_list = []; operators = {name: [] for name in OPERATORS}
                torch.cuda.synchronize(); before = time.monotonic()
                with precision_mode(model, torch, mode) as setting:
                    settings[mode] = {**setting, 'attention': model.config._attn_implementation}
                    retain('compute-settings.json', settings)
                    if mode.startswith('independent'):
                        for index, row in enumerate(ordered):
                            capture.positions = samples[index]
                            with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
                                result = budget.perform(mode, lambda: model(
                                    input_ids=torch.tensor([row['input_ids']], device=device), use_cache=False))
                            logits_list.append(result.logits.cpu())
                            for name in OPERATORS: operators[name].append(capture.values[name])
                            del result
                    else:
                        capture.positions = [offsets[i] + p for i, ps in enumerate(samples) for p in ps]
                        backend = 'torch-varlen-flash-gqa' if 'native-gqa' in mode else 'torch-varlen-flash'
                        result = budget.perform(mode, lambda: packed_forward(model, layout, backend=backend))
                        logits_list.append(result['logits'].cpu())
                        for name in OPERATORS: operators[name].extend(capture.values[name].reshape(8, 3, -1).unbind(0))
                        del result
                torch.cuda.synchronize(); times.append({'mode': mode, 'seconds': time.monotonic() - before})
                modes[mode] = {'logits': binary(mode + '-logits', torch.cat(logits_list, dim=1))}
                for name in OPERATORS:
                    modes[mode][name] = binary(mode + '-' + name, torch.stack(operators[name]))
        comparisons = {}
        for mode in MODES[2:]:
            reference = 'independent-fp32-linear' if 'fp32-linear' in mode else 'independent-flash-sdpa'
            comparisons[mode] = {name: {'max_absolute_error': float((value - modes[reference][name]).abs().max()),
                'bitwise_equal': torch.equal(value, modes[reference][name])} for name, value in modes[mode].items()}
        retain('operator-comparisons.json', comparisons)
        result = {'format': FORMAT, 'run_id': plan['run_id'], 'plan_digest': digest_value(plan), 'outcome': 'complete',
            'partial_model': True, 'decoder_layers_executed': 1, 'actual_outer_forwards': len(budget.events),
            'actual_input_tokens': sum(row['input_tokens'] for row in budget.events), 'maximum_input_tokens': plan['maximum_input_tokens'],
            'optimizer_steps': 0, 'backwards': 0, 'generation_calls': 0, 'teacher_calls': 0,
            'whole_model_numerical_gate_passed': False, 'full_sft_completed': False, 'correctness_scored': False,
            'contains_evaluator_truth': False, 'timings': times, 'worker_wall_seconds': time.monotonic() - started}
        retain('worker-result.json', result)
        return result
    finally:
        if capture is not None: capture.remove()
        torch.nn.Module._call_impl = original


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('plan', 'samples', 'compact', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    run(json.loads(args.plan.read_bytes()), json.loads(args.samples.read_bytes()), args.compact, args.output)
