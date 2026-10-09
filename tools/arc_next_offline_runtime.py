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
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.arc_next_offline_bundle import canonical, sha_file, verify_inputs, verify_runtime
from tools.arc_next_offline_environment import RuntimeCompatibilityError, inspect_runtime

PHASES = ('VERIFY_OFFLINE_INPUTS','INSTALL_OFFLINE_ENVIRONMENT','CHECK_CPU_IMPORTS',
          'RUN_CALIBRATION','RUN_ARCHITECTURE_PILOT','SCORE_DEVELOPMENT','EXPORT_REPORT')


def _validate(config):
    required = {'runtime_root','model_root','wheels_root','environment_dir','pins','run_tag','output_root',
                'training_profile','enable_training_pilot','max_wall_seconds','adapter_path'}
    # Accept legacy callers without requiring cost fields in the manual notebook.
    optional = {'approved_max_cost_usd','estimated_hourly_cost_usd','interpreter_root','interpreter_dir'}
    if not required <= set(config) or not set(config) <= required | optional:
        raise ValueError('Exact offline phase configuration required')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', config['run_tag']): raise ValueError('Safe fresh run tag required')
    if type(config['enable_training_pilot']) is not bool: raise ValueError('Boolean training switch required')
    interpreter = 'interpreter' in config.get('pins', {})
    if interpreter != ('interpreter_root' in config and 'interpreter_dir' in config):
        raise ValueError('Interpreter Dataset pin and both explicit interpreter paths are required together')
    if not interpreter and ({'interpreter_root','interpreter_dir'} & set(config)):
        raise ValueError('Unexpected interpreter paths without a Dataset pin')
    path_keys = ('runtime_root','model_root','wheels_root','environment_dir','output_root')
    for key in path_keys + (('interpreter_root','interpreter_dir') if interpreter else ()):
        if not isinstance(config[key], str) or not Path(config[key]).is_absolute(): raise ValueError('Explicit absolute local paths required')
    from tools.arc_next_offline_bundle import validate_reference
    if set(config['pins']) != {'runtime','model','wheels'} | ({'interpreter'} if interpreter else set()):
        raise ValueError('Exactly the reviewed immutable Dataset pins required')
    for pin in config['pins'].values():
        validate_reference(pin['reference'])
        if pin.get('private') is not True or not re.fullmatch('[0-9a-f]{64}', str(pin.get('manifest_sha256',''))):
            raise ValueError('Private SHA256-bound Dataset pin required')
    input_roots = [Path(config[key]).resolve() for key in ('runtime_root','model_root','wheels_root') + (('interpreter_root',) if interpreter else ())]
    for key in ('environment_dir','output_root') + (('interpreter_dir',) if interpreter else ()):
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
    command = [str(python), '-I', '-B', '-S', str(launcher)]
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
        return _summary(verify_inputs(config['runtime_root'],config['model_root'],config['wheels_root'],{k:config['pins'][k] for k in ('runtime','model','wheels')}))
    if phase == 'INSTALL_OFFLINE_ENVIRONMENT':
        # Exact mounted model/data/wheel closure is required before installing.
        verify_inputs(config['runtime_root'],config['model_root'],config['wheels_root'],{k:config['pins'][k] for k in ('runtime','model','wheels')})
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



