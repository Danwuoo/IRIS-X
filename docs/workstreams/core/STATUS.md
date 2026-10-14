# Core STATUS

Updated: 2026-10-14. Workstream: `core`.

## Scope

Shared P1 contracts, canonical serialization, deterministic reference evaluation,
selection, Domain Package verification, CLI and repository/build/test tooling.
This increment changes navigation and its checks, not product/runtime behavior.

## Evidence

The foundation starts from main `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`.
At the reviewed checkpoints, main and run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d`
have identical `src/`, `tests/`, `.github/` trees and `pyproject.toml`; run008's
additional run-specific tools and reviews are not merged here. This equality is
source comparison, not a passing test or operational baseline.

Use the PR's actual checks for this change. Historical test records remain in
[tests/README.md](../../../tests/README.md); no full-green claim follows from the
reference flow or the navigation suite.

## Blockers

The current wheel backend collects only flat `src/irisx/*.py` modules; editable
installation does not prove nested-package distribution. The CLI imports ARC and
Kaggle integrations at module scope. Complete tests also have historical fixture
and environment dependencies. Those issues are not repaired in this first PR.

## Next

Add non-editable installation coverage and a tested package boundary before any
nested domain migration. Split test execution by real dependencies while keeping
the old complete-suite result visible. Then establish line-b's minimum workflow.

## Boundaries

Do not change adopted contracts or frozen experiment bytes for directory cleanup.
Keep common changes in one reviewed PR; do not fork the core per domain. Do not
interpret a core or navigation pass as ARC GPU or scientific success.
