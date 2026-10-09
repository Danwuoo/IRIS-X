"""Eight locally authored synthetic families; no ARC data or imported generators.

All targets come from explicit family formulas, then receive fresh bounded
verification. One successful execution certifies both the witness and identical
repair target; a separate execution must establish a genuine semantic failure.
Nothing runs or writes on import.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import time

from arc_typed_ir import (canonical_json, compile_plan, digest, grammar_manifest,
                          validate_plan, IR_VERSION)

CURRICULUM_VERSION = "irisx/authored-fgpr-curriculum-v1"
FAMILIES = (
    "mirror_columns", "clockwise_quarter_turn", "replace_marker",
    "remove_background_border", "nearest_neighbor_double", "repeat_columns",
    "transpose_then_replace", "largest_object_box",
)
FAMILY_SPLIT = {family: ("train" if i < 6 else "validation")
                for i, family in enumerate(FAMILIES)}
DEFAULT_EPISODES = 512
MAX_VERIFICATIONS = 1024
MAX_WALL_SECONDS = 1200.0
PINNED_VERIFIER_SHA256 = "52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d"
PINNED_INTERPRETER_SHA256 = "9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7"
CALL_STEP_RESERVATION = 200000


class CurriculumError(ValueError):
    pass


def _seed(root, *parts):
    value = canonical_json([root, *parts]).encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def _palette(rng):
    colors = list(range(1, 10))
    rng.shuffle(colors)
    return colors


def _base(rng, height=None, width=None, palette=None):
    height = height or rng.randint(2, 4)
    width = width or rng.randint(5, 7)
    colors = palette or _palette(rng)
    grid = [[rng.choice([0, colors[0], colors[1]]) for _ in range(width)]
            for _ in range(height)]
    # Four distinct corners make horizontal/vertical and clockwise/counter-
    # clockwise mutations observably different on every generated example.
    grid[0][0], grid[0][-1] = colors[0], colors[1]
    grid[-1][0], grid[-1][-1] = colors[2], colors[3]
    return grid


def family_plans(family, parameters):
    """Authored witness and admitted semantic mutation, independently of grids."""
    source, target, wrong = parameters[:3]
    specs = {
        "mirror_columns": ([{"op": "flip_horizontal"}], [{"op": "flip_vertical"}]),
        "clockwise_quarter_turn": ([{"op": "rotate", "turns": 1}], [{"op": "rotate", "turns": 3}]),
        "replace_marker": ([{"op": "recolor", "source": source, "target": target}],
                           [{"op": "recolor", "source": source, "target": wrong}]),
        "remove_background_border": ([{"op": "crop_nonbackground", "background": 0}], [{"op": "identity"}]),
        "nearest_neighbor_double": ([{"op": "scale", "factor": 2}], [{"op": "scale", "factor": 3}]),
        "repeat_columns": ([{"op": "tile", "rows": 1, "columns": 2}],
                           [{"op": "tile", "rows": 2, "columns": 1}]),
        "transpose_then_replace": ([{"op": "transpose"}, {"op": "recolor", "source": source, "target": target}],
                                   [{"op": "transpose"}]),
        "largest_object_box": ([{"op": "largest_component_crop", "background": 0, "connectivity": 4}],
                               [{"op": "crop_nonbackground", "background": 0}]),
    }
    if family not in specs:
        raise CurriculumError("unknown authored family")
    witness, mutation = specs[family]
    return validate_plan({"steps": witness}), validate_plan({"steps": mutation})


def authored_example(family, seed, parameters):
    """Reference output formulas; never evaluate generated source or IR here."""
    rng = random.Random(seed)
    colors = list(parameters)
    if family == "largest_object_box":
        h, w = rng.randint(7, 9), rng.randint(7, 9)
        grid = [[0] * w for _ in range(h)]
        oh, ow = rng.randint(2, 3), rng.randint(2, 3)
        r0, c0 = rng.randint(1, 2), rng.randint(1, 2)
        for r in range(r0, r0 + oh):
            for c in range(c0, c0 + ow):
                grid[r][c] = colors[0]
        grid[h - 1][w - 1] = colors[1]
        return grid, [[colors[0]] * ow for _ in range(oh)]
    grid = _base(rng, palette=colors)
    if family == "mirror_columns":
        output = [list(reversed(row)) for row in grid]
    elif family == "clockwise_quarter_turn":
        output = [[grid[r][c] for r in range(len(grid) - 1, -1, -1)]
                  for c in range(len(grid[0]))]
    elif family == "replace_marker":
        output = [[colors[1] if x == colors[0] else x for x in row] for row in grid]
    elif family == "remove_background_border":
        output = [row[:] for row in grid]
        top, bottom, left, right = [rng.randint(1, 2) for _ in range(4)]
        width = len(grid[0]) + left + right
        grid = ([[0] * width for _ in range(top)] +
                [[0] * left + row + [0] * right for row in grid] +
                [[0] * width for _ in range(bottom)])
    elif family == "nearest_neighbor_double":
        output = [doubled[:] for row in grid
                  for doubled in [[cell for x in row for cell in (x, x)]]
                  for _ in range(2)]
    elif family == "repeat_columns":
        output = [row + row for row in grid]
    elif family == "transpose_then_replace":
        output = [[colors[1] if grid[r][c] == colors[0] else grid[r][c]
                   for r in range(len(grid))] for c in range(len(grid[0]))]
    else:
        raise CurriculumError("unknown authored family")
    return grid, output


def _validate_family_split(split):
    if type(split) is not dict or set(split) != set(FAMILIES):
        raise CurriculumError("split must assign every authored family exactly once")
    if any(value not in ("train", "validation") for value in split.values()):
        raise CurriculumError("invalid split")
    if sum(v == "train" for v in split.values()) != 6:
        raise CurriculumError("six train and two validation families required")
    # This fixed split is part of the frozen experiment, not a tuning option.
    if split != FAMILY_SPLIT:
        raise CurriculumError("family split differs from preregistered split")


def build_episode(index, *, seed=1015, family_split=None):
    split = dict(FAMILY_SPLIT if family_split is None else family_split)
    _validate_family_split(split)
    if type(index) is not int or not 0 <= index < DEFAULT_EPISODES:
        raise CurriculumError("episode index outside fixed curriculum")
    if type(seed) is not int or not 0 <= seed < 2 ** 63:
        raise CurriculumError("invalid root seed")
    family = FAMILIES[index // 64]
    augmentation = index % 64
    parameters = _palette(random.Random(_seed(seed, family, augmentation, "parameters")))
    plan, mutation = family_plans(family, parameters)
    examples, seeds, seen = [], {}, set()
    for role in ("demo_0", "demo_1", "query"):
        for nonce in range(16):
            sample_seed = _seed(seed, family, augmentation, role, nonce)
            grid, output = authored_example(family, sample_seed, parameters)
            input_hash = digest(grid)
            if input_hash not in seen:
                seen.add(input_hash)
                examples.append({"input": grid, "output": output})
                seeds[role] = sample_seed
                break
        else:
            raise CurriculumError("could not generate independent distinct examples")
    return {"episode_id": "%s-%03d" % (family, augmentation), "family": family,
            "split": split[family], "augmentation_index": augmentation,
            "parameters": parameters, "sample_seeds": seeds,
            "task": {"train": examples[:2], "test": [{"input": examples[2]["input"]}]},
            "query_target": examples[2]["output"], "witness_plan": plan,
            "mutation_plan": mutation, "witness_program": compile_plan(plan),
            "mutation_program": compile_plan(mutation)}


def fresh_verifier(agent_path, verifier_path=None):
    """Bind the reviewed verifier to the pinned interpreter, fresh child/call."""
    path = Path(agent_path).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != PINNED_INTERPRETER_SHA256:
        raise CurriculumError("interpreter source binding mismatch")
    wrapper_path = (Path(verifier_path) if verifier_path is not None else
                    path.with_name("arc_program_v2.py")).resolve()
    with wrapper_path.open("rb") as handle:
        wrapper_source = handle.read(100001)
    if len(wrapper_source) > 100000 or hashlib.sha256(wrapper_source).hexdigest() != PINNED_VERIFIER_SHA256:
        raise CurriculumError("verifier source binding mismatch")
    class CapturedSourceLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            if fullname != "irisx_curriculum_pinned_verifier":
                raise ImportError("unexpected verifier module name")
            # Compile only the captured, exact-hash trusted application module.
            # This deliberately bypasses any pyc and never sees candidate code.
            return self.source_to_code(wrapper_source, str(wrapper_path))
    loader = CapturedSourceLoader("irisx_curriculum_pinned_verifier", str(wrapper_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None or spec.loader is None:
        raise CurriculumError("pinned verifier loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    def verify(source, task, *, timeout_seconds=3.0):
        return module.verify_program(source, task, path, timeout_seconds=timeout_seconds)
    verify.provenance = {"implementation": "arc_program_v2.verify_program",
                         "fresh_os_limited_child_per_call": True,
                         "interpreter_sha256": PINNED_INTERPRETER_SHA256,
                         "verifier_sha256": PINNED_VERIFIER_SHA256,
                         "captured_source_cache_bypass": True}
    return verify


def _check_receipt(result, episode, *, mutation):
    if type(result) is not dict:
        raise CurriculumError("missing verifier result")
    for phase in ("format_admitted", "python_parse_admitted", "ast_admitted", "demo_execution_success"):
        if result.get(phase) is not True:
            raise CurriculumError("%s %s failed at %s" % (episode["episode_id"], "mutation" if mutation else "witness", phase))
    feedback = result.get("feedback")
    if type(feedback) is not dict or len(feedback.get("demonstrations", [])) != 2:
        raise CurriculumError("incomplete demonstration evidence")
    if mutation:
        if (result.get("error_category") != "demo_mismatch" or
                result.get("all_demonstrations_exact") is not False or
                all(row.get("exact") for row in feedback["demonstrations"])):
            raise CurriculumError("mutation is not a verified semantic mismatch")
    elif (result.get("all_demonstrations_exact") is not True or
          result.get("query_execution_success") is not True or
          result.get("candidate") != episode["query_target"] or
          result.get("error_category") is not None):
        raise CurriculumError("witness does not match independently authored query target")
    if type(result.get("program_steps")) is not int or not 0 < result["program_steps"] <= 200000:
        raise CurriculumError("invalid interpreter accounting")


def _receipt(result):
    # Operational wall timings are kept outside deterministic payloads/hashes.
    return {key: value for key, value in result.items()
            if key not in ("verification_seconds", "candidate")}


def _training_record(episode, witness_result, mutation_result):
    task = episode["task"]
    program = episode["witness_program"]
    return {"format": CURRICULUM_VERSION, "episode_id": episode["episode_id"],
            "family": episode["family"], "split": episode["split"],
            "augmentation_index": episode["augmentation_index"],
            "provenance": {"generator": "explicit_authored_family", "root_sources": "this module only",
                           "sample_seeds": episode["sample_seeds"],
                           "family_parameters": episode["parameters"],
                           "witness_plan_sha256": digest(episode["witness_plan"]),
                           "witness_source_sha256": hashlib.sha256(program.encode()).hexdigest()},
            "F": {"objective": "format_only_supplied_program_copy",
                  "input": {"instruction": "Return the supplied program verbatim as raw bounded source, without Markdown or prose; do not infer a transformation.",
                            "supplied_program": program},
                  "target": program, "target_format": "raw_bounded_source"},
            "G": {"objective": "predict_query_grid", "input": task,
                  "target": canonical_json(episode["query_target"]), "target_format": "grid_json"},
            "P": {"objective": "infer_bounded_program", "input": task,
                  "target": program, "target_format": "raw_bounded_source"},
            "R": {"objective": "repair_semantically_wrong_program",
                  "input": {"task": task, "failed_program": episode["mutation_program"],
                            "visible_demo_feedback": mutation_result["feedback"]},
                  "target": program, "target_format": "raw_bounded_source",
                  "failure_kind": "semantic", "mutation_plan": episode["mutation_plan"],
                  "repair_equals_verified_witness": True},
            "verification": {"witness_and_identical_repair": _receipt(witness_result),
                             "mutation": _receipt(mutation_result)}}


def make_curriculum(output, verify_fn, *, seed=1015, episodes=512,
                    max_verifications=1024, wall_seconds=1200, family_split=None):
    """Export fixed 512 episodes, or fail closed without a completed manifest.

    verify_fn must accept (source, task, timeout_seconds=...). Use fresh_verifier
    in production. The call budget is exactly 2 per episode; no retry consumes
    unrecorded calls. The frozen wall deadline is checked around every call and
    passed through as a tightened fresh-worker timeout. Custom verification
    functions are test adapters and must expose equivalent truthful provenance.
    """
    if type(episodes) is not int or episodes != DEFAULT_EPISODES:
        raise CurriculumError("the frozen curriculum contains exactly 512 episodes")
    if type(max_verifications) is not int or max_verifications != MAX_VERIFICATIONS:
        raise CurriculumError("the frozen call ceiling is 1024")
    if type(wall_seconds) not in (int, float) or not math.isfinite(wall_seconds) or not 0 < wall_seconds <= MAX_WALL_SECONDS:
        raise CurriculumError("invalid bounded wall budget")
    split = dict(FAMILY_SPLIT if family_split is None else family_split)
    _validate_family_split(split)
    if type(seed) is not int or not 0 <= seed < 2 ** 63:
        raise CurriculumError("invalid root seed")
    provenance = getattr(verify_fn, "provenance", None)
    if (type(provenance) is not dict or provenance.get("fresh_os_limited_child_per_call") is not True
            or not provenance.get("interpreter_sha256") or not provenance.get("verifier_sha256")):
        raise CurriculumError("fresh verifier provenance is required")
    # Reject adapters unable to receive a deadline rather than silently dropping it.
    inspect.signature(verify_fn).bind("source", {}, timeout_seconds=1.0)
    destination = Path(output)
    if destination.exists():
        raise CurriculumError("output already exists; immutable export will not overwrite it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + wall_seconds
    import arc_typed_ir
    generator_source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    compiler_source_hash = hashlib.sha256(Path(arc_typed_ir.__file__).read_bytes()).hexdigest()
    grammar_snapshot = grammar_manifest()
    calls, total_steps = 0, 0
    ledger = []
    verifier_seconds = 0.0
    count_by_split = {"train": 0, "validation": 0}
    witness_hashes = set()
    staging = Path(tempfile.mkdtemp(prefix=".curriculum-", dir=destination.parent))
    try:
        with (staging / "episodes.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for index in range(episodes):
                episode = build_episode(index, seed=seed, family_split=split)
                results = []
                for mutation in (False, True):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or calls >= max_verifications:
                        raise CurriculumError("curriculum budget exhausted")
                    calls += 1
                    program = episode["mutation_program" if mutation else "witness_program"]
                    entry = {"call_id": calls, "episode_id": episode["episode_id"],
                             "role": "mutation" if mutation else "witness_and_identical_repair",
                             "source_sha256": hashlib.sha256(program.encode()).hexdigest(),
                             "task_sha256": digest(episode["task"]), "status": "attempted",
                             "usage_known": False, "charged_program_steps": CALL_STEP_RESERVATION,
                             "returned_program_steps": None}
                    ledger.append(entry)
                    total_steps += CALL_STEP_RESERVATION
                    call_started = time.monotonic()
                    try:
                        result = verify_fn(program, episode["task"], timeout_seconds=min(3.0, remaining))
                    except BaseException as exc:
                        entry["status"] = "verifier_raised"
                        entry["exception_type"] = type(exc).__name__
                        raise
                    finally:
                        elapsed = time.monotonic() - call_started
                        entry["wall_seconds"] = elapsed
                        verifier_seconds += elapsed
                    entry["status"] = "returned"
                    steps = result.get("program_steps") if type(result) is dict else None
                    if type(steps) is int and 0 <= steps <= CALL_STEP_RESERVATION:
                        total_steps += steps - CALL_STEP_RESERVATION
                        entry["charged_program_steps"] = steps
                        entry["returned_program_steps"] = steps
                        entry["usage_known"] = True
                    else:
                        entry["status"] = "returned_untrusted_usage"
                    if type(result) is dict:
                        category = result.get("error_category")
                        entry["error_category"] = category[:64] if type(category) is str else None
                    # Charge returned work before either wall or semantic checks.
                    if time.monotonic() > deadline:
                        raise CurriculumError("curriculum wall deadline exceeded")
                    _check_receipt(result, episode, mutation=mutation)
                    entry["status"] = "validated"
                    results.append(result)
                record = _training_record(episode, *results)
                handle.write(canonical_json(record) + "\n")
                count_by_split[episode["split"]] += 1
                witness_hashes.add(record["provenance"]["witness_source_sha256"])
        if calls != 1024 or count_by_split != {"train": 384, "validation": 128}:
            raise CurriculumError("incomplete frozen curriculum")
        data = (staging / "episodes.jsonl").read_bytes()
        ledger_data = "".join(canonical_json(row) + "\n" for row in ledger).encode()
        (staging / "verification-ledger.jsonl").write_bytes(ledger_data)
        if (generator_source_hash != hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or
                compiler_source_hash != hashlib.sha256(Path(arc_typed_ir.__file__).read_bytes()).hexdigest()):
            raise CurriculumError("compiler or generator changed during export")
        manifest = {"format": CURRICULUM_VERSION, "status": "complete", "seed": seed,
                    "episodes": episodes, "families": list(FAMILIES), "family_split": split,
                    "split_before_augmentation": True, "family_split_sha256": digest(split),
                    "split_counts": count_by_split, "objectives": ["F", "G", "P", "R"],
                    "file": "episodes.jsonl", "payload_sha256": hashlib.sha256(data).hexdigest(),
                    "payload_bytes": len(data), "witness_source_hashes": sorted(witness_hashes),
                    "grammar": grammar_snapshot, "verifier": provenance,
                    "generator_sha256": generator_source_hash,
                    "compiler_sha256": compiler_source_hash,
                    "provenance": {"ARC_inputs": False, "evaluation_gold": False,
                                   "imported_generators": False, "model_calls": 0,
                                   "training_performed": False, "external_upload": False,
                                   "reference_outputs": "independent explicit authored family formulas"},
                    "accounting": {"fresh_verifier_calls": calls, "program_steps": total_steps,
                                   "attempted_calls": calls, "returned_calls": sum(row["status"] != "verifier_raised" for row in ledger),
                                   "unknown_usage_calls": sum(not row["usage_known"] for row in ledger),
                                   "ledger_file": "verification-ledger.jsonl",
                                   "ledger_sha256": hashlib.sha256(ledger_data).hexdigest(),
                                   "max_verifications": max_verifications, "wall_limit_seconds": wall_seconds,
                                   "verifier_wall_seconds": verifier_seconds,
                                   "generator_wall_seconds": time.monotonic() - started},
                    "repair_verification": "Repair source is byte-identical to witness; same successful receipt certifies both.",
                    "limitations": ["Family holdout is synthetic, not an ARC benchmark.",
                                    "Primitive overlap across families is intentional; no unseen-primitive claim.",
                                    "No training, model-quality or broad language-coverage claim."]}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        if time.monotonic() > deadline:
            (staging / "manifest.json").unlink()
            raise CurriculumError("curriculum wall deadline exceeded before publication")
        # The final directory appears only after every witness and mutation passes.
        os.rename(staging, destination)
        return manifest
    except BaseException:
        # Preserve bounded diagnostics, but never masquerade a partial dataset as complete.
        if (staging / "manifest.json").exists():
            (staging / "manifest.json").unlink()
        ledger_data = "".join(canonical_json(row) + "\n" for row in ledger).encode()
        (staging / "verification-ledger.jsonl").write_bytes(ledger_data)
        (staging / "FAILED.json").write_text(canonical_json({
            "status": "failed", "fresh_verifier_calls": calls, "attempted_calls": calls,
            "returned_calls": sum(row["status"] in ("returned", "returned_untrusted_usage", "validated") for row in ledger),
            "unknown_usage_calls": sum(not row["usage_known"] for row in ledger),
            "program_steps": total_steps,
            "conservative_reserved_steps": sum(row["charged_program_steps"] for row in ledger if not row["usage_known"]),
            "ledger_file": "verification-ledger.jsonl",
            "ledger_sha256": hashlib.sha256(ledger_data).hexdigest(),
            "verifier_wall_seconds": verifier_seconds,
            "generator_wall_seconds": time.monotonic() - started}) + "\n")
        raise
