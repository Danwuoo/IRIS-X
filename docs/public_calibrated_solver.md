# Public calibrated paired solver

This is an explicitly invoked, offline **Linux-only** orchestration endpoint for
the fixed public ARC-AGI-2 diagnostic. It integrates public demonstration-only
D4 calibration, the unchanged public BF16 native-Qwen3 generation/common-eight
NLL baseline, independent post-exit auditing and the public submission exporter.
It does not download a model, access a remote executor, submit to Kaggle, start
a notebook, train, or inspect private implementations.

The scope remains **12 public parents, 15 true task.test queries, 120 scientific
generation views**. The unchanged base additionally executes three full-query
admission generations and three cost-only scoring forwards. Those are separate
costs, not extra scientific predictions. The frozen public panel has 256 LOO
support/view calibration cells. Serializer generality does not expand this
experiment into an arbitrary hidden-task solver.

## Evidence and limitations

The CPU test backend is deliberately synthetic. It emits deterministic grids
and computes actual causal FP32 answer-token NLL tensors, including EOS. Its
12-parent/15-query fixture has 192 LOO cells, not the public panel's 256. The
tests exercise the actual subprocess chain and failure boundaries. They do not
load the 2B model, establish a runtime estimate, demonstrate accuracy, prove a
gain, or establish GPU feasibility. Every output records its execution kind and
`scientific_effectiveness_established: false`.

The real path uses the exact existing public model weight/config/tokenizer pins
and the frozen base source commit
`afb2dfaa3a5c3f6e09338fd38487e29f77a0c47c`. It preserves BF16, single CUDA GPU,
SDPA, native Qwen3, full support and answer context, the actual WordLevel
tokenizer, EOS accounting, greedy 931-token ceiling and common-eight scoring.
There is no quantized/CPU fallback or alternate model. Standard Transformers
position handling remains unresolved relative to any author-specific
multi-axis RoPE behavior; integration does not repair or conceal that caveat.

Public source identity and byte seals are integrity checks, not signatures or
independent authentication of model execution. Public evaluation may have been
seen in pretraining. Even a complete scientific *mechanics audit* is not proof
of effectiveness, hidden generalization or a statistically reliable improvement.

## Lifecycle and isolation

1. `prepare` checks the exact public plan, unchanged base source pins and full
   context schedule, then freezes the public source inventory. It reads no gold
   and loads no model. Source-lock bytes must be explicitly supplied to `run`.
2. `run` fixes one strategy (`vote`, `rescored`, or `demo_weighted`) and one
   no-candidate policy in an immutable initial intent. The original monotonic
   clock starts before run admission, verification and process creation.
3. A killable coordinator launches one owned model leaf. Only the leaf verifies
   local model bytes and creates the exact public backend, once. All subsequent
   stages receive that same backend and inherited deadline.
4. Every visible demonstration is held out in turn under all eight D4 views.
   Calibration uses all other demonstrations in their original order, full
   answer/EOS causal likelihood and no test labels. The calibration hash and
   source identity are frozen before **any** task.test generation, including
   the unchanged admission probes. Incomplete calibration forbids query
   generation. Its partial raw receipts and unknown failed costs are retained.
5. The unchanged base generates its common raw pool and rescoring evidence. A
   separate trace binds each raw view to the prior calibration freeze. No
   candidate is regenerated for the new method, and no partial weights can be
   promoted. Model parameter/buffer version checks are guards, not cryptographic
   state attestation.
6. The model PID exits. The coordinator seals the immutable raw receipt
   inventory, reconstructs partial evidence when necessary, reconciles trace
   and costs, freezes the preregistered selection, and invokes only the public
   exporter. It verifies exported bytes before launching the evaluator.
7. A separately bounded evaluator is the only process that opens gold. The
   supervisor/coordinator route its pathname without reading it; the model
   leaf is never passed that pathname and imports no evaluator.
   It checks seals, source and strategy lineage; independently recomputes LOO
   weights, raw pools and ranks; audits original NLL/vote evidence; and then
   evaluates. The selected export is verified again afterward. Scores cannot
   choose or change the selected strategy.

The model leaf's CLI has no gold argument and imports no evaluator. This is a
process/dataflow boundary, not an OS access-control sandbox: a malicious custom
program running under the same filesystem identity would need a stronger
sandbox. Arbitrary backend/module injection is intentionally not supported.

## One original deadline

`--budget-seconds` is a single 60..7200-second allowance covering source/model
verification, loading, calibration, generation, NLL, serialization, export,
post-exit reconstruction and evaluator statistics. It is never reset on an
exception or passed as a fresh stage budget. The unchanged deadline reserves
15..120 seconds for closure; model work cannot consume that reserve. The
coordinator separately bounds the evaluator within the remaining original
time, retaining a final closure margin. The supervisor bounds the coordinator
and its tracked model/evaluator descendants. Its own pre-launch source/plan
reads and final diagnostic writes are included in elapsed accounting but are
not independently hard-killed if local OS I/O blocks. This is not an absolute
wall-time cap on the entire CLI process. A late result cannot turn a partial
session complete.

