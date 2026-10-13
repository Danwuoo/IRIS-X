"""Parent-private scorer assembly bound to the reviewed outer/owner chain.

This is a trusted-code boundary, not same-UID secrecy. An independently reviewed
published notebook must authenticate its operator. Locally self-consistent JSON
is not independent review. Production release/cost/environment pins remain None.
No evaluator directory or file is opened here before actual inner + outer close.
"""
from pathlib import Path
import json
import os
import re

from .release import canonical, need, file_sha, source_digest
from . import bootstrap as b

FORMAT = 'owned-rl-parent-scorer-material-v1'
_FIELDS = {'format', 'scope', 'role', 'owner_id', 'original_request_id',
           'original_request_sha256', 'raw_source_sha256', 'evaluator_root',
           'evaluator_manifest_sha256', 'scorer_pins_sha256'}
# NVIDIA's CUDA base image exports this CLI directory. System fallbacks remain
# fixed; the caller's PATH is never inspected or extended.
TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES = ('/usr/local/nvidia/bin', '/bin', '/usr/bin', '/opt/bin')
TRUSTED_DRIVER_LIBRARY_DIRECTORIES = (
    '/usr/local/cuda/lib64', '/usr/local/nvidia/lib', '/usr/local/nvidia/lib64',
    '/usr/lib/x86_64-linux-gnu', '/usr/lib64')


def _strings(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def validate_model_config(config):
    need(type(config) is dict and type(config.get('fixture')) is bool, 'explicit model fixture scope required')
    need(all(not any(word in key.lower() for word in ('evaluator', 'gold', 'scorer'))
             for value in _walk_dicts(config) for key in value), 'no evaluator/scorer/gold fields in model configuration')
    if config['fixture']:
        need(set(config) <= {'fixture', 'failure_fixture'}, 'closed tiny CPU fixture configuration')
    else:
        need(set(config) == {'fixture', 'policy_path', 'environment_path', 'model', 'training_root', 'public_solver_root'},
             'closed production model configuration')
        need(type(config['model']) is dict, 'explicit source-bound model configuration')
        from tools.arc_qwen_transfer_20261012.model_profile import MODEL_KEY, PROFILE_ID, DEPLOYMENT_ID, MATERIAL_ADDENDUM_SHA256
        fixed={'enabled':True,'model_key':MODEL_KEY,'profile_id':PROFILE_ID,
               'reviewed_deployment_id':DEPLOYMENT_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,
               'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'tensor_parallel_size':1,
               'precision':'bf16-base-fp32-lora','seed':1917}
        path_fields={'model_path','tokenizer_path','wheel_root_path','contract_path','environment_lock_path'}
        model=config['model']
        need(set(model)==set(fixed)|path_fields and all(type(model[key]) is type(value) and model[key]==value
             for key,value in fixed.items()), 'exact target-free production model inputs required')
        for value in [config[key] for key in ('policy_path','environment_path','training_root','public_solver_root')]+[model[key] for key in path_fields]:
            need(type(value) is str and 0<len(value)<=4096 and Path(value).is_absolute() and
                 str(Path(value))==value and '..' not in Path(value).parts and not any(ord(c)<32 for c in value),
                 'canonical absolute target-free model material path required')


def _walk_dicts(value):
    if type(value) is dict:
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif type(value) in (list, tuple):
        for child in value:
            yield from _walk_dicts(child)


def worker_environment(*, fixture):
    """No inherited evaluator paths, data, credentials, or interpreter injection.

    Only explicit device visibility/order may be retained. Production loader
    search is constructed from the fixed source-owned standard driver directory
    tuple; inherited loader paths are never read or forwarded. Native identities
    and environment still require the pinned production descriptor's admission.
    """
    result = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
              'PYTHONHASHSEED': '0', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
              'HF_DATASETS_OFFLINE': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
              'TOKENIZERS_PARALLELISM': 'false', 'CUBLAS_WORKSPACE_CONFIG': ':4096:8'}
    if fixture:
        result['CUDA_VISIBLE_DEVICES'] = ''
    elif 'CUDA_VISIBLE_DEVICES' in os.environ:
        value = os.environ['CUDA_VISIBLE_DEVICES']
        token = r'(?:[0-9]+|GPU-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'
        need(len(value)<=4096 and re.fullmatch(token+r'(?:,'+token+r')*', value) is not None,
             'production device visibility requires numeric indexes or full canonical GPU UUIDs')
        result['CUDA_VISIBLE_DEVICES'] = value
    if not fixture and 'CUDA_DEVICE_ORDER' in os.environ:
        value = os.environ['CUDA_DEVICE_ORDER']
        need(value in ('PCI_BUS_ID', 'FASTEST_FIRST'), 'source-approved CUDA device ordering required')
        result['CUDA_DEVICE_ORDER'] = value
    if not fixture:
        result['PATH'] = ':'.join(TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES)
        result['LD_LIBRARY_PATH'] = ':'.join(TRUSTED_DRIVER_LIBRARY_DIRECTORIES)
    return result


