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

## Mathlib follow-up after delivery 3fcb8410

The initial core-only record above is preserved. A subsequent offline continuation
qualified a **local Mathlib import subset** on the same Lean runtime. It made no
Kaggle call and did not qualify a scoring panel or a remote verifier.

The official `v4.19.0` tag resolved to
`c44e0c8ee63ca166450922a373c7409c5d26b00b`; its `lean-toolchain` is
`leanprover/lean4:v4.19.0`. Source and cache identities are:

- Official source archive:
  <https://codeload.github.com/leanprover-community/mathlib4/tar.gz/c44e0c8ee63ca166450922a373c7409c5d26b00b>.
- Archive SHA-256:
  `9fce64f31ba5612df46871eee8b4581c81c120604deb08cc35fa9f0fb543a425`.
- Unchanged upstream `lake-manifest.json` SHA-256:
  `5c6421b650bc87a2427a892a39e5522dc44543ca4ac1bd6e9f08d536c044a752`.
- Frozen local project tree:
  `d0bb542569dd4742f2b883fea29caf41be39694a3d776c47a5a70d013c8faf79`.
- Compiled-cache manifest fingerprint:
  `33baebe77f94253328a6e8814f750b35cf6717a2454751d2ad4fc7b33f61ac87`.

The dedicated project is
`/home/wurre/irisx-math-m002-lean-20261019/mathlib-project-c44e0c8ee63ca166450922a373c7409c5d26b00b`.
It was materialized from an explicit allowlist: `Mathlib/`, `Cache/`,
`Mathlib.lean`, `lakefile.lean`, `lake-manifest.json`, `lean-toolchain`, and
`LICENSE`. The official source archive also bundled non-runtime directories;
`Archive`, `Counterexamples`, and `MathlibTest` were not inspected for proofs,
used as task/evaluator data, or included in this worker project. No benchmark
reference proof entered prompts or Git.

`lake exe cache --help` built the upstream cache tool and obtained eight
dependencies at the original manifest's exact commits. All eight checked-out
HEADs and clean source states were read back; their commits, Git trees and
license-file hashes are in
[`mathlib-tests.json`](../../../../docs/verification/MATH-002/mathlib-tests.json).
Mathlib and seven dependencies declare Apache-2.0; `Cli` declares MIT.
No `lake update`, global install, toolchain upgrade, or package-source edit ran.

The exact cache request was:

```text
<existing-Lean-root>/bin/lake exe cache get Mathlib.Tactic.Ring Mathlib.Tactic.NormNum
```

Run it from the dedicated project, with the existing Lean `bin` first in the
child process PATH and `MATHLIB_CACHE_DIR` set to the task-owned
`/home/wurre/irisx-math-m002-lean-20261019/mathlib-cache`. Acquisition used a
clean child environment, task-owned HOME and no credentials. The official tool
downloaded 691 transitive cache files, 29,365,191 compressed bytes, from
`https://lakecache.blob.core.windows.net/mathlib4`. Its pinned helper was
[`leantar` 0.1.15](https://github.com/digama0/leangz/releases/tag/v0.1.15),
executable SHA-256
`c3294bf820d5d1d7cc59bc3ce9bdc244b3f45cab37ea9dd649e1a388c20dbe3c`.
`cache lookup` read back the exact Mathlib commit above in the Ring and NormNum
archive comments. Existing local caches should be reused; `get!` is unnecessary.

The unchanged `lean_worker.py` execution policy still requires measured isolation,
immutable statement bindings and final-theorem transitive axiom checks. The
parent added process-exit classification so a wrapped signal (128–255) is an
infrastructure error. The new `mathlib_controls.py` also requires negative Lean
controls to return exit 1 with actual Lean error diagnostics; a crash cannot count
as a correctly rejected mathematical statement.

The first 2 GiB address-space run failed: all seven actual Lean processes exited
139 with empty output while importing this closure. That raw receipt remains at
`.irisx/line-b/MATH-002/mathlib/controls-attempt01.json`. Its original 6/10
status-matching count is **not semantic-control qualification**. A separate
4 GiB configuration then passed, with the runtime/library bytes unchanged.
This is a virtual-address-space limit, not a claim that Lean needs 4 GiB resident
memory. Other limits remain 30 wall seconds, 20 CPU seconds, 64 processes,
64 open files, 64 KiB output and zero core dumps.

The final invocation was:

```bash
PYTHONHASHSEED=0 /home/wurre/irisx-math-m002-lean-20261019/venv/bin/python -P -s -B research/math-proof-agent/round002/lean/mathlib_controls.py --config .irisx/line-b/MATH-002/lean-config-mathlib-4g-local.json --output .irisx/line-b/MATH-002/mathlib/controls-final.json
```

Use a fresh output filename to reproduce. The ignored config extends the original
core config with `project_root`, the project tree hash above, full
`mathlib_revision`, relative Lean library paths under `.lake/build/lib/lean` and
each pinned package, and `limits.memory_bytes=4294967296`.

Final results: 10/10 authored controls, 19/19 measured local isolation checks,
and **separately** 6/6 synthetic process-receipt branch tests. There were seven
actual Lean executions: Ring/NormNum/Omega each accepted a true control and
rejected a false control; a hidden arbitrary axiom was rejected despite exit 0.
The other three actual controls rejected native evaluation, command injection
and a statement-binding mutation before Lean execution. The synthetic branch
tests executed no Lean process. Final wall cost was 22.442 seconds, including
14.350 seconds of preflight; actual Lean candidate wall cost was 8.042 seconds.
Startup flags and source hashes were recorded and unchanged during the run.

This qualifies only these imports and authored local controls. It does not claim
full Mathlib coverage, human statement review, an independent proof checker,
model success, or Kaggle isolation. The original unresolved Kaggle submission
and the absent human-reviewed frozen panel still block a scored comparison.
