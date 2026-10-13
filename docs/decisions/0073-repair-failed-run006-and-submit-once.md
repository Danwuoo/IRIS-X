# Decision 0073: repair the reported failed run006 and submit once

Status: accepted by the owner's new 2026-10-13 instruction.

The owner reports `notebook failed` and explicitly requests retrieval, repair
and submission. This reopens the results work stopped after Decision 0072;
it does not reactivate monitoring or authorize an unattended repair loop.

The sole local publisher has observed private code Dataset v19 and notebook
v37 `ERROR`, with saved source SHA256
`dd849708ac6c13ccaba5341427b3f700b05123dd857999f41c24e192a7f7ea65`,
matching the consumed run006 receipt. Numeric v37 output retrieval preserves
the original failure files, closures, physical journal and opaque evidence ZIP
outside Git. Original epoch1791901490/deadline1791944690 and all physical work
remain run006's record; no clock, failure or charge is reset.

The worker's inner error is `ValueError: loaded cuDNN backend outside pinned
library directory`. Model loading and native calibration preceded that check.
The old error records no actual mapped library path; the exact offending path
and whether its bytes differ from the pinned wheel remain unproven. A repair
must preserve complete wheel/member hashes, actual API/version observation,
process ownership, closure and evaluator gates, and capture enough bounded
mapping diagnostics for another failure. No PUBLIC120 score exists from v37.

Use a separate `feat/run007-local-repair-20261013` branch derived from the
preserved run006 handoff, after fetching origin. Remote main remains
baaf47d4f449c534ddd4646ab9b3175bbaf1ef89; it has no new runtime change.
Preserve run006 sources, reviews and claims, the failed run005 snapshot/tag,
all user changes and earlier evidence. Implement significant changes with
subagents and obtain an independent fresh review of actual final bytes.

The finite work is retrieval and diagnosis; targeted runtime repair and
distinct successor assembly/operator adapters; affected normal/optimized CPU
and failure/cleanup/package tests; independent review; Git branch push and
verified backup; private code successor processing/readback, inactive notebook
source/settings readback, and one accepted active RUN with a new genuine clock.
Use actual live predecessor versions. Reconcile uncertain writes before any
retry. Do not reuse old approvals for modified bytes or fabricate evidence.

Keep official local authentication, the existing account/hardware, seven
non-code Dataset pins, model, offline switches and ARC3 metadata association.
Retain the 43,200-second whole-session limit, scientific controls, PUBLIC120's
120 tasks / 167 queries and evaluator-only answers. No quota query, resource
purchase, account switch, credential copying, HOME spoofing, force push,
main merge or frozen-tag move is permitted. Raw evidence, weights and secrets
stay outside Git. Report inherited full-suite/CI failures separately from the
new focused tests; CPU validation is not GPU validation.

After the active submission, make the necessary single bracket of identity,
source, settings and current status, then deliver and stop. QUEUED stays QUEUED.
An accepted RUN is not installation, training, inference or scoring success.
No watcher, continued polling, output download, automatic re-submission or
result analysis follows until another owner message.
