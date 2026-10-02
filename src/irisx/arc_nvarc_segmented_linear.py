"""Preserve independent GEMM shapes while attention remains physically packed."""
from contextlib import contextmanager
from types import MethodType

from .errors import ValidationError


@contextmanager
def segmented_linear(model, offsets, *, maximum_invocations_per_module=None):
    """Keep this scope open through backward/checkpoint recomputation.

    Each original Linear receives one whole sample at a time, using its
    unchanged weight, bias and dtype. There is no weight cast or extra outer
    model call. Attention, positions and packing masks stay with the caller.
    """
    import torch
    offsets=tuple(offsets)
    if (len(offsets)<2 or len(offsets)>9 or offsets[0]!=0 or
            any(type(value) is not int for value in offsets) or
            any(a>=b for a,b in zip(offsets,offsets[1:]))):
        raise ValidationError('one to eight closed whole-sample linear offsets required')
    if maximum_invocations_per_module is not None and (type(maximum_invocations_per_module) is not int or
            maximum_invocations_per_module<1):raise ValidationError('positive finite per-module invocation ceiling required')
    modules=[(name,module) for name,module in model.named_modules() if isinstance(module,torch.nn.Linear)]
    if not modules or any(type(module) is not torch.nn.Linear for _,module in modules):
        raise ValidationError('unmodified native torch Linear modules required')
    state={'offsets':list(offsets),'module_names':[name for name,_ in modules],
        'linear_calls_by_name':{name:0 for name,_ in modules},'segment_gemm_calls':0,
        'weight_or_dtype_casts':0,'weights_modified':False,
        'maximum_invocations_per_module':maximum_invocations_per_module,
        'weight_dtypes':{name:str(module.weight.dtype) for name,module in modules}}
    saved=[]
    try:
        for name,module in modules:
            if 'forward' in module.__dict__:
                raise ValidationError('nested/custom instance Linear override is not supported')
            saved.append(module)
            def forward(self, value, *, _name=name):
                if (value.ndim!=3 or value.shape[0]!=1 or value.shape[1]!=offsets[-1] or
                        value.shape[-1]!=self.in_features or value.dtype!=self.weight.dtype):
                    raise ValidationError('exact complete [1, packed tokens, features] linear input required')
                if maximum_invocations_per_module is not None and state['linear_calls_by_name'][_name]>=maximum_invocations_per_module:
                    raise ValidationError('per-module segmented GEMM ceiling reached')
                state['linear_calls_by_name'][_name]+=1
                state['segment_gemm_calls']+=len(offsets)-1
                return torch.cat([torch.nn.functional.linear(value[:,a:b,:],self.weight,self.bias)
                    for a,b in zip(offsets,offsets[1:])],dim=1)
            module.forward=MethodType(forward,module)
        yield state
    finally:
        for module in saved:del module.forward
