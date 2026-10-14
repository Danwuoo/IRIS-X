# line-b STATUS

Updated:2026-10-14. Workstream:`line-b` (temporary name). Task state:[board](../../management/BOARD.md).

## Scope

An independent synthetic engineering-only,non-deployable six-case label workload
now exercises specification/workload,baseline/candidate,evaluation/selection and
package build/verify through the common P1 contracts. Source:[engineering guide](../../../src/irisx/domains/line_b/README.md).
The real domain remains unassigned;this scaffold does not choose one.

## Evidence

New fixtures have distinct domain/workload/trial/case/config/evaluator identities.
The existing P1 deployment/limitations placeholder IDs are fixed shared-profile
exceptions. Reproducible bytes,unmet/missing evidence,tampering,fresh-process ARC/ML
blockers and simultaneous core/line-b output isolation have developer self-tests.
Reports and independent acceptance are separate from synthetic lookup outcomes.

## Blockers

Real workload,representative cases,quality requirements,resource budget and data
classification are not specified. Scientific/customer-domain capability and
deployment remain unverified. Independent engineering review is pending.

## Next

Follow task records through the board. Run `python tools/dev.py verify --suite line-b`
and use the actual code-path AGENTS. A future owner-defined Domain Specification
opens real-domain work separately;synthetic results do not authorize it.

## Boundaries

Use separate worktrees/environments and new ignored `.irisx/line-b/<task>/` roots.
No ARC internal imports,private fixtures,training,GPU,provider access,paid execution
or deployment. Common contracts/engine/package remain single-sourced.
