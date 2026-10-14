# ARC-AGI-2 STATUS

Updated: 2026-10-14. Workstream: `arc-agi-2`.
Engineering task state: [generated board](../../management/BOARD.md).
Original document lifecycle and roles: [catalog](../../management/documents.json).

## Scope

For the existing scientific direction, original research documents, measured
results and the next discriminating experiment, start with [RESEARCH](RESEARCH.md).
This STATUS covers engineering and resumption; it is not the research summary.

WSF-04 isolates the mutable parser/dispatch entrance in
`src/irisx/domains/arc_agi_2/cli.py`. Shared CLI supplies the original repository
root, and the facade calls retained ARC/Kaggle modules. The
[migration map](../../verification/WSF-04/MIGRATION.md) records consumers,
path/blob pins, explicit legacy exceptions and unverified reconstruction scope.
Existing solver, scorer, source/notebook/manifest/review/archive bytes remain at
their original paths. The separately preserved run008 runtime is not merged
here; no provider reconciliation, publication, training or monitoring follows.

## Evidence

The scientific reading route is STATUS → [RESEARCH](RESEARCH.md) → R1 historical
synthesis and original results → R2 architecture assessment/R3 prospective
portfolio → R4 method assessment/R5 current experiment. RESEARCH indexes the
original sources at fixed run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d`;
the catalog retains individual method, plan and evidence roles.

R2's A/B/C means direct-grid, independent program proposals and feedback repair.
R5's current A/B/C means same-session saved/reloaded SFT256, at most four
disjoint 64-slot RL batches and extra SFT matched to B's whole additional
model-phase wall interval. These comparisons retain separate models, data,
budgets and qualification. Earlier SFT64/full-sweep drafts do not replace R5.

The modified-input BASE/TTT observation 5/172 → 10/172 and exposed uncapped
top-2/pool-oracle 1/6 keep their local scope and costs. R3's seen-family v18
2/6 → 5/6 and retrospective portfolio 6/6 motivate its prospective panel;
they do not establish new ARC generalization. Standard PUBLIC120 remains
120 tasks / 167 queries. Missing run008 results do not erase these historical
observations or answer the current RL-versus-SFT hypothesis.

Source checkpoint: branch `feat/run008-native-research-20261013`, final published
commit `cc14bd1a79aac1fe6135017c9e09d4834300675d`, tree
`1e456ae718708e4af282f1b62f8275f7f57ae24d`. The reviewed implementation checkpoint
`98b488a2fc3185a64c392933f087b72ab13f1989` is a distinct anchor; do not rewrite it as
the later documentation commit.

Read the pinned [handoff](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/RUN008-LOCAL-HANDOFF.md),
[reconstruction guide](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/transfer_run008/README.md)
and [independent transfer review](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261014/transfer-package-review.json).
Loader repair, native transport and existing-CA propagation have focused CPU
and independent source-review evidence, not real 14B/GPU or method efficacy.

Last successful provider readback in that handoff: 2026-10-14 00:51:27 UTC
(08:51:27 Asia/Taipei), code Dataset v20 and notebook v39 ERROR. An interrupted
upload has no proven successor write and no run008 epoch. This is historical
readback, not a fresh observation. There is no new PUBLIC120 result.

[CI run 38496849147](https://github.com/Danwuoo/IRIS-X/actions/runs/38496849147)
failed at seven README checks. A separate recorded aggregate attempt had 1,583
tests, 2 failures, 35 errors and 74 skips, without a matched clean-baseline
comparison. Neither record establishes full-green CI; see the transfer review.

## Blockers

The last network-execution recovery failed during sandbox setup, before program
execution. The handoff reports OAuth access resolved; do not relabel this as an
unresolved credential problem. Destination bindings and actual remote state still
need fresh verification before any future authorized mutation.

The owner's 2026-10-14 delivery record reports the combined Drive ZIP uploaded
but download-blocked by a provider safety flag, with remote SHA-256 and
availability unverified. Cause is unverified. Delivery remains partial; this PR
does not retry, bypass, rename, repackage or attest the archive. Readable source
and handoff are sufficient for the current navigation work.

Authentic reconstruction, original numerical replay, full-model/cuDNN GPU
behavior and four-L4 deployment remain unverified. Source object equality and
the shared public CPU smoke surface do not remove these blockers.

## Next

For engineering, follow [WSF-04](../../management/tasks/WSF-04.json), its named
handoff and the [bounded map](../../verification/WSF-04/MIGRATION.md). Run
`python tools/dev.py verify --suite arc-unit`; retain `arc-unit-audit` and the
complete aggregate outcomes separately. Return actual commits/reports for
independent review; implementing subagent checks remain self-review.

Preserve the research question and its evidence-to-experiment links during PR 2–4.
Read R4/R5 through RESEARCH for the current SFT256/RL/extra-SFT comparison and its
conditional successors; do not replace it with the earlier architecture A/B/C
or treat a missing run008 score as loss of the existing research results.

The hypothesis remains unanswered. R4/R5 keep different conditional successors
for demonstrated environment/numerical failure, complete zero-signal reward
audit, valid paired A/B/C gains/losses, low candidate oracle and selection gap.
This engineering increment starts none of those experiments.

Preserve this checkpoint and carry out the independent core foundation. Do not
download reproducible archives for that work. If execution is later authorized,
use the pinned guide to identify genuine historical Git/input dependencies,
rebind the supported destination, reconcile uncertain writes read-only and obtain
new exact source/readback/admission reviews. Draft versions 21/40/41 are not
proven remote allocations. Original private evidence cannot be fabricated.

## Boundaries

Leave `tools/arc_qwen_rlvr004_20261013/`, overlays, inventories, scorer, source
pins and original reviews in place. Preserve all old identities, failed clocks
and charges. Run008-only additions remain fixed references listed by the map.
No new topic, model input acquisition, training, provider call, GPU run, quota
query or competition submission is part of this restructuring.
The existing science remains SFT256 A, disjoint 64-slot B batches
and wall-matched extra-SFT C, with the original full PUBLIC120 120-task/167-query
denominator. Keep evaluator-only inputs isolated. A future session retains its
single immutable 43,200-second cap and all publisher/process/data/scorer gates.
This source checkpoint is not a successful-baseline tag or a closed live candidate.
