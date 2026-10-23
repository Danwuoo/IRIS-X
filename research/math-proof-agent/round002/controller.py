"""Bounded paired inference with explicit solver and execution-identity boundaries."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import atomic_json, digest, file_digest, validate_scoring_identity, validate_model_cost
from lean_worker import statement_digest
from model_adapter import ContextBudgetError
from evaluator import supported_answer_problem, verified_receipt_matches

ARMS = {"M-DIRECT": 1, "M-SAMPLE": 4, "M-REPAIR": 4}
RUNTIME_SOURCES = frozenset({"common.py", "controller.py", "lean_worker.py", "model_adapter.py",
                             "evaluator.py", "analyze.py"})


def solver_view(problem):
    # Reconstruct nested objects too: statement_digest deliberately ignores
    # evaluator metadata, so copying the whole statement would leak that data.
    statement = problem["statement"]
    if (any(not isinstance(problem.get(key), str) for key in ("id", "natural_language", "answer_mode"))
            or any(not isinstance(statement.get(key), str) for key in ("id", "declaration", "fidelity", "sha256"))
            or not isinstance(statement.get("imports"), list)
            or any(not isinstance(item, str) for item in statement["imports"])):
        raise ValueError("solver fields must be scalar text or import names")
    result = {"id": problem["id"], "natural_language": problem["natural_language"],
            "answer_mode": problem["answer_mode"],
            "statement": {"id": statement["id"], "imports": list(statement["imports"]),
                          "declaration": statement["declaration"], "fidelity": statement["fidelity"],
                          "sha256": statement["sha256"]}}
    if problem["answer_mode"] == "find_answer":
        # Only a fixed mode label; never copy review metadata or arbitrary spec fields.
        result["answer_binding"] = {"kind": "closed_exists_nat_v1", "domain": "Nat"}
    return result


def parse_candidate(text):
    if not isinstance(text, str) or len(text.encode()) > 65536:
        raise ValueError("candidate must be text within byte limit")
    if text.startswith("```json\n") and text.rstrip().endswith("```"):
        text = text[8:].rstrip()[:-3]
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != {"answer", "proof_body"}:
        raise ValueError("expected exactly answer and proof_body")
    if not isinstance(value["proof_body"], str) or not value["proof_body"].strip():
        raise ValueError("empty proof body")
    if value["answer"] is not None and not isinstance(value["answer"], str):
        raise ValueError("answer must be string or null")
    return value


def accepted(result, problem, candidate=None, *, model_text=None):
    return verified_receipt_matches(result, problem, candidate, model_text=model_text)


def validate_binding(problem, model, verifier, protocol, identities, panel, source_files, execution_manifest):
    validate_scoring_identity(identities)
    if (not isinstance(execution_manifest, dict) or execution_manifest.get("scoring") is not True
            or execution_manifest.get("code_sha") != identities["code_sha"]
            or execution_manifest.get("source_sha256") != identities["source_sha256"]
            or execution_manifest.get("source_files") != source_files):
        raise ValueError("identity differs from committed execution manifest")
    if identities["protocol_semantic_sha256"] != digest(protocol):
        raise ValueError("protocol identity mismatch")
    if not isinstance(panel, list) or identities["panel_semantic_sha256"] != digest(panel):
        raise ValueError("panel identity mismatch")
    ids = [p["id"] for p in panel]
    if len(ids) != len(set(ids)) or sum(p == problem for p in panel) != 1:
        raise ValueError("problem must belong exactly once to frozen panel")
    if model.identity() != identities["model_spec_sha256"]:
        raise ValueError("model/tokenizer/runtime identity mismatch")
    if verifier.identity() != identities["verifier_spec_sha256"]:
        raise ValueError("verifier identity mismatch")
    if not isinstance(source_files, dict) or not RUNTIME_SOURCES.issubset(source_files):
        raise ValueError("complete source manifest required")
    if digest(source_files) != identities["source_sha256"]:
        raise ValueError("source manifest identity mismatch")
    root = Path(__file__).resolve().parent
    for name, expected in source_files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path.is_symlink() or file_digest(path) != expected:
            raise ValueError("source bytes mismatch")


def execute_arm(problem, arm, seed, model, verifier, protocol, output, identities, *, panel, source_files, execution_manifest):
    """Fresh execution only; no automatic partial resume or answer-key selection.

    panel is the exact frozen list (including provenance); source_files hashes
    the executing local source. execution_manifest must come from the trusted
    committed-source packager, not solver data; source hashes are checked here.
    Semantic scoring identities are not the smoke manifest's raw-file hashes.
    No scoring runner has yet been qualified, and smoke manifests fail closed.
    """
    output = Path(output)
    if output.exists():
        raise ValueError("fresh result directory required; automatic resume disabled")
    if arm not in ARMS or protocol.get("status") != "frozen":
        raise ValueError("unknown arm or protocol not frozen")
    if protocol.get("arms") != ARMS or not 1 <= protocol.get("max_completion_tokens", 0) <= 4096:
        raise ValueError("invalid frozen proposal ceilings")
    if (not isinstance(seed, int) or isinstance(seed, bool)
            or seed not in [protocol["first_seed"], *protocol["replication_seeds"]]
            or problem.get("answer_mode") not in {"proof_only", "answer_given", "find_answer"}
            or not 0 < protocol["arm_wall_seconds"] <= 10800):
        raise ValueError("unplanned seed, answer mode or wall ceiling")
    solver_view(problem)
    if problem.get("human_review", {}).get("status") != "approved":
        raise ValueError("formal statement lacks attributable human review")
    if statement_digest(problem["statement"]) != problem["statement_sha256"]:
        raise ValueError("statement drift")
    validate_binding(problem, model, verifier, protocol, identities, panel, source_files, execution_manifest)
    output.mkdir(parents=True)
    events = []
    state = {"problem_id": problem["id"], "arm": arm, "seed": seed,
             "identities": copy.deepcopy(identities), "status": "preflight", "events": events,
             "statement_sha256": problem["statement_sha256"],
             "answer_mode": problem["answer_mode"], "planned": True,
             "answer_status": "not_applicable" if problem["answer_mode"] == "proof_only" else "unknown",
             "joint_status": "unqualified" if problem["answer_mode"] == "find_answer" else "not_applicable"}
    atomic_json(output / "checkpoint.json", state)
    setup_start = time.monotonic()
    try:
        preflight = verifier.preflight()
    except Exception as exc:
        preflight = {"status": "blocked", "reason": type(exc).__name__}
    state.update(verifier_preflight=preflight, verifier_setup_seconds=time.monotonic() - setup_start)
    if preflight.get("status") != "passed":
        state.update(status="infrastructure_blocked", wall_seconds=0.0)
        atomic_json(output / "checkpoint.json", state)
        return state
    if problem["answer_mode"] == "find_answer":
        try:
            binding_ok = (supported_answer_problem(problem)
                          and verifier.answer_binding_spec(problem["statement"]["id"]) == problem["answer_binding"])
        except (AttributeError, KeyError, TypeError, ValueError):
            binding_ok = False
        if not binding_ok:
            state.update(status="infrastructure_blocked", reason="answer_proof_binding_unqualified", wall_seconds=0.0)
            atomic_json(output / "checkpoint.json", state)
            return state
        state["joint_status"] = "not_completed"
    started = time.monotonic()
    deadline = started + protocol["arm_wall_seconds"]
    state["status"] = "running"
    base = [{"role": "system", "content": protocol["system_prompt"]},
            {"role": "user", "content": json.dumps(solver_view(problem), ensure_ascii=False)}]
    last = None
    atomic_json(output / "checkpoint.json", state)
    for index in range(ARMS[arm]):
        if time.monotonic() >= deadline:
            state["status"] = "budget_exhausted"
            break
        prompt = list(base)
        if arm == "M-REPAIR" and last is not None:
            prompt += [{"role": "assistant", "content": last["model_text"]},
                       {"role": "user", "content": "Repair the same statement using this tool feedback:\n" +
                        last.get("feedback", "unavailable")[:protocol["feedback_max_chars"]]}]
        event = {"index": index, "parent": index - 1 if arm == "M-REPAIR" and index else None,
                 "prompt_sha256": digest(prompt), "status": "generating", "wall_started": time.time(),
                 "model_cost_complete": False, "tool_attempted": False}
        events.append(event)
        atomic_json(output / "checkpoint.json", state)
        call_start = time.monotonic()
        phase = "generation"
        try:
            generation_seed = int(digest([seed, problem["id"], index])[:8], 16)
            response = model.generate(prompt, seed=generation_seed,
                                      max_new_tokens=protocol["max_completion_tokens"],
                                      temperature=protocol["temperature"], top_p=protocol["top_p"],
                                      deadline=deadline)
            cost = response.get("cost", {})
            event.update(model_text=response["text"], model_cost=cost, stop_reason=response.get("stop_reason"))
            event["model_cost_validation"] = validate_model_cost(cost,
                force_partial=response.get("stop_reason") == "deadline")
            event["model_cost_complete"] = event["model_cost_validation"]["complete"]
            event["status"] = "generated"
            atomic_json(output / f"candidate-{index}.json", event)
            # Deadline outranks parse failure for truncated/late output.
            if response.get("stop_reason") == "deadline" or time.monotonic() >= deadline:
                raise TimeoutError("arm wall exhausted during generation")
            phase = "parse"
            candidate = parse_candidate(response["text"])
            if problem["answer_mode"] == "proof_only" and candidate["answer"] is not None:
                raise ValueError("proof-only answer must be null")
            event["candidate"] = candidate
            phase = "verification"
            tool_start = time.monotonic()
            event["tool_attempted"] = True
            try:
                if problem["answer_mode"] == "find_answer":
                    result = verifier.verify_answer(problem["statement"], candidate["answer"],
                                                    candidate["proof_body"], deadline=deadline)
                else:
                    result = verifier.verify(problem["statement"], candidate["proof_body"], deadline=deadline)
            finally:
                event["tool_wall_seconds"] = time.monotonic() - tool_start
            event.update(tool=result, feedback=result.get("execution", {}).get("output", result.get("reason", "")))
            qualifies = accepted(result, problem, candidate, model_text=event["model_text"])
            event["status"] = "accepted" if qualifies else result.get("status", "unknown")
            if event["status"] == "accepted" and not qualifies:
                event.update(status="trust_rejected", feedback="verifier receipt binding failed")
            if time.monotonic() > deadline:
                event["status"] = "timeout"
        except ContextBudgetError:
            event.update(status="context_budget_exceeded", feedback="fixed prompt/completion context ceiling exceeded")
        except TimeoutError as exc:
            event.update(status="timeout", feedback="resource timeout")
            if hasattr(exc, "cost"):
                event["model_cost"] = exc.cost
        except ValueError as exc:
            event.update(status="invalid_format" if phase == "parse" else "infrastructure_error",
                         feedback=str(exc) if phase == "parse" else type(exc).__name__)
        except Exception as exc:
            event.update(status="infrastructure_error", feedback=type(exc).__name__)
        event["model_cost_validation"] = validate_model_cost(event.get("model_cost"),
            force_partial=event.get("stop_reason") == "deadline" or event["status"] == "timeout")
        event["model_cost_complete"] = event["model_cost_validation"]["complete"]
        event["wall_seconds"] = time.monotonic() - call_start
        last = event if "model_text" in event else None
        atomic_json(output / f"candidate-{index}.json", event)
        atomic_json(output / "checkpoint.json", state)
        if event["status"] == "accepted":
            state["status"] = "proof_accepted"
            if problem["answer_mode"] == "find_answer":
                state.update(answer_status="correct", joint_status="kernel_verified", answer_evidence="kernel_witness")
            break
        if event["status"] in {"infrastructure_error", "infrastructure_blocked", "context_budget_exceeded"}:
            state["status"] = event["status"]
            break
    if state["status"] == "running":
        state["status"] = "budget_exhausted"
    state["wall_seconds"] = time.monotonic() - started
    atomic_json(output / "checkpoint.json", state)
    return state
