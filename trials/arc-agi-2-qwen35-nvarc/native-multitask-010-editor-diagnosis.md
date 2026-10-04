# Native multitask 010 Editor diagnosis

Date: 2026-10-05 (Asia/Taipei)
Status: **owner-Editor flow/export complete; strict local DFS replay unverified**.

The owner reports successful notebook execution and supplies root `結果.zip`.
Its 751,137 bytes have SHA-256
`cba8d464b1b0cd92ba9f47f00993c79367188fefdde5725f477b32b0606829c0`.
All **118 data members**, plus the closed manifest, match their exact sizes and
hashes and saved 010 plan digest
`sha256:d0e0e2084929a411e4cfa9464cbfe8a20fc73b91466aa7e4f8f4f1a905d0ab81`.
Every planned producer/source/helper payload and the existing model/source
inventory match the immutable submitted package. No Kaggle status, log,
output, retrieval, save or Dataset request was made for this diagnosis.

## Execution and export observation

The archive records four distinct BF16 L4s under Torch 2.8.0+cu128 / CUDA 12.8.
All four sequential fresh children bind to physical GPU0 UUID
`GPU-a866177d-379e-b0d0-5075-12b28af92f15`, with the pinned published original
Qwen3 model/material digest
`sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
Independent hardware, training, event-chain, budget, finite tensor topology,
cache-control and reset recount pass. All four baseline inventories and
prefill vectors agree; all four resets and their seventh control call verify.

| Attempt | Completed optimizer steps | Training input / supervised tokens | Outcome |
| --- | ---: | ---: | --- |
| `44f52bb0` | 128 | 15,360 / 1,536 | Two tests; complete epoch and reset; exit 0 |
| `833966f4` | 128 | 5,632 / 2,048 | One test; complete epoch and reset; exit 0 |
| `fault-first` | 2 | 240 / 24 | Expected injected fault; reset verified; exit 1 |
| `baseline-after-fault` | 0 | 0 / 0 | Identical fresh baseline and reset; exit 0 |

Parent wall time is **632.992 seconds**. All limits hold: 340 completed/reserved
model forwards (258 training, 28 controls, 48 generation and 6 verification),
258 completed/reserved optimizer steps, 259 reserved microsteps and twelve
generation batches. Training consumes 21,232 input / 3,608 supervised tokens.

The parent reached phase `terminal`, retained all receipt bindings and has no
parent error or export failure. Its `outcome=failed` is the renderer's expected
label when the deliberate `fault-first` receipt is failed. That label does not
identify a new notebook fault. The complete isolation observation remains
separate from ARC correctness or method promotion.

The bound fresh CPU exporter records startup `PYTHONHASHSEED=0`, immutable
hash-randomization flag 0, no visible GPU and zero new model calls. Its stdout
reports `export_completed=true`; stderr is empty. All three base-key hashes
match an independent local seed-0 interpreter. **All 24 actual verifier
source/query/answer row bindings match**. The old 008 eight-view export failure
does not recur in this run.

The archive now contains `native-evidence.json`, `submission-audit.json` and
`submission.json`. Independent partial reconstruction checks the evidence,
token parsing/inverse views, all verifier rows, source ranking, export mapping,
filler policy and audit digests against those exact retained files.

| Test | Retained distinct model candidate |
| --- | --- |
| `44f52bb0`, test 0 | `[[7]]` |
| `44f52bb0`, test 1 | `[[1]]` |
| `833966f4`, test 0 | `[[5],[4],[6],[2],[7]]` |

Each test completed all sixteen source views/four batches, processed sixteen
returned sequences and retained one distinct candidate with zero parse rejects.
The six output slots contain **three model-supplied attempts and three
duplicate-first fillers**. Fillers are not additional model predictions.
No expected test answer was opened and no ARC exact-match or official score
was computed.

- Submission SHA-256: `80312c1d0b0b5532b3b6581b7f479477a6dad365c0485ba35ed0b72ec60b459e`.
- Audit SHA-256: `0efc467c67082a6e16acd9a0b7d3fc260d55c46840a606abf2b289e75c893706`.

## Independent replay limit

The default strict local reader still rejects source DFS score replay under
Torch **2.12.1+cpu**, while the producer/exporter ran with **2.8.0+cu128**.
Across all twelve batches, row IDs, token suffixes, forward paths and clock-read
counts are identical; four exact replay comparisons pass and eight fail.
The maximum beam-score absolute difference is `2.3841676011215895e-07`.
The available alternate local runtime also has Torch 2.12.1+cpu. No new runtime
or dependency was acquired, and no numerical tolerance or threshold changed.

The diagnostic archive reader retains all verified worker/isolation/cost gates
and exported-artifact presence, with `native_candidate_export_verified=false`
and `gpu_validation_gate=false`; `--require-gpu-gate` exits 2. Its early return
also leaves its combined parent-finalization gate false. The separate partial
audit checks the actual terminal receipt record and expected injected-fault
label independently.

For the partial row/ranking/export audit, only `verify_test`'s explicit no-DFS
branch is used. The separately recorded strict replay remains failed. Partial
audit success does **not** replace that replay or qualify the GPU gate. An
initial local audit-harness assumption incorrectly expected the checkpoint to
include post-reset events; the corrected harness checks its exact committed
prefix/head. Both harness versions and command logs are retained. No returned
artifact, event, producer program or qualification check was rewritten.

This confirms the reviewed bounded flow and export repair's recorded execution.
Full strict portable replay, original-method parity, ARC correctness, full SFT
and promotion remain unestablished. Quota/session admission facts stay frozen
as unavailable; the returned hardware observation is separate evidence.

## Retention and validation

The original root ZIP was moved losslessly to
`.irisx/native-multitask-010-diagnosis-20261005-001/owner-editor-original-result.zip`
for the repository input boundary. The immutable analysis copy is
`owner-editor-result.zip` in the same directory; both retain the original hash.
Extracted artifacts, strict/diagnostic proofs, partial audit and full numerical
probe remain under that ignored diagnostic directory.

Machine-readable evidence is
[`native-multitask-010-editor-diagnosis.json`](configs/native-multitask-010-editor-diagnosis.json).
`python tools/repository_check.py --all` passed: three validator helper tests
and 511 unit tests, with no skips. Local CPU validation used OMP/MKL thread
limits of 2 with startup hash seed 0 and offline provider flags. These limits
apply to local validation only; no runtime package or acceptance gate changed.
Strict archive replay exit 1 and diagnostic-gate exit 2 remain recorded
qualification failures, separate from passing repository tests.

Decision 0058's save remains consumed. This result authorizes no additional
save, agent execution, provider query/retrieval, Dataset mutation, scoring,
teacher invocation or promotion. The saved package, admission, receipt and
all predecessor identities remain unchanged.
