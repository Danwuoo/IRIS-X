"""Bounded paired inference. Solver views are explicit allowlists, never panel dicts."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import atomic_json, digest
from lean_worker import statement_digest

ARMS = {"M-DIRECT": 1, "M-SAMPLE": 4, "M-REPAIR": 4}
SOLVER_KEYS = ("id", "statement", "natural_language", "answer_mode")


def solver_view(problem):
    return {key: problem[key] for key in SOLVER_KEYS}


def parse_candidate(text):
    if len(text.encode()) > 65536:
        raise ValueError("candidate exceeds byte limit")
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


def accepted(result, problem):
    return (result.get("proof_status") == "kernel_verified"
            and result.get("statement_sha256") == problem["statement_sha256"]
            and result.get("trust_policy_passed") is True)


def execute_arm(problem, arm, seed, model, verifier, protocol, output, identities):
    """Each call is bounded by adapter/worker deadlines and whole notebook timeout.

    No replay of partial candidates: interrupted snapshots remain unknown and
    require explicit identity/budget reconciliation before any future dispatch.
    """
    output = Path(output)
    if output.exists():
        raise ValueError("fresh result directory required; automatic resume disabled")
    if arm not in ARMS or protocol.get("status") != "frozen":
        raise ValueError("unknown arm or protocol not frozen")
    if problem.get("human_review", {}).get("status") != "approved":
        raise ValueError("formal statement lacks human review")
    if statement_digest(problem["statement"]) != problem["statement_sha256"]:
        raise ValueError("statement drift")
    if identities.get("protocol_sha256") != digest(protocol):
        raise ValueError("protocol identity mismatch")
    setup_start = time.monotonic()
    preflight = verifier.preflight()
    setup_seconds = time.monotonic() - setup_start
    if preflight.get("status") != "passed":
        raise ValueError("verifier not qualified")
    output.mkdir(parents=True)
    started = time.monotonic()
    events = []
    base = [{"role": "system", "content": protocol["system_prompt"]},
            {"role": "user", "content": json.dumps(solver_view(problem), ensure_ascii=False)}]
    last = None
    state = {"problem_id": problem["id"], "arm": arm, "seed": seed,
             "identities": identities, "status": "running", "events": events,
             "answer_mode": problem["answer_mode"], "planned": True,
             "verifier_preflight": preflight, "verifier_setup_seconds": setup_seconds}
    atomic_json(output / "checkpoint.json", state)
    for index in range(ARMS[arm]):
        remaining = protocol["arm_wall_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            state["status"] = "budget_exhausted"
            break
        prompt = list(base)
        if arm == "M-REPAIR" and last is not None:
            # Only the last candidate and bounded compiler diagnostics; no gold.
            prompt += [{"role": "assistant", "content": last["model_text"]},
                       {"role": "user", "content": "Repair the same statement using this tool feedback:\n" +
                        last.get("feedback", "unavailable")[:protocol["feedback_max_chars"]]}]
        event = {"index": index, "parent": index - 1 if arm == "M-REPAIR" and index else None,
                 "prompt_sha256": digest(prompt), "status": "generating", "wall_started": time.time()}
        events.append(event)
        atomic_json(output / "checkpoint.json", state)
        call_start = time.monotonic()
        try:
            # Same first seed across arms, separate deterministic proposal seeds.
            generation_seed = int(digest([seed, problem["id"], index])[:8], 16)
            response = model.generate(prompt, seed=generation_seed,
                                      max_new_tokens=protocol["max_completion_tokens"],
                                      temperature=protocol["temperature"], top_p=protocol["top_p"],
                                      deadline=time.monotonic() + remaining)
            event.update(model_text=response["text"], model_cost=response.get("cost", {}))
            event["status"] = "generated"
            atomic_json(output / f"candidate-{index}.json", event)
            candidate = parse_candidate(response["text"])
            if time.monotonic() - started >= protocol["arm_wall_seconds"]:
                raise TimeoutError("arm wall exhausted before verifier")
            tool_start = time.monotonic()
            result = verifier.verify(problem["statement"], candidate["proof_body"],
                                     deadline=started + protocol["arm_wall_seconds"])
            event.update(tool=result, tool_wall_seconds=time.monotonic() - tool_start,
                         candidate=candidate, feedback=result.get("execution", {}).get("output", result.get("reason", "")))
            event["status"] = "accepted" if accepted(result, problem) else result.get("status", "unknown")
            if time.monotonic() - started > protocol["arm_wall_seconds"]:
                event["status"] = "timeout"
        except (ValueError, json.JSONDecodeError) as exc:
            event.update(status="invalid_format", feedback=str(exc))
        except TimeoutError:
            event.update(status="timeout", feedback="resource timeout")
        except Exception as exc:
            event.update(status="infrastructure_error", feedback=type(exc).__name__)
        event["wall_seconds"] = time.monotonic() - call_start
        last = event if "model_text" in event else None
        atomic_json(output / f"candidate-{index}.json", event)
        atomic_json(output / "checkpoint.json", state)
        if event["status"] == "accepted":
            state["status"] = "proof_accepted"
            break
        if event["status"] in {"infrastructure_error", "infrastructure_blocked"}:
            state["status"] = event["status"]
            break
    if state["status"] == "running":
        state["status"] = "budget_exhausted"
    state["wall_seconds"] = time.monotonic() - started
    # Answer correctness is evaluator-only; never inferred from proof-only success.
    state["answer_status"] = "not_applicable" if problem["answer_mode"] == "proof_only" else "unknown"
    atomic_json(output / "checkpoint.json", state)
    return state