def _trusted_driver_roots():
    # Preserve the original three roots' canonical behavior (e.g. /bin links).
    # The newly admitted /opt/bin spelling cannot introduce an arbitrary linked
    # root. Links into an already trusted canonical root remain admissible.
    roots = {Path(p).resolve() for p in TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES[:-1]}
    roots.add(Path(TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES[-1]))
    return roots


def _driver_candidate_observations():
    """Bounded fixed-leaf metadata only; no ambient search or file-body reads.

    Diagnostics confer no admission. Canonical link targets are bounded strings;
    every original executable/library/native check still runs unchanged.
    """
    import stat
    roots = _trusted_driver_roots()
    rows = []
    for directory in TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES:
        candidate = Path(directory) / 'nvidia-smi'
        row = {'path': str(candidate), 'state': 'missing', 'resolved_path': None}
        try:
            candidate.lstat()
            resolved = candidate.resolve(strict=True)
            text = str(resolved)
            row['resolved_path'] = text[:512]
            row['resolved_path_truncated'] = len(text) > 512
            if resolved.parent not in roots:
                row['state'] = 'rejected-link-target'
            else:
                if not stat.S_ISREG(resolved.stat().st_mode):
                    row['state'] = 'nonregular'
                elif not os.access(resolved, os.X_OK):
                    row['state'] = 'non-executable'
                else:
                    row['state'] = 'executable'
        except FileNotFoundError:
            row['state'] = 'missing'
        except (OSError, RuntimeError) as exc:
            row['state'] = 'resolution-error'
            row['error_type'] = type(exc).__name__
        rows.append(row)
    return rows


def _driver_executable(receipt=None):
    """Resolve only the source-owned NVIDIA/system directories, never ambient PATH."""
    import shutil
    path = ':'.join(TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES)
    need(os.environ.get('PATH') == path, 'actual child executable search differs from fixed source policy')
    if receipt is not None:
        receipt['nvidia_cli_candidates'] = _driver_candidate_observations()
    selected = shutil.which('nvidia-smi', path=path)
    need(selected is not None, 'actual child cannot resolve nvidia-smi in fixed trusted directories: ' + path)
    executable = Path(selected)
    resolved = executable.resolve(strict=True)
    need(executable.parent.as_posix() in TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES and
         resolved.parent in _trusted_driver_roots() and
         resolved.is_file() and os.access(resolved, os.X_OK),
         'NVIDIA CLI must remain an executable regular file in fixed trusted directories')
    return executable, resolved


