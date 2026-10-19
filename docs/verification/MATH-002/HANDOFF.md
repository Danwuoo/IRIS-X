# MATH-002 developer/research handoff

State is `review_ready`, with scientific and remote blockers. This is implementer
self-review, including implementing subagents; no independent verification.
Return this handoff to the original ChatGPT conversation.

- Branch: `feat/math-proof-agent-20261018`; Draft PR: https://github.com/Danwuoo/IRIS-X/pull/10 (base `develop`).
- Starting SHA: `0deff2254d2e3b63b88c2eefc4c4f73856663047`.
- First smoke packaged runtime SHA: `ae051a79359c4e0be9658d89452c05793d64d831`.
- First delivery SHA: `3fcb8410a4bf8dacb374e3cb3d42e7b881314af2`; later offline corrections do not alter that submitted snapshot.
- Current offline code SHA: `6eb0c1e242fda087f46024307f505aaee74cede4`; not submitted to Kaggle.
- Delivery SHA: supplied by the final response and PR after this document's commit; no self-containing SHA is embedded.
- Actual desktop checkout: `C:\Users\wurre\Desktop\IRIS-X-Math`.
- Windows task venv: `.irisx/line-b/MATH-002/venv/`; optional numerical-control venv: `adapter-venv/` under the same task root.
- WSL task-owned Lean scratch: `/home/wurre/irisx-math-m002-lean-20261019`; repository remains on the actual Windows desktop.

The desktop was resolved through `[Environment]::GetFolderPath('Desktop')`.
No applicable ancestor AGENTS existed. Clone was full-history, specified branch,
with LFS smudge skipped only in the clone subprocess. Origin, branch, worktree
and clean status were checked before `git fetch origin` and the requested
`git pull --ff-only origin feat/math-proof-agent-20261018`. Known delivery was
confirmed an ancestor and HEAD was unchanged. No reset/clean/stash, global
Python/Git configuration, merge, force-push, tag or other branch write occurred.

## Delivered implementation

The [single plan](../../plan/2026-10-19-math-proof-agent-round02.md) records the
new owner scope, distinct from historical MATH-001. The [round002 guide](../../../research/math-proof-agent/round002/README.md)
routes one adapter, restricted Lean worker, bounded controller, events,
evaluator/analyzer and task monitor. Task/catalog use existing line-b IDs and
the original renderer. Original six-case fixture, R001 evidence and historical
acceptance records are unchanged.

The candidate model file pins full revisions, tokenizer/template and public
file hashes; JAX/libtpu, Transformers CPU reference and dependency versions are
explicit. Actual local numerical checks are eight virtual CPU devices, not TPU.
Lean worker fixes statement fields and final theorem, parses restricted proof
bodies, measures Linux isolation, limits resources and checks final transitive
axioms against `{propext, Quot.sound, Classical.choice}`. `sorryAx`, arbitrary
axioms and unqualified/native trust expansion are rejected. Compile exit0 alone
does not accept. Local qualification now includes Lean core and the pinned
Mathlib v4.19.0 Ring/NormNum transitive import closure, within a separate 4 GiB
worker configuration. It does not cover all Mathlib, other benchmark versions,
the Kaggle host or arbitrary Lean code.

Controller permits 1/4/4 generations, <=4096 completion tokens each, common
SAMPLE/REPAIR ceilings, stop on success, exact statement binding and limited
compiler feedback. Actual prompt/output/tool/compile/wall costs are retained.
The follow-up audit closed nested statement metadata leakage by reconstructing
every solver-facing field, and added actual source/model/verifier/panel binding.
Scoring identities use explicitly named semantic hashes; the first smoke's
raw-file hashes remain historical and cannot be used as a scoring identity.
The trusted committed-source execution manifest must match code/source identity.
No scoring manifest or scoring runner has yet been qualified.
Missing/timeout/error cases
remain planned denominator entries. Automatic partial-generation resume is
disabled until explicit snapshot/identity/budget reconciliation.

