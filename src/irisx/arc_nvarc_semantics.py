"""Local SDG semantic gates. Restricted rule language, never general prose proof.

The rule interpreter checks public demonstrations, not hidden ARC answers.
Finite program probes establish bounded contract conformance, not a theorem
about arbitrary programs or the uniqueness of the demonstrated rule.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import zipfile

from .arc_nvarc_data import grid
from .arc_nvarc_sdg import WSLNamespaceProgramExecutor, extract_teacher_program
from .arc_nvarc_teacher_spec import _object
from .arc_nvarc_teacher_spec import PROMPTS as V2_PROMPTS
from .canonical import digest_value
from .errors import ValidationError

PROFILE = "qwen-rule-contract-v3"
NUMPY_WHEEL_SHA256 = "fd83c01228a688733f1ded5201c678f0c53ecc1006ffbc404db9f7a899ac6249"
NUMPY_INVENTORY_DIGEST = "sha256:d2e0186fe8ea6e3f8189f09ea47b9a8456736e1c242927fd90ff082a5e295ff0"
OPERATIONS = {"identity", "boundary-pair-swap", "rotate180", "flip-rows", "flip-columns"}

PROMPTS = {
    **V2_PROMPTS,
    "summary": """Describe EACH public puzzle with an executable rule. Return JSON
with exactly puzzle1 and puzzle2. Each has input_shape [rows,columns] and operations,
a nonempty ordered list using ONLY identity, boundary-pair-swap, rotate180,
flip-rows, flip-columns. Boundary-pair-swap flattens row-major, swaps the first
two and last two cells, keeps the rest, and reshapes. Operations run left to right.
The rule must reproduce EVERY supplied demonstration. This restricted language
may not express a puzzle; do not substitute prose or invent another operation.
Puzzle 1: {PUZZLE1_DEMOS}
Puzzle 2: {PUZZLE2_DEMOS}
""",
    "mix": """Return JSON with exactly shape and output_from_input. Generalize
