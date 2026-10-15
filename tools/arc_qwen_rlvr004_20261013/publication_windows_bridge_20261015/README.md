# Windows / WSL publication bridge

This is a separately identified successor of the preserved
[POSIX publisher](../publication_portable_20261015/README.md), not a change to the
frozen A/B/C runtime. Status, test evidence and remaining admission blockers live
only in the [development progress document](../../../research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md).
The [existing local handoff](../../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#63-唯一-publisher-的有限提交與監看路徑)
owns environment setup, execution order and permissions. This page defines the
interface; source availability alone does not admit credentials or publication.

## Boundaries

- WSL owns the existing ext4 claims, journals, locks, fsync, immutable clocks,
  candidate/review gates, selected-output collection and evaluator isolation.
- A fixed Windows venv runs the official Kaggle 2.2.4 / SDK 0.1.37 from the
  original profile. `sdk-lock.json` preserves the original 170-source inventory.
  The venv's full dependencies and `pip check` require separate local evidence.
- `native_config.py` binds the actual SID/profile, executable and base-executable
  bytes, `pyvenv.cfg`, Python patch, seven source members and unchanged network
  settings. It performs metadata checks, never extracts credential contents.
- `native_auth.py` alone delegates auth to the official library. A refresh needs
  durable WSL intent acknowledgement before the official refresh/save, then a
  second durable completion acknowledgement. Uncertain state blocks replay.
- `protocol.py` implements closed DTOs and bounded binary content. Credentials,
  signed URLs and staging tokens stay Windows-local. WSL sees opaque upload
  handles; no generic method, URL, shell or environment execution is accepted.
- `win_supervisor.py` is the sole Job-handle owner. Assignment is atomic before
  Resume; worker NULL Job queries cannot keep a dead supervisor's Job alive.
  Per-command and nested official-RPC watchdogs are independent of worker code.
- The 43,200-second worker lease is separate from the original experiment clock.
  A clean read-only worker can rotate before expiry; an unknown operation,
  refresh or mutation cannot. Collector monitoring still seeks the actual
  terminal result after the experiment deadline; no clock reset or resubmit.

## Source/config interfaces

`launch.py publish|collect ACTION` preserves the prior required manifest,
material, review and local-config flags plus their hashes. It execs only the
pinned WSL Python with `-I -B`. All original mutation and wire gates remain.
`review_gate` and `git_publication_gate` bind all 18 operator/source/verifier
files; the seven Windows source descriptors must match the same WSL Git files.

The WSL config format is `irisx/run008-windows-bridge-operator-config-v1`.
It retains the POSIX contract fields, adds a hash of the existing `WSL_INTEROP`
socket selector, and adds `windows_bridge` with exactly four entries:

- `executable`, `supervisor`, `configuration`: each has `wsl_path`, `native_path`,
  `sha256`; only an exact `/mnt/<drive>/...` to local drive mapping is admitted.
- `native_acceptance`: `path`, `sha256` for the actual synthetic native receipt.

The Windows config format is `irisx/run008-windows-sdk-runtime-v1`; its exact
schema is in `native_config.validate_document`. `sources` contains only
`win_runtime.py`, `win_supervisor.py`, `protocol.py`, `native_config.py`,
`native_auth.py`, `sdk_worker.py`, `sdk-lock.json`, each with byte count and hash.
`versions` is the same reviewed successor allocation as the WSL manifest.
No config contains tokens, credential contents, delegated auth directories or a
substitute HOME. These consumer-local files remain ignored, not public Git data.
A receipt is structurally checked evidence, not independent review authority.

## Explicit failed-open recovery interface

`launch.py recover validate|prepare|reconcile-read-only` is a separate entry, with
all original contract flags plus `--input` / `--input-sha`. The canonical
[local recovery procedure](../../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#632-原failed-open的獨立恢復邊界)
defines exact input descriptors and approval order. `validate` is local-only;
`prepare` additionally runs the bounded no-auth boot observer and saves state;
`reconcile-read-only` requires a separately approved manual Windows Restart,
new boot evidence and an exact source/config/action review. No command restarts
the computer or automatically retries a failed capability.

Normal native configuration retains the seven-source v1 format. The distinct
`irisx/run008-windows-sdk-recovery-runtime-v1` adds only the eighth pinned source
`recovery_boot_probe.py` and an exact recovery stanza: capability/reservation
hashes, challenge, host/install hash, boot time, expiry, and the fixed
open/dataset/kernel/status/close allowlist. Normal entry rejects recovery mode.
`recovery_epoch.py` owns append-only preparation, one-use reservation, historical
disposition and a fixed completion seal under the same publisher lock/state.
`recovery_entry.py` connects that core to the existing owner and
`RecoveryBridgeClient`; it derives configuration from independently reviewed
templates, never caller-selected extra operations. The old UNKNOWN and its
closure=false bytes remain unchanged. New-session closure uses the original
Job-zero predicate, without exception.

All hash descriptors are integrity bindings, not proof of permission or trusted
host history. Full Restart establishes a new current process boundary; it does
not reconstruct a lost historical receipt. Saved fixtures are synthetic CPU
evidence only. Current actual native and provider acceptance belongs solely in
the development progress document, not this interface description.

## Early native diagnostic

The historical three-file diagnostic at commit `8f2a6d0` is preserved. The current
`native_probe.py` additionally loads the real framing/watchdog source and emits
four source hashes, actual interpreter/base-interpreter/venv configuration
hashes, and ten case results. It uses only synthetic processes and private
throwaway files; it does not import Kaggle, load real auth, contact a provider or
train a model. Run only on the authorized local Windows executor:

```powershell
& <reviewed-venv-python.exe> -I -B <native-checkout>\tools\arc_qwen_rlvr004_20261013\publication_windows_bridge_20261015\native_probe.py
```

Keep stdout, stderr and exit status separate. Linux produces a native-required
failure, not a skipped pass. A non-venv diagnostic can report its observations
but cannot satisfy final venv admission. Ten cases cover metadata, mutex, Job
tree, deadline, pipe EOF, actual Job-owner kill, explicit controller death,
source stability, framed operation expiry and nested official-RPC expiry.
An outer observer Job must be empty before success; merely observing two PIDs
stop is insufficient. This tests the internal synthetic supervisor path, not
production CLI, SDK, existing OAuth, Kaggle or scientific efficacy.
The ParentWatch case alone launches its synthetic controller with the already
hash-bound base interpreter, then launches the original venv supervisor/worker.
It watches that controller PID explicitly; killing a venv redirector instead
can close its own Job before the supervisor emits a receipt. The production
parent-watch default is unchanged. An immediate venv Job may have exact flags
0x3000; the supervisor-owned outer Job still requires exact 0x2000, atomic
membership before resume, no inherited Job handle and full closure proof.

The separate `wsl_native_probe.py` diagnoses WSL caller death through a fixed
native synthetic observer. Its receipt is additional local interop evidence;
it does not manufacture production acceptance or read credentials. Consult its
`--help` for exact local path arguments after verifying the source commit.


## Failed-open diagnostics and recovery boundary

An unsuccessful open remains `UNKNOWN`, including when a valid native Job-zero
receipt proves process closure. Neither the proxy exit nor a later successful
probe makes that operation successful or automatically permits another session.
The existing owner namespace, claims, refresh records and immutable event history
must be preserved. There is no automatic failed-open reconciliation command.

Future failures persist only bounded diagnostic metadata: observed ready/auth/RPC
phase milestones, cleanup outcomes, proxy exit, receipt byte count/hash and a
fixed allowlist of supervisor reason literals. Unknown text is never exported.
`cleanup=complete` describes completion of the bounded cleanup calls, not native
closure; only `native_process_closure_verified` records the existing validated
nonce-bound Job-zero predicate. Phase completion does not mean open succeeded.
Bootstrap failures retain a fixed stage label. If completion checking fails after
a genuine Job-zero query, that closure is retained with a failed result.

Older failures whose native receipt was discarded cannot be repaired by these
new diagnostics. A missing receipt stays missing; controller exit, elapsed time,
new probes or absence of a provider upload claim cannot substitute for it.
Run the existing synthetic native, WSL caller-death and production pre-auth probes
against newly pinned source/config bytes on the local executor before relying on
changed native code. Those no-auth probes are separate evidence and must not open
a new provider session in a namespace blocked by an earlier UNKNOWN.

## Offline tests

```bash
<test-python> -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/tests -v
<test-python> -O -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/tests -v
```

Synthetic fixtures exercise actual DTO/framing, durable journals, bounded file
publication and source gates with external SDK/Windows boundaries replaced.
They cannot establish native cleanup, genuine credential ACLs, provider access,
GPU execution or ARC results. Test counts and exact evidence are maintained in
the single progress document, not duplicated here.
