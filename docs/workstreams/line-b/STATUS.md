# line-b STATUS

Updated: 2026-10-14. Workstream: `line-b` (temporary name).

## Scope

Reserve an independent second development line alongside ARC-AGI-2. The owner
has not yet specified its domain, workload, acceptance criteria or backend.
Do not assume ARC-AGI-3. This PR creates only an entry point, not a domain package,
model implementation, ready-to-run branch or successful experiment.

## Evidence

The shared entry and navigation checks do not require run008 archives, authentic
historical inputs, GPU, credentials or a provider account. There are no line-b
workload or scientific results. The common P1 fixture is not line-b validation.

## Blockers

The real domain/workload, representative cases, quality requirements, resource
budget and data classification remain unspecified. Nested package support and
CLI separation belong to the next common PR. Physical source/test isolation is
not yet implemented by this navigation foundation.

## Next

Write a small Domain Specification: actual task inputs/outputs, a baseline,
measures and acceptance/stop criteria, data boundaries and permitted resources.
Then implement baseline -> evaluation -> package/verify independently of ARC.
New source may later live under `src/irisx/domains/<chosen-domain>/`, with matching
scoped AGENTS and tests, only after distribution and import boundaries are tested.
Do not create placeholder production modules merely to fill a proposed tree.

## Boundaries

Use its own worktree, environment and ignored `.irisx/line-b/<task>/` outputs.
Do not import ARC internals, reuse ARC private fixtures or consume ARC run clocks.
Common fixes return to the shared lane. An unspecified domain does not authorize
new provider access, training, paid resources, sensitive-data use or deployment.
Progress does not depend on ARC attaining a scientific target.
