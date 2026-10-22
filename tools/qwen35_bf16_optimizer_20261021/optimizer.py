"""Optax AdamW plus explicit BF16 stochastic final writes, without an FP32 master.

Moments retain Optax's documented dtypes. The update arithmetic below is FP32
only for each leaf candidate; an XLA memory report is required before full-model
use. Keys bind a stable tree path, optimizer step and fixed seed. Random arrays
have GLOBAL leaf shapes, never a local shard shape. Threefry partitioning and
layout replay must be verified on the selected accelerator before promotion.
"""
from __future__ import annotations
import hashlib
import json
from importlib.metadata import version
import jax
import jax.numpy as jnp
from flax import nnx

POLICY = 'bf16-final-write-threefry-sr-v1'
MAX_BF16 = 3.3895313892515355e38


def _path(path):
    parts = []
    for entry in path:
        if isinstance(entry, jax.tree_util.DictKey):
            key = entry.key
            if type(key) not in (str, int):
                raise TypeError('Only string/integer parameter dictionary keys are supported')
            parts.append(['dict', type(key).__name__, key])
        elif isinstance(entry, jax.tree_util.SequenceKey):
            parts.append(['seq', entry.idx])
        elif isinstance(entry, jax.tree_util.GetAttrKey):
            parts.append(['attr', entry.name])
        else:
            raise TypeError(f'Unsupported tree path component {type(entry).__name__}')
    return json.dumps(parts, ensure_ascii=True, separators=(',', ':'))


def policy_binding(seed):
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('Seed must be uint32')
    return {'policy': POLICY, 'seed': seed, 'rng': 'threefry2x32',
            'jax': version('jax'), 'flax': version('flax'), 'optax': version('optax'),
            'shape_semantics': 'global-leaf-shape',
            'path_semantics': 'typed-json-tree-path-sha256-128',
            'resume_requires_same_global_shapes_and_paths': True}


def validate_policy_binding(saved, seed):
    if saved != policy_binding(seed):
        raise ValueError('Checkpoint SR policy/seed/software binding differs')


def _key(seed, step, path):
    digest = hashlib.sha256(_path(path).encode()).digest()
    key = jax.random.key(seed, impl='threefry2x32')
    key = jax.random.fold_in(key, jnp.asarray(step, dtype=jnp.uint32))
    for offset in (0, 4, 8, 12):
        key = jax.random.fold_in(key, int.from_bytes(digest[offset:offset+4], 'little'))
    return key


def round_bf16(candidate, random_u32):
    """Discrete stochastic rounding of a finite FP32 candidate to BF16.

    Exact representable values survive unchanged. For a negative candidate,
    incrementing its magnitude bits chooses the numerically lower neighbour.
    Caller rejects nonfinite/overflow before committing the complete update.
    """
    if candidate.dtype != jnp.float32 or random_u32.dtype != jnp.uint32:
        raise TypeError('Expected FP32 candidates and uint32 random bits')
    if candidate.shape != random_u32.shape:
        raise ValueError('Random and candidate global shapes must match')
    bits = jax.lax.bitcast_convert_type(candidate, jnp.uint32)
    upper = (bits >> jnp.uint32(16)).astype(jnp.uint16)
    increment = ((random_u32 & jnp.uint32(0xffff)) < (bits & jnp.uint32(0xffff))).astype(jnp.uint16)
    return jax.lax.bitcast_convert_type(upper + increment, jnp.bfloat16)


def stochastic_apply_updates(params, updates, *, seed, step):
    """Return candidate tree and joint validity; never mutates input state."""
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('Seed must be an explicit uint32 integer')
    if jax.tree.structure(params) != jax.tree.structure(updates):
        raise ValueError('Parameter/update trees differ')
    leaves = jax.tree_util.tree_flatten_with_path(params)[0]
    names = [_path(path) for path, _ in leaves]
    if len(set(names)) != len(names):
        raise ValueError('Parameter path identities collide')
    valid = jnp.asarray(True)
    candidates = []
    update_leaves = jax.tree.leaves(updates)
    for (path, param), update in zip(leaves, update_leaves, strict=True):
        if param.dtype not in (jnp.bfloat16, jnp.float32):
            raise TypeError('Only BF16 bulk / explicitly retained FP32 source leaves supported')
        if param.shape != update.shape:
            raise ValueError('Parameter/update global shapes differ')
        candidate = param.astype(jnp.float32) + update.astype(jnp.float32)
        leaf_valid = jnp.all(jnp.isfinite(param)) & jnp.all(jnp.isfinite(update)) & jnp.all(jnp.isfinite(candidate))
        if param.dtype == jnp.bfloat16:
            leaf_valid &= jnp.all(jnp.abs(candidate) <= MAX_BF16)
            random = jax.random.bits(_key(seed, step, path), candidate.shape, dtype=jnp.uint32)
            candidate = round_bf16(candidate, random)
        valid &= leaf_valid
        candidates.append(candidate)
    return jax.tree.unflatten(jax.tree.structure(params), candidates), valid


def _all_finite(tree):
    tests = [jnp.all(jnp.isfinite(x)) for x in jax.tree.leaves(tree)
             if hasattr(x, 'dtype') and jnp.issubdtype(x.dtype, jnp.inexact)]
    return jnp.all(jnp.stack(tests)) if tests else jnp.asarray(True)


def _choose(valid, new, old):
    return jax.tree.map(lambda n, o: jnp.where(valid, n, o), new, old)


class BF16StochasticOptimizer(nnx.Optimizer):
    """Pinned Flax 0.12.10 adapter. Exact Optax state layout is retained.

    The caller MUST consume returned ``accepted`` and stop on rejection; no
    repeated silent skipped steps. Invalid gradients/candidates never alter
    params, moments or step. Seed/policy are immutable resolved-run metadata,
    and step is the existing checkpointed NNX optimizer counter.
    """
    def __init__(self, model, tx, *, seed, wrt=nnx.Param, graph=None):
        if type(seed) is not int or not 0 <= seed <= 0xffffffff:
            raise ValueError('Seed must be uint32')
        super().__init__(model, tx, wrt=wrt, graph=graph)
        self.sr_seed = seed
        self.sr_policy = POLICY

    def update(self, model, grads, /, **kwargs):
        params = nnx.as_pure(nnx.state(model, self.wrt, graph=self.graph))
        grad_arrays = nnx.as_pure(nnx.state(grads, self.wrt, graph=self.graph))
        old_state = nnx.as_pure(self.opt_state)
        updates, new_state = self.tx.update(grad_arrays, old_state, params, **nnx.as_pure(kwargs))
        candidates, valid = stochastic_apply_updates(params, updates, seed=self.sr_seed, step=self.step[...])
        valid &= _all_finite(grad_arrays) & _all_finite(new_state)
        valid &= self.step[...] != jnp.uint32(0xffffffff)
        committed = _choose(valid, candidates, params)
        state = _choose(valid, new_state, old_state)
        nnx.update(model, committed)
        nnx.update(self.opt_state, nnx.state(state, graph=self.graph))
        self.step[...] += valid.astype(jnp.uint32)
        return {'accepted': valid, 'step': self.step[...],
                'parameter_leaves': jnp.int32(len(jax.tree.leaves(params)))}
