# Full-support public calibrated integration

This is a new public-only integration, not a new solver method, a replacement
for frozen packages, or evidence of improved ARC capability. The old fixed-panel
validators (12 parents/15 queries, 8192 tokens, 7200 seconds) are unchanged and
are not monkeypatched. Only their public codec, native loader/loss, all-support
LOO specification, stable T=1 weighting math, strict serializer, and generic
Linux process-ownership primitives are reused.

## Run contract

`python -m tools.public_full_calibrated_solver plan --challenge challenge.json`
performs only gold-free CPU inventory. It does not load a model or predict fit.

Explicit prospective execution:

```sh
python -m tools.public_full_calibrated_solver run \
  --challenge challenge.json --model-dir /existing/pinned/public-model \
  --run-dir /new/evidence --output-dir /new/submission \
  --context-cap 10240 --budget-seconds 14400 --strategy vote \
  --evaluation-gold /evaluator-only/solutions.json
```

The evaluation option is optional for deployment without answers. When supplied,
its path remains in the controller request only, never in model dispatch. A
separate owned evaluator leaf first verifies exited-model evidence and immutable
prediction export, then opens gold. It must finish and close before the final
whole-clock completion receipt. Gold format is the ordinary ARC solutions map:
`{task_id: [output_grid_for_test_0, ...]}`. No gold data is packaged by this tool.

The wrapper may supply both `--original-start-monotonic` and
`--original-start-epoch` from the same machine, captured before extraction or
other preparation. Both must be earlier than the current clock. The original
14400-second budget is retained, not replaced with a new or residual clock.
Absent those arguments, the supervisor starts the clock before preprocessing.
This does not enable resume: evidence/output directories must be new, and every
publication is exclusive. Total budgets must be finite, positive, and at most
39600 seconds. Context must be a positive integer up to 262144, and actual
native-model admission separately requires it not exceed verified unchanged
native configuration. The 10240/14400 defaults are prospective, not measured
memory, runtime, quota, hardware-eligibility, or four-hour completion promises.

The original work deadline reserves 2% for normal large-budget closure,
serialization, evaluation and readback, with the same bounded small-budget
formula as the generic supervisor. The reserve is not reusable model time and
is not a promise that closure/evaluation will fit. Hard outer supervision bounds
preprocessing and closure; bounded termination/kill cleanup after failure cannot
turn a late session into a completed one.

## Scientific sequence

1. Validate the exact whole gold-free challenge and freeze task/query order,
   supports, strategy, context, budget, scheduler and source/model identity.
2. Admit every all-support LOO and generation envelope. Any overflow rejects
   the entire panel before model loading. No support truncation or reduced
   denominator is allowed.
3. Load exactly one pinned public native Qwen3 model, inference-only BF16 SDPA.
   Native tokenizer/config/device/dtype/adapter/quantization gates remain intact.
   The wrapper explicitly records the original loader's 8192 software cap and
   adopts the configured cap only after checking it against unchanged verified
   native configuration. It never patches config/RoPE or reloads the model.
4. For every multi-demo parent, leave each support out once in original order
   under all eight D4 views. Score every answer token including EOS with the
   unchanged full-answer causal FP32 NLL helper. For each view, average the
   per-support token-mean loss; apply the unchanged stable T=1 softmax. Single
   demo parents use uniform weights with no empty-conditioned LOO or adaptation.
   Underflow also follows the original uniform fallback. All LOO operations
   must finish before one immutable calibration freeze permits any query call.
5. Generate each query once per D4 view in view-major original-query order,
   retaining all original supports and the complete 931-token allowance.
6. Strictly parse EOS answers and invert D4 into one shared deduplicated pool.
   Rank that same pool by uniform occurrence vote, unchanged count minus mean
   of eight full-answer summed NLL scores, and frozen demo-weighted vote. Common8
   scores are not token-normalized; calibration losses are. No partial common8
   score can select a candidate, and incomplete query pools cannot apply weights.
7. Exit and clean up the owned model process and descendants, seal immutable
   receipts, independently reconstruct every raw operation/pool/rank, serialize
   and read back the chosen submission, optionally evaluate separately, and
   finish under the original clock.

