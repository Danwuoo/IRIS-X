# ARC-AGI-2 Trial 001

This is the tracked workspace for the first real P2 Engineering Trial admitted
by [Decision 0004](../../docs/decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md).
The trial uses only the official `arcprize/ARC-AGI-2` public training and public
evaluation splits at commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`.

[`trial-profile.json`](trial-profile.json) is a reviewed static input. Raw
upstream data, generated contracts, preflight reports, predictions, results,
and future packages stay under `.irisx/`; none of those local outputs becomes
authority merely by existing.

Trial 001 compares one baseline with one candidate. The only permitted
specialization difference is the candidate's versioned `prompts_programs`
component, deterministically derived from the official public training split.
The complete 120-task public evaluation split is frozen as `public_eval`, and
evaluator truth remains separate from every solver-facing payload.

No model or solver is selected or bound here. Decision 0004 does not authorize
the real run. Execution remains blocked until the owner supplies an immutable
local solver descriptor and execution envelope, every offline preflight gate
passes, and a later explicit owner decision admits the exact run authority and
runtime adapter. A trial-local authorization artifact cannot authorize its own
execution or make result and package evidence eligible.
External providers, networked trial execution, third-party ARC data, and paid
execution are prohibited.

The commands and evidence flow are documented in
[`../../docs/development/arc-agi-2-trial-001.md`](../../docs/development/arc-agi-2-trial-001.md).
