# H-P1a Luna structured-program specialization

Status: schema-corrected definition / new-run admission in progress

This experiment executes the bounded H-P1a contract in
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`. The
primary comparison is C1 versus C0 at fixed Luna runtime. C2 is a bounded Terra
seed-program runtime reference only.

The experiment uses the ChatGPT subscription path through Codex CLI. API-key
fallback, retries, recovery, routing, escalation, external web tools, and
candidate repository access are prohibited. Provider monetary cost remains
`Unknown` unless directly attributable evidence becomes available.

Run scripts only in the committed gate order described by the controlling
plan. Run directories and raw records are append-only.

The first model-backed attempt, `design-20260901-chatgpt-01`, is immutable and
blocked after deterministic provider schema rejection. The independently
authorized replacement identity is `design-20260901-chatgpt-02`. Every frozen
structured-output schema must pass `scripts/schema_preflight.py` under the
committed provider-subset policy before the replacement run is admitted. The
preflight uses zero model, network, and API calls and is a temporal-drift guard,
not a claim that provider aliases are immutable.
