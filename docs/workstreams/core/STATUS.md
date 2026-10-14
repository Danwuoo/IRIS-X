# Core STATUS

Updated: 2026-10-14. Workstream: `core`.

## Scope

Shared P1 contracts, canonical serialization, deterministic reference evaluation,
selection, Domain Package verification, CLI and repository/build/test tooling.
The foundation and this planning increment change navigation and development
instructions, not product/runtime behavior. Main integration is not authorized.

## Evidence

The foundation starts from main `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`.
At the reviewed checkpoints, main and run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d`
have identical `src/`, `tests/`, `.github/` trees and `pyproject.toml`; run008's
additional run-specific tools and reviews are not merged here. This equality is
source comparison, not a passing test or operational baseline.

Foundation implementation `76809c05c9d51de4a9d19e99c09e1dbd70edc9f9` passed
[navigation CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686348).
The four repository-check steps in offline-validation passed. The completed
[Ubuntu / Python 3.14 aggregate job](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686421/job/115656185090)
reported 1,588 tests, 5 failures, 96 errors and 110 skips; the other jobs ended
cancelled. That PR run checked the synthetic merge commit
`b5d7e10d90bda1e80a3b0971f64ee7f688befafa`; main was not merged.
These are historical observations for that head, not this planning commit's
checks or a matched before/after baseline. Full CI is not green.

## Blockers

The wheel backend collects only flat Python modules; editable installation does
not prove nested distribution. CLI imports ARC/Kaggle implementations at module
scope. Aggregate tests mix setup/dependency gaps, missing historical fixtures,
missing test/reference files and assertion failures. Their attribution needs
matched test-level comparison, not blanket inherited-error classification.
The unified management tooling and physical package/test separation are pending.

## Next

Follow the [PR 2–4 local development plan](../../plan/2026-10-14-workstream-pr2-pr4-local-development.md)
and [kickoff prompt](../../plan/2026-10-14-workstream-codex-kickoff.md).
Implement on stacked independent branches: packaging/CLI and management skeleton,
then test/CI separation and synthetic line-b flow, then mutable ARC isolation and
management onboarding. Developer reports stop at review_ready until independent
commit-bound verification. No merge is part of these increments.

## Boundaries

Do not change adopted contracts or frozen experiment bytes for directory cleanup.
Keep the shared implementation single-sourced; do not fork the core per domain.
Do not download run008 packages or restore cloud execution for this work.
Do not interpret scoped checks as full CI, ARC GPU or scientific success.