Only exact observed descendant identities are terminated. Each wait tracks
parent lineage and PID/start-time identity and holds Linux pidfds for signaling
and reaping, including descendants that leave the original process group with
setsid. Subreaper handling adopts owned descendants if their parent terminates.
Preexisting unrelated children are excluded. An adopted child whose lineage
was never observed is not safe to kill: cleanup fails explicitly, no completed
seal or gold evaluation is allowed, and no arbitrary PID is signaled. This is
not cgroup containment or a malicious-process sandbox. A normally exiting
leader with live descendants is cleaned up but remains a failed run.
SIGINT/SIGTERM cleanup follows the same ownership boundary. Linux pidfd support
and readable bounded process identity metadata are required before launch;
there is no unsafe Windows PID-only fallback. Platform-specific tests are
annotated with the repository's Linux capability requirement.

Hard termination can leave an incomplete receipt or no aggregate. Previously
published atomic receipts are never replaced or deleted, unknown interrupted
cost remains unknown, and recovery never promotes an interrupted run. Cleanup
and writing an explicit timeout diagnostic may finish after the deadline;
this is recorded as partial, never counted as within-budget success.

## Example commands

These commands describe a future explicitly authorized run, not work performed
by installing or importing the package. The local model directory must already
contain the exact pinned public model files. Source-lock hashes change when
reviewed source bytes change, so re-prepare after an intentional source update.

```sh
python -m tools.public_calibrated_solver prepare \
  --plan /path/to/public-materials/plan.json \
  --plan-sha256 bafeabeae62625171147645d166b524e3f008fdbf5e44164c0ed8c41498e9c1c \
  --output /path/to/new-source-plan

python -m tools.public_calibrated_solver run \
  --source-lock /path/to/new-source-plan/source_lock.json \
  --source-lock-sha256 SHA256_PRINTED_BY_PREPARE \
  --model-dir /path/to/exact-public-sft141-model \
  --gold /path/to/public-materials/gold.json \
  --gold-sha256 cab56c98868fdbf119646bb3ae2591f1588e9fc39800c7c1a08b368ec44e7471 \
  --strategy demo_weighted --fallback fail \
  --budget-seconds 7200 --output /path/to/new-paired-run
```

The real command admits only the exact public raw plan hash above and canonical
hash `cc795e7475cb689714b34fb5f10802c23f51a2534dcf50121774a56750c31069`.
The evaluator-only gold identity is checked against the already frozen public
material manifest; gold is not used to admit or select the model method.

Synthetic fixtures require `--synthetic` on both preparation and execution.
Synthetic fault/elapsed-clock controls are rejected for a real run. There is no
automatic synthetic fallback when model admission fails.

## Output contract

Read the outer `watchdog.json`, then `paired/closure.json`; the mere presence of
`submission.json` is not success. Useful artifacts include:

- `intent.json`: initial strategy, no-candidate policy, original clock and source
  identity, without gold pathname or labels.
- `paired/model/`: original calibration, admission, generation and score
  receipts; operation trace; immutable freeze; model-state and runtime evidence.
- `paired/worker_seal.json`: exited-worker inventory and byte hashes.
- `paired/calibration.json`, `pool.json`, `base_result.json`, `ranking.json`:
  controller reconstruction, distinct from preserved worker originals.
- `paired/selection.json`, `selected_candidates.json`: pre-gold strategy lineage.
- `paired/export/submission.json`: official two-attempt wire format, emitted
  and verified only through `public_sft141_submission`.
- `paired/evaluation/result.json`: independent full-denominator paired report.

The exporter adapter is explicitly `frozen`; the actual chosen method remains
in the initial intent and bound selection record. `--fallback fail` writes no
submission when any query has no eligible candidates. `copy-input` produces
clearly counted input-copy fallbacks, never model-success claims. Single
selected grids are duplicated as required by the wire format and counted as
one selected prediction, not two independent attempts.

Primary accuracy is query-micro pass@2 over all 15 queries, including missing or
ineligible predictions. Task-macro sensitivity and all-query task success are
secondary. Three strategy outcomes are paired on the same raw pool. Reports
include all per-query outcomes, 12-parent exact sign-flip enumeration and a
seeded descriptive cluster bootstrap. Parent independence and sign symmetry
are assumptions; small-cluster intervals are not generalization guarantees.

Every artifact directory must be new. Existing directories and no-follow input
or output ancestry checks fail closed. JSON publication is individually atomic
and exclusive, not a multi-file transaction or a hostile concurrent-filesystem
sandbox. Source changes require a fresh intent rather than overwriting evidence.

## Tests

```sh
python -m unittest tests.test_public_calibrated_solver -v
```

The suite runs the real synthetic subprocess chain, CPU causal loss, partial
calibration/generation, owned-leaf timeout, fixed-strategy export, tamper
rejection, source/plan pins, immutable raw evidence and full denominators. A
passed CPU suite does not authorize or claim any GPU or external execution.
The end-to-end tensor fixture and tensor-loss test require optional PyTorch;
the clean no-PyTorch lane explicitly skips them rather than claiming CPU
execution or failing setup. Pure contract/platform boundary tests still run.
