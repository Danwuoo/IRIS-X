"""Run the bounded Decision 0019 prompt search from its durable ledger."""

from __future__ import annotations

import argparse
from pathlib import Path

from irisx.arc_prompt_kaggle import KaggleCandidateEvaluator
from irisx.arc_prompt_optimizer import run_dspy_gepa_search
from irisx.canonical import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--search-root", type=Path, default=Path(".irisx/arc-agi-2/prompt-pilot/search"))
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    search_root = (repository_root / args.search_root).resolve() if not args.search_root.is_absolute() else args.search_root.resolve()
    runtime_wheel = search_root / "runtime/irisx-0.2.0-py3-none-any.whl"
    evaluator = KaggleCandidateEvaluator(
        repository_root=repository_root,
        ledger_path=search_root / "ledger.json",
        baseline_trial_root=repository_root / ".irisx/arc-agi-2/prompt-pilot/repair-002/trial",
        baseline_outbound=repository_root / ".irisx/arc-agi-2/prompt-pilot/repair-002/outbound/prompt-pilot-baseline-002.zip",
        runtime_wheel=runtime_wheel,
        search_root=search_root,
        notebook_template_root=repository_root / "trials/arc-agi-2-prompt-pilot/repair-002",
    )
    result = run_dspy_gepa_search(
        ledger_path=search_root / "ledger.json",
        baseline_trial_root=repository_root / ".irisx/arc-agi-2/prompt-pilot/repair-002/trial",
        proposer_workspace=search_root / "proposer",
        gepa_run_dir=search_root / "gepa",
        evaluate_candidate=evaluator,
    )
    write_json(search_root / "gepa-result.json", result)
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
