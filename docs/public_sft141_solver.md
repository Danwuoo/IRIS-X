# Public SFT141 gold-free deployment runner

This is an independent generic challenge-to-submission endpoint, not a new
model method. It reuses only the already-public diagnostic codec, exact public
model pins and Transformers backend, plus the public submission contract. It
does not modify the frozen 12-parent diagnostic or import its evaluator. No
private model export, historical private runtime, training, TTT, NLL rescoring,
calibration, model download, notebook operation or competition submission is
part of this runner.

## Run and verify

Use Linux, Python 3.11+, an already-prepared compatible PyTorch/Transformers
runtime, exactly one visible BF16-capable CUDA device, and the existing official
model directory. The runner verifies all eight exact public file sizes/SHA-256s
before loading. The public checkpoint identity is
`sorokin/qwen3_2b_grids15_sft141/transformers/bfloat16/1`; the bytes are pinned in
`tools/public_sft141_diagnostic/model_pins.py`. It never downloads weights or
falls back to a different backend.

The challenge must be an official task-ID object with every visible `train`
pair and every ordered `test` input. Test labels and unexpected fields are
rejected. Task insertion order, support order and test order are preserved.
Parent directories must already exist; run/export directories must be new.

```sh
mkdir -p .irisx/public-solver-runs
python -m tools.public_sft141_solver run \
  --challenge /absolute/path/challenge.json \
  --model-dir /absolute/path/official2b \
  --run-dir .irisx/public-solver-runs/run-001 \
  --output-dir .irisx/public-solver-runs/export-001 \
  --budget-seconds 7200

python -m tools.public_sft141_solver verify \
  --run-dir .irisx/public-solver-runs/run-001 \
  --output-dir .irisx/public-solver-runs/export-001
```

Default `--fallback fail` emits no submission if any query has no eligible
candidate. To explicitly request a format-only artifact even for such queries,
add `--fallback copy-input` to the original `run` command. Each unsupported
query then receives its input twice, with separate fallback counts and reasons.
Do not reinterpret this as a model prediction or accuracy result. There is no
retry/resume/export-after-failure CLI: every run has one immutable identity and
one original clock. The read-only `verify` command never runs a model.

Exit 0 means an in-budget, verified artifact, **not model accuracy**. JSON status
explicitly distinguishes format-only fallback, partial-view output, and a
complete eight-view format run. Rejection/failure is nonzero. A hard whole-clock
failure leaves available immutable evidence, never a valid outer completion.

## Frozen deployment protocol

- All parents, all ordered test queries, and all visible supports are included.
- One shared public model load. Exact local WordLevel tokenizer; BF16 CUDA/SDPA;
  no quantization, offload, remote code, adapters, training or alternative models.
- Eight fixed D4 views; greedy generation; the original 931-token ceiling.
- 8192 is **this deployment's frozen policy cap**, not the public model's native
  limit. The pinned config declares 262144 positions. This revision neither
  increases the cap nor claims the larger limit has been validated here.
- Admission requires every view's full support prompt plus 931 to fit the cap.
  Only affected queries are skipped; supports are never silently truncated.
- View-major round robin: every admissible query gets view 0 in original order,
  then every query gets view 1, and so on. No answer-driven priorities, separate
  query time slices, banked unused allowances, regeneration, or fresh clocks.
  Any unused time immediately serves the next original-order slot.
- After the model process and owned descendants exit, raw integer tokens are
  strictly parsed with EOS, inverted into the base orientation, and counted.
  Missing EOS, malformed/ragged grids, illegal tokens and oversized answers are
  not repaired. Top two distinct grids use occurrence count descending, then
  lexical canonical base-grid JSON. A singleton is explicitly duplicated.

Partial completed views may supply real candidates. Every query retains its
`completed_views`, `missing_views`, context reason, candidate pool and vote
counts. An interrupted start with no end is unknown, not zero-cost or successful.
A failed operation records elapsed cost and unknown token work; neither is
retried. `all_queries_eight_views_completed` counts completed returned views,
including invalid answers; `generation_protocol_complete` additionally requires
all views to be strict-valid public-model output, unchanged model state, source
and ownership checks, and an in-budget process exit. It is false for synthetic
backends. `scientific_complete`, `accuracy_established`, and `accuracy_evaluated`
remain false because this gold-free endpoint does not evaluate effectiveness.
A verified protocol-complete run is not thereby an accurate solver.

