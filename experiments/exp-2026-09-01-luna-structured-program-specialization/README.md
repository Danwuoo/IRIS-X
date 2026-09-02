# H-P1a Luna structured-program specialization

Status: complete valid H-P1a experiment / Phase 4 closure evidence

This experiment executes the bounded H-P1a contract in
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`. The
primary comparison is C1 versus C0 at fixed Luna runtime. C2 is a bounded Terra
seed-program runtime reference only.

The experiment uses the ChatGPT subscription path through Codex CLI. API-key
fallback, retries, recovery, routing, escalation, external web tools, and
candidate repository access are prohibited. Provider monetary cost remains
`Unknown` unless directly attributable evidence becomes available.

The valid replacement design run is `design-20260902-chatgpt-03`; its selected
C1 is `opt-02-r01`, SHA-256
`8bf10ea83da6c6096405d1c12a045c9830f5d4a6dc2ebefeff538a9fc5eeec1b`.
Blind run `blind-20260902-chatgpt-03` completed all 96 frozen schedule entries
exactly once. The reviewed result is `Supported — task-local`: C1 achieved
32/32 blind verified successes versus C0's 18/32. C2 is retained only as the
bounded Terra seed-program reference documented in the reviewed
interpretation and `research/phase-4-closure.md`.

Run scripts only in the committed gate order described by the controlling
plan. Run directories and raw records are append-only.

The first model-backed attempt, `design-20260901-chatgpt-01`, is immutable and
blocked after deterministic provider schema rejection. The second identity,
`design-20260901-chatgpt-02`, is also immutable after a zero-model-call
pre-invocation adapter path-binding failure. The independently authorized
replacement identity is `design-20260902-chatgpt-03`. Every frozen
structured-output schema must pass `scripts/schema_preflight.py` under the
committed provider-subset policy before the replacement run is admitted. The
preflight uses zero model, network, and API calls and is a temporal-drift guard,
not a claim that provider aliases are immutable.
