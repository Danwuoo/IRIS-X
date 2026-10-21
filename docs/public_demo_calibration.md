# Public demonstration-calibrated D4 ranking

## Status, scope, and the actual question

This is fresh public-only research code in `tools/public_demo_calibration/`,
not a notebook update, a GPU run, a private implementation reconstruction, a
fine-tuning method, or a capability result. The unchanged public base is commit
`afb2dfaa3a5c3f6e09338fd38487e29f77a0c47c`; this module uses its independently
implemented grid codec, native-Qwen3 backend, and exact public model pins.
No private Library material, private checkpoint, evaluator, or old private
pipeline is imported. No SFT141/2B-family or GPU execution was performed while
implementing this module. Its tiny CPU tests are validation, not ARC results.

**Hypothesis:** visible demonstrations may supply a task-local signal for
weighting the eight D4 generation views. Once calculated, weights can be reused
for every true `task.test` query of that task, replacing candidate-specific
rescoring with a weighted vote over the identical inverse-transformed pool.
This can be cheaper than eight-view rescoring, but need not be cheaper or better.

Held-demonstration likelihood is **only a within-task, label-visible calibration
signal**. It is not a replacement for true `task.test` effectiveness or evidence
of generalization. A low loss may measure formatting, output simplicity,
confidence, or model familiarity rather than actual view reliability. Supports
and LOO conditioning sets overlap. Eight views are strongly dependent. The
reported effective view count describes concentration, not an independent
sample size. No statistical reliability or gain is inferred from it.

