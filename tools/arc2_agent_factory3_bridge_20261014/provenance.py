"""Pinned, inspected upstream components; no dynamic fetch or framework import."""
from pathlib import Path
import hashlib

UPSTREAM_COMMIT = "a1836decb836cd52cf2b27f5022f6838cee75df3"
BASELINE_COMMIT = "cc14bd1a79aac1fe6135017c9e09d4834300675d"
ROOT = Path(__file__).resolve().parent
VENDOR_SHA256 = {
    "vendor/types.py": "bc6d7328b831d11699378261fae7556ad3516ea1b23c82bf843053a43f33c6c6",
    "vendor/losses/ddis_loss.py": "541ebd935dcbe27789e80aeb6ddfb8ce44390f71b796d026c428d9c13859c090",
    "vendor/losses/metric_state.py": "1cac291fadcf4a291568c2b0245fdd1df71bbaea628da44df4f006df0d4005f1",
    "vendor/LICENSE": "61900d0f9ecd85c532cacd77f9cc98fa68b55a4ab81f0d6435f178c0151d460d",
}
BASELINE_MATH = "tools/arc_qwen_rlvr004_20261013/source/reviewed/rl_math.py"
BASELINE_MATH_SHA256 = "3de11b818eccb6a6bd8896245005a010abc3d930f04982490cfba79e0306b65a"
FROZEN_CONTRACT_SHA256 = {
    BASELINE_MATH: BASELINE_MATH_SHA256,
    "tools/arc_qwen_rlvr004_20261013/source/rl_session/actor.py": "1aff23388143552ff528118b1380251f01803c7c40cbcc1e63866aa6f71142f0",
    "tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py": "73fb2f1197270c821a9bb8f39653db5529609145ccb84a8173d4bd476f43ff02",
    "tools/arc_qwen_rlvr004_20261013/source/owned_runtime/factory.py": "3b3604364f2cd20c96617e43d17087aeb47039ee48be322f81b76ca4a3ae8f8a",
    "tools/arc_qwen_rlvr004_20261013/source/design/MEASURED-POLICY.json": "3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda",
}


def verify_vendor():
    for relative, expected in VENDOR_SHA256.items():
        path = ROOT / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("vendored source drift: " + relative)
    return dict(VENDOR_SHA256)


def verify_frozen_contract():
    for relative, expected in FROZEN_CONTRACT_SHA256.items():
        path = ROOT.parents[1] / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("frozen contract source drift: " + relative)
    return dict(FROZEN_CONTRACT_SHA256)
