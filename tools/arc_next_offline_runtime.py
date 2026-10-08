"""Manual phase launcher for the exact, network-free, mounted ARC pilot.

Imports are inert. Training runs only with an explicit true switch and the
existing model/hardware/budget gates. This file has no provider operations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.arc_next_offline_bundle import canonical, sha_file, verify_inputs, verify_runtime

PHASES = ('VERIFY_OFFLINE_INPUTS','INSTALL_OFFLINE_ENVIRONMENT','CHECK_CPU_IMPORTS',
          'RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT','SCORE_DEVELOPMENT','EXPORT_REPORT')


def _validate(config):
    required = {'runtime_root','model_root','wheels_root','environment_dir','pins','run_tag','output_root',
                'training_profile','enable_training_pilot','max_wall_seconds','approved_max_cost_usd',
                'estimated_hourly_cost_usd','adapter_path'}
    if set(config) != required: raise ValueError('Exact offline phase configuration required')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', config['run_tag']): raise ValueError('Safe fresh run tag required')
    if type(config['enable_training_pilot']) is not bool: raise ValueError('Boolean training switch required')
    for key in ('runtime_root','model_root','wheels_root','environment_dir','output_root'):
        if not isinstance(config[key], str) or not Path(config[key]).is_absolute(): raise ValueError('Explicit absolute local paths required')
    from tools.arc_next_offline_bundle import validate_reference
    if set(config['pins']) != {'runtime','model','wheels'}:
        raise ValueError('Exactly three immutable Dataset pins required')
    for pin in config['pins'].values():
        validate_reference(pin['reference'])
        if pin.get('private') is not True or not re.fullmatch('[0-9a-f]{64}', str(pin.get('manifest_sha256',''))):
            raise ValueError('Private SHA256-bound Dataset pin required')
    input_roots = [Path(config[key]).resolve() for key in ('runtime_root','model_root','wheels_root')]
    for key in ('environment_dir','output_root'):
        output = Path(config[key]).resolve()
        if any(output.is_relative_to(source) for source in input_roots):
            raise ValueError('Environment and outputs must be outside every immutable Dataset root')
    return config


def _verify_model_pin(config):
    from tools.arc_next_offline_bundle import safe_file
    manifest = safe_file(config['model_root'], 'irisx-model-material.json')
    if sha_file(manifest) != config['pins']['model']['manifest_sha256']:
        raise ValueError('Model material manifest differs from the pinned Dataset version')


def _source_lock(config):
    return Path(config['runtime_root']) / 'runtime/research/arc-next-line/model-source-lock.json'


def _summary(value):
    # Preserve proofs without dumping the entire tensor inventory into notebook output.
    if 'model' in value:
        value = dict(value); value['model'] = {k:v for k,v in value['model'].items() if k != 'tensor_inventory'}
    return value


def _runtime_environment(config):
    """Derive the only admitted command; a mutable receipt cannot supply code."""
    from tools.arc_next_offline_bundle import safe_file
    from tools.arc_next_offline_environment import (NETWORK_GUARD, _LAUNCHER,
        NETWORK_GUARD_HOOK_RELATIVE, _network_guard_hook)
    root = Path(config['environment_dir']).absolute()
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError('Regular isolated environment root required')
    receipt = json.loads(safe_file(root, 'installation-receipt.json').read_bytes())
    python = safe_file(root, 'bin/python')
    launcher = safe_file(root, 'offline-run.py')
    guard = safe_file(root, 'lib/python3.12/site-packages/sitecustomize.py')
    startup_hook = safe_file(root, NETWORK_GUARD_HOOK_RELATIVE)
    lock_path = safe_file(root, 'evidence/environment-lock.json')
    wheel_path = safe_file(root, 'evidence/wheel-lock.json')
    requirements = safe_file(root, 'evidence/requirements.lock')
    venv_config = safe_file(root, 'pyvenv.cfg')
    command = [str(python), '-I', '-S', str(launcher)]
    if receipt.get('format') != 'irisx/arc-next-environment-lock-v1' or receipt.get('status') != 'installed-offline' or any(receipt.get(k) is not True for k in ('isolated_venv','complete_transitive_lock','pip_check_passed','pip_offline_resolution_verified')):
        raise ValueError('Verified isolated offline installation receipt required')
    if receipt.get('python_command') != command or receipt.get('python_executable') != str(python) or receipt.get('environment_lock') != str(lock_path):
        raise ValueError('Installation command or evidence path differs from the fixed isolated layout')
    if launcher.read_bytes() != _LAUNCHER.encode() or guard.read_bytes() != NETWORK_GUARD.encode():
        raise ValueError('Trusted offline launcher or persistent network guard changed')
    if (startup_hook.read_bytes() != _network_guard_hook(root).encode() or
            receipt.get('network_guard_startup') != 'exact-path-pth-v1' or
            receipt.get('network_guard_startup_hook_path') != str(startup_hook) or
            receipt.get('network_guard_startup_hook_sha256') != sha_file(startup_hook)):
        raise ValueError('Trusted early network guard startup hook changed or is missing')
    if receipt.get('python_executable_sha256') != sha_file(python) or sha_file(python) != sha_file(Path(sys.executable).resolve()):
        raise ValueError('Isolated interpreter differs from this CPython executable')
    if receipt.get('python_launcher_sha256') != sha_file(launcher) or receipt.get('network_guard_sha256') != sha_file(guard) or receipt.get('venv_config_sha256') != sha_file(venv_config):
        raise ValueError('Installation evidence file changed')
    cfg = dict(line.split(' = ',1) for line in venv_config.read_text().splitlines() if ' = ' in line)
    if cfg.get('include-system-site-packages') != 'false':
        raise ValueError('Host site packages must remain isolated')
    if json.loads(lock_path.read_bytes()) != receipt or receipt.get('wheel_lock_sha256') != sha_file(wheel_path):
        raise ValueError('Environment receipt and bound wheel evidence differ')
    source_wheels = Path(config['wheels_root'])
    mounted_lock = source_wheels/'wheel-lock.json'
    if sha_file(mounted_lock) != config['pins']['wheels']['manifest_sha256']:
        raise ValueError('Mounted wheel Dataset changed')
    prepared = json.loads(mounted_lock.read_bytes())
    evidence_wheels = json.loads(wheel_path.read_bytes())
    if evidence_wheels.get('prepared_wheel_lock_sha256') != config['pins']['wheels']['manifest_sha256'] or receipt.get('prepared_wheel_lock_sha256') != config['pins']['wheels']['manifest_sha256']:
        raise ValueError('Installed environment belongs to a different wheel Dataset')
    normalized = dict(evidence_wheels)
    normalized.pop('prepared_wheel_lock_sha256',None); normalized.pop('prepared_python',None)
    normalized['python'] = prepared.get('python'); normalized['platform'] = prepared.get('platform')
    if normalized != prepared or receipt.get('versions') != prepared.get('versions') or receipt.get('source_lock_sha256') != sha_file(_source_lock(config)):
        raise ValueError('Runtime wheel evidence differs from immutable prepared closure')
    if sha_file(requirements) != prepared.get('requirements_sha256'):
        raise ValueError('Installed requirements evidence changed')
    link = root/'evidence/wheels'
    if not link.is_symlink() or link.resolve() != (source_wheels/'wheels').resolve():
        raise ValueError('Evidence wheels must reference exactly the mounted wheel directory')
    return receipt


def launch_phase(phase, config, *, enabled=False):
    if type(enabled) is not bool: raise ValueError('Boolean manual phase switch required')
    if not enabled: return {'status':'disabled','network_calls':0,'gpu_calls':0}
    if phase not in PHASES: raise ValueError('Unknown manual offline phase')
    config = _validate(config)
    verify_runtime(config['runtime_root'], config['pins']['runtime']['manifest_sha256'])
    if phase == 'VERIFY_OFFLINE_INPUTS':
        return _summary(verify_inputs(config['runtime_root'],config['model_root'],config['wheels_root'],config['pins']))
    if phase == 'INSTALL_OFFLINE_ENVIRONMENT':
        # Exact mounted model/data/wheel closure is required before installing.
        verify_inputs(config['runtime_root'],config['model_root'],config['wheels_root'],config['pins'])
        from tools.arc_next_offline_environment import install_offline
        return install_offline(_source_lock(config),config['wheels_root'],config['environment_dir'],enabled=True)
    if phase in ('CHECK_CPU_IMPORTS','RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT'):
        _verify_model_pin(config)
    installed = _runtime_environment(config)
    root = Path(config['output_root']); root.mkdir(parents=True,exist_ok=True)
    request_root = Path(tempfile.mkdtemp(prefix='phase-'+phase.lower()+'-',dir=root))
    request = request_root/'request.json'; result_path=request_root/'result.json'
    request.write_bytes(canonical({'phase':phase,'config':config,'result_path':str(result_path)})+b'\n')
    code = Path(config['runtime_root'])/'runtime'
    script = code/'tools/arc_next_offline_runtime.py'
    from tools.arc_next_offline_environment import _offline_env
    env = _offline_env()
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1',WANDB_DISABLED='true',PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',
               TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
    # The guard-equipped interpreter is retained for nested multiprocessing children.
    command = installed['python_command'] + [str(script),'--request',str(request)]
    completed = subprocess.run(command,cwd=str(code),env=env,check=False)
    if completed.returncode != 0: raise RuntimeError('Offline phase failed; inspect the retained phase request/output. Exit '+str(completed.returncode))
    if not result_path.is_file():raise RuntimeError('Offline phase ended without its result receipt')
    return json.loads(result_path.read_bytes())


def cpu_import_check(config, installed):
    """Imports/tokenizer/config/safetensor verification only; no full model or GPU."""
    import socket
    if not getattr(socket, '_irisx_offline_guard', False):
        raise RuntimeError('Persistent Python network-denial guard is not active')
    blocked = False
    try:
        socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    except RuntimeError as exc:
        blocked = str(exc) == 'IRISX offline guard: network sockets and DNS are disabled'
    if not blocked: raise RuntimeError('Persistent Python network-denial guard is not active')
    from tools.arc_next_models import validate_environment, validate_material
    environment = validate_environment(installed['environment_lock'],'granite-4.2-8b')
    identity = validate_material(config['model_root'],'granite-4.2-8b',Path(config['model_root'])/'irisx-model-material.json')
    import torch
    import transformers
    import peft
    import accelerate
    from safetensors import safe_open
    tokenizer = transformers.AutoTokenizer.from_pretrained(config['model_root'],local_files_only=True,trust_remote_code=False,use_fast=True)
    model_config = transformers.AutoConfig.from_pretrained(config['model_root'],local_files_only=True,trust_remote_code=False)
    if model_config.model_type != 'granite' or model_config.vocab_size != 100352:raise ValueError('Native Granite config differs')
    if hashlib.sha256(tokenizer.get_chat_template().encode()).hexdigest() != identity['template_sha256']:
        raise ValueError('Native tokenizer template differs')
    vocab=tokenizer.get_vocab()
    from tools.arc_next_models import digest
    if digest(vocab)!=identity['vocabulary_mapping_sha256']:raise ValueError('Native tokenizer vocabulary differs')
    for name in sorted(Path(config['model_root']).glob('*.safetensors')):
        with safe_open(str(name),framework='pt',device='cpu') as opened:
            if not list(opened.keys()):raise ValueError('Empty model shard')
    # A missing local model must fail while the same denial guard is active.
    missing = Path(config['output_root'])/'deliberately-absent-offline-model'
    if missing.exists():raise ValueError('Negative-test path must be absent')
    failed = False
    try:transformers.AutoConfig.from_pretrained(str(missing),local_files_only=True,trust_remote_code=False)
    except (OSError,ValueError):failed=True
    if not failed:raise ValueError('Missing material unexpectedly loaded')
    return {'status':'cpu-import-tokenizer-safetensor-verified','environment':environment,
            'python_network_guard_verified':True,'missing_local_model_failed_closed':True,
            'gpu_runtime_verified':False,'full_model_load_verified':False,'model_inference_calls':0,
            'torch_cuda_build':torch.version.cuda,'note':'No torch.cuda call, model allocation or GPU execution occurred.'}


def execute_phase(phase,config):
    config=_validate(config)
    if phase in ('CHECK_CPU_IMPORTS','RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT'):
        _verify_model_pin(config)
    installed=_runtime_environment(config)
    verify_runtime(config['runtime_root'],config['pins']['runtime']['manifest_sha256'])
    data=Path(config['runtime_root'])/'training';output=Path(config['output_root'])/config['run_tag']
    if phase=='CHECK_CPU_IMPORTS':return cpu_import_check(config,installed)
    if phase=='RUN_CALIBRATION':
        from tools.arc_next_training import CalibrationConfig,RunBudget,PROFILES,run_calibration
        profile=config['training_profile']
        if profile not in PROFILES:raise ValueError('Unknown training profile')
        steps=PROFILES[profile]
        budget=RunBudget(max_optimizer_steps=steps,max_input_tokens=steps*4096,max_supervised_tokens=steps*4096,
          max_sequence_tokens=4096,max_eval_input_tokens=32768,max_eval_rows=4,max_wall_seconds=config['max_wall_seconds'])
        settings=CalibrationConfig(model_path=config['model_root'],model_key='granite-4.2-8b',
          training_tasks_path=str(data/'train-demonstrations.json'),training_manifest_path=str(data/'training-manifest.json'),
          environment_lock_path=installed['environment_lock'],model_manifest_path=str(Path(config['model_root'])/'irisx-model-material.json'),
          output_dir=str(output),enabled=True,profile=profile,enable_pilot=config['enable_training_pilot'],budget=budget,
          approved_max_cost_usd=config['approved_max_cost_usd'],estimated_hourly_cost_usd=config['estimated_hourly_cost_usd'],seed=1008)
        return run_calibration(settings)
    if phase=='RUN_ARCHITECTURE_PILOT':
        from tools.arc_next_workflow import ArchitectureConfig,run_architecture
        settings=ArchitectureConfig(model_path=config['model_root'],model_key='granite-4.2-8b',
          material_manifest_path=str(Path(config['model_root'])/'irisx-model-material.json'),environment_lock_path=installed['environment_lock'],
          challenges_path=str(data/'development-challenges.json'),output_dir=str(output),adapter_path=config['adapter_path'],enabled=True,
          maximum_wall_seconds=config['max_wall_seconds'],approved_max_cost_usd=config['approved_max_cost_usd'],
          estimated_hourly_cost_usd=config['estimated_hourly_cost_usd'])
        return run_architecture(settings)
    if phase=='SCORE_DEVELOPMENT':
        from tools.arc_next_report import score_development
        result=score_development(output,data)
        target=output.parent/(output.name+'-development-aggregate.json')
        with target.open('xb') as f:f.write(canonical(result)+b'\n')
        return result
    if phase=='EXPORT_REPORT':
        from tools.arc_next_report import export_report
        return export_report(output)
    raise ValueError('Unknown isolated runtime phase')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);args=parser.parse_args()
    request=json.loads(Path(args.request).read_bytes());target=Path(request['result_path'])
    if target.exists():raise ValueError('Fresh phase result path required')
    result=execute_phase(request['phase'],request['config'])
    with target.open('xb') as f:f.write(canonical(result)+b'\n')


if __name__=='__main__':
    # Scripts live under runtime/tools; install trusted parent explicitly.
    main()
