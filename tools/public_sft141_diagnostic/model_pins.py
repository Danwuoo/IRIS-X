"""Public upstream checkpoint identity, never a private IRIS adapter/export."""
from pathlib import Path
import hashlib

MODEL_HANDLE = 'sorokin/qwen3_2b_grids15_sft141/transformers/bfloat16/1'
MODEL_URL = 'https://www.kaggle.com/models/sorokin/qwen3_2b_grids15_sft141'
# Official public files, verified independently of any IRIS export.
MODEL_FILES = {
 'model.safetensors': (2818986736, '5b702462eb53feabfee67864031c6353237c9f8488491dd9be16a804cae53514'),
 'added_tokens.json': (68, 'cf1224e6a594b51a34b8b9ca6c6dce3026683777521f361e37526b8a33258bce'),
 'config.json': (1474, 'ac4be97ff98561df708cf940ac7c6c5844b121c6e4b7e7626740a37324d7cbf4'),
 'generation_config.json': (113, 'fd0abf1e2baa1f9407803a83486767a6e7841164481d750fcaa9b71d31a0ab02'),
 'special_tokens_map.json': (367, 'f4f79e08d97f4d1c87f8d89264f525c8789da3b73b3bb55d1e12f692f41a7b1b'),
 'tokenizer.json': (1731, 'af6b9e855f9db3192bd9152607708ebd7700b40f9fc5f792a26af70150a96cd5'),
 'tokenizer_config.json': (988, 'e1912aeba4050616cbfe01b34df3f3df2818207eda0056f6eb87c2336936ea90'),
 'vocab.json': (94, '8141a61e47eceec466524bc178bc9c6d5076b7d1b18b456fbd3fdf66cae57f82'),
}

def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def verify_model(directory):
    root = Path(directory).resolve()
    found = {}
    for name, (size, expected) in MODEL_FILES.items():
        path = root / name
        if not path.is_file() or path.stat().st_size != size:
            raise ValueError('Public model file size mismatch: ' + name)
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError('Public model SHA-256 mismatch: ' + name)
        found[name] = {'bytes': size, 'sha256': actual}
    # Prevent auto-loader precedence from accepting an unexpected alternate format.
    allowed = set(MODEL_FILES)
    for path in root.iterdir():
        if path.is_file() and (path.suffix in {'.bin', '.safetensors', '.py'} or path.name.endswith('.index.json')) and path.name not in allowed:
            raise ValueError('Unexpected loadable model file: ' + path.name)
    return {'handle': MODEL_HANDLE, 'url': MODEL_URL, 'files': found}
