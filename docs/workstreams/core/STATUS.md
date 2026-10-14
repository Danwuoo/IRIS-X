# Core STATUS

Updated: 2026-10-14. Workstream: `core`.
Task state: [generated board](../../management/BOARD.md).
Document lifecycle: [catalog](../../management/documents.json).

## Scope

Shared P1 contracts, canonical serialization, deterministic reference evaluation,
selection, Domain Package verification, packaging, CLI routing and repository
management/validation tools. The stacked increments add reproducible nested
wheels, lazy domain execution, controlled test selection and an independent
synthetic line-b flow. WSF-04 extracts mutable ARC parser/dispatch glue while
retaining the legacy implementations at their original paths.

The [migration map](../../verification/WSF-04/MIGRATION.md) supplies the bounded
source scope and dependency exceptions. Follow the board's task record to the
plan, code checkpoint and handoff; STATUS does not duplicate task progress.

## Evidence

The synchronized foundation is `08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059`,
descended from the main comparison anchor
`baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`. PR 4 starts from PR 3 delivery
`756cd560f8d61256ed35e12c3c3637ec456c6141`. These identify engineering source,
not scientific or operational baselines.

The [WSF-02 handoff](../../verification/WSF-02/HANDOFF.md) binds nested wheel,
external-cwd non-editable installation, public CLI/import boundaries and
management self-tests to its code checkpoint. The
[WSF-03 handoff](../../verification/WSF-03/HANDOFF.md) binds inventory/runner/CI
gate and synthetic line-b evidence to its own checkpoint. Both reports retain
raw-log fingerprints, exact counts and matched baseline limitations. Their
developer/subagent checks await independent acceptance.

The WSF-04 map retains source/blob comparisons against both foundation and fixed
run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d`. Its final code/report binding
is supplied by the root integration owner's task handoff. Git equality proves
source preservation only; it does not establish reconstruction or runtime parity.

Historical foundation [navigation CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686348)
passed. Its completed
[Ubuntu / Python 3.14 aggregate job](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686421/job/115656185090)
reported 1,588 tests, 5 failures, 96 errors and 110 skips; other jobs were
cancelled. It checked synthetic merge commit
`b5d7e10d90bda1e80a3b0971f64ee7f688befafa`, without merging main. Stage-specific
local aggregates remain separately recorded in the handoffs; full CI is not green.

## Blockers

Independent commit-bound verification and remote CI matrix outcomes remain
pending. Broader ARC/public and complete legacy audits retain collection,
dependency, platform, missing-input and assertion failures. Attribution needs
matched test IDs/signatures; unmatched observations stay unclassified.

Authentic reconstruction inputs, original Linux/CPython 3.12 replay and GPU
compatibility are outside this engineering task. No other legacy helper is
proved movable under those absent inputs; retention is intentional.

## Next

Use [WSF-04](../../management/tasks/WSF-04.json) and its
[plan](../../plan/2026-10-14-workstream-pr2-pr4-local-development.md) for the
remaining acceptance and handoff route. Run the management checks and controlled
public suites described in [tests/README](../../../tests/README.md), retain
the full `--all` audit and return actual branch/code/delivery/PR identities to
the original ChatGPT conversation. Task state stays at `review_ready` until
that conversation supplies independent verification. No merge follows.

## Boundaries

Adopted contracts, admission/promotion semantics and frozen experiments retain
their bytes and identities. Common implementations remain single-sourced;
core contracts/engine/package do not import ARC or line-b implementations.
Shared CLI's explicit parser/dispatch routing is recorded in the migration map.
No run008 branch change, archive/model/evaluator download, training, Kaggle call,
GPU work, main push or tag move is part of this task. Scoped checks are not
full CI, real-domain capability or scientific success.
