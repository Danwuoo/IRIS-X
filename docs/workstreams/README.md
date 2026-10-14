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

Owner direction on 2026-10-14 keeps this work on independent branches. Do not
merge or push to main, enable auto-merge, delete branches or move tags. PR #5
stays Draft; its main base is a comparison target, not permission to merge.
PR 2 targets the foundation branch, PR 3 targets the PR 2 branch, and PR 4 targets
the PR 3 branch. The exact branch names and checkpoints are in the
[local development plan](../plan/2026-10-14-workstream-pr2-pr4-local-development.md).
Do not merge a whole ARC experiment into line-b or maintain independently patched
copies of the common contracts. Never reset another worktree or overwrite output.

The original foundation base is main at
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
to core/CLI/build/CI must eventually exercise both domain suites; the foundation
does not pretend that test split or nested wheel support already exists.

Any future authorized external run needs its own actual identity and applicable
review. Keep one publisher for shared resources. No provider call, GPU run,
automatic retry, quota query or competition submission is part of this foundation.

## Increment sequence and unified management

The [PR 2–4 plan](../plan/2026-10-14-workstream-pr2-pr4-local-development.md)
and [Codex kickoff](../plan/2026-10-14-workstream-codex-kickoff.md) specify the
remaining implementation: packaging/CLI plus management foundations; test/CI
separation and the synthetic second line; then incremental ARC isolation.

The [document catalog](../management/documents.json) and [task records](../management/tasks/)
drive the [generated board](../management/BOARD.md). Use `python tools/dev.py status`,
`check` and `render --check`; explicit `render` refreshes the board.
The workstream registry remains navigation-only. STATUS retains scope and domain
evidence, not a duplicate task ledger. Developer handoffs remain review_ready
until an independently sourced, commit-bound review supports verification.
The management guide describes the implemented offline entry points. Suite selection
and domain boundaries are delivered in the following stacked increments.

Unchanged historical rules remain in the pinned
[pre-foundation root](https://github.com/Danwuoo/IRIS-X/blob/baaf47d4f449c534ddd4646ab9b3175bbaf1ef89/AGENTS.md).
History is a reference, not a task queue or portable execution approval.
