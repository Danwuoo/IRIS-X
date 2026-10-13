"""Local-only guards and bounded official SDK adapter for RL publication."""
import ast, contextlib, email.utils, fcntl, hashlib, json, os, re, shutil, signal, stat, threading, time, uuid, zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, urljoin

BASE = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parents[1]
STATE = WORK / 'publication/state'
STOP = BASE / 'learning-agent-goal-sprint-20261011/publication/state/SPRINT-GPU-STOP.json'
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
    for q in [p, *p.parents]:
        need(not q.is_symlink(), 'symlink_path')
    return p

def read(p, cap=16*1024**2):
    p = secure_path(p); need(p.is_file() and stat.S_ISREG(p.stat().st_mode) and p.stat().st_size <= cap, 'bounded_regular_file')
    return p.read_bytes()
def obj(p, cap=16*1024**2): return json.loads(read(p, cap))
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
    return write_new(STATE/'events'/f'{time.time_ns()}-{name}-{uuid.uuid4().hex[:8]}.json', value)
def journal(name, value):
    event(name, value); p=secure_path(STATE/f'{name}-journal.json'); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');write_new(t,value);os.replace(t,p);sync_directory(p.parent);return p

def claim(name, value): return write_new(STATE/f'{name}.claim.json',value)
@contextlib.contextmanager
def lock(name='operator'):
    STATE.mkdir(parents=True,exist_ok=True);p=secure_path(STATE/(name+'.lock'))
    with p.open('a+b') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise GuardError('operator_already_running')
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def no_gpu_stop(): need(not STOP.exists(),'sprint_gpu_stop_present')
def clean_message(message):
    s=str(message)[:8192]
    s=re.sub(r'https?://[^\s<>\"\']+', '[url-redacted]',s)
    s=re.sub(r'(?i)\b(?:Bearer|Basic)\s+[^\s\"\']+', '[credential-redacted]',s)
    s=re.sub(r'(?i)([\"\']?(?:access[_-]?token|refresh[_-]?token|authorization|password|api[_-]?key|cookie|token)[\"\']?\s*[:=]\s*)(?:[\"\'][^\"\']*[\"\']|[^\s,;]+)',r'\1[redacted]',s)
    s=re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]',s)
    return s[:2048]
def classify(status, message):
    s=clean_message(message)
    if status in (401,403): return 'ACCESS_BLOCKED', s
    zero=re.search(r'(?i)\bGPU\s+hours\s+(?:remaining|available|left)\s*[:=]?\s*0(?:\.0+)?(?![\d.])\b',s)
    zero=zero or re.search(r'(?i)\b(?:no|zero)\s+GPU\s+hours(?:\s+(?:remaining|available|left)\b|\s*[.!]?\s*$)',s)
    zero=zero or re.search(r'(?i)(?<![\d.])0(?:\.0+)?(?![\d.])\s+GPU\s+hours\s+(?:remaining|available|left)\b',s)
    unavailable=re.search(r'(?i)\bGPU(?:\s+accelerators?)?\s+(?:(?:is|are|currently)\s+)*(?:unavailable|not available)\b',s)
    quota=re.search(r'(?i)\bGPU\s+(?:quota|time limit|weekly limit)\s+(?:has been\s+|is\s+)?(?:exhausted|exceeded|reached)\b',s)
    if zero or unavailable or quota: return 'GPU_UNAVAILABLE_STOP', s
    if status==429 or status is not None and status>=500: return 'TRANSIENT',s
    return 'PROVIDER_ERROR',s

def failure(exc, action):
    response=getattr(exc,'response',None);code=getattr(response,'status_code',None)
    if response is not None and 'json' in response.headers.get('Content-Type',''):
        try:
            if len(response.content)<=65536:
                rpc_code=response.json().get('code')
                if type(rpc_code)is int and 400<=rpc_code<=599:code=rpc_code
        except Exception:pass
    classification,message=classify(code,str(exc))
    if isinstance(exc,GuardError): message=str(exc);classification='VERIFICATION_BLOCKED'
    if type(exc).__name__ in ('Timeout','ReadTimeout','ConnectTimeout','ConnectionError','ProxyError','WallTimeout') and classification not in ('ACCESS_BLOCKED','GPU_UNAVAILABLE_STOP'): classification='TRANSIENT'
    if isinstance(exc,AuthRefreshUncertain) and classification not in ('ACCESS_BLOCKED','GPU_UNAVAILABLE_STOP'):classification='AUTH_REFRESH_BLOCKED'
    retry=None
    if response is not None:
        r=response.headers.get('Retry-After')
        try: retry=max(0,min(600,int(r)))
        except (TypeError,ValueError):
            try: retry=max(0,min(600,email.utils.parsedate_to_datetime(r).timestamp()-time.time()))
            except Exception: pass
    result={'action':action,'classification':classification,'http_status':code,'message':message,'retry_after_seconds':retry,'time_epoch':time.time(),'sprint_stop':classification=='GPU_UNAVAILABLE_STOP'}
    if result['sprint_stop'] and not STOP.exists(): write_new(STOP,result)
    event('failure',result);return result

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

