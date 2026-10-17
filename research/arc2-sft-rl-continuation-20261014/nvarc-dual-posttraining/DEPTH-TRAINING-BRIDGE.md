# CPU-only depth post-training bridge

Status: local, unpublished mechanism integration, 2026-10-17. No production
admission, official-weight training, GPU execution, checkpoint release,
equal-compute comparison, or capability improvement is established.

## Contract and numerical reuse

`tools/nvarc_capacity_20261017/training.py` provides `DepthFixtureEngine` for
explicit CPU fixtures containing at most 1,000,000 total parameters after
expansion. It has no production loader or PEFT checkpoint/export route. The
existing `prototype.py`, `Engine`, `CompactEngine`, and experiment sources
remain unchanged; existing NVARC notebooks are untouched.

Admission requires a fresh native compact 16-token, untied, dropout-zero,
full-attention Qwen3 model and matching live identity-depth receipt. It checks
actual tensor geometry, unique parameter storage, finite values, layout and
counts before changing training flags. Added attention output and FFN down
projections must still be zero. This is a fresh-training bridge, not a resume
converter or proof that an arbitrary receipt authenticates model provenance.

The exact trainable inventory comprises every parameter of each added full
block plus the separate full input embedding and output head. Trainables are
FP32; inherited parameters retain their original uniform FP32 or BF16 dtype.
BF16 runs use CPU BF16 autocast. Frozen tensor ownership and values, module and
buffer identities, configuration, attention settings, tokenizer, and optimizer
ownership are checked. Original tensors cannot be silently included in AdamW.

SFT and actual upstream AF3/DDIS replay use the existing `Engine` methods.
Sampling uses `CompactEngine`'s complete 16-way temperature-one distribution,
private generator, literal EOS15, and existing context/generation bounds.
Existing exact-hybrid training and demonstration-only TTT/generated development
selection run against synthetic task fixtures. The separate mixed-reward AF3
test uses a declared toy one-token verifier, not an ARC exact-grid success.
The BF16 initial-parity test compares against a dtype-matched unexpanded control.

## Failure and restoration semantics

Nonfinite gradients, model updates, or optimizer tensors fail closed. Failed
optimizer mutation restores parameter bytes when possible and permanently
poisons the engine. Optimizer and RNG state are never claimed to be rolled
back or resumable. Physical optimizer attempts remain charged; rolled-back
updates are not counted as committed. Rollback failures are explicit fatal
errors, never successful recovery reports.

Snapshots are detached named trainable tensors. Restore validates and clones
the complete finite CPU FP32 input before touching parameters or gradients.
Invalid inputs leave both intact. A partial restore failure triggers byte
rollback and poisoning; successful restore clears gradients without resetting
physical counters or the sampling RNG. Callers must discard any old optimizer
when restoring parameters for a new adaptation phase. The unchanged experiment
module's internal restoration still uses its existing `restore_state` contract;
the new fault-atomic wrapper does not silently replace that frozen code path.

Expired SFT, generation, and AF3 work is rejected before model work. An update
that finishes before a post-step deadline exception remains physically charged
and committed. Higher-level accepted-step counts can therefore differ from the
engine's physical committed-update count on this late-return boundary; this is
not an optimizer rollback or evidence that requested work completed.

## Verification

Using `../ml-venv/bin/python` from the repository root without resolving its
symlink, with `PYTHONHASHSEED=0`, `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, and repository-backed TMPDIR:

- Focused depth bridge suite: 25 tests passed normally and under `-O`.
- Optional-dependency path: `python -S` imports the module and skips all 25
  tests cleanly when ML packages are absent. This is a skip, not a numerical pass.
- Capacity prototype, depth bridge, compact engine, and compact experiment
  regression suites: 70 tests passed together.

Tests cover SFT, real upstream DDIS invocation, zero-signal behavior, the full
exact-hybrid/generated-dev/demo-TTT lifecycle, finite checks, invalid geometry
and shared storage, mutable ownership/configuration, optimizer rollback,
restore prevalidation and partial failure, physical counters, deadline gates,
and the retained one-million-parameter admission cap. The repository aggregate
is separate from these focused results and is not represented here as passed.

No source publication or external/provider action was performed by this bridge
review. These CPU fixtures establish mechanism integration only. They do not
validate official 2B/4B training, GPU numerics, memory/time feasibility, benchmark
accuracy, inherited-data cleanliness, or a capacity gain.

Owner final validation: the complete Linux `--public` lane passed 2,019 tests,
with 1,754 passes and 265 explicit/optional skips; all 70 focused ML regressions
passed again. The reviewer's earlier strict aggregate lost its execution session
and ended in a partial log without a terminal summary. It remains interrupted
and unverified, not a pass or a substitute for missing historical evidence.

A separate BF16 two-step gradient probe used SGD with zero weight decay to
exclude decay-only parameter motion: the new block's zero attention output
projection changed after step one, its inner Q projection did not; the inner Q
projection changed after step two. This confirms the expected identity-init
gradient path in that tiny fixture, not useful learned capacity or model quality.
