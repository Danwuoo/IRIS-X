# Engineering Trials

This directory contains the historical P2 admission package, the closed first
real Engineering Trial, and the runtime-verified bounded Trial 002 smoke.
ARC-AGI-2 Trial 001 used official public data,
one static specialization intervention, a frozen Qwen3.8-27B model, an offline
manual Kaggle handoff, and a zero-USD external paid-execution budget. It closed
as `inconclusive-no-promotion`. The synthetic qualification fixture under
`.irisx/` is not a real trial.

Use [`first-real-domain/README.md`](first-real-domain/README.md) for the terminal
state and retained boundary. Model bytes, ARC bytes, and handoff packages remain
under `.irisx/`.

[`p2-admission/`](p2-admission/) is a decision package, not trial results. It
records the historical blocked state, required owner choices, first-trial
draft, acceptance criteria, falsifiers, and Unknown fields. It remains immutable
historical evidence and is not an authorization token. Decision 0004 now
authorizes creation of the ARC-AGI-2 implementation under the reserved
`first-real-domain/` location.

No further Trial 001 model/solver execution is authorized. Decision 0012 records
that `run-001` returned no result, `run-002` produced only an owner-reported
four-timeout observation, and no `run-003` result was locally accepted.

[`arc-agi-2-baseline/`](arc-agi-2-baseline/) is the distinct Decisions 0014 and
0015 Trial 002 workspace. It preserves the failed first smoke and the completed
replacement using a pinned Qwen3.5-4B solver, four answer-blind public-training
task/test pairs, exactly four inference invocations, and an explicitly mounted
ARC competition on private Kaggle L4 x4. All four jobs returned valid grids,
but local exact-match scoring was 0/4. No further external run or competition
submission is authorized.

[`arc-agi-2-prompt-pilot/`](arc-agi-2-prompt-pilot/) is the distinct Decision
0016 instruction-only research trial. Its first authorization is limited to one
384-job private baseline launch and startup verification; it does not extend
Trial 002 or authorize reflection, retrieval, scoring, or another kernel.
That version 1 failed before the hardware/model runner because its outbound was
not found at the assumed Dataset mount path; no model worker became ready and
no solver generation ran. The launch is consumed.
