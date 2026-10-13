"""Independent worst-case shape arithmetic; no model weights or allocation."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SOURCE=HERE.parent/'final-source-freeze-001'
p=SOURCE/'materials/qwen14b/expected-tensor-inventory.json';inventory=json.loads(p.read_text())['tensors']
weights=[(k,v['shape']) for k,v in inventory.items() if '.layers.' in k and len(v['shape'])==2]
if len(weights)!=280:raise RuntimeError('280 fixed projections required')
rank=8;adapter=sum(rank*(rows+cols)*4 for name,(rows,cols) in weights)
largest=max(rank*max(shape)*4 for name,shape in weights)
shard=32*1024**2;payload=31*1024**2;jsoncap=8*1024**2;small=64*1024
worst_groups=lambda n:math.ceil(n/(payload-largest))
rows=[]
for label,copies in [('base',1),('sft64',3),('sft256',3),('representative_ttt16',4)]:
    tensor=adapter*copies+small;groups=worst_groups(adapter)+worst_groups(adapter*(copies-1)+small)
    total=tensor+groups*(shard-payload)+4*jsoncap
    if total>768*1024**2:raise RuntimeError('per-checkpoint cap')
    rows.append({'label':label,'tensor_upper_bytes':tensor,'shards_upper':groups,'serialized_upper_bytes':total,
                 'file_count_upper':groups+4,'tensor_count_upper':560*copies+560+4})
    if rows[-1]['file_count_upper']>128 or rows[-1]['tensor_count_upper']>10000:raise RuntimeError('file/tensor caps')
store=sum(r['serialized_upper_bytes'] for r in rows)+3*jsoncap+64
if store>=2*1024**3:raise RuntimeError('store cap')
authored=json.loads((HERE.parent/'evidence/production-capacity-audit.json').read_text())
if authored['store_upper_bytes']!=store:raise RuntimeError('independent bound disagrees')
receipt={'format':'irisx/independent-production-checkpoint-capacity-v1','status':'passed','shape_only':True,
 'pretrained_weights_loaded':False,'adapter_bytes':adapter,'largest_tensor_bytes':largest,'checkpoints':rows,
 'store_upper_bytes':store,'store_limit_bytes':2*1024**3,'store_headroom_bytes':2*1024**3-store,
 'inventory_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'assumptions':['Original rank8 FP32 LoRA over280 projections','Two FP32 Adam moments and scalar steps','Representative TTT includes selected-global adapter snapshot','Conservative64KiB allowance per checkpoint for RNG/scalar tensors','No deduplication credit; source hard JSON/shard bounds retained'],
 'limits':'Analytical capacity proof, not measured production disk use, BF16 GPU fit, or model correctness.'}
(HERE/'capacity-independent.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
