# E00 repair 001: bounded mailbox reads

Base `fdf049a432524654bfba986ca3711d4cbe36e562` retained a genuine full
560-test plus three-self-test PASS. The controller's subsequent independent
43-test check failed once at the parent's `workers/3/ready.json` read with
`PermissionError(errno=13)`. Both observations remain unchanged in their
original local evidence directories. The repair is routine local E00 work,
with a new local commit and no push; E01 is not dispatched.

## Established defect and reproduction

The parent checked `is_file()` and then directly opened a mailbox that a
concurrent worker atomically renamed. Existence does not establish that a
Windows handle can be opened at that instant. The parent made one transient
access denial fatal before its next process/deadline poll. The same pattern
existed for ready, done and checkpoint; the worker read job identically.

The retained local reproduction uses 3,000 existing temp/fsync/replace writes
against concurrent CRT `Path.read_bytes` calls. It observed 1,855 reader
denials (`errno=13`, **no winerror**) and 1,577 writer replace denials
(`winerror=5`). A real Win32 exclusive handle deterministically produces the
same CRT reader error, and reading succeeds immediately after that handle
closes. Injecting just one such denied ready read into the exact fdf049a
parent Git blob reproduces its fatal failure before any task dispatch.

This establishes the unhandled concurrent file-access defect, rather than a
fixture-only timing problem. The original controller traceback does not retain
a Win32 error or lock-holder identity; it cannot identify a particular handle,
ACL or filesystem filter as that occurrence's cause. An ACL denial can look
identical. No exact unseen OS component is diagnosed.

An attempted shared-delete reader was rejected in an initial local test:
`Path.replace` still failed while its handle was open in this environment.
That approach is not shipped or claimed to fix writer transactions. The
initial repair test failures are retained, along with the corrected checks.

## Narrow reader change

`MailboxReader` performs one read per poll. Only Windows EACCES with absent
winerror or code 5/32/33 is eligible for finite probation; fifth denied read
raises the error. Optional not-yet-published files remain absent observations;
a required completed checkpoint also has the five-attempt missing-file bound.
POSIX permission denial, EPERM, other OS errors, malformed/duplicate/nonfinite
JSON and foreign identities fail immediately. No broad exception is swallowed.

The parent polls exit and active-task watchdog before live reads, and continues
its original startup/session checks. Completion cannot release a worker for
another task while that task's checkpoint is unavailable. Checkpoint dedup uses
the digest of actually read bytes, eliminating a separate stat/read version
race; the mailbox task ID must match before the unchanged store validation.
Stale completed sequences remain ignored; future or boolean sequences fail.
Worker job parsing now uses the existing strict JSON parser and rejects foreign
task or invalid sequence. It keeps its original deadline between polls.

After all producers are stopped, assigned checkpoints receive a finite final
read drain: at most four 0.2-second waits, with the same five-attempt ceiling
including earlier failures. This occurs after kill/wait, never grants model
work after a deadline, and preserves previously committed candidates on a
permanent failure. Parent progress retains deferred/recovered/exhausted reads
and retirement PID/return code before checkpoint recovery can fail.

The real CPU watchdog/code-17 and normal mailbox tests retain actual subprocess
launch and OS kill/wait. Their child job readers now use the same bounded
reader as the production worker. Separate deterministic fakes exercise each
denial/deadline and invalid message; they do not replace the OS lifecycle test.
No solve, training, budget, ranking, augmentation or dispatch-retry factor is
changed. Source producers for the frozen saved payloads are not rewritten.

## Remaining limits and handoff

Writer sharing failures still stop without an automatic write/model retry;
the previous committed file and uncommitted temp have their existing contract.
Multi-file export/root-copy transactions remain E01 gaps. Kernel-level file
calls are not forcibly preempted; the bounded reader prevents repeated polls
from bypassing process/session/watchdog checks. No GPU timing or external
runtime qualification follows from these CPU observations.

The new local artifact directory is `.irisx/stage4-e00-repair-001/`: reproduction
JSON, legacy blob replay, process receipts, each failure/success log, hashes,
validation and final handoff. The original `.irisx/stage4-e00-001/` and controller
`.irisx/control-review-e00-fdf049a/` remain untouched. The handoff records actual
test counts and the new commit only after completion. No provider request,
Kaggle save/run/query/retrieval, GPU/model run, data download, scoring, Dataset
mutation, automation or cross-chat message is authorized or made by this repair.
