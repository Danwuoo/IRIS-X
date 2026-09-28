"""Distinct M2 shape-conditioned token-floor probe over public train shapes."""

import copy
import math

from .arc_nvarc_candidates import QwenCandidateBackend, solve_task
from .arc_nvarc_data import grid
from .arc_nvarc_threshold_trial import _adapter_digest, _state_identity
from .canonical import digest_value
from .errors import ValidationError


def public_output_shape(task):
    tests = task["test"]
    train = task["train"]
    if len(tests) != 1 or len(train) < 2:
        raise ValidationError("shape witness workload differs")
    inputs = [grid(row["input"]) for row in train] + [grid(tests[0]["input"])]
    outputs = [grid(row["output"]) for row in train]
    input_shapes = {(len(value), len(value[0])) for value in inputs}
    output_shapes = {(len(value), len(value[0])) for value in outputs}
    if len(input_shapes) != 1 or len(output_shapes) != 1:
        raise ValidationError("public examples do not establish one output shape")
    shape = next(iter(output_shapes))
    if shape != (6, 6) or (shape[0] * shape[1] + shape[0]) > 64:
        raise ValidationError("reviewed public shape witness differs")
    return shape


def run_shape_floor(task, backend, config, *, call_observer=None):
    task, config = copy.deepcopy((task, config))
    expected = {"maximum_calls_per_task":4, "beams_per_call":2, "maximum_new_tokens":64,
        "representation":"source-qwen", "seed":2, "source_generation_seed":2,
        "color_repeats":2, "augmentation":"source-qwen", "ranking":"source-kgmon"}
    if (type(backend) is not QwenCandidateBackend or backend.decoding != "bounded-dfs" or
        backend.dfs_max_expansions != 128 or backend.token_probability_floor is not None or
        backend.required_shape is not None or any(config.get(k) != v for k,v in expected.items())):
        raise ValidationError("reviewed M2 shape-floor workload differs")
    adaptation = {"seed":42,"rank":2,"alpha":4,"learning_rate":.00005,
        "steps":1,"max_sequence_length":128,"augmentation_count":1,
        "source_augmentation_seed":1,"source_qwen":True}
    if backend.adapter is None or any(backend.adapter.config.get(k) != v for k,v in adaptation.items()):
        raise ValidationError("reviewed M2 task adaptation differs")
    shape = public_output_shape(task)
    prior = (backend.base_model, backend.adapter, backend.token_probability_floor, backend.required_shape)
    try:
        if call_observer:
            call_observer({"kind":"ttt","status":"reserved","steps":1,"task_id":task["task_id"]})
        backend.begin_task(task)
        adapted = backend.model
        frozen = _state_identity(adapted)
        adapter_digest = _adapter_digest(adapted)
        observation = prior[1].last_observation
        if call_observer:
            call_observer({"kind":"ttt","status":"complete","observation":observation,"task_id":task["task_id"]})
        backend.base_model, backend.adapter = adapted, None
        backend.token_probability_floor, backend.required_shape = .02, shape
        def observer(event):
            if call_observer:
                call_observer({**event,"arm_id":"shape-floor-p002"})
        results = solve_task(task, backend, config, call_observer=observer)
        if _state_identity(adapted) != frozen or _adapter_digest(adapted) != adapter_digest:
            raise ValidationError("adapted model changed during M2 inference")
        count = sum(len(row["ranked"]) for row in results)
        return {"format":"irisx/nvarc-shape-token-floor-trial-v1",
            "task_visible_digest":digest_value(task),"public_output_shape":list(shape),
            "token_probability_floor":.02,"shared_adaptation":observation,
            "shared_adapter_digest":adapter_digest,"results":results,
            "generation_calls":results[-1]["generation_calls_so_far"],
            "verification_calls":results[-1]["verification_calls_so_far"],
            "explicit_forwards":backend.forward_calls,"ranked_candidates":count,
            "model_mutation_guard_passed":True,
            "claim":"public-shape-conditioned candidate availability; no ARC scoring or promotion"}
    finally:
        backend.base_model, backend.adapter, backend.token_probability_floor, backend.required_shape = prior
        backend.end_task()
