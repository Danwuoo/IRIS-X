"""Acquire/verify a fixed original-family Qwen3 base and source 16-row cut.

Only ``acquire`` calls the Hub. Conversion/verification are offline and do not
load pickle or execute downloaded model code. This is not the historical SFT
checkpoint or evidence for an unknown original training environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import digest_value
from irisx.errors import ValidationError

REPO = 'Qwen/Qwen3-4B-Thinking-2507'
REVISION = '768f209d9ea81521153ed38c47d515654e938aea'
DEFAULT = ROOT / '.irisx/nvarc-original/materials/qwen3-thinking-2507-20261002-001'
SOURCE = ROOT / '.irisx/arc-agi-2/qwen35-nvarc/source/NVARC/ARChitects'
SYMBOLS = tuple('0123456789') + ('\n', 'user', 'assistant', '<|endoftext|>', '<|im_start|>', '<|im_end|>')


def inventory(path):
    return {p.relative_to(path).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha_file(p)}
            for p in sorted(path.rglob('*')) if p.is_file() and '.cache' not in p.parts}


def acquire(root):
    from huggingface_hub import HfApi, snapshot_download
    ledger = root / 'acquisition.json'
    if ledger.exists():
        raise ValidationError('acquisition identity is already reserved; verify retained bytes')
    root.mkdir(parents=True, exist_ok=True)
    model = HfApi(token=False).model_info(REPO, revision=REVISION, files_metadata=True)
    if model.sha != REVISION:
        raise ValidationError('Hub revision differs')
    members = {f.rfilename: {'bytes': f.size, 'git_blob': f.blob_id,
               'lfs_sha256': f.lfs.sha256 if f.lfs else None} for f in model.siblings}
    required = sum(m['bytes'] for m in members.values())
    # Retain raw base + changed first compact shard and a local disk reserve.
    if shutil.disk_usage(root).free < required + 4 * 1024**3 + 8 * 1024**3:
        raise ValidationError('insufficient base/conversion/disk reserve')
    journal = {'owner_decision': 'Decision 0054', 'repo': REPO, 'revision': REVISION,
               'download_reserved': True, 'members': members, 'paid_usd': 0}
    atomic(ledger, journal)
    try:
        snapshot_download(REPO, revision=REVISION, local_dir=root / 'base', token=False, max_workers=3)
        actual = inventory(root / 'base')
        if set(actual) != set(members):
            raise ValidationError('closed Hub file inventory differs')
        for name, entry in members.items():
            p = root / 'base' / name
            if p.stat().st_size != entry['bytes']:
                raise ValidationError('Hub member length differs: ' + name)
            if entry['lfs_sha256']:
                if actual[name]['sha256'] != entry['lfs_sha256']:
                    raise ValidationError('Hub LFS digest differs: ' + name)
            else:
                blob = hashlib.sha1(b'blob ' + str(p.stat().st_size).encode() + b'\0' + p.read_bytes()).hexdigest()
                if blob != entry['git_blob']:
                    raise ValidationError('Hub Git blob differs: ' + name)
        journal.update(complete=True, inventory=actual, inventory_digest=digest_value(actual))
        atomic(ledger, journal)
    except BaseException as error:
        journal.update(complete=False, error_type=type(error).__name__)
        atomic(ledger, journal)
        raise
    print(json.dumps({'revision': REVISION, 'raw_bytes': required, 'inventory_digest': journal['inventory_digest']}), flush=True)


def convert(root):
    from safetensors import safe_open
    from safetensors.torch import save_file
    import torch
    from transformers import AutoTokenizer
    journal = json.loads((root / 'acquisition.json').read_bytes())
    if not journal.get('complete') or inventory(root / 'base') != journal['inventory']:
        raise ValidationError('verified complete raw base required')
    # Every source byte is checked by the existing immutable source verifier.
    from tools.nvarc_source import verify
    verify(SOURCE.parents[1], json.loads((ROOT / 'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    tokenizer = AutoTokenizer.from_pretrained(root / 'base', local_files_only=True)
    row_ids = []
    for text in SYMBOLS:
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) != 1:
            raise ValidationError('source symbol is not one base row: ' + repr(text))
        row_ids.extend(ids)
    if row_ids != sorted(set(row_ids)):
        raise ValidationError('source sorted row mapping differs')
    from tokenizers import Tokenizer
    source_tok = Tokenizer.from_file(str(SOURCE / 'qwen3_configs/tokenizer.json'))
    if [source_tok.encode(text, add_special_tokens=False).ids for text in SYMBOLS] != [[i] for i in range(16)]:
        raise ValidationError('pinned source compact tokenizer differs')
    output = root / 'compact'
    if output.exists():
        raise ValidationError('compact identity already exists')
    output.mkdir()
    index = json.loads((root / 'base/model.safetensors.index.json').read_bytes())
    embed = 'model.embed_tokens.weight'
    if 'lm_head.weight' in index['weight_map']:
        raise ValidationError('source cut expects tied model without separate LM head')
    shard = index['weight_map'][embed]
    with safe_open(root / 'base' / shard, framework='pt', device='cpu') as handle:
        tensors = {key: handle.get_tensor(key) for key in handle.keys()}
        old_shape = list(tensors[embed].shape)
        selected = tensors[embed].index_select(0, torch.tensor(row_ids)).contiguous()
        tensors[embed] = selected
        save_file(tensors, output / shard, metadata={'format': 'pt'})
    del tensors
    for name in sorted(set(index['weight_map'].values()) - {shard}):
        # Immutable hard links save disk; verification still rehashes all bytes.
        os.link(root / 'base' / name, output / name)
    config = json.loads((root / 'base/config.json').read_bytes())
    if config['model_type'] != 'qwen3' or config['tie_word_embeddings'] is not True:
        raise ValidationError('original-family tied Qwen3 config required')
    config.update(vocab_size=16, bos_token_id=13, pad_token_id=13, eos_token_id=15)
    atomic(output / 'config.json', config)
    generation = json.loads((root / 'base/generation_config.json').read_bytes())
    generation.update(bos_token_id=13, pad_token_id=13, eos_token_id=15)
    atomic(output / 'generation_config.json', generation)
    index['metadata']['total_size'] -= (old_shape[0] - 16) * old_shape[1] * selected.element_size()
    atomic(output / 'model.safetensors.index.json', index)
    for p in (SOURCE / 'qwen3_configs').iterdir():
        if p.is_file():
            shutil.copyfile(p, output / p.name)
    shutil.copyfile(root / 'base/LICENSE', output / 'LICENSE')
    report = {'format': 'irisx/nvarc-original-qwen3-cut-v1', 'owner_decision': 'Decision 0054',
        'repo': REPO, 'revision': REVISION, 'base_inventory_digest': journal['inventory_digest'],
        'source_commit': '846d0198efa752534594e321fc3289fc0a06c657',
        'source_configs': inventory(SOURCE / 'qwen3_configs'), 'symbols': list(SYMBOLS), 'row_ids': row_ids,
        'source_tokenizer_interpreter': 'tokenizers.Tokenizer.from_file; source WordLevel JSON unchanged',
        'auto_tokenizer_compatibility': 'Transformers 5.8.1 AutoTokenizer resolves source Qwen2Tokenizer incorrectly: standalone user/assistant encode empty; use explicit WordLevel JSON interpreter',
        'base_embedding_shape': old_shape, 'compact_embedding_shape': list(selected.shape),
        'selected_embedding_sha256': hashlib.sha256(selected.view(torch.uint8).numpy().tobytes()).hexdigest(),
        'tied_embeddings': True, 'base_config': json.loads((root / 'base/config.json').read_bytes()),
        'compact_inventory': inventory(output), 'historical_base_commit_known': False,
        'original_sft_checkpoint': False, 'full_sft_completed': False,
        'original_nemo_version': None, 'original_unsloth_version': None}
    report['material_digest'] = digest_value(report['compact_inventory'])
    atomic(root / 'conversion.json', report)
    print(json.dumps({'row_ids': row_ids, 'material_digest': report['material_digest']}), flush=True)


def verify_cut(root):
    """Independent byte-level oracle for every source and compact tensor."""
    from safetensors import safe_open
    import torch
    report = json.loads((root / 'conversion.json').read_bytes())
    journal = json.loads((root / 'acquisition.json').read_bytes())
    if inventory(root / 'base') != journal['inventory'] or inventory(root / 'compact') != report['compact_inventory']:
        raise ValidationError('material bytes changed')
    index = json.loads((root / 'base/model.safetensors.index.json').read_bytes())
    compared = 0
    for shard in sorted(set(index['weight_map'].values())):
        with safe_open(root / 'base' / shard, framework='pt') as base, safe_open(root / 'compact' / shard, framework='pt') as cut:
            if base.keys() != cut.keys():
                raise ValidationError('tensor names differ')
            for key in base.keys():
                lhs = base.get_tensor(key)
                rhs = cut.get_tensor(key)
                if key == 'model.embed_tokens.weight':
                    lhs = torch.stack([lhs[row] for row in report['row_ids']])
                if lhs.dtype != rhs.dtype or not torch.equal(lhs.view(torch.uint8), rhs.view(torch.uint8)):
                    raise ValidationError('tensor differs: ' + key)
                compared += 1
    result = {'all_tensor_bytes_equal_to_base_or_selected_rows': True, 'tensors': compared,
              'material_digest': report['material_digest'], 'external_calls': 0}
    atomic(root / 'independent-verification.json', result)
    print(json.dumps(result), flush=True)


def publish(root):
    """One new private version; reserve before official resumable transport."""
    from kaggle.api.kaggle_api_extended import KaggleApi
    from tools.execute_nvarc_overnight_sft import token
    ledger = root / 'dataset-ledger.json'
    if ledger.exists():
        raise ValidationError('Dataset creation already reserved')
    report = json.loads((root / 'conversion.json').read_bytes())
    proof = json.loads((root / 'independent-verification.json').read_bytes())
    if proof['material_digest'] != report['material_digest'] or inventory(root / 'compact') != report['compact_inventory']:
        raise ValidationError('independently verified compact material required')
    folder = root / 'upload'
    folder.mkdir()
    for name in report['compact_inventory']:
        os.link(root / 'compact' / name, folder / name)
    atomic(folder / 'material-manifest.json', report)
    metadata = {'id': 'danielwuu/irisx-nvarc-original-qwen3-001', 'title': 'IRISX NVARC Original Qwen3 001',
        'licenses': [{'name': 'other'}],
        'description': 'Private engineering material: Apache-2.0 Qwen3-4B-Thinking-2507 base row cut; retained source tokenizer configs with no stated root license. Not historical SFT weights.'}
    atomic(folder / 'dataset-metadata.json', metadata)
    token()  # Refresh the existing credential without printing it.
    journal = {'owner_decision': 'Decision 0054', 'create_reserved': 1, 'dataset_id': metadata['id'],
        'private': True, 'paid_usd': 0, 'inventory': inventory(folder)}
    atomic(ledger, journal)
    try:
        api = KaggleApi()
        api.authenticate()
        response = api.dataset_create_new(str(folder), public=False, quiet=True, convert_to_csv=False)
        receipt = response.to_dict()
        atomic(root / 'dataset-receipt.json', receipt)
        journal.update(receipt=receipt, receipt_sha256=sha_file(root / 'dataset-receipt.json'))
        atomic(ledger, journal)
        if not dataset_receipt_accepted(receipt):
            raise ValidationError('Dataset creation rejected or uncertain; inspect receipt without another create')
        print(json.dumps({'dataset_id': metadata['id'], 'receipt': receipt}), flush=True)
    except BaseException as error:
        journal['error_type'] = type(error).__name__
        atomic(ledger, journal)
        raise


def dataset_receipt_accepted(receipt):
    return (not receipt.get('error') and str(receipt.get('status','')).lower() in {'ready','success','ok'}
        and receipt.get('url')=='https://www.kaggle.com/datasets/danielwuu/irisx-nvarc-original-qwen3-001'
        and receipt.get('ref')=='/datasets/danielwuu/irisx-nvarc-original-qwen3-001')


def dataset_status(root):
    from datetime import datetime,timezone
    from kaggle.api.kaggle_api_extended import KaggleApi
    from tools.execute_nvarc_overnight_sft import token
    ledger=root/'dataset-ledger.json';journal=json.loads(ledger.read_bytes())
    receipt=json.loads((root/'dataset-receipt.json').read_bytes())
    if not dataset_receipt_accepted(receipt):raise ValidationError('accepted exact Dataset receipt required')
    journal['accepted']=True
    # A previous local parser did not recognize the provider's capitalized Ok.
    # Retain that failure; this operation never creates another Dataset.
    journal['receipt_status_interpretation']='case-insensitive provider Ok accepted; original receipt unchanged'
    now=datetime.now(timezone.utc)
    if journal.get('last_status_reserved_utc') and (now-datetime.fromisoformat(journal['last_status_reserved_utc'])).total_seconds()<60:
        raise ValidationError('Dataset status backoff required')
    if journal.get('status_checks_reserved',0)>=8:raise ValidationError('Dataset status quota consumed')
    token();api=KaggleApi();api.authenticate()
    journal['status_checks_reserved']=journal.get('status_checks_reserved',0)+2
    journal['last_status_reserved_utc']=now.isoformat();atomic(ledger,journal)
    result=json.loads(api.dataset_status(journal['dataset_id'],format='json'))
    journal.setdefault('status_results',[]).append(result);atomic(ledger,journal)
    if result['current_version_number']!=1:raise ValidationError('immutable Dataset version differs')
    print(json.dumps(result),flush=True)


def forward_verify(root):
    """Actual CPU base/cut numerical oracle; two fixed forwards, no generate."""
    import gc
    import time
    import torch
    from transformers import Qwen3ForCausalLM
    from tokenizers import Tokenizer
    from irisx.arc_nvarc_source_recipe import SourceTextTokenizer
    ledger=root/'forward-verification-ledger.json'
    if ledger.exists():raise ValidationError('fixed local forward identity already reserved')
    report=json.loads((root/'conversion.json').read_bytes())
    proof=json.loads((root/'independent-verification.json').read_bytes())
    if proof['material_digest']!=report['material_digest']:raise ValidationError('verified cut required')
    text='<|im_start|>user\n12<|im_end|><|im_start|>assistant\n34<|im_end|>'
    ids=Tokenizer.from_file(str(root/'compact/tokenizer.json')).encode(text).ids
    if ids!=SourceTextTokenizer().encode(text):raise ValidationError('source-format oracle differs')
    atomic(ledger,{'run_id':'nvarc-original-qwen3-cut-parity-001','reserved_outer_forwards':2,
        'reserved_input_tokens':len(ids)*2,'generations':0,'optimizer_steps':0,
        'maximum_worker_wall_seconds':600,'model_material_digest':report['material_digest']})
    torch.set_num_threads(2);started=time.monotonic()
    raw_ids=[report['row_ids'][i] for i in ids]
    with torch.inference_mode():
        base=Qwen3ForCausalLM.from_pretrained(root/'base',local_files_only=True,dtype=torch.bfloat16,attn_implementation='sdpa').eval()
        expected=base(torch.tensor([raw_ids]),use_cache=False).logits.index_select(-1,torch.tensor(report['row_ids'])).float().clone()
        del base;gc.collect()
        cut=Qwen3ForCausalLM.from_pretrained(root/'compact',local_files_only=True,dtype=torch.bfloat16,attn_implementation='sdpa').eval()
        actual=cut(torch.tensor([ids]),use_cache=False).logits.float().clone()
        tied=cut.get_input_embeddings().weight.data_ptr()==cut.get_output_embeddings().weight.data_ptr()
        del cut;gc.collect()
    torch.testing.assert_close(actual,expected,atol=0.0625,rtol=0.01)
    if not tied:raise ValidationError('loaded compact embedding/head lost tying')
    value={'format':'irisx/nvarc-original-base-cut-forward-v1','run_id':'nvarc-original-qwen3-cut-parity-001',
        'model_material_digest':report['material_digest'],'input_ids':ids,'base_input_ids':raw_ids,
        'base_selected_logits':expected.tolist(),'compact_logits':actual.tolist(),
        'max_absolute_error':float((actual-expected).abs().max()),'atol':0.0625,'rtol':0.01,
        'tied_embeddings':tied,'dtype':'bfloat16','device':'cpu','torch_version':torch.__version__,
        'reserved_outer_forwards':2,'reserved_input_tokens':len(ids)*2,
        'generations':0,'optimizer_steps':0,'wall_seconds':time.monotonic()-started,
        'historical_sft_checkpoint':False,'external_calls':0}
    atomic(root/'forward-verification.json',value)
    print(json.dumps({k:v for k,v in value.items() if not k.endswith('logits')}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('acquire', 'convert', 'verify', 'publish','status','forward-verify'))
    parser.add_argument('--root', type=Path, default=DEFAULT)
    args = parser.parse_args()
    {'acquire': acquire, 'convert': convert, 'verify': verify_cut, 'publish': publish,'status':dataset_status,
     'forward-verify':forward_verify}[args.action](args.root)
