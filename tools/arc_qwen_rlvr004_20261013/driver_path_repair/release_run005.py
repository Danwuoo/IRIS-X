"""Closed source release admission. Caller JSON is never review or launch authority.

These unfilled source constants intentionally prohibit production in this candidate.
A separately reviewed source revision, not runtime flags, must freeze final costs.
"""
from pathlib import Path
import hashlib, json, os, stat, sys
from . import ROOT

# Self-consistency only, never independent review authority.
# Deliberately absent. Never populated from a request, environment variable or receipt.
NORMALIZED_SOURCE_CONTRACT_SHA256 = '895dc6f18cae4ad14d7887743faee721c2f1c5fd67b3426f11b0bd56eae4f840'
FINAL_V25_POLICY_SHA256 = '3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda'
REVIEWED_ENVIRONMENT_SHA256 = '0f7133bdb22d8cba124537622ab09a98e9450e1649df1b07d4e6661d48e33e28'
SOURCE_DIRECTORIES=('baseline','rl_session','reviewed','experiment_flow','owned_runtime','validation')
NONEXECUTABLE=('design/LEAD-EXPERIMENT-DECISIONS.json','independent-protocol-review/PROVISIONAL-DEFAULTS.json','independent-protocol-review/PROTOCOL-REVIEW.md','design/MEASURED-POLICY.json','design/COST-EVIDENCE.json')

def need(ok,message):
    if not ok:raise ValueError(message)

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def file_sha(p):
    result=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):result.update(block)
    return result.hexdigest()

def inventory(root=ROOT):
    root=Path(root).resolve(); result={}
    for name in SOURCE_DIRECTORIES:
        for p in sorted((root/name).rglob('*')):
            need(not p.is_symlink(),'source symlink forbidden: '+str(p))
            if p.is_dir():continue
            need(stat.S_ISREG(p.lstat().st_mode),'regular source only')
            if '__pycache__' not in p.parts:
                # Baseline's original200 contains authenticated tokenizer/config
                # material, never native model tensors or task/evaluator archives.
                if name=='baseline' or p.suffix=='.py':result[p.relative_to(root).as_posix()]=file_sha(p)
    for name in NONEXECUTABLE:
        p=root/name;need(p.is_file() and not p.is_symlink(),'source policy absent')
        result[name]=file_sha(p)
    need(result,'nonempty closed source')
    return dict(sorted(result.items()))

def source_digest(files):return sha(canonical(sorted(files.items())))

def verify_inventory(expected,root=ROOT):
    need(type(expected) is dict and inventory(root)==expected,'closed source inventory differs (unknown, missing or changed file)')
    return source_digest(expected)

def source_freeze(root=ROOT):
    from experiment_flow.contracts import SourceFreeze
    return SourceFreeze(str(Path(root).resolve()),tuple(inventory(root).items()))

def review_digest(files):
    # The self-consistency pin cannot hash its own filled-in literal. Normalize
    # exactly that one assignment, while the actual source manifest still pins
    # the complete unmodified release.py bytes and all other release constants.
    import re
    verify_inventory(files)
    path='owned_runtime/release.py';raw=(ROOT/path).read_bytes()
    normalized,count=re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = (?:None|'[0-9a-f]{64}')$",
                             b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',raw)
    need(count==1,'one closed release review pin assignment required')
    bound=dict(files);bound[path]=sha(normalized)
    return source_digest(bound)


class ExternalReleaseCapability:
    """Reserved boundary for later independently reviewed outer assembly.

    The exact checked-bootstrap issuer owns the registry. A JSON Boolean, local
    self-pin or object.__new__ token cannot populate it. External approval is
    independently bound to published outer bytes by the offline review chain.
    """
    def __new__(cls,*args,**kwargs):
        raise TypeError('use the exact source-owned reviewed bootstrap issuer')
    def __reduce__(self):
        raise TypeError('release authority cannot be serialized')
    def __copy__(self):
        raise TypeError('release authority cannot be copied')
    def __deepcopy__(self,memo):
        raise TypeError('release authority cannot be copied')

_EXTERNAL_RELEASES={}


def check_production_pins(files, *, policy_path, environment_path):
    digest=verify_inventory(files)
    need(NORMALIZED_SOURCE_CONTRACT_SHA256 is not None and FINAL_V25_POLICY_SHA256 is not None and REVIEWED_ENVIRONMENT_SHA256 is not None,
         'source-review-only candidate: final source contract, v25 cost freeze and environment bindings absent')
    from rl_session.plan import production_numeric_gate
    need(production_numeric_gate().maximum_batch_replay_backward_seconds is not None,'source-bound cumulative replay/backward budget awaits v25 freeze')
    need(review_digest(files)==NORMALIZED_SOURCE_CONTRACT_SHA256,'normalized source self-consistency contract differs')
    need(file_sha(policy_path)==FINAL_V25_POLICY_SHA256 and file_sha(environment_path)==REVIEWED_ENVIRONMENT_SHA256,'source-pinned policy/environment differs')
    return digest


def require_production_release(files, *, policy_path, environment_path, external_release=None):
    digest=check_production_pins(files,policy_path=policy_path,environment_path=environment_path)
    owned=_EXTERNAL_RELEASES.get(id(external_release))
    need(type(external_release) is ExternalReleaseCapability and owned is not None and owned.get('capability') is external_release and
         owned.get('raw_source_sha256')==digest and owned.get('pid')==os.getpid() and owned.get('scope')=='production-rl-abc',
         'reviewed outer bootstrap capability absent; normalized self-consistency is not approval')
    return digest

def closed_bootstrap(root=ROOT):
    root=Path(root).resolve()
    # Remove inherited cwd/sys.path aliases before importing any nested baseline.
    allowed=[str(root),str(root/'baseline'),str(root/'baseline/src')]
    external=[]
    for entry in sys.path:
        if not entry:continue
        p=Path(entry).resolve()
        if p==root or p.is_relative_to(root):continue
        if 'site-packages' in p.parts or 'python' in p.name or p.name=='lib-dynload':external.append(entry)
    sys.path[:]=allowed+external
    sys.dont_write_bytecode=True
    return allowed
