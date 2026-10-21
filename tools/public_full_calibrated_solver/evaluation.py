"""Separate evaluator-only entrypoint. Imported by neither solver nor worker.

Gold is opened only after complete exited-seal/export/readback verification.
All rankers use the frozen shared pool; the exported strategy cannot be changed.
Evaluation inherits the dispatch deadline, including when used as an owned leaf.
"""
from pathlib import Path
from . import core
from .controller import verify, read_replay
from tools.public_sft141_submission import contract as wire, files


def evaluate(run_dir, output_dir, gold_path, *, before_completion=False):
    root = files.safe_path(run_dir)
    verified = verify(root, output_dir, require_completion=not before_completion)
    challenge, dispatch, analysis, selections, seal = read_replay(root)
    if verified != analysis:
        raise ValueError("predictions changed before evaluator boundary")
    deadline = core.SharedDeadline(dispatch["start_monotonic"], dispatch["budget_seconds"])
    if deadline.remaining() <= 0:
        raise TimeoutError("original whole clock expired before evaluator gold read")
    # No gold pathname reaches any solver process, and this is the first read.
    gold, raw = files.load_json(gold_path)
    if not isinstance(gold, dict) or set(gold) != set(challenge):
        raise ValueError("gold must preserve the full frozen task denominator")
    for task, value in challenge.items():
        if not isinstance(gold[task], list) or len(gold[task]) != len(value["test"]):
            raise ValueError("gold query denominator differs from challenge")
        for grid in gold[task]:
            wire.validate_grid(grid)
    reports, per_query, paired = comparison_metrics(challenge, gold, selections, analysis["queries"])
    if deadline.remaining() <= 0:
        raise TimeoutError("original whole clock expired during evaluation")
    return {"schema": core.SCHEMA, "original_start_monotonic": deadline.start,
            "evaluated_monotonic": deadline.clock(), "exited_seal_sha256": seal, "gold_sha256": wire.digest(raw),
            "fixed_task_denominator": len(challenge), "fixed_query_denominator": analysis["fixed_query_denominator"],
            "frozen_export_strategy": dispatch["configuration"]["strategy"], "same_pool_scores": reports,
            "per_query": per_query, "paired_vs_vote": paired,
            "protocol_complete": analysis["protocol_complete"], "execution_kind": dispatch["execution_kind"],
            "all_planned_calls_returned": analysis["all_planned_calls_returned"],
            "all_generated_answers_valid": analysis["all_generated_answers_valid"],
            "candidate_coverage_complete": analysis["candidate_coverage_complete"],
            "scientific_effectiveness_established": False,
            "qualification": "Public-development or synthetic evaluation only; partial work keeps the entire denominator. No held-out generalization, model capability, or gain claim."}


def comparison_metrics(challenge, gold, selections, query_status):
    """Fixed-denominator descriptive comparisons, not significance or promotion."""
    keys = [(task, i) for task, value in challenge.items() for i in range(len(value["test"]))]
    n, tasks = len(keys), len(challenge)
    if not n or any(set(selections[s]) != set(keys) for s in core.STRATEGIES):
        raise ValueError("every strategy must retain the complete original query inventory")
    status = {(q["task_id"], q["test_index"]): q for q in query_status}
    rows, reports, outcomes = [], {}, {s: {} for s in core.STRATEGIES}
    for task, i in keys:
        row = {"task_id": task, "test_index": i, "query_id": f"{task}:{i}",
               "pool_complete": status.get((task, i), {}).get("pool_complete", False),
               "nll_complete": status.get((task, i), {}).get("nll_complete", False), "strategies": {}}
        for strategy in core.STRATEGIES:
            candidates = wire.validate_candidates(selections[strategy][(task, i)])
            first = bool(candidates and candidates[0] == gold[task][i])
            second = len(candidates) > 1 and candidates[1] == gold[task][i]
            observation = {"first_correct": first, "second_correct": second,
                           "pass_at_2_correct": first or second,
                           "selected_candidates": len(candidates), "missing_first": not candidates,
                           "missing_second": len(candidates) < 2, "missing_query": not candidates}
            outcomes[strategy][(task, i)] = observation
            row["strategies"][strategy] = observation
        rows.append(row)
    for strategy in core.STRATEGIES:
        values = outcomes[strategy]
        pass1 = sum(v["first_correct"] for v in values.values())
        pass2 = sum(v["pass_at_2_correct"] for v in values.values())
        macro1 = sum(sum(values[(task, i)]["first_correct"] for i in range(len(value["test"]))) / len(value["test"])
                     for task, value in challenge.items()) / tasks
        macro2 = sum(sum(values[(task, i)]["pass_at_2_correct"] for i in range(len(value["test"]))) / len(value["test"])
                     for task, value in challenge.items()) / tasks
        reports[strategy] = {"correct": pass2, "denominator": n, "pass_at_1_count": pass1,
            "pass_at_2_count": pass2, "pass_at_1": pass1 / n, "pass_at_2": pass2 / n,
            "query_micro_pass_at_1": pass1 / n, "query_micro_pass_at_2": pass2 / n,
            "equal_task_macro_pass_at_1": macro1, "equal_task_macro_pass_at_2": macro2,
            "task_denominator": tasks, "queries_without_candidates": sum(v["missing_query"] for v in values.values()),
            "queries_without_second_candidate": sum(v["missing_second"] for v in values.values())}
    paired = {}
    for strategy in core.STRATEGIES:
        comparison = {"denominator": n, "first_selection_changes": 0, "second_selection_changes": 0}
        for metric, field in (("pass_at_1", "first_correct"), ("pass_at_2", "pass_at_2_correct")):
            wins = sum(outcomes[strategy][k][field] and not outcomes["vote"][k][field] for k in keys)
            losses = sum(outcomes["vote"][k][field] and not outcomes[strategy][k][field] for k in keys)
            comparison[metric] = {"wins": wins, "losses": losses, "ties": n - wins - losses}
        for key in keys:
            baseline, candidate = selections["vote"][key], selections[strategy][key]
            for i, name in ((0, "first_selection_changes"), (1, "second_selection_changes")):
                comparison[name] += ((baseline[i] if len(baseline) > i else None) !=
                                     (candidate[i] if len(candidate) > i else None))
        paired[strategy] = comparison
    return reports, rows, paired


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--before-completion", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.run_dir, args.output_dir, args.gold, before_completion=args.before_completion), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
