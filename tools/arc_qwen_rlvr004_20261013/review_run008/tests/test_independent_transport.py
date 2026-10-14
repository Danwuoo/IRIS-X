"""Independent offline rejection/cleanup probes; fixtures never grant publication."""
from pathlib import Path
import hashlib, importlib.util, importlib, json, os, py_compile, signal, sys, tempfile, time, types, unittest
ROOT=Path(__file__).absolute().parents[4]
(ROOT/'.irisx/run008-launch-review/public-test-scratch').mkdir(parents=True,exist_ok=True)
PACKAGE=ROOT/'tools/arc_qwen_rlvr004_20261013/publication_run008'
def load(name,path):
    module=types.ModuleType(name);module.__file__=str(path);module.__package__='';sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(module));return module
common=load('independent_run008_common',PACKAGE/'operator_common.py')
auth=load('independent_run008_auth',PACKAGE/'native_auth.py')
class Response:
    headers={'Content-Type':'application/json','Content-Length':'2'};status_code=200
    def iter_content(self,chunk):yield b'{}'
    def close(self):self.closed=True
class Session:
    def __init__(self):self.calls=[]
    def mount(self,*args):pass
    def send(self,request,**kw):self.calls.append((request.url,kw));return Response()
class RpcChecks(unittest.TestCase):
    def setUp(self):
        self.session=Session();self.counts={}
        common.bound_sdk_client(types.SimpleNamespace(http_client=lambda:types.SimpleNamespace(_session=self.session)),self.counts)
    def request(self,operation,origin='https://api.kaggle.com/v1/kernels.KernelsApiService/'):
        return self.session.send(types.SimpleNamespace(url=origin+operation,method='POST'),stream=False)
    def test_unknown_mutation_fails_before_network(self):
        for op in ['DeleteKernel','CreateDataset','CancelKernelSession','GetGpuQuota','GetKernelSessionStatus?x=1']:
            if '?' in op: continue
            with self.assertRaises(common.GuardError):self.request(op)
        self.assertEqual(self.session.calls,[])
    def test_official_origin_only(self):
        for origin in ['http://api.kaggle.com/v1/','https://evil.test/v1/','https://api.kaggle.com:444/v1/','https://user@api.kaggle.com/v1/','https://api.kaggle.com/v2/']:
            with self.assertRaises(common.GuardError):self.request('GetKernel',origin)
        self.assertEqual(self.session.calls,[])
    def test_one_mutation_count_shared_read_retries_allowed(self):
        self.request('SaveKernel')
        with self.assertRaises(common.GuardError):self.request('SaveKernel')
        self.request('GetKernel');self.request('GetKernel')
        self.assertEqual(len(self.session.calls),3)
        self.assertEqual(self.counts,{'SaveKernel':1})
        for _,kw in self.session.calls:self.assertEqual(kw['allow_redirects'],False);self.assertEqual(kw['timeout'],(15,90))
    def test_timeout_restores_signal_state(self):
        old=signal.getsignal(signal.SIGALRM)
        with self.assertRaises(common.WallTimeout):
            with common.wall_bound(.02):time.sleep(.20)
        self.assertEqual(signal.getsignal(signal.SIGALRM),old)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_signed_storage_restrictions(self):
        for value in ['http://storage.googleapis.com/x','https://evil.test/x','https://user@storage.googleapis.com/x','https://storage.googleapis.com:444/x','https://storage.googleapis.com/x#fragment']:
            with self.assertRaises(common.GuardError):common.safe_url(value)
        common.safe_url('https://storage.googleapis.com/x?signature=synthetic')
class FinderChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'.irisx/run008-launch-review/public-test-scratch');self.root=Path(self.tmp.name)
        self.pkg=self.root/'kagglesdk';self.pkg.mkdir();self.source=self.pkg/'__init__.py'
        sys.path.insert(0,str(self.root));self.before=list(sys.meta_path)
    def tearDown(self):
        sys.meta_path[:]=self.before;sys.path.remove(str(self.root));sys.modules.pop('kagglesdk',None);self.tmp.cleanup()
    def finder(self):
        return auth.ReviewedSdkFinder(self.root,{'kagglesdk/__init__.py':hashlib.sha256(self.source.read_bytes()).hexdigest()},vars(common))
    def test_timestamp_valid_foreign_bytecode_cannot_execute(self):
        self.source.write_text('VALUE = "wrong"\n');before=self.source.stat()
        py_compile.compile(str(self.source),doraise=True)
        self.source.write_text('VALUE = "right"\n');os.utime(self.source,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(len('VALUE = "wrong"\n'),len('VALUE = "right"\n'))
        sys.meta_path.insert(0,self.finder());module=importlib.import_module('kagglesdk')
        self.assertEqual(module.VALUE,'right')
    def test_source_change_after_finder_creation_rejected(self):
        self.source.write_text('VALUE = "right"\n');finder=self.finder();self.source.write_text('VALUE = "wrong"\n')
        sys.meta_path.insert(0,finder)
        with self.assertRaises(common.GuardError):importlib.import_module('kagglesdk')
        self.assertNotIn('kagglesdk',sys.modules)
    def test_unpinned_submodule_rejected(self):
        self.source.write_text('');(self.pkg/'hidden.py').write_text('VALUE = "bad"\n');sys.meta_path.insert(0,self.finder())
        with self.assertRaises(common.GuardError):importlib.import_module('kagglesdk.hidden')
if __name__=='__main__':unittest.main(verbosity=2)
