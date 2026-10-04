# Native multitask 008 Editor diagnosis and local export repair

Date: 2026-10-04 (Asia/Taipei)
Status: **worker compute complete; parent export failed; strict GPU gate false**.

The owner supplied root `結果.zip` and the parent traceback
`eight-view actual source verification input/answer differs`. No Kaggle status,
log, output or retrieval request was made. After analysis the original input
was moved losslessly to
`.irisx/native-multitask-008-diagnosis-20261004-001/owner-editor-original-result.zip`
because repository layout rejects inbound ZIPs at root. An immutable analysis
copy is also retained under
`.irisx/native-multitask-008-diagnosis-20261004-001/owner-editor-result.zip`.
Its 703,001 bytes have SHA-256
`57f8e5537eac37b4246c4e57af9411951e290c74d79c1178766b9bb0e4177fae`.
All 111 data-member sizes/digests and the closed manifest verify against exact
008 plan digest
`sha256:fb16dd865cac10623576120f57c6d8d138bc002765e50a271067eb3351e1a28c`.
The saved notebook/package, admission and receipt remain unchanged.

## Retained runtime observation

The archive binds the pinned published original Qwen3 model and source inventory
and four distinct BF16 L4s under Torch 2.8.0+cu128 / CUDA 12.8. Each worker's
physical GPU0 UUID matches `GPU-8d6ff7db-9b2a-f50e-0a10-06c4ffe412a4`.
The exact training token rows/masks, native schedule/gradient limits, finite
506-tensor BF16 topology, raw deep/sibling cache controls and post-reset calls
verify independently. All four baseline inventories and prefill vectors agree.
Hashes bind retained bytes; they are not cryptographic execution attestations.

| Attempt | Observed result | Completed optimizer steps | Training input / supervised tokens |
| --- | --- | ---: | ---: |
| `44f52bb0` | Two recorded tests; complete TTT and reset; exit 0 | 128 | 15,360 / 1,536 |
| `833966f4` | One recorded test; complete TTT and reset; exit 0 | 128 | 5,632 / 2,048 |
| `fault-first` | Expected injected fault after two updates; reset verified; exit 1 | 2 | 240 / 24 |
| `baseline-after-fault` | Fresh baseline/control/reset only; exit 0 | 0 | 0 / 0 |

The parent recount is 340 completed/reserved model forwards, 258 completed/
reserved updates, 259 reserved microsteps and twelve DFS batch invocations,
within every approved ceiling. Training consumes 21,232 input / 3,608 supervised
tokens; inference includes 28 controls, 48 generation forwards and six verifier
forwards. The normal workers record all three tests, sixteen returned sequences
per test and one distinct ranked grid per test, with one missing attempt slot
each. These are recorded candidates, not verified ARC answers. No truth file,
test answer, ARC correctness score, new generation or teacher call was used.

The parent failed after 1,315.381 seconds at
`verified-native-submission-export`. Its first export and finalizer both retained
the same error. There is no `submission.json`, `submission-audit.json` or
`native-evidence.json` in the returned archive. The deliberate fault worker is
separate from the unexpected parent export error.

## Cause and independent replay limits

The unchanged source uses `hash(base_key) % 1024**2` to seed each eight-view
verification dataset. Model workers start in fresh interpreters with
`PYTHONHASHSEED=0`. The notebook parent called the exporter in its already
running interpreter without pinning its startup hash. Setting an environment
variable after startup cannot change that interpreter's hash secret.

Local replay in a fresh seed-0 process reproduces **all 24** retained source-view,
query-token and answer-token rows, across the three real tests. The same replay
with startup seed 1 reproduces **zero** rows. The archive does not retain the
notebook parent's actual hash secret, so seed 1 is a controlled reproduction,
not a claim about its observed value. The code path, failed comparison and exact
seed-0 row matches support the parent/worker hash mismatch diagnosis.

Two additional reader issues are retained separately:

- PEFT's exported `state_dict` strips the `default`/`modules_to_save` wrappers
  and sorts tensor names. The initial reader compared that output to parameter
  names in insertion order and failed. Current verification maps only the three
  reviewed wrapper spellings, rejects collisions and still requires every exact
  shape, BF16 dtype, element count, finite flag and valid fingerprint. All 506
  actual entries / 528,564,224 elements match; no artifact is rewritten.
