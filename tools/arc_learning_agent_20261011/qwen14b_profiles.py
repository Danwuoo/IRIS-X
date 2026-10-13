"""Distinct Qwen3-14B capability profile; no production deployment is admitted.

Probe caps are deliberately different from Granite rank32/context8192. A CPU
random-weight fixture cannot activate a production profile or assert GPU fit.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

MODEL_KEY = 'qwen3-14b'
MODEL_ID = 'Qwen/Qwen3-14B'
REVISION = '40c069824f4251a91eefaf281ebe4c544efd3e18'
PROFILE_ID = 'qwen3-14b-native-bf16-r8-c2048-probe-v1'
HF_LICENSE_SHA256 = '832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e'
VOCAB_SIZE = 151936
EOS_IDS = (151645, 151643)
SMALL_FILES = MappingProxyType({
    'config.json': 'e73c3664ca09b10a673fef0c22e8a6b456201d49bd4713c9691f775720e8857a',
    'generation_config.json': '2325da0f15bb848e018c5ae071b7943332e9f871d6b60e2ed22ca97d4cb993d2',
    'tokenizer_config.json': 'd5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101',
    'tokenizer.json': 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4',
})


def profile():
    return {'profile_id': PROFILE_ID, 'model_key': MODEL_KEY, 'repository': MODEL_ID,
            'revision': REVISION, 'architecture': 'Qwen3ForCausalLM', 'vocabulary_rows': VOCAB_SIZE,
            'production_layers': 40, 'production_hidden_size': 5120,
            'production_attention_heads': 40, 'production_kv_heads': 8, 'production_head_dim': 128,
            'context_limit': 2048, 'prompt_cap': 1792, 'output_cap': 256,
            'lora_rank': 8, 'lora_alpha': 16, 'batch_size': 1,
            'precision': 'bf16-base-fp32-lora', 'tensor_parallel_size': 1,
            'maximum_session_seconds': 43200, 'pretrained_loading_default': False,
            'production_admitted': False, 'g4_fit_measured': False, 'four_l4_tp_admitted': False,
            'fp8_measured': False, 'fp8_admitted': False, 'full_public167_coverage_admitted': False,
            'granite_recipe_equivalent': False,
            'required_deployment_evidence': ['exact-full-weight-byte-manifest',
                'independent-material-review', 'exact-environment-lock', 'exact-hardware-profile',
                'measured-memory-peak-and-throughput', 'finite-native-gradient-update',
                'strict-cache-reset-checks', 'whole-record-context-coverage', 'independent-backend-review']}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def authenticate_small_assets(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), 'local native tokenizer assets required')
    hashes = {}
    for name, expected in SMALL_FILES.items():
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size < 16 * 1024**2,
                'bounded regular native asset required: ' + name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == expected, 'exact HF native asset mismatch: ' + name)
        hashes[name] = actual
    return {'repository': MODEL_ID, 'revision': REVISION, 'files': hashes,
            'weights_verified': False, 'provider_material_interchangeable': False}


def require_pretrained_admission(config):
    from .qwen14b_admission import select_reviewed_deployment
    return select_reviewed_deployment(config)
