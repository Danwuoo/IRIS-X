# MATH-002 developer/research handoff

## Current delivery: independent-review repairs, 2026-10-19

**MATH-002 remains unfinished; research is `not_estimable`. Engineering is
`review_ready`, not independently verified.** Repair code is `fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`,
based on delivery `fb5cc667a2971f53a3fe3a6c387b02a0ff08f3fa` and reviewed code `d6e4309607936b66d34573350b9697e5fddc7b0f`.
Delivery SHA is supplied in the final response and PR10. This code was not sent
to Kaggle. Plan/task scope and acceptance controls are fixed in the code commit;
the following delivery records evidence and updates metadata only.

The [independent review](independent-review.json) preserves the published original
review and its negative outcome: Linux CPython3.13.5 normal/-O each 48 tests,
38 passes/10 failures. Its API state is COMMENTED; the body requests engineering
changes. The original reviewer private tests were not obtained. New developer
reproductions and corrected controls are separate records, never overwritten
versions of that independent failure.

| Finding | Repair and positive/negative controls | Current local self-test result |
| --- | --- | --- |
| M002-R1 | Reparse model text; all modes bind exact proof UTF-8 bytes, immutable statement and coherent accepted/status/proof/trust receipt. Keep find-answer answer/spec/witness binding. Matched receipts pass; stale hashes, altered body/text/statement, contradictory flags and answer bindings fail in controller and analyzer. | [R1 receipt](review-repair-r1-tests.json): 20 normal + 20 optimized, all pass, exit0. |
| M002-R2 | Shared schema; mandatory count is non-bool nonnegative int, time finite/nonnegative. Analyzer revalidates raw values independently of both complete flag and cached validation. Missing/NaN/negative/bool/partial/timeout/overflow stay incomplete; valid components remain lower bounds. | [R2 receipt](review-repair-r2-tests.json): 19 new + 45 controller + 20 answer tests per mode; 168 executions pass, exit0. Pre-fix five failures remain recorded. |
| M002-R3 | Preserve historical terminal/output evidence; source/version/status failure sets a sticky current-dispatch guard. reserve refuses uncertainty; only complete matching readback clears it. Includes retrieve failure, legacy observation_error, malformed versions/status and terminal contradictions. | [R3 receipt](review-repair-r3-tests.json): 47 normal + 47 optimized pass, exit0; all provider calls mocked, state temporary, real state protected by audit hook. |
| M002-CI1 | Admit only Python within exact round001/round002 directories; keep AST/archive/other executable restrictions. Inventory and commit gate require math test coverage. Five stdlib/mock files join public line-b; native adapter stays protected before import. | [CI1 local receipt](review-repair-ci-tests.json): line-b 163 per mode, all pass; runner31 and gate30 per mode pass. Repository18 per mode retains one missing-archive-tag failure per mode. |

Counts are test-method executions, include parameterized positive/negative
controls, and overlap between focused tests and the full line-b suite. They are
not unique scientific cases. Windows11/Python3.12.10 used controlled `-P -s -B`
startup (plus `-O` for optimized); effective PYTHONHASHSEED=0 was observed.
Local suite snapshots are development/attestable=false/target_commit=null;
their exact byte hashes are retained. [Source/preservation binding](review-repair-preservation.json)
maps working bytes to the code commit without changing old receipts.

The only real Lean recheck used existing restricted constants: WSL Ubuntu24.04,
Python3.12.3, Lean4.19.0; 7/7 controls, **5 actual candidate Lean processes**,
isolation19/19, host exit0. Worker/config/runtime/bwrap hashes and the five child
exit codes are separately recorded in the R1 receipt. No extra Mathlib, source
panel, model or unrestricted Lean program ran. This is local kernel evidence
for those controls only; scripted receipts are not kernel evidence.