def existing_token(initial):
    """Read only the approved workspace credential; renew once with durable intent."""
    from kagglesdk import KaggleCredentials
    need(Path.home()==BASE/'.kaggle-oauth-home','approved_auth_home_required')
    credential=secure_path(Path.home()/'.kaggle/credentials.json')
    need(credential.is_file() and stat.S_IMODE(credential.stat().st_mode)==0o600,'credential_storage_mode')
    name='read-auth-refresh';claim_path=STATE/(name+'.claim.json');journal_path=STATE/(name+'-journal.json')
    if claim_path.exists():need(journal_path.exists() and obj(journal_path).get('stage')=='refresh_accepted','auth_refresh_unknown_reconcile_only')
    creds=KaggleCredentials.load(client=initial)
    need(creds is not None and creds.get_username()=='danielwuu','auth_account_missing')
    expiry=creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
    if time.time()+300>=expiry or not creds._access_token:
        need(not claim_path.exists(),'auth_refresh_already_attempted_reconcile_only')
        claim(name,{'action':'existing_credential_refresh','old_expiration_epoch':expiry,'time_epoch':time.time()})
        journal(name,{'stage':'refresh_intent','attempts':1,'old_expiration_epoch':expiry})
        try:creds.refresh_access_token()
        except Exception as error:
            blocked=AuthRefreshUncertain(clean_message(str(error)));blocked.response=getattr(error,'response',None);raise blocked from error
        expiry=creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
        need(expiry>time.time()+300 and stat.S_IMODE(credential.stat().st_mode)==0o600,'refreshed_credential_invalid')
        journal(name,{'stage':'refresh_accepted','attempts':1,'expiration_epoch':expiry,'time_epoch':time.time(),'new_grant_created':False})
    token=creds.get_access_token();need(isinstance(token,str) and bool(token),'auth_token_missing')
    return token,expiry

