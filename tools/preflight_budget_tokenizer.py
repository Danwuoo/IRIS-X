"""Offline exact-revision tokenizer and chat-template preflight for Decision 0020."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from irisx import arc_budget_ablation as budget
from irisx import kaggle_runner_budget_ablation as runner
from irisx.canonical import digest_value
from irisx.transport import digest_path


def main() -> int:
    from transformers import AutoTokenizer

    root = Path(".irisx/arc-agi-2/budget-ablation")
    tokenizer_root = root / "source/tokenizer"
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_root, local_files_only=True, use_fast=True)
    cohort = json.loads((root / "cohort.json").read_bytes())
    baseline = json.loads(Path("C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot/repair-002/trial/solver-cases.json").read_bytes())
    selected = set(sum(cohort["strata"].values(), []))
    records = []
    for case in baseline["cases"]:
        if case["task_id"] not in selected:
            continue
        messages = budget.render_candidate(case, budget.BASE_INSTRUCTION)
        off = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        on = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=True)
        if not off.endswith("<think>\n\n</think>\n\n") or not on.endswith("<think>\n"):
            raise RuntimeError("pinned chat template does not support the expected thinking switch")
        records.append({"task_id": case["task_id"], "off_prompt_tokens": len(tokenizer(off, add_special_tokens=False)["input_ids"]),
                        "on_prompt_tokens": len(tokenizer(on, add_special_tokens=False)["input_ids"])})
    if len(records) != 64:
        raise RuntimeError("tokenizer preflight did not cover all 64 diagnostic cases")
    full_grid = "\n".join(["0123456789" * 3] * 30)
    final, state = runner.split_final_completion("reasoning 123\n</think>\n" + full_grid, enable_thinking=True)
    if state != "final_present" or budget.parse_grid_text(final) is None:
        raise RuntimeError("complete thinking fixture did not parse")
    if runner.split_final_completion("reasoning 123", enable_thinking=True)[0] is not None:
        raise RuntimeError("reasoning-only fixture was accepted")
    if runner.final_is_complete("maximum_new_tokens", False, "0123\n4567"):
        raise RuntimeError("capped partial-grid fixture was accepted")
    report = {"format": "irisx/arc-budget-tokenizer-preflight", "format_version": "1.0",
              "model_revision": budget.MODEL_REVISION, "tokenizer_class": tokenizer.__class__.__name__,
              "transformers_version": __import__("transformers").__version__,
              "tokenizer_json_digest": digest_path(tokenizer_root / "tokenizer.json"),
              "chat_template_digest": digest_path(tokenizer_root / "chat_template.jinja"),
              "diagnostic_case_count": len(records), "prompts": records,
              "full_30x30_digit_grid_tokens": len(tokenizer(full_grid, add_special_tokens=False)["input_ids"]),
              "full_grid_parse_valid": True, "reasoning_only_rejected": True, "truncated_grid_rejected": True}
    budget.atomic_json(root / "source/tokenizer-preflight.json", report)
    print(json.dumps({"diagnostic_case_count": 64, "full_30x30_digit_grid_tokens": report["full_30x30_digit_grid_tokens"],
                      "report_digest": digest_value(report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