- Strict source DFS replay in local Torch **2.12.1+cpu** passes four batches and
  rejects eight. All twelve batches retain identical row IDs, token suffixes,
  callable paths and clock-read counts; beam scores differ by at most
  `2.3841676011215895e-07`. The archive was produced under Torch **2.8.0+cu128**.
  The numerical/build difference remains unresolved. Exact replay is still
  required; no tolerance, beam threshold, ranking or acceptance gate was relaxed.

The explicit `--diagnostic-only` archive-reader mode retains independently
verified hardware/training/control/ledger gates when strict candidate replay
fails, while `native_candidate_export_verified=false` and
`gpu_validation_gate=false` remain. `--require-gpu-gate` exits **2**, as expected.
The default strict reader still rejects the candidate replay. No submission
was recovered or complete original-method qualification claimed.

## Local repair and immutable proposal

`tools/nvarc_native_export.py` runs export in a **fresh CPU interpreter**, launched
with startup `PYTHONHASHSEED=0` and GPU visibility empty. It also checks the
immutable interpreter hash-randomization flag, so an in-process environment
change cannot masquerade as startup seed 0. It uses the same strict bridge,
source DFS replay, eight-view row checks and ranking, with zero model loads or
new model calls. Its bytes bind through a separate helper SHA-256 and the
outbound payload map, leaving the fixed eight scientific producer bindings
unchanged. The existing parent clock bounds the helper to at most 240 seconds.

Historical runs through 008 retain their exact render. New local proposals use
the isolated exporter. Immutable inert review
`nvarc-original-qwen3-native-multitask-009` is staged at
`.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-009/package-l4`.

| Proposal binding | SHA-256 |
| --- | --- |
| Plan | `02ac331440fdb44642225bc5f9977fb18f7af8c1ccab32ffb532f4a6292bb75d` |
| Notebook | `8641f929504f77182992d362669af532fbde4f134a5154237c8473d781fa9b32` |
| CPU export helper | `a092cb4d426dbef1672e4c2c2ee263cbdae1e7b00c32d820b39061c84f8668a5` |
| Offline QUICK_SAVE request | `f5c651cb73c5d7f216091df5cfa794cbb8a3a9d6438fcb0278e57ae5070bb44e` |

All seventeen existing non-plan payloads, original scientific producer bindings,
model/material/source identities, training/inference parameters and resource
ceilings match 008. The added helper and parent export transport are the only
implementation change. The proposal is `approved=false`, `review_only=true`,
without an admission, push reservation or credential/provider call. Frozen
review 007 and approved 008 both pass unchanged offline reconstruction.

## Validation and authority

Twenty-two focused tests passed with zero skips, including an actual seed-1
parent that reproduces the original eight-view error and then successfully
exports real tiny-CPU evidence through a fresh seed-0 child. That test substitutes
only fixture provenance/readout and preserves strict source DFS, eight-view
token verification and ranking; it proves process transport, not Qwen GPU
quality or target-runtime parity. Topology mutations/collisions and diagnostic
gate failures also remain covered.

The first focused run retained one failure: adding the CPU helper to the bridge's
fixed scientific producer set was correctly rejected. The helper now has its
own payload/SHA binding and the scientific producer set is unchanged. Its
failed log and corrected passing log are retained.

The full repository command ran three helper validators and 508 unit tests,
zero skips. Its sole failure was the root input ZIP layout: 507 tests passed,
and `test_active_repository_is_valid` rejected `結果.zip`. The original ZIP was
then moved into ignored storage with its digest verified before and after,
and all fifteen repository-check tests passed. No implementation/expectation
changed to bypass layout; the original full-command failure is retained, and
the unrelated 507 tests were not repeated. The initial numerical-detail file
collided with its command-summary filename; its original stdout/summary and
probe source are retained, and the same read-only probe was rerun with a
distinct detail filename, reproducing the same summary digest and decisions.
Final repository invariants and whitespace checks pass after archival. The
unchanged original `--all` failure remains recorded as a layout-only failure.

The digest-bound archive manifest, worker proof, seed-0/seed-1 row transcripts,
all twelve numerical replay comparisons, exact command/log digests and inert
proposal bindings are retained in
[`configs/native-multitask-008-editor-diagnosis.json`](configs/native-multitask-008-editor-diagnosis.json).

Decision 0057's sole save is consumed. This owner ZIP and local repair grant no
additional QUICK_SAVE, model execution, query, retrieval, Dataset mutation,
scoring or promotion. The frozen review must use a distinct admitted identity
if the owner separately authorizes a later save. Quota information remains
unavailable; no reservation or resource sufficiency is invented.
