# Workstreams

Start at [docs/README](../README.md), then the [generated board](../management/BOARD.md)
and the selected task. Read the applicable AGENTS and stream STATUS before
editing source. Task records supply engineering state; STATUS supplies scope,
evidence, limitations and the route to original research.

| Stream | Reading entry | Implementation scope |
| --- | --- | --- |
| Core | [STATUS](core/STATUS.md) | Shared contracts, reference flow, packaging, CLI routing and repository tooling |
| ARC-AGI-2 | [STATUS](arc-agi-2/STATUS.md) → [RESEARCH](arc-agi-2/RESEARCH.md) | Mutable CLI facade at `src/irisx/domains/arc_agi_2/`; retained legacy modules and run tools keep their original paths |
| line-b | [STATUS](line-b/STATUS.md) | Independent synthetic engineering fixture at `src/irisx/domains/line_b/`; real domain remains unassigned |

[registry.json](registry.json) remains a navigation index containing stream IDs,
roles and repository-relative STATUS paths. It contains no task states,
credentials, run configuration or execution approval. Each STATUS uses Scope,
Evidence, Blockers, Next and Boundaries; original trials and research retain
their evidence and identities.

## Working arrangement

Use separate worktrees, virtual environments, output roots and agent sessions.
New generated outputs belong under ignored `.irisx/core/<task>/`,
`.irisx/arc-agi-2/<task>/` or `.irisx/line-b/<task>/`. Keep historical hash-bound
reconstruction paths unchanged. Git worktrees do not isolate shared provider
accounts, notebooks, GPUs or credentials.

The [local plan](../plan/2026-10-14-workstream-pr2-pr4-local-development.md)
defines the provisional stack: PR 2 targets the foundation branch, PR 3 targets
PR 2, and PR 4 targets PR 3. Each next stage starts from its predecessor's
delivery commit, including its handoff. PR #5 and the three delivery PRs stay
Draft; main and run008 remain separate preserved branches. No merge, main push,
auto-merge, force push, reset, branch deletion or tag move follows from this work.

Shared contracts, engine and package implementations remain single-sourced.
Shared CLI imports the parser-only ARC facade and routes a selected ARC command;
the facade calls retained legacy ARC/Kaggle implementation paths. Core modules
do not import domain implementations, and the two domain lines do not import
each other. The [bounded migration map](../verification/WSF-04/MIGRATION.md)
records this exception, original consumers, path/blob pins and intentionally
retained helpers. Scoped AGENTS at actual domain source paths govern new code;
this documentation directory does not implicitly govern those paths.

## Single management and verification loop

The [document catalog](../management/documents.json) is the metadata source;
[task records](../management/tasks/) supply task state and dependencies;
[BOARD](../management/BOARD.md) is generated from them. Use the
[management guide](../management/README.md) for the complete routine loop:
document entry → board → task → plan → scoped code → named handoff. Do not
hand-edit a second progress ledger in README or STATUS.

```sh
python tools/dev.py status
python tools/dev.py check
python tools/dev.py render --check
python tools/dev.py context --task WSF-04
python tools/dev.py verify --suite core
python tools/dev.py verify --suite arc-unit
python tools/dev.py verify --suite line-b
```

`check` and `render --check` are read-only. Explicit `render` updates the marked
board. Suite selection reads the [static inventory](../../tests/inventory.json)
before importing tests and produces named reports in fresh ignored roots. See
[test guidance](../../tests/README.md) for the public smoke surface, broader
`arc-unit-audit`, distribution checks and blocked reconstruction/native suites.
The retained complete entry is `python tools/repository_check.py --all`.
Public smoke success, a red legacy audit and blocked authentic inputs remain
separate outcomes; CI matrix and independent acceptance need their own evidence.

Developer handoffs and implementing subagent checks establish self-review.
Tasks remain `review_ready` until a separately sourced review binds the actual
implementation commit. Reports must name failures, skips, blocked inputs and
unverified scope; a generated view cannot establish human acceptance.

## Research and execution boundaries

ARC STATUS → RESEARCH → R1–R5 routes readers to the original question,
method assessments, results and current SFT256/RL/extra-SFT experiment.
Historical direct-grid/program/feedback-repair comparisons and modified-input
BASE/TTT results keep their original roles and denominators. `arc-next-line` is
ARC research and does not assign line-b's domain.

The foundation is fixed at `08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059`.
Run008 is separately fixed at `cc14bd1a79aac1fe6135017c9e09d4834300675d`;
newer run008-only paths are commit-pinned references, not imported runtime.
Unchanged historical rules remain recoverable at the
[pre-foundation root](https://github.com/Danwuoo/IRIS-X/blob/baaf47d4f449c534ddd4646ab9b3175bbaf1ef89/AGENTS.md).
History and source availability do not reopen consumed execution scope.

No model, evaluator input, transfer archive or credential is needed for this
engineering loop. No Kaggle/provider call, training, GPU run, quota query,
automatic retry or competition submission is authorized. Future execution
requires its actual identity, publisher reconciliation and applicable reviews.
