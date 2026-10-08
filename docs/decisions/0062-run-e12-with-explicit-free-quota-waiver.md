# Decision 0062: Run E12 with an explicit free-quota reservation waiver

Status: Accepted
Date: 2026-10-07 (UTC)

The owner explicitly requests renewed login and submission of the prepared E12
experiment, waiving the coordinator's conservative GPU-hour reservation:
“程式應該都還在吧，同意登錄，不用管保守時數，提交 run 就對了”.
This changes the reservation policy for this one experiment. It does not
increase the USD 0 ceiling, enable paid scaling, bypass platform limits or
change the scientific workload, native dependency bytes or cleanup deadlines.

The original recovered INERT package `stage4-e12-probe-prefix-20261007-001`
remains immutable. Its manual Editor declarations require at least four free
GPU hours and must not be asserted by an automatic runner. A new package,
`stage4-e12-probe-prefix-20261007-002`, binds the explicit request to a true
automatic RUN admission and a fresh observed provider quota snapshot.
The original conservative four-GPU-hour policy remains the default. Only this
explicit waiver admits a positive remaining free quota below that reservation.
Zero or oversubscribed free quota, paid scaling, stale/mismatched observations,
conflicting reservations or a provider refusal still block admission. An
accepted job may be terminated by the platform if free quota runs out; the
coordinator must preserve that incomplete result rather than claim success.

The unchanged experiment uses the existing private notebook
`danielwuu/stage4-e10-probe-20261006-001` (numeric ID 137327571), with the same
pinned model and previously disclosed modified native dependency stack,
Internet disabled, four L4 GPUs, four selected public development tasks,
independent 64-update and 128-update arms (768 updates in total), and twelve
test executions. Each test has 120 seconds for generation within a 150-second
total window. The internal notebook deadline and requested provider session
limit remain 3,600 seconds; existing producer-stop and artifact reserves stay
in force. No task, training step, generation policy or deadline is silently
reduced to fit the observed remaining quota.

Before the sole save-and-run request, independently review the exact committed
sources, package, embedded executable bytes and actual SDK wire, verify the
current notebook destination/version/settings, and refresh the free quota.
Use the official `SAVE_AND_RUN_ALL` execution type, a journal that distinguishes
unsent, sent, ambiguous and accepted attempts, and no blind duplicate requests.
The current owner workflow requires active monitoring until terminal state,
then exact output retrieval and independent evidence acceptance, without
waiting for a further owner message. A submission receipt is not runtime or
scientific success. The quota snapshot proves its observation time; it is not
an independent attestation of quota or GPU state at a later queued startup.

Preserve failures, prior identities, original recovery artifacts, answer
isolation and the unopened confirmation set. Commit and save the work on the
existing dedicated private recovery branch after stopping; preserve the local
history and any explicitly mapped remote snapshot. This decision authorizes
neither a paid service, new dependency/security scope nor official competition
submission. Stage 4's official score target remains unfulfilled.
