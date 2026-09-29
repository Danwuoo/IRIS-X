# Compact ABC owner-Editor sensitivity 003

Decision 0046 authorizes one private QUICK_SAVE of
`nvarc-compact-abc-editor-003`. The exact approved plan is
`configs/compact-abc-editor-003.json`, digest
`sha256:3ae9ebf9786e775be7c0d96981982c884257c0fbd562444a8278af1fb49f4734`.
The owner will select L4 x4, attach
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`, start the saved
notebook in Editor, and return its `/kaggle/working/結果.zip`.

The study holds the compact base, eight-step SFT export, selected public
parents, grammar completion, two views, candidate and ranking budgets fixed.
It changes only task-local TTT effort from the C0 one-step/5e-5 control:
C2 takes two steps at 5e-5 and CH takes one step at 1e-4. A and B remain
no-TTT controls. All five arms run sequentially on one selected L4 after
four distinct BF16 L4s are verified. The plan binds 30 generation calls,
60 returned sequences, 60 candidate verifications, 12 TTT steps and 3,072
TTT training tokens as notebook-wide maxima. The fixed rank 2, alpha 4 and
one augmentation avoid changing multiple adaptation factors together.

The [002 isolated public-development score](compact-abc-002-public-dev-score.md)
motivates the comparison. These are repeatedly examined tuning tasks, not
fresh generalization tests. The notebook and its ZIP contain no evaluator
answers, scores or answer-derived selection. Any correctness comparison after
the owner returns the result belongs to a separate local evaluator.

## Sole save receipt

The one private `QUICK_SAVE` was accepted on 2026-09-29 as version 1:
[nvarc-compact-abc-editor-003](https://www.kaggle.com/code/danielwuu/nvarc-compact-abc-editor-003)
(kernel ID `136338160`). The agent sent exactly one `SaveKernel` request and did
not start a session. The owner will run the saved notebook in Editor; runtime
state is unqueried. The save authority is consumed.

The exact plan digest is
`sha256:3ae9ebf9786e775be7c0d96981982c884257c0fbd562444a8278af1fb49f4734`.
The locally staged notebook SHA-256 is
`32f8471db15d2dfa1569e927731d802f74a4f0d4d4f2dbe2f339bf84e73b9bcb`;
runtime wheel SHA-256 is
`1a2158c1f2ed88afc161e6553b4485acea6a21212d8536a0ae6f950c815e7d5f`;
metadata SHA-256 is
`1400ca84948be2273485caa0c902a7da101ac32322acf8eafd15658e39f7ca00`.
The local preflight SHA-256 is
`486285643344fa774f70316a39ad0013339792d4fc04020e4a4771bb62a503e3`,
the exact SDK request SHA-256 is
`58750e9ac085185d8dd546a77a38cc09ff2b2f22b76d367a93e0c1c6065045a9`,
and the provider receipt SHA-256 is
`0b89178bf81ca808f790bab3f0f1d6528d974f73700be95637738edf271d17c8`.
The ignored local ledger records the sole reservation, send and receipt at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0046-save-ledger.json`.

Offline verification included the exact material preflight, a two-step tiny
Qwen adapter and generation replay, and `python tools/repository_check.py --all`
(284 tests, four skipped, pass). No further save, agent execution, status or
output request, retrieval, Dataset change or automatic retry is authorized.

The owner later returned the Editor `結果.zip`. Its complete, digest-bound
runtime and separate public development score are retained in the
[003 diagnosis](compact-abc-003-editor-diagnosis.md). The result does not
reopen this consumed save identity.
