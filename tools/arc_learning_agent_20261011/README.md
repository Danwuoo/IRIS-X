# IRIS-X learning agent: one bounded research cycle

Status: development candidate. No new 8B GPU training, Kaggle run, Git push, or
publication has been performed for this package. CPU validation and its exact
source bindings are recorded separately.

## Why this replaces the previous method

The successful PUBLIC120 v2 run completed operationally, but every policy had
zero eligible answer grids and therefore 0/167 micro pass@1/pass@2. Strict native
finite-trie decoding fixed syntax (88/88 admitted outputs were legal), while none
of the model programs fit a demonstration. The raw arm had75 JSON syntax failures,
11 IR-schema failures, one inventory program and one legal program outside the
inventory. Two CPU search orders each tried64 of5965 plans per task and found no
all-demo-fit program. Query execution therefore never began.

That experiment used an unchanged base model, no adapter and no training. Its
model prompt showed demonstrations but no query input. It cannot establish the
potential of NVARC-style learning or of a complete feedback-driven agent.

This implementation changes the method substantially:

1. Genuine global LoRA SFT on clean, source-bound training tasks and independently
   verified authored targets. Full native embeddings/output head are retained.
2. Training-only program/repair rollouts. One training demonstration is withheld
   from every generation/feedback prompt. A fitted visible-demo program must also
   pass the withheld demonstration before it becomes a refinement target.
3. Per-public-task adaptation starts from the exact frozen global adapter, with
   fresh optimizer/scheduler/RNG and demo-only LODO data. Every task resets in a
   finally block. Those LODO rows are training examples, not a fresh-fold accuracy
   estimate after adaptation.
4. Direct arbitrary-grid generation sees demonstrations and query input. Its
   grammar admits every rectangular1..30 by1..30 grid over colors0..9; it does not
   enumerate a finite answer/program inventory. Native BPE, EOS and prefix rules
   are audited against the actual tokenizer.
5. A host-owned controller maintains typed hypotheses, parent links and verifier
   evidence. It routes global-model program proposals and repairs through the
   unchanged bounded Python VM, then fuses those predictions with adapted grid
   candidates. Generated code is never executed by host Python.
6. Identical ordered eight-view likelihood comparisons use the same adapter
   snapshot and complete native output head. Missing views cannot improve a
   candidate by averaging fewer scores. Reversible views and unique support are
   recorded; untrusted self-reported confidence is not a ranking signal.

This is real weight adaptation plus agent scaffolding. The controller is
host-deterministic; it is not a claim that the transformer's architecture itself
was redesigned. A single8B base is shared, rather than loading several backbones
and consuming the limited session on isolated micro-experiments.

## Target and experiment views

The primary goal preserves the project's PUBLIC120 **micro pass@2 >=50%**, which
requires at least84 correct test inputs out of167. Task-macro pass@2 and all-test
whole-task success are secondary and always shown separately. This supersedes
the earlier research draft that proposed task-macro as primary. No50% result is
promised.

The three views are:

- global_grid: trained global adapter, reversible direct-grid candidates;
- task_ttt: independently task-adapted direct-grid candidates;
- full_agent: shared direct candidates plus verified program/repair candidates.

Shared calls count once physically. Additional adaptation, program verification,
feedback prompt length and likelihood forwards are separately visible. These
are not equal-FLOP ablations. Every view retains the full120-task/167-test
primary denominator; per-task validity, missingness and budget/context exclusions
are reported without inflating the score.

## Data quality and learning limits

The official training source is arcprize/ARC-AGI-2 at commit
f3283f727488ad98fe575ea6a5ac981e4a188e49:1000 exact Git-blob/size-verified files.
The existing800train/200dev partition is preserved. Connected family/ancestry or
known D4/color-variant components can demote train members todev, never promote
historicaldev totrain. Original training-file test fields are stripped before
building model rows. Every public120 ancestor, unknown parent and split-crossing
lineage is rejected.

The prepared clean v2 material has21,243 augmented official grid LODO rows and
192 authored grid/program/repair rows,21,435 total. The64 authored episodes span
8 families but only22 distinct program targets,13 in training and9 in dev. These
small counts are disclosed; repeated sampler exposure is not new data diversity.
The declared6-grid:1-program:1-repair record schedule balances families within
objectives; actual processed and supervised token shares are measured, not
claimed to equal those record proportions.

Original NVARC full contains evaluation-derived ancestry. It is not silently
included. An optional training-only synthetic derivative requires exact version,
license, all-parent closure and current800-train admission before use. The core
package does not pretend a clean million-row corpus is already available.

Public evaluation is known development data, with unknown base-pretraining
exposure. No untouched-holdout or official4-L4 competition equivalence is claimed.

## Twelve-hour session envelope

The maximum is43,200seconds total, including setup and closure:

| Stage | Maximum seconds |
|---|---:|
| Bootstrap/model load |1800|
| Throughput calibration |900|
| Data admission |900|
| Global SFT |10800|
| Training-only program rollouts |2700|
| Verified trajectory SFT |2700|
| Training-dev choice/freeze |3600|
| Frozen public solve |16200|
| Seal/score/export |1800|
| Reserve |1800|
| Total |43200|

