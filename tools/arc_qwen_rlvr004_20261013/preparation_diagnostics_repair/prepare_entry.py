"""Model-free owned preparation, followed by the exact installed parent entry."""
from pathlib import Path
import json, os, shutil, sys, time
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import types
def _source_module(name):
    path=HERE/(name+'.py');module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module
_source_module('source_loader')
from source_loader import read_regular,parse,digest,need,clean_path,encoded,source_import_paths
_source_module('launch_notebook')
from launch_notebook import load_file,run_bounded,PREPARATION_EXCEPTIONS


def resolve(reference,input_root):
    owner,slug,version=reference.split('/')
    base=clean_path(input_root)
    present=[p for p in (base/slug,base/'datasets'/owner/slug) if p.is_dir()]
    need(len(present)==1,'one retained Dataset mount required: '+reference)
    return clean_path(present[0])


def verify_target_free_materials(release,input_root):
    pins=release['material_pins']
    data=resolve(pins['data']['reference'],input_root)
    raw=read_regular(data/'public-data-material.json',2*1024**2)
    need(digest(raw)==pins['data']['manifest_sha256'],'public material metadata pin')
    doc=parse(raw)
    need(doc['format']=='irisx/public120-data-material-v1' and doc['reference']==pins['data']['reference'] and doc['role_manifests']==pins['data']['role_manifests'],'public data role identity')
    # Evaluator path is derived lexically and not statted, resolved or opened.
    training=resolve(pins['training']['reference'],input_root)
    raw=read_regular(training/'manifest.json',2*1024**2)
    need(digest(raw)==pins['training']['manifest_sha256'],'training manifest hash')
    manifest=parse(raw)
    need(manifest['format']=='irisx/learning-training-material-v1' and manifest['reference']==pins['training']['reference'] and manifest['tasks']==1000 and manifest['public_evaluation_files']==0,'clean1000 training material')
    from source_loader import _actual_files,safe_name
    need(len(manifest['files'])<=1100 and sum(v['bytes'] for v in manifest['files'].values())<=32*1024**2,'training inventory limits')
    need(_actual_files(training)==set(manifest['files'])|{'manifest.json'},'exact training inventory')
    for name,row in manifest['files'].items():
        safe_name(name);raw=read_regular(training/name,2*1024**2)
        need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'training file byte pin')
    return data,training



def authenticate_preinstall_source(ready,release):
    """Stdlib material authentication only; this cannot admit model execution.

    The full unchanged check_production_pins/NumericGate runs in the installed
    reviewed bootstrap/runner and again in the owned factory before any model.
    Importing that tensor-dependent gate before offline installation is forbidden.
    """
    source=clean_path(ready['source_root'])
    from owned_runtime import release as r
    files=r.inventory()
    need(r.source_digest(files)==ready['source_sha256']==release['source_sha256'], 'complete source inventory changed')
    need(r.NORMALIZED_SOURCE_CONTRACT_SHA256 is not None and r.review_digest(files)==r.NORMALIZED_SOURCE_CONTRACT_SHA256,
         'normalized pre-install source authentication differs')
    policy=source/'design/MEASURED-POLICY.json';environment=source.parent/'release/REVIEWED-ENVIRONMENT.json'
    need(r.FINAL_V25_POLICY_SHA256 is not None and r.file_sha(policy)==r.FINAL_V25_POLICY_SHA256==release['phase_policy_sha256'],
         'pre-install policy authentication differs')
    need(r.REVIEWED_ENVIRONMENT_SHA256 is not None and r.file_sha(environment)==r.REVIEWED_ENVIRONMENT_SHA256==release['environment_sha256'],
         'pre-install environment authentication differs')
    return policy,environment


# Inert development overlay only. These inherited run005 paths are not a new
# execution identity or approval. A future release requires separate review.
DIAGNOSTIC_LAUNCHER_ROOT = Path('/kaggle/working/irisx-qwen14b-rlvr-20261012-run005-launcher')
DIAGNOSTIC_ENVIRONMENT_ROOT = Path('/tmp/irisx-qwen14b-rlvr-20261012-environment005')
PREPARATION_STAGES = (
    'request-validation', 'source-import-policy', 'source-authentication',
    'preparation-imports', 'dataset-resolution', 'target-free-material-verification',
    'model-discovery', 'storage-admission', 'offline-installation',
    'interpreter-lineage', 'installed-model-config', 'parent-descriptor',
    'parent-request-write', 'preparation-receipt-write', 'installed-parent-guard',
    'installed-parent-runtime', 'complete',
)
DIAGNOSTIC_BYTES = 64 * 1024
INSTALLER_EXCERPT_BYTES = 128 * 1024
STAGE_JOURNAL_BYTES = 16 * 1024


