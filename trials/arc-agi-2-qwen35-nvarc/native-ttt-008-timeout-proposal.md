# Inert native TTT 008 timeout repair proposal

Status: immutable inert proposal retained; owner approved a separate Decision 0056 envelope.

The owner subsequently directs 「對，提交 quick save」. The separate
[approved 008 package](native-ttt-008-editor.md) now follows
[Decision 0056](../../docs/decisions/0056-save-native-ttt-timeout-repair-for-owner-editor.md).
The original proposal bytes and false approval flag remain unchanged; the
description below records its original inert review state.
Date: 2026-10-03 (Asia/Taipei).

The [007 diagnosis](native-ttt-007-editor-diagnosis.md) verifies a 96-of-128-step
prefix stopped by its 979-second worker deadline. The proposed distinct 008
keeps every scientific workload and material field, while increasing only the
parent/child time limits from **1,500/1,200** to **3,600/3,000 seconds**. The
parent continues to reserve 120 seconds for ZIP finalization and shortens the
child if setup consumes too much of the finite envelope.

With the observed 400.982-second parent setup interval, replay of the actual
emitted timeout expression gives 3,000 worker seconds. It does not authorize
more than the original 128 views/128 optimizer steps, zero generations,
zero teachers, no checkpoint export and no ARC score. Four distinct BF16 L4s,
one sequential rank-zero worker, exact original materials, private/offline
transport, USD 0 and final `結果.zip` remain unchanged.
The run would restart from the same published checkpoint for all 128 steps.
007 retains diagnostics, not a resumable model/optimizer checkpoint; this is
not a continuation of its transient 96-step trained state.

The closed ignored proposal is
`.irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-008/proposal-001/`.
Plan digest:
`sha256:ccc7640aeecf42bacaaf671b9bc384d9c47bc470dd1b0986452c5e6e8449dc66`.
Its `approved` flag is false and owner authority explicitly says UNAPPROVED.
An emitted-parent guard stops before dependency, hardware or model work; the
unchanged worker also requires an accepted approval envelope. The staging tool
contains no provider operations, and the existing 007 save transport rejects
the 008 identity. There is no submission journal or save receipt.

Native worker, helper, source, material, budget and scheduler payloads are
byte-identical to 007. Only plan identity/authority/time fields and the inert
parent approval barrier differ. Offline tests replay the actual parent timeout
expression with 007's measured setup interval and verify that the unapproved
notebook stops before runtime work while retaining a zero-work diagnostic ZIP.
The small [offline review](configs/native-ttt-008-timeout-proposal-review.json)
binds the exact local package and confirms that 007's receipt, saved package
and reservation journal are unchanged.

[Decision 0055](../../docs/decisions/0055-save-native-ttt-for-owner-editor.md)
consumed exactly one 007 QUICK_SAVE and excludes automatic retry. This local
proposal grants no new save or execution. If the owner directs a replacement,
retain these proposal bytes separately and bind one exact new approved private
QUICK_SAVE envelope before any provider mutation. Owner Editor execution and
agent stop-at-receipt remain the proposed transport choice.