The first controller/evaluator could combine an independently correct answer
with an unrelated proof. This was found before any target-model scoring.
`find_answer` now stops before generation and `joint_rate` is null pending a
reviewed kernel-checked answer/witness binding. This is an unfinished capability,
not an efficacy failure. Context 8192 also cannot fit a 4096-token prior candidate,
base/feedback and 4096 new tokens: the common output/context budget needs measured
qualification before freeze. No arm receives silent truncation or a special cap.
No-generation blocked records retain their planned denominator with null proof
rate and `not_estimable`; completed model failures must not be removed.

## Actual checks

| Report | Environment / command surface | Outcome |
| --- | --- | --- |
| [baseline-tests.json](baseline-tests.json) | Windows11/Python3.12.10; controlled `-P -s -B`, normal/-O; five named safety files and R001 | 208 tests total, zero failures/errors/skips; 64 R001 case executions with unchanged 12/16/4 decisions per mode |
| [controller-tests.json](controller-tests.json) | task venv `controls.py`, normal/-O | 19 each, exit0; scripted control only |
| [remote-controls.json](remote-controls.json) | `test_remote_controls.py`, normal/-O | final28 each, exit0; all mocked/no provider calls |
| [adapter-tests.json](adapter-tests.json) | optional CPU venv `test_model_adapter.py`; fixed tiny random tensors | 9/9, exit0; short greedy tokens and bounded logits match pinned Transformers |
| [lean-tests.json](lean-tests.json) | WSL Ubuntu24.04/Python3.12.3, Lean4.19.0, Lake5.0.0-6caaee8, bubblewrap0.9.0 | parser13/13, isolation19/19, actual Lean7/7; final exit0 |
| [adapter-followup-tests.json](adapter-followup-tests.json) | same CPU venv, model-byte/spec/context/partial-cost controls plus numerical parity | 16/16, exit0; no pretrained model/TPU execution |
| [controller-followup-tests.json](controller-followup-tests.json) | controlled normal/-O; exact final source hashes in report | final45 each, exit0; identity/leak/timeout/cost/joint/denominator regression; original19 report and intermediate42 preserved |
| [mathlib-tests.json](mathlib-tests.json) | WSL Lean4.19.0, mathlib `c44e0c8ee63ca166450922a373c7409c5d26b00b`, 4 GiB | 10/10 controls (7 Lean processes, 3 pre-execution rejections), isolation19/19; separate synthetic exit6/6; exit0 |

Reports retain commands, exact source file hashes, necessary environment
allowlists, costs and limitations. Local checks ran on working bytes before
commit; Windows JSON newline conversion means raw Git blob hashes can differ.
The remote package exclusively uses committed Git bytes and its own manifest.
No report pretends a previously nonexistent Git commit was the execution cwd.

Preserved failures: initial Lean controls used an unsupported `-T` switch and
failed before corrected attempt02. Adding fresh notebook slugs made six old
mock expectations fail (5 failures/1 error); fixtures and explicit new gate
controls produced final28/28. Original reports/logs remain in ignored storage.
The original aggregate, ARC audit/training/native/reconstruction, full CI/OS
matrix and independent WSF-R5 acceptance were not run or promoted.

Mathlib's first 2 GiB attempt produced seven wrapped child exits139 with empty
diagnostics. Those are infrastructure failures, not mathematical negative
controls. The separately recorded 4 GiB attempt passed; final control wall was
22.442 seconds, including 14.350-second preflight and 8.042-second candidate
Lean cost. Worker now classifies both negative signals and bubblewrap's
128+signal exits as infrastructure_error. General-purpose upstream mathlib
source archive included non-runtime Archive directories; these were not opened
as benchmark proofs. Only the explicit Mathlib/Cache/config allowlist and
locked dependencies enter the worker, with Ring/NormNum cache closure. See the
receipt's precise source-scope note; this is not a claim that every upstream
archive byte is a statement-only benchmark artifact.

## Actual Kaggle submission and stop

