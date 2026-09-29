# Compact ABC owner-Editor paired task-TTT comparison 005

Decision 0048 authorizes one distinct private QUICK_SAVE of
`nvarc-compact-abc-editor-005`. Its exact plan is
`configs/compact-abc-editor-005.json`, canonical digest
`sha256:e99993fda56f204c2dab8ac64882d94713004c8c41d6b4e628ce7ac3f88066a2`.

The [004 Editor diagnosis](compact-abc-004-editor-diagnosis.md) shows that
the two-path model beam changed candidate pools but did not recover a new
correct grid on three repeatedly examined public development parents. The
005 notebook fixes that beam and compares a two-by-two checkpoint/TTT
matrix: A compact base, AT base plus one task-local LoRA step, B retained
eight-step SFT pilot, and C that SFT export plus the same task-local step.
All use the same public demonstrations, visible test inputs, two views,
two generation calls per task, candidate and ranking budgets. The notebook
has no evaluator truth, score or answer-derived rule.

The owner will select L4 x4, attach
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`, run the saved notebook
in Editor and return `/kaggle/working/結果.zip`. The notebook checks four
distinct BF16 L4 UUIDs but runs the four arms sequentially on one selected
GPU, with the existing three Datasets, Internet off, USD 0 and a
1,800-second session. The bound totals are at most 24 generation calls,
48 returned sequences, 48 verifications, six TTT steps and 1,536 TTT
training tokens.

## Sole save receipt

The one private `QUICK_SAVE` was accepted on 2026-09-29 as version 1:
[nvarc-compact-abc-editor-005](https://www.kaggle.com/code/danielwuu/nvarc-compact-abc-editor-005)
(kernel ID `136357374`). The agent sent exactly one `SaveKernel` request and
did not start a session or query runtime. The owner will run it in Editor
and return `結果.zip`. The save authority is consumed.

The exact plan digest is
`sha256:e99993fda56f204c2dab8ac64882d94713004c8c41d6b4e628ce7ac3f88066a2`.
The staged notebook SHA-256 is
`d999dadd7ad134a3fa06ae17127a1d2735d0e72431e0d815c90fcd8b7e655ca4`;
runtime wheel SHA-256 is
`4bb7f4fb32f1efbeaf2b5be0dbac494703d1ab0a22d125f73a9bb676b9ae2bd2`;
metadata SHA-256 is
`20f903e6c00e31e06e1b53a9423c0da94a56737f79559cd97b7b7d1561afbca1`.
The local preflight SHA-256 is
`1d595d6fa5ff5a315d59d0852bec4a4773684b71713f43e3d705bcc787520903`,
the exact SDK request SHA-256 is
`2443c46c34b2f48869cba71f66903817832c83fccf626f50673588949cafa91a`,
and the provider receipt SHA-256 is
`f9c8e652019a7766caadf8de516f3cc36756215f64159f40efcf8cd9d8741784`.
The ignored local ledger records the sole reservation, send and receipt at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0048-save-ledger.json`.

Offline verification included exact material and embedded-payload preflight,
a tiny Qwen base-start adapter and beam replay, and
`python tools/repository_check.py --all` (290 tests, four skipped, pass).
No further save, agent execution, status/log/output query, retrieval,
Dataset change or automatic retry is authorized.

## Owner-Editor result

The owner returned the complete 005 Editor ZIP. [The digest-bound local
diagnosis](compact-abc-005-editor-diagnosis.md) verifies all four arms on the
approved mount and four distinct BF16 L4s. Isolated scoring of the same three
public development parents found A and AT each at 1/3, B and C each at 0/3
for pass@1, pass@2 and candidate-pool coverage. TTT produced finite adapter
updates but no correct new candidate. The conditional request for another
repair and QUICK_SAVE did not yield a concrete software fault or supported
parameter change, so no new save was sent.
