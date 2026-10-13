"""Verified parent notebook launch and bounded, non-authoritative failure evidence."""
from pathlib import Path
import hashlib, json, math, os, selectors, stat, subprocess, sys, time, types

FAILURE_BYTES = 64 * 1024
_SAFE_MESSAGES = frozenset({
    'unsupported loader path; only source-bounded standard CUDA/NVIDIA library directories are allowed',
    'production device visibility requires numeric indexes or full canonical GPU UUIDs',
    'source-approved CUDA device ordering required',
    'source bytecode cache forbidden', 'source import symlink',
    'original outer reserve exhausted',
    'Linux pidfd signaling and waiting required; no PID-only fallback',
    'owned supervisor failed before launch handshake',
    'owned supervisor launch handshake timed out',
    'owned parent preparation/runtime failed; preserve closure and logs',
})


def load_file(name,path):
    # Hash-bound .py bytes are always compiled directly. Never consult pyc caches.
    path=Path(path).absolute();module=types.ModuleType(name)
    module.__file__=str(path);module.__package__=name.rpartition('.')[0]
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module


def _number(value):
    return value if type(value) in (int,float) and math.isfinite(value) else None


PREPARATION_STAGES = frozenset({
    'request-validation', 'source-import-policy', 'source-authentication',
    'preparation-imports', 'dataset-resolution', 'target-free-material-verification',
    'model-discovery', 'storage-admission', 'offline-installation',
    'interpreter-lineage', 'installed-model-config', 'parent-descriptor',
    'parent-request-write', 'preparation-receipt-write', 'installed-parent-guard',
    'installed-parent-runtime', 'complete',
})
PREPARATION_EXCEPTIONS = frozenset({
    'ValueError', 'RuntimeError', 'OSError', 'FileNotFoundError', 'FileExistsError',
    'PermissionError', 'IsADirectoryError', 'NotADirectoryError',
    'ImportError', 'ModuleNotFoundError', 'TimeoutError', 'TypeError', 'KeyError',
    'AssertionError', 'SystemExit', 'KeyboardInterrupt', 'OtherException',
})


def _diagnostic_sha(value):
    return type(value) is str and len(value) == 64 and set(value) <= set('0123456789abcdef')


def _diagnostic_directory_fd(directory):
    """Anchor every directory component without following replacement links."""
    directory = Path(directory)
    if not directory.is_absolute() or '..' in directory.parts:
        raise ValueError('absolute diagnostic directory required')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open('/', flags)
    try:
        for component in directory.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def read_preparation_failure(directory, context):
    """Read only a bounded, context-matching child diagnostic, never its raw log.

    The result is a diagnostic projection, not a source/runtime/closure grant.
    Refuse aliases, nonregular files, duplicate JSON keys, mutation, unknown
    enums and all authority claims. A missing or rejected report remains unknown.
    """
    fd = directory_fd = None
    try:
        source_sha = context.get('source_sha256')
        request_sha = context.get('request_sha256')
        if not (_diagnostic_sha(source_sha) and _diagnostic_sha(request_sha)):
            return None
        directory_fd = _diagnostic_directory_fd(directory)
        name = 'preparation-failure.json'
        before_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before_path.st_mode) or before_path.st_nlink != 1 or not 0 < before_path.st_size <= FAILURE_BYTES:
            return None
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory_fd)
        before = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (before_path.st_dev, before_path.st_ino):
            return None
        chunks = []
        left = FAILURE_BYTES + 1
        while left:
            block = os.read(fd, min(left, 8192))
            if not block:
                break
            chunks.append(block)
            left -= len(block)
        raw = b''.join(chunks)
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        if not stat.S_ISREG(after.st_mode) or identity(before) != identity(after) or identity(after) != identity(current):
            return None
        if len(raw) != before.st_size or len(raw) > FAILURE_BYTES:
            return None
        def pairs(rows):
            value = {}
            for key, item in rows:
                if key in value:
                    raise ValueError('duplicate diagnostic key')
                value[key] = item
            return value
        def invalid_constant(_):
            raise ValueError('nonfinite diagnostic JSON')
        document = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
        if type(document) is not dict or document.get('format') != 'irisx/rlvr-preparation-failure-v1' or document.get('status') != 'FAILED':
            return None
        if document.get('source_sha256') != source_sha or document.get('request_sha256') != request_sha:
            return None
        stage = document.get('stage')
        error_type = document.get('exception_type')
        if stage not in PREPARATION_STAGES or error_type not in PREPARATION_EXCEPTIONS:
            return None
        if type(document.get('source_authenticated')) is not bool or document.get('diagnostic_only') is not True:
            return None
        if any(document.get(key) is not False for key in (
                'closure_authority', 'model_or_GPU_execution_claim', 'scoring_authority', 'operational_success')):
            return None
        return {'format': 'irisx/rlvr-preparation-failure-projection-v1',
                'stage': stage, 'exception_type': error_type,
                'source_authenticated': document['source_authenticated'],
                'report_sha256': hashlib.sha256(raw).hexdigest(),
                'diagnostic_only': True, 'closure_authority': False,
                'model_or_GPU_execution_claim': False, 'scoring_authority': False,
                'operational_success': False}
    except BaseException:
        return None
    finally:
        for descriptor in (fd, directory_fd):
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except BaseException:
                pass


