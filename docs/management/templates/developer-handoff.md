# Developer handoff template

This is a template, not observations or an independent review. Save one concrete
report in docs/verification/<task>/ after the implementation checkpoint exists.
Register its path and use its document ID for the task's handoff_ref.

## Identity

- Task and state: <task>; review_ready after actual self-tests pass.
- Base/head branches: <actual branch names>.
- Base commit: <full SHA including upstream delivery>.
- target_commit: <implementation checkpoint full SHA>.
- tested_commit: <actual tested SHA if different; explain any merge commit>.
- Delivery commit: recorded externally after this metadata commit exists.
- Draft PR: <actual URL or unpublished reason>; no merge authorization.
- Self-review: developer and implementation subagent checks only.
- Independent review: pending.

## Changes and acceptance

Describe the final behavior, public compatibility and exact changed scope.
List each plan acceptance ID, result and supporting report/evidence. Distinguish
pass, fail, blocked and unexecuted. For ARC research continuity state the adopted
plan SHA, individually indexed R1–R5, prior results/limits and current frozen
comparison. Do not copy a second scientific score ledger.

## Checks

For each command record actual cwd, OS, interpreter/tool versions, allowed
environment settings, exit code, tests/failures/errors/skips/blocked and scope.
Link a compact machine-readable summary. Preserve raw logs in ignored .irisx.
Distribution evidence includes wheel digest, RECORD verification, non-editable
venv origin and execution outside the checkout. No credential/environment dump.

## Regression and preservation

Compare base/head under the same conditions by test ID and exception signature.
Label unpaired failures unclassified. Describe frozen Git blob/path checks and
what is unchanged, explicitly retained in place, only referenced or blocked.
Do not relabel a scoped pass as complete CI, exact reconstruction or GPU success.

## Limits and next action

List actual failures, missing inputs, unavailable environments and unverified
claims. Record downstream provisional dependencies. Return this handoff to the
original ChatGPT conversation for independent commit-bound verification; leave
the task review_ready. A new regression stops its dependent implementation chain.