def _preflight_child_driver(deadline, receipt):
    """Bounded actual-child startup check before data, wheel or native weight work.

    This observes the real official-location CLI and CUDA loader, not GPU fit,
    model loading, calibration, or scientific admission. The complete original
    native hardware/driver/package/weight gates still execute unchanged later.
    """
    import ctypes, math, subprocess, sys, time
    from . import ROOT
    need(type(deadline) in (int,float) and math.isfinite(deadline) and time.monotonic()<deadline,
         'original inner deadline required for child startup preflight')
    need(Path.cwd().resolve()==ROOT and Path(sys.executable).is_absolute() and
         os.access(sys.executable,os.X_OK) and sys.flags.isolated and
         sys.flags.ignore_environment and sys.flags.no_user_site and sys.dont_write_bytecode,
         'owned isolated interpreter, executable and source cwd required')
    need(os.environ.get('LD_LIBRARY_PATH')==':'.join(TRUSTED_DRIVER_LIBRARY_DIRECTORIES),
         'actual child loader search differs from fixed source policy')
    receipt['stage']='resolve-nvidia-cli'
    executable,resolved = _driver_executable(receipt)
    receipt.update(nvidia_smi_path=str(executable),nvidia_smi_resolved_path=str(resolved),
                   nvidia_smi_file_sha256=file_sha(resolved))
    receipt['stage']='resolve-cuda-library'
    try:
        driver = ctypes.CDLL('libcuda.so.1')
    except OSError as exc:
        raise ValueError('actual child cannot resolve libcuda.so.1 before model loading') from exc
    need(getattr(driver,'cuInit',None) is not None, 'resolved CUDA driver lacks cuInit')
    receipt['driver_resolved_before_weights']=True
    receipt['stage']='query-nvidia-driver'
    remaining=deadline-time.monotonic()
    need(remaining>0,'original inner deadline expired before NVIDIA CLI preflight')
    query=subprocess.run([str(executable),'--query-gpu=driver_version','--format=csv,noheader'],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=min(10.,remaining))
    need(len(query.stdout)<=16384 and len(query.stderr)<=16384,'bounded NVIDIA CLI startup response required')
    receipt.update(nvidia_smi_query_complete=True,driver_version=query.stdout.strip())
    receipt['stage']='observe-cuda-visibility'
    remaining=deadline-time.monotonic()
    need(remaining>0,'original inner deadline expired before CUDA visibility preflight')
    probe=subprocess.run([sys.executable,'-I','-B','-c',
        "import json,torch;print(json.dumps({'cuda_available':torch.cuda.is_available(),'device_count':torch.cuda.device_count()}))"],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=min(60.,remaining))
    need(len(probe.stdout)<=16384 and len(probe.stderr)<=16384,'bounded CUDA visibility response required')
    observed=json.loads(probe.stdout)
    need(type(observed) is dict and set(observed)=={'cuda_available','device_count'} and
         type(observed['cuda_available']) is bool and type(observed['device_count']) is int,
         'actual isolated child CUDA visibility response required')
    receipt['cuda_visibility']=observed
    need(observed['cuda_available'] and observed['device_count']>0,
         'actual isolated child reports CUDA unavailable or zero visible devices')
    receipt['stage']='verify-pinned-driver'
    hardware=ROOT/'baseline/materials/qwen14b/hardware-contract.json'
    need(query.stdout.strip()==json.loads(hardware.read_text())['driver_version'],
         'actual child NVIDIA CLI driver differs from unchanged hardware contract')
    need(time.monotonic()<deadline,'original inner deadline expired during NVIDIA CLI preflight')
    return {**receipt,'status':'complete','stage':'complete','format':'owned-rl-child-driver-resolution-v1','library':'libcuda.so.1',
            'driver_resolved_before_weights':True,'native_model_loaded':False,
            'executable_search_directories':list(TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES),
            'nvidia_smi_path':str(executable),'nvidia_smi_resolved_path':str(resolved),
            'nvidia_smi_file_sha256':file_sha(resolved),'driver_version':query.stdout.strip(),
            'nvidia_smi_query_complete':True,'hardware_contract_sha256':file_sha(hardware),
            'python_executable':sys.executable,'python_prefix':sys.prefix,'cwd':str(ROOT),
            'isolated_interpreter':True,'provenance':'observed host executable in fixed official/system directories; not a vendor signature',
            'full_native_admission_still_required':True,'GPU_fit_or_throughput_claim':False}


def preflight_child_driver(*, deadline):
    receipt={'format':'owned-rl-child-driver-resolution-v1','status':'failed','stage':'child-policy',
             'library':'libcuda.so.1','driver_resolved_before_weights':False,
             'nvidia_smi_query_complete':False,'native_model_loaded':False,
             'executable_search_directories':list(TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES),
             'GPU_fit_or_throughput_claim':False,'full_native_admission_still_required':True}
    try:
        return _preflight_child_driver(deadline,receipt)
    except BaseException as exc:
        receipt['error']={'type':type(exc).__name__,'message':str(exc)}
        if hasattr(exc,'returncode'):receipt['subprocess_returncode']=exc.returncode
        exc.child_driver_resolution=receipt
        raise


