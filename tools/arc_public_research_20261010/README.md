# PUBLIC120 bounded public-development research

This separate package adds actual query predictions and the unchanged project
public scorer to the next finite-plan research notebook. It does not change the
old consolidated package, FULL witness gate, interpreter, scorer or prior runs.
Decision [0069](../../docs/decisions/0069-evaluate-sealed-public-research-predictions.md)
records the narrow accepted boundary change.

## What one notebook does

1. Authenticate code and the solver's public-data projection; run 128 independent
   synthetic controls using fresh bounded verifier processes.
2. Freeze all 5,965 compiled plans and both complete ranking orders for each of
   120 tasks before any search verification. Uniform and `shape_palette_v1`
   each verify 64 distinct candidates per task. Every candidate has positive
   support; there is no hard pruning, full enumeration, cached fit or injected
   witness.
3. If explicitly enabled, prepare the five pinned offline assets once, validate
   the native-token trie, load Granite once, and run paired raw/strict selection.
   Both arms see identical compact JSON prompts, seeds and finite support.
4. Select only fresh, all-demo-fit programs. Raw/strict have at most one plan;
   the ranking arms use the first two distinct fits in their precommitted order.
   Query executions use separate bounded processes and receive no answers.
5. Stop model ownership, seal proof-bound predictions, then use a separate CPU
   evaluator to read public answers and invoke the original project scorer.
6. Export predictions, score reports, physical-cost ledger, source/data identities
   and a verified evidence archive. Unresolved closure blocks scoring.

## Interpretation

`competition_gpu_equivalent=false`; official competition score is null. Record
prediction origin, hardware, model/environment, full source identity, adapter
status and public-data exposure. These results are research inferences and must
not be reported as competition four-L4 submission results. No training occurs.
The adapter is authenticated as an existing dependency but is not loaded.

The 120 tasks and 167 ordered test inputs are the complete evaluation directory
at official ARC-AGI-2 commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`, verified
through its Git commit/tree/blob chain and the project's SHA-256 provenance.
This is a version-pinned public development set, not a fresh holdout or a claim
about later upstream versions. The original Apache-2.0 license is retained.
There is known prior project public evaluation exposure; training exposure
cannot be excluded. The earlier eight engineering IDs do not overlap this set.

The solver-neutral `tools/arc_offline_evaluation.py` is used unchanged. Its
primary pass@1/pass@2 is exact grid equality, with all 167 tests in the micro
averages. The 120-task mean and whole-task success are supplementary metrics.
Missing/excluded/failed tasks retain their denominators. Duplicate candidate
grids are rejected, not credited twice. Do not substitute the separate historical
NVARC 172-test input variant. Do not combine the four policy pools into an
unregistered ensemble score.

The model comparison is constrained finite-pool selection/format reliability,
not unrestricted program synthesis. The CPU arms cover all 120 tasks. A real
pinned-tokenizer prompt audit admits 88 model task pairs (122 test inputs) and
excludes both arms on 32 tasks (45 tests) at the unchanged 6,144-token limit.
Thus 240 is the reserved ceiling; at most 176 calls are presently eligible.
Full-denominator scores and the prespecified paired-eligible stratum should be
reported separately in analysis (the unchanged scorer retains its full denominator). CPU-vs-model global score differences also include this
availability difference. No prompt truncation or task deletion is allowed.

## Runtime limits

- Session: 7,200 seconds including preparation, ranking, model, queries and export;
  120 seconds reserved for cleanup/scoring/export admission.
- Model: at most 240 physical calls; 120 seconds each; prompt 6,144, output 2,048,
  context 8,192. Same native vocabulary, one beam, one return sequence.
- CPU: at most 17,064 physical checks: 128 controls + 15,360 rank checks + 240
  generated-plan checks + 1,336 query checks. At most four verifier workers.
- Each generated program: 200,000 gas, 256 MiB, 2 CPU seconds/3 wall seconds;
  source/AST/grid/output bounds remain inherited and enforced.
- Unknown operations consume reservations. No automatic model retries or partial
  resume. Completed-run inspection is allowed; incomplete runs need a fresh root.

## Data boundary

The solver role contains demonstrations and test inputs only. The evaluator role
contains original public evaluation files. Generation and rankers receive only
validated demonstrations. The evaluator checks exact source identities, current
owner-stop evidence, fresh fit/query proofs and a closed prediction inventory
before scoring. It rebuilds candidate pools from those proofs. Scores cannot
feed back into the same run.

This is a trusted-code/lifecycle/dataflow boundary, not hostile-process filesystem
isolation on a shared-UID Kaggle mount. No private/hidden or competition answers
are admitted. After scoring, public-development exposure remains explicit.

See [RUN_GUIDE.md](RUN_GUIDE.md) for settings and [VALIDATION.md](VALIDATION.md)
for the exact reviewed source, tests and remaining runtime qualifications.
