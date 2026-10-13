"""Bounded, atomic, pickle-free Qwen branch checkpoints.

Inference adapter shards are reusable independently of resume/state.json. Resume
references those same adapter bytes, so optimizer state does not duplicate them.
The external tokenizer/base are exact hash-bound references, never copied here.
PEFT 0.21 has no sharded adapter loader: use load_inference_adapter explicitly.
Physical accounting belongs to the live wrappers and is never deserialized.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import uuid

from tools.arc_learning_agent_20261011.training import _fingerprint_tree
from tools.arc_next_models import canonical, digest, require
from tools.arc_next_training import _state_fingerprint

FORMAT = 'irisx/qwen-branch-safe-checkpoint-v1'


@dataclass(frozen=True)
class CheckpointLimits:
    shard_bytes: int = 32 * 1024**2
    checkpoint_bytes: int = 768 * 1024**2
    store_bytes: int = 2 * 1024**3
    json_bytes: int = 8 * 1024**2
    files: int = 128
    tensors: int = 10000
    branches: int = 2
    versions_per_branch: int = 3
    reserve_bytes: int = 4 * 1024**3

    def __post_init__(self):
        require(all(type(x) is int and x > 0 for x in self.__dict__.values()), 'positive checkpoint limits required')
        require(self.shard_bytes <= 32 * 1024**2 and self.store_bytes <= 2 * 1024**3,
                'checkpoint hard byte limits cannot be raised')
        require(self.json_bytes <= 32 * 1024**2 and self.checkpoint_bytes <= self.store_bytes,
                'checkpoint metadata/total limits differ')


def _raw(trainer):
    return getattr(trainer, 'trainer', trainer)


def _physical(trainer):
    ledger = getattr(trainer, 'ledger', None)
    return None if ledger is None else deepcopy(ledger.summary())


def _safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'checkpoint symlink path forbidden')
    return path


def _relative(name):
    require(type(name) is str and '\\' not in name and name and
            not PurePosixPath(name).is_absolute() and
            all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe checkpoint relative path')
    return name


def _sha(path):
    h = hashlib.sha256()
    with _safe_path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def _json(path, cap):
    path = _safe_path(path)
    require(path.is_file() and 0 < path.stat().st_size <= cap, 'bounded checkpoint JSON required')
    def pairs(items):
        value = {}
        for k, v in items:
            require(k not in value, 'duplicate checkpoint JSON key')
            value[k] = v
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'nonfinite checkpoint JSON'))


def _write_json(path, value, cap):
    data = canonical(value) + b'\n'
    require(len(data) <= cap, 'checkpoint JSON exceeds cap')
    with _safe_path(path).open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _inventory(root, *, max_files, max_bytes):
    root = _safe_path(root)
    result = {}; total = 0
    for path in sorted(root.rglob('*')):
        _safe_path(path)
        require(path.is_file() or path.is_dir(), 'nonregular checkpoint object forbidden')
        if path.is_file():
            require(path.stat().st_nlink == 1, 'checkpoint hard links forbidden')
            name = _relative(path.relative_to(root).as_posix())
            size = path.stat().st_size; total += size
            require(len(result) < max_files and total <= max_bytes, 'checkpoint file/byte cap exceeded')
            result[name] = {'bytes': size, 'sha256': _sha(path)}
    return result, total


def _binding(trainer, branch_id, records, provenance, checkpoint_schedule=None):
    require(checkpoint_schedule is not None or not getattr(trainer, '_checkpoint_schedule_required', False),
            'TransferTrainer requires an explicit source-bound checkpoint schedule')
    trainer._assert_adapter_recipe()
    trainer.native._assert_tokenizer_backend()
    trainer.native.prompt_contract._assert_tokenizer_unchanged()
    require(trainer._model_identity() == trainer._base_identity, 'live model/tokenizer/runtime identity changed')
    require(type(branch_id) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', branch_id), 'bounded branch identity required')
    require(type(records) is list and records, 'exact nonempty branch records required')
    require(type(provenance) is dict, 'checkpoint provenance object required')
    source = deepcopy(trainer._source_identity())
    source['tools/arc_qwen_portfolio_20261012/checkpoints.py'] = _sha(Path(__file__))
    schedule = {}
    if checkpoint_schedule is not None:
        from tools.arc_qwen_transfer_20261012.checkpoint_policy import bind
        schedule['checkpoint_schedule'] = bind(trainer, checkpoint_schedule, branch_id)
    return json.loads(canonical({**schedule, 'branch_id': branch_id, 'model': deepcopy(trainer._base_identity),
            'config': deepcopy(trainer.config), 'source': source,
            'records_sha256': digest(records), 'records_count': len(records),
            'record_ids': [r['record_id'] for r in records],
            'parameter_names': list(trainer.parameters),
            'expanded_target_inventory': deepcopy(trainer._adapter_recipe_identity),
            'provenance': deepcopy(provenance), 'precision': 'bf16-base-fp32-lora',
            'rank': 8, 'alpha': 16, 'physical_ledger_included': False}))


def _check_update(update, binding, trainer=None):
    schedule = binding.get('checkpoint_schedule')
    require(schedule is not None or binding.get('model', {}).get('native_identity', {}).get('profile_id') !=
            'qwen3-14b-native-bf16-r8-c4096-transfer-v1',
            'stored TransferTrainer identity requires an explicit checkpoint schedule')
    if schedule is not None:
        require(type(update) is int, 'integer transfer checkpoint update required')
        from tools.arc_qwen_transfer_20261012.checkpoint_policy import validate_contract
        validate_contract(schedule, binding['branch_id'], update)
        require(not schedule['fixture_only'] or binding.get('config', {}).get('tiny_cpu') is True,
                'fixture checkpoint binding must be tiny CPU')
        if trainer is not None:
            require(schedule['scope'] == ('task' if trainer._task_id is not None else 'global'),
                    'checkpoint schedule/training scope differs')
    else:
        require(type(update) is int and 0 <= update <= 16, 'bounded checkpoint update required')
        if trainer is not None:
            require(trainer.config['tiny_cpu'] or update in (0, 8, 16), 'production checkpoints are base/8/16')


def _tensor_hash(tensor):
    import torch
    value = tensor.detach().cpu().contiguous()
    return digest([str(value.dtype), list(value.shape),
                   hashlib.sha256(value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()])


def _write_shards(tensors, directory, prefix, limits):
    from safetensors.torch import save_file
    directory.mkdir()
    groups = []; group = {}; total = 0
    # Leave room for safetensors' bounded per-tensor headers.
    payload_cap = limits.shard_bytes - min(1024**2, limits.shard_bytes // 8)
    for key, value in sorted(tensors.items()):
        size = value.numel() * value.element_size()
        require(size <= payload_cap, 'single tensor exceeds shard cap')
        if group and total + size > payload_cap:
            groups.append(group); group = {}; total = 0
        group[key] = value.detach().cpu().contiguous().clone(); total += size
    if group:
        groups.append(group)
    index = {}
    for i, group in enumerate(groups):
        name = '%s-%05d-of-%05d.safetensors' % (prefix, i + 1, len(groups))
        path = directory / name
        save_file(group, str(path), metadata={'format': FORMAT})
        require(path.stat().st_size <= limits.shard_bytes, 'serialized shard exceeds cap')
        with path.open('rb') as f:
            os.fsync(f.fileno())
        index.update({key: name for key in group})
    return index


def _encode_tree(value, torch, tensors, tensor_aliases, limits):
    """Tagged JSON preserves integer optimizer keys and Python RNG tuples."""
    def encode(item, depth=0):
        require(depth <= 64, 'checkpoint tree nesting cap exceeded')
        if isinstance(item, torch.Tensor):
            key = tensor_aliases.get(_tensor_hash(item))
            if key is None:
                require(len(tensors) < limits.tensors, 'checkpoint tensor cap exceeded')
                key = 'resume/t%05d' % len(tensors)
                tensors[key] = item.detach().cpu().contiguous().clone()
                tensor_aliases[_tensor_hash(item)] = key
            return {'t': key}
        if type(item) in (dict, list, tuple):
            if type(item) is dict:
                require(all(type(k) in (str, int) for k in item), 'unsupported checkpoint mapping key')
                return {'d': [[encode(k, depth+1), encode(v, depth+1)] for k, v in item.items()]}
            return {'q' if type(item) is tuple else 'l': [encode(v, depth+1) for v in item]}
        require(item is None or type(item) in (str, bool, int, float), 'unsafe checkpoint tree object')
        require(type(item) is not float or math.isfinite(item), 'nonfinite checkpoint scalar')
        return {'v': item}
    return encode(value)


def _decode_tree(value, tensors):
    count = [0]
    def decode(node, depth=0):
        count[0] += 1
        require(depth <= 64 and count[0] <= 2000000 and type(node) is dict and len(node) == 1,
                'invalid/beyond-limit checkpoint tree')
        tag, item = next(iter(node.items()))
        if tag == 't':
            require(type(item) is str and item in tensors, 'unknown checkpoint tensor reference')
            return tensors[item].clone()
        if tag == 'v':
            require(item is None or type(item) in (str, bool, int, float), 'invalid checkpoint scalar')
            require(type(item) is not float or math.isfinite(item), 'nonfinite checkpoint scalar')
            return item
        require(tag in ('d', 'l', 'q') and type(item) is list, 'invalid checkpoint tree tag')
        if tag == 'd':
            result = {}
            for pair in item:
                require(type(pair) is list and len(pair) == 2, 'invalid checkpoint mapping pair')
                key = decode(pair[0], depth+1)
                require(type(key) in (str, int) and key not in result, 'duplicate/invalid checkpoint mapping key')
                result[key] = decode(pair[1], depth+1)
            return result
        result = [decode(v, depth+1) for v in item]
        return tuple(result) if tag == 'q' else result
    return decode(value)


def _validate_rng(rng, torch):
    import random
    import numpy as np
    require(type(rng) is dict and set(rng) == {'python','numpy','torch','cuda'}, 'RNG state inventory differs')
    random.Random().setstate(rng['python'])
    n=rng['numpy']
    require(type(n) is dict and set(n)=={'name','keys','position','has_gauss','cached_gaussian'} and
            type(n['keys']) is list and len(n['keys'])==624 and
            all(type(x) is int and 0 <= x < 2**32 for x in n['keys']), 'NumPy RNG state differs')
    np.random.RandomState().set_state((n['name'],np.array(n['keys'],dtype=np.uint32),n['position'],n['has_gauss'],n['cached_gaussian']))
    require(isinstance(rng['torch'],torch.Tensor) and rng['torch'].dtype==torch.uint8 and
            rng['torch'].shape==torch.get_rng_state().shape, 'Torch RNG dtype/shape differs')
    torch.Generator(device='cpu').set_state(rng['torch'])
    require(type(rng['cuda']) is list, 'CUDA RNG list required')
    if rng['cuda']:
        require(torch.cuda.is_available() and len(rng['cuda'])==torch.cuda.device_count(), 'CUDA RNG device count differs')
        for i,value in enumerate(rng['cuda']):
            require(value.dtype==torch.uint8 and value.shape==torch.cuda.get_rng_state(i).shape, 'CUDA RNG shape differs')


def _validate_optimizer(trainer, payload, update):
    optimizer=payload['optimizer']; scheduler=payload['scheduler']; c=trainer.config; torch=trainer.torch
    if optimizer is None: return
    require(type(optimizer) is dict and set(optimizer)=={'state','param_groups'} and
            type(optimizer['state']) is dict and type(optimizer['param_groups']) is list and
            len(optimizer['param_groups'])==1, 'AdamW state schema differs')
    task=payload['task_id'] is not None; lr=c['task_learning_rate'] if task else c['learning_rate']
    fresh=torch.optim.AdamW(list(trainer.parameters.values()),lr=lr,betas=tuple(c['betas']),eps=c['eps'],
                           weight_decay=c['weight_decay'],foreach=False)
    if task:
        warmup,total=(c['task_warmup_steps'],c['task_schedule_steps']) if c['stability_mode'] else (0,0)
    else: warmup,total=c['warmup_steps'],c['schedule_steps']
    def schedule(step):
        if total==0: return 1.0
        if warmup and step<warmup: return (step+1)/warmup
        progress=min(1.,max(0.,(step-warmup)/max(1,total-warmup)))
        return c['min_lr_ratio']+(1-c['min_lr_ratio'])*.5*(1+math.cos(math.pi*progress))
    fresh_scheduler=torch.optim.lr_scheduler.LambdaLR(fresh,schedule)
    expected=fresh.state_dict()['param_groups'][0]; group=optimizer['param_groups'][0]
    require(type(group) is dict and set(group)==set(expected), 'AdamW group fields differ')
    require({k:v for k,v in group.items() if k!='lr'} == {k:v for k,v in expected.items() if k!='lr'} and
            group['lr']==lr*schedule(update), 'AdamW parameter/config/scheduled LR differs')
    require(set(optimizer['state']) == (set(range(len(trainer.parameters))) if update else set()),
            'AdamW per-parameter inventory differs')
    for index,p in enumerate(trainer.parameters.values()):
        if not update: break
        value=optimizer['state'][index]
        require(type(value) is dict and set(value)=={'step','exp_avg','exp_avg_sq'}, 'AdamW tensor fields differ')
        step=value['step']
        require(isinstance(step,torch.Tensor) and step.dtype==torch.float32 and step.shape==torch.Size([]) and
                float(step)==update, 'AdamW step counter differs')
        for field in ('exp_avg','exp_avg_sq'):
            tensor=value[field]
            require(isinstance(tensor,torch.Tensor) and tensor.dtype==p.dtype and tensor.shape==p.shape and
                    bool(torch.isfinite(tensor).all()), 'AdamW moment dtype/shape/finite check failed')
        require(bool((value['exp_avg_sq']>=0).all()), 'AdamW squared moment negative')
    expected_scheduler=fresh_scheduler.state_dict()
    require(type(scheduler) is dict and set(scheduler)==set(expected_scheduler), 'scheduler state fields differ')
    for key,value in expected_scheduler.items():
        if key not in ('last_epoch','_step_count','_last_lr'):
            require(scheduler[key]==value, 'scheduler configuration differs: '+key)
    require(scheduler['last_epoch']==update and scheduler['_step_count']==update+1 and
            scheduler['_last_lr']==[group['lr']], 'scheduler counters/LR differ')
    # Isolated state_dict loaders validate framework version-specific structure
    # without modifying the model's actual optimizer or scheduler bindings.
    fresh.load_state_dict(optimizer); fresh_scheduler.load_state_dict(scheduler)


def _check_payload(trainer, payload, handle, binding, update, records):
    _check_update(update, binding)
    torch = trainer.torch
    expected_fields = {'adapter','optimizer','scheduler','scaler','rng','run_state','schedule_records',
                       'effective_cycle','optimizer_serial','task_id','task_seed','task_records_digest',
                       'caller_rng','global_snapshot','global_snapshot_value','last_task_reset_receipt','model_training'}
    require(type(payload) is dict and set(payload) == expected_fields, 'resume state fields differ')
    if binding.get('checkpoint_schedule') is not None:
        require(binding['checkpoint_schedule']['scope'] == ('task' if payload['task_id'] is not None else 'global'),
                'checkpoint schedule/resume task scope differs')
    require(handle['state_sha256'] == _fingerprint_tree(payload, torch), 'complete resume state hash differs')
    require(handle['identity_sha256'] == digest({'model': trainer._base_identity, 'config': trainer.config,
                                                 'source': trainer._source_identity()}), 'snapshot identity differs')
    require(set(payload['adapter']) == set(trainer.parameters), 'resume adapter inventory differs')
    for name, value in payload['adapter'].items():
        p = trainer.parameters[name]
        require(value.dtype == p.dtype and value.shape == p.shape and bool(torch.isfinite(value).all()),
                'resume adapter dtype/shape/finite check failed')
    require(_state_fingerprint(payload['adapter'], torch) == handle['fingerprint'], 'resume adapter hash differs')
    require((payload['optimizer'] is None) == (payload['scheduler'] is None), 'incomplete optimizer/scheduler pair')
    require((getattr(trainer, 'scaler', None) is None) == (payload['scaler'] is None), 'resume scaler differs')
    require(type(payload['model_training']) is bool and type(payload['optimizer_serial']) is int and
            payload['optimizer_serial'] >= 0, 'resume mode/counters differ')
    _validate_rng(payload['rng'],torch)
    if payload['caller_rng'] is not None: _validate_rng(payload['caller_rng'],torch)
    if payload['scaler'] is not None: deepcopy(trainer.scaler).load_state_dict(payload['scaler'])
    _validate_optimizer(trainer,payload,update)
    global_handle,global_value=payload['global_snapshot'],payload['global_snapshot_value']
    require((global_handle is None)==(global_value is None), 'global snapshot handle/value pair differs')
    if global_handle is not None:
        require(type(global_handle) is dict and set(global_handle)=={'snapshot_id','label','fingerprint','model_identity_sha256'} and
                type(global_handle['snapshot_id']) is str and re.fullmatch(r'[0-9a-f]{32}',global_handle['snapshot_id']),
                'global snapshot handle schema differs')
        require(type(global_value) is dict and set(global_value)=={'state','rng','fingerprint','label','model_identity_sha256'},
                'global snapshot value schema differs')
        require(global_value['model_identity_sha256']==global_handle['model_identity_sha256']==digest(trainer._base_identity) and
                global_value['label']==global_handle['label'] and
                global_value['fingerprint']==global_handle['fingerprint']==_state_fingerprint(global_value['state'],torch),
                'global snapshot state/identity differs')
        require(set(global_value['state'])==set(trainer.parameters), 'global snapshot adapter inventory differs')
        for name,value in global_value['state'].items():
            p=trainer.parameters[name]
            require(value.shape==p.shape and value.dtype==p.dtype and bool(torch.isfinite(value).all()),
                    'global snapshot adapter dtype/shape/finite check failed')
        _validate_rng(global_value['rng'],torch)
        if global_handle['snapshot_id'] in trainer._snapshots:
            require(_fingerprint_tree(trainer._snapshots[global_handle['snapshot_id']],torch)==_fingerprint_tree(global_value,torch),
                    'global snapshot would replace a different live snapshot')
    state = payload['run_state']
    if state is None:
        require(update == 0 and payload['optimizer'] is None, 'untrained checkpoint must be base state')
    else:
        require(type(state) is dict and state['steps'] == update and state['attempted_steps'] == state['microbatches']
                and not state['failed_update'], 'resume not a complete claimed update')
        require(state['identity']['data_sha256'] == digest(records) and
                state['identity']['model'] == trainer._base_identity and
                state['identity']['source'] == trainer._source_identity() and
                state['identity']['config_sha256'] == digest(trainer.config) and
                state['identity']['parameter_names'] == list(trainer.parameters) and
                state['identity']['effective_objective_cycle'] == payload['effective_cycle'], 'resume run identity differs')
        require(all(type(state[k]) is int and state[k] >= 0 for k in ('steps','microbatches','attempted_steps',
                'input_tokens','supervised_tokens','attempted_input_tokens','attempted_supervised_tokens','epoch','cursor')),
                'resume nonnegative integer counters required')
        from tools.arc_learning_agent_20261011.data import semantic_sample_id
        expected_schedule=[{**{k:r[k] for k in ('kind','family_id','record_id')},'semantic_id':semantic_sample_id(r)}
                           for r in records if r['split']=='train']
        require(payload['schedule_records']==expected_schedule, 'resume sampler record metadata differs')
        train_count = sum(r['split'] == 'train' for r in records)
        require(all(type(i) is int and 0 <= i < train_count for i in state['order']) and
                0 <= state['cursor'] <= len(state['order']), 'resume data cursor invalid')
        require(len(payload['schedule_records']) == train_count and payload['optimizer'] is not None,
                'resume sampler/optimizer missing')
        previous = (trainer._schedule_records, trainer._effective_cycle, trainer._task_id,
                    getattr(trainer, '_task_seed', None))
        try:
            trainer._schedule_records = payload['schedule_records']; trainer._effective_cycle = payload['effective_cycle']
            trainer._task_id = payload['task_id']; trainer._task_seed = payload['task_seed']
            require(state['order'] == trainer._order(train_count, state['epoch']), 'resume sampler order differs')
            require(state['identity'] == trainer._identity(records), 'exact resume training identity differs')
        finally:
            trainer._schedule_records, trainer._effective_cycle, trainer._task_id, trainer._task_seed = previous
    require(payload['task_id'] == (state['identity']['task_id'] if state else payload['task_id']), 'resume task identity differs')


def save_branch_checkpoint(trainer, root, *, branch_id, update, records, provenance=None,
                           limits=None, checkpoint_schedule=None):
    """Persist legacy base/8/16 or an explicit source-bound transfer schedule."""
    limits = limits or CheckpointLimits(); wrapper = trainer; trainer = _raw(trainer)
    require(trainer._complete_training_boundary(), 'checkpoint needs complete cleared-gradient boundary')
    physical = _physical(wrapper)
    require(physical is None or not physical['pending'], 'unresolved physical work prevents checkpoint')
    binding = _binding(trainer, branch_id, records, provenance or {}, checkpoint_schedule)
    _check_update(update, binding, trainer)
    root = _safe_path(root); root.mkdir(parents=True, exist_ok=True)
    lock = root / '.writer-lock'
    with lock.open('x') as f:
        f.write(uuid.uuid4().hex)
    staging = None; handle = None
    try:
        existing, current_bytes = _inventory(root, max_files=limits.files * limits.versions_per_branch * limits.branches + 8,
                                             max_bytes=limits.store_bytes)
        marker = root / 'store.json'
        if marker.exists():
            require(_json(marker, limits.json_bytes) == {'format': FORMAT, 'max_bytes': limits.store_bytes}, 'checkpoint store ownership differs')
        else:
            require(set(existing) == {'.writer-lock'}, 'unowned checkpoint store is not empty')
            _write_json(marker, {'format': FORMAT, 'max_bytes': limits.store_bytes}, limits.json_bytes)
        branches = [p for p in root.iterdir() if p.is_dir()]
        branch = root / branch_id
        require(branch.exists() or len(branches) < limits.branches, 'checkpoint branch cap exceeded')
        branch.mkdir(exist_ok=True)
        owner = branch / 'branch.json'
        if owner.exists():
            require(_json(owner, limits.json_bytes) == binding, 'checkpoint branch ownership/records identity differs')
        else:
            require(not list(branch.iterdir()), 'unowned branch is not empty')
            _write_json(owner, binding, limits.json_bytes)
        versions = [p for p in branch.iterdir() if p.is_dir()]
        require(len(versions) < limits.versions_per_branch, 'checkpoint retention cap reached; no implicit deletion')
        target = branch / ('update-%08d' % update)
        require(not target.exists(), 'immutable checkpoint update already exists')
        handle = trainer.snapshot_training_state('disk-' + branch_id + '-' + str(update))
        payload = trainer._training_snapshots[handle['snapshot_id']]['payload']
        _check_payload(trainer, payload, handle, binding, update, records)
        from peft import get_peft_model_state_dict
        inference = get_peft_model_state_dict(trainer.model)
        aliases = {}; adapter_keys = {}
        for name, tensor in payload['adapter'].items():
            key = name.replace('.default.', '.')
            require(key in inference and _tensor_hash(inference[key]) == _tensor_hash(tensor), 'PEFT inference adapter mapping differs')
            adapter_keys[name] = key; aliases[_tensor_hash(tensor)] = 'inference/' + key
        require(set(adapter_keys.values()) == set(inference), 'unexpected inference adapter tensors')
        extra = {}; tree = _encode_tree(payload, trainer.torch, extra, aliases, limits)
        tensor_bytes = sum(t.numel()*t.element_size() for t in inference.values()) + sum(t.numel()*t.element_size() for t in extra.values())
        projected = tensor_bytes + 2 * limits.json_bytes + limits.shard_bytes // 8
        require(projected <= limits.checkpoint_bytes and current_bytes + projected <= limits.store_bytes,
                'projected checkpoint/store byte cap exceeded')
        reserve = max(limits.reserve_bytes, trainer.config['checkpoint_disk_reserve_bytes'])
        free = shutil.disk_usage(root).free
        require(free >= projected + reserve, 'insufficient checkpoint disk reserve')
        if not trainer.config['tiny_cpu']:
            require(free >= limits.store_bytes - current_bytes + reserve,
                    'insufficient free space for remaining bounded checkpoint store plus reserve')
        staging = Path(tempfile.mkdtemp(prefix='.pending-', dir=branch))
        inference_index = _write_shards(inference, staging/'inference', 'adapter', limits)
        resume_index = _write_shards(extra, staging/'resume', 'state', limits)
        from dataclasses import asdict
        def normalized(value):
            if type(value) is dict: return {k: normalized(v) for k,v in value.items()}
            if type(value) is set: return sorted(normalized(v) for v in value)
            if type(value) in (list,tuple): return [normalized(v) for v in value]
            return value
        config = normalized(asdict(trainer.model.peft_config['default']))
        _write_json(staging/'inference'/'adapter_config.json', config, limits.json_bytes)
        _write_json(staging/'inference'/'adapter_model.safetensors.index.json',
                    {'format': FORMAT, 'weight_map': inference_index, 'loader': 'load_inference_adapter',
                     **({'update': update} if checkpoint_schedule is not None else {}),
                     'resume_capable': False, 'binding': binding, 'binding_sha256': digest(binding),
                     'adapter_sha256': handle['fingerprint']['sha256'], 'adapter_keys': adapter_keys,
                     'files': _inventory(staging/'inference', max_files=limits.files, max_bytes=limits.checkpoint_bytes)[0],
                     'tokenizer_reference': binding['model'],
                     'expanded_target_inventory': binding['expanded_target_inventory']}, limits.json_bytes)
        _write_json(staging/'resume'/'state.json', {'format': FORMAT, 'handle': handle, 'tree': tree,
                    'weight_map': resume_index, 'adapter_keys': adapter_keys, 'gradients': 'all-cleared-none',
                    'physical_ledger_included': False}, limits.json_bytes)
        files, byte_count = _inventory(staging, max_files=limits.files, max_bytes=limits.checkpoint_bytes)
        manifest = {'format': FORMAT, 'binding': binding, 'binding_sha256': digest(binding),
                    'update': update, 'state_sha256': handle['state_sha256'],
                    'adapter_sha256': handle['fingerprint']['sha256'], 'files': files,
                    'tensor_bytes': tensor_bytes, 'payload_file_bytes': byte_count,
                    'resume_capable': True, 'physical_ledger_included': False,
                    'inference_loader': 'load_inference_adapter', 'fresh_backend_reload_verified': False}
        _write_json(staging/'manifest.json', manifest, limits.json_bytes)
        _, total = _inventory(staging, max_files=limits.files+1, max_bytes=limits.checkpoint_bytes)
        require(current_bytes + total <= limits.store_bytes, 'actual checkpoint store cap exceeded')
        for subdir in (staging/'inference', staging/'resume', staging): _sync_dir(subdir)
        os.rename(staging, target); staging = None
        _sync_dir(branch); _sync_dir(root)
        require(_physical(wrapper) == physical, 'checkpoint altered physical accounting')
        return {'path': str(target), 'manifest_sha256': _sha(target/'manifest.json'),
                'branch_id': branch_id, 'update': update, 'state_sha256': manifest['state_sha256'],
                'adapter_sha256': manifest['adapter_sha256'],
                'inference_path': str(target/'inference'),
                'inference_manifest_sha256': _sha(target/'inference'/'adapter_model.safetensors.index.json'),
                'bytes': total, 'tensor_bytes': tensor_bytes,
                'projected_bytes': projected, 'disk_free_before_bytes': free, 'reserve_bytes': reserve,
                'atomic': True, 'pickle_free': True, 'resume_capable': True,
                'physical_ledger_untouched': True, 'fresh_backend_reload_verified': False}
    finally:
        if handle is not None: trainer.release_training_state(handle)
        if staging is not None and staging.exists(): shutil.rmtree(staging)
        lock.unlink()


def inspect_checkpoint(checkpoint, *, expected_manifest_sha256=None, limits=None):
    limits = limits or CheckpointLimits(); root = _safe_path(checkpoint)
    manifest = _json(root/'manifest.json', limits.json_bytes)
    require(expected_manifest_sha256 is None or _sha(root/'manifest.json') == expected_manifest_sha256,
            'checkpoint manifest receipt hash differs')
    require(manifest.get('format') == FORMAT and manifest['binding_sha256'] == digest(manifest['binding']),
            'checkpoint manifest format/binding differs')
    _check_update(manifest['update'], manifest['binding'])
    files, total = _inventory(root, max_files=limits.files+1, max_bytes=limits.checkpoint_bytes)
    files.pop('manifest.json')
    require(files == manifest['files'] and sum(v['bytes'] for v in files.values()) == manifest['payload_file_bytes'],
            'checkpoint file inventory/hash differs')
    require(all(v['bytes'] <= (limits.shard_bytes if k.endswith('.safetensors') else limits.json_bytes)
                for k,v in files.items()), 'checkpoint individual file cap exceeded')
    allowed = {'manifest.json','inference/adapter_config.json','inference/adapter_model.safetensors.index.json','resume/state.json'}
    require(all(k in allowed or re.fullmatch(r'(inference/adapter|resume/state)-[0-9]{5}-of-[0-9]{5}\.safetensors', k)
                for k in files), 'unexpected checkpoint file type')
    return manifest


def _read_tensors(root, manifest, limits):
    from safetensors import safe_open
    tensors = {}
    for prefix, filename in (('inference','adapter_model.safetensors.index.json'), ('resume','state.json')):
        index = _json(root/prefix/filename, limits.json_bytes)['weight_map']
        require(type(index) is dict and len(index) <= limits.tensors, 'tensor index cap exceeded')
        expected_by_file = {}
        for key, name in index.items():
            require(type(key) is str and type(name) is str and Path(name).name == name and
                    prefix+'/'+name in manifest['files'], 'unsafe/missing shard reference')
            expected_by_file.setdefault(name, set()).add(key)
        shard_files = {Path(k).name for k in manifest['files'] if k.startswith(prefix+'/') and k.endswith('.safetensors')}
        require(set(expected_by_file) == shard_files, 'unindexed checkpoint shard')
        for name, expected in expected_by_file.items():
            with safe_open(str(_safe_path(root/prefix/name)), framework='pt', device='cpu') as f:
                require(set(f.keys()) == expected, 'checkpoint shard tensor inventory differs')
                for key in f.keys():
                    address = prefix+'/'+key if prefix == 'inference' else key
                    require(address not in tensors, 'duplicate tensor address')
                    tensors[address] = f.get_tensor(key)
                    require(len(tensors) <= limits.tensors, 'checkpoint tensor cap exceeded')
    return tensors


def load_branch_checkpoint(trainer, checkpoint, *, branch_id, records,
                           expected_manifest_sha256=None, provenance=None, limits=None, checkpoint_schedule=None):
    limits = limits or CheckpointLimits(); wrapper = trainer; trainer = _raw(trainer)
    physical = _physical(wrapper)
    require(physical is None or not physical['pending'], 'unresolved physical work prevents reload')
    require(trainer._complete_training_boundary(), 'reload requires cleared-gradient boundary')
    root = _safe_path(checkpoint)
    manifest = inspect_checkpoint(root, expected_manifest_sha256=expected_manifest_sha256, limits=limits)
    expected = _binding(trainer, branch_id, records,
                        manifest['binding']['provenance'] if provenance is None else provenance, checkpoint_schedule)
    require(expected == manifest['binding'], 'checkpoint branch/model/tokenizer/source/config/records identity differs')
    payload_json = _json(root/'resume'/'state.json', limits.json_bytes)
    require(payload_json['format'] == FORMAT and payload_json['physical_ledger_included'] is False and
            payload_json['gradients'] == 'all-cleared-none', 'resume boundary format differs')
    tensors = _read_tensors(root, manifest, limits)
    payload = _decode_tree(payload_json['tree'], tensors); handle = payload_json['handle']
    require(handle['state_sha256'] == manifest['state_sha256'] and
            handle['fingerprint']['sha256'] == manifest['adapter_sha256'], 'manifest resume state binding differs')
    _check_payload(trainer, payload, handle, expected, manifest['update'], records)
    bindings = {k: id(v) for k,v in trainer.parameters.items()}
    # Register only fully validated content into the existing complete restore
    # contract; disk input is never passed to torch.load or Python unpickling.
    rollback = trainer.snapshot_training_state('pre-disk-load-rollback')
    handle = deepcopy(handle); handle['snapshot_id'] = uuid.uuid4().hex
    trainer._training_snapshots[handle['snapshot_id']] = {'handle': deepcopy(handle), 'payload': payload}
    try:
        result = trainer.restore_training_state(handle)
        check = trainer.snapshot_training_state('disk-readback')
        try:
            require(check['state_sha256'] == manifest['state_sha256'], 'readback complete state differs')
        finally:
            trainer.release_training_state(check)
    except BaseException:
        trainer.restore_training_state(rollback)
        raise
    finally:
        trainer.release_training_state(handle)
        trainer.release_training_state(rollback)
    require(bindings == {k:id(v) for k,v in trainer.parameters.items()}, 'reload replaced live parameter bindings')
    require(_physical(wrapper) == physical, 'reload altered/refunded physical accounting')
    return {**result, 'loaded': True, 'branch_id': branch_id, 'update': manifest['update'],
            'manifest_sha256': _sha(root/'manifest.json'), 'same_parameter_bindings': True,
            'disk_reload_verified': True, 'fresh_backend_reload_verified': False}


def load_inference_adapter(trainer, checkpoint, *, branch_id, records,
                           expected_manifest_sha256=None, expected_inference_manifest_sha256=None,
                           provenance=None, limits=None, checkpoint_schedule=None):
    """Load ONLY the reusable inference subartifact into fresh native Qwen+PEFT.

    checkpoint may be the full checkpoint directory or its standalone inference
    subdirectory. No resume metadata or optimizer shard is required or read.
    The caller must construct the exact authenticated base/tokenizer first.
    """
    limits = limits or CheckpointLimits(); wrapper = trainer; trainer = _raw(trainer)
    require(trainer.optimizer is None and trainer.scheduler is None and trainer._run_state is None and
            trainer._complete_training_boundary(), 'inference reload requires clean training state')
    physical = _physical(wrapper); root = _safe_path(checkpoint)
    index_name = 'adapter_model.safetensors.index.json'
    inference_root = root if (root/index_name).exists() else _safe_path(root/'inference')
    index = _json(inference_root/index_name, limits.json_bytes)
    if expected_manifest_sha256 is not None:
        require(inference_root != root and _sha(root/'manifest.json') == expected_manifest_sha256,
                'full checkpoint manifest receipt hash differs')
        parent_manifest = _json(root/'manifest.json', limits.json_bytes)
        require(parent_manifest['files']['inference/'+index_name]['sha256'] == _sha(inference_root/index_name),
                'inference index differs from full checkpoint manifest')
    require(expected_inference_manifest_sha256 is None or
            _sha(inference_root/index_name) == expected_inference_manifest_sha256,
            'inference manifest receipt hash differs')
    require(index.get('format') == FORMAT and index.get('resume_capable') is False and
            index['binding_sha256'] == digest(index['binding']), 'inference manifest format/binding differs')
    require(_binding(trainer, branch_id, records, index['binding']['provenance'] if provenance is None else provenance, checkpoint_schedule)
            == index['binding'], 'inference branch/model/source/config/records identity differs')
    if checkpoint_schedule is not None:
        _check_update(index.get('update'), index['binding'])
        if expected_manifest_sha256 is not None:
            require(parent_manifest['update'] == index['update'] and parent_manifest['binding'] == index['binding'],
                    'inference schedule/update differs from full checkpoint manifest')
    files, _ = _inventory(inference_root, max_files=limits.files, max_bytes=limits.checkpoint_bytes)
    files.pop(index_name)
    require(files == index['files'] and set(files) == {'adapter_config.json'} | set(index['weight_map'].values()),
            'inference file inventory/hash differs')
    require(files['adapter_config.json']['bytes'] <= limits.json_bytes and
            all(v['bytes'] <= limits.shard_bytes for k,v in files.items() if k.endswith('.safetensors')),
            'inference individual file cap exceeded')
    from safetensors import safe_open
    inference = {}; by_file = {}
    require(type(index['weight_map']) is dict and len(index['weight_map']) <= limits.tensors,
            'inference tensor cap exceeded')
    expected_keys = {name.replace('.default.', '.'):name for name in trainer.parameters}
    require(set(index['weight_map']) == set(expected_keys) and
            index['adapter_keys'] == {name:key for key,name in expected_keys.items()},
            'inference exact named parameter inventory differs')
    for key,name in index['weight_map'].items():
        require(type(name) is str and re.fullmatch(r'adapter-[0-9]{5}-of-[0-9]{5}\.safetensors',name),
                'unsafe inference shard path')
        by_file.setdefault(name,set()).add(key)
    for name,keys in by_file.items():
        with safe_open(str(_safe_path(inference_root/name)),framework='pt',device='cpu') as f:
            require(set(f.keys()) == keys, 'inference shard tensor inventory differs')
            for key in f.keys():
                tensor=f.get_tensor(key); parameter=trainer.parameters[expected_keys[key]]
                require(tensor.dtype == trainer.torch.float32 == parameter.dtype and
                        tensor.shape == parameter.shape and bool(trainer.torch.isfinite(tensor).all()),
                        'inference tensor dtype/shape/finite check failed')
                inference[key]=tensor
    resumed_names={expected_keys[key]:value for key,value in inference.items()}
    require(_state_fingerprint(resumed_names,trainer.torch)['sha256'] == index['adapter_sha256'],
            'inference tensor fingerprint differs')
    from peft import set_peft_model_state_dict
    bindings = {k:id(v) for k,v in trainer.parameters.items()}
    set_peft_model_state_dict(trainer.model, inference, adapter_name='default')
    trainer._assert_adapter_recipe(); trainer._publish_fingerprint()
    require(trainer.fingerprint()['sha256'] == index['adapter_sha256'], 'inference adapter readback differs')
    require(bindings == {k:id(v) for k,v in trainer.parameters.items()} and _physical(wrapper) == physical,
            'inference reload changed parameter bindings/accounting')
    return {'loaded': True, 'resume_capable': False, 'adapter_sha256': index['adapter_sha256'],
            'same_parameter_bindings': True, 'physical_ledger_untouched': True,
            'inference_manifest_sha256': _sha(inference_root/index_name),
            'optimizer_shards_read': False, 'standalone_inference_artifact': True}


def verify_disk_reload(trainer, checkpoint, *, branch_id, records, clean_snapshot, evaluate,
                       expected_manifest_sha256=None, limits=None, checkpoint_schedule=None):
    """Evaluate actual tokens/NLL, clean-reset, disk-reload, evaluate again.

    evaluate() must use metered native generation/scoring and return exactly
    {'output_token_ids': [...], 'nll': finite float}. No NLL tolerance is widened.
    Leaves the selected disk state loaded. Evaluation remains physically charged.
    """
    raw = _raw(trainer); before = evaluate()
    def valid(value):
        require(type(value) is dict and set(value) == {'output_token_ids','nll'} and
                type(value['output_token_ids']) is list and value['output_token_ids'] and
                all(type(x) is int and 0 <= x < 151936 for x in value['output_token_ids']) and
                type(value['nll']) in (int,float) and math.isfinite(value['nll']), 'actual output-token/NLL receipt required')
    valid(before); bindings = {k:id(v) for k,v in raw.parameters.items()}
    ledger_before = _physical(trainer)
    raw.restore_training_state(clean_snapshot)
    require(raw.optimizer is None and raw.scheduler is None and raw._run_state is None,
            'reload verification reset was not clean base')
    result = load_branch_checkpoint(trainer, checkpoint, branch_id=branch_id, records=records,
                                   expected_manifest_sha256=expected_manifest_sha256, limits=limits, checkpoint_schedule=checkpoint_schedule)
    require(_physical(trainer) == ledger_before, 'reset/reload refunded physical work')
    after = evaluate(); valid(after)
    require(before == after, 'disk reload output-token/NLL parity failed')
    require(bindings == {k:id(v) for k,v in raw.parameters.items()}, 'verification parameter bindings changed')
    ledger_after = _physical(trainer)
    require(ledger_before is None or all(ledger_after['charged'][k] >= v for k,v in ledger_before['charged'].items()),
            'reload verification physical ledger regressed')
    return {**result, 'output_token_ids': after['output_token_ids'], 'nll_before': before['nll'],
            'nll_after': after['nll'], 'output_token_parity': True, 'nll_exact_parity': True,
            'clean_reset_verified': True, 'physical_ledger_monotone': True}