def _descriptor(entry, path, config):
    from .public_bridge import EVALUATOR_MANIFEST_SHA256, SCORER_PINS_SHA256
    raw, ref = b._read(path)
    receipt = entry['receipt']
    need(ref['file_sha256'] == receipt.get('parent_scorer_sha256'),
         'reviewed v2 operator must pin complete parent-private scorer descriptor bytes')
    descriptor = b._json(raw, 'parent scorer descriptor')
    need(type(descriptor) is dict and set(descriptor) == _FIELDS and descriptor['format'] == FORMAT,
         'closed parent scorer descriptor schema')
    for key in ('scope', 'role', 'owner_id', 'original_request_id', 'raw_source_sha256'):
        need(descriptor[key] == receipt[key], 'parent scorer owner/source lineage differs: ' + key)
    need(descriptor['original_request_sha256'] == receipt['original_request']['file_sha256'],
         'parent scorer original request bytes differ')
    need(descriptor['scorer_pins_sha256'] == SCORER_PINS_SHA256,
         'unchanged original scorer import-closure pin required')
    need(b._sha_value(descriptor['evaluator_manifest_sha256']), 'parent evaluator manifest SHA required')
    production = receipt['scope'] == b.PRODUCTION_SCOPE
    need(production == (config['fixture'] is False), 'parent scorer fixture/production scope differs')
    need((descriptor['evaluator_manifest_sha256'] == EVALUATOR_MANIFEST_SHA256) is production,
         'original evaluator pin required only in production; synthetic gold cannot claim it')
    value = descriptor['evaluator_root']
    need(type(value) is str and 0 < len(value) <= 4096 and Path(value).is_absolute() and
         str(Path(value)) == value and '..' not in Path(value).parts,
         'canonical absolute parent-only evaluator root required')
    # Do not resolve/stat/open evaluator_root: no evaluator I/O before closure.
    secrets = (value, ref['path'])
    need(all(not any(secret in item for secret in secrets) for item in _strings(config)),
         'parent scorer material path leaked into model configuration')
    for item in _strings(config):
        if item.startswith('/'):
            p, evaluator = Path(item), Path(value)
            need(not (p == evaluator or p.is_relative_to(evaluator) or evaluator.is_relative_to(p)),
                 'model material paths must be disjoint from evaluator material')
    environment=worker_environment(fixture=config['fixture'])
    for item in environment.values():
        need(not any(secret in item for secret in secrets), 'parent scorer path leaked into effective child environment')
        for component in item.split(':'):
            if component.startswith('/'):
                p=Path(component)
                need(all(not (p==Path(secret) or p.is_relative_to(Path(secret)) or Path(secret).is_relative_to(p))
                         for secret in secrets), 'child environment paths overlap parent-private scorer material')
    # The worker re-reads these authenticated outer documents; they must contain
    # only the descriptor's hash, never its private path or evaluator location.
    for name in b._FILES:
        if name == 'source_archive':
            continue
        document, _ = b._read(receipt[name]['path'])
        need(not any(secret.encode() in document for secret in secrets),
             'parent scorer path leaked into worker-visible outer document: ' + name)
        try:
            parsed = b._json(document, name)
        except ValueError:
            continue  # A material review may be ordinary text.
        need(all(not any(secret in item for secret in secrets) for item in _strings(parsed)),
             'parent scorer path leaked into parsed worker-visible outer document: ' + name)
    return descriptor, ref


def bind_parent_scorer(context, path, *, config):
    b._require_caller('owned_runtime.bootstrap', ('reviewed_bootstrap', 'synthetic_scoring_bootstrap'))
    entry = b._context(context)
    need('parent_scorer' not in entry, 'parent scorer binding already consumed')
    validate_model_config(config)
    descriptor, ref = _descriptor(entry, path, config)
    entry['parent_scorer'] = {'descriptor': descriptor, 'ref': ref, 'config': canonical(config), 'scored': False}


def require_parent_scorer(context, *, config):
    entry = b._context(context)
    bound = entry.get('parent_scorer')
    need(type(bound) is dict and bound['config'] == canonical(config), 'checked parent-private scorer binding required')
    descriptor, ref = _descriptor(entry, bound['ref']['path'], config)
    need(descriptor == bound['descriptor'] and ref == bound['ref'], 'parent scorer descriptor changed')
    return entry


