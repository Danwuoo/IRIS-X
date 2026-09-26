"""Offline exact-tokenizer checks; later-stage probes are not model replies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from irisx.arc_nvarc_sdg import render_source_teacher_prompt
from irisx.arc_nvarc_teacher_profile import PROMPTS, LIMITS
from irisx.canonical import canonical_bytes, digest_value
from materialize_nvarc_teacher_tokenizer import FILES


def preflight(tokenizer_root: Path, package: Path) -> dict:
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    import torch
    import transformers
    from transformers import AutoTokenizer

    manifest = json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/base-model-manifest.json").read_bytes())
    for entry in manifest["files"]:
        if entry["path"] not in FILES:
            continue
        payload = (tokenizer_root / entry["path"]).read_bytes()
        if (len(payload) != entry["byte_size"] or
                "sha256:" + hashlib.sha256(payload).hexdigest() != entry["content_digest"]):
            raise ValueError("tokenizer preflight material differs")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_root, local_files_only=True)
    seed = json.loads((package / "seed.json").read_bytes())
    item = {**seed["record"], "stage_responses": {}}
    rows = []
    for stage in PROMPTS:
        rendered = render_source_teacher_prompt(stage, item, PROMPTS[stage])
        messages = [{"role": "user", "content": rendered}]
        direct = tokenizer.apply_chat_template(messages, tokenize=False,
                                              add_generation_prompt=True, enable_thinking=False)
        if not direct.endswith("<think>\n\n</think>\n\n"):
            raise ValueError("pinned direct-mode template differs")
        tokens = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                    return_tensors="pt", add_generation_prompt=True, enable_thinking=False)
        if not isinstance(tokens, torch.Tensor) or tokens.ndim != 2 or tokens.shape[0] != 1:
            raise ValueError("teacher template tensor differs")
        count = int(tokens.shape[-1])
        if count > LIMITS[stage]["input"]:
            raise ValueError("teacher input preflight exceeds cap: " + stage)
        rows.append({"stage": stage, "input_tokens": count, "input_limit": LIMITS[stage]["input"],
                     "prompt_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                     "case": "exact public seed" if stage == "summary" else "synthetic prior-output budget probe"})
        # One token per word in this pinned tokenizer; simulate a prior reply
        # at its output cap without pretending these are real generated replies.
        probe = " x" * LIMITS[stage]["output"]
        item["stage_responses"][stage] = {"content": probe}
    return {"format": "irisx/nvarc-teacher-tokenizer-preflight-v1",
            "model_manifest_digest": manifest["manifest_digest"],
            "seed_sha256": hashlib.sha256((package / "seed.json").read_bytes()).hexdigest(),
            "prompts_digest": digest_value(PROMPTS), "transformers": transformers.__version__,
            "tokenizer_class": type(tokenizer).__name__, "rows": rows,
            "model_calls": 0, "external_calls": 0,
            "limitation": "actual dependent replies remain subject to runtime input gates"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError("new preflight report required")
    report = preflight(args.tokenizer, args.package)
    args.report.write_bytes(canonical_bytes(report, newline=True))
    print(json.dumps(report, indent=2))
