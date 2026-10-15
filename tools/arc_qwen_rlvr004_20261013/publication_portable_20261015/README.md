# Consumer-local POSIX publication successor

This directory replaces the original machine's wrapper binding with a reviewed
native Linux/WSL environment. It does not replace the frozen run008 experiment,
material admission, ownership, numeric readback, mutation or terminal-consumer
contracts. Current implementation, review and publication status live only in
the [development progress document](../../../research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md).
The [local handoff](../../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md)
owns the execution sequence and outstanding destination checks.
The immutable [offline validation receipt](VALIDATION.json) records the scoped
tests, source hashes and known aggregate failures; it is not provider admission.

## Boundary

- Linux/POSIX, Python 3.12, effective native filesystem semantics, real account
  HOME, and an explicitly reviewed venv. Native Windows and DrvFS operational
  state are not supported by this repair. The existing flock, SIGALRM total
  deadlines, directory fsync and Linux owned-process gates remain in force.
- No fabricated `kaggle_setup/kaggle.sh`, redirected HOME, copied Windows store,
  extracted token, new trust certificate or disabled verification.
- A fixed interpreter path, resolved executable and SHA256, exact Python patch
  version, venv prefix and SDK root are bound by the reviewed local config.
  An ordinary copied venv executable or one direct, pinned leaf symlink is
  supported; chained/ancestor symlinks are rejected. A new venv created with
  the official interpreter's `-m venv --copies` avoids ambiguous symlink chains.
- Only the official SDK loads/refreshes the existing native
  `HOME/.kaggle/credentials.json`. Adapter checks inspect metadata only: regular
  single-link bounded file, current UID and mode0600, with no alternate auth
  files or environment. New login is a separate user-approved operation.
- `-I -B`, closed child environment, exact source-only SDK imports and the
  unchanged official-session refresh/uncertainty/no-delete logic are retained.
  Proxy settings are inherited unchanged. An existing `REQUESTS_CA_BUNDLE`
  must equal its reviewed local path/hash; absent means Requests default
  verification. This code never installs or selects a new CA.

## Local configuration interface

Use format `irisx/run008-portable-posix-operator-config-v1`. All original fields
remain except `native_wrapper`, which is replaced by this closed `runtime` map:

```json
{
  "venv_prefix": "/work/native-venv",
  "executable": {
    "path": "/work/native-venv/bin/python",
    "resolved_path": "/work/native-venv/bin/python",
    "sha256": "EXACT_LOCAL_EXECUTABLE_SHA256"
  },
  "python_version": [3, 12, 3],
  "sdk_root": "/work/native-venv/lib/python3.12/site-packages",
  "home": "/home/actual-account",
  "requests_ca_bundle": null
}
```

These are illustrative paths, never a deployable config. `home` must equal
the actual account's `pwd` entry and inherited HOME. If Requests already uses a
custom bundle, replace null with exactly `{"path": "...", "sha256": "..."}`
for those existing bytes. Do not edit the environment to fit an example.
The full config retains repository/candidate/scratch/state/evidence/stop paths,
username, manifest SHA, the five numeric versions and fresh remote predecessor.
State/evidence remain `state-run008`/`evidence-run008` beneath the reviewed
scratch; choose a new scratch only after reconciling all prior claims and stop
latches. A new directory is never permission to repeat an uncertain mutation.

The launcher takes the original explicit arguments:

```sh
python3 tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/launch.py publish validate \
  --manifest /reviewed/candidate/publication-manifest.json --manifest-sha EXACT_SHA \
  --material /reviewed/material.json --material-sha EXACT_SHA \
  --review /reviewed/transport-review.json --review-sha EXACT_SHA \
  --local-config /reviewed/local-config.json --local-config-sha EXACT_SHA
```

`validate` needs the completed original admission contract. It creates no
Provider and does not prove authentication, GPU readiness or scientific success.
All original action names and remaining CLI arguments are preserved. Runtime
source and fresh consumer/action reviews must refer to this successor's exact
bytes; an old wrapper-config or review is rejected.

## Official packages and authentication facts

The unchanged [SDK source lock](sdk-lock.json) fixes Kaggle2.2.4 and SDK0.1.37,
including all170 Python source members. [Official wheel provenance](SDK-WHEEL-PROVENANCE.json)
records exact registry URLs/hashes and static closure verification. Both wheels
declare Python>=3.11. This lock does not claim to lock every transitive dependency;
record the installed dependency environment separately. Version metadata alone
does not prove loaded origin or source identity.

OAuth load/save/refresh uses the native home store; `KAGGLE_CONFIG_DIR` controls
general CLI config and does not relocate OAuth. Refresh directly writes the
store and attempts chmod0600, so metadata checks and durable uncertain-refresh
handling remain essential. See the [pinned credential implementation](https://github.com/Kaggle/kaggle-sdk-python/blob/ae99c895ac3d5cfb80436be8e426c0bc658c5892/kagglesdk/kaggle_creds.py#L15-L136).
Importing `kaggle` can authenticate, including help/version probes; inspect
versions with `importlib.metadata`, without importing either SDK package.

When separately approved by the user, the official native login command is:

```sh
/verified/native-venv/bin/python -I -B -m kaggle auth login --no-launch-browser
```

The pinned CLI requests `resources.admin:*` and saves persistent native OAuth;
there is no scope-selection flag. User approval must cover that scope/store,
and the user completes official consent. Do not use `--force`, export tokens,
copy a store, log callbacks, or invoke `print-access-token`.
See [pinned login source](https://github.com/Kaggle/kaggle-cli/blob/f0afa32699d28c97f82691728ada3ed8c16c5abf/src/kaggle/api/kaggle_api_extended.py#L1596-L1612).

## Hash-chain and independent wire review

[Frozen provenance](FROZEN-SOURCE-PROVENANCE.json) identifies the seven unchanged
source originals. The successor's acyclic pins are config/auth → common →
transport → collector → launcher. The source-only SDK lock is byte-identical.
Even a binding-only change alters the collector SHA: pass that new explicit
collector to the existing `admission_run008/assemble.py`, and regenerate the
proposal, independently reviewed release/material, consumer operator/entry,
derived manifest/notebooks and final transport/monitor reviews. The original
259 runtime members/source archive and21 consumer helpers remain exact bytes.
No old review or invented attestation can stand in for this rebinding.

`verify_active_wire.py` uses static-pin format
`irisx/run008-portable-active-review-static-pins-v1`, with an explicit five-field
`versions` map matching local config, manifest and actual numeric readbacks.
It retains the original actual-wire receipt format and all immutable60-second
JIT, unsent-claim, source, clock and exact settings checks. The old verifier's
fixed21/40/41 assumption is not reused for another allocation. The verifier
does not allocate a clock, mutate a candidate or send a RUN.

## Offline regression entry

Use a Python3.12 test environment containing Requests. The scoped CPU receipt
records Requests2.32.5; the SDK itself is never imported by these mocked tests.
This test environment is separate from a fully installed local provider runtime.

```sh
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/tests -v
python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/tests -v
```

Providers, credentials, CA contents and JIT fixtures in these tests are synthetic.
Frozen regressions are source-bound and run against the successor; obsolete
wrapper assertions are replaced by the new binding tests. AST comparisons
constrain common/transport/collector and official-session changes. Process lock,
timeout, failed writes, cleanup and TLS send-path tests are separate from model,
provider, authentic material reconstruction and scientific efficacy evidence.
