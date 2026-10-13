# Bounded offline installer log repair

Local, separately reviewed successor overlay for
`baseline/tools/arc_qwen_transfer_deployment_20261012/bootstrap.py`.
The frozen repository original remains unchanged, SHA-256
`4ddac4166b154e1506fb029373b14297f7b0bfc7c87f37d9e83bcb9f554909f8`.

The original installer redirects both streams directly to `installation.log`.
The enclosing launcher's 8 MiB pipe limit cannot bound that independent file.
This is a demonstrated source robustness defect, **not an established cause of
the unidentified manual run005 failure**.

## Change and invariants

- Replace only `prepare_environment`'s child-running call. Preserve its exact
  interpreter command, isolated/no-bytecode flags, request hash, inherited/offline
  environment, material checks, disk admission, pins and verified receipt gate.
  All other original functions and constants remain unchanged.
- Drain combined stdout/stderr through one nonblocking pipe into the exclusively
  created log, in at most 64 KiB blocks with constant memory. Preserve every byte
  when output is at or below 8 MiB. Retain only the first 8 MiB on overflow and
  raise a failure; a capped prefix is never a successful installation.
- Use the unchanged minimum execution/hard deadline and 120-second outer reserve.
  Map only the original remaining time onto monotonic time before launch, then
  enforce both absolute wall and monotonic deadlines while draining and waiting.
  Wall-clock rollback cannot extend that mapped budget; forward jumps fail closed.
  No request/epoch mutation or new session clock is introduced. The enclosing
  launcher's earlier clock mapping remains authoritative during all preparation.
- Keep the installer inside the existing owned process tree: no new session,
  shell, process group or nested subreaper. On failure, kill/reap the direct child
  with at most one second of cleanup from the existing reserve, then propagate
  the original failure. The existing outer `OwnedProcessGuard` must close every
  descendant and verify its unchanged closure proof. This helper does not claim
  independent tree closure. A surviving child with closed pipes still causes the
  outer guard to reject success.
- Write/flush failures and nonzero child status remain failures. The separate
  preparation-diagnostics overlay can retain its existing bounded 128 KiB excerpt;
  it does not become closure or installation authority.

The 8 MiB cap matches the existing launcher cap and fits inside the unchanged
4 GiB free-space reserve; no storage admission value is reduced. It is a limit
on captured output, not a claim about all installer temporary/storage use.

## CPU validation

Only stdlib synthetic subprocesses execute. No package installation, package or
model download, GPU/model/scorer execution, provider request or publication occurs.
Tests never monkeypatch production modules. Whole-module AST comparison verifies
original behavior outside the narrow child-running call and added helper code.
The actual frozen Linux pidfd/subreaper guard is used, including double-forked,
separate-session descendants, inherited-pipe hangs and closed-pipe survivors.

From the repository root, with more than 5 GiB free:

```sh
mkdir -p .irisx/tmp
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 TMPDIR="$PWD/.irisx/tmp"
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/installer_logging_repair -p 'test_*.py' -v
python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/installer_logging_repair -p 'test_*.py' -v
```

Coverage includes binary combined logs, empty output, nonzero status, exact cap,
overflow, constant-memory capture, expired/earlier hard deadlines, clock arithmetic,
open/closed pipe timeouts, spawn failure, real read-only-file write failure, short
writes, zero-progress writes, injected sink flush failure and offline environment.
Direct cleanup-boundary tests inject pipe-close, kill/wait and error-annotation
failures without replacing production objects. Original failures survive secondary
cleanup faults; a pipe-close fault after otherwise successful work is still failure.
Synthetic clock arithmetic does not change the host clock. Trace allocation stays
below 1 MiB while capturing an 8 MiB log. Timing tests bound controlled subprocesses;
they do not prove behavior under an uninterruptible kernel I/O stall.

## Limits and integration

This directory is source review input only. The assembler must bind the exact old
bootstrap digest and overlay digest into a separately reviewed new source identity;
it must not report the changed baseline member as byte-identical or patch a loaded
production module. Every historical source and consumed run identity stays frozen.
Only the designated publisher may publish or dispatch an admitted successor.
Real pinned installation, production process closure, hardware/model execution,
complete PUBLIC120 scoring and the manual failure's root cause remain unverified.
The targeted tests are not a complete repository/CI pass.