def score_parent_public(context, capability, seal, *, sources, config, clock, output_root):
    """Source-owned parent path, invoked while the live closure is still available."""
    b._require_caller('owned_runtime.runner', ('run_owned',))
    from .supervisor import verify_closed_capability
    closed = verify_closed_capability(capability)  # First. No evaluator I/O on failure.
    entry = require_parent_scorer(context, config=config)
    bound = entry['parent_scorer']
    need(not bound['scored'], 'parent scorer operation is one-use')
    root = Path(output_root).resolve()
    need(str(root) == closed['output_root'], 'parent scorer output belongs to another owner')
    request_path = root / 'owner-request.json'
    binding = b._request_binding(entry['receipt'], request_path=request_path,
                                 request_sha256=closed['request_sha256'], sources=dict(sources.files),
                                 plan_sha256=json.loads(request_path.read_text())['plan_sha256'], clock=clock)
    need(binding['raw_source_sha256'] == source_digest(dict(sources.files)), 'closed scorer source differs')
    bound['scored'] = True
    from experiment_flow.contracts import write_json
    descriptor = bound['descriptor']
    input_ref = write_json(root / 'parent-scorer-input.json', {
        'format': 'owned-rl-parent-scorer-input-v1', 'descriptor': descriptor,
        'descriptor_original_ref': bound['ref'], 'checked_outer': entry['receipt'],
        'owner_request_sha256': closed['request_sha256'],
        'owner_inner_closure_sha256': closed['inner_closure_sha256'],
        'owner_outer_closure': {'path': str(root / 'outer-closure.json'), 'file_sha256': file_sha(root / 'outer-closure.json')},
        'authority': 'live-parent-context-and-inner-outer-closed-capability; independent-published-review-still-required'})
    from .public_bridge import score_closed_public
    score = score_closed_public(capability, seal, sources=sources,
                                evaluator_root=descriptor['evaluator_root'], output_root=root / 'public-scoring',
                                evaluator_manifest_sha256=descriptor['evaluator_manifest_sha256'])
    receipt = write_json(root / 'parent-scorer-receipt.json', {
        'format': 'owned-rl-parent-scorer-receipt-v1', 'input': input_ref,
        'score': {'path': score['path'], 'file_sha256': score['file_sha256']},
        'owner_request_sha256': closed['request_sha256'],
        'original_epoch': clock.original_epoch, 'production_admitted': False,
        'independent_review_authority': 'pending externally pinned published chain', 'fixture': config['fixture']})
    return score, receipt


def persist_parent_lineage(context, output_root):
    """Retain exact raw independently referenced documents after worker exit.

    Failures retain observed bytes and report mismatches; copies never supply
    independent authority or overwrite the original outer/owner chain.
    """
    b._require_caller('owned_runtime.runner', ('run_owned',))
    need(type(context) is b.VerifiedOuterContext and context in b._CONTEXTS,
         'registered parent context required for lineage retention')
    entry=b._CONTEXTS[context]
    need(entry['pid']==os.getpid(), 'parent lineage context belongs to another process')
    root=Path(output_root).resolve()
    from experiment_flow.contracts import write_json
    from .evidence import admit_write
    refs={name:entry['receipt'][name] for name in b._FILES}
    if entry.get('parent_scorer'):
        refs['parent_scorer']=entry['parent_scorer']['ref']
    copies={}
    for name, expected in refs.items():
        try:
            raw, actual=b._read(expected['path'],maximum=b._MAX_ARCHIVE if name=='source_archive' else b._MAX_DOCUMENT)
            path=root/'parent-lineage'/(name+('.zip' if name=='source_archive' else '.raw'))
            admit_write(path,len(raw));path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            copies[name]={'original':expected,'retained':{'path':str(path),'file_sha256':file_sha(path)},
                          'bytes':len(raw),'matches_original_binding':actual==expected}
        except Exception as exc:
            copies[name]={'original':expected,'retained':None,'matches_original_binding':False,
                          'error':{'type':type(exc).__name__,'message':str(exc)[:4096]}}
    return write_json(root/'parent-lineage/index.json',{'format':'owned-rl-parent-lineage-copies-v1',
        'files':copies,'all_original_bytes_retained':all(row['matches_original_binding'] for row in copies.values()),
        'independent_approval_claim':False})
