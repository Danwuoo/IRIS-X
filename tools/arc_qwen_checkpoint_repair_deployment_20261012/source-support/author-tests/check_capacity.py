"""Source/shape-only production checkpoint capacity bound; no weight loading."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_portfolio_20261012.checkpoints import CheckpointLimits
p=ROOT/'worktree/materials/qwen14b/expected-tensor-inventory.json';inventory=json.loads(p.read_text())['tensors']
projections={k:v for k,v in inventory.items() if '.layers.' in k and len(v['shape'])==2}
assert len(projections)==280
A=sum(8*sum(v['shape'])*4 for v in projections.values())
max_tensor=max(8*max(v['shape'])*4 for v in projections.values())
limits=CheckpointLimits();payload=limits.shard_bytes-min(1024**2,limits.shard_bytes//8)
# Account without content dedup: all adapter and moments, plus full global
# snapshot at TTT. RNG upper allowance is deliberately larger than observed5072B;
# scalar Adam counters do not duplicate the model and fit within the same64KiB.
small=64*1024
def shards(n):return math.ceil(n/(payload-max_tensor)) if n else 0
rows=[]
for label,copies,resume_copies in [('base',1,0),('sft64',3,2),('sft256',3,2),('representative_ttt16',4,3)]:
    tensor=copies*A+small;count=shards(A)+shards(resume_copies*A+small)
    # Four bounded JSONs/version: adapter_config, inference index, resume state,
    # full manifest. Store and branch ownership JSONs are accounted separately.
    actual_upper=tensor+count*(limits.shard_bytes-payload)+4*limits.json_bytes
    projected=tensor+2*limits.json_bytes+limits.shard_bytes//8
    assert actual_upper<limits.checkpoint_bytes and projected<limits.checkpoint_bytes
    rows.append({'label':label,'tensor_upper_bytes':tensor,'shard_count_upper':count,
        'serialized_upper_bytes':actual_upper,'save_projection_upper_bytes':projected})
upper=sum(r['serialized_upper_bytes'] for r in rows)+3*limits.json_bytes+64
assert upper<limits.store_bytes
receipt={'format':'irisx/transfer-checkpoint-capacity-audit-v1','status':'passed','production_shape_only':True,
    'no_weights_loaded':True,'projection_modules':len(projections),'lora_rank':8,'fp32_adapter_elements':A//4,
    'adapter_bytes':A,'largest_adapter_tensor_bytes':max_tensor,'observed_v23_base_tensor_bytes':128455632,
    'observed_v23_base_serialized_bytes':129878173,'observed_nonadapter_base_tensor_bytes':128455632-A,
    'limits':limits.__dict__,'per_checkpoint_upper_bounds':rows,'store_upper_bytes':upper,
    'store_headroom_bytes':limits.store_bytes-upper,
    'per_checkpoint_file_upper':max(r['shard_count_upper']+4 for r in rows),
    'store_file_upper_including_writer_lock':sum(r['shard_count_upper']+4 for r in rows)+4,
    'store_file_cap':limits.files*limits.versions_per_branch*limits.branches+8,
    'ttt_tensor_upper_without_scalar_dedup':280*2*5+4,
    'tensor_cap':limits.tensors,'expected_production_branches':2,
    'expected_global_versions':3,'expected_ttt_versions':1,'retention_cap_per_branch':3,
    'assumptions':['Fixed native40-layer seven-projection rank8 FP32 LoRA; exact source inventory',
        'AdamW two FP32 moments per parameter; no pickle/base/tokenizer copies',
        'TTT additionally retains one full selected-global adapter snapshot',
        'Conservative64KiB per checkpoint for single-device RNG and Adam scalar counters',
        'Safetensors shard per-file bound remains32MiB; greedy payload cap31MiB',
        'Four JSON files per checkpoint, two branch and one store JSON, each existing8MiB cap'],
    'source_inventory_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(ROOT/'evidence/production-capacity-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