class Provider:
    """Official SDK; all methods are explicit and quota APIs are absent."""
    def __init__(self):
        from kagglesdk import KaggleClient,KaggleCredentials
        self.mutation_counts={}
        with KaggleClient() as initial:
            bound_sdk_client(initial,self.mutation_counts)
            token,self.access_expires_epoch=existing_token(initial)
        self.client=KaggleClient(api_token=token);self.client.__enter__();del token
        bound_sdk_client(self.client,self.mutation_counts)
        from kagglesdk.common.types.http_redirect import HttpRedirect
        original=self.client.http_client()._prepare_response
        def prepare(kind,response):
            if kind is HttpRedirect and 200<=response.status_code<400:return response
            return original(kind,response)
        self.client.http_client()._prepare_response=prepare
    def ensure_read_auth(self):
        """Normal renewal of the existing approved credential; no new grant or scope."""
        if time.time()+300 < self.access_expires_epoch:return
        from kagglesdk import KaggleClient,KaggleCredentials
        # A separate durable one-attempt guard; resource mutation counters never reset.
        with KaggleClient() as initial:
            bound_sdk_client(initial,{})
            token,expiry=existing_token(initial)
        old=self.client;replacement=KaggleClient(api_token=token);replacement.__enter__();del token
        bound_sdk_client(replacement,self.mutation_counts)
        from kagglesdk.common.types.http_redirect import HttpRedirect
        original=replacement.http_client()._prepare_response
        def prepare(kind,response):
            if kind is HttpRedirect and 200<=response.status_code<400:return response
            return original(kind,response)
        replacement.http_client()._prepare_response=prepare
        self.client=replacement;self.access_expires_epoch=expiry;old.__exit__(None,None,None)
        event('read-auth-client-renewed',{'expiration_epoch':expiry,'time_epoch':time.time(),'resource_mutation_counters_preserved':True})
    def close(self):self.client.__exit__(None,None,None)
    def dataset(self):
        self.ensure_read_auth()
        from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest
        r=ApiGetDatasetRequest();r.owner_slug='danielwuu';r.dataset_slug=DREF.split('/')[1]
        return self.client.datasets.dataset_api_client.get_dataset(r)
    def kernel(self):
        self.ensure_read_auth()
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        r=ApiGetKernelRequest();r.user_name='danielwuu';r.kernel_slug=REF.split('/')[1]
        return self.client.kernels.kernels_api_client.get_kernel(r)
    def status(self):
        self.ensure_read_auth()
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionStatusRequest
        r=ApiGetKernelSessionStatusRequest();r.user_name='danielwuu';r.kernel_slug=REF.split('/')[1]
        return self.client.kernels.kernels_api_client.get_kernel_session_status(r)
    def list_files(self, dataset=False, version=27):
        from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetFilesRequest
        from kagglesdk.kernels.types.kernels_api_service import ApiListKernelFilesRequest
        need(dataset is True,'whole_kernel_inventory_not_supported')
        token='';tokens=set();rows={}
        for page in range(100):
            self.ensure_read_auth()
            if dataset:
                r=ApiListDatasetFilesRequest();r.owner_slug='danielwuu';r.dataset_slug=DREF.split('/')[1];r.dataset_version_number=version
            else:
                r=ApiListKernelFilesRequest();r.user_name='danielwuu';r.kernel_slug=REF.split('/')[1];r.version_label=str(version)
            r.page_size=200
            if token:r.page_token=token
            out=self.client.datasets.dataset_api_client.list_dataset_files(r) if dataset else self.client.kernels.kernels_api_client.list_kernel_files(r)
            if dataset:need(not out.error_message,'provider_file_listing_error')
            for f in out.dataset_files if dataset else out.files:
                relative(f.name);need(f.name not in rows,'duplicate_provider_file');rows[f.name]=f.total_bytes if dataset else f.size
                need(type(rows[f.name])is int and rows[f.name]>=0 and len(rows)<=20000,'provider_inventory_cap')
            token=out.next_page_token
            if not token:return rows
            need(token not in tokens,'pagination_loop');tokens.add(token)
        raise GuardError('provider_pagination_cap')
    def output(self,name):
        self.ensure_read_auth()
        from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest
        r=ApiDownloadKernelOutputRequest();r.owner_slug='danielwuu';r.kernel_slug=REF.split('/')[1];r.version_number=27;r.file_path=name
        return self.client.kernels.kernels_api_client.download_kernel_output(r)
    def dataset_download(self,name=None):
        self.ensure_read_auth()
        from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
        r=ApiDownloadDatasetRequest();r.owner_slug='danielwuu';r.dataset_slug=DREF.split('/')[1];r.dataset_version_number=14
        if name:r.file_name=name;r.raw=True
        return self.client.datasets.dataset_api_client.download_dataset(r)
    def start_upload(self,path):
        from kagglesdk.blobs.types.blob_api_service import ApiStartBlobUploadRequest,ApiBlobType
        r=ApiStartBlobUploadRequest();r.type=ApiBlobType.DATASET;r.name=path.name;r.content_type='application/zip';r.content_length=path.stat().st_size
        return self.client.blobs.blob_api_client.start_blob_upload(r)
    def version(self,token,notes):
        from kagglesdk.datasets.types.dataset_api_service import ApiCreateDatasetVersionByIdRequest,ApiCreateDatasetVersionRequestBody,ApiDatasetNewFile
        f=ApiDatasetNewFile();f.token=token;b=ApiCreateDatasetVersionRequestBody();b.files=[f];b.delete_old_versions=False;b.version_notes=notes
        r=ApiCreateDatasetVersionByIdRequest();r.id=12504696;r.body=b
        return self.client.datasets.dataset_api_client.create_dataset_version_by_id(r)
    def save(self, wire):
        from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        r=ApiSaveKernelRequest()
        for k,v in wire.items():
            if k=='kernel_execution_type':v=KernelExecutionType(v)
            if v is not None:setattr(r,k,v)
        return self.client.kernels.kernels_api_client.save_kernel(r)