def annotate_preparation_failure(error, directory, context):
    """Make the safe inner milestone visible without replacing the real error."""
    report = read_preparation_failure(directory, context)
    if report is None:
        note = ('Inner preparation diagnosis is unavailable or unverified. Preserve '
                'preparation/stderr.txt, preparation/closure.json and startup-failure.json; '
                'the outer error alone does not identify the root cause.')
    else:
        note = ('Preparation diagnostic stage: ' + report['stage'] + '; exception type: ' +
                report['exception_type'] + '. Preserve preparation/preparation-failure.json, '
                'preparation/stderr.txt and preparation/closure.json. This stage report '
                'is diagnostic only; it does not prove model or GPU closure.')
    try:
        error.add_note(note)
    except BaseException:
        pass
    return report


def persist_failure(directory, *, stage, error, context, dispatch_state, proof=None, proof_verified=False, preparation_failure=None):
    """Parent-only diagnostic; never persist ambient variables, argv or error text.

    Only known fixed error messages are retained. Unknown messages are omitted.
    Failure evidence is not an owned-process closure capability or model receipt.
    An unknown/absent proof always remains unknown; zero exit is not proof.
    """
    try:
        directory=Path(directory)
        if not directory.is_absolute() or '..' in directory.parts or any(p.is_symlink() for p in (directory,*directory.parents)) or not directory.is_dir():
            return False
        frames=[];tb=error.__traceback__
        while tb is not None and len(frames)<32:
            frames.append({'file':Path(tb.tb_frame.f_code.co_filename).name[:128],
                           'function':tb.tb_frame.f_code.co_name[:128],'line':tb.tb_lineno})
            tb=tb.tb_next
        text=str(error)
        safe_text=text if text in _SAFE_MESSAGES else 'Exception text omitted; consult the bounded official execution log.'
        clean=bool(proof_verified and type(proof) is dict and proof.get('closed') is True and proof.get('ownership_complete') is True
                   and proof.get('forced') is False and proof.get('remaining')==[] and proof.get('errors')==[])
        record={'format':'irisx/rlvr-parent-startup-failure-v1','status':'FAILED','stage':stage,
                'exception_type':type(error).__name__[:128],'safe_message':safe_text,'frames':frames,
                'observed_epoch':_number(time.time()),'observed_monotonic':_number(time.monotonic()),
                'original_epoch':_number(context.get('original_epoch')),'deadline_epoch':_number(context.get('deadline_epoch')),
                'source_sha256':context.get('source_sha256'),'request_sha256':context.get('request_sha256'),
                'dispatch_state':dispatch_state,'proof_available':type(proof) is dict,'proof_verified':bool(proof_verified),
                'clean_owned_closure_verified':clean,'closure_authority':False,
                'model_or_GPU_execution_claim':False,'environment_values_recorded':False,
                'operational_success':False,'VM_teardown_or_billing_claim':False,
                'preparation_failure':preparation_failure}
        raw=(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        if len(raw)>FAILURE_BYTES:return False
        with (directory/'startup-failure.json').open('xb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        return True
    except BaseException:
        # Diagnostics must not replace the original failure or fabricate success.
        return False


def run_bounded(argv, *, guard_module, directory, deadline_epoch, env, scope, failure_context=None):
    directory=Path(directory);directory.mkdir(exist_ok=False)
    started_epoch=time.time();started_monotonic=time.monotonic()
    context=dict(failure_context or {});context['deadline_epoch']=deadline_epoch
    guard=None;selector=None;out=None;err=None;proof=None;proof_verified=False;spawn_attempted=False
    forced=False;reason=None;total=0;stage='budget-check';failure=None;receipt=None
    deadline_mono=None
    try:
        remaining=deadline_epoch-started_epoch
        if remaining<=15:raise ValueError('original outer reserve exhausted')
        deadline_mono=time.monotonic()+remaining
        stage='log-open';out=(directory/'stdout.txt').open('xb');err=(directory/'stderr.txt').open('xb')
        stage='owned-spawn';spawn_attempted=True
        guard=guard_module.OwnedProcessGuard.spawn(argv,evidence_dir=directory/'owned-tree',stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            cwd=str(directory),close_fds=True,start_new_session=True,env=env)
        stage='selector-setup';selector=selectors.DefaultSelector()
        for stream,target in ((guard.child.stdout,out),(guard.child.stderr,err)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,target)
        stage='owned-drain'
        while True:
            exited=guard.poll() is not None
            for key,_ in selector.select(0 if exited else .2):
                block=os.read(key.fileobj.fileno(),65536)
                if not block:
                    selector.unregister(key.fileobj);continue
                left=8*1024**2-total
                if left>0:key.data.write(block[:left]);total+=min(left,len(block))
                if len(block)>left:forced=True;reason='bounded-launcher-log-cap';break
            if forced or exited and not selector.get_map():break
            if time.monotonic()>=deadline_mono-10 or time.time()>=deadline_epoch-10:
                forced=True;reason='original-outer-deadline';break
    except BaseException as exc:
        failure=exc;forced=True;reason='parent-exception'
    finally:
        # Setup errors are inside this cleanup boundary, even after spawn returns.
        if selector is not None:
            try:selector.close()
            except BaseException as exc:
                if failure is None:failure=exc;stage='selector-close'
                forced=True;reason='parent-exception'
        if guard is not None:
            try:
                timeout=min(10,max(.1,deadline_mono-time.monotonic()))
                proof=guard.stop(timeout=timeout) if forced else guard.closed_proof()
                if not proof.get('closed') or proof.get('remaining'):
                    forced=True;proof=guard.stop(timeout=min(10,max(.1,deadline_mono-time.monotonic())))
                guard_module.verify_closed_proof(proof);proof_verified=True
                receipt={'format':'irisx/rlvr-outer-process-closure-v1','scope':scope,'deadline_epoch':deadline_epoch,
                    'started_epoch':started_epoch,'started_monotonic':started_monotonic,'completed_monotonic':time.monotonic(),
                    'completed_epoch':time.time(),'within_deadline':time.time()<=deadline_epoch and time.monotonic()<=deadline_mono,
                    'forced':forced,'reason':reason,'proof':proof,'log_bytes':total,'log_cap_bytes':8*1024**2,'VM_teardown_or_billing_claim':False}
                raw=(json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
                if len(raw)>4*1024**2:raise ValueError('bounded parent closure receipt')
                (directory/'closure.json').write_bytes(raw)
            except BaseException as exc:
                if failure is None:failure=exc;stage='owned-closure'
                # A failed proof/cleanup attempt does not remove our obligation
                # to stop the acquired owned tree. One bounded best-effort retry
                # preserves the original exception and never invents a proof.
                forced=True;reason='parent-exception';proof_verified=False
                try:
                    proof=guard.stop(timeout=min(10,max(.1,deadline_mono-time.monotonic())))
                    guard_module.verify_closed_proof(proof);proof_verified=True
                except BaseException:
                    pass
        pipes=() if guard is None else (guard.child.stdout,guard.child.stderr)
        for stream in (*pipes,out,err):
            if stream is not None:
                try:stream.close()
                except BaseException as exc:
                    if failure is None:failure=exc;stage='log-close'
    if failure is None and (forced or not receipt['within_deadline'] or proof['returncode']!=0 or proof['worker_returncode']!=0 or proof['forced']):
        failure=RuntimeError('owned parent preparation/runtime failed; preserve closure and logs');stage='owned-result'
    if failure is not None:
        preparation_failure = (annotate_preparation_failure(failure, directory, context)
                               if scope == 'entire-owned-preparation-and-runtime' else None)
        persist_failure(directory,stage=stage,error=failure,context=context,
                        dispatch_state=('owned-guard-returned' if guard is not None else 'unknown-spawn-may-not-have-returned' if spawn_attempted else 'not-dispatched'),
                        proof=proof,proof_verified=proof_verified,preparation_failure=preparation_failure)
        raise failure
    return receipt


def launch(*,ready,release,finalized,loader_source,output_root,input_root,epoch):
    here=Path(__file__).resolve().parent
    loader=load_file('rlvr_checked_loader',here/'source_loader.py')
    builder=load_file('rlvr_checked_builder',here/'notebook_builder.py')
    need=loader.need
    need(release.get('production_admitted') is True and release.get('release_role')=='rlvr004','production release admission absent')
    need(type(epoch) is int and 0<=time.time()-epoch<=42000-1800,'original clock is future/expired before preparation')
    output=loader.clean_path(output_root);parent=loader.clean_path(ready['source_root']).parent
    launcher=output.with_name(output.name+'-launcher');environment=Path('/tmp/irisx-qwen14b-rlvr-20261012-environment005')
    for path in (output,launcher,environment):
        loader.clean_path(path);need(not path.exists(),'fresh run and auxiliary paths required')
        need(not path.is_relative_to(parent) and not parent.is_relative_to(path),'source/output overlap')
    need(output_root==builder.OUTPUT and str(parent)==builder.SOURCE,'exact run005/source005 paths required')
    launcher.mkdir()
    context={'original_epoch':epoch,'deadline_epoch':epoch+42180,'source_sha256':ready['source_sha256']}
    stage='notebook-document-write';dispatch_state='not-dispatched'
    try:
        notebook=builder.build(release,loader_source,kind='active-finalized',finalized=finalized)
        for name,value in (('outer.ipynb',notebook),('original-request.json',finalized['owner_request']),('operator.json',finalized['operator'])):
            with (launcher/name).open('xb') as stream:stream.write(builder.encoded(value))
        stage='preparation-request-write'
        request={'format':'irisx/rlvr-parent-preparation-request-v1','ready':ready,'release':release,'finalized':finalized,
            'notebook_python_executable':sys.executable,'output_root':output_root,'input_root':input_root,'epoch':epoch,'launcher_root':str(launcher),'environment_root':str(environment)}
        request_path=launcher/'preparation-request.json';request_raw=builder.encoded(request);context['request_sha256']=loader.digest(request_raw)
        request_path.write_bytes(request_raw)
        source=Path(ready['source_root']);stage='source-guard-import'
        guard=load_file('rlvr_outer_guard',source/'baseline/tools/arc_learning_agent_20261011/process_guard.py')
        stage='source-import-policy';loader.source_import_paths(source)
        stage='parent-environment-import'
        from owned_runtime.parent_scoring import worker_environment
        stage='parent-environment-policy';env=worker_environment(fixture=False)
        stage='owned-preparation';dispatch_state='unknown-consult-owned-stage-proof'
        receipt=run_bounded([sys.executable,'-I','-B',str(here/'prepare_entry.py'),str(request_path),context['request_sha256']],
            guard_module=guard,directory=launcher/'preparation',deadline_epoch=epoch+42180,env=env,scope='entire-owned-preparation-and-runtime',failure_context=context)
        stage='parent-result-read'
        result=loader.parse(loader.read_regular(launcher/'result.json',2*1024**2))
        return {'status':result['status'],'source_sha256':ready['source_sha256'],'terminal_export':result.get('terminal_export'),
                'launcher_closed':receipt['proof']['closed'],'production_admitted':result.get('production_admitted',False)}
    except BaseException as exc:
        persist_failure(launcher,stage=stage,error=exc,context=context,dispatch_state=dispatch_state)
        raise
