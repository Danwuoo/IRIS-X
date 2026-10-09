"""Bounded manual ARC-AGI-2 architecture pilot and offline four-L4 plan.

This module does not access evaluators, networks, providers or credentials.
All model imports are lazy; the disabled entry point is fully inert.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from pathlib import Path
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): raise ValueError('Immutable evidence destination already exists')
    path.write_bytes(canonical(value) + b'\n')


@dataclass(frozen=True)
class ArchitectureConfig:
    model_path: str
    material_manifest_path: str
    challenges_path: str
    output_dir: str
    model_key: str = 'granite-4.2-8b'
    adapter_path: str | None = None
    environment_lock_path: str = ""
    allow_experimental_qwen: bool = False
    enabled: bool = False
    arms: tuple[str, ...] = ('grid', 'program', 'repair')
    task_limit: int = 4
    seed: int = 1008
    max_calls_per_arm: int = 4
    max_generated_tokens_per_arm: int = 4096
    max_prompt_tokens_per_arm: int = 32768
    max_new_tokens_per_call: int = 1024
    max_context_tokens: int = 8192
    max_wall_seconds_per_arm: float = 120.0
    maximum_wall_seconds: float = 1800.0
    approved_max_cost_usd: float | None = None  # Deprecated compatibility field; never enforced.
    estimated_hourly_cost_usd: float | None = None


def validate_config(config):
    if type(config.enabled) is not bool or type(config.allow_experimental_qwen) is not bool:
        raise ValueError('Explicit Boolean execution flags required')
    if config.arms != ('grid', 'program', 'repair'):
        raise ValueError('First pilot compares the same declared A/B/C arms')
    for key in ('task_limit', 'max_calls_per_arm', 'max_generated_tokens_per_arm',
                'max_prompt_tokens_per_arm', 'max_new_tokens_per_call', 'max_context_tokens'):
        if type(getattr(config, key)) is not int or getattr(config, key) <= 0:
            raise ValueError('Positive integral workload budgets required')
    if config.task_limit > 32: raise ValueError('First pilot is limited to 32 task groups')
    if config.max_new_tokens_per_call > config.max_generated_tokens_per_arm:
        raise ValueError('Per-call token budget exceeds shared arm budget')
    for key in ('max_wall_seconds_per_arm', 'maximum_wall_seconds'):
        value = getattr(config, key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Finite positive wall budgets required')
    return config


def normalize_messages(messages):
    """One user turn works with all three native templates, including Seed.

    The original role labels remain data inside this user turn; no system role
    is passed to a template that forbids it. Same normalization for all arms.
    """
    if type(messages) is not list or not messages: raise ValueError('Messages required')
    pieces=[]
    for item in messages:
        if type(item) is not dict or set(item) != {'role', 'content'} or item['role'] not in ('system','user','assistant') or type(item['content']) is not str:
            raise ValueError('Only text roles are supported')
        pieces.append(item['role'].upper() + ':\n' + item['content'])
    return [{'role':'user','content':'\n\n'.join(pieces)}]


class HFGenerator:
    def __init__(self, session, model_id, deadline):
        self.session, self.model_id, self.deadline = session, model_id, deadline
        self.arm_deadline = deadline
    def _ids(self, messages):
        return self.session.tokenizer.apply_chat_template(normalize_messages(messages),
                    tokenize=True, add_generation_prompt=True, return_tensors='pt', enable_thinking=False)
    def count_prompt_tokens(self, messages):
        return int(self._ids(messages).shape[-1])
    def __call__(self, request):
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList
        deadline = min(self.deadline, self.arm_deadline, request.get("deadline_monotonic", self.deadline))
        class Deadline(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return time.monotonic() >= deadline
        if time.monotonic() >= deadline: raise TimeoutError('Pilot wall deadline reached')
        ids = self._ids(request['messages']).to(self.session.model.device)
        n = int(ids.shape[-1])
        torch.manual_seed(request['seed']); torch.cuda.manual_seed_all(request['seed'])
        with torch.inference_mode():
            outputs = self.session.model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                max_new_tokens=request['max_new_tokens'], do_sample=True, temperature=0.7, top_p=0.95,
                use_cache=True, stopping_criteria=StoppingCriteriaList([Deadline()]),
                pad_token_id=(self.session.tokenizer.pad_token_id if self.session.tokenizer.pad_token_id is not None else self.session.tokenizer.eos_token_id))
        generated = outputs[0,n:]
        text = self.session.tokenizer.decode(generated, skip_special_tokens=True)
        return {'text':text,'prompt_tokens':n,'generated_tokens':int(generated.numel()),
                'model_id':self.model_id,'finish_reason':'wall' if time.monotonic()>=deadline else
                ('length' if generated.numel() == request['max_new_tokens'] else 'stop')}


def _run_architecture(config, *, loader=None):
    validate_config(config)
    if not config.enabled: return {'status':'disabled','model_calls':0,'provider_calls':0}
    output=Path(config.output_dir)
    if output.exists(): raise ValueError('Fresh immutable pilot directory required')
    from tools.arc_kaggle_submission import challenge_counts
    from tools.arc_next_agent import Limits, solve_task
    challenges=json.loads(Path(config.challenges_path).read_bytes())
    counts=challenge_counts(challenges)
    if any(not re.fullmatch(r'[0-9a-f]{8}', task_id) for task_id in challenges):
        raise ValueError('Exact eight-hex ARC task identities required; path-like IDs forbidden')
    if len(challenges)>config.task_limit: raise ValueError('Input exceeds explicit pilot task count; no silent subset')
    if loader is None:
        from tools.arc_next_models import load_candidate, observe_g4_hardware
        import torch
        observe_g4_hardware(torch)
        loader=load_candidate
    started=time.monotonic(); deadline=started+config.maximum_wall_seconds
    output.mkdir(parents=True)
    write_json(output/'config.json',asdict(config))
    write_json(output/'input-binding.json',{'challenges_sha256':file_sha(config.challenges_path),
        'task_count':len(challenges),'test_count':sum(counts.values()),'truth_present':False})
    session=loader(config.model_path,config.model_key,manifest_path=config.material_manifest_path,
                   environment_lock_path=config.environment_lock_path,
                   allow_experimental_qwen=config.allow_experimental_qwen,
                   device='cuda:0',adapter_path=config.adapter_path)
    session.model.eval()
    identity=session.identity
    model_id='sha256:'+hashlib.sha256(canonical(identity)).hexdigest()
    generate=HFGenerator(session,model_id,deadline)
    write_json(output/'model-identity.json',identity)
    results=[]
    # Rotate arm order by task to reduce consistent warm-up/thermal order bias.
    # Every arm gets its own equal charged cap; timings remain measured rather
    # than claiming exact equal FLOPs across language and grid tokenizers.
    for index,(task_id,task) in enumerate(sorted(challenges.items())):
        order=list(config.arms[index%3:]+config.arms[:index%3])
        for arm in order:
            remaining=deadline-time.monotonic()
            if remaining<=0: break
            limits=Limits(max_calls=config.max_calls_per_arm,
                max_generated_tokens=config.max_generated_tokens_per_arm,
                max_prompt_tokens=config.max_prompt_tokens_per_arm,
                max_new_tokens_per_call=config.max_new_tokens_per_call,
                max_context_tokens=config.max_context_tokens,
                max_wall_seconds=min(config.max_wall_seconds_per_arm,remaining))
            generate.arm_deadline = time.monotonic() + min(config.max_wall_seconds_per_arm,remaining)
            result=solve_task(task,arm=arm,model=generate,
                count_prompt_tokens=generate.count_prompt_tokens,limits=limits,
                seed=config.seed+index*100,expected_model_id=model_id)
            record={'task_id':task_id,'arm':arm,'result':result}
            write_json(output/(task_id+'-'+arm+'.json'),record);results.append(record)
    complete=len(results)==len(challenges)*3
    receipt={'format':'irisx/arc-next-architecture-receipt-v1',
        'status':'complete' if complete else 'partial','requested_task_count':len(challenges),
        'requested_arm_records':len(challenges)*3,'completed_arm_records':len(results),
        'wall_seconds':time.monotonic()-started,'model_id':model_id,
        'challenges_sha256':file_sha(config.challenges_path),
        'correctness_scored':False,'lodo_status':'not_run','official_score':None,
        'paid_vm_shutdown_performed':False,'program_cost_cap_enforced':False,
        'cost_warning':'The program stop does not stop GCP billing. Stop the VM manually.',
        'files':{p.name:file_sha(p) for p in sorted(output.glob('*.json'))}}
    write_json(output/'receipt.json',receipt)
    return receipt


def four_l4_contract(model_key, *, context_tokens=4096):
    """An explicit deployment contract, not a tested device-fit promise."""
    return {'format':'irisx/arc-next-four-l4-contract-v1','model_key':model_key,
        'device_count':4,'device_family':'NVIDIA L4','per_device_marketed_gb':24,
        'topology':'four independent single-GPU model replicas with task scheduling',
        'aggregate_memory_is_not_pooled':True,'dtype':'bfloat16','context_tokens':context_tokens,
        'preferred_artifact':'exact pinned base safetensors + trained LoRA adapter + full original tokenizer',
        'quantization':'none in first qualification; int4 only after separate accuracy and Ada kernel checks',
        'training_only_files_forbidden':['optimizer states','training data','development answers','Blackwell compiled kernels'],
        'required_gates':['offline environment lock','exact source/model/tokenizer hashes',
            'four distinct L4 device UUIDs','one-replica measured VRAM at longest actual prompt',
            'adapter reload equivalence','full task/test denominator','12-hour provider budget with export reserve',
            'atomic checkpoint/output recovery','truth-free submission.json schema'],
        'gpu_runtime_verified':False,'competition_submission_authorized':False,
        'official_code_requirements':'https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description'}


def run_architecture(config):
    """Owner-enabled process supervisor, including model startup in the deadline.

    A SIGKILL closes the owned model process on overrun. It cannot shut down the
    billed VM; its narrowly scoped process watchdog is not a cloud billing cap.
    """
    validate_config(config)
    if not config.enabled: return {'status':'disabled','model_calls':0,'provider_calls':0}
    import os
    import signal
    import subprocess
    import sys
    import uuid
    output=Path(config.output_dir).absolute()
    if output.exists() or any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('Fresh non-symlink pilot output directory required')
    output.parent.mkdir(parents=True,exist_ok=True)
    cfgpath=output.parent/(output.name+'-config-'+uuid.uuid4().hex+'.json')
    write_json(cfgpath,asdict(config))
    logpath=output.parent/(output.name+'-process.log')
    if logpath.exists(): raise ValueError('Fresh process log required')
    env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',
             WANDB_DISABLED='true',TOKENIZERS_PARALLELISM='false',PYTHONHASHSEED='0')
    started=time.monotonic(); timedout=False; interrupted=None
    def stop_owned(process):
        if process.poll() is not None: return process.returncode
        try: os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError: pass
        try: return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            return process.wait(timeout=10)
    with logpath.open('xb') as log:
        process=subprocess.Popen([sys.executable,str(Path(__file__).absolute()),'worker',str(cfgpath)],
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        try:
            returncode=process.wait(timeout=config.maximum_wall_seconds)
        except subprocess.TimeoutExpired:
            timedout=True
            returncode=stop_owned(process)
        except BaseException as error:
            interrupted=error
            returncode=stop_owned(process)
        finally:
            if process.poll() is None: returncode=stop_owned(process)
    if process.poll() is None: raise RuntimeError('Owned model process stop is unconfirmed; do not archive')
    receipt={'format':'irisx/arc-next-architecture-supervision-v1','returncode':returncode,
             'timed_out':timedout,'confirmed_stopped':process.poll() is not None,
             'wall_seconds':time.monotonic()-started,'maximum_wall_seconds':config.maximum_wall_seconds,
             'hard_owned_process_deadline_enforced':True,'vm_shutdown_performed':False,
             'log_sha256':file_sha(logpath),'config_sha256':file_sha(cfgpath),
             'interrupted':interrupted is not None,
             'interruption_type':type(interrupted).__name__ if interrupted is not None else None,
             'status':'complete' if returncode==0 and not timedout and interrupted is None else 'failed_or_partial'}
    childreceipt=output/'receipt.json'
    if childreceipt.is_file(): receipt['child_receipt']=json.loads(childreceipt.read_bytes())
    write_json(output.parent/(output.name+'-supervision.json'),receipt)
    if interrupted is not None: raise interrupted
    return receipt


if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    if len(sys.argv)!=3 or sys.argv[1]!='worker': raise SystemExit('Internal worker requires exact configuration path')
    value=json.loads(Path(sys.argv[2]).read_bytes()); value['arms']=tuple(value['arms'])
    result=_run_architecture(ArchitectureConfig(**value))
    print(json.dumps(result,sort_keys=True))
