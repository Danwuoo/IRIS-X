# Stage 4 combined-process reliability repair 001

Scope: local CPU process supervision, based on exact commit
`aa2107164b8911c267743210ff3557b4f73ed0dc`. No model, GPU, provider, official
submission or historical run was executed or changed. This report does not
establish integrated or official-scoring readiness.

## Historical finding remains unresolved

The handoff records a 625-test run in 1053.719 seconds with one failing subtest:
`mode='tampered'` expected M2 `failed`, observed `timed-out`. Initially the actual
10/06 companion/log was unavailable and the supplied 10/05 research archive was
a different artifact. The correct restored original log and
`HANDOFF_VALIDATION.json` are now independently read and SHA-256 verified:
`117ef362f4c594071909dfe56ca5c9f2901aa3218285beee55e0443944f7f976`.
Lines 690–703 confirm the Windows assertion but contain no branch stop cause,
readiness/phase observations or fixture artifacts; normal teardown removed the
fixture directories. The prior aggregate-partial assertion passed, which,
together with M2 timed out and the two-branch aggregator, implies M3 completed.
That is an inference from the retained trace and exact test/supervisor source,
not a printed M3 receipt. The precise historical cause remains **unknown**, as
does the earlier, distinct descendant-cleanup failure. Packaging load is context,
not a demonstrated cause, and a later PASS is not a flake classification.

A deterministic counterexample preserves the existing 3-second work budget,
2-second terminal reserve and 0.6-second readiness bound while delaying only
M2's interpreter by 0.8 seconds. M2 becomes `timed-out`, M3 completes, and M2
never writes model-ready or worker-terminal evidence, hence never executes its
tamper payload. That disposition is correct. The former unconditional fault
assertion silently assumed interpreter startup would always fit 0.6 seconds.
This explains a possible mechanism, not the unavailable historical trace.

The fault-classification regression now explicitly admits the fixture only once
its model-ready file exists or its pre-ready process has exited. Admission still
consumes the original overall work budget, uses no retry and does not alter the
production readiness limit. Separate real-launch regressions preserve the slow
startup timeout, pre-ready hang and global work timeout. Test expectations come
from these declared fault/deadline protocols and independent fixture artifacts,
not from solver/candidate outputs.

## Independently established defects

Three newly specified counterexamples were run against the exact base source;
all three failed before the repair:

1. M2 log-reader retirement blocks M3 admission/watchdog handling and can spend
   M3's work budget although cleanup belongs to the terminal reserve.
2. M2's synchronous independent verification blocks observation of an on-time
   M3 exit and incorrectly loses the sibling.
3. A final descendant write after primary exit changes an already-verified
   artifact, yet the old supervisor still reports M2 complete.

These are separately established lifecycle defects, not assertions about which
one caused either historical failure.

## Repair and invariants

- Each branch is launched at most once. A returned process/job is registered
  before log readers are acquired; partial reader startup cannot orphan it.
  Attempt and returned-process counts are recorded separately.
- Exit-poll errors remain branch-local and cannot discard cleanup registration.
  `finish` observes or records the poll failure before removing active ownership;
  a repeated poll/handle error cannot orphan descendants or cancel its sibling.
- Branch retirement proceeds independently while the scheduler continues to
  admit/observe its sibling and enforce the unchanged work/readiness bounds.
  All owned trees begin retirement before terminal joins.
- Readiness admission has fresh guards before querying its marker, after reading
  it and after process polling. An already-present but late marker cannot disable
  its unchanged bound. Returned validator/diagnostic data and input specifications
  are deep snapshots; later callback mutation cannot rewrite reconciled counts.
- A successful leader must be observed inside the work budget. Only after its
  owned tree is stopped and log readers finish do envelope and independent
  semantic verification run within the existing terminal reserve. No model
  work is admitted in that reserve.
- Admission and successful-exit checks read the monotonic clock again after
  ready/event/directory IO. A loop-start timestamp cannot admit a sibling or
  qualify a completed leader after that IO crosses the absolute work deadline.
- A readiness/global timeout retains the parent's stop cause separately from
  worker diagnostics. Exit observed before stop, readiness, disposition time,
  process-exit/log-drain observations and retirement completion are explicit.
  Leader exit, tree observation and log completion are distinct evidence.
