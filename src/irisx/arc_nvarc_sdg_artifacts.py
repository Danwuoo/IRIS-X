"""Bounded published SDG response replay, with generated Python only in WSL.

The caller verifies the complete pinned source Git tree before this operation.
The first provider-ordered output group is fixed before any program executes;
there is no search for a favorable puzzle or relaxation of the 8/12/4 gate.
"""
from __future__ import annotations

import ast
import builtins
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import time
from types import SimpleNamespace

from .arc_nvarc_data import source_sdg_messages
from .arc_nvarc_datasets import sha_file
from .arc_nvarc_original_corpus import parent_metadata
from .arc_nvarc_sdg import WSLNamespaceProgramExecutor
from .arc_nvarc_upstream import sdg_build_datasets
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

KEYS = ("mix_name", "summary_name1", "summary_name2", "puzzle_name1", "puzzle_name2")


def _rows(path):
    import pyarrow.parquet as pq
    for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
        yield from batch.to_pylist()


def _source_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise ValidationError("published SDG source function inventory differs")
    # These are hash/Git-gated upstream functions, never Parquet program text.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def replay(material: Path, source: Path, catalog_path: Path, output: Path,
           executor: WSLNamespaceProgramExecutor, *, reuse: Path | None = None):
    import numpy as np
    import pandas as pd
    acquisition = json.loads((material / "acquisition.json").read_bytes())
    expected = {f"{group}/data-00000.parquet" for group in ("summaries", "mixtures", "inputs", "outputs")}
    if (output.exists() or acquisition["state"] != "verified-partial-published-artifacts" or
            acquisition["dataset"] != "sorokin/nvarc-artifacts-puzzles/1" or
            {row["path"] for row in acquisition["members"]} != expected):
        raise ValidationError("new exact published SDG replay/material required")
    for row in acquisition["members"]:
        path = material / row["path"]
        if path.is_symlink() or path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
            raise ValidationError("published SDG replay member bytes differ")
    first = next(_rows(material / "outputs/data-00000.parquet"))
    key = tuple(first[name] for name in KEYS)
    if (any(not isinstance(value, str) or not value for value in key) or
            any(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is None for value in key[:3]) or
            any(re.fullmatch(r"[0-9a-f]{8}", value) is None for value in key[-2:])):
        raise ValidationError("published SDG closed parent identity differs")
    solutions = [row for row in _rows(material / "outputs/data-00000.parquet")
                 if tuple(row[name] for name in KEYS) == key]
    if len(solutions) != 20 or {row["sid"] for row in solutions} != set(range(20)):
        raise ValidationError("first published SDG output group lacks exactly twenty solutions")
    solutions.sort(key=lambda row: row["sid"])
    history = {}
    for group in ("mixtures", "inputs"):
        matched = [row for row in _rows(material / f"{group}/data-00000.parquet")
                   if tuple(row[name] for name in KEYS) == key]
        if len(matched) != 1:
            raise ValidationError("published SDG parent/program join is not unique: " + group)
        history[group] = matched[0]
    summaries = []
    for summary, parent in ((key[1], key[3]), (key[2], key[4])):
        matched = [row for row in _rows(material / "summaries/data-00000.parquet")
                   if row["summary_name"] == summary and row["puzzle_name"] == parent]
        if len(matched) != 1:
            raise ValidationError("published SDG summary join is not unique")
        summaries.append(matched[0])
    name = "_".join(key[-2:])
    catalog = json.loads(catalog_path.read_bytes())
    parents, tags = parent_metadata("nvarc_training", name, catalog,
                                   {("nvarc_training", name): {"parent_ids": sorted(set(key[-2:])),
                                                               "status": "published-artifact-lineage"}})
    scripts = source / "NVARC/SDG/scripts"
    parser = _source_functions(scripts / "parser.py", ("parse_python_code",), {"re": re})
    input_checks = _source_functions(scripts / "puzzle.py", ("filter_input_tests",), {})
    input_validation = _source_functions(scripts / "generate_input_grids.py", ("validate_grids",),
                                         {"Grid": list[list[int]]})
    input_code = parser["parse_python_code"](history["inputs"]["completion"])
    output_codes = [parser["parse_python_code"](row["completion"]) for row in solutions]
    if not input_code or any(not code for code in output_codes):
        raise ValidationError("published SDG longest Python fence is absent")
    tree = ast.parse(input_code)
    functions = {node.name: ast.get_source_segment(input_code, node) for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    validation_code = input_checks["filter_input_tests"](functions)
    if not validation_code:
        raise ValidationError("published SDG input code has no source-recognized tests")
    for code in output_codes:
        if "generate_puzzle_output" not in {node.name for node in ast.parse(code).body
                                           if isinstance(node, ast.FunctionDef)}:
            raise ValidationError("published SDG output entry is absent")
    plan = {"format": "irisx/nvarc-published-sdg-replay-v1", "owner_decision": "Decision 0053",
            "run_id": output.name,
            "selection": "first provider-ordered output group, before execution",
            "join_key": dict(zip(KEYS, key)), "parent_ids": parents, "exposure_tags": tags,
            "acquisition_sha256": sha_file(material / "acquisition.json"),
            "catalog_sha256": sha_file(catalog_path), "maximum_program_invocations": 660,
            "maximum_wall_seconds": 1200, "maximum_teacher_calls": 0, "maximum_paid_usd": 0,
            "source_filter": {"minimum_majority": 8, "minimum_pairs": 12, "minimum_correct_solutions": 4},
            "source_function_files": {path.name: sha_file(path) for path in
                (scripts / "parser.py", scripts / "puzzle.py", scripts / "generate_input_grids.py",
                 scripts / "make_pairs.py", scripts / "build_datasets.py")},
            "execution_variants": ["WSL namespace/chroot/resource limits",
                "retain unused helper functions; no generated program executed on host",
                "fixed input seed 0; source records seed after increment"],
            "teacher_model_rows": [{"stage": stage, "model_name": row["model_name"],
                "reasoning_level": row["reasoning_level"], "response_digest": digest_value(row)}
                for stage, row in [("summary1", summaries[0]), ("summary2", summaries[1]),
                    ("mix", history["mixtures"]), ("input", history["inputs"])] +
                    [("output-" + str(row["sid"]), row) for row in solutions]],
            "contains_evaluator_truth": False, "complete_dataset_verified": False}
    if reuse is not None:
        previous = json.loads((reuse / "plan.json").read_bytes())
        if (previous["join_key"] != plan["join_key"] or
                previous["acquisition_sha256"] != plan["acquisition_sha256"] or
                previous["source_function_files"] != plan["source_function_files"] or
                previous["catalog_sha256"] != plan["catalog_sha256"]):
            raise ValidationError("published SDG local recovery inputs differ")
        plan["recovery"] = {"parent_run": reuse.name, "repair": "UTF-8 host file opening and canonical recovery envelope",
            "parent_artifact_sha256": {path.relative_to(reuse).as_posix(): sha_file(path)
                                       for path in sorted(reuse.rglob("*")) if path.is_file()},
            "new_program_invocations": 0}
    output.mkdir(parents=True)
    (output / "plan.json").write_bytes(canonical_bytes(plan, newline=True))
    (output / "responses.json").write_bytes(canonical_bytes({"summaries": summaries,
        **history, "outputs": solutions}, newline=True))
    (output / "programs.json").write_bytes(canonical_bytes({"input": input_code,
        "input_validation": validation_code, "outputs": output_codes}, newline=True))
    started = time.monotonic()
    reserved = 0
    failures = Counter()

    def execute(code, entry, **kwargs):
        nonlocal reserved
        if reserved >= 660 or time.monotonic() - started >= 1200:
            raise ValidationError("published SDG isolated invocation/time ceiling reached")
        reserved += 1
        with (output / "invocations.jsonl").open("ab") as stream:
            stream.write(canonical_bytes({"invocation": reserved, "entry": entry,
                "argument_digest": digest_value(kwargs), "code_digest": digest_value(code),
                "elapsed_seconds": time.monotonic() - started}, newline=True))
        try:
            value = executor.execute_entry(code, entry, source_numpy=True, **kwargs)
        except ValidationError as error:
            failures[type(error).__name__] += 1
            with (output / "rejections.jsonl").open("ab") as stream:
                stream.write(canonical_bytes({"invocation": reserved, "cause": str(error)[:1200]}, newline=True))
            value = None
        with (output / "program-results.jsonl").open("ab") as stream:
            stream.write(canonical_bytes({"invocation": reserved, "result": value,
                "result_digest": digest_value(value)}, newline=True))
        return value

    try:
        inputs, seed = [], 0
        prior_outputs = []
        if reuse is not None:
            events = [json.loads(line) for line in (reuse / "invocations.jsonl").read_bytes().splitlines()]
            outcomes = [json.loads(line) for line in (reuse / "program-results.jsonl").read_bytes().splitlines()]
            if (len(events) != len(outcomes) or not 630 <= len(events) <= 660 or
                    [row["invocation"] for row in events] != list(range(1, len(events) + 1)) or
                    json.loads((reuse / "programs.json").read_bytes()) !=
                    {"input": input_code, "input_validation": validation_code, "outputs": output_codes}):
                raise ValidationError("published SDG retained program coverage differs")
            for event, outcome in zip(events, outcomes):
                value = outcome["result"]
                if outcome["invocation"] != event["invocation"] or outcome["result_digest"] != digest_value(value):
                    raise ValidationError("published SDG retained execution result differs")
                if event["entry"] == "generate_puzzle_input":
                    if (prior_outputs or event["code_digest"] != digest_value(input_code) or
                            event["argument_digest"] != digest_value({"seed": seed, "validation_code": validation_code})):
                        raise ValidationError("published SDG retained input invocation differs")
                    seed += 1
                    if value is not None and all(previous != value for _, previous in inputs):
                        inputs.append([seed, value])
                elif event["entry"] == "generate_puzzle_output":
                    gid, sid = divmod(len(prior_outputs), 20)
                    if (len(inputs) != 30 or gid >= 30 or event["code_digest"] != digest_value(output_codes[sid]) or
                            event["argument_digest"] != digest_value({"input_grid": inputs[gid][1]})):
                        raise ValidationError("published SDG retained output invocation differs")
                    prior_outputs.append({"gid": gid, "sid": sid, "grid": None if value == inputs[gid][1] else value})
                else:
                    raise ValidationError("published SDG retained entry differs")
            if len(prior_outputs) != 600:
                raise ValidationError("published SDG retained output matrix is incomplete")
            reserved = len(events)
            for artifact_name in ("invocations.jsonl", "program-results.jsonl", "rejections.jsonl"):
                if (reuse / artifact_name).exists():
                    shutil.copyfile(reuse / artifact_name, output / artifact_name)
            if (reuse / "rejections.jsonl").exists():
                failures["ValidationError"] = len((reuse / "rejections.jsonl").read_bytes().splitlines())
        else:
            for _ in range(60):
                value = execute(input_code, "generate_puzzle_input", seed=seed, validation_code=validation_code)
                seed += 1
                if value is not None and all(previous != value for _, previous in inputs):
                    inputs.append([seed, value])  # exact source post-increment seed convention
                    if len(inputs) == 30:
                        break
        if len(inputs) != 30 or not input_validation["validate_grids"](inputs):
            raise ValidationError("published SDG source input diversity/30-grid gate failed")
        grids = prior_outputs
        if reuse is None:
            for gid, (_, input_grid) in enumerate(inputs):
                for sid, code in enumerate(output_codes):
                    value = execute(code, "generate_puzzle_output", input_grid=input_grid)
                    grids.append({"gid": gid, "sid": sid,
                                  "grid": None if value == input_grid else value})
        relative = Path(key[0]) / key[3] / (name + ".json")
        input_path, output_path = output / "input-grids" / relative, output / "output-grids" / relative
        input_path.parent.mkdir(parents=True)
        output_path.parent.mkdir(parents=True)
        input_path.write_bytes(canonical_bytes(inputs, newline=True))
        output_path.write_bytes(canonical_bytes({"grids": grids, "codes": output_codes}, newline=True))
        filter_namespace = _source_functions(scripts / "make_pairs.py",
            ("filter_solutions", "validate_grids", "grid_to_string", "string_to_grid"),
            {"os": os, "glob": SimpleNamespace(glob=lambda pattern: [output_path.as_posix()]),
             "json": json, "np": np, "pd": pd, "tqdm": lambda values: values, "Grid": list[list[int]],
             "open": lambda path, mode="r": builtins.open(path, mode, encoding="utf-8")})
        pair_root = output / "accepted-pairs"
        filter_namespace["filter_solutions"]((output / "input-grids").as_posix(), output_path.as_posix(),
                                             pair_root.as_posix(), 8, 12, 4)
        pair_path = pair_root / relative
        pairs = json.loads(pair_path.read_bytes()) if pair_path.exists() else []
        source_validator = sdg_build_datasets()
        if pairs and (not source_validator.validate_pairs(pairs) or
                      any(not source_validator.validate_grid(pair[side]) for pair in pairs
                          for side in ("input", "output"))):
            raise ValidationError("source augmented-dataset pair gate differs")
        if pairs:
            messages = source_sdg_messages(pairs, seed=2400, augment=True)
            (output / "augmented-messages.json").write_bytes(canonical_bytes({"parent_ids": parents,
                "exposure_tags": tags, **messages}, newline=True))
        result = {"format": "irisx/nvarc-published-sdg-replay-result-v1", "plan_digest": digest_value(plan),
                  "parent_ids": parents, "exposure_tags": tags, "input_grid_count": len(inputs),
                  "output_program_count": len(output_codes), "output_attempts": len(grids),
                  "valid_nonidentity_outputs": sum(row["grid"] is not None for row in grids),
                  "isolated_program_invocations": reserved, "program_rejections": dict(failures),
                  "new_program_invocations": reserved if reuse is None else 0,
                  "reused_program_invocations": 0 if reuse is None else reserved,
                  "accepted_pairs": len(pairs), "source_filter": plan["source_filter"],
                  "teacher_calls": 0, "contains_evaluator_truth": False, "correctness_scored": False,
                  "original_teacher_regenerated": False, "complete_dataset_verified": False,
                  "wall_seconds": time.monotonic() - started}
        (output / "result.json").write_bytes(canonical_bytes(result, newline=True))
        return result
    except BaseException as error:
        (output / "failure.json").write_bytes(canonical_bytes({"plan_digest": digest_value(plan),
            "program_invocations_reserved": reserved, "error_type": type(error).__name__,
            "error_message": str(error)[:1200], "contains_evaluator_truth": False}, newline=True))
        raise
