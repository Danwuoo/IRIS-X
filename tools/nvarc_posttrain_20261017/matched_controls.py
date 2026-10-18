"""Bounded compact, frozen-anchor collection and matched-loss mechanism screen.

No data loader, model loader, evaluator, selection, provider, or publication lives
here. The caller must independently admit the training partition and pin the
manifest BEFORE collection. Hashes detect substitution, not a dishonest source
or semantic independence. Known-variant detection has its documented syntactic
limits; family lineage is supplied by the admitted source, never inferred here.

All complete groups, including all-wrong/all-correct, remain in the shared pool.
Incomplete groups are retained and charged but excluded from EVERY loss. Target
CE weights complete groups equally. Positive CE weights each group's unique
compact target by its observed positive count: it mainly reweights prompts, not
novel reasoning paths. DDIS uses only complete mixed groups and the real upstream
AF3 implementation through CompactEngine.af3_update. This is one optimizer step
per active arm, NOT equal compute, full DAPO/RAFT, or evidence of effectiveness.

Returned states are exact named trainables relative to the hash-verified frozen
base, not full-model copies or optimizer/RNG resume checkpoints. All exits restore
entry trainables and verify the FULL policy. Poisoned engines remain poisoned.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import math
import random
import re
import time

import torch

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import canonical, valid_grid
from tools.arc2_goal_sprint_20261017.model import (
    PhaseDeadline, adapter_state, check_deadline, make_optimizer, restore_state, state_digest,
)
from .codec import encode_example, grid_tokens, parse_completion
from .engine import (CompactEngine, FatalUpdateError, model_contract,
                     validate_tokenizer, validate_trainables)

FORMAT = "irisx/compact-matched-controls-v1"
ADMISSION_FORMAT = "irisx/compact-training-panel-v1"
ARMS = ("anchor", "known_target_ce", "exact_positive_ce", "exact_centered_ddis")
GROUP_SIZE = 8
COUNTERS = ("forward_calls", "sampled_tokens", "optimizer_steps", "optimizer_attempts",
            "generation_forward_attempts", "generation_input_tokens", "generation_row_token_slots",
            "generation_finished_row_token_slots", "generation_padding_tokens")
DEFAULT_CONFIG = {"seed": 0, "max_groups": 64, "target_mixed_groups": 8,
                  "microbatch": 2, "context_tokens": 8192, "generation_tokens": 931,
                  "learning_rate": 2e-5}
ROW_KEYS = {"input_ids", "prompt_length", "completion_ids", "behavior_log_probs", "text",
            "completion_tokens", "stop", "group_id", "sample_id", "reward", "parent_id",
            "family_id", "variant_group", "task_sha256", "training_target", "policy_sha256",
            "anchor_sha256", "model_identity_sha256", "admission_sha256"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _is_sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value) is not None


def _schema(value, keys, label):
    _need(type(value) is dict and set(value) == set(keys), "strict " + label + " schema required")


def admit_panel(training, admission, *, expected_admission_sha256):
    """Validate a predeclared <=16-parent panel, without reading excluded data.

    Expected manifest digest must come from the caller's independent split/data
    admission, not from this function. It binds source/split/family-lineage hashes,
    exact task bytes, a fixed held-demo index, and explicit exclusion sets.
    """
    _schema(admission, ("format", "source_sha256", "split_sha256", "family_lineage_sha256",
                        "parents", "excluded"), "training admission")
    _need(admission["format"] == ADMISSION_FORMAT, "training admission format differs")
    for key in ("source_sha256", "split_sha256", "family_lineage_sha256"):
        _need(_is_sha(admission[key]), "pinned source/split/family lineage SHA required")
    _need(_is_sha(expected_admission_sha256), "independently pinned training admission SHA required")
    parents = admission["parents"]
    _need(type(parents) is list and 1 <= len(parents) <= 16, "bounded prespecified parent panel required")
    _schema(admission["excluded"], ("parent_ids", "variant_groups", "family_ids"), "exclusion")
    excluded = {}
    for key, values in admission["excluded"].items():
        valid = _is_sha if key == "variant_groups" else _id
        _need(type(values) is list and len(values) <= 100000 and all(valid(v) for v in values)
              and len(set(values)) == len(values), "bounded distinct exclusions required")
        excluded[key] = set(values)
    _need(type(training) is dict and 1 <= len(training) <= 16, "selected training tasks only required")
    ids, variants, result = set(), set(), {}
    for entry in parents:
        _schema(entry, ("parent_id", "task_sha256", "variant_group", "family_id", "held_index"), "parent")
        parent, family = entry["parent_id"], entry["family_id"]
        _need(_id(parent) and _id(family) and parent not in ids and parent in training,
              "unique admitted parent and source family required")
        task = training[parent]
        _schema(task, ("train",), "train-only task")
        pairs = task["train"]
        _need(type(pairs) is list and 2 <= len(pairs) <= 32, "two to32 training demonstrations required")
        for pair in pairs:
            _schema(pair, ("input", "output"), "demonstration")
            _need(all(valid_grid(grid) for grid in pair.values()), "valid training grids required")
        _need(_is_sha(entry["task_sha256"]) and _sha(task) == entry["task_sha256"], "training task SHA differs")
        variant = known_variant_group({"train": pairs, "test": []})
        _need(entry["variant_group"] == variant and variant not in variants,
              "recomputed distinct training variant groups required")
        _need(parent not in excluded["parent_ids"] and variant not in excluded["variant_groups"]
              and family not in excluded["family_ids"], "excluded task/variant/family leaked into training")
        _need(type(entry["held_index"]) is int and 0 <= entry["held_index"] < len(pairs), "fixed held-demo index required")
        ids.add(parent); variants.add(variant)
        result[parent] = copy.deepcopy(entry)
    _need(set(training) == ids, "training mapping must contain exactly the prespecified panel")
    _need(_sha(admission) == expected_admission_sha256, "independently pinned training admission SHA differs")
    return result


def _config(config):
    config = copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    _schema(config, DEFAULT_CONFIG, "screen config")
    for key, low, high in (("seed", 0, 2**63 - 1), ("max_groups", 1, 64),
                            ("target_mixed_groups", 1, 8), ("microbatch", 1, 8),
                            ("context_tokens", 3, 8192), ("generation_tokens", 1, 931)):
        _need(type(config[key]) is int and low <= config[key] <= high, "bounded " + key + " required")
    _need(config["generation_tokens"] < config["context_tokens"], "generation reservation exceeds context")
    lr = config["learning_rate"]
    _need(type(lr) in (int, float) and math.isfinite(lr) and 0 < lr <= 1e-3, "bounded finite learning rate required")
    return config


def _model_identity(engine):
    # Live execution state is not synonymous with cached PEFT admission metadata.
    live = {}
    for name, module in engine.model.named_modules():
        if hasattr(module, "active_adapters") or hasattr(module, "gradient_checkpointing"):
            row = {}
            for key in ("active_adapters", "disable_adapters", "merged_adapters", "scaling",
                        "r", "lora_alpha", "use_dora", "gradient_checkpointing"):
                if hasattr(module, key):
                    value = getattr(module, key)
                    if not callable(value):
                        row[key] = copy.deepcopy(value)
            function = getattr(module, "_gradient_checkpointing_func", None)
            if function is not None:
                row["checkpoint_kwargs"] = copy.deepcopy(getattr(function, "keywords", {}))
            live[name] = row
    configs = {}
    for name, cfg in engine.model.peft_config.items():
        configs[name] = {key: sorted(value) if isinstance(value, set) else copy.deepcopy(value)
                        for key, value in cfg.to_dict().items()}
    return {"live_modules": live, "live_peft_configs": configs,"base_identity": engine.base_identity, "model_contract": engine.contract,
            "model_config": engine.model.config.to_dict(), "tokenizer": engine.tokenizer_admission,
            "trainables": engine.trainable_inventory}


def full_policy_sha256(engine, meter=None):
    """Hash ALL parameters and buffers, streaming <=1 MiB chunks to the CPU.

    Includes dtype/shape/trainability and admitted policy configuration. No
    adapter-only alias, sampled tensor hash, or base-identity assertion suffices.
    Hash work is separately metered; it is not model FLOPs or an optimizer step.
    """
    started = time.monotonic()
    if meter is not None:
        meter["calls"] += 1
    try:
        h = hashlib.sha256(canonical(_model_identity(engine)))
        for kind, tensors in (("parameter", engine.model.named_parameters()), ("buffer", engine.model.named_buffers())):
            for name, tensor in sorted(tensors):
                _need(tensor.layout == torch.strided and tensor.is_contiguous(), "dense contiguous policy tensors required")
                h.update(canonical([kind, name, list(tensor.shape), str(tensor.dtype), tensor.requires_grad]))
                flat = tensor.detach().reshape(-1)
                step = max(1, 1024**2 // tensor.element_size())
                for offset in range(0, flat.numel(), step):
                    chunk = flat[offset:offset + step].cpu().contiguous()
                    raw = chunk.view(torch.uint8).numpy().tobytes()
                    h.update(raw)
                    if meter is not None:
                        meter["tensor_bytes"] += len(raw)
        return h.hexdigest()
    finally:
        if meter is not None:
            meter["wall_seconds"] += time.monotonic() - started


def _live_admission(engine):
    # Unlike _checkpoint_admission, safe to call during mandatory restoration of
    # an already poisoned engine. This does NOT clear poison or authorize reuse.
    engine._structure_admission()
    for module in engine.model.modules():
        if hasattr(module, "lora_A") or hasattr(module, "modules_to_save"):
            disabled = getattr(module, "disable_adapters", False)
            if not callable(disabled):
                _need(not disabled, "disabled compact adapters forbidden")
            _need(not getattr(module, "merged_adapters", []), "merged compact adapters forbidden")


class _Meter:
    """Top-level model attempts include failed forwards; not measured FLOPs.

    Checkpointed layer recomputation is not a top-level model invocation. Engine
    counters additionally distinguish successful calls and generation slots.
    """
    def __init__(self, engine):
        self.engine, self.attempts, self.input_tokens = engine, 0, 0
        self.handle = engine.model.register_forward_pre_hook(self._before, with_kwargs=True)

    def _before(self, module, args, kwargs):
        self.attempts += 1
        tokens = kwargs.get("input_ids", args[0] if args else None)
        if isinstance(tokens, torch.Tensor):
            self.input_tokens += tokens.numel()

    def snapshot(self):
        values = {key: getattr(self.engine, key) for key in COUNTERS}
        _need(all(type(v) is int and v >= 0 for v in values.values()), "nonnegative engine counters required")
        return {**values, "model_forward_attempts": self.attempts, "model_input_tokens": self.input_tokens}

    def close(self):
        self.handle.remove()


def _delta(after, before):
    result = {key: after[key] - before[key] for key in before}
    _need(all(value >= 0 for value in result.values()), "physical counters regressed")
    return result


class _Chooser:
    """Alternating uniform-parent exploration and family/parent mixed priority."""
    def __init__(self, panel, seed):
        self.panel, self.rng, self.n = panel, random.Random(seed), 0
        empty = dict(complete=0, trajectories=0, positive=0, all_wrong=0, all_correct=0, mixed=0)
        self.parents = {key: Counter(empty) for key in panel}
        self.families = {row["family_id"]: Counter(empty) for row in panel.values()}

    @staticmethod
    def _weight(stats):
        # Beta smoothing leaves all-correct and all-wrong parents reachable.
        p = (stats["positive"] + 1) / (stats["trajectories"] + 2)
        return 0.05 + 4 * p * (1 - p) + 1 / math.sqrt(stats["complete"] + 1)

    def choose(self):
        self.n += 1
        ids = sorted(self.panel)
        if self.n % 2:
            return self.rng.choice(ids), "uniform-parent"
        weights = [self._weight(self.parents[key]) * self._weight(self.families[self.panel[key]["family_id"]]) for key in ids]
        return self.rng.choices(ids, weights=weights, k=1)[0], "smoothed-family-parent-mixed"

    def observe(self, parent, rows):
        positives = sum(row["reward"] for row in rows)
        category = "all_wrong" if positives == 0 else "all_correct" if positives == GROUP_SIZE else "mixed"
        for stats in (self.parents[parent], self.families[self.panel[parent]["family_id"]]):
            stats.update({"complete": 1, "trajectories": GROUP_SIZE, "positive": positives, category: 1})
        return category


def _example(task, entry, cfg):
    pairs, held = task["train"], entry["held_index"]
    target = copy.deepcopy(pairs[held]["output"])
    example = encode_example([pair for i, pair in enumerate(pairs) if i != held], pairs[held]["input"],
                             context=cfg["context_tokens"], generation=cfg["generation_tokens"])
    _need(len(example["prompt_ids"]) + len(grid_tokens(target)) + 1 <= cfg["context_tokens"],
          "complete target exceeds context; do not truncate")
    return example, target


def _validate_row(row, group, entry, lineage, engine, cfg):
    _schema(row, ROW_KEYS, "captured trajectory")
    ids, n, completion = row["input_ids"], row["prompt_length"], row["completion_ids"]
    _need(type(ids) is list and 2 <= len(ids) <= cfg["context_tokens"]
          and all(type(t) is int and 0 <= t < 16 for t in ids), "bounded original compact token IDs required")
    _need(type(n) is int and n == len(group["prompt_ids"]) and ids[:n] == group["prompt_ids"]
          and type(completion) is list and ids[n:] == completion and 1 <= len(completion) <= cfg["generation_tokens"]
          and all(type(t) is int and 0 <= t < 16 for t in completion)
          and type(row["completion_tokens"]) is int and row["completion_tokens"] == len(completion),
          "original prompt/completion boundary differs")
    _need(15 not in completion[:-1] and row["stop"] in {"length", "completed"}
          and (row["stop"] == "completed") == (completion[-1] == 15)
          and (row["stop"] != "length" or len(completion) == cfg["generation_tokens"]), "EOS/length accounting differs")
    logps = row["behavior_log_probs"]
    _need(type(logps) is list and len(logps) == len(ids)
          and all(type(v) in (int, float) and math.isfinite(v) and v <= 1e-6 for v in logps)
          and all(v == 0 for v in logps[:n]), "finite aligned raw behavior log probabilities required")
    _need(row["text"] == engine.tokenizer.decode(completion, skip_special_tokens=False,
                                                clean_up_tokenization_spaces=False), "raw compact decoding differs")
    for key in ("parent_id", "family_id", "variant_group", "task_sha256"):
        _need(row[key] == entry[key], "captured training lineage differs")
    for key, value in lineage.items():
        _need(row[key] == value, "captured anchor/model/admission identity differs")
    _need(row["group_id"] == group["group_id"] and valid_grid(row["training_target"])
          and row["training_target"] == group["training_target"], "group target lineage differs")
    reward = float(parse_completion(completion) == group["training_target"])
    _need(type(row["reward"]) in (int, float) and row["reward"] == reward, "exact-only reward differs")
    if reward:
        _need(completion == grid_tokens(group["training_target"]) + [15], "positive must equal unique compact target")


def validate_capture(capture, training, admission, *, expected_admission_sha256, engine, hash_cost=None):
    """Rebuild every eligible prompt/target from pinned training, reject tampering.

    This structural validator does not certify stochastic sampling by itself.
    run_matched_controls collects directly and also verifies logps on the full
    frozen policy. It never accepts an external historical pool for updates.
    """
    panel = admit_panel(training, admission, expected_admission_sha256=expected_admission_sha256)
    _schema(capture, ("config", "lineage", "groups", "status", "seal_sha256"), "capture")
    cfg = _config(capture["config"])
    _schema(capture["lineage"], ("policy_sha256", "anchor_sha256", "model_identity_sha256", "admission_sha256"), "capture lineage")
    _need(all(_is_sha(v) for v in capture["lineage"].values())
          and capture["lineage"]["admission_sha256"] == expected_admission_sha256
          and capture["lineage"]["model_identity_sha256"] == _sha(_model_identity(engine)), "capture lineage SHA differs")
    _need(capture["lineage"]["policy_sha256"] == full_policy_sha256(engine, hash_cost)
          and capture["lineage"]["anchor_sha256"] == state_digest(adapter_state(engine.model)),
          "captured full anchor policy differs from the supplied engine")
    _need(capture["status"] in {"target_reached", "budget_exhausted", "deadline", "failed"}, "terminal collection status required")
    groups = capture["groups"]
    _need(type(groups) is list and len(groups) <= cfg["max_groups"], "bounded physical groups required")
    samples, chooser, mixed_count = set(), _Chooser(panel, cfg["seed"]), 0
    _need(bool(groups), "at least one charged group attempt required")
    for i, group in enumerate(groups):
        _schema(group, ("group_id", "parent_id", "allocation", "prompt_ids", "training_target", "demos_dropped",
                        "rows", "batches", "status", "category"), "captured group")
        _need(group["group_id"] == f"g{i}" and group["parent_id"] in panel, "unique ordered admitted groups required")
        expected_parent, expected_allocation = chooser.choose()
        _need(group["allocation"] == expected_allocation and group["parent_id"] == expected_parent,
              "seeded adaptive training allocation differs")
        _need(mixed_count < cfg["target_mixed_groups"], "collection continued after mixed target")
        entry = panel[group["parent_id"]]
        example, target = _example(training[group["parent_id"]], entry, cfg)
        _need(type(group["prompt_ids"]) is list and all(type(t) is int for t in group["prompt_ids"])
              and group["prompt_ids"] == example["prompt_ids"] and valid_grid(group["training_target"])
              and group["training_target"] == target and type(group["demos_dropped"]) is int
              and group["demos_dropped"] == example["demos_dropped"], "capture differs from admitted training prompt/target")
        rows, batches = group["rows"], group["batches"]
        _need(type(rows) is list and len(rows) <= GROUP_SIZE and type(batches) is list
              and len(batches) <= GROUP_SIZE, "bounded captured trajectories/batches required")
        requested = returned = accepted = 0
        for batch_index, batch in enumerate(batches):
            _schema(batch, ("requested", "returned", "accepted", "status"), "generation attempt")
            _need(all(type(batch[k]) is int for k in ("requested", "returned", "accepted"))
                  and 1 <= batch["requested"] <= cfg["microbatch"]
                  and 0 <= batch["accepted"] <= batch["returned"] <= batch["requested"]
                  and batch["status"] in {"complete", "deadline", "failed"}, "physical generation attempt differs")
            _need(batch["requested"] == min(cfg["microbatch"], GROUP_SIZE - requested), "generation dispatch slots differ")
            _need(batch["status"] != "complete" or batch["requested"] == batch["returned"] == batch["accepted"], "incomplete successful batch")
            _need(batch["status"] == "complete" or batch_index == len(batches) - 1, "nonterminal failed generation batch")
            requested += batch["requested"]; returned += batch["returned"]; accepted += batch["accepted"]
        _need(requested <= GROUP_SIZE and accepted == len(rows), "physical attempt/retained trajectory conservation differs")
        for slot, row in enumerate(rows):
            _validate_row(row, group, entry, capture["lineage"], engine, cfg)
            _need(row["sample_id"] == f"g{i}:s{slot}" and row["sample_id"] not in samples, "duplicate/misordered physical sample")
            samples.add(row["sample_id"])
        _need(group["status"] in {"complete", "deadline", "failed"}, "terminal group status required")
        if group["status"] == "complete":
            _need(len(rows) == GROUP_SIZE and requested == returned == GROUP_SIZE
                  and all(b["status"] == "complete" for b in batches), "complete eight-trajectory group required")
            positives = sum(r["reward"] for r in rows)
            category = "all_wrong" if positives == 0 else "all_correct" if positives == GROUP_SIZE else "mixed"
            _need(group["category"] == category, "complete exact group category differs")
            chooser.observe(group["parent_id"], rows)
            mixed_count += int(category == "mixed")
        else:
            _need(group["category"] is None and i == len(groups) - 1
                  and capture["status"] == group["status"], "only terminal partial groups may lack a reward category")
    complete = all(g["status"] == "complete" for g in groups)
    if capture["status"] == "target_reached":
        _need(complete and mixed_count == cfg["target_mixed_groups"], "mixed target was not actually reached")
    elif capture["status"] == "budget_exhausted":
        _need(complete and len(groups) == cfg["max_groups"] and mixed_count < cfg["target_mixed_groups"], "group budget was not actually exhausted")
    else:
        _need(not complete, "failed/deadline collection requires a terminal incomplete attempt")
    _need(capture["seal_sha256"] == _sha({k: v for k, v in capture.items() if k != "seal_sha256"}), "captured pool seal differs")
    return groups


def _weights(groups, arm):
    complete = [g for g in groups if g["status"] == "complete"]
    counts = [1 if arm == "known_target_ce" else sum(r["reward"] for r in g["rows"]) for g in complete]
    total = sum(counts)
    return [(g, count / total) for g, count in zip(complete, counts) if count] if total else []


def _ce_update(engine, weighted, optimizer, deadline, *, positive=False):
    """One streamed target-only SFT gradient sum, equivalent duplicate reduction."""
    optimizer.zero_grad(set_to_none=True)
    if not weighted:
        return {"updated": False, "reason": "no_eligible_prompts", "loss": None, "backward_trajectories": 0}
    total = 0.0
    try:
        for group, weight in weighted:
            check_deadline(deadline)
            prompt = group["prompt_ids"]
            target = (next(row["completion_ids"] for row in group["rows"] if row["reward"] == 1)
                      if positive else grid_tokens(group["training_target"]) + [15])
            values = engine.completion_logps(prompt + target, len(prompt))
            loss = -values[len(prompt):].mean() * weight
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("nonfinite target-only CE")
            total += loss.item()
            loss.backward()
            del loss, values
        check_deadline(deadline)
        return {**engine.commit(optimizer), "loss": total, "backward_trajectories": len(weighted)}
    finally:
        optimizer.zero_grad(set_to_none=True)


def run_matched_controls(engine, training, admission, *, expected_admission_sha256,
                         deadline, config=None):
    """Collect once, verify, execute declared controls, return private evidence.

    deadline is the caller's finite original-session wall deadline, never reset.
    Deadline returns a partial receipt/state inventory; other errors propagate
    unchanged with .matched_controls_result attached. No failed step is retried.
    Mandatory anchor restoration/hash verification can exceed that deadline.
    """
    _need(isinstance(engine, CompactEngine), "actual admitted CompactEngine required")
    engine._checkpoint_admission()
    _live_admission(engine)
    _need(type(deadline) in (int, float) and math.isfinite(deadline), "finite original-session deadline required")
    cfg = _config(config)
    panel = admit_panel(training, admission, expected_admission_sha256=expected_admission_sha256)
    # Defend against caller mutation while collection is in progress.
    training, admission = copy.deepcopy(training), copy.deepcopy(admission)
    examples = {key: _example(training[key], entry, cfg) for key, entry in panel.items()}
    started, mode = time.monotonic(), engine.model.training
    anchor = adapter_state(engine.model)
    hash_cost = {"calls": 0, "tensor_bytes": 0, "wall_seconds": 0.0}
    policy_sha = full_policy_sha256(engine, hash_cost)
    lineage = {"policy_sha256": policy_sha, "anchor_sha256": state_digest(anchor),
               "model_identity_sha256": _sha(_model_identity(engine)), "admission_sha256": expected_admission_sha256}
    meter = _Meter(engine); before = meter.snapshot()
    capture = {"config": cfg, "lineage": lineage, "groups": [], "status": "failed", "seal_sha256": ""}
    result = {"format": FORMAT, "status": "running", "capture": capture, "states": {"anchor": anchor},
              "arms": {arm: {"status": "not_run"} for arm in ARMS}, "cleanup_errors": [], "hash_cost": hash_cost, "original_session_deadline": deadline,
              "probability_measure": "full-16-vocabulary-temperature-one-no-filter",
              "equal_compute_claim": False, "efficacy_claim": False, "optimizer_rng_resumed": False,
              "state_contract": "exact-named-trainables-relative-to-verified-frozen-base",
              "partial_groups_used_for_loss": False, "collection": {}, "verification": {},
              "prompt_weighting": "target:uniform-complete-group; positive:observed-positive-count; DDIS:uniform-complete-mixed-group",
              "limitations": ["No full DAPO/RAFT reproduction or efficacy evaluation.",
                              "Pinned provenance is a caller trust boundary, not proof of semantic independence.",
                              "Inherited benchmark exposure is not removed.",
                              "Mixed groups may repeat one task; adaptive success rates are not unbiased corpus estimates.",
                              "Top-level forward/token counters are not FLOPs or checkpoint recomputation counts."]}
    chooser = _Chooser(panel, cfg["seed"])
    generator = torch.Generator(device=engine.device).manual_seed(cfg["seed"])
    optimizer, body_error = None, None

    def finish_phase(record, phase_before, phase_started, phase, primary):
        # A failed GPU synchronization must not erase charged work or a primary
        # exception. Record both; propagate sync failure only if it is primary.
        sync_error = None
        try:
            engine.sync()
        except BaseException as error:
            sync_error = error
            result["cleanup_errors"].append({"phase": phase, "action": "synchronize",
                                             "error": type(error).__name__,
                                             "primary_error": type(primary).__name__ if primary else None})
        finally:
            record.update(physical=_delta(meter.snapshot(), phase_before),
                          wall_seconds=time.monotonic() - phase_started)
            if phase in ARMS:
                record["backward_cost"] = {"completed_trajectories": record.get("backward_trajectories"),
                    "partial_work_unknown": "backward_trajectories" not in record,
                    "note": "Interrupted backward work is not a completed trajectory or zero compute."}
        if sync_error is not None:
            record.update(status="failed", synchronization_error=type(sync_error).__name__)
            if primary is None or isinstance(primary, PhaseDeadline):
                raise sync_error from primary

    def restore():
        # Never clear _fatal_update, rewind physical counters, or claim optimizer rollback.
        restore_state(engine.model, anchor)
        for p in engine.parameters:
            p.grad = None
        if full_policy_sha256(engine, hash_cost) != policy_sha:
            engine._fatal_update = True
            raise FatalUpdateError("full policy differs after anchor restore; frozen state/config may be damaged; abort worker")
        _live_admission(engine)

    try:
        phase_before, phase_started = meter.snapshot(), time.monotonic()
        collection_error = None
        try:
            for i in range(cfg["max_groups"]):
                parent, allocation = chooser.choose()
                example, target = examples[parent]
                group = {"group_id": f"g{i}", "parent_id": parent, "allocation": allocation,
                         "prompt_ids": list(example["prompt_ids"]), "training_target": target,
                         "demos_dropped": example["demos_dropped"], "rows": [], "batches": [],
                         "status": "failed", "category": None}
                capture["groups"].append(group)  # Even a deadline before the first forward counts.
                try:
                    check_deadline(deadline)
                    for offset in range(0, GROUP_SIZE, cfg["microbatch"]):
                        count = min(cfg["microbatch"], GROUP_SIZE - offset)
                        batch = {"requested": count, "returned": 0, "accepted": 0, "status": "failed"}
                        group["batches"].append(batch)
                        try:
                            generated = engine.generate(group["prompt_ids"], count=count, sample=True,
                                max_new_tokens=cfg["generation_tokens"], deadline=deadline, generator=generator)
                            _need(type(generated) is list and len(generated) <= count, "bounded generator result required")
                            batch["returned"] = len(generated)
                            for raw in generated:
                                _schema(raw, ("input_ids", "prompt_length", "completion_ids", "behavior_log_probs",
                                              "text", "completion_tokens", "stop"), "engine rollout")
                                row = {**copy.deepcopy(raw), **lineage, **{key: panel[parent][key]
                                       for key in ("parent_id", "family_id", "variant_group", "task_sha256")},
                                       "training_target": copy.deepcopy(target), "group_id": group["group_id"],
                                       "sample_id": f"g{i}:s{len(group['rows'])}",
                                       "reward": float(parse_completion(raw["completion_ids"]) == target)}
                                _validate_row(row, group, panel[parent], lineage, engine, cfg)
                                group["rows"].append(row); batch["accepted"] += 1
                            _need(len(generated) == count, "partial generator return; no synthetic replacement")
                            batch["status"] = "complete"
                        except PhaseDeadline:
                            batch["status"] = "deadline"
                            raise
                    check_deadline(deadline)
                    group["category"] = chooser.observe(parent, group["rows"])
                    group["status"] = "complete"
                except PhaseDeadline:
                    group["status"] = "deadline"
                    raise
                if sum(g["category"] == "mixed" for g in capture["groups"]) >= cfg["target_mixed_groups"]:
                    capture["status"] = "target_reached"
                    break
            else:
                capture["status"] = "budget_exhausted"
        except PhaseDeadline as error:
            capture["status"] = "deadline"
            collection_error = error
            raise
        except BaseException as error:
            collection_error = error
            raise
        finally:
            capture["seal_sha256"] = _sha({k: v for k, v in capture.items() if k != "seal_sha256"})
            result["collection"] = {"groups_attempted": len(capture["groups"]),
                "categories": dict(Counter(g["category"] or "partial" for g in capture["groups"])),
                "trajectories_requested": sum(b["requested"] for g in capture["groups"] for b in g["batches"]),
                "trajectories_returned": sum(b["returned"] for g in capture["groups"] for b in g["batches"]),
                "trajectories_retained": sum(len(g["rows"]) for g in capture["groups"]),
                "parent_stats": {key: dict(value) for key, value in chooser.parents.items()},
                "family_stats": {key: dict(value) for key, value in chooser.families.items()},
                "mixed_target_met": sum(g["category"] == "mixed" for g in capture["groups"]) >= cfg["target_mixed_groups"]}
            finish_phase(result["collection"], phase_before, phase_started, "collection", collection_error)
        _need(full_policy_sha256(engine, hash_cost) == policy_sha, "full policy changed during frozen collection")
        _need(meter.snapshot()["optimizer_attempts"] == before["optimizer_attempts"]
              and meter.snapshot()["optimizer_steps"] == before["optimizer_steps"], "policy updates during collection forbidden")
        validate_capture(capture, training, admission, expected_admission_sha256=expected_admission_sha256, engine=engine, hash_cost=hash_cost)
        verify_before, verify_started, verified = meter.snapshot(), time.monotonic(), 0
        gap, observed, failed_row = None, 0, None
        verification_error = None
        try:
            with torch.no_grad():
                for group in capture["groups"]:
                    for row in group["rows"]:
                        check_deadline(deadline)
                        current = engine.completion_logps(row["input_ids"], row["prompt_length"])
                        old = torch.tensor(row["behavior_log_probs"], device=engine.device)
                        differences = current - old
                        difference = differences.abs().max().item()
                        # Fixed engineering tolerance, not a measured GPU error bar.
                        tolerance = 0.05 if engine.base_dtype == torch.bfloat16 else 1e-5
                        # Persist the returned failing measurement BEFORE admission.
                        # Zero previously meant no accepted rows, not measured parity.
                        observed += 1
                        gap = difference if gap is None else max(gap, difference)
                        if difference > tolerance:
                            index = int(differences.abs().argmax().item())
                            failed_row = {"sample_id": row["sample_id"], "group_id": row["group_id"],
                                "prompt_length": row["prompt_length"], "completion_tokens": row["completion_tokens"],
                                "tolerance": tolerance, "max_abs_logp_gap": difference,
                                "max_gap_token_index": index, "max_gap_token_id": row["input_ids"][index],
                                "behavior_logp_at_max": float(old[index].item()),
                                "replay_logp_at_max": float(current[index].item()),
                                "mean_abs_completion_logp_gap": float(differences[row["prompt_length"]:].abs().mean().item()),
                                "replay_log_probs": current.detach().cpu().tolist(),
                                "generation_path": "eval-cached-microbatch",
                                "replay_path": "train-full-sequence-singleton",
                                "numerical_cause_established": False}
                        _need(difference <= tolerance, "captured behavior logps differ from full frozen policy")
                        verified += 1
            check_deadline(deadline)
        except BaseException as error:
            verification_error = error
            raise
        finally:
            result["verification"] = {"rows": verified, "observed_rows": observed,
                                      "max_logp_gap": gap, "failed_row": failed_row}
            finish_phase(result["verification"], verify_before, verify_started, "verification", verification_error)
        for arm in ARMS:
            arm_before, arm_started = meter.snapshot(), time.monotonic()
            record = {"status": "pending", "fresh_optimizer": True, "before_policy_sha256": policy_sha,
                      "requested_optimizer_steps": int(arm != "anchor"), "prompt_weights": [],
                      "pool_sha256": capture["seal_sha256"]}
            result["arms"][arm] = record
            arm_error = None
            try:
                restore()
                check_deadline(deadline)
                optimizer = make_optimizer(engine.model, cfg["learning_rate"])
                _need(not optimizer.state, "fresh optimizer must have empty state")
                record["optimizer_initial_state_entries"] = len(optimizer.state)
                record["status"] = "running"
                if arm == "anchor":
                    update = {"updated": False, "reason": "unchanged_anchor", "backward_trajectories": 0}
                elif arm in {"known_target_ce", "exact_positive_ce"}:
                    weighted = _weights(capture["groups"], arm)
                    record["prompt_weights"] = [{"group_id": g["group_id"], "parent_id": g["parent_id"], "weight": w}
                                                for g, w in weighted]
                    update = _ce_update(engine, weighted, optimizer, deadline, positive=arm == "exact_positive_ce")
                else:
                    mixed = [g for g in capture["groups"] if g["status"] == "complete" and g["category"] == "mixed"]
                    record["prompt_weights"] = [{"group_id": g["group_id"], "parent_id": g["parent_id"], "weight": 1 / len(mixed)} for g in mixed]
                    if mixed:
                        update = engine.af3_update([r for g in mixed for r in g["rows"]], optimizer,
                            expected_groups=[g["group_id"] for g in mixed], group_size=GROUP_SIZE, deadline=deadline)
                        update["backward_trajectories"] = update["replayed"]
                    else:
                        update = {"updated": False, "reason": "no_complete_mixed_groups", "backward_trajectories": 0}
                state = adapter_state(engine.model)
                changed = state_digest(state) != lineage["anchor_sha256"]
                _need(bool(update["updated"]) == changed, "optimizer parameter delta claim differs")
                result["states"][arm] = state
                record.update(update, status="complete", after_sha256=state_digest(state),
                              parameter_delta_verified=changed, optimizer_final_state_entries=len(optimizer.state),
                              returned_after_deadline=time.time() >= deadline)
                check_deadline(deadline)
            except PhaseDeadline as error:
                arm_error = error
                record["status"] = "deadline"
                raise
            except BaseException as error:
                arm_error = error
                record.update(status="failed", error=type(error).__name__)
                raise
            finally:
                if optimizer is not None:
                    optimizer.zero_grad(set_to_none=True)
                    optimizer = None
                finish_phase(record, arm_before, arm_started, arm, arm_error)
        result["status"] = "complete"
    except PhaseDeadline as error:
        body_error = error
        result["status"] = "deadline"
    except BaseException as error:
        body_error = error
        result.update(status="failed", error=type(error).__name__)
        error.matched_controls_result = result
        raise
    finally:
        restoration_error = None
        try:
            restore()
            result["anchor_restored"] = True
        except BaseException as error:
            restoration_error = error
            engine._fatal_update = True
            result.update(anchor_restored=False, status="failed", restoration_error=type(error).__name__)
            error.matched_controls_result = result
            raise
        finally:
            primary, cleanup_error = restoration_error or body_error, None
            try:
                engine.model.train(mode)
            except BaseException as error:
                cleanup_error = error
                engine._fatal_update = True
                result["cleanup_errors"].append({"phase": "final", "action": "restore_mode", "error": type(error).__name__})
            try:
                result["engine_poisoned"] = engine._fatal_update
                result["physical"] = _delta(meter.snapshot(), before)
                result["wall_seconds"] = time.monotonic() - started
            except BaseException as error:
                cleanup_error = cleanup_error or error
                result["cleanup_errors"].append({"phase": "final", "action": "snapshot_work", "error": type(error).__name__})
            finally:
                meter.close()
            if cleanup_error is not None:
                result["status"] = "failed"
                if primary is None or isinstance(primary, PhaseDeadline):
                    cleanup_error.matched_controls_result = result
                    raise cleanup_error from primary
    return result