def _launch_training_native(config, *, enabled=False):
    """One owner-started pilot128, with automatic prerequisites and evidence export.

    No smoke/pilot16 chain, architecture inference, provisioning, retry, or resume.
    Every attempt consumes its run tag, including prerequisite failures. Existing
    local inputs are reverified and an existing environment must pass the exact
    isolated-layout checks; a failed/partial environment is never silently reused.
    """
    if type(enabled) is not bool:
        raise ValueError('Boolean manual training switch required')
    if not enabled:
        return {'status':'disabled','network_calls':0,'gpu_calls':0}
    config = json.loads(canonical(_validate(config)))
    if (config['training_profile'] != 'pilot128' or config['enable_training_pilot'] is not True
            or config['adapter_path'] is not None):
        raise ValueError('Single-start training requires the existing pilot128 preset and no input adapter')
    root = Path(config['output_root'])
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Regular non-symlink output root required')
    root.mkdir(parents=True, exist_ok=True)
    output = root / config['run_tag']
    diagnostic = root / (config['run_tag'] + '-workflow')
    archive = root / (config['run_tag'] + '-workflow-diagnostics.zip')
    for path in (output, diagnostic, archive, root / (config['run_tag'] + '-evidence.zip')):
        if path.exists() or path.is_symlink():
            raise ValueError('Run tag already consumed; use a fresh RUN_TAG without overwriting or resuming evidence')
    # Atomic ownership before any install or training: concurrent/repeated starts fail.
    diagnostic.mkdir(exist_ok=False)
    def write(name, value):
        with (diagnostic / name).open('xb') as stream:
            stream.write(canonical(value) + b'\n')
    write('request.json', {'format':'irisx/arc-next-training-workflow-request-v1','config':config})
    result = {'format':'irisx/arc-next-training-workflow-result-v1','status':'failed',
              'run_tag':config['run_tag'],'training_profile':'pilot128','requested_optimizer_steps':128,
              'architecture_pilot_started':False,'stages':{},'diagnostics_archive':str(archive)}
    current = 'VERIFY_OFFLINE_INPUTS'
    def step(name, function):
        nonlocal current
        current = name
        write(name.lower() + '-started.json', {'stage':name})
        value = _summary(function())
        result['stages'][name] = value
        write(name.lower() + '-result.json', value)
        return value
    export_attempted = False
    failure = None
    try:
        write('host-runtime.json', inspect_runtime())
        if 'interpreter' in config['pins']:
            def interpreter_identity():
                from tools.arc_next_offline_interpreter import validate_interpreter
                receipt = validate_interpreter(config['interpreter_root'], config['pins']['interpreter']['manifest_sha256'], config['interpreter_dir'])
                if (Path(sys.executable).resolve() != Path(receipt['python_executable']).resolve() or
                        sha_file(Path(sys.executable).resolve()) != receipt['executable_sha256']):
                    raise ValueError('Whole workflow must run under the exact pinned CPython interpreter')
                return receipt
            step('VERIFY_OFFLINE_INTERPRETER', interpreter_identity)
            if os.getsid(0) != os.getpid():
                raise ValueError('Pinned interpreter workflow must own its dispatch session')
            os.environ['IRISX_OFFLINE_DISPATCH_SESSION'] = str(os.getsid(0))
        step('VERIFY_OFFLINE_INPUTS', lambda: launch_phase('VERIFY_OFFLINE_INPUTS', config, enabled=True))
        def environment():
            destination = Path(config['environment_dir'])
            reused = destination.exists() or destination.is_symlink()
            if not reused:
                from tools.arc_next_offline_environment import install_offline
                install_offline(_source_lock(config), config['wheels_root'], destination, enabled=True)
            # Validate both new and cached installations; do not trust existence alone.
            receipt = _runtime_environment(config)
            return {'status':'verified-existing' if reused else 'installed-and-verified',
                    'environment_lock':receipt['environment_lock'],'reused':reused}
        step('PREPARE_OFFLINE_ENVIRONMENT', environment)
        checked = step('CHECK_CPU_IMPORTS', lambda: launch_phase('CHECK_CPU_IMPORTS', config, enabled=True))
        if (checked.get('status') != 'cpu-import-tokenizer-safetensor-verified'
                or checked.get('python_network_guard_verified') is not True
                or checked.get('missing_local_model_failed_closed') is not True):
            raise RuntimeError('CPU prerequisite receipt did not confirm offline import checks')
        trained = step('RUN_CALIBRATION', lambda: launch_phase('RUN_CALIBRATION', config, enabled=True))
        training = trained.get('training', {})
        updates = training.get('budget', {}).get('actual_optimizer_updates')
        cleanup = trained.get('cleanup', {})
        if (trained.get('status') != 'completed-calibration' or training.get('completed_profile') is not True
                or type(updates) is not int or updates != 128
                or cleanup.get('worker_alive_after_cleanup') is not False
                or cleanup.get('group_still_observable_after_kill') is not False):
            child_error = trained.get('error', {})
            detail = ('; child ' + str(child_error.get('type', 'unknown')) + ': ' +
                      str(child_error.get('message', '')) if child_error else '')
            raise RuntimeError('Training did not complete all 128 optimizer updates with confirmed worker cleanup'
                               + '; calibration status=' + str(trained.get('status'))
                               + '; actual_optimizer_updates=' + str(updates) + detail)
        export_attempted = True
        step('EXPORT_REPORT', lambda: launch_phase('EXPORT_REPORT', config, enabled=True))
        result['status'] = 'completed-training-and-export'
    except BaseException as error:
        failure = error
        result['status'] = 'cancelled' if isinstance(error, (KeyboardInterrupt,SystemExit)) else 'failed'
        result['failed_stage'] = current
        result['error'] = {'type':type(error).__name__,'message':str(error)[:2000],
                           'traceback':traceback.format_exc()}
        if isinstance(error, RuntimeCompatibilityError):
            result['error']['runtime_diagnostic'] = error.diagnostic
        # Report export is read-only with respect to training; its own guard refuses
        # live/unconfirmed workers. A prerequisite failure still gets diagnostics.
        if not export_attempted and (output / 'preflight.json').is_file():
            try:
                step('EXPORT_REPORT', lambda: launch_phase('EXPORT_REPORT', config, enabled=True))
            except BaseException as export_error:
                result['partial_export_error'] = {'type':type(export_error).__name__,
                                                 'message':str(export_error)[:2000]}
    write('result.json', result)
    # Only this workflow's immutable JSON receipts; never model/data/credentials.
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as target:
        for path in sorted(diagnostic.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != '.json':
                raise ValueError('Unexpected workflow diagnostic member')
            target.write(path, path.name)
    if failure is not None:
        if isinstance(failure, (KeyboardInterrupt, SystemExit)):
            raise failure
        raise RuntimeError('Manual training stopped at ' + result['failed_stage'] + ': '
                           + result['error']['message'] + '; diagnostics: ' + str(archive)) from failure
    return result


def _process_identity(pid):
    """Linux kernel identity, including birth time to reject reused PID numbers."""
    try:
        value = (Path('/proc')/str(pid)/'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = value[value.rfind(')')+2:].split()
    return {'pid':pid,'state':fields[0],'ppid':int(fields[1]),
            'group':int(fields[2]),'session':int(fields[3]),'birth':int(fields[19])}


def _refresh_owned_processes(session, owned):
    """Track only our new session and its identity-verified descendants."""
    observed = {}
    for path in Path('/proc').iterdir():
        if path.name.isdecimal():
            item = _process_identity(int(path.name))
            if item is not None:
                observed[item['pid']] = item
    # A new session is created by Popen, so unrelated processes cannot join it.
    for item in observed.values():
        if item['session'] == session:
            owned[(item['pid'],item['birth'])] = item
    changed = True
    while changed:
        changed = False
        parents = {pid for pid,birth in owned if pid in observed and observed[pid]['birth'] == birth}
        for item in observed.values():
            key = (item['pid'],item['birth'])
            if item['ppid'] in parents and key not in owned:
                owned[key] = item
                changed = True
    return [item for item in observed.values()
            if (item['pid'],item['birth']) in owned and item['state'] not in ('Z','X')]


_DISPATCH_CANCEL_STAGES = ((signal.SIGINT,30),(signal.SIGTERM,10),(signal.SIGKILL,5))


def _stop_dispatch_processes(process, owned):
    """Allow supervisor cleanup, then stop only still-owned live descendants."""
    live = _refresh_owned_processes(process.pid, owned)
    for sig, grace in _DISPATCH_CANCEL_STAGES:
        # First signal reaches the original session's supervisors and worker
        # groups. The supervisor still executes its existing worker cleanup.
        targets = live if sig != signal.SIGINT else [p for p in live if p['session'] == process.pid]
        for item in targets:
            current = _process_identity(item['pid'])
            if current is not None and current['birth'] == item['birth']:
                try: os.kill(item['pid'],sig)
                except ProcessLookupError: pass
        deadline = time.monotonic()+grace
        while time.monotonic() < deadline:
            process.poll()  # Reap the leader without abandoning its descendants.
            live = _refresh_owned_processes(process.pid,owned)
            if not live:
                return
            time.sleep(0.1)
    raise RuntimeError('Owned interpreter workflow processes remain live after cleanup; stop the manual session immediately')


def _dispatch_process(command, *, cwd, env):
    """Wait for the whole owned workflow, including cancellation cleanup."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Manual interpreter dispatcher requires the main thread for cancellation handling')
    if not Path('/proc/self/stat').is_file():
        raise RuntimeError('Linux process identity tracking is required before interpreter dispatch')
    process = None
    owned = {}
    previous = signal.getsignal(signal.SIGTERM)
    def terminated(signum, frame):
        raise SystemExit('Manual interpreter dispatcher received SIGTERM')
    signal.signal(signal.SIGTERM,terminated)
    try:
        process = subprocess.Popen(command,cwd=cwd,env=env,start_new_session=True)
        while True:
            _refresh_owned_processes(process.pid,owned)
            try:
                code = process.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                pass
        if _refresh_owned_processes(process.pid,owned):
            raise RuntimeError('Interpreter workflow leader exited while owned descendants remain live')
        return code
    except BaseException:
        if process is not None:
            # Restore ordinary SIGTERM behavior only after owned cleanup. A
            # repeated cancellation must not interrupt this bounded cleanup.
            signal.signal(signal.SIGTERM,signal.SIG_IGN)
            prior_int = signal.signal(signal.SIGINT,signal.SIG_IGN)
            try:
                _stop_dispatch_processes(process,owned)
            finally:
                signal.signal(signal.SIGINT,prior_int)
        raise
    finally:
        signal.signal(signal.SIGTERM,previous)


def launch_training(config, *, enabled=False):
    """One manual start; a pinned portable interpreter owns the whole workflow."""
    if type(enabled) is not bool:
        raise ValueError('Boolean manual training switch required')
    if not enabled:
        return {'status':'disabled','network_calls':0,'gpu_calls':0}
    config = json.loads(canonical(_validate(config)))
    if 'interpreter' not in config['pins']:
        return _launch_training_native(config, enabled=True)
    if (config['training_profile'] != 'pilot128' or config['enable_training_pilot'] is not True
            or config['adapter_path'] is not None):
        raise ValueError('Single-start training requires the existing pilot128 preset and no input adapter')
    root = Path(config['output_root'])
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Regular non-symlink output root required')
    root.mkdir(parents=True, exist_ok=True)
    tag = config['run_tag']
    diagnostic = root / (tag + '-dispatch')
    archive = root / (tag + '-dispatch-diagnostics.zip')
    for path in (root/tag, root/(tag+'-workflow'), root/(tag+'-workflow-diagnostics.zip'),
                 root/(tag+'-evidence.zip'), diagnostic, archive):
        if path.exists() or path.is_symlink():
            raise ValueError('Run tag already consumed; use a fresh RUN_TAG without overwriting or resuming evidence')
    diagnostic.mkdir(exist_ok=False)
    def write(name, value):
        with (diagnostic/name).open('xb') as stream:
            stream.write(canonical(value) + b'\n')
    result = {'format':'irisx/arc-next-interpreter-dispatch-v1','status':'failed',
              'run_tag':tag,'scientific_workflow_changed':False,
              'diagnostics_archive':str(archive)}
    failure = None
    training = None
    try:
        observation = inspect_runtime()
        write('host-runtime.json', observation)
        write('request.json', {'config':config})
        platform_failures = [key for key in ('system','machine','glibc_minimum')
                             if not observation['checks'][key]]
        if platform_failures:
            raise RuntimeCompatibilityError(dict(observation, mismatches=platform_failures, compatible=False))
        verify_runtime(config['runtime_root'], config['pins']['runtime']['manifest_sha256'])
        from tools.arc_next_offline_interpreter import prepare_interpreter, validate_interpreter
        destination = Path(config['interpreter_dir'])
        function = validate_interpreter if destination.exists() or destination.is_symlink() else prepare_interpreter
        receipt = function(config['interpreter_root'], config['pins']['interpreter']['manifest_sha256'], destination)
        write('interpreter.json', receipt)
        code = Path(config['runtime_root'])/'runtime'
        request = diagnostic/'training-request.json'
        response = diagnostic/'training-result.json'
        write(request.name, {'config':config,'result_path':str(response)})
        from tools.arc_next_offline_environment import _LAUNCHER, _offline_env
        command = [receipt['python_executable'],'-I','-B','-S','-c',_LAUNCHER,
                   str(code/'tools/arc_next_offline_runtime.py'),'--training-request',str(request)]
        result['selected_python'] = receipt['python_executable']
        result['interpreter_manifest_sha256'] = receipt['manifest_sha256']
        result['returncode'] = _dispatch_process(command, cwd=str(code), env=_offline_env())
        if result['returncode'] != 0:
            workflow_result = root/(tag+'-workflow')/'result.json'
            detail = ''
            if workflow_result.is_file() and not workflow_result.is_symlink():
                try:
                    failed = json.loads(workflow_result.read_bytes())
                    if (failed.get('format') == 'irisx/arc-next-training-workflow-result-v1'
                            and failed.get('run_tag') == tag and failed.get('status') in ('failed','cancelled')):
                        result['workflow_error'] = failed.get('error', {})
                        detail = ': ' + str(result['workflow_error'].get('message', ''))
                except (OSError, ValueError, TypeError, AttributeError):
                    pass  # A missing/malformed diagnostic never changes the failed return code.
            raise RuntimeError('Pinned CPython workflow failed' + detail + '; inspect '
                               + str(root/(tag+'-workflow-diagnostics.zip')))
        if not response.is_file() or response.is_symlink():
            raise RuntimeError('Pinned CPython workflow ended without its result receipt')
        training = json.loads(response.read_bytes())
        if (training.get('format') != 'irisx/arc-next-training-workflow-result-v1' or
                training.get('status') != 'completed-training-and-export' or
                training.get('run_tag') != tag or training.get('training_profile') != 'pilot128' or
                training.get('requested_optimizer_steps') != 128 or
                training.get('architecture_pilot_started') is not False or
                training.get('diagnostics_archive') != str(root/(tag+'-workflow-diagnostics.zip'))):
            raise RuntimeError('Pinned CPython workflow did not complete the exact training and export identity')
        result['status'] = 'completed-dispatched-training'
    except BaseException as error:
        failure = error
        result['status'] = 'cancelled' if isinstance(error, (KeyboardInterrupt,SystemExit)) else 'failed'
        result['error'] = {'type':type(error).__name__,'message':str(error)[:2000],
                           'traceback':traceback.format_exc()}
        if isinstance(error, RuntimeCompatibilityError):
            result['error']['runtime_diagnostic'] = error.diagnostic
    write('result.json', result)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as target:
        for path in sorted(diagnostic.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != '.json':
                raise ValueError('Unexpected interpreter dispatch diagnostic member')
            target.write(path, path.name)
    if failure is not None:
        if isinstance(failure, (KeyboardInterrupt,SystemExit)):
            raise failure
        raise RuntimeError('Manual training interpreter handoff stopped: ' + result['error']['message']
                           + '; diagnostics: '+str(archive)) from failure
    return dict(training, interpreter_dispatch=result)


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
          estimated_hourly_cost_usd=config.get('estimated_hourly_cost_usd'),seed=1008)
        return run_calibration(settings)
    if phase=='RUN_ARCHITECTURE_PILOT':
        from tools.arc_next_workflow import ArchitectureConfig,run_architecture
        settings=ArchitectureConfig(model_path=config['model_root'],model_key='granite-4.2-8b',
          material_manifest_path=str(Path(config['model_root'])/'irisx-model-material.json'),environment_lock_path=installed['environment_lock'],
          challenges_path=str(data/'development-challenges.json'),output_dir=str(output),adapter_path=config['adapter_path'],enabled=True,
          maximum_wall_seconds=config['max_wall_seconds'],
          estimated_hourly_cost_usd=config.get('estimated_hourly_cost_usd'))
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
    parser=argparse.ArgumentParser()
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--request');choice.add_argument('--training-request')
    args=parser.parse_args()
    request=json.loads(Path(args.training_request or args.request).read_bytes())
    target=Path(request['result_path'])
    if target.exists() or target.is_symlink():raise ValueError('Fresh phase result path required')
    result=(_launch_training_native(request['config'],enabled=True) if args.training_request
            else execute_phase(request['phase'],request['config']))
    with target.open('xb') as f:f.write(canonical(result)+b'\n')


if __name__=='__main__':
    # Scripts live under runtime/tools; install trusted parent explicitly.
    main()
