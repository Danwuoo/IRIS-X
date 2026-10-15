"""WSL durable owner for the bounded native Windows official SDK bridge.

Reviewed consumer-local runtime, internal official OAuth and source-only SDK
are separate reviewed native bindings. No token export, quota API, grant change,
new resource, implicit numeric output or automatic mutation retry is supported.
"""
import ast, contextlib, email.utils, fcntl, hashlib, json, os, re, shutil, signal, stat, threading, time, uuid, zipfile, sys, types
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, urljoin

BASE = WORK = STATE = STOP = CONFIG = CONFIG_PATH = MANIFEST_PATH = ACTION_REVIEW = None
CONFIG_SOURCE_SHA256 = '9bd6468cb4579e6a4eeaadb8d487b23b9732c545a170cc4b8fcf48c66f35f42a'
BRIDGE_CLIENT_SHA256 = '2708754672e39d4343891c159e37b3bc6810d8f5b2e2001f454822b97322ed12'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
MODEL = 'qwen-lm/qwen-3/transformers/14b/1'
MODEL_ALIASES = [[MODEL], ['qwen-lm/qwen-3/Transformers/14b/1']]
TERMINAL = {'COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'}
RESERVE = 4 * 1024**3

class GuardError(ValueError): pass
class WallTimeout(TimeoutError): pass
class ProviderReportedError(RuntimeError): pass
class AuthRefreshUncertain(RuntimeError): pass

def configured():
    need(CONFIG is not None, 'reviewed_local_configuration_required')
    return CONFIG

def configure(config_path, config_sha256, manifest_path, manifest_sha256, *, recovery=False):
    """Compile exact local configuration code; bind once before any provider."""
    global BASE, WORK, STATE, STOP, CONFIG, CONFIG_PATH, MANIFEST_PATH
    need(CONFIG is None, 'local_configuration_already_bound')
    path=Path(__file__).absolute().with_name('config.py')
    module=load_source_module('reviewed_rl_local_config_'+CONFIG_SOURCE_SHA256,path,CONFIG_SOURCE_SHA256)
    try:config_=module.load(config_path,config_sha256,manifest_path,manifest_sha256, recovery=recovery)
    except ValueError as error:raise GuardError(str(error)) from None
    CONFIG=config_;CONFIG_PATH=Path(config_path).absolute();MANIFEST_PATH=Path(manifest_path).absolute();BASE=config_.repository_root;WORK=config_.candidate_root
    STATE=config_.state_root;STOP=config_.gpu_stop_path
    return config_

def configuration_descriptor():
    """Exact admitted current document; historical identity never drives launch."""
    config_=configured()
    need(CONFIG_PATH is not None, 'current_configuration_path_required')
    raw=verified(CONFIG_PATH,config_.document_sha256,cap=1024**2)
    return {'path':str(CONFIG_PATH),'bytes':len(raw),'sha256':config_.document_sha256}

def publication_manifest_descriptor():
    """Actual configure input, not a guessed historical candidate pathname."""
    config_=configured()
    need(MANIFEST_PATH is not None, 'current_manifest_path_required')
    raw=verified(MANIFEST_PATH,config_.publication_manifest_sha256,cap=4*1024**2)
    need(MANIFEST_PATH.parent==config_.candidate_root,'current_manifest_candidate_root')
    return {'path':str(MANIFEST_PATH),'bytes':len(raw),'sha256':config_.publication_manifest_sha256}

def bind_action_review(path,digest):
    """Called only after transport's exact action/source review gate succeeds."""
    global ACTION_REVIEW
    need(ACTION_REVIEW is None,'action_review_already_bound')
    raw=verified(path,digest,cap=4*1024**2)
    ACTION_REVIEW={'path':str(Path(path).absolute()),'bytes':len(raw),'sha256':digest}

