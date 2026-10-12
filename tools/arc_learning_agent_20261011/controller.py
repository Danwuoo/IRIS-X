"""Evidence-driven learning agent over one genuinely trained native model.

Three logical policies reuse physical work: pre-adaptation global grids, demo-only
adapted grids, and full direct/program fusion. Only demo verifier receipts can
admit source execution; valid direct grids are never filtered by program fit.
Model generation is an injected NativeModel interface, not trusted agent control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import copy
import hashlib
import json
import math
from pathlib import Path
import time

from . import grid_codec, program_tools
from .budget import BudgetExceeded
from tools.arc_consolidated_20261010 import verifier as legacy


class EvidenceKind(str, Enum):
    TASK = "task"
    DECISION = "decision"
    GENERATION = "generation"
    GRID = "grid_hypothesis"
    PROGRAM = "program_hypothesis"
    VERIFICATION = "demo_verification"
    QUERY = "query_execution"
    SCORE = "likelihood"
    ADAPTATION = "adaptation"
    STATE = "adapter_state"
    ERROR = "error"
    SELECTION = "selection"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass
class EvidenceMemory:
    """Append-only, bounded, typed task-local evidence with backward parent links."""
    task_id: str
    max_records: int = 8192
    records: list = field(default_factory=list)

    def add(self, kind, payload, parents=()):
        if not isinstance(kind, EvidenceKind):
            raise ValueError("typed evidence kind required")
        if len(self.records) >= self.max_records:
            raise ValueError("task evidence memory capacity")
        known = {row["id"] for row in self.records}
        if any(parent not in known for parent in parents):
            raise ValueError("evidence parent is not from this task")
        value = json.loads(_json(payload))
        ident = "e%05d" % len(self.records)
        self.records.append({"id": ident, "task_id": self.task_id, "kind": kind.value,
                             "parents": list(parents), "payload": value})
        return ident


@dataclass
class GridHypothesis:
    grid: list
    sha256: str
    evidence_ids: list = field(default_factory=list)
    origins: set = field(default_factory=set)
    view_support: dict = field(default_factory=dict)
    program_ids: set = field(default_factory=set)

    def support(self, phase=None):
        phases = [phase] if phase else self.view_support
        return len(set(view for key in phases for view in self.view_support.get(key, set())))


@dataclass
class ProgramHypothesis:
    source: str
    sha256: str
    evidence_id: str
    proof: dict
    parent_id: str | None = None
    repairs: int = 0


@dataclass(frozen=True)
class View:
    """D4 spatial symmetry plus a bijective color relabeling; exactly invertible."""
    index: int

    def forward(self, grid):
        value = legacy._grid(grid)
        if self.index >= 4:
            value = [row[::-1] for row in value]
        for _ in range(self.index % 4):
            value = [list(row) for row in zip(*value[::-1])]
        # Keep view zero literal. Nonidentity views also test color equivariance.
        shift = self.index
        return [[(cell + shift) % 10 for cell in row] for row in value]

    def inverse(self, grid):
        value = [[(cell - self.index) % 10 for cell in row] for row in legacy._grid(grid)]
        for _ in range((-self.index) % 4):
            value = [list(row) for row in zip(*value[::-1])]
        if self.index >= 4:
            value = [row[::-1] for row in value]
        return legacy._grid(value)

    def demos(self, demos):
        return [{"input": self.forward(row["input"]), "output": self.forward(row["output"])} for row in demos]


VIEWS = tuple(View(index) for index in range(8))
DEFAULTS = {"global_views": 2, "adapted_views": 2, "initial_programs": 1, "repair_attempts": 1,
            "score_candidates": 8, "scoring_views": 8, "max_candidates": 32, "ttt_steps": 16,
            "max_new_tokens": 2048, "prompt_token_reservation": 6144,
            "max_generation_calls": 1600, "max_scoring_forwards": 12000,
            "max_input_tokens": 50000000, "max_output_tokens": 3200000,
            "max_cpu_checks": 12000, "max_program_gas": 2400000000,
            "program_policy": "auto", "program_branch": "trained", "seed": 0}
HARD_MAX = {"global_views": 2, "adapted_views": 4, "initial_programs": 2, "repair_attempts": 2,
            "score_candidates": 8, "scoring_views": 8, "max_candidates": 32, "max_new_tokens": 2048, "ttt_steps": 8192,
            "max_generation_calls": 1600, "max_scoring_forwards": 12000,
            "max_input_tokens": 50000000, "max_output_tokens": 3200000,
            "max_cpu_checks": 12000, "max_program_gas": 2400000000}


def _config(config):
    if config is None:
        config = {}
    if type(config) is not dict:
        raise ValueError("controller config must be a dictionary")
    values = {**DEFAULTS, **config}
    for key, default in DEFAULTS.items():
        if type(default) is int:
            if type(values[key]) is not int or values[key] < 0:
                raise ValueError("nonnegative integer configuration required: " + key)
            if key in HARD_MAX and values[key] > HARD_MAX[key]:
                raise ValueError("controller hard cap exceeded: " + key)
    if values["scoring_views"] != 8:
        raise ValueError("same-view likelihood uses exactly eight views; zero budget disables dispatch")
    if not 1 <= values["max_candidates"] <= 32 or not 1 <= values["max_new_tokens"] <= 2048:
        raise ValueError("positive candidate/output caps required")
    if values["prompt_token_reservation"] < 6144:
        raise ValueError("unknown prompt usage must reserve at least native prompt cap")
    if values["program_policy"] not in {"auto", "always", "never"}:
        raise ValueError("unknown program policy")
    if values["program_branch"] not in {"trained", "base"}:
        raise ValueError("unknown program adapter branch")
    return values


def _task(task):
    if type(task) is not dict or set(task) != {"train", "test"}:
        raise ValueError("task must contain exactly train and test")
    demos = legacy.validate_task({"task_id": "controller-admission", "demos": task["train"]})["demos"]
    if type(task["test"]) is not list or not 1 <= len(task["test"]) <= 10:
        raise ValueError("expected 1..10 query inputs")
    queries = []
    for pair in task["test"]:
        if type(pair) is not dict or set(pair) != {"input"}:
            raise ValueError("query answers/metadata forbidden")
        queries.append({"input": legacy._grid(pair["input"])})
    return {"train": demos, "test": queries}


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _counter(receipt, key, unknown):
    value = receipt.get(key)
    return (value, False) if type(value) is int and value >= 0 else (unknown, True)


class _Controller:
    def __init__(self, task_id, task, model, trainer, config, deadline, output_dir, work_ledger=None):
        if type(task_id) is not str or not task_id or len(task_id.encode()) > 128:
            raise ValueError("bounded nonempty task_id required")
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError("finite absolute monotonic deadline required")
        self.task_id, self.task = task_id, _task(task)
        self.model, self.trainer, self.config, self.deadline = model, trainer, _config(config), deadline
        self.root = Path(output_dir)
        if self.root.is_symlink() or (self.root.exists() and any(self.root.iterdir())):
            raise ValueError("task output identity consumed or symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        self.memory = EvidenceMemory(task_id)
        self.pools = [{} for _ in self.task["test"]]
        self.programs = []
        self.scores = {"global": {}, "task": {}}
        self.events = []
        self.work_ledger = work_ledger
        self.counts = {"generation_calls": 0, "scoring_forwards": 0, "input_tokens": 0, "output_tokens": 0,
                       "optimizer_steps": 0, "supervised_tokens": 0, "cpu_checks": 0, "program_gas": 0,
                       "unknown_usage_events": 0, "model_forward_calls": 0, "forward_input_tokens": 0,
                       "generation_attempts": 0, "scoring_attempts": 0, "cpu_attempts": 0}
        self.adapter = None
        self.stop_reasons = set()
        self.task_eid = self.memory.add(EvidenceKind.TASK, {"task_sha256": _hash(self.task),
            "query_count": len(self.task["test"]), "demo_count": len(self.task["train"]),
            "selection": "verifier tier, complete common-eight-view mean NLL, unique view support, stable grid hash; direct floor",
            "scoring_precap": "up to eight grids by descending distinct view support then stable grid hash",
            "query_answers_available": False})

    def decision(self, action, reason, **facts):
        return self.memory.add(EvidenceKind.DECISION, {"action": action, "reason": reason, **facts}, [self.task_eid])

    def available(self, kind, count=1):
        if time.monotonic() >= self.deadline:
            self.stop_reasons.add("deadline")
            return False
        c, v = self.counts, self.config
        if kind in {"generation", "score"}:
            key = "generation_calls" if kind == "generation" else "scoring_forwards"
            if c[key] + count > v["max_" + key]:
                self.stop_reasons.add(key + "_cap")
                return False
            input_reserve = v["prompt_token_reservation"] + (v["max_new_tokens"] if kind == "score" else 0)
            if c["input_tokens"] + input_reserve * count > v["max_input_tokens"]:
                self.stop_reasons.add("input_token_cap")
                return False
            if kind == "generation" and c["output_tokens"] + v["max_new_tokens"] * count > v["max_output_tokens"]:
                self.stop_reasons.add("output_token_cap")
                return False
        elif kind == "cpu":
            if c["cpu_checks"] + count > v["max_cpu_checks"] or c["program_gas"] + legacy.MAX_STEPS * count > v["max_program_gas"]:
                self.stop_reasons.add("cpu_cap")
                return False
        return True

    def event(self, kind, receipt, *, phase, evidence_id, **details):
        event = {"index": len(self.events), "kind": kind, "phase": phase, "adapter_sha256": self.adapter,
                 "evidence_id": evidence_id, **details}
        if kind in {"generation", "score"}:
            key = "generation_calls" if kind == "generation" else "scoring_forwards"
            self.counts["generation_attempts" if kind == "generation" else "scoring_attempts"] += 1
            dispatched = receipt.get("dispatched") is not False
            self.counts[key] += int(dispatched)
            event["dispatched"] = receipt.get("dispatched")
            reserve = self.config["prompt_token_reservation"] + (self.config["max_new_tokens"] if kind == "score" else 0)
            inp, unknown = _counter(receipt, "input_tokens", reserve)
            out, unknown_out = _counter(receipt, "output_tokens", self.config["max_new_tokens"]) if kind == "generation" else (0, False)
            if not dispatched:
                inp, out, unknown, unknown_out = 0, 0, False, False
            self.counts["input_tokens"] += inp
            self.counts["output_tokens"] += out
            event.update(input_tokens_charged=inp, output_tokens_charged=out, unknown_usage=unknown or unknown_out)
            for forward_key in ("forward_calls", "forward_input_tokens"):
                value = receipt.get(forward_key, 0)
                if type(value) is int and value >= 0:
                    self.counts["model_forward_calls" if forward_key == "forward_calls" else forward_key] += value
                    event[forward_key] = value
            self.counts["unknown_usage_events"] += int(unknown or unknown_out)
        elif kind == "adaptation":
            steps, unknown = _counter(receipt, "steps", self.config["ttt_steps"])
            inp, unknown_in = _counter(receipt, "input_tokens", self.config["max_input_tokens"] - self.counts["input_tokens"])
            sup, unknown_sup = _counter(receipt, "supervised_tokens", 0)
            self.counts["optimizer_steps"] += steps
            self.counts["input_tokens"] += inp
            self.counts["supervised_tokens"] += sup
            event.update(optimizer_steps=steps, input_tokens_charged=inp, supervised_tokens=sup,
                         unknown_usage=unknown or unknown_in or unknown_sup or receipt.get("usage_is_conservative_reservation", False))
            self.counts["unknown_usage_events"] += int(event["unknown_usage"])
        elif kind in {"demo_verify", "query_execute"}:
            self.counts["cpu_attempts"] += 1
            self.counts["cpu_checks"] += int(receipt.get("dispatched", False))
            gas = receipt.get("gas_charged", legacy.MAX_STEPS)
            if type(gas) is not int or not 0 <= gas <= legacy.MAX_STEPS:
                gas = legacy.MAX_STEPS
            self.counts["program_gas"] += gas
            event.update(gas_charged=gas, dispatched=receipt.get("dispatched", False),
                         owned_descendants_stopped=receipt.get("owned_descendants_stopped", False))
        self.events.append(event)
        with (self.root / "physical-events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(_json(event) + "\n")

    def fingerprint(self, phase, receipt=None):
        value = None
        method = getattr(self.trainer, "adapter_fingerprint", None)
        if callable(method):
            value = method()
        elif callable(getattr(self.trainer, "fingerprint", None)):
            value = self.trainer.fingerprint().get("sha256")
        if value is None and isinstance(receipt, dict):
            for key in ("adapter_after_sha256", "adapter_sha256", "global_sha256", "restored_sha256"):
                if isinstance(receipt.get(key), str):
                    value = receipt[key]
                    break
        if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("actual adapter fingerprint required at phase boundary")
        self.adapter = value
        self.memory.add(EvidenceKind.STATE, {"phase": phase, "adapter_sha256": value}, [self.task_eid])

    def generate(self, messages, kind, phase, query_index=None, view=None, parent=None):
        if not self.available("generation"):
            return None, None
        call_index = self.counts["generation_attempts"]
        seed = int(_hash([self.config["seed"], self.task_id, phase, query_index, view, call_index])[:8], 16)
        began = time.monotonic()
        try:
            receipt = self.model.generate(messages, kind=kind, seed=seed, max_new_tokens=self.config["max_new_tokens"], deadline=self.deadline)
            if type(receipt) is not dict:
                raise ValueError("generation receipt must be a dictionary")
            # Reject non-JSON/nonfinite model receipts instead of trusting prose.
            _json(receipt)
        except BudgetExceeded as exc:
            self.stop_reasons.add("session_budget")
            self.decision("stop_generation", str(exc)[:160])
            return None, None
        except Exception as exc:
            receipt = {"valid": False, "error": str(exc)[:512], "text": "", "elapsed_seconds": time.monotonic() - began}
        text = receipt.get("text", "")
        payload = {"kind": kind, "phase": phase, "query_index": query_index, "view": view,
                   "adapter_sha256": self.adapter, "receipt": receipt}
        eid = self.memory.add(EvidenceKind.GENERATION, payload, [parent or self.task_eid])
        self.event("generation", receipt, phase=phase, evidence_id=eid, query_index=query_index, view=view)
        adapter_bound = receipt.get("adapter_state_sha256", self.adapter) == self.adapter
        if not adapter_bound:
            self.memory.add(EvidenceKind.ERROR, {"action": "generation_state_binding", "error": "adapter receipt differs"}, [eid])
        if receipt.get("valid") is not True or type(text) is not str or not adapter_bound:
            return None, eid
        return text, eid

    def add_grid(self, index, grid, origin, evidence_id, view=None, program_id=None):
        grid = legacy._grid(grid)
        digest = _hash(grid)
        pool = self.pools[index]
        if digest not in pool:
            if len(pool) >= self.config["max_candidates"]:
                self.decision("discard_candidate", "unique grid capacity", query_index=index, grid_sha256=digest)
                return
            pool[digest] = GridHypothesis(grid, digest)
        candidate = pool[digest]
        candidate.origins.add(origin)
        if view is not None:
            candidate.view_support.setdefault(origin, set()).add(view)
        if program_id:
            candidate.program_ids.add(program_id)
        eid = self.memory.add(EvidenceKind.GRID, {"query_index": index, "grid": grid, "grid_sha256": digest,
            "origin": origin, "view": view, "program_id": program_id}, [evidence_id])
        candidate.evidence_ids.append(eid)

    def direct(self, phase, count):
        # Round-robin floor: each query receives view zero before any second view.
        for view in VIEWS[:count]:
            for index, pair in enumerate(self.task["test"]):
                if not self.available("generation"):
                    return
                messages = grid_codec.grid_messages(view.demos(self.task["train"]), view.forward(pair["input"]))
                text, eid = self.generate(messages, "grid", phase, index, view.index)
                if text is None:
                    continue
                try:
                    output = view.inverse(grid_codec.decode_grid(text))
                    self.add_grid(index, output, phase, eid, view.index)
                except (ValueError, TypeError, IndexError) as exc:
                    self.memory.add(EvidenceKind.ERROR, {"action": "grid_decode", "error": str(exc)[:512]}, [eid])

    def score(self, phase, origin=None):
        for index, pair in enumerate(self.task["test"]):
            pool = self.pools[index]
            eligible = [c for c in pool.values() if origin is None or origin in c.origins]
            eligible.sort(key=lambda c: (-c.support(origin), c.sha256))
            chosen = eligible[:self.config["score_candidates"]]
            self.decision("score_common_views", "same ordered eight views and adapter snapshot", phase=phase,
                          query_index=index, adapter_sha256=self.adapter, candidate_sha256=[c.sha256 for c in chosen],
                          excluded_sha256=[c.sha256 for c in eligible[len(chosen):]])
            # Round-robin across grids. A partially evaluated grid never gets a
            # better likelihood rank than one with all eight valid views.
            for view in VIEWS:
                messages = grid_codec.grid_messages(view.demos(self.task["train"]), view.forward(pair["input"]))
                for candidate in chosen:
                    key = (index, candidate.sha256)
                    entry = self.scores[phase].setdefault(key, {"adapter_sha256": self.adapter, "views": [], "evidence_ids": []})
                    if not self.available("score"):
                        return
                    completion = grid_codec.encode_grid(view.forward(candidate.grid))
                    try:
                        receipt = self.model.score_completion(messages, completion, deadline=self.deadline)
                        if type(receipt) is not dict:
                            raise ValueError("score receipt must be a dictionary")
                        _json(receipt)
                    except BudgetExceeded as exc:
                        self.stop_reasons.add("session_budget")
                        self.decision("stop_scoring", str(exc)[:160])
                        return
                    except Exception as exc:
                        receipt = {"valid": False, "error": str(exc)[:512]}
                    valid = (receipt.get("valid") is True and receipt.get("adapter_state_sha256", self.adapter) == self.adapter and _finite_number(receipt.get("nll_sum")) and
                             _finite_number(receipt.get("mean_nll")) and type(receipt.get("token_count")) is int and receipt["token_count"] > 0)
                    if valid and not math.isclose(receipt["nll_sum"] / receipt["token_count"], receipt["mean_nll"], rel_tol=1e-6, abs_tol=1e-6):
                        valid = False
                    eid = self.memory.add(EvidenceKind.SCORE, {"query_index": index, "grid_sha256": candidate.sha256,
                        "view": view.index, "phase": phase, "adapter_sha256": self.adapter,
                        "valid": valid, "receipt": receipt}, candidate.evidence_ids[:1])
                    entry["views"].append({"view": view.index, "valid": valid,
                        "mean_nll": receipt["mean_nll"] if valid else None})
                    entry["evidence_ids"].append(eid)
                    self.event("score", receipt, phase=phase, evidence_id=eid, query_index=index,
                               grid_sha256=candidate.sha256, view=view.index)

    def likelihood(self, phase, index, candidate):
        entry = self.scores[phase].get((index, candidate.sha256))
        if entry and [v["view"] for v in entry["views"]] == list(range(8)) and all(v["valid"] for v in entry["views"]):
            return sum(v["mean_nll"] for v in entry["views"]) / 8
        return None

    def program_reason(self):
        policy = self.config["program_policy"]
        if policy == "never":
            return None
        if policy == "always":
            return "explicit always program policy"
        for pool in self.pools:
            candidates = [c for c in pool.values() if "global" in c.origins]
            if not candidates:
                return "missing global direct-grid candidate"
            if len(candidates) > 1:
                return "global reversible views disagree"
            if candidates[0].support("global") < 2:
                return "direct-grid support below two distinct reversible views"
        return None

    def program_feedback(self, parent):
        return {"source": parent.source, "program_sha256": parent.sha256,
                "demo_results": parent.proof["receipt"].get("demos", []), "errors": parent.proof["errors"],
                "partial_score": parent.proof["partial_score"]["exact_fraction"]}

    def cpu_reserve(self, operation):
        if self.work_ledger is None:
            return None
        ident = "controller-" + _hash(self.task_id)[:20] + "-%05d-%s" % (self.counts["cpu_attempts"], operation)
        try:
            self.work_ledger.reserve(ident, {"cpu_checks": 1, "gas": legacy.MAX_STEPS})
        except BudgetExceeded as exc:
            self.stop_reasons.add("session_budget")
            self.decision("stop_cpu", str(exc)[:160])
            return False
        return ident

    def cpu_complete(self, ident, receipt):
        if ident is None:
            return
        if receipt.get("dispatched") and receipt.get("gas") is None:
            self.work_ledger.unknown(ident, "bounded verifier outcome unknown")
        else:
            self.work_ledger.complete(ident, {"cpu_checks": int(receipt.get("dispatched", False)), "gas": receipt.get("gas_charged", 0)},
                                      status="complete" if receipt.get("dispatched") else "excluded")

    def propose_program(self, parent=None):
        if not self.available("generation") or not self.available("cpu"):
            return None
        facts = [{"type": "demo_verification", "program_sha256": row.sha256,
                  "exact_demos": row.proof["partial_score"]["exact_demos"],
                  "total_demos": row.proof["partial_score"]["demo_count"],
                  "all_demo_fit": row.proof["all_demos_fit"]} for row in self.programs[-4:]]
        messages = grid_codec.program_messages(self.task, facts=facts, feedback=self.program_feedback(parent) if parent else None)
        text, generation_eid = self.generate(messages, "program", "global_program_repair" if parent else "global_program", parent=parent.evidence_id if parent else None)
        if text is None:
            return None
        if not self.available("cpu"):
            return None
        call_id = "program-%03d" % self.counts["cpu_attempts"]
        reservation = self.cpu_reserve("demo")
        if reservation is False:
            return None
        proof = program_tools.verify_program(text, self.task["train"], self.root / "programs", call_id, deadline=self.deadline)
        self.cpu_complete(reservation, proof["receipt"])
        eid = self.memory.add(EvidenceKind.VERIFICATION, {"source_sha256": proof["source_sha256"],
            "all_demos_fit": proof["all_demos_fit"], "partial_score": proof["partial_score"],
            "errors": proof["errors"], "receipt": proof["receipt"], "proof_sha256": proof["proof_sha256"]}, [generation_eid])
        self.event("demo_verify", proof["receipt"], phase="global_program", evidence_id=eid)
        program_eid = self.memory.add(EvidenceKind.PROGRAM, {"source": text, "source_sha256": proof["source_sha256"],
            "all_demos_fit": proof["all_demos_fit"], "parent_program_id": parent.evidence_id if parent else None}, [eid])
        candidate = ProgramHypothesis(text, proof["source_sha256"], program_eid, proof, parent.evidence_id if parent else None)
        self.programs.append(candidate)
        if parent:
            parent.repairs += 1
        if proof["all_demos_fit"]:
            self.execute_program(candidate)
        return candidate

    def execute_program(self, candidate):
        for index, pair in enumerate(self.task["test"]):
            if not self.available("cpu"):
                return
            call_id = "query-%03d" % self.counts["cpu_attempts"]
            reservation = self.cpu_reserve("query")
            if reservation is False:
                return
            receipt = program_tools.execute_queries(candidate.proof, [pair["input"]], self.root / "programs", call_id, deadline=self.deadline)
            eid = self.memory.add(EvidenceKind.QUERY, {"program_id": candidate.evidence_id, "query_index": index,
                                                       "receipt": receipt}, [candidate.evidence_id])
            rows = receipt["results"]
            physical = rows[0] if rows else {"dispatched": False, "gas_charged": 0, "owned_descendants_stopped": True}
            self.cpu_complete(reservation, physical)
            self.event("query_execute", physical, phase="global_program", evidence_id=eid, query_index=index)
            if rows and rows[0]["status"] == "valid":
                self.add_grid(index, rows[0]["output"], "program", eid, program_id=candidate.evidence_id)

    def programs_phase(self):
        reason = self.program_reason()
        if reason is None:
            self.decision("skip_programs", "configured off or two-view global agreement")
            return
        self.decision("generate_programs", reason)
        for _ in range(self.config["initial_programs"]):
            if len([p for p in self.programs if p.proof["all_demos_fit"]]) >= 2:
                break
            self.propose_program()
        for _ in range(self.config["repair_attempts"]):
            # Partial fit is solely repair-parent evidence, never prediction evidence.
            if any(p.proof["all_demos_fit"] for p in self.programs):
                self.decision("stop_repairs", "an all-demo-fit program is available")
                break
            failed = [p for p in self.programs if not p.proof["all_demos_fit"]]
            if not failed:
                break
            failed.sort(key=lambda p: (-p.proof["partial_score"]["exact_demos"],
                                      -p.proof["partial_score"]["cell_agreement"], p.repairs, p.sha256))
            parent = failed[0]
            self.decision("repair_program", "best actual verifier partial fit", parent_program_id=parent.evidence_id,
                          exact_demos=parent.proof["partial_score"]["exact_demos"])
            self.propose_program(parent)

    def select(self, policy, phase, origin=None):
        items = []
        for index, pool in enumerate(self.pools):
            candidates = [c for c in pool.values() if origin is None or origin in c.origins]
            def key(candidate):
                nll = self.likelihood(phase, index, candidate)
                tier = int(policy == "full_agent" and bool(candidate.program_ids))
                return (-tier, nll is None, nll if nll is not None else 0.0, -candidate.support(origin), candidate.sha256)
            candidates.sort(key=key)
            selected = candidates[:2]
            floor = None
            if policy == "full_agent":
                direct = [c for c in candidates if c.origins & {"global", "task"}]
                if direct and selected and not any(c.origins & {"global", "task"} for c in selected):
                    floor = direct[0]
                    selected = selected[:1] + [floor]
            evidence_ids = [eid for c in selected for eid in c.evidence_ids]
            selection_eid = self.memory.add(EvidenceKind.SELECTION, {"policy": policy, "query_index": index,
                "ranked_grid_sha256": [c.sha256 for c in candidates], "selected_grid_sha256": [c.sha256 for c in selected],
                "direct_floor_sha256": floor.sha256 if floor else None,
                "likelihood": [{"grid_sha256": c.sha256, "common_view_mean_nll": self.likelihood(phase, index, c),
                                "complete_views_required": 8} for c in candidates]}, evidence_ids)
            items.append({"candidates": [copy.deepcopy(c.grid) for c in selected],
                          "status": "complete" if len(selected) == 2 else "partial" if selected else "missing",
                          "evidence_ids": evidence_ids + [selection_eid]})
        return items

    def run(self):
        policies = {}
        begun = False
        status = "complete"
        try:
            if not self.available("generation"):
                self.decision("stop", "task budget unavailable before first call")
            else:
                receipt = self.trainer.begin_task(self.task_id)
                begun = True
                self.fingerprint("global", receipt)
                self.direct("global", self.config["global_views"])
                self.score("global", "global")
                policies["global_grid"] = self.select("global_grid", "global", "global")
                if self.config["program_branch"] == "base":
                    self.decision("program_base_branch", "preserve frozen-base program capability separately from grid adaptation")
                    with self.model.adapter_branch("base"):
                        self.programs_phase()
                else:
                    self.programs_phase()
                remaining_input = max(0, self.config["max_input_tokens"] - self.counts["input_tokens"])
                adaptation_steps = min(self.config["ttt_steps"], remaining_input // 8192)
                if self.available("adapt") and adaptation_steps > 0:
                    self.decision("adapt_demos", "fresh task-local LODO updates from demonstrations only")
                    adaptation_failure = None
                    try:
                        receipt = self.trainer.adapt_task(self.task_id, copy.deepcopy(self.task["train"]),
                                                        max_steps=adaptation_steps, deadline=self.deadline)
                    except BudgetExceeded:
                        raise
                    except Exception as exc:
                        adaptation_failure = exc
                        receipt = {"status": "unknown", "error": str(exc)[:512],
                                   "steps": adaptation_steps, "input_tokens": adaptation_steps * 8192,
                                   "supervised_tokens": 0, "usage_is_conservative_reservation": True}
                    eid = self.memory.add(EvidenceKind.ADAPTATION, {"receipt": receipt,
                        "inputs": "demonstrations only", "evaluation_claim": "no out-of-sample claim"}, [self.task_eid])
                    self.event("adaptation", receipt, phase="task", evidence_id=eid)
                    if adaptation_failure is not None:
                        raise RuntimeError("task adaptation failed; conservative reservation retained") from adaptation_failure
                    if receipt.get("status") in {"failed_update", "failed", "error", "unknown"}:
                        raise RuntimeError("failed adaptation receipt; restore global without task inference")
                    self.fingerprint("task", receipt)
                else:
                    self.decision("skip_adaptation", "deadline or zero task-step budget")
                    self.fingerprint("task")
                self.direct("task", self.config["adapted_views"])
                self.score("task")
                policies["task_ttt"] = self.select("task_ttt", "task", "task")
                policies["full_agent"] = self.select("full_agent", "task")
        except BudgetExceeded as exc:
            status = "budget_stopped"
            self.stop_reasons.add("session_budget")
            self.decision("stop", str(exc)[:160])
        except Exception as exc:
            status = "error"
            self.memory.add(EvidenceKind.ERROR, {"action": "controller", "error": str(exc)[:512]}, [self.task_eid])
        finally:
            if begun:
                try:
                    receipt = self.trainer.end_task()
                    self.fingerprint("reset_global", receipt)
                except Exception as exc:
                    status = "reset_failed"
                    self.memory.add(EvidenceKind.ERROR, {"action": "end_task", "error": str(exc)[:512]}, [self.task_eid])
        for policy, phase, origin in (("global_grid", "global", "global"), ("task_ttt", "task", "task"), ("full_agent", "task", None)):
            if policy not in policies:
                policies[policy] = self.select(policy, phase, origin)
        if status == "complete" and self.stop_reasons:
            status = "budget_stopped"
        result = {"task_id": self.task_id, "policies": policies, "evidence": self.memory.records,
                  "physical_usage": {**self.counts, "events": self.events, "logical_policies_share_physical_work": True},
                  "status": status, "stop_reasons": sorted(self.stop_reasons)}
        with (self.root / "result.json").open("x", encoding="utf-8") as handle:
            handle.write(_json(result) + "\n")
        return result


def solve_task(task_id, task, *, model, trainer, config, deadline, output_dir, work_ledger=None):
    """Solve one truth-free task and restore its global adapter in a finally block.

    The owner process must still enforce hard neural-call/stage/session deadlines.
    CPU program subprocesses are individually killed/reaped by program_tools.
    """
    return _Controller(task_id, task, model, trainer, config, deadline, output_dir, work_ledger).run()