Vote remains the default export. Demo-weighted ranking is experimental and
requires an explicit pre-gold selection; neither the evaluator nor observed
answers may promote a strategy or change the immutable export. All three
same-pool results remain available in analysis/evaluation. Evaluator diagnostics
include per-query first/second correctness and missing flags, query-micro
pass@1/pass@2, equal-task macro rates, and paired wins/losses/ties and first/second
selection changes against vote. These are descriptive, not significance claims. There is no training,
TTT, adapter, quantization, offload, runtime model download, retry, or resume.
No extra calibration/cost probe is run; its exact call count is zero. There is
no hidden measured-feasibility admission or answer-driven scheduling.

## Evidence, failures and verification

`python -m tools.public_full_calibrated_solver verify --run-dir /evidence
--output-dir /submission` is CPU-only strict raw replay. It checks unchanged
source, exact challenge/plan, exited-process seal, original clock, immutable
calibration, deterministic operation prefix, complete causal counts, canonical
candidate pool, selected export and final readback. Hashes establish local byte
integrity, not independent model-execution authentication.

Each operation receives an immutable start before execution and an end on return
or reported failure. Abrupt exits preserve the unmatched start as unknown cost.
Failed operations never fabricate zero tokens. Global and per-query physical
counters expose completed lower bounds and unknown totals; explicit failed,
unknown, late, invalid and missing states retain the full task/query denominator.
Model load is separately timed, and unfinished loading stays unknown. Model
state guards inspect tensor versions/pointers/structure and file metadata, not
cryptographic GPU tensor contents. Failed state guards suppress selections.

The default serializer fails if any query lacks candidates. Explicit
`--fallback copy-input` can produce a format-complete partial bundle; that is
not a completed scientific run. Invalid raw answers are never repaired.
Invalid-but-returned views do not themselves make the unchanged algorithm
incomplete. `all_generated_answers_valid`, `all_planned_calls_returned`, and
`candidate_coverage_complete` are separate diagnostics. A nonempty valid pool
still receives all eight NLL conditions. `whole_comparison_complete` additionally
requires full protocol completion, a valid candidate for every query, completed
isolated evaluation, and verified original-clock closure. All-invalid queries
remain unsolved/fallback, never fabricated model predictions.
An evaluator or whole-clock failure cannot produce final completed-run evidence.
A standalone evaluator invocation also inherits the original dispatch deadline,
not a fresh evaluation budget. No network, provider, competition submission or
publication is performed by any command.

## Minimum portable source closure

Copy the exact files listed by `core.source_identity()['files']`. That inventory
includes this package and the public-only dependency modules. Do not include
historical/private packages, denied materials, model weights, evaluator gold,
logs, or generated outputs. Model files must already exist and match all eight
unchanged `tools.public_sft141_diagnostic.model_pins.MODEL_FILES` size/SHA pins.
The controller writes `challenge.json`, `plan.json`, `dispatch.json`, raw worker
receipts, exited seal, `analysis.json`, and completion records under the new
run directory. The separate output directory holds `submission.json` and
`closure.json`. Optional evaluator reports remain controller-owned.

## Validation and preserved evidence

The scoped unittest suite exercises dynamic inventory, exact LOO masks and
weighting, all three same-pool ranks, synthetic complete/partial execution,
real subprocess failures/hangs, owned escaped-descendant cleanup with an
unrelated-process negative control, independent outer-watchdog interruption,
immutable raw replay, full-denominator evaluation, and CPU tensor full-EOS loss.
CPU tensor tests require an existing Torch installation; ordinary tests do not.
No test loads the public model or establishes GPU effectiveness.

The separately supplied static public challenge has 120 parents, 167 queries,
359 demos, 2872 LOO calls and 1336 generation views. Its largest full LOO envelope
is 7464 tokens and largest generation envelope is 9331, so 10240 covers the
static tokenizer lengths, not measured GPU memory/runtime. Original public12
results remain 15/15 for vote and NLL over 120 views with no observed gain or
headroom. The separate 137-program CPU grammar search remains 0/167 and is not
promoted or included in this integration. No denied Library material was read,
rebuilt, or transferred.