def material_lineage_descriptor():
    """Read lineage only from the already admitted, immutable action review."""
    need(ACTION_REVIEW is not None,'admitted_action_review_required')
    row=ACTION_REVIEW
    review=json.loads(verified(row['path'],row['sha256'],row['bytes'],4*1024**2))
    need(review.get('status')=='PASS' and review.get('local_config_sha256')==configured().document_sha256
         and review.get('publication_manifest_sha256')==configured().publication_manifest_sha256,
         'admitted_action_review_changed')
    lineage=review.get('candidate_lineage')
    if lineage is None:return None
    need(type(lineage)is dict and set(lineage)=={'path','bytes','sha256'},'candidate_lineage_descriptor_schema')
    verified(lineage['path'],lineage['sha256'],lineage['bytes'],4*1024**2)
    return dict(lineage)

def credential_guard():
    config_=configured()
    module=sys.modules['reviewed_rl_local_config_'+CONFIG_SOURCE_SHA256]
    try:return module.credential_guard(config_)
    except ValueError as error:raise GuardError(str(error)) from None

@contextlib.contextmanager
def wall_bound(seconds):
    """A total bound including DNS, headers and slow streaming, main thread only."""
    need(threading.current_thread() is threading.main_thread(), 'wall_timer_main_thread_required')
    old_handler=signal.getsignal(signal.SIGALRM);old_timer=signal.getitimer(signal.ITIMER_REAL);start=time.monotonic()
    def expired(*_):raise WallTimeout('official_request_total_wall_timeout')
    signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,min(seconds,old_timer[0]) if old_timer[0]>0 else seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler)
        if old_timer[0]>0:signal.setitimer(signal.ITIMER_REAL,max(0.000001,old_timer[0]-(time.monotonic()-start)),old_timer[1])

def bounded_call(seconds,fn,*args,**kwargs):
    with wall_bound(seconds):return fn(*args,**kwargs)

def no_retry_session(session):
    from requests.adapters import HTTPAdapter
    session.mount('https://',HTTPAdapter(max_retries=0));session.mount('http://',HTTPAdapter(max_retries=0))
    return session

def bound_sdk_client(client, mutation_counts):
    """Apply before any credential introspection/refresh or resource RPC."""
    session=no_retry_session(client.http_client()._session);send=session.send
    def bounded(request,**kw):
        u=urlparse(request.url)
        need(u.scheme=='https' and u.hostname=='api.kaggle.com' and u.port in (None,443) and not u.username and not u.password and not u.fragment and u.path.startswith('/v1/'),'official_rpc_route_required')
        operation=u.path.rsplit('/',1)[-1]
        routes={'datasets.DatasetApiService':{'GetDataset','ListDatasetFiles','DownloadDataset','CreateDatasetVersionById'},'kernels.KernelsApiService':{'GetKernel','GetKernelSessionStatus','DownloadKernelOutput','SaveKernel'},'blobs.BlobApiService':{'StartBlobUpload'},'users.AccountService':{'GenerateAccessToken'}}
        need(request.method=='POST' and not u.query and any(u.path=='/v1/'+service+'/'+operation and operation in allowed for service,allowed in routes.items()),'unreviewed_rpc_operation')
        if operation in {'StartBlobUpload','CreateDatasetVersionById','SaveKernel','GenerateAccessToken'}:
            need(mutation_counts.get(operation,0)==0,'rpc_mutation_resend_forbidden');mutation_counts[operation]=1
        was_stream=bool(kw.get('stream'))
        kw.update(timeout=(15,90),allow_redirects=False,stream=True)
        with wall_bound(120):
            response=send(request,**kw)
            # Redirect/download responses retain their stream for binary_get; every JSON body is capped before parsing.
            is_json='json' in response.headers.get('Content-Type','')
            if not was_stream or is_json and not (300<=response.status_code<400 and response.headers.get('Location')):
                try:
                    declared=response.headers.get('Content-Length');need(declared is None or 0<=int(declared)<=16*1024**2,'metadata_declared_cap')
                    parts=[];total=0
                    for block in response.iter_content(65536):
                        total+=len(block);need(total<=16*1024**2,'metadata_stream_cap');parts.append(block)
                    response._content=b''.join(parts);response._content_consumed=True
                except BaseException:response.close();raise
                response.close()
            return response
    session.send=bounded