- Cleanup failure cannot become complete. Emergency cleanup attempts the owned
  POSIX process group or Windows job and primary wait independently. Launch,
  gate, log-reader and retirement-thread failures preserve their primary and
  secondary errors and continue cleanup of the other owned resources.
- Child JSON rejects duplicate keys, non-finite constants and float overflow.
  Ready/diagnostic identity includes the exact child run ID. Partial diagnostic
  callbacks cannot overwrite supervisor disposition or identity and must remain
  serializable. Candidate/artifact/event retention failure cannot become complete.
- Counter and device bindings compare canonical JSON bytes rather than Python
  equality, which aliases `True` with `1` and `1.0` with `1`. Recomputed parent
  hardware and each logical-device field use the same type-preserving binding;
  the logical CUDA index must specifically be an integer. No numeric counter,
  device/resource limit or semantic qualification threshold is changed.
- A terminal-budget overrun produces a failed, unconfirmed retirement receipt.
  Its published/returned manifest is frozen; an overdue verification thread
  cannot later replace it with a successful result. Python cannot forcibly stop
  arbitrary blocking validators or filesystem/kernel calls, so this is explicit
  failed evidence, not a claim that every such callback has stopped.
- Retirement-thread refusal issues immediate owned termination without waiting,
  then defers full log/IO retirement until no active sibling needs observation.
  That no-thread fallback skips arbitrary partial callbacks, explicitly retaining
  unknown unreconciled counts and the raw files; it cannot block the parent on a
  validator/diagnostic callback.
  Ordered asynchronous event delivery uses only short bookkeeping locks, so a
  terminal append cannot suspend the scheduler. Per-branch event errors/pending
  writes are retained, separately from dispatcher-thread exit. Actual appends
  recheck the terminal deadline before and after opening; an overdue callback
  cannot subsequently append a successful terminal observation. Kernel IO still
  cannot be forcibly preempted. Background callback `SystemExit`/other
  `BaseException` failures become explicit failed evidence after owned cleanup.
- Retirement observations are explicitly provisional. Preceding event IO is
  reconciled before final branch terminal records are queued, and those records
  reference `aggregate-terminal.json` as authoritative. A prior append failure
  cannot leave a final successful branch claim beside a failed aggregate.
  Branch-specific directory/environment acquisition is contained locally, so
  failure to prepare M3 cannot cancel an already-working M2.

## Process-tree limits and platform evidence

Linux cleanup sends TERM to the owned session/group, reaps the primary, sends
KILL to surviving group members, and bounds a procfs observation of non-zombie
members. TERM-ignoring child and grandchild fixtures inherit the log pipes;
the new regression confirms both terminate after the primary has exited.
Terminated zombies can remain under the host reaper and are reported separately;
they cannot execute work or retain open descriptors. A procfs read denial is an
error, not evidence of zero live members.

Windows retains CREATE_SUSPENDED, assignment-before-resume and the pipe gate,
plus owned-job termination and active-member accounting before job close. The
job-close secondary exception no longer replaces the primary exception. The
Windows paths were inspected but **not executed on Windows here**. Linux tests
of injected assignment/cleanup and thread failures are not Windows attestation.
Non-Linux POSIX lacks this procfs count and keeps that observation null.
These helpers contain normal inherited process trees; they are not a security
sandbox against a hostile descendant that deliberately escapes the group/job.

## Validation and retained failures

Environment: CPython 3.12.14, Linux 6.18.44 x86_64, glibc 2.41. All process tests
are synthetic CPU fixtures. Commands used `PYTHONPATH=src`, `PYTHONHASHSEED=0`,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, and
`CUDA_VISIBLE_DEVICES=`. No ML backend or evaluator truth is used in these
regressions.

- Original 11 process tests: PASS, 6.259 seconds. This observation does not
  supersede the historical full-suite FAIL.
- Exact-base independent counterexamples: FAIL, 3 of 3, 2.003 seconds, as
  required to demonstrate the old violations.
- An intermediate 52-test focused run: FAIL, one new test errored because launch
  cleanup notes were mistakenly captured in the verification exception path.
  The failed log is preserved; note capture was repaired and the three cleanup
  negatives passed independently in 0.585 seconds.
- Initial final six-module combined focused run: PASS, 57 tests, 14.863 seconds, zero
  failures/errors/skips. This includes the slow startup, sibling retention,
  quiescent verification, ignored TERM grandchildren, acquisition faults,
  malformed/foreign JSON, terminal overrun/immutability and retention faults.