A persisted pre-dispatch epoch can include provider startup when available.
Otherwise the first active notebook cell starts the measured budget; unseen
provider startup is not claimed. New solver work stops with3600seconds reserved
for score/export/cleanup. Each active stage is supervised by the parent, and
public time is allocated across remaining tasks rather than exhausted by early
search. External provider termination is still possible; no zero-bug or
hard-provider-time guarantee is made.

Physical ceilings:1600 generations,12000 likelihood forwards,8192 training
microbatches,50M model-input tokens,3.2M generated tokens,12000 CPU verifier calls,
2.4B verifier gas. These are ceilings, not promised work or throughput. Training
steps scale down from actual calibration; a capped/skipped stage is explicit.
Unknown dispatched work keeps its reservation and blocks scoring.

## Reused safety and scoring contracts

Program entry is transform(grid). The unchanged safe interpreter supports useful
loops/helpers and host-provided list/grid/component operations while forbidding
imports, filesystem/network access and general host attributes. Each fresh
verifier retains200000gas,256MiB,2CPU seconds and3wall seconds. Program queries
require a persisted all-demo-fit proof; direct-grid answers do not need a
program-fit gate.

A dedicated subreaper supervisor tracks PID incarnations and shuts down owned
setsid/double-fork descendants. Only a gracefully stopped owner, complete work
ledger and immutable prediction seal permit the independent CPU evaluator to
read public answers. The original arc_offline_evaluation.py bytes remain pinned.
This is trusted-code dataflow/lifecycle isolation, not adversarial same-UID
filesystem secrecy.

The evidence ZIP excludes installed environments and large adapter/checkpoint
payloads. Those remain separately retained and hash-listed. Checkpoints include
real adapter/Adam/scheduler/RNG/data cursor identities; only the latest two owned
checkpoints are retained. An inference adapter alone is not an exact restart
checkpoint.

## Research lineage

- [NVARC primary repository](https://github.com/1ytic/NVARC): synthetic puzzles,
  global SFT, task-local rsLoRA, augmentation, search and common-view rescoring.
  This bounded implementation uses standard LoRA (not rsLoRA or full-weight SFT).
  Its reported global training scale was864H100 GPU-hours; this single-G4 recipe
  transfers method ideas, not that training scale.
- [AVO paper](https://arxiv.org/html/2603.24517v1): hypothesis lineage and
  evidence-directed revision inform the bounded program repair branch.
- [Duck harness](https://tufalabs.ai/research/duck-harness/): host-owned facts and
  tool-grounded observations inform the controller; its original hardware/model
  setting is not8B/G4 evidence.
- [Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent): task-scoped
  addressable state, completion gates and memory discipline inform typed memory;
  its general Python runtime is not transplanted as a sandbox.
- [NeMo profiling](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/profiler.html):
  actual stage/physical-call tracing, not an unnecessary framework migration.
- [Jev confidence documentation](https://docs.typesafe.ai/confidence): structured
  typed choices motivate interfaces; reported confidence is never ARC truth.

NVARC's use of NeMo RL as an SFT framework is not evidence of online RL in this
implementation. Verified trajectory refinement here is supervised learning.

## Current validation and remaining production uncertainty

The actual native Granite tokenizer admitted all 21,435 prepared training rows
without truncation. All 167 query-visible base grid prompts, all 1,336 declared
augmented grid prompts, and all 120 whole-task program prompts fit the unchanged
6,144-token prompt ceiling. Maximum lengths were 3,945 or fewer for the grid
views and 4,684 for the program prompts; repair prompts remain candidate-dependent.
This removes the previous prompt-format exclusions in these predeclared prompts,
not a guarantee that every later generated trajectory fits.

Tiny CPU tests use real forward/backward operations, PEFT LoRA parameters,
optimizer states, native-vocabulary masking and isolated task resets. The current
suite also executes the entire two-task learning/agent/stop/seal/scorer/archive
flow on explicitly synthetic fixtures. These tests do not establish a PUBLIC120
score or the throughput/VRAM behavior of the 8B model on G4.

The in-session calibration currently measures three optimizer updates drawn from
the first 64 admitted training records. It conservatively scales a training-step
ceiling from the slowest observation. It is not a longest-context generation,
scoring or task-adaptation benchmark. The hard per-stage and per-call caps remain
necessary: normal cooperative cutoffs leave cleanup time inside each cap, while
an unresponsive owner is stopped and cannot produce a successful scoring receipt.

The optional published NVARC synthetic corpus is excluded entirely. Its pinned
version was inspected in quarantine, but the available metadata has no verified
license grant and the records do not establish the required complete training-only
ancestor graph. No filename-based ancestry inference was accepted. Its inclusion
count is zero; the quarantine archive is not a runtime or release input.

This release is prepared locally. The proposed code/training Dataset references
have not been published, and no new GPU session has been launched. The notebook
must receive separately verified published asset pins before a real deployment.