def need(value, code):
    if not value: raise GuardError(code)
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(o): return (json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
def secure_path(p):
    p = Path(p).absolute()
    need('..' not in p.parts,'parent_path_segment')
    for q in [p, *p.parents]:
        need(not q.is_symlink(), 'symlink_path')
    return p

def read(p, cap=16*1024**2):
    p = secure_path(p); need(p.is_file() and stat.S_ISREG(p.stat().st_mode) and p.stat().st_size <= cap, 'bounded_regular_file')
    return p.read_bytes()
def obj(p, cap=16*1024**2):
    def pairs(items):
        result={}
        for key,value in items:need(key not in result,'duplicate_json_key');result[key]=value
        return result
    def finite(token):
        value=float(token);need(__import__('math').isfinite(value),'nonfinite_json');return value
    return json.loads(read(p,cap),object_pairs_hook=pairs,parse_float=finite,parse_constant=lambda _:need(False,'nonfinite_json'))
def file_sha(p):
    p=secure_path(p); need(p.is_file(), 'missing_file'); h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024**2), b''): h.update(b)
    return h.hexdigest()
def descriptor(p):
    p=secure_path(p); return {'path':str(p), 'bytes':p.stat().st_size, 'sha256':file_sha(p)}
def verified(p, digest, size=None, cap=128*1024**2):
    b=read(p,cap); need(sha(b)==digest and (size is None or len(b)==size),'artifact_hash_or_size'); return b

