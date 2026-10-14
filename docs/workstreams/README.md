# Workstreams

This foundation separates the shared engineering lane from ARC-AGI-2 and an
unassigned second line. It does not create a new domain implementation or move
existing runtime files. Read the selected STATUS before editing its source.

| Stream | Current summary | Role |
| --- | --- | --- |
| Core | [STATUS](core/STATUS.md) | Common contracts, reference flow, packaging and development infrastructure |
| ARC-AGI-2 | [STATUS](arc-agi-2/STATUS.md) | Existing experiments and pinned run008 handoff |
| line-b | [STATUS](line-b/STATUS.md) | Second-line definition and future independent workload |

[registry.json](registry.json) contains only IDs, roles and repository-relative
status paths. It has no owner approval, credentials, run configuration or remote
state. Each STATUS uses Scope, Evidence, Blockers, Next and Boundaries sections.
It is the current stream summary; linked original trials/reviews keep their
original evidence and exact identities. Do not duplicate live status into README,
AGENTS, a second ledger and a registry. Update the relevant STATUS with the work.

## Working arrangement

Use one worktree, virtual environment, output root and agent session per stream.
For example, use ignored `.irisx/core/<task>/`, `.irisx/arc-agi-2/<new-task>/` and
`.irisx/line-b/<task>/` for new outputs. Existing hash-bound reconstruction paths
are exceptions: keep them unchanged. Separate Git worktrees do not isolate shared
provider accounts, notebooks, GPUs or credentials.

Common changes use a small `chore/` or `fix/` PR into main. Domain tasks use their
own `feat/` branches and integrate the common PR after review. Do not merge a
whole ARC experiment into line-b or maintain two independently patched copies of
the common contracts. Never reset another worktree or overwrite its output.

For this first increment the base is main at
`baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`. Run008 stays at the separately
preserved `cc14bd1a79aac1fe6135017c9e09d4834300675d` reference; its implementation
and private operational context are not imported. References to files absent
from this base must use the pinned GitHub URL rather than a broken relative link.

Root AGENTS explicitly routes the old flat source/tool paths. This documentation
folder is not a substitute for scoped AGENTS in future actual code directories.
When adding those directories later, add their scoped rules and tests together.

## Validation and resource boundaries

[tests/README.md](../../tests/README.md) distinguishes standalone navigation,
shared product, ARC CPU, historical reconstruction and private operational tests.
Do not download an archive or request a login merely to pass a navigation check.
Missing dependencies remain explicit; synthetic fixtures must be newly named and
reviewed test fixtures, never counterfeit original owner/readback evidence.

Navigation checks have their own workflow; the existing full workflow and its
failures are retained. A passing navigation job proves only navigation. Changes
to core/CLI/build/CI must eventually exercise both domain suites; this first PR
does not pretend that test split or nested wheel support already exists.

Any future authorized external run needs its own actual identity and applicable
review. Keep one publisher for shared resources. No provider call, GPU run,
automatic retry, quota query or competition submission is part of this foundation.

## Increment sequence

1. This PR: current entries, status routing, test dependency documentation and a
   standalone navigation regression check; preserve historical bytes and paths.
2. Next shared PR: non-editable wheel/install coverage, nested-package support,
   CLI import boundaries and explicit test selection without hiding failures.
3. Second-line increment: declare its workload, requirements and resource budget,
   then baseline/evaluation/package verification in its own scope. Only afterwards
   migrate mutable ARC modules incrementally with reconstruction checks.

Unchanged historical rules remain in the pinned
[pre-foundation root](https://github.com/Danwuoo/IRIS-X/blob/baaf47d4f449c534ddd4646ab9b3175bbaf1ef89/AGENTS.md).
History is a reference, not a task queue or portable execution approval.
