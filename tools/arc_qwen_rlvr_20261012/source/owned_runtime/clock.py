"""Original pre-dispatch epoch mapped once to this boot's monotonic clock."""
from dataclasses import dataclass
import math, time
from types import MappingProxyType
OFFSETS = MappingProxyType({'inner':42000., 'outer':42180., 'provider':42300., 'absolute':43200.})

def need(ok, message):
    if not ok: raise ValueError(message)

def finite(x):
    return type(x) in (float,int) and math.isfinite(x)

@dataclass(frozen=True)
class OriginalClock:
    original_epoch: float
    origin_monotonic: float
    observed_epoch: float
    observed_monotonic: float
    session_id: str
    fixture: bool = False

    def __post_init__(self):
        self._invariants()

    def _invariants(self):
        need(all(finite(getattr(self,k)) for k in ('original_epoch','origin_monotonic','observed_epoch','observed_monotonic')),'finite original clock identity')
        need(0<self.original_epoch<=self.observed_epoch,'valid original epoch identity')
        need(abs(self.origin_monotonic-(self.observed_monotonic-(self.observed_epoch-self.original_epoch)))<=1e-6,'original epoch mapping cannot be extended')
        need(type(self.fixture) is bool and type(self.session_id) is str and 1<=len(self.session_id)<=128,'clock identity/scope')

    @classmethod
    def create(cls, original_epoch, session_id, *, wall=time.time, monotonic=time.monotonic, fixture=False):
        before=monotonic(); epoch=wall(); after=monotonic()
        need(all(finite(x) for x in (original_epoch,before,epoch,after)), 'finite original clock')
        need(0 < original_epoch <= epoch and 0<=after-before<=1., 'future origin or unstable clock sample')
        need(type(session_id) is str and 1<=len(session_id)<=128, 'bounded session identity')
        need(type(fixture) is bool, 'explicit fixture scope')
        # Earlier bracket endpoint is conservative: sampling latency never grants time.
        result=cls(float(original_epoch),before-(epoch-original_epoch),epoch,before,session_id,fixture)
        result.check_mapping(wall=wall,monotonic=monotonic)
        return result

    @classmethod
    def from_receipt(cls, receipt):
        need(type(receipt) is dict and set(receipt)=={'format','original_epoch','origin_monotonic','observed_epoch','observed_monotonic','session_id','fixture','offsets'}, 'closed clock receipt')
        need(receipt['format']=='owned-rl-original-clock-v1' and receipt['offsets']==OFFSETS,'original clock offsets differ')
        obj=cls(**{k:receipt[k] for k in cls.__dataclass_fields__})
        need(all(finite(getattr(obj,k)) for k in ('original_epoch','origin_monotonic','observed_epoch','observed_monotonic')), 'finite mapped clock')
        need(obj.original_epoch>0 and obj.observed_epoch>=obj.original_epoch and abs(obj.origin_monotonic-(obj.observed_monotonic-(obj.observed_epoch-obj.original_epoch)))<=1e-6,'epoch monotonic mapping differs')
        need(type(obj.fixture) is bool and type(obj.session_id) is str and obj.session_id,'clock scope and identity')
        obj.check_mapping()
        return obj

    def deadline(self, kind='inner'):
        self._invariants()
        need(kind in OFFSETS,'unknown clock boundary')
        return self.origin_monotonic+OFFSETS[kind]

    def check_mapping(self, *, wall=time.time, monotonic=time.monotonic):
        self._invariants()
        now=monotonic(); epoch=wall()
        need(finite(now) and finite(epoch),'finite live clock')
        need(now>=self.observed_monotonic-1e-3, 'different boot or backwards monotonic clock')
        need(abs((epoch-self.observed_epoch)-(now-self.observed_monotonic))<=2., 'wall monotonic mapping drift')
        return now

    def receipt(self):
        return {'format':'owned-rl-original-clock-v1', **vars(self), 'offsets':dict(OFFSETS)}
