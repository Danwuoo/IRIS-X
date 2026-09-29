# Decision 0048: Save one paired compact base/SFT task-TTT comparison

Status: Accepted
Date: 2026-09-29

The owner returned the 004 Editor ZIP and directs continued correction and
one new QUICK_SAVE. The [004 diagnosis](../../trials/arc-agi-2-qwen35-nvarc/compact-abc-004-editor-diagnosis.md)
binds a complete three-arm run. Its two-path model beam generated new
candidate grids but did not improve exact-match coverage on the three
repeated public development parents. A compact base attained 1/3, while
the retained eight-step SFT pilot export and its one-step task TTT attained
0/3. This motivates testing the same task-local adaptation on the compact
base as a paired checkpoint-by-TTT comparison, without changing the beam.

Authorize one distinct private `nvarc-compact-abc-editor-005` owner-Editor
QUICK_SAVE. The exact approved plan is
`trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-005.json`, canonical
digest `sha256:e99993fda56f204c2dab8ac64882d94713004c8c41d6b4e628ce7ac3f88066a2`.
It has four sequential arms: A compact base without TTT; AT that same base
with one task-local LoRA step; B the retained eight-step SFT pilot export
without TTT; C the same export with one task-local LoRA step. AT and C use
the same rank 2, alpha 4, 5e-5 learning rate, one augmentation, seed and
fresh adapter reset for each task. All four arms use the exact 004 public
grammar and two-path model beam, three selected public parents, two source
views, two generation calls per task, two candidates per call, verifier and
ranking. No new SFT, teacher, checkpoint, model, Dataset, prompt, public
rule or answer-derived selection enters the notebook.

The whole notebook may reserve at most 24 generation calls, 48 returned
sequences, 3,072 generation forwards, 48 candidate verifications, 384
verification forwards, six TTT optimizer steps and 1,536 training tokens.
The official mount
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`, four distinct BF16 L4
hardware gate, one sequential worker, existing three private Datasets,
Internet-disabled, USD 0 and 1,800-second session with 60-second terminal
reserve remain. The result ZIP contains predictions and truth-free task
adaptation diagnostics, never evaluator answers.

These repeatedly examined tasks are development data. A later owner-returned
ZIP may be scored only in a separate local evaluator; this decision changes
no accuracy or method-promotion threshold.

After focused tests, exact-package preflight and the full repository check,
reserve and send at most one private `KernelExecutionType.QUICK_SAVE` request.
Stop at its receipt, accepted, rejected or uncertain. The owner will start
the saved notebook in Editor and return `結果.zip`. No agent execution,
status/log/output query, retrieval, monitoring, Dataset mutation, automatic
retry, second save, paid work, hidden/locked scoring or competition
submission is authorized. Status is
`trials/arc-agi-2-qwen35-nvarc/compact-abc-editor-005.md`.

The sole private QUICK_SAVE was accepted as version 1, kernel ID `136357374`,
after offline preflight and the full repository check passed. Exact package,
request and receipt digests are retained on the status page. The one save is
consumed; the agent started no session and did not query runtime state.
