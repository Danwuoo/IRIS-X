from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib, importlib.util, json, math
import torch
from . import ROOT
from tools.arc_learning_agent_20261011.training import _fingerprint_tree

def need(ok, message):
    if not ok:
        raise ValueError(message)

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(x): return hashlib.sha256(canonical(x)).hexdigest()
def file_sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tree_sha(x): return _fingerprint_tree(x, torch)

def clone(x):
    if torch.is_tensor(x): return x.detach().cpu().clone()
    if isinstance(x, dict): return {k: clone(v) for k,v in x.items()}
    if isinstance(x, tuple): return tuple(clone(v) for v in x)
    if isinstance(x, list): return [clone(v) for v in x]
    return deepcopy(x)

def finite(x):
    if torch.is_tensor(x): return bool(torch.isfinite(x).all())
    if isinstance(x, dict): return all(finite(v) for v in x.values())
    if isinstance(x, (list,tuple)): return all(finite(v) for v in x)
    return not isinstance(x,float) or math.isfinite(x)

MATH_SHA='3de11b818eccb6a6bd8896245005a010abc3d930f04982490cfba79e0306b65a'
need(file_sha(ROOT/'reviewed/rl_math.py') == MATH_SHA, 'reviewed math changed')
spec=importlib.util.spec_from_file_location('rl_session_reviewed_math', ROOT/'reviewed/rl_math.py')
rl_math=importlib.util.module_from_spec(spec); spec.loader.exec_module(rl_math)

def source_identity():
    from owned_runtime.release import SOURCE_DIRECTORIES, NONEXECUTABLE
    paths=sorted({p for name in SOURCE_DIRECTORIES for p in (ROOT/name).rglob('*.py') if '__pycache__' not in p.parts})
    paths += [ROOT/name for name in NONEXECUTABLE]
    return {p.relative_to(ROOT).as_posix():file_sha(p) for p in paths}


def tensor_signature(parameters):
    # Owned optimizer/copy_ writes only; untracked .data or concurrent mutation
    # are prohibited. The frozen 29GB base is NEVER copied/hashed here.
    return tuple((n,id(p),p.data_ptr(),p._version,tuple(p.shape),str(p.dtype),str(p.device),p.requires_grad)
                 for n,p in parameters)
