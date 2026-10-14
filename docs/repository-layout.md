# Repository Layout and Workstream Boundaries

Updated: 2026-10-14. This is the workstream-foundation layout based on main
`baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`, not a migration of run008 into main.
Start at the [workstream guide](workstreams/README.md) and
[registry](workstreams/registry.json). The directory tree is still physically
shared; the first increment separates navigation and responsibilities only.

| Path | Responsibility | Current boundary |
| --- | --- | --- |
| `PRODUCT_THESIS.md` | Product direction | Adopted bytes unchanged |
| `AGENTS.md` | Short common rules and scope routing | Historical run logs addressed by pinned Git links |
| `docs/workstreams/` | One STATUS per stream and a navigation-only registry | Core, ARC-AGI-2, unassigned line-b |
| `docs/product/` | Contracts, package format and product scope | Existing contracts retained |
| `docs/development/` | Routine development and data/execution policy | Shared workflow, not run authorization |
| `docs/decisions/` | Durable decisions and historical rationale | Existing files unchanged |
| `src/irisx/` | Shared P1 code and retained ARC implementations | Flat layout and public imports unchanged |
| `tests/` | Existing suites plus standalone navigation checks | Dependency classes documented; no tests removed |
| `tools/` | Build backend, repository checker, run-specific utilities | No script moves or byte changes in this increment |
| `trials/` | Trial-specific status, source and retained outcomes | Historical paths and identities preserved |
| `research/` | Research evidence and compact reviews | Run008 continuation is on its pinned branch, not silently imported |
| `.github/workflows/` | Existing full validation plus independent navigation check | Existing full-validation workflow retained |
| `archive/` | Read-only Git-native historical catalog | Catalog and tag unchanged |
| `.irisx/` | Ignored local output and isolated workstream scratch | Not publication authority or a transferable live machine |

## Where changes belong

Common contract/CLI/build/CI changes belong to the shared lane. Existing `arc_*`,
Kaggle runners and run-specific tools belong to ARC-AGI-2; locate its current
checkpoint through [ARC STATUS](workstreams/arc-agi-2/STATUS.md), not a guessed
local path. Second-line scope and its proposed path allocation are in
[line-b STATUS](workstreams/line-b/STATUS.md); these paths are not created yet.

Do not move frozen runtime, notebook, scorer, overlay, inventory, review or
reconstruction paths for cosmetic consistency. A later migration needs an exact
before/after inventory, compatible imports where appropriate, packaging tests,
and proof that historical reconstruction still resolves its original bytes.
The current wheel builder is flat; nested packages require a separate build
change and a non-editable installation test before use.

## Historical index (not current execution authority)

Decision 0010 supplies routine risk-based development. Decision 0012 records the
closed ARC-AGI-2 Trial 001 without a locally accepted result; consult the
[Trial 001 status page](../trials/first-real-domain/README.md). Decision 0014 and
Decision 0015 preserve the distinct consumed Trial 002 smoke and its original
identities. Later experiments do not overwrite those records.

The pre-product payload remains in Git at the annotated tag
`archive/pre-product-transition-2026-09-17`, not deep-moved into `archive/`.
The code18/run005 snapshot and the run008 branch remain distinct source anchors.
See [tests/README.md](../tests/README.md) for what can be checked without private
inputs and what remains dependent or unverified.
