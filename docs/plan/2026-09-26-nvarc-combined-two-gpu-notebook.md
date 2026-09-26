# NVARC combined M2/M3 notebook development

Date: 2026-09-26
Status: owner-authorized local development; external execution is not authorized.
Implementation assignee: `gpt-6-sol`, reasoning effort `xhigh`.

## Owner direction and objective

The owner proposed running the two existing continuations in one notebook,
using two GPUs, then requested this plan under `docs/plan` and development by
GPT-6 Sol xhigh. Implement one locally staged notebook that prepares its
environment once and runs M2 source continuation and M3 teacher in separate
processes on separate GPUs. Keep local engineering progressing independently
of Kaggle startup availability.

This is the existing bounded NVARC trial scope. It does not introduce a
production runtime, a new solver, a public contract or a scientific acceptance
change. No new decision record is needed for this local implementation.

## Starting evidence and preserved state

- M2 completed eight full-parameter SFT steps and a digest-verified HF export.
  Its subsequent source stage failed before TTT on absent packaged source.
  The portable source-bundle repair is implemented on main.
- M3's last retrieved batch contains four truncated responses and no accepted
  SDG pairs. The direct-response profile and complete-stage checks exist.
- Decision 0034's `nvarc-m2-source-cont-002` and
  `nvarc-m3-teacher-small-005` have accepted version-1 receipts. Their runtime
  state remains unqueried. Do not infer a specific provider bug or zero work.
- Both existing notebook templates require four L4s while using one. Both
  model paths choose logical `cuda:0`; the teacher additionally checks that
  its process sees four GPUs. Merely concatenating the notebooks or setting
  a second GPU index is insufficient.
- Local tests already cover tiny real Qwen, source differential behavior,
  FSDP resume, installed-wheel deployment and WSL network isolation. Extend
  these facilities rather than rebuilding them.
- At planning time main contains uncommitted edits in
  `src/irisx/arc_nvarc_sdg.py`, `src/irisx/arc_nvarc_sdg_teacher.py` and
  `tests/test_nvarc_continuation.py`. They retain teacher failure causes and
  completion diagnostics. Review and preserve them; do not reset or silently
  overwrite another task's edits.

References:

- [Current trial status](../../trials/arc-agi-2-qwen35-nvarc/README.md)
- [Retrieved M2/M3 evidence](../../trials/arc-agi-2-qwen35-nvarc/m2-m3-decision-0032-terminal.md)
- [Restart receipts](../../trials/arc-agi-2-qwen35-nvarc/m2-m3-decision-0034.md)
- [Source/teacher continuation](2026-09-26-nvarc-source-teacher-continuation.md)
- [Decision 0034](../decisions/0034-restart-nvarc-without-monitoring.md)

## Authorization boundary

Develop, refactor, test, document and stage inert packages locally on main.
Use cached sources, dependencies, tokenizers and tiny locally created models.
Keep generated evidence under ignored `.irisx/` paths.

Do not make provider queries, downloads, Dataset mutations, kernel submissions,
output retrievals, real 4B generations, ARC scoring, holdout reads or teacher
calls. Do not resume monitoring or scheduled tasks. Do not upload artifacts,
push Git or modify consumed run identities and evidence. Preserve the exact
old submitted bytes and their binding checks.

Create a distinct internal combined draft identity, for example
`nvarc-m2-m3-combined-001`, with separately named M2/M3 child identities.
Its staged plan must have `approved: false`, no owner execution decision and
an unpushable draft kernel ID. All external-action allowances are zero.
Listed model-work limits describe a future proposal, not executable authority.
The generated live entry point must reject the draft before dependency
mutation, model loading or workload execution. A future owner instruction and
exact package binding are required before submission. Decisions 0033/0034
must not activate the combined draft.

## Workload retained in the proposal

| Branch | Model and input | Maximum work |
| --- | --- | --- |
| M2 | Existing compact SFT export, original training lineage, source bundle and visible task `00576224` | Zero SFT; one demonstration-only LoRA step; four generation calls; 64 new tokens and 128 DFS expansions per call; existing bounded ranking |
| M3 | Pinned full-vocabulary Qwen3.5-4B; public parents `833966f4` and `6150a2bd`; unchanged direct-response prompts | Four dependent teacher calls; thinking disabled; 28,160 reserved tokens; no retries |