## Whole clock and process ownership

The independent outer supervisor starts the original monotonic clock before
challenge reading, source verification, model verification/load or dispatch.
That exact clock is carried into the inner controller and worker. The maximum
is 7200 seconds including source checks, model work, output and cleanup. A
preregistered closure reserve is `min(budget/4, max(0.25, 0.02*budget))`; it is
never reused for more generation.

The inner controller hard-stops model work at the work deadline. The separate
outer process also bounds hung preprocessing, sealing, export or readback, not
just model generation. A hard-deadline failure may need a short bounded
TERM/KILL/reap tail outside the expired original clock; that is explicitly a
failed run and cannot receive an accepted outer completion. There is no resumed
model work or restarted time allowance during closure. Final watchdog metadata
uses an interval timer; its completion marker is published only after real
precommit readback. Verification rejects missing or failed completion markers.

A new Linux session/process group is owned per child. Descendant provenance is
observed from `/proc` ancestry and pinned to PID plus process-start ticks;
escaped observed descendants are signalled using pidfds. Only those identities
and the owned process group are targeted. Existing unrelated children are not
killed or reaped. An adopted child with unobserved provenance blocks the seal
instead of licensing an arbitrary PID kill. This assumes ordinary Linux scheduling and filesystem behavior, not a hostile
host, uninterruptible kernel I/O, or cryptographic process attestation. This is
operational ownership, not an adversarial OS sandbox; failure to establish closure is a real blocker.

## Evidence and export

The immutable run directory contains original challenge bytes, dynamic plan,
source/model/scheduler identities, actual backend/hardware metadata, version/
pointer/structure model-state guards, every operation start/end, controller
closure, raw-replay analysis, and clock-bound completion records. File metadata
is also guarded across public model verification/load/execution. These guards
are not a cryptographic GPU-state proof. Interrupted guards remain unknown.

`worker.log` preserves a bounded 1 MiB prefix of combined stdout/stderr, including
bootstrap/native failures before `terminal.json`; truncation is explicit. The
controller never dumps inherited environment variables. Logs are not scientific
evidence. Missing terminal metadata is labelled unclean, not assumed success.

The exited seal binds exact bytes; it is **integrity, not authentication or an
independent attestation**. Source changes, raw receipt tampering, reordered or
retried slots, source/clock mismatch and inconsistent exports are rejected.
The output uses the existing strict public submission builder and atomic,
exclusive publication. It contains exactly `attempt_1` and `attempt_2` per query.
Readback compares actual bytes against independent raw-token reconstruction.
Do not use an interrupted bundle without successful `verify` and its required
outer completion. Neither an existing `submission.json` nor a provider COMPLETE
status is enough.

## Validation and limits

```sh
python -m unittest tests.test_public_sft141_solver -v
python tools/repository_check.py --all
```

The new suite uses handcrafted cases and real synthetic subprocesses, not model
inference. Pure codec/inventory checks remain portable. Linux process/watchdog
cases carry the repository's explicit `requires_linux` eligibility annotation;
optional model dependencies are honestly skipped when absent.

The retained gold-free PUBLIC120 challenge (SHA-256
`8cade36130fdf1fa8fbab00cfcdfb5be8e74acbf04140f6fe18c5f502f0639be`) has 120
parents and 167 ordered queries. Input-only admission reproduces exactly three
policy-overflow queries in two parents: 164 admissible queries, 1312 schedulable
views, and 24 blocked views out of 1336. This is a cap-policy finding, not a
claim that the model intrinsically cannot handle those tasks. No labels were
read to alter this policy.

A no-model replay of the already-generated public diagnostic v2 reconstructs
120 strict views, 33 candidate grids, and identical uniform-vote selections for
all 15 queries in its 12 parents. This proves codec/selection equivalence only:
it is not a new runtime measurement, improved score, or full-denominator result.

The generic endpoint has **not** been GPU-run, RTX 3050 validated, shown to fit
all admissible PUBLIC120 work inside 7200 seconds, or proven competition
eligible. Prior small-panel evidence does not establish any of those claims.
No accuracy improvement over the already-public baseline is asserted.
