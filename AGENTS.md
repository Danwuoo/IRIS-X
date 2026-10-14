# IRIS-X Repository Governance

## Start with the workstream, not an old run log

Product direction remains [PRODUCT_THESIS.md](PRODUCT_THESIS.md). Read the
[workstream guide](docs/workstreams/README.md) and the selected stream's STATUS
before changing its files. The [registry](docs/workstreams/registry.json) is a
navigation index, not an execution configuration or an authorization token.

| Work | Status / scope |
| --- | --- |
| Shared contracts, packaging, CLI, repository tooling | [Core](docs/workstreams/core/STATUS.md) |
| ARC-AGI-2 source, trials, research and run-specific tools | [ARC-AGI-2](docs/workstreams/arc-agi-2/STATUS.md) |
| Second line, not yet assigned a domain | [line-b](docs/workstreams/line-b/STATUS.md) |

These routes apply to the existing flat source and tool paths too. A guide under
`docs/` is not an automatically inherited code-directory instruction. Read any
narrower AGENTS at the actual path being edited. Physical package separation is
not implemented by this documentation change.

## Working rules

Use Decision 0010's routine lane for local, offline, reversible implementation,
tests, documentation and refactoring within the accepted product scope. State
one outcome and its check; do not create a decision record for ordinary work.
Explicit current owner direction and applicable narrower instructions govern
the task. Historical plans and consumed approvals do not restart work.

Shared changes use a small common PR; domain work must not depend on another
line's private implementation or operational fixtures. Use separate worktrees,
virtual environments, agent sessions and ignored output roots. Do not edit the
same shared file concurrently across lines. See the workstream guide for the
integration sequence; no automatic merge, provider call or run follows.

Preserve adopted thesis bytes, public contracts, acceptance thresholds and frozen
source/notebook/scorer/manifest identities. Do not rename, reformat or replace a
hash-bound artifact with a compatibility shim. Preserve previous failures,
unknown states, denominators, clocks and physical charges. Changed runtime bytes
need a distinct identity and their applicable reviews, not reused approval.

Secrets, account state, raw provider receipts, private conversations, evaluator
answer bodies, model weights and generated archives do not belong in Git.
Keep generated work in ignored `.irisx/`, separated by stream. Keep evaluator-only
inputs isolated from solver, training and prompt contexts. Follow the
[data and execution policy](docs/development/data-and-execution-policy.md).

Product/contract/threshold/promotion changes, frozen-identity changes, external
provider or paid/sensitive-data work and irreversible changes require the
applicable explicit owner scope. A GitHub PR request permits its sanitized Git
changes, not Kaggle publication, training, resource purchases or competition
submission. Do not infer execution authority from repository access or a registry.
Before future authorized ARC execution, preserve single-publisher reconciliation,
exact source/version/readback and process/data/scorer gates. Consult the pinned
ARC handoff, rebind the destination environment, and never blindly retry an
uncertain remote write. This foundation does not reopen a consumed run.

## Historical boundaries (index, not a task queue)

Decision 0011 and Decision 0013 preserve distinct run-002/run-003 identities.
Decision 0012 closes Trial 001 as `inconclusive-no-promotion`; its terminal page is
[trials/first-real-domain/README.md](trials/first-real-domain/README.md).
Decision 0014 and Decision 0015 preserve the consumed Trial 002 smoke allowance:
no further Trial 002 external execution follows from it. Decision 0016 and the
later prompt-pilot decisions remain scoped lineage, not second-line instructions.
The P2 admission snapshot remains historical blocked-state evidence, never an
authorization token. Preserve the code18/run005 snapshot tag and all later
run006/run007/run008 sources and evidence; none is promoted by this PR.

The previous root guidance remains byte-for-byte recoverable in Git:
[main before this foundation](https://github.com/Danwuoo/IRIS-X/blob/baaf47d4f449c534ddd4646ab9b3175bbaf1ef89/AGENTS.md)
and [run008 checkpoint](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/AGENTS.md).
Read their relevant provenance when resuming that work; do not execute their old
"Active" sections merely because they are present. The existing `archive/`
catalog and annotated historical tag retain their original meaning and bytes.

## Validation

Use [tests/README.md](tests/README.md) for dependency classes and honest result
reporting. Navigation-only checks need Python and this checkout, not a package,
model, private fixture, login or archive download. The full handoff entry remains
`python tools/repository_check.py --all`; focused success is not full CI success.
Missing historical inputs remain visible failures/blockers. Never manufacture
old approval, observations or fixtures, delete tests, or edit frozen evidence to
make a check green. CPU results are not GPU validation or scientific efficacy.
