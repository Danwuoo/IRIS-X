"""Closed-byte/tensor verification and bounded published-model forwards."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.acquire_nvarc_qwen3_sft import DEFAULT,REF

IDS=[14,11,10,1,2,15,14,12,10,3,4,15]
CHAT='<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>'


def verified_inventory(folder):
    acquisition=json.loads((folder/'acquisition.json').read_bytes())
    if acquisition['state']!='complete-published-bytes' or acquisition['ref']!=REF:
        raise ValidationError('complete source-named published bytes required')
    model=folder/'model';expected={r['path']:r for r in acquisition['members']}
    if {p.name for p in model.iterdir() if p.is_file()}!=set(expected):
        raise ValidationError('closed published model inventory differs')
    actual={}
    for name,row in sorted(expected.items()):
        path=model/name
        if path.is_symlink() or path.stat().st_size!=row['expected_bytes'] or sha_file(path)!=row['sha256']:
            raise ValidationError('published model retained bytes differ')
        actual[name]={'bytes':path.stat().st_size,'sha256':row['sha256']}
    return actual


def verify(folder):
    import torch
    from safetensors import safe_open
    from tokenizers import Tokenizer
    output=folder/'independent-verification.json'
    if output.exists():raise ValidationError('published verification observation is immutable')
    inventory=verified_inventory(folder);model=folder/'model';config=json.loads((model/'config.json').read_bytes())
    required={'model_type':'qwen3','vocab_size':16,'hidden_size':2560,'intermediate_size':9728,
        'num_hidden_layers':36,'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,
        'tie_word_embeddings':False,'bos_token_id':13,'eos_token_id':15,'rope_theta':5000000,
        'transformers_version':'4.53.3'}
    if any(config.get(key)!=value for key,value in required.items()):
        raise ValidationError('source-linked published original architecture differs')
    tokenizer=Tokenizer.from_file(str(model/'tokenizer.json'))
    if tokenizer.encode(CHAT).ids!=IDS or tokenizer.get_vocab_size()!=16:
        raise ValidationError('published source WordLevel row map differs')
    index=json.loads((model/'model.safetensors.index.json').read_bytes())['weight_map']
    tensors={};bytes_seen=0;torch.set_num_threads(2)
    for shard in sorted(set(index.values())):
        if shard not in inventory:raise ValidationError('published tensor shard is absent')
        with safe_open(model/shard,framework='pt',device='cpu') as stream:
            for name in stream.keys():
                if name in tensors or index.get(name)!=shard:raise ValidationError('published tensor index differs')
                tensor=stream.get_tensor(name)
                if tensor.dtype!=torch.bfloat16 or not bool(torch.isfinite(tensor).all()):
                    raise ValidationError('published tensor dtype/finite contract differs')
                raw=tensor.contiguous().view(torch.uint8).numpy().tobytes();bytes_seen+=len(raw)
                tensors[name]={'shape':list(tensor.shape),'dtype':str(tensor.dtype),
                    'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if set(tensors)!=set(index) or len(tensors)!=399 or any(tensors[name]['shape']!=[16,2560]
            for name in ('model.embed_tokens.weight','lm_head.weight')):
        raise ValidationError('complete original untied 399-tensor checkpoint required')
    result={'format':'irisx/nvarc-published-qwen3-sft-material-v1','ref':REF,'model_instance_version_id':627758,
        'inventory':inventory,'material_digest':digest_value(inventory),'tensor_count':len(tensors),
        'tensor_bytes':bytes_seen,'tensors':tensors,'source_chat_input_ids':IDS,
        'config_transformers_version':'4.53.3','embedding_head_tied':False,
        'training_reproduced':False,'clean_exposure_established':False,'correctness_scored':False,
        'model_calls':0,'external_calls':0,'paid_usd':0}
    atomic(output,result);print(json.dumps({k:v for k,v in result.items() if k not in {'tensors','inventory'}}),flush=True)


def forward(folder,version,output):
    import torch
    import transformers
    from transformers import Qwen3ForCausalLM
    from tokenizers import Tokenizer
    if version not in {'4.53.3','5.8.1'} or transformers.__version__!=version or output.exists():
        raise ValidationError('new exact bounded runtime forward identity required')
    proof=json.loads((folder/'independent-verification.json').read_bytes())
    if digest_value(verified_inventory(folder))!=proof['material_digest']:
        raise ValidationError('verified published forward material differs')
    if Tokenizer.from_file(str(folder/'model/tokenizer.json')).encode(CHAT).ids!=IDS:
        raise ValidationError('source chat encoding differs')
    output.mkdir(parents=True);atomic(output/'ledger.json',{'owner_decision':'Decision 0054',
        'run_id':output.name,'reserved_outer_forwards':1,'reserved_input_tokens':12,
        'generations':0,'optimizer_steps':0,'maximum_wall_seconds':600,
        'material_digest':proof['material_digest'],'transformers_version':version})
    torch.set_num_threads(2);started=time.monotonic()
    try:
        model=Qwen3ForCausalLM.from_pretrained(folder/'model',local_files_only=True,
            torch_dtype=torch.bfloat16,attn_implementation='sdpa').eval()
        if model.get_input_embeddings().weight.data_ptr()==model.get_output_embeddings().weight.data_ptr():
            raise ValidationError('published untied embedding/head was silently tied')
        with torch.inference_mode():logits=model(torch.tensor([IDS]),use_cache=False).logits.float()
        result={'run_id':output.name,'outcome':'complete','material_digest':proof['material_digest'],
            'transformers_version':version,'torch_version':torch.__version__,'dtype':'bfloat16','device':'cpu',
            'input_ids':IDS,'logits':logits.tolist(),'outer_forwards':1,'input_tokens':12,
            'embedding_head_tied':False,'wall_seconds':time.monotonic()-started,
            'historical_runtime_parity':False,'correctness_scored':False,'external_calls':0}
        atomic(output/'result.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='logits'}),flush=True)
    except BaseException as error:
        atomic(output/'failure.json',{'error_type':type(error).__name__,'message':str(error)[:1000]});raise


def compare(folder,left,right,output):
    if output.exists():raise ValidationError('runtime comparison observation is immutable')
    proof=json.loads((folder/'independent-verification.json').read_bytes())
    rows=[json.loads((path/'result.json').read_bytes()) for path in (left,right)]
    if ({row['transformers_version'] for row in rows}!={'4.53.3','5.8.1'} or
            any(row['outcome']!='complete' or row['material_digest']!=proof['material_digest'] or
                row['input_ids']!=IDS or row['outer_forwards']!=1 or row['input_tokens']!=12 or
                row['device']!='cpu' or row['dtype']!='bfloat16' or row['embedding_head_tied'] is not False
                for row in rows)):
        raise ValidationError('exact two source-linked runtime observations required')
    vectors=[]
    for row in rows:
        logits=row['logits']
        if len(logits)!=1 or len(logits[0])!=12 or any(len(token)!=16 for token in logits[0]):
            raise ValidationError('complete original runtime numeric vector required')
        vector=[value for token in logits[0] for value in token]
        if any(not isinstance(value,(int,float)) or not math.isfinite(value) for value in vector):
            raise ValidationError('nonfinite original runtime numeric observation')
        vectors.append(vector)
    differences=[abs(a-b) for a,b in zip(*vectors)]
    result={'format':'irisx/nvarc-published-qwen3-runtime-comparison-v1',
        'material_digest':proof['material_digest'],'observations':[
            {'run_id':path.name,'result_sha256':sha_file(path/'result.json')} for path in (left,right)],
        'transformers_versions':[row['transformers_version'] for row in rows],
        'max_absolute_logit_error':max(differences),'all_192_logits_bitwise_equal':all(value==0 for value in differences),
        'within_bf16_atol_00625_rtol_001':all(abs(a-b)<=.0625+.01*abs(a) for a,b in zip(*vectors)),
        'input_tokens_per_observation':12,'total_reserved_outer_forwards':2,'total_reserved_input_tokens':24,
        'new_forwards':0,'external_calls':0,'correctness_scored':False,
        'scope':'one BF16 CPU source chat under two library versions; historical CUDA/NeMo/Unsloth numerical parity remains unknown'}
    atomic(output,result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('verify','forward','compare'))
    parser.add_argument('--folder',type=Path,default=DEFAULT);parser.add_argument('--version')
    parser.add_argument('--output',type=Path);parser.add_argument('--left',type=Path);parser.add_argument('--right',type=Path)
    args=parser.parse_args()
    if args.action=='verify':verify(args.folder)
    elif args.action=='forward':forward(args.folder,args.version,args.output)
    else:compare(args.folder,args.left,args.right,args.output)
