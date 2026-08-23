# Stage 1 MVP Entry Gate

## Purpose

Lock the entry conditions for Stage 1 runtime work after Stage 0 conceptual
boundaries have been accepted.

This document is an implementation gate for the first measured runtime spine. It
does not validate the architecture and does not replace experiment or evaluation
results.

## Status

Accepted as the Stage 1 MVP entry gate for Phase 1 runtime implementation.
Stage 1 and Experiment 001 are now closed as `Closed: local smoke completed`
through the OpenClaw `openai-codex/gpt-5.4-mini` candidate canonical local LLM
baseline. That run is still a smoke result, not statistical support for the
architecture.

## Controlled Environment

Stage 1 uses local Document Ops fixtures as the first controlled environment.

The environment is limited to fixture-local document operations over files stored
under benchmark fixture workspaces. Source documents must not be modified unless
a task explicitly allows a reversible fixture-local edit.

## Allowed Action Scope

| Side-effect class | Stage 1 status | Interpretation |
| --- | --- | --- |
| `READ_ONLY` | Allowed | Reads, listings, hashing, and validation that do not mutate fixture files. |
| `SIMULATED` | Allowed | Candidate edits, diffs, and validations that do not write source files. |
| `REVERSIBLE` | Allowed | Fixture-local edits with backup metadata and rollback support. |
| `COMMITTABLE` | Deferred | Not required for the first MVP runtime. |
| `IRREVERSIBLE` | Disallowed | External or non-reversible effects are outside Stage 1 scope. |
| `MEMORY_WRITE` | Disallowed | Durable memory writes are outside Stage 1 scope and are not learning. |

## Verifier v0

Verifier v0 is deterministic and rule-based. It may use JSON Schema validation,
fixture-specific acceptance checks, side-effect-class checks, required evidence
checks, and provenance completeness checks.

Verifier v0 must not be described as a model-based verifier, human-assisted
verifier, or final-answer-only judge.

## Commit Rule

A Stage 1 action may commit only when all of these conditions hold:

- The side-effect class is `READ_ONLY`, `SIMULATED`, or `REVERSIBLE`.
- The verifier decision is `accept`.
- The Evidence Packet contains required Stage 1 evidence fields.
- The Episode Journal records state hashes, evidence references, verifier output
  references, commit status, rollback status, and runtime manifest metadata.
- Reversible actions include backup metadata sufficient for fixture-local
  rollback.

If any condition is missing, the Commit Controller must reject or abort the
action path without updating accepted runtime state.

## Minimum Evidence Before Commit

The minimum Evidence Packet for Stage 1 commit contains:

- `pre_state_hash`
- `post_state_hash`
- `step_id`
- `action_ref`
- normalized `observation`
- `post_state_summary`
- `provenance`
- `runtime_context`

For simulated or reversible edits, the normalized observation must include a
diff or result summary sufficient for verifier and audit review.

## Fixture Layout

Document Ops fixtures are mirrored in two locations:

- `docs/04_experiments/fixtures/document_ops/` is the research-readable source.
- `test/fixtures/document_ops/` is the executable test mirror.

Automated tests must fail if the mirrored fixture trees diverge.

## Non-goals

- Full Context OS optimization.
- Long-term memory governance.
- Model-based verifier implementation.
- Human-in-the-loop verifier implementation.
- Irreversible external actions.
- Production deployment.
- Unmeasured Experiment 001 result reporting.

## Related Documents

- [Stage 0 Boundary Lock](Stage_0_Boundary_Lock.md)
- [Stage 1 Experiment 001 Closure](Stage_1_Experiment_001_Closure.md)
- [Minimal Closed Loop Runtime Spec](../02_specs/Minimal_Closed_Loop_Runtime_Spec.md)
- [Document Ops Benchmark](../04_experiments/Document_Ops_Benchmark.md)
- [Experiment 001: Minimal Loop](../04_experiments/Experiment_001_Minimal_Loop.md)
- [Runtime Module Plan](../06_engineering/Runtime_Module_Plan.md)
