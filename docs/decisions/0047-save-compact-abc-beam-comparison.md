# Decision 0047: Save one bounded compact ABC beam comparison

Status: Accepted
Date: 2026-09-29

The owner returned the 003 Editor ZIP and directs continued correction and
one new QUICK_SAVE. The [003 diagnosis](../../trials/arc-agi-2-qwen35-nvarc/compact-abc-003-editor-diagnosis.md)
binds a complete five-arm run. On its three repeated public development
parents, A retained 1/3 exact candidate coverage; B, C0, C2 and CH each
retained 0/3. TTT step-count and learning-rate changes did not recover an
answer. The miss is in candidate generation before ranking, so this distinct
run changes only the legal model candidate search.

Authorize one private `nvarc-compact-abc-editor-004` owner-Editor QUICK_SAVE.
The exact approved plan is
`trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-004.json`, canonical
digest `sha256:ab9a2427ae41a274f9db5f423e7fb19db4ba3868b2beaa3e7f9d647c59561ebf`.
A uses the retained compact base, B the eight-step SFT pilot export, and C
the same export plus one task-local LoRA step at 5e-5. The same three public
development parents, two source-Qwen views, two generation calls per task,
two returned candidates per call, shape/palette grammar, verifier and
ranking remain. Instead of choosing the second-best color only at the first
cell, the decoder keeps the two lowest cumulative model-NLL legal prefixes
at every output position. It does not renormalize probabilities over legal
colors. This is a bounded, deterministic decoder comparison, with no truth
lookup, output-derived rule, new SFT, new model or Dataset mutation.

The whole notebook may reserve at most 18 generation calls, 36 returned
sequences, 2,304 generation forwards, 36 candidate verifications, 288
verification forwards, three TTT optimizer steps and 768 training tokens.
The exact official mount
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`, four distinct BF16 L4
hardware gate, one sequential model worker, existing three private Datasets,
Internet-disabled, USD 0 and 1,800-second session with 60-second terminal
reserve remain. Four allocated GPUs are checked; one performs the sequential
comparison. The result ZIP contains predictions and truth-free diagnostics.

The same three visible tasks are tuning data, not a fresh holdout. The local
scorer remains isolated and does not enter the notebook, plan or ZIP. No
accuracy or method-promotion threshold changes.

After focused tests, exact-package preflight and the full repository check,
reserve and send at most one private `KernelExecutionType.QUICK_SAVE` request.
Stop at its receipt, whether accepted, rejected or uncertain. The owner will
start the notebook in Editor and return `結果.zip`. No agent execution,
status/log/output query, retrieval, monitoring, Dataset mutation, automatic
retry, second save, paid work, hidden/locked scoring or competition
submission is authorized. Status is
`trials/arc-agi-2-qwen35-nvarc/compact-abc-editor-004.md`.

The sole private QUICK_SAVE was accepted as version 1, kernel ID `136344090`,
after offline preflight and the full repository check passed. Exact package,
request and receipt digests are retained on the status page. The one save is
consumed; the agent started no session and did not query runtime state.
