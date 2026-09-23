# Second development acceptance review — 2026-09-23

Reviewed main: `4d23546` (`Normalize TRM saved tensors without evaluator truth`).
Verdict: **partial; complete development acceptance not passed**.
The earlier three concrete P1 examples and recursive DFS failure are repaired,
but independently reproduced budget and DDP failures remain. The TRM evaluation
adapter still does not implement the declared inference path.

This review inspects the existing continuation against the
[continuation plan](../../docs/plan/2026-09-23-qwen35-nvarc-acceptance-continuation.md).
It does not authorize or run an external experiment, change acceptance
thresholds, or claim real Qwen3.5/PEFT/TRM compatibility.

## Blocking findings

### P1 — Reservations can raise TTT/DFS limits above the bound configuration

Location: `src/irisx/arc_nvarc_runtime.py:270–285`.

`validate_checkpoint` recomputes generation/sequence/verification reservation
limits from the binding, but only checks that the DFS and TTT reservations are
nonnegative and sum to their own counters. An altered reservation can therefore
raise its own limit. The later observed-versus-reserved comparisons do not
repair this missing binding check.

Reproduction: keep the original fixture binding unchanged (`ttt: {}`), put
999 TTT steps and 9,999 training tokens into one completed record and its
reservation, reconcile counters and predictions, and correctly rebuild the
result ZIP. `verify_result` accepts it. No actual TTT was performed; this is a
synthetic acceptance of forbidden claimed work. The analogous DFS reservation
field is also not compared to the configured expansion ceiling in this code.

Required repair: independently derive every reservation field from the bound
configuration, require zero TTT budget when disabled, and enforce per-task as
well as aggregate observations. Add rehashed counter/reservation regression
cases, including disabled TTT and inflated DFS, plus legitimate failure/resume
records. Do not merely check that counters agree with each other.

### P1 — DDP fails with retained parameters unused by text-only training

Location: `src/irisx/arc_nvarc_distributed.py:79–80`, forward at line 133.

The DDP wrapper assumes every trainable parameter contributes to the loss.
Compact conversion retains vision modules; `load_compact_model` does not freeze
or remove them. Text-only SFT needs an explicit supported policy for such
unused branches.

Reproduction used the production `train_ddp` with two CPU Gloo ranks and the
existing tiny model plus a trainable `unused_visual` linear layer. Both ranks
failed on the second training step with `Expected to have finished reduction`
and unused parameter indices 3 and 4. This proves the backend failure under
the relevant unused-branch condition; it is not a real Qwen3.5 execution claim.
The existing collective regression uses every parameter and passes.

Required repair: define which retained branches are frozen/excluded from the
optimizer or support unused parameters correctly. Confirm language attention,
DeltaNet, embedding and head gradients are not accidentally disabled. Exercise
at least two optimizer steps, resume, and rank failure with a tiny unused-branch
model; then run the tiny actual architecture profile when its dependencies are
available. Preserve DDP versus model-sharding distinctions.

### P1 — TRM evaluate launch still enters a training loop

Location: `src/irisx/arc_nvarc_trm.py:125–145`.

`mode="evaluate"` invokes pinned `eval-arc-k-10.py`, emits `epochs={steps}`
and fixed `eval_interval=2000`, but requires only a test dataset. The pinned
source asserts epoch divisibility at line 569, unconditionally loads training
data at line 571, and calls `train_batch` before `evaluate` at lines 609/627.
Disabling its evaluator plugin prevents that plugin's truth access; it does
not remove the script's training path.

The adapter accepts a synthetic test-only processed directory and `steps=1`,
then emits a specification that fails the upstream divisibility assertion.
The source hash was independently checked against
`62ec1e2f179cd80c58a7f0067ab51c76e2e7eb213959566b015c107c5d98b36f`.
No upstream model command was executed. Even a divisible epoch count still
selects the train-then-evaluate path, rather than inference-only evaluation.

Required repair: implement a source-backed inference entry or explicitly split
and name adaptation-plus-evaluation with its own training inputs and budgets.
Do not silently train under evaluation authority. Validate argument semantics,
dataset/checkpoint binding and output production with a tiny adapter harness.
Unknown GPU performance is a separate gate from this known control-flow defect.

## Independently verified results

| Check | Result |
| --- | --- |
| `python tools/repository_check.py --all` | PASS: 185 tests, 4 skipped under default Python 3.14 |
| Python 3.12 installed-torch NVARC, boundaries, DDP, SDG and TRM adapter tests | PASS: 29 tests, no skips |
| Earlier outbound test-output probe | Rejected |
| Earlier incomplete-result probe | Rejected |
| Earlier empty-material probe | Rejected; tracked closed-inventory regressions also pass |
| Earlier deterministic 1,000-token DFS path | Completes with 1,001 expansions, no recursion failure |
| 300-token path with 256 expansion cap | Still produces no completion, now explicitly documented as a resource bound |
| Fixture E2E | PASS as part of tests and independently regenerated probe fixture; synthetic only |
| Strict optional ML profile on Python 3.12 | BLOCKED, exit 2: missing transformers, peft, safetensors |
| Additional TTT budget and unused-branch probes | Reproduce the first two blockers above |

The strict ML profile's refusal to call missing dependencies a pass is correct.
Actual tiny Qwen3.5 conversion/gradients and PEFT remain unverified. Docker
sandbox enforcement and real upstream TRM integration likewise retain their
documented missing-runtime/dependency gates. This review did not install
packages, launch Docker, acquire real datasets/weights or access a provider.

## Evidence and disposition

Local evidence directory:
`C:/Users/wurre/Desktop/IRIS-X/.irisx/nvarc-acceptance-4d23546/`.

- `validation.log`, `torch312.log`, `ml-profile.log` retain test results.
- `review_probes.py`, `review-probes.json` repeat the original synthetic probes.
- `additional_probes.py`, `additional-probes.json`, `unused-rank-0.log` and
  `unused-rank-1.log` retain the budget and DDP reproductions.
- `trm-spec/review.json` records accepted arguments and the independently
  checked upstream incompatibility; its synthetic checkpoint was never loaded.

Keep the current state partial. Resolve these code-level defects before another
development acceptance claim, and report environmental gates separately.
The retained improvements and passing tests remain valid evidence; neither
they nor missing GPU authority eliminate the concrete failures above.