The old integrity failure is retained, not relabeled: PR run39201053930,
job117893912538, comparison target e92f5c748d24af7c8ca8ae2cf11a41f50df2f199,
15 tests/1 failure. Local validation no longer reports the original twenty-two
math executable admission issues; the local checkout still lacks
archive/pre-product-transition-2026-09-17 and
therefore preserves one repository failure. No tag was fetched/created/moved,
no integrity assertion disabled. See [new exact-target CI readback](review-repair-ci-readback.json)
for actual new run/job/target results; a whole workflow failure is not hidden
when the protected audit step stops. Audit/aggregate bodies remain unexecuted.

New PR workstream run **39209591512** finished: all 34 jobs were retrieved,
28 success / 6 failure. All four line-b jobs pass **163 tests** each; all four
integrity jobs report **18 tests / 1 failure / exit1**. The failing test remains
`test_repository_check.RepositoryCheckTests.test_active_repository_is_valid`.
In total, 24 public jobs and four formal jobs pass; gate117921764493 fails on
the four integrity reports, and the audit job stops before checkout/import.
Navigation39209591576 passes; offline39209591532 stops the protected aggregate.
The actual comparison target is **a5b2795fb91ea8b5ab6a7ce5efbe6623a3496812**;
its tree **7fcf40bbb885219fcc1f1bd5b6141ebc5dc4ac17** equals the code tree.
This temporary PR comparison commit is not a merge performed by this task.

Integrity artifact12166709338 (ZIP SHA256
`5aad3ab24e181393d5ca4c5211dde40ddc03c12d9e30e273ba4c141d7846e70d`)
confirms the single failure ID and unchanged source, but does not contain the
assertion traceback. The exact remote archive-tag API returns404; together
with the local direct diagnosis this supports the missing-tag explanation.
The CI assertion's full issue list was not observed, so that explanation is
an inference, not a fully captured remote traceback. Integrity and gate remain
failed; no historical prerequisite was bypassed to make them pass.

**This repair performed zero Kaggle operations.** The original state, heartbeat,
stopped-monitor record and smoke manifest have identical before/after hashes.
Only attempt m002-smoke-20261019-a7f91c remains submission_unknown/version null,
notebook danielwuu/irisx-math-m002-20261019-a7f91c, reserved **1/4 and
1800/21600 seconds**. No new ledger, refund, push, cancel or reconcile occurred.
Historical batch-capacity/403/HTTPError observations below were not freshly
retested. No monitor is running. Platform/permission changes must be handled by
the owner; a later read-only reconcile belongs to the original research scope
and needs its own receipt. Unknown identity still forbids dispatch. Preserve the
reservation; recover exact private source/version/status and verified outputs
before considering any later run within the original budget.

Independent review must recheck the exact new code plus delivery, R1/R2/R3
counterexamples and CI1 admission/inventory/gate changes; kernel trust and
isolation on Kaggle, target v5e-8/model parity/cost, faithful source/panel admission,
context policy/freeze and paired efficacy remain unverified. R001, MATH-001,
WSF-R5, prior JSON evidence, ARC/product source and workflow bytes are unchanged.

## Prior implementation and evidence (retained history)

Return this handoff to the original ChatGPT conversation for independent review.

- Branch: `feat/math-proof-agent-20261018`; Draft PR: https://github.com/Danwuoo/IRIS-X/pull/10 (base `develop`).
- Starting SHA: `0deff2254d2e3b63b88c2eefc4c4f73856663047`.
- First smoke packaged runtime SHA: `ae051a79359c4e0be9658d89452c05793d64d831`.
- First delivery SHA: `3fcb8410a4bf8dacb374e3cb3d42e7b881314af2`; later offline corrections do not alter that submitted snapshot.
- Previous offline delivery SHA: `8ba60f78cd96a7fedda0d05d730dd3d62027f4a0`; its reports remain historical.
- Prior independently reviewed offline code SHA: `d6e4309607936b66d34573350b9697e5fddc7b0f`; not submitted to Kaggle.
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
with an unrelated proof. This was found before any target-model scoring; the
first offline correction blocked all `find_answer` execution. The latest version
adds a narrow `closed_exists_nat_v1` route: a fixed `_root_.Exists.intro` wrapper
selects the reported canonical Nat as witness of the unchanged original theorem.
Restricted proof body proves its remaining property, and final transitive axiom
audit includes that proof. Controller, evaluator and analyzer recheck exact
candidate/proof, statement, binding spec and normalized answer hashes. Optional
private keys only check consistency after selection; disagreement blocks a joint
conclusion. Unsupported declarations/types still block before generation. The
source's original proposition must express the complete task; no weakening is
allowed to fit this interface. Authored Lean controls establish the engineering
path only; no actual source statement or scoring panel has been admitted.

