# Engineering Trials

This directory contains the historical P2 admission package and the first real
Engineering Trial. ARC-AGI-2 Trial 001 uses official public data, one static
specialization intervention, a frozen Qwen3.8-27B model, an offline manual
Kaggle handoff, and a zero-USD external paid-execution budget. The synthetic
qualification fixture under `.irisx/` is not a real trial.

Use [`first-real-domain/README.md`](first-real-domain/README.md) for the current
state, next action, and fixed boundary. Model bytes, ARC bytes, handoff packages,
returned predictions, and evaluation evidence remain under `.irisx/`.

[`p2-admission/`](p2-admission/) is a decision package, not trial results. It
records the historical blocked state, required owner choices, first-trial
draft, acceptance criteria, falsifiers, and Unknown fields. It remains immutable
historical evidence and is not an authorization token. Decision 0004 now
authorizes creation of the ARC-AGI-2 implementation under the reserved
`first-real-domain/` location.

The real ARC-AGI-2 model/solver run is not yet authorized. It requires a passing
technical preflight and a separate explicit owner execution authorization.
The prior non-checkpointing `run-001` attempt returned no result; the active
implementation target is the separately identified, resumable v4 `run-002`
transport defined by Decision 0011.
