# Official NVARC dual-specialist continuation

Status: local implementation and validation, not a submitted experiment.
The unchanged 2B/4B build has priority. Capacity expansion is a separate future
comparison and does not alter these checkpoint identities.

## Starting points and measurement qualification

- [Official compact 2B SFT141](https://www.kaggle.com/models/sorokin/qwen3_2b_grids15_sft141/transformers/bfloat16/1):
  1,409,475,584 BF16 parameters, 28 layers, vocabulary 16.
- [Official compact 4B SFT139](https://www.kaggle.com/models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1):
  3,633,593,856 BF16 parameters, 36 layers, vocabulary 16.
- Exact files, sizes, hashes and exposure qualifications are in
  `tools/nvarc_posttrain_20261017/model-pins.json`. These are trained author
  releases, not the older locally trimmed untrained base. No ReArc model is used.
- The 4B lineage includes public-derived material and all training parents;
  the 2B release is not established clean. Our train/dev split prevents new
  within-run leakage but cannot erase inherited exposure. PUBLIC120 results are
  therefore exposure-qualified development results, not clean generalization,
  hidden/official scores, or evidence that the original clean >93% goal is met.

All 710 tensors passed finite-value inspection. Both complete file inventories
and tokenizer roundtrips passed. The actual 2B model also loaded and produced
finite short teacher-forced probabilities on CPU: 69,795,840 trainables,
approximately 3.38 GiB peak RSS, 12.6 seconds total on the local machine. This is
loader/forward evidence only, not a GPU benchmark or model-quality result.
An additional actual-2B CPU admission committed one finite synthetic SFT update
and roundtripped its exact adapter checkpoint through a fresh engine. The
adapter changed, optimizer state was not resumed, and peak RSS was approximately
4.65 GiB over 24.7 seconds. That deliberately synthetic checkpoint is excluded
from scientific continuation and from the source capsule.

## Four independent workers in one notebook

The fixed jobs are 2b-S, 4b-S, 2b-H and 4b-H. S requests 1,024 continued-SFT
steps; H requests 256 SFT warmup steps and 64 groups of eight full-vocabulary
rollouts with actual upstream Agent Factory 3 DDIS updates. These are distinct
practical recipes, not a claim of step-, token- or compute-matched treatments.

Both use rank-64 rsLoRA, alpha 16, all seven projections, FP32 trainables and
the tiny untied full embedding/output head over a frozen BF16 base. Independent
workers have private adapters, optimizers, seeds, caches and checkpoint roots.
Adapter initialization is paired within each model; generated dev views and
TTT use a separate fixed evaluation seed across every arm.

The literal compact prompt matches the author formatter: role tokens and
single digits, no English grid wrappers or added separator newline. A strict
serialized fast tokenizer avoids the automatic Qwen BPE fallback that otherwise
drops the compact role tokens. Context is 8,192, generation limit 931, EOS 15.
Only entire demonstrations may be dropped; queries and target grids are never
cropped. Invalid completions remain invalid.

The hybrid reward is exact grid equality only. Wrong grids never receive pixel
shaping credit. Mixed-success parent sampling retains uniform exploration.
Verified exact-positive CE is separately labelled off-policy replay; all-wrong
groups do not manufacture an RL update and may instead use a separately counted
real training-demonstration SFT update. Rollout microbatches share one unchanged
behavior policy. Physical attempts, zero-signal groups and partial discarded
groups are counted, not hidden by success-only accounting.

## Measured concurrency and the original platform clock

One actual CUDA device is required and logged. Ordinary independent processes
share it; no hardware partition, MIG/MPS configuration, DDP or extra GPU is
claimed. Initial serial probes measure loading, 2k/4k/8k SFT, long cached decode
and actual DDIS replay/backward. Synthetic probe rewards are resource fixtures,
never scientific successes. Identical four-job workloads are repeated twice at
concurrency 1, 2 and, if memory permits, 4. Every proposed speedup must beat the
previous setting on both repeats by at least 5%, including startup/closure.

Admission uses actual measured allocator peaks with margin and checks total
resident memory. A software allocator cap is not a hardware reservation.
Failure falls back to a measured safe setting, never a promised four-way speedup.
Every launched process tree is closed and verified before further dispatch.

A four-parent, train-derived TTT/inference pilot per model measures reset/hash,
adaptation, eight-view decoding, startup, export and closure costs. A 1.5 safety
factor reserves two complete 120-task/167-query evaluations before training is
allocated. The original pre-dispatch epoch + 12-hour platform deadline never
resets. Per-task/query shares retain partial finished candidates rather than
discard them. Misses remain in the denominator. If preparation/controller work
fails, a closed-failure export reconstructs the fixed ensemble from finished
specialist predictions and inserts explicit misses for absent models. Only
source-, workload-, model- and device-bound evidence from verified closed workers
is admissible. Explicitly rejected results and their raw prediction files stay
out of selection, recovery and sealed scoring. A closed-failure export cannot
claim operational/model success.

## Selection, inference and evaluation boundary

Each arm evaluates an untouched adapter baseline and its continuation on the
same frozen 24-parent generated leave-one-demonstration-out dev panel. Selection
uses exact pass@2, then pass@1, validity and lower training cost, never dev NLL.
Incomplete panels cannot win. This small exposed-parent panel is a practical
selection signal, not unseen-task proof or a statistically strong comparison.

The selected adapter for each model is restored before every PUBLIC task.
Thirty-two requested demo-only TTT updates and eight fixed transformed views
are explicit recipe choices, not a reproduction claim for the author's larger
TTT/search budget. Candidate ordering uses votes, then own-view likelihood.
The ensemble takes one top candidate per specialist, fills duplicate gaps by a
fixed order, and retains at most TWO total guesses per query, not four.

The GPU notebook mounts solver-only challenges, never the evaluator-bearing
PUBLIC dataset. This is dataset separation, not an OS sandbox claim. After the
entire owned controller/worker subtree closes, predictions, model-specific
candidate/adaptation records and summary are sealed by exact hashes. An external
CPU scorer first binds exact numeric notebook/version, source, terminal status
and downloaded seal. Only then may it open evaluator answers and invoke the
unchanged pinned scorer over all 120 tasks/167 queries. Even a numeric 167/167
cannot set `clean_goal_met` true for this exposed initialization.

## Local artifacts and pending execution

Runtime: `tools/nvarc_posttrain_20261017/`. Focused synthetic tests:
`tests/test_nvarc_posttrain_*.py`. Source capsules contain only the runtime import
closure, license notices, model-file pins and four official PyPI dependency
wheels. The approximately 10 GB of author weights remain official model mounts.
Private prediction/checkpoint data and evaluator material never enter the source
capsule or public repository.

Proposed new private notebook: `danielwuu/iris-x-nvarc-dual-posttrain-20261017`.
Proposed new private source: `danielwuu/iris-x-nvarc-dual-source-20261017-001/1`.
These are local draft identities, not verified existing remote objects. Previous
pending upload/publication/run approvals are not silently reused for a materially
different payload. No new run, upload or public source publication is represented
by local tests or capsule creation. Independent local integration review found
and verified fixes for failure-path ensemble reconstruction and rejected-worker
identity consumption. Actual GPU memory, throughput and learning evidence remain
required; CPU tests and a reviewed source capsule cannot establish these.