A failed trust/binding check can no longer inherit `accepted` from a tool's
status field. Registered null binding cannot fall through to the proof-only
route. A pair with either arm lacking generation is explicitly a
`no_generation_pair`, never a measured tie/gain/loss.
Context 8192 cannot fit a 4096-token prior candidate, base/feedback and 4096 new
tokens: pinned-tokenizer measurements confirm 9209 tokens even for the shortest
authored repair case. A 2048 common ceiling is a candidate, not an adopted policy;
one 64-parameter/4000-character-feedback case leaves only 56 tokens. Exact prompt
capacity, a registered feedback/overflow rule and actual TPU prefill cost still
need qualification before freeze. No arm receives silent truncation or a special cap.
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
| [answer-binding-tests.json](answer-binding-tests.json) | same WSL Lean and measured isolation; authored closed Nat witnesses | final44/44 admission/verification controls (6 actual Lean), helper7/7, isolation19/19; core7/7, parser13/13, mathlib10/10; exit0 |
| [answer-pipeline-tests.json](answer-pipeline-tests.json) | controlled Windows normal/-O; new20 answer-flow tests plus unchanged45 | 130 executions passed, exit0; scripted receipts only, including altered bindings and no-generation pairs; earlier124/126 retained |
| [context-tests.json](context-tests.json) | both exact pinned public tokenizers/configs, CPU only | 23 controls / 34 observations, exit0; no weights, generation or TPU |

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

During the answer-binding regression, accidentally concurrent core/mathlib
checks exhausted thread creation: five candidate exits1 and a version probe
exit134 are retained as infrastructure failures. Their apparent negative
matches are not semantic-control passes. The worker now recognizes the observed
thread failure and runs the version query with `-j1`; final Lean checks ran
sequentially. Final answer controls used 6.336 seconds wall / 5.344 seconds
preflight; final mathlib regression used 13.519 seconds. New reports preserve
intermediate successes as well as failures. Pinned tokenizer/config acquisition
was 22,866,285 bytes / 21.344 seconds; latest cache-only context run was 3.203
seconds. These are local costs, not target-model inference or TPU consumption.

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
The third goal continuation again ran `reconcile`: wrapper exit0, underlying
SDK readback exit2/HTTPError, version still null. This helper does not expose a
new HTTP status, so HTTP403 above refers to the earlier captured response.

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

The [third source audit](../../../research/math-proof-agent/round002/source-feasibility-audit-03.json)
found proof-named fields with unknown contents and no verified statement-only
projection for miniF2F-v2c. Some source answer slots also differ from a fixed
existential proof-body interface. No bulk dataset or reference-proof archive
was acquired. A methodology-paper search incidentally exposed an example answer
for `amc12b_2021_p3` to the audit agent; its value is not reproduced or sent to
any solver, and no panel was selected or changed. This is recorded exposure,
not a claim that the audit saw no answer content.

Remaining blockers are the batch TPU slot/403/unknown submission, exact reviewed
source admission and compatible runtime, real-panel answer binding and feasible
repair context, actual Kaggle isolation/Lean controls, actual v5e-8 model
parity/performance, panel/model freeze and paired experiment. No
SFT/RL/TTT/LoRA/distillation/synthetic SGD or paid/model API call occurred.

## Safe recovery under the original research task

The current engineering repair does not authorize these Kaggle commands. Resume
only under the original task scope after an actual platform/permission change;
record the new readback separately and preserve unknown reservations.

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
