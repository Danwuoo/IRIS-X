# MATH-002 restricted Lean worker

This is a local engineering qualification, not a model evaluation or a qualified
Kaggle verifier. No formal research panel has human statement review. The local
controls are explicitly `authored_engineering_control`; they cannot enter the
default `human_checked` admission route.

## Observed local environment

- Repository: `C:\Users\wurre\Desktop\IRIS-X-Math`.
- WSL: Ubuntu 24.04, Linux `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3.
- Task scratch: `/home/wurre/irisx-math-m002-lean-20261019`.
- Task Python: scratch `venv/bin/python`, with `zstandard==0.23.0` used only to
  extract the public release archive. No global Python or Lean install changed.
- Lean: `Lean (version 4.19.0, x86_64-unknown-linux-gnu, commit 6caaee842e94, Release)`.
- Lake: `Lake version 5.0.0-6caaee8 (Lean version 4.19.0)`.
- Mathlib: **not acquired, pinned, or qualified**. Executed controls use `Init`.
- Bubblewrap: Ubuntu package `0.9.0-1ubuntu0.3`, executable reports `bubblewrap 0.9.0`.

The official Lean release archive is
<https://github.com/leanprover/lean4/releases/download/v4.19.0/lean-4.19.0-linux.tar.zst>.
Its downloaded SHA-256 is
`6fe3ce97a58f44e2b3567d455b994eacec5bfe9ae7774f2a573444480ba813fe`.
The extracted Lean tree fingerprint produced by `tree_sha256` is
`2f0099538d4ccc23173829faa440c7dccfca1e790807336a24a75cba18c6038a`.
The Ubuntu `.deb` SHA-256 is
`2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094`;
the extracted `usr/bin/bwrap` SHA-256 is
`e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71`.
These are observed identities, not a claim of independent binary provenance review.

## Reproduce without global installation

Use the task-owned WSL scratch above, or a new task-owned directory and record the
mapping. Download the exact `.deb` with
`apt-get download bubblewrap=0.9.0-1ubuntu0.3` and extract it locally with
`dpkg-deb --extract <deb> <scratch>/deps/bwrap-root`. Do not run `apt install`.
Fetch the Lean archive from the exact URL above, verify its SHA-256, and extract
using `zstandard.ZstdDecompressor().stream_reader` plus Python 3.12
`tarfile.extractall(..., filter="data")`. Do not run a downloaded installer.
Keep existing archives and weights; no repeated acquisition is needed.

The working local configuration is ignored at
`.irisx/line-b/MATH-002/lean-config-local.json`:

```json
{
  "lean_root": "/home/wurre/irisx-math-m002-lean-20261019/deps/lean-4.19.0-linux",
  "expected_runtime_sha256": "2f0099538d4ccc23173829faa440c7dccfca1e790807336a24a75cba18c6038a",
  "expected_lean_version": "Lean (version 4.19.0, x86_64-unknown-linux-gnu, commit 6caaee842e94, Release)",
  "bwrap_path": "/home/wurre/irisx-math-m002-lean-20261019/deps/bwrap-root/usr/bin/bwrap",
  "work_root": "/home/wurre/irisx-math-m002-lean-20261019"
}
```

From the repository in WSL, run with the controlled startup (do not add `-I` or
`-E`, which would ignore `PYTHONHASHSEED`):

```bash
PYTHONHASHSEED=0 /home/wurre/irisx-math-m002-lean-20261019/venv/bin/python -P -s -B research/math-proof-agent/round002/lean_controls.py --parser-only --output .irisx/line-b/MATH-002/lean-parser-new.json
PYTHONHASHSEED=0 /home/wurre/irisx-math-m002-lean-20261019/venv/bin/python -P -s -B research/math-proof-agent/round002/lean_controls.py --config .irisx/line-b/MATH-002/lean-config-local.json --output .irisx/line-b/MATH-002/lean-controls-new.json
```

Use new output filenames for each attempt. The retained first Lean attempt failed
because the old `-T` argument produced an unknown-option error in this version.
That option was removed; the source sets `maxHeartbeats`, while OS CPU and wall
limits remain active. Attempt 2 and the final-source repeat passed 7/7 authored
Lean controls. The parser passed 13/13 and measured isolation passed 19/19.
See `docs/verification/MATH-002/lean-tests.json` for source hashes and commands.

An initial setup attempted a `/tmp` scratch that did not survive between WSL
invocations, then partially created a repository-root venv after a failed `cd`.
That task-owned incomplete directory was stopped and moved, without deletion, to
ignored `.irisx/line-b/MATH-002/abandoned-wsl-venv`. The effective scratch is the
home-directory task root above.

## Admission and trust limits

`LeanWorker(config).preflight()` must return `status="passed"`; unknown/missing
Linux namespace support or bubblewrap blocks execution. Windows alone fails
closed. `probe_isolation()` needs no Lean installation and returns measured
evidence, suitable for a separate Kaggle preflight. Successful WSL controls do
not establish Kaggle isolation.

Production statements need a separately human-reviewed immutable panel. The
worker requires `fidelity="human_checked"`, the normalized `statement_digest`,
and an entry in the configured `statement_sha256s` map. Setting `sha256` on an
arbitrary caller-provided statement is insufficient. Fixed imported libraries,
Lean bytes and optional project bytes are fingerprinted before admission.

Model input is only a restricted tactic body beginning with a separate `by`
line. The grammar permits basic built-in tactics, selected trusted arithmetic
tactics and identifier-only `exact`/`apply`/`intro` forms. It rejects terms,
commands, macros, arbitrary elaborator code, `run_tac`, and native evaluation.
Unsupported syntax is an explicit retained outcome. This restriction affects
model performance and must be in the frozen prompts/protocol.

The final theorem is named by the worker. Its `#print axioms` output includes
transitive dependencies; only `propext`, `Quot.sound`, and `Classical.choice` are
allowed. An actual hidden dependency on a newly introduced false axiom is rejected
despite Lean exit 0. This is neither an exit-code-only check nor a blacklist of
strings. The Lean kernel, pinned libraries/tactics, runtime, bubblewrap and Linux
kernel remain the trust base; no independent kernel checker was run.

Bubblewrap mounts public system runtime directories and the pinned input/runtime
read-only, exposes a fresh private `/proc`, and omits host home, `/etc`, notebook
inputs and ambient credentials. Its environment is cleared, network namespace
has no routes and cannot reach a host loopback listener, and Linux user/mount/pid
namespaces are distinct. The local probe also enforces memory, process and file
size limits; CPU/open-file/core limits are read back. Default candidate limits
are 30 wall seconds, 20 CPU seconds, 2 GiB address space, 64 processes, 64 open
files, 64 KiB output and zero core dumps. Each process group is killed on timeout.
Only one worker is intended; a caller must not create an unbounded worker pool.
An optional monotonic arm deadline can only reduce the candidate wall limit.

The absence of arbitrary metaprogramming and the measured local boundary are
intentional. This is not a claim that unrestricted hostile Lean code has been
qualified. Public system runtime directories must remain free of credentials;
if a destination cannot establish that boundary, stop before model proof execution.
