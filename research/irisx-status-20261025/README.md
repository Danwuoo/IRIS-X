# IRIS-X source checkpoint — 2026-10-25

This small, sanitized checkpoint consolidates reviewed research and offline
contracts on the existing research branch. It is not a model package, cloud
controller, resource receipt, deployment instruction, new run authorization or
formal-training admission. No original scientific artifacts are rewritten.

## Current directions

- **CPT development is paused.** The existing public
  [offline prerequisites](../../docs/cpt-prerequisites-checkpoint-20261022.md) are not a trained 35B model.
  Use [CPT paused index](cpt/README.md) for the actual repository entry points
  and the preserved private-research document hashes. The archive itself,
  corpus and evaluator answers are not in Git.
- **4B post-SFT is active research.** TPU studies offline preference learning,
  winner/iterative SFT and on-policy reward signal. GPU studies episodic
  adaptation, search and reranking. Shared correctness smoke does not justify
  duplicating the full study on both devices. See [split](postsft/README.md).
- **K1 is engineering progress, not a quality win.** Real four-rank numerical
  gates and selected updates ran; two training parents produced no observed
  gain. RLVR had uniform rewards and correctly made zero updates. Checkpoint
  save did not establish restore. See [sanitized aggregate](postsft/K1-RESULT.json).
- **Larger studies are conditional.** Fixed metadata supply, modelwall cost,
  signal sufficiency, reset/restore, independent evaluation and an authorized
  execution budget must precede each larger stage. No automatic formal training.

## What is included

1. Sanitized historical CPT document navigation and candid limitations.
2. K1 aggregate outcomes without raw candidates, gold, cloud IDs or live ledgers.
3. Disabled TPU discovery/method matrix with fixed TRAIN-only metadata selection.
4. A separate GPU adaptation/search proposal and pure synthetic selector tests.
5. Byte-identical, already reviewed query-span/loss functions and small synthetic
   CPU tests. They contain no model loader, downloader or training launcher.

The existing
[method-landscape §7](../arc2-sft-rl-continuation-20261014/method-landscape.zh-TW.md)
remains the historical decision/trigger source. The 14B frozen A/B/C protocol,
17-October AF3 goal successor and present 4B/grid16/P1 adaptation are different
experiments. Do not replace their original results or transfer old permissions.

`SOURCE-PROVENANCE.json` distinguishes unchanged source from sanitized derived
documents. Each file is below 1 MiB; no raw archive, weights, checkpoint, private
answer, credential, operational log or live controller state is published.
The authoring worktree was isolated from active work; this file is not proof of
the final remote push or current resource state.