- A subsequent self-review found the inherited stale loop-clock admission/exit
  gate. Two independent negatives both failed against repair commit `4f58908`
  in 0.854 seconds and passed after fresh observation/admission gates in 0.849
  seconds. The newest six-module run passed 59 tests in 15.668 seconds, zero
  failures/errors/skips. Both prior PASS/FAIL logs and the first receipt remain
  unchanged; the new final receipt is a separate artifact.
- Independent review of `69cbf7` retained six additional failing counterexamples:
  late readiness admission, synchronous retirement-refusal fallback, shared event
  IO locking, mutable validator aliases, `SystemExit` evidence loss and late
  successful event append after frozen failure. Its stable suite had 6 FAIL /
  3 PASS in 5.769 seconds. These failed observations are not erased by initial
  focused PASSes. The next repair adds the invariants above and six tracked
  regressions; its 65-test focused suite passed in 19.685 seconds. Independent
  acceptance of that next candidate remained pending.
- A further ownership-order negative demonstrated an actual live descendant
  after `finish` removed active ownership and its second poll raised. The tracked
  negative failed before repair in 0.238 seconds and passed in 0.402 seconds
  after branch-local poll guards. The first exploratory probe used an overly
  specific `not-started` condition and printed `False`, while its retained state
  correctly showed the orphan alive (`S`); that exploratory classifier is not
  used as the acceptance result. Both logs and the explicit emergency test
  cleanup remain retained. The current six-module focused run passed 66 tests
  in 20.126 seconds. Independent acceptance of source snapshot SHA-256
  `0c589485266e259e81e20c9d923cb2c074a5cfa1425ce7998898522c697df908`
  was independently checked: the original nine cases and both poll-ownership
  controls passed, while new reserve/event-consistency/acquisition negatives
  required another repair. Those failures remain retained.
- The final source SHA-256
  `909911e7a4c7f32df0ceccc05ceb6179da04de731c60eceb1bc5384b247d7140`
  passes 14 independent cases in 6.837 seconds, zero errors/skips. The reviewer
  accepts those exact bytes for integration/serial full validation with no
  reproduced P1/P2 remaining. Its `ACCEPTANCE_004.md` and 879-file hashed receipt
  are retained separately. The final own six-module scope passes 69 tests in
  21.019 seconds. Neither result establishes integrated, Windows or GPU success.
- A synthetic retention control intentionally fails an otherwise successful
  process test and confirms its 15 original files/receipt remain available.
  This is an expected harness failure, not a product regression. Future actual
  process-test assertion/error failures retain fixture directories; successful
  tests still clean up. One small branch-acquisition after-probe accidentally set
  `PYTHONSEED` instead of `PYTHONHASHSEED`; its log remains a recorded deviation.
  The final complete focused run used all specified offline/CPU/hash-seed flags.
- A final independent type audit qualified the initial 004 acceptance: declared
  boolean `True` counters incorrectly matched independently verified integer `1`
  under Python dictionary equality. The exact 004 negative and qualified receipt
  remain intact. Canonical counter/ready/terminal/hardware type bindings repair
  that defect. Two tracked methods produce nine failed subtests on 004 and pass
  repaired; the newest six-module scope passes 71 tests in 21.815 seconds.
  Final source SHA-256
  `e372161c8c944d4404f25e9575a2be66e9c3a8e8dedcde969d48e2d96c752a8f`
  passes the 15-case independent suite in 6.980 seconds plus a separate hardware
  binding method with six substitution negatives. That hardware method has six
  failed subtests on 004. The reviewer checked the exact typed diff and source
  match and reports no reproduced P1/P2 remaining on 005. Previous 004 acceptance
  is historical, not the final disposition.
- `git diff --check` and compilation of the three changed Python files: PASS.
  A post-run process listing found no live fixture worker/sleep process.

Raw logs, the exact base module, the retained slow-start output/events, source
hashes and a validation receipt are under the ignored local directory
`.irisx/stage4-reliability-001/`. They remain distinct from historical artifacts.
The coordinator owns the serial integrated full suite and repository validator;
this lane did not run either. Independent source review is complete for the
exact final bytes above. Integrated validation, actual Windows execution and
the unresolved historical cause remain outstanding.