M3 stage input/output ceilings remain 4,096/512, 4,096/1,024,
4,096/3,072 and 8,192/3,072. M2 retains the exact export digest
`sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`.
Reuse the exact source/material digests from the existing plans. Do not copy
their consumed approval fields into new identities.

Use a single proposed 1,800-second notebook deadline including shared setup,
both loads, workloads and a terminal-packaging reserve. Retain the 300-second
setup ceiling and explicit process cleanup bounds. No branch gains time,
calls or tokens because the other branch finishes early or fails.

## Implementation

### 1. Shared preparation and observable startup

Add a separate combined staging tool and notebook template. Install the union
of pinned dependencies once, before launching either worker; include M2's
PEFT requirement. Preserve the offline incompatible-torchao repair. Verify
the embedded payload, source bundle, tokenizer/material manifests and existing
Dataset mount rules. Use only exact owner-qualified or explicit legacy mount
paths; ambiguous/missing mounts fail before model work.

Record startup events from the earliest writable output point: payload
validation, hardware inventory, mount resolution, dependency setup, source
verification, each worker launch, model-ready and terminal outcome. Each
event identifies its branch, elapsed time and package/plan binding. Preserve
bounded exception details and return codes even for early failures; do not
dump environment variables or credentials into evidence.

Separate shared prerequisites from branch prerequisites. A shared preparation
failure stops both. A branch-specific input/load/work failure terminalizes
that branch while the independent branch can continue within the global
deadline. Avoid installing dependencies concurrently in the same environment.

### 2. Two assigned devices and isolated workers

The new draft proposes exactly two active, distinct BF16-capable L4 devices,
each satisfying the existing minimum-memory checks. Inventory all allocated
devices and record the chosen indices and UUIDs. Support a larger allocation
with only those two devices assigned. Do not claim Kaggle offers a two-L4
allocation; provider resource selection remains unresolved until a future
execution proposal. Do not silently substitute T4s or weaken model precision.

Launch separate Python processes with `CUDA_VISIBLE_DEVICES` set before
Torch/CUDA initialization. Each worker sees one logical `cuda:0`; validate
its assignment against the parent hardware record and bound combined plan.
Reject duplicate assignments and inconsistent identities. Keep existing
four-device checks intact for historical standalone profiles; add an explicit
combined profile rather than a global bypass or permissive environment flag.

Use bounded model-ready signaling to stagger model loading and reduce transient
host-RAM/disk pressure, then permit workload overlap. Bound every readiness
wait. A worker that fails before readiness must not leave its sibling waiting
forever. Device-memory isolation does not isolate host RAM, disk or the whole
notebook; document these shared-resource limits and report memory where
available. Preserve the model, algorithms and generation settings.

### 3. Supervision and independent evidence

Give M2 and M3 separate output directories, logs, call ledgers and result
files under the combined run. Record the parent/child identities and their
plan/material digests without rewriting the old result contracts or lineage.
Never start full SFT, copy optimizer-state claims or train on teacher outputs.

The parent must drain logs safely, observe both child processes and reap their
process groups after exit/timeout. Enforce a global monotonic deadline and
retain enough time for terminal records. Do not abort healthy sibling work
merely because the other branch exits nonzero. Do stop both on global timeout
or a shared prerequisite failure. Never retry a failed/reserved generation or
restart a consumed child automatically.

Always produce an atomic aggregate terminal manifest when writable, including
branch outcome, last phase, error, assigned device, artifact digests, reserved
and actual counters when known, and observed wall time. Distinguish unknown
counts from zero. Represent complete, partial, failed and timed-out outcomes
without treating partial completion as success. Independently validate child
artifacts before claiming complete; absent/truncated/mismatched results cannot
be promoted by a zero process return code. Keep outputs truth-free.

### 4. Offline package verification

