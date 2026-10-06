# E01 control-review repair 001

This local, offline repair starts at
`8cdfb07ba5ef66253d43e2a37f3f1accc8672cce`. It addresses the two requested
findings in `.irisx/control-review-e01-8cdfb07/review.json`. The prior 57-member
handoff, committed blobs and 591 + 3 passing checks remain retained. The
controller's separate 70-test regression had three missing kill barriers; their
exact pre-barrier cause is unknown. The controller's synthetic cleanup fault
attempted only the first worker and left eight logs open. It launched no real
worker. Controller-created temporary directories are preserved.

Public and official parents now use independent bounded cleanup of registered
processes and streams. The original exception object is retained; stop, poll,
close and drain errors are structured secondary diagnostics. Cleanup failure
without a primary still raises failure. Final checkpoint drain and public archive
creation require confirmed producer exit. Log acquisition is registered before
the next open or launch, so partial acquisition also receives cleanup.

The real CPU writer harness retains seven transaction/projection kill boundaries.
Atomic phase controls and nonce-bound acknowledgements identify minimal startup,
core import, store recovery and the selected barrier. Per-phase and overall
deadlines are finite. Core child imports avoid the test fixture's cold Torch
import. A separate pre-repair observation took 5.798 seconds importing the test
fixture and 0.172 seconds importing the core; this does not establish the cause
of the controller's three earlier timeouts. Controls use the existing bounded
Windows mailbox probation, with malformed/foreign controls failing immediately.
Launcher and actual writer observations are separate; absent writer/handle
evidence stays unknown. Failure case trees and receipts are retained.

`tests.test_nvarc_cleanup` reproduces primary + stop failure, eight stream closes,
unconfirmed-stop drain suppression, simultaneous stop/close/drain errors,
cleanup-only failures, partial open/launch failures, official-finally diagnostic
retention using injected synthetic handles, and public archive suppression.
`tests.test_nvarc_fault_protocol` checks bounded control denial, missing phases,
delayed controls, malformed/foreign messages, atomic replacement and real CPU
missing-startup/missing-barrier cleanup. The existing F01–F24 two-replay matrix,
strict tiny export, frozen transport and solver regressions remain applicable.

Exact commands, counts, durations, failures, hashes, phase controls and process
receipts are retained in `.irisx/stage4-e01-repair-001/`. Initial repair failures
remain recorded: the archive test initially stopped at its earlier input hash
gate; transient Windows control EACCES initially aborted three new harness
cases. Their receipts correctly retain null or independently observed writer
evidence. They do not imply exporter corruption. Final acceptance must use the
frozen tested snapshot and the new handoff, including one full repository check
after the implementation settles.

Scope remains output/checkpoint reliability. No provider request, Kaggle action,
real neural benchmark, download, Dataset mutation, scoring, automation, Goal,
Git push or E10/E20 work is authorized here. Tiny existing CPU regressions are
the only model work. Official 56840442 still has unknown exception cause and null
score. No method promotion, GPU, Linux OS kill or power-loss claim follows.
