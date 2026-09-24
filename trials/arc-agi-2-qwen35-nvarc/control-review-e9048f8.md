# Compact-flow acceptance analysis — 2026-09-24

Reviewed main: `e9048f8`.
Verdict: **PASS for the previously specified bounded synthetic complete-flow
milestone; candidate yield remains partial; full NVARC reproduction is not
accepted as complete**.

The pre-execution plan required a real compact 4B conversion/reload, bounded
task-local adaptation, real model generation with at least one complete grid,
likelihood ranking, truth-free result packaging and independent verification.
It did not require every synthetic test to return candidates or establish ARC
accuracy. Pilot `nvarc-4b-compact-complete-003` meets that narrow milestone.
This review found no new blocking defect in the exercised happy path; it is
not an exhaustive validation of larger configurations or all failure modes.

## Independent validation

All checks used retained local material. No provider status, log or output
request, kernel launch, real-model training/generation or ARC scoring occurred
during this review.

| Check | Result |
| --- | --- |
| Full repository validation | PASS: 206 tests, 4 optional skips under default Python 3.14 |
| Strict optional ML profile | PASS: 6 tests, no skips; includes actual tiny Qwen3.5 conversion/material verification, PEFT/reset, nonfinite rejection, two-task/four-test model flow and CPU collective checks |
| Retrieved compact model inventory and four shards | Rehashed with `arc_nvarc_compact_pilot verify`; PASS |
| Outbound/result independent verification | PASS; exact material and result digests match the recorded terminal verification |
| Returned plan, visible source, base/wheel manifests and runtime wheel | Hashes match the approved staged package |
| Notebook, metadata, phase, checkpoint and terminal log snapshot | Hashes match their recorded bindings |
| Executed wheel versus current code | Compact pilot, candidates, representation, training, runtime and Kaggle runner bytes match |
| Previously rejected checked-in candidate config | Unchanged current `qwen-candidates.json` now passes `make_binding` on a synthetic workload |

Verified compact material digest:
`sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982`.
Verified result digest:
`sha256:085db1e03d9d673701cabccb85db029b9a016b021f7fd4674c08df1f29eb6130`.

New review logs are in `.irisx/nvarc-acceptance-e9048f8/`:
`validation.log`, `ml-profile.log`, `material-result-verification.log` and
`evidence-check.json`. Original evidence remains untouched under
`.irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-003/`.

## What this run actually proves

The real pinned 4B weights were transformed to the 16-symbol representation,
saved in four shards and reloaded, closing the previous pilot's semantic gap
of feeding compact IDs into an unchanged full-vocabulary base model.

Both synthetic tasks ran one finite-checked task-local LoRA step, ten training
tokens each. Each task's observation contains fresh nonzero gradient-group
counts for attention, DeltaNet, embedding and head. The same adapted solver
then processed both of that task's test inputs. CPU tests separately check
cross-task adapter reset and rejection/reset after nonfinite updates.

The returned checkpoint reconciles two steps, 20 training tokens, four
generation calls, four returned sequences, four candidate verification calls,
43 explicit model forwards and zero teacher calls. The four candidate checks
use eight likelihood views each: 32 verification forwards plus 11 DFS
expansions explain the 43 total. These counts fit the approved limits.

`synthetic-rect-b` produced two distinct complete-grid attempts for each of
its two tests. `synthetic-rect-a` returned no candidates for either test and
retained explicit missing records. Therefore **2/4 tests have complete grids**;
this is candidate availability, not pass@2 or correctness. No synthetic answer
comparison or ARC score was computed by this review.

The two missing tests stopped after two and one DFS expansions respectively,
with `no_valid_candidate`, below the 16-expansion limit and without timeout.
The successful tests stopped at the two-sequence ceiling after four expansions
each. The observed missing outputs therefore do not show a wall-time or
expansion-budget bottleneck; the current probability pruning and valid-grid
conditions yielded no completed path. More GPU time alone is not an evidenced
repair. Changing the search threshold would be a new method configuration,
not a correction to the completed run.

Application phases reached compact reload at 173.53 seconds and terminal result
at 247.18 seconds. Conversion/reload ran on CPU (reported CUDA peak zero and
parent process peak RSS 8,585 MiB); the worker then loaded the compact model on
one L4. Worker load peak was 7,558 MiB, with task peaks 8,257 and 8,265 MiB.
These are phase-specific allocation observations for this tiny workload,
not proof that full SFT or rank-256/8,192-token adaptation fits on an L4.

## Repair history and remaining engineering cleanup

The shipped-config schema mismatch and nonfinite-gradient validation gap from
the previous control review are repaired and regression-tested.

The new 001 attempt rejected the Dataset inventory before loading; 002 allowed
the exact retained legacy tree but failed when the converter serialized tuple
`SYMBOLS` into canonical JSON. The 003 repair writes a list and adds a test
through the actual converter/save/reload/material path. That regression is
more valuable than merely testing a parallel tiny-model conversion helper.
Inventory handling keeps exact filename/tree checks rather than disabling the
closed-world material gate.

Sharding the model into 2 GB members improved recovery, but 003 still required
same-version targeted continuation after `IncompleteRead`. Windows `charmap`
errors recurred when printing logs despite the earlier UTF-8 lesson. The full
model/result hashes now pass, so this is not a missing-artifact blocker for
003. Before another large retrieval, consolidate UTF-8 subprocess handling,
small-diagnostics-first retrieval and digest/size-checked per-file continuation
in one reusable transport path. Do not repeat model work to repair a download.

The README had stale statements saying the compact artifact/GPU result were
unverified and that no pilot generated outputs. This review updates those
statements to distinguish the earlier compatibility pilots from this flow.

## Scope still open and the next milestone

This run has no ARC-SFT checkpoint and does not measure learned ARC solving.
It uses rank 2, one adaptation step per task, at most eight output tokens and
one generation view per test. Eight likelihood views exercise reranking;
they do not verify the intended 16-view generation workload. Four visible
GPUs do not mean four workers were used. Full SFT, real distributed GPU
training, long grids, rank 256, TRM integration, SDG sandbox execution and
full-method quality/cost remain outside the evidence.

The useful next milestone is a small, source-bound ARC training/quality pilot:
freeze a clean training/dev split, specify a genuinely bounded SFT feasibility
run with measured optimizer/memory requirements, retain a trained artifact,
and compare compact base, SFT and SFT-plus-TTT under fixed generation budgets.
Keep candidate availability separate from exact-match quality and include
failure/missing outputs in denominators. Do not tune on the old locked holdout.
The retained compact artifact can serve as a verified starting material;
there is no need to repeat its conversion merely to demonstrate the same gate.

Before that new experiment, finish the transport cleanup and prepare exact
data/model/runtime identities and resource limits. Decision 0027 ended when
this small flow was verified; this analysis does not start another kernel or
grant new experimental authority.