CLI `2.2.4`; existing authentication successfully listed owned notebooks;
`kernels init` produced metadata for account `danielwuu`. Inspected push/status/
pull/output/logs help and source, including the latest-only status/log/output
behavior despite accepted `/version`. Read-only SDK metadata preserves actual
`current_version_number`; source and privacy must match around latest reads.
Each subsequent attempt requires a fresh task slug and explicit budget check.

One submit command, after the code commit and exact notebook packaging:

```text
kaggle kernels push -p .irisx/line-b/MATH-002/staging --accelerator TpuV5E8 --timeout 1800
```

Notebook target: `danielwuu/irisx-math-m002-20261019-a7f91c`.
Run: `m002-smoke-20261019-a7f91c`; version **unknown/null**. CLI exit **0**, actual
response **`Kernel push error: Maximum batch TPU session count of 1 reached.`**
Exact task source returned **HTTP403**. Read-only owner search returned a private
placeholder without ref/version, so neither source nor session can be bound.
State remains **submission_unknown**, not successful, not confirmed_not_started.
No second push, other notebook operation or attempted quota bypass occurred.

[Sanitized run summary](run-summary.json) and [expected source manifest](../../../research/math-proof-agent/round002/run-manifest-smoke001.json)
contain all fingerprints. Reservation remains **1/4 submits, 1800/21600 seconds**
for the whole v5e-8. No unknown reservation was refunded. Actual TPU seconds,
devices, model/prompt/output tokens, compile/inference/remote Lean costs are
unknown. No bound output, checkpoint or terminal version was retrieved.

The bounded monitor was actually invoked and stopped immediately on unresolved
identity; `heartbeat.json` and `monitor-stopped.json` record this. No detached
monitor is running and no background continuation is promised. State and raw
receipts are at `.irisx/line-b/MATH-002/`; credentials are not copied to source,
notebook, datasets, outputs or Git. Raw receipts remain ignored.

## Research conclusion and blockers

[ROUND002-RESULTS](../../../research/math-proof-agent/ROUND002-RESULTS.zh-TW.md)
reports **not estimable**, not zero gain. There are no bound target-model
observations and no frozen scoring panel. The 24-question proposal remains a
proposal. Follow-up metadata research found attributable upstream human fidelity
reviews for miniF2F-v2c and ProofNet-Verified. The earlier assumption that the
owner must personally supply/review statements was too strong. Source admission
still needs exact statement-only acquisition, per-item review/provenance,
exposure/answer classification and the compatible runtime. ProofNet's Lean4.28
cannot inherit Lean4.19 qualification. Agent-authored controls were never
substituted or called human-reviewed. See [source feasibility notes](../../../research/math-proof-agent/round002/source-feasibility-notes.json).
Pure-proof tasks use not_applicable; answer-given tasks cannot count discovery.
PutnamBench remains conservatively excluded in favor of alternatives; its
no-public-proof request is explicit, whereas a universal requirement to contact
authors before private automated evaluation was our prior interpretation.

Remaining blockers are the batch TPU slot/403/unknown submission, exact reviewed
source admission and compatible runtime, qualified answer-proof binding and
repair context, actual Kaggle isolation/Lean controls, actual v5e-8 model
parity/performance, panel/model freeze and paired experiment. No
SFT/RL/TTT/LoRA/distillation/synthetic SGD or paid/model API call occurred.

## Safe recovery

First read the task state and raw push receipt; do not reset the ledger or
re-submit. From the desktop checkout, use the existing task venv:

```powershell
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py reconcile
.irisx/line-b/MATH-002/venv/Scripts/python.exe research/math-proof-agent/round002/kaggle_run.py observe
```

These commands only read remote state. Any login/terms/permission issue needs
the account owner; do not bypass or disturb another active TPU task. Only after
the exact target source/version and terminal state are established may the
current research task decide whether a new attempt is lawful and affordable.
Keep the first 1800-second reservation and original failures. Reuse immutable
downloaded weights if any are later actually recovered; none is currently
claimed recoverable. Before scoring, complete the formal/source/runtime gates,
freeze a revised feasible panel and protocol before viewing model answers, and
commit that code before packaging another run. Reviewers must independently
check this exact code/delivery; task state remains review_ready.
