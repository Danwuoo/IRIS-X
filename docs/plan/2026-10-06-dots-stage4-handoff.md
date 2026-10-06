# Stage 4 development handoff to dots / Astra ultra

Owner direction and current authority: [Decision 0061](../decisions/0061-transfer-stage4-development-to-dots.md).
This is an implementation handoff, not a new research-only assignment.

## Start here

1. Use Astra ultra in the owner's dots built-in thread. Clone/fetch
   `https://github.com/Danwuoo/IRIS-X.git`, including archive tags and history,
   and use the handoff commit supplied with the companion ZIP. Verify the ZIP's
   external SHA-256 and its member manifest before extracting at checkout root.
2. Read this plan, Decision 0061, the incoming Astra research under
   `.irisx/stage4-research-incoming-20261006-001/`, and the latest controller
   acceptance at `.irisx/control-review-e10-validation-002/review.json`.
   The research ZIP/backlog's old research-only and wait instructions are
   historical; the owner's new authorization governs this continuation.
3. Read `docs/development/nvarc-phase-telemetry.md`,
   `nvarc-output-lifecycle.md`, `nvarc-verification-schedule.md` and
   `arc-offline-evaluation.md`, plus `research/stage4-e10/REPAIR_001.md`.
4. Rebuild the environment for the cloud OS. Do not copy Windows virtualenvs.
   The companion includes environment versions, selected pinned source, data,
   evidence and reacquisition metadata. Existing absolute Windows paths are
   historical: make a new relocated config rather than altering frozen bytes.
   Keep evaluator materials out of solver workers and all GPU outbound bundles.

## Accepted baseline

Implementation commit: `13c03bede7c33ad698912e0fc7cb4ae996e76c02`.
E00 telemetry/budget contracts and E01 atomic output/recovery are accepted.
E10 deferred verification and caller-owned allocation repair are accepted for
local engineering. The independent controller ran 73 focused tests and 13
negative replay mutations; latest full observed validation passed 625 unit
tests plus three validator tests, with 370 retained artifact hashes checked.
The earlier unobserved cleanup failure and invalid observer run remain frozen;
the original cleanup failure cause is unknown. A later PASS is not proof of
a flake. Windows-specific cleanup still needs appropriate cloud-OS coverage.

E10 has not yet passed a real GPU screen or demonstrated a quality gain.
Real coordinator allocation transport and deployable packaging remain pending;
the CLI fails closed without the independent caller allocations. Synthetic
replay consistency is not physical GPU timing attestation.

Stage 3 official submission `56840442` ended `Notebook Threw Exception` with
public/private scores null, not zero; cause remains unknown. No valid official
score or >85 claim exists. The retained public comparison is BASE pass@2
5/172 versus TTT128 10/172 (six gains, one loss). Parent wall times are
1290.418 versus 7896.522 seconds. These are exposed public development data.
The NVARC variant has 120 tasks/172 tests; canonical upstream has 120/167.
Never mix these denominators or reinterpret public performance as official.

The current published solver is Qwen3-4B SFT139:
`sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`.
It is distinct from the historical Qwen3.5 compact experiments. Verify exact
material digests and current availability when acquiring/mounting resources.

## Parallel work and integration

The coordinator owns integration, execution budget, scientific comparison and
acceptance. Use subagents with separate branches/worktrees and clear file
ownership; review before integration and serialize shared-schema changes.
Do not let concurrent workers overwrite main or share mutable runtime state.
An independent reviewer should inspect claims, failures, source/truth boundaries
and resource evidence rather than trusting an implementer's PASS summary.

Open these complementary lanes, respecting dependencies:

- Runtime lane: finish E10 allocation transport, exact packaging and frozen
  development manifest; verify interleaved/deferred parity, then run a bounded
  private GPU comparison. The inert E10 screen proposes 24 tasks, two arms and
  two repeats (96 task-runs); finalize measurable caps and quota before launch.
- Solver lane: E20 minimal object/geometry DSL with bounded search and a neutral
  candidate/provenance interface. Preserve NVARC-specific view semantics; do
  not pretend a DSL result passed eight native verification views. Measure
  complementary solved tasks and union coverage before adding a learned router.
- Evaluation/reliability lane: independently audit exposure, denominators,
  output finalization, replay, fault cases, resource feasibility and integration.
  Preserve failures and test meaningful invariants, not just implementation.

After the E10 runtime comparison, evaluate E12 TTT64/128 and E11 DFS0.2/0.1
with other factors fixed. Implement shared configuration changes serially or
behind reviewed interfaces. E21 program synthesis, E22 larger open reasoner,
E30 alternative-model ensemble and E40 synthetic data/training are conditional
branches from the Astra backlog; prioritize measured benefit and feasibility.
Do not stop at the end of this list's first task, and do not implement every
speculative branch solely to mark it complete. Continue until the readiness
conditions below are supported, or all useful work faces a genuine blocker.

## Validation and GPU practice

For local CPU checks set `PYTHONPATH=src`, `PYTHONHASHSEED=0`,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`,
`CUDA_VISIBLE_DEVICES=` and
`IRIS_NATIVE_CODE_ONLY_DIR=<checkout>/.irisx/public-eval-analysis-20261005-001/verified-source`.
Use a suitable Python 3.12 environment with the included version inventory;
validate OS-specific dependency differences explicitly. Run
`python tools/repository_check.py --all` before integrated handoff and retain
commands, environment, exits, failures/skips and artifact digests. Do not run
separate full suites concurrently or repeatedly rerun unchanged code for green.

Kaggle authentication is supplied by the owner/cloud environment; never copy
credentials from this handoff or print tokens. Free private GPU use, necessary
private staging and measured development scoring are authorized by Decision
0061. Bound each run, use fresh identities for changed bytes, retain receipts,
back off monitoring, retrieve terminal evidence deliberately and verify it.
Repair ordinary code/transport problems and continue under that standing scope.
Check available quota/hardware rather than assuming four L4s or a session limit.
Do not restore old timers or resume consumed notebooks. Do not use hidden truth.

## Official-scoring readiness

Deliver a selected, versioned candidate with exact source/model/config digests,
candidate selection rationale and honest baseline/ablation/coverage measures;
reproducible build and a private GPU completion/resource check; official-format
output validation and recoverable finalization; licenses/exposure/current-rule
checks; immutable outbound package and exact CLI submission commands. Include
all unresolved reliability or generalization risks. No development metric can
predict or guarantee the official >85 objective. E90 is the scoring handoff:
stop before submitting to the competition, then report what official scoring
will decide. Do not stop earlier merely to request routine task permission.

## Companion archive

The archive restores selected ignored paths under `.irisx/` and includes a
per-file SHA-256 manifest, restore/verification instructions, environment
inventory and omitted-large-assets metadata. It includes evaluator answers and
diagnostics for local assessment, so it is **not** a Kaggle runtime Dataset or
truth-free outbound package. Keep it private to the development workspace.
Historical source snapshots may include answer lookup code; use the separate
three-file code-only fixture for native tests and review any selected sources.
Large reacquirable weights/corpora, installed environments, credentials and
unrelated historical outputs are intentionally omitted. The archive records
these omissions and retained acquisition metadata rather than claiming that
every old experiment can be reproduced without fetching its assets.
