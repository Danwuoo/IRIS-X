# Original native TTT 007 Editor timeout diagnosis

Authority: [Decision 0055](../../docs/decisions/0055-save-native-ttt-for-owner-editor.md).
Status: digest-bound owner-Editor timeout; 96-step verified prefix, no full epoch.
Date: 2026-10-03 (Asia/Taipei).

The owner supplies `結果.zip` in the main checkout root and reports the
`TimeoutExpired` traceback. Local verification matches the exact approved 007
plan, every payload binding, all **32 manifest members**, original published
checkpoint, all 41 source/metadata bindings and four distinct BF16 L4 UUIDs.
The ZIP is 596,037 bytes, with 7,743,796 uncompressed bytes including manifest;
SHA-256 `f238b7614d9f7838fc690ddc2e7aae1011e7a3827e7e9837be010bcc4e8e630c`.
An exact copy and independent proof are retained under ignored
`.irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-007/owner-editor-report-20261003-001/`.
The original root input is retained as `owner-root-結果.zip` in that same ignored
directory, with identical bytes, after the repository validator correctly rejects
the unexpected top-level binary. The initial validator log is preserved; its
Windows console encoding also fails while printing the Chinese filename.
No provider query or retrieval is used.

## Completed and interrupted work

| Observation | Verified value |
| --- | --- |
| Original prepared views | 128, exact raw inputs/labels; context 8,192 |
| Completed model forwards | 97, with finite scalar losses |
| Completed Trainer forward/backward steps | 96 |
| Completed optimizer steps | 96 of 128, all 506 gradients finite per step |
| Completed forward input/supervised tokens | 724,008 / 360,840 |
| Interrupted step | 97th Trainer step reserved and forward returned; no 97th optimizer reservation |
| Optimizer rates | Exact same-platform source cosine oracle through index 95 |
| Model generations / teacher calls / paid USD | 0 / 0 / 0 |
| Full epoch / terminal moments / trained fingerprint / adapter reset | Unverified |

The 97-forward token count includes the interrupted 97th training step; it is
not a claim that all those tokens completed backward/update. The ledger retains
completed and reserved work separately. No `training-result.json`,
`optimizer-state.json`, `trained-inventory.json` or `reset-inventory.json` exists.
There is no exported checkpoint or ARC score. The parent kills and reaps the
worker process group at the wait deadline, then successfully packages diagnostics.

## Time limit mechanism

The exact saved parent computes:

```python
remaining = min(child_limit, parent_limit - 120 - elapsed_parent_setup)
```

Parent/child limits are 1,500/1,200 seconds. The observed `remaining` is
979.0179684269999 seconds, so elapsed parent setup is derived as
**400.9820315730001 seconds**. This is the combined pre-worker interval; the
archive does not time individual source/model verification stages. The parent
terminal wall time is 1,380.2661273899998 seconds, consistent with its 120-second
archive reserve.

The worker progress stream advances regularly through step 96 at rounded
training elapsed 11:06, with a recent smoothed rate of 6.62 seconds per step.
The remaining 32 optimizer steps suggest about 211.84 additional training
seconds at that rate, plus unmeasured final moment/fingerprint/reset work.
That linear estimate is not a completion guarantee. No completed worker timing,
CUDA peak or final optimizer tensor observation can be recovered after the kill.
The terminal cause is the saved parent's deadline; no separate worker Python
exception is retained. Keep warnings and numerical observations distinct from
this terminal timeout.

## Local repair proposal

The [inert 008 proposal](native-ttt-008-timeout-proposal.md) extends only the
finite parent/child envelope to **3,600/3,000 seconds**. It retains the exact
128-view/128-step workload, model/source/optimizer/schedule/reset behavior,
hardware, offline/private/USD 0 boundaries and `結果.zip` packaging. All native
worker and material payloads remain byte-identical. No reduced workload or
scientific success threshold change follows. The proposal fails closed before
runtime work and has no provider operation; new owner direction is required
before a separately approved QUICK_SAVE.

Local reader review also identifies a complete-result compatibility defect:
the real hardware helper emits `memory_bytes`, while the existing final timing
check expected `total_memory_bytes` from an artificial test fixture. The reader
now accepts the actual field, preserves the legacy fixture spelling, and rejects
conflicting aliases. This does not alter saved 007 bytes, its timeout proof,
scientific memory bounds or the absence of a full result.

The small [diagnostic evidence record](configs/native-ttt-007-editor-diagnosis.json)
binds the source ZIP, retained proof, observed work, exact receipt and unchanged
save journal. The owner report grants no new external save, run, query,
retrieval, Dataset mutation, scoring or promotion.

## Local validation limitation

All nine focused Editor/proposal/native-reader tests pass in 10.534 seconds,
including actual-field GPU capacity verification and the emitted-parent guards.
Repository layout invariants and diff checks pass after retaining the input
under `.irisx`. Full repository validation runs all 403 tests twice, with four
optional skips each, but both runs fail in the same pre-existing
`StructuredTeacherTests.test_paired_descriptions_four_dependent_saved_stages_and_fail_closed_replay`:
Windows denies `os.replace` in `arc_nvarc_runtime.atomic_json` while replacing
`good/mix.json` (WinError 5). The six-test class alone passes in 0.244 seconds.
The two full-run logs and focused replay are retained; the source of the file
access denial remains unresolved. No full-validation PASS is claimed. This
does not change the independently verified 007 archive or authorize an external
008 save. The unrelated SDG runtime and frozen notebook bytes remain untouched.