the DEMONSTRATION-CHECKED puzzle1 operations to shape {SHAPE}, then execute
puzzle2 operations. Flatten row-major; output_from_input lists the final source
index at each output position, each source index exactly once. No prose or code.
Puzzle 1: {PUZZLE1}
Puzzle 2: {PUZZLE2}
"""}


def prompt_values(stage, item):
    history = item.get("stage_responses", {})
    if stage == "summary":
        return {"PUZZLE1_DEMOS": json.dumps(item["train_demos"]),
                "PUZZLE2_DEMOS": json.dumps(item["second_train_demos"])}
    summary = semantic_stage("summary", history["summary"]["content"], item)
    if stage == "mix":
        return {"SHAPE": json.dumps(shape(item["composition_shape"])),
                "PUZZLE1": json.dumps(summary["puzzle1"]),
                "PUZZLE2": json.dumps(summary["puzzle2"])}
    spec = semantic_stage("mix", history["mix"]["content"], item)
    values = {"PUZZLE": json.dumps(spec)}
    if stage == "output-logic":
        values["INPUT_CODE"] = history["input-logic"]["content"]
    elif stage != "input-logic":
        raise ValidationError("unknown_semantic_prompt_stage")
    return values


def shape(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) is not int or not 1 <= x <= 30 for x in value)):
        raise ValidationError("rule_shape_invalid")
    return value


def apply_rule(rows, operations):
    """Trusted reference interpreter over colors; no teacher code evaluated."""
    value = grid(rows)
    if (not isinstance(operations, list) or not 1 <= len(operations) <= 8 or
            any(not isinstance(op, str) or op not in OPERATIONS for op in operations)):
        raise ValidationError("rule_operation_unsupported")
    for op in operations:
        if op == "rotate180":
            value = [row[::-1] for row in value[::-1]]
        elif op == "flip-rows":
            value = value[::-1]
        elif op == "flip-columns":
            value = [row[::-1] for row in value]
        elif op == "boundary-pair-swap":
            flat = [color for row in value for color in row]
            if len(flat) < 4:
                raise ValidationError("boundary_pairs_overlap")
            flat[0], flat[1] = flat[1], flat[0]
            flat[-2], flat[-1] = flat[-1], flat[-2]
            width = len(value[0])
            value = [flat[i:i + width] for i in range(0, len(flat), width)]
    return value


def validate_summary(summary, demo_groups):
    """Require executable claims and check EVERY supplied demonstration."""
    if not isinstance(summary, dict) or set(summary) != set(demo_groups):
        raise ValidationError("summary_parents_differ")
    for name, demos in demo_groups.items():
        rule = summary[name]
        if not isinstance(rule, dict) or set(rule) != {"input_shape", "operations"}:
            raise ValidationError("summary_executable_rule_required:" + name)
        declared = shape(rule["input_shape"])
        if not isinstance(demos, list) or len(demos) < 2:
            raise ValidationError("summary_insufficient_demonstrations:" + name)
        for index, demo in enumerate(demos):
            if set(demo) != {"input", "output"}:
                raise ValidationError("summary_demo_fields_differ")
            before, after = grid(demo["input"]), grid(demo["output"])
            if [len(before), len(before[0])] != declared:
                raise ValidationError("summary_shape_mismatch:" + name)
            if apply_rule(before, rule["operations"]) != after:
                raise ValidationError(f"summary_demo_mismatch:{name}:{index}")
    return copy.deepcopy(summary)


def legacy_rotation_claim(summary):
    """Negative-replay adapter for a single unambiguous retained prose claim.

    This is not a natural-language verifier. Other prose fails closed and v3
    never accepts prose as a substitute for an executable rule.
    """
    converted = {}
    for name, rule in summary.items():
        text = rule.get("rule", "").lower()
        if not text.startswith("the output grid is the input grid rotated 180 degrees,"):
            raise ValidationError("legacy_prose_unverified")
        converted[name] = {"input_shape": rule["input_shape"], "operations": ["rotate180"]}
    return converted


def compose_order(target_shape, rules):
    """Derive an index map from operations on one-hot COLOR probes.

    Using binary grids keeps the interpreter in its real 0..9 domain while
    recovering arbitrary <=30x30 permutations without out-of-domain labels.
    """
    height, width = shape(target_shape)
    count = height * width
    order = [None] * count
    for index in range(count):
        flat = [int(i == index) for i in range(count)]
        value = [flat[i:i + width] for i in range(0, count, width)]
        for operations in rules:
            value = apply_rule(value, operations)
        result = [c for row in value for c in row]
        if result.count(1) != 1:
            raise ValidationError("composition_not_permutation")
        order[result.index(1)] = index
    return order


def validate_mix(spec, target_shape, ordered_rules):
    if not isinstance(spec, dict) or set(spec) != {"shape", "output_from_input"}:
        raise ValidationError("mix_schema_invalid")
    if shape(spec["shape"]) != shape(target_shape):
        raise ValidationError("mix_shape_mismatch")
    order = spec["output_from_input"]
    count = target_shape[0] * target_shape[1]
    if (not isinstance(order, list) or any(type(x) is not int for x in order) or
            sorted(order) != list(range(count))):
        raise ValidationError("mix_indices_invalid")
    if order != compose_order(target_shape, ordered_rules):
        raise ValidationError("mix_composition_mismatch")
    return copy.deepcopy(spec)


def semantic_stage(stage, text, item):
    groups = {"puzzle1": item["train_demos"], "puzzle2": item["second_train_demos"]}
    if stage == "summary":
        return validate_summary(_object(text), groups)
    summary = validate_summary(_object(item["stage_responses"]["summary"]["content"]), groups)
    if stage == "mix":
        return validate_mix(_object(text), item["composition_shape"],
                            [summary[key]["operations"] for key in ("puzzle1", "puzzle2")])
    raise ValidationError("unknown_semantic_stage")


def accept_semantic_record(item, responses, executor):
    """Full gate with raw-response lineage; schema success alone accepts nothing."""
    from .arc_nvarc_sdg import validate_teacher_response
    checked = copy.deepcopy(responses)
    for stage in ("summary", "mix", "input-logic", "output-logic"):
        validate_teacher_response(stage, checked[stage])  # EOS/AST, unchanged raw text
    summary = validate_summary(_object(checked["summary"]["content"]), {
        "puzzle1": item["train_demos"], "puzzle2": item["second_train_demos"]})
    spec = validate_mix(_object(checked["mix"]["content"]), item["composition_shape"],
                        [summary[key]["operations"] for key in ("puzzle1", "puzzle2")])
    accepted = accept_program_pairs(checked["input-logic"]["content"],
                                    checked["output-logic"]["content"], spec, executor)
    return {**accepted, "profile": PROFILE, "record_id": item["record_id"],
            "parent_binding": digest_value({"train_demos": item["train_demos"],
                                           "second_train_demos": item["second_train_demos"]}),
            "raw_response_digests": {stage: digest_value(value) for stage, value in responses.items()}}


class SemanticProgramExecutor(WSLNamespaceProgramExecutor):
    """Existing namespace boundary with ONLY a digest-bound cached NumPy mount."""

    def __init__(self, dependencies: Path, *, launcher: Path | None = None, launcher_sha256: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.launcher = launcher
        self.launcher_sha256 = launcher_sha256
        self.dependencies = dependencies.resolve()
        manifest = json.loads((dependencies / "inventory.json").read_bytes())
        if digest_value(manifest) != NUMPY_INVENTORY_DIGEST:
            raise ValidationError("sandbox_dependency_inventory_differs")
        actual = {p.relative_to(dependencies).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in dependencies.rglob("*") if p.is_file() and p.name != "inventory.json"}
        if actual != manifest["files"] or not actual or any(p.is_symlink() for p in dependencies.rglob("*")):
            raise ValidationError("sandbox_dependency_inventory_differs")
        self.material_digest = digest_value(manifest)

    def command(self):
        import os
        if os.name == "posix":
            if (self.launcher is None or self.launcher.is_symlink() or not self.launcher.is_file() or
                    hashlib.sha256(self.launcher.read_bytes()).hexdigest() != self.launcher_sha256):
                raise ValidationError("semantic_namespace_launcher_unavailable")
            import sys
            if not sys.executable.startswith("/usr/"):
                raise ValidationError("semantic_namespace_python_prefix_unsupported")
            return ["sh", str(self.launcher.resolve()), str(self.dependencies), sys.executable]
        root = Path(__file__).resolve().parents[2]
        launcher = root / "tools/nvarc_sdg_semantic_namespace.sh"
        if not launcher.is_file() or self.dependencies.drive.lower() != "c:":
            raise ValidationError("semantic_namespace_launcher_unavailable")
        linux = lambda p: "/mnt/c" + p.resolve().as_posix()[2:]
        return ["wsl", "-d", self.distribution, "--", "sh", linux(launcher), linux(self.dependencies)]

    def probe(self, code, entry, *, seed=None, input_grid=None):
        if entry not in {"generate_puzzle_input", "generate_puzzle_output"} or len(code.encode()) > self.output_bytes:
            raise ValidationError("semantic_program_bounds_invalid")
        if entry == "generate_puzzle_input":
            if type(seed) is not int or not 0 <= seed <= 1000000:
                raise ValidationError("semantic_seed_invalid")
            arguments = {"seed": seed}
        else:
            arguments = {"grid": grid(input_grid)}
        return self._execute_payload(json.dumps({"code": code, "entry": entry, **arguments}).encode())


def prepare_numpy(wheel: Path, target: Path):
    """Materialize existing Linux cp312 wheel only; no install or network fetch."""
    if target.exists() or not wheel.name.startswith("numpy-") or "cp312" not in wheel.name or "manylinux" not in wheel.name:
        raise ValidationError("cached_numpy_target_or_wheel_invalid")
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != NUMPY_WHEEL_SHA256:
        raise ValidationError("cached_numpy_wheel_digest_differs")
    target.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = Path(name).parts
            if name.startswith(("/", "\\")) or ".." in parts or not parts or parts[0] not in {"numpy", "numpy.libs"}:
                continue
            archive.extract(name, target)
    manifest = {"wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "files": {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in target.rglob("*") if p.is_file()}}
    (target / "inventory.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest


def _typed_grid(observation, expected_shape, label):
    if observation.get("error"):
        raise ValidationError(label + "_execution_error:" + observation["error"])
    if observation.get("kind") != "ndarray" or observation.get("dtype_kind") not in {"i", "u"}:
        raise ValidationError(label + "_type_mismatch")
    if observation.get("shape") != expected_shape:
        raise ValidationError(label + "_shape_mismatch")
    try:
        return grid(observation["value"])
    except (ValidationError, KeyError) as error:
        raise ValidationError(label + "_color_or_grid_invalid") from error


def accept_program_pairs(input_text, output_text, spec, executor, *, seeds=(11, 22, 33, 44, 55)):
    """Bounded challenge suite before source filtering, with concrete safe executors.

    The namespace executor runs isolated Python. The exact AST executor runs
    no teacher code at all and accepts only its reviewed syntax family.
    Caller-provided callbacks remain prohibited. No pair survives rejection.
    """
    from .arc_nvarc_safe_ast import SafeASTProgramExecutor
    if type(executor) not in {SemanticProgramExecutor, SafeASTProgramExecutor}:
        raise ValidationError("verified_semantic_program_executor_required")
    # Trusted pinned source/dependencies must be ready BEFORE any program call.
    from .arc_nvarc_upstream import sdg_build_datasets
    source = sdg_build_datasets()
    if len(seeds) < 5 or len(set(seeds)) != len(seeds):
        raise ValidationError("semantic_seed_suite_invalid")
    target = shape(spec["shape"])
    order = spec["output_from_input"]
    count = target[0] * target[1]
    if count > 30:
        raise ValidationError("semantic_challenge_cell_limit")
    if any(type(i) is not int for i in order) or sorted(order) != list(range(count)):
        raise ValidationError("semantic_permutation_invalid")
    input_code = extract_teacher_program(input_text, "generate_puzzle_input")
    output_code = extract_teacher_program(output_text, "generate_puzzle_output")
    pairs = []
    for seed in seeds:
        before = _typed_grid(executor.probe(input_code, "generate_puzzle_input", seed=seed), target, "input")
        again = _typed_grid(executor.probe(input_code, "generate_puzzle_input", seed=seed), target, "input")
        if before != again:
            raise ValidationError("input_seed_nondeterministic")
        pairs.append({"input": before})
    if len({digest_value(pair["input"]) for pair in pairs}) < 3:
        raise ValidationError("input_seed_variation_missing")
    cell_traces = list(zip(*([c for row in p["input"] for c in row] for p in pairs)))
    if any(len(set(trace)) < 2 for trace in cell_traces):
        raise ValidationError("input_cell_variation_missing")
    if len(set(cell_traces)) != count:
        raise ValidationError("input_correlated_cell_traces")
    # Exhaustive one-hot bases plus repeated/offset colors expose programs that
    # return index labels, ignore color values, use wrong flattening, or only
    # match the particular generated training samples.
    challenges = []
    for index in range(count):
        flat = [9 if i == index else 0 for i in range(count)]
        challenges.append([flat[i:i + target[1]] for i in range(0, count, target[1])])
    for offset in (0, 3, 7):
        flat = [(i + offset) % 10 for i in range(count)]
        challenges.append([flat[i:i + target[1]] for i in range(0, count, target[1])])
    measured = {}
    for before in [p["input"] for p in pairs] + challenges:
        flat = [c for row in before for c in row]
        selected = [flat[i] for i in order]
        expected = [selected[i:i + target[1]] for i in range(0, count, target[1])]
        after = _typed_grid(executor.probe(output_code, "generate_puzzle_output", input_grid=before), target, "output")
        repeated = _typed_grid(executor.probe(output_code, "generate_puzzle_output", input_grid=before), target, "output")
        if after != repeated:
            raise ValidationError("output_nondeterministic")
        if after != expected:
            raise ValidationError("output_permutation_mismatch")
        measured[digest_value(before)] = after
    for pair in pairs:
        pair["output"] = measured[digest_value(pair["input"])]
    if not all(source.validate_grid(p[side]) for p in pairs for side in ("input", "output")) or not source.validate_pairs(pairs):
        raise ValidationError("source_pair_filter_rejected")
    return {"status": "accepted-bounded-contract", "pairs": pairs,
            "program_digests": {"input": digest_value(input_code), "output": digest_value(output_code)},
            "spec_digest": digest_value(spec), "sandbox_material_digest": executor.material_digest,
            "seeds": list(seeds), "output_challenges": len(challenges),
            "program_invocations": 2 * len(seeds) + 2 * (len(seeds) + len(challenges)),
            "program_validation_mode": ("isolated-namespace-python" if
                type(executor) is SemanticProgramExecutor else "trusted-ast-interpretation"),
            "teacher_programs_executed": type(executor) is SemanticProgramExecutor,
            "source_filter_passed": True, "teacher_yield_claim": False,
            "random_distribution_proven": False,
            "limitation": "finite seed/color probes reject observed correlations; do not prove distributional independence or universal program equivalence"}
