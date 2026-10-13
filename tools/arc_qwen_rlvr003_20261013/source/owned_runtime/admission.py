"""One-use process-owned native/calibration/session grants; never imported from JSON."""
from dataclasses import dataclass
import os, time, uuid
from .release import need, canonical, sha, verify_inventory

@dataclass(frozen=True)
class _SessionGrant:
    identity: str

_REGISTRY={}

def _issue(native,trainer,ledger,clock,sources,plan_sha256,calibration_sha256, *, fixture,owner_request_sha256=None):
    # The private builder is a source-owned call site, not a public mint API.
    import inspect
    from .factory import _construct
    need(inspect.currentframe().f_back.f_code is _construct.__code__,'grant only from owned factory construction')
    verify_inventory(sources)
    need(type(fixture) is bool and native.tiny_cpu is fixture,'grant native scope')
    if not fixture:
        from .factory import _verify_production_native
        _verify_production_native(native,trainer,calibration_sha256)
    grant=_SessionGrant(uuid.uuid4().hex)
    _REGISTRY[id(grant)]={'grant':grant,'native':native,'trainer':trainer,'ledger':ledger,'clock':clock,
        'sources':dict(sources),'plan_sha256':plan_sha256,'calibration_sha256':calibration_sha256,
        'pid':os.getpid(),'fixture':fixture,'consumed':False,'owner_request_sha256':owner_request_sha256}
    return grant

def consume(grant,native,trainer,global_deadline,fixture):
    from rl_session.actor import NativeActor
    import inspect
    need(inspect.currentframe().f_back.f_code is NativeActor.__init__.__code__,'grant consumed only by native actor initializer')
    record=_REGISTRY.get(id(grant))
    need(type(grant) is _SessionGrant and record is not None and record['grant'] is grant,'unknown production grant')
    need(not record['consumed'] and record['pid']==os.getpid(),'grant already consumed or different process')
    need(record['native'] is native and record['trainer'] is trainer and record['fixture'] is fixture,'grant backend identities differ')
    need(global_deadline==record['clock'].deadline('inner'),'grant deadline differs from original epoch')
    record['clock'].check_mapping();verify_inventory(record['sources'])
    need(time.monotonic()<global_deadline,'original inner clock expired before grant consumption')
    record['consumed']=True
    return record['ledger']

def revoke(grant):
    record=_REGISTRY.pop(id(grant),None)
    if record:record.clear()

def public_receipt(grant):
    record=_REGISTRY.get(id(grant));need(record is not None and record['grant'] is grant,'unknown grant')
    return {'format':'owned-session-admission-v1','grant_id':grant.identity,'pid':record['pid'],
        'scope':'native-tiny-CPU-fixture' if record['fixture'] else 'source-admitted-pretrained-session',
        'consumed':record['consumed'],'plan_sha256':record['plan_sha256'],
        'source_sha256':sha(canonical(sorted(record['sources'].items()))),
        'calibration_sha256':record['calibration_sha256'],'owner_request_sha256':record['owner_request_sha256'],'clock':record['clock'].receipt(),
        'RL_commit_admitted':False,'commit_gate':'first/current full audit original-token replay+backward in this session'}