def load_source_module(name,path,expected_sha,cap=16*1024**2):
    """Compile authenticated source bytes directly; never consult .pyc caches."""
    import sys,types
    path=secure_path(path);raw=verified(path,expected_sha,cap=cap)
    module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
    sys.modules[name]=module
    try:exec(compile(raw,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(module))
    except BaseException:
        if sys.modules.get(name) is module:del sys.modules[name]
        raise
    return module

def sync_directory(p):
    fd=os.open(secure_path(p),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def write_new(p, value):
    p=secure_path(p); p.parent.mkdir(parents=True,exist_ok=True); secure_path(p.parent)
    data=value if isinstance(value,bytes) else canonical(value)
    with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    sync_directory(p.parent)
    return descriptor(p)
def event(name, value):
    configured()
    return write_new(STATE/'events'/f'{time.time_ns()}-{name}-{uuid.uuid4().hex[:8]}.json', value)
def journal(name, value):
    configured()
    event(name, value); p=secure_path(STATE/f'{name}-journal.json'); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');write_new(t,value);os.replace(t,p);sync_directory(p.parent);return p

def claim(name, value):
    configured()
    return write_new(STATE/f'{name}.claim.json',value)
@contextlib.contextmanager
def lock(name='operator'):
    config_=configured()
    need(type(name)is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',name) is not None,'operator_lock_role')
    config_.scratch_root.mkdir(parents=True,exist_ok=True)
    p=secure_path(config_.scratch_root/'publisher.lock')
    with p.open('a+b') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise GuardError('operator_already_running:'+name)
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def no_gpu_stop():
    configured()
    need(not STOP.exists(),'sprint_gpu_stop_present')
def redacted_message(message):
    raw=str(message);truncated=len(raw)>8192;s=raw[:8192]
    # urllib3 may expose signed relative paths without an https:// prefix.
    s=re.sub(r'''(?i)(\bwith\s+url:\s*)(?:"[^"\r\n]*(?:"|$)|'[^'\r\n]*(?:'|$)|[^\s<>]+)''',r'\1[url-redacted]',s)
    s=re.sub(r'https?://[^\s<>\"\']+', '[url-redacted]',s)
    s=re.sub(r'(?i)\b(?:Bearer|Basic)\s+[^\s\"\']+', '[credential-redacted]',s)
    s=re.sub(r'(?i)([\"\']?(?:access[_-]?token|refresh[_-]?token|authorization|password|api[_-]?key|cookie|token)[\"\']?\s*[:=]\s*)(?:[\"\'][^\"\']*[\"\']|[^\s,;]+)',r'\1[redacted]',s)
    s=re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]',s)
    return s,truncated
def clean_message(message):
    return redacted_message(message)[0][:2048]
def classify(status, message):
    s,truncated=redacted_message(message);display=s[:2048]
    proxy_denial=re.search(r'(?i)\bTunnel connection failed:\s*(?:401|403)(?![\d.])\b',s)
    if status in (401,403) or proxy_denial: return 'ACCESS_BLOCKED', display
    zero=re.search(r'(?i)\bGPU\s+hours\s+(?:remaining|available|left)\s*[:=]?\s*0(?:\.0+)?(?![\d.])\b',s)
    zero=zero or re.search(r'(?i)\b(?:no|zero)\s+GPU\s+hours(?:\s+(?:remaining|available|left)\b|\s*[.!]?\s*$)',s)
    zero=zero or re.search(r'(?i)(?<![\d.])0(?:\.0+)?(?![\d.])\s+GPU\s+hours\s+(?:remaining|available|left)\b',s)
    unavailable=re.search(r'(?i)\bGPU(?:\s+accelerators?)?\s+(?:(?:is|are|currently)\s+)*(?:unavailable|not available)\b',s)
    quota=re.search(r'(?i)\bGPU\s+(?:quota|time limit|weekly limit)\s+(?:has been\s+|is\s+)?(?:exhausted|exceeded|reached)\b',s)
    if zero or unavailable or quota: return 'GPU_UNAVAILABLE_STOP', display
    if truncated:return 'DIAGNOSTIC_TRUNCATED_BLOCKED',display
    if status==429 or status is not None and status>=500: return 'TRANSIENT',display
    return 'PROVIDER_ERROR',display

def failure(exc, action):
    response=getattr(exc,'response',None);code=getattr(response,'status_code',None)
    if response is not None and 'json' in response.headers.get('Content-Type',''):
        try:
            if len(response.content)<=65536:
                rpc_code=response.json().get('code')
                if type(rpc_code)is int and 400<=rpc_code<=599:code=rpc_code
        except Exception:pass
    classification,message=classify(code,str(exc))
    bridge=getattr(exc,'bridge_failure',None)
    if type(bridge)is dict:
        classification=bridge['classification'];code=bridge['http_status'];message=bridge['code']
    if isinstance(exc,GuardError) and classification not in ('ACCESS_BLOCKED','GPU_UNAVAILABLE_STOP','DIAGNOSTIC_TRUNCATED_BLOCKED'): message=clean_message(str(exc));classification='VERIFICATION_BLOCKED'
    if type(exc).__name__ in ('Timeout','ReadTimeout','ConnectTimeout','ConnectionError','ProxyError','WallTimeout') and classification not in ('ACCESS_BLOCKED','GPU_UNAVAILABLE_STOP','DIAGNOSTIC_TRUNCATED_BLOCKED'): classification='TRANSIENT'
    if isinstance(exc,AuthRefreshUncertain) and classification not in ('ACCESS_BLOCKED','GPU_UNAVAILABLE_STOP','DIAGNOSTIC_TRUNCATED_BLOCKED'):classification='AUTH_REFRESH_BLOCKED'
    retry=None
    if response is not None:
        r=response.headers.get('Retry-After')
        try: retry=max(0,min(600,int(r)))
        except (TypeError,ValueError):
            try: retry=max(0,min(600,email.utils.parsedate_to_datetime(r).timestamp()-time.time()))
            except Exception: pass
    if type(bridge)is dict:retry=bridge['retry_after_seconds']
    result={'action':action,'classification':classification,'http_status':code,'message':message,'retry_after_seconds':retry,'time_epoch':time.time(),'sprint_stop':classification=='GPU_UNAVAILABLE_STOP'}
    if CONFIG is not None:
        if result['sprint_stop'] and not STOP.exists(): write_new(STOP,result)
        event('failure',result)
    return result

def relative(name):
    p=PurePosixPath(name);need(isinstance(name,str) and name and not p.is_absolute() and '\\' not in name and all(x not in ('','..','.') for x in p.parts) and str(p)==name,'unsafe_relative_path');return p

def source_normalize(raw):
    n=json.loads(raw)
    for cell in n['cells']:
        if isinstance(cell.get('source'),list):cell['source']=''.join(cell['source'])
    return n

def config(raw):
    found={}
    for cell in json.loads(raw)['cells']:
        if cell.get('cell_type')!='code':continue
        text=cell['source'];text=''.join(text) if isinstance(text,list) else text
        try: nodes=ast.parse(text).body
        except SyntaxError:continue
        for n in nodes:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                try: v=ast.literal_eval(n.value)
                except (ValueError,TypeError):continue
                key=n.targets[0].id;need(key not in found,'duplicate_config_assignment') if key=='PREDISPATCH_EPOCH' else None;found[key]=v
    return found

def check_zip(path, max_bytes=256*1024**2, max_members=12000, large=(), compressed_max_bytes=None):
    compressed_max_bytes=max_bytes if compressed_max_bytes is None else compressed_max_bytes
    need(secure_path(path).stat().st_size<=compressed_max_bytes,'compressed_archive_cap');result={};total=0
    with zipfile.ZipFile(path) as z:
        need(len(z.infolist())<=max_members,'archive_member_count')
        seen=set()
        for info in z.infolist():
            name=info.filename.rstrip('/') if info.is_dir() else info.filename;relative(name)
            need(name not in seen,'duplicate_archive_member');seen.add(name)
            mode=info.external_attr>>16;need(not stat.S_ISLNK(mode) and (not stat.S_IFMT(mode) or stat.S_ISREG(mode) or info.is_dir() and stat.S_ISDIR(mode)),'archive_special_file')
            if info.is_dir():continue
            cap=64*1024**2 if name in large else 16*1024**2
            need(info.file_size<=cap and not info.flag_bits&1,'archive_member_bound');total+=info.file_size;need(total<=max_bytes,'expanded_archive_cap')
            h=hashlib.sha256();size=0
            with z.open(info) as f:
                for b in iter(lambda:f.read(65536),b''):size+=len(b);need(size<=info.file_size,'archive_stream_bound');h.update(b)
            need(size==info.file_size,'archive_size_mismatch');result[name]={'bytes':size,'sha256':h.hexdigest()}
    return result

def safe_url(url, upload=False):
    u=urlparse(url);need(u.scheme=='https' and u.port in (None,443) and not u.username and not u.password and not u.fragment,'unsafe_storage_url')
    hosts={'storage.googleapis.com','www.googleapis.com'} if upload else {'storage.googleapis.com','www.kaggleusercontent.com'}
    need(u.hostname in hosts and u.path.startswith('/'),'storage_host_not_allowed');return u

class Provider:
    """Every provider, storage and credential operation stays in Windows."""
    def __init__(self):
        credential_guard()
        path=Path(__file__).with_name('bridge_client.py')
        module=load_source_module('reviewed_windows_bridge_client_'+BRIDGE_CLIENT_SHA256,path,BRIDGE_CLIENT_SHA256)
        self.bridge=module.BridgeClient(globals(),dict(configured().windows_bridge))
    def ensure_read_auth(self):
        # Leave enough time for the longest next command and bounded clean close.
        # The worker lease is not the immutable notebook/JIT/training clock.
        if self.bridge.closed or self.bridge.lease_deadline-self.bridge.clock()<1030:
            need(self.bridge.can_rotate_read_only(),'bridge_lease_or_failure_reconcile_only')
            self.bridge=self.bridge.rotate_read_only()
        need(not self.bridge.unknown,'bridge_unknown_reconcile_only')
    def close(self):return self.bridge.close()
    def dataset(self):
        self.ensure_read_auth();return self.bridge.dto(self.bridge.call('dataset',{}),'dataset')
    def kernel(self):
        self.ensure_read_auth();return self.bridge.dto(self.bridge.call('kernel',{}),'kernel')
    def status(self):
        self.ensure_read_auth();return self.bridge.dto(self.bridge.call('status',{}),'status')
    def list_files(self,dataset=False,*,version):
        need(dataset is True,'whole_kernel_inventory_not_supported')
        self.ensure_read_auth();return self.bridge.call('list_files',{'dataset':True,'version':version})
    def output(self,name,*,version):
        relative(name)
        need(type(version)is int and version in {configured().versions[k] for k in ('inactive_predecessor','inactive','active')},'reviewed_numeric_output_version_required')
        return DownloadRequest(self,'output',{'name':name,'version':version})
    def dataset_download(self,name=None,*,version):
        if name is not None:relative(name)
        need(type(version)is int and version in {configured().versions['code_predecessor'],configured().versions['code']},'reviewed_numeric_dataset_download_version_required')
        return DownloadRequest(self,'dataset_download',{'name':name,'version':version})
    def start_upload(self,path):
        path=secure_path(path);self.ensure_read_auth()
        result=self.bridge.call('start_upload',{'name':path.name,'bytes':path.stat().st_size,'sha256':file_sha(path)})
        return types.SimpleNamespace(handle=result['handle'],origin=result['origin'])
    def upload_once(self,handle,path):return self.bridge.upload_once(handle,path)
    def version(self,handle,notes):
        result=self.bridge.call('version',{'handle':handle,'notes':notes,'expected_predecessor_version':configured().versions['code_predecessor']})
        return self.bridge.dto(result,'version')
    def save(self,wire):
        self.ensure_read_auth();return self.bridge.dto(self.bridge.call('save',{'wire':wire}),'save')


class DownloadRequest:
    """Inert numerical request descriptor, never a URL or live HTTP response."""
    def __init__(self,provider,operation,arguments):
        self.provider,self.operation,self.arguments=provider,operation,dict(arguments)
        self.used=False
    def consume(self):
        need(not self.used,'bridge_download_descriptor_reused');self.used=True
        self.provider.ensure_read_auth();return self.provider.bridge
    def close(self):self.used=True


def _binary_get(response,dest,cap,expected=None,expected_size=None):
    need(type(response)is DownloadRequest,'native_bridge_download_descriptor')
    need(type(cap)is int and 0<=cap<=8*1024**3,'download_cap_type')
    dest=secure_path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        need(expected is not None and file_sha(dest)==expected and (expected_size is None or dest.stat().st_size==expected_size),'unverified_download_cache');return descriptor(dest)
    partial=dest.with_name(dest.name+'.partial');secure_path(partial)
    if partial.exists():
        q=dest.parent/'quarantined-partials';q.mkdir(exist_ok=True);secure_path(q);partial.rename(q/(partial.name+'.'+uuid.uuid4().hex))
    need(shutil.disk_usage(dest.parent).free>=RESERVE+cap,'download_disk_reserve')
    bridge=response.consume()
    h=hashlib.sha256();count=0
    with partial.open('xb') as stream:
        class Sink:
            def write(self,block):
                nonlocal count
                need(type(block)is bytes,'download_frame_bytes')
                count+=len(block)
                need(count<=cap and shutil.disk_usage(dest.parent).free>=RESERVE,'download_stream_cap_or_reserve')
                need(stream.write(block)==len(block),'download_short_write');h.update(block)
                return len(block)
        result=bridge.download(response.operation,response.arguments,Sink(),cap=cap,expected=expected,expected_size=expected_size)
        need(result['bytes']==count and result['sha256']==h.hexdigest(),'bridge_download_end_binding')
        stream.flush();os.fsync(stream.fileno())
    need(expected is None or h.hexdigest()==expected,'download_hash_mismatch')
    need(expected_size is None or count==expected_size,'download_size_mismatch')
    need(not dest.exists(),'download_destination_race');partial.rename(dest);sync_directory(dest.parent)
    return descriptor(dest)


def binary_get(response,dest,cap,expected=None,expected_size=None):
    try:
        with wall_bound(900):return _binary_get(response,dest,cap,expected,expected_size)
    finally:response.close()


def binary_metadata(response,expected_size,cap):
    need(type(response)is DownloadRequest and response.operation=='output','native_bridge_metadata_descriptor')
    need(type(expected_size)is int and 0<=expected_size<=cap,'metadata_expected_size_cap')
    try:
        bridge=response.consume()
        with wall_bound(120):
            return bridge.call('binary_metadata',{**response.arguments,'expected_size':expected_size,'cap':cap})
    finally:response.close()
