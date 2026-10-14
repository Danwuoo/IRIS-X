# Development Operating Model

Product engineering is the default IRIS-X track. Decision 0010's lightweight,
risk-based model remains the basis: [accepted decision](../decisions/0010-adopt-lightweight-risk-based-development.md).
Product direction remains in the [Product Scope](../product/product-scope.md);
[data and execution policy](data-and-execution-policy.md) remains applicable.

## Default loop

Use **Build–Measure–Select**: state one outcome and its check, build the smallest
reversible increment, measure it, then keep, revise or reject it. An Engineering Trial
records a baseline, intervention, workload, measures, costs, stop condition
and selection when empirical product evidence is needed. Preserve P1 contracts.

## Parallel development

Start from the [workstream guide](../workstreams/README.md). Each stream has one
current STATUS and separate branches/worktrees, environments, agent sessions and
ignored output roots. The registry is an index only. Historical trial READMEs
remain terminal evidence for their own identities, not competing current project
status pages.

The owner's 2026-10-14 instruction keeps restructuring on independent branches:
no main merge or push, no auto-merge, and no automatic merge between the stacked
PRs. PR #5 remains Draft. Use foundation -> PR 2 -> PR 3 -> PR 4 as the dependency
chain, with each Draft PR targeting its predecessor branch rather than main.
Main remains a reference, not a successful-model or green baseline. Run008 is
referenced through immutable Git URLs and is not merged into this work.
Avoid simultaneous edits to shared CLI, contracts, build, management schemas or CI.

## Routine work

Local, offline, reversible implementation, tests, documentation, refactoring and
fixture work within accepted product boundaries do not need a new decision or
repeated approval. Keep evidence proportional to risk. Navigation work must not
require rebuilding ARC, downloading archives or restoring cloud credentials.

## Gated work

An owner-authorized scope is required for product-goal, public-contract,
acceptance-threshold or promotion changes; external/provider/paid/sensitive-data
work; explicitly gated model workloads; frozen artifact identity changes; and
irreversible deletion or migration. A PR instruction does not reopen Kaggle
execution. Record a durable decision only when it must govern later work.

Independent development is not independent access to shared external resources.
Any future authorized ARC publication still needs one publisher and its exact
readback, source, process, data and clock gates. Uncertain remote writes must be
reconciled read-only, not repeated blindly. Preserve earlier attempts and charges.

## Validation and handoff

Use [test dependency classes](../../tests/README.md). Report command, environment,
commit, tested scope, failures and missing inputs separately. Keep the complete
handoff entry `python tools/repository_check.py --all`; navigation or focused CPU
passes must not be called full CI, real-model or GPU success. Preserve the
existing suite while its dependency split is implemented in a later PR.

## Unified document and development management

The [PR 2–4 plan](../plan/2026-10-14-workstream-pr2-pr4-local-development.md)
defines a repository-native document catalog, task records, generated board,
scoped validation entry and separate developer/independent reports. Implement
these incrementally with the code, not as a parallel cloud service or manual
tracker. Routine work needs one task record and a useful handoff, not a new ADR
for every edit. The detailed plan distinguishes planned interfaces from commands
that have actually been implemented. No independent verification follows merely
from a developer or subagent claiming that tests passed.

## Research track

Research is conditional: a concrete authorized question arising from product
engineering, not an obligatory prerequisite for unrelated domain work. Return a
usable method, rule or negative result to product engineering. The second line
need not wait for ARC-AGI-2 to achieve its scientific target.
