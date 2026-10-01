# Decision 0050: Preserve the original NVARC recipe in an isolated reproduction track

Status: Accepted
Date: 2026-10-01

The owner directs that reproduction accept the original material and recipe in
full, with isolation, rather than remove published inputs to make the recipe
clean. This supersedes using clean-research exclusions as a prerequisite for
local preparation of the original reproduction track. Decision 0049's filtered
outputs and terminal observations remain immutable evidence of a separate
clean-data preparation.

For original-recipe preparation, retain all six published training sources,
including evaluation-derived `nvarc_full`, without development-parent filtering
or the added 8192-token review cap. They contain 3,255,481 records in the already
verified augmented version-1 archive. Preserve `arc2_evaluation6` separately as
the original validation source (720 records), not a seventh training source.
Apply the actual upstream loader/packing behavior once implemented and checked;
do not invent a truncation rule. Record source versions, both synthetic parents,
exposure and overlap instead of deleting original inputs to clear a clean gate.

Keep original reproduction and clean-data comparison in distinct material,
manifest, checkpoint, run-identity and result namespaces. A model exposed to
these public evaluation/development ancestors must never be represented as
unexposed on those tasks. Future inference inputs and evaluator answers remain
separate. No previous locked-holdout evaluator file is opened or scored by this
local preparation, and no clean/fresh-holdout or promotion claim follows.

The original Qwen3 model, source training backend and exact notebook version
must be distinguished from the current Qwen3.5 port. This direction does not
silently replace the pinned solver, reinterpret the eight-step port as full
SFT, or turn tiny-model evidence into original-scale reproduction.

Authorize local, reversible preparation and documentation of this separated
track. Preserve the frozen 20260930 method contract; a later distinct contract
and importer must express the new policy and multi-parent lineage. No new
dataset/model acquisition, Dataset mutation, kernel save/run, external teacher
call, real-data training, output retrieval, paid work, hidden/locked scoring,
competition submission or publication is authorized by this scope correction.
The current remaining-work inventory is
`docs/plan/2026-10-01-nvarc-reproduction-gaps.md`.
