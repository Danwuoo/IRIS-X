# Decision 0063: Repair E12 arm telemetry and run one replacement

Status: Accepted
Date: 2026-10-08 (UTC)

The owner explicitly requested “修正完重新提交 run” at
2026-10-08T00:24:51.517558+00:00, message
`Sentinel_f5427e757f54819193ef59565b8c7b23`.
This authorizes one repaired replacement for failed E12 run002, preserving
Decision 0062's positive-free-quota waiver and USD 0 limits. No further model
run follows automatically from a failure of this replacement.

Preserve run002, its exact submitted package, accepted notebook version 10,
ERROR terminal status, partial training/inference evidence, and failure archive.
Its second arm reused the first arm's PhaseTelemetry test-index namespace and
failed before second-arm inference. Independent per-arm inference collectors
repair that lifecycle error; original worker load/control/training telemetry
remains separate. Do not add elapsed collector times or infer allocated GPU
cost from these overlapping host observations.

The distinct replacement is `stage4-e12-probe-prefix-20261008-003`, expected
version 11 of the same private notebook
`danielwuu/stage4-e10-probe-20261006-001` (ID 137327571), following version 10.
Keep exactly the same four public-development tasks, both independent 64/128
training arms, 768 total optimizer updates, twelve test executions, counterbalance,
model/dependency pins, Internet-off four-L4 hardware gate, per-test windows,
maximum 3600-second notebook/session limits, cleanup and export reserves,
truth isolation, and zero paid spend. Do not reduce the workload to fit quota.

Before the sole SaveKernel, independently review the final committed package
and genuine SDK wire, verify the provider's current version/source/settings,
and refresh actual positive free quota with no conflicting reservation and
paid scaling disabled. An accepted RUN is not proof of runtime completion.
Actively wait through terminal, retrieve the exact version's bounded output,
and independently analyze it without waiting for the owner. The host-only
output transport may correct the already-observed SDK empty-redirect parsing
failure without changing scientific payload or adding any run.

Preserve ambiguous sends rather than blindly retrying. Preserve historical
repository test failures honestly; focused green checks are not a claim that
all retained historical tests pass. After terminal diagnosis, commit and push
audited work to the already-authorized dedicated recovery branch, never main.
No paid scaling, official competition submission, hidden scoring, new native
dependency/security scope, or scientific promotion is authorized.