The public source is official ARC-AGI-2 commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`, and the original public model is
`sorokin/qwen3_2b_grids15_sft141/transformers/bfloat16/1`.
Public-data exposure is possible; neither this panel nor its later scores are a
clean holdout or official competition result. The base documentation describes
additional native-Qwen3 versus author mRoPE compatibility limitations.

## Frozen method, before viewing any test labels

For a task with `n >= 2` visible support pairs and each view `v = 0..7`:

1. Hold out support `i`. Condition on **all other** support pairs in original
   order. Transform their inputs and outputs, held input, and held target by
   the same D4 view. Never use another query's output as conditioning.
2. Teacher-force the complete transformed held output, **including EOS**.
   With prompt length `p` and answer length `a`, the model input is
   `prompt + answer[:-1]`; score logits at `[p-1 : p-1+a]` against all `a`
   answer tokens. Prompt targets and padding never enter loss.
3. Let `L_iv = summed_NLL_iv / a_iv`, then `m_v = mean_i L_iv`. This is an
   equal-support arithmetic mean of per-token loss, not a token-weighted pooled
   average. It avoids allowing a larger visible output to dominate the task's
   calibration, and handles the different newline counts of rectangular views.
4. Fix `T = 1` without result tuning. Compute
   `w_v = softmax(-(m_v - mean_u m_u) / T)` in stable arithmetic. Implementation
   subtracts the minimum loss before exponentiating, an algebraically equivalent
   maximum-logit shift. Report all means, individual support losses, weights,
   ESS `1/sum(w_v**2)`, min/max/range, and support/view coverage. If floating-point
   underflow would set any view weight to zero, fail back to uniform rather than
   silently suppress that view. No top-k views or weight threshold is used.
5. Before generating any true query, freeze calibration receipts and their hash.
   Generate using the **unchanged full-support** prompt, fixed original order,
   all eight D4 views, native greedy decoding, and the base 931-token ceiling.
   Strictly parse EOS-terminated grids, inverse-transform, and deduplicate.
6. Uniform anchor: rank by descending occurrence count. Candidate: rank by
   `sum(w_v for views v producing that canonical grid)`. Both have the same pool;
   exact ties use ascending compact-JSON canonical grid keys, just as the base
   uniform anchor. Output full rankings and the first two unique grids. There is
   **no candidate likelihood mix** and no optimizer or model update.

This calibration normalization deliberately differs from the original candidate
score `count - mean_v(sum answer NLL)`. That original score assesses each query
candidate under all eight full-support prompts; it remains an unchanged, separate
comparison arm. The new loss estimates task-local view weighting from visible
supports, and is not a reimplementation or normalization change to that arm.

A single-demo task has no valid nonempty LOO conditioning. It performs **zero**
calibration forwards, uses explicit `single_demo_fallback` status and eight
uniform weights, and retains the original full-support generation. Missing,
failed, late, or partial calibration anywhere in the frozen bundle cannot
promote a weighted result, even if some tasks already finished. A partial query
pool also falls back, with missing views explicit. Invalid completed generations
remain invalid, do not vote, and their weight is not redistributed. They do not
justify replacing tasks, views, or support pairs.

The synthetic counterexample test has three canonical candidates with counts
4, 3, and 1. Visible-support mean losses `[10,10,10,10,2,2,2,0]` make the weighted
top two exclude the plurality candidate. If that plurality candidate is the
synthetic true output, uniform top-2 succeeds and calibrated top-2 fails. This
is a valid failure mode, not a claim about real tasks.

## Boundaries, receipts, and low-memory execution

`plan` and `rank` accept only the base gold-free 12-parent plan. Test records
must contain exactly input, original test index, and query ID; test outputs,
label metadata, unexpected fields, duplicate JSON keys, and nonfinite numbers
are rejected. The ranking CLI never imports an evaluator. File SHA-256 pins are
mandatory for plan, calibration, and pool files. These are integrity bindings,
not authentication or proof that an external model really ran.

Each LOO receipt binds the plan/protocol/public-model identity, session, held
pair/input/output hashes, every conditioned support index and pair hash, view,
complete prompt/answer/model-input token hashes, causal loss-mask boundaries,
EOS inclusion, actual processed token counts, forward count, elapsed seconds,
and available memory readings. A wrong held-output association or mask fails
closed. Every generation receipt binds all support indices/hashes and the exact
true-query input, view, raw output tokens, event order, and calibration hash.
There is no mutable cross-task cache: one immutable task-local calibration
bundle supplies reusable weights for its bound queries only.

`runtime.collect` actually invokes `backend.score(prompt, answer, deadline)`
sequentially, with batch one and `use_cache=False`, never retaining a set of
logits. It freezes parameter gradients, requires eval mode, checks tensor
versions/pointers/shapes before and after each forward, and saves exclusive,
atomic per-attempt receipts. The version guard catches ordinary mutation but is
not a cryptographic attestation against malicious `.data` writes. The actual
backend uses `torch.inference_mode`; there is no optimizer or backward pass.
No quantization/offload/adapter substitution is allowed by the public backend.
This reduces adaptation-state memory, not the base model's weight/activation
requirements. A 6 GB fit is **not established**.

The explicit `run-calibration` command verifies all eight exact public model
files, validates the actual tokenizer against every full and LOO prompt/target,
and then uses the published `TransformersBackend`. It does not generate query
candidates or run an evaluator. Initial context admission checks **every** full
query prompt plus 931 tokens and **every** complete LOO answer. The loaded
model's smaller declared context is checked again; no cropping or support
omission is permitted. A monotonic clock starts before preflight/load. A parent
watchdog owns and may kill only its single leaf at the original work deadline,
leaving a closure reserve. Successful, failed, and interrupted receipts remain
saved; absent failure counters stay unknown, not zero. The controller reconciles
aggregate rows against atomic receipts; any mismatch forces partial status and
retains validated per-forward cost accounting rather than dropping saved work. No resume/reset path is
provided. Before a future paired experiment, its owner must integrate this stage
with generation, original rescoring, and post-exit evaluation under **one**
whole-session clock, not stack independent 7,200-second budgets.

Real controller/leaf admission pins canonical plan SHA-256
`cc795e7475cb689714b34fb5f10802c23f51a2534dcf50121774a56750c31069`
(the existing file-byte SHA-256 is
`bafeabeae62625171147645d166b524e3f008fdbf5e44164c0ed8c41498e9c1c`).
Reformatting can change a file-byte hash but cannot change the canonical plan
identity; CLI file-byte pins must still match the actual supplied bytes.

The CLI is implemented for later authorized execution; its presence is not
permission to run it. This work did not invoke `run-calibration` on real weights,
start GPU/local SFT141 execution, update a notebook, publish a dataset, or alter
the frozen QuickSave candidate.

## Cost accounting, not an automatic speedup claim

For `n >= 2`, calibration uses exactly `8*n` completed teacher-forced forwards
per task, reusable across its `q` test inputs. Original same-pool rescoring uses
`8*sum_j K_j` forwards, where `K_j <= 8` is each query's unique valid candidate
count: up to 64 per query. A one-candidate task with two supports costs 16 versus
8 forwards, so the proposed ranker can cost **more**. Forward counts alone also
hide prompt/answer length differences.

The report sums actual calibration input tokens `p+a-1`, scored targets `a`,
recorded seconds, and peak allocated bytes when available. It computes exact
**counterfactual** original rescoring input/target token counts from the same
observed pool and every full-support view. It reports shared generation calls,
prompt/output tokens, and recorded seconds separately, without pretending these
are all transformer forward calls or FLOPs. Failed/missing work makes totals
lower bounds. Counterfactual original-rescoring GPU seconds and any GPU time
saving remain `null` until actually measured. Uniform voting adds no forwards;
its calibration overhead is not hidden. Memory/kernel latency, setup/load,
serialization, invalid generations, and admission must be reported in a real
end-to-end comparison.

## Frozen paired true-test evaluation protocol

Before execution, freeze this method/source hash, the original base source,
public model file pins, the **same existing 12-parent panel** and its order, all
true `task.test` inputs, context/time budget, and complete query denominator.
Reuse the base label-free four-length-quartile/three-hash-per-quartile selection
and its predefined multi-query rule. Do not select a fresh easier panel or
rerun selection after any labels or outcomes. The real `run-calibration` controller and its leaf both require the exact
canonical public plan hash recorded below, before model loading, so neither
changed supports nor changed queries can replace this panel. The separate
owner/evaluator must also preserve and verify the original material manifest
for paired evaluation. Pure `plan`/`rank` can accept synthetic supplied plans
for mechanics tests; that does not confer scientific admission.

Execute one calibration and one shared eight-view generation pool. Freeze the
pool, then compare: A unchanged uniform vote; B original count-minus-mean summed
NLL under all eight views; C this fixed calibrated vote. B's extra forwards are
measured separately. C cannot generate extra candidates. Stop model ownership
and seal predictions before an isolated evaluator opens gold. No label-based
hyperparameter, temperature, fallback, threshold, view, or panel tuning.

Use full-denominator query-micro pass@2 as the primary adoption outcome,
matching the [official 2026 Kaggle evaluation rule](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2):
successful task test outputs divided by all task test outputs. Report micro
pass@1, task-macro pass@1/pass@2 (equal parent weight), and all-queries-solved
task rates separately. Task-macro is a secondary sensitivity measure, not a
replacement for the named competition metric. This preregistration correction
was based on the published rule, not result labels or outcomes; existing
diagnostic recipes/results are unchanged and already distinguish both measures. Missing/failed outputs count
as failures, not excluded rows. Report A/B/C paired query wins/losses/ties,
unique-pool oracle coverage, invalid/missing views, and absolute numerators and
denominators. Uniform fallback counts are disclosed. An incomplete run is
inconclusive and cannot qualify for adoption, even if a completed subset wins.

Preregister this decision rule for the one panel, without altering it after
results:

- Retain A by default. A candidate C signal requires positive full-denominator
  query-micro pass@2 gain over A and no query-micro pass@1 decrease. Report the exact gain and regressions.
- Do not call a small query-level difference statistically established. Report
  an exact **parent-cluster** sign-flip randomization test on each parent's
  pass@2 raw success-count difference, enumerating all `2**12` sign flips, two-sided
  `p = fraction(|permuted total| >= |observed total|)`. Zero-difference parents
  remain in the panel. Parents with more queries contribute their larger raw
  count difference, matching the official query-micro weighting. This is a descriptive paired test conditional on
  exchangeability, not proof that public tasks are IID or unseen. Mark low power
  and possible exposure. An adoption recommendation requires `p <= 0.05` as
  well as the practical/cost conditions; otherwise the result is exploratory.
- To call C a cheaper replacement for B, require complete measured extra-ranking
  wall time and processed-token cost for C to be lower than B, without lower
  full-denominator query-micro pass@2. Report C's actual additional time versus A, not just
  its savings versus B. Both CPU ranking time and calibration forwards count.
- Every arm must fit the frozen whole-session/context/memory constraints. If C
  does not meet these rules, retain A and report the failed hypothesis. Even a
  qualifying public-panel signal is a reason for independent future validation,
  not a clean-generalization claim or automatic production promotion.

No evaluator is implemented/imported here, and no paired solve/cost observation
exists yet. Unit passes, preparation, accepted saves, and provider completion
cannot satisfy these scientific requirements.

## Offline CLI and validation

Run from the repository root. SHA values below are actual file-byte SHA-256s
frozen by the owner, not canonical-object hashes inside receipts. Output files
and directories must be new. Store generated private/local outputs outside Git.

```text
python -m tools.public_demo_calibration plan --plan PLAN.json --plan-sha256 PLAN_SHA --output PLAN_RECEIPT.json
python -m tools.public_demo_calibration rank --plan PLAN.json --plan-sha256 PLAN_SHA --calibration CALIBRATION.json --calibration-sha256 CALIBRATION_SHA --pool POOL.json --pool-sha256 POOL_SHA --output RANKINGS.json
```

The later explicitly authorized calibration-only runtime entry is:

```text
python -m tools.public_demo_calibration run-calibration --plan PLAN.json --plan-sha256 PLAN_SHA --model-dir ORIGINAL_PUBLIC_MODEL --output NEW_OUTPUT --budget-seconds 7200
```

Tests use synthetic gold-free tasks, numerical tensors, and a tiny random CPU
module only. They cover causal alignment and EOS, stable weights, exact original
support order, source/output binding, one-demo fallback, partial work, context
and time rejection, strict frozen files, same-pool canonical ties, mutation
checks, no evaluator import, and counterexamples to both improvement and cost.

```text
python -m unittest discover -s tests -p test_public_demo_calibration.py -v
python -O -m unittest discover -s tests -p test_public_demo_calibration.py -v
```

Use the existing CPU Torch environment to exercise the real tensor tests;
without Torch those tests are explicitly skipped, not a numerical pass. Set
`PUBLIC_DEMO_PLAN_PATH` to the already materialized gold-free `plan.json` to
exercise the exact actual-public-panel admission test without loading a model;
it is explicitly skipped when that file is not supplied. No
package installation or network access is part of these tests. These scoped
checks are not a claim that the repository's entire historical suite is green.

## Preparation-only observation on the existing panel

The existing gold-free plan has 12 parents and 15 true test queries. Its
canonical plan SHA-256 is
`cc795e7475cb689714b34fb5f10802c23f51a2534dcf50121774a56750c31069`.
Without opening evaluator gold or executing any model, planning computes 256
LOO forwards, 479,832 LOO model-input tokens, and 80,756 scored target tokens.
The longest LOO model input is 3,419 tokens; the longest unchanged full-support
query prompt is 4,356 tokens. All planned contexts fit the declared 8,192 cap,
not a measured GPU memory limit. The shared pool needs 120 generation calls;
original same-pool rescoring is at most 960 forwards, with its actual count
unknown until the number of unique valid candidates is observed. GPU seconds,
actual fit, solve rates, and ranking gain remain unknown.

The 12 support counts in frozen panel order are
`[2,3,2,2,4,3,3,3,2,2,3,3]`, totaling 32. LOO prompt tokens total 399,332;
shared generation prompt tokens total 299,152. Conservative LOO context
(including its final target) peaks at 3,420; full query context including the
931-token generation allowance peaks at 5,287. Per-task reuse amortizes the
calibration to 12, 16, or 24 forwards per true query, averaging 256/15 = 17.07
across the panel. Original rescoring can use 0..64 per query: zero when no valid
candidate exists, eight when there is only one, and 64 for eight unique grids.
No unknown candidate diversity is assumed to establish a speed advantage.