def _binary_get(response,dest,cap,expected=None,expected_size=None):
    """Signed URL is consumed only in RAM; no credential forwarding or redirect guessing."""
    import requests
    dest=secure_path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        need(expected is not None and file_sha(dest)==expected and (expected_size is None or dest.stat().st_size==expected_size),'unverified_download_cache');return descriptor(dest)
    partial=dest.with_name(dest.name+'.partial');secure_path(partial)
    if partial.exists():
        q=dest.parent/'quarantined-partials';q.mkdir(exist_ok=True);secure_path(q);partial.rename(q/(partial.name+'.'+uuid.uuid4().hex))
    need(shutil.disk_usage(dest.parent).free>=RESERVE+cap,'download_disk_reserve')
    url=response.headers.get('Location')
    if url is None and 'json' in response.headers.get('Content-Type',''):
        need(int(response.headers.get('Content-Length','0'))<=1024**2,'redirect_response_cap')
        need(len(response.content)<=1024**2,'redirect_response_body_cap')
        data=response.json();url=data.get('url') if isinstance(data,dict) else None
    session=None
    try:
        if url:
            response.close();session=no_retry_session(requests.Session())
            for _ in range(5):
                safe_url(url);req=requests.Request('GET',url,headers={'Accept-Encoding':'identity'}).prepare()
                need('Authorization' not in req.headers and 'Cookie' not in req.headers,'credential_forwarding')
                kw=session.merge_environment_settings(url,{},None,None,None);kw.update(stream=True,timeout=(15,120),allow_redirects=False)
                response=session.send(req,**kw)
                if response.status_code in (301,302,303,307,308):
                    nxt=response.headers.get('Location');need(bool(nxt),'redirect_location_missing');url=urljoin(url,nxt);response.close();continue
                break
            else:raise GuardError('redirect_limit')
        response.raise_for_status();need(response.status_code==200,'download_status')
        declared=response.headers.get('Content-Length');need(declared is None or 0<=int(declared)<=cap,'download_declared_cap')
        h=hashlib.sha256();n=0
        with partial.open('xb') as f:
            for b in response.iter_content(65536):
                n+=len(b);need(n<=cap and shutil.disk_usage(dest.parent).free>=RESERVE,'download_stream_cap_or_reserve');f.write(b);h.update(b)
        need(expected is None or h.hexdigest()==expected,'download_hash_mismatch');need(expected_size is None or n==expected_size,'download_size_mismatch')
        need(not dest.exists(),'download_destination_race');partial.rename(dest);sync_directory(dest.parent)
        return descriptor(dest)
    finally:
        response.close()
        if session:session.close()

def _upload_once(url,path):
    import requests
    safe_url(url,upload=True)
    with no_retry_session(requests.Session()) as session, secure_path(path).open('rb') as f:
        request=requests.Request('PUT',url,data=f,headers={'Content-Type':'application/zip','Content-Length':str(path.stat().st_size)}).prepare()
        need('Authorization' not in request.headers and 'Cookie' not in request.headers,'upload_credential_forwarding')
        kw=session.merge_environment_settings(url,{},None,None,None);kw.update(timeout=(15,180),allow_redirects=False,stream=True)
        response=session.send(request,**kw)
        try:
            response.raise_for_status();need(response.status_code in (200,201),'upload_incomplete_no_retry')
            total=0
            for block in response.iter_content(65536):total+=len(block);need(total<=1024**2,'upload_response_cap')
        finally:response.close()


def binary_get(response,dest,cap,expected=None,expected_size=None):
    try:
        with wall_bound(900):return _binary_get(response,dest,cap,expected,expected_size)
    finally:response.close()

def upload_once(url,path):
    with wall_bound(600):return _upload_once(url,path)


def binary_metadata(response, expected_size, cap):
    """Verify a numeric-output response's size/presence without consuming its body."""
    import requests
    session=None
    try:
        need(type(expected_size)is int and 0<=expected_size<=cap,'metadata_expected_size_cap')
        with wall_bound(120):
            url=response.headers.get('Location')
            if url is None and 'json' in response.headers.get('Content-Type',''):
                need(len(response.content)<=1024**2,'metadata_redirect_response_cap')
                data=response.json();url=data.get('url') if isinstance(data,dict) else None
            if url:
                response.close();session=no_retry_session(requests.Session())
                for _ in range(5):
                    safe_url(url);request=requests.Request('GET',url,headers={'Accept-Encoding':'identity'}).prepare()
                    need('Authorization' not in request.headers and 'Cookie' not in request.headers,'metadata_credential_forwarding')
                    kw=session.merge_environment_settings(url,{},None,None,None);kw.update(stream=True,timeout=(15,90),allow_redirects=False)
                    response=session.send(request,**kw)
                    if 300<=response.status_code<400 and response.headers.get('Location'):
                        next_url=urljoin(url,response.headers['Location']);response.close();url=next_url;continue
                    break
                else:raise GuardError('metadata_redirect_limit')
            response.raise_for_status();need(response.status_code==200,'checkpoint_metadata_http_status')
            length=response.headers.get('Content-Length')
            need(length is not None and int(length)==expected_size and 0<=int(length)<=cap,'checkpoint_metadata_length')
            need(response.headers.get('Content-Encoding','identity') in ('','identity'),'checkpoint_metadata_encoding')
            return {'http_status':200,'bytes':int(length),'body_consumed_bytes':0,'archive_bytes_verified':False,'scope':'numeric output request; Content-Length and successful response only'}
    finally:
        response.close()
        if session:session.close()
