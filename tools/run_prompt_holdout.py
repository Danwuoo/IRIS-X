"""Run the frozen Decision 0019 final holdout from the durable ledger."""

from __future__ import annotations

import argparse
from pathlib import Path

from irisx.arc_prompt_kaggle import KaggleFinalHoldoutEvaluator
from irisx.arc_prompt_optimizer import freeze_final_candidate, load_ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--search-root", type=Path, default=Path(".irisx/arc-agi-2/prompt-pilot/search"))
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    search_root = (repository_root / args.search_root).resolve() if not args.search_root.is_absolute() else args.search_root.resolve()
    ledger_path = search_root / "ledger.json"
    ledger = load_ledger(ledger_path)
    if ledger["holdout"].get("status") is None:
        freeze_final_candidate(ledger_path)
    evaluator = KaggleFinalHoldoutEvaluator(
        repository_root=repository_root,
        ledger_path=ledger_path,
        baseline_trial_root=repository_root / ".irisx/arc-agi-2/prompt-pilot/repair-002/trial",
        baseline_outbound=repository_root / ".irisx/arc-agi-2/prompt-pilot/repair-002/outbound/prompt-pilot-baseline-002.zip",
        runtime_wheel=search_root / "runtime/irisx-0.2.0-py3-none-any.whl",
        search_root=search_root,
        notebook_template_root=repository_root / "trials/arc-agi-2-prompt-pilot/repair-002",
        source_training_root=repository_root / ".irisx/arc-agi-2/prompt-pilot/source/upstream/data/training",
    )
    print(evaluator(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
