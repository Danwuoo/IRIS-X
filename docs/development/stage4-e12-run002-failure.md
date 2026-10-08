# E12 RUN002 — preserved native failure

Kaggle accepted exactly one save-and-run request as notebook ID 137327571,
version 10, under `stage4-e12-probe-prefix-20261007-002`. A preceding attempt
failed on a read-only gateway response before any SaveKernel call. The admitted
source is `51e2e9a1c4ada49b5a426ab77241c38190245d88`; test checkpoint
`7c4eb589628511dad03e71fcfad8ead7fbd2b8af` changes only test context.

Active monitoring observed RUNNING and then ERROR at 2026-10-08 00:02:16 UTC.
The original delivery ZIP is 4,006,489 bytes, SHA-256
`fde6b0bfb89cc78efa9cbcc90a204f3e402d99588cad4fc59e560a0a56faf7b8`.
Its nested runtime ZIP has 324 members, 3,988,986 bytes and SHA-256
`0bb29f35f05ec91092fb2ccfb3101655511809543cd07b63adaf467cbf3cdfd1`.
Safe archive/source/material checks, confirmed owned-producer stop and actual
post-write finalization pass. The complete archive preserves a failed pilot;
it is neither a successful pilot nor a diagnostic-only summary.

## Grounded cause

Worker 2 completed its ttt64 arm and trained all 128 updates in its second arm.
Starting that arm's inference test 0 raised `one telemetry lifecycle per test
required`. The worker passed one `PhaseTelemetry` instance to both arms, so
`begin_test(0)` found the first arm's existing key. The coordinator stopped the
other workers without retry. This is a host bookkeeping lifecycle defect, not
an observed OOM, numerical-training failure, quota termination or watchdog
expiry. A direct CPU reproduction through the real telemetry and solve-test
lifecycle reproduces the same exception. The remedy is separate retained
inference telemetry for each arm while keeping the same resident model.

## Qualified extent

Durably completed optimizer updates are 646, rather than 768 planned or 384
closed-first-arm updates:

| Worker | ttt64 | ttt128 |
|---|---:|---:|
| 0 | 64 | 65 |
| 1 | 55 | 128 |
| 2 | 64 | 128 |
| 3 | 14 | 128 |

There are 648 completed training forwards and 646 completed backward/callback
records. Interrupted or unpersisted work is not promoted to completion. Six
native tests entered inference; seven allocations were created. All six tests
stopped at generation limits, with eight retained unqualified attempts and
zero eligible outputs. There is no complete pair or valid quality comparison.
No evaluator gold or confirmation data was opened.

Four distinct BF16 L4s, original model/dependency byte bindings, and matching
observed row/LR/RNG prefix structure are evidenced. All first-arm resets pass;
worker 2 also has its second reset and final control. Workers 0, 1 and 3 were
SIGKILLed and lack terminal reset and peak-memory summaries. Those gates remain
unknown. All owned process groups and the coordinator were confirmed stopped.

Coordinator host wall time was 912.026 seconds. The outer interval through the
post-write receipt was 918.688 seconds. Neither is GPU kernel time or a total
allocated-GPU cost measurement. A post-terminal account observation had
9,597.4081 free quota seconds, zero reserved and paid scaling off. The account's
used-quota delta was 1,905.726 seconds; it is not attested job-specific billing
and does not exclude other account activity. The conservative reservation
waiver did not enable paid compute or alter the scientific workload.

## Preserved failures and recovery

The required corrected full suite ran 1,089 tests: one retained-native failure,
36 historical/dependency errors and 44 skips, with no new baseline labels.
The first failed integration run remains preserved. A valid RUN fixture
context and startup `PYTHONHASHSEED=0` resolved its new observations without
weakening production gates. Eighty-two independent CPU package/wire/admission
checks passed before submission; they did not establish real runtime success.

Terminal log retrieval initially failed before the log request on ProxyError.
The bounded same-route recovery obtained the exact v10 log. The first delivery
RPC hit an official SDK parser defect: HTTP 302 with application/json and an
empty body was parsed as JSON before redirect handling. A tested raw-response
capture on the same endpoint then downloaded the exact file anonymously, with
version/source checks before and after. No access denial was bypassed, signed
URL retained, or new GPU run made.

The result validator's initial allowlist omitted `dependency-setup.log`, which
the frozen producer contract explicitly allows. Its first rejection and narrow
correction are preserved; scientific requirements did not change. The final
independent reconciliation distinguishes 646 durable updates, six native tests
and seven allocations explicitly.

The complete owner artifact is `IRIS-X-E12-v10-Failure-Evidence-20261008.zip`,
Library `libfile_6d63e0e06dac8191a8a855846d4db8d7`, SHA-256
`7fd3f467251bec29945fefe1324165ceec027ef39eed2c743dad1802a904d530`.
Original source, requests, receipts, output, log and failures remain unchanged.
The telemetry repair is being tested separately. No repair RUN, full E12 screen,
confirmation evaluation, promotion or official competition submission follows
from this failed result automatically.