Build a deterministic combined review package with an inspectable inert plan,
notebook, runtime wheel, source bundle and exact payload inventory. Verify
parent/child bindings, closed file inventory, separate budgets, distinct GPU
assignments, deadline and historical identity exclusion. Store large/local
materials by their existing verified references; no new Dataset is needed
for local preparation.

Provide one documented offline command to stage the draft and one to verify
it. Preserve old package builders and their regression behavior. Prefer small
internal helpers shared by the new paths over a broad runtime redesign.

## Validation and acceptance

1. Meaningful CPU process tests exercise two successful children, one failing
   before model-ready, one failing during work, one hanging, a shared setup
   failure, global timeout and artifact tampering. Verify the healthy sibling
   is retained, waits are bounded, children are reaped and no retry occurs.
2. Offline hardware tests verify two unique assignments, a four-device
   inventory with only two selected, logical-device mapping and rejection of
   missing/duplicate/wrong-type devices. These are simulated hardware tests,
   not GPU runtime evidence.
3. Build/install the actual wheel in isolation. Exercise the combined worker
   orchestration with tiny real Qwen where applicable, and saved-response
   teacher replay through existing stage validation. Do not replace tiny-model
   evidence with mocks or label replay as new teacher output.
4. Extend the cached WSL deployment test where it can validate the new entry
   points with checkout hidden and network disabled. Retain the actual local
   dependency versions; do not claim equivalence to Kaggle's image.
5. Negative preflights reject stale decisions, historical identity reuse,
   changed materials, extra files, increased budgets and live execution of
   the inert draft. Ensure generated notebooks compile.
6. Run `python tools/repository_check.py --all`. Run the existing strict ML
   profile with `.irisx/nvarc-ml-venv/Scripts/python.exe` if that cached runtime
   remains available. Missing prerequisites are an explicit blocked check,
   never a passing/skipped substitute for required ML evidence. Do not acquire
   dependencies over the network to resolve a missing local prerequisite.

Completion means a tested local implementation, deterministic inert package,
verified failure isolation and an updated trial status/reproduction table.
It does not establish two-GPU runtime fit, successful 4B candidate ranking,
accepted teacher yield or ARC quality. Record those as pending GPU acceptance.

## Delivery and handoff

Implement on main, preserving the existing dirty changes. Keep changes focused
on this plan. Document commands, retained evidence paths, test outcomes and
remaining GPU checks in the trial status page and this plan's implementation
record. Review and commit the relevant completed local changes after checks;
do not include unrelated edits or generated `.irisx` outputs. Do not push.

The assigned GPT-6 Sol xhigh developer should carry implementation through
offline validation and report concrete completion or blockers. No further
agents are needed by default. The coordinating task reviews the final diff
and evidence before reporting the handoff result to the owner.

## Implementation record

The distinct inert `nvarc-m2-m3-combined-001` plan, staging/preflight tools,
notebook template, explicit device profile, workers and supervisor are
implemented. The [trial implementation record](../../trials/arc-agi-2-qwen35-nvarc/combined-notebook-001.md)
retains reproduction commands, exact materials, final package bindings,
validation results and pending GPU checks. Historical standalone guards and
submitted templates remain unchanged; the original dirty teacher diagnostics
were preserved and integrated.

CPU tests cover success, pre-ready/work failure, hanging readiness, global
timeout, descendant cleanup, injected cleanup failure, large-log draining,
artifact tampering and contradictory counters. Simulated hardware tests cover
two selected devices, larger allocation, logical mapping and rejected
assignments. The actual isolated wheel and WSL paths run tiny real Qwen source
work alongside validated saved-response replay, with zero teacher calls.

The full strict profile passed 32 tests and final affected deployment/package
checks passed five tests. Final package/preflight and WSL deployment also
passed; repository validation passed 236 tests with four existing optional
skips. Exact dispositions are retained in the linked record.
The draft has no live
activation path: new owner direction and a reviewed exact package-binding
change are required. Two-L4 fit, GPU UUID representation and Kaggle image
behavior remain unverified. No provider request or remote Git push occurred.
