"""Reviewed outside-in entry. This file must itself be pinned by the publisher.

Acyclic release: publisher pins this entry; it pins external operator bytes;
operator pins collector and helper inventory. Neither is in producer inventory.
None means pending independent review and is a hard production block.
"""
from pathlib import Path
import hashlib, importlib.util, importlib.abc, importlib, inspect, json, math, sys, types, weakref

REVIEWED_OPERATOR_PINS_SHA256 = 'c9b5c454ec31cb78ff41abf7ef39d79868fc8c5e338f1dc6a3faaecf153eda34'
_CONTEXTS=weakref.WeakKeyDictionary()
ROOT=Path(__file__).resolve().parent


def need(value,message):
    if not value:raise ValueError(message)
def is_sha(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def file_sha(path,limit=5*1024**3+16*1024**2):
    path=Path(path).absolute();need(all(not p.is_symlink() for p in (path,*path.parents)) and path.is_file(),'regular reviewed file required')
    need(path.stat().st_size<=limit,'bounded reviewed file required');before=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    after=path.stat();need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'reviewed bytes changed while hashing')
    return h.hexdigest()
def read(path):
    path=Path(path);need(path.stat().st_size<=16*1024**2,'bounded review JSON required')
    def pairs(rows):
        result={}
        for k,v in rows:need(k not in result,'duplicate review key');result[k]=v
        return result
    def number(v):
        n=float(v);need(math.isfinite(n),'finite review numbers');return n
    return json.loads(path.read_bytes(),object_pairs_hook=pairs,parse_float=number,
                      parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite review JSON')))

def _codes(code):
    yield code
    for item in code.co_consts:
        if isinstance(item,types.CodeType):yield from _codes(item)

class CollectionContext:
    __slots__=('__weakref__',)
    def __new__(cls,*args,**kwargs):raise TypeError('reviewed actual collector context required')
    def __reduce__(self):raise TypeError('collection authority is not serializable')


def receive_authenticated_collection(path,expected_sha256,*,operator_pins_path):
    """Called only from independently pinned collector after actual transport."""
    need(is_sha(REVIEWED_OPERATOR_PINS_SHA256),'independently reviewed operator pin is pending')
    need(file_sha(operator_pins_path,16*1024**2)==REVIEWED_OPERATOR_PINS_SHA256,'external operator pin bytes differ')
    pins=read(operator_pins_path)
    pin_fields={'format','source_sha256','source_archive_sha256','policy_sha256','release_sha256',
                'collector_entry_sha256','helper_inventory_sha256'}
    need(set(pins)==pin_fields and pins['format']=='owned-rl-batched-consumer-operator-v1'
         and all(is_sha(pins[k]) for k in pin_fields-{'format'}),'closed external operator pin schema')
    frame=inspect.currentframe().f_back;filename=Path(frame.f_code.co_filename)
    need(file_sha(filename,16*1024**2)==pins['collector_entry_sha256'],'authenticated expectation requires reviewed collector callsite')
    compiled=compile(filename.read_bytes(),str(filename),'exec',dont_inherit=True,optimize=sys.flags.optimize)
    need(any(frame.f_code==code for code in _codes(compiled)),'actual reviewed collector code object required')
    need(is_sha(expected_sha256) and file_sha(path,16*1024**2)==expected_sha256,'authenticated actual collection envelope bytes differ')
    body=read(path)
    fields={'format','source_sha256','source_archive_sha256','policy_sha256','release_sha256','launch_sha256',
            'artifact_inventory_sha256','dataset_sha256','archive_sha256','terminal_sha256',
            'owner_request_sha256','outer_closure_sha256','checkpoint_archive_observation'}
    need(set(body)==fields and body['format']=='owned-rl-batched-authenticated-collection-v1'
         and all(is_sha(body[k]) for k in fields-{'format','checkpoint_archive_observation'}),
         'closed complete authenticated collection envelope')
    for key in ('source_sha256','source_archive_sha256','policy_sha256','release_sha256'):
        need(body[key]==pins[key],'collection differs from independently reviewed '+key)
    context=object.__new__(CollectionContext)
    _CONTEXTS[context]={'path':str(Path(path).absolute()),'sha256':expected_sha256,'body':body,
                      'pins':pins,'pins_path':str(Path(operator_pins_path).absolute())}
    return context


def _load_helpers(expected_inventory_sha256):
    inventory=ROOT/'CONSUMER-INVENTORY.json'
    need(file_sha(inventory,16*1024**2)==expected_inventory_sha256,'reviewed helper inventory bytes differ before imports')
    document=read(inventory);need(set(document)=={'format','files'} and document['format']=='owned-rl-batched-consumer-helpers-v1','closed helper inventory')
    files=document['files'];need(type(files) is dict and files,'complete helper file inventory')
    actual={}
    for path in sorted(ROOT.rglob('*.py')):
        need(not path.is_symlink(),'helper symlink forbidden')
        relative=path.relative_to(ROOT).as_posix()
        if '__pycache__' in path.parts or relative=='reviewed_entry.py' or relative.startswith('tests/'):continue
        actual[relative]=file_sha(path,16*1024**2)
    need(files==actual and all(is_sha(v) for v in files.values()),'unknown/missing/changed helper bytes before import')
    name='_owned_batched_consumer_'+expected_inventory_sha256
    need(not any(k==name or k.startswith(name+'.') for k in sys.modules),'fresh reviewed consumer process required; ambient module reuse forbidden')
    # Compile the authenticated .py bytes ourselves. SourceFileLoader and -B
    # still permit reads of attacker-controlled timestamp-valid .pyc caches.
    class BoundSourceLoader(importlib.abc.Loader):
        def __init__(self,relative,is_package):self.relative=relative;self.is_package=is_package
        def create_module(self,spec):return None
        def exec_module(self,module):
            path=ROOT/self.relative
            need(file_sha(path,16*1024**2)==files[self.relative],'helper changed before source-only import')
            data=path.read_bytes();need(hashlib.sha256(data).hexdigest()==files[self.relative],'import source bytes differ')
            module.__file__=str(path);module.__cached__=None
            if self.is_package:module.__path__=[str(path.parent)]
            exec(compile(data,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),module.__dict__)
    class BoundSourceFinder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname!=name and not fullname.startswith(name+'.'):return None
            relative=fullname[len(name):].lstrip('.').replace('.','/')
            package=(relative+'/' if relative else '')+'__init__.py'
            leaf=relative+'.py'
            if package in files:selected,is_package=package,True
            elif leaf in files:selected,is_package=leaf,False
            else:raise ModuleNotFoundError('unreviewed consumer module: '+fullname)
            spec=importlib.util.spec_from_loader(fullname,BoundSourceLoader(selected,is_package),is_package=is_package)
            spec.origin=str(ROOT/selected);return spec
    sys.meta_path.insert(0,BoundSourceFinder())
    return importlib.import_module(name+'.production').validate_received_collection


def validate_reviewed(context,*,archive_path,terminal_path,output_root,source_root,release_root):
    """Production-only compact mode. No caller fixture override or fake approval."""
    need(type(context) is CollectionContext and context in _CONTEXTS,'registered authenticated collection required')
    entry=_CONTEXTS[context]
    need(file_sha(entry['pins_path'],16*1024**2)==REVIEWED_OPERATOR_PINS_SHA256
         and file_sha(entry['path'],16*1024**2)==entry['sha256'],'authenticated review/collection changed')
    validator=_load_helpers(entry['pins']['helper_inventory_sha256'])
    result=validator(entry['body'],archive_path=archive_path,terminal_path=terminal_path,
                     output_root=output_root,source_root=source_root,release_root=release_root)
    accepted=result.get('evidence_valid') is True and result.get('release_content_binding_valid') is True
    result['authenticated_collection_verified']=True
    result['external_owner_envelope_verified']=result.get('release_content_binding_valid') is True
    result['production_admitted']=accepted
    result['operational_complete']=bool(accepted and result.get('phase_status',{}).get('owner_process_closed') is True)
    result['comparison_eligible']=bool(accepted and result.get('comparison_complete') is True and result.get('compute_matched') is True)
    public=result.get('public',{});metric=public.get('micro_pass_at_2',{})
    eligible=bool(accepted and public.get('status')=='SEALED_SCORER_ROWS_REPLAYED' and public.get('scorer_rows_complete') is True
        and type(metric.get('denominator')) is int and metric['denominator']==167 and type(metric.get('numerator')) is int
        and 0<=metric['numerator']<=167 and type(metric.get('value')) in (int,float) and math.isfinite(metric['value'])
        and abs(metric['value']-metric['numerator']/167)<=1e-12)
    result['public_benchmark_evidence_eligible']=eligible
    result['public_goal_met']=bool(eligible and metric['numerator']>=151 and public.get('metric_threshold_reached') is True)
    result['scientific_goal_met']=result['public_goal_met']
    if accepted:result['status']='REVIEWED_PRODUCTION_CONTENT_COMPLETE'
    return result
