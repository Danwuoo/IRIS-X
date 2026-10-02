"""Offline source/config/version audit, without inventing original locks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.nvarc_qwen3_material import DEFAULT,SOURCE
from tools.nvarc_source import verify
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE


def audit(output):
    from omegaconf import OmegaConf
    manifest=json.loads((ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
    verify(SOURCE.parents[1],manifest)
    shell=(SOURCE/'run_sft_4b.sh').read_text(encoding='utf-8')
    command=shell[shell.index('uv run '):].replace('\\\n',' ')
    overrides=[s for s in shlex.split(command) if '=' in s and not s.startswith('--')]
    actual=OmegaConf.to_container(OmegaConf.merge(OmegaConf.load(SOURCE/'sft_mg.yaml'),OmegaConf.from_dotlist(overrides)),resolve=True)
    source_config=json.loads((DEFAULT/'base/config.json').read_bytes())
    notebook_path=SOURCE.parents[1]/manifest['notebooks']['qwen']['path']
    notebook=json.loads(notebook_path.read_bytes())
    cells='\n'.join(''.join(cell['source']) for cell in notebook['cells'])
    report={'format':'irisx/nvarc-original-backend-audit-v1','source_commit':manifest['git']['NVARC']['commit'],
        'files':{str(path.relative_to(SOURCE)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [SOURCE/'run_sft_4b.sh',SOURCE/'sft_mg.yaml',SOURCE/'run_sft.py',SOURCE/'cut_tokenizer.ipynb']},
        'resolved_source_sft_config':actual,'original_model_config':source_config,
        'source_qwen_notebook':{'version':10,'sha256':manifest['notebooks']['qwen']['sha256'],
            'python':notebook['metadata']['language_info']['version'],
            'kaggle':notebook['metadata']['kaggle'],
            'sft_model_path':'/kaggle/input/qwen3_4b_grids15_sft139/transformers/bfloat16/1',
            'backend':'Unsloth; custom batch DFS with mutable KV cache',
            'pinning_statements':[line for line in cells.splitlines() if 'pip install' in line or 'unsloth==' in line]},
        'original_nemo_revision':None,'original_megatron_revision':None,'original_unsloth_version':None,
        'version_gap_reason':'pinned NVARC tree has no NeMo/Unsloth environment lock; Docker image ID and model instance version are known but do not determine all package bytes',
        'source_recipe':RECIPE,
        'qwen35_port_delta':{'model_type':'qwen3_5 versus qwen3','layers':'32 hybrid versus 36 full-attention',
            'recurrent_state':'DeltaNet in Qwen3.5; absent in Qwen3',
            'rope_theta':'original acquired base 5000000; port positional configuration belongs to a separate hybrid architecture',
            'parameter_bytes':'port weights cannot replace original-family weights',
            'packing_backend':'port isolated-segments versus new native-varlen original-family probe'},
        'historical_base_commit_known':False,'full_sft_completed':False,
        'historical_nemo_unsloth_numerical_parity':False,'external_calls':0}
    atomic(output,report)
    print(json.dumps({'audit_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'source_model':actual['policy']['model_name'],'source_global_batch':actual['policy']['train_global_batch_size'],
        'source_steps':actual['sft']['max_num_steps'],'nemo_revision':None,'unsloth_version':None}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
