# Decision 0046: Save one bounded compact ABC adaptation study

Status: Accepted
Date: 2026-09-29

The owner directs continued NVARC tuning after independent acceptance of the
002 engineering run. The frozen 002 result was scored locally against exactly
three public `training2` development parents with an isolated evaluator:
A reached pass@1/pass@2/oracle coverage 1/3; B and C each reached 0/3.
Every B/C candidate pool missed the answer. These repeatedly examined tasks
are tuning data, not fresh generalization evidence. This small observation
does not settle the value of full SFT or TTT. No source label, score or
answer-derived metadata enters the next notebook or its result ZIP.

The distinct owner-Editor identity is `nvarc-compact-abc-editor-003`. Its exact
approved plan is
`trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-003.json`, canonical
digest `sha256:3ae9ebf9786e775be7c0d96981982c884257c0fbd562444a8278af1fb49f4734`.
The five sequential arms on one selected L4 are A (compact base), B (the
retained eight-step SFT pilot), C0 (SFT plus one TTT step, learning rate
5e-5), C2 (two steps, 5e-5), and CH (one step, 1e-4). All three C arms use
rank 2, alpha 4, the same one source augmentation, seed and fresh adapter
reset per task. All five use the same three public tuning parents, two views,
two generation calls per task, public-derived shape/palette grammar, two
sequences per call and unchanged verification/ranking. No new SFT, teacher,
search-diversity treatment, model, Dataset or answer-guided rule is added.
The current legal-token generator remains narrow greedy completion; this
study isolates TTT steps and learning rate first.

Across all arms, reserve at most 30 generation calls, 60 returned sequences,
3,840 generation forwards, 60 candidate verifications and 480 verification
forwards. Across C0/C2/CH, reserve at most 12 TTT optimizer steps and 3,072
training tokens. Record per-step losses, finite gradient-group coverage,
nonzero adapter deltas and per-task reset. The exact official competition
mount `/kaggle/input/competitions/arc-prize-2026-arc-agi-2`, four distinct
BF16 L4 hardware gate, existing three private Datasets, Internet-disabled,
USD 0 and 1,800-second session with 60-second terminal reserve remain.
Four allocated GPUs do not imply four running workers; this notebook runs
one sequential worker on one selected GPU.

Success for this run means complete bounded, truth-free evidence for the five
arms. Failures retain partial ledgers and terminal artifacts where Python can
finalize. The notebook never selects an arm by oracle correctness. A later
owner-returned ZIP may be scored only in the separate local public-development
evaluator. No accuracy or promotion threshold is changed by this decision.

After focused and strict tests, exact-package preflight and the full repository
check, authorize exactly one private `KernelExecutionType.QUICK_SAVE`. Atomically
reserve the sole send before transport. Rejection or uncertainty consumes it.
Stop at the save receipt. The owner starts the notebook in Editor and returns
`結果.zip`. No agent execution, status/log/output query, retrieval, Dataset
mutation, monitoring, automatic retry, second save, paid work, hidden/locked
truth scoring or competition submission is authorized. Status is
`trials/arc-agi-2-qwen35-nvarc/compact-abc-editor-003.md`.

The sole `QUICK_SAVE` was accepted as private version 1, kernel ID
`136338160`, after offline preflight and the full repository check passed.
Its exact request, receipt and package digests are retained on the status
page. The one save is consumed; no agent session was started and runtime
remains unqueried pending the owner's Editor report.