def _diagnostic_directory(path):
    """Acquire each ordinary directory by descriptor; never follow a link."""
    import stat
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or str(path) != os.fspath(path):
        raise ValueError('noncanonical diagnostic directory')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open('/', flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError('ordinary diagnostic directory required')
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _diagnostic_new_file(directory_fd, name, raw, maximum):
    """Bounded, private, exclusive file creation in the acquired owner directory."""
    import stat
    if len(raw) > maximum or '/' in name or name in ('', '.', '..'):
        raise ValueError('bounded fixed diagnostic file required')
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('ordinary private diagnostic output required')
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def _installer_log_excerpt(directory_fd):
    """Read only the fixed installation.log, with bounded first/last extents.

    No source hash is claimed for a truncated log. The retained excerpt's digest
    binds only its bytes; offsets identify how those bytes map to the original.
    """
    import hashlib, stat
    environment_fd = _diagnostic_directory(DIAGNOSTIC_ENVIRONMENT_ROOT)
    fd = None
    try:
        fd = os.open('installation.log', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=environment_fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size < 0:
            raise ValueError('ordinary single-link installer log required')
        size = before.st_size
        half = INSTALLER_EXCERPT_BYTES // 2
        ranges = [(0, size)] if size <= INSTALLER_EXCERPT_BYTES else [(0, half), (size - half, half)]
        blocks = []
        offsets = []
        excerpt_offset = 0
        for source_offset, length in ranges:
            block = os.pread(fd, length, source_offset)
            if len(block) != length:
                raise ValueError('installer log changed during bounded read')
            blocks.append(block)
            offsets.append({'source_offset': source_offset, 'excerpt_offset': excerpt_offset, 'bytes': length})
            excerpt_offset += length
        after = os.fstat(fd)
        current = os.stat('installation.log', dir_fd=environment_fd, follow_symlinks=False)
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                    info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if identity(before) != identity(after) or identity(before) != identity(current):
            raise ValueError('installer log changed during bounded read')
        raw = b''.join(blocks)
        filename = 'installation-log-excerpt.bin'
        _diagnostic_new_file(directory_fd, filename, raw, INSTALLER_EXCERPT_BYTES)
        return {'filename': filename, 'sha256': hashlib.sha256(raw).hexdigest(),
                'original_bytes': size, 'bytes': len(raw), 'truncated': size > len(raw),
                'offsets': offsets, 'sha256_scope': 'retained-excerpt-bytes-only',
                'private_evidence': True}
    finally:
        if fd is not None:
            os.close(fd)
        os.close(environment_fd)


class _PreparationDiagnostics:
    """Best-effort observability only; never admission, closure, or success."""
    def __init__(self, request, request_sha256):
        self.stage = 'request-validation'
        self.source_authenticated = False
        self.directory_fd = None
        self.journal_fd = None
        self.journal_bytes = 0
        self.request_sha256 = self._digest(request_sha256)
        self.source_sha256 = None
        try:
            if self.request_sha256 is not None:
                self.source_sha256 = self._digest(request['ready']['source_sha256'])
            if (request['launcher_root'] != str(DIAGNOSTIC_LAUNCHER_ROOT) or
                    request['environment_root'] != str(DIAGNOSTIC_ENVIRONMENT_ROOT)):
                return
            directory = DIAGNOSTIC_LAUNCHER_ROOT / 'preparation'
            descriptor = _diagnostic_directory(directory)
            self.directory_fd = descriptor
            owned = os.fstat(descriptor)
            actual = os.stat('.')
            if (owned.st_dev, owned.st_ino) != (actual.st_dev, actual.st_ino):
                raise ValueError('actual preparation cwd required for diagnostics')
            # Reservation also prevents a reused output directory from appending
            # misleading fresh markers to old diagnostic evidence.
            self.journal_fd = os.open('preparation-stages.jsonl',
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=descriptor)
        except BaseException:
            self.close()

    @staticmethod
    def _digest(value):
        return value if type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value) else None

    def mark(self, stage):
        # All callers pass source literals. Do not log caller-provided labels.
        if stage not in PREPARATION_STAGES:
            return
        self.stage = stage
        if self.journal_fd is None:
            return
        try:
            import math
            epoch, monotonic = time.time(), time.monotonic()
            if not (math.isfinite(epoch) and math.isfinite(monotonic)):
                return
            raw = encoded({'stage': stage, 'observed_epoch': epoch,
                           'observed_monotonic': monotonic})
            # The journal is JSONL, so use compact one-line serialization.
            raw = (json.dumps(json.loads(raw), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
            if self.journal_bytes + len(raw) > STAGE_JOURNAL_BYTES:
                return
            with os.fdopen(self.journal_fd, 'ab', closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(self.journal_fd)
            self.journal_bytes += len(raw)
        except BaseException:
            pass

    def fail(self, error):
        if self.directory_fd is None or self.journal_fd is None:
            return
        try:
            excerpt = None
            log_status = 'not-requested'
            if self.stage == 'offline-installation':
                try:
                    excerpt = _installer_log_excerpt(self.directory_fd)
                    log_status = 'retained'
                except BaseException:
                    log_status = 'unavailable-or-unsafe'
            # Exception classes can be application-defined. Bound to builtin
            # class names so neither arbitrary text nor private paths can leak.
            import builtins
            name = type(error).__name__
            exception_type = name if (name in PREPARATION_EXCEPTIONS and
                                      getattr(builtins, name, None) is type(error)) else 'OtherException'
            record = {'format': 'irisx/rlvr-preparation-failure-v1', 'status': 'FAILED',
                'stage': self.stage, 'exception_type': exception_type,
                'source_sha256': self.source_sha256, 'request_sha256': self.request_sha256,
                'source_authenticated': self.source_authenticated,
                'installer_log_status': log_status, 'installer_log': excerpt,
                'diagnostic_only': True, 'closure_authority': False,
                'model_or_GPU_execution_claim': False, 'scoring_authority': False,
                'operational_success': False}
            _diagnostic_new_file(self.directory_fd, 'preparation-failure.json',
                                 encoded(record), DIAGNOSTIC_BYTES)
        except BaseException:
            # Retain the original exception even if all diagnostics fail.
            pass

    def close(self):
        for name in ('journal_fd', 'directory_fd'):
            fd = getattr(self, name, None)
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException:
                    pass
                setattr(self, name, None)


def prepare(request, *, request_sha256=None):
    diagnostics = _PreparationDiagnostics(request, request_sha256)
    try:
        return _prepare(request, diagnostics)
    except BaseException as error:
        diagnostics.fail(error)
        raise
    finally:
        diagnostics.close()


def _prepare(request, diagnostics):
    diagnostics.mark('request-validation')
    ready=request['ready'];release=request['release'];epoch=request['epoch']
    need(request['format']=='irisx/rlvr-parent-preparation-request-v1' and release['production_admitted'] is True,'reviewed production preparation required')
    need(type(epoch) is int and epoch==request['finalized']['owner_request']['original_epoch'],'single original epoch')
    need(time.time()<epoch+42000-1800,'original setup/closure allowance exhausted')
    source=clean_path(ready['source_root']);baseline=source/'baseline'
    diagnostics.mark('source-import-policy')
    source_import_paths(source)
    diagnostics.mark('source-authentication')
    policy,environment=authenticate_preinstall_source(ready,release)
    diagnostics.source_authenticated = True
    diagnostics.mark('preparation-imports')
    from owned_runtime.parent_scoring import worker_environment
    from tools.arc_qwen_transfer_deployment_20261012.bootstrap import resolve_datasets,discover_model,nonmodel_input_roots,prepare_environment
    diagnostics.mark('dataset-resolution')
    roots=resolve_datasets(request['input_root'])
    diagnostics.mark('target-free-material-verification')
    data,training=verify_target_free_materials(release,request['input_root'])
    diagnostics.mark('model-discovery')
    contract=baseline/'materials/qwen14b/material-contract.json'
    model_root=discover_model(request['input_root'],contract,excluded=nonmodel_input_roots(request['input_root'],release['dataset_references']))
    # Co-resident storage demand is issued by the reviewed source storage planner.
    diagnostics.mark('storage-admission')
    from owned_runtime.storage import storage_plan,before_session
    storage=storage_plan()
    # Phase-specific source admission; installer separately checks actual /tmp
    # expansion on its backing filesystem. Full caps are descriptive, not free-space demand.
    disk_admission=before_session(Path(request['launcher_root']),fixture=False)
    prepare_request={'environment_root':request['environment_root'],'execution_deadline_epoch':epoch+42000,
        'hard_deadline_epoch':epoch+42180,'global_deadline_epoch':epoch+43200,'provider_deadline_epoch':epoch+42300,
        'started_epoch':epoch}
    diagnostics.mark('offline-installation')
    installed=prepare_environment(prepare_request,baseline,roots)
    diagnostics.mark('interpreter-lineage')
    interpreter_manifest=read_regular(Path(roots['interpreter'])/'interpreter-manifest.json',4*1024**2)
    need(digest(interpreter_manifest)==installed['interpreter']['manifest_sha256'],'installed interpreter manifest lineage')
    (Path(request['launcher_root'])/'interpreter-manifest.json').write_bytes(interpreter_manifest)
    need(time.time()<epoch+42000,'original inner deadline reached during setup')
    diagnostics.mark('installed-model-config')
    from tools.arc_qwen_transfer_20261012.model_profile import MODEL_KEY,PROFILE_ID,DEPLOYMENT_ID,MATERIAL_ADDENDUM_SHA256
    config={'fixture':False,'policy_path':str(policy),'environment_path':str(environment),'training_root':str(training/'data/training'),
        'public_solver_root':str(data/'solver'),'model':{'enabled':True,'model_key':MODEL_KEY,'profile_id':PROFILE_ID,
        'reviewed_deployment_id':DEPLOYMENT_ID,'material_addendum_sha256':MATERIAL_ADDENDUM_SHA256,
        'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'tensor_parallel_size':1,'precision':'bf16-base-fp32-lora','seed':1917,
        'model_path':model_root,'tokenizer_path':str(contract.parent/'hf-overlay'),'wheel_root_path':roots['wheels'],
        'contract_path':str(contract),'environment_lock_path':str(contract.parent/'environment-lock.json')}}
    expected=parse(read_regular(environment,2*1024**2));need(expected['model_config']==config['model'],'exact reviewed model material paths differ')
    diagnostics.mark('parent-descriptor')
    from owned_runtime.public_bridge import EVALUATOR_MANIFEST_SHA256,SCORER_PINS_SHA256
    launcher=Path(request['launcher_root']);owner_raw=read_regular(launcher/'original-request.json',128*1024);owner=parse(owner_raw)
    descriptor={'format':'owned-rl-parent-scorer-material-v1','scope':'production-rl-abc','role':'rl-abc',
        'owner_id':owner['owner_id'],'original_request_id':owner['request_id'],'original_request_sha256':digest(owner_raw),
        'raw_source_sha256':ready['source_sha256'],'evaluator_root':str(data/'evaluator'),
        'evaluator_manifest_sha256':EVALUATOR_MANIFEST_SHA256,'scorer_pins_sha256':SCORER_PINS_SHA256}
    raw=encoded(descriptor)
    need(digest(raw)==request['finalized']['operator']['parent_scorer_sha256'],'resolved parent-private descriptor differs from reviewed JIT hash')
    private=launcher/'parent-private-scorer.json'
    with private.open('xb') as stream:stream.write(raw)
    diagnostics.mark('parent-request-write')
    parent_request={'format':'irisx/rlvr-installed-parent-request-v1','source_root':str(source),'output_root':request['output_root'],'config':config,
        'paths':{'outer_notebook_path':str(launcher/'outer.ipynb'),'operator_path':str(launcher/'operator.json'),
        'material_review_path':str(source.parent/'release/MATERIAL-REVIEW.json'),'source_archive_path':ready['source_archive_path'],
        'original_request_path':str(launcher/'original-request.json'),'parent_scorer_path':str(private)},
        'result_path':str(launcher/'result.json'),'source_sha256':ready['source_sha256']}
    path=launcher/'installed-parent-request.json';path.write_bytes(encoded(parent_request))
    diagnostics.mark('preparation-receipt-write')
    receipt={'format':'irisx/rlvr-offline-preparation-receipt-v1','source_sha256':ready['source_sha256'],'source_acceptance':ready,
        'original_epoch':epoch,'installed_offline':True,'offline_environment':installed,'model_mount':model_root,
        'public_answers_opened':False,'model_loaded_by_preparation':False,'storage_plan':storage,'disk_admission':disk_admission,'actual_disk_free_bytes':shutil.disk_usage(source.parent).free}
    (launcher/'preparation-receipt.json').write_bytes(encoded(receipt))
    diagnostics.mark('installed-parent-guard')
    guard=load_file('rlvr_installed_parent_guard',baseline/'tools/arc_learning_agent_20261011/process_guard.py')
    diagnostics.mark('installed-parent-runtime')
    run_bounded(installed['python_command']+[str(HERE/'parent_entry.py'),str(path),digest(path.read_bytes())],guard_module=guard,
        directory=launcher/'installed-parent',deadline_epoch=epoch+42180,env=worker_environment(fixture=False),scope='installed-parent-with-owned-model-child',
        failure_context={'original_epoch':epoch,'source_sha256':ready['source_sha256'],'request_sha256':digest(path.read_bytes())})
    diagnostics.mark('complete')


def main():
    need(len(sys.argv)==3,'exact preparation request and byte hash required')
    raw=read_regular(Path(sys.argv[1]),2*1024**2);need(digest(raw)==sys.argv[2],'preparation request bytes differ')
    prepare(parse(raw), request_sha256=digest(raw))

if __name__=='__main__':main()
